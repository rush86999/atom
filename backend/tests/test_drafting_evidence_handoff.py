# -*- coding: utf-8 -*-
"""Research -> drafting evidence handoff (Repair 1 of the 2026-10-08 guide).

The drafting contract must be built from the job's ACTUAL durable typed
findings, not from resolved-question prose. A resolved question is history
and may represent scoped absence, supersession, or an informational
disposition — it is not automatically a verified fact.

Record shape is the real persisted shape captured from the live ledger
(goal_runs parameters.task_lifecycle.operations[].execution.findings):

    {"field": "completion_date", "column": "Completion Date",
     "raw": "2026-11-15",
     "parsed": {"value": "2026-11-15", "raw": "2026-11-15"},
     "source": "Plan.xlsx!Projects!row10"}

sitting on an operation whose execution carries
{invoked, outcome, served_basis, freshness_status, items, findings, ...}.

Required pins (guide, Repair 1):
1. four typed findings survive into the planner input
2. a scoped miss is not verified evidence
3. protected manual value survives exactly
4. two differently configured agents receive their own teaching
5. a fork inherits permitted findings without acquiring mutation authority
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest

import integrations.chat_orchestrator as chat


def _tl_returning(record):
    """A lifecycle stub exposing the lookup as a METHOD — the real
    ``find_active_task_for_canvas`` is a TaskLifecycle method, not a
    module function (the old adapter imported it as one and the
    ImportError was swallowed, so it always returned None)."""
    return SimpleNamespace(
        find_active_task_for_canvas=lambda canvas_id: record,
        find_active_task=lambda conv: record)


# --- the real persisted shape -------------------------------------------

def typed_finding(field, column, raw, parsed, source):
    return {"field": field, "column": column, "raw": raw,
            "parsed": parsed, "source": source}


def op_with_findings(operation_id, findings, *, items=None,
                     outcome="read_succeeded", served_basis="saved_copy",
                     freshness_status=None):
    """An operation row carrying typed findings on its execution facts."""
    return {
        "operation_id": operation_id,
        "operation_type": "retrieve",
        "status": "applied",
        "requested_change": "read Plan.xlsx for Site A Expansion",
        "execution": {
            "invoked": True,
            "outcome": outcome,
            "served_basis": served_basis,
            "freshness_status": freshness_status,
            "items": items or {},
            "findings": findings,
            "failure_stage": None,
            "planning": None,
            "raw_outcome": outcome,
            "at": "2026-10-07T22:20:59Z",
        },
    }


def job_record(operations, *, unresolved=None, canvas_id="cv-1"):
    return {
        "run_id": "run-1",
        "conversation_id": "s-1",
        "canvas_id": canvas_id,
        "task_revision": {
            "objective_id": "obj-1",
            "revision": 3,
            "goal_text": "verify the quote and draft the email",
            "entities": [{"id": "Site A Expansion", "label": "Site A Expansion"}],
            "requested_fields": ["completion_date", "contractor"],
            "authorized_actions": ["retrieve", "present", "calculate",
                                   "edit"],
            "unresolved": unresolved or [],
        },
        "operations": operations,
    }


FOUR_FINDINGS = [
    typed_finding("completion_date", "Completion Date", "2026-11-15",
                  {"value": "2026-11-15", "raw": "2026-11-15"},
                  "Plan.xlsx!Projects!row10"),
    typed_finding("contractor", "Contractor", "Delta Builders Ltd.",
                  {"value": "Delta Builders Ltd.", "raw": "Delta Builders Ltd."},
                  "Plan.xlsx!Projects!row10"),
    typed_finding("unit_price", "Unit Price", "2,902.00",
                  {"value": 2902.0, "currency": "USD", "basis": "each",
                   "raw": "2,902.00"},
                  "Price List.xlsx!Sheet1!row1"),
    typed_finding("lead_time", "Lead Time", "12",
                  {"value": 12, "unit": "days", "raw": "12"},
                  "Plan.xlsx!Projects!row10"),
]


class TestTypedFindingsReachThePlanner:
    """Repair 1 items 2-3: read operation execution.findings and keep
    subject, field, value, basis/unit/currency, source identity and
    freshness qualification TOGETHER."""

    def _findings(self, record):
        orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
        orch.tenant_id = "default"
        with patch.object(chat, "_task_lifecycle_for",
                          return_value=_tl_returning(record)):
            return orch._canvas_job_findings(
                "u1", {"canvas_id": "cv-1"}, {"id": "s-1"},
                "draft the email", agent_id="agent-alpha")

    def test_four_typed_findings_survive_into_the_planner_input(self):
        rec = job_record([op_with_findings(
            "op-1", FOUR_FINDINGS,
            items={"Site A Expansion": "row10"},
            freshness_status="saved_copy_unverified")])
        out = self._findings(rec)
        assert out is not None, "a job with typed findings must yield a section"
        section = out.get("typed_findings") or []
        assert len(section) == 4, (
            f"all four typed findings must survive; got {len(section)}: "
            f"{section}")

    def test_finding_keeps_field_value_basis_source_and_freshness_together(self):
        rec = job_record([op_with_findings(
            "op-1", [FOUR_FINDINGS[2]],
            items={"Site A Expansion": "row10"},
            served_basis="saved_copy",
            freshness_status="saved_copy_unverified")])
        out = self._findings(rec)
        (f,) = out.get("typed_findings") or []
        # field
        assert f.get("field") == "unit_price"
        # parsed value + basis/unit/currency
        assert (f.get("parsed") or {}).get("value") == 2902.0
        assert (f.get("parsed") or {}).get("currency") == "USD"
        assert (f.get("parsed") or {}).get("basis") == "each"
        # source identity
        assert f.get("source") == "Price List.xlsx!Sheet1!row1"
        # subject
        assert f.get("subject") == "Site A Expansion"
        # operation id
        assert f.get("operation_id") == "op-1"
        # freshness qualification — never claimed as current
        assert f.get("served_basis") == "saved_copy"
        assert f.get("freshness_status") == "saved_copy_unverified"

    def test_resolution_prose_is_supplemental_not_verified_fact(self):
        """A resolved question is HISTORY. It must not be presented as a
        verified finding, and must never stand in for one."""
        rec = job_record(
            [op_with_findings("op-1", [FOUR_FINDINGS[0]],
                              items={"Site A Expansion": "row10"})],
            unresolved=[{
                "question_id": "q1", "item": "Unit Price",
                "question": "which basis applies to unit price?",
                "kind": "business_decision", "status": "resolved",
                "resolution": "the owner chose 'each' at 2,902.00",
                "attempts": 1,
            }])
        out = self._findings(rec)
        verified_items = [f.get("field") for f in (out.get("typed_findings")
                                                   or [])]
        assert verified_items == ["completion_date"], (
            "only the operation's typed finding is verified; the resolved "
            f"question must not join it: {verified_items}")
        notes = " ".join(str(x) for x in (out.get("resolution_notes") or []))
        assert "owner chose" in notes, (
            "the resolution prose is still available as supplemental "
            f"explanation: {notes!r}")

    def test_scoped_miss_is_not_verified_evidence(self):
        """An operation that found NOTHING is a scoped absence — it must
        never surface as a verified value."""
        rec = job_record([op_with_findings(
            "op-1", [],
            items={"Roper Whitney 381": "absent"},
            outcome="read_succeeded",
            freshness_status=None)])
        out = self._findings(rec)
        assert not (out or {}).get("typed_findings"), (
            "an empty findings list is a scoped miss, not a verified fact")
        misses = (out or {}).get("scoped_misses") or []
        assert any("381" in str(m) for m in misses), (
            f"the scoped miss must be stated, not hidden: {misses}")


class TestProtectedManualValues:
    """Repair 1 item 4: protected values come from OWNER-INSTRUCTION
    provenance, not from a word match in a note."""

    def test_protected_manual_value_survives_exactly(self):
        orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
        orch.tenant_id = "default"
        rec = job_record([op_with_findings("op-1", [], items={})])
        rec["task_revision"]["unresolved"] = []
        # Established owner-instruction provenance: a business decision
        # RESOLVED BY THE OWNER carrying the value. Not a word match.
        rec["task_revision"]["unresolved"] = [{
            "question_id": "q-manual", "item": "No. 381",
            "question": "which unit price applies to No. 381?",
            "kind": "business_decision", "status": "resolved",
            "decision_owner": "owner",
            "resolution": {"detail": "$2,902.00", "value": "$2,902.00",
                           "field": "Unit Price"},
            "attempts": 1,
        }]
        with patch.object(chat, "_task_lifecycle_for",
                          return_value=_tl_returning(rec)):
            out = orch._canvas_job_findings(
                "u1", {"canvas_id": "cv-1"}, {"id": "s-1"},
                "prepare the email draft now", agent_id="agent-alpha")
        preserved = out.get("manual_preserved") or []
        assert any("2,902.00" in str(p) and "381" in str(p)
                   for p in preserved), (
            f"the owner's exact manual value must survive: {preserved}")

    def test_word_match_in_a_note_is_not_authority(self):
        """The inverse: prose containing 'approved' must not mint a
        protected value."""
        orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
        orch.tenant_id = "default"
        rec = job_record(
            [op_with_findings("op-1", [], items={})],
            unresolved=[{
                "question_id": "q1", "item": "Unit Price",
                "question": "which price?", "kind": "verification",
                "status": "resolved",
                "decision_owner": None,
                "resolution": "the note says the price was approved last "
                              "year by someone",
                "attempts": 1,
            }])
        with patch.object(chat, "_task_lifecycle_for",
                          return_value=_tl_returning(rec)):
            out = orch._canvas_job_findings(
                "u1", {"canvas_id": "cv-1"}, {"id": "s-1"},
                "prepare the email draft now", agent_id="agent-alpha")
        assert not (out.get("manual_preserved") or []), (
            "a word match in a note must not create a protected value: "
            f"{out.get('manual_preserved')}")


class TestAgentScopedTeaching:
    """Repair 1 items 1 and 5: the acting agent identity is threaded
    explicitly (never an unbound name), and two differently configured
    agents each get their OWN teaching."""

    def test_agent_identity_is_threaded_not_an_unbound_name(self):
        """Regression for the swallowed NameError: `_canvas_job_findings`
        referenced `agent_id` although the signature never received it, so
        lesson retrieval silently did nothing."""
        import inspect

        sig = inspect.signature(chat.ChatOrchestrator._canvas_job_findings)
        assert "agent_id" in sig.parameters, (
            "the acting agent identity must be an explicit parameter, "
            f"not a swallowed unbound name; got {list(sig.parameters)}")

    def test_two_agents_receive_their_own_teaching(self):
        def lessons_for(agent_id):
            orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
            orch.tenant_id = "default"
            rec = job_record([op_with_findings("op-1", [], items={})])
            captured = {}

            def fake_lessons(db, aid, **kw):
                captured["agent_id"] = aid
                return [{"lesson": f"rule for {aid}"}] if aid else []

            with patch.object(chat, "_task_lifecycle_for",
                              return_value=_tl_returning(rec)), \
                 patch("core.student_learning_service.get_agent_lessons",
                       fake_lessons):
                out = orch._canvas_job_findings(
                    "u1", {"canvas_id": "cv-1"}, {"id": "s-1"},
                    "prepare the email draft now",
                    agent_id=agent_id)
            return out, captured

        out_a, cap_a = lessons_for("agent-alpha")
        out_b, cap_b = lessons_for("agent-beta")
        assert cap_a["agent_id"] == "agent-alpha"
        assert cap_b["agent_id"] == "agent-beta"
        rules_a = " ".join(str(r) for r in (out_a or {}).get("taught_rules")
                           or [])
        rules_b = " ".join(str(r) for r in (out_b or {}).get("taught_rules")
                           or [])
        assert rules_a != rules_b, (
            "two differently configured agents must not share teaching: "
            f"{rules_a!r} vs {rules_b!r}")


class TestNoHardcodedBusinessIdentities:
    """Repair 1 item 5: contacts and header rules come from the agent's
    teaching and verified correspondence — not hardcoded people."""

    def test_no_hardcoded_people_in_the_adapter_source(self):
        import inspect

        src = inspect.getsource(chat.ChatOrchestrator._canvas_job_findings)
        for banned in ("brennan", "chandrakant", "vipul",
                       "amacisaac", "alumasafway", "quote for slitter"):
            assert banned not in src.lower(), (
                f"the drafting evidence adapter hardcodes a business "
                f"identity ({banned!r}); contacts must come from teaching "
                f"and verified correspondence")


class TestForkInheritanceIsEvidenceOnly:
    """Repair 1 pin 5: a fork inherits the source's PERMITTED findings
    without acquiring the source's mutation authority."""

    def test_fork_inherits_findings_but_not_mutation_authority(self):
        orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
        orch.tenant_id = "default"
        source = job_record([op_with_findings(
            "op-src", [FOUR_FINDINGS[0]],
            items={"Site A Expansion": "row10"})],
            canvas_id="cv-parent")
        # The SOURCE job's revision authorises editing; the FORK's own
        # revision does not.
        source["task_revision"]["authorized_actions"] = [
            "retrieve", "present", "edit"]

        import core.models as models

        class _ForkRow:
            details_json = {"source_canvas_id": "cv-parent"}
            metadata_json = None

        class _Q:
            def filter(self, *a, **k):
                return self

            def order_by(self, *a, **k):
                return self

            def first(self):
                return _ForkRow()

        class _DB:
            def query(self, *a, **k):
                return _Q()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        # The FORK has its own empty job; only the SOURCE canvas resolves
        # to the research record.
        fork_tl = SimpleNamespace(
            find_active_task_for_canvas=lambda cid: (
                source if cid == "cv-parent" else None),
            find_active_task=lambda conv: None)
        with patch.object(chat, "_task_lifecycle_for",
                          return_value=fork_tl), \
             patch("core.database.get_db_session", lambda: _DB()):
            out = orch._canvas_job_findings(
                "u1", {"canvas_id": "cv-fork"}, {"id": "s-fork"},
                "prepare the email draft now", agent_id="agent-alpha")

        assert out.get("inherited_from") == "cv-parent", (
            f"the fork must reach the source's research: {out}")
        assert (out.get("typed_findings") or []), (
            "inherited findings must be present")
        assert out.get("mutation_authority_inherited") is False, (
            "a fork inherits EVIDENCE, never the source's mutation "
            "authority")


