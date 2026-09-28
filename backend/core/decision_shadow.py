"""Intent-routing shadow hook (Phase 2).

Compares the incumbent classifier (LLM or heuristic) against the local
decision model without changing any response: every call records a
``DecisionRouterAudit`` row (would-have pick vs what actually ran) for
offline calibration. Shadow-only — ``enforced`` is always False.

Conventions (mirrors turn_fact_extractor + stage_router):
- NEVER raises. All public entry points catch everything → skip (None).
- Opt-in via ``ATOM_OLLAYA_SHADOW_INTENT`` (default off) AND the master
  ``ATOM_OLLAYA_ENABLED`` switch.
- No raw request text in the DB — ``input_hash`` only (PHI hygiene).
- Fire-and-forget from the classify path (own DB session); sync version for
  tests and live verification.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import weakref

logger = logging.getLogger(__name__)

# Bare create_task handles would warn "pending task destroyed" in tests and
# leak on shutdown; track + discard like the extractor's _pending_* sets.
_pending_turn_tasks: set = set()


def shadow_enabled() -> bool:
    try:
        from core.runtime_settings import get_bool_setting
        return bool(get_bool_setting("ATOM_OLLAYA_SHADOW_INTENT", False))
    except Exception:
        return False


def shadow_enabled_turn() -> bool:
    try:
        from core.runtime_settings import get_bool_setting
        return bool(get_bool_setting("ATOM_OLLAYA_SHADOW_TURN", False))
    except Exception:
        return False


def _decide(state, questions: dict, timeout_s: float = 30.0) -> dict:
    """Thin wrapper over DecisionService (patch point for tests).

    Generous default budget: shadow runs fire-and-forget in the background,
    so it can ride out cold model loads (~5s) that inline callers must skip.
    Hot-path callers (gate) pass their own tight budget.
    """
    from core import decision_service as ds
    return ds.decide(state, questions=questions, timeout_s=timeout_s)


def _normalize(text: object) -> str:
    return " ".join(str(text).lower().split())


def build_intent_audit_record(user_request: str, llm_category: str,
                              llm_confidence: float, decide_result: dict) -> dict:
    """Pure builder: incumbent pick + decision-model pick → audit record dict."""
    from core.decision_questions import INTENT_CHOICE_TO_CATEGORY

    answers = (decide_result or {}).get("answers", {})
    intent = answers.get("intent", {}) if isinstance(answers, dict) else {}
    choice = intent.get("choice") if isinstance(intent, dict) else None
    if choice not in INTENT_CHOICE_TO_CATEGORY:
        choice = None
    mapped = INTENT_CHOICE_TO_CATEGORY.get(choice) if choice else None
    return {
        "surface": "intent",
        "input_hash": hashlib.sha256(_normalize(user_request).encode()).hexdigest(),
        "llm_category": str(llm_category),
        "llm_confidence": float(llm_confidence),
        "ollaya_choice": mapped,
        "ollaya_confidence": float(intent.get("confidence", 0.0)) if choice else None,
        "agreement": bool(mapped is not None and mapped == str(llm_category)),
        "ollaya_latency_ms": float((decide_result or {}).get("latency_ms", 0.0)),
        "model": str((decide_result or {}).get("model", "")),
        "enforced": False,
    }


def _persist(session, record: dict) -> None:
    """Self-provisioning insert (trust-calibration precedent: no alembic chain
    risk for shadow audit tables). Raises on DB errors (caller converts)."""
    from core.models import DecisionRouterAudit

    try:
        DecisionRouterAudit.__table__.create(bind=session.get_bind(), checkfirst=True)
    except Exception:
        pass  # table likely exists; the insert is the real check
    row = DecisionRouterAudit(
        workspace_id=record.get("workspace_id"),
        surface=record.get("surface", "intent"),
        input_hash=record["input_hash"],
        llm_category=record.get("llm_category"),
        llm_confidence=record.get("llm_confidence"),
        ollaya_choice=record.get("ollaya_choice"),
        ollaya_confidence=record.get("ollaya_confidence"),
        agreement=record.get("agreement"),
        ollaya_latency_ms=record.get("ollaya_latency_ms"),
        model=record.get("model"),
        enforced=False,
    )
    session.add(row)
    session.commit()


def record_intent_shadow(session, workspace_id: str, user_request: str,
                         llm_category: str, llm_confidence: float) -> dict | None:
    """Synchronous shadow record. Never raises; None = skipped. Owns nothing:
    pass a session (tests) or None for an owned SessionLocal (classify path)."""
    owned = None
    try:
        if not shadow_enabled():
            return None
        from core import decision_service as ds
        if not ds.ollaya_enabled():
            return None
        from core.decision_questions import INTENT_ROUTING_QUESTIONS

        result = _decide(user_request, INTENT_ROUTING_QUESTIONS)
        record = build_intent_audit_record(user_request, llm_category,
                                           llm_confidence, result)
        record["workspace_id"] = workspace_id
        if session is None:
            from core.database import SessionLocal
            owned = SessionLocal()
            session = owned
        _persist(session, record)
        return record
    except Exception as exc:
        logger.warning("[DecisionShadow] skipped (%s: %s)", type(exc).__name__, exc)
        try:
            if session is not None:
                session.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            if owned is not None:
                owned.close()
        except Exception:
            pass


async def _record_async(workspace_id: str, user_request: str,
                        llm_category: str, llm_confidence: float) -> None:
    record_intent_shadow(None, workspace_id, user_request, llm_category, llm_confidence)


async def _record_turn_async(workspace_id: str, digest: str,
                             execution_id: str | None,
                             session_id: str | None) -> None:
    record_turn_shadow(None, workspace_id, digest, execution_id, session_id)


def schedule_intent_shadow(workspace_id: str, user_request: str,
                           llm_category: str, llm_confidence: float) -> None:
    """Fire-and-forget entry for the classify path. Never raises, never blocks."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    try:
        if loop is not None:
            _t = loop.create_task(_record_async(workspace_id, user_request,
                                                llm_category, llm_confidence))
            _pending_turn_tasks.add(_t)
            _t.add_done_callback(lambda t: _pending_turn_tasks.discard(t))
        else:
            record_intent_shadow(None, workspace_id, user_request,
                                 llm_category, llm_confidence)
    except Exception as exc:
        logger.warning("[DecisionShadow] schedule skipped (%s)", type(exc).__name__)


