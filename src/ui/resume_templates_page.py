"""Streamlit UI page for Resume Templates.

Visualizes and configures resume layout templates, including the IIM Nagpur format.
"""

from __future__ import annotations

import streamlit as st
from src.database.connection import DatabaseConnection
from src.resume.templates import TEMPLATES, TemplateConfig
from src.ui.components import render_top_header, navigate_to


def render(db: DatabaseConnection):
    """Render the Resume Templates page."""
    render_top_header("Resume Templates", db)

    st.markdown("## 📐 Resume Templates & Formats")
    st.caption("Standardized, recruiter-approved resume layouts tailored for MBA placement and corporate hiring.")

    cols = st.columns(len(TEMPLATES))
    for idx, (t_id, tmpl) in enumerate(TEMPLATES.items()):
        with cols[idx]:
            is_iim = t_id == "iim_nagpur"
            badge = " ⭐ (Default MBA)" if is_iim else ""
            st.markdown(
                f'<div class="metric-card" style="text-align: left; height: 100%;">'
                f'<h4>{tmpl.name}{badge}</h4>'
                f'<p style="color: #94a3b8; font-size: 0.85rem;">{tmpl.description}</p>'
                f'<hr style="border-color: #334155; margin: 0.75rem 0;" />'
                f'<div style="font-size: 0.8rem; color: #cbd5e1; line-height: 1.6;">'
                f'• <b>Font:</b> {tmpl.font_family}<br>'
                f'• <b>Header Size:</b> {tmpl.font_size_header}pt<br>'
                f'• <b>Body Size:</b> {tmpl.font_size_body}pt<br>'
                f'• <b>Margins:</b> {tmpl.margin_top_inches}" top/bottom, {tmpl.margin_left_inches}" sides<br>'
                f'• <b>Spacing:</b> {tmpl.line_spacing}x line spacing<br>'
                f'• <b>Accent Color:</b> <span style="display:inline-block;width:12px;height:12px;background:{tmpl.accent_color_hex};border-radius:2px;vertical-align:middle;"></span> {tmpl.accent_color_hex}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
            if st.button(f"👁️ Preview in {tmpl.name[:12]}...", key=f"tmpl_pv_{t_id}", use_container_width=True):
                navigate_to("Resume Preview")

    st.markdown("---")
    st.markdown("### 🎓 IIM Nagpur Placement Specification & Order")
    st.markdown("""
    The IIM Nagpur format enforces a rigorous, high-density 1-page structure:
    1. **Header**: Full Name (Bold, 16pt), MBA Roll/Batch, Email, Phone, LinkedIn, Location.
    2. **Academic Qualifications**: Tabular layout with columns for *Degree / Examination*, *Institution*, *Board / University*, *Year*, and *Percentage / CGPA*.
    3. **Work Experience**: Pre-MBA professional experience with quantifiable impact (revenue, team size, cost reduction).
    4. **Summer Internship / Live Projects**: Highlight MBA summer internship deliverables, industry impact, and sponsor organization.
    5. **Academic Projects**: Capstone or major coursework projects.
    6. **Positions of Responsibility (POR)**: Student council, Placement Committee, Club Coordinator roles demonstrating leadership.
    7. **Certifications & Skills**: Industry certifications (CFA, Six Sigma, Scrum) and domain tools (Python, PowerBI, SQL, Advanced Excel).
    8. **Achievements & Extra-curricular**: National case competition wins, sports, community leadership.
    """)

    st.info("💡 **Tip**: When you export or preview any resume using the **IIM Nagpur MBA Standard** template, education rows are automatically formatted into an official ATS-compliant table.")
