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

import asyncio
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


# --- Producer attribution through the ACTUAL trusted route ------------------


def test_real_assignment_route_agent_attribution_reaches_review(
        world, monkeypatch, tmp_path):
    """Builder -> intake -> producer -> G1 discovery/receipt/baseline.

    The plan targets the ADMIN User and names the distinct AGENT registry row.
    Campaign intake must own the durable execution by AGENT (not the User),
    and the normal review path must then discover, bind and pin it.
    """
    import core.database as dbmod
    from api.assignment_routes import AssignmentStart, start_assignment
    from core.employee_campaign_intake import (
        complete_campaign_execution,
        durable_assignment,
        record_campaign_evidence,
        resolve_campaign_attribution,
        start_campaign_execution,
    )

    source = tmp_path / "attribution-source.json"
    source.write_text(json.dumps({
        "invoice": "INV-4491", "total": "140.25"}))
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_INTERNAL_FIXTURE_ROOT", str(tmp_path))
    # The route's executor resolves its own session factory lazily from
    # core.database; point it at this scratch world (never the live DB).
    monkeypatch.setattr(dbmod, "SessionLocal", world.Session)
    monkeypatch.setattr(dbmod, "engine", world.engine)

    body = AssignmentStart(
        objective="Prepare the attribution evidence document.",
        sources=[{"kind": "document", "path": str(source)}],
        calculation={
            "expression": "2 + 2",
            "bindings": {},
            "units": {},
            "output_unit": "",
        },
        deliverables=[{
            "kind": "document",
            "description": "Attribution evidence document",
        }],
        authorized_actions=["retrieve", "present"],
        agent_id=AGENT,
        employee_id=ADMIN,
    )
    with world.Session() as db:
        actor = db.get(User, ADMIN)
        started = asyncio.run(start_assignment(body, actor, db))
    run_id = started["run_id"]

    plan = durable_assignment(world.db_path, run_id)
    assert plan["employee_id"] == ADMIN
    assert plan["provenance"]["agent_id"] == AGENT
    assert plan["employee_id"] != plan["provenance"]["agent_id"]
    completed_at = plan.get("completed_at")
    assert completed_at, plan

    assignment = {**plan, "run_id": run_id}
    resolution = resolve_campaign_attribution(
        db_path=world.db_path, assignment=assignment, run_id=run_id)
    assert resolution.ok is True, resolution
    assert resolution.agent_id == AGENT
    assert resolution.employee_id == ADMIN
    assert (resolution.tenant_id, resolution.workspace_id) == (
        TENANT, WORKSPACE)

    execution_id = f"employee-campaign-{run_id}"
    assert start_campaign_execution(
        db_path=world.db_path,
        execution_id=execution_id,
        assignment=assignment,
        run_id=run_id,
    ) == execution_id
    assert complete_campaign_execution(
        db_path=world.db_path,
        execution_id=execution_id,
        assignment=assignment,
        completed_at=completed_at,
        served_identity={"provider": BASELINE[0], "model": BASELINE[1]},
        run_id=run_id,
    ) is True

    result = record_campaign_evidence(
        db_path=world.db_path,
        execution_id=execution_id,
        campaign="employee-heldout-two-domain",
        observation=_heldout_observation(),
        completed_at=completed_at,
        decisions=[{
            "kind": "employee_route",
            "accepted": True,
            "attempt_id": "attempt-real-route",
            "requested_route": {
                "provider": BASELINE[0], "model": BASELINE[1]},
            "served_route": {
                "provider": BASELINE[0], "model": BASELINE[1]},
            "response_identity": {
                "provider": BASELINE[0], "model": BASELINE[1]},
        }],
        assignment=assignment,
    )
    assert result["status"] == "recorded", result
    assert result["evidence"]["execution"]["agent_id"] == AGENT
    assert result["evidence"]["execution"]["agent_id"] != ADMIN

    with world.Session() as db:
        row = db.get(AgentExecution, execution_id)
        assert row is not None
        assert row.agent_id == AGENT
        assert row.tenant_id == TENANT
        assert row.workspace_id == WORKSPACE
        assert row.status == "completed"

    bundles = world.bundles()
    item = next(
        entry for entry in bundles["items"]
        if entry["execution_id"] == execution_id)
    assert item["binding"]["binding_state"] == "bound"
    assert item["repeat_task_comparable"] is True
    assert item["binding"]["serving_routes"] == [
        {"provider": BASELINE[0], "model": BASELINE[1]}]

    receipt_id = world.approve_and_write(world.request(item["evidence_refs"]))
    metadata = world.receipt(receipt_id)
    assert metadata["state"] == "valid"
    assert metadata["binding_state"] == "bound"
    assert metadata["repeat_task_comparable"] is True

    world.promote()
    baseline = world.baseline_resolution()
    assert baseline["ok"] is True, baseline
    assert baseline["repeat_task_comparable"] is True
    # The route completed the campaign just now, after the fixture's clock.
    decision = world.resolve(now=world.now + timedelta(days=1))
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]


