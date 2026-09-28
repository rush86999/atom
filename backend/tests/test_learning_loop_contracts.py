from core.feedback_classifier import (
    KIND_FACTUAL,
    KIND_PERMISSION,
    KIND_PREFERENCE,
    KIND_SOURCE,
    KIND_STRATEGY,
    KIND_UNKNOWN,
    classify_feedback,
)
from core.lesson_candidates import (
    extract_lesson_candidate,
    evaluate_promotion_gate,
    promote_candidate,
    rollback_candidate,
    transition_candidate,
)
from core.task_outcome_contract import (
    build_task_outcome,
    derive_success_kinds,
    diagnose_task_failure,
    merge_feedback_into_outcome,
)
from core.exchange_example_service import _fire_teaching_circuit
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


def test_terminal_execution_persists_outcome_and_success_kinds():
    from integrations.chat_orchestrator import ChatOrchestrator

    class Query:
        def __init__(self, row):
            self.row = row

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.row

    class Database:
        def __init__(self, row):
            self.row = row
            self.committed = False

        def query(self, model):
            return Query(self.row)

        def commit(self):
            self.committed = True

    class Session:
        def __init__(self, db):
            self.db = db

        def __enter__(self):
            return self.db

        def __exit__(self, *args):
            return False

    row = SimpleNamespace(metadata_json={})
    database = Database(row)
    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    session = {
        "id": "session-1",
        "user_id": "user-1",
        "_pending_file_task": {
            "original_message": "read inventory.xlsx",
            "mention": "inventory.xlsx",
        },
        "_pending_file_result": {
            "execution_id": "execution-1",
            "status": "delivered",
            "coverage_complete": True,
            "identity": {"resource_id": "resource-1"},
        },
    }
    with patch("core.database.get_db_session", return_value=Session(database)):
        orchestrator._finish_chat_execution(
            "execution-1",
            "success",
            "answer",
            session=session,
            message="yes",
            response={
                "success": True,
                "message": "answer",
                "model": "deterministic",
            },
            pending_task=session["_pending_file_task"],
            authorized_actions=["read"],
        )
    assert database.committed is True
    assert row.metadata_json["task_success_kinds"]["task_success"] is True
    assert row.metadata_json["learning_event"]["event_type"] == "task_outcome"


def test_failure_layers_are_explicit_and_bounded():
    identity = build_task_outcome(
        objective="read the named source",
        objective_met=False,
        source_constraints={"file_identity": {"file_name": "source.xlsx"}},
    )
    identity_failure = diagnose_task_failure(identity)
    assert identity_failure is not None
    assert identity_failure["layer"] == "identity"
    comparison = build_task_outcome(
        objective="compare the two values",
        objective_met=False,
    )
    comparison_failure = diagnose_task_failure(comparison)
    assert comparison_failure is not None
    assert comparison_failure["layer"] == "comparison"
    discovery = build_task_outcome(
        objective="find the current release",
        objective_met=False,
    )
    discovery_failure = diagnose_task_failure(discovery)
    assert discovery_failure is not None
    assert discovery_failure["layer"] == "discovery"
    assert diagnose_task_failure(build_task_outcome(objective="x")) is None


def test_feedback_scope_rejects_another_users_durable_session():
    from core.models import ChatSession
    from integrations.chat_routes import (
        ChatFeedbackRequest,
        _assert_feedback_scope,
    )

    class Query:
        def __init__(self, result):
            self.result = result

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.result

    class Database:
        def query(self, model):
            if model.__name__ == "ChatSession":
                return Query(ChatSession(id="session-1", user_id="other-user"))
            return Query(None)

    request = ChatFeedbackRequest(
        message_id="message-1",
        session_id="session-1",
        feedback="thumbs_up",
    )
    with pytest.raises(HTTPException) as error:
        _assert_feedback_scope(
            Database(), request, SimpleNamespace(id="current-user")
        )
    assert error.value.status_code == 403


def test_classified_feedback_does_not_fan_out_as_a_standing_lesson():
    classification = classify_feedback("I prefer tables")
    fired = _fire_teaching_circuit(
        {},
        SimpleNamespace(
            id="ex-1",
            label="negative",
            comment="I prefer tables",
            user_query="format the answer",
            conversation_id="conv-1",
            workspace_id="ws-1",
        ),
        classification=classification,
    )
    assert "human_correction_lesson" not in fired
    assert "operating_agent_lesson" not in fired
    assert fired["feedback_classification"]["destination"] == "user_configuration"