# NLU route (ai.nlp_engine.RouteCategory) -> intent-bucket mapping for the
# meta-agent shadow seam. Only KNOWLEDGE_QUERY and AUTOMATION have clean
# counterparts (chat / workflow); everything else is recorded under an
# explicit "nlu:<raw>" label so it NEVER fabricates agreement — it shows up
# as its own group in calibration instead.
NLU_TO_INTENT = {
    "knowledge_query": "chat",
    "recurring_automation": "workflow",
}


def schedule_nlu_shadow(workspace_id: str, request: str, nlu_category: str,
                        nlu_confidence: float) -> None:
    """Meta-agent routing seam: compare the NLU route vs the decision model.

    Never raises, never blocks, never alters routing. Delegates to the
    intent shadow so all rows share one table and one calibrator.
    """
    try:
        raw = str(nlu_category or "unknown")
        mapped = NLU_TO_INTENT.get(raw, f"nlu:{raw}")
        schedule_intent_shadow(workspace_id, request, mapped,
                               float(nlu_confidence or 0.0))
    except Exception as exc:
        logger.warning("[DecisionShadow] nlu schedule skipped (%s)", type(exc).__name__)


# ---------------------------------------------------------------------------
# Turn judgments (Phase 3 — record-only telemetry next to fact extraction)
# ---------------------------------------------------------------------------

def _truncate_digest(digest: str) -> str:
    from core.decision_questions import TURN_DIGEST_MAX_CHARS
    text = str(digest or "")
    if len(text) > TURN_DIGEST_MAX_CHARS:
        text = text[:TURN_DIGEST_MAX_CHARS]
    return text


def build_turn_digest(request: str, steps: list, final_answer: str) -> str:
    """Bounded run digest mirroring the extractor's session-digest shape."""
    parts = [f"REQUEST: {request}"]
    for s in (steps or [])[-6:]:
        t = (str((s or {}).get("thought") or ""))[:200]
        o = (str((s or {}).get("output") or ""))[:200]
        if t:
            parts.append(f"THOUGHT: {t}")
        if o:
            parts.append(f"OBSERVATION: {o}")
    parts.append(f"FINAL ANSWER: {final_answer}")
    return _truncate_digest("\n".join(parts))


