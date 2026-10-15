"""Tests for ResumeRepository database operations, versions, sections, and bullets."""

import pytest
from src.resume.models import BulletItem, ParsedResume, SectionItem
from src.resume.repository import ResumeRepository


def test_resume_crud(db):
    """Test creating, listing, master setting, and deleting resumes."""
    repo = ResumeRepository(db)

    r_id = repo.create_resume(name="My First Resume", is_master=True, notes="Initial test")
    assert r_id is not None

    resumes = repo.list_resumes()
    assert len(resumes) == 1
    assert resumes[0].name == "My First Resume"
    assert resumes[0].is_master is True

    # Create second resume and toggle master
    r_id_2 = repo.create_resume(name="Tech PM Resume", is_master=False)
    repo.set_master_resume(r_id_2)

    master = repo.get_master_resume()
    assert master["id"] == r_id_2
    assert master["name"] == "Tech PM Resume"

    # Delete first resume
    deleted = repo.delete_resume(r_id)
    assert deleted is True
    assert len(repo.list_resumes()) == 1


def test_version_creation_and_snapshot(db):
    """Test version creation with nested sections and bullets."""
    repo = ResumeRepository(db)
    r_id = repo.create_resume(name="MBA Placement Master")

    sec1 = SectionItem(
        section_type="education",
        title="Education",
        display_order=1,
        bullets=[
            BulletItem(content="MBA | IIM Nagpur | 2026", bullet_type="text", display_order=1),
            BulletItem(content="B.Tech | IIT Bombay | 2021", bullet_type="text", display_order=2),
        ],
    )
    sec2 = SectionItem(
        section_type="experience",
        title="Work Experience",
        display_order=2,
        bullets=[
            BulletItem(content="Led team to deliver 40% margin improvement", action_verb="led", metrics=["40%"], display_order=1),
        ],
    )

    ver = repo.create_version(
        resume_id=r_id,
        version_name="v1.0 (Master)",
        description="Base MBA version",
        sections=[sec1, sec2],
    )

    assert ver.version_number == 1
    assert len(ver.sections) == 2
    assert len(ver.sections[0].bullets) == 2
    assert len(ver.sections[1].bullets) == 1

    # Verify snapshot JSON was saved
    loaded_ver = repo.get_version(ver.id)
    assert loaded_ver is not None
    assert loaded_ver.sections[0].title == "Education"
    assert loaded_ver.sections[1].bullets[0].action_verb == "led"


def test_fork_version(db):
    """Test branching a version copies all sections and bullets with fresh IDs."""
    repo = ResumeRepository(db)
    r_id = repo.create_resume(name="Master Profile")

    sec = SectionItem(
        section_type="experience",
        title="Experience",
        bullets=[BulletItem(content="Engineered low-latency system")],
    )
    v1 = repo.create_version(resume_id=r_id, version_name="v1.0", sections=[sec])

    v2 = repo.fork_version(v1.id, new_version_name="v2.0 (Consulting Tailored)")
    assert v2.version_number == 2
    assert v2.parent_version_id == v1.id
    assert v2.id != v1.id

    # Verify bullet has a different ID but same content
    assert v2.sections[0].id != v1.sections[0].id
    assert v2.sections[0].bullets[0].id != v1.sections[0].bullets[0].id
    assert v2.sections[0].bullets[0].content == v1.sections[0].bullets[0].content


def test_section_and_bullet_mutations(db):
    """Test adding, editing, reordering, and deleting sections and bullets."""
    repo = ResumeRepository(db)
    r_id = repo.create_resume(name="Test Resume")
    ver = repo.create_version(resume_id=r_id, version_name="v1.0")

    # Add section
    s1_id = repo.add_section(ver.id, section_type="skills", title="Core Skills")
    s2_id = repo.add_section(ver.id, section_type="projects", title="Academic Projects")

    # Add bullets
    b1_id = repo.add_bullet(s1_id, content="Python, SQL, R")
    b2_id = repo.add_bullet(s1_id, content="Financial Modeling")

    # Update bullet
    repo.update_bullet(b1_id, content="Python, SQL, R, Tableau", is_verified=True)

    # Reorder bullets
    repo.reorder_bullets(s1_id, [b2_id, b1_id])

    hydrated = repo.get_version(ver.id)
    assert len(hydrated.sections) == 2
    assert hydrated.sections[0].bullets[0].id == b2_id
    assert hydrated.sections[0].bullets[1].content == "Python, SQL, R, Tableau"

    # Delete bullet
    repo.delete_bullet(b2_id)
    hydrated_after_del = repo.get_version(ver.id)
    assert len(hydrated_after_del.sections[0].bullets) == 1

    # Delete section
    repo.delete_section(s2_id)
    hydrated_after_s_del = repo.get_version(ver.id)
    assert len(hydrated_after_s_del.sections) == 1


def test_save_parsed_resume_end_to_end(db):
    """Test saving a parsed resume creates master resume and v1.0 version."""
    from src.resume.models import ContactInfo, ParsedResume, SectionItem, BulletItem

    repo = ResumeRepository(db)
    parsed = ParsedResume(
        contact_info=ContactInfo(
            name="Vikram Seth",
            email="vikram@example.com",
            phone="+91 9888877777",
            linkedin="https://linkedin.com/in/vikramseth",
            location="Bangalore",
        ),
        sections=[
            SectionItem(
                section_type="education",
                title="Education",
                bullets=[BulletItem(content="MBA IIM Nagpur | 2026")],
            ),
            SectionItem(
                section_type="experience",
                title="Work Experience",
                bullets=[BulletItem(content="Led 10-person growth team", action_verb="led", metrics=["10-person"])],
            ),
        ],
        raw_text="Sample text",
        file_type="pdf",
    )

    r_id, v_id = repo.save_parsed_resume(
        resume_name="Vikram Master MBA",
        parsed=parsed,
        original_filename="vikram.pdf",
        is_master=True,
    )

    assert r_id is not None
    assert v_id is not None

    resume = repo.get_resume(r_id)
    assert resume["is_master"] == 1
    assert resume["file_type"] == "pdf"

    version = repo.get_version(v_id)
    assert version.version_number == 1
    assert len(version.sections) == 3  # ContactInfo section + 2 parsed sections
    assert version.sections[0].section_type == "contact"
    assert "Vikram Seth" in version.sections[0].bullets[0].content
