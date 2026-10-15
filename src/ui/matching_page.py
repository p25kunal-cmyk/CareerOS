"""Streamlit UI page for Resume-Job Matching and Gap Analysis.

Provides multidimensional compatibility scoring, bullet evidence attribution,
and actionable skill gap recommendations.
"""

from __future__ import annotations

import streamlit as st

from src.database.connection import DatabaseConnection
from src.matching.engine import MatchingEngine
from src.resume.repository import ResumeRepository
from src.tracker.repository import TrackerRepository


def render(db: DatabaseConnection):
    """Render the Job Matching page."""
    matching_engine = MatchingEngine(db)
    resume_repo = ResumeRepository(db)
    tracker_repo = TrackerRepository(db)

    st.markdown("## 🎯 Job Matching & Gap Analysis")
    st.caption("Evaluate resume compatibility against target roles, identify skill gaps, and view verifiable evidence.")

    resumes = resume_repo.list_resumes()
    jobs = tracker_repo.list_jobs(limit=100)

    if not resumes:
        st.warning("No resumes found. Please upload a resume first.")
        return

    if not jobs:
        st.warning("No job opportunities found. Please capture or discover a job opportunity first.")
        return

    # Selectors
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        # Build flattened versions list
        all_versions = []
        for r in resumes:
            for v in resume_repo.list_versions(r.id):
                all_versions.append({
                    "id": v["id"],
                    "label": f"{r.name} — {v['version_name']} (v{v['version_number']})",
                })

        ver_idx = st.selectbox(
            "Select Resume Version",
            range(len(all_versions)),
            format_func=lambda i: all_versions[i]["label"],
        )
        selected_version_id = all_versions[ver_idx]["id"]

    with col_sel2:
        job_idx = st.selectbox(
            "Select Target Job Opportunity",
            range(len(jobs)),
            format_func=lambda i: f"{jobs[i].company} — {jobs[i].title} ({jobs[i].location or 'Any'})",
        )
        selected_job = jobs[job_idx]

    resume_version = resume_repo.get_version(selected_version_id)

    if st.button("⚡ Run Match Analysis", type="primary", use_container_width=True):
        st.session_state["active_match_run"] = True

    # Check if existing or session run
    match_result = matching_engine.get_match_result(selected_job.id, selected_version_id)
    if st.session_state.get("active_match_run") or match_result is None:
        if resume_version and selected_job:
            with st.spinner("Analyzing requirements, synonyms, and evidence..."):
                match_result = matching_engine.calculate_match(resume_version, selected_job)
                st.session_state["active_match_run"] = False

    if match_result:
        st.markdown("---")

        # Top score header
        score = match_result.overall_score
        if score >= 80:
            badge_color = "#10b981"
            rating_text = "Strong Match"
        elif score >= 65:
            badge_color = "#3b82f6"
            rating_text = "Good Match"
        elif score >= 50:
            badge_color = "#f59e0b"
            rating_text = "Moderate Match"
        else:
            badge_color = "#ef4444"
            rating_text = "Weak Match — Tailoring Recommended"

        st.markdown(
            f'<div style="background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; text-align: center; margin-bottom: 1.5rem;">'
            f'<div style="font-size: 2.8rem; font-weight: 800; color: {badge_color};">{score}%</div>'
            f'<div style="font-size: 1.1rem; font-weight: 600; color: #f8fafc; text-transform: uppercase; letter-spacing: 0.05em;">{rating_text}</div>'
            f'<div style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.3rem;">Method: {match_result.match_method.title()} Analysis · Stable UUID Evidence</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Factor Cards
        sb = match_result.score_breakdown
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            st.metric("Skills Match (40%)", f"{sb.skills_score}%")
        with f2:
            st.metric("Title Alignment (25%)", f"{sb.title_score}%")
        with f3:
            st.metric("Experience Depth (20%)", f"{sb.experience_score}%")
        with f4:
            st.metric("Academics (15%)", f"{sb.education_score}%")

        st.markdown("---")

        # Detailed breakdown
        c_req1, c_req2 = st.columns(2)

        with c_req1:
            st.markdown("##### ✅ Matched Requirements & Evidence")
            if not match_result.matched_requirements:
                st.caption("No direct skills matched.")
            else:
                for req in match_result.matched_requirements:
                    with st.expander(f"✓ {req}"):
                        evidence_bullets = match_result.resume_evidence.get(req, [])
                        if evidence_bullets:
                            st.markdown("**Verifiable Resume Evidence:**")
                            for b in evidence_bullets:
                                st.markdown(f"- *\"{b}\"*")
                        else:
                            st.caption("Matched via skill tag or overview context.")

            if match_result.partial_requirements:
                st.markdown("##### ⚠️ Partial / Context Matches")
                for req in match_result.partial_requirements:
                    st.markdown(f"- **{req}** (Keyword detected with different context)")

        with c_req2:
            st.markdown("##### ❌ Missing Requirements & Gaps")
            if not match_result.missing_requirements:
                st.success("All listed requirements appear in your resume!")
            else:
                for req in match_result.missing_requirements:
                    st.markdown(
                        f"<div style='background: #450a0a; border: 1px solid #7f1d1d; border-radius: 6px; padding: 0.4rem 0.75rem; margin-bottom: 0.4rem; color: #fca5a5; font-size: 0.85rem;'>"
                        f"✕ {req}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

            st.markdown("##### 💡 Actionable Improvement Recommendations")
            for sug in match_result.improvement_suggestions:
                st.info(sug)

        st.markdown("---")
        # Tailor action
        t_col1, t_col2 = st.columns([3, 1])
        with t_col1:
            st.markdown("##### Tailor Resume for this Job")
            st.caption("Create a branched version specifically customized for this opportunity.")
        with t_col2:
            if st.button("🔀 Branch Tailored Version", type="primary", use_container_width=True):
                new_v_name = f"{resume_version.version_name or 'v1.0'} - {selected_job.company} {selected_job.title[:15]}"
                forked = resume_repo.fork_version(selected_version_id, new_v_name)
                st.session_state["active_resume_id"] = forked.resume_id
                st.session_state["active_version_id"] = forked.id
                st.success(f"Branched new version: {new_v_name}!")
                st.session_state["nav_target"] = "Resume Editor"
                st.rerun()
