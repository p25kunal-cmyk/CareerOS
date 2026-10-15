"""CareerOS Automation Scheduler and Task Runner.

Provides scheduled and manual execution of background tasks:
- Automated database backups with retention policies
- Scheduled job discovery runs with failure isolation
- Follow-up reminder scanning for active applications
- System health diagnostics and integrity verification
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.settings import settings
from src.database.connection import DatabaseConnection
from src.automation.backup import BackupManager
from src.jobs.engine import JobDiscoveryEngine
from src.tracker.repository import TrackerRepository
from src.utils.logger import get_logger

logger = get_logger("automation.scheduler")


class AutomationRepository:
    """Database repository for logging and tracking automation runs."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def log_run_start(self, task_type: str, task_config: Optional[Dict[str, Any]] = None) -> str:
        """Record the start of an automation task."""
        run_id = str(uuid.uuid4())
        config_json = json.dumps(task_config or {})
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO automation_runs (
                    id, task_type, task_config, status, started_at,
                    items_processed, items_added, items_updated
                ) VALUES (?, ?, ?, 'running', datetime('now'), 0, 0, 0)
                """,
                (run_id, task_type, config_json),
            )
        logger.info("Started automation task %s (%s)", run_id, task_type)
        return run_id

    def log_run_completion(
        self,
        run_id: str,
        status: str = "completed",
        items_processed: int = 0,
        items_added: int = 0,
        items_updated: int = 0,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Record completion or failure of an automation task."""
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE automation_runs SET
                    status = ?,
                    completed_at = datetime('now'),
                    items_processed = ?,
                    items_added = ?,
                    items_updated = ?,
                    result_summary = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (
                    status,
                    items_processed,
                    items_added,
                    items_updated,
                    result_summary,
                    error_message,
                    run_id,
                ),
            )
        logger.info(
            "Completed automation task %s status=%s added=%d updated=%d",
            run_id, status, items_added, items_updated,
        )

    def list_runs(self, limit: int = 25) -> List[Dict[str, Any]]:
        """List historical automation runs newest first."""
        rows = self.db.execute(
            """
            SELECT * FROM automation_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in rows]

    def get_recent_run(self, task_type: str) -> Optional[Dict[str, Any]]:
        """Get the most recent run for a specific task type."""
        row = self.db.execute_one(
            """
            SELECT * FROM automation_runs
            WHERE task_type = ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (task_type,),
        )
        return dict(row) if row else None


