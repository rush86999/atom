"""Confirmation-path review handoff.

A review read is evidence, not the answer.  These tests exercise the
production confirmation path: the direct reader times out, a bounded replan
executes ONE subject-bound read, and that receipt must supply the review
prompt/assessment/delivery without an older empty-item carrier standing in.

The model is controlled here on purpose: this isolates handoff correctness
from provider latency.  A real-model smoke check belongs after this passes.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import core.chat_tool_planner as planner
import integrations.chat_orchestrator as chat
from core.answer_presentation import build_structured_record, build_targets_from_scan
from core.pending_file_task import FILE_TASK_SESSION_KEY
from core.review_contract import build_accepted_contract
from core.review_handoff import (
    reject_conflicting_identity_fields,
    validate_read_receipt,
)

REVIEW_ASK = (
    "Using the uploaded orders.xlsx, review order O-1010 against the "
    "order processing policy. Cite Order ID, Status, Qty, Unit Price, "
    "Currency, Approval 1, Approval 2, Manager Exception, and Notes "
    "from the row. State process or escalate."
)
LESSONS = [{
    "id": "policy-1",
    "topic": "Order processing policy",
    "scope": "global",
    "lesson": "Recommend process; escalate exceptions.",
    "decision_options": ["Process", "Escalate"],
}]


def _orch():
    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m", "provider": "p",
    })
    orch.llm_service = llm
    return orch


def _targets(subject: str = "O-1010", status: str = "On Hold"):
    return build_targets_from_scan(
        [subject],
        {subject: {
            "status": "found",
            "evidence": [{
                "sheet": "Orders",
                "row": 2,
                "values": [
                    {"cell": "A2", "field": "Order ID", "value": subject},
                    {"cell": "B2", "field": "Status", "value": status},
                ],
            }],
        }},
        {},
    )


def _record(
    *,
    subject: str = "O-1010",
    file_name: str = "orders.xlsx",
    resource_id: str = "r1",
    content_hash: str = "hash-1",
    targets=None,
    attempt_id: str = "attempt-replan",
    evidence_revision: str = "hash-1:2026-10-27",
):
    return build_structured_record(
        source_identity={
            "file_name": file_name,
            "service": "datasets",
            "resource_id": resource_id,
            "content_hash": content_hash,
        },
        evidence_revision=evidence_revision,
        attempt_id=attempt_id,
        evidence_action="new_read",
        requested_items=[subject],
        requested_fields=["Status"],
        targets=_targets(subject) if targets is None else targets,
        coverage={"complete": True},
    )


def _receipt(record, *, file_name=None, resource_id=None,
             content_hash=None,
             rendered="Workbook read: orders.xlsx | O-1010 | Orders!R2"):
    source = record.get("source_identity") or {}
    return {
        "service": "datasets",
        "file_id": resource_id or source.get("resource_id") or "r1",
        "resource_id": resource_id or source.get("resource_id") or "r1",
        "file_name": file_name or source.get("file_name") or "orders.xlsx",
        "content_hash": content_hash or source.get("content_hash") or "hash-1",
        "identity_verified": True,
        "completed": True,
        "coverage_complete": True,
        "rendered_answer": rendered,
        "structured_result": record,
    }


def _session(*, stale_empty: bool = True):
    session = {
        "id": f"review-handoff-{time.time_ns()}",
        "history": [],
        FILE_TASK_SESSION_KEY: {
            "task_id": "task-review-handoff",
            "mention": "orders.xlsx",
            "original_message": REVIEW_ASK,
            "status": "pending",
            "created_at": time.time(),
            "attempts": 0,
            "resolved_file": {
                "file_name": "orders.xlsx",
                "resource_id": "r1",
                "content_hash": "hash-1",
            },
        },
    }
    if stale_empty:
        session["_pending_file_result"] = {
            "status": "incomplete",
            "rendered": (
                "The workbook was read, but no items were named to check — "
                "nothing can be confirmed or ruled out from an empty list."),
            "identity": {
                "file_name": "orders.xlsx",
                "resource_id": "r1",
                "content_hash": "hash-1",
            },
            "structured_result": {
                "source_identity": {
                    "file_name": "orders.xlsx",
                    "resource_id": "r1",
                    "content_hash": "hash-1",
                },
                "attempt_id": "attempt-old-empty",
                "evidence_revision": "hash-1:old",
                "requested_items": [],
                "targets": [],
            },
        }
    return session


def _review_content(evidence_id: str):
    payload = {"assessments": [{
        "subject_id": "O-1010",
        "decision": "Process",
        "evidence_ids": [evidence_id],
        "policy_ids": ["policy-1"],
        "unresolved_requirements": [],
    }]}
    return (
        "O-1010 is on hold; recommend process with the recorded exception.\n\n"
        "```review_result\n"
        + json.dumps(payload)
        + "\n```"
    )


def _system_texts(prompts):
    return [
        "\n".join(
            str(message.get("content") or "")
            for message in messages
            if isinstance(message, dict) and message.get("role") == "system"
        )
        for messages in prompts
    ]


def _wire(
    orch,
    session,
    *,
    record,
    narration,
):
    prompts = []
    read_calls = []
    direct_calls = []
    named_read_calls = []

    async def fake_plan(message, history, user_id, llm_service, **kwargs):
        if "REQUIRED RESEARCH" in str(message or ""):
            return planner.ToolPlan(
                use_tool=True, service="datasets", intent="search",
                query="O-1010")
        raise asyncio.TimeoutError("initial planner timed out")

    async def fake_execute(plan, user_id, tenant_id=None, context=None,
                           llm_service=None):
        read_calls.append(plan)
        source_name = (
            (record.get("source_identity") or {}).get("file_name")
            or "orders.xlsx")
        plan._result_meta = {"storage_read": _receipt(
            record,
            rendered=(
                f"Workbook read: {source_name}\n"
                "| O-1010 | FOUND | Orders!R2 [Status=On Hold] |"),
        )}
        return (
            f"Workbook read: {source_name}\n"
            "| O-1010 | FOUND | Orders!R2 [Status=On Hold] |")

    async def fake_direct(*args, **kwargs):
        direct_calls.append((args, kwargs))
        return {"ok": False, "reason": "direct lane timed out"}

    async def fake_named_read(*args, **kwargs):
        named_read_calls.append((args, kwargs))
        raise asyncio.TimeoutError("direct named-file lane timed out")

    async def fake_narration(messages=None, **kwargs):
        prompts.append(messages or [])
        text = "\n".join(
            str(message.get("content") or "")
            for message in (messages or [])
            if isinstance(message, dict) and message.get("role") == "system")
        evidence_id = "ev:O-1010:Orders!R2"
        for token in text.replace("|", " ").split():
            if token.startswith("ev:O-1010:"):
                evidence_id = token.strip(" ,;")
                break
        return narration(evidence_id, text)

    def fake_update(sess, message, response, intent):
        sess.setdefault("history", []).append({
            "message": message,
            "response": response,
            "intent": intent,
        })

    orch.llm_service.generate_completion = AsyncMock(
        side_effect=fake_narration)
    orch._agent_lessons = lambda agent_id, query, limit=5: list(LESSONS)
    orch._required_research_sources = lambda **kwargs: {"datasets"}

    patches = [
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session", side_effect=fake_update),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_load_pending_file_result", return_value=None),
        patch.object(orch, "_direct_confirmed_file_read", new=fake_direct),
        patch("core.chat_tool_planner._datasets_named_file_block",
              new=fake_named_read),
        patch("core.chat_tool_planner.plan_tool_use", new=fake_plan),
        patch("core.chat_tool_planner.execute_tool_plan", new=fake_execute),
        patch("core.chat_tool_planner._provenance_menu", new=AsyncMock(
            return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(chat, "_verbatim_mail_evidence", new=AsyncMock(
            return_value=[])),
    ]
    return prompts, read_calls, direct_calls, named_read_calls, patches


@pytest.mark.asyncio
async def test_confirmation_adopts_one_subject_bound_read_and_delivers_review():
    orch = _orch()
    session = _session(stale_empty=False)
    record = _record()
    prompts, read_calls, direct_calls, named_read_calls, patches = _wire(
        orch, session, record=record, narration=lambda ev, text: {
            "success": True,
            "content": _review_content(ev),
            "model": "controlled",
            "provider": "test",
        })

    with patches[0], patches[1], patches[2], patches[3], patches[4], \
            patches[5], patches[6], patches[7], patches[8], patches[9], \
            patches[10]:
        response = await orch.process_chat_message(
            "u1", "go ahead", session_id=session["id"], context={})

    assert len(read_calls) == 1, "exactly one completed source read"
    assert named_read_calls, "the direct named-file lane was attempted"
    assert read_calls, "the bounded replan read completed"
    system_texts = _system_texts(prompts)
    contract_prompts = [
        text for text in system_texts if "REVIEW OUTPUT CONTRACT" in text]
    assert contract_prompts, "the review prompt must carry the contract"
    prompt = contract_prompts[-1]
    assert "O-1010" in prompt
    assert "Orders!R2" in prompt
    assert "ev:O-1010:Orders!R2" in prompt

    assert response["success"] is True
    assert "VALIDATED REVIEW" in response["message"]
    assert "O-1010" in response["message"]
    assert "no items were named" not in response["message"].lower()
    assert response["data"]["review_result"]["ok"] is True
    assert response["data"]["review_result"]["assessments"][0][
        "subject_id"] == "O-1010"

    pfr = session["_pending_file_result"]
    assert pfr["status"] == "delivered"
    assert pfr["structured_result"]["requested_items"] == ["O-1010"]
    assert pfr["evidence_index"][0]["retrieval_execution_id"] == (
        response["execution_id"])
    canonical = {
        "file_name": "orders.xlsx",
        "resource_id": "r1",
        "content_hash": "hash-1",
    }
    for identity in (
            pfr["identity"],
            pfr["structured_result"]["source_identity"],
            pfr["evidence_index"][0]["source_identity"]):
        for key, value in canonical.items():
            assert identity[key] == value
    assert session[FILE_TASK_SESSION_KEY]["status"] == "delivered"

    # The delivered response and the persisted history are the same answer.
    assert session["history"][-1]["response"]["message"] == response["message"]
    assert session["history"][-1]["response"]["data"]["review_result"][
        "ok"] is True


def _valid_contract():
    return build_accepted_contract(
        REVIEW_ASK,
        catalogued_names=["orders.xlsx"],
        source_version="hash-1",
        lessons=LESSONS,
    )


@pytest.mark.asyncio
async def test_valid_replan_replaces_stale_empty_carrier_atomically():
    """The newer receipt and the older empty-item representation must not
    coexist: one adoption updates record, presentation and evidence index."""
    orch = _orch()
    session = _session(stale_empty=True)
    record = _record()
    prompts, read_calls, _direct, _named, patches = _wire(
        orch, session, record=record, narration=lambda ev, text: {
            "success": True,
            "content": _review_content(ev),
            "model": "controlled",
            "provider": "test",
        })

    with patches[0], patches[1], patches[2], patches[3], patches[4], \
            patches[5], patches[6], patches[7], patches[8], patches[9], \
            patches[10]:
        response = await orch.process_chat_message(
            "u1", "go ahead", session_id=session["id"], context={})

    assert len(read_calls) == 1
    prompt = [
        text for text in _system_texts(prompts)
        if "REVIEW OUTPUT CONTRACT" in text][-1]
    assert "O-1010" in prompt and "ev:O-1010:Orders!R2" in prompt
    assert "attempt-old-empty" not in prompt
    assert "no items were named" not in response["message"].lower()
    carrier = session["_pending_file_result"]
    assert carrier["attempt_id"] == "attempt-replan"
    assert carrier["structured_result"]["attempt_id"] == "attempt-replan"
    assert carrier["structured_result"]["requested_items"] == ["O-1010"]
    assert carrier["evidence_index"][0]["evidence_id"] == (
        "ev:O-1010:Orders!R2")
    assert "O-1010" in carrier["rendered"]
    assert "no items were named" not in carrier["rendered"].lower()
    assert session[FILE_TASK_SESSION_KEY]["status"] == "delivered"


def test_reject_conflicting_identity_fields_raises():
    with pytest.raises(ValueError, match="conflicting read identity"):
        reject_conflicting_identity_fields(
            {"file_name": "orders.xlsx", "content_hash": "hash-1"},
            {"file_name": "other.xlsx", "content_hash": "hash-2"},
        )


@pytest.mark.parametrize("field,value,revision", [
    ("file_name", "other.xlsx", "hash-1:2026-10-27"),
    ("resource_id", "r2", "hash-1:2026-10-27"),
    ("content_hash", "hash-2", "hash-2:2026-10-27"),
])
def test_nested_identity_contradicting_correct_outer_receipt_is_rejected(
        field, value, revision):
    record = _record(evidence_revision=revision, **{field: value})
    plan = planner.ToolPlan(
        use_tool=True, service="datasets", intent="search", query="O-1010")
    plan._result_meta = {"storage_read": _receipt(
        record,
        file_name="orders.xlsx",
        resource_id="r1",
        content_hash="hash-1",
    )}

    selected = validate_read_receipt(
        plan,
        _valid_contract(),
        {"file_name": "orders.xlsx", "resource_id": "r1",
         "content_hash": "hash-1"},
        execution_id="exec-review",
    )

    assert selected["ok"] is False
    assert "conflicting read identity" in selected["reason"]
    assert selected["evidence_index"] == []


@pytest.mark.parametrize("field,value", [
    ("file_name", "other.xlsx"),
    ("resource_id", "r2"),
    ("content_hash", "hash-2"),
])
def test_outer_receipt_contradicting_correct_nested_record_is_rejected(
        field, value):
    record = _record()
    plan = planner.ToolPlan(
        use_tool=True, service="datasets", intent="search", query="O-1010")
    plan._result_meta = {"storage_read": _receipt(
        record, **{field: value})}

    selected = validate_read_receipt(
        plan,
        _valid_contract(),
        {"file_name": "orders.xlsx", "resource_id": "r1",
         "content_hash": "hash-1"},
        execution_id="exec-review",
    )

    assert selected["ok"] is False
    assert "conflicting read identity" in selected["reason"]
    assert selected["evidence_index"] == []


def test_consistent_outer_and_nested_identity_is_accepted_canonical():
    record = _record()
    plan = planner.ToolPlan(
        use_tool=True, service="datasets", intent="search", query="O-1010")
    plan._result_meta = {"storage_read": _receipt(record)}

    selected = validate_read_receipt(
        plan,
        _valid_contract(),
        {"file_name": "orders.xlsx", "resource_id": "r1",
         "content_hash": "hash-1"},
        execution_id="exec-review",
    )

    assert selected["ok"] is True
    assert selected["identity"]["file_name"] == "orders.xlsx"
    assert selected["identity"]["resource_id"] == "r1"
    assert selected["identity"]["content_hash"] == "hash-1"
    structured_identity = selected["structured_result"]["source_identity"]
    assert structured_identity["file_name"] == "orders.xlsx"
    assert structured_identity["resource_id"] == "r1"
    assert structured_identity["content_hash"] == "hash-1"
    evidence_identity = selected["evidence_index"][0]["source_identity"]
    assert evidence_identity["file_name"] == "orders.xlsx"
    assert evidence_identity["resource_id"] == "r1"
    assert evidence_identity["content_hash"] == "hash-1"
    assert "orders.xlsx" in selected["presentation"]


def test_datasets_search_metadata_alone_is_not_evidence():
    plan = planner.ToolPlan(
        use_tool=True, service="datasets", intent="search", query="O-1010")
    plan._result_meta = {"datasets_search": {
        "executed": True,
        "query": "O-1010",
        "match_count": 1,
    }}

    selected = validate_read_receipt(
        plan,
        _valid_contract(),
        {"file_name": "orders.xlsx", "content_hash": "hash-1"},
        execution_id="exec-review",
    )

    assert selected["ok"] is False
    assert selected["structured_result"] is None


@pytest.mark.parametrize("case", [
    "wrong_subject",
    "wrong_workbook",
    "wrong_version",
    "no_matching_rows",
])
def test_receipt_validation_rejects_incomplete_evidence(case):
    if case == "wrong_subject":
        record = _record(subject="O-1001")
        bound = {"file_name": "orders.xlsx", "content_hash": "hash-1"}
    elif case == "wrong_workbook":
        record = _record(file_name="other.xlsx")
        bound = {"file_name": "orders.xlsx", "content_hash": "hash-1"}
    elif case == "wrong_version":
        record = _record(content_hash="hash-2",
                         evidence_revision="hash-2:2026-10-27")
        bound = {"file_name": "orders.xlsx", "content_hash": "hash-1"}
    else:
        record = _record(targets=[])
        bound = {"file_name": "orders.xlsx", "content_hash": "hash-1"}

    plan = planner.ToolPlan(
        use_tool=True, service="datasets", intent="search", query="O-1010")
    plan._result_meta = {"storage_read": _receipt(record)}
    selected = validate_read_receipt(
        plan, _valid_contract(), bound, execution_id="exec-review")

    assert selected["ok"] is False
    assert selected["evidence_index"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "wrong_subject",
    "wrong_workbook",
    "wrong_version",
    "no_matching_rows",
])
async def test_incomplete_receipt_never_delivers_the_review(case):
    orch = _orch()
    session = _session()
    if case == "wrong_subject":
        record = _record(subject="O-1001")
    elif case == "wrong_workbook":
        record = _record(file_name="other.xlsx")
    elif case == "wrong_version":
        record = _record(
            content_hash="hash-2", evidence_revision="hash-2:2026-10-27")
    else:
        record = _record(targets=[])

    prompts, read_calls, _direct_calls, _named_read_calls, patches = _wire(
        orch, session, record=record, narration=lambda ev, text: {
            "success": True,
            "content": _review_content(ev),
            "model": "controlled",
            "provider": "test",
        })

    with patches[0], patches[1], patches[2], patches[3], patches[4], \
            patches[5], patches[6], patches[7], patches[8], patches[9], \
            patches[10]:
        response = await orch.process_chat_message(
            "u1", "go ahead", session_id=session["id"], context={})

    assert len(read_calls) == 1
    assert not any(
        "REVIEW OUTPUT CONTRACT" in text for text in _system_texts(prompts)), (
        "incomplete evidence must not invite a review assessment")
    assert "VALIDATED REVIEW" not in response.get("message", "")
    assert response.get("outcome") != "completed"
    assert session[FILE_TASK_SESSION_KEY]["status"] != "delivered"
    assert session.get("_pending_file_result", {}).get(
        "status") != "delivered"


@pytest.mark.asyncio
async def test_narration_failure_keeps_evidence_and_retry_reuses_it():
    orch = _orch()
    session = _session(stale_empty=False)
    record = _record()
    prompts, read_calls, direct_calls, named_read_calls, patches = _wire(
        orch, session, record=record, narration=lambda ev, text: {
            "success": False,
            "content": "",
            "model": "controlled",
            "provider": "test",
        })

    with patches[0], patches[1], patches[2], patches[3], patches[4], \
            patches[5], patches[6], patches[7], patches[8], patches[9], \
            patches[10]:
        first = await orch.process_chat_message(
            "u1", "go ahead", session_id=session["id"], context={})

    assert first is not None
    assert len(read_calls) == 1
    pfr = session["_pending_file_result"]
    assert pfr["status"] == "retrieved"
    assert pfr["structured_result"]["requested_items"] == ["O-1010"]
    assert pfr["evidence_index"][0]["evidence_id"] == "ev:O-1010:Orders!R2"
    retrieval_execution_id = pfr["source_execution_id"]
    assert retrieval_execution_id == first["execution_id"]
    assert pfr["evidence_index"][0][
        "retrieval_execution_id"] == retrieval_execution_id
    assert session[FILE_TASK_SESSION_KEY]["status"] == "retrieved"
    assert "VALIDATED REVIEW" not in (first.get("message") or "")

    # RETRY: the same retrieved evidence resumes the assessment. No second
    # read, no planner execution, and the same evidence ID reaches the model.
    retry_prompts, retry_reads, retry_direct, retry_named_reads, retry_patches = _wire(
        orch, session, record=record, narration=lambda ev, text: {
            "success": True,
            "content": _review_content(ev),
            "model": "controlled",
            "provider": "test",
        })
    with retry_patches[0], retry_patches[1], retry_patches[2], \
            retry_patches[3], retry_patches[4], retry_patches[5], \
            retry_patches[6], retry_patches[7], retry_patches[8], \
            retry_patches[9], retry_patches[10]:
        second = await orch.process_chat_message(
            "u1", "go ahead", session_id=session["id"], context={})

    assert len(retry_reads) == 0, "retry must not re-read the workbook"
    assert not retry_named_reads, "retry must not open the workbook reader"
    assert not retry_direct, "retry must resume the assessment, not re-read"
    retry_texts = _system_texts(retry_prompts)
    contract_texts = [
        text for text in retry_texts if "REVIEW OUTPUT CONTRACT" in text]
    assert contract_texts
    assert all("ev:O-1010:Orders!R2" in text for text in contract_texts)
    assert second["success"] is True
    assert "VALIDATED REVIEW" in second["message"]
    assert session[FILE_TASK_SESSION_KEY]["status"] == "delivered"
    retried = session["_pending_file_result"]
    assert retried["status"] == "delivered"
    assert retried["source_execution_id"] == retrieval_execution_id
    assert retried["evidence_index"][0][
        "retrieval_execution_id"] == retrieval_execution_id
    assert retrieval_execution_id in second["data"]["review_result"][
        "source_execution_ids"]