def build_turn_audit_record(digest: str, execution_id: str | None,
                            session_id: str | None, decide_result: dict) -> dict:
    """Pure builder: decision-model noul probabilities → audit record dict."""
    from core.decision_questions import TURN_JUDGMENTS

    answers = (decide_result or {}).get("answers", {})
    judgments: dict = {}
    for name in TURN_JUDGMENTS:
        ans = answers.get(name, {}) if isinstance(answers, dict) else {}
        prob = ans.get("noul") if isinstance(ans, dict) else None
        judgments[name] = float(prob) if isinstance(prob, (int, float)) else None
    return {
        "surface": "turn",
        "input_hash": hashlib.sha256(_normalize(digest).encode()).hexdigest(),
        "execution_id": execution_id,
        "session_id": session_id,
        "judgments": judgments,
        "ollaya_latency_ms": float((decide_result or {}).get("latency_ms", 0.0)),
        "model": str((decide_result or {}).get("model", "")),
        "enforced": False,
    }


def record_turn_shadow(session, workspace_id: str, digest: str,
                       execution_id: str | None,
                       session_id: str | None) -> dict | None:
    """Synchronous turn-judgment record. Never raises; None = skipped."""
    owned = None
    try:
        if not shadow_enabled_turn():
            return None
        from core import decision_service as ds
        if not ds.ollaya_enabled():
            return None
        from core.decision_questions import TURN_JUDGMENTS
        from core.models import DecisionTurnAudit

        result = _decide(_truncate_digest(digest), TURN_JUDGMENTS)
        record = build_turn_audit_record(digest, execution_id, session_id, result)
        record["workspace_id"] = workspace_id
        if session is None:
            from core.database import SessionLocal
            owned = SessionLocal()
            session = owned
        try:
            DecisionTurnAudit.__table__.create(bind=session.get_bind(), checkfirst=True)
        except Exception:
            pass
        session.add(DecisionTurnAudit(
            workspace_id=record["workspace_id"],
            execution_id=record["execution_id"],
            session_id=record["session_id"],
            surface="turn",
            input_hash=record["input_hash"],
            judgments=record["judgments"],
            ollaya_latency_ms=record["ollaya_latency_ms"],
            model=record["model"],
            enforced=False,
        ))
        session.commit()
        return record
    except Exception as exc:
        logger.warning("[DecisionShadow] turn skipped (%s: %s)",
                       type(exc).__name__, exc)
        try:
            if session is not None:
                session.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            if owned is not None:
                owned.close()
        except Exception:
            pass


