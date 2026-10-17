"""Streamlit UI page for the Application Tracker.

Features an interactive pipeline Kanban board, stage progression, and event audits.
"""

from __future__ import annotations

import streamlit as st

from src.database.connection import DatabaseConnection
from src.resume.repository import ResumeRepository
from src.tracker.models import ApplicationRecord
from src.tracker.repository import TrackerRepository
from src.ui.components import render_top_header, navigate_to

STATUS_CONFIG = {
    "saved": {"label": "Saved", "icon": "📌", "color": "#64748b"},
    "shortlisted": {"label": "Shortlisted", "icon": "⭐", "color": "#3b82f6"},
    "resume_prepared": {"label": "Resume Ready", "icon": "📄", "color": "#8b5cf6"},
    "applied": {"label": "Applied", "icon": "🚀", "color": "#0ea5e9"},
    "assessment": {"label": "Assessment / OA", "icon": "📊", "color": "#f59e0b"},
    "interview": {"label": "Interviewing", "icon": "💼", "color": "#ec4899"},
    "offer": {"label": "Offer Received", "icon": "🏆", "color": "#10b981"},
    "rejected": {"label": "Rejected", "icon": "❌", "color": "#ef4444"},
    "withdrawn": {"label": "Withdrawn", "icon": "↩️", "color": "#475569"},
}

KANBAN_COLUMNS = [
    ("saved", "📌 Saved / Shortlisted", ["saved", "shortlisted", "resume_prepared"]),
    ("applied", "🚀 Applied", ["applied"]),
    ("assessment", "📊 Assessment / OA", ["assessment"]),
    ("interview", "💼 Interviewing", ["interview"]),
    ("offer", "🏆 Offers", ["offer"]),
    ("archived", "📁 Archive", ["rejected", "withdrawn"]),
]


