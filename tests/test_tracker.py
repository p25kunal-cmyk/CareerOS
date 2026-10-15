"""Unit and integration tests for Job Tracking, Search Profiles, and Application Funnel."""

import pytest
from src.tracker.models import JobPosting, JobSearchProfile
from src.tracker.repository import TrackerRepository


def test_job_deduplication(db):
    """Test job insertion and deduplication via URL and title+company."""
    repo = TrackerRepository(db)

    job1 = JobPosting(
        title="Associate Product Manager",
        company="Swiggy",
        location="Bangalore",
        original_url="https://swiggy.com/careers/apm-101",
        description="Initial description",
        required_skills=["SQL", "Analytics"],
    )

    job_id1, is_new1 = repo.add_or_update_job(job1)
    assert is_new1 is True
    assert job_id1 is not None

    # Deduplicate via identical original_url
    job2 = JobPosting(
        title="APM - Core",
        company="Swiggy",
        original_url="https://swiggy.com/careers/apm-101",
        description="Updated description with more details",
        required_skills=["SQL", "Analytics", "A/B Testing"],
    )
    job_id2, is_new2 = repo.add_or_update_job(job2)
    assert is_new2 is False
    assert job_id2 == job_id1

    # Verify updated description
    saved_job = repo.get_job(job_id1)
    assert "Updated description" in saved_job.description
    assert "A/B Testing" in saved_job.required_skills

    # Deduplicate via title + company
    job3 = JobPosting(
        title="Management Consultant",
        company="McKinsey & Company",
        location="Mumbai",
    )
    id3, is_new3 = repo.add_or_update_job(job3)
    assert is_new3 is True

    job4 = JobPosting(
        title="management consultant",  # case-insensitive check
        company="mckinsey & company",
        location="Mumbai",
    )
    id4, is_new4 = repo.add_or_update_job(job4)
    assert is_new4 is False
    assert id4 == id3


def test_job_search_and_filter(db):
    """Test filtering jobs by query and status."""
    repo = TrackerRepository(db)

    repo.add_or_update_job(JobPosting(title="Strategy Lead", company="Tata Sons", location="Mumbai"))
    repo.add_or_update_job(JobPosting(title="Investment Banking Analyst", company="Goldman Sachs", location="Bangalore"))
    repo.add_or_update_job(JobPosting(title="Brand Manager", company="HUL", location="Mumbai"))

    mumbai_jobs = repo.list_jobs(query="Mumbai")
    assert len(mumbai_jobs) == 2

    goldman_jobs = repo.list_jobs(query="Goldman")
    assert len(goldman_jobs) == 1
    assert goldman_jobs[0].company == "Goldman Sachs"


def test_search_profile_crud(db):
    """Test creating, listing, setting default, and deleting search profiles."""
    repo = TrackerRepository(db)

    prof1 = JobSearchProfile(
        name="Consulting Focus",
        is_default=True,
        target_roles=["Management Consultant", "Strategy Associate"],
        preferred_locations=["Mumbai", "Delhi NCR"],
        min_salary=2500000.0,
    )
    p1_id = repo.create_profile(prof1)

    prof2 = JobSearchProfile(
        name="Product Focus",
        is_default=False,
        target_roles=["Product Manager"],
        min_salary=2200000.0,
    )
    p2_id = repo.create_profile(prof2)

    profiles = repo.list_profiles()
    assert len(profiles) >= 2

    # Verify default profile
    default_p = repo.get_default_profile()
    assert default_p is not None
    assert default_p.name == "Consulting Focus"

    # Toggle default
    repo.set_default_profile(p2_id)
    new_default = repo.get_default_profile()
    assert new_default.id == p2_id
    assert new_default.name == "Product Focus"


def test_application_lifecycle_and_audit_timeline(db):
    """Test application creation, stage advancement, and event timeline."""
    repo = TrackerRepository(db)

    job_id, _ = repo.add_or_update_job(JobPosting(title="Program Manager", company="Microsoft", location="Hyderabad"))

    # 1. Create application in 'saved' stage
    app_id = repo.create_application(job_id=job_id, status="saved", notes="Referral through alumni")
    assert app_id is not None

    app = repo.get_application(app_id)
    assert app.status == "saved"

    # 2. Advance stage to 'applied'
    repo.update_status(app_id, "applied", note="Submitted resume v1.0 on career portal")
    app_applied = repo.get_application(app_id)
    assert app_applied.status == "applied"

    # 3. Advance stage to 'interview'
    repo.update_status(app_id, "interview", note="Received invite for Round 1 Case Interview")
    app_interview = repo.get_application(app_id)
    assert app_interview.status == "interview"

    # 4. Add custom milestone event
    repo.add_event(app_id, "interview", "Cleared Round 1 Case Interview with Partner")

    # 5. Check timeline audit trail
    timeline = repo.get_timeline(app_id)
    assert len(timeline) >= 4  # Initial creation + 2 status changes + 1 milestone
    assert timeline[0].event_type == "status_change"
    assert any("Round 1 Case Interview" in ev.description for ev in timeline)

    # 6. Pipeline stats
    stats = repo.get_pipeline_stats()
    assert stats["interview"] >= 1

    # 7. List joined applications
    joined_apps = repo.list_applications()
    match = next(a for a in joined_apps if a.application.id == app_id)
    assert match.job.title == "Program Manager"
    assert match.job.company == "Microsoft"
    assert match.events_count >= 4
