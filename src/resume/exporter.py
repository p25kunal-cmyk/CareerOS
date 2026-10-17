"""Resume export engine for DOCX, PDF, Markdown, and Plain Text.

Renders version data into pixel-precise documents adhering to template
specifications and IIM placement standards.
"""

from __future__ import annotations

import io
import os
import re
from typing import Any, List, Optional

import docx
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor
import fitz  # PyMuPDF

from src.resume.models import BulletItem, ResumeVersionData, SectionItem
from src.resume.templates import TemplateConfig, get_template
from src.utils.logger import get_logger

logger = get_logger("resume.exporter")


def _hex_to_rgb(hex_code: str) -> RGBColor:
    """Convert hex string (e.g. '#1e293b') to docx RGBColor."""
    h = hex_code.lstrip("#")
    if len(h) != 6:
        return RGBColor(15, 23, 42)
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _set_cell_background(cell, hex_color: str):
    """Set table cell background color."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color.lstrip("#")}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)


def _set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set cell margins/padding in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


class ResumeExporter:
    """Generates documents across formats from ResumeVersionData."""

    @classmethod
    def export_docx(
        cls,
        version: ResumeVersionData,
        template_id: str = "iim_nagpur",
        output_path: Optional[str] = None,
    ) -> bytes:
        """Render resume version to a styled DOCX document."""
        tmpl = get_template(template_id)
        doc = docx.Document()

        # Set page margins
        for section in doc.sections:
            section.top_margin = Inches(tmpl.margin_top_inches)
            section.bottom_margin = Inches(tmpl.margin_bottom_inches)
            section.left_margin = Inches(tmpl.margin_left_inches)
            section.right_margin = Inches(tmpl.margin_right_inches)

        # Base style configuration
        normal_style = doc.styles['Normal']
        normal_style.font.name = tmpl.font_family
        normal_style.font.size = Pt(tmpl.font_size_body)
        normal_style.font.color.rgb = _hex_to_rgb(tmpl.header_color_hex)
        normal_style.paragraph_format.line_spacing = tmpl.line_spacing
        normal_style.paragraph_format.space_after = Pt(tmpl.space_after_bullet_pt)
        normal_style.paragraph_format.space_before = Pt(0)

        # ── Header / Contact ──────────────────────────────────────
        contact_sec = next((s for s in version.sections if s.section_type == "contact" and s.is_visible), None)
        candidate_name = "Candidate Name"
        contact_lines: List[str] = []

        if contact_sec:
            for b in contact_sec.bullets:
                if b.bullet_type == "header":
                    candidate_name = b.content
                else:
                    contact_lines.append(b.content)
        else:
            candidate_name = version.version_name or "Resume"

        # Add Name Header
        p_name = doc.add_paragraph()
        p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_name.paragraph_format.space_after = Pt(2)
        r_name = p_name.add_run(candidate_name)
        r_name.bold = True
        r_name.font.size = Pt(tmpl.font_size_name)
        r_name.font.color.rgb = _hex_to_rgb(tmpl.header_color_hex)

        # Add Contact details
        for line in contact_lines:
            p_c = doc.add_paragraph()
            p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_c.paragraph_format.space_after = Pt(2)
            r_c = p_c.add_run(line)
            r_c.font.size = Pt(tmpl.font_size_sub)
            r_c.font.color.rgb = RGBColor(71, 85, 105)

        # ── Sections ──────────────────────────────────────────────
        visible_sections = [s for s in version.sections if s.section_type != "contact" and s.is_visible]
        visible_sections.sort(key=lambda s: s.display_order)

        for sec in visible_sections:
            p_head = doc.add_paragraph()
            p_head.paragraph_format.space_before = Pt(6)
            p_head.paragraph_format.space_after = Pt(tmpl.space_after_heading_pt)
            p_head.paragraph_format.keep_with_next = True

            r_head = p_head.add_run(sec.title.upper())
            r_head.bold = True
            r_head.font.size = Pt(tmpl.font_size_header)
            r_head.font.color.rgb = _hex_to_rgb(tmpl.accent_color_hex)

            if tmpl.header_underline:
                pPr = p_head._p.get_or_add_pPr()
                pbdr = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="6" w:space="1" w:color="{tmpl.accent_color_hex.lstrip("#")}"/></w:pBdr>')
                pPr.append(pbdr)

            is_edu = sec.section_type == "education"
            has_pipe_rows = any("|" in b.content for b in sec.bullets)

            if is_edu and has_pipe_rows:
                cls._render_education_table(doc, sec.bullets, tmpl)
            else:
                for b in sec.bullets:
                    cls._render_bullet_item(doc, b, tmpl)

        bio = io.BytesIO()
        doc.save(bio)
        content_bytes = bio.getvalue()

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(content_bytes)
            logger.info("Exported DOCX to %s (%d bytes)", output_path, len(content_bytes))

        return content_bytes

    @classmethod
    def _render_education_table(cls, doc: docx.Document, bullets: List[BulletItem], tmpl: TemplateConfig):
        """Render education rows as a clean, bordered table."""
        rows_data = []
        for b in bullets:
            parts = [p.strip() for p in b.content.split("|") if p.strip()]
            if len(parts) >= 3:
                rows_data.append(parts)

        if not rows_data:
            for b in bullets:
                cls._render_bullet_item(doc, b, tmpl)
            return

        col_count = max(len(r) for r in rows_data)
        normalized_rows = [r + [""] * (col_count - len(r)) for r in rows_data]

        table = doc.add_table(rows=len(normalized_rows), cols=col_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = True

        for r_idx, row_vals in enumerate(normalized_rows):
            row = table.rows[r_idx]
            is_header_row = (r_idx == 0 and any(w in row_vals[0].lower() for w in ("degree", "qualification", "programme", "course")))
            for c_idx, val in enumerate(row_vals):
                cell = row.cells[c_idx]
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                _set_cell_margins(cell, top=80, bottom=80, left=120, right=120)

                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.05

                if is_header_row:
                    _set_cell_background(cell, "f1f5f9")
                    run = p.add_run(val)
                    run.bold = True
                    run.font.size = Pt(tmpl.font_size_sub)
                    run.font.color.rgb = _hex_to_rgb(tmpl.header_color_hex)
                else:
                    run = p.add_run(val)
                    if c_idx == 0:
                        run.bold = True
                    run.font.size = Pt(tmpl.font_size_sub)
                    run.font.color.rgb = _hex_to_rgb(tmpl.header_color_hex)

                if c_idx >= col_count - 2:
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        p_spacer = doc.add_paragraph()
        p_spacer.paragraph_format.space_before = Pt(0)
        p_spacer.paragraph_format.space_after = Pt(2)

    @classmethod
    def _render_bullet_item(cls, doc: docx.Document, bullet: BulletItem, tmpl: TemplateConfig):
        """Render a single bullet item into document."""
        if bullet.bullet_type in ("header", "subheader"):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.keep_with_next = True

            run = p.add_run(bullet.content)
            run.bold = (bullet.bullet_type == "header")
            run.font.size = Pt(tmpl.font_size_body if bullet.bullet_type == "header" else tmpl.font_size_sub)
            run.font.color.rgb = _hex_to_rgb(tmpl.header_color_hex)

            if bullet.sub_content:
                p_sub = doc.add_paragraph()
                p_sub.paragraph_format.space_after = Pt(1)
                r_sub = p_sub.add_run(bullet.sub_content)
                r_sub.italic = True
                r_sub.font.size = Pt(tmpl.font_size_sub)
                r_sub.font.color.rgb = RGBColor(100, 116, 139)

        elif bullet.bullet_type == "text":
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(tmpl.space_after_bullet_pt)
            run = p.add_run(bullet.content)
            run.font.size = Pt(tmpl.font_size_body)
            run.font.color.rgb = _hex_to_rgb(tmpl.header_color_hex)

        else:
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.space_after = Pt(tmpl.space_after_bullet_pt)
            p.paragraph_format.left_indent = Inches(0.25 * (bullet.indent_level + 1))

            content_text = re.sub(r"^[\s•\-\*–—\d\.\)\?]+", "", bullet.content).strip()
            run = p.add_run(content_text)
            run.font.size = Pt(tmpl.font_size_body)
            run.font.color.rgb = _hex_to_rgb(tmpl.header_color_hex)

    @classmethod
    def export_markdown(cls, version: ResumeVersionData) -> str:
        """Render version to formatted Markdown."""
        lines = []

        contact_sec = next((s for s in version.sections if s.section_type == "contact" and s.is_visible), None)
        if contact_sec:
            for b in contact_sec.bullets:
                if b.bullet_type == "header":
                    lines.append(f"# {b.content}\n")
                else:
                    lines.append(f"**{b.content}**  ")
            lines.append("")

        for sec in version.sections:
            if sec.section_type == "contact" or not sec.is_visible:
                continue
            lines.append(f"## {sec.title.upper()}\n")
            for b in sec.bullets:
                if b.bullet_type in ("header", "subheader"):
                    lines.append(f"\n### {b.content}")
                    if b.sub_content:
                        lines.append(f"*{b.sub_content}*\n")
                elif b.bullet_type == "text":
                    lines.append(f"{b.content}\n")
                else:
                    indent = "  " * b.indent_level
                    cleaned = re.sub(r"^[\s•\-\*–—\?]+", "", b.content).strip()
                    lines.append(f"{indent}- {cleaned}")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def export_text(cls, version: ResumeVersionData) -> str:
        """Render version to clean plain text."""
        lines = []
        for sec in version.sections:
            if not sec.is_visible:
                continue
            lines.append("=" * 60)
            lines.append(sec.title.upper())
            lines.append("=" * 60)
            for b in sec.bullets:
                if b.bullet_type == "header":
                    lines.append(f"\n[{b.content}]")
                elif b.bullet_type == "bullet":
                    cleaned = re.sub(r"^[\s•\-\*–—\?]+", "", b.content).strip()
                    lines.append(f"  * {cleaned}")
                else:
                    lines.append(f"  {b.content}")
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def export_pdf(
        cls,
        version: ResumeVersionData,
        template_id: str = "iim_nagpur",
        output_path: Optional[str] = None,
    ) -> bytes:
        """Render vector PDF using PyMuPDF."""
        tmpl = get_template(template_id)
        doc = fitz.open()

        page_width = 612.0
        page_height = 792.0
        margin_x = tmpl.margin_left_inches * 72.0
        margin_y = tmpl.margin_top_inches * 72.0

        page = doc.new_page(width=page_width, height=page_height)
        current_y = margin_y + 15

        def check_page_break(needed_height: float):
            nonlocal page, current_y
            if current_y + needed_height > (page_height - margin_y):
                page = doc.new_page(width=page_width, height=page_height)
                current_y = margin_y + 15

        contact_sec = next((s for s in version.sections if s.section_type == "contact" and s.is_visible), None)
        candidate_name = "Candidate Name"
        contact_sub = []
        if contact_sec:
            for b in contact_sec.bullets:
                if b.bullet_type == "header":
                    candidate_name = b.content
                else:
                    contact_sub.append(b.content)

        # Name
        name_len = fitz.get_text_length(candidate_name, fontname="helv", fontsize=tmpl.font_size_name)
        page.insert_text(
            fitz.Point((page_width - name_len) / 2, current_y),
            candidate_name,
            fontsize=tmpl.font_size_name,
            fontname="helv",
            color=(0.06, 0.09, 0.16),
        )
        current_y += 18

        # Contact line
        for c_line in contact_sub:
            c_len = fitz.get_text_length(c_line, fontname="helv", fontsize=tmpl.font_size_sub)
            page.insert_text(
                fitz.Point((page_width - c_len) / 2, current_y),
                c_line,
                fontsize=tmpl.font_size_sub,
                fontname="helv",
                color=(0.28, 0.33, 0.41),
            )
            current_y += 14

        current_y += 10

        visible_sections = [s for s in version.sections if s.section_type != "contact" and s.is_visible]
        visible_sections.sort(key=lambda s: s.display_order)

        for sec in visible_sections:
            check_page_break(36)
            current_y += 10
            page.insert_text(
                fitz.Point(margin_x, current_y),
                sec.title.upper(),
                fontsize=tmpl.font_size_header,
                fontname="helv",
                color=(0.12, 0.16, 0.23),
            )
            current_y += 4

            if tmpl.header_underline:
                page.draw_line(
                    fitz.Point(margin_x, current_y),
                    fitz.Point(page_width - margin_x, current_y),
                    color=(0.6, 0.65, 0.72),
                    width=0.75,
                )
            current_y += 14

            for b in sec.bullets:
                check_page_break(20)
                cleaned = re.sub(r"^[\s•\-\*–—\?]+", "", b.content).strip()

                if b.bullet_type in ("header", "subheader"):
                    page.insert_text(
                        fitz.Point(margin_x, current_y),
                        cleaned,
                        fontsize=tmpl.font_size_body,
                        fontname="helv",
                        color=(0.06, 0.09, 0.16),
                    )
                    current_y += 15
                else:
                    page.draw_circle(fitz.Point(margin_x + 4, current_y - 3), 1.5, color=(0.2, 0.2, 0.2), fill=(0.2, 0.2, 0.2))
                    page.insert_text(
                        fitz.Point(margin_x + 12, current_y),
                        cleaned,
                        fontsize=tmpl.font_size_body,
                        fontname="helv",
                        color=(0.1, 0.1, 0.1),
                    )
                    current_y += 14

        pdf_bytes = doc.tobytes()
        doc.close()

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info("Exported PDF to %s (%d bytes)", output_path, len(pdf_bytes))

        return pdf_bytes

    @classmethod
    def render_pdf_pages_as_images(
        cls,
        version: ResumeVersionData,
        template_id: str = "iim_nagpur",
        dpi: int = 150,
    ) -> List[bytes]:
        """Render each page of the exported PDF as a PNG image using PyMuPDF."""
        pdf_bytes = cls.export_pdf(version, template_id)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_images: List[bytes] = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            pages_images.append(pix.tobytes("png"))
        doc.close()
        return pages_images

    @classmethod
    def export_html(
        cls,
        version: ResumeVersionData,
        template_id: str = "iim_nagpur",
        highlight_metrics: bool = False,
        zoom: float = 1.0,
    ) -> str:
        """Render version into a pixel-precise, beautifully styled HTML/CSS resume document."""
        tmpl = get_template(template_id)

        # ── Header / Contact ──────────────────────────────────────────
        contact_sec = next((s for s in version.sections if s.section_type == "contact" and s.is_visible), None)
        candidate_name = "Candidate Name"
        contact_lines: List[str] = []

        if contact_sec:
            for b in contact_sec.bullets:
                if b.bullet_type == "header":
                    candidate_name = b.content
                else:
                    contact_lines.append(b.content)
        else:
            candidate_name = version.version_name or "Resume"

        # Format contact line
        contact_html_items = []
        for line in contact_lines:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            for p in parts:
                contact_html_items.append(f"<span>{p}</span>")

        contact_html = ' <span class="sep">•</span> '.join(contact_html_items)

        # ── Sections ──────────────────────────────────────────────────
        visible_sections = [s for s in version.sections if s.section_type != "contact" and s.is_visible]
        visible_sections.sort(key=lambda s: s.display_order)

        sections_html = []
        for sec in visible_sections:
            sec_header_border = f"border-bottom: 1.5px solid {tmpl.accent_color_hex};" if tmpl.header_underline else ""
            sec_body = []

            is_edu = sec.section_type == "education"
            has_pipe_rows = any("|" in b.content for b in sec.bullets)

            if is_edu and has_pipe_rows:
                # Render clean MBA education table
                rows_data = []
                for b in sec.bullets:
                    parts = [p.strip() for p in b.content.split("|") if p.strip()]
                    if len(parts) >= 3:
                        rows_data.append(parts)

                if rows_data:
                    col_count = max(len(r) for r in rows_data)
                    norm_rows = [r + [""] * (col_count - len(r)) for r in rows_data]

                    table_rows_html = []
                    for r_idx, r in enumerate(norm_rows):
                        is_head = (r_idx == 0 and any(w in r[0].lower() for w in ("degree", "qualification", "programme", "course", "year")))
                        tag = "th" if is_head else "td"
                        tds = "".join(f"<{tag}>{c}</{tag}>" for c in r)
                        tr_cls = ' class="table-header-row"' if is_head else ""
                        table_rows_html.append(f"<tr{tr_cls}>{tds}</tr>")

                    sec_body.append(f"""
                    <table class="edu-table">
                        <tbody>
                            {"".join(table_rows_html)}
                        </tbody>
                    </table>
                    """)
                else:
                    for b in sec.bullets:
                        sec_body.append(cls._bullet_to_html(b, highlight_metrics))
            else:
                for b in sec.bullets:
                    sec_body.append(cls._bullet_to_html(b, highlight_metrics))

            sections_html.append(f"""
            <div class="resume-section">
                <div class="section-title" style="{sec_header_border} color: {tmpl.accent_color_hex};">
                    {sec.title.upper()}
                </div>
                <div class="section-content">
                    {"".join(sec_body)}
                </div>
            </div>
            """)

        zoom_percent = int(zoom * 100)

        html = f"""
        <div class="resume-wrapper" style="zoom: {zoom};">
            <style>
                .resume-wrapper {{
                    display: flex;
                    justify-content: center;
                    padding: 1rem 0;
                    background: transparent;
                }}
                .resume-paper {{
                    background: #ffffff;
                    color: {tmpl.header_color_hex};
                    font-family: '{tmpl.font_family}', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    width: 100%;
                    max-width: 820px;
                    min-height: 1050px;
                    padding: {tmpl.margin_top_inches * 72}px {tmpl.margin_left_inches * 72}px;
                    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.1);
                    border-radius: 4px;
                    box-sizing: border-box;
                    font-size: {tmpl.font_size_body}pt;
                    line-height: {tmpl.line_spacing};
                }}
                .candidate-header {{
                    text-align: center;
                    margin-bottom: 12px;
                }}
                .candidate-name {{
                    font-size: {tmpl.font_size_name}pt;
                    font-weight: 700;
                    color: {tmpl.header_color_hex};
                    margin: 0 0 4px 0;
                    letter-spacing: -0.01em;
                }}
                .candidate-contact {{
                    font-size: {tmpl.font_size_sub}pt;
                    color: #475569;
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: center;
                    gap: 6px;
                    line-height: 1.3;
                }}
                .candidate-contact .sep {{
                    color: #94a3b8;
                    margin: 0 2px;
                }}
                .resume-section {{
                    margin-top: 10px;
                    margin-bottom: 6px;
                }}
                .section-title {{
                    font-size: {tmpl.font_size_header}pt;
                    font-weight: 700;
                    letter-spacing: 0.05em;
                    padding-bottom: 2px;
                    margin-bottom: 5px;
                }}
                .section-content {{
                    padding: 0 1px;
                }}
                .item-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: baseline;
                    font-size: {tmpl.font_size_body}pt;
                    font-weight: 700;
                    color: {tmpl.header_color_hex};
                    margin-top: 5px;
                    margin-bottom: 1px;
                }}
                .item-subheader {{
                    font-size: {tmpl.font_size_sub}pt;
                    color: #475569;
                    font-style: italic;
                    margin-bottom: 2px;
                }}
                .item-text {{
                    margin: 2px 0;
                    font-size: {tmpl.font_size_body}pt;
                }}
                .bullet-list {{
                    margin: 2px 0 5px 0;
                    padding-left: 18px;
                }}
                .bullet-item {{
                    font-size: {tmpl.font_size_body}pt;
                    margin-bottom: {tmpl.space_after_bullet_pt + 1}px;
                    color: #1e293b;
                    line-height: {tmpl.line_spacing};
                }}
                .edu-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 4px 0 8px 0;
                    font-size: {tmpl.font_size_sub + 0.5}pt;
                }}
                .edu-table th, .edu-table td {{
                    border: 1px solid {tmpl.table_border_color_hex};
                    padding: 3px 6px;
                    text-align: left;
                }}
                .edu-table th {{
                    background: #f8fafc;
                    font-weight: 700;
                    color: #0f172a;
                }}
                .edu-table td:last-child, .edu-table th:last-child {{
                    text-align: right;
                }}
                .metric-pill {{
                    background: #ecfdf5;
                    color: #065f46;
                    font-weight: 600;
                    padding: 0 3px;
                    border-radius: 3px;
                    border: 1px solid #a7f3d0;
                }}
                .verb-pill {{
                    color: #1e40af;
                    font-weight: 600;
                }}
                @media print {{
                    body {{ background: transparent !important; }}
                    .resume-wrapper {{ padding: 0 !important; }}
                    .resume-paper {{
                        box-shadow: none !important;
                        border-radius: 0 !important;
                        width: 100% !important;
                        max-width: 100% !important;
                        padding: 0 !important;
                    }}
                }}
            </style>
            <div class="resume-paper">
                <div class="candidate-header">
                    <div class="candidate-name">{candidate_name}</div>
                    <div class="candidate-contact">{contact_html}</div>
                </div>
                {"".join(sections_html)}
            </div>
        </div>
        """
        return html

    @classmethod
    def _bullet_to_html(cls, b: BulletItem, highlight_metrics: bool = False) -> str:
        """Convert a single bullet into clean semantic HTML."""
        content = b.content.strip()

        if b.bullet_type in ("header", "subheader"):
            # If header contains separation like '|' or '—', format into flex row
            if "—" in content:
                parts = [p.strip() for p in content.split("—", 1)]
                return f"""
                <div class="item-header">
                    <span>{parts[0]}</span>
                    <span style="font-weight: normal; font-size: 0.9em; color: #475569;">{parts[1]}</span>
                </div>
                """
            elif "|" in content:
                parts = [p.strip() for p in content.split("|", 1)]
                return f"""
                <div class="item-header">
                    <span>{parts[0]}</span>
                    <span style="font-weight: normal; font-size: 0.9em; color: #475569;">{parts[1]}</span>
                </div>
                """
            else:
                return f'<div class="item-header"><span>{content}</span></div>'

        if b.bullet_type == "text":
            return f'<div class="item-text">{content}</div>'

        # Regular bullet item
        clean_text = re.sub(r"^[\s•\-\*–—\?]+", "", content).strip()

        if highlight_metrics:
            # Highlight action verb if present
            if b.action_verb and b.action_verb.lower() in clean_text.lower():
                # case-insensitive replace of the first occurrence
                pattern = re.compile(re.escape(b.action_verb), re.IGNORECASE)
                clean_text = pattern.sub(f'<span class="verb-pill">{b.action_verb.title()}</span>', clean_text, count=1)

            # Highlight metrics if present
            for m in b.metrics:
                if m in clean_text:
                    clean_text = clean_text.replace(m, f'<span class="metric-pill">{m}</span>')

        return f'<ul class="bullet-list" style="list-style-type: disc;"><li class="bullet-item">{clean_text}</li></ul>'