class TestHandoffReachesThePlannerInput:
    """The whole point of Repair 1: the durable research reaches the
    EDIT PLANNER'S INPUT. Not just the adapter's dict."""

    def test_typed_finding_renders_into_the_planner_section(self):
        from core.chat_canvas_editor import _job_findings_section

        orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
        orch.tenant_id = "default"
        rec = job_record([op_with_findings(
            "op-1", [FOUR_FINDINGS[2]],
            items={"Site A Expansion": "row10"},
            served_basis="saved_copy",
            freshness_status="saved_copy_unverified")])
        with patch.object(chat, "_task_lifecycle_for",
                          return_value=_tl_returning(rec)):
            findings = orch._canvas_job_findings(
                "u1", {"canvas_id": "cv-1"}, {"id": "s-1"},
                "prepare the email draft now", agent_id="agent-alpha")
        section = _job_findings_section(findings)
        assert section.strip(), "the planner section must not be empty"
        assert "2,902.00" in section or "2902" in section, (
            f"the researched value must reach the planner input: {section}")
        assert "Price List.xlsx" in section, (
            f"the source identity must reach the planner input: {section}")
        assert "unverified" in section.lower() or "saved_copy" in section, (
            f"the freshness qualification must reach the planner input: "
            f"{section}")

    def test_presentation_only_drafting_needs_no_invented_price_pair(self):
        """The guide's rule: presentation-only drafting must not require
        invented changed-price pairs. With typed findings present and NO
        comparable-changed pair, the section still hands the planner real
        evidence — nothing is invented to satisfy a gate."""
        from core.chat_canvas_editor import _job_findings_section

        orch = chat.ChatOrchestrator.__new__(chat.ChatOrchestrator)
        orch.tenant_id = "default"
        rec = job_record([op_with_findings(
            "op-1", [FOUR_FINDINGS[0], FOUR_FINDINGS[1]],
            items={"Site A Expansion": "row10"})])
        with patch.object(chat, "_task_lifecycle_for",
                          return_value=_tl_returning(rec)):
            findings = orch._canvas_job_findings(
                "u1", {"canvas_id": "cv-1"}, {"id": "s-1"},
                "prepare the email draft now", agent_id="agent-alpha")
        section = _job_findings_section(findings)
        # Real evidence is handed over...
        assert "Delta Builders" in section
        # ...and nothing claims a price CHANGE that was never observed.
        assert "changed" not in section.lower() or "unresolved" in section.lower(), (
            f"no invented changed-price pair: {section}")


