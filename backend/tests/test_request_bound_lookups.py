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
    """Inside the sync search: the request's resolved subjects ARE the
    candidate pool. History texts never enter it, so they can neither
    replace nor displace an explicit subject.

    Observable is the probe's own ``tokens_tried`` receipt — explicit
    subjects are FIRST-CLASS candidates (they bypass the token-extraction
    helper entirely), so asserting on that helper's arguments pins a seam
    this path deliberately does not use.
    """
    import core.sheet_dataset_service as sds

    helper_calls: list = []

    def _capture_helper(texts, **kwargs):
        helper_calls.append(list(texts))
        return ["noise-from-history"]

    monkeypatch.setattr(sds, "candidate_probe_tokens", _capture_helper)
    monkeypatch.setattr(sds, "distinctive_name_tokens", lambda srcs: set())
    # Hermetic: an empty catalog means the scan loop finds nothing and the
    # function returns its receipt instead of touching the database.
    monkeypatch.setattr(sds, "find_entries_sync", lambda *a, **k: [])

    out = search_all_datasets_sync(
        "price for No. 381", "u1", "ws", 2, 5,
        context_texts=["earlier SLE24-16 slitter checked"],
        name_context_texts=["price for No. 381"],
        request_subjects=["No. 381"])

    assert out is not None, "an explicit subject must yield a probe receipt"
    tried = " ".join(str(t) for t in (out.get("tokens_tried") or []))
    assert "381" in tried, (
        f"the request's resolved subject must be probed; tokens_tried={tried!r}")
    assert "sle24" not in tried.lower(), (
        "history-derived subjects must not enter the candidate pool when "
        f"explicit request subjects are bound; tokens_tried={tried!r}")
    assert not helper_calls, (
        "explicit subjects produced first-class tokens, so the history-"
        "supplemented extraction helper must not run at all "
        f"(it was called with {helper_calls})")


def test_subjectless_request_never_supplements_from_history(monkeypatch):
    """When explicit subjects yield no usable tokens the extraction helper
    is the fallback — but it is fed the query and the REQUEST'S subjects
    only. ``context_texts`` (history) still may not enter the pool."""
    import core.sheet_dataset_service as sds

    helper_calls: list = []

    def _capture_helper(texts, **kwargs):
        helper_calls.append(list(texts))
        return ["orphan"]

    monkeypatch.setattr(sds, "candidate_probe_tokens", _capture_helper)
    monkeypatch.setattr(sds, "distinctive_name_tokens", lambda srcs: set())
    monkeypatch.setattr(sds, "find_entries_sync", lambda *a, **k: [])

    out = search_all_datasets_sync(
        "price for No. 381", "u1", "ws", 2, 5,
        context_texts=["earlier SLE24-16 slitter checked"],
        name_context_texts=["price for No. 381"],
        request_subjects=["ab"])   # too short to yield tokens

    assert helper_calls, "the fallback extractor should have been consulted"
    fed = " ".join(" ".join(c) for c in helper_calls).lower()
    assert "sle24" not in fed, (
        f"history must never supplement a bound request scope; fed={fed!r}")
    assert "no. 381" in fed, (
        f"the request's own subjects feed the fallback; fed={fed!r}")
    assert (out or {}).get("subject_scope_unprobed") == ["ab"], (
        "a subject that yielded no tokens is reported, not silently dropped")


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


def test_unchanged_price_formatting_proceeds():
    """Formatting that CARRIES an unchanged price is presentation, not a
    fact change (the old monetary heuristic blocked exactly this)."""
    import asyncio
    with patch("tools.canvas_crud_tool.update_canvas_content",
               new=_fake_update), \
            patch.object(cce, "_apply_patch_ops",
                         new=lambda content, ops: (
                             {"body": "Unit Price: $2,902.00 (CAD)"}, None)):
        plan = cce.CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=[cce.CanvasPatchOp(
                find="Unit Price: $2,902.00",
                replace="Unit Price: $2,902.00 (CAD)")])
        result, reason = asyncio.run(_run_apply(
            plan,
            {"canvas_id": "c-fmt", "canvas_type": "email",
             "content": {"body": "Unit Price: $2,902.00"}},
            {"actions": []}))
    assert result is not None, (
        f"unchanged-value formatting must proceed (reason={reason!r})")


