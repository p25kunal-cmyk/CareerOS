"""CareerOS Dashboard — overview page with live metrics, quick actions, and sample data onboarding."""

import json
import streamlit as st
from src.database.connection import DatabaseConnection
from src.resume.sample_data import create_sample_mba_resume
from src.resume.repository import ResumeRepository
from src.ui.components import metric_card, empty_state, section_header, status_badge, render_top_header, navigate_to


def render(db: DatabaseConnection):
    """Render the main dashboard page."""
    render_top_header("Dashboard", db)

    section_header("Command Center", "Your AI-powered job search and resume operations at a glance")

    stats = _load_stats(db)

    # ── Onboarding banner if 0 resumes ────────────────────────
    if stats["resumes"] == 0:
        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, #1e293b 0%, #172554 100%);
                border: 1px solid #3b82f644;
                border-radius: 12px;
                padding: 1.25rem 1.5rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
            ">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                    <div>
                        <h3 style="color:#f8fafc; margin:0 0 4px 0;">✨ Kickstart Your CareerOS Journey</h3>
                        <p style="color:#cbd5e1; margin:0; font-size:0.9rem;">
                            No resumes found in your database. Load our comprehensive, ATS-compliant <b>IIM MBA Master Resume</b> to immediately explore the Live Previewer, Granular Editor, and AI Matching Engine.
                        </p>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c_seed1, c_seed2 = st.columns([1, 1])
        with c_seed1:
            if st.button("✨ Load High-Impact MBA Sample Resume", type="primary", use_container_width=True):
                repo = ResumeRepository(db)
                r_id, v_id = create_sample_mba_resume(repo)
                navigate_to("Resume Preview", active_resume_id=r_id, active_version_id=v_id)
        with c_seed2:
            if st.button("📥 Upload Your Own Resume File (PDF / DOCX)", use_container_width=True):
                navigate_to("My Resumes")
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Metrics row ───────────────────────────────────────────
    cols = st.columns(4)
    with cols[0]:
        metric_card("Resumes", stats["resumes"], icon="📄")
    with cols[1]:
        metric_card("Jobs Saved", stats["jobs"], icon="💼")
    with cols[2]:
        metric_card("Applications", stats["applications"], icon="📋")
    with cols[3]:
        ai_label = "Enabled" if stats["ai_enabled"] else "Disabled"
        metric_card("AI Engine", ai_label, icon="🤖")

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # ── Two-column layout ─────────────────────────────────────
    left, right = st.columns([3, 2])

    with left:
        st.markdown("### Recent Activity & Discoveries")
        _render_recent_activity(db)

    with right:
        st.markdown("### Quick Actions")
        _render_quick_actions()

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
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
    events = db.execute(
        """SELECT ae.event_type, ae.description, ae.event_date,
                  ae.new_status, j.title, j.company
           FROM application_events ae
           JOIN application_records ar ON ae.application_id = ar.id
           JOIN jobs j ON ar.job_id = j.id
           ORDER BY ae.created_at DESC LIMIT 10"""
    )

    if not events:
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
                "📭", "No activity recorded yet",
                "Load a sample resume or discover jobs to start building your career pipeline.",
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
        if st.button("📄 My Resumes", use_container_width=True):
            navigate_to("My Resumes")
    with col2:
        if st.button("👁️ Resume Preview", type="primary", use_container_width=True):
            navigate_to("Resume Preview")

    col3, col4 = st.columns(2)
    with col3:
        if st.button("✏️ Resume Editor", use_container_width=True):
            navigate_to("Resume Editor")
    with col4:
        if st.button("⚡ AI Optimizer", use_container_width=True):
            navigate_to("Resume Optimization")

    col5, col6 = st.columns(2)
    with col5:
        if st.button("🔍 Find Jobs", use_container_width=True):
            navigate_to("Find Jobs")
    with col6:
        if st.button("🎯 Job Matching", use_container_width=True):
            navigate_to("Job Matching")


def _render_system_status(db: DatabaseConnection, stats: dict):
    """Show system health indicators."""
    st.markdown(
        f"<div style='padding:6px 0;border-bottom:1px solid #1e293b;display:flex;justify-content:space-between;'>"
        f"<span style='color:#94a3b8;'>Database Engine</span> "
        f"<span style='color:#10b981;font-weight:600;'>● SQLite (v{stats['schema_version']})</span></div>",
        unsafe_allow_html=True,
    )
    ai_color = "#10b981" if stats["ai_enabled"] else "#f59e0b"
    ai_text = "Connected" if stats["ai_enabled"] else "Heuristic / Rule Engine"
    st.markdown(
        f"<div style='padding:6px 0;border-bottom:1px solid #1e293b;display:flex;justify-content:space-between;'>"
        f"<span style='color:#94a3b8;'>AI Provider</span> "
        f"<span style='color:{ai_color};font-weight:600;'>● {ai_text}</span></div>",
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
