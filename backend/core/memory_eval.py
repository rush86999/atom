"""
Memory Eval Harness (P2.3) — recall@k regression gate for retrieval.

The golden set encodes (question → expected memory) pairs drawn from the
brennan.ca pilot domain, including the two hard classes surfaced during
P0–P1 verification:

  - keyword-reachable   ("press brake" appears verbatim in the graph)
  - paraphrase-only     (semantic match required: "bending flat steel" →
                         "press brake"; no lexical overlap with the name)

`evaluate_retrieval()` runs each question through the same retrieval legs
the agent surfaces use (GraphRAG context + documents hybrid search) against
an ISOLATED workspace the harness seeds itself — never a live database —
and reports per-question hits plus aggregate recall@k.

The CI test (`tests/test_memory_eval_gate.py`) fails when recall drops
below the recorded baseline, making "fetched but dropped" and ranking
regressions test failures instead of silent bugs. Raise the gate when you
improve retrieval; never lower it without a plan-doc note.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Golden set (brennan.ca domain)
# --------------------------------------------------------------------------- #

@dataclass
class EvalQuestion:
    question: str
    expected_snippets: List[str]          # any-of: hit if ANY snippet matches
    category: str = "keyword"             # keyword | paraphrase


GOLDEN_SET: List[EvalQuestion] = [
    EvalQuestion(
        "What did ACME Fabrication inquire about?",
        ["ACME", "press brake"],
    ),
    EvalQuestion(
        "What is the list price of the AccurPress 50-ton press brake?",
        ["84,500", "84500"],
    ),
    EvalQuestion(
        "How many fiber lasers do we have in stock?",
        ["FL-2KW", "fiber laser"],
    ),
    EvalQuestion(
        "Who supplies the SigmaMax fiber laser?",
        ["SigmaMax"],
    ),
    EvalQuestion(
        "What budget did the ACME Fab lead mention?",
        ["80", "budget"],
    ),
    # Paraphrase-only: no lexical overlap with node names/descriptions.
    EvalQuestion(
        "Do we carry equipment for bending flat steel plates?",
        ["press brake", "AccurPress"],
        category="paraphrase",
    ),
    EvalQuestion(
        "machine that cuts metal with a focused light beam",
        ["laser", "Laser"],
        category="paraphrase",
    ),
]


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #

@dataclass
class EvalResult:
    question: str
    hit: bool
    category: str
    matched_snippet: Optional[str] = None
    context_chars: int = 0


@dataclass
class EvalReport:
    results: List[EvalResult] = field(default_factory=list)

    @property
    def recall(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.hit) / len(self.results)

    @property
    def recall_keyword(self) -> float:
        rows = [r for r in self.results if r.category == "keyword"]
        return sum(1 for r in rows if r.hit) / len(rows) if rows else 1.0

    @property
    def recall_paraphrase(self) -> float:
        rows = [r for r in self.results if r.category == "paraphrase"]
        return sum(1 for r in rows if r.hit) / len(rows) if rows else 1.0

    def summary(self) -> Dict[str, Any]:
        return {
            "recall": round(self.recall, 3),
            "recall_keyword": round(self.recall_keyword, 3),
            "recall_paraphrase": round(self.recall_paraphrase, 3),
            "total": len(self.results),
            "missed": [r.question for r in self.results if not r.hit],
        }


def _seed_eval_workspace(workspace_id: str) -> None:
    """Seed the isolated eval workspace with the brennan golden entities."""
    # Fresh databases (e.g. CI sqlite files) have no schema until the app
    # boots; create it so the harness is self-contained.
    from core.database import engine
    from core.models import Base

    Base.metadata.create_all(bind=engine)

    from core.graphrag_engine import GraphRAGEngine

    # demo/ lives at the repo root, not inside backend/ — resolve it relative
    # to this file so the import works regardless of the caller's cwd
    # (CI runs the backend job with working-directory: backend).
    import importlib.util
    import pathlib
    import sys

    _seed_path = (
        pathlib.Path(__file__).resolve().parents[2] / "demo" / "brennan" / "seed_data.py"
    )
    if "demo.brennan.seed_data" not in sys.modules:
        _spec = importlib.util.spec_from_file_location(
            "demo.brennan.seed_data", _seed_path
        )
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules["demo.brennan.seed_data"] = _mod
        _spec.loader.exec_module(_mod)
    from demo.brennan.seed_data import (  # type: ignore
        PRODUCTS, CUSTOMERS, VENDORS, LEADS, RELATIONSHIPS,
    )

    engine = GraphRAGEngine(workspace_id=workspace_id)
    engine.ingest_structured_data(
        entities=PRODUCTS + CUSTOMERS + VENDORS + LEADS,
        relationships=RELATIONSHIPS,
    )
    # Vector mirror for the semantic leg
    engine.backfill_node_vectors(workspace_id)


async def evaluate_retrieval(
    workspace_id: Optional[str] = None,
    k: int = 5,
    seed: bool = True,
) -> EvalReport:
    """Run the golden set through graph retrieval; report recall@k.

    Each invocation uses a fresh workspace id (uuid suffix) so runs never
    inherit stale LanceDB/SQL state from previous executions — the gate
    must be deterministic regardless of test ordering or prior runs."""
    import uuid as _uuid

    workspace_id = workspace_id or f"memory-eval-{_uuid.uuid4().hex[:8]}"
    report = EvalReport()
    if seed:
        await asyncio.to_thread(_seed_eval_workspace, workspace_id)

    from core.graphrag_engine import GraphRAGEngine

    engine = GraphRAGEngine(workspace_id=workspace_id)

    for q in GOLDEN_SET:
        context = ""
        try:
            context = await engine.get_context_for_ai(query=q.question)
        except Exception as e:
            logger.warning(f"eval: retrieval failed for {q.question!r}: {e}")
        matched = next(
            (s for s in q.expected_snippets if s.lower() in (context or "").lower()),
            None,
        )
        report.results.append(EvalResult(
            question=q.question,
            hit=matched is not None,
            category=q.category,
            matched_snippet=matched,
            context_chars=len(context or ""),
        ))
    return report


def _embedding_stack_available() -> bool:
    """Probe whether real embeddings work in this process (pytest suites
    install module-level AI fakes that can break provider resolution —
    the full gate is meaningless there)."""
    try:
        from core.lancedb_handler import LanceDBHandler

        h = LanceDBHandler(db_path="./data/atom_memory/_eval_probe")
        v = h.embed_text("probe")
        return v is not None and any(abs(x) > 0 for x in (v.tolist() if hasattr(v, "tolist") else v))
    except Exception:
        return False


if __name__ == "__main__":  # Standalone gate: python -m core.memory_eval
    import json as _json

    report = asyncio.run(evaluate_retrieval())
    print(_json.dumps(report.summary(), indent=2))
    raise SystemExit(0 if report.recall >= 1.0 else 1)
