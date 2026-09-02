"""Transfer safety for imported experience — the WikiSkill W6 negative-
transfer guard.

The paper's starkest failure mode: skills evolved by a weak model, applied
to a strong model, can be catastrophic (Qwen-4B skills dropped Gemini's
SpreadSheet score 50.5%→18.1% — the imported skills encoded low-level
workarounds and fragmented diagnostics that exhausted the interaction
budget). "Skills developed by one model often transfer to another … but
this isn't guaranteed, so it should be checked case by case."

Atom's rule, then: an imported ExperienceItem NEVER becomes consumable by
assignment — it is quarantined (``validation_state="pending"``) at import
and must be validated ON THE RECEIVING INSTALLATION before activation:

* advisory kinds (``pattern`` / ``canvas_lesson`` / ``fact``) auto-activate
  once the receiving tenant's incident-eval corpus replays without a
  single FAIL (skips don't block — unrunnable cases are not evidence);
* ``skill`` items — the catastrophic class in the paper — always wait for
  explicit human review (:func:`activate_item` / :func:`reject_item`).

``list_active_items`` is the only sanctioned read path for consumers; it
returns legacy rows (``validation_state IS NULL``) for backward
compatibility and never returns quarantined/rejected ones.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

AUTO_VALIDATABLE_KINDS = ("pattern", "canvas_lesson", "fact")
HUMAN_REVIEW_KINDS = ("skill",)


def list_active_items(db: Any, workspace_id: str,
                      source_agent_id: Optional[str] = None,
                      kind: Optional[str] = None,
                      limit: int = 500) -> List[Any]:
    """Validated (or legacy) non-superseded items — the consumer surface.
    Quarantined (``pending``) and ``rejected`` items are never returned."""
    from core.models import ExperienceItem

    q = db.query(ExperienceItem).filter(
        ExperienceItem.workspace_id == workspace_id,
        ExperienceItem.superseded_at.is_(None),
        (ExperienceItem.validation_state.is_(None))
        | (ExperienceItem.validation_state == "active"),
    )
    if source_agent_id:
        q = q.filter(ExperienceItem.source_agent_id == source_agent_id)
    if kind:
        q = q.filter(ExperienceItem.kind == kind)
    return q.order_by(ExperienceItem.updated_at.desc()).limit(limit).all()


def pending_items(db: Any, workspace_id: Optional[str] = None,
                  source_agent_id: Optional[str] = None,
                  limit: int = 200) -> List[Any]:
    from core.models import ExperienceItem

    q = db.query(ExperienceItem).filter(
        ExperienceItem.validation_state == "pending",
        ExperienceItem.superseded_at.is_(None),
    )
    if workspace_id:
        q = q.filter(ExperienceItem.workspace_id == workspace_id)
    if source_agent_id:
        q = q.filter(ExperienceItem.source_agent_id == source_agent_id)
    return q.order_by(ExperienceItem.created_at.asc()).limit(limit).all()


def _set_state(db: Any, item_pk: str, workspace_id: str,
               state: str) -> bool:
    from core.models import ExperienceItem

    row = db.query(ExperienceItem).filter(
        ExperienceItem.id == item_pk,
        ExperienceItem.workspace_id == workspace_id,
    ).first()
    if row is None:
        return False
    row.validation_state = state
    db.commit()
    return True


def activate_item(db: Any, workspace_id: str, item_pk: str) -> bool:
    """Explicit human activation (the skill-kind path out of quarantine)."""
    return _set_state(db, item_pk, workspace_id, "active")


def reject_item(db: Any, workspace_id: str, item_pk: str) -> bool:
    """Explicit rejection — negative transfer suspected; the row stays for
    audit but is never consumable."""
    return _set_state(db, item_pk, workspace_id, "rejected")


async def auto_validate_import(
    db: Any,
    workspace_id: str,
    tenant_id: Optional[str],
    source_agent_id: Optional[str] = None,
    llm_service: Any = None,
) -> Dict[str, Any]:
    """Validate one import cohort against the receiving installation.

    Replays the tenant's incident evals; while the corpus is clean, advisory
    kinds auto-activate. ``skill`` items always remain for human review.
    Never raises — called from the sleep-time maintenance loop.
    """
    out: Dict[str, Any] = {"activated": 0, "held": 0, "reason": None}
    rows = pending_items(db, workspace_id=workspace_id,
                         source_agent_id=source_agent_id)
    if not rows:
        return out

    clean = True
    try:
        from core.incident_eval_runner import run_evals

        summary = await run_evals(db, tenant_id=tenant_id or "default",
                                  limit=20, llm_service=llm_service)
        failed = summary.get("failed", 0)
        if failed:
            clean = False
            out["reason"] = f"incident_evals_failing ({failed})"
    except Exception as e:
        # A broken eval corpus is not evidence of a bad import, but with
        # nothing to validate against, advisory auto-activation would be a
        # leap — hold the cohort; explicit review can still activate.
        clean = False
        out["reason"] = f"eval_replay_unavailable ({e})"

    for row in rows:
        if clean and (row.kind or "") in AUTO_VALIDATABLE_KINDS:
            row.validation_state = "active"
            out["activated"] += 1
        else:
            out["held"] += 1
    db.commit()
    return out


async def validate_pending_imports(db: Any, llm_service: Any = None,
                                   max_cohorts: int = 3) -> List[Dict[str, Any]]:
    """Maintenance-loop entry: validate every quarantine cohort (oldest
    first, capped per cycle). Returns one summary dict per cohort."""
    from core.models import ExperienceItem

    cohort_rows = (
        db.query(ExperienceItem.workspace_id, ExperienceItem.tenant_id,
                 ExperienceItem.source_agent_id)
        .filter(ExperienceItem.validation_state == "pending",
                ExperienceItem.superseded_at.is_(None))
        .distinct()
        .limit(max_cohorts)
        .all()
    )
    results: List[Dict[str, Any]] = []
    for workspace_id, tenant_id, source_agent_id in cohort_rows:
        try:
            res = await auto_validate_import(
                db, workspace_id, tenant_id,
                source_agent_id=source_agent_id, llm_service=llm_service)
            res.update({"workspace_id": workspace_id,
                        "source_agent_id": source_agent_id})
            results.append(res)
        except Exception as e:
            logger.debug("import validation skipped for cohort: %s", e)
    return results
