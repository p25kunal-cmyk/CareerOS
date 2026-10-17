"""Streamlit UI page for Resume-Job Matching and Gap Analysis.

Provides multidimensional compatibility scoring, bullet evidence attribution,
and actionable skill gap recommendations.
"""

from __future__ import annotations

import streamlit as st

from src.database.connection import DatabaseConnection
from src.matching.engine import MatchingEngine
from src.resume.repository import ResumeRepository
from src.resume.sample_data import create_sample_mba_resume
from src.tracker.repository import TrackerRepository
from src.ui.components import empty_state, navigate_to, render_top_header


def render(db: DatabaseConnection):
    """Render the Job Matching page."""
    matching_engine = MatchingEngine(db)
    resume_repo = ResumeRepository(db)
    tracker_repo = TrackerRepository(db)

    render_top_header("Job Matching", db)

    st.markdown("## 🎯 Job Matching & Gap Analysis")
    st.caption("Evaluate resume compatibility against target roles, identify skill gaps, and view verifiable evidence.")

    resumes = resume_repo.list_resumes()
    jobs = tracker_repo.list_jobs(limit=100)

    if not resumes:
        empty_state(
            "🎯",
            "No Resumes Available for Matching",
            "Load our high-impact MBA sample resume or upload your own to analyze compatibility.",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✨ Load High-Impact MBA Sample Resume", type="primary", use_container_width=True):
                r_id, v_id = create_sample_mba_resume(resume_repo)
                navigate_to("Job Matching", active_resume_id=r_id, active_version_id=v_id)
        with c2:
            if st.button("📥 Upload Resume in My Resumes", use_container_width=True):
                navigate_to("My Resumes")
        return

    if not jobs:
        empty_state(
            "💼",
            "No Job Opportunities Found",
            "Add a target role in 'Find Jobs' or capture an opportunity to run matching analysis.",
        )
        if st.button("🔍 Go to Find Jobs", type="primary"):
            navigate_to("Find Jobs")
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
                    "resume_id": r.id,
                    "label": f"{r.name} — {v['version_name']} (v{v['version_number']})",
                })

        ver_idx = st.selectbox(
            "Select Resume Version",
            range(len(all_versions)),
            format_func=lambda i: all_versions[i]["label"],
        )
        selected_version_id = all_versions[ver_idx]["id"]
        selected_resume_id = all_versions[ver_idx]["resume_id"]

    with col_sel2:
        job_idx = st.selectbox(
            "Select Target Job Opportunity",
            range(len(jobs)),
            format_func=lambda i: f"{jobs[i].company} — {jobs[i].title} ({jobs[i].location or 'Any'})",
        )
        selected_job = jobs[job_idx]

    st.markdown("---")

    resume_version = resume_repo.get_version(selected_version_id)
    if not resume_version:
        st.error("Could not load version data.")
        return

    with st.spinner("Analyzing semantic fit, experience depth, and requirement evidence..."):
        match_result = matching_engine.match(resume_version, selected_job)

        # Score Dashboard
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Overall Fit Score", f"{match_result.overall_score}%", help="Weighted blend of hard skills, experience, and domain alignment")
        m2.metric("Requirements Match", f"{match_result.requirement_score}%")
        m3.metric("Experience Depth", f"{match_result.experience_score}%")
        m4.metric("Matched Criteria", f"{len(match_result.matched_requirements)} / {len(selected_job.requirements or [])}")

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        # Visual score bar
        st.progress(match_result.overall_score / 100.0)

        # Quick navigation actions
        q_col1, q_col2, q_col3 = st.columns([1, 1, 1])
        with q_col1:
            if st.button("👁️ Preview This Resume", use_container_width=True):
                navigate_to("Resume Preview", active_resume_id=selected_resume_id, active_version_id=selected_version_id)
        with q_col2:
            if st.button("⚡ AI Optimize for this Job", type="primary", use_container_width=True):
                navigate_to("Resume Optimization", active_resume_id=selected_resume_id, active_version_id=selected_version_id)
        with q_col3:
            if st.button("✏️ Edit in Studio", use_container_width=True):
                navigate_to("Resume Editor", active_resume_id=selected_resume_id, active_version_id=selected_version_id)

        st.markdown("---")

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
                st.success(f"Branched new version: {new_v_name}!")
                navigate_to("Resume Editor", active_resume_id=forked.resume_id, active_version_id=forked.id)
