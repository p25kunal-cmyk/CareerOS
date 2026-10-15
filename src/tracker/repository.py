"""Database repository for Job Tracking, Search Profiles, and Application Funnel.

Provides transactional deduplication, pipeline audits, and status progression.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.database.connection import DatabaseConnection
from src.tracker.models import (
    ApplicationEvent,
    ApplicationRecord,
    ApplicationWithJob,
    JobPosting,
    JobSearchProfile,
)
from src.utils.logger import get_logger

logger = get_logger("tracker.repository")


class TrackerRepository:
    """Data access layer for jobs, search profiles, and application funnel."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ── Job Management & Deduplication ────────────────────────────

    def add_or_update_job(self, job: JobPosting) -> Tuple[str, bool]:
        """Insert or update a job posting with deduplication.

        Returns (job_id, is_new).
        """
        req_skills_json = json.dumps(job.required_skills)
        pref_skills_json = json.dumps(job.preferred_skills)

        # 1. Check duplicate by URL
        existing = None
        if job.original_url:
            existing = self.db.execute_one(
                "SELECT id FROM jobs WHERE original_url = ?", (job.original_url,)
            )

        # 2. Check duplicate by title + company + location
        if not existing and job.title and job.company:
            existing = self.db.execute_one(
                """
                SELECT id FROM jobs 
                WHERE LOWER(TRIM(title)) = LOWER(TRIM(?)) 
                  AND LOWER(TRIM(company)) = LOWER(TRIM(?))
                  AND (location IS NULL OR LOWER(TRIM(location)) = LOWER(TRIM(?)) OR ? = 'Any')
                """,
                (job.title, job.company, job.location or "", job.location or "Any"),
            )

        with self.db.transaction() as conn:
            if existing:
                job_id = existing["id"]
                conn.execute(
                    """
                    UPDATE jobs SET
                        last_seen = datetime('now'),
                        description = COALESCE(NULLIF(?, ''), description),
                        salary_min = COALESCE(?, salary_min),
                        salary_max = COALESCE(?, salary_max),
                        required_skills = ?,
                        preferred_skills = ?,
                        status = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        job.description,
                        job.salary_min,
                        job.salary_max,
                        req_skills_json,
                        pref_skills_json,
                        job.status,
                        job_id,
                    ),
                )
                logger.info("Updated existing job %s ('%s' at %s)", job_id, job.title, job.company)
                return job_id, False
            else:
                job_id = job.id or str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO jobs (
                        id, title, company, location, employment_type,
                        experience_min, experience_max, salary_min, salary_max,
                        salary_currency, date_posted, description, required_skills,
                        preferred_skills, source_portal, original_url, application_url,
                        status, is_manually_entered, first_discovered, last_seen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (
                        job_id,
                        job.title,
                        job.company,
                        job.location,
                        job.employment_type,
                        job.experience_min,
                        job.experience_max,
                        job.salary_min,
                        job.salary_max,
                        job.salary_currency,
                        job.date_posted,
                        job.description,
                        req_skills_json,
                        pref_skills_json,
                        job.source_portal,
                        job.original_url,
                        job.application_url,
                        job.status,
                        1 if job.is_manually_entered else 0,
                    ),
                )
                logger.info("Inserted new job %s ('%s' at %s)", job_id, job.title, job.company)
                return job_id, True

    def get_job(self, job_id: str) -> Optional[JobPosting]:
        """Fetch job posting by ID."""
        row = self.db.execute_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not row:
            return None
        return self._row_to_job(row)

    def list_jobs(
        self,
        filter_status: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
    ) -> List[JobPosting]:
        """List jobs matching optional status or text search query."""
        sql = "SELECT * FROM jobs WHERE 1=1"
        params: List[Any] = []

        if filter_status:
            sql += " AND status = ?"
            params.append(filter_status)

        if query:
            sql += " AND (LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(location) LIKE ?)"
            term = f"%{query.lower().strip()}%"
            params.extend([term, term, term])

        sql += " ORDER BY first_discovered DESC LIMIT ?"
        params.append(limit)

        rows = self.db.execute(sql, tuple(params))
        return [self._row_to_job(r) for r in rows]

    def delete_job(self, job_id: str) -> bool:
        """Delete job posting and cascade to matches and applications."""
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0

    def _row_to_job(self, r: Any) -> JobPosting:
        """Convert database Row to JobPosting model."""
        req_skills = json.loads(r["required_skills"]) if r["required_skills"] else []
        pref_skills = json.loads(r["preferred_skills"]) if r["preferred_skills"] else []
        return JobPosting(
            id=r["id"],
            title=r["title"],
            company=r["company"],
            location=r["location"],
            employment_type=r["employment_type"],
            experience_min=r["experience_min"],
            experience_max=r["experience_max"],
            salary_min=r["salary_min"],
            salary_max=r["salary_max"],
            salary_currency=r["salary_currency"] or "INR",
            date_posted=r["date_posted"],
            description=r["description"] or "",
            required_skills=req_skills,
            preferred_skills=pref_skills,
            source_portal=r["source_portal"] or "manual",
            original_url=r["original_url"],
            application_url=r["application_url"],
            status=r["status"] or "active",
            is_manually_entered=bool(r["is_manually_entered"]),
            first_discovered=r["first_discovered"],
            last_seen=r["last_seen"],
        )

    # ── Search Profiles ───────────────────────────────────────────

    def create_profile(self, profile: JobSearchProfile) -> str:
        """Create a new job search profile."""
        prof_id = profile.id or str(uuid.uuid4())
        with self.db.transaction() as conn:
            if profile.is_default:
                conn.execute("UPDATE job_search_profiles SET is_default = 0")

            conn.execute(
                """
                INSERT INTO job_search_profiles (
                    id, name, is_default, target_roles, preferred_industries,
                    preferred_locations, remote_preference, experience_level,
                    employment_type, min_salary, salary_currency, required_keywords,
                    excluded_keywords, companies_of_interest, max_job_age_days
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prof_id,
                    profile.name,
                    1 if profile.is_default else 0,
                    json.dumps(profile.target_roles),
                    json.dumps(profile.preferred_industries),
                    json.dumps(profile.preferred_locations),
                    profile.remote_preference,
                    profile.experience_level,
                    profile.employment_type,
                    profile.min_salary,
                    profile.salary_currency,
                    json.dumps(profile.required_keywords),
                    json.dumps(profile.excluded_keywords),
                    json.dumps(profile.companies_of_interest),
                    profile.max_job_age_days,
                ),
            )
        return prof_id

    def get_profile(self, profile_id: str) -> Optional[JobSearchProfile]:
        """Fetch search profile by ID."""
        row = self.db.execute_one("SELECT * FROM job_search_profiles WHERE id = ?", (profile_id,))
        return self._row_to_profile(row) if row else None

    def get_default_profile(self) -> Optional[JobSearchProfile]:
        """Fetch the default search profile."""
        row = self.db.execute_one("SELECT * FROM job_search_profiles WHERE is_default = 1 LIMIT 1")
        return self._row_to_profile(row) if row else None

    def list_profiles(self) -> List[JobSearchProfile]:
        """List all configured search profiles."""
        rows = self.db.execute("SELECT * FROM job_search_profiles ORDER BY is_default DESC, created_at DESC")
        return [self._row_to_profile(r) for r in rows]

    def set_default_profile(self, profile_id: str) -> bool:
        """Set a profile as the default."""
        with self.db.transaction() as conn:
            conn.execute("UPDATE job_search_profiles SET is_default = 0")
            cursor = conn.execute("UPDATE job_search_profiles SET is_default = 1 WHERE id = ?", (profile_id,))
            return cursor.rowcount > 0

    def update_profile(self, profile: JobSearchProfile) -> bool:
        """Update an existing search profile."""
        with self.db.transaction() as conn:
            if profile.is_default:
                conn.execute("UPDATE job_search_profiles SET is_default = 0 WHERE id != ?", (profile.id,))

            cursor = conn.execute(
                """
                UPDATE job_search_profiles SET
                    name = ?,
                    is_default = ?,
                    target_roles = ?,
                    preferred_industries = ?,
                    preferred_locations = ?,
                    remote_preference = ?,
                    experience_level = ?,
                    employment_type = ?,
                    min_salary = ?,
                    salary_currency = ?,
                    required_keywords = ?,
                    excluded_keywords = ?,
                    companies_of_interest = ?,
                    max_job_age_days = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    profile.name,
                    1 if profile.is_default else 0,
                    json.dumps(profile.target_roles),
                    json.dumps(profile.preferred_industries),
                    json.dumps(profile.preferred_locations),
                    profile.remote_preference,
                    profile.experience_level,
                    profile.employment_type,
                    profile.min_salary,
                    profile.salary_currency,
                    json.dumps(profile.required_keywords),
                    json.dumps(profile.excluded_keywords),
                    json.dumps(profile.companies_of_interest),
                    profile.max_job_age_days,
                    profile.id,
                ),
            )
            return cursor.rowcount > 0

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a search profile."""
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM job_search_profiles WHERE id = ?", (profile_id,))
            return cursor.rowcount > 0

    def _row_to_profile(self, r: Any) -> JobSearchProfile:
        """Convert Row to JobSearchProfile."""
        return JobSearchProfile(
            id=r["id"],
            name=r["name"],
            is_default=bool(r["is_default"]),
            target_roles=json.loads(r["target_roles"]) if r["target_roles"] else [],
            preferred_industries=json.loads(r["preferred_industries"]) if r["preferred_industries"] else [],
            preferred_locations=json.loads(r["preferred_locations"]) if r["preferred_locations"] else [],
            remote_preference=r["remote_preference"] or "any",
            experience_level=r["experience_level"],
            employment_type=r["employment_type"],
            min_salary=r["min_salary"],
            salary_currency=r["salary_currency"] or "INR",
            required_keywords=json.loads(r["required_keywords"]) if r["required_keywords"] else [],
            excluded_keywords=json.loads(r["excluded_keywords"]) if r["excluded_keywords"] else [],
            companies_of_interest=json.loads(r["companies_of_interest"]) if r["companies_of_interest"] else [],
            max_job_age_days=r["max_job_age_days"] or 30,
        )

    # ── Application Funnel & Lifecycle ────────────────────────────

    def create_application(
        self,
        job_id: str,
        resume_version_id: Optional[str] = None,
        status: str = "saved",
        application_date: Optional[str] = None,
        follow_up_date: Optional[str] = None,
        notes: Optional[str] = None,
        recruiter_name: Optional[str] = None,
        recruiter_email: Optional[str] = None,
        recruiter_phone: Optional[str] = None,
    ) -> str:
        """Create a new job application record and log initial event."""
        app_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO application_records (
                    id, job_id, resume_version_id, status, application_date,
                    follow_up_date, notes, recruiter_name, recruiter_email,
                    recruiter_phone, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    app_id,
                    job_id,
                    resume_version_id,
                    status,
                    application_date,
                    follow_up_date,
                    notes,
                    recruiter_name,
                    recruiter_email,
                    recruiter_phone,
                ),
            )

            # Audit event
            conn.execute(
                """
                INSERT INTO application_events (
                    id, application_id, event_type, old_status, new_status,
                    description, event_date, created_at
                ) VALUES (?, ?, 'status_change', NULL, ?, ?, datetime('now'), datetime('now'))
                """,
                (event_id, app_id, status, f"Application created with initial status '{status}'"),
            )

        logger.info("Created application %s for job %s with status '%s'", app_id, job_id, status)
        return app_id

    def get_application(self, app_id: str) -> Optional[ApplicationRecord]:
        """Fetch application record by ID."""
        row = self.db.execute_one("SELECT * FROM application_records WHERE id = ?", (app_id,))
        if not row:
            return None
        return ApplicationRecord(
            id=row["id"],
            job_id=row["job_id"],
            resume_version_id=row["resume_version_id"],
            status=row["status"],
            application_date=row["application_date"],
            follow_up_date=row["follow_up_date"],
            notes=row["notes"] or "",
            recruiter_name=row["recruiter_name"],
            recruiter_email=row["recruiter_email"],
            recruiter_phone=row["recruiter_phone"],
            interview_stages=row["interview_stages"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update_status(
        self,
        app_id: str,
        new_status: str,
        note: Optional[str] = None,
    ) -> bool:
        """Advance or change application stage with audit event."""
        current = self.get_application(app_id)
        if not current:
            return False

        old_status = current.status
        event_id = str(uuid.uuid4())
        desc = note or f"Status updated from '{old_status}' to '{new_status}'"

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE application_records SET
                    status = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (new_status, app_id),
            )

            conn.execute(
                """
                INSERT INTO application_events (
                    id, application_id, event_type, old_status, new_status,
                    description, event_date, created_at
                ) VALUES (?, ?, 'status_change', ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (event_id, app_id, old_status, new_status, desc),
            )

        logger.info("Application %s transitioned from '%s' to '%s'", app_id, old_status, new_status)
        return cursor.rowcount > 0

    def add_event(
        self,
        application_id: str,
        event_type: str,
        description: str,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
    ) -> str:
        """Append an event to the application timeline."""
        event_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO application_events (
                    id, application_id, event_type, old_status, new_status,
                    description, event_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (event_id, application_id, event_type, old_status, new_status, description),
            )
        return event_id

    def list_applications(
        self,
        status_filter: Optional[str] = None,
    ) -> List[ApplicationWithJob]:
        """Fetch applications joined with job details and version name."""
        sql = """
            SELECT 
                a.*,
                j.title as job_title, j.company as job_company, j.location as job_location,
                j.employment_type as job_employment_type, j.salary_min as job_salary_min,
                j.salary_max as job_salary_max, j.salary_currency as job_salary_currency,
                j.source_portal as job_source_portal, j.description as job_description,
                j.required_skills as job_required_skills, j.preferred_skills as job_preferred_skills,
                j.original_url as job_original_url, j.application_url as job_application_url,
                j.status as job_status, j.is_manually_entered as job_is_manual,
                v.version_name as resume_version_name,
                (SELECT COUNT(*) FROM application_events WHERE application_id = a.id) as events_count
            FROM application_records a
            JOIN jobs j ON a.job_id = j.id
            LEFT JOIN resume_versions v ON a.resume_version_id = v.id
            WHERE 1=1
        """
        params: List[Any] = []
        if status_filter:
            sql += " AND a.status = ?"
            params.append(status_filter)

        sql += " ORDER BY a.updated_at DESC"

        rows = self.db.execute(sql, tuple(params))
        results: List[ApplicationWithJob] = []

        for r in rows:
            app = ApplicationRecord(
                id=r["id"],
                job_id=r["job_id"],
                resume_version_id=r["resume_version_id"],
                status=r["status"],
                application_date=r["application_date"],
                follow_up_date=r["follow_up_date"],
                notes=r["notes"] or "",
                recruiter_name=r["recruiter_name"],
                recruiter_email=r["recruiter_email"],
                recruiter_phone=r["recruiter_phone"],
                interview_stages=r["interview_stages"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )

            job = JobPosting(
                id=r["job_id"],
                title=r["job_title"],
                company=r["job_company"],
                location=r["job_location"],
                employment_type=r["job_employment_type"],
                salary_min=r["job_salary_min"],
                salary_max=r["job_salary_max"],
                salary_currency=r["job_salary_currency"] or "INR",
                description=r["job_description"] or "",
                required_skills=json.loads(r["job_required_skills"]) if r["job_required_skills"] else [],
                preferred_skills=json.loads(r["job_preferred_skills"]) if r["job_preferred_skills"] else [],
                source_portal=r["job_source_portal"] or "manual",
                original_url=r["job_original_url"],
                application_url=r["job_application_url"],
                status=r["job_status"] or "active",
                is_manually_entered=bool(r["job_is_manual"]),
            )

            results.append(ApplicationWithJob(
                application=app,
                job=job,
                resume_version_name=r["resume_version_name"],
                events_count=r["events_count"] or 0,
            ))

        return results

    def get_timeline(self, app_id: str) -> List[ApplicationEvent]:
        """Fetch chronological event history for an application."""
        rows = self.db.execute(
            """
            SELECT * FROM application_events
            WHERE application_id = ?
            ORDER BY event_date ASC, created_at ASC
            """,
            (app_id,),
        )
        return [
            ApplicationEvent(
                id=r["id"],
                application_id=r["application_id"],
                event_type=r["event_type"],
                old_status=r["old_status"],
                new_status=r["new_status"],
                description=r["description"] or "",
                event_date=r["event_date"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_pipeline_stats(self) -> Dict[str, int]:
        """Return counts by stage for Kanban summary."""
        stages = [
            "saved", "shortlisted", "resume_prepared", "applied",
            "assessment", "interview", "offer", "rejected", "withdrawn"
        ]
        counts = {s: 0 for s in stages}

        rows = self.db.execute(
            "SELECT status, COUNT(*) as cnt FROM application_records GROUP BY status"
        )
        for r in rows:
            if r["status"] in counts:
                counts[r["status"]] = r["cnt"]

        return counts

    def delete_application(self, app_id: str) -> bool:
        """Delete application record and cascade to events."""
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM application_records WHERE id = ?", (app_id,))
            return cursor.rowcount > 0
