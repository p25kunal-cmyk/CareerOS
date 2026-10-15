"""Shared test fixtures for CareerOS.

Provides an in-memory SQLite database and temporary directories
so tests never touch the user's real data.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import DatabaseConnection
from src.database.migrations import run_migrations, seed_default_templates


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test data."""
    for sub in ("uploads", "exports", "backups"):
        (tmp_path / sub).mkdir()
    return tmp_path


@pytest.fixture
def db(tmp_dir):
    """Provide a fresh SQLite database with full schema applied."""
    db_path = str(tmp_dir / "test.db")
    conn = DatabaseConnection(db_path)
    run_migrations(conn)
    seed_default_templates(conn)
    return conn


@pytest.fixture
def empty_db(tmp_dir):
    """Provide a raw SQLite database with NO migrations (for testing migrations)."""
    db_path = str(tmp_dir / "empty.db")
    return DatabaseConnection(db_path)
