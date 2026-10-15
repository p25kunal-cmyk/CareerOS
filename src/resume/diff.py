"""Resume version comparison and visual diff engine.

Provides structured section-by-section and bullet-by-bullet diffs between
any two resume versions, calculating changes, similarity scores, and summaries.
"""

from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.resume.models import BulletItem, ResumeVersionData, SectionItem


class BulletDiff(BaseModel):
    """Diff result for a single bullet item."""
    change_type: str  # 'added', 'removed', 'modified', 'unchanged'
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    diff_html: Optional[str] = None
    bullet_id: Optional[str] = None


class SectionDiff(BaseModel):
    """Diff result for a single section."""
    section_title: str
    section_type: str
    status: str  # 'added', 'removed', 'modified', 'unchanged'
    bullets: List[BulletDiff] = Field(default_factory=list)


class ResumeVersionDiff(BaseModel):
    """Complete diff comparison between two resume versions."""
    base_version_name: str
    target_version_name: str
    similarity_ratio: float
    added_sections: int = 0
    removed_sections: int = 0
    modified_sections: int = 0
    added_bullets: int = 0
    removed_bullets: int = 0
    modified_bullets: int = 0
    sections: List[SectionDiff] = Field(default_factory=list)


class ResumeDiffer:
    """Computes granular diffs between resume versions."""

    @staticmethod
    def diff_versions(base: ResumeVersionData, target: ResumeVersionData) -> ResumeVersionDiff:
        """Compare base version against target version."""
        base_sections = {s.title.lower().strip(): s for s in base.sections}
        target_sections = {s.title.lower().strip(): s for s in target.sections}

        all_titles_ordered = []
        for s in target.sections:
            t = s.title.lower().strip()
            if t not in all_titles_ordered:
                all_titles_ordered.append(t)
        for s in base.sections:
            t = s.title.lower().strip()
            if t not in all_titles_ordered:
                all_titles_ordered.append(t)

        section_diffs: List[SectionDiff] = []
        added_sec_count = 0
        removed_sec_count = 0
        modified_sec_count = 0
        added_bul_count = 0
        removed_bul_count = 0
        modified_bul_count = 0

        # Full text representation for similarity ratio
        base_full_text = "\n".join(b.content for s in base.sections for b in s.bullets)
        target_full_text = "\n".join(b.content for s in target.sections for b in s.bullets)
        sim_ratio = difflib.SequenceMatcher(None, base_full_text, target_full_text).ratio()

        for key in all_titles_ordered:
            base_s = base_sections.get(key)
            target_s = target_sections.get(key)

            if base_s is None and target_s is not None:
                # Newly added section
                added_sec_count += 1
                b_diffs = []
                for b in target_s.bullets:
                    added_bul_count += 1
                    b_diffs.append(BulletDiff(
                        change_type="added",
                        old_content=None,
                        new_content=b.content,
                        bullet_id=b.id,
                    ))
                section_diffs.append(SectionDiff(
                    section_title=target_s.title,
                    section_type=target_s.section_type,
                    status="added",
                    bullets=b_diffs,
                ))

            elif base_s is not None and target_s is None:
                # Removed section
                removed_sec_count += 1
                b_diffs = []
                for b in base_s.bullets:
                    removed_bul_count += 1
                    b_diffs.append(BulletDiff(
                        change_type="removed",
                        old_content=b.content,
                        new_content=None,
                        bullet_id=b.id,
                    ))
                section_diffs.append(SectionDiff(
                    section_title=base_s.title,
                    section_type=base_s.section_type,
                    status="removed",
                    bullets=b_diffs,
                ))

            else:
                # Section present in both -> compare bullets
                b_diffs = ResumeDiffer._diff_bullets(base_s.bullets, target_s.bullets)
                has_changes = any(d.change_type != "unchanged" for d in b_diffs)
                if has_changes:
                    modified_sec_count += 1
                    for d in b_diffs:
                        if d.change_type == "added":
                            added_bul_count += 1
                        elif d.change_type == "removed":
                            removed_bul_count += 1
                        elif d.change_type == "modified":
                            modified_bul_count += 1

                section_diffs.append(SectionDiff(
                    section_title=target_s.title,
                    section_type=target_s.section_type,
                    status="modified" if has_changes else "unchanged",
                    bullets=b_diffs,
                ))

        return ResumeVersionDiff(
            base_version_name=base.version_name or f"v{base.version_number}",
            target_version_name=target.version_name or f"v{target.version_number}",
            similarity_ratio=round(sim_ratio * 100, 1),
            added_sections=added_sec_count,
            removed_sections=removed_sec_count,
            modified_sections=modified_sec_count,
            added_bullets=added_bul_count,
            removed_bullets=removed_bul_count,
            modified_bullets=modified_bul_count,
            sections=section_diffs,
        )

    @staticmethod
    def _diff_bullets(base_bullets: List[BulletItem], target_bullets: List[BulletItem]) -> List[BulletDiff]:
        """Compare two lists of bullets using sequence matching."""
        base_texts = [b.content for b in base_bullets]
        target_texts = [b.content for b in target_bullets]

        sm = difflib.SequenceMatcher(None, base_texts, target_texts)
        results: List[BulletDiff] = []

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for i in range(i1, i2):
                    results.append(BulletDiff(
                        change_type="unchanged",
                        old_content=base_texts[i],
                        new_content=base_texts[i],
                        bullet_id=base_bullets[i].id,
                    ))
            elif tag == "replace":
                for idx_old, idx_new in zip(range(i1, i2), range(j1, j2)):
                    results.append(BulletDiff(
                        change_type="modified",
                        old_content=base_texts[idx_old],
                        new_content=target_texts[idx_new],
                        bullet_id=target_bullets[idx_new].id,
                    ))
                # Handle unequal lengths in replace chunk
                len_old = i2 - i1
                len_new = j2 - j1
                if len_old > len_new:
                    for i in range(i1 + len_new, i2):
                        results.append(BulletDiff(
                            change_type="removed",
                            old_content=base_texts[i],
                            new_content=None,
                            bullet_id=base_bullets[i].id,
                        ))
                elif len_new > len_old:
                    for j in range(j1 + len_old, j2):
                        results.append(BulletDiff(
                            change_type="added",
                            old_content=None,
                            new_content=target_texts[j],
                            bullet_id=target_bullets[j].id,
                        ))
            elif tag == "delete":
                for i in range(i1, i2):
                    results.append(BulletDiff(
                        change_type="removed",
                        old_content=base_texts[i],
                        new_content=None,
                        bullet_id=base_bullets[i].id,
                    ))
            elif tag == "insert":
                for j in range(j1, j2):
                    results.append(BulletDiff(
                        change_type="added",
                        old_content=None,
                        new_content=target_texts[j],
                        bullet_id=target_bullets[j].id,
                    ))

        return results