def test_nonpricing_fact_changes_require_evidence():
    """Changed integers, dates and booleans are evidence-dependent facts
    (the old heuristic missed all three)."""
    import asyncio
    for find, replace in (
            ("Ships in 3-4 weeks", "Ships in 2 weeks"),
            ("Valid until 2026-10-01", "Valid until 2026-11-15"),
            ("Status: in stock", "Status: out of stock")):
        plan = cce.CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=[cce.CanvasPatchOp(find=find, replace=replace)])
        result, reason = asyncio.run(_run_apply(
            plan,
            {"canvas_id": "c-fact", "canvas_type": "email",
             "content": {"body": find}},
            {"actions": []}))
        assert result is None and reason == "no_ready_evidence_change", (
            f"{find!r}->{replace!r} must require ready evidence "
            f"(got {reason!r})")


async def _run_fetch(reused, existing_block=None):
    from core.chat_canvas_editor import fetch_fresh_data_section
    return await fetch_fresh_data_section(
        "prepare the draft", [], object(), "u1", canvas=None,
        existing_block=existing_block,
        reused_findings=reused)


def test_durable_finding_reaches_drafting_without_narration():
    """A valid structured receipt (observations present) satisfies the
    edit's evidence need with NO provider call — the finding is reused,
    freshness-labeled, even though narration is absent."""
    import asyncio
    from unittest.mock import patch

    async def _fail_plan(*a, **k):
        raise RuntimeError("narration unavailable — must not be needed")

    reused = {
        "status": "retrieved",
        "rendered": "U-22 | List Price 1,799 | LINMAC sheet row 26",
        "identity": {"file_name": "Consolidated Price List 2019.xlsx"},
        "structured_result": {"targets": [
            {"item": "U-22", "identity": {"status": "single"}}]},
    }
    with patch("core.chat_tool_planner.plan_tool_use",
               side_effect=_fail_plan):
        fresh = asyncio.run(_run_fetch(reused))
    assert fresh.ok and fresh.block, (
        "the durable receipt must satisfy the evidence need")
    assert "REUSED FINDINGS" in fresh.section, (
        "reuse must be freshness-labeled, never 'fetched just now'")


def test_receiptless_prose_does_not_masquerade_as_findings():
    """Text without a structured receipt is NOT valid reuse — the
    planner path runs (text non-emptiness must not establish research).
    """
    import asyncio
    from unittest.mock import patch

    called = {"n": 0}

    async def _fake_plan(*a, **k):
        called["n"] += 1
        return None

    prose_only = {"status": "retrieved", "rendered": "some prose", "identity": {}}
    with patch("core.chat_tool_planner.plan_tool_use",
               side_effect=_fake_plan):
        asyncio.run(_run_fetch(prose_only))
    assert called["n"] >= 1, (
        "receiptless prose must fall through to the planner, not reuse")


def test_findings_without_actions_carry_no_mutation_authority():
    """A read receipt's actions:[] stays intact: FINDING a value does not
    AUTHORIZE changing it. The comparison builder marks edit actions
    authorized ONLY from the caller's explicit authorization list — the
    owner's instruction, never the receipt itself."""
    from core.workbook_read_artifact import build_source_comparison
    obs = [{
        "entity_id": "SLE24-16", "field": "price",
        "raw_value": "8,984", "verification": "verified",
        "currency": "CAD", "basis": "list",
        "source": {"source_id": "wb", "source_type": "workbook",
                   "temporal_role": "decision"},
    }, {
        "entity_id": "SLE24-16", "field": "price",
        "raw_value": "8,880", "verification": "verified",
        "currency": "CAD", "basis": "list",
        "source": {"source_id": "canvas", "source_type": "artifact",
                   "temporal_role": "current"},
    }]
    # NO authorized_actions: findings exist, actions stay blocked
    contract = build_source_comparison(
        obs, requested_entities=["SLE24-16"],
        requested_fields=["price"],
        artifact_source_ids=["canvas"],
        decision_source_ids=["wb"], authorized_actions=[])
    blocked = contract.get("blocked_actions") or []
    assert blocked and all(
        a.get("authorized") is not True for a in blocked), (
        "a receipt without owner authorization must not mark any edit "
        "action authorized")
    # WITH the owner's authorization: the same evidence yields a ready action
    contract2 = build_source_comparison(
        obs, requested_entities=["SLE24-16"],
        requested_fields=["price"],
        artifact_source_ids=["canvas"],
        decision_source_ids=["wb"],
        authorized_actions=["edit_artifact"])
    ready = [a for a in (contract2.get("actions") or [])
             if a.get("status") == "ready"
             and a.get("authorized") is True]
    assert ready, (
        "the owner's explicit authorization is what turns the finding "
        "into an applicable action")


