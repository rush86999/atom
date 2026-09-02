"""Incident evals — live failures as replayable regression cases
(Installation Adaptation Plan Phase 2). Every supervisor correction yields
one deterministic case: the snapshot the failed draft was planned against,
the instruction, and a PROGRAMMATIC expected property (no LLM-judge) — the
Promptfoo "production failure → test case" pattern, in-repo.

Generation hooks into the correction-capture path
(CanvasContextService.record_user_correction → generate_from_correction);
replay lives in core/incident_eval_runner.py.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.failure_taxonomy import classify_correction, property_for

logger = logging.getLogger(__name__)


def _fingerprint(canvas_id: str, taxonomy: str, value: str) -> str:
    raw = f"{canvas_id}|{taxonomy}|{value}"
    return hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()


def generate_from_correction(
    db,
    tenant_id: str,
    canvas_id: str,
    canvas_type: str,
    snapshot: Dict[str, Any],
    original: Any,
    corrected: Any,
    instruction: Optional[str] = None,
) -> Optional[Any]:
    """Create-or-bump the IncidentEval for one correction. The snapshot is
    the canvas state the FAILED draft was planned against: {canvas_type,
    title, content}. Fault-isolated by the caller; returns the row."""
    from core.models import IncidentEval

    taxonomy, _signals = classify_correction(original, corrected)
    prop = property_for(taxonomy, original, corrected)
    fp = _fingerprint(canvas_id, taxonomy, str(prop.get("value") or ""))

    existing = db.query(IncidentEval).filter(
        IncidentEval.fingerprint == fp,
        IncidentEval.tenant_id == tenant_id,
    ).first()
    if existing is not None:
        existing.occurrences = (existing.occurrences or 1) + 1
        db.commit()
        return existing

    row = IncidentEval(
        tenant_id=tenant_id,
        canvas_id=canvas_id,
        canvas_type=canvas_type,
        taxonomy=taxonomy,
        instruction=instruction,
        context_snapshot=snapshot or {},
        expected_property=prop,
        source="correction",
        fingerprint=fp,
    )
    db.add(row)
    db.commit()
    logger.info(
        f"incident eval generated: canvas={canvas_id} class={taxonomy} "
        f"property={prop.get('kind')}"
    )
    return row


# ─────────────── property evaluation (deterministic) ───────────────

def evaluate_property(expected: Dict[str, Any], planned_content: Any,
                      snapshot_content: Any,
                      reported_no_change: bool = False) -> Dict[str, Any]:
    """Check a planned edit against the case's expected property.
    Returns {status: pass|fail, detail}."""
    from core.failure_taxonomy import _plain

    kind = (expected or {}).get("kind")
    value = str((expected or {}).get("value") or "")
    planned = _plain(planned_content)
    snapshot = _plain(snapshot_content)

    if kind == "changed":
        if reported_no_change or planned != snapshot:
            return {"status": "pass", "detail": "output differs or honest no-change"}
        return {"status": "fail", "detail": "planned content is byte-identical to input"}

    if kind == "excludes":
        if not value:
            return {"status": "pass", "detail": "no distinctive token to exclude"}
        if value.lower() in planned.lower():
            return {"status": "fail", "detail": f"forbidden token present: {value!r}"}
        return {"status": "pass", "detail": f"forbidden token absent: {value!r}"}

    if kind == "includes":
        if not value:
            return {"status": "pass", "detail": "no template line recorded"}
        if value.lower() in planned.lower():
            return {"status": "pass", "detail": "template line present"}
        return {"status": "fail", "detail": f"template line missing: {value!r}"}

    if kind == "no_unverified":
        from core.failure_taxonomy import _ASSERT_RE, _HEDGE_RE
        if not value:
            return {"status": "pass", "detail": "no assertion recorded"}
        # The softened claim must not reappear assertively: either the
        # claim text is gone, or every occurrence sits near a hedge.
        for m in _ASSERT_RE.finditer(planned):
            window = planned[max(0, m.start() - 120):m.end() + 120]
            if value.lower() in window.lower() and not _HEDGE_RE.search(window):
                return {"status": "fail",
                        "detail": f"assertive claim without hedge: {value!r}"}
        return {"status": "pass", "detail": "claim hedged or absent"}

    return {"status": "pass", "detail": f"unknown kind {kind!r} — vacuous"}
