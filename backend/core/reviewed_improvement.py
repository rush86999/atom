"""Apply a reviewed Memento candidate as a typed prompt skill.

Review and application are deliberately separate and content-bound:

- ``pending`` is not permission to apply anything;
- ``validated`` means a reviewer approved an exact candidate snapshot;
- ``apply`` reloads the candidate, revalidates the reviewed digest/scope and
  claims the validated revision with a conditional update;
- only a prompt-only skill package is written. Generated executable code is
  never written, imported or run.

The package, registry execution, Skill row, workspace assignment and candidate
promotion commit in one caller-owned transaction. Filesystem packages use a
deterministic candidate+review identity; a failed application removes only the
package it created.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.auto_dev.models import SkillCandidate

SKILL_APPLY_SCHEMA = "atom-reviewed-skill-apply-1"
REVIEW_SCHEMA = "atom-reviewed-skill-review-1"


def _safe_name(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(name or "")).strip("_").lower()
    return safe[:80] or f"reviewed_skill_{uuid.uuid4().hex[:8]}"


def candidate_material(candidate: Any) -> Dict[str, Any]:
    """Canonical reviewed material (never generated executable code bytes)."""
    failure = candidate.failure_pattern or {}
    if isinstance(failure, str):
        failure = {"failure_summary": failure}
    if not isinstance(failure, dict):
        failure = {}
    return {
        "skill_name": str(candidate.skill_name or ""),
        "skill_description": str(candidate.skill_description or ""),
        "failure_pattern": failure,
        "source_episode_id": str(candidate.source_episode_id or ""),
        "agent_id": str(candidate.agent_id or ""),
        "generated_code_sha256": hashlib.sha256(
            str(candidate.generated_code or "").encode("utf-8")).hexdigest(),
    }


def review_digest(candidate: Any) -> str:
    blob = json.dumps(
        candidate_material(candidate), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _binding_digest(
    candidate: Any, *, tenant_id: str, workspace_id: str, agent_id: str,
) -> str:
    payload = {
        "material": candidate_material(candidate),
        "tenant_id": str(tenant_id or ""),
        "workspace_id": str(workspace_id or ""),
        "agent_id": str(agent_id or ""),
    }
    blob = json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def review_binding(
    candidate: Any,
    *,
    tenant_id: str,
    workspace_id: str,
    agent_id: str,
    reviewer_id: str,
    review_revision: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the exact scope+material binding a reviewer approves."""
    existing = candidate.validation_result if isinstance(
        candidate.validation_result, dict) else {}
    previous = existing.get("review") if isinstance(
        existing.get("review"), dict) else {}
    revision = int(
        review_revision if review_revision is not None
        else int(previous.get("review_revision") or 0) + 1)
    return {
        "schema": REVIEW_SCHEMA,
        "digest": _binding_digest(
            candidate, tenant_id=tenant_id, workspace_id=workspace_id,
            agent_id=agent_id),
        "review_revision": revision,
        "reviewed_by": str(reviewer_id or ""),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": str(tenant_id or ""),
        "workspace_id": str(workspace_id or ""),
        "agent_id": str(agent_id or ""),
    }


def mark_reviewed(
    candidate: Any,
    *,
    reviewer_id: str,
    tenant_id: str,
    workspace_id: str,
) -> Dict[str, Any]:
    """Record the exact reviewed snapshot. Does not apply or promote."""
    if candidate.validation_status in ("applying", "promoted"):
        raise ValueError(
            "candidate_state_conflict: a newer application already owns "
            "this candidate")
    existing = candidate.validation_result if isinstance(
        candidate.validation_result, dict) else {}
    review = review_binding(
        candidate, tenant_id=tenant_id, workspace_id=workspace_id,
        agent_id=str(candidate.agent_id or ""), reviewer_id=reviewer_id)
    candidate.validation_result = {**existing, "review": review}
    candidate.validation_status = "validated"
    candidate.validated_at = datetime.now(timezone.utc)
    return review


def _review_snapshot(candidate: Any) -> Dict[str, Any]:
    result = candidate.validation_result if isinstance(
        candidate.validation_result, dict) else {}
    review = result.get("review") if isinstance(
        result.get("review"), dict) else {}
    return review
def review_revision(candidate: Any) -> int:
    try:
        return int(_review_snapshot(candidate).get("review_revision") or 0)
    except (TypeError, ValueError):
        return 0


def review_revision_predicate(db: Session, revision: int):
    """DB predicate for the exact review revision; fail closed if unsupported."""
    from sqlalchemy import func, or_

    bind = db.get_bind()
    dialect = getattr(getattr(bind, "dialect", None), "name", "")
    value = int(revision)
    if dialect == "sqlite":
        extracted = func.json_extract(
            SkillCandidate.validation_result, "$.review.review_revision")
        return or_(extracted.is_(None), extracted == 0) if value == 0 \
            else extracted == value
    if dialect in ("postgresql", "postgres"):
        expression = SkillCandidate.validation_result[
            "review"]["review_revision"].as_integer()
        return or_(expression.is_(None), expression == 0) if value == 0 \
            else expression == value
    raise ValueError(
        f"review_revision_predicate_unsupported: dialect {dialect!r}")


