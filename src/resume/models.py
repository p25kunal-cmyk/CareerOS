"""Data models and schemas for the Resume Engine.

All entities use stable UUIDs so that edits, version forks, and reorders
preserve item identity across sessions.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    """Structured candidate contact information."""
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    location: str = ""
    website: str = ""
    raw_header: str = ""


class BulletItem(BaseModel):
    """A single atomic bullet or text element within a resume section."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    section_id: Optional[str] = None
    content: str
    sub_content: Optional[str] = None
    bullet_type: str = "bullet"  # bullet, header, subheader, text, skill_group, date_range, location, contact_item
    display_order: int = 0
    indent_level: int = 0
    is_verified: bool = True
    action_verb: Optional[str] = None
    metrics: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SectionItem(BaseModel):
    """A logical section of a resume (e.g. Work Experience, Education)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version_id: Optional[str] = None
    section_type: str = "experience"  # contact, summary, education, experience, internships, projects, skills, certifications, achievements, positions_of_responsibility, extracurricular, custom
    title: str
    display_order: int = 0
    is_visible: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    bullets: List[BulletItem] = Field(default_factory=list)


class ResumeVersionData(BaseModel):
    """Complete snapshot of a resume version with all sections and bullets."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resume_id: str
    version_number: int = 1
    version_name: Optional[str] = None
    description: Optional[str] = None
    is_draft: bool = False
    parent_version_id: Optional[str] = None
    created_at: Optional[str] = None
    sections: List[SectionItem] = Field(default_factory=list)

    def to_snapshot_json(self) -> str:
        """Serialize full content snapshot to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_snapshot_json(cls, json_str: str) -> ResumeVersionData:
        """Deserialize from snapshot JSON."""
        return cls.model_validate_json(json_str)


class ResumeSummary(BaseModel):
    """High-level summary of a resume profile."""
    id: str
    name: str
    is_master: bool = False
    original_filename: Optional[str] = None
    original_file_path: Optional[str] = None
    file_type: Optional[str] = None
    upload_timestamp: Optional[str] = None
    notes: Optional[str] = None
    version_count: int = 1
    latest_version_number: int = 1
    created_at: str
    updated_at: str


class ParsedResume(BaseModel):
    """Result of parsing a raw document (PDF/DOCX/TXT)."""
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    sections: List[SectionItem] = Field(default_factory=list)
    raw_text: str = ""
    warnings: List[str] = Field(default_factory=list)
    file_type: str = "pdf"
