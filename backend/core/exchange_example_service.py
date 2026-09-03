"""
Exchange example learning loop (Phase 56) — capture, retrieval, and the
hooks that make rated exchanges part of the agent learning/teaching
circuitry rather than a write-only log.

Three consumers, one table (``ExchangeExample``):

1. CAPTURE (this module, ``capture_exchange``): the chat feedback endpoint
   persists the full (query, response) pair — the feedback endpoint used to
   drop the pair entirely when the learning router was off, and experience
   storage truncates to 200/500 chars. Labels are conservative: only
   explicit thumbs and the regenerate handler count (false negatives are
   the top documented failure mode of negative-sample learning).

2. TEACHING CIRCUIT (fire on capture): a comment-bearing rejection is a
   human correction — fanned out to STUDENT agents via
   ``StudentLearningService`` as a PERMANENT lesson (rendered first in
   every prompt by format_lessons_block, survives graduation), and both
   labels feed ``PedagogicalFramework.record_mastery_exposure`` for the
   operating agent (positive exposures build mastery so scaffolding
   withdraws; mistakes add corrective entries — errors are information).
   Confidence nudges stay under the learning ceiling: examples never
   graduate an agent by themselves, the training system confers maturity.

3. WORK-TIME RETRIEVAL (``search_similar_examples``, consumed by the
   memory_context_assembler leg): semi-hard band filtering per the
   negative-sampling literature — positives want HIGH similarity (a
   demonstration for this exact kind of request); negatives want the MID
   band (too-similar negatives in the same conversation are the just-
   rejected answer itself, too-dissimilar ones are easy negatives that
   add noise). Same-conversation negatives are excluded outright.

Flag: ``ATOM_EXCHANGE_MEMORY`` = off | shadow | enforce (default shadow,
matching ATOM_VERIFY_PANEL conventions). Capture + the teaching circuit
run in shadow and enforce (learning is the point); only prompt injection
waits for enforce — shadow logs what would have been injected.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core.models import ChatMessage, ExchangeExample

logger = logging.getLogger(__name__)

_MODE_FLAG = "ATOM_EXCHANGE_MEMORY"
_VECTOR_TABLE = "exchange_examples"

# Semi-hard band defaults (LanceDB search score = clamp(1 - distance, 0, 1),
# higher = more similar). Env-tunable so deployments can calibrate without
# code changes; unit-tested in tests/test_exchange_example_service.py.
_NEG_SIM_MIN = 0.55
_NEG_SIM_MAX = 0.92
_POS_SIM_MIN = 0.80

_MAX_RESPONSE_CHARS = 4000  # full text, but bounded against runaway outputs
_REGENERATE_COMMENT = "regenerated"  # the frontend's regenerate handler marker


_MODES = ("off", "shadow", "enforce")


def exchange_memory_setting(db=None) -> tuple:
    """Raw resolved setting as (value, source) — 'auto' is a legal value here.

    Sources: explicit env > UI/db row > catalog default. An explicit env var
    is the operator kill-switch and is never overridden by automation."""
    from core.runtime_settings import resolve_setting

    res = resolve_setting(_MODE_FLAG, db=db)
    value = str(res.value or "auto").strip().lower()
    return value, res.source


def exchange_memory_mode(db=None) -> str:
    """The EFFECTIVE mode: off | shadow | enforce.

    ``auto`` (the default) self-regulates: it behaves as shadow — learning
    runs, answers unchanged — until the maintenance latch flips the stored
    value to enforce once the corpus is healthy (see
    core/exchange_memory_maintenance.py). Pinning off/shadow/enforce holds
    that state; an explicit env var wins over everything."""
    value, _ = exchange_memory_setting(db=db)
    if value == "auto":
        return "shadow"  # pre-latch effective state
    return value if value in _MODES else "shadow"


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def _resolve_exchange_pair(
    db, conversation_id: Optional[str], message_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Resolve the rated (query, response) pair from the chat transcript.

    Layered because the frontend's message_id is only sometimes the durable
    ChatMessage.id (fresh turns carry client-generated ids):
      1. message_id matches a ChatMessage row -> that assistant row.
      2. else the newest assistant row of the conversation, but ONLY when it
         is also the newest row overall (nothing was said after it) — once
         the user continues, the rated message can no longer be identified.
    Error-artifact turns (metadata quality=error) never qualify: an
    infrastructure failure is not a content example to learn from.
    """
    def _usable(assistant_row: ChatMessage) -> Optional[Dict[str, Any]]:
        if assistant_row is None or not (assistant_row.content or "").strip():
            return None
        try:
            meta = json.loads(assistant_row.metadata_json or "{}")
        except Exception:
            meta = {}
        if meta.get("quality") == "error":
            return None
        query_row = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == assistant_row.conversation_id,
                ChatMessage.role == "user",
                ChatMessage.created_at < assistant_row.created_at,
            )
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        if query_row is None or not (query_row.content or "").strip():
            return None
        return {
            "user_query": query_row.content,
            "assistant_response": assistant_row.content[:_MAX_RESPONSE_CHARS],
            "assistant_message_id": assistant_row.id,
            "agent_id": assistant_row.agent_id,
            "conversation_id": assistant_row.conversation_id,
            "tenant_id": assistant_row.tenant_id or "default",
            # The model's chain-of-thought persisted at reply time
            # (ChatMessage.metadata_json.reasoning) — feedback training
            # judges WHAT the agent was thinking, not just what it said.
            "reasoning": (str(meta.get("reasoning"))[:20000] if meta.get("reasoning") else None),
        }

    if message_id:
        row = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if row is not None and row.role == "assistant":
            pair = _usable(row)
            if pair:
                return pair

    if not conversation_id:
        return None
    newest = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.desc())
        .first()
    )
    if newest is None or newest.role != "assistant":
        return None
    return _usable(newest)


