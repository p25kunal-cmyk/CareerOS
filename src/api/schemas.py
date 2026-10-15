"""Request/Response schemas for the CareerOS local REST API.

Pydantic v2 models used for validation, serialization, and OpenAPI docs.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ── Health ────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    uptime_seconds: float = 0.0


# ── Jobs ──────────────────────────────────────────────────────

class QuickJobCreate(BaseModel):
    """Minimal payload from Chrome extension to save a job."""
    title: str = Field(..., min_length=1, max_length=500)
    company: str = Field(..., min_length=1, max_length=300)
    location: Optional[str] = None
    employment_type: Optional[str] = None
    description: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    source_portal: str = "chrome_extension"
    original_url: Optional[str] = None
    application_url: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "INR"
    experience_min: Optional[int] = None
    experience_max: Optional[int] = None


class JobResponse(BaseModel):
    id: str
    title: str
    company: str
    location: Optional[str] = None
    employment_type: Optional[str] = None
    status: str = "active"
    source_portal: str = "manual"
    original_url: Optional[str] = None
    created: bool = False


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int


# ── Applications ──────────────────────────────────────────────

class ApplicationStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(saved|shortlisted|resume_prepared|applied|assessment|interview|offer|rejected|withdrawn)$",
    )
    note: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    status: str
    job_title: str
    company: str
    application_date: Optional[str] = None
    updated_at: Optional[str] = None


class ApplicationListResponse(BaseModel):
    applications: List[ApplicationResponse]
    total: int


# ── Resumes ───────────────────────────────────────────────────

class ResumeListItem(BaseModel):
    id: str
    name: str
    is_master: bool = False
    version_count: int = 1
    updated_at: str


class ResumeListResponse(BaseModel):
    resumes: List[ResumeListItem]
    total: int


# ── Pipeline Stats ────────────────────────────────────────────

class PipelineStatsResponse(BaseModel):
    stages: Dict[str, int]
    total_applications: int


# ── Quick Match ───────────────────────────────────────────────

class QuickMatchRequest(BaseModel):
    job_id: str
    resume_id: Optional[str] = None


class QuickMatchResponse(BaseModel):
    overall_score: float
    matched_skills: List[str]
    missing_skills: List[str]
    suggestions: List[str]


# ── Error ─────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
