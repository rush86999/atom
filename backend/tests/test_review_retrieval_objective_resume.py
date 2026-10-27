"""Retrieved review tasks keep the accepted objective and can resume."""
from __future__ import annotations

import copy
import json
import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import core.chat_tool_planner as planner
import integrations.chat_orchestrator as chat
from core.answer_presentation import (
    build_structured_record,
    build_targets_from_scan,
    present_from_record,
)
from core.pending_file_task import (
    FILE_TASK_SESSION_KEY,
    mark_task_retrieved,
    require_original_objective,
    settle_retrieval_task,
)
from core.review_result import build_evidence_index

ASK = (
    "Using the uploaded orders.xlsx, review order O-1010 against the "
    "order processing policy. Cite Order ID, Status, Qty, Unit Price, "
    "Currency, Approval 1, Approval 2, Manager Exception, and Notes from "
    "the row. State process or escalate and explain the policy basis. "
    "Do not send, approve, or modify anything."
)
LESSONS = [{
    "id": "policy-1",
    "topic": "Order processing policy",
    "lesson": "Recommend process; escalate exceptions.",
    "decision_options": ["Process", "Escalate"],
}]
IDENTITY = {
    "file_name": "orders.xlsx",
    "file_id": "r1",
    "resource_id": "r1",
    "content_hash": "hash-1",
}


def _orch():
    orch = chat.ChatOrchestrator()
    orch.ai_engines = {}
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={
        "success": True, "content": "reply", "model": "m", "provider": "p",
    })
    orch.llm_service = llm
    orch._agent_lessons = lambda agent_id, query, limit=5: list(LESSONS)
    return orch


def _read_record():
    targets = build_targets_from_scan(
        ["O-1010"],
        {"O-1010": {
            "status": "found",
            "evidence": [{
                "sheet": "Orders",
                "row": 11,
                "values": [
                    {"cell": "A11", "field": "Order ID", "value": "O-1010"},
                    {"cell": "B11", "field": "Status", "value": "Approved"},
                ],
            }],
        }},
        {},
    )
    record = build_structured_record(
        source_identity={
            "file_name": "orders.xlsx",
            "service": "datasets",
            "resource_id": "r1",
            "content_hash": "hash-1",
        },
        evidence_revision="hash-1:2026-10-27",
        attempt_id="attempt-read",
        evidence_action="new_read",
        requested_items=["O-1010"],
        requested_fields=["Status"],
        targets=targets,
        coverage={"complete": True},
    )
    record["source_execution_id"] = "read-exec-1"
    return record


def _pending_result(record):
    rendered = present_from_record(record)["answer"]
    return {
        "status": "retrieved",
        "target_extraction_version": 3,
        "rendered": rendered,
        "identity": dict(IDENTITY),
        "workbook_read": None,
        "execution_id": "read-exec-1",
        "source_execution_id": "read-exec-1",
        "structured_result": record,
        "evidence_index": build_evidence_index(
            record, subjects=["O-1010"]),
        "retrieved_at": 1.0,
    }


def _retrieved_task(orch):
    task = orch._accepted_file_task(
        {"id": "fresh"},
        original_message=ASK,
        mention="orders.xlsx",
        requested_targets=["O-1010"],
        identity=IDENTITY,
        agent_id="agent-1",
        workspace_id="workspace-1",
    )
    require_original_objective(task)
    task = mark_task_retrieved(task, IDENTITY)
    task = settle_retrieval_task(
        task,
        IDENTITY,
        retrieval_finished=True,
        answer_delivered=False,
        calculation_complete=True,
        open_requirements=[],
    )
    return task


@pytest.mark.asyncio
async def test_budget_end_after_read_persists_accepted_objective():
    """The reported failure: no task before the read, read completes, budget
    ends before assessment. Retrieval state must not create an empty task."""
    orch = _orch()
    session = {"id": "budget-review", "history": []}
    record = _read_record()
    plan = planner.ToolPlan(
        use_tool=True, service="datasets", intent="search",
        query="orders.xlsx O-1010")

    async def execute(p, user_id, tenant_id=None, context=None,
                      llm_service=None):
        p._result_meta = {"storage_read": {
            "service": "datasets",
            "file_id": "r1",
            "resource_id": "r1",
            "file_name": "orders.xlsx",
            "content_hash": "hash-1",
            "identity_verified": True,
            "completed": True,
            "coverage_complete": True,
            "rendered_answer": "Orders!R11: O-1010 Approved",
            "workbook_read": None,
            "structured_result": record,
        }}
        return "Orders!R11: O-1010 Approved"

    with (
        patch("core.chat_tool_planner.plan_tool_use", new=AsyncMock(
            return_value=plan)),
        patch("core.chat_tool_planner.execute_tool_plan", new=execute),
        patch("core.chat_tool_planner._provenance_menu", new=AsyncMock(
            return_value="")),
        patch("core.memory_context_assembler.assembly_enabled",
              return_value=False),
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_load_pending_file_result", return_value=None),
        patch.object(orch.llm_service, "generate_completion", new=AsyncMock(
            side_effect=AssertionError("budget exhausted before assessment"))),
    ):
        await orch._get_qwen_response(
            ASK, [], user_id="u1", session_id="budget-review",
            execution_id="budget-exec-1", session=session,
            workspace_id="workspace-1", agent_id="agent-1",
        )

    task = session[FILE_TASK_SESSION_KEY]
    assert task["original_message"] == ASK
    assert task["requested_targets"] == ["O-1010"]
    assert task["accepted_contract"]["subjects"] == ["O-1010"]
    assert task["agent_id"] == "agent-1"
    assert task["workspace_id"] == "workspace-1"
    assert task["status"] == "retrieved"
    assert task["retrieval_finished"] is True
    assert task["answer_delivered"] is False
    require_original_objective(task)