def _default_builder():
    from core.skill_builder_service import SkillBuilderService

    root = os.getenv("ATOM_WORKSPACE_SKILLS_ROOT")
    if not root:
        data_root = os.getenv("ATOM_DATA_DIR")
        root = str(Path(data_root) / "workspaces") if data_root else None
    return SkillBuilderService(workspace_root=root) if root else SkillBuilderService()


def _yaml_frontmatter(frontmatter: Dict[str, Any]) -> str:
    try:
        import yaml

        return yaml.safe_dump(
            frontmatter, sort_keys=False, default_flow_style=False,
            allow_unicode=True).strip()
    except Exception:  # noqa: BLE001 - deterministic fallback
        return "\n".join(
            f"{key}: {json.dumps(value, ensure_ascii=True)}"
            for key, value in frontmatter.items())


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
    frontmatter = {
        "name": str(candidate.skill_name or ""),
        "description": description or instructions,
        "version": "1.0.0",
        "author": "Memento-Skills",
        "tags": ["memento", "reviewed"],
    }
    return (
        "---\n"
        f"{_yaml_frontmatter(frontmatter)}\n"
        "---\n\n"
        f"# {candidate.skill_name}\n\n"
        f"{description or instructions}\n\n"
        "## Instructions\n"
        f"{instructions}\n\n"
        "## Provenance\n"
        f"- candidate: {candidate.id}\n"
        f"- source episode: {candidate.source_episode_id}\n"
    )


def _package_dir(builder: Any, tenant_id: str, safe_name: str) -> Path:
    return Path(builder.workspace_root) / str(tenant_id) / "skills" / safe_name


def _same_package(path: Path, markdown: str) -> bool:
    skill_md = path / "SKILL.md"
    if not skill_md.is_file():
        return False
    return hashlib.sha256(skill_md.read_bytes()).hexdigest() == hashlib.sha256(
        markdown.encode("utf-8")).hexdigest()


def _applied_result(candidate: Any) -> Dict[str, Any]:
    result = candidate.validation_result if isinstance(
        candidate.validation_result, dict) else {}
    applied = result.get("applied") if isinstance(
        result.get("applied"), dict) else {}
    return {
        "schema": SKILL_APPLY_SCHEMA,
        "status": "promoted",
        "already_applied": True,
        "skill_id": applied.get("skill_id"),
        "package_path": applied.get("package_path"),
        "review_revision": applied.get("review_revision"),
        "review_digest": applied.get("review_digest"),
        "candidate_id": str(candidate.id),
    }


