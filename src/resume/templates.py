"""Resume templates and formatting configuration.

Defines layout conventions, typography, and section styling for MBA,
Executive, and Product Management formats.
"""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class TemplateConfig(BaseModel):
    """Configuration schema for a resume export template."""
    id: str
    name: str
    description: str
    font_family: str = "Calibri"
    font_size_name: float = 16.0
    font_size_header: float = 12.0
    font_size_body: float = 10.0
    font_size_sub: float = 9.0
    margin_top_inches: float = 0.5
    margin_bottom_inches: float = 0.5
    margin_left_inches: float = 0.6
    margin_right_inches: float = 0.6
    line_spacing: float = 1.15
    space_after_heading_pt: float = 3.0
    space_after_bullet_pt: float = 2.0
    header_underline: bool = True
    header_color_hex: str = "#0f172a"
    accent_color_hex: str = "#1e3a8a"
    table_border_color_hex: str = "#cbd5e1"
    section_order: List[str] = Field(default_factory=list)


# ── Built-in Templates ────────────────────────────────────────

IIM_NAGPUR_TEMPLATE = TemplateConfig(
    id="iim_nagpur",
    name="IIM Nagpur MBA Standard",
    description="Rigorous MBA placement format with clean tabular education, highlighted metrics, and summer internship sections.",
    font_family="Calibri",
    font_size_name=16.0,
    font_size_header=11.5,
    font_size_body=9.5,
    font_size_sub=8.5,
    margin_top_inches=0.45,
    margin_bottom_inches=0.45,
    margin_left_inches=0.55,
    margin_right_inches=0.55,
    line_spacing=1.05,
    space_after_heading_pt=2.0,
    space_after_bullet_pt=1.5,
    header_underline=True,
    header_color_hex="#0f172a",
    accent_color_hex="#1e293b",
    table_border_color_hex="#94a3b8",
    section_order=[
        "contact",
        "education",
        "experience",
        "internships",
        "projects",
        "positions_of_responsibility",
        "certifications",
        "skills",
        "achievements",
        "extracurricular",
    ],
)

PROFESSIONAL_TEMPLATE = TemplateConfig(
    id="professional",
    name="Corporate Executive",
    description="Classic corporate format optimized for consulting, finance, and general management roles.",
    font_family="Arial",
    font_size_name=18.0,
    font_size_header=12.0,
    font_size_body=10.0,
    font_size_sub=9.0,
    margin_top_inches=0.6,
    margin_bottom_inches=0.6,
    margin_left_inches=0.65,
    margin_right_inches=0.65,
    line_spacing=1.15,
    space_after_heading_pt=4.0,
    space_after_bullet_pt=2.5,
    header_underline=True,
    header_color_hex="#1e293b",
    accent_color_hex="#3b82f6",
    table_border_color_hex="#e2e8f0",
    section_order=[
        "contact",
        "summary",
        "experience",
        "education",
        "projects",
        "skills",
        "certifications",
        "achievements",
    ],
)

PRODUCT_MANAGEMENT_TEMPLATE = TemplateConfig(
    id="product_management",
    name="Tech & Product Manager",
    description="Modern layout emphasizing measurable impact, product metrics, tech proficiencies, and initiatives.",
    font_family="Arial",
    font_size_name=17.0,
    font_size_header=12.0,
    font_size_body=10.0,
    font_size_sub=9.0,
    margin_top_inches=0.5,
    margin_bottom_inches=0.5,
    margin_left_inches=0.6,
    margin_right_inches=0.6,
    line_spacing=1.15,
    space_after_heading_pt=3.5,
    space_after_bullet_pt=2.0,
    header_underline=False,
    header_color_hex="#0f172a",
    accent_color_hex="#6366f1",
    table_border_color_hex="#cbd5e1",
    section_order=[
        "contact",
        "summary",
        "experience",
        "projects",
        "skills",
        "education",
        "achievements",
        "certifications",
    ],
)

TEMPLATES: Dict[str, TemplateConfig] = {
    "iim_nagpur": IIM_NAGPUR_TEMPLATE,
    "professional": PROFESSIONAL_TEMPLATE,
    "product_management": PRODUCT_MANAGEMENT_TEMPLATE,
}


def get_template(template_id: str) -> TemplateConfig:
    """Retrieve template configuration by ID with fallback to IIM Nagpur."""
    return TEMPLATES.get(template_id, IIM_NAGPUR_TEMPLATE)
