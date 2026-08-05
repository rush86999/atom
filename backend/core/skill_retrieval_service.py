"""Skill auto-injection at prompt time (Workstream C, R72).

Deterministic keyword scorer over the imported community-skill registry
(``SkillRegistryService.list_skills``). Returns a formatted instruction
block that agents splice into their ReAct system prompt as
``{skill_instructions}``.

Design constraints:
  * 0-token — no LLM involved. Pure string scoring over name + description
    + tags, gated by ``ATOM_SKILL_INJECTION_ENABLED`` (default ON).
  * No-op when no skills exist or the flag is off (empty string).
  * Singleton accessor mirrors ``get_field_guide_service``.
"""

import logging
from typing import Any, List

from sqlalchemy.orm import Session

from core.hallucination_config import is_skill_injection_enabled

logger = logging.getLogger(__name__)

# Stopwords stripped before keyword scoring (low information content).
_STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "that", "this", "to",
    "of", "in", "on", "at", "by", "from", "is", "are", "it", "be", "use",
    "using", "how", "what", "when", "why", "your", "you", "i", "me",
}


class SkillRetrievalService:
    """Ranks cached skills by keyword match against the current request."""

    def retrieve_top_skills(
        self,
        db: Session,
        tenant_id: str | None,
        workspace_id: str | None,
        request: str,
        limit: int = 3,
    ) -> str:
        """Return a formatted instruction block for the top ``limit`` skills.

        Empty string when the flag is off, no Active skills exist, or no
        keyword overlap is found.
        """
        if not is_skill_injection_enabled():
            return ""
        if not request:
            return ""

        from core.skill_registry_service import SkillRegistryService

        try:
            registry = SkillRegistryService(db)
            skills = registry.list_skills(status="Active", limit=50)
        except Exception as e:  # never break the ReAct loop
            logger.debug("skill retrieval unavailable: %s", e)
            return ""

        # Phase P8 (Cloudflare G8) — workspace-scoped skill filtering. When a
        # workspace_id is supplied against a real DB session, restrict to skills
        # explicitly assigned to that workspace (via the workspace_skills
        # association table). ``None`` or a non-session db (e.g. unit-test
        # MagicMock) keeps the historical "all skills" behavior. Never raises —
        # a failed workspace lookup degrades to the unfiltered list.
        if workspace_id and skills and isinstance(db, Session):
            try:
                from core.models import SkillExecution, workspace_skills

                assigned_skill_ids = {
                    row[0]
                    for row in db.query(workspace_skills.c.skill_id)
                    .filter(workspace_skills.c.workspace_id == workspace_id)
                    .all()
                }
                if not assigned_skill_ids:
                    return ""
                # Map SkillExecution rows -> the Skill.id FK they reference so we
                # keep only executions whose underlying Skill is workspace-assigned.
                allowed_exec_ids = {
                    row[0]
                    for row in db.query(SkillExecution.id)
                    .filter(SkillExecution.skill_id.in_(assigned_skill_ids))
                    .all()
                }
                skills = [s for s in skills if s["skill_id"] in allowed_exec_ids]
                if not skills:
                    return ""
            except Exception as e:  # pragma: no cover - defensive
                logger.debug("workspace skill filtering unavailable: %s", e)

        # Build (score, display) candidates from name + description + tags.
        query_terms = self._tokenize(request)
        if not query_terms:
            return ""

        scored: List[tuple] = []
        for skill in skills:
            detail = self._fetch_detail(registry, skill)
            text = " ".join(
                [
                    detail.get("skill_name") or "",
                    detail.get("description") or "",
                    " ".join(detail.get("tags") or []),
                ]
            )
            score = sum(1 for term in query_terms if term in text.lower())
            if score > 0:
                scored.append((score, detail))

        scored.sort(key=lambda x: (-x[0], x[1].get("skill_name", "")))
        top = scored[:limit]
        if not top:
            return ""

        lines = ["The following skills may be relevant to the current task:"]
        for _score, skill in top:
            name = skill.get("skill_name") or "unnamed"
            description = skill.get("description") or ""
            usage = (skill.get("skill_body") or "")[:120].replace("\n", " ")
            lines.append(
                f"- `{name}`: {description or 'No description'}"
                + (f" ({usage}...)" if usage else "")
            )
        lines.append(
            "Only invoke a skill if it directly matches the task; otherwise "
            "ignore this block."
        )
        return "\n".join(lines)

    @staticmethod
    def _fetch_detail(registry: Any, skill: dict) -> dict:
        """Return skill detail, falling back to the list entry."""
        try:
            detail = registry.get_skill(skill.get("skill_id")) or {}
            detail.setdefault("skill_name", skill.get("skill_name", ""))
            detail.setdefault("description", "")
            detail.setdefault("tags", [])
            return detail
        except Exception:
            return {
                "skill_name": skill.get("skill_name", ""),
                "description": "",
                "tags": [],
                "skill_body": "",
            }

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        import re

        tokens = re.findall(r"[a-z0-9_]+", text.lower())
        return [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]


# Singleton accessor mirroring get_field_guide_service.
_service: SkillRetrievalService | None = None


def get_skill_retrieval_service() -> SkillRetrievalService:
    global _service
    if _service is None:
        _service = SkillRetrievalService()
    return _service
