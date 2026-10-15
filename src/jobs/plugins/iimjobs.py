"""IIMjobs Discovery Plugin.

Fetches MBA and management consulting, strategy, product, and finance opportunities.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import List, Optional
from bs4 import BeautifulSoup

from src.jobs.base import BaseJobSource
from src.tracker.models import JobPosting
from src.utils.logger import get_logger

logger = get_logger("jobs.plugins.iimjobs")


class IIMjobsSource(BaseJobSource):
    """Fetches premium MBA opportunities from IIMjobs."""

    def __init__(self):
        super().__init__(name="iimjobs", min_delay_seconds=2.0)
        self.base_url = "https://www.iimjobs.com/search"

    def search(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 25,
    ) -> List[JobPosting]:
        """Search IIMjobs for target roles."""
        clean_q = urllib.parse.quote_plus(query)
        clean_loc = urllib.parse.quote_plus(location or "")
        url = f"{self.base_url}/{clean_q}-{clean_loc}.html" if clean_loc else f"{self.base_url}/{clean_q}.html"

        try:
            resp = self.make_request(url)
            return self.parse_html(resp.text, limit=limit)
        except Exception as e:
            logger.error("[IIMjobs] Search failed for query '%s': %s", query, e)
            return []

    def parse_html(self, html_content: str, limit: int = 25) -> List[JobPosting]:
        """Parse IIMjobs listing HTML into JobPosting objects."""
        soup = BeautifulSoup(html_content, "html.parser")
        job_rows = soup.find_all("div", class_=re.compile(r"\b(regularListing|job_card)\b"))

        postings: List[JobPosting] = []

        for row in job_rows[:limit]:
            # Title & Link
            title_tag = row.find("a", class_=re.compile(r"jobtitle|listing-title"))
            if not title_tag:
                title_tag = row.find("a")
            title = title_tag.get_text(strip=True) if title_tag else ""
            link = title_tag.get("href") if title_tag else None
            if link and not link.startswith("http"):
                link = f"https://www.iimjobs.com{link}"

            if not title:
                continue

            # Company / Recruiter
            comp_tag = row.find(["span", "div"], class_=re.compile(r"recruiter|company"))
            company = comp_tag.get_text(strip=True) if comp_tag else "Confidential (IIMjobs Recruiter)"

            # Location & Exp
            loc_tag = row.find(["span", "div"], class_=re.compile(r"location"))
            location = loc_tag.get_text(strip=True) if loc_tag else "India"

            exp_tag = row.find(["span", "div"], class_=re.compile(r"experience|exp"))
            exp_text = exp_tag.get_text(strip=True) if exp_tag else ""
            exp_min = 0
            exp_match = re.search(r"(\d+)\s*-\s*(\d+)", exp_text)
            if exp_match:
                exp_min = int(exp_match.group(1))

            postings.append(
                JobPosting(
                    title=title,
                    company=company,
                    location=location,
                    experience_min=exp_min,
                    source_portal="iimjobs",
                    original_url=link,
                    application_url=link,
                    is_manually_entered=False,
                )
            )

        logger.info("[IIMjobs] Parsed %d jobs from HTML", len(postings))
        return postings
