"""Decision-plane certification automation (Phase 5).

Consent-gated certification for the three shadow surfaces (intent / turn /
gate), mirroring ``stage_router_automation`` + trust-calibration automation:
- ``run_automation_pass`` evaluates each surface's audit rows against its
  gate. READY → ``certify`` action (``approval`` state, or ``applied`` in
  ``auto`` mode). An enforced surface whose stats regress → ``revoke``
  action, ALWAYS auto-applied whatever the mode (fail-safe).
- ``resolve_decision_enforce`` is the single read path: env hard-switch
  (``ATOM_OLLAYA_FORCE_ENFORCE``) wins, else the latest applied ledger row.
- ``decision_status`` reports off/collecting/ready/enforced + next action.
- Act-rules (``intent_should_act`` etc.) are pure threshold functions. No
  prod path acts on them yet — they exist so the first enforcement has a
  tested shape.

Conventions: never raises (automation degrades to no-ops), tables
self-provision (decision-table precedent), monotonic int PK ledger.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_automation_task = None

# Certification gates (mirror the calibrator defaults / trust convention).
INTENT_MIN_ROWS = 30
INTENT_MIN_AGREEMENT = 0.8
INTENT_MAX_BRIER = 0.25


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

def _auto_enforce_mode() -> str:
    try:
        from core.runtime_settings import get_setting
        mode = str(get_setting("ATOM_DECISION_AUTO_ENFORCE", "off") or "off")
        return mode.strip().lower() if mode.strip().lower() in (
            "off", "notify", "approve", "auto") else "off"
    except Exception:
        return "off"


def _force_enforce() -> bool:
    try:
        from core.runtime_settings import get_bool_setting
        return bool(get_bool_setting("ATOM_OLLAYA_FORCE_ENFORCE", False))
    except Exception:
        return False


def intent_act_threshold() -> float:
    try:
        from core.runtime_settings import get_float_setting
        return float(get_float_setting("ATOM_OLLAYA_INTENT_ACT_THRESHOLD", 0.6))
    except Exception:
        return 0.6


def automation_interval_min() -> float:
    try:
        from core.runtime_settings import get_float_setting
        return float(get_float_setting("ATOM_DECISION_AUTO_INTERVAL_MIN", 60.0))
    except Exception:
        return 60.0


# ---------------------------------------------------------------------------
# Pure act-rules (tested shape for the first enforcement; unused by prod yet)
# ---------------------------------------------------------------------------

def intent_should_act(choice: Optional[str], confidence: Optional[float],
                      threshold: float) -> bool:
    try:
        return (choice in ("chat", "workflow", "task")
                and confidence is not None and float(confidence) >= float(threshold))
    except Exception:
        return False


def gate_should_block(verdict: Optional[str], confidence: Optional[float],
                      threshold: float) -> bool:
    try:
        return (verdict == "block" and confidence is not None
                and float(confidence) >= float(threshold))
    except Exception:
        return False


def turn_should_skip_extraction(prob: Optional[float], threshold: float) -> bool:
    try:
        return prob is not None and float(prob) <= float(threshold)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def _ensure_table(session) -> None:
    from core.models import DecisionAutomationAction
    try:
        DecisionAutomationAction.__table__.create(bind=session.get_bind(),
                                                  checkfirst=True)
    except Exception:
        pass


def _row_to_dict(row) -> Dict[str, Any]:
    return {"id": row.id, "surface": row.surface, "verdict": row.verdict,
            "mode": row.mode, "state": row.state, "stats": row.stats_json,
            "created_at": str(row.created_at), "decided_at": str(row.decided_at)}


def _write_action(session, surface: str, verdict: str, mode: str,
                  stats: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from core.models import DecisionAutomationAction
    _ensure_table(session)
    row = DecisionAutomationAction(surface=surface, verdict=verdict, mode=mode,
                                   state="approval", stats_json=stats or {})
    session.add(row)
    session.commit()
    return _row_to_dict(row)


def _latest_action(session, surface: str):
    from core.models import DecisionAutomationAction
    _ensure_table(session)
    return (session.query(DecisionAutomationAction)
            .filter(DecisionAutomationAction.surface == surface)
            .order_by(DecisionAutomationAction.id.desc()).first())


def approve_action(session, action_id: int) -> bool:
    """Apply an approval-queued action. Never raises."""
    try:
        from core.models import DecisionAutomationAction
        row = (session.query(DecisionAutomationAction)
               .filter(DecisionAutomationAction.id == action_id).first())
        if row is None or row.state != "approval":
            return False
        row.state = "applied"
        row.decided_at = datetime.now(timezone.utc)
        session.commit()
        return True
    except Exception as exc:
        logger.warning("[DecisionAutomation] approve failed (%s)", type(exc).__name__)
        try:
            session.rollback()
        except Exception:
            pass
        return False


def reject_action(session, action_id: int) -> bool:
    """Reject an approval-queued action. Never raises."""
    try:
        from core.models import DecisionAutomationAction
        row = (session.query(DecisionAutomationAction)
               .filter(DecisionAutomationAction.id == action_id).first())
        if row is None or row.state != "approval":
            return False
        row.state = "rejected"
        row.decided_at = datetime.now(timezone.utc)
        session.commit()
        return True
    except Exception as exc:
        logger.warning("[DecisionAutomation] reject failed (%s)", type(exc).__name__)
        try:
            session.rollback()
        except Exception:
            pass
        return False


def resolve_decision_enforce(session, surface: str) -> bool:
    """Single read path: env hard-switch wins, else latest applied row."""
    try:
        if _force_enforce():
            return True
        latest = _latest_action(session, surface)
        if latest is not None and latest.state == "applied":
            return latest.verdict == "certify"
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Stats + automation pass
# ---------------------------------------------------------------------------

def _intent_stats(session) -> Dict[str, Any]:
    from core.models import DecisionRouterAudit
    try:
        rows = (session.query(DecisionRouterAudit)
                .filter(DecisionRouterAudit.surface == "intent").all())
    except Exception:
        rows = []
    decided = [r for r in rows if r.ollaya_choice is not None
               and r.ollaya_confidence is not None]
    n = len(decided)
    if not n:
        return {"n": 0, "agreement": 0.0, "brier": None}
    agreement = sum(1 for r in decided if r.agreement) / n
    brier = sum(((r.ollaya_confidence or 0.0) - (1.0 if r.agreement else 0.0)) ** 2
                for r in decided) / n
    return {"n": n, "agreement": round(agreement, 3), "brier": round(brier, 3)}


def _intent_ready(stats: Dict[str, Any]) -> bool:
    return (stats["n"] >= INTENT_MIN_ROWS
            and stats["agreement"] >= INTENT_MIN_AGREEMENT
            and stats["brier"] is not None and stats["brier"] <= INTENT_MAX_BRIER)


def run_automation_pass(session=None, mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Evaluate surfaces, write certify/revoke actions. Never raises.

    Turn + gate surfaces always HOLD (no certifiable ground truth yet:
    turn needs the facts outcome-join at volume, gate needs violation-join
    review) — recorded here explicitly so the pass stays honest.
    """
    owned = None
    actions: List[Dict[str, Any]] = []
    try:
        if session is None:
            from core.database import SessionLocal
            owned = SessionLocal()
            session = owned
        mode = (mode or _auto_enforce_mode()).strip().lower()
        if mode == "off":
            return []

        stats = _intent_stats(session)
        ready = _intent_ready(stats)
        enforced = resolve_decision_enforce(session, "intent")

        if ready and not enforced:
            action = _write_action(session, "intent", "certify", mode, stats)
            if mode == "auto":
                approve_action(session, action["id"])
                action = _row_to_dict(_latest_action(session, "intent"))
            actions.append(action)
        elif not ready and enforced:
            # Regression on a live surface: revoke immediately, any mode.
            action = _write_action(session, "intent", "revoke", mode,
                                   {**stats, "reason": "stats regressed below gate"})
            approve_action(session, action["id"])
            action = _row_to_dict(_latest_action(session, "intent"))
            actions.append(action)
        return actions
    except Exception as exc:
        logger.warning("[DecisionAutomation] pass failed (%s: %s)",
                       type(exc).__name__, exc)
        return []
    finally:
        try:
            if owned is not None:
                owned.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Operator status
