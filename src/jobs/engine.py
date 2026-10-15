"""Job Discovery Engine.

Orchestrates multi-source searches, isolates failures, deduplicates opportunities,
and records discovery run audits.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.database.connection import DatabaseConnection
from src.jobs.base import BaseJobSource
from src.jobs.plugins.iimjobs import IIMjobsSource
from src.jobs.plugins.indeed import IndeedJobSource
from src.jobs.plugins.linkedin import LinkedInJobSource
from src.jobs.plugins.naukri import NaukriJobSource
from src.tracker.models import JobPosting, JobSearchProfile
from src.tracker.repository import TrackerRepository
from src.utils.logger import get_logger

logger = get_logger("jobs.engine")


class DiscoveryResult(BaseModel):
    """Structured report of a discovery execution."""
    run_id: str
    status: str  # 'completed', 'failed', 'partial'
    started_at: str
    completed_at: str
    duration_seconds: float
    items_processed: int = 0
    items_added: int = 0
    items_updated: int = 0
    sources_attempted: List[str] = Field(default_factory=list)
    sources_succeeded: List[str] = Field(default_factory=list)
    sources_failed: List[str] = Field(default_factory=list)
    errors: Dict[str, str] = Field(default_factory=dict)


class JobDiscoveryEngine:
    """Coordinates automated multi-source job fetching."""

    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.tracker_repo = TrackerRepository(db)
        self.sources: Dict[str, BaseJobSource] = {
            "linkedin": LinkedInJobSource(),
            "iimjobs": IIMjobsSource(),
            "indeed": IndeedJobSource(),
            "naukri": NaukriJobSource(),
        }

    def register_source(self, source: BaseJobSource):
        """Register custom or mocked job source."""
        self.sources[source.name] = source

    def list_source_statuses(self) -> List[Dict[str, Any]]:
        """Return configured sources with enabled state and health metrics."""
        rows = self.db.execute("SELECT * FROM job_sources ORDER BY name ASC")
        return [dict(r) for r in rows]

    def toggle_source(self, source_id_or_type: str, is_enabled: bool) -> bool:
        """Enable or disable a specific job source."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE job_sources SET
                    is_enabled = ?,
                    updated_at = datetime('now')
                WHERE id = ? OR source_type = ?
                """,
                (1 if is_enabled else 0, source_id_or_type, source_id_or_type),
            )
            return cursor.rowcount > 0

    def run_discovery(
        self,
        profile_id: Optional[str] = None,
        source_types: Optional[List[str]] = None,
        limit_per_source: int = 15,
    ) -> DiscoveryResult:
        """Execute discovery across enabled sources using criteria from search profile."""
        run_id = str(uuid.uuid4())
        start_time = time.time()
        start_ts = time.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Fetch search profile
        profile = None
        if profile_id:
            profile = self.tracker_repo.get_profile(profile_id)
        if not profile:
            profile = self.tracker_repo.get_default_profile()
        if not profile:
            # Fallback default MBA profile
            profile = JobSearchProfile(
                name="MBA General Management",
                target_roles=["Product Manager", "Management Consultant", "Strategy Associate"],
                preferred_locations=["India", "Bangalore", "Mumbai", "Delhi NCR"],
            )

        # 2. Fetch enabled sources
        if source_types:
            enabled_types = source_types
        else:
            src_rows = self.db.execute(
                "SELECT source_type FROM job_sources WHERE is_enabled = 1 AND source_type != 'manual'"
            )
            enabled_types = [r["source_type"] for r in src_rows]
            if not enabled_types:
                enabled_types = [k for k in self.sources.keys() if k != 'manual']

        # 3. Log run in automation_runs
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO automation_runs (
                    id, task_type, task_config, status, started_at
                ) VALUES (?, 'job_discovery', ?, 'running', datetime('now'))
                """,
                (run_id, json.dumps({"profile_id": profile.id, "sources": enabled_types})),
            )

        items_processed = 0
        items_added = 0
        items_updated = 0
        sources_attempted = []
        sources_succeeded = []
        sources_failed = []
        errors = {}

        # 4. Execute queries
        target_roles = profile.target_roles or ["Product Manager"]
        primary_location = profile.preferred_locations[0] if profile.preferred_locations else "India"

        for src_name in enabled_types:
            plugin = self.sources.get(src_name)
            if not plugin:
                continue

            sources_attempted.append(src_name)
            source_has_error = False

            for role in target_roles[:3]:  # Top 3 target roles to stay within rate limits
                try:
                    logger.info("[%s] Searching for '%s' in '%s'", src_name, role, primary_location)
                    found_jobs = plugin.search(role, location=primary_location, limit=limit_per_source)
                    items_processed += len(found_jobs)

                    for job in found_jobs:
                        _, is_new = self.tracker_repo.add_or_update_job(job)
                        if is_new:
                            items_added += 1
                        else:
                            items_updated += 1

                except Exception as e:
                    source_has_error = True
                    err_msg = str(e)
                    errors[f"{src_name}:{role}"] = err_msg
                    logger.error("[%s] Search failed for '%s': %s", src_name, role, err_msg)

            # Update job_sources status
            with self.db.transaction() as conn:
                if source_has_error:
                    sources_failed.append(src_name)
                    conn.execute(
                        """
                        UPDATE job_sources SET
                            last_error = ?,
                            last_error_time = datetime('now'),
                            updated_at = datetime('now')
                        WHERE source_type = ?
                        """,
                        (errors.get(src_name, "Error during discovery"), src_name),
                    )
                else:
                    sources_succeeded.append(src_name)
                    conn.execute(
                        """
                        UPDATE job_sources SET
                            last_successful_run = datetime('now'),
                            last_error = NULL,
                            updated_at = datetime('now')
                        WHERE source_type = ?
                        """,
                        (src_name,),
                    )

        duration = time.time() - start_time
        completed_ts = time.strftime("%Y-%m-%d %H:%M:%S")
        status = "failed" if (sources_failed and not sources_succeeded) else "completed"

        summary = json.dumps({
            "processed": items_processed,
            "added": items_added,
            "updated": items_updated,
            "succeeded": sources_succeeded,
            "failed": sources_failed,
        })

        # 5. Complete automation_runs
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE automation_runs SET
                    status = ?,
                    completed_at = datetime('now'),
                    result_summary = ?,
                    error_message = ?,
                    items_processed = ?,
                    items_added = ?,
                    items_updated = ?
                WHERE id = ?
                """,
                (
                    status,
                    summary,
                    json.dumps(errors) if errors else None,
                    items_processed,
                    items_added,
                    items_updated,
                    run_id,
                ),
            )

        logger.info(
            "Discovery completed in %.2fs: %d processed, %d added, %d updated",
            duration, items_processed, items_added, items_updated
        )

        return DiscoveryResult(
            run_id=run_id,
            status=status,
            started_at=start_ts,
            completed_at=completed_ts,
            duration_seconds=round(duration, 2),
            items_processed=items_processed,
            items_added=items_added,
            items_updated=items_updated,
            sources_attempted=sources_attempted,
            sources_succeeded=sources_succeeded,
            sources_failed=sources_failed,
            errors=errors,
        )