def _campaign_plan(
    run_id: str = "run-attribution-negative",
    *,
    agent: str = AGENT,
    employee: str = ADMIN,
    tenant: str = TENANT,
    workspace: str = WORKSPACE,
) -> dict:
    return {
        "objective": "held-out attribution campaign",
        "employee_id": employee,
        "provenance": {"agent_id": agent},
        "tenant_id": tenant,
        "workspace_id": workspace,
        "status": "completed",
        "run_id": run_id,
    }


def _accepted_decision(call_id: str = "attempt-attribution") -> dict:
    route = {"provider": BASELINE[0], "model": BASELINE[1]}
    return {
        "kind": "employee_route",
        "accepted": True,
        "attempt_id": call_id,
        "requested_route": dict(route),
        "served_route": dict(route),
        "response_identity": dict(route),
    }


def test_campaign_intake_refuses_unresolvable_agent_before_creating(world):
    from core.employee_campaign_intake import (
        CampaignAttributionError,
        start_campaign_execution,
    )

    cases = [
        ({**_campaign_plan(), "provenance": {}}, "campaign_agent_missing"),
        ({**_campaign_plan(), "provenance": {"agent_id": "not-a-registry-row"}},
         "campaign_agent_not_found"),
        (_campaign_plan(tenant="foreign-tenant"),
         "campaign_agent_tenant_mismatch"),
        (_campaign_plan(workspace="foreign-workspace"),
         "campaign_agent_workspace_mismatch"),
        (_campaign_plan(employee="not-a-user"),
         "campaign_employee_not_found"),
    ]
    for index, (assignment, reason) in enumerate(cases):
        execution_id = f"exec-refused-{index}"
        with pytest.raises(CampaignAttributionError) as raised:
            start_campaign_execution(
                db_path=world.db_path,
                execution_id=execution_id,
                assignment=assignment,
                run_id=assignment["run_id"],
            )
        assert raised.value.reason == reason
        with world.Session() as db:
            assert db.get(AgentExecution, execution_id) is None

    # No run identity is not guessed, and no row is created.
    assignment = _campaign_plan()
    assignment.pop("run_id")
    with pytest.raises(CampaignAttributionError) as raised:
        start_campaign_execution(
            db_path=world.db_path,
            execution_id="exec-refused-run",
            assignment=assignment,
        )
    assert raised.value.reason == "campaign_run_identity_missing"
    with world.Session() as db:
        assert db.get(AgentExecution, "exec-refused-run") is None


def test_shared_system_agent_is_scope_authorized_not_user_paired(world):
    """A NULL-owner shared agent is valid; the employee remains a distinct User."""
    from core.employee_campaign_intake import start_campaign_execution

    shared = "campaign-shared-agent"
    with world.Session() as db:
        db.add(AgentRegistry(
            id=shared, name="Campaign Shared", category="operations",
            role="agent", type="system", capabilities=[],
            module_path="core.generic_agent", class_name="GenericAgent",
            user_id=None, workspace_id=WORKSPACE, tenant_id=TENANT,
            status="student", enabled=True, confidence_score=0.62,
            configuration={},
        ))
        db.commit()

    assignment = _campaign_plan(agent=shared, employee=ADMIN)
    assert start_campaign_execution(
        db_path=world.db_path,
        execution_id="exec-shared-agent",
        assignment=assignment,
        run_id=assignment["run_id"],
    ) == "exec-shared-agent"
    with world.Session() as db:
        row = db.get(AgentExecution, "exec-shared-agent")
        assert row.agent_id == shared
        assert row.agent_id != ADMIN
        assert row.tenant_id == TENANT
        assert row.workspace_id == WORKSPACE