def test_retrieval_completion_preserves_objective_contract_and_scope():
    orch = _orch()
    task = _retrieved_task(orch)

    assert task["original_message"] == ASK
    assert task["requested_targets"] == ["O-1010"]
    assert task["requested_fields"]
    assert task["accepted_contract"]["subjects"] == ["O-1010"]
    assert task["accepted_contract"]["requested_fields"]
    assert task["agent_id"] == "agent-1"
    assert task["workspace_id"] == "workspace-1"
    assert task["task_id"]
    assert task["status"] == "retrieved"
    assert task["retrieval_finished"] is True
    assert task["answer_delivered"] is False

    # Fresh-process JSON round trip, not the in-memory object.
    reloaded = json.loads(json.dumps(task))
    assert reloaded["original_message"] == ASK
    assert reloaded["accepted_contract"] == task["accepted_contract"]
    require_original_objective(reloaded)


def _review_content(evidence_id):
    payload = {"assessments": [{
        "subject_id": "O-1010",
        "decision": "Process",
        "basis": ["Record is complete."],
        "evidence_ids": [evidence_id],
        "policy_ids": ["policy-1"],
        "unresolved_requirements": [],
    }]}
    return (
        "O-1010 is complete and ready for routine processing.\n\n"
        "```review_result\n" + json.dumps(payload) + "\n```"
    )


@pytest.mark.asyncio
async def test_fresh_confirmation_finishes_retrieved_review_without_read():
    orch = _orch()
    task = _retrieved_task(orch)
    record = _read_record()
    pending = _pending_result(record)
    fresh_session = {
        "id": "fresh-review-resume",
        "history": [],
        FILE_TASK_SESSION_KEY: copy.deepcopy(task),
        "_pending_file_result": copy.deepcopy(pending),
    }
    prompts = []
    direct = AsyncMock(side_effect=AssertionError("must not re-read"))
    plan = AsyncMock(side_effect=AssertionError("must not plan a source"))
    execute = AsyncMock(side_effect=AssertionError("must not execute a read"))

    async def narration(messages=None, **kwargs):
        prompts.append(messages or [])
        text = "\n".join(
            str(message.get("content") or "")
            for message in (messages or [])
            if isinstance(message, dict)
            and message.get("role") == "system")
        evidence_id = "ev:O-1010:Orders!R11"
        for token in text.replace("|", " ").split():
            if token.startswith("ev:O-1010:"):
                evidence_id = token.strip(" ,;")
                break
        return {
            "success": True,
            "content": _review_content(evidence_id),
            "model": "controlled",
            "provider": "test",
        }

    orch.llm_service.generate_completion = AsyncMock(side_effect=narration)

    with (
        patch.object(orch, "_get_or_create_session", return_value=fresh_session),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_load_pending_file_result", return_value=None),
        patch.object(orch, "_direct_confirmed_file_read", new=direct),
        patch("core.chat_tool_planner.plan_tool_use", new=plan),
        patch("core.chat_tool_planner.execute_tool_plan", new=execute),
    ):
        response = await orch.process_chat_message(
            "u1", "go ahead", session_id="fresh-review-resume",
            context={"agent_id": "agent-1", "workspace_id": "workspace-1"},
        )

    direct.assert_not_awaited()
    plan.assert_not_awaited()
    execute.assert_not_awaited()
    contract_texts = [
        text for text in (
            "\n".join(
                str(message.get("content") or "")
                for message in messages
                if isinstance(message, dict)
                and message.get("role") == "system")
            for messages in prompts)
        if "REVIEW OUTPUT CONTRACT" in text
    ]
    assert contract_texts
    assert all("O-1010" in text for text in contract_texts)
    assert response["success"] is True
    assert response["outcome"] == "completed"
    review = (
        response.get("review_result")
        or (response.get("data") or {}).get("review_result")
        or (response.get("metadata") or {}).get("review_result"))
    assert review and review.get("ok") is True
    assert review.get("completion") == "completed"
    assert fresh_session[FILE_TASK_SESSION_KEY][
        "original_message"] == ASK
    assert fresh_session[FILE_TASK_SESSION_KEY]["status"] == "delivered"