class AutomationScheduler:
    """Background automation manager and task coordinator."""

    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.repo = AutomationRepository(db)
        self.backup_mgr = BackupManager(db)
        self.discovery_engine = JobDiscoveryEngine(db)
        self.tracker_repo = TrackerRepository(db)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval_minutes = 60
        self._stop_event = threading.Event()

    # ── Task Executors ────────────────────────────────────────────

    def execute_backup(self, max_keep: int = 10, label: str = "auto") -> Dict[str, Any]:
        """Execute automated database backup and prune old backups."""
        run_id = self.repo.log_run_start("backup", {"max_keep": max_keep, "label": label})
        try:
            backup_path = self.backup_mgr.create_backup(label=label)
            if not backup_path:
                raise RuntimeError("Backup creation returned None")

            pruned = self.backup_mgr.prune_backups(max_keep=max_keep)
            size_kb = round(backup_path.stat().st_size / 1024, 1)
            summary = f"Backup created: {backup_path.name} ({size_kb} KB). Pruned {pruned} old backups."

            self.repo.log_run_completion(
                run_id=run_id,
                status="completed",
                items_processed=1,
                items_added=1,
                items_updated=pruned,
                result_summary=summary,
            )
            return {"status": "success", "backup_file": backup_path.name, "summary": summary}
        except Exception as e:
            err = str(e)
            logger.error("Automated backup failed: %s", err)
            self.repo.log_run_completion(
                run_id=run_id,
                status="failed",
                error_message=err,
                result_summary="Backup creation failed",
            )
            return {"status": "failed", "error": err}

    def execute_job_discovery(self) -> Dict[str, Any]:
        """Execute automated job discovery across enabled plugins."""
        profile = self.tracker_repo.get_default_profile()
        profile_id = profile.id if profile else None
        profile_name = profile.name if profile else "System Default"

        run_id = self.repo.log_run_start("job_discovery", {"profile": profile_name})
        try:
            report = self.discovery_engine.run_discovery(profile_id=profile_id)
            summary = (
                f"Discovered {report.items_processed} jobs across {len(report.sources_attempted)} sources. "
                f"New: {report.items_added}, Updated: {report.items_updated}, Failed Sources: {len(report.sources_failed)}"
            )

            status = "completed" if not report.sources_failed else "completed_with_warnings"
            self.repo.log_run_completion(
                run_id=run_id,
                status=status,
                items_processed=report.items_processed,
                items_added=report.items_added,
                items_updated=report.items_updated,
                result_summary=summary,
            )
            return {
                "status": "success",
                "total_discovered": report.items_processed,
                "total_added": report.items_added,
                "summary": summary,
            }
        except Exception as e:
            err = str(e)
            logger.error("Automated job discovery failed: %s", err)
            self.repo.log_run_completion(
                run_id=run_id,
                status="failed",
                error_message=err,
                result_summary="Job discovery failed",
            )
            return {"status": "failed", "error": err}

    def check_application_reminders(self) -> List[Dict[str, Any]]:
        """Identify applications with pending follow-ups or stale statuses."""
        reminders = []

        # 1. Due or overdue follow-up dates
        due_rows = self.db.execute(
            """
            SELECT a.id, a.job_id, a.status, a.follow_up_date, a.notes,
                   j.title, j.company
            FROM application_records a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.follow_up_date IS NOT NULL
              AND a.follow_up_date <= date('now', '+2 days')
              AND a.status NOT IN ('offer', 'rejected', 'withdrawn')
            ORDER BY a.follow_up_date ASC
            """
        )
        for r in due_rows:
            reminders.append({
                "type": "follow_up_due",
                "app_id": r["id"],
                "job_title": r["title"],
                "company": r["company"],
                "status": r["status"],
                "due_date": r["follow_up_date"],
                "message": f"Follow-up scheduled with {r['company']} for {r['title']} on {r['follow_up_date']}",
            })

        # 2. Stale applications (status unchanged > 14 days)
        stale_rows = self.db.execute(
            """
            SELECT a.id, a.job_id, a.status, a.updated_at, j.title, j.company
            FROM application_records a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.status IN ('applied', 'assessment')
              AND a.updated_at <= datetime('now', '-14 days')
            ORDER BY a.updated_at ASC
            """
        )
        for r in stale_rows:
            reminders.append({
                "type": "stale_application",
                "app_id": r["id"],
                "job_title": r["title"],
                "company": r["company"],
                "status": r["status"],
                "updated_at": r["updated_at"],
                "message": f"No status update for {r['company']} ({r['title']}) in over 14 days",
            })

        return reminders

    def run_system_diagnostics(self) -> Dict[str, Any]:
        """Perform comprehensive system diagnostics and integrity checks."""
        # SQLite PRAGMA integrity check
        try:
            with self.db.transaction() as conn:
                cur = conn.execute("PRAGMA integrity_check")
                row = cur.fetchone()
                integrity = row[0] if row else "unknown"
        except Exception as e:
            integrity = f"error: {e}"

        # DB file size
        db_path = Path(settings.database.path)
        db_size_kb = round(db_path.stat().st_size / 1024, 1) if db_path.exists() else 0

        # Counts
        counts = {
            "resumes": self.db.execute_one("SELECT COUNT(*) AS c FROM resumes")["c"],
            "versions": self.db.execute_one("SELECT COUNT(*) AS c FROM resume_versions")["c"],
            "bullets": self.db.execute_one("SELECT COUNT(*) AS c FROM resume_bullets")["c"],
            "jobs": self.db.execute_one("SELECT COUNT(*) AS c FROM jobs")["c"],
            "applications": self.db.execute_one("SELECT COUNT(*) AS c FROM application_records")["c"],
            "matches": self.db.execute_one("SELECT COUNT(*) AS c FROM job_matches")["c"],
            "backups": len(self.backup_mgr.list_backups()),
        }

        # Disk space in data directory
        data_dir = Path(settings.project_root) / "data"
        try:
            total, used, free = shutil.disk_usage(data_dir)
            free_gb = round(free / (1024 ** 3), 2)
        except Exception:
            free_gb = -1.0

        return {
            "integrity_check": integrity,
            "db_size_kb": db_size_kb,
            "counts": counts,
            "free_disk_gb": free_gb,
            "status": "healthy" if integrity == "ok" else "warning",
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ── Background Worker Loop ────────────────────────────────────

    def start_background_worker(self, interval_minutes: int = 60) -> None:
        """Start the background automation thread."""
        if self._running and self._thread and self._thread.is_alive():
            logger.info("Automation worker is already running")
            return

        self._interval_minutes = max(1, interval_minutes)
        self._stop_event.clear()
        self._running = True

        def _worker():
            logger.info("Automation worker thread started (interval %dm)", self._interval_minutes)
            while not self._stop_event.is_set():
                # Perform periodic backup
                try:
                    self.execute_backup(label="worker")
                except Exception as e:
                    logger.error("Periodic backup failed: %s", e)

                # Wait for interval or stop event
                self._stop_event.wait(timeout=self._interval_minutes * 60)

            logger.info("Automation worker thread exiting")

        self._thread = threading.Thread(target=_worker, daemon=True, name="CareerOS-Scheduler")
        self._thread.start()

    def stop_background_worker(self) -> None:
        """Signal the background automation thread to stop."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Automation worker thread stopped")

    @property
    def is_running(self) -> bool:
        """Check if background worker thread is active."""
        return self._running and bool(self._thread and self._thread.is_alive())