def _topic_for_query(query: str) -> str:
    """Coarse mastery topic from the query — same token heuristic the
    lesson scorer uses (content words, no stopwords), top 3 joined."""
    tokens = [
        t for t in re.findall(r"[a-z0-9]{3,}", (query or "").lower())
        if t not in {
            "the", "and", "for", "with", "this", "that", "please", "can",
            "you", "your", "how", "what", "when", "who", "why", "are", "was",
        }
    ]
    return " ".join(tokens[:3]) or "general"


def _dedupe_key_match(db, pair: Dict[str, Any], label: str):
    """The same rejection must not stack rows: thumbs-down then regenerate
    posts the same pair twice. Match on the resolved assistant message id,
    falling back to exact query text when the id is client-generated."""
    q = db.query(ExchangeExample).filter(ExchangeExample.label == label)
    if pair.get("conversation_id"):
        q = q.filter(ExchangeExample.conversation_id == pair["conversation_id"])
    if pair.get("assistant_message_id"):
        return q.filter(
            ExchangeExample.assistant_message_id == pair["assistant_message_id"]
        ).first()
    return q.filter(ExchangeExample.user_query == pair["user_query"]).first()


def _write_vector(row: ExchangeExample) -> bool:
    """Best-effort LanceDB side-write (turn_fact_vector_store pattern):
    SQL row is the source of truth; corruption here never fails capture."""
    try:
        from core.lancedb_handler import LanceDBHandler

        handler = LanceDBHandler(workspace_id=row.workspace_id or "default")
        return bool(handler.add_document(
            table_name=_VECTOR_TABLE,
            text=row.user_query,
            source=f"exchange_example:{row.label}",
            metadata={
                "label": row.label,
                "feedback_source": row.source,
                "has_comment": bool(row.comment),
                "conversation_id": row.conversation_id,
                "agent_id": row.agent_id,
                "example_id": row.id,
            },
            user_id=row.user_id or "exchange_example",
            workspace_id=row.workspace_id or "default",
            doc_id=row.id,
            skip_ai_triggers=True,
        ))
    except Exception as e:
        logger.debug("exchange example vector write skipped for %s: %s", row.id, e)
        return False