class TestReusedEvidenceIsNotCalledFresh:
    """Repair 2 (guide) + the regression for the captured failed transition.

    Live case-1 trial, session 38a1c3d0, continuation de3dd9d2
    (2026-10-08): three attempts, the served planner DECLINED
    (wants_edit=False) twice and attempt 3 was skipped by the budget
    floor. READBACK-DECISION on both served attempts recorded
    ``evidence_contract=False`` — the drafting planner had NO verified
    pairs even though this conversation had already read the workbook.
    The turn's own reply said it plainly: "the workbook ... was retrieved
    earlier in this conversation but was not re-returned now."

    Guide Repair 2 item 3: never call an old block freshly fetched simply
    because this turn reused it. Required pin: saved-copy reuse stays
    freshness-qualified.
    """

    def test_a_reused_block_is_not_labelled_fetched_just_now(self):
        import inspect

        from core import chat_canvas_editor as cce

        src = inspect.getsource(cce.fetch_fresh_data_section)
        # Only the EXISTING-BLOCK reuse path is under test here: it reformats
        # an earlier leg's block and must not advertise a fresh fetch.
        at = src.index("if existing_block:")
        tail = src[at:at + 700]
        assert "fetched just now" not in tail, (
            "the existing-block reuse path must not claim the block was "
            f"fetched just now; it currently reads:\n{tail[:400]}")

    def test_saved_copy_reuse_stays_freshness_qualified(self):
        import inspect

        from core import chat_canvas_editor as cce

        src = inspect.getsource(cce.fetch_fresh_data_section)
        at = src.index("REUSED FINDINGS")
        window = src[at - 200:at + 700]
        assert "not re-fetched this turn" in window, (
            "reused findings must say they were not re-fetched this turn")
        assert "source identity and revision" in window, (
            "reused findings must carry their original source identity and "
            f"revision; window reads:\n{window[:400]}")

    def test_reuse_supplies_the_evidence_contract_from_the_completed_read(self):
        """The captured transition's exact defect: evidence_contract=False
        while a completed read existed. Receipt-based reuse must hand the
        drafting planner the contract that read produced, or the planner
        has nothing verified to apply and declines."""
        import asyncio

        from core import chat_canvas_editor as cce

        contract = {"contract_version": 2,
                    "coverage": {"requested_entities": ["381"],
                                 "requested_fields": ["unit_price"],
                                 "outcome_count": 1, "complete": True},
                    "actions": [], "evidence_ids": ["ev-1"]}
        reused = {
            # Validity is the STRUCTURED RECEIPT, not text non-emptiness.
            "source_observations": [{"item": "381", "value": 2035}],
            "rendered": "381: E66=2035 [basis=PRICE]",
            "identity": {"file_name": "Price List.xlsx"},
            "objective_evidence": contract,
        }

        out = asyncio.run(cce.fetch_fresh_data_section(
            message="prepare the draft now",
            history=[],
            llm_service=None,
            user_id="u1",
            canvas_id="cv-1",
            reused_findings=reused,
            existing_evidence_contract=None))

        assert out.evidence_contract == contract, (
            "the completed read's contract must reach the drafting "
            f"planner; got {out.evidence_contract!r}")
        assert out.ok and out.needed is False
        assert "REUSED FINDINGS" in (out.section or ""), out.section

    def test_receiptless_prose_does_not_satisfy_the_evidence_need(self):
        """The mirror pin: text non-emptiness must NOT establish successful
        research (guide Repair 2 item 2)."""
        import asyncio

        from core import chat_canvas_editor as cce

        out = asyncio.run(cce.fetch_fresh_data_section(
            message="prepare the draft now",
            history=[],
            llm_service=None,
            user_id="u1",
            canvas_id="cv-1",
            reused_findings={
                "rendered": "lots of confident prose but no receipt",
            },
            existing_evidence_contract=None))
        assert out.evidence_contract is None, (
            "receiptless prose must not mint an evidence contract: "
            f"{out.evidence_contract!r}")