# ---------------------------------------------------------------------------

def _count(session, model, surface: str) -> int:
    try:
        return session.query(model).filter(model.surface == surface).count()
    except Exception:
        return 0


def get_automation_status(session) -> Dict[str, Any]:
    """Admin automation view: mode, pending queue, latest action per surface."""
    from core.models import DecisionAutomationAction
    try:
        _ensure_table(session)
        pending = (session.query(DecisionAutomationAction)
                   .filter(DecisionAutomationAction.state == "approval")
                   .order_by(DecisionAutomationAction.id).all())
        latest: Dict[str, Any] = {}
        for surface in ("intent", "turn", "gate"):
            row = _latest_action(session, surface)
            if row is not None:
                latest[surface] = _row_to_dict(row)
        return {"mode": _auto_enforce_mode(),
                "pending": [_row_to_dict(r) for r in pending],
                "latest": latest}
    except Exception as exc:
        logger.warning("[DecisionAutomation] status failed (%s)", type(exc).__name__)
        return {"mode": _auto_enforce_mode(), "pending": [], "latest": {},
                "error": "unavailable"}


def _probe_audit_tables(session) -> str:
    """ok | missing | broken — distinguishes 'no shadow traffic yet'
    (table absent, self-provision will create it) from a dead database."""
    try:
        from core.models import DecisionRouterAudit
        session.query(DecisionRouterAudit).limit(0).all()
        return "ok"
    except Exception as exc:
        msg = str(exc).lower()
        if "no such table" in msg or "does not exist" in msg or "undefinedtable" in msg:
            return "missing"
        return "broken"


