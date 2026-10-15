"""Data models for Resume-Job Matching, Scoring Breakdown, and Evidence Attribution.

Provides structured gap analysis and bullet-level evidence mapping.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MatchScoreBreakdown(BaseModel):
    """Component scores contributing to the overall match score."""
    skills_score: float = 0.0
    title_score: float = 0.0
    experience_score: float = 0.0
    education_score: float = 0.0
    overall_score: float = 0.0


class MatchResult(BaseModel):
    """Complete diagnostic match assessment between a resume version and a job posting."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    resume_version_id: str
    overall_score: float  # 0 to 100
    score_breakdown: MatchScoreBreakdown = Field(default_factory=MatchScoreBreakdown)
    matched_requirements: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    partial_requirements: List[str] = Field(default_factory=list)
    resume_evidence: Dict[str, List[str]] = Field(default_factory=dict)  # requirement -> [bullet text]
    improvement_suggestions: List[str] = Field(default_factory=list)
    match_method: str = "keyword"  # keyword, semantic, hybrid, ai
    is_stale: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
