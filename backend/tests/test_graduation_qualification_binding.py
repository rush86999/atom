"""Focused scratch tests for durable qualification-receipt bindings.

Covers the write -> durable read -> revalidation path for the optional
server-owned benchmark identity (dataset hash, rubric, workload scope) and the
actual serving routes resolved from validated evidence. No provider call, no
live DB, no dispatch path.

Run with ``TESTING=1`` (set below so a direct invocation cannot touch a live
world).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

import core.agent_graduation_service as grad
from core.agent_graduation_service import (
    QUALIFICATION_BINDING_SCHEMA,
    commit_qualified_transition,
    evaluate_qualification_gate,
    find_qualification_receipt,
    request_qualification_review,
    resolve_runtime_qualification_baseline,
    validate_qualification_evidence,
    validate_qualification_review_binding,
    write_qualification_receipt_from_review,
)
from core.database import Base
from core.models import (
    AgentEpisode,
    AgentExecution,
    AgentRegistry,
    GraduationExam,
    HITLAction,
    HITLActionStatus,
    PromotionHistory,
    Tenant,
    User,
    Workspace,
)
from core.promotion_policy_service import (
    ASSESSMENT_POLICY_KEY,
    get_assessment_policy,
)

grad.get_lancedb_handler = lambda: None
grad.POMDP_AVAILABLE = False

TENANT = "binding-tenant"
WORKSPACE = "binding-workspace"
SUPERVISOR = "binding-supervisor"
ADMIN = "binding-admin"
AGENT = "binding-agent"

DATASET_SHA = "a" * 64
SCOPE = {
    "task_policy": "Approve Open records with Amount >= 100 and Risk Low.",
    "decision_options": ["APPROVE", "REVIEW", "DENY"],
    "subject_field": "Ref",
}


def _benchmark_identity() -> dict:
    return {
        "dataset_sha256": DATASET_SHA,
        "rubric_version": "heldout-v1",
        "task_scope": dict(SCOPE),
    }


def _provenance(provider: str = "openai", model: str = "gpt-5.4-2026-03") -> dict:
    return {
        "provider": provider,
        "model": model,
        "serving_models": [{"provider": provider, "model": model}],
    }


class World:
    def __init__(self, tmp_path, *, with_binding: bool = True):
        self.db_path = tmp_path / "qualification-binding.db"
        self._connect()
        started = datetime.now(timezone.utc) - timedelta(days=2)
        with self.Session() as db:
            db.add(Tenant(
                id=TENANT, name="Binding Tenant",
                subdomain=f"b-{uuid.uuid4().hex[:8]}", edition="personal",
                is_active=True,
            ))
            db.add(Workspace(id=WORKSPACE, name="Binding", tenant_id=TENANT))
            db.add_all([
                User(
                    id=SUPERVISOR, tenant_id=TENANT, workspace_id=WORKSPACE,
                    email="sup@binding.test", first_name="S", last_name="V",
                    role="team_lead", status="active", is_active=True,
                ),
                User(
                    id=ADMIN, tenant_id=TENANT, workspace_id=WORKSPACE,
                    email="admin@binding.test", first_name="A", last_name="V",
                    role="admin", status="active", is_active=True,
                ),
            ])
            db.add(AgentRegistry(
                id=AGENT, name="Binding Candidate", category="operations",
                role="agent", type="personal", capabilities=[],
                module_path="core.generic_agent", class_name="GenericAgent",
                user_id=SUPERVISOR, workspace_id=WORKSPACE, tenant_id=TENANT,
                status="student", enabled=True, confidence_score=0.62,
                configuration={"learning": {"role": "operations", "log": []}},
            ))
            episode_metadata = (
                {
                    "benchmark_identity": _benchmark_identity(),
                    "model_provenance": _provenance(),
                }
                if with_binding else {}
            )
            execution_metadata = (
                {"model_provenance": _provenance()}
                if with_binding else {}
            )
            db.add(AgentExecution(
                id="exec-1", agent_id=AGENT, tenant_id=TENANT,
                workspace_id=WORKSPACE, status="completed",
                input_summary="held-out binding task",
                result_summary="actual durable binding output",
                completed_at=started + timedelta(minutes=5),
                metadata_json=execution_metadata,
            ))
            db.add(AgentEpisode(
                id="ep-1", agent_id=AGENT, tenant_id=TENANT,
                workspace_id=WORKSPACE, execution_id="exec-1",
                task_description="held-out binding task",
                maturity_at_time="student", constitutional_score=0.9,
                human_intervention_count=0, confidence_score=0.62,
                outcome="success", success=True, status="completed",
                started_at=started, completed_at=started + timedelta(minutes=5),
                metadata_json=episode_metadata,
            ))
            db.commit()

    def _connect(self):
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, expire_on_commit=False)

    def reopen(self):
        """Fresh engine/session on the same durable file (restart readback)."""
        self.engine.dispose()
        self._connect()


@pytest.fixture(autouse=True)
def _default_policy(monkeypatch):
    monkeypatch.delenv(ASSESSMENT_POLICY_KEY, raising=False)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def _request(world, refs=None, note=None):
    refs = refs or [
        {"kind": "agent_episode", "id": "ep-1"},
        {"kind": "agent_execution", "id": "exec-1"},
    ]
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        result = request_qualification_review(
            db,
            agent=agent,
            target_level="INTERN",
            evidence_refs=refs,
            rubric_version="heldout-v1",
            requested_by=SUPERVISOR,
            tenant_id=TENANT,
            workspace_id=WORKSPACE,
            note=note,
        )
        return result["action_id"]


def _approve_and_write(world, action_id):
    with world.Session() as db:
        action = db.get(HITLAction, action_id)
        assert validate_qualification_review_binding(db, action)["valid"]
        action.status = HITLActionStatus.APPROVED.value
        action.reviewed_by = ADMIN
        action.reviewed_at = datetime.now(timezone.utc)
        db.commit()
    with world.Session() as db:
        result = write_qualification_receipt_from_review(
            db, action_id=action_id, approved=True, reviewer_id=ADMIN,
        )
        assert result["state"] == "valid", result
        return result["receipt_id"]


def _receipt(world):
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        return db.get(GraduationExam, agent.last_exam_id)


def _read(world):
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        return find_qualification_receipt(
            db, agent, "INTERN", get_assessment_policy(db))


def test_receipt_binds_server_evidence_not_caller_claims(world):
    # Caller-controlled lookalikes on the refs must never become the binding.
    caller_refs = [
        {
            "kind": "agent_episode", "id": "ep-1",
            "benchmark_identity": {
                "dataset_sha256": "caller-claim",
                "rubric_version": "caller-rubric",
                "task_scope": {"task_policy": "caller-scope"},
            },
            "dataset_hash": "caller-claim",
            "workload_scope": "caller-scope",
            "serving_routes": [{"provider": "caller", "model": "caller"}],
        },
        {
            "kind": "agent_execution", "id": "exec-1",
            "serving_routes": [{"provider": "caller", "model": "caller"}],
        },
    ]
    action_id = _request(world, refs=caller_refs)
    with world.Session() as db:
        params = dict(db.get(HITLAction, action_id).params)
        binding = params["binding"]
        assert params["binding_schema"] == QUALIFICATION_BINDING_SCHEMA
        assert binding["benchmark_identity"] == {
            "dataset_sha256": DATASET_SHA,
            "rubric_version": "heldout-v1",
            "workload_scope": SCOPE,
        }
        assert binding["serving_routes"] == [
            {"provider": "openai", "model": "gpt-5.4-2026-03"}]
        assert binding["repeat_task_comparable"] is True

    receipt_id = _approve_and_write(world, action_id)
    assert receipt_id
    receipt = _receipt(world)
    metadata = dict(receipt.metadata_json)
    assert metadata["binding_schema"] == QUALIFICATION_BINDING_SCHEMA
    assert metadata["benchmark_identity"] == {
        "dataset_sha256": DATASET_SHA,
        "rubric_version": "heldout-v1",
        "workload_scope": SCOPE,
    }
    assert metadata["serving_routes"] == [
        {"provider": "openai", "model": "gpt-5.4-2026-03"}]
    assert metadata["repeat_task_comparable"] is True
    # No caller claim was copied anywhere into the durable binding.
    assert "caller-claim" not in json.dumps(metadata, sort_keys=True)

    # Durable restart readback: same binding, still valid.
    world.reopen()
    result = _read(world)
    assert result["ok"] is True, result
    assert result["repeat_task_comparable"] is True
    assert result["binding"]["serving_routes"] == [
        {"provider": "openai", "model": "gpt-5.4-2026-03"}]


def test_receipt_revalidation_tracks_evidence_and_receipt_binding(world):
    _approve_and_write(world, _request(world))
    assert _read(world)["ok"] is True

    # Evidence benchmark identity change invalidates the v2 source revision.
    with world.Session() as db:
        episode = db.get(AgentEpisode, "ep-1")
        original = json.loads(json.dumps(episode.metadata_json))
        original_updated_at = episode.updated_at
        episode.metadata_json["benchmark_identity"]["rubric_version"] = "heldout-v2"
        flag_modified(episode, "metadata_json")
        db.commit()
    assert _read(world)["state"] == "unresolved_stale"
    with world.Session() as db:
        episode = db.get(AgentEpisode, "ep-1")
        episode.metadata_json = original
        episode.updated_at = original_updated_at
        db.commit()
    assert _read(world)["ok"] is True

    # Evidence serving route change also invalidates it.
    with world.Session() as db:
        execution = db.get(AgentExecution, "exec-1")
        original = json.loads(json.dumps(execution.metadata_json))
        execution.metadata_json["model_provenance"] = _provenance(
            "other", "other-model")
        flag_modified(execution, "metadata_json")
        db.commit()
    assert _read(world)["state"] == "unresolved_stale"
    with world.Session() as db:
        execution = db.get(AgentExecution, "exec-1")
        execution.metadata_json = original
        db.commit()
    assert _read(world)["ok"] is True

    # Evidence moved out of scope is a scope failure, not a stale claim.
    with world.Session() as db:
        execution = db.get(AgentExecution, "exec-1")
        original = (execution.tenant_id, execution.workspace_id)
        execution.tenant_id = "foreign-tenant"
        execution.workspace_id = "foreign-workspace"
        db.commit()
    assert _read(world)["state"] == "unresolved_scope"
    with world.Session() as db:
        execution = db.get(AgentExecution, "exec-1")
        execution.tenant_id, execution.workspace_id = original
        db.commit()
    assert _read(world)["ok"] is True

    # Receipt-side binding tampering is detected.
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        receipt = db.get(GraduationExam, agent.last_exam_id)
        original = json.loads(json.dumps(receipt.metadata_json))
        receipt.metadata_json["binding"]["serving_routes"] = [
            {"provider": "tampered", "model": "tampered"}]
        flag_modified(receipt, "metadata_json")
        db.commit()
    assert _read(world)["state"] == "unresolved_stale"
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        receipt = db.get(GraduationExam, agent.last_exam_id)
        receipt.metadata_json = original
        db.commit()
    assert _read(world)["ok"] is True


def test_unbound_new_receipt_promotes_but_has_no_repeat_baseline(tmp_path):
    world = World(tmp_path, with_binding=False)
    caller_refs = [
        {
            "kind": "agent_episode", "id": "ep-1",
            "benchmark_identity": _benchmark_identity(),
            "serving_routes": [{"provider": "caller", "model": "caller"}],
        },
        {"kind": "agent_execution", "id": "exec-1"},
    ]
    _approve_and_write(world, _request(world, refs=caller_refs))
    result = _read(world)
    assert result["ok"] is True, result
    assert result["binding_schema"] == QUALIFICATION_BINDING_SCHEMA
    assert result["binding"]["benchmark_identity"] is None
    assert result["binding"]["serving_routes"] == []
    assert result["binding"]["binding_state"] == "unbound"
    assert result["repeat_task_comparable"] is False

    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        gate = evaluate_qualification_gate(db, agent, "INTERN")
    assert gate["allowed"] is True
    assert gate["candidate_capability_qualified"] is True
    assert gate["repeat_task_comparable"] is False


def test_distinct_evidence_rows_never_establish_comparability(tmp_path):
    """The handoff regression case: benchmark identity on one evidence row and
    the serving route on another must never make the receipt repeat-task
    comparable. Routes observed without a same-observation complete identity
    are not promoted into the binding; they stay in the normalized evidence
    for audit only, so the binding is empty and unbound."""
    world = World(tmp_path, with_binding=False)
    with world.Session() as db:
        episode = db.get(AgentEpisode, "ep-1")
        episode.metadata_json = {"benchmark_identity": _benchmark_identity()}
        execution = db.get(AgentExecution, "exec-1")
        execution.metadata_json = {"model_provenance": _provenance()}
        db.commit()
    _approve_and_write(world, _request(world))

    result = _read(world)
    assert result["ok"] is True, result
    assert result["binding"]["benchmark_identity"] == {
        "dataset_sha256": DATASET_SHA,
        "rubric_version": "heldout-v1",
        "workload_scope": SCOPE,
    }
    assert result["binding"]["serving_routes"] == []
    assert result["binding"]["binding_state"] == "unbound"
    assert result["repeat_task_comparable"] is False

    # Promotion is unaffected; only the repeat-task baseline is withheld.
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        gate = evaluate_qualification_gate(db, agent, "INTERN")
    assert gate["allowed"] is True
    assert gate["candidate_capability_qualified"] is True
    assert gate["repeat_task_comparable"] is False


def test_routes_bind_only_with_same_observation_identity(tmp_path):
    """A mixed case: one observation carries a complete benchmark identity
    together with its actual served route (valid, comparable), while an
    unrelated observation carries a route with no identity. Only the route
    bound to the identified observation enters the binding; the unrelated
    route stays out of the durable binding."""
    world = World(tmp_path, with_binding=False)
    with world.Session() as db:
        # Identified observation: complete identity + served route together.
        episode = db.get(AgentEpisode, "ep-1")
        episode.metadata_json = {
            "benchmark_identity": _benchmark_identity(),
            "model_provenance": _provenance(),
        }
        # Unrelated observation: route only, no benchmark identity.
        execution = db.get(AgentExecution, "exec-1")
        execution.metadata_json = {"model_provenance": _provenance(
            "unrelated", "unrelated-model")}
        db.commit()
    _approve_and_write(world, _request(world))

    result = _read(world)
    assert result["ok"] is True, result
    assert result["binding"]["benchmark_identity"] == {
        "dataset_sha256": DATASET_SHA,
        "rubric_version": "heldout-v1",
        "workload_scope": SCOPE,
    }
    assert result["binding"]["serving_routes"] == [
        {"provider": "openai", "model": "gpt-5.4-2026-03"}]
    assert result["binding"]["binding_state"] == "bound"
    assert result["repeat_task_comparable"] is True
    # The unrelated route was never promoted into the durable binding.
    assert "unrelated" not in json.dumps(
        result["binding"], sort_keys=True)


def test_partial_benchmark_identity_is_not_completed_or_comparable(tmp_path):
    world = World(tmp_path, with_binding=False)
    with world.Session() as db:
        episode = db.get(AgentEpisode, "ep-1")
        episode.metadata_json = {
            "benchmark_identity": {"dataset_sha256": DATASET_SHA}
        }
        execution = db.get(AgentExecution, "exec-1")
        execution.metadata_json = {"model_provenance": _provenance()}
        db.commit()
    _approve_and_write(world, _request(world))
    result = _read(world)
    assert result["ok"] is True, result
    assert result["binding"]["benchmark_identity"] is None
    assert result["repeat_task_comparable"] is False
    # Missing rubric/workload values were not invented.
    assert "rubric_version" not in json.dumps(result["binding"])
    assert "workload_scope" not in json.dumps(result["binding"])


def test_legacy_receipt_keeps_existing_promotion_semantics(world):
    action_id = _request(world)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        action = db.get(HITLAction, action_id)
        params = dict(action.params)
        ok, _normalized, legacy_source_revision, error = (
            validate_qualification_evidence(
                db, agent, params["evidence_refs"],
                tenant_id=TENANT, workspace_id=WORKSPACE,
                rubric_version="heldout-v1",
                include_binding=False,
            ))
        assert ok, error
        for key in (
            "binding_schema", "binding", "benchmark_identity",
            "serving_routes", "repeat_task_comparable", "binding_state",
        ):
            params.pop(key, None)
        params["source_revision"] = legacy_source_revision
        action.params = params
        flag_modified(action, "params")
        db.commit()

    receipt_id = _approve_and_write(world, action_id)
    assert receipt_id
    receipt = _receipt(world)
    assert "binding_schema" not in (receipt.metadata_json or {})

    result = _read(world)
    assert result["ok"] is True, result
    assert result["binding"] is None
    assert result["binding_state"] == "legacy_unbound"
    assert result["repeat_task_comparable"] is False

    # Legacy source revision never included benchmark/route metadata, so a
    # later evidence-attribution change does not retroactively invalidate the
    # receipt. New receipts are covered by the separate v2 test above.
    with world.Session() as db:
        execution = db.get(AgentExecution, "exec-1")
        execution.metadata_json = {"model_provenance": _provenance(
            "other", "other-model")}
        flag_modified(execution, "metadata_json")
        db.commit()
    assert _read(world)["ok"] is True


def _promote_to_intern(world):
    with world.Session() as db:
        result = commit_qualified_transition(
            db,
            agent_id=AGENT,
            target_level="INTERN",
            actor_id=SUPERVISOR,
            readiness={"ready": True, "score": 0.88, "gaps": []},
            source="focused-post-promotion-test",
            operation_id="post-promotion-baseline",
        )
    assert result["status"] == "verified", result
    return result


def test_post_promotion_baseline_after_actual_promotion_and_restart(world):
    receipt_id = _approve_and_write(world, _request(world))
    promoted = _promote_to_intern(world)
    history_id = promoted["data"]["promotion_history_id"]

    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        history = db.query(PromotionHistory).filter(
            PromotionHistory.agent_id == AGENT).one()
        assert agent.status == "intern"
        assert history.id == history_id
        assert history.exam_id == receipt_id == agent.last_exam_id
        assert (history.from_level, history.to_level) == ("student", "intern")

        # The pre-transition authorization read is unchanged: the receipt
        # that authorized STUDENT -> INTERN is no longer current-tier valid.
        refused = find_qualification_receipt(
            db, agent, "INTERN", get_assessment_policy(db))
        assert refused["ok"] is False
        assert refused["state"] == "unresolved_stale"
        assert evaluate_qualification_gate(
            db, agent, "SUPERVISED")["allowed"] is False

    # Fresh engine/session on the durable file, then resolve the baseline the
    # committed transition established.
    world.reopen()
    with world.Session() as db:
        baseline = resolve_runtime_qualification_baseline(
            db, db.get(AgentRegistry, AGENT))

    assert baseline["ok"] is True, baseline
    assert baseline["state"] == "valid"
    assert baseline["promotion_id"] == history_id
    assert baseline["source_level"] == "student"
    assert baseline["target_level"] == "intern"
    assert baseline["receipt_id"] == receipt_id
    assert baseline["repeat_task_comparable"] is True
    assert baseline["binding_state"] == "bound"
    assert baseline["serving_routes"] == [
        {"provider": "openai", "model": "gpt-5.4-2026-03"}]
    assert baseline["benchmark_identity"] == {
        "dataset_sha256": DATASET_SHA,
        "rubric_version": "heldout-v1",
        "workload_scope": SCOPE,
    }


def test_post_promotion_baseline_fails_closed_on_scope_stale_and_transition(world):
    _approve_and_write(world, _request(world))
    _promote_to_intern(world)
    world.reopen()

    def baseline():
        with world.Session() as db:
            return resolve_runtime_qualification_baseline(
                db, db.get(AgentRegistry, AGENT))

    assert baseline()["ok"] is True

    # Evidence moved outside the agent's current scope is not reusable even
    # though the committed transition and receipt still exist.
    with world.Session() as db:
        execution = db.get(AgentExecution, "exec-1")
        original_scope = (execution.tenant_id, execution.workspace_id)
        execution.tenant_id = "foreign-tenant"
        execution.workspace_id = "foreign-workspace"
        db.commit()
    result = baseline()
    assert result["ok"] is False
    assert result["state"] == "unresolved_scope"
    with world.Session() as db:
        execution = db.get(AgentExecution, "exec-1")
        execution.tenant_id, execution.workspace_id = original_scope
        db.commit()
    world.reopen()
    assert baseline()["ok"] is True

    # Evidence changed after the receipt is stale, not a new baseline.
    with world.Session() as db:
        episode = db.get(AgentEpisode, "ep-1")
        original_task = episode.task_description
        original_updated_at = episode.updated_at
        episode.task_description = "changed after the committed promotion"
        db.commit()
    result = baseline()
    assert result["ok"] is False
    assert result["state"] == "unresolved_stale"
    with world.Session() as db:
        episode = db.get(AgentEpisode, "ep-1")
        episode.task_description = original_task
        episode.updated_at = original_updated_at
        db.commit()
    world.reopen()
    assert baseline()["ok"] is True

    # A promotion row that does not bind the protected receipt pointer cannot
    # become the runtime baseline.
    with world.Session() as db:
        history = db.query(PromotionHistory).filter(
            PromotionHistory.agent_id == AGENT).one()
        original_exam_id = history.exam_id
        history.exam_id = None
        db.commit()
    result = baseline()
    assert result["ok"] is False
    assert result["state"] == "unresolved_stale"

    # Removing the committed transition removes the baseline entirely.
    with world.Session() as db:
        history = db.query(PromotionHistory).filter(
            PromotionHistory.agent_id == AGENT).one()
        history.exam_id = original_exam_id
        db.delete(history)
        db.commit()
    result = baseline()
    assert result["ok"] is False
    assert result["state"] == "unresolved_missing"


def test_newer_nonmatching_transition_supersedes_older_matching_receipt(world):
    """The newest committed transition into the current tier is authoritative.

    A newer promotion that binds a different receipt, or that is not an
    adjacent-tier transition (an owner exception), must fail the runtime
    baseline closed. It must never fall back to an older matching receipt.
    """
    receipt_id = _approve_and_write(world, _request(world))
    promoted = _promote_to_intern(world)
    established_id = promoted["data"]["promotion_history_id"]
    world.reopen()

    def baseline():
        with world.Session() as db:
            return resolve_runtime_qualification_baseline(
                db, db.get(AgentRegistry, AGENT))

    assert baseline()["promotion_id"] == established_id

    with world.Session() as db:
        established = db.get(PromotionHistory, established_id)
        assert established.exam_id == receipt_id
        promoted_at = established.promoted_at

    # A newer committed transition into INTERN bound to a different receipt
    # supersedes the older row that binds the protected pointer.
    with world.Session() as db:
        db.add(PromotionHistory(
            id="later-different-receipt",
            agent_id=AGENT,
            tenant_id=TENANT,
            from_level="student",
            to_level="intern",
            promotion_type="manual",
            readiness_score=0.9,
            exam_id="other-receipt",
            promoted_by=SUPERVISOR,
            justification="later decision with another receipt",
            promoted_at=promoted_at + timedelta(minutes=5),
        ))
        db.commit()
    result = baseline()
    assert result["ok"] is False
    assert result["state"] == "unresolved_stale"
    assert result.get("promotion_id") is None

    # A newer non-adjacent transition carrying the same receipt pointer (an
    # owner exception recorded without an adjacent source tier) supersedes it
    # too: the older matching receipt cannot survive it.
    with world.Session() as db:
        db.delete(db.get(PromotionHistory, "later-different-receipt"))
        db.add(PromotionHistory(
            id="later-non-adjacent",
            agent_id=AGENT,
            tenant_id=TENANT,
            from_level="",
            to_level="intern",
            promotion_type="manual",
            readiness_score=0.9,
            exam_id=receipt_id,
            promoted_by=SUPERVISOR,
            justification="later owner exception",
            promoted_at=promoted_at + timedelta(minutes=5),
        ))
        db.commit()
    result = baseline()
    assert result["ok"] is False
    assert result["state"] == "unresolved_stale"

    # Removing the superseding decision restores the committed baseline.
    with world.Session() as db:
        db.delete(db.get(PromotionHistory, "later-non-adjacent"))
        db.commit()
    world.reopen()
    restored = baseline()
    assert restored["ok"] is True, restored
    assert restored["promotion_id"] == established_id
    assert restored["receipt_id"] == receipt_id
