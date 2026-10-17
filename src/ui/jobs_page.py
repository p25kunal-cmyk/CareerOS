"""Streamlit UI page for Job Discovery, Source Plugins, and Search Profiles.

Enables automated scraping across job portals, deduplicating records,
and configuring MBA target profiles.
"""

from __future__ import annotations

import streamlit as st

from src.database.connection import DatabaseConnection
from src.jobs.engine import JobDiscoveryEngine
from src.tracker.models import JobPosting, JobSearchProfile
from src.tracker.repository import TrackerRepository
from src.ui.components import render_top_header, navigate_to


def render(db: DatabaseConnection):
    """Render Find Jobs, Discovery, and Job Profiles page."""
    tracker_repo = TrackerRepository(db)
    engine = JobDiscoveryEngine(db)

    render_top_header("Find Jobs", db)

    st.markdown("## 🔍 Job Opportunities & Discovery")
    st.caption("Capture job opportunities, run automated multi-source discovery, and manage MBA search targets.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "💼 Job Directory",
        "⚡ Automated Discovery",
        "➕ Manual Job Entry",
        "🎯 MBA Search Profiles",
    ])

    # ── TAB 1: DIRECTORY ──────────────────────────────────────────
    with tab1:
        s_col1, s_col2 = st.columns([3, 1])
        with s_col1:
            search_query = st.text_input("Search Jobs", placeholder="Filter by title, company, or city...")
        with s_col2:
            status_filter = st.selectbox("Status", ["All", "active", "closed", "expired"])

        f_status = None if status_filter == "All" else status_filter
        jobs = tracker_repo.list_jobs(filter_status=f_status, query=search_query)

        st.markdown(f"##### Opportunities ({len(jobs)} total)")

        if not jobs:
            st.info("No jobs found. Run **Automated Discovery** or use **Manual Job Entry**.")
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

                        btn_col1, btn_col2, btn_col3 = st.columns(3)
                        with btn_col1:
                            if st.button("📋 Track", key=f"track_job_{job.id}", type="primary", use_container_width=True):
                                tracker_repo.create_application(job_id=job.id, status="saved")
                                st.success("Added to Tracker!")
                                navigate_to("Application Tracker")
                        with btn_col2:
                            if st.button("🎯 Match", key=f"match_job_{job.id}", use_container_width=True):
                                navigate_to("Job Matching")
                        with btn_col3:
                            if st.button("🗑️ Del", key=f"del_job_{job.id}", use_container_width=True):
                                tracker_repo.delete_job(job.id)
                                st.rerun()

    # ── TAB 2: AUTOMATED DISCOVERY ────────────────────────────────
    with tab2:
        st.markdown("#### Automated Multi-Portal Discovery")
        st.caption("Search across LinkedIn, IIMjobs, Indeed, and Naukri with intelligent deduplication and rate limiting.")

        profiles = tracker_repo.list_profiles()
        sources_status = engine.list_source_statuses()

        col_cfg1, col_cfg2 = st.columns([3, 2])
        with col_cfg1:
            if profiles:
                selected_prof_idx = st.selectbox(
                    "Active Search Profile Criteria",
                    range(len(profiles)),
                    format_func=lambda i: f"{'⭐ ' if profiles[i].is_default else ''}{profiles[i].name} ({', '.join(profiles[i].target_roles[:2])})",
                )
                selected_profile = profiles[selected_prof_idx]
            else:
                selected_profile = None
                st.warning("No search profiles found. Create one in the MBA Search Profiles tab.")

            limit_per_source = st.slider("Max results per role per portal", min_value=5, max_value=25, value=10)

        with col_cfg2:
            st.markdown("##### Portal Statuses")
            for src in sources_status:
                s_icon = "🟢" if src["is_enabled"] else "⚪"
                last_run = src["last_successful_run"] or "Never"
                st.markdown(f"{s_icon} **{src['name']}** (`{src['source_type']}`) · *Last:* `{last_run}`")

        if st.button("⚡ Start Job Discovery", type="primary", use_container_width=True):
            with st.spinner("Scraping portals and deduplicating opportunities..."):
                res = engine.run_discovery(
                    profile_id=selected_profile.id if selected_profile else None,
                    limit_per_source=limit_per_source,
                )

                st.markdown("---")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Opportunities Processed", res.items_processed)
                m2.metric("New Added", f"+{res.items_added}")
                m3.metric("Updated (Deduplicated)", f"~{res.items_updated}")
                m4.metric("Duration", f"{res.duration_seconds}s")

                if res.sources_succeeded:
                    st.success(f"Successfully queried sources: {', '.join(res.sources_succeeded)}")
                if res.sources_failed:
                    st.warning(f"Failed sources: {', '.join(res.sources_failed)}")

        st.markdown("---")
        st.markdown("##### Source Configuration & Toggles")
        for src in sources_status:
            t_col1, t_col2 = st.columns([4, 1])
            with t_col1:
                st.markdown(f"**{src['name']}** — `{src['source_type']}`")
                if src.get("last_error"):
                    st.caption(f"Last Error: {src['last_error']}")
            with t_col2:
                new_state = st.toggle("Enabled", value=bool(src["is_enabled"]), key=f"toggle_{src['id']}")
                if new_state != bool(src["is_enabled"]):
                    engine.toggle_source(src["id"], new_state)
                    st.rerun()

    # ── TAB 3: MANUAL CAPTURE ─────────────────────────────────────
    with tab3:
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
                    job_id, is_new = tracker_repo.add_or_update_job(job_obj)
                    if is_new:
                        st.success(f"Added new opportunity: **{title}** at **{company}**!")
                    else:
                        st.info(f"Updated existing opportunity: **{title}** at **{company}** (Deduplicated)")
                    st.rerun()

    # ── TAB 4: SEARCH PROFILES ────────────────────────────────────
    with tab4:
        st.markdown("#### MBA Search Profiles")
        st.caption("Configure target domains, roles, and compensation preferences to filter opportunities.")

        profiles = tracker_repo.list_profiles()
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
                            tracker_repo.set_default_profile(prof.id)
                            st.rerun()
                    if st.button("🗑️ Delete", key=f"prof_del_{prof.id}", use_container_width=True):
                        tracker_repo.delete_profile(prof.id)
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
                tracker_repo.create_profile(new_profile)
                st.success(f"Created profile '{prof_name}'!")
                st.rerun()