@pytest.mark.asyncio
async def test_capture_exchange_passes_classification_to_safe_teaching_circuit():
    from core.exchange_example_service import capture_exchange

    database = MagicMock()
    pair = {
        "user_query": "format the answer",
        "assistant_response": "answer",
        "assistant_message_id": "assistant-1",
        "agent_id": "agent-1",
        "conversation_id": "session-1",
        "tenant_id": "default",
        "user_id": "user-1",
        "execution_id": "execution-1",
    }
    with (
        patch("core.exchange_example_service._resolve_exchange_pair", return_value=pair),
        patch("core.exchange_example_service._dedupe_key_match", return_value=None),
        patch("core.exchange_example_service._write_vector", return_value=True),
        patch("core.exchange_example_service._fire_teaching_circuit", return_value={}) as fire,
        patch("core.database.SessionLocal", return_value=database),
    ):
        result = await capture_exchange(
            message_id="assistant-1",
            feedback="thumbs_down",
            comment="I prefer tables",
            session_id="session-1",
            user_id="user-1",
        )
    assert result["feedback_classification"]["kind"] == KIND_PREFERENCE
    assert fire.call_args.kwargs["classification"]["destination"] == "user_configuration"


def test_resume_outcome_uses_original_objective_and_rejects_stale_evidence():
    from integrations.chat_orchestrator import ChatOrchestrator

    orchestrator = ChatOrchestrator.__new__(ChatOrchestrator)
    task = {
        "original_message": "how many units are in inventory.xlsx",
        "mention": "inventory.xlsx",
    }
    session: Dict[str, Any] = {
        "id": "session-1",
        "user_id": "user-1",
        "_pending_file_task": task,
        "_pending_file_result": {
            "execution_id": "current-execution",
            "status": "delivered",
            "coverage_complete": True,
            "identity": {
                "file_name": "inventory.xlsx",
                "resource_id": "resource-1",
                "content_hash": "hash-1",
            },
        },
    }
    outcome = orchestrator._build_turn_task_outcome(
        session,
        "yes, that is the right file",
        {"success": True, "message": "answer", "model": "deterministic"},
        None,
        None,
        execution_id="current-execution",
        pending_task=task,
        authorized_actions=["read"],
    )
    assert outcome["objective"] == task["original_message"]
    assert outcome["success_kinds"]["task_success"] is True

    session["_pending_file_result"]["execution_id"] = "old-execution"
    stale = orchestrator._build_turn_task_outcome(
        session,
        "thanks",
        {"success": True, "message": "welcome", "model": "deterministic"},
        None,
        None,
        execution_id="new-execution",
        pending_task=task,
    )
    assert stale["evidence_refs"] == []
    assert stale["success_kinds"]["task_success"] is None


def test_verified_unrelated_tool_does_not_prove_task_success():
    outcome = build_task_outcome(
        objective="answer the request",
        objective_met=True,
        delivery={"delivered": True},
        tool_outcomes=[{
            "tool": "unrelated",
            "verified": True,
            "evidence_refs": [{
                "resource_id": "other",
                "addresses_requested": False,
            }],
        }],
        evidence_refs=[{
            "resource_id": "other",
            "addresses_requested": False,
        }],
    )
    kinds = derive_success_kinds(outcome)
    assert kinds["tool_success"] is True
    assert kinds["task_success"] is None
    assert kinds["task_success_basis"] == "insufficient_evidence"


def test_unknown_tool_state_is_not_aggregate_success():
    outcome = build_task_outcome(
        objective="answer the request",
        objective_met=True,
        delivery={"delivered": True},
        tool_outcomes=[
            {"tool": "verified", "verified": True},
            {"tool": "unknown", "verified": None},
        ],
    )
    assert derive_success_kinds(outcome)["tool_success"] is None


def test_feedback_classification_preserves_destinations():
    assert classify_feedback("I prefer tables")["kind"] == KIND_PREFERENCE
    assert classify_feedback("That price is wrong; it should be 123")["kind"] == KIND_FACTUAL
    assert classify_feedback("Next time verify the source")["kind"] == KIND_STRATEGY
    permission = classify_feedback("Never send without my approval")
    assert permission["kind"] == KIND_PERMISSION
    assert permission["learnable_as_instruction"] is False
    assert permission["requires_authorization"] is True