def _fire_teaching_circuit(pair: Dict[str, Any], row: ExchangeExample) -> Dict[str, Any]:
    """Feed the rated pair into the existing learning/teaching circuitry.

    - Comment-bearing rejection -> human_correction observation for STUDENT
      agents in the workspace (auto_observe opens its own session,
      fire-and-forget). human_correction is a _PERMANENT_OBSERVATIONS type:
      it becomes standing work-time guidance, which is the teaching circuit.
      A bare thumbs-down stays a retrieval/caution example only — without a
      comment there is no actionable lesson content to teach.
    - Both labels -> pedagogy mastery exposure for the operating agent
      (positives build mastery so scaffolding withdraws; mistakes add
      corrective entries).
    """
    fired: Dict[str, Any] = {}

    if row.label == "negative" and (row.comment or "").strip():
        try:
            import asyncio
            from core.student_learning_service import auto_observe

            summary = (
                f"A human rejected the assistant's answer to "
                f"\"{(row.user_query or '')[:120]}\": {row.comment[:300]}. "
                f"Treat that as a correction: do not repeat the rejected "
                f"approach for requests like this."
            )
            asyncio.get_running_loop().create_task(auto_observe(
                workspace_id=row.workspace_id or "default",
                observation_type="human_correction",
                summary=summary,
                details={
                    "example_id": row.id,
                    "conversation_id": row.conversation_id,
                    "query": (row.user_query or "")[:300],
                    "rejection_reason": row.comment[:500],
                    "feedback_source": row.source,
                },
            ))
            fired["human_correction_lesson"] = True
        except Exception as e:
            logger.debug("human_correction fan-out skipped: %s", e)

        # The STUDENT fan-out above skips SUPERVISED/graduated hires. The
        # operating agent that produced the rejected answer must get the
        # rule at ANY tier — the supervisor's correction IS the approval
        # for their own agent (same rationale as the canvas real-time
        # path). Status-independent, deduped, fire-and-forget.
        operating_agent_id = (
            getattr(row, "agent_id", None) or pair.get("agent_id") or ""
        )
        if str(operating_agent_id).strip():
            try:
                from core.database import SessionLocal
                from core.student_learning_service import journal_standing_lesson

                jd = SessionLocal()
                try:
                    journaled = journal_standing_lesson(
                        jd, str(operating_agent_id), summary,
                        source="observation",
                        observation_type="human_correction",
                        details={
                            "example_id": row.id,
                            "conversation_id": row.conversation_id,
                            "query": (row.user_query or "")[:300],
                            "rejection_reason": row.comment[:500],
                            "feedback_source": row.source,
                            "surface": "chat_feedback",
                        },
                    )
                finally:
                    jd.close()
                if journaled:
                    fired["operating_agent_lesson"] = True
            except Exception as e:
                logger.debug("operating-agent correction journal skipped: %s", e)

    agent_id = pair.get("agent_id")
    if agent_id:
        try:
            from core.agent_pedagogy import PedagogicalFramework
            from core.database import SessionLocal
            from core.models import AgentRegistry

            db = SessionLocal()
            try:
                agent = db.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id
                ).first()
                if agent is not None:
                    PedagogicalFramework(db).record_mastery_exposure(
                        agent,
                        _topic_for_query(row.user_query),
                        positive=(row.label == "positive"),
                        note=(row.comment or row.user_query or "")[:200],
                    )
                    fired["mastery_exposure"] = row.label
            finally:
                db.close()
        except Exception as e:
            logger.debug("mastery exposure skipped: %s", e)

    return fired


