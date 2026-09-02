"""Installation metrics — the trust-ramp dashboard numbers (Installation
Adaptation Plan Phase 5), computed from stores that already exist:

  corrections_per_10_turns — supervisor intervention density
  taxonomy_distribution    — WHAT the install corrects (failure classes)
  repeated_feedback_rate   — same instruction twice = the agent didn't land
                             the first one (process failure)
  playbook_stats           — capture pipeline health (drafts waiting)
  eval_summary             — last replay results (pass/fail/skipped)

No new event tables: everything derives from canvas_contexts
(user_corrections), incident_evals, playbooks, chat_messages. Metrics that
need future signal (no-op claim rate post-fix, grounding coverage) appear
once their sources accumulate and read 0/absent meanwhile.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def report(db, tenant_id: str = "default",
           window_days: int = 30) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "window_days": window_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    for name, fn in (
        ("corrections", _correction_stats),
        ("repeated_feedback", _repeated_feedback),
        ("playbooks", _playbook_stats),
        ("evals", _eval_summary),
    ):
        try:
            out[name] = fn(db, tenant_id, window_days)
        except Exception as e:
            logger.debug(f"install metrics[{name}] skipped: {e}")
            out[name] = None
    return out


def _correction_stats(db, tenant_id: str, window_days: int) -> Dict[str, Any]:
    """Corrections + their taxonomy distribution, from incident_evals
    (Phase 2 stamps every correction) and canvas_contexts as the base."""
    from core.models import CanvasContext, IncidentEval

    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    evals = (db.query(IncidentEval)
             .filter(IncidentEval.tenant_id == tenant_id,
                     IncidentEval.created_at >= since).all())
    distribution: Dict[str, int] = Counter(
        (e.taxonomy or "other") for e in evals)

    contexts = (db.query(CanvasContext)
                .filter(CanvasContext.tenant_id == tenant_id).all())
    total_corrections = sum(len(c.user_corrections or []) for c in contexts)

    # Chat turn density over the window (user messages as a turn proxy).
    from core.models import ChatMessage
    turns = (db.query(ChatMessage)
             .filter(ChatMessage.tenant_id == tenant_id,
                     ChatMessage.role == "user",
                     ChatMessage.created_at >= since).count())
    per_10 = round(total_corrections * 10.0 / turns, 2) if turns else None

    return {
        "total_all_time": total_corrections,
        "window_turns": turns,
        "corrections_per_10_turns_window": per_10,
        "taxonomy_distribution_window": dict(distribution),
    }


def _repeated_feedback(db, tenant_id: str, window_days: int) -> Dict[str, Any]:
    """Consecutive identical user messages in the same conversation — the
    strongest single signal that a correction didn't land (the da27bb76
    'nothing changed' x3 pattern). Normalized text compare."""
    from core.models import ChatMessage

    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    msgs = (db.query(ChatMessage)
            .filter(ChatMessage.tenant_id == tenant_id,
                    ChatMessage.role == "user",
                    ChatMessage.created_at >= since)
            .order_by(ChatMessage.conversation_id, ChatMessage.created_at)
            .all())

    def norm(t: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", (t or "").lower()).strip()

    repeats = 0
    prev_conv, prev_text = None, None
    for m in msgs:
        text = norm(m.content)
        if m.conversation_id == prev_conv and text and text == prev_text:
            repeats += 1
        prev_conv, prev_text = m.conversation_id, text
    total = len(msgs)
    return {
        "window_user_messages": total,
        "repeats": repeats,
        "rate": round(repeats / total, 4) if total else None,
    }


def _playbook_stats(db, tenant_id: str, window_days: int) -> Dict[str, Any]:
    from core.models import Playbook

    rows = (db.query(Playbook)
            .filter(Playbook.tenant_id == tenant_id).all())
    by_state: Dict[str, int] = Counter(r.approval_state or "draft" for r in rows)
    by_source: Dict[str, int] = Counter(r.source or "authored" for r in rows)
    return {
        "total": len(rows),
        "by_approval_state": dict(by_state),
        "by_source": dict(by_source),
        "drafts_awaiting_approval": by_state.get("draft", 0),
    }


def _eval_summary(db, tenant_id: str, window_days: int) -> Dict[str, Any]:
    from core.models import IncidentEval

    rows = (db.query(IncidentEval)
            .filter(IncidentEval.tenant_id == tenant_id).all())
    ran = [r for r in rows if (r.last_result or {}).get("status")]
    by_status: Dict[str, int] = Counter(
        (r.last_result or {}).get("status", "not_run") for r in rows)
    return {
        "total_cases": len(rows),
        "never_run": sum(1 for r in rows if not (r.last_result or {}).get("status")),
        "by_status": dict(by_status),
    }