def render(db: DatabaseConnection):
    """Render Application Tracker page."""
    tracker_repo = TrackerRepository(db)
    resume_repo = ResumeRepository(db)

    render_top_header("Application Tracker", db)

    st.markdown("## 📋 Application Tracker")
    st.caption("Manage your job application pipeline through every stage from bookmark to offer.")

    stats = tracker_repo.get_pipeline_stats()
    total_apps = sum(stats.values())
    active_apps = stats.get("applied", 0) + stats.get("assessment", 0) + stats.get("interview", 0)
    offers = stats.get("offer", 0)

    # Metric summary row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon">📋</div>'
            f'<div class="metric-value">{total_apps}</div>'
            f'<div class="metric-label">Total Applications</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon">⚡</div>'
            f'<div class="metric-value">{active_apps}</div>'
            f'<div class="metric-label">Active Pipeline</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon">💼</div>'
            f'<div class="metric-value">{stats.get("interview", 0)}</div>'
            f'<div class="metric-label">Interviewing</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon">🏆</div>'
            f'<div class="metric-value" style="color: #10b981;">{offers}</div>'
            f'<div class="metric-label">Offers Received</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["📊 Pipeline Kanban", "📜 Application Timeline & Audit", "➕ Log Application"])

    all_apps = tracker_repo.list_applications()

    # ── TAB 1: KANBAN BOARD ───────────────────────────────────────
    with tab1:
        if not all_apps:
            st.info("No applications logged yet. Log an application in the 'Log Application' tab or save a job.")
        else:
            cols = st.columns(len(KANBAN_COLUMNS))
            for col_idx, (col_id, col_name, status_group) in enumerate(KANBAN_COLUMNS):
                with cols[col_idx]:
                    matching_apps = [a for a in all_apps if a.application.status in status_group]
                    st.markdown(
                        f"<div style='background: #1e293b; padding: 0.5rem 0.75rem; border-radius: 6px; font-weight: 600; font-size: 0.85rem; margin-bottom: 0.5rem; text-align: center; border-left: 3px solid #6366f1;'>"
                        f"{col_name} ({len(matching_apps)})"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                    for item in matching_apps:
                        app = item.application
                        job = item.job
                        cfg = STATUS_CONFIG.get(app.status, {"label": app.status, "icon": "•", "color": "#cbd5e1"})

                        with st.container():
                            st.markdown(
                                f"<div style='background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 0.75rem; margin-bottom: 0.65rem;'>"
                                f"<div style='font-weight: 600; font-size: 0.9rem; color: #f8fafc;'>{job.title}</div>"
                                f"<div style='font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.25rem;'>🏢 {job.company} · 📍 {job.location or 'Any'}</div>"
                                f"<div style='font-size: 0.75rem; color: {cfg['color']}; margin-bottom: 0.4rem;'>{cfg['icon']} {cfg['label']}</div>"
                                f"<div style='font-size: 0.72rem; color: #64748b;'>Resume: {item.resume_version_name or 'Default'}</div>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                            # Quick stage change selectbox
                            all_statuses = list(STATUS_CONFIG.keys())
                            cur_status_idx = all_statuses.index(app.status) if app.status in all_statuses else 0
                            new_st = st.selectbox(
                                "Move to",
                                all_statuses,
                                index=cur_status_idx,
                                key=f"kb_stage_{app.id}",
                                format_func=lambda s: f"{STATUS_CONFIG[s]['icon']} {STATUS_CONFIG[s]['label']}",
                                label_visibility="collapsed",
                            )
                            if new_st != app.status:
                                tracker_repo.update_status(app.id, new_st)
                                st.rerun()

    # ── TAB 2: AUDIT TIMELINE ─────────────────────────────────────
    with tab2:
        st.markdown("#### Chronological Audit Trail")
        st.caption("Inspect stage transitions, notes, and activity timeline for each application.")

        if not all_apps:
            st.info("No applications to show timeline.")
        else:
            selected_app_idx = st.selectbox(
                "Select Application",
                range(len(all_apps)),
                format_func=lambda i: f"{all_apps[i].job.company} — {all_apps[i].job.title} ({STATUS_CONFIG.get(all_apps[i].application.status, {}).get('label', all_apps[i].application.status)})",
            )
            selected_item = all_apps[selected_app_idx]
            timeline = tracker_repo.get_timeline(selected_item.application.id)

            st.markdown(f"##### Timeline for **{selected_item.job.title}** at **{selected_item.job.company}**")
            for ev in timeline:
                st.markdown(
                    f"<div style='border-left: 2px solid #6366f1; padding-left: 1rem; margin-bottom: 0.75rem;'>"
                    f"<span style='font-size: 0.78rem; color: #64748b;'>{ev.event_date or ev.created_at}</span><br>"
                    f"<b>{ev.event_type.replace('_', ' ').title()}</b>: {ev.description}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Add Note Form
            with st.form(key=f"note_form_{selected_item.application.id}"):
                note_text = st.text_input("Add Note / Milestone", placeholder="e.g. Cleared round 1 technical interview, next round scheduled on Monday...")
                submit_note = st.form_submit_button("Add Event")
                if submit_note and note_text.strip():
                    tracker_repo.add_event(selected_item.application.id, "note", note_text.strip())
                    st.success("Event logged!")
                    st.rerun()

    # ── TAB 3: LOG APPLICATION ────────────────────────────────────
    with tab3:
        st.markdown("#### Log New Application")
        st.caption("Connect a job opportunity with the specific resume version you submitted.")

        jobs_list = tracker_repo.list_jobs(limit=100)
        resumes_list = resume_repo.list_resumes()

        if not jobs_list:
            st.warning("No jobs tracked in the system yet. Please add a job first in the 'Find Jobs' page.")
            if st.button("Go to Find Jobs"):
                st.session_state["nav_target"] = "Find Jobs"
                st.rerun()
        else:
            with st.form("new_application_form"):
                job_idx = st.selectbox(
                    "Job Posting",
                    range(len(jobs_list)),
                    format_func=lambda i: f"{jobs_list[i].company} — {jobs_list[i].title} ({jobs_list[i].location or 'Any'})",
                )

                # Version selection
                all_versions = []
                for r in resumes_list:
                    for v in resume_repo.list_versions(r.id):
                        all_versions.append({
                            "id": v["id"],
                            "label": f"{r.name} - {v['version_name']} (v{v['version_number']})",
                        })

                version_id = None
                if all_versions:
                    ver_idx = st.selectbox(
                        "Resume Version Used",
                        range(len(all_versions)),
                        format_func=lambda i: all_versions[i]["label"],
                    )
                    version_id = all_versions[ver_idx]["id"]

                app_col1, app_col2 = st.columns(2)
                with app_col1:
                    init_status = st.selectbox(
                        "Initial Status",
                        list(STATUS_CONFIG.keys()),
                        index=3,  # 'applied' default
                        format_func=lambda s: f"{STATUS_CONFIG[s]['icon']} {STATUS_CONFIG[s]['label']}",
                    )
                    recruiter_name = st.text_input("Recruiter / Contact Name", placeholder="e.g. Sarah Jenkins")
                with app_col2:
                    follow_up = st.date_input("Follow-up Reminder Date")
                    recruiter_email = st.text_input("Recruiter Email", placeholder="e.g. sarah@company.com")

                app_notes = st.text_area("Notes", placeholder="Referral by senior batchmate; focus on strategy experience...")
                submit_app = st.form_submit_button("Track Application", type="primary")

                if submit_app:
                    chosen_job = jobs_list[job_idx]
                    app_id = tracker_repo.create_application(
                        job_id=chosen_job.id,
                        resume_version_id=version_id,
                        status=init_status,
                        follow_up_date=str(follow_up) if follow_up else None,
                        notes=app_notes,
                        recruiter_name=recruiter_name,
                        recruiter_email=recruiter_email,
                    )
                    st.success(f"Tracked application for **{chosen_job.title}** at **{chosen_job.company}**!")
                    st.rerun()
