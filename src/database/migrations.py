"""Database schema and migrations for CareerOS.

Manages versioned schema creation. All entities use TEXT UUIDs as primary keys
so that IDs remain stable across edits, reorders, and AI suggestions.
"""

import json
import sqlite3
import uuid

from src.database.connection import DatabaseConnection
from src.utils.logger import get_logger

logger = get_logger("database.migrations")

SCHEMA_VERSION = 1

# ── Full V1 schema ────────────────────────────────────────────

SCHEMA_V1 = """
-- Version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

-- ============================================================
-- RESUME TABLES
-- ============================================================
CREATE TABLE IF NOT EXISTS resumes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_master INTEGER NOT NULL DEFAULT 0,
    original_filename TEXT,
    original_file_path TEXT,
    file_type TEXT CHECK(file_type IN ('pdf', 'docx', NULL)),
    upload_timestamp TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resume_versions (
    id TEXT PRIMARY KEY,
    resume_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    version_name TEXT,
    description TEXT,
    is_draft INTEGER NOT NULL DEFAULT 0,
    parent_version_id TEXT,
    snapshot_data TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_version_id) REFERENCES resume_versions(id) ON DELETE SET NULL,
    UNIQUE(resume_id, version_number)
);

CREATE TABLE IF NOT EXISTS resume_sections (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    section_type TEXT NOT NULL CHECK(section_type IN (
        'contact','summary','education','experience','internships',
        'projects','skills','certifications','achievements',
        'positions_of_responsibility','extracurricular','custom'
    )),
    title TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    is_visible INTEGER NOT NULL DEFAULT 1,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (version_id) REFERENCES resume_versions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resume_bullets (
    id TEXT PRIMARY KEY,
    section_id TEXT NOT NULL,
    content TEXT NOT NULL,
    sub_content TEXT,
    bullet_type TEXT NOT NULL DEFAULT 'bullet' CHECK(bullet_type IN (
        'bullet','header','subheader','text','skill_group',
        'date_range','location','contact_item'
    )),
    display_order INTEGER NOT NULL,
    indent_level INTEGER NOT NULL DEFAULT 0,
    is_verified INTEGER NOT NULL DEFAULT 1,
    metadata TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (section_id) REFERENCES resume_sections(id) ON DELETE CASCADE
);

-- ============================================================
-- TEMPLATE TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS resume_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    template_type TEXT NOT NULL CHECK(template_type IN (
        'iim_nagpur','professional','product_management','custom'
    )),
    template_config TEXT NOT NULL DEFAULT '{}',
    preview_path TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- JOB TABLES
-- ============================================================
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    employment_type TEXT,
    experience_min INTEGER,
    experience_max INTEGER,
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT DEFAULT 'INR',
    date_posted TEXT,
    description TEXT,
    required_skills TEXT,
    preferred_skills TEXT,
    source_portal TEXT,
    original_url TEXT,
    application_url TEXT,
    first_discovered TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN (
        'active','expired','closed','unknown'
    )),
    is_manually_entered INTEGER NOT NULL DEFAULT 0,
    raw_data TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN (
        'linkedin','iimjobs','indeed','naukri','manual','other'
    )),
    is_enabled INTEGER NOT NULL DEFAULT 1,
    config TEXT,
    last_successful_run TEXT,
    last_error TEXT,
    last_error_time TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_search_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    target_roles TEXT,
    preferred_industries TEXT,
    preferred_locations TEXT,
    remote_preference TEXT DEFAULT 'any' CHECK(remote_preference IN (
        'remote','hybrid','onsite','any'
    )),
    experience_level TEXT,
    employment_type TEXT,
    min_salary REAL,
    salary_currency TEXT DEFAULT 'INR',
    required_keywords TEXT,
    excluded_keywords TEXT,
    companies_of_interest TEXT,
    max_job_age_days INTEGER DEFAULT 30,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- MATCHING TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS job_matches (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    resume_version_id TEXT NOT NULL,
    overall_score REAL NOT NULL CHECK(overall_score >= 0 AND overall_score <= 100),
    score_breakdown TEXT NOT NULL DEFAULT '{}',
    matched_requirements TEXT,
    missing_requirements TEXT,
    partial_requirements TEXT,
    resume_evidence TEXT,
    improvement_suggestions TEXT,
    match_method TEXT NOT NULL DEFAULT 'keyword' CHECK(match_method IN (
        'keyword','semantic','ai','hybrid'
    )),
    is_stale INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id) ON DELETE CASCADE,
    UNIQUE(job_id, resume_version_id, match_method)
);

-- ============================================================
-- AI TABLES
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_suggestions (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    resume_version_id TEXT NOT NULL,
    suggestion_type TEXT NOT NULL CHECK(suggestion_type IN (
        'rephrase','reorder','add_bullet','remove_bullet',
        'add_skill','flag_missing','request_verification'
    )),
    target_section_id TEXT,
    source_bullet_id TEXT,
    original_text TEXT,
    proposed_text TEXT,
    reason TEXT,
    supporting_evidence_ids TEXT,
    verification_status TEXT NOT NULL DEFAULT 'pending' CHECK(verification_status IN (
        'pending','verified','rejected','needs_verification'
    )),
    confidence REAL,
    is_applied INTEGER NOT NULL DEFAULT 0,
    applied_to_version_id TEXT,
    batch_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id) ON DELETE CASCADE,
    FOREIGN KEY (target_section_id) REFERENCES resume_sections(id) ON DELETE SET NULL,
    FOREIGN KEY (source_bullet_id) REFERENCES resume_bullets(id) ON DELETE SET NULL,
    FOREIGN KEY (applied_to_version_id) REFERENCES resume_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ai_cache (
    id TEXT PRIMARY KEY,
    input_hash TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    operation TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS ai_usage_records (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    operation TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost REAL,
    input_hash TEXT,
    cache_hit INTEGER NOT NULL DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- APPLICATION TRACKING
-- ============================================================
CREATE TABLE IF NOT EXISTS application_records (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    resume_version_id TEXT,
    status TEXT NOT NULL DEFAULT 'saved' CHECK(status IN (
        'saved','shortlisted','resume_prepared','applied',
        'assessment','interview','offer','rejected','withdrawn'
    )),
    application_date TEXT,
    follow_up_date TEXT,
    notes TEXT,
    recruiter_name TEXT,
    recruiter_email TEXT,
    recruiter_phone TEXT,
    interview_stages TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS application_events (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN (
        'status_change','note','follow_up','interview','feedback','other'
    )),
    old_status TEXT,
    new_status TEXT,
    description TEXT,
    event_date TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (application_id) REFERENCES application_records(id) ON DELETE CASCADE
);

-- ============================================================
-- AUTOMATION
-- ============================================================
CREATE TABLE IF NOT EXISTS automation_runs (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL CHECK(task_type IN (
        'job_discovery','job_refresh','backup','other'
    )),
    task_config TEXT,
    status TEXT NOT NULL CHECK(status IN (
        'running','completed','failed','cancelled'
    )),
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    result_summary TEXT,
    error_message TEXT,
    items_processed INTEGER NOT NULL DEFAULT 0,
    items_added INTEGER NOT NULL DEFAULT 0,
    items_updated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- USER SETTINGS
-- ============================================================
CREATE TABLE IF NOT EXISTS user_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    category TEXT CHECK(category IN (
        'general','ai','automation','export','display','matching'
    )),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_rv_resume ON resume_versions(resume_id);
CREATE INDEX IF NOT EXISTS idx_rs_version ON resume_sections(version_id);
CREATE INDEX IF NOT EXISTS idx_rs_order ON resume_sections(version_id, display_order);
CREATE INDEX IF NOT EXISTS idx_rb_section ON resume_bullets(section_id);
CREATE INDEX IF NOT EXISTS idx_rb_order ON resume_bullets(section_id, display_order);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source_portal);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_discovered ON jobs(first_discovered);
CREATE INDEX IF NOT EXISTS idx_jm_job ON job_matches(job_id);
CREATE INDEX IF NOT EXISTS idx_jm_resume ON job_matches(resume_version_id);
CREATE INDEX IF NOT EXISTS idx_ais_version ON ai_suggestions(resume_version_id);
CREATE INDEX IF NOT EXISTS idx_ais_batch ON ai_suggestions(batch_id);
CREATE INDEX IF NOT EXISTS idx_aic_hash ON ai_cache(input_hash);
CREATE INDEX IF NOT EXISTS idx_aiu_created ON ai_usage_records(created_at);
CREATE INDEX IF NOT EXISTS idx_ar_job ON application_records(job_id);
CREATE INDEX IF NOT EXISTS idx_ar_status ON application_records(status);
CREATE INDEX IF NOT EXISTS idx_ae_app ON application_events(application_id);
CREATE INDEX IF NOT EXISTS idx_auto_type ON automation_runs(task_type);
"""


