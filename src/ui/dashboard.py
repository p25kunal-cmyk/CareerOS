"""CareerOS Dashboard — overview page with live metrics and quick actions."""

import json
import streamlit as st
from src.database.connection import DatabaseConnection
from src.ui.components import metric_card, empty_state, section_header, status_badge


def render(db: DatabaseConnection):
    """Render the main dashboard page."""
    section_header("Dashboard", "Your job search at a glance")

    # ── Metrics row ───────────────────────────────────────────
    stats = _load_stats(db)

    cols = st.columns(4)
    with cols[0]:
        metric_card("Resumes", stats["resumes"], icon="📄")
    with cols[1]:
        metric_card("Jobs Saved", stats["jobs"], icon="💼")
    with cols[2]:
        metric_card("Applications", stats["applications"], icon="📋")
    with cols[3]:
        ai_label = "Enabled" if stats["ai_enabled"] else "Disabled"
        metric_card("AI Status", ai_label, icon="🤖")

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # ── Two-column layout ─────────────────────────────────────
    left, right = st.columns([3, 2])

    with left:
        st.markdown("### Recent Activity")
        _render_recent_activity(db)

    with right:
        st.markdown("### Quick Actions")
        _render_quick_actions()

        st.markdown("### System Status")
        _render_system_status(db, stats)


def _load_stats(db: DatabaseConnection) -> dict:
    """Gather dashboard statistics from the database."""
    from config.settings import settings

    return {
        "resumes": db.count("resumes"),
        "jobs": db.count("jobs"),
        "applications": db.count("application_records"),
        "ai_enabled": settings.ai.enabled,
        "schema_version": _get_schema_version(db),
    }


def _get_schema_version(db: DatabaseConnection) -> int:
    try:
        row = db.execute_one("SELECT MAX(version) AS v FROM schema_version")
        return row["v"] if row and row["v"] else 0
    except Exception:
        return 0


def _render_recent_activity(db: DatabaseConnection):
    """Show recent application events and job discoveries."""
    # Recent application events
    events = db.execute(
        """SELECT ae.event_type, ae.description, ae.event_date,
                  ae.new_status, j.title, j.company
           FROM application_events ae
           JOIN application_records ar ON ae.application_id = ar.id
           JOIN jobs j ON ar.job_id = j.id
           ORDER BY ae.created_at DESC LIMIT 10"""
    )

    if not events:
        # Check for recent jobs
        recent_jobs = db.execute(
            "SELECT title, company, first_discovered FROM jobs ORDER BY first_discovered DESC LIMIT 5"
        )
        if recent_jobs:
            for job in recent_jobs:
                st.markdown(
                    f"💼 **{job['title']}** at {job['company'] or 'Unknown'} — "
                    f"<small style='color:#64748b'>{job['first_discovered']}</small>",
                    unsafe_allow_html=True,
                )
        else:
            empty_state(
                "📭", "No activity yet",
                "Upload a resume or add a job to get started.",
            )
        return

    for event in events:
        badge = ""
        if event["new_status"]:
            badge = status_badge(event["new_status"])

        desc = event["description"] or event["event_type"].replace("_", " ").title()
        company = event["company"] or ""
        title = event["title"] or ""

        st.markdown(
            f"{badge} **{title}** {('at ' + company) if company else ''} — "
            f"{desc} <small style='color:#64748b'>{event['event_date']}</small>",
            unsafe_allow_html=True,
        )


def _render_quick_actions():
    """Show quick-action buttons."""
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Upload Resume", use_container_width=True):
            st.session_state["nav_target"] = "My Resumes"
            st.rerun()
    with col2:
        if st.button("💼 Add Job", use_container_width=True):
            st.session_state["nav_target"] = "Find Jobs"
            st.rerun()

    col3, col4 = st.columns(2)
    with col3:
        if st.button("🎯 Match Jobs", use_container_width=True):
            st.session_state["nav_target"] = "Job Matching"
            st.rerun()
    with col4:
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state["nav_target"] = "Settings"
            st.rerun()


def _render_system_status(db: DatabaseConnection, stats: dict):
    """Show system health indicators."""
    st.markdown(
        f"<div style='padding:4px 0;border-bottom:1px solid #1e293b;'>"
        f"<span style='color:#94a3b8;'>Database</span> "
        f"<span style='color:#10b981;float:right;'>● v{stats['schema_version']}</span></div>",
        unsafe_allow_html=True,
    )
    ai_color = "#10b981" if stats["ai_enabled"] else "#f59e0b"
    ai_text = "Connected" if stats["ai_enabled"] else "Not configured"
    st.markdown(
        f"<div style='padding:4px 0;border-bottom:1px solid #1e293b;'>"
        f"<span style='color:#94a3b8;'>AI Provider</span> "
        f"<span style='color:{ai_color};float:right;'>● {ai_text}</span></div>",
        unsafe_allow_html=True,
    )

    # Application breakdown by status
    status_rows = db.execute(
        "SELECT status, COUNT(*) as cnt FROM application_records GROUP BY status ORDER BY cnt DESC"
    )
    if status_rows:
        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
        st.markdown("**Application Pipeline**")
        for row in status_rows:
            st.markdown(
                f"{status_badge(row['status'])} × {row['cnt']}",
                unsafe_allow_html=True,
            )
