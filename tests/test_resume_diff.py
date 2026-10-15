"""Tests for ResumeDiffer comparing versions."""

import pytest
from src.resume.diff import ResumeDiffer
from src.resume.models import BulletItem, ResumeVersionData, SectionItem


def test_version_diff():
    """Test comparing base version with modified target version."""
    base_v = ResumeVersionData(
        resume_id="r1",
        version_number=1,
        version_name="v1.0 (Base)",
        sections=[
            SectionItem(
                title="Experience",
                section_type="experience",
                bullets=[
                    BulletItem(content="Developed web services for 100k users"),
                    BulletItem(content="Maintained legacy SQL reports"),
                ]
            ),
            SectionItem(
                title="Education",
                section_type="education",
                bullets=[BulletItem(content="B.Tech NIT")]
            )
        ]
    )

    target_v = ResumeVersionData(
        resume_id="r1",
        version_number=2,
        version_name="v2.0 (Tailored)",
        sections=[
            SectionItem(
                title="Experience",
                section_type="experience",
                bullets=[
                    BulletItem(content="Developed web services for 100k users"),
                    BulletItem(content="Orchestrated migration to Snowflake saving $20k"),  # Replaced
                    BulletItem(content="Spearheaded pilot with 5 enterprise clients"),    # Added
                ]
            ),
            # Education unchanged
            SectionItem(
                title="Education",
                section_type="education",
                bullets=[BulletItem(content="B.Tech NIT")]
            ),
            # Newly added section
            SectionItem(
                title="Certifications",
                section_type="certifications",
                bullets=[BulletItem(content="AWS Certified Solutions Architect")]
            )
        ]
    )

    diff = ResumeDiffer.diff_versions(base_v, target_v)

    assert diff.base_version_name == "v1.0 (Base)"
    assert diff.target_version_name == "v2.0 (Tailored)"
    assert diff.added_sections == 1
    assert diff.added_bullets >= 1
    assert diff.similarity_ratio > 40.0
