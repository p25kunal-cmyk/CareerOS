"""Tests for CareerOS Automation, Backup & Maintenance Suite.

Tests backup creation, retention pruning, database restore,
run audit logging, background scheduling, reminders, and diagnostics.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest

from src.automation.backup import BackupManager
from src.automation.scheduler import AutomationRepository, AutomationScheduler
from src.tracker.repository import TrackerRepository
from src.tracker.models import JobPosting


@pytest.fixture
def backup_dir(tmp_path):
    """Provide a dedicated backup directory for tests."""
    b_dir = tmp_path / "backups_test"
    b_dir.mkdir(parents=True, exist_ok=True)
    return str(b_dir)


class TestBackupManager:
    """Test database backup creation, listing, pruning, and restoring."""

    def test_create_and_list_backup(self, db, backup_dir):
        mgr = BackupManager(db, backup_dir=backup_dir)
        backup_path = mgr.create_backup(label="unit_test")
        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.stat().st_size > 0
        assert "unit_test" in backup_path.name

        backups = mgr.list_backups()
        assert len(backups) == 1
        assert backups[0]["filename"] == backup_path.name
        assert backups[0]["size_bytes"] > 0

    def test_prune_backups(self, db, backup_dir):
        mgr = BackupManager(db, backup_dir=backup_dir)
        for i in range(5):
            mgr.create_backup(label=f"test_{i}")
            time.sleep(0.01)  # Ensure unique timestamps

        backups = mgr.list_backups()
        assert len(backups) == 5

        # Prune to keep 2
        removed = mgr.prune_backups(max_keep=2)
        assert removed == 3
        remaining = mgr.list_backups()
        assert len(remaining) == 2

    def test_restore_backup(self, db, backup_dir):
        tracker = TrackerRepository(db)
        mgr = BackupManager(db, backup_dir=backup_dir)

        # 1. Add job to current DB
        job = JobPosting(title="Product Lead", company="Amazon India")
        job_id, _ = tracker.add_or_update_job(job)

        # 2. Take backup containing this job
        backup_path = mgr.create_backup(label="with_job")
        assert backup_path is not None

        # 3. Delete job from DB
        tracker.delete_job(job_id)
        assert tracker.get_job(job_id) is None

        # 4. Restore backup
        success = mgr.restore_backup(str(backup_path))
        assert success is True

        # 5. Verify job restored
        restored_job = tracker.get_job(job_id)
        assert restored_job is not None
        assert restored_job.title == "Product Lead"

    def test_restore_invalid_file(self, db, backup_dir):
        mgr = BackupManager(db, backup_dir=backup_dir)
        fake_file = Path(backup_dir) / "corrupt.db"
        fake_file.write_text("not a real sqlite database")

        assert mgr.restore_backup(str(fake_file)) is False
        assert mgr.restore_backup("/nonexistent/path/file.db") is False


class TestAutomationRepository:
    """Test run auditing and history logging."""

    def test_log_run_lifecycle(self, db):
        repo = AutomationRepository(db)

        run_id = repo.log_run_start("backup", {"target": "all"})
        assert run_id is not None

        repo.log_run_completion(
            run_id=run_id,
            status="completed",
            items_processed=10,
            items_added=2,
            items_updated=1,
            result_summary="Completed successfully",
        )

        runs = repo.list_runs(limit=10)
        assert len(runs) >= 1
        assert runs[0]["id"] == run_id
        assert runs[0]["status"] == "completed"
        assert runs[0]["items_added"] == 2

        recent = repo.get_recent_run("backup")
        assert recent is not None
        assert recent["id"] == run_id


class TestAutomationScheduler:
    """Test scheduler tasks, diagnostics, and background loop."""

    def test_execute_backup_task(self, db, backup_dir):
        scheduler = AutomationScheduler(db)
        scheduler.backup_mgr = BackupManager(db, backup_dir=backup_dir)

        res = scheduler.execute_backup(max_keep=3, label="sched_test")
        assert res["status"] == "success"
        assert "backup_file" in res

        recent = scheduler.repo.get_recent_run("backup")
        assert recent is not None
        assert recent["status"] == "completed"

    def test_execute_job_discovery_task(self, db):
        scheduler = AutomationScheduler(db)
        res = scheduler.execute_job_discovery()
        assert res["status"] == "success"

        recent = scheduler.repo.get_recent_run("job_discovery")
        assert recent is not None
        assert recent["status"] in ("completed", "completed_with_warnings")

    def test_check_reminders(self, db):
        scheduler = AutomationScheduler(db)
        tracker = TrackerRepository(db)

        job = JobPosting(title="Consultant", company="BCG")
        job_id, _ = tracker.add_or_update_job(job)

        # Create application with follow-up date today
        app_id = tracker.create_application(
            job_id=job_id,
            status="applied",
            follow_up_date=time.strftime("%Y-%m-%d"),
        )

        reminders = scheduler.check_application_reminders()
        assert len(reminders) >= 1
        assert any(r["app_id"] == app_id for r in reminders)
        assert any(r["company"] == "BCG" for r in reminders)

    def test_system_diagnostics(self, db):
        scheduler = AutomationScheduler(db)
        diag = scheduler.run_system_diagnostics()

        assert diag["integrity_check"] == "ok"
        assert diag["status"] == "healthy"
        assert "counts" in diag
        assert diag["counts"]["jobs"] >= 0

    def test_worker_start_stop(self, db):
        scheduler = AutomationScheduler(db)
        assert scheduler.is_running is False

        scheduler.start_background_worker(interval_minutes=1)
        assert scheduler.is_running is True

        # Idempotent start
        scheduler.start_background_worker(interval_minutes=1)
        assert scheduler.is_running is True

        scheduler.stop_background_worker()
        assert scheduler.is_running is False
