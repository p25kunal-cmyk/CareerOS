"""Database repository for Resume Engine.

Handles transactional persistence of Resumes, Versions, Sections, and Bullets.
Ensures stable UUIDs, snapshot generation, and audit integrity.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.database.connection import DatabaseConnection
from src.resume.models import (
    BulletItem,
    ContactInfo,
    ParsedResume,
    ResumeSummary,
    ResumeVersionData,
    SectionItem,
)
from src.utils.logger import get_logger

logger = get_logger("resume.repository")


class ResumeRepository:
    """Data access layer for all resume entities."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ── Resumes ───────────────────────────────────────────────────

    def create_resume(
        self,
        name: str,
        original_filename: Optional[str] = None,
        original_file_path: Optional[str] = None,
        file_type: Optional[str] = None,
        is_master: bool = False,
        notes: Optional[str] = None,
    ) -> str:
        """Create a new resume record."""
        resume_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            if is_master:
                conn.execute("UPDATE resumes SET is_master = 0 WHERE is_master = 1")

            conn.execute(
                """
                INSERT INTO resumes (
                    id, name, is_master, original_filename, original_file_path,
                    file_type, upload_timestamp, notes
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
                """,
                (resume_id, name, 1 if is_master else 0, original_filename, original_file_path, file_type, notes),
            )
        logger.info("Created resume '%s' (ID: %s)", name, resume_id)
        return resume_id

    def get_resume(self, resume_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve resume metadata by ID."""
        row = self.db.execute_one("SELECT * FROM resumes WHERE id = ?", (resume_id,))
        return dict(row) if row else None

    def get_master_resume(self) -> Optional[Dict[str, Any]]:
        """Retrieve the primary master resume if designated."""
        row = self.db.execute_one("SELECT * FROM resumes WHERE is_master = 1 LIMIT 1")
        return dict(row) if row else None

    def set_master_resume(self, resume_id: str) -> bool:
        """Designate a resume as the master resume."""
        with self.db.transaction() as conn:
            conn.execute("UPDATE resumes SET is_master = 0")
            cursor = conn.execute("UPDATE resumes SET is_master = 1, updated_at = datetime('now') WHERE id = ?", (resume_id,))
            return cursor.rowcount > 0

    def list_resumes(self) -> List[ResumeSummary]:
        """List all resumes with version counts."""
        rows = self.db.execute(
            """
            SELECT 
                r.id, r.name, r.is_master, r.original_filename, r.original_file_path,
                r.file_type, r.upload_timestamp, r.notes, r.created_at, r.updated_at,
                COUNT(v.id) as version_count,
                COALESCE(MAX(v.version_number), 1) as latest_version_number
            FROM resumes r
            LEFT JOIN resume_versions v ON r.id = v.resume_id
            GROUP BY r.id
            ORDER BY r.is_master DESC, r.updated_at DESC
            """
        )
        return [
            ResumeSummary(
                id=row["id"],
                name=row["name"],
                is_master=bool(row["is_master"]),
                original_filename=row["original_filename"],
                original_file_path=row["original_file_path"],
                file_type=row["file_type"],
                upload_timestamp=row["upload_timestamp"],
                notes=row["notes"],
                version_count=row["version_count"],
                latest_version_number=row["latest_version_number"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def delete_resume(self, resume_id: str) -> bool:
        """Delete resume and cascade to all versions, sections, and bullets."""
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
            logger.info("Deleted resume %s (affected: %d)", resume_id, cursor.rowcount)
            return cursor.rowcount > 0

    # ── Versions ──────────────────────────────────────────────────

    def create_version(
        self,
        resume_id: str,
        version_name: Optional[str] = None,
        description: Optional[str] = None,
        parent_version_id: Optional[str] = None,
        is_draft: bool = False,
        sections: Optional[List[SectionItem]] = None,
    ) -> ResumeVersionData:
        """Create a new version with sections and bullets atomically."""
        version_id = str(uuid.uuid4())
        sections = sections or []

        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_ver FROM resume_versions WHERE resume_id = ?",
                (resume_id,),
            ).fetchone()
            ver_num = row["next_ver"] if row else 1
            v_name = version_name or f"v{ver_num}.0"

            conn.execute(
                """
                INSERT INTO resume_versions (
                    id, resume_id, version_number, version_name, description,
                    is_draft, parent_version_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (version_id, resume_id, ver_num, v_name, description, 1 if is_draft else 0, parent_version_id),
            )

            persisted_sections: List[SectionItem] = []
            for s_idx, sec in enumerate(sections, start=1):
                sec_id = sec.id or str(uuid.uuid4())
                meta_json = json.dumps(sec.metadata) if sec.metadata else "{}"
                conn.execute(
                    """
                    INSERT INTO resume_sections (
                        id, version_id, section_type, title, display_order, is_visible, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sec_id, version_id, sec.section_type, sec.title, sec.display_order or s_idx, 1 if sec.is_visible else 0, meta_json),
                )

                persisted_bullets: List[BulletItem] = []
                for b_idx, bul in enumerate(sec.bullets, start=1):
                    bul_id = bul.id or str(uuid.uuid4())
                    b_meta = json.dumps({
                        **bul.metadata,
                        "action_verb": bul.action_verb,
                        "metrics": bul.metrics,
                    })
                    conn.execute(
                        """
                        INSERT INTO resume_bullets (
                            id, section_id, content, sub_content, bullet_type,
                            display_order, indent_level, is_verified, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            bul_id, sec_id, bul.content, bul.sub_content, bul.bullet_type,
                            bul.display_order or b_idx, bul.indent_level, 1 if bul.is_verified else 0, b_meta
                        ),
                    )
                    persisted_bullets.append(bul.model_copy(update={"id": bul_id, "section_id": sec_id}))

                persisted_sections.append(
                    sec.model_copy(update={"id": sec_id, "version_id": version_id, "bullets": persisted_bullets})
                )

            v_data = ResumeVersionData(
                id=version_id,
                resume_id=resume_id,
                version_number=ver_num,
                version_name=v_name,
                description=description,
                is_draft=is_draft,
                parent_version_id=parent_version_id,
                sections=persisted_sections,
            )

            snapshot_json = v_data.to_snapshot_json()
            conn.execute(
                "UPDATE resume_versions SET snapshot_data = ? WHERE id = ?",
                (snapshot_json, version_id),
            )

            conn.execute(
                "UPDATE resumes SET updated_at = datetime('now') WHERE id = ?",
                (resume_id,),
            )

        logger.info("Created version %s (v%d) for resume %s with %d sections", v_name, ver_num, resume_id, len(sections))
        return v_data

    def get_version(self, version_id: str) -> Optional[ResumeVersionData]:
        """Hydrate complete version with sections and bullets."""
        v_row = self.db.execute_one("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
        if not v_row:
            return None

        sec_rows = self.db.execute(
            "SELECT * FROM resume_sections WHERE version_id = ? ORDER BY display_order ASC",
            (version_id,),
        )

        sections: List[SectionItem] = []
        for s in sec_rows:
            bul_rows = self.db.execute(
                "SELECT * FROM resume_bullets WHERE section_id = ? ORDER BY display_order ASC",
                (s["id"],),
            )

            bullets: List[BulletItem] = []
            for b in bul_rows:
                meta = json.loads(b["metadata"]) if b["metadata"] else {}
                action_verb = meta.get("action_verb")
                metrics = meta.get("metrics", [])
                bullets.append(
                    BulletItem(
                        id=b["id"],
                        section_id=b["section_id"],
                        content=b["content"],
                        sub_content=b["sub_content"],
                        bullet_type=b["bullet_type"],
                        display_order=b["display_order"],
                        indent_level=b["indent_level"],
                        is_verified=bool(b["is_verified"]),
                        action_verb=action_verb,
                        metrics=metrics,
                        metadata=meta,
                    )
                )

            s_meta = json.loads(s["metadata"]) if s["metadata"] else {}
            sections.append(
                SectionItem(
                    id=s["id"],
                    version_id=s["version_id"],
                    section_type=s["section_type"],
                    title=s["title"],
                    display_order=s["display_order"],
                    is_visible=bool(s["is_visible"]),
                    metadata=s_meta,
                    bullets=bullets,
                )
            )

        return ResumeVersionData(
            id=v_row["id"],
            resume_id=v_row["resume_id"],
            version_number=v_row["version_number"],
            version_name=v_row["version_name"],
            description=v_row["description"],
            is_draft=bool(v_row["is_draft"]),
            parent_version_id=v_row["parent_version_id"],
            created_at=v_row["created_at"],
            sections=sections,
        )

    def get_latest_version(self, resume_id: str) -> Optional[ResumeVersionData]:
        """Fetch the latest version for a resume."""
        row = self.db.execute_one(
            "SELECT id FROM resume_versions WHERE resume_id = ? ORDER BY version_number DESC LIMIT 1",
            (resume_id,),
        )
        if not row:
            return None
        return self.get_version(row["id"])

    def list_versions(self, resume_id: str) -> List[Dict[str, Any]]:
        """List summary of all versions for a resume."""
        rows = self.db.execute(
            """
            SELECT id, resume_id, version_number, version_name, description,
                   is_draft, parent_version_id, created_at
            FROM resume_versions
            WHERE resume_id = ?
            ORDER BY version_number DESC
            """,
            (resume_id,),
        )
        return [dict(r) for r in rows]

    def fork_version(
        self,
        source_version_id: str,
        new_version_name: str,
        description: Optional[str] = None,
    ) -> ResumeVersionData:
        """Create a new version branching from an existing version."""
        source = self.get_version(source_version_id)
        if not source:
            raise ValueError(f"Source version {source_version_id} not found")

        new_sections: List[SectionItem] = []
        for s in source.sections:
            new_bullets: List[BulletItem] = [
                b.model_copy(update={"id": str(uuid.uuid4()), "section_id": None})
                for b in s.bullets
            ]
            new_sections.append(
                s.model_copy(update={"id": str(uuid.uuid4()), "version_id": None, "bullets": new_bullets})
            )

        return self.create_version(
            resume_id=source.resume_id,
            version_name=new_version_name,
            description=description or f"Branched from {source.version_name or f'v{source.version_number}'}",
            parent_version_id=source_version_id,
            is_draft=False,
            sections=new_sections,
        )

    def sync_snapshot(self, version_id: str) -> bool:
        """Regenerate and save snapshot JSON for a version."""
        v_data = self.get_version(version_id)
        if not v_data:
            return False
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE resume_versions SET snapshot_data = ? WHERE id = ?",
                (v_data.to_snapshot_json(), version_id),
            )
        return True

    # ── Section & Bullet Mutations ────────────────────────────────

    def add_section(
        self,
        version_id: str,
        section_type: str,
        title: str,
        display_order: Optional[int] = None,
    ) -> str:
        """Add a section to an existing version."""
        sec_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            if display_order is None:
                row = conn.execute(
                    "SELECT COALESCE(MAX(display_order), 0) + 1 AS next_ord FROM resume_sections WHERE version_id = ?",
                    (version_id,),
                ).fetchone()
                display_order = row["next_ord"] if row else 1

            conn.execute(
                """
                INSERT INTO resume_sections (id, version_id, section_type, title, display_order, is_visible)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (sec_id, version_id, section_type, title, display_order),
            )
        self.sync_snapshot(version_id)
        return sec_id

    def update_section(
        self,
        section_id: str,
        title: Optional[str] = None,
        is_visible: Optional[bool] = None,
        display_order: Optional[int] = None,
        section_type: Optional[str] = None,
    ) -> bool:
        """Update section properties."""
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if is_visible is not None:
            updates.append("is_visible = ?")
            params.append(1 if is_visible else 0)
        if display_order is not None:
            updates.append("display_order = ?")
            params.append(display_order)
        if section_type is not None:
            updates.append("section_type = ?")
            params.append(section_type)

        if not updates:
            return False

        updates.append("updated_at = datetime('now')")
        params.append(section_id)

        with self.db.transaction() as conn:
            query = f"UPDATE resume_sections SET {', '.join(updates)} WHERE id = ?"
            cursor = conn.execute(query, tuple(params))
            affected = cursor.rowcount

        sec = self.db.execute_one("SELECT version_id FROM resume_sections WHERE id = ?", (section_id,))
        if sec:
            self.sync_snapshot(sec["version_id"])

        return affected > 0

    def delete_section(self, section_id: str) -> bool:
        """Delete section and all its bullets."""
        sec = self.db.execute_one("SELECT version_id FROM resume_sections WHERE id = ?", (section_id,))
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM resume_sections WHERE id = ?", (section_id,))
            affected = cursor.rowcount
        if sec:
            self.sync_snapshot(sec["version_id"])
        return affected > 0

    def reorder_sections(self, version_id: str, section_ids: List[str]) -> bool:
        """Reorder sections according to provided list of section IDs."""
        with self.db.transaction() as conn:
            for idx, s_id in enumerate(section_ids, start=1):
                conn.execute(
                    "UPDATE resume_sections SET display_order = ?, updated_at = datetime('now') WHERE id = ? AND version_id = ?",
                    (idx, s_id, version_id),
                )
        self.sync_snapshot(version_id)
        return True

    def add_bullet(
        self,
        section_id: str,
        content: str,
        bullet_type: str = "bullet",
        display_order: Optional[int] = None,
        indent_level: int = 0,
        sub_content: Optional[str] = None,
        is_verified: bool = True,
        action_verb: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> str:
        """Add bullet item to section."""
        bul_id = str(uuid.uuid4())
        metrics = metrics or []
        meta_json = json.dumps({"action_verb": action_verb, "metrics": metrics})

        with self.db.transaction() as conn:
            if display_order is None:
                row = conn.execute(
                    "SELECT COALESCE(MAX(display_order), 0) + 1 AS next_ord FROM resume_bullets WHERE section_id = ?",
                    (section_id,),
                ).fetchone()
                display_order = row["next_ord"] if row else 1

            conn.execute(
                """
                INSERT INTO resume_bullets (
                    id, section_id, content, sub_content, bullet_type,
                    display_order, indent_level, is_verified, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bul_id, section_id, content, sub_content, bullet_type,
                    display_order, indent_level, 1 if is_verified else 0, meta_json
                ),
            )

        sec = self.db.execute_one("SELECT version_id FROM resume_sections WHERE id = ?", (section_id,))
        if sec:
            self.sync_snapshot(sec["version_id"])

        return bul_id

    def update_bullet(
        self,
        bullet_id: str,
        content: Optional[str] = None,
        sub_content: Optional[str] = None,
        bullet_type: Optional[str] = None,
        is_verified: Optional[bool] = None,
        display_order: Optional[int] = None,
        action_verb: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> bool:
        """Update bullet content or attributes."""
        bul = self.db.execute_one("SELECT * FROM resume_bullets WHERE id = ?", (bullet_id,))
        if not bul:
            return False

        meta = json.loads(bul["metadata"]) if bul["metadata"] else {}
        if action_verb is not None:
            meta["action_verb"] = action_verb
        if metrics is not None:
            meta["metrics"] = metrics

        updates = ["metadata = ?"]
        params = [json.dumps(meta)]

        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if sub_content is not None:
            updates.append("sub_content = ?")
            params.append(sub_content)
        if bullet_type is not None:
            updates.append("bullet_type = ?")
            params.append(bullet_type)
        if is_verified is not None:
            updates.append("is_verified = ?")
            params.append(1 if is_verified else 0)
        if display_order is not None:
            updates.append("display_order = ?")
            params.append(display_order)

        updates.append("updated_at = datetime('now')")
        params.append(bullet_id)

        with self.db.transaction() as conn:
            query = f"UPDATE resume_bullets SET {', '.join(updates)} WHERE id = ?"
            cursor = conn.execute(query, tuple(params))
            affected = cursor.rowcount

        sec = self.db.execute_one("SELECT version_id FROM resume_sections WHERE id = ?", (bul["section_id"],))
        if sec:
            self.sync_snapshot(sec["version_id"])

        return affected > 0

    def delete_bullet(self, bullet_id: str) -> bool:
        """Delete a bullet point."""
        bul = self.db.execute_one("SELECT section_id FROM resume_bullets WHERE id = ?", (bullet_id,))
        if not bul:
            return False

        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM resume_bullets WHERE id = ?", (bullet_id,))
            affected = cursor.rowcount

        sec = self.db.execute_one("SELECT version_id FROM resume_sections WHERE id = ?", (bul["section_id"],))
        if sec:
            self.sync_snapshot(sec["version_id"])

        return affected > 0

    def reorder_bullets(self, section_id: str, bullet_ids: List[str]) -> bool:
        """Reorder bullets within a section."""
        with self.db.transaction() as conn:
            for idx, b_id in enumerate(bullet_ids, start=1):
                conn.execute(
                    "UPDATE resume_bullets SET display_order = ?, updated_at = datetime('now') WHERE id = ? AND section_id = ?",
                    (idx, b_id, section_id),
                )

        sec = self.db.execute_one("SELECT version_id FROM resume_sections WHERE id = ?", (section_id,))
        if sec:
            self.sync_snapshot(sec["version_id"])

        return True

    # ── High Level Import Helper ─────────────────────────────────

    def save_parsed_resume(
        self,
        resume_name: str,
        parsed: ParsedResume,
        original_filename: Optional[str] = None,
        original_file_path: Optional[str] = None,
        is_master: bool = False,
    ) -> Tuple[str, str]:
        """Save parsed resume data as a new resume with an initial v1.0 version."""
        resume_id = self.create_resume(
            name=resume_name,
            original_filename=original_filename,
            original_file_path=original_file_path,
            file_type=parsed.file_type,
            is_master=is_master,
            notes=f"Parsed from {original_filename or 'upload'}. Sections: {len(parsed.sections)}",
        )

        sections_to_save: List[SectionItem] = []
        c = parsed.contact_info
        if c.name or c.email or c.phone or c.linkedin:
            contact_bullets = []
            if c.name:
                contact_bullets.append(BulletItem(content=c.name, bullet_type="header", display_order=1))
            contact_line_parts = [p for p in (c.phone, c.email, c.location) if p]
            if contact_line_parts:
                contact_bullets.append(BulletItem(content=" | ".join(contact_line_parts), bullet_type="contact_item", display_order=2))
            links = [l for l in (c.linkedin, c.github, c.website) if l]
            if links:
                contact_bullets.append(BulletItem(content=" | ".join(links), bullet_type="contact_item", display_order=3))

            sections_to_save.append(
                SectionItem(
                    id=str(uuid.uuid4()),
                    section_type="contact",
                    title="Contact Information",
                    display_order=1,
                    bullets=contact_bullets,
                    metadata=c.model_dump(),
                )
            )

        for idx, sec in enumerate(parsed.sections, start=len(sections_to_save) + 1):
            sections_to_save.append(sec.model_copy(update={"display_order": idx}))

        v_data = self.create_version(
            resume_id=resume_id,
            version_name="v1.0 (Master)" if is_master else "v1.0 (Initial Import)",
            description=f"Initial parsed version from {original_filename or 'upload'}",
            parent_version_id=None,
            is_draft=False,
            sections=sections_to_save,
        )

        return resume_id, v_data.id