def decision_status(session) -> Dict[str, Any]:
    """off/collecting/ready/enforced + next action. Never raises."""
    try:
        ensure_automation_task()  # lazy schedule (mirrors stage-router status)
    except Exception:
        pass
    from core import decision_service as ds
    config = {"enabled": False, "force_enforce": False,
              "mode": _auto_enforce_mode(),
              "intent_act_threshold": intent_act_threshold()}
    try:
        config["enabled"] = bool(ds.ollaya_enabled())
        config["force_enforce"] = bool(_force_enforce())
    except Exception:
        pass
    try:
        from core.models import (DecisionRouterAudit, DecisionTurnAudit,
                                 DecisionGateAudit)
        probe = _probe_audit_tables(session)
        if probe == "broken":
            return {**config, "phase": "error",
                    "next_action": "Status unavailable — the audit tables are "
                                   "unreadable. Check DB connectivity; shadows keep "
                                   "serving (they degrade to skips).",
                    "surfaces": {}}
        surfaces = {
            "intent": {"rows": _count(session, DecisionRouterAudit, "intent")},
            "turn": {"rows": _count(session, DecisionTurnAudit, "turn")},
            "gate": {"rows": _count(session, DecisionGateAudit, "gate")},
        }
        stats = _intent_stats(session)
        enforced = any(resolve_decision_enforce(session, s) for s in surfaces)
    except Exception:
        return {**config, "phase": "error",
                "next_action": "Status unavailable — check the decision audit tables exist "
                               "(they self-provision on first shadow write).",
                "surfaces": {}}
    if not config["enabled"]:
        return {**config, "phase": "off", "surfaces": surfaces,
                "next_action": "Set ATOM_OLLAYA_ENABLED=true + a SHADOW flag to start "
                               "audit-only telemetry (model selection untouched)."}
    if enforced:
        return {**config, "phase": "enforced", "surfaces": surfaces,
                "next_action": "Live enforcement active. Keep shadows on and re-run "
                               "scripts/calibrate_decision_router.py periodically. "
                               "Kill switch: ATOM_OLLAYA_FORCE_ENFORCE=false + revoke."}
    if _intent_ready(stats):
        return {**config, "phase": "ready", "surfaces": surfaces,
                "intent_stats": stats,
                "next_action": "Intent surface clears the gate: run the automation pass "
                               "(approve mode) or review scripts/calibrate_decision_router.py, "
                               "then approve the certify action."}
    return {**config, "phase": "collecting", "surfaces": surfaces,
            "intent_stats": stats,
            "next_action": "Shadow is recording. Drive traffic until intent n>=30, then "
                           "re-run calibration. Turn/gate need their outcome joins at volume."}


