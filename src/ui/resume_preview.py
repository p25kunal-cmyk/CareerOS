"""Streamlit UI page and reusable component for Resume Preview.

Renders pixel-precise interactive HTML document sheets, vector-rasterized PDF pages,
and raw markdown with template switching, zoom controls, and instant downloads.
"""

from __future__ import annotations

import io
from typing import Optional
import streamlit as st

from src.database.connection import DatabaseConnection
from src.resume.exporter import ResumeExporter
from src.resume.models import ResumeVersionData
from src.resume.repository import ResumeRepository
from src.resume.templates import TEMPLATES, get_template


def render_resume_preview_component(
    version_data: ResumeVersionData,
    resume_name: str = "Resume",
    default_template: str = "iim_nagpur",
    key_prefix: str = "pv",
    show_toolbar: bool = True,
    show_export_buttons: bool = True,
):
    """Render a comprehensive, realistic resume preview container."""
    if not version_data:
        st.warning("No version data provided to preview.")
        return

    # ── Toolbar Controls ──────────────────────────────────────────
    if show_toolbar:
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, #1e293b 0%, #172033 100%);
                        padding: 0.85rem 1.25rem; border-radius: 10px;
                        border: 1px solid #334155; margin-bottom: 1.25rem;
                        box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                    <div>
                        <span style="font-size:1.05rem; font-weight:700; color:#f1f5f9;">👁️ Live Resume Previewer</span>
                        <span style="color:#94a3b8; font-size:0.85rem; margin-left:8px;">ATS & Recruiter-Ready View</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_t1, col_t2, col_t3, col_t4 = st.columns([3, 3, 2, 2])

        with col_t1:
            tmpl_keys = list(TEMPLATES.keys())
            tmpl_default_idx = tmpl_keys.index(default_template) if default_template in tmpl_keys else 0
            selected_template = st.selectbox(
                "Layout Template",
                tmpl_keys,
                index=tmpl_default_idx,
                format_func=lambda k: TEMPLATES[k].name,
                key=f"{key_prefix}_tmpl_select",
                help="Switch between IIM Nagpur MBA, Corporate Executive, and Tech PM styling.",
            )

        with col_t2:
            view_mode = st.radio(
                "Display Mode",
                ["📄 Interactive Paper", "📕 True PDF Vector", "📝 Markdown"],
                horizontal=True,
                key=f"{key_prefix}_mode_select",
            )

        with col_t3:
            zoom_str = st.select_slider(
                "Zoom",
                options=["80%", "90%", "100%", "110%", "120%"],
                value="100%",
                key=f"{key_prefix}_zoom_slider",
            )
            zoom_val = float(zoom_str.replace("%", "")) / 100.0

        with col_t4:
            st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
            highlight_metrics = st.checkbox(
                "Highlight Verbs & Metrics",
                value=False,
                key=f"{key_prefix}_metrics_toggle",
                help="Visually highlight action verbs and quantitative numbers for easy review.",
            )

        # Template details badge
        tmpl_obj = get_template(selected_template)
        st.markdown(
            f"""
            <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.75rem; padding: 4px 8px; background: #0f172a66; border-radius: 6px; border: 1px solid #1e293b;">
                <b>Font:</b> {tmpl_obj.font_family} · <b>Margins:</b> {tmpl_obj.margin_top_inches}" top / {tmpl_obj.margin_left_inches}" sides · <b>Line Spacing:</b> {tmpl_obj.line_spacing}x · <b>Heading Underline:</b> {'Yes' if tmpl_obj.header_underline else 'No'}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        selected_template = default_template
        view_mode = "📄 Interactive Paper"
        zoom_val = 1.0
        highlight_metrics = False

    # ── Display Content ───────────────────────────────────────────
    if view_mode == "📄 Interactive Paper":
        html_doc = ResumeExporter.export_html(
            version=version_data,
            template_id=selected_template,
            highlight_metrics=highlight_metrics,
            zoom=zoom_val,
        )
        st.markdown(html_doc, unsafe_allow_html=True)

    elif view_mode == "📕 True PDF Vector":
        with st.spinner("Rendering vector PDF pages..."):
            try:
                pages_images = ResumeExporter.render_pdf_pages_as_images(
                    version=version_data,
                    template_id=selected_template,
                    dpi=160,
                )
                if not pages_images:
                    st.info("No pages generated.")
                else:
                    for p_num, img_bytes in enumerate(pages_images, 1):
                        st.markdown(
                            f"""
                            <div style="display:flex; justify-content:space-between; align-items:center; max-width:820px; margin: 10px auto 4px auto; color:#94a3b8; font-size:0.8rem;">
                                <span>📄 PDF Page {p_num} of {len(pages_images)}</span>
                                <span>100% Vector Layout</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.image(
                            img_bytes,
                            caption=f"Page {p_num}",
                            use_container_width=True,
                        )
            except Exception as e:
                st.error(f"Error rendering PDF preview: {e}")

    else:  # Markdown
        md_text = ResumeExporter.export_markdown(version_data)
        st.markdown(
            f"""
            <div style="background: #1e293b; padding: 1.5rem; border-radius: 8px; border: 1px solid #334155; color: #f1f5f9; line-height: 1.6;">
            """,
            unsafe_allow_html=True,
        )
        st.markdown(md_text)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Export & Action Buttons ───────────────────────────────────
    if show_export_buttons:
        st.markdown("---")
        c_ex1, c_ex2, c_ex3 = st.columns(3)
        safe_name = resume_name.replace(" ", "_")
        ver_name = (version_data.version_name or "v1").replace(" ", "_")

        with c_ex1:
            try:
                pdf_bytes = ResumeExporter.export_pdf(version_data, selected_template)
                st.download_button(
                    label="📕 Download PDF Document",
                    data=pdf_bytes,
                    file_name=f"{safe_name}_{ver_name}.pdf",
                    mime="application/pdf",
                    type="primary",
                    key=f"{key_prefix}_dl_pdf",
                    use_container_width=True,
                )
            except Exception as err:
                st.button("📕 PDF Export Unavailable", disabled=True, key=f"{key_prefix}_dl_pdf_dis")

        with c_ex2:
            try:
                docx_bytes = ResumeExporter.export_docx(version_data, selected_template)
                st.download_button(
                    label="📄 Download Word (.docx)",
                    data=docx_bytes,
                    file_name=f"{safe_name}_{ver_name}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"{key_prefix}_dl_docx",
                    use_container_width=True,
                )
            except Exception as err:
                st.button("📄 Word Export Unavailable", disabled=True, key=f"{key_prefix}_dl_docx_dis")

        with c_ex3:
            md_bytes = ResumeExporter.export_markdown(version_data)
            st.download_button(
                label="📝 Download Markdown (.md)",
                data=md_bytes,
                file_name=f"{safe_name}_{ver_name}.md",
                mime="text/markdown",
                key=f"{key_prefix}_dl_md",
                use_container_width=True,
            )


def render(db: DatabaseConnection):
    """Render the full dedicated Resume Previewer page."""
    repo = ResumeRepository(db)

    st.markdown("## 👁️ Resume Previewer & Studio Inspector")
    st.caption("Inspect your resume in true pixel-perfect paper format, preview multiple templates, and export ready-to-send documents.")

    resumes = repo.list_resumes()
    if not resumes:
        st.info("No resumes found in the library yet.")
        from src.resume.sample_data import create_sample_mba_resume
        if st.button("✨ Load High-Impact MBA Sample Resume (IIM Nagpur Format)", type="primary"):
            r_id, v_id = create_sample_mba_resume(repo)
            st.session_state["active_resume_id"] = r_id
            st.session_state["active_version_id"] = v_id
            st.success("Loaded sample MBA resume! Rendering preview now...")
            st.rerun()

        st.markdown("<p style='color:#94a3b8;'>Or upload your own resume from My Resumes page:</p>", unsafe_allow_html=True)
        if st.button("📥 Go to My Resumes (Upload & Import)"):
            st.session_state["active_page"] = "My Resumes"
            st.rerun()
        return

    # Resume Selection Header
    col_sel1, col_sel2, col_sel3 = st.columns([3, 2, 2])

    default_res_id = st.session_state.get("active_resume_id", resumes[0].id)
    res_index = next((i for i, r in enumerate(resumes) if r.id == default_res_id), 0)

    with col_sel1:
        selected_resume = st.selectbox(
            "Select Resume Profile",
            resumes,
            index=res_index,
            format_func=lambda r: f"{'⭐ [MASTER] ' if r.is_master else '📄 '}{r.name} ({r.version_count} versions)",
            key="preview_page_resume_select",
        )
        st.session_state["active_resume_id"] = selected_resume.id

    versions = repo.list_versions(selected_resume.id)
    if not versions:
        st.warning("No versions found for this resume profile.")
        return

    default_ver_id = st.session_state.get("active_version_id", versions[0]["id"])
    ver_index = next((i for i, v in enumerate(versions) if v["id"] == default_ver_id), 0)

    with col_sel2:
        selected_ver_meta = st.selectbox(
            "Version",
            versions,
            index=ver_index,
            format_func=lambda v: f"{v['version_name']} (v{v['version_number']})",
            key="preview_page_ver_select",
        )
        st.session_state["active_version_id"] = selected_ver_meta["id"]

    version_data = repo.get_version(selected_ver_meta["id"])
    if not version_data:
        st.error("Could not load version data.")
        return

    with col_sel3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        quick_col1, quick_col2 = st.columns(2)
        with quick_col1:
            if st.button("✏️ Edit Resume", use_container_width=True):
                st.session_state["active_page"] = "Resume Editor"
                st.session_state["active_resume_id"] = selected_resume.id
                st.session_state["active_version_id"] = version_data.id
                st.rerun()
        with quick_col2:
            if st.button("⚡ Optimize", use_container_width=True):
                st.session_state["active_page"] = "Resume Optimization"
                st.session_state["active_resume_id"] = selected_resume.id
                st.session_state["active_version_id"] = version_data.id
                st.rerun()

    st.markdown("---")

    # Render Reusable Resume Preview Component
    render_resume_preview_component(
        version_data=version_data,
        resume_name=selected_resume.name,
        default_template="iim_nagpur",
        key_prefix="main_preview_page",
        show_toolbar=True,
        show_export_buttons=True,
    )
