"""Data models for Job Tracking, Search Profiles, and Application Lifecycle.

All records utilize stable UUIDs and support timeline event audits.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    """Normalized job opportunity representation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    company: str
    location: Optional[str] = "Any"
    employment_type: Optional[str] = "Full-time"
    experience_min: Optional[int] = 0
    experience_max: Optional[int] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "INR"
    date_posted: Optional[str] = None
    description: Optional[str] = ""
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    source_portal: str = "manual"  # manual, linkedin, iimjobs, indeed, naukri
    original_url: Optional[str] = None
    application_url: Optional[str] = None
    status: str = "active"  # active, expired, closed, unknown
    is_manually_entered: bool = True
    first_discovered: Optional[str] = None
    last_seen: Optional[str] = None


class JobSearchProfile(BaseModel):
    """User preferences for target roles, industries, and keywords."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    is_default: bool = False
    target_roles: List[str] = Field(default_factory=list)
    preferred_industries: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    remote_preference: str = "any"  # remote, hybrid, onsite, any
    experience_level: Optional[str] = None
    employment_type: Optional[str] = None
    min_salary: Optional[float] = None
    salary_currency: str = "INR"
    required_keywords: List[str] = Field(default_factory=list)
    excluded_keywords: List[str] = Field(default_factory=list)
    companies_of_interest: List[str] = Field(default_factory=list)
    max_job_age_days: int = 30


class ApplicationRecord(BaseModel):
    """Tracks a candidate's application through the hiring funnel."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    resume_version_id: Optional[str] = None
    status: str = "saved"  # saved, shortlisted, resume_prepared, applied, assessment, interview, offer, rejected, withdrawn
    application_date: Optional[str] = None
    follow_up_date: Optional[str] = None
    notes: Optional[str] = ""
    recruiter_name: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_phone: Optional[str] = None
    interview_stages: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ApplicationEvent(BaseModel):
    """Immutable audit trail event in the application lifecycle."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str
    event_type: str = "status_change"  # status_change, note, follow_up, interview, feedback, other
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    description: Optional[str] = ""
    event_date: Optional[str] = None
    created_at: Optional[str] = None


class ApplicationWithJob(BaseModel):
    """Joined view combining application status with job details."""
    application: ApplicationRecord
    job: JobPosting
    resume_version_name: Optional[str] = None
    events_count: int = 0
