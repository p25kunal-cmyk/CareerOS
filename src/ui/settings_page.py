"""CareerOS Settings page — AI configuration, matching weights, and system info."""

import json
import streamlit as st
from config.settings import settings
from src.database.connection import DatabaseConnection
from src.ui.components import section_header, info_row


def render(db: DatabaseConnection):
    """Render the Settings & AI Usage page."""
    section_header("Settings & AI Usage", "Configure your CareerOS instance")

    tabs = st.tabs(["AI Provider", "Matching Weights", "Data & Backup", "System Info"])

    with tabs[0]:
        _render_ai_settings(db)

    with tabs[1]:
        _render_matching_weights(db)

    with tabs[2]:
        _render_data_settings(db)

    with tabs[3]:
        _render_system_info(db)


def _render_ai_settings(db: DatabaseConnection):
    """AI provider configuration panel."""
    st.markdown("#### AI Provider Configuration")

    if settings.ai.enabled:
        st.success(f"✅ AI enabled — **{settings.ai.provider}** / `{settings.ai.model}`")
    else:
        st.warning(
            "⚠️ AI is not configured. All features work without AI. "
            "To enable, set `CAREEROS_AI_PROVIDER` and `CAREEROS_AI_API_KEY` "
            "in your `.env` file."
        )

    with st.expander("Current AI Configuration", expanded=False):
        info_row("Provider", settings.ai.provider or "—")
        info_row("Model", settings.ai.model)
        info_row("Max Tokens", settings.ai.max_tokens)
        info_row("Monthly Budget", f"${settings.ai.monthly_budget:.2f}")
        info_row("API Key", "••••••••" if settings.ai.api_key else "Not set")

    # AI usage summary
    st.markdown("#### AI Usage This Month")
    usage = db.execute(
        """SELECT COUNT(*) as calls,
                  SUM(CASE WHEN cache_hit=1 THEN 1 ELSE 0 END) as cache_hits,
                  SUM(input_tokens) as total_input,
                  SUM(output_tokens) as total_output,
                  SUM(estimated_cost) as total_cost
           FROM ai_usage_records
           WHERE created_at >= date('now', 'start of month')"""
    )
    if usage and usage[0]["calls"]:
        row = usage[0]
        cols = st.columns(4)
        cols[0].metric("API Calls", row["calls"])
        cols[1].metric("Cache Hits", row["cache_hits"] or 0)
        cols[2].metric("Tokens Used", f"{(row['total_input'] or 0) + (row['total_output'] or 0):,}")
        cols[3].metric("Est. Cost", f"${row['total_cost'] or 0:.4f}")

        remaining = settings.ai.monthly_budget - (row["total_cost"] or 0)
        if remaining <= 0:
            st.error("🚫 Monthly budget exhausted. AI calls are disabled until next month.")
        elif remaining < settings.ai.monthly_budget * 0.2:
            st.warning(f"⚠️ Budget remaining: ${remaining:.4f}")
    else:
        st.info("No AI usage recorded this month.")


def _render_matching_weights(db: DatabaseConnection):
    """Allow users to adjust job matching score weights."""
    st.markdown("#### Matching Score Weights")
    st.caption("Adjust how different factors contribute to the job match score (total should be 100).")

    weight_keys = [
        ("matching_weight_required_skills", "Required Skills"),
        ("matching_weight_preferred_skills", "Preferred Skills"),
        ("matching_weight_experience_level", "Experience Level"),
        ("matching_weight_role_alignment", "Role Alignment"),
        ("matching_weight_domain_relevance", "Domain Relevance"),
        ("matching_weight_location_preference", "Location Preference"),
    ]

    current_weights = {}
    for key, label in weight_keys:
        row = db.execute_one(
            "SELECT value FROM user_settings WHERE key=?", (key,)
        )
        current_weights[key] = int(row["value"]) if row else 0

    new_weights = {}
    for key, label in weight_keys:
        new_weights[key] = st.slider(
            label, 0, 50, current_weights[key], key=f"slider_{key}"
        )

    total = sum(new_weights.values())
    if total != 100:
        st.warning(f"Weights sum to **{total}** — they should total 100.")
    else:
        st.success("Weights sum to 100 ✓")

    if st.button("Save Weights", type="primary"):
        with db.transaction() as conn:
            for key, val in new_weights.items():
                conn.execute(
                    """INSERT OR REPLACE INTO user_settings (key, value, category, updated_at)
                       VALUES (?, ?, 'matching', datetime('now'))""",
                    (key, str(val)),
                )
        st.success("Matching weights saved.")
        st.rerun()


def _render_data_settings(db: DatabaseConnection):
    """Data directory info and backup controls."""
    st.markdown("#### Data Directories")
    info_row("Data Root", settings.data_dir)
    info_row("Uploads", settings.uploads_dir)
    info_row("Exports", settings.exports_dir)
    info_row("Backups", settings.backups_dir)
    info_row("Database", settings.database.path)

    st.markdown("#### Database Backup")
    st.caption("Create a timestamped backup of the SQLite database.")

    if st.button("🗄️ Backup Database Now"):
        import shutil
        from datetime import datetime
        from pathlib import Path

        src_path = settings.database.path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"careeros_backup_{timestamp}.db"
        backup_path = Path(settings.backups_dir) / backup_name

        try:
            # Use SQLite backup API for consistency
            import sqlite3
            src_conn = sqlite3.connect(src_path)
            dst_conn = sqlite3.connect(str(backup_path))
            src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()
            st.success(f"✅ Backup created: `{backup_name}`")
        except Exception as e:
            st.error(f"Backup failed: {e}")


def _render_system_info(db: DatabaseConnection):
    """System and version information."""
    st.markdown("#### System Information")

    from src.database.migrations import get_schema_version
    schema_v = get_schema_version(db)

    info_row("Application", "CareerOS v0.1.0")
    info_row("Schema Version", schema_v)
    info_row("Python", _python_version())
    info_row("Streamlit", _streamlit_version())
    info_row("Log Level", settings.logging.level)
    info_row("Log File", settings.logging.log_file)

    # Table row counts
    st.markdown("#### Database Statistics")
    tables = [
        "resumes", "resume_versions", "resume_sections", "resume_bullets",
        "jobs", "job_search_profiles", "application_records",
        "ai_suggestions", "ai_usage_records", "automation_runs",
    ]
    for tbl in tables:
        try:
            cnt = db.count(tbl)
            info_row(tbl.replace("_", " ").title(), cnt)
        except Exception:
            info_row(tbl.replace("_", " ").title(), "—")


def _python_version() -> str:
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _streamlit_version() -> str:
    try:
        import streamlit
        return streamlit.__version__
    except Exception:
        return "unknown"
