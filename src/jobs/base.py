"""Base abstractions and utilities for Job Discovery plugins.

Provides rate limiting, user-agent rotation, error isolation, and retry logic.
"""

from __future__ import annotations

import abc
import random
import time
from typing import Any, Dict, List, Optional
import requests

from src.tracker.models import JobPosting
from src.utils.logger import get_logger

logger = get_logger("jobs.base")

# ── Rotating User Agents ──────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


class BaseJobSource(abc.ABC):
    """Abstract base class for all job portal plugins."""

    def __init__(self, name: str, min_delay_seconds: float = 1.5):
        self.name = name
        self.min_delay_seconds = min_delay_seconds
        self._last_request_time = 0.0
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        """Generate headers with rotated user agent and standard accept headers."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }

    def _rate_limit(self):
        """Enforce polite rate limiting between external portal requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_delay_seconds:
            sleep_time = self.min_delay_seconds - elapsed + random.uniform(0.1, 0.4)
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def make_request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
        max_retries: int = 2,
    ) -> requests.Response:
        """Execute HTTP request with rate limiting and retry backoff."""
        self._rate_limit()
        headers = self._get_headers()

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=timeout)
                if resp.status_code == 429:
                    logger.warning("[%s] Rate limited (429). Backing off...", self.name)
                    time.sleep(3.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_exc = e
                logger.warning("[%s] Request failed (attempt %d/%d): %s", self.name, attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    time.sleep(2.0 * (attempt + 1))

        raise RuntimeError(f"[{self.name}] Failed to fetch {url} after {max_retries + 1} attempts: {last_exc}")

    @abc.abstractmethod
    def search(
        self,
        query: str,
        location: Optional[str] = None,
        limit: int = 25,
    ) -> List[JobPosting]:
        """Search the portal for job opportunities matching criteria."""
        pass

    def is_available(self) -> bool:
        """Check if source is reachable and active."""
        return True
