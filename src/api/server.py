"""CareerOS Local REST API Server.

Provides endpoints for the Chrome extension to interact with CareerOS.
Binds to 127.0.0.1 only — never exposed to the network.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import require_auth, get_or_create_token
from src.api.schemas import (
    HealthResponse,
    QuickJobCreate,
    JobResponse,
    JobListResponse,
    ApplicationStatusUpdate,
    ApplicationResponse,
    ApplicationListResponse,
    ResumeListItem,
    ResumeListResponse,
    PipelineStatsResponse,
    QuickMatchRequest,
    QuickMatchResponse,
    ErrorResponse,
)
from src.database.connection import DatabaseConnection, init_db
from src.database.migrations import run_migrations, seed_default_templates
from src.tracker.models import JobPosting, ApplicationRecord
from src.tracker.repository import TrackerRepository
from src.resume.repository import ResumeRepository
from src.matching.engine import MatchingEngine
from src.utils.logger import get_logger, setup_logging
from config.settings import settings

logger = get_logger("api.server")

# ── App startup timestamp ─────────────────────────────────────
_start_time = time.time()


def create_app(db: Optional[DatabaseConnection] = None) -> FastAPI:
    """Factory function to create the FastAPI application.

    Accepts an optional DatabaseConnection for testing.
    """
    if db is None:
        setup_logging(settings.logging.level, settings.logging.log_file)
        db = init_db(settings.database.path)
        run_migrations(db)
        seed_default_templates(db)

    app = FastAPI(
        title="CareerOS Local API",
        description="Local-only REST API for Chrome extension integration",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # CORS — allow Chrome extension origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "chrome-extension://*",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Shared repositories ───────────────────────────────────
    tracker_repo = TrackerRepository(db)
    resume_repo = ResumeRepository(db)
    matching_engine = MatchingEngine(db)

    # ══════════════════════════════════════════════════════════
    # ENDPOINTS
    # ══════════════════════════════════════════════════════════

    @app.get("/api/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        """Public health check — no auth required."""
        return HealthResponse(
            status="ok",
            version="0.1.0",
            uptime_seconds=round(time.time() - _start_time, 1),
        )

    # ── Jobs ──────────────────────────────────────────────────

    @app.post(
        "/api/jobs",
        response_model=JobResponse,
        tags=["Jobs"],
        responses={401: {"model": ErrorResponse}},
    )
    async def create_job(
        payload: QuickJobCreate,
        _token: str = Depends(require_auth),
    ):
        """Save a job from the Chrome extension.

        Performs deduplication by title+company before inserting.
        """
        # Check for duplicates
        existing = db.execute(
            "SELECT id FROM jobs WHERE LOWER(title) = LOWER(?) AND LOWER(company) = LOWER(?)",
            (payload.title, payload.company),
        )
        if existing:
            row = existing[0]
            return JobResponse(
                id=row["id"],
                title=payload.title,
                company=payload.company,
                location=payload.location,
                employment_type=payload.employment_type,
                status="active",
                source_portal=payload.source_portal,
                original_url=payload.original_url,
                created=False,
            )

        job = JobPosting(
            title=payload.title,
            company=payload.company,
            location=payload.location or "Any",
            employment_type=payload.employment_type or "Full-time",
            experience_min=payload.experience_min or 0,
            experience_max=payload.experience_max,
            salary_min=payload.salary_min,
            salary_max=payload.salary_max,
            salary_currency=payload.salary_currency,
            description=payload.description or "",
            required_skills=payload.required_skills,
            preferred_skills=payload.preferred_skills,
            source_portal=payload.source_portal,
            original_url=payload.original_url,
            application_url=payload.application_url,
            is_manually_entered=False,
        )

        job_id, is_new = tracker_repo.add_or_update_job(job)
        logger.info("Job saved via API: %s at %s (id=%s)", job.title, job.company, job_id)

        return JobResponse(
            id=job_id,
            title=job.title,
            company=job.company,
            location=job.location,
            employment_type=job.employment_type,
            status="active",
            source_portal=job.source_portal,
            original_url=job.original_url,
            created=is_new,
        )

    @app.get(
        "/api/jobs",
        response_model=JobListResponse,
        tags=["Jobs"],
    )
    async def list_jobs(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        status: Optional[str] = None,
        _token: str = Depends(require_auth),
    ):
        """List saved jobs with pagination."""
        sql = "SELECT * FROM jobs WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY first_discovered DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = db.execute(sql, tuple(params))
        total_row = db.execute_one(
            "SELECT COUNT(*) as cnt FROM jobs" + (" WHERE status = ?" if status else ""),
            (status,) if status else (),
        )
        total = total_row["cnt"] if total_row else 0

        jobs = [
            JobResponse(
                id=r["id"],
                title=r["title"],
                company=r["company"],
                location=r["location"],
                employment_type=r["employment_type"],
                status=r["status"],
                source_portal=r["source_portal"],
                original_url=r["original_url"],
            )
            for r in rows
        ]
        return JobListResponse(jobs=jobs, total=total)

    @app.get(
        "/api/jobs/{job_id}",
        response_model=JobResponse,
        tags=["Jobs"],
    )
    async def get_job(
        job_id: str,
        _token: str = Depends(require_auth),
    ):
        """Get a single job by ID."""
        row = db.execute_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")

        return JobResponse(
            id=row["id"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            employment_type=row["employment_type"],
            status=row["status"],
            source_portal=row["source_portal"],
            original_url=row["original_url"],
        )

    # ── Applications ──────────────────────────────────────────

    @app.post(
        "/api/jobs/{job_id}/apply",
        response_model=ApplicationResponse,
        tags=["Applications"],
    )
    async def create_application(
        job_id: str,
        _token: str = Depends(require_auth),
    ):
        """Create a new application record for a job (initial status: saved)."""
        job_row = db.execute_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check for existing application
        existing = db.execute_one(
            "SELECT id FROM application_records WHERE job_id = ?", (job_id,)
        )
        if existing:
            app = tracker_repo.get_application(existing["id"])
            return ApplicationResponse(
                id=app.id,
                job_id=app.job_id,
                status=app.status,
                job_title=job_row["title"],
                company=job_row["company"],
                application_date=app.application_date,
                updated_at=app.updated_at,
            )

        app_id = tracker_repo.create_application(job_id=job_id)
        app = tracker_repo.get_application(app_id)
        return ApplicationResponse(
            id=app.id,
            job_id=app.job_id,
            status=app.status,
            job_title=job_row["title"],
            company=job_row["company"],
            application_date=app.application_date,
            updated_at=app.updated_at,
        )

    @app.put(
        "/api/applications/{app_id}/status",
        response_model=ApplicationResponse,
        tags=["Applications"],
    )
    async def update_application_status(
        app_id: str,
        payload: ApplicationStatusUpdate,
        _token: str = Depends(require_auth),
    ):
        """Update an application's pipeline status."""
        app = tracker_repo.get_application(app_id)
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        tracker_repo.update_status(app_id, payload.status, payload.note)
        updated = tracker_repo.get_application(app_id)
        job_row = db.execute_one("SELECT title, company FROM jobs WHERE id = ?", (updated.job_id,))

        return ApplicationResponse(
            id=updated.id,
            job_id=updated.job_id,
            status=updated.status,
            job_title=job_row["title"] if job_row else "Unknown",
            company=job_row["company"] if job_row else "Unknown",
            application_date=updated.application_date,
            updated_at=updated.updated_at,
        )

    @app.get(
        "/api/applications",
        response_model=ApplicationListResponse,
        tags=["Applications"],
    )
    async def list_applications(
        status: Optional[str] = None,
        _token: str = Depends(require_auth),
    ):
        """List all applications with optional status filter."""
        records = tracker_repo.list_applications(status_filter=status)
        apps = [
            ApplicationResponse(
                id=r.application.id,
                job_id=r.application.job_id,
                status=r.application.status,
                job_title=r.job.title,
                company=r.job.company,
                application_date=r.application.application_date,
                updated_at=r.application.updated_at,
            )
            for r in records
        ]
        return ApplicationListResponse(applications=apps, total=len(apps))

    # ── Resumes ───────────────────────────────────────────────

    @app.get(
        "/api/resumes",
        response_model=ResumeListResponse,
        tags=["Resumes"],
    )
    async def list_resumes(
        _token: str = Depends(require_auth),
    ):
        """List all resumes with version counts."""
        summaries = resume_repo.list_resumes()
        items = [
            ResumeListItem(
                id=s.id,
                name=s.name,
                is_master=s.is_master,
                version_count=s.version_count,
                updated_at=s.updated_at,
            )
            for s in summaries
        ]
        return ResumeListResponse(resumes=items, total=len(items))

    # ── Pipeline Stats ────────────────────────────────────────

    @app.get(
        "/api/pipeline/stats",
        response_model=PipelineStatsResponse,
        tags=["Pipeline"],
    )
    async def pipeline_stats(
        _token: str = Depends(require_auth),
    ):
        """Get application pipeline stage counts for dashboard widget."""
        stats = tracker_repo.get_pipeline_stats()
        total = sum(stats.values())
        return PipelineStatsResponse(stages=stats, total_applications=total)

    # ── Quick Match ───────────────────────────────────────────

    @app.post(
        "/api/match",
        response_model=QuickMatchResponse,
        tags=["Matching"],
    )
    async def quick_match(
        payload: QuickMatchRequest,
        _token: str = Depends(require_auth),
    ):
        """Run a quick keyword match between a job and resume."""
        # Get job
        job_row = db.execute_one("SELECT * FROM jobs WHERE id = ?", (payload.job_id,))
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")

        job = JobPosting(
            id=job_row["id"],
            title=job_row["title"],
            company=job_row["company"],
            location=job_row["location"],
            employment_type=job_row["employment_type"],
            description=job_row["description"] or "",
            required_skills=json.loads(job_row["required_skills"]) if job_row["required_skills"] else [],
            preferred_skills=json.loads(job_row["preferred_skills"]) if job_row["preferred_skills"] else [],
        )

        # Get resume (master or specified)
        if payload.resume_id:
            resume_row = db.execute_one(
                "SELECT id FROM resumes WHERE id = ?", (payload.resume_id,)
            )
        else:
            resume_row = db.execute_one(
                "SELECT id FROM resumes WHERE is_master = 1"
            )

        if not resume_row:
            raise HTTPException(status_code=404, detail="No resume found")

        # Get latest version
        version_row = db.execute_one(
            "SELECT id FROM resume_versions WHERE resume_id = ? ORDER BY version_number DESC LIMIT 1",
            (resume_row["id"],),
        )
        if not version_row:
            raise HTTPException(status_code=404, detail="No resume version found")

        version = resume_repo.get_version(version_row["id"])
        if not version:
            raise HTTPException(status_code=404, detail="Resume version data not found")

        result = matching_engine.calculate_match(version, job)

        return QuickMatchResponse(
            overall_score=result.overall_score,
            matched_skills=result.matched_requirements,
            missing_skills=result.missing_requirements,
            suggestions=result.improvement_suggestions,
        )

    # ── API Token Info ────────────────────────────────────────

    @app.get("/api/token", tags=["System"])
    async def get_token_info():
        """Get the API token for extension configuration.

        This endpoint is accessible without auth (localhost only)
        so the extension popup can auto-configure.
        """
        token = get_or_create_token()
        return {"token": token, "port": settings.api.port}

    return app


# ── Standalone entry point ────────────────────────────────────

def run_server():
    """Run the API server directly (for development/testing)."""
    import uvicorn

    app = create_app()
    logger.info(
        "Starting CareerOS API on http://%s:%d",
        settings.api.host,
        settings.api.port,
    )
    uvicorn.run(
        app,
        host=settings.api.host,
        port=settings.api.port,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
