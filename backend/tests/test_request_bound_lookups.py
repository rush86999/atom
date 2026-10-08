"""Request-bound lookups: explicit subjects lead; receipts count; readiness
distinguishes drafting from price changes.

Owner final repair (2026-10-08) pins:
- WRONG-SUBJECT (direct research lookup): with request subjects bound, the
  datasets probe uses THEM and history does not displace them (case-4
  searched 'sle24' from canvas history while the request named 'No. 381').
- WRONG-SOURCE (editor fresh-data / background): the reloaded background
  contract rides the blackboard into the fresh-data context.
- RECEIPT-GATED CONSULTATION: a block without a structured receipt is not
  a consultation.
- PRICE-CHANGE vs DRAFTING READINESS: value-changing ops need ready
  evidence; formatting/header ops proceed under authorization.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("TESTING", "1")

from core import chat_canvas_editor as cce
from core.sheet_dataset_service import search_all_datasets_sync
from core.chat_tool_planner import _datasets_search_block


def test_probe_uses_request_subjects_not_history(monkeypatch):
    captured: dict = {}

    def fake_sync(query, user_id, ws, limit, max_files, context_texts,
                  name_context_texts, deadline=None,
                  request_subjects=None):
        captured["request_subjects"] = request_subjects
        captured["context_texts"] = context_texts
        return {"files_searched": 0, "hits": []}

    import core.sheet_dataset_service as sds
    monkeypatch.setattr(sds, "candidate_probe_tokens",
                        lambda texts, **k: [t for t in " ".join(
                            texts).split() if any(
                                c.isdigit() for c in t)][:5])
    with patch("core.sheet_dataset_service.search_all_datasets_sync",
               side_effect=fake_sync):
        import asyncio
        asyncio.run(_datasets_search_block(
            "u1", "What is the current price for No. 381?", {
                "message": "What is the current price for No. 381?",
                "history": [{"role": "user", "content":
                             "earlier we checked SLE24-16 slitter"}],
                "request_scope": {"subjects": ["No. 381"],
                                  "scope_change": "replace"},
            }, plan=SimpleNamespace(_result_meta={})))
    assert captured["request_subjects"] == ["No. 381"], (
        "the request's resolved subjects must reach the probe")


def test_search_all_datasets_prefers_request_subjects(monkeypatch):
    """Inside the sync search: with request_subjects, history texts do not
    enter the candidate pool (they may not REPLACE explicit subjects)."""
    seen: dict = {}

    class _FakeCandidates:
        def __call__(self, texts, **kwargs):
            seen["texts"] = list(texts)
            return ["381"]

    import core.sheet_dataset_service as sds
    monkeypatch.setattr(sds, "candidate_probe_tokens", _FakeCandidates())
    monkeypatch.setattr(sds, "distinctive_name_tokens", lambda srcs: set())
    import inspect
    for name, fn in list(vars(sds).items()):
        if name.startswith("_") and callable(fn) and not inspect.isclass(fn):
            try:
                import asyncio as _aio
                if _aio.iscoroutinefunction(fn):
                    continue
                monkeypatch.setattr(sds, name,
                                    lambda *a, _f=None, **k: iter([]))
            except Exception:
                pass
    try:
        search_all_datasets_sync(
            "price for No. 381", "u1", "ws", 2, 5,
            context_texts=["earlier SLE24-16 slitter checked"],
            name_context_texts=["price for No. 381"],
            request_subjects=["No. 381"])
    except Exception:
        pass  # probe may early-out on empty files; token capture is the pin
    joined = " ".join(seen.get("texts") or [])
    assert "381" in joined
    assert "SLE24-16" not in joined, (
        "history-derived subjects must not replace explicit request "
        "subjects in the candidate pool")


def test_background_contract_rides_blackboard():
    from core import async_turn_continuation as atc

    cont = atc.AsyncTurnContinuation(
        continuation_id="c1", user_id="u1", session_id="s1",
        message="prepare the draft", canvas={"canvas_id": "c1"},
        execution_id="e1", agent_id=None, history_snapshot=[])
    cont.request_scope = {"subjects": ["No. 381"],
                          "scope_change": "replace"}
    # the runner builds the blackboard from the persisted contract
    src = open(atc.__file__).read()
    assert '"request_scope": cont.request_scope' in src, (
        "the execution blackboard must reload the persisted request "
        "contract")


async def _run_apply(plan, canvas, contract):
    from core.chat_canvas_editor import apply_canvas_edit
    return await apply_canvas_edit(
        plan, "u1", canvas,
        return_reason=True,
        evidence_contract=contract,
    )


def test_price_changing_op_requires_ready_evidence():
    import asyncio
    plan = cce.CanvasEditPlan(
        wants_edit=True, edit_mode="patch",
        ops=[cce.CanvasPatchOp(
            find="price $1,000.00", replace="price $1,200.00")])
    result, reason = asyncio.run(_run_apply(
        plan,
        {"canvas_id": "c-test-1", "canvas_type": "email",
         "content": {"body": "price $1,000.00"}},
        {"actions": []}))
    assert result is None and reason == "no_ready_evidence_change", (
        "an op changing a price still requires ready, authorized evidence")


def test_formatting_op_proceeds_without_price_actions():
    import asyncio
    async def _fake_update(*a, **k):
        return {"success": True, "audit_id": "a1", "write_outcome":
                "appended"}

    with patch("tools.canvas_crud_tool.update_canvas_content",
               new=_fake_update), \
            patch.object(cce, "_apply_patch_ops",
                         new=lambda content, ops: (
                             {"body": "Hi Steve, please find our updated "
                              "quote below."}, None)):
        plan = cce.CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=[cce.CanvasPatchOp(
                find="Hi Steve,",
                replace="Hi Steve, please find our updated quote "
                        "below.")])
        result, reason = asyncio.run(_run_apply(
            plan,
            {"canvas_id": "c-test-2", "canvas_type": "email",
             "content": {"body": "Hi Steve,"}},
            {"actions": []}))
    assert result is not None, (
        "separately authorized formatting/header work supported by the "
        "existing draft must not be blocked by price-change readiness "
        f"(reason={reason!r})")
