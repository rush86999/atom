"""G1: scored campaign evidence binds through the normal review path.

The campaign producer (``core.employee_benchmark_evidence``) writes a
digest-sealed record under the reserved ``benchmark_evidence`` metadata key of
the run's ``AgentExecution``. This file proves, end to end and against a
scratch SQLite world, that such a record is:

* discoverable by the normal scoped qualification-evidence bundle enumerator;
* bound into the real review request, approval and qualification receipt;
* the runtime baseline of the committed promotion; and
* the route evidence the repeat-task resolver selects from.

Every record used here is produced by the ACTUAL writer from a sealed
campaign transport journal and the frozen in-repo benchmark registry, with
fake accepted transport outcomes. No provider SDK, model call, network or live
database is involved. Negatives cover missing/tampered/wrong-execution/forged
records, conflicts, cross-agent scope, stale evidence and build ambiguity.
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

import core.agent_graduation_service as grad
import core.employee_benchmark_evidence as bench_evidence
from core.agent_graduation_service import (
    QUALIFICATION_BINDING_SCHEMA,
    QualificationReviewError,
    commit_qualified_transition,
    list_qualification_evidence_bundles,
    request_qualification_review,
    resolve_runtime_qualification_baseline,
    validate_qualification_evidence,
    validate_qualification_review_binding,
    write_qualification_receipt_from_review,
)
from core.database import Base
from core.llm.graduation_route import (
    STATE_PINNED,
    STATE_SUPERVISED,
    resolve_repeat_task_route,
)
from core.models import (
    AgentExecution,
    AgentRegistry,
    GraduationExam,
    HITLAction,
    HITLActionStatus,
    Tenant,
    User,
    Workspace,
)
from core.promotion_policy_service import (
    ASSESSMENT_POLICY_KEY,
    DEFAULT_ASSESSMENT_POLICY,
)

grad.get_lancedb_handler = lambda: None
grad.POMDP_AVAILABLE = False

TENANT = "campaign-binding-tenant"
WORKSPACE = "campaign-binding-workspace"
SUPERVISOR = "campaign-supervisor"
ADMIN = "campaign-admin"
AGENT = "campaign-agent"
OTHER_AGENT = "campaign-other-agent"

_BENCHMARK_REGISTRY_PATH = bench_evidence.benchmark_registry_path()
_FROZEN_BENCHMARK, _FROZEN_REGISTRY, _FROZEN_REASONS = (
    bench_evidence._prepare_benchmark(None))
assert _FROZEN_BENCHMARK is not None, _FROZEN_REASONS
BENCHMARK_ID = _FROZEN_BENCHMARK["benchmark_id"]
DATASET_SHA = _FROZEN_BENCHMARK["dataset_sha256"]
RUBRIC = _FROZEN_BENCHMARK["rubric_version"]
SCOPE = dict(_FROZEN_BENCHMARK["task_scope"])
BASELINE = ("openai", "gpt-5.4-2026-03")
CANDIDATE = ("openai", "gpt-5.5-mini")
CANDIDATE_BUILD = "gpt-5.5-mini-2026-01"


def _heldout_observation(*, failed_case: str | None = None) -> dict:
    """Observed held-out outputs; the writer computes the verdict."""
    cases = {
        "heldout-quote": {
            "assignment_status": "completed",
            "steps": {"calculate": {"value": "96.30", "currency": "USD"}},
            "deliverables": {"document": {
                "status": "applied",
                "text": (
                    "Approved quote total USD 96.30 from the authorized "
                    "price rows under the taught terms."),
            }},
            "external_effects": 0,
        },
        "heldout-reconcile": {
            "assignment_status": "completed",
            "steps": {"reconcile": {"value": "140.25", "currency": "USD"}},
            "deliverables": {"document": {
                "status": "applied",
                "text": (
                    "Reconciled invoice total USD 140.25 against the "
                    "purchase order and receiving records."),
            }},
            "external_effects": 0,
        },
    }
    if failed_case == "quote":
        cases["heldout-quote"]["steps"]["calculate"]["value"] = "41.00"
        cases["heldout-quote"]["deliverables"]["document"]["text"] = (
            "Quote total unavailable.")
    return {
        "run": {"restart": {"same_wait": True}},
        "external_effects": 0,
        "cases": cases,
    }


def _matching_assignment() -> dict:
    return {
        "assignment_id": "asg-campaign-binding",
        "objective": "repeat the held-out workload",
        "workload_scope": dict(SCOPE),
    }


@pytest.fixture(autouse=True)
def _pinned_server_config(monkeypatch):
    monkeypatch.setenv(
        "ATOM_EMPLOYEE_BENCHMARK_FILE", str(_BENCHMARK_REGISTRY_PATH))
    # Same production policy schema and digest checks; the rubric is aligned
    # with the frozen benchmark so the review and the measured identity
    # describe the same held-out assessment.
    policy = dict(DEFAULT_ASSESSMENT_POLICY)
    policy["rubric_version"] = RUBRIC
    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
    monkeypatch.delenv("ATOM_EMPLOYEE_PROVIDER_MODEL", raising=False)


class World:
    """Scratch SQLite world with real campaign-produced evidence."""

    def __init__(self, tmp_path):
        self.db_path = tmp_path / "campaign-binding.db"
        self._connect()
        self.now = datetime.now(timezone.utc)
        with self.Session() as db:
            db.add(Tenant(
                id=TENANT, name="Campaign Binding",
                subdomain=f"cb-{uuid.uuid4().hex[:8]}", edition="personal",
                is_active=True,
            ))
            db.add(Workspace(id=WORKSPACE, name="Campaign", tenant_id=TENANT))
            db.add_all([
                User(
                    id=SUPERVISOR, tenant_id=TENANT, workspace_id=WORKSPACE,
                    email="sup@campaign.test", first_name="S", last_name="V",
                    role="team_lead", status="active", is_active=True,
                ),
                User(
                    id=ADMIN, tenant_id=TENANT, workspace_id=WORKSPACE,
                    email="admin@campaign.test", first_name="A", last_name="V",
                    role="admin", status="active", is_active=True,
                ),
            ])
            for agent_id, name in (
                    (AGENT, "Campaign Candidate"),
                    (OTHER_AGENT, "Campaign Peer")):
                db.add(AgentRegistry(
                    id=agent_id, name=name, category="operations",
                    role="agent", type="personal", capabilities=[],
                    module_path="core.generic_agent",
                    class_name="GenericAgent",
                    user_id=SUPERVISOR, workspace_id=WORKSPACE,
                    tenant_id=TENANT, status="student", enabled=True,
                    confidence_score=0.62,
                    configuration={
                        "learning": {"role": "operations", "log": []}},
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
        self.engine.dispose()
        self._connect()

    # --- writer -----------------------------------------------------------

    def campaign(
        self,
        execution_id: str,
        provider: str,
        model: str,
        *,
        observed_at: datetime,
        echo_model: str | None = None,
        agent_id: str = AGENT,
        result_summary: str | None = None,
        registry: dict | None = None,
        failed_case: str | None = None,
    ) -> dict:
        """Run the ACTUAL producer for one fake accepted campaign call.

        The durable row is left exactly as the campaign intake leaves it (an
        unscored completed execution with its own scope and completion time);
        the campaign's sealed transport journal records the accepted route and
        provider echo; the producer computes the verdict from the frozen
        checks and appends the digest-sealed record.
        """
        route = {"provider": provider, "model": model}
        build = echo_model or model
        with self.Session() as db:
            db.add(AgentExecution(
                id=execution_id, agent_id=agent_id, tenant_id=TENANT,
                workspace_id=WORKSPACE, status="completed",
                input_summary="held-out benchmark campaign",
                result_summary=result_summary,
                output_summary="completed",
                completed_at=observed_at,
                metadata_json={"model_provenance": {
                    "provider": provider,
                    "model": model,
                    "source": "route_attribution",
                    "serving_models": [dict(route)],
                }},
            ))
            db.commit()
        journal = bench_evidence.open_campaign_transport_journal(
            campaign_id=f"heldout-{execution_id}",
            execution_id=execution_id,
        )
        journal.record_call(
            accepted=True,
            requested_route=dict(route),
            served_route=dict(route),
            response_identity={"provider": provider, "model": build},
        )
        journal.seal(completed_at=observed_at)
        return bench_evidence.produce_employee_benchmark_evidence(
            execution_id=execution_id,
            observation=_heldout_observation(failed_case=failed_case),
            transport_journal=journal,
            registry=registry,
            session_factory=self.Session,
        )

    def baseline(self, execution_id: str = "exec-baseline", **kwargs) -> dict:
        result = self.campaign(
            execution_id, *BASELINE,
            observed_at=self.now - timedelta(days=2), **kwargs)
        assert result["status"] == "recorded", result
        return result

    def candidate(self, execution_id: str = "exec-candidate", **kwargs) -> dict:
        result = self.campaign(
            execution_id, *CANDIDATE,
            observed_at=self.now - timedelta(days=1), **kwargs)
        assert result["status"] == "recorded", result
        return result

    # --- review chain -----------------------------------------------------

    def bundles(self, *, agent_id: str = AGENT, limit: int = 10) -> dict:
        with self.Session() as db:
            agent = db.get(AgentRegistry, agent_id)
            return list_qualification_evidence_bundles(
                db, agent, "INTERN", TENANT, WORKSPACE, limit=limit)

    def request(self, refs, *, agent_id: str = AGENT) -> str:
        with self.Session() as db:
            agent = db.get(AgentRegistry, agent_id)
            result = request_qualification_review(
                db,
                agent=agent,
                target_level="INTERN",
                evidence_refs=refs,
                rubric_version=RUBRIC,
                requested_by=SUPERVISOR,
                tenant_id=TENANT,
                workspace_id=WORKSPACE,
            )
            return result["action_id"]

    def approve_and_write(self, action_id: str) -> str:
        with self.Session() as db:
            action = db.get(HITLAction, action_id)
            assert validate_qualification_review_binding(db, action)["valid"]
            action.status = HITLActionStatus.APPROVED.value
            action.reviewed_by = ADMIN
            action.reviewed_at = datetime.now(timezone.utc)
            db.commit()
        with self.Session() as db:
            written = write_qualification_receipt_from_review(
                db, action_id=action_id, approved=True, reviewer_id=ADMIN,
            )
            assert written["state"] == "valid", written
            return written["receipt_id"]

    def promote(self, operation_id: str = "campaign-binding-promotion") -> str:
        with self.Session() as db:
            result = commit_qualified_transition(
                db,
                agent_id=AGENT,
                target_level="INTERN",
                actor_id=SUPERVISOR,
                readiness={"ready": True, "score": 0.88, "gaps": []},
                source="campaign-binding-test",
                operation_id=operation_id,
            )
            assert result["status"] == "verified", result
            return result["data"]["promotion_history_id"]

    def qualified_agent(self, refs) -> str:
        """Review -> real receipt -> committed STUDENT -> INTERN transition."""
        receipt_id = self.approve_and_write(self.request(refs))
        self.promote()
        return receipt_id

    # --- durable reads ----------------------------------------------------

    def receipt(self, receipt_id: str) -> dict:
        with self.Session() as db:
            return dict(db.get(GraduationExam, receipt_id).metadata_json or {})

    def baseline_resolution(self) -> dict:
        with self.Session() as db:
            return resolve_runtime_qualification_baseline(
                db, db.get(AgentRegistry, AGENT))

    def resolve(self, *, candidates=None, now: datetime | None = None) -> dict:
        with self.Session() as db:
            return resolve_repeat_task_route(
                db,
                db.get(AgentRegistry, AGENT),
                assignment=_matching_assignment(),
                candidates=candidates,
                now=now or self.now,
            )

    def close(self):
        self.engine.dispose()


@pytest.fixture
def world(tmp_path):
    built = World(tmp_path)
    try:
        yield built
    finally:
        built.close()


# --- Positive path ----------------------------------------------------------


def test_campaign_evidence_is_discoverable_and_binds_end_to_end(world):
    produced = world.baseline()
    assert produced["passed"] is True

    # 1. Normal scoped discovery: the campaign execution is offered as a
    #    reviewable bundle with the producer's measured identity, not a
    #    hand-written metadata claim.
    bundles = world.bundles()
    assert len(bundles["items"]) == 1, bundles["items"]
    item = bundles["items"][0]
    assert item["bundle_id"] == "bundle:execution:exec-baseline"
    assert item["execution_id"] == "exec-baseline"
    assert item["episode_id"] is None
    assert item["task_preview"] == "held-out benchmark campaign"
    assert item["output_preview"] == "completed"
    assert item["evidence_refs"] == [
        {"kind": "agent_execution", "id": "exec-baseline"}]
    assert item["binding"]["binding_state"] == "bound"
    assert item["binding"]["benchmark_identity"] == {
        "dataset_sha256": DATASET_SHA,
        "rubric_version": RUBRIC,
        "workload_scope": SCOPE,
    }
    assert item["binding"]["serving_routes"] == [
        {"provider": BASELINE[0], "model": BASELINE[1]}]
    assert item["repeat_task_comparable"] is True

    # 2. Real review request, approval and receipt from the discovered refs.
    receipt_id = world.approve_and_write(world.request(item["evidence_refs"]))
    metadata = world.receipt(receipt_id)
    assert metadata["receipt_kind"] == "capability_qualification"
    assert metadata["state"] == "valid"
    assert metadata["binding_schema"] == QUALIFICATION_BINDING_SCHEMA
    assert metadata["binding_state"] == "bound"
    assert metadata["repeat_task_comparable"] is True
    assert metadata["benchmark_identity"] == {
        "dataset_sha256": DATASET_SHA,
        "rubric_version": RUBRIC,
        "workload_scope": SCOPE,
    }
    assert metadata["serving_routes"] == [
        {"provider": BASELINE[0], "model": BASELINE[1]}]

    # 3. Real promotion, then the current runtime baseline.
    world.promote()
    baseline = world.baseline_resolution()
    assert baseline["ok"] is True, baseline
    assert baseline["state"] == "valid"
    assert baseline["repeat_task_comparable"] is True
    assert baseline["benchmark_identity"] == {
        "dataset_sha256": DATASET_SHA,
        "rubric_version": RUBRIC,
        "workload_scope": SCOPE,
    }

    # 4. A fresh passing candidate on the same cohort/scope is pinned.
    world.candidate(echo_model=CANDIDATE_BUILD)
    decision = world.resolve(candidates=[CANDIDATE])
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    assert decision["baseline_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}
    assert decision["selected_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    assert decision["selected_build"] == CANDIDATE_BUILD
    assert decision["comparison"]["baseline"]["state"] == "established"


# --- Negatives --------------------------------------------------------------


def test_missing_producer_record_is_unbound_and_supervised(world):
    """Writer-only wiring alone must not produce a comparable baseline.

    This is the G1 counter: the execution is completed reviewable work, but
    without a producer record the reader has no measured identity. A bare
    ``benchmark_identity`` plus a route claim cannot manufacture one.
    """
    with world.Session() as db:
        db.add(AgentExecution(
            id="exec-claim-only", agent_id=AGENT, tenant_id=TENANT,
            workspace_id=WORKSPACE, status="completed",
            input_summary="held-out benchmark campaign",
            output_summary="completed",
            completed_at=world.now - timedelta(days=2),
            metadata_json={
                "benchmark_identity": {
                    "dataset_sha256": DATASET_SHA,
                    "rubric_version": RUBRIC,
                    "task_scope": dict(SCOPE),
                },
                "model_provenance": {
                    "provider": BASELINE[0], "model": BASELINE[1],
                    "serving_models": [{
                        "provider": BASELINE[0], "model": BASELINE[1]}],
                },
            },
        ))
        db.commit()

    # Not discoverable as authoritative evidence.
    assert world.bundles()["items"] == []

    # An operator who knows the id may still submit it, but the receipt is
    # unbound: promotion is allowed, repeat-task comparability is not.
    receipt_id = world.approve_and_write(world.request([
        {"kind": "agent_execution", "id": "exec-claim-only"}]))
    metadata = world.receipt(receipt_id)
    assert metadata["binding_state"] == "unbound"
    assert metadata["repeat_task_comparable"] is False
    assert metadata["benchmark_identity"] is None
    assert metadata["serving_routes"] == []

    world.promote()
    baseline = world.baseline_resolution()
    assert baseline["ok"] is True, baseline
    assert baseline["repeat_task_comparable"] is False
    decision = world.resolve()
    assert decision["route_state"] == STATE_SUPERVISED
    assert "receipt_binding_not_comparable" in decision["reasons"]
    assert decision["selected_route"] is None


def test_tampered_and_wrong_execution_records_never_bind(world):
    world.baseline("exec-source")
    with world.Session() as db:
        source = db.get(AgentExecution, "exec-source")
        records = json.loads(json.dumps(
            source.metadata_json["benchmark_evidence"]))
    assert len(records) == 1
    source_record = records[0]

    # A digest-valid record copied to another durable execution belongs to the
    # execution it names, never to the row it was pasted on.
    with world.Session() as db:
        db.add(AgentExecution(
            id="exec-wrong-row", agent_id=AGENT, tenant_id=TENANT,
            workspace_id=WORKSPACE, status="completed",
            input_summary="held-out benchmark campaign",
            output_summary="completed",
            completed_at=world.now - timedelta(days=2),
            metadata_json={"benchmark_evidence": [dict(source_record)]},
        ))
        # Tampering the sealed verdict keeps the JSON shape but breaks the
        # digest; it must be rejected, not re-interpreted.
        tampered = json.loads(json.dumps(source_record))
        tampered["accuracy"] = 0.01
        tampered["passed"] = False
        db.add(AgentExecution(
            id="exec-tampered", agent_id=AGENT, tenant_id=TENANT,
            workspace_id=WORKSPACE, status="completed",
            input_summary="held-out benchmark campaign",
            output_summary="completed",
            completed_at=world.now - timedelta(days=2),
            metadata_json={"benchmark_evidence": [tampered]},
        ))
        db.commit()

    assert {
        item["execution_id"] for item in world.bundles()["items"]} == {
            "exec-source"}

    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        wrong_ok, wrong_normalized, _, _ = validate_qualification_evidence(
            db, agent,
            [{"kind": "agent_execution", "id": "exec-wrong-row"}],
            tenant_id=TENANT, workspace_id=WORKSPACE,
            rubric_version=RUBRIC, include_binding=True,
        )
        assert wrong_ok
        wrong_binding = grad.qualification_binding_from_normalized(
            wrong_normalized)
        assert wrong_binding["binding_state"] == "unbound"
        assert wrong_binding["benchmark_identity"] is None
        tampered_ok, tampered_normalized, _, _ = (
            validate_qualification_evidence(
                db, agent,
                [{"kind": "agent_execution", "id": "exec-tampered"}],
                tenant_id=TENANT, workspace_id=WORKSPACE,
                rubric_version=RUBRIC, include_binding=True,
            ))
        assert tampered_ok
        tampered_binding = grad.qualification_binding_from_normalized(
            tampered_normalized)
        assert tampered_binding["binding_state"] == "unbound"

    receipt_id = world.approve_and_write(world.request([
        {"kind": "agent_execution", "id": "exec-wrong-row"},
        {"kind": "agent_execution", "id": "exec-tampered"},
    ]))
    assert world.receipt(receipt_id)["repeat_task_comparable"] is False
    world.promote()
    decision = world.resolve()
    assert decision["route_state"] == STATE_SUPERVISED
    assert "receipt_binding_not_comparable" in decision["reasons"]


def test_cross_agent_evidence_is_out_of_scope(world):
    other = world.campaign(
        "exec-other-agent", *BASELINE,
        observed_at=world.now - timedelta(days=2), agent_id=OTHER_AGENT)
    assert other["status"] == "recorded", other

    assert world.bundles(agent_id=OTHER_AGENT)["items"]
    assert world.bundles(agent_id=AGENT)["items"] == []

    with pytest.raises(QualificationReviewError) as excinfo:
        world.request([{"kind": "agent_execution", "id": "exec-other-agent"}])
    assert excinfo.value.state == "unresolved_scope"

    # Copying the peer's valid record onto this agent's execution does not
    # transfer the peer's measured identity either: the record names the
    # other agent's execution.
    with world.Session() as db:
        peer = db.get(AgentExecution, "exec-other-agent")
        record = json.loads(json.dumps(
            peer.metadata_json["benchmark_evidence"][0]))
        db.add(AgentExecution(
            id="exec-copied", agent_id=AGENT, tenant_id=TENANT,
            workspace_id=WORKSPACE, status="completed",
            input_summary="held-out benchmark campaign",
            output_summary="completed",
            completed_at=world.now - timedelta(days=2),
            metadata_json={"benchmark_evidence": [record]},
        ))
        db.commit()
    assert world.bundles()["items"] == []


def test_conflicting_validated_identities_fail_closed(world, tmp_path):
    """Two real producer identities in one review are a conflict, not a pick."""
    world.baseline("exec-identity-a")

    # A second server-controlled registry pin with the same frozen dataset
    # and scope but a different rubric version. The real producer seals a
    # second valid record under it.
    alt_registry = json.loads(json.dumps(_FROZEN_REGISTRY))
    alt_registry["benchmarks"][0]["rubric_version"] = "employee-heldout-v2"
    alt = world.campaign(
        "exec-identity-b", *BASELINE,
        observed_at=world.now - timedelta(days=2),
        registry=alt_registry)
    assert alt["status"] == "recorded", alt
    assert alt["evidence"]["rubric_version"] == "employee-heldout-v2"

    # Both records still validate under the configured registry (the registry
    # pins dataset/scoring/scope; the record carries its own rubric).
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        ok, normalized, _revision, error = validate_qualification_evidence(
            db, agent,
            [
                {"kind": "agent_execution", "id": "exec-identity-a"},
                {"kind": "agent_execution", "id": "exec-identity-b"},
            ],
            tenant_id=TENANT, workspace_id=WORKSPACE,
            rubric_version=RUBRIC, include_binding=True,
        )
        assert ok, error
        binding = grad.qualification_binding_from_normalized(normalized)
    assert binding["binding_state"] == "conflict"
    assert binding["benchmark_identity"] is None
    assert binding["serving_routes"] == []
    assert binding["repeat_task_comparable"] is False

    receipt_id = world.approve_and_write(world.request([
        {"kind": "agent_execution", "id": "exec-identity-a"},
        {"kind": "agent_execution", "id": "exec-identity-b"},
    ]))
    metadata = world.receipt(receipt_id)
    assert metadata["binding_state"] == "conflict"
    assert metadata["repeat_task_comparable"] is False
    world.promote()
    decision = world.resolve()
    assert decision["route_state"] == STATE_SUPERVISED
    assert "receipt_binding_not_comparable" in decision["reasons"]


def test_stale_candidate_and_baseline_evidence_are_not_pinned(world):
    world.baseline()
    world.qualified_agent([
        {"kind": "agent_execution", "id": "exec-baseline"}])

    # Candidate record exists but is older than the freshness window.
    world.campaign(
        "exec-stale-candidate", *CANDIDATE,
        observed_at=world.now - timedelta(days=45))
    decision = world.resolve(candidates=[CANDIDATE])
    assert decision["route_state"] == STATE_SUPERVISED
    assert "stale_evidence" in decision["reasons"]

    # A fresh candidate would be pinned...
    world.candidate()
    assert world.resolve(candidates=[CANDIDATE])["route_state"] == STATE_PINNED

    # ...until the receipt's own evidence changes after the receipt: the
    # current baseline is stale and the resolver never reaches selection.
    with world.Session() as db:
        row = db.get(AgentExecution, "exec-baseline")
        row.completed_at = world.now - timedelta(days=3)
        db.commit()
    baseline = world.baseline_resolution()
    assert baseline["ok"] is False
    assert baseline["state"] == "unresolved_stale"
    decision = world.resolve(candidates=[CANDIDATE])
    assert decision["route_state"] == STATE_SUPERVISED
    assert "baseline_unresolved_stale" in decision["reasons"]


def test_build_conflict_on_the_candidate_route_blocks_selection(world):
    world.baseline()
    world.qualified_agent([
        {"kind": "agent_execution", "id": "exec-baseline"}])

    # Same callable route, two newest provider builds: ambiguous evidence.
    newer = world.now - timedelta(days=1)
    world.campaign(
        "exec-build-one", *CANDIDATE,
        observed_at=newer,
        echo_model="gpt-5.5-mini-2026-01")
    world.campaign(
        "exec-build-two", *CANDIDATE,
        observed_at=newer,
        echo_model="gpt-5.5-mini-2026-07")

    decision = world.resolve(candidates=[CANDIDATE])
    assert decision["route_state"] == STATE_SUPERVISED
    assert "ambiguous_evidence" in decision["reasons"]
    candidate = next(
        entry for entry in decision["comparison"]["candidates"]
        if (entry["provider"], entry["model"]) == CANDIDATE)
    assert candidate["evidence_state"] == "insufficient"
    assert candidate["reasons"] == ["model_build_conflict"]
