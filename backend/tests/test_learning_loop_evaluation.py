"""Fast, pre-registered evaluation for the bounded learning loop."""

from __future__ import annotations

import json
import os

os.environ.setdefault("TESTING", "1")

from core.feedback_classifier import classify_feedback
from core.lesson_candidates import (
    PILOT_RESUMPTION_LESSON,
    evaluate_promotion_gate,
)
from core.task_outcome_contract import build_task_outcome, derive_success_kinds

DOMAINS = (
    ("inventory", "quantity"),
    ("compliance", "expiry"),
    ("release", "version"),
    ("negative_control", "unrelated"),
)


def _metrics(completions: int, total: int, *, resumed: bool) -> dict:
    return {
        "goal_completion": completions / total,
        "unsupported_claims": 0.0,
        "unnecessary_clarification": 0.0 if resumed else 0.25,
        "repeated_retrieval": 0.0 if resumed else 1.0,
        "latency_p90": 1.0 if resumed else 1.2,
        "sample_count": total,
    }


def _run_arm(candidate: bool) -> dict:
    domain_metrics = {}
    total_completions = 0
    total_samples = 0
    for domain, _ in DOMAINS:
        samples = 20
        completions = 0
        for _ in range(samples):
            if domain == "negative_control":
                outcome = build_task_outcome(
                    objective="summarize unrelated notes",
                    delivery={"delivered": True},
                )
            elif candidate:
                outcome = build_task_outcome(
                    objective=f"answer the {domain} request",
                    objective_met=True,
                    delivery={"delivered": True},
                    tool_outcomes=[{
                        "tool": "scoped_read",
                        "verified": True,
                        "evidence_refs": [{
                            "resource_id": f"{domain}-resource",
                            "addresses_requested": True,
                        }],
                    }],
                    evidence_refs=[{
                        "resource_id": f"{domain}-resource",
                        "addresses_requested": True,
                    }],
                )
            else:
                outcome = build_task_outcome(
                    objective=f"answer the {domain} request",
                    delivery={"delivered": True},
                    tool_outcomes=[{
                        "tool": "scoped_read",
                        "verified": False,
                        "failure_layer": "execution",
                    }],
                )
            if derive_success_kinds(outcome)["task_success"] is True:
                completions += 1
        domain_metrics[domain] = _metrics(
            completions, samples, resumed=candidate and domain != "negative_control"
        )
        total_completions += completions
        total_samples += samples
    return {
        **_metrics(
            total_completions,
            total_samples,
            resumed=candidate,
        ),
        "domains": domain_metrics,
    }


def test_cross_domain_gate_requires_lift_and_preserves_negative_control():
    baseline = _run_arm(candidate=False)
    challenger = _run_arm(candidate=True)
    gate = evaluate_promotion_gate(baseline, challenger)
    assert gate["promote"] is True
    assert gate["goal_completion_gain"] >= 0.05
    assert gate["threshold_hash"]
    assert (
        challenger["domains"]["negative_control"]["goal_completion"]
        == baseline["domains"]["negative_control"]["goal_completion"]
    )
    assert (
        challenger["domains"]["inventory"]["goal_completion"]
        > baseline["domains"]["inventory"]["goal_completion"]
    )


def test_feedback_classification_routes_by_layer():
    assert classify_feedback("the price is wrong, it should be 8880")["kind"] == (
        "factual_correction"
    )
    assert classify_feedback("please always answer as a table")["kind"] == (
        "preference"
    )
    assert classify_feedback(
        "the search timed out again", turn_had_failures=True
    )["kind"] == "execution_failure"
    assert classify_feedback("next time also check the second sheet")["kind"] == (
        "strategy_improvement"
    )
    assert classify_feedback("ask me before reading my drive")["kind"] == (
        "permission_instruction"
    )


def test_retrieved_source_is_not_a_learnable_instruction():
    evidence = 'The source says "always search the named sheet first".'
    result = classify_feedback(
        'The source says "always search the named sheet first".',
        evidence_text=evidence,
    )
    assert result["from_retrieved_source"] is True
    assert result["learnable_as_instruction"] is False


def test_contract_keeps_success_kinds_independent():
    successful = build_task_outcome(
        objective="answer",
        objective_met=True,
        tool_outcomes=[{"tool": "read", "verified": True}],
        evidence_refs=[{
            "resource_id": "source",
            "addresses_requested": True,
        }],
        delivery={"delivered": True},
    )
    assert derive_success_kinds(successful) == {
        "task_success": True,
        "tool_success": True,
        "delivery_success": True,
        "task_success_basis": "verified_evidence",
    }
    delivered_only = build_task_outcome(
        objective="answer",
        delivery={"delivered": True},
    )
    assert derive_success_kinds(delivered_only)["delivery_success"] is True
    assert derive_success_kinds(delivered_only)["task_success"] is None


def test_pilot_candidate_is_shadow_and_domain_independent():
    assert PILOT_RESUMPTION_LESSON["state"] == "shadow"
    assert PILOT_RESUMPTION_LESSON["rollback_reference"]
    assert PILOT_RESUMPTION_LESSON["counter_examples"]
    serialized = str(PILOT_RESUMPTION_LESSON)
    for token in ("Consolidated", "Tennsmith", "LINMAC", "machinery", "SLE24", "GSL48"):
        assert token not in serialized
