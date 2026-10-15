"""Unit and integration tests for Job Discovery Engine and Source Plugins."""

import pytest
from src.jobs.base import BaseJobSource
from src.jobs.engine import JobDiscoveryEngine
from src.jobs.plugins.iimjobs import IIMjobsSource
from src.jobs.plugins.indeed import IndeedJobSource
from src.jobs.plugins.linkedin import LinkedInJobSource
from src.jobs.plugins.naukri import NaukriJobSource
from src.tracker.models import JobPosting, JobSearchProfile
from src.tracker.repository import TrackerRepository


SAMPLE_LINKEDIN_HTML = """
<ul class="jobs-search__results-list">
    <li>
        <div class="base-card">
            <a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/product-manager-at-google-12345?refId=abc">
                <span class="sr-only">Product Manager</span>
            </a>
            <div class="base-search-card__info">
                <h3 class="base-search-card__title">Product Manager - Search</h3>
                <h4 class="base-search-card__subtitle">
                    <a href="https://linkedin.com/company/google">Google</a>
                </h4>
                <span class="job-search-card__location">Bangalore, Karnataka, India</span>
                <time datetime="2026-10-12">3 days ago</time>
            </div>
        </div>
    </li>
    <li>
        <div class="base-card">
            <a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/strategy-lead-at-bcg-67890">
                <span class="sr-only">Strategy Lead</span>
            </a>
            <div class="base-search-card__info">
                <h3 class="base-search-card__title">Strategy Consultant</h3>
                <h4 class="base-search-card__subtitle">BCG</h4>
                <span class="job-search-card__location">Mumbai, Maharashtra, India</span>
                <time datetime="2026-10-14">1 day ago</time>
            </div>
        </div>
    </li>
</ul>
"""

SAMPLE_INDEED_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
    <title>Indeed Job Search</title>
    <item>
        <title>Senior Product Manager - Microsoft - Hyderabad, Telangana</title>
        <link>https://in.indeed.com/viewjob?jk=abc123456</link>
        <description>Lead development of AI cloud services for enterprise.</description>
        <pubDate>Mon, 13 Oct 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
        <title>Management Consultant - Bain &amp; Company - New Delhi</title>
        <link>https://in.indeed.com/viewjob?jk=def789012</link>
        <description>Drive digital transformation for global clients.</description>
        <pubDate>Sun, 12 Oct 2026 10:00:00 GMT</pubDate>
    </item>
</channel>
</rss>
"""

SAMPLE_IIMJOBS_HTML = """
<div class="job-listings">
    <div class="regularListing">
        <a class="jobtitle" href="/j/lead-strategy-consultant-1234.html">Lead Strategy Consultant</a>
        <div class="recruiter">Kearney</div>
        <div class="location">Gurgaon</div>
        <div class="exp">3 - 6 yrs</div>
    </div>
</div>
"""

SAMPLE_NAUKRI_HTML = """
<div class="srp-jobtuple-wrapper">
    <div class="cust-job-tuple">
        <a class="title" href="https://naukri.com/job-1">Associate Vice President - Strategy</a>
        <a class="comp-name">HDFC Bank</a>
        <span class="loc">Mumbai</span>
        <span class="sal">25-35 Lacs P.A.</span>
    </div>
</div>
"""


def test_base_job_source_headers():
    """Verify headers contain rotating user agents."""
    source = LinkedInJobSource()
    headers1 = source._get_headers()
    assert "User-Agent" in headers1
    assert "Mozilla" in headers1["User-Agent"]


def test_linkedin_html_parser():
    """Test parsing LinkedIn public search HTML."""
    source = LinkedInJobSource()
    jobs = source.parse_html(SAMPLE_LINKEDIN_HTML)

    assert len(jobs) == 2
    assert jobs[0].title == "Product Manager - Search"
    assert jobs[0].company == "Google"
    assert "Bangalore" in jobs[0].location
    assert jobs[0].original_url == "https://in.linkedin.com/jobs/view/product-manager-at-google-12345"

    assert jobs[1].title == "Strategy Consultant"
    assert jobs[1].company == "BCG"


def test_indeed_rss_parser():
    """Test parsing Indeed RSS feed."""
    source = IndeedJobSource()
    jobs = source.parse_rss(SAMPLE_INDEED_RSS)

    assert len(jobs) == 2
    assert jobs[0].title == "Senior Product Manager"
    assert jobs[0].company == "Microsoft"
    assert "Hyderabad" in jobs[0].location
    assert "AI cloud services" in jobs[0].description


def test_iimjobs_html_parser():
    """Test parsing IIMjobs HTML."""
    source = IIMjobsSource()
    jobs = source.parse_html(SAMPLE_IIMJOBS_HTML)

    assert len(jobs) == 1
    assert jobs[0].title == "Lead Strategy Consultant"
    assert jobs[0].company == "Kearney"
    assert jobs[0].experience_min == 3
    assert "iimjobs.com" in jobs[0].original_url


def test_naukri_html_parser():
    """Test parsing Naukri HTML."""
    source = NaukriJobSource()
    jobs = source.parse_html(SAMPLE_NAUKRI_HTML)

    assert len(jobs) == 1
    assert jobs[0].title == "Associate Vice President - Strategy"
    assert jobs[0].company == "HDFC Bank"


class MockSource(BaseJobSource):
    """Mock source returning predictable job postings."""
    def __init__(self, name: str, should_fail: bool = False):
        super().__init__(name=name)
        self.should_fail = should_fail

    def search(self, query: str, location: str = None, limit: int = 15):
        if self.should_fail:
            raise ConnectionError("Mock connection timeout")
        return [
            JobPosting(
                title=f"{query} Specialist",
                company="Mock Corp",
                location="Bangalore",
                source_portal=self.name,
                original_url=f"https://mock.com/{self.name}-{query}",
            )
        ]


def test_job_discovery_engine(db):
    """Test running discovery engine with mock sources and recording in automation_runs."""
    engine = JobDiscoveryEngine(db)

    # Register mocks
    engine.register_source(MockSource("linkedin", should_fail=False))
    engine.register_source(MockSource("indeed", should_fail=False))
    engine.register_source(MockSource("iimjobs", should_fail=True))  # Failure isolation test

    res = engine.run_discovery(limit_per_source=5)

    assert res.run_id is not None
    assert res.items_processed >= 2
    assert res.items_added >= 2
    assert "linkedin" in res.sources_succeeded
    assert "indeed" in res.sources_succeeded
    assert "iimjobs" in res.sources_failed

    # Check automation_runs entry
    runs = db.execute("SELECT * FROM automation_runs WHERE id = ?", (res.run_id,))
    assert len(runs) == 1
    assert runs[0]["task_type"] == "job_discovery"
    assert runs[0]["items_added"] >= 2

    # Check job_sources status updated
    src_statuses = engine.list_source_statuses()
    linkedin_status = next(s for s in src_statuses if s["source_type"] == "linkedin")
    assert linkedin_status["last_successful_run"] is not None

    iimjobs_status = next(s for s in src_statuses if s["source_type"] == "iimjobs")
    assert iimjobs_status["last_error"] is not None
