"""
Memory eval gate (P2.3) — recall@k regression test.

Baseline (2026-08-19, brennan golden set, isolated workspace):
  keyword recall 1.0 · paraphrase recall 1.0 · overall 1.0

The gate fails when retrieval regresses below the recorded baseline.
Raise the thresholds when retrieval improves; never lower them without a
note in docs/architecture/AGENT_MEMORY_UNIFICATION_PLAN.md.
"""

import os
os.environ.setdefault("TESTING", "1")
os.environ["DATABASE_URL"] = "sqlite:///./test_memory_eval_gate.db"
os.environ.setdefault("LANCEDB_URI", "./data/atom_memory")

import pytest


def _stack_ok() -> bool:
    from core.memory_eval import _embedding_stack_available

    return _embedding_stack_available()


@pytest.mark.asyncio
async def test_memory_recall_gate():
    if not _stack_ok():
        pytest.skip(
            "embedding stack unavailable in this pytest env (suite AI fakes); "
            "run `python -m core.memory_eval` for the full recall gate"
        )
    from core.memory_eval import evaluate_retrieval

    report = await evaluate_retrieval(workspace_id="memory-eval-gate")
    summary = report.summary()

    # Recorded baseline — regression gate
    assert summary["recall_keyword"] >= 1.0, (
        f"keyword recall regressed: {summary}"
    )
    assert summary["recall_paraphrase"] >= 1.0, (
        f"paraphrase recall regressed: {summary}"
    )
    assert summary["recall"] >= 1.0, f"overall recall regressed: {summary}"


@pytest.mark.asyncio
async def test_eval_report_shape():
    from core.memory_eval import EvalReport, EvalResult

    report = EvalReport(results=[
        EvalResult(question="q1", hit=True, category="keyword"),
        EvalResult(question="q2", hit=False, category="paraphrase"),
    ])
    assert report.recall == 0.5
    assert report.recall_keyword == 1.0
    assert report.recall_paraphrase == 0.0
    assert report.summary()["missed"] == ["q2"]
