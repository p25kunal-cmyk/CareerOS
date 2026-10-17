"""Streamlit UI page for AI Resume Optimization.

Features bullet rephrasing, MBA STAR framing, factual verification safeguards,
and branched version application.
"""

from __future__ import annotations

import streamlit as st

from src.ai.optimizer import ResumeOptimizer
from src.database.connection import DatabaseConnection
from src.resume.repository import ResumeRepository
from src.resume.sample_data import create_sample_mba_resume
from src.tracker.repository import TrackerRepository
from src.ui.components import empty_state, navigate_to, render_top_header


def render(db: DatabaseConnection):
    """Render the Resume Optimization page."""
    optimizer = ResumeOptimizer(db)
    resume_repo = ResumeRepository(db)
    tracker_repo = TrackerRepository(db)

    render_top_header("Resume Optimization", db)

    st.markdown("## ⚡ AI Resume Optimization")
    st.caption("Elevate bullet points using executive action verbs, quantifiable metrics, and verified STAR framing.")

    resumes = resume_repo.list_resumes()
    jobs = tracker_repo.list_jobs(limit=100)

    if not resumes:
        empty_state(
            "⚡",
            "No Resumes Available to Optimize",
            "Load our high-impact MBA sample resume or upload your own to begin AI optimization.",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✨ Load High-Impact MBA Sample Resume", type="primary", use_container_width=True):
                r_id, v_id = create_sample_mba_resume(resume_repo)
                navigate_to("Resume Optimization", active_resume_id=r_id, active_version_id=v_id)
        with c2:
            if st.button("📥 Upload Resume in My Resumes", use_container_width=True):
                navigate_to("My Resumes")
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

    # Action bar
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    b_col1, b_col2, b_col3 = st.columns([2, 1, 1])
    with b_col1:
        run_opt = st.button("✨ Generate AI Optimization Suggestions", type="primary", use_container_width=True)
    with b_col2:
        if st.button("👁️ Preview Resume", use_container_width=True):
            navigate_to("Resume Preview", active_resume_id=selected_resume_id, active_version_id=selected_version_id)
    with b_col3:
        if st.button("✏️ Edit in Studio", use_container_width=True):
            navigate_to("Resume Editor", active_resume_id=selected_resume_id, active_version_id=selected_version_id)

    st.markdown("---")

    if run_opt:
        with st.spinner("Analyzing bullet action verbs, quantifiable metrics, and STAR structure..."):
            suggestions = optimizer.optimize_version(
                version_id=selected_version_id,
                job_id=selected_job_id,
            )
            st.success(f"Generated {len(suggestions)} optimization suggestions!")

    # Fetch existing pending / verified suggestions
    existing_suggestions = optimizer.get_version_suggestions(selected_version_id)

    if not existing_suggestions:
        st.info("No active suggestions. Click **'Generate AI Optimization Suggestions'** above to analyze your resume.")
    else:
        st.markdown(f"##### Optimization Recommendations ({len(existing_suggestions)} bullets flagged)")
        st.caption("Review each proposed enhancement. Check 'Verify Metrics & Facts' before applying into a new tailored branch.")

        verified_count = sum(1 for s in existing_suggestions if s["status"] == "verified")

        for idx, s in enumerate(existing_suggestions):
            status = s["status"]
            status_color = "#10b981" if status == "verified" else ("#ef4444" if status == "rejected" else "#f59e0b")

            with st.expander(
                f"Item {idx + 1}: {s['original_text'][:55]}... [{status.upper()}]",
                expanded=(status != "rejected"),
            ):
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.markdown("**Original Bullet:**")
                    st.markdown(f"<div style='background: #1e293b; padding: 0.75rem; border-radius: 6px; border: 1px solid #334155; font-size: 0.9rem;'>{s['original_text']}</div>", unsafe_allow_html=True)
                with sc2:
                    st.markdown("**Proposed Rephrasing (MBA STAR Format):**")
                    st.markdown(f"<div style='background: #1e3a8a33; padding: 0.75rem; border-radius: 6px; border: 1px solid #3b82f644; font-size: 0.9rem; color: #93c5fd;'>{s['suggested_text']}</div>", unsafe_allow_html=True)

                st.markdown(f"*Rationale:* {s['rationale']}")
                if s.get("added_metrics"):
                    st.caption(f"Suggested metrics to verify: {s['added_metrics']}")

                # Verification toggle & reject button
                b_col1, b_col2, b_col3 = st.columns([3, 1, 1])
                with b_col1:
                    confirm = st.checkbox(
                        "✓ I verify these metrics and accomplishments are factual and accurate",
                        value=(status == "verified"),
                        key=f"chk_ver_{s['id']}",
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
                st.success(f"Created new optimized version: '{new_v.version_name}'!")
                navigate_to("Resume Editor", active_resume_id=selected_resume_id, active_version_id=new_v.id)
        else:
            st.button("🔀 Apply Verified Suggestions (Verify at least 1 suggestion first)", disabled=True, use_container_width=True)
