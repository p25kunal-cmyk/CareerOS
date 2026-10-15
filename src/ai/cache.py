"""AI Cache Manager with SHA-256 fingerprinting.

Guarantees predictable costs by caching prompt outputs in SQLite.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Dict, Optional

from src.database.connection import DatabaseConnection
from src.utils.logger import get_logger

logger = get_logger("ai.cache")


class AICacheManager:
    """Manages persistent caching of AI prompt-response pairs."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def generate_hash(self, prompt: str, provider: str, model: str, temperature: float = 0.7) -> str:
        """Compute deterministic SHA-256 hash for request parameters."""
        raw = f"{provider}:{model}:{temperature}:{prompt.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_cached_response(self, input_hash: str) -> Optional[str]:
        """Fetch cached response text if available."""
        row = self.db.execute_one(
            "SELECT response FROM ai_cache WHERE input_hash = ?",
            (input_hash,),
        )
        if row:
            logger.info("AI Cache HIT for hash %s", input_hash[:8])
            return row["response"]
        return None

    def store_cached_response(
        self,
        input_hash: str,
        prompt: str,
        response_text: str,
        provider: str,
        model: str,
        operation: str = "bullet_optimization",
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Store prompt-response pair in ai_cache table."""
        cache_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO ai_cache (
                    id, input_hash, provider, model, operation, response, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(input_hash) DO UPDATE SET
                    response = excluded.response,
                    operation = excluded.operation
                """,
                (cache_id, input_hash, provider, model, operation, response_text),
            )
        logger.info("AI Cache STORED for hash %s (%d tokens)", input_hash[:8], tokens_in + tokens_out)