def test_agent_less_turn_still_derives_required_sources():
    """The value-trial seam: a plain chat request carries NO agent_id —
    the lessons lookup used to return [] (and required-sources stayed
    empty, so the planner-boundary chaining never fired and the
    workbook check routed to memory). The teaching fallback reads from
    the workspace's agents WITH lessons. Pinned against an INJECTED
    registry session (test DB has no teaching)."""
    import json
    import integrations.chat_orchestrator as orch_mod

    orch = orch_mod.ChatOrchestrator.__new__(orch_mod.ChatOrchestrator)

    class _Agent:
        def __init__(self, aid, cfg):
            self.id = aid
            self.configuration = cfg

    _LESSON = {"id": "l1", "lesson": "price list 2019 in zoho workdrive "
               "has the most common formulas"}

    class _Query:
        def __init__(self, agents):
            self._agents = agents

        def limit(self, n):
            return self

        def all(self):
            return self._agents

    class _DB:
        def __init__(self, agents):
            self._agents = agents

        def query(self, *a, **k):
            return _Query(self._agents)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    db = _DB([
        _Agent("hire-1", json.dumps({"learning": {"log": [_LESSON]}})),
        _Agent("hire-2", json.dumps({"learning": {"log": []}})),
    ])

    def _fake_gl(db, aid, query=None, limit=5):
        return ([_LESSON] if aid == "hire-1" else [])

    import core.student_learning_service as sls
    orig_gl = sls.get_agent_lessons
    sls.get_agent_lessons = _fake_gl
    try:
        out = orch._lessons_from_taught_agents(db, "price basis", 5)
    finally:
        sls.get_agent_lessons = orig_gl
    assert out, "the fallback must read teaching from agents that have it"
    assert "price list" in str(out[0].get("lesson"))

    # and the required-source derivation consumes it
    req = orch._required_research_sources(
        agent_id=None, message="check the price list workbook")
    assert isinstance(req, set)


def test_datasets_receipt_findings_persist_association():
    """B1 (owner correction 2026-10-09): dispatch is not retrieval, and
    retrieval that never persists leaves the job findings-less. The
    receipt's hit digest converts to typed findings carrying the full
    association (item, field, value, file, sheet, hash, ingested)."""
    from integrations.chat_orchestrator import (
        _findings_from_datasets_receipt)

    receipt = {"datasets_search": {"_hits": [{
        "file_name": "Consolidated Price List 2019.xlsx",
        "entity_name": "Tennsmith",
        "content_hash": "ce61dd3d40cac",
        "ingested_at": "2026-10-03T01:34:18",
        "rows": [{"MODEL NO.": "SLE24-16", "PRICE": "8984"}],
    }]}}
    fnd = _findings_from_datasets_receipt(receipt)
    assert fnd and fnd[0]["item"] == "SLE24-16"
    assert fnd[0]["value"] == "8984"
    assert fnd[0]["source_file_name"] == "Consolidated Price List 2019.xlsx"
    assert fnd[0]["sheet"] == "Tennsmith"
    assert fnd[0]["content_hash"] == "ce61dd3d40cac"
    assert fnd[0]["field"] == "price"
    # no digest / prose-only -> no findings fabricated
    assert _findings_from_datasets_receipt({"datasets_search": {}}) == []
    assert _findings_from_datasets_receipt({}) == []


def test_teaching_fallback_authority_rules():
    """B2 (owner correction 2026-10-09): agent-less turns use ONE
    deterministic scope — a single designating hire, or several hires
    sharing ONE corpus (same training); genuinely different corpora stay
    explicit (no silent merge)."""
    import json
    import integrations.chat_orchestrator as orch_mod

    orch = orch_mod.ChatOrchestrator.__new__(orch_mod.ChatOrchestrator)

    class _Agent:
        def __init__(self, aid, lessons):
            self.id = aid
            self.configuration = json.dumps(
                {"learning": {"log": lessons}})

    class _Query:
        def __init__(self, agents):
            self._a = agents
        def limit(self, n):
            return self
        def all(self):
            return self._a

    class _DB:
        def __init__(self, agents):
            self._a = agents
        def query(self, *a, **k):
            return _Query(self._a)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    L_A = [{"id": "a1", "lesson": "price list workbook is the basis"}]
    L_B = [{"id": "b1", "lesson": "NEVER use the price list; email only"}]

    def run(agents):
        db = _DB(agents)
        def gl(db, aid, query=None, limit=30):
            m = {"h1": L_A, "h2": L_A, "h3": L_B}
            return m.get(aid, [])
        import core.student_learning_service as sls
        orig = sls.get_agent_lessons
        sls.get_agent_lessons = gl
        try:
            return orch._lessons_from_taught_agents(db, "price", 5)
        finally:
            sls.get_agent_lessons = orig

    # several hires, SAME corpus -> single authority, teaching returned
    out = run([_Agent("h1", L_A), _Agent("h2", L_A)])
    assert out, "same-corpus designating hires are one authority"
    # genuinely different corpora -> explicit ambiguity, nothing merged
    out2 = run([_Agent("h1", L_A), _Agent("h3", L_B)])
    assert out2 == [], (
        "different teachings must stay explicit — no silent merge of "
        "conflicting business rules")


