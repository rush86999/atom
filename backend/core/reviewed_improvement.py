"""Apply a reviewed Memento candidate as a typed prompt skill.

Review and application are deliberately separate:

- ``pending`` is not permission to apply anything;
- ``validated`` means a reviewer approved the proposal;
- ``apply`` (this module) is the explicit, authorized step that writes a
  **prompt-only** skill package, registers it in the canonical skill registry,
  assigns it to the agent's workspace and marks the candidate promoted.

Generated executable code is never written, imported or run here. The code
stays reviewable on the candidate; applying it needs a separate, explicit
code-modification authority that this lifecycle does not grant.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

SKILL_APPLY_SCHEMA = "atom-reviewed-skill-apply-1"


def _safe_name(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(name or "")).strip("_").lower()
    return safe[:80] or f"reviewed_skill_{uuid.uuid4().hex[:8]}"


def _skill_markdown(candidate: Any) -> str:
    """Typed prompt skill: metadata + instructions, no scripts by design."""
    description = str(candidate.skill_description or "").strip()
    failure = candidate.failure_pattern or {}
    if not isinstance(failure, dict):
        failure = {}
    instructions = (
        description
        or str(failure.get("failure_summary") or "").strip()
        or "Use the reviewed lesson from the failed episode."
    )
    tags = "memento, reviewed"
    return (
        "---\n"
        f"name: {candidate.skill_name}\n"
        f"description: {description or instructions}\n"
        "version: 1.0.0\n"
        "author: Memento-Skills\n"
        f"tags: [{tags}]\n"
        "---\n\n"
        f"# {candidate.skill_name}\n\n"
        f"{description or instructions}\n\n"
        "## Instructions\n"
        f"{instructions}\n\n"
        "## Provenance\n"
        f"- candidate: {candidate.id}\n"
        f"- source episode: {candidate.source_episode_id}\n"
    )


async def apply_reviewed_skill(
    db: Session,
    candidate: Any,
    *,
    tenant_id: str,
    workspace_id: str,
    builder: Optional[Any] = None,
    registry: Optional[Any] = None,
) -> Dict[str, Any]:
    """Apply one validated candidate. Raises ValueError otherwise."""
    if candidate is None:
        raise ValueError("candidate_not_found")
    if candidate.validation_status == "promoted":
        applied = dict(
            (candidate.validation_result or {}).get("applied") or {})
        return {
            "schema": SKILL_APPLY_SCHEMA,
            "status": "promoted",
            "already_applied": True,
            "skill_id": applied.get("skill_id"),
            "package_path": applied.get("package_path"),
            "candidate_id": str(candidate.id),
        }
    if candidate.validation_status != "validated":
        raise ValueError(
            "candidate_not_reviewed: only a validated candidate may be applied")

    from core.skill_builder_service import SkillBuilderService, SkillMetadata
    from core.skill_registry_service import SkillRegistryService

    builder = builder or SkillBuilderService()
    registry = registry or SkillRegistryService(db)
    markdown = _skill_markdown(candidate)
    safe_name = _safe_name(candidate.skill_name)
    metadata = SkillMetadata(
        name=safe_name,
        description=str(candidate.skill_description or "")[:500],
        version="1.0.0",
        author="Memento-Skills",
        capabilities=[],
        instructions=str(
            (candidate.failure_pattern or {}).get("failure_summary")
            or candidate.skill_description or "")[:2000],
    )
    package = builder.create_skill_package(
        tenant_id=tenant_id, metadata=metadata, scripts={})
    if not package.get("success") and "already exists" not in str(
            package.get("message") or "").lower():
        raise ValueError(
            f"skill_package_failed: {package.get('message') or 'unknown'}")

    imported = await registry.import_skill(
        "raw_content", markdown,
        metadata={"author": "Memento-Skills", "tags": ["memento", "reviewed"]})
    registry_status = str(imported.get("status") or "")
    registry_id = str(imported.get("skill_id") or "")
    if registry_status != "Active" and registry_id:
        registry.promote_skill(registry_id)

    # Ordinary work consumes Active community skills through the registry,
    # and workspace prompts filter by ``workspace_skills``. Mirror the typed
    # skill into that canonical table and point the execution row at it.
    from core.models import AgentExecution, Skill, SkillExecution, workspace_skills

    skill_id = str(uuid.uuid4())
    db.add(Skill(
        id=skill_id,
        tenant_id=tenant_id,
        author_tenant_id=tenant_id,
        name=safe_name,
        description=str(candidate.skill_description or "")[:2000],
        long_description=markdown,
        version="1.0.0",
        type="prompt",
        input_schema={},
        output_schema=None,
        config={"instructions": metadata.instructions},
        is_public=False,
        is_approved=True,
        is_featured=False,
        category="auto_dev",
        tags=["memento", "reviewed"],
    ))
    db.execute(workspace_skills.insert().values(
        workspace_id=workspace_id, skill_id=skill_id))
    execution = (
        db.query(SkillExecution)
        .filter(SkillExecution.id == registry_id)
        .first()
    )
    if execution is None:
        raise ValueError("skill_registry_row_missing")
    execution.skill_id = skill_id
    if candidate.agent_id:
        execution.agent_id = str(candidate.agent_id)
    execution.tenant_id = tenant_id
    execution.workspace_id = workspace_id

    applied = {
        "schema": SKILL_APPLY_SCHEMA,
        "skill_id": skill_id,
        "registry_execution_id": registry_id,
        "package_path": package.get("path"),
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "generated_code_applied": False,
    }
    candidate.validation_status = "promoted"
    candidate.promoted_at = datetime.now(timezone.utc)
    candidate.validation_result = {
        **(candidate.validation_result or {}),
        "applied": applied,
    }
    db.commit()
    return {
        **applied,
        "status": "promoted",
        "already_applied": False,
        "candidate_id": str(candidate.id),
    }
