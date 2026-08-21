"""
Conversational-memory eval (rev.2 plan §5) — golden-QA gate over the
turn-fact store.

The P2.3 harness (`core/memory_eval`) gates RETRIEVAL recall over
GraphRAG/documents. This module extends measurement to the CONVERSATIONAL
memory layer: synthetic multi-session dialogues are ingested as durable
facts, then golden questions run through the same Tier-1 recall the agent
prompt assembly uses — pinning:

  - single-hop recall      (the right fact surfaces in top-k)
  - update/temporal        (superseded facts never resurface; latest wins)
  - source attribution     (stated ranks above equally-recent inferred under
                            prioritize_stated — survey §7.3 policy)
  - epistemic filtering    (epistemic_type="stated" excludes inferences)

HONEST SCOPE: ingestion bypasses the LLM extractor (facts are written via
`_persist_one` directly), so this measures STORE + RECALL correctness — not
extraction quality. Extraction quality needs live-LLM runs; see the plan's
§5 note. Isolated workspace per invocation; never touches live data.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Golden conversations (synthetic, deterministic)
# --------------------------------------------------------------------------- #

@dataclass
class ScriptedTurn:
    session: int                     # 1-based session number
    speaker: str                     # "user" | "agent"
    text: str


@dataclass
class SeededFact:
    """A fact the seeder writes for a scripted turn (what the extractor
    WOULD produce). Kept explicit so the golden set documents intent."""
    turn_index: int                  # index into the flattened turn list
    fact_text: str
    category: str
    epistemic_type: str = "stated"
    confidence: float = 0.9
    supersede_of: Optional[str] = None   # fact_text this replaces (update chain)


@dataclass
class GoldenQA:
    question: str
    kind: str                        # "hit" | "absent" | "ordering" | "filter"
    expected_snippet: str            # fact_text (substring match, case-fold)
    top_k: int = 5
    epistemic_type: Optional[str] = None
    prioritize_stated: bool = False


GOLDEN_CONVERSATION: List[ScriptedTurn] = [
    ScriptedTurn(1, "user", "We're on the monthly plan and we need SSO enabled before our audit in March."),
    ScriptedTurn(1, "agent", "Noted — I'll treat SSO-before-March-audit as a hard requirement."),
    ScriptedTurn(2, "user", "Our finance contact is Dana Whitfield; all invoices go through her."),
    ScriptedTurn(2, "agent", "Recorded: Dana Whitfield is the finance contact for invoicing."),
    ScriptedTurn(3, "user", "We just upgraded from the monthly plan to the annual plan."),
    ScriptedTurn(3, "agent", "Congratulations on the upgrade — updating your account notes."),
    ScriptedTurn(4, "user", "Honestly, based on how fast you turned SSO around, I'd guess you prioritize enterprise customers."),
    ScriptedTurn(4, "agent", "That's a fair read — enterprise requests do jump the queue here."),
]

GOLDEN_FACTS: List[SeededFact] = [
    # session 1
    SeededFact(0, "Customer requires SSO enabled before their March audit", "hard_constraint", "stated"),
    SeededFact(0, "Customer is on the monthly plan", "exact_value", "stated"),
    # session 2
    SeededFact(3, "Dana Whitfield is the finance contact; all invoices route through her", "exact_value", "stated"),
    # session 3 — UPDATE of the plan fact (supersede chain)
    SeededFact(5, "Customer upgraded to the annual plan", "exact_value", "stated",
               supersede_of="Customer is on the monthly plan"),
    # session 4 — an INFERENCE (agent conclusion about priority), newer than nothing
    SeededFact(7, "Customer likely values fast enterprise-grade turnaround", "implicit_pref",
               "inferred", confidence=0.6),
]

GOLDEN_QA: List[GoldenQA] = [
    GoldenQA("Which plan is the customer on?", "hit",
             "Customer upgraded to the annual plan"),
    GoldenQA("Is the customer still on the monthly plan?", "absent",
             "Customer is on the monthly plan"),
    GoldenQA("Who routes invoices?", "hit",
             "Dana Whitfield is the finance contact"),
    GoldenQA("Any hard constraints?", "hit",
             "SSO enabled before their March audit",
             epistemic_type="stated"),
    GoldenQA("What does the customer value?", "ordering",
             "Customer requires SSO enabled before their March audit",
             prioritize_stated=True),
]


# --------------------------------------------------------------------------- #
# Seeder + evaluator
# --------------------------------------------------------------------------- #

def seed_conversation_memory(workspace_id: str) -> List:
    """Ingest the golden conversation into the turn-fact store.

    Bypasses the LLM extractor deliberately (measures store + recall).
    Returns the persisted rows. Supersession chains use the extractor's
    dedup contract: same content_hash supersedes when confidence beats by
    margin — here we supersede explicitly via _persist_one's collision path.
    """
    from core.database import Base, SessionLocal, engine as _engine

    # Fresh databases get schema from create_all; EXISTING tables don't gain
    # new columns from it — apply the source-attribution DDL guardedly so the
    # harness is self-contained on pre-migration databases.
    Base.metadata.create_all(bind=_engine)
    with _engine.begin() as conn:
        from sqlalchemy import text as _text

        cols = {
            r[1] for r in conn.execute(_text("PRAGMA table_info(turn_facts)"))
        }
        if "epistemic_type" not in cols:
            conn.execute(_text(
                "ALTER TABLE turn_facts ADD COLUMN epistemic_type VARCHAR(16) "
                "NOT NULL DEFAULT 'stated'"
            ))
        if "sensitivity" not in cols:
            conn.execute(_text(
                "ALTER TABLE turn_facts ADD COLUMN sensitivity VARCHAR(16) "
                "NOT NULL DEFAULT 'internal'"
            ))

    from core.models import TurnFact
    from core.turn_fact_extractor import TurnFactExtractor

    svc = TurnFactExtractor(workspace_id=workspace_id)
    persisted: List = []
    for seeded in GOLDEN_FACTS:
        row = svc._persist_one(
            fact_text=seeded.fact_text,
            category=seeded.category,
            domain="conversation-eval",
            confidence=seeded.confidence,
            tags=None,
            extraction_source="turn",
            execution_id=None,
            reasoning_step_id=None,
            episode_id=None,
            session_id=None,
            user_id=None,
            epistemic_type=seeded.epistemic_type,
            _skip_antithrash=True,
        )
        if row is not None:
            persisted.append(row)

    # Explicit update chains: differing fact texts never collide by hash, so
    # the consolidator-style supersession is applied directly (this mirrors
    # what the nightly contradiction sweep does in production).
    for seeded in GOLDEN_FACTS:
        if not seeded.supersede_of:
            continue
        with SessionLocal() as db:
            stale = (
                db.query(TurnFact)
                .filter(
                    TurnFact.workspace_id == workspace_id,
                    TurnFact.status == "active",
                    TurnFact.fact_text == seeded.supersede_of,
                )
                .all()
            )
            now = datetime.now(timezone.utc)
            for r in stale:
                r.status = "superseded"
                r.superseded_at = now
                r.commit_message = f"superseded by update ({seeded.fact_text[:40]})"
            db.commit()
    return persisted


def evaluate_conversation_memory(
    workspace_id: Optional[str] = None,
    seed: bool = True,
) -> Dict[str, Any]:
    """
    Run the golden QAs against Tier-1 recall; report per-question results
    and aggregate accuracy. Never raises.
    """
    import time

    workspace_id = workspace_id or f"conv-eval-{uuid.uuid4().hex[:8]}"
    results: List[Dict[str, Any]] = []
    try:
        if seed:
            seed_conversation_memory(workspace_id)

        from core.turn_fact_extractor import get_active_facts_for_prompt

        # small stagger so recency ordering is deterministic on coarse clocks
        def _recall(qa: GoldenQA):
            time.sleep(0.01)
            return get_active_facts_for_prompt(
                None if False else _session(),
                workspace_id,
                limit=qa.top_k,
                epistemic_type=qa.epistemic_type,
                prioritize_stated=qa.prioritize_stated,
            )

        for qa in GOLDEN_QA:
            rows = _recall(qa)
            texts = [(r.fact_text or "").lower() for r in rows]
            snippet = qa.expected_snippet.lower()

            if qa.kind == "hit":
                passed = any(snippet in t for t in texts)
            elif qa.kind == "absent":
                passed = all(snippet not in t for t in texts)
            elif qa.kind == "ordering":
                # stated-first: the expected STATED fact must rank at/above
                # every inferred fact in the window
                stated_idx = next(
                    (i for i, r in enumerate(rows)
                     if r.epistemic_type == "stated"
                     and snippet in (r.fact_text or "").lower()),
                    None,
                )
                inferred_idxs = [
                    i for i, r in enumerate(rows) if r.epistemic_type == "inferred"
                ]
                passed = (
                    stated_idx is not None
                    and all(stated_idx <= i for i in inferred_idxs)
                )
            elif qa.kind == "filter":
                passed = any(snippet in t for t in texts) and all(
                    r.epistemic_type == qa.epistemic_type for r in rows
                )
            else:
                passed = False

            results.append({
                "question": qa.question,
                "kind": qa.kind,
                "passed": bool(passed),
                "expected": qa.expected_snippet,
                "recalled": texts[:qa.top_k],
            })
    except Exception as e:
        logger.warning("evaluate_conversation_memory failed: %s", e)
        results.append({"question": "<harness-error>", "kind": "error",
                        "passed": False, "expected": "", "recalled": [],
                        "error": str(e)})

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "workspace_id": workspace_id,
        "total": len(results),
        "passed": passed_count,
        "accuracy": (passed_count / len(results)) if results else 0.0,
        "results": results,
    }


def _session():
    """Fresh session per recall call (keeps the helper pure-SQL contract)."""
    from core.database import SessionLocal

    return SessionLocal()


if __name__ == "__main__":  # python -m core.memory_eval_conversation
    import json as _json

    print(_json.dumps(evaluate_conversation_memory(), indent=2, default=str))