def test_swapped_prices_require_ready_evidence():
    """Token equality is not fact equality: swapping two rows' prices
    preserves the value BAG but changes both associations — the
    association rule (field-contract values in first-occurrence order)
    must catch it."""
    import asyncio
    plan = cce.CanvasEditPlan(
        wants_edit=True, edit_mode="patch",
        ops=[cce.CanvasPatchOp(
            find="381 roll bender $2,902.00 | U-22 bead roller "
                 "$1,777.00",
            replace="381 roll bender $1,777.00 | U-22 bead roller "
                    "$2,902.00")])
    result, reason = asyncio.run(_run_apply(
        plan,
        {"canvas_id": "c-swap", "canvas_type": "email",
         "content": {"body": "381 roll bender $2,902.00 | U-22 bead "
                              "roller $1,777.00"}},
        {"outcomes": [
            {"entity_id": "381", "field": "price",
             "evidence": [{"raw_value": "2902.00"}]},
            {"entity_id": "U-22", "field": "price",
             "evidence": [{"raw_value": "1777.00"}]},
        ], "actions": []}))
    assert result is None and reason == "no_ready_evidence_change", (
        f"a value swap must require ready evidence (got {reason!r})")


def test_changed_tracked_text_field_requires_ready_evidence():
    """A contract-tracked TEXT fact (e.g. a contractor name bound to an
    entity-field) is an association change, not presentation."""
    import asyncio
    plan = cce.CanvasEditPlan(
        wants_edit=True, edit_mode="patch",
        ops=[cce.CanvasPatchOp(
            find="Installed by Acme Mechanical Ltd.",
            replace="Installed by Northgate Services Inc.")])
    result, reason = asyncio.run(_run_apply(
        plan,
        {"canvas_id": "c-text", "canvas_type": "email",
         "content": {"body": "Installed by Acme Mechanical Ltd."}},
        {"outcomes": [
            {"entity_id": "installer", "field": "contractor",
             "evidence": [{"raw_value": "Acme Mechanical Ltd."}]},
        ], "actions": []}))
    assert result is None and reason == "no_ready_evidence_change", (
        f"a tracked text-field change must require ready evidence "
        f"(got {reason!r})")


def test_authorized_unassertion_proceeds_without_evidence():
    """Deleting an unverified line asserts nothing — the evidence
    requirement protects ASSERTIONS, and the T_AUTH's own words
    ("leave anything unresolved unasserted") authorize removals. The
    artifact-level scope guards still police identity-dropping."""
    import asyncio
    async def _fake_update(*a, **k):
        return {"success": True, "audit_id": "a9",
                "write_outcome": "appended"}
    with patch("tools.canvas_crud_tool.update_canvas_content",
               new=_fake_update), \
            patch.object(cce, "_apply_patch_ops",
                         new=lambda content, ops: (
                             {"body": "Row 5 price line"}, None)):
        plan = cce.CanvasEditPlan(
            wants_edit=True, edit_mode="patch",
            ops=[cce.CanvasPatchOp(
                find="Unverified: $2,902.00 pending vendor",
                replace="")])
        result, reason = asyncio.run(_run_apply(
            plan,
            {"canvas_id": "c-unassert", "canvas_type": "email",
             "content": {"body": "Unverified: $2,902.00 pending "
                                  "vendor"}},
            {"actions": []}))
    assert result is not None, (
        f"a removal-only op must proceed under authorization "
        f"(reason={reason!r})")


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


async def _fake_update(*a, **k):
    return {"success": True, "audit_id": "a1", "write_outcome":
            "appended"}


def test_formatting_op_proceeds_without_price_actions():
    import asyncio

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
