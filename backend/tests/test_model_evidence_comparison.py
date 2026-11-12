"""Focused contract tests for task-scoped model evidence comparison.

The comparison is deliberately pure: no provider call, no DB, no credential,
no runtime consumer change. It answers one question — which exact
``(provider, model)`` pair has current, comparable, task-scoped evidence — and
returns an explicit insufficient-evidence result when it cannot.

Run with ``TESTING=1`` (also set below so a direct pytest invocation cannot
touch a live world).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("TESTING", "1")

import pytest

from core.llm.model_evidence_comparison import (
    INSUFFICIENT_EVIDENCE,
    compare_model_evidence,
    load_assessment_qualification_evidence,
    normalize_task_scope,
    task_scope_digest,
)

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
FRESH = (NOW - timedelta(days=2)).isoformat()
STALE = (NOW - timedelta(days=45)).isoformat()

SCOPE = {
    "task_policy": (
        "Approve Open records with Amount >= 100 and Risk Low. "
        "Review Open records with Amount 50-99 or Risk High. "
        "Deny Closed records."),
    "decision_options": ["APPROVE", "REVIEW", "DENY"],
    "subject_field": "Ref",
}


def _evidence(
    provider: str = "openai",
    model: str = "gpt-test",
    **overrides,
) -> dict:
    record = {
        "provider": provider,
        "model": model,
        "task_scope": SCOPE,
        "observed_at": FRESH,
        "passed": True,
        "accuracy": 0.9,
        "dataset_id": "qualification-set",
        "dataset_sha256": "sha-current",
        "scoring_version": "v2",
        "source": "assessment_qualification",
        "evidence_id": f"ev:{provider}/{model}:{overrides.get('phase', 'run')}",
    }
    record.update(overrides)
    return record


def _compare(evidence, **overrides):
    return compare_model_evidence(
        task_scope=overrides.pop("task_scope", SCOPE),
        evidence=evidence,
        now=NOW,
        **overrides,
    )


def _reasons(result):
    block = result.get("insufficient_evidence") or {}
    return block.get("reasons") or []


# ---------------------------------------------------------------------------
# Identity is exact
# ---------------------------------------------------------------------------


def test_model_name_alone_or_an_alias_is_not_an_identity():
    result = _compare([
        {"model": "gpt-test", "task_scope": SCOPE,
         "observed_at": FRESH, "passed": True},
        {"provider": "auto", "model": "auto", "task_scope": SCOPE,
         "observed_at": FRESH, "passed": True},
        {"model_provenance": {"source": "unknown"}, "task_scope": SCOPE,
         "observed_at": FRESH, "passed": True},
    ])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert result["selected"] is None
    assert "missing_evidence" in _reasons(result)
    assert result["candidates"] == []


def test_requested_route_is_never_accepted_as_the_served_identity():
    result = _compare([{
        "requested_provider": "openai",
        "requested_model": "gpt-test",
        "task_scope": SCOPE,
        "observed_at": FRESH,
        "passed": True,
    }])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "missing_evidence" in _reasons(result)
    assert any(
        "identity_missing" in item["reasons"]
        for item in result["not_task_evidence"])


def test_explicit_unknown_provenance_does_not_fall_back_to_a_direct_pair():
    result = _compare([{
        "model_provenance": {"source": "unknown"},
        "provider": "openai",
        "model": "gpt-test",
        "task_scope": SCOPE,
        "observed_at": FRESH,
        "passed": True,
    }])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "missing_evidence" in _reasons(result)
    assert result["selected"] is None


def test_a_partial_provenance_is_not_completed_from_another_source():
    result = _compare([{
        "model_provenance": {"provider": "openai"},
        "model": "gpt-test",
        "task_scope": SCOPE,
        "observed_at": FRESH,
        "passed": True,
    }])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "missing_evidence" in _reasons(result)
    assert any(
        "identity_partial" in item["reasons"]
        for item in result["not_task_evidence"])


def test_a_single_serving_model_pair_is_an_exact_identity():
    result = _compare([{
        "serving_models": [{"provider": "openai", "model": "gpt-test"}],
        "task_scope": SCOPE,
        "observed_at": FRESH,
        "passed": True,
        "accuracy": 0.9,
    }])

    assert result["outcome"] == "compared"
    assert result["selected"]["route"] == "openai/gpt-test"


# ---------------------------------------------------------------------------
# Scope / rubric / contract matching
# ---------------------------------------------------------------------------


def test_task_scope_mismatch_is_not_task_equivalent_evidence():
    result = _compare([_evidence(task_scope={
        "task_policy": "A different policy",
        "decision_options": ["APPROVE", "REVIEW", "DENY"],
        "subject_field": "Ref",
    })])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "mismatched_evidence" in _reasons(result)
    assert any(
        "task_scope_mismatch" in item["reasons"]
        for item in result["not_task_evidence"])
    assert result["selected"] is None


def test_a_global_leaderboard_is_rejected_as_task_evidence():
    result = _compare([_evidence(source="global_model_leaderboard")])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "mismatched_evidence" in _reasons(result)
    assert any(
        "global_leaderboard_not_task_evidence" in item["reasons"]
        for item in result["not_task_evidence"])
    assert result["selected"] is None


def test_rubric_version_must_match_and_be_present():
    result = _compare(
        [
            _evidence(rubric_version="heldout-v1"),
            _evidence(model="other", rubric_version=""),
        ],
        rubric_version="heldout-v2",
    )

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "mismatched_evidence" in _reasons(result)
    reasons = {
        reason
        for item in result["not_task_evidence"]
        for reason in item["reasons"]
    }
    assert "rubric_version_mismatch" in reasons
    assert "rubric_version_missing" in reasons


def test_contract_version_mismatch_is_mismatched_evidence():
    result = _compare(
        [_evidence(contract_version="review-result-1")],
        contract_version="review-result-2",
    )

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "mismatched_evidence" in _reasons(result)
    assert any(
        "contract_version_mismatch" in item["reasons"]
        for item in result["not_task_evidence"])


def test_scope_digest_is_canonical_and_ignores_extra_keys():
    first = task_scope_digest(SCOPE)
    second = task_scope_digest({
        "task_policy": SCOPE["task_policy"],
        "decision_options": list(SCOPE["decision_options"]),
        "subject_field": SCOPE["subject_field"],
        "canvas_id": "ignored",
    })
    assert first == second
    assert normalize_task_scope(SCOPE)["decision_options"] == [
        "APPROVE", "REVIEW", "DENY"]


# ---------------------------------------------------------------------------
# Newest valid comparable results
# ---------------------------------------------------------------------------


def test_newest_result_per_route_wins_and_candidates_rank_by_accuracy():
    result = _compare([
        _evidence("openai", "gpt-test", accuracy=0.80,
                  observed_at=(NOW - timedelta(days=8)).isoformat()),
        _evidence("openai", "gpt-test", accuracy=0.95),
        _evidence("other", "model-two", accuracy=0.90),
    ])

    assert result["outcome"] == "compared"
    assert result["selected"]["route"] == "openai/gpt-test"
    assert result["selected"]["score"] == 0.95
    assert [item["route"] for item in result["ranked"]] == [
        "openai/gpt-test", "other/model-two"]


def test_newer_comparable_cohort_supersedes_an_older_scoring_version():
    result = _compare([
        _evidence(accuracy=1.0, scoring_version="v1", dataset_sha256="sha-old"),
        _evidence(accuracy=0.80, scoring_version="v2",
                  dataset_sha256="sha-current"),
    ])

    assert result["outcome"] == "compared"
    assert result["selected"]["score"] == 0.80
    assert result["comparison_set"]["scoring_version"] == "v2"
    assert any(
        "superseded_result_set" in item["reasons"]
        for item in result["not_task_evidence"])


def test_another_routes_newer_cohort_does_not_supersede_the_compared_routes():
    result = _compare(
        [
            _evidence("openai", "gpt-test", accuracy=0.99,
                      scoring_version="v2", dataset_sha256="sha-current"),
            _evidence("other", "model-two", accuracy=0.80,
                      scoring_version="v1", dataset_sha256="sha-old"),
        ],
        candidates=[{"provider": "other", "model": "model-two"}],
    )

    assert result["outcome"] == "compared"
    assert result["selected"]["route"] == "other/model-two"
    assert result["selected"]["score"] == 0.80
    assert result["comparison_set"]["scoring_version"] == "v1"


def test_conflicting_newest_results_are_ambiguous():
    result = _compare([
        _evidence(accuracy=0.95),
        _evidence(accuracy=0.55),
    ])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "ambiguous_evidence" in _reasons(result)
    assert result["candidates"][0]["reasons"] == [
        "conflicting_newest_evidence"]


# ---------------------------------------------------------------------------
# Freshness policy
# ---------------------------------------------------------------------------


def test_stale_evidence_is_an_explicit_insufficient_result():
    result = _compare([_evidence(observed_at=STALE)])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "stale_evidence" in _reasons(result)
    assert result["candidates"][0]["reasons"] == ["evidence_expired"]
    assert result["freshness"]["window_days"] == 30


def test_missing_timestamp_is_stale_when_freshness_is_required():
    result = _compare([_evidence(observed_at=None)])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "stale_evidence" in _reasons(result)
    assert result["candidates"][0]["reasons"] == ["observed_at_missing"]


def test_freshness_can_reuse_an_existing_capability_profile():
    from core.llm.capability_profiles import get_profile

    profile = get_profile("employee_adaptive_planning")
    result = _compare(
        [_evidence(observed_at=STALE)],
        profile_name=profile.name,
    )

    assert result["freshness"]["policy"] == (
        f"capability_profile:{profile.name}@{profile.version}")
    assert result["freshness"]["window_days"] == profile.evidence_window_days
    assert "stale_evidence" in _reasons(result)

    # An explicit window overrides the profile policy.
    relaxed = _compare(
        [_evidence(observed_at=STALE)],
        profile_name=profile.name,
        freshness_days=90,
    )
    assert relaxed["outcome"] == "compared"
    assert relaxed["freshness"]["window_days"] == 90


def test_freshness_can_come_from_an_injected_policy_mapping():
    result = _compare(
        [_evidence(observed_at=(NOW - timedelta(days=15)).isoformat())],
        freshness_policy={
            "name": "custom_workload",
            "version": "2026-11-01",
            "evidence_window_days": 10,
        },
    )

    assert result["freshness"]["policy"] == (
        "capability_profile:custom_workload@2026-11-01")
    assert result["freshness"]["window_days"] == 10
    assert "stale_evidence" in _reasons(result)


def test_nonpositive_or_malformed_freshness_never_bypasses_freshness():
    """Zero, negative and malformed windows fall back to the default."""
    for bad_window in (0, -7, "none", "30d", True):
        result = _compare(
            [_evidence(observed_at=STALE)], freshness_days=bad_window)

        assert result["outcome"] == INSUFFICIENT_EVIDENCE, bad_window
        assert result["freshness"]["window_days"] == 30
        assert "stale_evidence" in _reasons(result)
        assert result["selected"] is None


def test_nonpositive_injected_policy_window_falls_back_to_the_default():
    result = _compare(
        [_evidence(observed_at=STALE)],
        freshness_policy={
            "name": "bad_profile",
            "version": "1",
            "evidence_window_days": 0,
        },
    )

    assert result["freshness"]["window_days"] == 30
    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "stale_evidence" in _reasons(result)


def test_a_future_result_timestamp_is_not_trusted_for_freshness():
    result = _compare(
        [_evidence(observed_at=(NOW + timedelta(days=1)).isoformat())])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "stale_evidence" in _reasons(result)
    assert result["candidates"][0]["reasons"] == ["observed_at_untrusted"]


def test_malformed_timestamps_are_never_fresh():
    for bad_timestamp in ("not-a-date", object()):
        result = _compare([_evidence(observed_at=bad_timestamp)])

        assert result["outcome"] == INSUFFICIENT_EVIDENCE, bad_timestamp
        assert result["candidates"][0]["reasons"] == ["observed_at_missing"]


# ---------------------------------------------------------------------------
# Ambiguity / mismatch / failure
# ---------------------------------------------------------------------------


def test_mixed_serving_identity_and_unattributed_calls_are_ambiguous():
    mixed = _compare([_evidence(serving_models=[
        {"provider": "openai", "model": "gpt-test"},
        {"provider": "other", "model": "model-two"},
    ])])
    assert mixed["outcome"] == INSUFFICIENT_EVIDENCE
    assert "ambiguous_evidence" in _reasons(mixed)
    assert mixed["candidates"][0]["reasons"] == ["mixed_serving_identity"]

    unattributed = _compare([_evidence(unattributed_calls=2)])
    assert unattributed["outcome"] == INSUFFICIENT_EVIDENCE
    assert unattributed["candidates"][0]["reasons"] == ["unattributed_calls"]


def test_registry_result_disagreement_is_ambiguous():
    result = _compare([_evidence(
        registry_status="qualified", passed=False)])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "ambiguous_evidence" in _reasons(result)
    assert result["candidates"][0]["reasons"] == [
        "registry_result_disagreement"]


def test_declared_and_served_identity_mismatch_is_rejected():
    result = _compare([_evidence(
        declared_provider="openai", declared_model="gpt-test",
        provider="fallback", model="other-model",
    )])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "mismatched_evidence" in _reasons(result)
    assert any(
        "declared_served_identity_mismatch" in item["reasons"]
        for item in result["not_task_evidence"])


def test_revoked_evidence_is_mismatched():
    result = _compare([_evidence(revoked=True)])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "mismatched_evidence" in _reasons(result)
    assert result["candidates"][0]["reasons"] == ["evidence_revoked"]


def test_failed_evidence_is_a_valid_negative_not_missing_evidence():
    result = _compare([_evidence(passed=False, accuracy=0.4)])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert _reasons(result) == ["no_passing_evidence"]
    assert result["candidates"][0]["evidence_state"] == "failed"
    assert result["candidates"][0]["reasons"] == ["evidence_not_passed"]


def test_accuracy_floor_marks_a_passing_result_as_failed():
    result = _compare(
        [_evidence(accuracy=0.70)], min_accuracy=0.90)

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert result["candidates"][0]["evidence_state"] == "failed"
    assert result["candidates"][0]["reasons"] == ["below_accuracy_floor"]


def test_partial_evidence_selects_the_sufficient_route_and_names_the_rest():
    result = _compare([
        _evidence("openai", "gpt-test"),
        _evidence("other", "model-two", observed_at=STALE),
    ], candidates=[
        {"provider": "openai", "model": "gpt-test"},
        {"provider": "other", "model": "model-two"},
        {"provider": "missing", "model": "model-three"},
    ])

    assert result["outcome"] == "compared"
    assert result["evidence_state"] == "partial"
    assert result["selected"]["route"] == "openai/gpt-test"
    assert result["insufficient_evidence"]["reasons"] == [
        "missing_evidence", "stale_evidence"]
    candidate_reasons = result["insufficient_evidence"]["candidate_reasons"]
    assert candidate_reasons["other/model-two"] == ["evidence_expired"]
    assert candidate_reasons["missing/model-three"] == [
        "no_task_scoped_evidence"]


def test_comparison_is_json_serializable():
    result = _compare([_evidence()])
    payload = json.dumps(result)
    assert '"outcome": "compared"' in payload


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


def test_registry_claim_without_frozen_evidence_is_insufficient(tmp_path):
    """A qualified registry row alone is not a frozen workload result."""
    registry = {
        "schema": "atom-assessment-qualification-1",
        "configurations": [{
            "id": "missing-evidence",
            "capability": "canvas_assessment.model_judgment",
            "provider": "openai",
            "model": "gpt-test",
            "contract_version": "review-result-2",
            "status": "qualified",
            "revoked": False,
            "evidence": "does-not-exist",
            "scope": SCOPE,
        }],
    }

    loaded = load_assessment_qualification_evidence(
        registry=registry, repo_root=tmp_path)
    assert len(loaded) == 1
    assert loaded[0]["issues"] == ["evidence_path_missing"]

    result = compare_model_evidence(
        task_scope=SCOPE,
        evidence=loaded,
        contract_version="review-result-2",
        now=NOW,
    )

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert result["selected"] is None
    assert "missing_evidence" in _reasons(result)
    assert "evidence_path_missing" in result["candidates"][0]["reasons"]


# ---------------------------------------------------------------------------
# Frozen dataset dates bind only to the scored runs they belong to
# ---------------------------------------------------------------------------


def test_frozen_dataset_date_requires_a_verified_binding(tmp_path):
    """A frozen date bounds freshness only for runs on the frozen set."""
    frozen_set = {
        "schema": "atom-assessment-dataset-1",
        "id": "qualification-2026-10-31",
        "frozen": "2026-10-31",
    }
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "qualification-set.json").write_text(
        json.dumps(frozen_set))
    (evidence_dir / "judgment-bound.json").write_text(json.dumps({
        "schema": "atom-substantive-assessment-judgment-2",
        "served_provider": "openai",
        "served_model": "gpt-test",
        "dataset_id": "qualification-2026-10-31",
        "dataset_sha256": "sha-x",
        "accuracy": 0.9,
        "ok": True,
        "phase": "create",
        "scoring": {"version": "v1"},
    }))
    (evidence_dir / "judgment-unbound.json").write_text(json.dumps({
        "schema": "atom-substantive-assessment-judgment-2",
        "served_provider": "openai",
        "served_model": "gpt-test",
        "dataset_id": "qualification-2026-11-15",
        "dataset_sha256": "sha-y",
        "accuracy": 0.9,
        "ok": True,
        "phase": "create",
        "scoring": {"version": "v1"},
    }))
    registry = {"configurations": [{
        "id": "bound",
        "capability": "canvas_assessment.model_judgment",
        "provider": "openai",
        "model": "gpt-test",
        "evidence": str(evidence_dir),
        "scope": SCOPE,
    }]}

    loaded = load_assessment_qualification_evidence(
        registry=registry, repo_root=tmp_path)
    bound = [
        record for record in loaded
        if record["observed_at_source"] == "frozen_dataset_date"]
    unbound = [
        record for record in loaded
        if record["observed_at_source"] != "frozen_dataset_date"]

    # The run naming the frozen set's id gets the conservative bound; the
    # run from a different dataset does not inherit the frozen date.
    assert len(bound) == 1
    assert bound[0]["observed_at"] == "2026-10-31T00:00:00+00:00"
    assert len(unbound) == 1
    assert unbound[0]["observed_at"] is None

    result = compare_model_evidence(
        task_scope=SCOPE, evidence=unbound, now=NOW)

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "stale_evidence" in _reasons(result)
    assert result["candidates"][0]["reasons"] == ["observed_at_missing"]


# ---------------------------------------------------------------------------
# Registry-only claims, declared routes and unscored artifacts
# ---------------------------------------------------------------------------


def test_a_registry_only_positive_claim_cannot_establish_evidence(tmp_path):
    """A qualified registry row alone is not a frozen workload result."""
    registry = {"configurations": [{
        "id": "claim-only",
        "capability": "canvas_assessment.model_judgment",
        "provider": "openai",
        "model": "gpt-test",
        "status": "qualified",
        "revoked": False,
        "scope": SCOPE,
    }]}

    loaded = load_assessment_qualification_evidence(
        registry=registry, repo_root=tmp_path)
    assert loaded[0]["passed"] is None

    result = compare_model_evidence(
        task_scope=SCOPE, evidence=loaded, now=NOW)

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert result["selected"] is None
    assert result["candidates"][0]["evidence_state"] == "insufficient"


def test_a_registry_only_failure_keeps_its_negative_verdict(tmp_path):
    registry = {"configurations": [{
        "id": "failed-claim",
        "capability": "canvas_assessment.model_judgment",
        "provider": "openai",
        "model": "gpt-test",
        "status": "failed",
        "revoked": False,
        "qualified_at": FRESH,
        "scope": SCOPE,
    }]}

    loaded = load_assessment_qualification_evidence(
        registry=registry, repo_root=tmp_path)
    assert loaded[0]["passed"] is False

    result = compare_model_evidence(
        task_scope=SCOPE, evidence=loaded, now=NOW)

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert _reasons(result) == ["no_passing_evidence"]
    assert result["candidates"][0]["evidence_state"] == "failed"
    assert result["candidates"][0]["reasons"] == ["evidence_not_passed"]


def test_a_declared_route_alone_is_not_positive_evidence():
    result = _compare([{
        "declared_provider": "openai",
        "declared_model": "gpt-test",
        "task_scope": SCOPE,
        "observed_at": FRESH,
    }])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "missing_evidence" in _reasons(result)
    assert result["selected"] is None


def test_an_unscored_artifact_is_never_positive_benchmark_evidence(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "vendor-dump.json").write_text(json.dumps({
        "schema": "vendor-run-dump-1",
        "served_provider": "openai",
        "served_model": "gpt-test",
        "status": "success",
    }))
    registry = {"configurations": [{
        "id": "dump",
        "capability": "canvas_assessment.model_judgment",
        "provider": "openai",
        "model": "gpt-test",
        "evidence": str(evidence_dir),
        "scope": SCOPE,
    }]}

    loaded = load_assessment_qualification_evidence(
        registry=registry, repo_root=tmp_path)
    assert "unscored_artifact" in loaded[0]["issues"]

    result = compare_model_evidence(
        task_scope=SCOPE, evidence=loaded, now=NOW)

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert result["selected"] is None
    assert "missing_evidence" in _reasons(result)
    assert "unscored_artifact" in result["candidates"][0]["reasons"]


# ---------------------------------------------------------------------------
# Real durable source: the assessment qualification registry
# ---------------------------------------------------------------------------


def test_frozen_assessment_results_load_and_do_not_select_the_failed_model():
    """The real registry's failed llama3.1:8b result stays a failed result.

    This is the durable-source integration check: it reads the server-owned
    registry and the frozen ``judgment-*.json`` results it points at. No
    provider is called and no runtime consumer is changed.
    """
    from core.canvas_capability_service import (
        load_assessment_qualification_registry,
    )

    registry = load_assessment_qualification_registry()
    entries = [
        entry for entry in (registry.get("configurations") or [])
        if entry.get("capability") == "canvas_assessment.model_judgment"
    ]
    if not entries:
        pytest.skip("assessment qualification registry has no entries")

    entry = entries[0]
    loaded = load_assessment_qualification_evidence(registry=registry)
    if not any(record.get("scoring_version") for record in loaded):
        pytest.skip("frozen assessment qualification results are unavailable")

    assert all(
        record["provider"] == entry["provider"]
        and record["model"] == entry["model"]
        for record in loaded
    )

    result = compare_model_evidence(
        task_scope=entry["scope"],
        evidence=loaded,
        contract_version=entry["contract_version"],
        now=NOW,
    )

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert result["selected"] is None
    assert result["comparison_set"]["scoring_version"] == "v2-2026-10-31"
    assert result["candidates"][0]["provider"] == entry["provider"]
    assert result["candidates"][0]["model"] == entry["model"]
    assert result["candidates"][0]["evidence_state"] == "failed"
    assert "no_passing_evidence" in _reasons(result)


# ---------------------------------------------------------------------------
# Graduation baseline
# ---------------------------------------------------------------------------


def test_a_fresh_but_weaker_model_is_rejected_against_the_baseline():
    result = _compare(
        [
            _evidence("openai", "gpt-test", accuracy=0.95),
            _evidence("other", "model-two", accuracy=0.80),
        ],
        baseline={"provider": "openai", "model": "gpt-test"},
    )

    assert result["baseline"]["state"] == "established"
    assert result["baseline"]["score"] == 0.95
    assert result["candidates"][1]["evidence_state"] == "failed"
    assert result["candidates"][1]["reasons"] == ["baseline_not_met"]
    # The weaker model is excluded from ranking; only the baseline survives.
    assert [item["route"] for item in result["ranked"]] == ["openai/gpt-test"]
    assert result["selected"]["route"] == "openai/gpt-test"


def test_a_model_meeting_the_baseline_is_still_selected():
    result = _compare(
        [
            _evidence("openai", "gpt-test", accuracy=0.95),
            _evidence("other", "model-two", accuracy=0.98),
        ],
        baseline={"provider": "openai", "model": "gpt-test"},
    )

    assert result["outcome"] == "compared"
    assert result["selected"]["route"] == "other/model-two"


def test_baseline_requires_the_same_dataset_hash():
    result = _compare(
        [
            _evidence("openai", "gpt-test", accuracy=0.95,
                      dataset_sha256="sha-baseline"),
            _evidence("other", "model-two", accuracy=0.99,
                      dataset_sha256="sha-other"),
        ],
        baseline={"provider": "openai", "model": "gpt-test"},
    )

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert result["baseline"]["state"] == "not_established"
    assert "missing_evidence" in _reasons(result)
    assert result["selected"] is None


def test_baseline_abstention_floor_applies_where_scored():
    baseline_record = _evidence(
        "openai", "gpt-test", accuracy=0.90,
        safe_abstention={"passed": True})

    unproven = _evidence("other", "model-two", accuracy=0.99)
    result = _compare(
        [baseline_record, unproven],
        baseline={"provider": "openai", "model": "gpt-test"},
    )

    assert result["candidates"][1]["evidence_state"] == "failed"
    assert result["candidates"][1]["reasons"] == ["abstention_not_met"]
    assert result["candidates"][1] not in result["ranked"]

    proven = _evidence(
        "other", "model-three", accuracy=0.99,
        safe_abstention={"passed": True})
    result = _compare(
        [baseline_record, proven],
        baseline={"provider": "openai", "model": "gpt-test"},
    )

    assert result["outcome"] == "compared"
    assert result["selected"]["route"] == "other/model-three"


def test_a_baseline_without_a_complete_identity_is_insufficient():
    result = _compare([_evidence()], baseline={"provider": "openai"})

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert result["baseline"]["state"] == "invalid_identity"
    assert "missing_evidence" in _reasons(result)
    assert result["selected"] is None


# ---------------------------------------------------------------------------
# Model build identity
# ---------------------------------------------------------------------------


def test_conflicting_model_build_identity_is_insufficient():
    result = _compare([
        _evidence(resolved_model="gpt-test-1",
                  observed_at=(NOW - timedelta(days=1)).isoformat()),
        _evidence(resolved_model="gpt-test-2",
                  observed_at=(NOW - timedelta(days=1)).isoformat()),
    ])

    assert result["outcome"] == INSUFFICIENT_EVIDENCE
    assert "ambiguous_evidence" in _reasons(result)
    assert result["candidates"][0]["reasons"] == ["model_build_conflict"]


def test_available_model_build_identity_is_checked_and_surfaced():
    result = _compare([_evidence(resolved_model="gpt-test-2")])

    assert result["outcome"] == "compared"
    assert result["candidates"][0]["evidence"]["model_build"] == "gpt-test-2"
