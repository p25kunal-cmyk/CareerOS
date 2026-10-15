"""Naukri Discovery Plugin.

Fetches job listings from Naukri's search endpoint with clean fallback.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import List, Optional
from bs4 import BeautifulSoup

from src.jobs.base import BaseJobSource
from src.tracker.models import JobPosting
from src.utils.logger import get_logger

logger = get_logger("jobs.plugins.naukri")


class NaukriJobSource(BaseJobSource):
    """Fetches opportunities from Naukri."""

    def __init__(self):
        super().__init__(name="naukri", min_delay_seconds=2.0)
        self.base_url = "https://www.naukri.com"

    def search(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 25,
    ) -> List[JobPosting]:
        """Search Naukri for opportunities."""
        clean_q = re.sub(r"[^a-zA-Z0-9]+", "-", query.strip().lower()).strip("-")
        clean_loc = re.sub(r"[^a-zA-Z0-9]+", "-", (location or "").strip().lower()).strip("-")
        
        path = f"/{clean_q}-jobs-in-{clean_loc}" if clean_loc else f"/{clean_q}-jobs"
        url = f"{self.base_url}{path}"

        try:
            resp = self.make_request(url)
            return self.parse_html(resp.text, limit=limit)
        except Exception as e:
            logger.error("[Naukri] Search failed for query '%s': %s", query, e)
            return []

    def parse_html(self, html_content: str, limit: int = 25) -> List[JobPosting]:
        """Parse Naukri job listing HTML."""
        soup = BeautifulSoup(html_content, "html.parser")
        articles = soup.find_all(["article", "div"], class_=re.compile(r"\b(cust-job-tuple|jobTuple)\b"))

        postings: List[JobPosting] = []

        for art in articles[:limit]:
            title_elem = art.find("a", class_=re.compile(r"title"))
            title = title_elem.get_text(strip=True) if title_elem else ""
            link = title_elem.get("href") if title_elem else None

            if not title:
                continue

            comp_elem = art.find("a", class_=re.compile(r"comp-name|subTitle"))
            company = comp_elem.get_text(strip=True) if comp_elem else "Confidential"

            loc_elem = art.find(["span", "li"], class_=re.compile(r"loc|location"))
            location = loc_elem.get_text(strip=True) if loc_elem else "India"

            sal_elem = art.find(["span", "li"], class_=re.compile(r"sal|salary"))
            salary_text = sal_elem.get_text(strip=True) if sal_elem else ""

            postings.append(
                JobPosting(
                    title=title,
                    company=company,
                    location=location,
                    description=salary_text,
                    source_portal="naukri",
                    original_url=link,
                    application_url=link,
                    is_manually_entered=False,
                )
            )

        logger.info("[Naukri] Parsed %d jobs from HTML", len(postings))
        return postings