def schedule_turn_shadow(workspace_id: str, digest: str,
                         execution_id: str | None = None,
                         session_id: str | None = None) -> None:
    """Fire-and-forget entry for the extraction hook sites. Never raises."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    try:
        if loop is not None:
            _t = loop.create_task(_record_turn_async(workspace_id, digest,
                                                     execution_id, session_id))
            _pending_turn_tasks.add(_t)
            _t.add_done_callback(lambda t: _pending_turn_tasks.discard(t))
        else:
            record_turn_shadow(None, workspace_id, digest, execution_id, session_id)
    except Exception as exc:
        logger.warning("[DecisionShadow] turn schedule skipped (%s)", type(exc).__name__)


# ---------------------------------------------------------------------------
# Pre-action gate (Phase 4 — advisory, inline on a deterministic sample)
# ---------------------------------------------------------------------------

def _ensure_column(session, table_name: str, column_ddl: str) -> None:
    """Additive DDL for self-provisioned shadow tables (table may predate a
    column). Plain ALTER TABLE is sqlite+postgres compatible; failures
    (duplicate column, locked) are swallowed — the insert is the real check."""
    try:
        from sqlalchemy import text as _text
        session.execute(_text(f"ALTER TABLE {table_name} ADD COLUMN {column_ddl}"))
        session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass


def shadow_enabled_gate() -> bool:
    try:
        from core.runtime_settings import get_bool_setting
        return bool(get_bool_setting("ATOM_OLLAYA_SHADOW_GATE", False))
    except Exception:
        return False


def gate_sample_rate() -> float:
    try:
        from core.runtime_settings import get_float_setting
        rate = float(get_float_setting("ATOM_OLLAYA_GATE_SAMPLE_RATE", 0.1))
        return min(max(rate, 0.0), 1.0)
    except Exception:
        return 0.1


def _gate_sampled(tool_name: str, args_hash: str, rate: float) -> bool:
    """Deterministic sampler (hash-based, no RNG state in the security path)."""
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    digest = hashlib.sha256(f"{tool_name}::{args_hash}".encode()).hexdigest()
    return (int(digest[:8], 16) / 0xFFFFFFFF) < rate


def _hash_gate_args(args: object) -> str:
    try:
        normalized = json.dumps(args, sort_keys=True, default=str)
    except Exception:
        normalized = "?"
    return hashlib.sha256(normalized.encode()).hexdigest()


def _gate_state(tool_name: str, args: object, context: dict | None) -> str:
    from core.decision_questions import GATE_STATE_MAX_CHARS

    try:
        args_s = json.dumps(args, sort_keys=True, default=str)[:600]
    except Exception:
        args_s = "?"
    ctx = context or {}
    tier = ctx.get("tier_at_issuance") or ctx.get("tier") or "?"
    return f"TOOL: {tool_name} ARGS: {args_s} TIER: {tier}"[:GATE_STATE_MAX_CHARS]


def build_gate_audit_record(tool_name: str, args_hash: str, sandbox_decision: str,
                            decide_result: dict, args: object = None) -> dict:
    """Pure builder: sandbox decision + would-have verdict → audit record."""
    from core.decision_questions import ACTION_JUDGMENTS  # noqa: F401 (schema pin)

    answers = (decide_result or {}).get("answers", {})
    verdict = answers.get("verdict", {}) if isinstance(answers, dict) else {}
    risky = answers.get("risky", {}) if isinstance(answers, dict) else {}
    choice = verdict.get("choice") if isinstance(verdict, dict) else None
    if choice not in ("allow", "ask", "block"):
        choice = None
    prob = risky.get("noul") if isinstance(risky, dict) else None
    sandbox = str(sandbox_decision or "").lower()
    if choice is None:
        agreement = False
    elif sandbox == "allowed":
        agreement = choice == "allow"
    else:  # sandbox required review / blocked: ask or block both count as caught
        agreement = choice in ("ask", "block")
    return {
        "surface": "gate",
        "tool_name": str(tool_name),
        "args_hash": str(args_hash),
        "sandbox_decision": str(sandbox_decision),
        "ollaya_verdict": choice,
        "ollaya_confidence": float(verdict.get("confidence", 0.0)) if choice else None,
        "risky": float(prob) if isinstance(prob, (int, float)) else None,
        "agreement": agreement,
        "ollaya_latency_ms": float((decide_result or {}).get("latency_ms", 0.0)),
        "model": str((decide_result or {}).get("model", "")),
        "enforced": False,
    }


def observe_gate(session, workspace_id: str, tool_name: str, args: object,
                 sandbox_decision: str, context: dict | None) -> dict | None:
    """Inline advisory observation. Never raises; None = skipped/abstained."""
    owned = None
    try:
        if not shadow_enabled_gate():
            return None
        from core import decision_service as ds
        if not ds.ollaya_enabled():
            return None
        args_hash = _hash_gate_args(args)
        if not _gate_sampled(tool_name, args_hash, gate_sample_rate()):
            return None
        from core.decision_questions import ACTION_JUDGMENTS, GATE_TIMEOUT_S
        from core.models import DecisionGateAudit

        result = _decide(_gate_state(tool_name, args, context),
                         ACTION_JUDGMENTS, timeout_s=GATE_TIMEOUT_S)
        record = build_gate_audit_record(tool_name, args_hash, sandbox_decision,
                                         result, args=args)
        record["workspace_id"] = workspace_id
        if session is None:
            from core.database import SessionLocal
            owned = SessionLocal()
            session = owned
        try:
            DecisionGateAudit.__table__.create(bind=session.get_bind(), checkfirst=True)
        except Exception:
            pass
        _ensure_column(session, "decision_gate_audit", "surface VARCHAR(24)")
        try:  # backfill rows written before the surface column existed
            from sqlalchemy import text as _text2
            session.execute(_text2(
                "UPDATE decision_gate_audit SET surface='gate' WHERE surface IS NULL"))
            session.commit()
        except Exception:
            try:
                session.rollback()
            except Exception:
                pass
        session.add(DecisionGateAudit(
            workspace_id=record["workspace_id"],
            tool_name=record["tool_name"],
            surface="gate",
            args_hash=record["args_hash"],
            sandbox_decision=record["sandbox_decision"],
            ollaya_verdict=record["ollaya_verdict"],
            ollaya_confidence=record["ollaya_confidence"],
            risky=record["risky"],
            agreement=record["agreement"],
            ollaya_latency_ms=record["ollaya_latency_ms"],
            model=record["model"],
            enforced=False,
        ))
        session.commit()
        return record
    except Exception as exc:
        logger.warning("[DecisionShadow] gate skipped (%s: %s)",
                       type(exc).__name__, exc)
        try:
            if session is not None:
                session.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            if owned is not None:
                owned.close()
        except Exception:
            pass