async def apply_reviewed_skill(
    db: Session,
    candidate: Any,
    *,
    tenant_id: str,
    workspace_id: str,
    builder: Optional[Any] = None,
    registry: Optional[Any] = None,
    reviewer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply one validated candidate atomically. Raises ValueError otherwise."""
    if candidate is None:
        raise ValueError("candidate_not_found")
    candidate_id = str(candidate.id)

    # End any stale read snapshot before re-reading the authoritative row.
    try:
        db.rollback()
    except Exception:  # noqa: BLE001 - a fresh reload is still attempted
        pass
    current = (
        db.query(type(candidate))
        .filter(type(candidate).id == candidate_id,
                type(candidate).tenant_id == tenant_id)
        .populate_existing()
        .first()
    )
    if current is None:
        raise ValueError("candidate_not_found")

    review = _review_snapshot(current)
    if not review:
        raise ValueError(
            "candidate_not_reviewed: fresh review is required before apply")
    if (str(review.get("tenant_id") or "") != str(tenant_id)
            or str(review.get("workspace_id") or "") != str(workspace_id)
            or str(review.get("agent_id") or "") != str(
                current.agent_id or "")):
        raise ValueError(
            "stale_review: reviewed scope or target changed")
    expected_digest = _binding_digest(
        current, tenant_id=tenant_id, workspace_id=workspace_id,
        agent_id=str(current.agent_id or ""))
    if str(review.get("digest") or "") != expected_digest:
        raise ValueError(
            "stale_review: reviewed material changed")
    if current.validation_status == "promoted":
        return _applied_result(current)
    if current.validation_status != "validated":
        raise ValueError(
            f"candidate_not_reviewed: status is {current.validation_status!r}")

    # Recheck the CURRENT employee, not the route's earlier read: a move after
    # authorization must not redirect the application into another workspace.
    from sqlalchemy import and_, exists
    from core.models import AgentRegistry
    agent = (
        db.query(AgentRegistry)
        .filter(AgentRegistry.id == current.agent_id)
        .populate_existing()
        .first()
    )
    if (agent is None or str(agent.tenant_id) != str(tenant_id)
            or str(agent.workspace_id) != str(workspace_id)):
        raise ValueError(
            "workspace_mismatch: target employee moved or is no longer in "
            "the reviewed workspace")

    reviewed_revision = review_revision(current)
    claimed = (
        db.query(type(current))
        .filter(
            type(current).id == candidate_id,
            type(current).tenant_id == tenant_id,
            type(current).validation_status == "validated",
            type(current).validated_at == current.validated_at,
            review_revision_predicate(db, reviewed_revision),
            exists().where(and_(
                AgentRegistry.id == type(current).agent_id,
                AgentRegistry.tenant_id == str(tenant_id),
                AgentRegistry.workspace_id == str(workspace_id),
            )),
        )
        .update({"validation_status": "applying"},
                synchronize_session=False)
    )
    if claimed != 1:
        db.rollback()
        fresh = (
            db.query(type(candidate))
            .filter(type(candidate).id == candidate_id,
                    type(candidate).tenant_id == tenant_id)
            .populate_existing()
            .first()
        )
        if fresh is not None and fresh.validation_status == "promoted":
            applied = _applied_result(fresh)
            if (applied.get("review_revision") == reviewed_revision
                    and applied.get("review_digest") == expected_digest):
                return applied
        raise ValueError(
            "candidate_state_conflict: the reviewed revision changed before "
            "the claim; reload and review again")
    db.flush()

    from core.skill_registry_service import SkillRegistryService

    builder = builder or _default_builder()
    registry = registry or SkillRegistryService(db)
    claimed_revision = reviewed_revision
    safe_name = f"{_safe_name(current.skill_name)}_r{claimed_revision}"
    markdown = _skill_markdown(current)
    final_dir = _package_dir(builder, tenant_id, safe_name)
    created = False
    package_path = final_dir
    try:
        if final_dir.exists():
            if not _same_package(final_dir, markdown):
                raise ValueError(
                    "package_conflict: existing package content differs")
        else:
            final_dir.mkdir(parents=True, exist_ok=True)
            (final_dir / "SKILL.md").write_text(markdown, encoding="utf-8")
            created = True
            if not _same_package(package_path, markdown):
                raise ValueError(
                    "skill_package_failed: generated package content differs")

        imported = await registry.import_skill(
            "raw_content", markdown,
            metadata={"author": "Memento-Skills",
                      "tags": ["memento", "reviewed"]},
            commit=False)
        registry_status = str(imported.get("status") or "")
        registry_id = str(imported.get("skill_id") or "")
        if registry_status != "Active" and registry_id:
            registry.promote_skill(registry_id, commit=False)

        from core.models import (
            Skill, SkillExecution, workspace_skills,
        )

        skill_id = str(uuid.uuid4())
        db.add(Skill(
            id=skill_id,
            tenant_id=tenant_id,
            author_tenant_id=tenant_id,
            name=safe_name,
            description=str(current.skill_description or "")[:2000],
            long_description=markdown,
            version="1.0.0",
            type="prompt",
            input_schema={},
            output_schema=None,
            config={"instructions": str(
                (current.failure_pattern or {}).get("failure_summary")
                or current.skill_description or "")[:2000]},
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
        if current.agent_id:
            execution.agent_id = str(current.agent_id)
        execution.tenant_id = tenant_id
        execution.workspace_id = workspace_id

        applied = {
            "schema": SKILL_APPLY_SCHEMA,
            "skill_id": skill_id,
            "registry_execution_id": registry_id,
            "package_path": str(package_path),
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "generated_code_applied": False,
            "review_revision": claimed_revision,
            "review_digest": review.get("digest"),
        }
        authoritative = (
            db.query(type(candidate))
            .filter(type(candidate).id == candidate_id)
            .populate_existing()
            .one()
        )
        merged = {
            **(authoritative.validation_result or {}),
            "applied": applied,
        }
        promoted = (
            db.query(type(candidate))
            .filter(
                type(candidate).id == candidate_id,
                type(candidate).tenant_id == tenant_id,
                type(candidate).validation_status == "applying",
                review_revision_predicate(db, reviewed_revision),
            )
            .update(
                {
                    "validation_status": "promoted",
                    "promoted_at": datetime.now(timezone.utc),
                    "validation_result": merged,
                },
                synchronize_session=False,
            )
        )
        if promoted != 1:
            raise ValueError(
                "candidate_state_conflict: the claimed review revision "
                "changed before promotion")
        db.commit()
        return {
            **applied,
            "status": "promoted",
            "already_applied": False,
            "candidate_id": candidate_id,
        }
    except Exception:
        db.rollback()
        if created:
            shutil.rmtree(final_dir, ignore_errors=True)
        raise