# ---------------------------------------------------------------------------
# Background loop (fully automated passes; consent-gated actions only)
# ---------------------------------------------------------------------------

async def decision_automation_loop() -> None:
    """Periodic certification pass. Failures are logged, never raised.

    Each tick runs run_automation_pass with an owned session: READY surfaces
    queue certify approvals (or auto-apply in auto mode), regressed enforced
    surfaces auto-revoke in ANY mode. Off mode = tick is a no-op.
    """
    while True:
        try:
            await asyncio.sleep(max(automation_interval_min(), 0.5) * 60)
            run_automation_pass()
        except asyncio.CancelledError:
            break
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Decision automation loop iteration failed: {e}")


def ensure_automation_task() -> None:
    """Lazily start the background loop (mirrors stage-router pattern)."""
    global _automation_task
    if _automation_task is not None or _auto_enforce_mode() == "off":
        return
    try:
        from core.asyncio_compat import get_event_loop
        loop = get_event_loop()
        if loop.is_running():
            _automation_task = loop.create_task(decision_automation_loop())
    except Exception as e:
        logger.warning(f"Could not start decision automation loop: {e}")


# ---------------------------------------------------------------------------
# Human ground-truth labels (correctness, not agreement)
# ---------------------------------------------------------------------------

def record_intent_label(session, audit_id: str, input_hash: str,
                        llm_correct: bool | None, ollaya_correct: bool | None,
                        labeler: str = "human") -> bool:
    """Store one human label. Never raises; False = skipped."""
    try:
        from core.models import DecisionIntentLabel, DecisionAutomationAction
        DecisionIntentLabel.__table__.create(bind=session.get_bind(), checkfirst=True)
        existing = (session.query(DecisionIntentLabel)
                    .filter(DecisionIntentLabel.audit_id == audit_id).first())
        if existing is not None:
            existing.llm_correct = llm_correct
            existing.ollaya_correct = ollaya_correct
            existing.labeler = labeler
        else:
            session.add(DecisionIntentLabel(
                audit_id=audit_id, input_hash=input_hash,
                llm_correct=llm_correct, ollaya_correct=ollaya_correct,
                labeler=labeler))
        session.commit()
        return True
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning("[DecisionAutomation] label failed (%s)",
                                             type(exc).__name__)
        try:
            session.rollback()
        except Exception:
            pass
        return False


def label_accuracy(session) -> dict:
    """Per-model accuracy over human labels. Empty dict when unlabeled."""
    try:
        from core.models import DecisionIntentLabel
        rows = session.query(DecisionIntentLabel).all()
    except Exception:
        return {}
    llm = [r.llm_correct for r in rows if r.llm_correct is not None]
    oll = [r.ollaya_correct for r in rows if r.ollaya_correct is not None]
    out = {"n": len(rows)}
    if llm:
        out["llm_accuracy"] = round(sum(1 for v in llm if v) / len(llm), 3)
        out["llm_n"] = len(llm)
    if oll:
        out["ollaya_accuracy"] = round(sum(1 for v in oll if v) / len(oll), 3)
        out["ollaya_n"] = len(oll)
    return out
