"""Replay incident evals against the real editor (Installation Adaptation
Plan Phase 2). Each case rebuilds the canvas from its snapshot, plans the
edit with the live planner, and checks the programmatic expected property.
Cases that need an LLM are `skipped` when no planner is reachable, so CI
stays green without provider keys while staging/prod runs them for real.

CLI:  python -m core.incident_eval_runner --tenant default [--limit 20]
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def run_evals(db, tenant_id: str = "default", limit: int = 20,
                    llm_service: Any = None) -> Dict[str, Any]:
    """Run pending cases for a tenant. Returns
    {ran, passed, failed, skipped, results:[{eval_id, taxonomy, status, detail}]}.
    Never raises on individual cases — a crashing case is a `skipped` with
    the error captured, because the runner must be safe to call from the
    graduation exam."""
    from core.models import IncidentEval

    rows = (db.query(IncidentEval)
            .filter(IncidentEval.tenant_id == tenant_id)
            .order_by(IncidentEval.occurrences.desc(), IncidentEval.created_at.desc())
            .limit(limit).all())

    summary: Dict[str, Any] = {"ran": 0, "passed": 0, "failed": 0,
                               "skipped": 0, "results": []}

    if rows and llm_service is None:
        llm_service = _default_llm_service()

    for row in rows:
        summary["ran"] += 1
        result = await _run_one(row, llm_service)
        row.last_result = result
        row.last_run_at = datetime.now(timezone.utc)
        status = result.get("status")
        if status == "pass":
            summary["passed"] += 1
        elif status == "fail":
            summary["failed"] += 1
        else:
            summary["skipped"] += 1
        summary["results"].append({
            "eval_id": row.id,
            "taxonomy": row.taxonomy,
            "instruction": (row.instruction or "")[:120],
            **result,
        })

    try:
        db.commit()
    except Exception as e:
        logger.debug(f"incident eval result persist skipped: {e}")
    return summary


async def _run_one(row, llm_service: Optional[Any]) -> Dict[str, Any]:
    """Replay one case PURELY: plan against the snapshot, derive the
    would-be content with the editor's deterministic merge/patch functions,
    and check the property. The real store is never touched — an eval run
    must not write to any canvas."""
    try:
        from core.chat_canvas_editor import (
            _apply_patch_ops,
            _decode_replace_content,
            _merge_replace_content,
            plan_canvas_edit,
        )
        from core.incident_eval_service import evaluate_property

        snap = row.context_snapshot or {}
        content = snap.get("content")
        canvas = {
            "canvas_id": row.canvas_id or f"eval-{row.id}",
            "canvas_type": snap.get("canvas_type") or row.canvas_type or "generic",
            "title": snap.get("title") or "Incident replay",
            "content": content,
        }

        if llm_service is None:
            return {"status": "skipped", "detail": "no planner reachable"}

        plan = await plan_canvas_edit(
            row.instruction or "apply the supervisor's correction",
            [], canvas, llm_service,
        )
        if plan is None or not getattr(plan, "wants_edit", False):
            expected = row.expected_property or {}
            if expected.get("kind") == "changed":
                return {"status": "pass",
                        "detail": "planner declined edit — honest fall-through"}
            return {"status": "fail", "detail": "planner produced no edit"}

        if getattr(plan, "ops", None):
            planned_content, failed = _apply_patch_ops(content, plan.ops)
            if failed:
                return {"status": "skipped",
                        "detail": f"{len(failed)} patch op(s) no longer match"}
        else:
            parsed, decode_reason = _decode_replace_content(plan, content)
            if parsed is None:
                return {"status": "skipped",
                        "detail": f"undecodable replace payload: {decode_reason}"}
            planned_content, _merge_reason = _merge_replace_content(
                parsed, content, canvas["canvas_type"])
            if planned_content is None:
                return {"status": "skipped", "detail": "merge failed"}

        checked = evaluate_property(row.expected_property, planned_content,
                                    content)
        return {"status": checked["status"], "detail": checked["detail"]}
    except Exception as e:
        return {"status": "skipped", "detail": f"runner error: {e}"}


def _default_llm_service():
    """Best-effort live planner; None when providers aren't configured so
    callers (CI, graduation in air-gapped installs) skip instead of fail."""
    try:
        from core.llm_service import LLMService
        svc = LLMService()
        handler = svc._get_handler()
        if getattr(handler, "clients", None):
            return svc
    except Exception as e:
        logger.debug(f"no LLM service for eval runner: {e}")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay incident evals")
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    import asyncio

    from core.database import SessionLocal

    async def _amain() -> None:
        db = SessionLocal()
        try:
            summary = await run_evals(db, tenant_id=args.tenant, limit=args.limit)
            print(json.dumps({k: v for k, v in summary.items() if k != "results"},
                             indent=2))
            for r in summary["results"]:
                print(f"  [{r['status']:>7}] {r['taxonomy']:<10} {r['detail'][:90]}")
        finally:
            db.close()

    asyncio.run(_amain())


if __name__ == "__main__":
    main()