# ── Default seed data ─────────────────────────────────────────

DEFAULT_SEARCH_PROFILE = {
    "name": "Product Management — Default",
    "target_roles": [
        "Product Manager", "Associate Product Manager", "Product Analyst",
        "Product Owner", "Business Analyst", "Strategy Analyst",
        "Growth Product Manager", "Technical Product Manager",
    ],
    "preferred_industries": [
        "Technology", "SaaS", "E-commerce", "Fintech", "EdTech",
        "HealthTech", "Consumer Internet", "Enterprise Software",
    ],
    "preferred_locations": [
        "Bangalore", "Mumbai", "Hyderabad", "Pune", "Delhi NCR",
        "Gurgaon", "Noida", "Chennai", "Remote",
    ],
    "remote_preference": "any",
    "experience_level": "0-3 years",
    "employment_type": ["Full-time", "Internship"],
    "required_keywords": [
        "product", "analytics", "strategy", "roadmap",
        "user research", "stakeholder", "agile", "data-driven",
    ],
    "excluded_keywords": [],
    "companies_of_interest": [],
    "max_job_age_days": 30,
}

DEFAULT_MATCHING_WEIGHTS = {
    "required_skills": 30,
    "preferred_skills": 15,
    "experience_level": 15,
    "role_alignment": 20,
    "domain_relevance": 10,
    "location_preference": 10,
}


