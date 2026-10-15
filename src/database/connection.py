"""SQLite database connection management.

Uses WAL mode for better concurrent read performance with Streamlit.
Provides context managers for safe transaction handling.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from src.utils.logger import get_logger

logger = get_logger("database.connection")


class DatabaseConnection:
    """Manages SQLite connections with WAL mode and foreign key enforcement."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Create a new connection with standard pragmas."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that commits on success, rolls back on error."""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def read(self) -> Generator[sqlite3.Connection, None, None]:
        """Read-only context manager."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> list:
        """Run a SELECT and return all rows as sqlite3.Row objects."""
        with self.read() as conn:
            return conn.execute(sql, params).fetchall()

    def execute_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Run a SELECT and return a single row or None."""
        with self.read() as conn:
            return conn.execute(sql, params).fetchone()

    def execute_write(self, sql: str, params: tuple = ()) -> int:
        """Run an INSERT/UPDATE/DELETE inside a transaction. Returns lastrowid."""
        with self.transaction() as conn:
            cursor = conn.execute(sql, params)
            return cursor.lastrowid

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        row = self.execute_one(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return row is not None

    def count(self, table_name: str) -> int:
        """Return row count for a table."""
        row = self.execute_one(f"SELECT COUNT(*) as cnt FROM [{table_name}]")
        return row["cnt"] if row else 0


# ── Module-level singleton ────────────────────────────────────
_db: Optional[DatabaseConnection] = None


def get_db() -> DatabaseConnection:
    """Get or create the global database connection instance."""
    global _db
    if _db is None:
        from config.settings import settings
        _db = DatabaseConnection(settings.database.path)
    return _db


def init_db(db_path: str) -> DatabaseConnection:
    """Initialize with a specific path (used by tests)."""
    global _db
    _db = DatabaseConnection(db_path)
    return _db
