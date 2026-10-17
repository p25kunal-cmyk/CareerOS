"""Sample resume generator for CareerOS.

Provides high-quality, ATS-optimized MBA placement resume data
to bootstrap the database and enable instant previews, editing, and matching.
"""

from __future__ import annotations

import uuid
from typing import Tuple

from src.resume.models import BulletItem, ContactInfo, ParsedResume, SectionItem
from src.resume.repository import ResumeRepository


def create_sample_mba_resume(repo: ResumeRepository, name: str = "Ananya Sen — IIM MBA Master Resume") -> Tuple[str, str]:
    """Create and persist a comprehensive IIM Nagpur MBA Master Resume."""
    contact = ContactInfo(
        name="Ananya Sen",
        email="ananya.sen@iimnagpur.ac.in",
        phone="+91 98111 22334",
        linkedin="linkedin.com/in/ananya-sen-iim",
        github="github.com/ananya-analytics",
        location="Nagpur / Mumbai, India",
    )

    sections = [
        # Contact Section
        SectionItem(
            id=str(uuid.uuid4()),
            title="Contact Information",
            section_type="contact",
            display_order=0,
            is_visible=True,
            bullets=[
                BulletItem(content="Ananya Sen", bullet_type="header", display_order=0),
                BulletItem(
                    content="ananya.sen@iimnagpur.ac.in | +91 98111 22334 | linkedin.com/in/ananya-sen-iim | Nagpur, India",
                    bullet_type="text",
                    display_order=1,
                ),
            ],
        ),
        # Academic Qualifications (Table format)
        SectionItem(
            id=str(uuid.uuid4()),
            title="Academic Qualifications",
            section_type="education",
            display_order=1,
            is_visible=True,
            bullets=[
                BulletItem(content="Degree / Examination | Institution | Board / University | Year | % / CGPA", bullet_type="text", display_order=0),
                BulletItem(content="MBA (Strategy & Product) | Indian Institute of Management Nagpur | Autonomous | 2024–2026 | 8.4 / 10.0", bullet_type="text", display_order=1),
                BulletItem(content="B.Tech Computer Science | BITS Pilani | Autonomous | 2018–2022 | 8.7 / 10.0", bullet_type="text", display_order=2),
                BulletItem(content="Class XII (CBSE) | Delhi Public School, R.K. Puram | CBSE | 2018 | 96.2%", bullet_type="text", display_order=3),
                BulletItem(content="Class X (CBSE) | Delhi Public School, R.K. Puram | CBSE | 2016 | 10.0 CGPA", bullet_type="text", display_order=4),
            ],
        ),
        # Work Experience
        SectionItem(
            id=str(uuid.uuid4()),
            title="Work Experience",
            section_type="experience",
            display_order=2,
            is_visible=True,
            bullets=[
                BulletItem(
                    content="Deloitte Consulting — Senior Consultant / Technology Analyst",
                    sub_content="Gurugram, India | Jul 2022 – Jun 2024 (24 months)",
                    bullet_type="header",
                    display_order=0,
                ),
                BulletItem(
                    content="Spearheaded digital transformation roadmap for Fortune 500 retail banking client across 4 markets, improving onboarding turnaround by 38%.",
                    bullet_type="bullet",
                    action_verb="spearheaded",
                    metrics=["38%", "4 markets"],
                    is_verified=True,
                    display_order=1,
                ),
                BulletItem(
                    content="Engineered automated data reconciliation pipeline utilizing Python and SQL, saving 120 analyst hours per quarter and eliminating $450K in reconciliation discrepancies.",
                    bullet_type="bullet",
                    action_verb="engineered",
                    metrics=["120 analyst hours", "$450K"],
                    is_verified=True,
                    display_order=2,
                ),
                BulletItem(
                    content="Mentored a cohort of 6 associate analysts in Agile scrum methodology, achieving 100% on-time sprint deliverables with zero defect spillover.",
                    bullet_type="bullet",
                    action_verb="mentored",
                    metrics=["6 associate analysts", "100%"],
                    is_verified=True,
                    display_order=3,
                ),
            ],
        ),
        # Summer Internship
        SectionItem(
            id=str(uuid.uuid4()),
            title="Summer Internship",
            section_type="internships",
            display_order=3,
            is_visible=True,
            bullets=[
                BulletItem(
                    content="Microsoft — Product Manager Intern (AI & Cloud Platforms)",
                    sub_content="Hyderabad, India | Apr 2025 – Jun 2025 (8 weeks)",
                    bullet_type="header",
                    display_order=0,
                ),
                BulletItem(
                    content="Formulated product requirement document (PRD) and go-to-market strategy for enterprise Copilot workflow connector, projected to generate $1.8M ARR.",
                    bullet_type="bullet",
                    action_verb="formulated",
                    metrics=["$1.8M ARR"],
                    is_verified=True,
                    display_order=1,
                ),
                BulletItem(
                    content="Conducted 24 customer discovery interviews across EMEA enterprise accounts; synthesized findings into 3 core workflow features adopted in Q3 roadmap.",
                    bullet_type="bullet",
                    action_verb="conducted",
                    metrics=["24 customer discovery interviews", "3 core workflow features"],
                    is_verified=True,
                    display_order=2,
                ),
            ],
        ),
        # Academic & Live Projects
        SectionItem(
            id=str(uuid.uuid4()),
            title="Projects & Initiatives",
            section_type="projects",
            display_order=4,
            is_visible=True,
            bullets=[
                BulletItem(
                    content="E-Commerce D2C Pricing Optimization Engine | Capstone Project",
                    bullet_type="header",
                    display_order=0,
                ),
                BulletItem(
                    content="Developed multi-variable price elasticity model analyzing 500K transaction records; modeled dynamic discount strategy yielding 14.5% gross margin expansion.",
                    bullet_type="bullet",
                    action_verb="developed",
                    metrics=["500K transaction records", "14.5%"],
                    is_verified=True,
                    display_order=1,
                ),
            ],
        ),
        # Positions of Responsibility
        SectionItem(
            id=str(uuid.uuid4()),
            title="Positions of Responsibility",
            section_type="positions_of_responsibility",
            display_order=5,
            is_visible=True,
            bullets=[
                BulletItem(
                    content="Senior Coordinator — Placement Committee, IIM Nagpur",
                    sub_content="2024 – Present",
                    bullet_type="header",
                    display_order=0,
                ),
                BulletItem(
                    content="Steering corporate relations and recruitment operations for batch of 260+ MBA students; engaged with 45+ marquee recruiters across BFSI and Consulting.",
                    bullet_type="bullet",
                    action_verb="steering",
                    metrics=["260+ MBA students", "45+ marquee recruiters"],
                    is_verified=True,
                    display_order=1,
                ),
            ],
        ),
        # Certifications & Skills
        SectionItem(
            id=str(uuid.uuid4()),
            title="Skills & Certifications",
            section_type="skills",
            display_order=6,
            is_visible=True,
            bullets=[
                BulletItem(
                    content="Certifications: CFA Investment Foundations, Certified Scrum Product Owner (CSPO), Bloomberg Market Concepts (BMC)",
                    bullet_type="text",
                    display_order=0,
                ),
                BulletItem(
                    content="Tools & Analytics: Python (Pandas/NumPy), SQL, PowerBI, Tableau, Advanced Excel & Financial Modeling, Jira, Figma",
                    bullet_type="text",
                    display_order=1,
                ),
            ],
        ),
        # Achievements
        SectionItem(
            id=str(uuid.uuid4()),
            title="Achievements & Extracurriculars",
            section_type="achievements",
            display_order=7,
            is_visible=True,
            bullets=[
                BulletItem(
                    content="National Winner (Rank 1/1,200+ teams) — Reliance T.U.P Business Case Challenge 2024; awarded INR 300,000 cash prize.",
                    bullet_type="bullet",
                    action_verb="awarded",
                    metrics=["Rank 1/1,200+ teams", "INR 300,000"],
                    is_verified=True,
                    display_order=0,
                ),
                BulletItem(
                    content="Published research paper on 'Algorithmic Pricing in Emerging Retail' in IEEE Xplore conference proceedings.",
                    bullet_type="bullet",
                    is_verified=True,
                    display_order=1,
                ),
            ],
        ),
    ]

    parsed = ParsedResume(
        contact_info=contact,
        sections=sections,
        raw_text="",
        file_type="pdf",
    )

    resume_id, version_id = repo.save_parsed_resume(
        resume_name=name,
        parsed=parsed,
        original_filename="Ananya_Sen_MBA_Resume.pdf",
        is_master=True,
    )

    return resume_id, version_id