# ── Public API ────────────────────────────────────────────────

def get_schema_version(db: DatabaseConnection) -> int:
    """Return the current schema version (0 if uninitialised)."""
    try:
        if not db.table_exists("schema_version"):
            return 0
        row = db.execute_one("SELECT MAX(version) AS v FROM schema_version")
        return row["v"] if row and row["v"] is not None else 0
    except Exception:
        return 0


def run_migrations(db: DatabaseConnection) -> None:
    """Apply all pending migrations up to SCHEMA_VERSION."""
    current = get_schema_version(db)
    if current >= SCHEMA_VERSION:
        logger.info("Schema up-to-date (v%d)", current)
        return

    logger.info("Migrating schema v%d → v%d", current, SCHEMA_VERSION)

    with db.transaction() as conn:
        if current < 1:
            _apply_v1(conn)

    logger.info("Migration complete — now at v%d", SCHEMA_VERSION)


def seed_default_templates(db: DatabaseConnection) -> None:
    """Insert default resume templates if they don't exist yet."""
    templates = [
        ("IIM Nagpur Format",
         "Standard IIM Nagpur placement resume. Single-page tabular layout with institutional branding.",
         "iim_nagpur", True),
        ("Professional Standard",
         "Clean professional template for industry applications outside campus placements.",
         "professional", False),
        ("Product Management",
         "Optimised for PM roles — emphasises impact metrics, user research, and product thinking.",
         "product_management", False),
    ]
    with db.transaction() as conn:
        for name, desc, ttype, is_default in templates:
            exists = conn.execute(
                "SELECT 1 FROM resume_templates WHERE template_type=?", (ttype,)
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """INSERT INTO resume_templates
                   (id, name, description, template_type, template_config, is_default)
                   VALUES (?,?,?,?,?,?)""",
                (str(uuid.uuid4()), name, desc, ttype,
                 json.dumps({"version": 1}), int(is_default)),
            )
    logger.info("Default resume templates seeded")


# ── Private helpers ───────────────────────────────────────────

def _apply_v1(conn: sqlite3.Connection) -> None:
    """Apply v1 — initial schema creation."""
    logger.info("Applying migration v1: initial schema")
    conn.executescript(SCHEMA_V1)

    conn.execute(
        "INSERT INTO schema_version (version, description) VALUES (?,?)",
        (1, "Initial schema — all tables, indexes, constraints"),
    )

    # Seed default search profile
    pid = str(uuid.uuid4())
    p = DEFAULT_SEARCH_PROFILE
    conn.execute(
        """INSERT INTO job_search_profiles
           (id,name,is_default,target_roles,preferred_industries,
            preferred_locations,remote_preference,experience_level,
            employment_type,required_keywords,excluded_keywords,
            companies_of_interest,max_job_age_days)
           VALUES (?,?,1,?,?,?,?,?,?,?,?,?,?)""",
        (pid, p["name"], json.dumps(p["target_roles"]),
         json.dumps(p["preferred_industries"]),
         json.dumps(p["preferred_locations"]),
         p["remote_preference"], p["experience_level"],
         json.dumps(p["employment_type"]),
         json.dumps(p["required_keywords"]),
         json.dumps(p["excluded_keywords"]),
         json.dumps(p["companies_of_interest"]),
         p["max_job_age_days"]),
    )

    # Seed default matching weights
    for key, value in DEFAULT_MATCHING_WEIGHTS.items():
        conn.execute(
            "INSERT INTO user_settings (key,value,category) VALUES (?,?,?)",
            (f"matching_weight_{key}", str(value), "matching"),
        )

    # Seed job sources
    sources = [
        ("linkedin",  "LinkedIn",      "linkedin",  0),
        ("iimjobs",   "IIMJobs",       "iimjobs",   0),
        ("indeed",    "Indeed India",   "indeed",    0),
        ("naukri",    "Naukri",         "naukri",    0),
        ("manual",    "Manual Entry",   "manual",    1),
    ]
    for sid, name, stype, enabled in sources:
        conn.execute(
            "INSERT INTO job_sources (id,name,source_type,is_enabled) VALUES (?,?,?,?)",
            (sid, name, stype, enabled),
        )

    logger.info("v1 migration applied — %d tables created", 16)