class TestChainToContractEndToEnd:
    """Guide instruction 2: chain -> stored receipt -> drafting caller ->
    planner contract, INCLUDING unavailable narration, with subject, field,
    value, source/version and freshness preserved together.

    This is the seam the captured case-1 transition died on. The chained
    confirmed-file read persisted its structured receipt into
    ``_pending_file_result`` but NOT the rendered evidence, and the
    drafting caller's receipt-based reuse requires both — so a read that
    had produced real findings was reported to the planner as none.
    """

    CARRIER_INPUT = {
        # The named-file reader's real ``storage_read`` shape (captured
        # from the live workbook read).
        "rendered_answer": (
            "PER-ITEM OUTCOMES ... | 381 | FOUND | RoperWhitney!A66 R66 "
            "(values: E66=2035 [basis=PRICE], M66=1172 [basis=U.S. LIST]) |"),
        "workbook_read": {"sheets": 41},
        "structured_result": {
            "schema_version": 1,
            "evidence_action": "new_read",
            "evidence_revision":
                "c01b108a3ca1019111f09ecf0dbda5d9996aa4c5:"
                "2026-10-08T21:14:01.594636",
            "source_identity": {
                "file_name": "Copy of Consolidated Price List 2019 - "
                             "Linmac Update.xlsx",
                "service": "datasets",
                "source": "zoho_workdrive",
                "resource_id": "9ef83433837cdf6b841b6b7604d64e24dab42",
                "content_hash": "c01b108a3ca1019111f09ecf0dbda5d9996aa4c5",
                "ingested_at": "2026-10-08T21:14:01.594636",
                "source_modified_at": None,
                "live_vs_saved": "saved copy",
                "evidence_kind": "materialized_copy",
            },
            "targets": [{
                "item": "381",
                "field": {"status": "competing", "values": [
                    {"col": "E66", "basis": "PRICE", "kind": "number",
                     "value": 2035.0, "display": "2,035"},
                    {"col": "M66", "basis": "U.S. LIST", "kind": "number",
                     "value": 1172.0, "display": "1,172"}]},
                "identity": {"status": "single", "candidates": [
                    {"ref": "RoperWhitney!R66"}]},
                "retrieval": {"status": "searched", "error_category": None},
                "scope_receipt": {"authorization": "granted"},
            }],
            "coverage": {"read_status": "success"},
        },
    }

    def _carrier(self):
        """What the chained-read persist must produce (see the merge in
        chat_orchestrator's value-trace -> confirmed-file read)."""
        sr = self.CARRIER_INPUT
        return {
            "status": "retrieved",
            "identity": {"file_name": sr["structured_result"][
                "source_identity"]["file_name"], "execution_id": "e1"},
            "workbook_read": sr.get("workbook_read"),
            "structured_result": sr.get("structured_result"),
            "rendered": sr.get("rendered_answer") or "",
            "execution_id": "e1",
            "retrieved_at": 0.0,
            "chained_read": True,
        }

    def test_the_chained_read_persists_the_rendered_evidence(self):
        """The regression: the carrier must carry `rendered` alongside the
        structured receipt. `rendered` is the carrier's canonical key."""
        import inspect

        from integrations import chat_orchestrator as co

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        at = src.index("chained_read")
        window = src[max(0, at - 2500):at]
        assert '"rendered"' in window, (
            "the chained-read carrier persist must set the canonical "
            f"'rendered' key; the block reads:\\n{window[-700:]}")

    def test_chain_receipt_reaches_the_planner_with_unavailable_narration(self):
        """Guide instruction 2 end to end: with the LLM unavailable the
        already-read evidence still reaches the drafting planner."""
        import asyncio

        from core import chat_canvas_editor as cce

        out = asyncio.run(cce.fetch_fresh_data_section(
            message="prepare the draft now",
            history=[],
            llm_service=None,          # narration unavailable
            user_id="u1",
            canvas_id="cv-1",
            reused_findings=self._carrier(),
            existing_evidence_contract=None))

        assert out.needed is False and out.ok
        assert out.evidence_contract is not None, (
            "the chained read's contract must reach the planner with no "
            f"model available; got {out.evidence_contract!r}")

    def test_subject_field_value_source_and_freshness_survive_together(self):
        import asyncio

        from core import chat_canvas_editor as cce

        out = asyncio.run(cce.fetch_fresh_data_section(
            message="prepare the draft now",
            history=[],
            llm_service=None,
            user_id="u1",
            canvas_id="cv-1",
            reused_findings=self._carrier(),
            existing_evidence_contract=None))
        section = (out.section or "").lower()
        contract = out.evidence_contract or {}

        # subject and value are visible to the planner
        assert "381" in section, out.section
        assert "2035" in section and "price" in section, out.section
        # source cell identity
        assert "roperwhitney!a66" in section, out.section
        # the reuse never claims a fresh fetch
        assert "not re-fetched this turn" in section, out.section

        # source/version and freshness ride the CONTRACT together with
        # the subject, field and value.
        rows = [e for e in (contract.get("evidence") or [])
                if e.get("entity_id") == "381"]
        assert rows, contract.get("evidence")
        ev = next(e for e in rows if e.get("basis") == "PRICE")
        assert ev.get("field"), ev                       # field
        assert ev.get("current_value") == 2035.0, ev     # value
        assert ev.get("basis") == "PRICE", ev            # basis
        assert ev.get("source") == "RoperWhitney!R66", ev  # source cell
        assert ev.get("content_hash"), ev                # version
        assert ev.get("source_version"), ev              # revision
        assert ev.get("freshness"), ev                   # freshness
        assert contract.get("source", {}).get("evidence_kind") == (
            "materialized_copy"), contract.get("source")
        # and the read authorized NO value-changing edit
        assert contract.get("actions") == [], (
            "a read receipt never authorizes a value change: "
            f"{contract.get('actions')}")
