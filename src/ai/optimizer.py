"""Resume Optimization and AI Suggestion Engine.

Generates bullet rephrasings, enforces factual verification safeguards,
and applies accepted suggestions to branched versions.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from src.ai.cache import AICacheManager
from src.ai.provider import BaseAIProvider, get_ai_provider
from src.database.connection import DatabaseConnection
from src.resume.models import BulletItem, ResumeVersionData, SectionItem
from src.resume.repository import ResumeRepository
from src.tracker.repository import TrackerRepository
from src.utils.logger import get_logger

logger = get_logger("ai.optimizer")


class ResumeOptimizer:
    """Manages AI-driven bullet rephrasings, verification, and branching."""

    def __init__(self, db: DatabaseConnection, provider: Optional[BaseAIProvider] = None):
        self.db = db
        self.provider = provider or get_ai_provider(db)
        self.cache = AICacheManager(db)
        self.resume_repo = ResumeRepository(db)
        self.tracker_repo = TrackerRepository(db)

    def optimize_version(
        self,
        resume_version_id: str,
        job_id: Optional[str] = None,
        target_section_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate tailored rephrasings and suggestions for bullets in a resume version."""
        version = self.resume_repo.get_version(resume_version_id)
        if not version:
            raise ValueError(f"Resume version {resume_version_id} not found")

        job = self.tracker_repo.get_job(job_id) if job_id else None

        # Filter target sections
        sections_to_optimize = [
            s for s in version.sections
            if s.section_type in ("experience", "internships", "projects", "positions_of_responsibility")
            and (target_section_id is None or s.id == target_section_id)
        ]

        bullets_map: Dict[str, Tuple[SectionItem, BulletItem]] = {}
        prompt_bullets = []

        for s in sections_to_optimize:
            for b in s.bullets:
                if b.bullet_type in ("bullet", "text") and len(b.content.split()) >= 4:
                    bullets_map[b.content.strip()] = (s, b)
                    prompt_bullets.append(f"- {b.content.strip()}")

        if not prompt_bullets:
            logger.info("No actionable bullets found for optimization.")
            return []

        # Construct prompt
        context = f"Target Role: {job.title} at {job.company}\nKey Skills: {', '.join(job.required_skills)}" if job else "Target: General MBA Consulting / Product Management"
        prompt = (
            f"Context: {context}\n"
            f"Please optimize these resume bullets using the STAR framework and powerful action verbs.\n"
            f"Input bullets:\n" + "\n".join(prompt_bullets[:8])
        )

        input_hash = self.cache.generate_hash(prompt, self.provider.name, self.provider.model)
        cached = self.cache.get_cached_response(input_hash)

        cache_hit = False
        if cached:
            response_text = cached
            tokens_in, tokens_out, cost = 0, 0, 0.0
            cache_hit = True
        else:
            response_text, tokens_in, tokens_out, cost = self.provider.generate(prompt)
            self.cache.store_cached_response(
                input_hash=input_hash,
                prompt=prompt,
                response_text=response_text,
                provider=self.provider.name,
                model=self.provider.model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
            )

        # Log usage record
        usage_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO ai_usage_records (
                    id, provider, model, operation, input_tokens, output_tokens,
                    estimated_cost, input_hash, cache_hit, success, created_at
                ) VALUES (?, ?, ?, 'bullet_optimization', ?, ?, ?, ?, ?, 1, datetime('now'))
                """,
                (usage_id, self.provider.name, self.provider.model, tokens_in, tokens_out, cost, input_hash, 1 if cache_hit else 0),
            )

        # Parse output JSON
        suggestions_created = []
        batch_id = str(uuid.uuid4())

        try:
            # Clean markdown codeblocks if returned
            clean_json = re.sub(r"^```(?:json)?\s*", "", response_text.strip())
            clean_json = re.sub(r"\s*```$", "", clean_json)
            raw_suggestions = json.loads(clean_json)

            if isinstance(raw_suggestions, list):
                for item in raw_suggestions:
                    orig = item.get("original", "").strip()
                    prop = item.get("proposed", "").strip()
                    reason = item.get("reason", "MBA impact enhancement")
                    conf = item.get("confidence", 0.85)

                    if not prop or orig == prop:
                        continue

                    # Lookup source bullet
                    sec_item, bul_item = None, None
                    for b_text, (s_ref, b_ref) in bullets_map.items():
                        if orig.lower() in b_text.lower() or b_text.lower() in orig.lower():
                            sec_item, bul_item = s_ref, b_ref
                            break

                    # Verification safeguard check: Check if new numbers/metrics were introduced
                    orig_metrics = re.findall(r"\d+%", orig)
                    prop_metrics = re.findall(r"\d+%", prop)
                    needs_verif = any(m not in orig_metrics for m in prop_metrics)

                    s_id = str(uuid.uuid4())
                    with self.db.transaction() as conn:
                        conn.execute(
                            """
                            INSERT INTO ai_suggestions (
                                id, job_id, resume_version_id, suggestion_type,
                                target_section_id, source_bullet_id, original_text,
                                proposed_text, reason, verification_status, confidence,
                                batch_id, is_applied, created_at, updated_at
                            ) VALUES (?, ?, ?, 'rephrase', ?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'), datetime('now'))
                            """,
                            (
                                s_id,
                                job.id if job else None,
                                resume_version_id,
                                sec_item.id if sec_item else None,
                                bul_item.id if bul_item else None,
                                orig,
                                prop,
                                reason,
                                "needs_verification" if needs_verif else "pending",
                                conf,
                                batch_id,
                            ),
                        )

                    suggestions_created.append({
                        "id": s_id,
                        "original_text": orig,
                        "proposed_text": prop,
                        "reason": reason,
                        "verification_status": "needs_verification" if needs_verif else "pending",
                    })

        except Exception as e:
            logger.error("Failed to parse AI optimization response: %s", e)

        return suggestions_created

    def list_suggestions(
        self,
        resume_version_id: str,
        only_pending: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retrieve suggestions for a resume version."""
        sql = "SELECT * FROM ai_suggestions WHERE resume_version_id = ?"
        params: List[Any] = [resume_version_id]
        if only_pending:
            sql += " AND is_applied = 0 AND verification_status != 'rejected'"
        sql += " ORDER BY created_at DESC"

        rows = self.db.execute(sql, tuple(params))
        return [dict(r) for r in rows]

    def update_suggestion_status(
        self,
        suggestion_id: str,
        verification_status: str,  # 'verified', 'rejected', 'pending'
        proposed_text: Optional[str] = None,
    ) -> bool:
        """Update suggestion status or manually edited proposed text."""
        updates = ["verification_status = ?", "updated_at = datetime('now')"]
        params: List[Any] = [verification_status]
        if proposed_text is not None:
            updates.append("proposed_text = ?")
            params.append(proposed_text)
        params.append(suggestion_id)

        with self.db.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE ai_suggestions SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            return cursor.rowcount > 0

    def apply_approved_suggestions(
        self,
        resume_version_id: str,
        new_version_name: Optional[str] = None,
    ) -> ResumeVersionData:
        """Fork version and replace approved bullets with proposed text."""
        version = self.resume_repo.get_version(resume_version_id)
        if not version:
            raise ValueError(f"Resume version {resume_version_id} not found")

        # Fetch verified suggestions
        rows = self.db.execute(
            """
            SELECT * FROM ai_suggestions 
            WHERE resume_version_id = ? AND verification_status = 'verified' AND is_applied = 0
            """,
            (resume_version_id,),
        )
        if not rows:
            raise ValueError("No verified suggestions available to apply. Please verify suggestions first.")

        replacements = {r["source_bullet_id"]: r["proposed_text"] for r in rows if r["source_bullet_id"]}
        applied_s_ids = [r["id"] for r in rows]

        # Clone sections and bullets, replacing text where bullet ID matches
        new_sections: List[SectionItem] = []
        for s in version.sections:
            new_bullets: List[BulletItem] = []
            for b in s.bullets:
                new_text = replacements.get(b.id, b.content)
                new_bullets.append(
                    b.model_copy(update={
                        "id": str(uuid.uuid4()),
                        "content": new_text,
                        "section_id": None,
                        "is_verified": True,
                    })
                )
            new_sections.append(
                s.model_copy(update={
                    "id": str(uuid.uuid4()),
                    "version_id": None,
                    "bullets": new_bullets,
                })
            )

        # Create branched version
        branch_name = new_version_name or f"{version.version_name or f'v{version.version_number}'} (AI Optimized)"
        forked = self.resume_repo.create_version(
            resume_id=version.resume_id,
            version_name=branch_name,
            description=f"Applied {len(replacements)} verified AI suggestions to {version.version_name}",
            parent_version_id=version.id,
            sections=new_sections,
        )

        # Mark suggestions as applied
        with self.db.transaction() as conn:
            for s_id in applied_s_ids:
                conn.execute(
                    """
                    UPDATE ai_suggestions SET
                        is_applied = 1,
                        applied_to_version_id = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (forked.id, s_id),
                )

        logger.info("Applied %d suggestions to create new branch %s (%s)", len(replacements), branch_name, forked.id)
        return forked
