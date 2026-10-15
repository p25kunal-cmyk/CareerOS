"""Streamlit UI page for Structured Resume Editing.

Enables deep, granular editing of sections and bullets, ordering,
verification badges, branching versions, and exporting.
"""

from __future__ import annotations

import streamlit as st

from src.database.connection import DatabaseConnection
from src.resume.exporter import ResumeExporter
from src.resume.models import BulletItem, SectionItem
from src.resume.repository import ResumeRepository
from src.resume.templates import TEMPLATES


def render(db: DatabaseConnection):
    """Render the Resume Editor page."""
    repo = ResumeRepository(db)

    st.markdown("## ✏️ Resume Editor")
    st.caption("Granular section and bullet editing with stable UUIDs, reordering, and instant export.")

    resumes = repo.list_resumes()
    if not resumes:
        st.warning("No resumes found. Please upload or import a resume in the 'My Resumes' page first.")
        if st.button("Go to My Resumes"):
            st.session_state["nav_target"] = "My Resumes"
            st.rerun()
        return

    # Select Resume
    default_res_id = st.session_state.get("active_resume_id", resumes[0].id)
    res_index = next((i for i, r in enumerate(resumes) if r.id == default_res_id), 0)

    top_col1, top_col2, top_col3 = st.columns([3, 2, 2])
    with top_col1:
        selected_resume = st.selectbox(
            "Select Resume Profile",
            resumes,
            index=res_index,
            format_func=lambda r: f"{'⭐ ' if r.is_master else ''}{r.name} ({r.version_count} versions)",
        )
        st.session_state["active_resume_id"] = selected_resume.id

    versions = repo.list_versions(selected_resume.id)
    if not versions:
        st.info("No versions found for this resume.")
        return

    default_ver_id = st.session_state.get("active_version_id", versions[0]["id"])
    ver_index = next((i for i, v in enumerate(versions) if v["id"] == default_ver_id), 0)

    with top_col2:
        selected_ver_meta = st.selectbox(
            "Version",
            versions,
            index=ver_index,
            format_func=lambda v: f"{v['version_name']} (v{v['version_number']})",
        )
        st.session_state["active_version_id"] = selected_ver_meta["id"]

    version_data = repo.get_version(selected_ver_meta["id"])
    if not version_data:
        st.error("Could not load version data.")
        return

    with top_col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔀 Branch New Version", use_container_width=True):
            new_v = repo.fork_version(
                source_version_id=version_data.id,
                new_version_name=f"{version_data.version_name or 'Version'} (Branch)",
            )
            st.session_state["active_version_id"] = new_v.id
            st.success(f"Branched into {new_v.version_name}!")
            st.rerun()

    st.markdown("---")

    tab_edit, tab_preview, tab_export = st.tabs(["📝 Section & Bullet Editor", "👁️ Live Preview", "🚀 Export Center"])

    # ── TAB 1: SECTION & BULLET EDITOR ────────────────────────────
    with tab_edit:
        st.markdown("##### Sections & Content")
        st.caption("Expand sections below to edit, reorder, or add bullets. Changes persist immediately with transactional safety.")

        sections = version_data.sections
        for s_idx, sec in enumerate(sections):
            with st.expander(f"{s_idx + 1}. {sec.title} ({sec.section_type.replace('_', ' ').title()}) · {len(sec.bullets)} items", expanded=(s_idx < 3)):
                # Section controls
                sc1, sc2, sc3, sc4, sc5 = st.columns([3, 2, 1, 1, 1])
                with sc1:
                    new_title = st.text_input("Section Title", value=sec.title, key=f"title_{sec.id}")
                    if new_title != sec.title:
                        repo.update_section(sec.id, title=new_title)
                        st.rerun()
                with sc2:
                    sec_types = [
                        "contact", "summary", "education", "experience", "internships",
                        "projects", "skills", "certifications", "achievements",
                        "positions_of_responsibility", "extracurricular", "custom"
                    ]
                    st_index = sec_types.index(sec.section_type) if sec.section_type in sec_types else 0
                    new_type = st.selectbox("Category", sec_types, index=st_index, key=f"type_{sec.id}")
                    if new_type != sec.section_type:
                        repo.update_section(sec.id, section_type=new_type)
                        st.rerun()
                with sc3:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if s_idx > 0:
                        if st.button("⬆️", key=f"sec_up_{sec.id}", help="Move section up"):
                            sec_ids = [s.id for s in sections]
                            sec_ids[s_idx], sec_ids[s_idx - 1] = sec_ids[s_idx - 1], sec_ids[s_idx]
                            repo.reorder_sections(version_data.id, sec_ids)
                            st.rerun()
                with sc4:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if s_idx < len(sections) - 1:
                        if st.button("⬇️", key=f"sec_dn_{sec.id}", help="Move section down"):
                            sec_ids = [s.id for s in sections]
                            sec_ids[s_idx], sec_ids[s_idx + 1] = sec_ids[s_idx + 1], sec_ids[s_idx]
                            repo.reorder_sections(version_data.id, sec_ids)
                            st.rerun()
                with sc5:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"sec_del_{sec.id}", help="Delete section"):
                        repo.delete_section(sec.id)
                        st.rerun()

                st.markdown("---")

                # Bullets inside section
                for b_idx, bullet in enumerate(sec.bullets):
                    bc1, bc2, bc3, bc4 = st.columns([5, 1, 1, 1])
                    with bc1:
                        b_content = st.text_area(
                            f"Item {b_idx + 1}",
                            value=bullet.content,
                            key=f"b_txt_{bullet.id}",
                            height=68,
                            label_visibility="collapsed",
                        )
                        if b_content != bullet.content:
                            repo.update_bullet(bullet.id, content=b_content)

                        # Badges for action verb & metrics
                        badge_html = []
                        if bullet.action_verb:
                            badge_html.append(f"<span style='background: #1e3a8a; color: #93c5fd; padding: 2px 6px; border-radius: 4px; font-size: 0.72rem;'>Verb: {bullet.action_verb}</span>")
                        if bullet.metrics:
                            badge_html.append(f"<span style='background: #064e3b; color: #6ee7b7; padding: 2px 6px; border-radius: 4px; font-size: 0.72rem;'>Metrics: {', '.join(bullet.metrics)}</span>")
                        if bullet.is_verified:
                            badge_html.append("<span style='background: #1e293b; color: #10b981; padding: 2px 6px; border-radius: 4px; font-size: 0.72rem;'>✓ Verified</span>")
                        if badge_html:
                            st.markdown(" ".join(badge_html), unsafe_allow_html=True)

                    with bc2:
                        b_types = ["bullet", "header", "subheader", "text"]
                        cur_t_idx = b_types.index(bullet.bullet_type) if bullet.bullet_type in b_types else 0
                        new_b_type = st.selectbox("Type", b_types, index=cur_t_idx, key=f"b_type_{bullet.id}", label_visibility="collapsed")
                        if new_b_type != bullet.bullet_type:
                            repo.update_bullet(bullet.id, bullet_type=new_b_type)
                            st.rerun()
                    with bc3:
                        if b_idx > 0:
                            if st.button("⬆️", key=f"b_up_{bullet.id}", help="Move bullet up"):
                                b_ids = [b.id for b in sec.bullets]
                                b_ids[b_idx], b_ids[b_idx - 1] = b_ids[b_idx - 1], b_ids[b_idx]
                                repo.reorder_bullets(sec.id, b_ids)
                                st.rerun()
                    with bc4:
                        if st.button("🗑️", key=f"b_del_{bullet.id}", help="Delete bullet"):
                            repo.delete_bullet(bullet.id)
                            st.rerun()

                # Add new bullet to this section
                with st.form(key=f"add_b_form_{sec.id}"):
                    ab1, ab2 = st.columns([5, 1])
                    with ab1:
                        new_bullet_text = st.text_input("Add new bullet / item", placeholder="e.g. Led a team of 5 consultants to increase revenue by 24%...")
                    with ab2:
                        submit_b = st.form_submit_button("➕ Add Bullet")
                    if submit_b and new_bullet_text.strip():
                        repo.add_bullet(sec.id, content=new_bullet_text.strip())
                        st.rerun()

        st.markdown("---")
        # Add new Section Form
        with st.form("add_section_form"):
            st.markdown("##### ➕ Add New Section")
            ns_col1, ns_col2, ns_col3 = st.columns([3, 2, 1])
            with ns_col1:
                new_sec_title = st.text_input("Section Title", placeholder="e.g. Live Projects, Leadership Roles")
            with ns_col2:
                new_sec_type = st.selectbox(
                    "Section Type",
                    [
                        "experience", "internships", "projects", "education", "skills",
                        "certifications", "achievements", "positions_of_responsibility",
                        "extracurricular", "summary", "custom"
                    ]
                )
            with ns_col3:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                add_sec_submit = st.form_submit_button("Add Section", type="primary")

            if add_sec_submit and new_sec_title.strip():
                repo.add_section(version_data.id, section_type=new_sec_type, title=new_sec_title.strip())
                st.success(f"Added section '{new_sec_title}'!")
                st.rerun()

    # ── TAB 2: LIVE PREVIEW ───────────────────────────────────────
    with tab2:
        st.markdown("##### Live Rendered Preview")
        preview_tmpl_id = st.selectbox(
            "Preview Template",
            list(TEMPLATES.keys()),
            format_func=lambda k: TEMPLATES[k].name,
            index=0,
        )

        md_content = ResumeExporter.export_markdown(version_data)
        st.markdown(
            f'<div style="background: #1e293b; padding: 2rem; border-radius: 8px; border: 1px solid #334155; color: #f8fafc;">'
            f'{md_content}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── TAB 3: EXPORT CENTER ──────────────────────────────────────
    with tab3:
        st.markdown("##### 🚀 Export Resume")
        st.caption("Generate professional DOCX, PDF, or Markdown files formatted for applicant tracking systems (ATS) and human recruiters.")

        ex_col1, ex_col2 = st.columns(2)
        with ex_col1:
            export_template = st.selectbox(
                "Export Template Layout",
                list(TEMPLATES.keys()),
                format_func=lambda k: f"{TEMPLATES[k].name} — {TEMPLATES[k].description}",
                index=0,
                key="export_center_template",
            )
            tmpl_obj = TEMPLATES[export_template]
            st.info(f"**Font:** {tmpl_obj.font_family} | **Margins:** {tmpl_obj.margin_top_inches}\" | **Line spacing:** {tmpl_obj.line_spacing}x")

        with ex_col2:
            st.markdown("###### Download Options")
            # DOCX
            docx_bytes = ResumeExporter.export_docx(version_data, export_template)
            st.download_button(
                label="📄 Download Microsoft Word (.docx)",
                data=docx_bytes,
                file_name=f"{selected_resume.name}_{version_data.version_name}.docx".replace(" ", "_"),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
            )

            # PDF
            pdf_bytes = ResumeExporter.export_pdf(version_data, export_template)
            st.download_button(
                label="📕 Download PDF Document (.pdf)",
                data=pdf_bytes,
                file_name=f"{selected_resume.name}_{version_data.version_name}.pdf".replace(" ", "_"),
                mime="application/pdf",
                use_container_width=True,
            )

            # Markdown
            md_str = ResumeExporter.export_markdown(version_data)
            st.download_button(
                label="📝 Download Markdown (.md)",
                data=md_str,
                file_name=f"{selected_resume.name}_{version_data.version_name}.md".replace(" ", "_"),
                mime="text/markdown",
                use_container_width=True,
            )
