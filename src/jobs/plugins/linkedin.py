"""LinkedIn Job Discovery Plugin.

Scrapes public job listings from LinkedIn's guest search endpoint.
"""

from __future__ import annotations

import re
from typing import List, Optional
from bs4 import BeautifulSoup

from src.jobs.base import BaseJobSource
from src.tracker.models import JobPosting
from src.utils.logger import get_logger

logger = get_logger("jobs.plugins.linkedin")


class LinkedInJobSource(BaseJobSource):
    """Fetches job opportunities from LinkedIn public guest endpoint."""

    def __init__(self):
        super().__init__(name="linkedin", min_delay_seconds=2.0)
        self.base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def search(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 25,
    ) -> List[JobPosting]:
        """Search public LinkedIn postings."""
        params = {
            "keywords": query,
            "location": location or "India",
            "start": 0,
        }

        try:
            resp = self.make_request(self.base_url, params=params)
            return self.parse_html(resp.text, limit=limit)
        except Exception as e:
            logger.error("[LinkedIn] Search failed for query '%s': %s", query, e)
            return []

    def parse_html(self, html_content: str, limit: int = 25) -> List[JobPosting]:
        """Parse LinkedIn job card HTML into JobPosting objects."""
        soup = BeautifulSoup(html_content, "html.parser")
        job_cards = soup.find_all("li")
        if not job_cards:
            # Try alternate card containers
            job_cards = soup.find_all("div", class_=re.compile(r"base-card|job-search-card"))

        postings: List[JobPosting] = []

        for card in job_cards[:limit]:
            # Title
            title_elem = card.find(["h3", "h4"], class_=re.compile(r"base-search-card__title|job-card-list__title"))
            if not title_elem:
                title_elem = card.find("a", class_=re.compile(r"base-card__full-link"))
            title = title_elem.get_text(strip=True) if title_elem else ""

            if not title:
                continue

            # Company
            company_elem = card.find(["h4", "a"], class_=re.compile(r"base-search-card__subtitle|job-search-card__subtitle"))
            company = company_elem.get_text(strip=True) if company_elem else "Confidential"

            # Location
            loc_elem = card.find("span", class_=re.compile(r"job-search-card__location"))
            location = loc_elem.get_text(strip=True) if loc_elem else "India"

            # URL
            link_elem = card.find("a", class_=re.compile(r"base-card__full-link"))
            job_url = link_elem["href"].split("?")[0] if (link_elem and link_elem.get("href")) else None

            # Date posted
            time_elem = card.find("time")
            date_posted = time_elem.get("datetime") if (time_elem and time_elem.get("datetime")) else None

            postings.append(
                JobPosting(
                    title=title,
                    company=company,
                    location=location,
                    employment_type="Full-time",
                    date_posted=date_posted,
                    source_portal="linkedin",
                    original_url=job_url,
                    application_url=job_url,
                    is_manually_entered=False,
                )
            )

        logger.info("[LinkedIn] Parsed %d jobs from HTML", len(postings))
        return postings
