"""Streamlit UI page for AI Resume Optimization.

Features bullet rephrasing, MBA STAR framing, factual verification safeguards,
and branched version application.
"""

from __future__ import annotations

import streamlit as st

from src.ai.optimizer import ResumeOptimizer
from src.database.connection import DatabaseConnection
from src.resume.repository import ResumeRepository
from src.tracker.repository import TrackerRepository


def render(db: DatabaseConnection):
    """Render the Resume Optimization page."""
    optimizer = ResumeOptimizer(db)
    resume_repo = ResumeRepository(db)
    tracker_repo = TrackerRepository(db)

    st.markdown("## ⚡ AI Resume Optimization")
    st.caption("Elevate bullet points using executive action verbs, quantifiable metrics, and verified STAR framing.")

    resumes = resume_repo.list_resumes()
    jobs = tracker_repo.list_jobs(limit=100)

    if not resumes:
        st.warning("No resumes found. Please upload a resume first.")
        return

    # Top selectors
    c_sel1, c_sel2 = st.columns(2)
    with c_sel1:
        all_versions = []
        for r in resumes:
            for v in resume_repo.list_versions(r.id):
                all_versions.append({
                    "id": v["id"],
                    "resume_id": r.id,
                    "label": f"{r.name} — {v['version_name']} (v{v['version_number']})",
                })

        ver_idx = st.selectbox(
            "Select Resume Version to Optimize",
            range(len(all_versions)),
            format_func=lambda i: all_versions[i]["label"],
        )
        selected_version_id = all_versions[ver_idx]["id"]
        selected_resume_id = all_versions[ver_idx]["resume_id"]

    with c_sel2:
        job_options = [{"id": None, "label": "General MBA Optimization (No specific job)"}]
        for j in jobs:
            job_options.append({"id": j.id, "label": f"{j.company} — {j.title}"})

        job_idx = st.selectbox(
            "Target Opportunity (Optional)",
            range(len(job_options)),
            format_func=lambda i: job_options[i]["label"],
        )
        selected_job_id = job_options[job_idx]["id"]

    # Action Trigger
    if st.button("🚀 Analyze & Generate Suggestions", type="primary", use_container_width=True):
        with st.spinner("Analyzing bullets with MBA STAR framework..."):
            new_sugs = optimizer.optimize_version(selected_version_id, job_id=selected_job_id)
            if new_sugs:
                st.success(f"Generated {len(new_sugs)} optimization suggestions!")
            else:
                st.info("No new suggestions generated.")
            st.rerun()

    st.markdown("---")

    # Suggestions list
    suggestions = optimizer.list_suggestions(selected_version_id, only_pending=False)

    if not suggestions:
        st.info("No suggestions available for this version. Click 'Analyze & Generate Suggestions' above.")
    else:
        pending_count = sum(1 for s in suggestions if not s["is_applied"] and s["verification_status"] != "rejected")
        verified_count = sum(1 for s in suggestions if not s["is_applied"] and s["verification_status"] == "verified")

        st.markdown(f"##### Suggestions Review ({pending_count} pending, {verified_count} verified)")
        st.caption("Review proposed rewrites. To ensure academic integrity, verify that all introduced metrics are accurate before applying.")

        for s in suggestions:
            is_applied = bool(s["is_applied"])
            status = s["verification_status"]

            border_color = "#10b981" if status == "verified" else ("#f59e0b" if status == "needs_verification" else "#334155")
            if is_applied:
                border_color = "#6366f1"

            with st.container():
                st.markdown(
                    f"<div style='border: 1px solid {border_color}; background: #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem;'>"
                    f"<div style='font-size: 0.75rem; color: #94a3b8; margin-bottom: 0.4rem;'>Status: <b>{status.upper()}</b> {'· [APPLIED]' if is_applied else ''}</div>"
                    f"<div style='font-size: 0.85rem; color: #fca5a5; margin-bottom: 0.4rem;'><b>Original:</b> {s['original_text']}</div>"
                    f"<div style='font-size: 0.9rem; color: #a7f3d0; margin-bottom: 0.4rem;'><b>Proposed:</b> {s['proposed_text']}</div>"
                    f"<div style='font-size: 0.75rem; color: #94a3b8;'><i>Reason: {s['reason']}</i></div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if not is_applied:
                    b_col1, b_col2, b_col3 = st.columns([2, 1, 1])
                    with b_col1:
                        confirm = st.checkbox(
                            "✓ Confirm this metric / achievement is factually accurate",
                            value=(status == "verified"),
                            key=f"verif_check_{s['id']}",
                        )
                        if confirm and status != "verified":
                            optimizer.update_suggestion_status(s["id"], "verified")
                            st.rerun()
                        elif not confirm and status == "verified":
                            optimizer.update_suggestion_status(s["id"], "pending")
                            st.rerun()

                    with b_col2:
                        pass
                    with b_col3:
                        if st.button("✕ Reject", key=f"rej_sug_{s['id']}", use_container_width=True):
                            optimizer.update_suggestion_status(s["id"], "rejected")
                            st.rerun()

        st.markdown("---")
        # Apply button
        if verified_count > 0:
            if st.button(f"🔀 Apply {verified_count} Verified Suggestions into New Branched Version", type="primary", use_container_width=True):
                new_v = optimizer.apply_approved_suggestions(selected_version_id)
                st.session_state["active_resume_id"] = selected_resume_id
                st.session_state["active_version_id"] = new_v.id
                st.success(f"Created new optimized version: '{new_v.version_name}'!")
                st.session_state["nav_target"] = "Resume Editor"
                st.rerun()
        else:
            st.button("🔀 Apply Verified Suggestions (Verify at least 1 suggestion first)", disabled=True, use_container_width=True)
