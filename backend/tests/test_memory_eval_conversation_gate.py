"""
CI gate for conversational memory (rev.2 plan §5): golden-QA over the
turn-fact store. Fails when conversation-memory recall regresses —
single-hop hits, update/supersession, source-attribution ordering, and
epistemic filtering are all pinned by core/memory_eval_conversation.

Gate is set at the recorded baseline (currently 5/5). Raise it when you
improve recall; never lower it without a plan-doc note.
"""

import pytest

from core.memory_eval_conversation import evaluate_conversation_memory

BASELINE_ACCURACY = 1.0


@pytest.mark.asyncio
async def test_conversation_memory_gate():
    report = evaluate_conversation_memory()
    assert report["total"] == 5, f"golden QA count drifted: {report['total']}"
    failed = [r for r in report["results"] if not r["passed"]]
    assert report["accuracy"] >= BASELINE_ACCURACY, (
        f"conversational-memory gate regressed: {report['passed']}/{report['total']} "
        f"failed={[(r['question'], r['kind']) for r in failed]}"
    )