async def capture_exchange(
    *,
    message_id: Optional[str],
    feedback: str,
    comment: Optional[str],
    session_id: Optional[str],
    model: Optional[str] = None,
    provider: Optional[str] = None,
    user_id: Optional[str] = None,
    reasoning: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist the rated exchange pair + fire the teaching circuit.

    Called from POST /api/chat/feedback BEFORE the learning-router branch so
    capture happens regardless of router state (the router branch is
    unchanged). Never raises into the caller's flow.

    ``reasoning`` (the model's chain-of-thought for the rated reply) is
    taken from the request when the client sends it, else recovered from the
    assistant ChatMessage's persisted metadata — one of the two is always
    available for turns served by the reasoning-capture path.
    """
    mode = exchange_memory_mode()
    if mode == "off":
        return {"captured": False, "reason": "flag_off"}

    label = "positive" if feedback == "thumbs_up" else "negative"
    source = (
        "regenerate_implicit"
        if (comment or "").strip().lower() == _REGENERATE_COMMENT
        else "explicit_thumbs"
    )

    from core.database import SessionLocal

    db = SessionLocal()
    try:
        pair = _resolve_exchange_pair(db, session_id, message_id)
        if not pair:
            return {"captured": False, "reason": "pair_unresolvable"}

        if _dedupe_key_match(db, pair, label) is not None:
            return {"captured": False, "reason": "duplicate"}

        row = ExchangeExample(
            tenant_id=pair["tenant_id"],
            user_id=user_id,
            workspace_id=None,  # resolved below via the user's workspace
            conversation_id=pair["conversation_id"],
            message_id=message_id,
            assistant_message_id=pair["assistant_message_id"],
            agent_id=pair["agent_id"],
            user_query=pair["user_query"],
            assistant_response=pair["assistant_response"],
            label=label,
            source=source,
            comment=(comment or "").strip() or None,
            model=model,
            provider=provider,
            reasoning=(
                (reasoning or "").strip()[:20000]
                or pair.get("reasoning")
                or None
            ),
        )
        # Workspace scoping must match chat-time retrieval: the assembler
        # retrieves from resolve_user_workspace(user_id) (chat_orchestrator)
        # — which is itself just the User.workspace_id lookup below. Keep
        # the two in sync or examples become invisible to recall.
        try:
            from core.models import User

            user_row = (
                db.query(User.workspace_id).filter(User.id == user_id).first()
                if user_id
                else None
            )
            row.workspace_id = (user_row[0] if user_row else None) or "default"
        except Exception:
            row.workspace_id = "default"

        db.add(row)
        db.commit()

        import asyncio

        embedded = await asyncio.to_thread(_write_vector, row)
        circuitry = _fire_teaching_circuit(pair, row)

        logger.info(
            "exchange example captured: %s label=%s source=%s embedded=%s circuitry=%s",
            row.id, label, source, embedded, circuitry,
        )
        return {
            "captured": True,
            "example_id": row.id,
            "label": label,
            "source": source,
            "embedded": embedded,
            "circuitry": circuitry,
        }
    except Exception as e:
        logger.warning(f"exchange example capture failed (non-fatal): {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return {"captured": False, "reason": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Retrieval (semi-hard band filtering)
# ---------------------------------------------------------------------------

def _band_bounds(label: str) -> Tuple[float, float]:
    """(min, max) similarity band for a label, from env with defaults."""
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, "") or default)
        except ValueError:
            return default

    if label == "negative":
        return (
            _env_float("ATOM_EXCHANGE_NEG_SIM_MIN", _NEG_SIM_MIN),
            _env_float("ATOM_EXCHANGE_NEG_SIM_MAX", _NEG_SIM_MAX),
        )
    return (_env_float("ATOM_EXCHANGE_POS_SIM_MIN", _POS_SIM_MIN), 1.01)


def filter_examples_by_band(
    hits: List[Dict[str, Any]],
    label: str,
    min_sim: Optional[float] = None,
    max_sim: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Pure band filter over LanceDB search hits (each has a ``score`` in
    [0, 1], higher = more similar).

    Positives: keep the HIGH band — a demonstration must actually match this
    request. Negatives: keep the MID band — below min is an easy negative
    (noise), above max is usually the just-rejected answer itself
    (false-negative territory). Order is preserved (vector rank)."""
    lo, hi = _band_bounds(label)
    lo = lo if min_sim is None else min_sim
    hi = hi if max_sim is None else max_sim
    return [
        h for h in hits
        if isinstance(h, dict) and lo <= float(h.get("score") or 0.0) <= hi
    ]


def search_similar_examples(
    workspace_id: str,
    query: str,
    label: str,
    limit: int = 2,
    exclude_conversation_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Similar rated exchanges of one label, band-filtered, hydrated from SQL.

    Returns [{query, response, comment, label, source, created_at, score}]
    ordered by vector rank. [] on any failure — never blocks the turn.
    """
    if not query or len(query.strip()) < 3:
        return []
    try:
        from core.lancedb_handler import LanceDBHandler

        handler = LanceDBHandler(workspace_id=workspace_id or "default")
        safe_ws = str(workspace_id or "default").replace("'", "''")
        clauses = [f"label == '{label}'", f"workspace_id == '{safe_ws}'"]
        if exclude_conversation_id:
            safe_conv = str(exclude_conversation_id).replace("'", "''")
            # NULL conversation_id rows can't be attributed to the current
            # conversation — keep them.
            clauses.append(
                f"(conversation_id != '{safe_conv}' OR conversation_id IS NULL)"
            )
        hits = handler.search(
            table_name=_VECTOR_TABLE,
            query=query[:500],
            limit=max(limit * 3, 6),  # over-fetch: the band filters some out
            filter_str=" AND ".join(clauses),
        ) or []
        hits = filter_examples_by_band(hits, label)[:limit]
        if not hits:
            return []

        ids = [str(h.get("id")) for h in hits if h.get("id")]
        from core.database import SessionLocal

        db = SessionLocal()
        try:
            rows = db.query(ExchangeExample).filter(
                ExchangeExample.id.in_(ids)
            ).all()
            by_id = {r.id: r for r in rows}
        finally:
            db.close()

        out: List[Dict[str, Any]] = []
        for h in hits:
            r = by_id.get(str(h.get("id")))
            if r is None:
                continue  # SQL row gone — vector is stale; skip, don't render
            out.append({
                "id": r.id,
                "query": r.user_query,
                "response": r.assistant_response,
                "comment": r.comment,
                "label": r.label,
                "source": r.source,
                "created_at": r.created_at,
                "score": h.get("score"),
            })
        return out
    except Exception as e:
        logger.debug("exchange example retrieval failed: %s", e)
        return []


def get_corpus_counts(db) -> Dict[str, int]:
    """Whole-corpus rated counts — the Settings page's health numbers for
    the learning loop (how much there is to learn from)."""
    out = {"positive": 0, "negative": 0, "total": 0}
    try:
        labels = [r[0] for r in db.query(ExchangeExample.label).all()]
        pos = sum(1 for l in labels if l == "positive")
        neg = sum(1 for l in labels if l == "negative")
        out = {"positive": pos, "negative": neg, "total": pos + neg}
    except Exception as e:
        logger.debug("corpus counts failed: %s", e)
    return out


def get_rated_exchange_summary(db, agent_id: str) -> Dict[str, Any]:
    """Rated-exchange counts for one operating agent — the maturity evidence
    view (training panels / readiness reporting read this; the graduation
    formula itself is untouched)."""
    out = {"positive": 0, "negative": 0, "ratio": 0.0}
    try:
        rows = (
            db.query(ExchangeExample.label)
            .filter(ExchangeExample.agent_id == agent_id)
            .all()
        )
        labels = [r[0] for r in rows]
        pos = sum(1 for l in labels if l == "positive")
        neg = sum(1 for l in labels if l == "negative")
        total = pos + neg
        out = {
            "positive": pos,
            "negative": neg,
            "ratio": (pos / total) if total else 0.0,
        }
    except Exception as e:
        logger.debug("rated exchange summary failed for %s: %s", agent_id, e)
    return out


def load_example_corpus(
    db, workspace_id: Optional[str] = None, limit: int = 500
) -> List[Dict[str, Any]]:
    """The rated corpus for evaluation / regression use (retrieval eval
    harness now; available to exam/evolution code as a validation set)."""
    q = db.query(ExchangeExample).order_by(ExchangeExample.created_at.desc())
    if workspace_id:
        q = q.filter(ExchangeExample.workspace_id == workspace_id)
    return [
        {
            "id": r.id,
            "query": r.user_query,
            "response": r.assistant_response,
            "label": r.label,
            "comment": r.comment,
        }
        for r in q.limit(limit).all()
    ]