def test_unmatched_feedback_and_source_content_are_not_lessons():
    assert classify_feedback("")["kind"] == KIND_UNKNOWN
    source = classify_feedback(
        "Next time verify this source",
        evidence_text="Next time verify this source",
    )
    assert source["kind"] == KIND_SOURCE
    assert source["learnable_as_instruction"] is False
    unquoted = classify_feedback(
        "The source says always search the named sheet first",
        evidence_text="The source says always search the named sheet first.",
    )
    assert unquoted["from_retrieved_source"] is True
    assert unquoted["learnable_as_instruction"] is False


def test_factual_feedback_does_not_become_a_global_lesson():
    result = classify_feedback("The total is wrong; it should be 42")
    assert result["destination"] == "knowledge_candidate"
    assert result["learnable_as_instruction"] is False
    assert result["requires_verification"] is True


def test_feedback_merge_marks_original_task_uncertain_or_corrected():
    outcome = build_task_outcome(
        objective="answer the request",
        objective_met=True,
        delivery={"delivered": True},
        evidence_refs=[{"resource_id": "source-1", "addresses_requested": True}],
    )
    merged = merge_feedback_into_outcome(
        outcome,
        {
            "kind": KIND_FACTUAL,
            "destination": "knowledge_candidate",
            "supporting_text": "The value is wrong",
            "confidence": 0.9,
        },
    )
    assert merged["success_kinds"]["task_success"] is False
    assert merged["feedback_classifications"][0]["kind"] == KIND_FACTUAL
    assert set(merged["learning_layers"]) == {
        "general_capability",
        "user_business_configuration",
        "task_evidence",
    }


def test_lesson_extraction_is_sanitized_and_shadow_only():
    candidate = extract_lesson_candidate(
        "Next time verify Inventory.xlsx before answering",
        scope={"workspace_id": "ws-1"},
    )
    assert candidate is not None
    assert candidate["state"] == "shadow"
    assert ".xlsx" not in candidate["expected_behavioral_change"]
    assert candidate["strategy_fingerprint"]
    assert candidate["applicability"]["domains"] == "any"


def _metrics(goal: float, sample_count: int = 20) -> dict:
    return {
        "goal_completion": goal,
        "unsupported_claims": 0.0,
        "unnecessary_clarification": 0.1,
        "repeated_retrieval": 0.0,
        "latency_p90": 1.0,
        "sample_count": sample_count,
    }


def test_promotion_gate_requires_lift_and_rejects_domain_regression():
    baseline = _metrics(0.50)
    candidate = _metrics(0.60)
    gate = evaluate_promotion_gate(baseline, candidate)
    assert gate["promote"] is True
    assert gate["threshold_hash"]

    regressed = _metrics(0.60)
    regressed["unsupported_claims"] = 0.2
    gate = evaluate_promotion_gate(baseline, regressed)
    assert gate["promote"] is False
    assert any("domain_regression" in reason for reason in gate["reasons"])


def test_promotion_gate_fails_closed_on_missing_metrics():
    gate = evaluate_promotion_gate({"goal_completion": 0.5}, {"goal_completion": 0.9})
    assert gate["promote"] is False
    assert "missing_metrics" in gate["reasons"]


def test_active_transition_requires_actor_and_evaluation():
    candidate = extract_lesson_candidate("Next time verify the source")
    assert candidate is not None
    assert transition_candidate(candidate, "active", actor_id=None) is None
    assert transition_candidate(
        candidate,
        "active",
        actor_id="supervisor-1",
        evaluation={"promote": False},
    ) is None
    candidate["state"] = "limited"
    with patch("core.lesson_candidates._event", return_value="event-1"):
        promoted = promote_candidate(
            candidate,
            {"promote": True, "threshold_hash": "hash-1"},
            actor_id="supervisor-1",
        )
        rolled_back = rollback_candidate(
            promoted,
            actor_id="supervisor-1",
            reason="held-out regression",
        ) if promoted is not None else None
    assert promoted is not None
    assert promoted["state"] == "active"
    assert promoted["version"] == 2
    assert rolled_back is not None
    assert rolled_back["state"] == "rolled_back"
    assert rolled_back["version"] == 3
