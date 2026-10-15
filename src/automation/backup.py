"""CareerOS Database Backup and Restore Manager.

Provides safe SQLite backup creation using SQLite's backup API or vacuum copy,
retention pruning, and backup validation/restore.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from src.database.connection import DatabaseConnection
from src.utils.logger import get_logger

logger = get_logger("automation.backup")


class BackupManager:
    """Manages database snapshots, backups, and restores."""

    def __init__(self, db: DatabaseConnection, backup_dir: Optional[str] = None):
        self.db = db
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = Path(settings.project_root) / "data" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, label: Optional[str] = None) -> Optional[Path]:
        """Create a timestamped SQLite database backup file.

        Uses SQLite online backup API to ensure snapshot consistency even while
        the app is open.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"careeros_backup_{timestamp}"
        if label:
            clean_label = "".join(c for c in label if c.isalnum() or c in ("-", "_"))
            filename = f"{prefix}_{clean_label}.db"
        else:
            filename = f"{prefix}.db"

        target_path = self.backup_dir / filename

        try:
            # Source SQLite connection
            with self.db.transaction() as src_conn:
                # Open destination connection
                dst_conn = sqlite3.connect(str(target_path))
                try:
                    # Online backup ensures point-in-time consistency
                    src_conn.backup(dst_conn)
                    dst_conn.close()
                except Exception:
                    dst_conn.close()
                    if target_path.exists():
                        target_path.unlink()
                    raise

            logger.info("Created database backup: %s (%d bytes)", target_path.name, target_path.stat().st_size)
            return target_path
        except Exception as e:
            logger.error("Failed to create database backup: %s", e)
            return None

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all existing backups sorted newest first."""
        backups = []
        if not self.backup_dir.exists():
            return backups

        for f in self.backup_dir.glob("*.db"):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "path": str(f.resolve()),
                "size_bytes": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 1),
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp": stat.st_mtime,
            })

        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups

    def prune_backups(self, max_keep: int = 10) -> int:
        """Keep only the most recent N backups and remove older ones."""
        backups = self.list_backups()
        if len(backups) <= max_keep:
            return 0

        to_remove = backups[max_keep:]
        removed_count = 0
        for b in to_remove:
            try:
                Path(b["path"]).unlink(missing_ok=True)
                removed_count += 1
                logger.info("Pruned old backup: %s", b["filename"])
            except Exception as e:
                logger.warning("Could not remove old backup %s: %s", b["filename"], e)

        return removed_count

    def restore_backup(self, backup_path: str) -> bool:
        """Restore database from a backup file.

        Validates the backup file with PRAGMA integrity_check before restoring.
        """
        p = Path(backup_path)
        if not p.exists():
            logger.error("Backup file not found: %s", backup_path)
            return False

        # Validate backup file
        try:
            test_conn = sqlite3.connect(str(p))
            cursor = test_conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            test_conn.close()
            if not result or result[0] != "ok":
                logger.error("Integrity check failed for backup %s: %s", p.name, result)
                return False
        except Exception as e:
            logger.error("Failed to validate backup %s: %s", p.name, e)
            return False

        # Restore online using backup API
        try:
            src_conn = sqlite3.connect(str(p))
            with self.db.transaction() as dst_conn:
                src_conn.backup(dst_conn)
            src_conn.close()
            logger.info("Successfully restored database from %s", p.name)
            return True
        except Exception as e:
            logger.error("Failed to restore database from %s: %s", p.name, e)
            return False
