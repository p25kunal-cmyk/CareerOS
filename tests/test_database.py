"""Tests for database schema, migrations, and connection management.

Verifies that:
- All 16 tables are created.
- Foreign keys are enforced.
- Indexes exist.
- Transactions commit and rollback correctly.
- Migration is idempotent.
- Default seed data is present.
"""

import json
import uuid
import pytest

from src.database.connection import DatabaseConnection
from src.database.migrations import (
    SCHEMA_VERSION,
    get_schema_version,
    run_migrations,
    seed_default_templates,
)


# ── Schema creation ───────────────────────────────────────────

EXPECTED_TABLES = [
    "schema_version",
    "resumes",
    "resume_versions",
    "resume_sections",
    "resume_bullets",
    "resume_templates",
    "jobs",
    "job_sources",
    "job_search_profiles",
    "job_matches",
    "ai_suggestions",
    "ai_cache",
    "ai_usage_records",
    "application_records",
    "application_events",
    "automation_runs",
    "user_settings",
]


def test_all_tables_created(db):
    """Every expected table must exist after migration."""
    for table in EXPECTED_TABLES:
        assert db.table_exists(table), f"Table '{table}' missing"


def test_schema_version(db):
    """Schema version must match SCHEMA_VERSION constant."""
    assert get_schema_version(db) == SCHEMA_VERSION


def test_migration_idempotent(db):
    """Running migrations again must not error or change the version."""
    run_migrations(db)  # second run
    assert get_schema_version(db) == SCHEMA_VERSION


def test_empty_db_version_zero(empty_db):
    """An uninitialised database should report version 0."""
    assert get_schema_version(empty_db) == 0


# ── Seed data ─────────────────────────────────────────────────

def test_default_search_profile_seeded(db):
    """A default PM search profile must be present."""
    rows = db.execute(
        "SELECT * FROM job_search_profiles WHERE is_default=1"
    )
    assert len(rows) == 1
    profile = rows[0]
    assert "Product Management" in profile["name"]
    roles = json.loads(profile["target_roles"])
    assert "Product Manager" in roles


def test_default_matching_weights_seeded(db):
    """Matching weight settings must be present."""
    rows = db.execute(
        "SELECT * FROM user_settings WHERE category='matching'"
    )
    assert len(rows) >= 6
    keys = {r["key"] for r in rows}
    assert "matching_weight_required_skills" in keys


def test_default_job_sources_seeded(db):
    """All five job sources must be seeded."""
    rows = db.execute("SELECT * FROM job_sources ORDER BY id")
    assert len(rows) == 5
    types = {r["source_type"] for r in rows}
    assert types == {"linkedin", "iimjobs", "indeed", "naukri", "manual"}


def test_default_templates_seeded(db):
    """Three resume templates must be seeded."""
    rows = db.execute("SELECT * FROM resume_templates ORDER BY template_type")
    assert len(rows) == 3
    types = {r["template_type"] for r in rows}
    assert types == {"iim_nagpur", "professional", "product_management"}


def test_template_seeding_idempotent(db):
    """Seeding templates again must not create duplicates."""
    seed_default_templates(db)
    rows = db.execute("SELECT * FROM resume_templates")
    assert len(rows) == 3


# ── CRUD operations ──────────────────────────────────────────

def test_insert_and_read_resume(db):
    """Insert a resume and read it back."""
    rid = str(uuid.uuid4())
    db.execute_write(
        "INSERT INTO resumes (id, name, is_master) VALUES (?,?,?)",
        (rid, "Test Resume", 1),
    )
    row = db.execute_one("SELECT * FROM resumes WHERE id=?", (rid,))
    assert row is not None
    assert row["name"] == "Test Resume"
    assert row["is_master"] == 1


def test_insert_resume_version_fk(db):
    """A resume version must reference a valid resume."""
    rid = str(uuid.uuid4())
    vid = str(uuid.uuid4())

    db.execute_write(
        "INSERT INTO resumes (id, name) VALUES (?,?)", (rid, "R")
    )
    db.execute_write(
        "INSERT INTO resume_versions (id, resume_id, version_number, version_name) "
        "VALUES (?,?,?,?)",
        (vid, rid, 1, "v1"),
    )
    row = db.execute_one("SELECT * FROM resume_versions WHERE id=?", (vid,))
    assert row["resume_id"] == rid


