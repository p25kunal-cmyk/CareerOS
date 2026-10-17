"""Resume parsing engine for PDF, DOCX, and text formats.

Extracts structured sections, bullets, contact information, and metadata
with special handling for MBA formats (tables, IIM headers, metrics).
"""

from __future__ import annotations

import io
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import docx

from src.resume.models import BulletItem, ContactInfo, ParsedResume, SectionItem
from src.utils.logger import get_logger

logger = get_logger("resume.parser")

# ── Common Action Verbs ───────────────────────────────────────
ACTION_VERBS = {
    "accelerated", "accomplished", "achieved", "acquired", "administered",
    "advised", "allocated", "analyzed", "appraised", "architected", "audited",
    "automated", "boosted", "budgeted", "built", "championed", "coached",
    "collaborated", "consolidated", "consulted", "controlled", "coordinated",
    "counseled", "created", "curated", "customized", "decreased", "defined",
    "delivered", "deployed", "designed", "developed", "devised", "directed",
    "drove", "eliminated", "enabled", "engineered", "enhanced", "established",
    "evaluated", "executed", "expanded", "expedited", "facilitated", "forecasted",
    "formulated", "founded", "generated", "governed", "guided", "headed",
    "identified", "implemented", "improved", "increased", "initiated", "innovated",
    "inspected", "instituted", "instructed", "integrated", "interviewed",
    "introduced", "investigated", "launched", "led", "leveraged", "managed",
    "maximized", "measured", "mentored", "minimized", "modeled", "monitored",
    "motivated", "navigated", "negotiated", "optimized", "orchestrated",
    "organized", "outperformed", "overhauled", "oversaw", "partnered",
    "performed", "pioneered", "planned", "positioned", "prepared", "presented",
    "prioritized", "produced", "programmed", "promoted", "proposed", "published",
    "re-engineered", "reconciled", "recruited", "redesigned", "reduced",
    "refined", "reformed", "remodeled", "reorganized", "restructured",
    "retrieved", "revamped", "reviewed", "revitalized", "saved", "scaled",
    "scheduled", "secured", "shaped", "simplified", "slashed", "solved",
    "spearheaded", "standardized", "steered", "streamlined", "strengthened",
    "structured", "supervised", "synthesized", "systematized", "targeted",
    "trained", "transformed", "unified", "upgraded", "utilized", "validated"
}

# ── Section Mapping ───────────────────────────────────────────
SECTION_PATTERNS = [
    ("contact", re.compile(r"^(contact|personal\s+details|personal\s+information|candidate\s+info)$", re.IGNORECASE)),
    ("summary", re.compile(r"^(summary|executive\s+summary|professional\s+summary|profile|about\s+me|career\s+objective|objective)$", re.IGNORECASE)),
    ("education", re.compile(r"^(education|academic\s+qualifications|academics|educational\s+background|academic\s+credentials|qualification)$", re.IGNORECASE)),
    ("experience", re.compile(r"^(experience|work\s+experience|professional\s+experience|employment\s+history|career\s+history)$", re.IGNORECASE)),
    ("internships", re.compile(r"^(internships|internship\s+experience|summer\s+internship|summer\s+internships|industrial\s+training|live\s+projects)$", re.IGNORECASE)),
    ("projects", re.compile(r"^(projects|academic\s+projects|key\s+projects|selected\s+projects|capstone\s+projects)$", re.IGNORECASE)),
    ("skills", re.compile(r"^(skills|technical\s+skills|core\s+competencies|competencies|areas\s+of\s+expertise|key\s+skills|technical\s+proficiencies|tools\s+&\s+technologies)$", re.IGNORECASE)),
    ("positions_of_responsibility", re.compile(r"^(positions\s+of\s+responsibility|leadership|leadership\s+roles|responsibilities|pors|committee\s+memberships)$", re.IGNORECASE)),
    ("certifications", re.compile(r"^(certifications|licenses\s+&\s+certifications|professional\s+certifications|courses)$", re.IGNORECASE)),
    ("achievements", re.compile(r"^(achievements|scholastic\s+achievements|honors\s+&\s+awards|awards\s+&\s+achievements|recognitions)$", re.IGNORECASE)),
    ("extracurricular", re.compile(r"^(extracurricular|extra-curricular\s+activities|co-curricular\s+activities|interests|hobbies)$", re.IGNORECASE)),
]

