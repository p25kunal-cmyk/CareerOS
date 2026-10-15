"""Indeed Job Discovery Plugin.

Fetches job listings from Indeed's public RSS and search feeds.
"""

from __future__ import annotations

import re
from typing import List, Optional
from bs4 import BeautifulSoup

from src.jobs.base import BaseJobSource
from src.tracker.models import JobPosting
from src.utils.logger import get_logger

logger = get_logger("jobs.plugins.indeed")


class IndeedJobSource(BaseJobSource):
    """Fetches opportunities from Indeed public feeds."""

    def __init__(self):
        super().__init__(name="indeed", min_delay_seconds=1.5)
        self.base_url = "https://in.indeed.com/rss"

    def search(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 25,
    ) -> List[JobPosting]:
        """Search Indeed India opportunities."""
        params = {
            "q": query,
            "l": location or "India",
        }

        try:
            resp = self.make_request(self.base_url, params=params)
            return self.parse_rss(resp.text, limit=limit)
        except Exception as e:
            logger.error("[Indeed] Search failed for query '%s': %s", query, e)
            return []

    def parse_rss(self, xml_content: str, limit: int = 25) -> List[JobPosting]:
        """Parse Indeed RSS feed into JobPosting objects."""
        soup = BeautifulSoup(xml_content, "xml")
        items = soup.find_all("item")
        if not items:
            # Fallback to standard html parsing if xml parser unavailable
            soup = BeautifulSoup(xml_content, "html.parser")
            items = soup.find_all("item")

        postings: List[JobPosting] = []

        for item in items[:limit]:
            raw_title = item.title.get_text(strip=True) if item.title else ""
            link = item.link.get_text(strip=True) if item.link else None
            desc = item.description.get_text(strip=True) if item.description else ""
            pub_date = item.pubDate.get_text(strip=True) if item.pubDate else None

            # Indeed titles in RSS are typically: "Job Title - Company Name - Location"
            parts = [p.strip() for p in raw_title.split(" - ") if p.strip()]
            title = parts[0] if parts else raw_title
            company = parts[1] if len(parts) > 1 else "Unknown"
            location = parts[2] if len(parts) > 2 else "India"

            if not title:
                continue

            postings.append(
                JobPosting(
                    title=title,
                    company=company,
                    location=location,
                    description=desc,
                    date_posted=pub_date,
                    source_portal="indeed",
                    original_url=link,
                    application_url=link,
                    is_manually_entered=False,
                )
            )

        logger.info("[Indeed] Parsed %d jobs from RSS", len(postings))
        return postings
