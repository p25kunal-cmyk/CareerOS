"""Unit and integration tests for Matching Engine, Gap Analysis, and Evidence Attribution."""

import pytest
from src.matching.engine import MatchingEngine
from src.matching.models import MatchResult
from src.resume.models import BulletItem, ResumeVersionData, SectionItem
from src.resume.repository import ResumeRepository
from src.tracker.models import JobPosting
from src.tracker.repository import TrackerRepository


@pytest.fixture
def candidate_resume(db):
    """Provides a persisted MBA candidate resume version."""
    repo = ResumeRepository(db)
    r_id = repo.create_resume(name="MBA Master Test", is_master=True)

    sec_edu = SectionItem(
        section_type="education",
        title="Education",
        bullets=[BulletItem(content="MBA | IIM Nagpur | 2026")],
    )
    sec_exp = SectionItem(
        section_type="experience",
        title="Work Experience",
        bullets=[
            BulletItem(content="Led cross-functional team to launch GTM strategy for SaaS product, driving 25% growth."),
            BulletItem(content="Built automated data analytics dashboards in SQL and Tableau for 50+ executives."),
            BulletItem(content="Formulated product roadmap and user stories using Agile Scrum methodologies."),
        ],
    )
    sec_skills = SectionItem(
        section_type="skills",
        title="Technical & Business Skills",
        bullets=[
            BulletItem(content="Product Strategy, A/B Testing, Wireframing, Financial Modeling, SQL"),
        ],
    )

    ver = repo.create_version(
        resume_id=r_id,
        version_name="v1.0 (Master)",
        sections=[sec_edu, sec_exp, sec_skills],
    )
    return ver


def test_matching_and_evidence_attribution(db, candidate_resume):
    """Test matching engine scores correctly and maps bullets to requirements."""
    engine = MatchingEngine(db)
    tracker_repo = TrackerRepository(db)

    job = JobPosting(
        title="Senior Product Manager",
        company="Uber",
        location="Bangalore",
        experience_min=2,
        required_skills=["Product Strategy", "SQL", "A/B Testing", "Machine Learning", "Go To Market"],
    )
    job_id, _ = tracker_repo.add_or_update_job(job)
    persisted_job = tracker_repo.get_job(job_id)

    res = engine.calculate_match(candidate_resume, persisted_job)

    assert res.overall_score >= 60.0
    assert "SQL" in res.matched_requirements
    assert "Product Strategy" in res.matched_requirements
    assert "Go To Market" in res.matched_requirements

    # Missing skill test
    assert "Machine Learning" in res.missing_requirements

    # Evidence attribution test: Verify the bullet was mapped to Go To Market
    gtm_evidence = res.resume_evidence.get("Go To Market", [])
    assert len(gtm_evidence) > 0
    assert any("GTM strategy" in b or "launch" in b for b in gtm_evidence)

    # Database persistence test
    retrieved = engine.get_match_result(persisted_job.id, candidate_resume.id)
    assert retrieved is not None
    assert retrieved.overall_score == res.overall_score
    assert retrieved.is_stale is False


def test_stale_match_invalidation(db, candidate_resume):
    """Test invalidating cached match when resume or job changes."""
    engine = MatchingEngine(db)
    tracker_repo = TrackerRepository(db)

    job = JobPosting(
        title="Management Consultant",
        company="BCG",
        required_skills=["Consulting", "Financial Modeling"],
    )
    job_id, _ = tracker_repo.add_or_update_job(job)
    persisted_job = tracker_repo.get_job(job_id)

    res = engine.calculate_match(candidate_resume, persisted_job)
    assert res.is_stale is False

    # Invalidate by resume version ID
    invalidated_count = engine.invalidate_stale_matches(resume_version_id=candidate_resume.id)
    assert invalidated_count >= 1

    stale_match = engine.get_match_result(persisted_job.id, candidate_resume.id)
    assert stale_match.is_stale is True

    # Re-running clears stale flag
    recalculated = engine.calculate_match(candidate_resume, persisted_job)
    assert recalculated.is_stale is False