METRIC_REGEX = re.compile(
    r"(\$[\d,]+(?:\.\d+)?\s*[kKmMbBtT]?|[₹€£]\s*[\d,]+(?:\.\d+)?\s*[kKmMbBtTLCr]?|\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*(?:k|K|M|B|Cr|Lakhs?|Crores?|bps|x|X)\b|\b\d+\+?(?:\s*(?:users|clients|teams|members|people|projects|million|billion|lakh|crore))?)",
    re.IGNORECASE,
)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:(?:\+91|91|0)[\s-]?)?[6-9]\d{9}|\b\+?[1-9]\d{0,2}[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b")
LINKEDIN_REGEX = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_-]+)/?", re.IGNORECASE)
GITHUB_REGEX = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/?", re.IGNORECASE)


class ResumeParser:
    """Parses resumes from various formats into structured models."""

    def parse_file(self, file_path_or_bytes: str | bytes | io.BytesIO, filename: str) -> ParsedResume:
        """Parse resume from a file path or in-memory byte buffer."""
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            try:
                return self._parse_pdf(file_path_or_bytes)
            except Exception as e:
                logger.error("PDF parsing failed: %s", e)
                raise ValueError(
                    f"Could not parse PDF file '{filename}'. "
                    "The file may be corrupted, password-protected, or a scanned image. "
                    "Try saving it as a new PDF or converting to DOCX/TXT."
                ) from e
        elif ext == ".docx":
            try:
                return self._parse_docx(file_path_or_bytes)
            except Exception as e:
                logger.error("DOCX parsing failed: %s", e)
                raise ValueError(
                    f"Could not parse DOCX file '{filename}'. "
                    "The file may be corrupted or in an unsupported format."
                ) from e
        elif ext == ".doc":
            # Old .doc format: try as DOCX first, then fall back to text extraction
            try:
                return self._parse_docx(file_path_or_bytes)
            except Exception:
                logger.warning("DOCX parse failed for .doc file, falling back to text extraction")
                try:
                    return self._parse_text(file_path_or_bytes)
                except Exception as e2:
                    logger.error("Text fallback also failed for .doc: %s", e2)
                    raise ValueError(
                        f"Could not parse .doc file '{filename}'. "
                        "Old .doc format has limited support. Please save as .docx or .pdf first, "
                        "then re-upload."
                    ) from e2
        elif ext in (".txt", ".md"):
            return self._parse_text(file_path_or_bytes)
        else:
            raise ValueError(f"Unsupported file format: {ext}. CareerOS supports PDF, DOCX, and TXT/MD.")

    def _parse_pdf(self, file_source: str | bytes | io.BytesIO) -> ParsedResume:
        """Parse PDF document with layout and font awareness."""
        if isinstance(file_source, str):
            doc = fitz.open(file_source)
        elif isinstance(file_source, bytes):
            doc = fitz.open(stream=file_source, filetype="pdf")
        elif isinstance(file_source, io.BytesIO):
            doc = fitz.open(stream=file_source.getvalue(), filetype="pdf")
        else:
            raise TypeError("Unsupported file source type")

        lines_with_meta: List[Dict[str, Any]] = []
        raw_text_parts: List[str] = []

        for page in doc:
            page_text = page.get_text()
            raw_text_parts.append(page_text)
            
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        line_text = ""
                        max_font_size = 0.0
                        is_bold = False
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")
                            font_size = span.get("size", 10.0)
                            if font_size > max_font_size:
                                max_font_size = font_size
                            flags = span.get("flags", 0)
                            font_name = span.get("font", "").lower()
                            if (flags & 2 != 0) or ("bold" in font_name):
                                is_bold = True

                        cleaned_line = line_text.strip()
                        if cleaned_line:
                            lines_with_meta.append({
                                "text": cleaned_line,
                                "font_size": max_font_size,
                                "is_bold": is_bold,
                            })

        doc.close()
        raw_text = "\n".join(raw_text_parts)

        warnings = []
        if len(raw_text.strip()) < 50:
            warnings.append("Document yielded very little text. It may be a scanned image or non-selectable PDF.")

        return self._build_parsed_resume(raw_text, lines_with_meta, file_type="pdf", warnings=warnings)

    def _parse_docx(self, file_source: str | bytes | io.BytesIO) -> ParsedResume:
        """Parse DOCX document handling paragraphs and tables in true document sequence."""
        if isinstance(file_source, (bytes, io.BytesIO)):
            bio = file_source if isinstance(file_source, io.BytesIO) else io.BytesIO(file_source)
            doc = docx.Document(bio)
        elif isinstance(file_source, str):
            doc = docx.Document(file_source)
        else:
            raise TypeError("Unsupported file source type")

        lines_with_meta: List[Dict[str, Any]] = []
        raw_text_parts: List[str] = []

        # Iterate in true document order through body elements
        for element in doc.element.body:
            if element.tag.endswith('p'):
                p = docx.text.paragraph.Paragraph(element, doc)
                text = p.text.strip()
                if not text:
                    continue
                raw_text_parts.append(text)

                is_bold = any(run.bold for run in p.runs if run.bold)
                is_heading = p.style.name.startswith("Heading") or is_bold
                font_size = 11.0
                for run in p.runs:
                    if run.font.size and run.font.size.pt:
                        font_size = max(font_size, run.font.size.pt)

                lines_with_meta.append({
                    "text": text,
                    "font_size": font_size,
                    "is_bold": is_bold or is_heading,
                    "style": p.style.name,
                })

            elif element.tag.endswith('tbl'):
                table = docx.table.Table(element, doc)
                for row in table.rows:
                    cell_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    unique_texts = []
                    for ct in cell_texts:
                        if not unique_texts or unique_texts[-1] != ct:
                            unique_texts.append(ct)
                    if unique_texts:
                        combined_row = " | ".join(unique_texts)
                        raw_text_parts.append(combined_row)
                        lines_with_meta.append({
                            "text": combined_row,
                            "font_size": 10.0,
                            "is_bold": False,
                            "is_table_row": True,
                        })

        raw_text = "\n".join(raw_text_parts)
        return self._build_parsed_resume(raw_text, lines_with_meta, file_type="docx")

    def _parse_text(self, file_source: str | bytes | io.BytesIO) -> ParsedResume:
        """Parse plain text or Markdown resume."""
        if isinstance(file_source, str):
            with open(file_source, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
        elif isinstance(file_source, bytes):
            raw_text = file_source.decode("utf-8", errors="ignore")
        elif isinstance(file_source, io.BytesIO):
            raw_text = file_source.getvalue().decode("utf-8", errors="ignore")
        else:
            raise TypeError("Unsupported file source type")

        lines_with_meta: List[Dict[str, Any]] = []
        for line in raw_text.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            is_header = cleaned.startswith("#") or cleaned.isupper()
            text = cleaned.lstrip("#").strip()
            lines_with_meta.append({
                "text": text,
                "font_size": 14.0 if is_header else 10.0,
                "is_bold": is_header,
            })

        return self._build_parsed_resume(raw_text, lines_with_meta, file_type="text")

    def _extract_contact_info(self, raw_text: str, lines: List[Dict[str, Any]]) -> ContactInfo:
        """Extract candidate contact information using robust regex & position."""
        contact = ContactInfo()
        contact.raw_header = "\n".join(item["text"] for item in lines[:6])

        # Email
        emails = EMAIL_REGEX.findall(raw_text)
        if emails:
            contact.email = emails[0].strip()

        # Phone
        phones = PHONE_REGEX.findall(raw_text)
        if phones:
            contact.phone = phones[0].strip()

        # LinkedIn
        linkedins = LINKEDIN_REGEX.findall(raw_text)
        if linkedins:
            contact.linkedin = f"https://linkedin.com/in/{linkedins[0]}"
        elif "linkedin.com" in raw_text.lower():
            match = re.search(r"linkedin\.com/[^\s,]+", raw_text, re.IGNORECASE)
            if match:
                contact.linkedin = "https://" + match.group(0).lstrip("https://").lstrip("http://")

        # GitHub
        githubs = GITHUB_REGEX.findall(raw_text)
        if githubs:
            contact.github = f"https://github.com/{githubs[0]}"

        # Name detection: look at top 4 lines
        for item in lines[:4]:
            t = item["text"]
            if ("@" not in t and "http" not in t and "linkedin" not in t.lower()
                    and not re.search(r"\d{5,}", t) and len(t.split()) in (2, 3, 4)
                    and not self._identify_section_type(t)):
                contact.name = t
                break

        return contact

    def _identify_section_type(self, title: str) -> Optional[str]:
        """Classify a section header into standard section type."""
        norm_title = re.sub(r"[:\-_|]", "", title).strip()
        for sec_type, pattern in SECTION_PATTERNS:
            if pattern.match(norm_title):
                return sec_type
        return None

    def _is_section_header(self, item: Dict[str, Any], median_font_size: float) -> bool:
        """Determine if a line is likely a section header."""
        text = item["text"].strip()
        if len(text) > 60:
            return False

        # Direct pattern match
        if self._identify_section_type(text) is not None:
            return True

        # Font-based detection
        is_large = item.get("font_size", 10.0) >= (median_font_size + 1.5)
        is_bold = item.get("is_bold", False)
        is_all_caps = text.isupper() and len(text.split()) <= 5

        if (is_large or (is_bold and is_all_caps)) and len(text.split()) <= 5:
            if not text.startswith(("-", "•", "*", "–", "—", "?")) and not EMAIL_REGEX.search(text):
                return True

        return False

    def _analyze_bullet(self, text: str) -> Tuple[Optional[str], List[str]]:
        """Extract action verbs and metrics from a bullet point."""
        cleaned = re.sub(r"^[\s•\-\*–—\d\.\)\?]+", "", text).strip()
        first_word = cleaned.split()[0].lower() if cleaned.split() else ""
        first_word_clean = re.sub(r"[^a-zA-Z]", "", first_word)
        
        action_verb = first_word_clean if first_word_clean in ACTION_VERBS else None
        matches = METRIC_REGEX.findall(text)
        metrics = [m.strip() for m in matches if m.strip()]

        return action_verb, metrics

    def _build_parsed_resume(
        self,
        raw_text: str,
        lines: List[Dict[str, Any]],
        file_type: str,
        warnings: Optional[List[str]] = None
    ) -> ParsedResume:
        """Assemble structured ParsedResume from extracted lines."""
        warnings = warnings or []
        contact_info = self._extract_contact_info(raw_text, lines)

        # Calculate median font size
        font_sizes = [item.get("font_size", 10.0) for item in lines if item.get("font_size")]
        median_font_size = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 10.0

        sections: List[SectionItem] = []
        current_section: Optional[SectionItem] = None
        current_order = 0

        # Skip only leading contact lines until first non-contact line
        header_skipped = 0
        while header_skipped < len(lines):
            line_txt = lines[header_skipped]["text"]
            if (EMAIL_REGEX.search(line_txt) or PHONE_REGEX.search(line_txt)
                    or "linkedin.com" in line_txt.lower() or line_txt == contact_info.name):
                header_skipped += 1
            else:
                break

        body_lines = lines[header_skipped:]

        for item in body_lines:
            text = item["text"].strip()
            if not text:
                continue

            if self._is_section_header(item, median_font_size):
                sec_type = self._identify_section_type(text) or "custom"
                current_order += 1
                current_section = SectionItem(
                    id=str(uuid.uuid4()),
                    section_type=sec_type,
                    title=text,
                    display_order=current_order,
                    bullets=[],
                )
                sections.append(current_section)
            else:
                if current_section is None:
                    current_order += 1
                    current_section = SectionItem(
                        id=str(uuid.uuid4()),
                        section_type="summary",
                        title="Summary",
                        display_order=current_order,
                        bullets=[],
                    )
                    sections.append(current_section)

                action_verb, metrics = self._analyze_bullet(text)
                bullet_type = "bullet"
                if item.get("is_table_row"):
                    bullet_type = "text"
                elif item.get("is_bold") and len(text.split()) <= 8 and not text.startswith(("-", "•", "*", "?")):
                    bullet_type = "header"

                bullet = BulletItem(
                    id=str(uuid.uuid4()),
                    section_id=current_section.id,
                    content=text,
                    bullet_type=bullet_type,
                    display_order=len(current_section.bullets) + 1,
                    action_verb=action_verb,
                    metrics=metrics,
                    is_verified=True,
                )
                current_section.bullets.append(bullet)

        if not sections:
            single_section = SectionItem(
                id=str(uuid.uuid4()),
                section_type="summary",
                title="Resume Content",
                display_order=1,
                bullets=[
                    BulletItem(
                        id=str(uuid.uuid4()),
                        content=item["text"],
                        display_order=idx + 1,
                    )
                    for idx, item in enumerate(lines)
                ]
            )
            sections.append(single_section)

        return ParsedResume(
            contact_info=contact_info,
            sections=sections,
            raw_text=raw_text,
            warnings=warnings,
            file_type=file_type,
        )
