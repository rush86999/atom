"""Forced overlapping-session evaluations for the feedback write CAS.

The weak writer reads the transport row, pauses, a second session commits a
stronger failure, then the weak writer resumes. The database-enforced CAS must
match zero rows, reload the authoritative row, and refuse/skip — never overwrite
the committed failure from a stale snapshot.
"""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.llm.capability_profiles import (
    get_profile,
    load_feedback_evidence,
    reset_capability_evidence_cache,
)
from tests.test_employee_business_feedback import (  # noqa: F401
    feedback_db,
    fresh_router,
    _insert_outcome_row,
    _row_by_id,
    _synthetic_result,
)


def _pause_weak_read(monkeypatch, generation, read, release):
    from sqlalchemy.orm import Query

    original = Query.all

    def paused_all(query):
        rows = original(query)
        if (threading.current_thread().name.startswith("weak")
                and rows
                and any(getattr(row, "routing_result_id", None) == generation
                        for row in rows)):
            read.set()
            assert release.wait(20)
        return rows

    monkeypatch.setattr(Query, "all", paused_all)


def _evaluate(positive, generation):
    from core.employee_routing_feedback import (
        record_attempt_evaluation,
        record_pending_business_evaluation,
    )

    result = _synthetic_result(generation)
    if positive == "pending":
        return asyncio.run(record_pending_business_evaluation(
            result, stage="employee_evidence_selection",
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
    return asyncio.run(record_attempt_evaluation(
        result, stage="employee_evidence_selection",
        evaluation="satisfied" if positive else "failed",
        failure_kind=None if positive else "wrong_evidence_selection",
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))


@pytest.mark.parametrize("weak_kind", ["positive", "pending"])
def test_stale_weak_annotation_cannot_erase_committed_failure(
        feedback_db, fresh_router, monkeypatch, weak_kind):
    generation = f"interleave-stale-{weak_kind}"
    row_id = _insert_outcome_row(feedback_db, generation)
    read = threading.Event()
    release = threading.Event()
    _pause_weak_read(monkeypatch, generation, read, release)

    with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weak") as pool:
        pending = pool.submit(_evaluate, weak_kind, generation)
        assert read.wait(20)
        try:
            strong = _evaluate(False, generation)
            assert strong["status"] == "annotated", strong
        finally:
            release.set()
        weak = pending.result(timeout=20)

    assert weak["recorded"] is False, (weak, strong)
    assert weak["status"] in ("skipped_verdict", "refused_verdict"), (
        weak, strong)
    row = _row_by_id(feedback_db, row_id)  # fresh session
    assert row.success is False, (weak, strong, row.prompt_features)
    assert row.quality_satisfied is False, (weak, strong, row.prompt_features)
    features = row.prompt_features or {}
    assert features.get("business_outcome") == "failed", (
        weak, strong, features)
    assert features.get("verdict") == "wrong_evidence_selection", (
        weak, strong, features)
    assert features.get("failure_kind") == "wrong_evidence_selection", (
        weak, strong, features)

    # The committed failure is still visible to a fresh selector read.
    reset_capability_evidence_cache()
    evidence = load_feedback_evidence(
        get_profile("employee_evidence_selection"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    route = evidence["local_ctrl1234/llama3.1:8b"]
    assert route["semantic_failures"] == 1, evidence
    assert route["last_failure_kind"] == "semantic_failure", evidence


def test_stronger_failure_overwrites_committed_positive(
        feedback_db, fresh_router):
    generation = "interleave-stronger-failure"
    row_id = _insert_outcome_row(feedback_db, generation)
    positive = _evaluate(True, generation)
    assert positive["status"] == "annotated", positive
    failure = _evaluate(False, generation)
    assert failure["status"] == "annotated", failure
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False
    features = row.prompt_features or {}
    assert features.get("verdict") == "wrong_evidence_selection"
    assert features.get("business_outcome") == "failed"

    reset_capability_evidence_cache()
    evidence = load_feedback_evidence(
        get_profile("employee_evidence_selection"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    route = evidence["local_ctrl1234/llama3.1:8b"]
    assert route["semantic_failures"] == 1, evidence
    assert route["successes"] == 0, evidence


def test_duplicate_verdict_is_idempotent_and_incident_identity_stable(
        feedback_db, fresh_router):
    generation = "interleave-duplicate"
    row_id = _insert_outcome_row(feedback_db, generation)
    first = _evaluate(False, generation)
    assert first["status"] == "annotated", first
    reset_capability_evidence_cache()
    before = load_feedback_evidence(
        get_profile("employee_evidence_selection"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    incident = before["local_ctrl1234/llama3.1:8b"]["incidents"][0][
        "incident_id"]

    second = _evaluate(False, generation)
    assert second["recorded"] is False, second
    assert second["status"] == "skipped_verdict", second
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False
    reset_capability_evidence_cache()
    after = load_feedback_evidence(
        get_profile("employee_evidence_selection"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    assert after["local_ctrl1234/llama3.1:8b"]["incidents"][0][
        "incident_id"] == incident


def test_stale_failure_read_retries_after_positive_commit(
        feedback_db, fresh_router, monkeypatch):
    """A failure that read before a positive commit retries on fresh state."""
    generation = "interleave-failure-after-positive"
    row_id = _insert_outcome_row(feedback_db, generation)
    read = threading.Event()
    release = threading.Event()
    _pause_weak_read(monkeypatch, generation, read, release)

    with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weak") as pool:
        late_failure = pool.submit(_evaluate, False, generation)
        assert read.wait(20)
        try:
            positive = _evaluate(True, generation)
            assert positive["status"] == "annotated", positive
        finally:
            release.set()
        failure = late_failure.result(timeout=20)

    assert failure["status"] == "annotated", failure
    row = _row_by_id(feedback_db, row_id)
    assert row.success is False
    features = row.prompt_features or {}
    assert features.get("business_outcome") == "failed"
    assert features.get("verdict") == "wrong_evidence_selection"


@pytest.mark.parametrize(
    "legacy_verdict", ["grounding_ok", "unsupported_figures"])
def test_pending_business_cannot_erase_committed_legacy_verdict(
        feedback_db, fresh_router, monkeypatch, legacy_verdict):
    from core.employee_routing_feedback import (
        record_pending_business_evaluation,
    )
    from core.learning_llm_router import (
        LearningBasedRouter,
        RoutingFeedback,
    )

    generation = f"legacy-grounding-{legacy_verdict}"
    row_id = _insert_outcome_row(feedback_db, generation)
    if legacy_verdict == "unsupported_figures":
        from core.models import LLMRoutingFeedback

        with feedback_db["Session"]() as session:
            row = session.query(LLMRoutingFeedback).filter_by(
                id=row_id).one()
            row.quality_satisfied = False
            row.user_satisfaction = 0.1
            session.commit()

    read = threading.Event()
    release = threading.Event()
    _pause_weak_read(monkeypatch, generation, read, release)

    def _weak_pending():
        return asyncio.run(record_pending_business_evaluation(
            _synthetic_result(generation),
            stage="employee_evidence_selection",
            workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))

    with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weak") as pool:
        pending = pool.submit(_weak_pending)
        assert read.wait(20)
        try:
            writer = LearningBasedRouter.__new__(LearningBasedRouter)
            strong = writer._persist_feedback(
                RoutingFeedback(
                    routing_result_id=generation,
                    tenant_id="tenant-ctrl",
                    model_id="llama3.1:8b",
                    task_type="general",
                    success=True,
                    quality_satisfied=(
                        legacy_verdict != "unsupported_figures"),
                    cost_within_budget=True,
                    user_satisfaction=(
                        0.1 if legacy_verdict == "unsupported_figures"
                        else 0.9),
                ),
                {"verdict": legacy_verdict})
            assert strong == "annotated", strong
        finally:
            release.set()
        weak = pending.result(timeout=20)

    assert weak["recorded"] is False, weak
    assert weak["status"] == "skipped_verdict", weak
    row = _row_by_id(feedback_db, row_id)
    assert row.prompt_features.get("verdict") == legacy_verdict, (
        weak, row.prompt_features)


def test_stale_legacy_grounding_cannot_overwrite_committed_business_failure(
        feedback_db, fresh_router, monkeypatch):
    from core.employee_routing_feedback import record_attempt_evaluation
    from core.learning_llm_router import (
        LearningBasedRouter,
        RoutingFeedback,
    )

    generation = "stale-legacy-grounding"
    row_id = _insert_outcome_row(feedback_db, generation)
    read = threading.Event()
    release = threading.Event()
    _pause_weak_read(monkeypatch, generation, read, release)

    def _weak_legacy():
        writer = LearningBasedRouter.__new__(LearningBasedRouter)
        return writer._persist_feedback(
            RoutingFeedback(
                routing_result_id=generation,
                tenant_id="tenant-ctrl",
                model_id="llama3.1:8b",
                task_type="general",
                success=True,
                quality_satisfied=True,
                cost_within_budget=True,
                user_satisfaction=0.9,
            ),
            {"verdict": "grounding_ok"})

    with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weak") as pool:
        pending = pool.submit(_weak_legacy)
        assert read.wait(20)
        try:
            strong = asyncio.run(record_attempt_evaluation(
                _synthetic_result(generation),
                stage="employee_evidence_selection",
                evaluation="failed",
                failure_kind="wrong_evidence_selection",
                workspace_id="ws-ctrl", tenant_id="tenant-ctrl"))
            assert strong["status"] == "annotated", strong
        finally:
            release.set()
        weak = pending.result(timeout=20)

    assert weak == "skipped_verdict", weak
    row = _row_by_id(feedback_db, row_id)
    assert row.prompt_features.get("verdict") == (
        "wrong_evidence_selection"), (weak, row.prompt_features)
    assert row.prompt_features.get("evaluation_revision", 0) >= 1


def test_changed_binding_during_evaluation_refuses(
        feedback_db, fresh_router, monkeypatch):
    from core.models import LLMRoutingFeedback

    generation = "interleave-binding-change"
    row_id = _insert_outcome_row(feedback_db, generation)
    read = threading.Event()
    release = threading.Event()
    _pause_weak_read(monkeypatch, generation, read, release)

    with ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weak") as pool:
        pending = pool.submit(_evaluate, "positive", generation)
        assert read.wait(20)
        try:
            with feedback_db["Session"]() as session:
                row = session.query(LLMRoutingFeedback).filter(
                    LLMRoutingFeedback.id == row_id).one()
                features = dict(row.prompt_features or {})
                features["workspace_id"] = "ws-changed"
                row.prompt_features = features
                session.commit()
        finally:
            release.set()
        weak = pending.result(timeout=20)

    assert weak["recorded"] is False, weak
    assert weak["status"] == "refused_workspace", weak
    row = _row_by_id(feedback_db, row_id)
    features = row.prompt_features or {}
    assert features.get("workspace_id") == "ws-changed"
    assert features.get("business_outcome") is None
    assert row.success is True

    reset_capability_evidence_cache()
    evidence = load_feedback_evidence(
        get_profile("employee_evidence_selection"),
        workspace_id="ws-ctrl", tenant_id="tenant-ctrl")
    assert "local_ctrl1234/llama3.1:8b" not in evidence, evidence