def test_campaign_row_idempotency_foreign_collision_and_immutability(world):
    from core.employee_campaign_intake import (
        CampaignAttributionError,
        complete_campaign_execution,
        record_campaign_evidence,
        start_campaign_execution,
    )

    assignment = _campaign_plan(run_id="run-idempotent")
    execution_id = "exec-idempotent"
    assert start_campaign_execution(
        db_path=world.db_path, execution_id=execution_id,
        assignment=assignment, run_id="run-idempotent") == execution_id
    # Same plan: idempotent reuse, never a second row.
    assert start_campaign_execution(
        db_path=world.db_path, execution_id=execution_id,
        assignment=assignment, run_id="run-idempotent") == execution_id

    other_run = _campaign_plan(run_id="run-different")
    with pytest.raises(CampaignAttributionError) as raised:
        start_campaign_execution(
            db_path=world.db_path, execution_id=execution_id,
            assignment=other_run, run_id="run-different")
    assert raised.value.reason == "campaign_row_identity_mismatch"
    with world.Session() as db:
        row = db.get(AgentExecution, execution_id)
        assert row.status == "running"
        assert row.metadata_json["campaign"] == {
            "id": "employee-heldout-two-domain", "run_id": "run-idempotent"}

    # A caller-chosen id already naming another agent's running row is refused
    # by BOTH create paths and never completed/re-attributed.
    with world.Session() as db:
        db.add(AgentExecution(
            id="exec-foreign-row", agent_id=OTHER_AGENT,
            tenant_id=TENANT, workspace_id=WORKSPACE, status="running",
            metadata_json={"campaign": {
                "id": "employee-heldout-two-domain", "run_id": "run-foreign"}},
        ))
        db.commit()
    with pytest.raises(CampaignAttributionError) as raised:
        start_campaign_execution(
            db_path=world.db_path, execution_id="exec-foreign-row",
            assignment=assignment, run_id="run-idempotent")
    assert raised.value.reason == "campaign_row_attribution_mismatch"
    with pytest.raises(CampaignAttributionError) as raised:
        complete_campaign_execution(
            db_path=world.db_path, execution_id="exec-foreign-row",
            assignment=assignment, completed_at=world.now,
            run_id="run-idempotent")
    assert raised.value.reason == "campaign_row_attribution_mismatch"

    refused = record_campaign_evidence(
        db_path=world.db_path,
        execution_id="exec-foreign-row",
        campaign="employee-heldout-two-domain",
        observation=_heldout_observation(),
        completed_at=world.now,
        decisions=[_accepted_decision()],
        assignment=assignment,
    )
    assert refused["status"] == "rejected"
    assert refused["reason"] == "campaign_row_attribution_mismatch"
    with world.Session() as db:
        row = db.get(AgentExecution, "exec-foreign-row")
        assert row.agent_id == OTHER_AGENT
        assert row.status == "running"
        assert row.completed_at is None
        assert bench_evidence.EVIDENCE_KEY not in (row.metadata_json or {})

    # Completed history is immutable: identical re-completion is a no-op;
    # a different completion time is refused without touching the row.
    first_completed = world.now - timedelta(hours=1)
    assert complete_campaign_execution(
        db_path=world.db_path, execution_id=execution_id,
        assignment=assignment, completed_at=first_completed,
        run_id="run-idempotent") is True
    with world.Session() as db:
        sealed_at = db.get(AgentExecution, execution_id).completed_at
    assert complete_campaign_execution(
        db_path=world.db_path, execution_id=execution_id,
        assignment=assignment, completed_at=first_completed,
        run_id="run-idempotent") is True
    with world.Session() as db:
        row = db.get(AgentExecution, execution_id)
        assert row.completed_at == sealed_at
        assert row.agent_id == AGENT
        assert row.status == "completed"
    with pytest.raises(CampaignAttributionError) as raised:
        complete_campaign_execution(
            db_path=world.db_path, execution_id=execution_id,
            assignment=assignment,
            completed_at=first_completed + timedelta(hours=1),
            run_id="run-idempotent")
    assert raised.value.reason == "campaign_completion_mismatch"
    with world.Session() as db:
        row = db.get(AgentExecution, execution_id)
        assert row.completed_at == sealed_at
        assert row.agent_id == AGENT


def test_legacy_user_attributed_rows_are_refused_not_resealed(world):
    from core.employee_campaign_intake import (
        CampaignAttributionError,
        complete_campaign_execution,
        record_campaign_evidence,
    )

    with world.Session() as db:
        db.add(AgentExecution(
            id="exec-legacy-user", agent_id=ADMIN,
            tenant_id=TENANT, workspace_id=WORKSPACE, status="completed",
            output_summary="completed", completed_at=world.now,
            metadata_json={"campaign": {
                "id": "employee-heldout-two-domain", "run_id": "run-legacy"}},
        ))
        db.commit()

    assignment = _campaign_plan(run_id="run-legacy", agent=AGENT)
    with pytest.raises(CampaignAttributionError) as raised:
        complete_campaign_execution(
            db_path=world.db_path, execution_id="exec-legacy-user",
            assignment=assignment, completed_at=world.now,
            run_id="run-legacy")
    assert raised.value.reason == "campaign_row_attribution_mismatch"

    refused = record_campaign_evidence(
        db_path=world.db_path,
        execution_id="exec-legacy-user",
        campaign="employee-heldout-two-domain",
        observation=_heldout_observation(),
        completed_at=world.now,
        decisions=[_accepted_decision("attempt-legacy")],
        assignment=assignment,
    )
    assert refused["status"] == "rejected"
    assert refused["reason"] == "campaign_row_attribution_mismatch"

    # Even a caller that omits the plan cannot seal the user-attributed row:
    # no registry row exists for a User.id, so the row is unresolved.
    refused_unplanned = record_campaign_evidence(
        db_path=world.db_path,
        execution_id="exec-legacy-user",
        campaign="employee-heldout-two-domain",
        observation=_heldout_observation(),
        completed_at=world.now,
        decisions=[_accepted_decision("attempt-legacy-unplanned")],
    )
    assert refused_unplanned["status"] == "rejected"
    assert refused_unplanned["reason"] == "campaign_row_agent_unresolved"
    with world.Session() as db:
        row = db.get(AgentExecution, "exec-legacy-user")
        assert bench_evidence.EVIDENCE_KEY not in (row.metadata_json or {})
        assert row.agent_id == ADMIN
