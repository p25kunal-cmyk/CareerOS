"""Matching Engine for scoring resumes against job opportunities.

Performs deterministic keyword extraction, synonym normalization,
multi-factor scoring, gap analysis, and bullet evidence attribution.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from src.database.connection import DatabaseConnection
from src.matching.models import MatchResult, MatchScoreBreakdown
from src.resume.models import BulletItem, ResumeVersionData
from src.tracker.models import JobPosting
from src.utils.logger import get_logger

logger = get_logger("matching.engine")

# ── Synonyms & Acronym Normalization ──────────────────────────
SYNONYM_MAP: Dict[str, Set[str]] = {
    "product management": {"pm", "product manager", "product strategy", "product roadmapping", "product lifecycle"},
    "go to market": {"gtm", "go-to-market", "market launch", "commercialization"},
    "analytics": {"data analytics", "business analytics", "sql", "tableau", "power bi", "bi", "metrics"},
    "machine learning": {"ml", "data science", "ai", "artificial intelligence", "nlp", "predictive modeling"},
    "financial modeling": {"valuation", "dcf", "financial analysis", "p&l", "budgeting", "corporate finance"},
    "consulting": {"management consulting", "strategy consulting", "advisory", "case study", "business strategy"},
    "agile": {"scrum", "kanban", "sprints", "jira", "user stories"},
    "a/b testing": {"ab testing", "experimentation", "hypothesis testing", "split testing"},
    "operations": {"supply chain", "logistics", "process optimization", "six sigma", "operational excellence"},
    "mba": {"pgdm", "master of business administration", "iim", "management degree"},
}


class MatchingEngine:
    """Computes match diagnostics and evidence between a resume version and a job posting."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def calculate_match(
        self,
        resume_version: ResumeVersionData,
        job: JobPosting,
        match_method: str = "keyword",
    ) -> MatchResult:
        """Score resume against job posting and attribute evidence."""
        # 1. Collect candidate resume text & bullet map
        all_bullets: List[BulletItem] = [b for s in resume_version.sections for b in s.bullets]
        resume_full_text = " ".join(b.content for b in all_bullets).lower()

        # 2. Extract job requirements
        target_skills = list(job.required_skills)
        if not target_skills and job.description:
            # Extract common skills and terms from JD
            target_skills = self._extract_terms_from_text(job.description)

        if not target_skills:
            target_skills = ["Communication", "Leadership", "Problem Solving", "Strategy"]

        matched_reqs: List[str] = []
        missing_reqs: List[str] = []
        partial_reqs: List[str] = []
        evidence: Dict[str, List[str]] = {}

        for skill in target_skills:
            norm_skill = skill.strip().lower()
            matching_variants = {norm_skill}
            for canon, syns in SYNONYM_MAP.items():
                if norm_skill == canon or norm_skill in syns:
                    matching_variants.add(canon)
                    matching_variants.update(syns)

            # Check if any variant appears in resume
            is_matched = False
            supporting_bullets = []

            for bullet in all_bullets:
                b_text_lower = bullet.content.lower()
                for var in matching_variants:
                    # Match word boundary
                    pattern = rf"\b{re.escape(var)}\b"
                    if re.search(pattern, b_text_lower):
                        is_matched = True
                        if bullet.content not in supporting_bullets:
                            supporting_bullets.append(bullet.content)

            if is_matched:
                matched_reqs.append(skill)
                evidence[skill] = supporting_bullets[:2]  # top 2 supporting bullets
            else:
                # Check for partial word overlap
                words = [w for w in norm_skill.split() if len(w) > 3]
                if words and any(w in resume_full_text for w in words):
                    partial_reqs.append(skill)
                else:
                    missing_reqs.append(skill)

        # 3. Factor calculations
        total_skills = len(target_skills) or 1
        skills_score = min(100.0, ((len(matched_reqs) + len(partial_reqs) * 0.5) / total_skills) * 100)

        # Title alignment score
        title_score = self._calculate_title_score(resume_version, job.title)

        # Experience alignment score
        exp_score = self._calculate_experience_score(resume_version, job.experience_min or 0)

        # Education score
        edu_score = self._calculate_education_score(resume_version)

        # 4. Weighted overall score
        # 40% Skills, 25% Title alignment, 20% Experience, 15% Education
        overall = (skills_score * 0.40) + (title_score * 0.25) + (exp_score * 0.20) + (edu_score * 0.15)
        overall_clamped = round(max(0.0, min(100.0, overall)), 1)

        breakdown = MatchScoreBreakdown(
            skills_score=round(skills_score, 1),
            title_score=round(title_score, 1),
            experience_score=round(exp_score, 1),
            education_score=round(edu_score, 1),
            overall_score=overall_clamped,
        )

        # 5. Improvement suggestions
        suggestions = []
        if missing_reqs:
            top_missing = missing_reqs[:3]
            suggestions.append(f"Incorporate missing core skills: {', '.join(top_missing)}.")
        if skills_score < 70 and partial_reqs:
            suggestions.append(f"Strengthen context around partial matches: {', '.join(partial_reqs[:2])}.")
        if title_score < 60:
            suggestions.append(f"Tailor your Executive Summary to explicitly highlight interest in '{job.title}'.")

        result = MatchResult(
            job_id=job.id,
            resume_version_id=resume_version.id,
            overall_score=overall_clamped,
            score_breakdown=breakdown,
            matched_requirements=matched_reqs,
            missing_requirements=missing_reqs,
            partial_requirements=partial_reqs,
            resume_evidence=evidence,
            improvement_suggestions=suggestions,
            match_method=match_method,
            is_stale=False,
        )

        # 6. Save to database
        self.save_match_result(result)
        return result

    def _extract_terms_from_text(self, text: str) -> List[str]:
        """Extract prominent technical, business, and MBA terms from description."""
        terms = []
        text_lower = text.lower()
        for canon, variants in SYNONYM_MAP.items():
            if canon in text_lower or any(v in text_lower for v in variants):
                terms.append(canon.title())
        return list(dict.fromkeys(terms))[:8]

    def _calculate_title_score(self, resume: ResumeVersionData, job_title: str) -> float:
        """Score title alignment based on keywords in resume."""
        clean_title_words = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", job_title)]
        if not clean_title_words:
            return 80.0

        full_resume_text = " ".join(b.content for s in resume.sections for b in s.bullets).lower()
        matched = sum(1 for w in clean_title_words if w in full_resume_text)
        return min(100.0, (matched / len(clean_title_words)) * 100.0)

    def _calculate_experience_score(self, resume: ResumeVersionData, exp_min: int) -> float:
        """Estimate experience alignment."""
        exp_sec = next((s for s in resume.sections if s.section_type in ("experience", "internships")), None)
        if not exp_sec or not exp_sec.bullets:
            return 50.0 if exp_min > 0 else 85.0

        # Number of achievement bullets correlates with candidate experience depth
        bullet_count = len(exp_sec.bullets)
        if exp_min <= 2:
            return 95.0 if bullet_count >= 3 else 80.0
        elif exp_min <= 5:
            return 90.0 if bullet_count >= 5 else 75.0
        else:
            return 85.0 if bullet_count >= 6 else 65.0

    def _calculate_education_score(self, resume: ResumeVersionData) -> float:
        """Score academic pedigree (MBA / Premier institutes)."""
        edu_sec = next((s for s in resume.sections if s.section_type == "education"), None)
        if not edu_sec:
            return 70.0

        edu_text = " ".join(b.content for b in edu_sec.bullets).lower()
        if "iim" in edu_text or "mba" in edu_text or "iit" in edu_text or "bits" in edu_text or "nit" in edu_text:
            return 100.0
        return 85.0

    def save_match_result(self, match: MatchResult) -> bool:
        """Persist match assessment into job_matches table."""
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO job_matches (
                    id, job_id, resume_version_id, overall_score, score_breakdown,
                    matched_requirements, missing_requirements, partial_requirements,
                    resume_evidence, improvement_suggestions, match_method, is_stale,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(job_id, resume_version_id, match_method) DO UPDATE SET
                    overall_score = excluded.overall_score,
                    score_breakdown = excluded.score_breakdown,
                    matched_requirements = excluded.matched_requirements,
                    missing_requirements = excluded.missing_requirements,
                    partial_requirements = excluded.partial_requirements,
                    resume_evidence = excluded.resume_evidence,
                    improvement_suggestions = excluded.improvement_suggestions,
                    is_stale = 0,
                    updated_at = datetime('now')
                """,
                (
                    match.id,
                    match.job_id,
                    match.resume_version_id,
                    match.overall_score,
                    match.score_breakdown.model_dump_json(),
                    json.dumps(match.matched_requirements),
                    json.dumps(match.missing_requirements),
                    json.dumps(match.partial_requirements),
                    json.dumps(match.resume_evidence),
                    json.dumps(match.improvement_suggestions),
                    match.match_method,
                    1 if match.is_stale else 0,
                ),
            )
        return True

    def get_match_result(
        self,
        job_id: str,
        resume_version_id: str,
        match_method: str = "keyword",
    ) -> Optional[MatchResult]:
        """Retrieve existing match from database."""
        row = self.db.execute_one(
            """
            SELECT * FROM job_matches 
            WHERE job_id = ? AND resume_version_id = ? AND match_method = ?
            """,
            (job_id, resume_version_id, match_method),
        )
        if not row:
            return None

        breakdown_dict = json.loads(row["score_breakdown"]) if row["score_breakdown"] else {}
        return MatchResult(
            id=row["id"],
            job_id=row["job_id"],
            resume_version_id=row["resume_version_id"],
            overall_score=row["overall_score"],
            score_breakdown=MatchScoreBreakdown(**breakdown_dict),
            matched_requirements=json.loads(row["matched_requirements"]) if row["matched_requirements"] else [],
            missing_requirements=json.loads(row["missing_requirements"]) if row["missing_requirements"] else [],
            partial_requirements=json.loads(row["partial_requirements"]) if row["partial_requirements"] else [],
            resume_evidence=json.loads(row["resume_evidence"]) if row["resume_evidence"] else {},
            improvement_suggestions=json.loads(row["improvement_suggestions"]) if row["improvement_suggestions"] else [],
            match_method=row["match_method"],
            is_stale=bool(row["is_stale"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def invalidate_stale_matches(
        self,
        resume_version_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> int:
        """Mark cached match scores as stale when resume or job changes."""
        sql = "UPDATE job_matches SET is_stale = 1, updated_at = datetime('now') WHERE 1=1"
        params: List[Any] = []
        if resume_version_id:
            sql += " AND resume_version_id = ?"
            params.append(resume_version_id)
        if job_id:
            sql += " AND job_id = ?"
            params.append(job_id)

        with self.db.transaction() as conn:
            cursor = conn.execute(sql, tuple(params))
            return cursor.rowcount
