"""Streamlit UI page for Resume Management and Import.

Provides resume upload, parsing preview, library management, live visual previewing,
and version diffing.
"""

from __future__ import annotations

import io
import os
import streamlit as st

from src.database.connection import DatabaseConnection
from src.resume.diff import ResumeDiffer
from src.resume.exporter import ResumeExporter
from src.resume.models import ResumeVersionData
from src.resume.parser import ResumeParser
from src.resume.repository import ResumeRepository
from src.resume.sample_data import create_sample_mba_resume
from src.resume.templates import TEMPLATES
from src.ui.components import empty_state, navigate_to, render_top_header
from src.ui.resume_preview import render_resume_preview_component


def render(db: DatabaseConnection):
    """Render the My Resumes page."""
    repo = ResumeRepository(db)
    parser = ResumeParser()

    render_top_header("My Resumes", db)

    st.markdown("## 📄 Resume Management & Library")
    st.caption("Upload, organize, preview, tailor, and version your master and job-specific resumes.")

    resumes = repo.list_resumes()
    master_resume = next((r for r in resumes if r.is_master), None)

    # Top metric summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon">📑</div>'
            f'<div class="metric-value">{len(resumes)}</div>'
            f'<div class="metric-label">Total Resumes</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col2:
        m_name = master_resume.name if master_resume else "None Set"
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon">⭐</div>'
            f'<div class="metric-value" style="font-size: 1.1rem; padding-top: 0.5rem;">{m_name[:18]}</div>'
            f'<div class="metric-label">Master Resume</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col3:
        total_versions = sum(r.version_count for r in resumes)
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon">🔀</div>'
            f'<div class="metric-value">{total_versions}</div>'
            f'<div class="metric-label">Total Versions</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-icon">🎯</div>'
            f'<div class="metric-value">IIM Standard</div>'
            f'<div class="metric-label">Default Template</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📚 Resume Library",
        "📥 Import & Parse",
        "👁️ Live Document Preview",
        "🔍 Compare Versions (Diff)",
    ])

    # ── TAB 1: LIBRARY ────────────────────────────────────────────
    with tab1:
        if not resumes:
            empty_state(
                "📭",
                "No Resumes Found in Library",
                "Get started in seconds by loading our battle-tested MBA Master Resume or upload your own file.",
            )
            c_act1, c_act2 = st.columns(2)
            with c_act1:
                if st.button("✨ Load High-Impact MBA Sample Resume (IIM Format)", type="primary", use_container_width=True):
                    r_id, v_id = create_sample_mba_resume(repo)
                    navigate_to("My Resumes", active_resume_id=r_id, active_version_id=v_id)
            with c_act2:
                if st.button("📥 Upload Your Own Resume File", use_container_width=True):
                    st.info("Switch to the '📥 Import & Parse' tab above to upload your PDF, DOCX, or TXT file.")
        else:
            for r in resumes:
                with st.expander(f"{'⭐ [MASTER] ' if r.is_master else '📄 '}{r.name} · ({r.version_count} versions)", expanded=r.is_master):
                    c_info, c_actions = st.columns([3, 3])
                    with c_info:
                        st.markdown(f"**Original File:** `{r.original_filename or 'Manual / Imported'}` ({r.file_type or 'custom'})")
                        st.markdown(f"**Last Updated:** `{r.updated_at}`")
                        if r.notes:
                            st.caption(f"Notes: {r.notes}")

                    with c_actions:
                        subcol1, subcol2, subcol3 = st.columns(3)
                        with subcol1:
                            if st.button("✏️ Edit", key=f"edit_{r.id}", use_container_width=True):
                                navigate_to("Resume Editor", active_resume_id=r.id)

                        with subcol2:
                            if st.button("👁️ Preview", key=f"pv_btn_{r.id}", type="primary", use_container_width=True):
                                navigate_to("Resume Preview", active_resume_id=r.id)

                        with subcol3:
                            if not r.is_master:
                                if st.button("⭐ Set Master", key=f"master_{r.id}", use_container_width=True):
                                    repo.set_master_resume(r.id)
                                    st.success(f"Set '{r.name}' as master resume!")
                                    st.rerun()

                        # Export options
                        latest_v = repo.get_latest_version(r.id)
                        if latest_v:
                            dl_c1, dl_c2 = st.columns(2)
                            with dl_c1:
                                docx_bytes = ResumeExporter.export_docx(latest_v, "iim_nagpur")
                                st.download_button(
                                    label="📥 Word (.docx)",
                                    data=docx_bytes,
                                    file_name=f"{r.name.replace(' ', '_')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_docx_{r.id}",
                                    use_container_width=True,
                                )
                            with dl_c2:
                                pdf_bytes = ResumeExporter.export_pdf(latest_v, "iim_nagpur")
                                st.download_button(
                                    label="📕 PDF (.pdf)",
                                    data=pdf_bytes,
                                    file_name=f"{r.name.replace(' ', '_')}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_pdf_{r.id}",
                                    use_container_width=True,
                                )

                    # Inline quick document preview accordion
                    with st.expander("👁️ Quick View Document Sheet", expanded=False):
                        latest_v = repo.get_latest_version(r.id)
                        if latest_v:
                            render_resume_preview_component(
                                version_data=latest_v,
                                resume_name=r.name,
                                default_template="iim_nagpur",
                                key_prefix=f"inline_{r.id}",
                                show_toolbar=True,
                                show_export_buttons=False,
                            )

                    # Versions sub-list
                    st.markdown("##### Version History")
                    versions = repo.list_versions(r.id)
                    for v in versions:
                        v_col1, v_col2, v_col3, v_col4 = st.columns([3, 2, 1, 1])
                        with v_col1:
                            st.markdown(f"- **{v['version_name']}** (`v{v['version_number']}`) — {v.get('description') or 'No description'}")
                        with v_col2:
                            st.caption(f"Created: {v['created_at']}")
                        with v_col3:
                            if st.button("Branch", key=f"branch_{v['id']}", help="Fork a new tailored variant"):
                                new_v = repo.fork_version(v["id"], f"{v['version_name']} - Variant")
                                st.success(f"Created branch {new_v.version_name}!")
                                st.rerun()
                        with v_col4:
                            if st.button("Edit", key=f"edit_ver_{v['id']}", help="Open in editor"):
                                navigate_to("Resume Editor", active_resume_id=r.id, active_version_id=v["id"])

    # ── TAB 2: IMPORT & PARSE ─────────────────────────────────────
    with tab2:
        st.markdown("#### Import Resume File")
        st.markdown("Upload your existing resume in **PDF**, **DOCX**, or **TXT** format. The parser will extract contact details, classify sections, and detect achievements and metrics.")

        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "docx", "doc", "txt", "md"],
            help="Upload your master or MBA resume.",
        )

        resume_name = st.text_input("Resume Profile Name", value=uploaded_file.name.rsplit(".", 1)[0] if uploaded_file else "Master Resume - MBA")
        is_master = st.checkbox("Set as primary Master Resume", value=(len(resumes) == 0))

        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            with st.spinner("Parsing document structure, sections, and metrics..."):
                try:
                    parsed = parser.parse_file(file_bytes, uploaded_file.name)
                    st.success(f"Successfully parsed **{uploaded_file.name}** ({len(parsed.sections)} sections detected)")

                    # Parse preview summary
                    st.markdown("---")
                    st.markdown("##### Extraction Summary")

                    p_col1, p_col2 = st.columns(2)
                    with p_col1:
                        st.markdown("**Candidate Contact Information**")
                        st.markdown(f"- **Name:** {parsed.contact_info.name or '*(Not detected)*'}")
                        st.markdown(f"- **Email:** {parsed.contact_info.email or '*(Not detected)*'}")
                        st.markdown(f"- **Phone:** {parsed.contact_info.phone or '*(Not detected)*'}")
                        st.markdown(f"- **LinkedIn:** {parsed.contact_info.linkedin or '*(Not detected)*'}")

                    with p_col2:
                        st.markdown("**Identified Sections**")
                        for s in parsed.sections:
                            metric_count = sum(len(b.metrics) for b in s.bullets)
                            verb_count = sum(1 for b in s.bullets if b.action_verb)
                            st.markdown(f"- **{s.title}** (`{s.section_type}`) · {len(s.bullets)} bullets ({verb_count} action verbs, {metric_count} metrics)")

                    if parsed.warnings:
                        for w in parsed.warnings:
                            st.warning(w)

                    # LIVE PREVIEW OF PARSED DOCUMENT BEFORE SAVING
                    st.markdown("##### 👁️ Live Document Preview (Parsed Content)")
                    st.caption("Verify how your extracted resume looks rendered in paper format before saving.")
                    temp_preview_ver = ResumeVersionData(
                        id="temp_import_preview",
                        resume_id="temp_import_preview",
                        version_name="Imported Version",
                        version_number=1,
                        sections=parsed.sections,
                    )
                    render_resume_preview_component(
                        version_data=temp_preview_ver,
                        resume_name=resume_name,
                        default_template="iim_nagpur",
                        key_prefix="import_parsed_pv",
                        show_toolbar=True,
                        show_export_buttons=False,
                    )

                    if st.button("💾 Save Resume to Database", type="primary", use_container_width=True):
                        r_id, v_id = repo.save_parsed_resume(
                            resume_name=resume_name,
                            parsed=parsed,
                            original_filename=uploaded_file.name,
                            is_master=is_master,
                        )
                        st.success(f"Resume '{resume_name}' saved successfully!")
                        navigate_to("Resume Editor", active_resume_id=r_id, active_version_id=v_id)

                except Exception as e:
                    st.error(f"Error parsing resume: {str(e)}")

    # ── TAB 3: LIVE DOCUMENT PREVIEW ─────────────────────────────
    with tab3:
        if not resumes:
            st.info("No resumes uploaded yet to preview.")
        else:
            default_res_id = st.session_state.get("active_resume_id", resumes[0].id)
            res_index = next((i for i, r in enumerate(resumes) if r.id == default_res_id), 0)

            c_pick1, c_pick2 = st.columns(2)
            with c_pick1:
                cur_res = st.selectbox(
                    "Select Resume to Preview",
                    resumes,
                    index=res_index,
                    format_func=lambda r: f"{'⭐ ' if r.is_master else ''}{r.name}",
                    key="tab_pv_res_select",
                )
            with c_pick2:
                r_versions = repo.list_versions(cur_res.id)
                ver_sel = st.selectbox(
                    "Select Version",
                    r_versions,
                    format_func=lambda v: f"{v['version_name']} (v{v['version_number']})",
                    key="tab_pv_ver_select",
                )

            if ver_sel:
                ver_obj = repo.get_version(ver_sel["id"])
                if ver_obj:
                    render_resume_preview_component(
                        version_data=ver_obj,
                        resume_name=cur_res.name,
                        default_template="iim_nagpur",
                        key_prefix=f"tab3_{cur_res.id}",
                        show_toolbar=True,
                        show_export_buttons=True,
                    )

    # ── TAB 4: VISUAL DIFF ────────────────────────────────────────
    with tab4:
        st.markdown("#### Version Comparison & Visual Diff")
        st.caption("Compare two versions to inspect additions, deletions, rephrasings, and similarity score.")

        all_versions_options = []
        for r in resumes:
            for v in repo.list_versions(r.id):
                all_versions_options.append({
                    "label": f"{r.name} — {v['version_name']} (v{v['version_number']})",
                    "version_id": v["id"],
                })

        if len(all_versions_options) < 2:
            st.info("You need at least 2 versions to perform a comparison. Upload or branch a version first.")
        else:
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                base_idx = st.selectbox(
                    "Base Version (Original)",
                    range(len(all_versions_options)),
                    format_func=lambda i: all_versions_options[i]["label"],
                    index=0,
                )
            with d_col2:
                target_idx = st.selectbox(
                    "Target Version (Modified / Tailored)",
                    range(len(all_versions_options)),
                    format_func=lambda i: all_versions_options[i]["label"],
                    index=1 if len(all_versions_options) > 1 else 0,
                )

            if st.button("🔍 Compare Versions", type="primary"):
                v_base = repo.get_version(all_versions_options[base_idx]["version_id"])
                v_target = repo.get_version(all_versions_options[target_idx]["version_id"])

                if v_base and v_target:
                    diff_res = ResumeDiffer.diff_versions(v_base, v_target)

                    st.markdown("---")
                    # Summary metrics
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Similarity", f"{diff_res.similarity_ratio}%")
                    m2.metric("Added Bullets", f"+{diff_res.added_bullets}")
                    m3.metric("Removed Bullets", f"-{diff_res.removed_bullets}")
                    m4.metric("Modified Bullets", f"~{diff_res.modified_bullets}")
                    m5.metric("Modified Sections", f"{diff_res.modified_sections}")

                    st.markdown("##### Section & Bullet Breakdown")
                    for s_diff in diff_res.sections:
                        with st.expander(f"{s_diff.section_title} [{s_diff.status.upper()}]", expanded=(s_diff.status != "unchanged")):
                            for b in s_diff.bullets:
                                if b.change_type == "added":
                                    st.markdown(f"<span style='color: #10b981;'>➕ **[ADDED]** {b.new_content}</span>", unsafe_allow_html=True)
                                elif b.change_type == "removed":
                                    st.markdown(f"<span style='color: #ef4444; text-decoration: line-through;'>➖ **[REMOVED]** {b.old_content}</span>", unsafe_allow_html=True)
                                elif b.change_type == "modified":
                                    st.markdown(f"<span style='color: #f59e0b;'>✏️ **[OLD]** {b.old_content}</span><br><span style='color: #10b981;'>&nbsp;&nbsp;&nbsp;&nbsp;**[NEW]** {b.new_content}</span>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"• {b.new_content}")