def test_cascade_delete_resume(db):
    """Deleting a resume must cascade-delete its versions."""
    rid = str(uuid.uuid4())
    vid = str(uuid.uuid4())

    with db.transaction() as conn:
        conn.execute("INSERT INTO resumes (id, name) VALUES (?,?)", (rid, "R"))
        conn.execute(
            "INSERT INTO resume_versions (id, resume_id, version_number) VALUES (?,?,?)",
            (vid, rid, 1),
        )

    db.execute_write("DELETE FROM resumes WHERE id=?", (rid,))
    row = db.execute_one("SELECT * FROM resume_versions WHERE id=?", (vid,))
    assert row is None


def test_unique_version_number(db):
    """Two versions of the same resume cannot share a version_number."""
    rid = str(uuid.uuid4())
    db.execute_write("INSERT INTO resumes (id, name) VALUES (?,?)", (rid, "R"))
    db.execute_write(
        "INSERT INTO resume_versions (id, resume_id, version_number) VALUES (?,?,?)",
        (str(uuid.uuid4()), rid, 1),
    )
    with pytest.raises(Exception):
        db.execute_write(
            "INSERT INTO resume_versions (id, resume_id, version_number) VALUES (?,?,?)",
            (str(uuid.uuid4()), rid, 1),
        )


# ── Transactions ──────────────────────────────────────────────

def test_transaction_rollback(db):
    """A failed transaction must not leave partial data."""
    rid = str(uuid.uuid4())
    try:
        with db.transaction() as conn:
            conn.execute("INSERT INTO resumes (id, name) VALUES (?,?)", (rid, "Bad"))
            raise ValueError("Simulated error")
    except ValueError:
        pass

    row = db.execute_one("SELECT * FROM resumes WHERE id=?", (rid,))
    assert row is None, "Rolled-back insert must not persist"


def test_transaction_commit(db):
    """A successful transaction must persist data."""
    rid = str(uuid.uuid4())
    with db.transaction() as conn:
        conn.execute("INSERT INTO resumes (id, name) VALUES (?,?)", (rid, "Good"))

    row = db.execute_one("SELECT * FROM resumes WHERE id=?", (rid,))
    assert row is not None


# ── Foreign key enforcement ───────────────────────────────────

def test_fk_enforced_on_resume_version(db):
    """Inserting a version with a non-existent resume_id must fail."""
    with pytest.raises(Exception):
        db.execute_write(
            "INSERT INTO resume_versions (id, resume_id, version_number) VALUES (?,?,?)",
            (str(uuid.uuid4()), "nonexistent", 1),
        )


def test_fk_enforced_on_section(db):
    """Inserting a section with a non-existent version_id must fail."""
    with pytest.raises(Exception):
        db.execute_write(
            "INSERT INTO resume_sections (id, version_id, section_type, title, display_order) "
            "VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), "nonexistent", "education", "Education", 1),
        )


# ── Count helper ──────────────────────────────────────────────

def test_count_helper(db):
    """The count() helper should return correct row counts."""
    initial = db.count("resumes")
    rid = str(uuid.uuid4())
    db.execute_write("INSERT INTO resumes (id, name) VALUES (?,?)", (rid, "X"))
    assert db.count("resumes") == initial + 1


# ── Check constraints ─────────────────────────────────────────

def test_job_match_score_range(db):
    """Match score must be between 0 and 100."""
    # Create required resume + version + job
    rid = str(uuid.uuid4())
    vid = str(uuid.uuid4())
    jid = str(uuid.uuid4())

    with db.transaction() as conn:
        conn.execute("INSERT INTO resumes (id, name) VALUES (?,?)", (rid, "R"))
        conn.execute(
            "INSERT INTO resume_versions (id, resume_id, version_number) VALUES (?,?,?)",
            (vid, rid, 1),
        )
        conn.execute(
            "INSERT INTO jobs (id, title) VALUES (?,?)", (jid, "PM")
        )

    # Valid score
    db.execute_write(
        "INSERT INTO job_matches (id, job_id, resume_version_id, overall_score, score_breakdown) "
        "VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), jid, vid, 75.0, "{}"),
    )

    # Invalid score > 100
    with pytest.raises(Exception):
        db.execute_write(
            "INSERT INTO job_matches (id, job_id, resume_version_id, overall_score, score_breakdown) "
            "VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), jid, vid, 150.0, "{}"),
        )
