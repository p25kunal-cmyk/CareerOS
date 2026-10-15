"""Streamlit UI page for Job Discovery, Manual Entry, and Search Profiles.

Enables capturing job descriptions, deduplicating records, and defining MBA search targets.
"""

from __future__ import annotations

import streamlit as st

from src.database.connection import DatabaseConnection
from src.tracker.models import JobPosting, JobSearchProfile
from src.tracker.repository import TrackerRepository


def render(db: DatabaseConnection):
    """Render Find Jobs and Job Profiles page."""
    repo = TrackerRepository(db)

    st.markdown("## 🔍 Job Opportunities & Profiles")
    st.caption("Capture job opportunities, configure MBA target profiles, and discover matching roles.")

    tab1, tab2, tab3 = st.tabs(["💼 Job Directory", "➕ Capture Job Posting", "🎯 MBA Search Profiles"])

    # ── TAB 1: DIRECTORY ──────────────────────────────────────────
    with tab1:
        s_col1, s_col2 = st.columns([3, 1])
        with s_col1:
            search_query = st.text_input("Search Jobs", placeholder="Filter by title, company, or city...")
        with s_col2:
            status_filter = st.selectbox("Status", ["All", "active", "closed", "expired"])

        f_status = None if status_filter == "All" else status_filter
        jobs = repo.list_jobs(filter_status=f_status, query=search_query)

        st.markdown(f"##### Opportunities ({len(jobs)} total)")

        if not jobs:
            st.info("No jobs found. Use the **Capture Job Posting** tab to log a job.")
        else:
            for job in jobs:
                with st.expander(f"💼 {job.title} — {job.company} · ({job.location or 'Any'})", expanded=False):
                    c1, c2 = st.columns([3, 2])
                    with c1:
                        st.markdown(f"**Employment:** `{job.employment_type}` | **Source:** `{job.source_portal.upper()}`")
                        if job.salary_min or job.salary_max:
                            curr = job.salary_currency
                            sal_str = f"{job.salary_min or 0:,.0f} - {job.salary_max or 0:,.0f} {curr}"
                            st.markdown(f"**Compensation:** `{sal_str}`")
                        if job.required_skills:
                            skills_pills = " ".join(f"`{s}`" for s in job.required_skills)
                            st.markdown(f"**Required Skills:** {skills_pills}")
                        if job.original_url:
                            st.markdown(f"[🔗 View Original Posting]({job.original_url})")

                        if job.description:
                            st.caption(job.description[:300] + ("..." if len(job.description) > 300 else ""))

                    with c2:
                        st.markdown(f"**First Discovered:** `{job.first_discovered}`")
                        st.markdown(f"**Last Seen:** `{job.last_seen}`")

                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("📋 Track in Funnel", key=f"track_job_{job.id}", use_container_width=True):
                                repo.create_application(job_id=job.id, status="saved")
                                st.success("Added to Application Tracker!")
                                st.session_state["nav_target"] = "Application Tracker"
                                st.rerun()
                        with btn_col2:
                            if st.button("🗑️ Delete", key=f"del_job_{job.id}", use_container_width=True):
                                repo.delete_job(job.id)
                                st.rerun()

    # ── TAB 2: MANUAL CAPTURE ─────────────────────────────────────
    with tab2:
        st.markdown("#### Capture New Job Opportunity")
        st.caption("Paste job details from LinkedIn, IIMjobs, company portals, or campus placement postings.")

        with st.form("manual_job_form"):
            c_top1, c_top2 = st.columns(2)
            with c_top1:
                title = st.text_input("Job / Role Title *", placeholder="e.g. Product Manager - Core Platform")
                company = st.text_input("Company Name *", placeholder="e.g. Flipkart")
                location = st.text_input("Location", placeholder="e.g. Bangalore, India (or Remote)")
                emp_type = st.selectbox("Employment Type", ["Full-time", "Internship", "Contract", "Part-time"])

            with c_top2:
                portal = st.selectbox("Source Portal", ["manual", "linkedin", "iimjobs", "indeed", "naukri", "campus_portal"])
                orig_url = st.text_input("Job Posting URL", placeholder="https://www.linkedin.com/jobs/view/...")
                sal_min = st.number_input("Minimum Salary / CTC", min_value=0.0, step=100000.0, value=0.0)
                sal_max = st.number_input("Maximum Salary / CTC", min_value=0.0, step=100000.0, value=0.0)

            skills_raw = st.text_input("Key Skills (comma-separated)", placeholder="Product Strategy, SQL, Roadmapping, A/B Testing")
            description = st.text_area("Full Job Description", height=180, placeholder="Paste entire JD text here...")

            submit_job = st.form_submit_button("💾 Save Opportunity", type="primary")

            if submit_job:
                if not title.strip() or not company.strip():
                    st.error("Role Title and Company Name are required.")
                else:
                    skills_list = [s.strip() for s in skills_raw.split(",") if s.strip()]
                    job_obj = JobPosting(
                        title=title.strip(),
                        company=company.strip(),
                        location=location.strip() or "Any",
                        employment_type=emp_type,
                        salary_min=sal_min if sal_min > 0 else None,
                        salary_max=sal_max if sal_max > 0 else None,
                        salary_currency="INR",
                        source_portal=portal,
                        original_url=orig_url.strip() or None,
                        required_skills=skills_list,
                        description=description.strip(),
                        is_manually_entered=True,
                    )
                    job_id, is_new = repo.add_or_update_job(job_obj)
                    if is_new:
                        st.success(f"Added new opportunity: **{title}** at **{company}**!")
                    else:
                        st.info(f"Updated existing opportunity: **{title}** at **{company}** (Deduplicated)")
                    st.rerun()

    # ── TAB 3: SEARCH PROFILES ────────────────────────────────────
    with tab3:
        st.markdown("#### MBA Search Profiles")
        st.caption("Configure target domains, roles, and compensation preferences to filter opportunities.")

        profiles = repo.list_profiles()
        for prof in profiles:
            with st.expander(f"{'⭐ [DEFAULT] ' if prof.is_default else '🎯 '}{prof.name}", expanded=prof.is_default):
                p_c1, p_c2 = st.columns([3, 1])
                with p_c1:
                    st.markdown(f"**Target Roles:** {', '.join(prof.target_roles) or 'Any'}")
                    st.markdown(f"**Target Locations:** {', '.join(prof.preferred_locations) or 'Any'} (Remote: `{prof.remote_preference}`)")
                    st.markdown(f"**Target Industries:** {', '.join(prof.preferred_industries) or 'Any'}")
                    if prof.min_salary:
                        st.markdown(f"**Min Compensation:** `₹{prof.min_salary:,.0f}`")
                    if prof.required_keywords:
                        st.markdown(f"**Required Keywords:** {', '.join(prof.required_keywords)}")

                with p_c2:
                    if not prof.is_default:
                        if st.button("⭐ Set Default", key=f"prof_def_{prof.id}", use_container_width=True):
                            repo.set_default_profile(prof.id)
                            st.rerun()
                    if st.button("🗑️ Delete", key=f"prof_del_{prof.id}", use_container_width=True):
                        repo.delete_profile(prof.id)
                        st.rerun()

        st.markdown("---")
        with st.form("new_profile_form"):
            st.markdown("##### ➕ Create New Target Profile")
            prof_name = st.text_input("Profile Name", placeholder="e.g. Product Management - Tech")
            p_roles = st.text_input("Target Roles (comma-separated)", placeholder="Product Manager, Associate PM, Technical PM")
            p_locs = st.text_input("Target Locations (comma-separated)", placeholder="Bangalore, Mumbai, Delhi NCR, Remote")
            p_ind = st.text_input("Preferred Industries (comma-separated)", placeholder="Tech, E-commerce, FinTech, SaaS")
            p_min_sal = st.number_input("Minimum Target CTC (INR)", min_value=0.0, step=200000.0, value=2000000.0)
            p_is_def = st.checkbox("Set as default profile", value=False)

            submit_prof = st.form_submit_button("Create Search Profile", type="primary")
            if submit_prof and prof_name.strip():
                new_profile = JobSearchProfile(
                    name=prof_name.strip(),
                    is_default=p_is_def,
                    target_roles=[r.strip() for r in p_roles.split(",") if r.strip()],
                    preferred_locations=[l.strip() for l in p_locs.split(",") if l.strip()],
                    preferred_industries=[i.strip() for i in p_ind.split(",") if i.strip()],
                    min_salary=p_min_sal,
                )
                repo.create_profile(new_profile)
                st.success(f"Created profile '{prof_name}'!")
                st.rerun()
