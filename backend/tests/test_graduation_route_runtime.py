"""Scripted runtime tests for repeat-task graduation route integration.

Covers the runtime wiring added on top of the verified comparator
(``core.llm.model_evidence_comparison``) and the durable qualification
receipt (``core.agent_graduation_service``):

* route evidence is only the validated reserved ``benchmark_evidence``
  records the server-side campaign producer
  (``core.employee_benchmark_evidence``) writes: eligible records are
  produced through the ACTUAL writer (sealed campaign journal, frozen
  scoring, authoritative completion time), while generic execution
  metadata and forged/tampered records are discarded, never scored;
* an equal-or-better replacement pins dispatch through the structured
  qualification pin (strict: exact route or failure);
* a weaker or stale replacement, and any route without same-benchmark
  evidence, is never dispatched — the normal supervised path applies;
* an unqualified fallback is filtered before the attempt (no unpinned
  escape on a strict graduation pin);
* a missing or conflicting provider response identity makes the result
  ineligible for autonomous use;
* before an irreversible effect the fresh evidence is revalidated through
  the assignment executor's autonomy gate, including after a restart.

No live provider, no live DB: scratch sqlite worlds, scripted transports,
the server-controlled frozen benchmark config, ``TESTING=1`` only.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional

import core.agent_graduation_service as grad
import core.employee_benchmark_evidence as bench_evidence
from core import autonomy_policy as ap
from core.agent_graduation_service import (
    request_qualification_review,
    validate_qualification_review_binding,
    write_qualification_receipt_from_review,
)
from core.database import Base
from core.assignment_planner import plan_assignment
from core.llm.graduation_route import (
    IDENTITY_CONFLICT,
    IDENTITY_MISSING,
    IDENTITY_VERIFIED,
    ROUTE_DECISION_KIND,
    STATE_PINNED,
    STATE_SUPERVISED,
    filter_route_for_attempt,
    load_repeat_task_evidence,
    revalidate_repeat_task_effect,
    resolve_repeat_task_route,
    validate_served_identity,
)
from core.llm.model_provenance import (
    clear_route_attribution,
    set_resolved_model,
    set_served_route,
)
from core.models import (
    AgentExecution,
    AgentRegistry,
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
from tests.test_assignment_routes import route_env  # noqa: F401

grad.get_lancedb_handler = lambda: None
grad.POMDP_AVAILABLE = False

TENANT = "route-runtime-tenant"
WORKSPACE = "route-runtime-workspace"
SUPERVISOR = "route-supervisor"
ADMIN = "route-admin"
AGENT = "route-agent"
OWNER = "route-owner"


def _frozen_benchmark() -> dict:
    """The server-controlled frozen benchmark (registry + digest-verified set)."""
    from core.employee_benchmark_evidence import _prepare_benchmark

    benchmark, _registry, reasons = _prepare_benchmark(None)
    assert benchmark is not None, reasons
    return benchmark


# The receipt binding, the assignment workload scope and the writer records
# all name the SAME frozen benchmark identity: the digest-pinned dataset, its
# scoring generation and the registry's canonical task scope.
_FROZEN = _frozen_benchmark()
BENCHMARK_ID = _FROZEN["benchmark_id"]
DATASET_SHA = _FROZEN["dataset_sha256"]
RUBRIC = _FROZEN["rubric_version"]
SCOPE = dict(_FROZEN["task_scope"])
_BENCHMARK_REGISTRY_PATH = bench_evidence.benchmark_registry_path()
BASELINE = ("openai", "gpt-5.4-2026-03")
CANDIDATE = ("openai", "gpt-5.5-mini")
UNQUALIFIED = ("openai", "gpt-unqualified")


def _utc_now():
    return datetime.now(timezone.utc)


def _newer(moment: datetime) -> datetime:
    """A strictly later completion time within the freshness window."""
    return moment + timedelta(minutes=5)


def _heldout_observation(
    *, failed_case: Optional[str] = None,
) -> dict:
    """Observed held-out campaign outputs, carrying NO authority claims.

    ``failed_case`` names one frozen case whose outcome fails its checks;
    everything else is the passing campaign observation. The verdict is
    computed by the writer from the frozen checks — never asserted here.
    """
    cases = {
        "heldout-quote": {
            "assignment_status": "completed",
            "steps": {"calculate": {
                "value": "96.30", "currency": "USD",
            }},
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
            "steps": {"reconcile": {
                "value": "140.25", "currency": "USD",
            }},
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
    elif failed_case == "reconcile":
        cases["heldout-reconcile"]["steps"]["reconcile"]["value"] = "99.00"
        cases["heldout-reconcile"]["deliverables"]["document"]["text"] = (
            "Reconciliation total unavailable.")
    # The frozen checks resolve ``external_effects`` inside each case and
    # ``run.restart.same_wait`` from the run context, so the observation
    # carries the effect count at the scope the checks actually read.
    return {
        "run": {"restart": {"same_wait": True}},
        "external_effects": 0,
        "cases": cases,
    }


class World:
    """Scratch world: durable receipt + campaign-writer benchmark records.

    ``ids`` may retarget every durable identity so the same world can be
    built inside another fixture's database (e.g. the assignment API route
    env); defaults are the module-level constants.
    """

    def __init__(
        self,
        tmp_path,
        *,
        engine=None,
        session_factory=None,
        ids: Optional[dict] = None,
        baseline_route=None,
        baseline_build: Optional[str] = None,
    ):
        self.ids = {
            "tenant": TENANT,
            "workspace": WORKSPACE,
            "supervisor": SUPERVISOR,
            "admin": ADMIN,
            "agent": AGENT,
            "owner": OWNER,
        }
        self.ids.update(ids or {})
        if session_factory is not None:
            # Shared durable world: the caller owns the engine (e.g. the
            # API route env's scratch database).
            self.db_path = None
            self.engine = None
            self.Session = session_factory
        else:
            self.db_path = tmp_path / "graduation-route-runtime.db"
            self._connect()
        started = _utc_now() - timedelta(days=2)
        tenant = self.ids["tenant"]
        workspace = self.ids["workspace"]
        supervisor = self.ids["supervisor"]
        admin = self.ids["admin"]
        agent_id = self.ids["agent"]
        owner = self.ids["owner"]
        baseline_route = tuple(baseline_route or BASELINE)
        baseline_provenance = {
            "provider": baseline_route[0],
            "model": baseline_route[1],
            "serving_models": [{
                "provider": baseline_route[0], "model": baseline_route[1]}],
        }
        if baseline_build:
            # The receipt's serving route stays the callable route; the
            # provider build is recorded separately, never merged into it.
            baseline_provenance["resolved_model"] = baseline_build
        with self.Session() as db:
            db.add(Tenant(
                id=tenant, name="Route Runtime Tenant",
                subdomain=f"rr-{uuid.uuid4().hex[:8]}", edition="personal",
                is_active=True,
            ))
            db.add(Workspace(
                id=workspace, name="Route Runtime", tenant_id=tenant))
            db.add_all([
                User(
                    id=supervisor, tenant_id=tenant, workspace_id=workspace,
                    email=f"{supervisor}@route.test", first_name="S",
                    last_name="V", role="team_lead", status="active",
                    is_active=True,
                ),
                User(
                    id=admin, tenant_id=tenant, workspace_id=workspace,
                    email=f"{admin}@route.test", first_name="A", last_name="V",
                    role="admin", status="active", is_active=True,
                ),
            ])
            db.add(AgentRegistry(
                id=agent_id, name="Route Candidate", category="operations",
                role="agent", type="personal", capabilities=[],
                module_path="core.generic_agent", class_name="GenericAgent",
                user_id=supervisor, workspace_id=workspace, tenant_id=tenant,
                status="student", enabled=True, confidence_score=0.62,
                configuration={"learning": {"role": "operations", "log": []}},
            ))
            # The receipt's own qualification evidence: baseline serving route
            # observed next to a complete benchmark identity.
            db.add(AgentExecution(
                id="exec-1", agent_id=agent_id, tenant_id=tenant,
                workspace_id=workspace, status="completed",
                input_summary="held-out qualification task",
                result_summary="actual durable qualification output",
                completed_at=started + timedelta(minutes=5),
                metadata_json={
                    "model_provenance": dict(baseline_provenance),
                },
            ))
            db.add(grad.AgentEpisode(
                id="ep-1", agent_id=agent_id, tenant_id=tenant,
                workspace_id=workspace, execution_id="exec-1",
                task_description="held-out qualification task",
                maturity_at_time="student", constitutional_score=0.9,
                human_intervention_count=0, confidence_score=0.62,
                outcome="success", success=True, status="completed",
                started_at=started,
                completed_at=started + timedelta(minutes=5),
                metadata_json={
                    "benchmark_identity": {
                        "dataset_sha256": DATASET_SHA,
                        "rubric_version": RUBRIC,
                        "task_scope": dict(SCOPE),
                    },
                    "model_provenance": dict(baseline_provenance),
                },
            ))
            db.commit()
        self.receipt_id = self._approve_receipt()
        # Repeat-task routing resolves the runtime baseline from the committed
        # promotion transition into the agent's current tier, so the world
        # actually promotes STUDENT -> INTERN on the verified receipt.
        self.promotion_id = self._promote_to_intern()

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
        if self.db_path is None:
            return
        self.engine.dispose()
        self._connect()

    def _promote_to_intern(self) -> str:
        from core.agent_graduation_service import commit_qualified_transition

        agent_id = self.ids["agent"]
        with self.Session() as db:
            result = commit_qualified_transition(
                db,
                agent_id=agent_id,
                target_level="INTERN",
                actor_id=self.ids["supervisor"],
                readiness={"ready": True, "score": 0.88, "gaps": []},
                source="graduation-route-runtime",
                operation_id=f"graduation-route-runtime-promotion-{agent_id}",
            )
            assert result["status"] == "verified", result
            history_id = result["data"]["promotion_history_id"]
        with self.Session() as db:
            agent = db.get(AgentRegistry, agent_id)
            assert agent.status == "intern"
            assert agent.last_exam_id == self.receipt_id
        return history_id

    def _approve_receipt(self) -> str:
        agent_id = self.ids["agent"]
        with self.Session() as db:
            agent = db.get(AgentRegistry, agent_id)
            result = request_qualification_review(
                db,
                agent=agent,
                target_level="INTERN",
                evidence_refs=[
                    {"kind": "agent_episode", "id": "ep-1"},
                    {"kind": "agent_execution", "id": "exec-1"},
                ],
                rubric_version=RUBRIC,
                requested_by=self.ids["supervisor"],
                tenant_id=self.ids["tenant"],
                workspace_id=self.ids["workspace"],
            )
            action_id = result["action_id"]
        with self.Session() as db:
            action = db.get(HITLAction, action_id)
            assert validate_qualification_review_binding(db, action)["valid"]
            action.status = HITLActionStatus.APPROVED.value
            action.reviewed_by = self.ids["admin"]
            action.reviewed_at = _utc_now()
            db.commit()
        with self.Session() as db:
            written = write_qualification_receipt_from_review(
                db, action_id=action_id, approved=True,
                reviewer_id=self.ids["admin"],
            )
            assert written["state"] == "valid", written
            return written["receipt_id"]

    def produce_benchmark_evidence(
        self, exec_id: str, provider: str, model: str, *,
        observed_at: datetime, failed_case: Optional[str] = None,
        served_model: Optional[str] = None,
        echo_model: Optional[str] = None,
        echo_provider: Optional[str] = None,
        execution_provenance: Optional[dict] = None,
    ) -> dict:
        """Score one held-out campaign run through the ACTUAL writer.

        The durable execution row is created exactly as a campaign run
        leaves it (unscored, no benchmark claims); the campaign's own
        transport journal records the accepted callable route separately
        from the provider-echoed build and is sealed with the execution's
        durable completion time; then ``produce_employee_benchmark_evidence``
        computes the verdict from the frozen checks and appends the
        digest-sealed record. Nothing here asserts a score, a timestamp or a
        route.

        ``model`` is the selected callable route; ``served_model`` defaults
        to it. ``echo_model``/``echo_provider`` are the provider's response
        echo, which may be a versioned build of the same route.
        """
        from core.employee_benchmark_evidence import (
            open_campaign_transport_journal,
            produce_employee_benchmark_evidence,
        )

        with self.Session() as db:
            db.add(AgentExecution(
                id=exec_id, agent_id=self.ids["agent"],
                tenant_id=self.ids["tenant"],
                workspace_id=self.ids["workspace"], status="completed",
                input_summary="held-out benchmark campaign run",
                result_summary="campaign observation (unscored material)",
                completed_at=observed_at,
                metadata_json=dict(execution_provenance or {}),
            ))
            db.commit()
        journal = open_campaign_transport_journal(
            campaign_id=f"heldout-{exec_id}", execution_id=exec_id)
        journal.record_call(
            accepted=True,
            requested_route={"provider": provider, "model": model},
            served_route={
                "provider": provider, "model": served_model or model},
            response_identity={
                "provider": echo_provider or provider,
                "model": echo_model or model,
            },
        )
        journal.seal(completed_at=observed_at)
        return produce_employee_benchmark_evidence(
            execution_id=exec_id,
            observation=_heldout_observation(failed_case=failed_case),
            transport_journal=journal,
            session_factory=self.Session,
        )

    def add_benchmark_evidence(self, *args, **kwargs) -> dict:
        result = self.produce_benchmark_evidence(*args, **kwargs)
        assert result["status"] == "recorded", result
        return result

    def stored_benchmark_records(self, exec_id: str) -> list:
        with self.Session() as db:
            row = db.get(AgentExecution, exec_id)
            records = (row.metadata_json or {}).get("benchmark_evidence")
        return list(records or [])

    def age_all_observations(self, days: int) -> None:
        """Move every benchmark observation outside the freshness window.

        The writer binds ``observed_at`` to the durable execution
        completion time, so aging is expressed the only way the writer
        would have recorded it: the execution completed earlier, and the
        stored record is re-sealed for that completion time (digests
        recomputed exactly as the writer does; the authoritative verdict
        is untouched).
        """
        old = _utc_now() - timedelta(days=days)
        from core.employee_benchmark_evidence import record_digest

        with self.Session() as db:
            rows = (
                db.query(AgentExecution)
                .filter(AgentExecution.agent_id == self.ids["agent"])
                .all()
            )
            for row in rows:
                metadata = dict(row.metadata_json or {})
                raw_records = metadata.get("benchmark_evidence")
                if not isinstance(raw_records, list):
                    continue
                aged: list = []
                for record in raw_records:
                    if not isinstance(record, dict):
                        continue
                    record = dict(record)
                    execution = dict(record.get("execution") or {})
                    execution["completed_at"] = old.isoformat()
                    record["execution"] = execution
                    record["observed_at"] = old.isoformat()
                    integrity = dict(record.get("integrity") or {})
                    integrity["record_sha256"] = record_digest(record)
                    record["integrity"] = integrity
                    aged.append(record)
                metadata["benchmark_evidence"] = aged
                row.metadata_json = metadata
                flag_modified(row, "metadata_json")
            db.commit()

    def agent(self):
        with self.Session() as db:
            return db.get(AgentRegistry, self.ids["agent"])


@pytest.fixture(autouse=True)
def _default_policy(monkeypatch):
    # The frozen benchmark is the in-repo server-controlled registry: pin
    # the env override to the exact file the module constants came from so
    # a developer's environment cannot retarget the tests.
    monkeypatch.setenv(
        "ATOM_EMPLOYEE_BENCHMARK_FILE", str(_BENCHMARK_REGISTRY_PATH))
    # The qualification receipt binds the owner's assessment-policy rubric,
    # while the campaign evidence independently carries the frozen benchmark
    # rubric. This fixture pins the policy to the frozen benchmark rubric
    # (same production policy schema and digest checks, no relaxed
    # validation) so the two server-owned identities describe the same
    # held-out assessment instead of the built-in development default.
    policy = dict(DEFAULT_ASSESSMENT_POLICY)
    policy["rubric_version"] = RUBRIC
    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
    monkeypatch.delenv("ATOM_EMPLOYEE_PROVIDER_MODEL", raising=False)


@pytest.fixture()
def world(tmp_path):
    return World(tmp_path)


# --- Scripted transports ---------------------------------------------------


class ScriptedHandler:
    def __init__(self, clients):
        self.clients = {name: object() for name in clients}

        class _Policy:
            def allows(self, provider, model):
                return True

        self.provider_policy = _Policy()


class ScriptedLLM:
    """A scripted provider boundary: records dispatch kwargs and stamps the
    served identity exactly like the real byok boundary does."""

    def __init__(self, clients=("openai",), *, behavior="ok",
                 served_route=None, resolved_model=None, result=None):
        self._handler = ScriptedHandler(clients)
        self.behavior = behavior
        self.served_route = served_route
        self.resolved_model = resolved_model
        self.result = result if result is not None else SimpleNamespace(ok=True)
        self.calls: list = []

    def _get_handler(self, workspace_id=None, tenant_id=None):
        return self._handler

    async def generate_structured_response(self, **kwargs):
        self.calls.append(kwargs)
        if self.behavior == "raise":
            raise RuntimeError("scripted provider failure")
        if self.behavior == "none":
            return None
        if self.served_route:
            set_served_route(self.served_route[0], self.served_route[1])
        if self.resolved_model:
            set_resolved_model(self.resolved_model)
        return self.result


class DecisionLog:
    """Durable append-only decision log on a scratch file (restart-safe)."""

    def __init__(self, path):
        self.path = path

    def _load(self):
        try:
            with open(self.path) as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return []

    def append_decision(self, run_id, entry):
        entries = self._load()
        entries.append({"ts": _utc_now().isoformat(), **dict(entry)})
        with open(self.path, "w") as handle:
            json.dump(entries, handle)

    def get_decisions(self, run_id):
        return self._load()

    def route_entries(self):
        return [
            entry for entry in self._load()
            if str(entry.get("kind") or "") == ROUTE_DECISION_KIND
        ]


def stub_executor(world: World, log: DecisionLog, record: dict):
    runs = SimpleNamespace(
        _sessions=lambda: world.Session,
        append_decision=log.append_decision,
        get_decisions=log.get_decisions,
    )

    def mutate_assignment(run_id, compute, *, rationale=""):
        new_assignment, result = compute(record, record.get("assignment"))
        record["assignment"] = new_assignment
        return result

    lifecycle = SimpleNamespace(
        runs=runs,
        get_task=lambda run_id: dict(record),
        mutate_assignment=mutate_assignment,
    )
    return SimpleNamespace(lifecycle=lifecycle)


def _assignment_record(
    *,
    agent_id=AGENT,
    provider_model=None,
    workload_scope=SCOPE,
):
    provenance = {"user_id": OWNER}
    if agent_id:
        provenance["agent_id"] = agent_id
    assignment = {
        "assignment_id": "asg-route-1",
        "objective": "held-out repeat task",
        "employee_id": OWNER,
        "workspace_id": WORKSPACE,
        "tenant_id": TENANT,
        "status": "planned",
        "steps": [],
        "sources": [],
        "provenance": provenance,
    }
    if workload_scope is not None:
        # Server-durable workload identity on the persisted plan; the
        # dispatch-time request is never consulted by the resolver.
        assignment["workload_scope"] = workload_scope
    return {
        "run_id": "run-route-1",
        "task_revision": {"task_revision": 1, "unresolved": []},
        "assignment": assignment,
    }


# --- Receipt-backed resolution ---------------------------------------------


def _matching_assignment(**overrides):
    """The durable plan shape the resolver reads for workload identity."""
    assignment = {
        "assignment_id": "asg-route-unit",
        "objective": "held-out repeat task",
        "workload_scope": dict(SCOPE),
    }
    assignment.update(overrides)
    return assignment


def test_equal_or_better_replacement_pins_dispatch(world):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh))
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            candidates=[CANDIDATE])
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    # The baseline resolves from the committed promotion transition plus its
    # durable receipt, not from the now-stale pre-transition read.
    assert decision["promotion_id"] == world.promotion_id
    assert decision["source_level"] == "student"
    assert decision["target_level"] == "intern"
    assert decision["receipt_id"] == world.receipt_id
    assert decision["baseline_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}
    assert decision["selected_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    assert decision["autonomous_eligible"] is True
    assert decision["comparison"]["baseline"]["state"] == "established"

    # The structured qualification pin resolves for the selected route.
    llm = ScriptedLLM(clients=("openai",))
    allowed = filter_route_for_attempt(
        decision["selected_route"], quality=1.0, llm_service=llm,
        workspace_id=WORKSPACE, tenant_id=TENANT, evidence={})
    assert allowed["allowed"] is True, allowed["reasons"]
    assert allowed["pin"] == CANDIDATE

    # Strict pinned dispatch: exactly one provider attempt, identity verified.
    llm.served_route = CANDIDATE
    llm.resolved_model = "gpt-5.5-mini-2026-01"
    provenance: dict = {}
    clear_route_attribution()
    result = asyncio.run(_pinned(llm, provenance))
    assert result is not None
    assert len(llm.calls) == 1
    assert llm.calls[0]["provider_model"] == CANDIDATE
    assert validate_served_identity(CANDIDATE, provenance) == IDENTITY_VERIFIED


async def _pinned(llm, provenance):
    from core.llm.pinned_planning import pinned_structured_call

    return await pinned_structured_call(
        llm,
        prompt="held-out repeat task",
        response_model=SimpleNamespace,
        system_instruction="Return JSON only.",
        call_kwargs={"provider_model": CANDIDATE},
        log_label="employee work proposal",
        task_type="planning",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        provenance=provenance,
        strict_pin=True,
    )


def test_failed_replacement_supervises_but_baseline_still_pins(world):
    """A replacement whose benchmark run FAILED is never dispatched.

    The writer recorded the candidate's run against the frozen set and the
    verdict is negative: valid negative evidence, not a substitution — the
    normal supervised path applies and the receipt's own baseline route
    still pins.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh),
        failed_case="reconcile")
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            candidates=[CANDIDATE])
    assert decision["route_state"] == STATE_SUPERVISED
    assert decision["autonomous_eligible"] is False
    assert any(
        "evidence_not_passed" in reasons
        for candidate in decision["comparison"]["candidates"]
        for reasons in [candidate["reasons"]])

    # The receipt's own baseline route remains evidence-eligible: the normal
    # supervised path is unaffected and the original route still pins.
    baseline_decision = resolve_repeat_task_route(
        db, agent, assignment=_matching_assignment())
    assert baseline_decision["route_state"] == STATE_PINNED
    assert baseline_decision["selected_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}


def test_unknown_assignment_workload_never_inherits_baseline(world):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        # No server-derived workload identity on the assignment record: the
        # receipt baseline must not be inherited, whatever the evidence says.
        decision = resolve_repeat_task_route(
            db, agent, assignment={"assignment_id": "asg-unknown"})
        assert decision["route_state"] == STATE_SUPERVISED
        assert "workload_scope_unknown" in decision["reasons"]
        assert decision["selected_route"] is None
        assert decision["autonomous_eligible"] is False
        # The workload gate fires before any evidence is read: even with no
        # assignment object at all the outcome is supervision, not baseline
        # inheritance.
        decision = resolve_repeat_task_route(db, agent)
        assert decision["route_state"] == STATE_SUPERVISED
        assert "workload_scope_unknown" in decision["reasons"]


def test_unrelated_assignment_workload_never_inherits_baseline(world):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh))
    unrelated = {
        "task_policy": "Summarize unread email threads for the digest.",
        "decision_options": ["SEND", "HOLD"],
        "subject_field": "Thread",
    }
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(
                workload_scope=unrelated, assignment_id="asg-unrelated"))
        assert decision["route_state"] == STATE_SUPERVISED
        assert "workload_scope_mismatch" in decision["reasons"]
        assert decision["selected_route"] is None
        assert decision["autonomous_eligible"] is False
        # A string scope never equals the binding's mapping scope.
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(
                workload_scope="approve-open-records",
                assignment_id="asg-string-scope"))
        assert decision["route_state"] == STATE_SUPERVISED
        assert "workload_scope_mismatch" in decision["reasons"]


def test_stale_replacement_supervises(world):
    fresh = _utc_now() - timedelta(days=2)
    stale = _utc_now() - timedelta(days=45)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=stale)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            candidates=[CANDIDATE])
    assert decision["route_state"] == STATE_SUPERVISED
    assert "stale_evidence" in decision["reasons"]


def test_unqualified_route_is_never_a_candidate(world):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            candidates=[UNQUALIFIED])
    # No same-benchmark evidence for the unqualified route: supervised, and
    # the proposed route was not silently substituted by another route.
    assert decision["route_state"] == STATE_SUPERVISED
    assert decision["selected_route"] is None
    assert "missing_evidence" in decision["reasons"]


def test_strict_graduation_pin_never_falls_back(world):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert decision["route_state"] == STATE_PINNED

    # A strict graduation pin refuses the unpinned fallback: the failed route
    # is the end of the attempt list, never an escape to an unqualified pool.
    failing = ScriptedLLM(behavior="raise")
    provenance: dict = {}
    clear_route_attribution()
    result = asyncio.run(_pinned_baseline(failing, provenance))
    assert result is None
    assert len(failing.calls) == 1
    assert failing.calls[0].get("provider_model") == BASELINE

    # Contrast: the historical non-strict behavior still retries unpinned.
    clear_route_attribution()
    legacy = ScriptedLLM(behavior="raise")
    legacy_result = asyncio.run(
        _pinned_baseline(legacy, {}, strict_pin=None))
    assert legacy_result is None
    assert len(legacy.calls) == 2
    assert "provider_model" not in legacy.calls[1]


async def _pinned_baseline(llm, provenance, *, strict_pin=True):
    from core.llm.pinned_planning import pinned_structured_call

    return await pinned_structured_call(
        llm,
        prompt="held-out repeat task",
        response_model=SimpleNamespace,
        system_instruction="Return JSON only.",
        call_kwargs={"provider_model": BASELINE},
        log_label="employee work proposal",
        task_type="planning",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        provenance=provenance,
        strict_pin=strict_pin,
    )


def test_capability_filter_refuses_pinless_route(world):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert decision["route_state"] == STATE_PINNED
    # A dispatch scope whose handler does not carry the provider refuses the
    # pin: the route is filtered before any attempt.
    scoped = ScriptedLLM(clients=("other",))
    allowed = filter_route_for_attempt(
        decision["selected_route"], quality=1.0, llm_service=scoped,
        workspace_id=WORKSPACE, tenant_id=TENANT, evidence={})
    assert allowed["allowed"] is False
    assert allowed["reasons"] == ["pin_refused"]


def test_missing_provider_identity_is_ineligible(world):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert decision["route_state"] == STATE_PINNED

    # The provider answered but the boundary recorded no served identity.
    llm = ScriptedLLM(clients=("openai",))
    provenance: dict = {}
    clear_route_attribution()
    result = asyncio.run(_pinned_baseline(llm, provenance))
    assert result is not None
    assert validate_served_identity(BASELINE, provenance) == IDENTITY_MISSING

    # A conflicting served identity is equally ineligible; an available build
    # identity must agree on the model family.
    clear_route_attribution()
    llm.served_route = (BASELINE[0], "gpt-other")
    llm.resolved_model = "gpt-other-2026-01"
    conflict_provenance: dict = {}
    asyncio.run(_pinned_baseline(llm, conflict_provenance))
    assert validate_served_identity(
        BASELINE, conflict_provenance) == IDENTITY_CONFLICT


# --- Assignment entry point -------------------------------------------------


def _install_entry_fakes(monkeypatch, *, calls, routing):
    from core.llm.pinned_planning import routing_snapshot

    async def fake_work(context, **kwargs):
        calls.append(kwargs)
        provenance: dict = {}
        for key, value in (
                ("mode", "pinned" if kwargs.get("provider_model") else "unpinned"),
                ("requested_route", (
                    {"provider": kwargs["provider_model"][0],
                     "model": kwargs["provider_model"][1]}
                    if kwargs.get("provider_model") else None)),
                ("served_route", routing.get("served_route")),
                ("resolved_model", routing.get("resolved_model")),
        ):
            if value is not None:
                provenance[key] = value
        snapshot = routing_snapshot(provenance)
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "scoped read of authorized evidence",
                "evidence_reads": [],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
            "attempt_id": "attempt-1",
            "routing": snapshot,
        }

    async def fake_adaptation(context, observations, **kwargs):
        calls.append(kwargs)
        return {
            "proposal": {"decision": "retain", "reason": "nothing ready"},
            "source": "model",
            "technical_fallback": False,
            "errors": [],
            "routing": routing_snapshot({}),
        }

    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work", fake_work)
    monkeypatch.setattr(
        "api.assignment_routes.propose_adaptation", fake_adaptation)
    import core.employee_job_runner as runner

    monkeypatch.setattr(
        runner, "evidence_observations", lambda record: [])
    monkeypatch.setattr(
        runner, "unread_authorized_sources",
        lambda assignment: [{"source_id": "s-1"}])
    import core.task_lifecycle as task_lifecycle
    import core.employee_proposal as employee_proposal

    monkeypatch.setattr(
        task_lifecycle, "open_unresolved_questions", lambda record: False)
    monkeypatch.setattr(
        employee_proposal, "operation_capabilities", lambda assignment: [])
    monkeypatch.setattr(
        runner, "deterministic_unread_evidence_proposal", lambda unread: None)


def test_entry_point_pins_equal_or_better_candidate(world, tmp_path, monkeypatch):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh))
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": CANDIDATE[0], "model": CANDIDATE[1]},
            "resolved_model": "gpt-5.5-mini-2026-01",
        })
    log = DecisionLog(tmp_path / "decisions.json")
    record = _assignment_record()
    executor = stub_executor(world, log, record)

    from api.assignment_routes import _advance_employee_work

    rounds = asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=("other", "legacy-model")))

    assert rounds
    # The graduation-evidence route superseded the caller pin and dispatched
    # strictly through the qualification pin.
    assert calls[0]["provider_model"] == CANDIDATE
    assert calls[0]["strict_pin"] is True
    entries = log.route_entries()
    assert entries, "a durable route decision must be recorded"
    final = entries[-1]
    assert final["route_state"] == STATE_PINNED
    assert final["selected_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    assert final["identity_state"] == IDENTITY_VERIFIED
    assert final["autonomous_eligible"] is True


def test_entry_point_rejects_failed_candidate_and_keeps_baseline(
        world, tmp_path, monkeypatch):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh),
        failed_case="reconcile")
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": BASELINE[0], "model": BASELINE[1]},
            "resolved_model": BASELINE[1],
        })
    log = DecisionLog(tmp_path / "decisions.json")
    executor = stub_executor(world, log, _assignment_record())

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=("other", "legacy-model")))

    # The failed replacement is never dispatched; the receipt's own serving
    # route — still evidence-eligible — is pinned strictly instead, and the
    # durable decision supersedes the caller pin for this repeat task.
    assert calls[0]["provider_model"] == BASELINE
    assert calls[0]["strict_pin"] is True
    entries = log.route_entries()
    assert entries
    final = entries[-1]
    assert final["route_state"] == STATE_PINNED
    assert final["selected_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}
    assert final["identity_state"] == IDENTITY_VERIFIED


def test_entry_point_supervises_when_all_evidence_is_stale(
        world, tmp_path, monkeypatch):
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE,
        observed_at=_utc_now() - timedelta(days=45))
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": "other", "model": "legacy-model"},
        })
    log = DecisionLog(tmp_path / "decisions.json")
    executor = stub_executor(world, log, _assignment_record())

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=("other", "legacy-model")))

    # No current same-benchmark evidence: eligibility is unknown, the normal
    # supervised path applies and the caller's routing is untouched.
    assert calls[0]["provider_model"] == ("other", "legacy-model")
    assert calls[0].get("strict_pin") is None
    entries = log.route_entries()
    assert entries
    final = entries[-1]
    assert final["route_state"] == STATE_SUPERVISED
    assert final["autonomous_eligible"] is False


def test_entry_point_supervises_unrelated_assignment_workload(
        world, tmp_path, monkeypatch):
    """The same agent on an unrelated workload never inherits the baseline.

    Fresh passing evidence exists for the candidate on the receipt's own
    benchmark, but the assignment's server-derived workload identity does not
    match the binding: no route is selected, the caller's routing is
    untouched, and the durable decision records the supervised outcome.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh))
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": "other", "model": "legacy-model"},
        })
    log = DecisionLog(tmp_path / "decisions.json")
    record = _assignment_record(workload_scope={
        "task_policy": "Summarize unread email threads for the digest.",
        "decision_options": ["SEND", "HOLD"],
        "subject_field": "Thread",
    })
    executor = stub_executor(world, log, record)

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=("other", "legacy-model")))

    # Normal supervised path: the caller/operator routing is untouched and no
    # strict pin was forced.
    assert calls[0]["provider_model"] == ("other", "legacy-model")
    assert calls[0].get("strict_pin") is None
    entries = log.route_entries()
    assert entries
    final = entries[-1]
    assert final["route_state"] == STATE_SUPERVISED
    assert "workload_scope_mismatch" in final["reasons"]
    assert final["autonomous_eligible"] is False
    # The durable plan marker binds the supervision requirement for the
    # effect gate even if these decision records are lost later.
    assert record["assignment"]["repeat_task_route"]["route_state"] == (
        STATE_SUPERVISED)


def test_entry_point_records_identity_conflict(world, tmp_path, monkeypatch):
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            # The provider answered on a different route than the pin.
            "served_route": {"provider": "openai", "model": "gpt-shadow"},
        })
    log = DecisionLog(tmp_path / "decisions.json")
    executor = stub_executor(world, log, _assignment_record())

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=None))

    assert calls[0]["provider_model"] == BASELINE
    assert calls[0]["strict_pin"] is True
    entries = log.route_entries()
    assert entries
    final = entries[-1]
    assert final["identity_state"] == IDENTITY_CONFLICT
    assert final["autonomous_eligible"] is False


def test_entry_point_without_comparable_receipt_is_unrouted(
        world, tmp_path, monkeypatch):
    # No qualification receipt for this agent: unrelated routing untouched,
    # no repeat-task decision recorded.
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": "other", "model": "legacy-model"},
        })
    log = DecisionLog(tmp_path / "decisions.json")
    record = _assignment_record()
    record["assignment"]["provenance"]["agent_id"] = "agent-without-receipt"
    executor = stub_executor(world, log, record)

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("other",)),
        max_rounds=1, provider_model=("other", "legacy-model")))

    assert calls[0]["provider_model"] == ("other", "legacy-model")
    assert calls[0].get("strict_pin") is None
    assert log.route_entries() == []


# --- Effect gate revalidation (including after restart) ---------------------


def _governance_ok():
    gov = MagicMock()
    gov.can_perform_action.return_value = {
        "allowed": True,
        "agent_status": "supervised",
        "required_status": "supervised",
        "reason": "ok",
    }
    return gov


def _gate_assignment(*, marker: Optional[dict] = None):
    assignment = {
        "assignment_id": "asg-route-1",
        "employee_id": OWNER,
        "provenance": {"agent_id": AGENT, "user_id": OWNER},
        "workload_scope": dict(SCOPE),
    }
    if marker is not None:
        assignment["repeat_task_route"] = marker
    return assignment


def _route_marker(**overrides):
    marker = {
        "schema": "atom-repeat-task-route-marker-1",
        "kind": ROUTE_DECISION_KIND,
        "agent_id": AGENT,
        "route_state": STATE_PINNED,
        "recorded_at": _utc_now().isoformat(),
    }
    marker.update(overrides)
    return marker


def _gate_step():
    return {
        "step_id": "crm-1",
        "operation_type": "outbound",
        "adapter": "crm.update_record",
        "effect": "external",
    }


def _prepare_gate(world, monkeypatch):
    with world.Session() as db:
        assert ap.set_mode(
            db, OWNER, "crm_write", ap.MODE_AUTO_IF_MATURE) is True
        db.commit()
    monkeypatch.setattr(
        "core.service_factory.ServiceFactory.get_governance_service",
        lambda *a, **k: _governance_ok(),
    )


def test_effect_gate_revalidates_fresh_evidence(world, tmp_path, monkeypatch):
    _prepare_gate(world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision("run-route-1", {
        "kind": ROUTE_DECISION_KIND,
        "agent_id": AGENT,
        "route_state": STATE_PINNED,
        "selected_route": {"provider": BASELINE[0], "model": BASELINE[1]},
        "identity_state": IDENTITY_VERIFIED,
        "autonomous_eligible": True,
    })
    from core.assignment_executor import AssignmentExecutor

    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        assert executor._autonomy_gate(
            _gate_assignment(), _gate_step(),
            run_id="run-route-1") is None


def test_effect_gate_demotes_stale_evidence_after_restart(
        world, tmp_path, monkeypatch):
    _prepare_gate(world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision("run-route-1", {
        "kind": ROUTE_DECISION_KIND,
        "agent_id": AGENT,
        "route_state": STATE_PINNED,
        "identity_state": IDENTITY_VERIFIED,
        "autonomous_eligible": True,
    })
    from core.assignment_executor import AssignmentExecutor

    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        assert executor._autonomy_gate(
            _gate_assignment(), _gate_step(),
            run_id="run-route-1") is None

    # Evidence ages out; a fresh process re-reads the durable world.
    world.age_all_observations(days=45)
    world.reopen()
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        denial = executor._autonomy_gate(
            _gate_assignment(), _gate_step(), run_id="run-route-1")
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert denial.get("source") == "repeat_task_route_recheck"
    assert "supervised" in str(denial.get("reason"))


def test_effect_gate_demotes_conflicting_identity(world, tmp_path, monkeypatch):
    _prepare_gate(world, monkeypatch)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision("run-route-1", {
        "kind": ROUTE_DECISION_KIND,
        "agent_id": AGENT,
        "route_state": STATE_PINNED,
        "identity_state": IDENTITY_CONFLICT,
        "autonomous_eligible": False,
    })
    from core.assignment_executor import AssignmentExecutor

    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        denial = executor._autonomy_gate(
            _gate_assignment(), _gate_step(), run_id="run-route-1")
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert "identity" in str(denial.get("reason"))


def test_effect_gate_without_route_context_is_untouched(
        world, tmp_path, monkeypatch):
    _prepare_gate(world, monkeypatch)
    from core.assignment_executor import AssignmentExecutor

    log = DecisionLog(tmp_path / "decisions.json")
    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        # No repeat-task decision on this run: the existing autonomy gate
        # alone decides, exactly as before this integration.
        assert executor._autonomy_gate(
            _gate_assignment(), _gate_step(),
            run_id="run-route-1") is None


def test_revalidate_returns_none_without_route_context(world, tmp_path):
    log = DecisionLog(tmp_path / "decisions.json")
    with world.Session() as db:
        assert revalidate_repeat_task_effect(
            db, agent_id=AGENT,
            decisions=log.get_decisions("run-route-1")) is None


# --- Fail-closed durable effect revalidation --------------------------------


def test_effect_gate_supervises_when_route_records_missing_after_restart(
        world, tmp_path, monkeypatch):
    """A persisted repeat assignment outlives its decision records.

    The durable plan marker says this run used a repeat-task route; the
    decision log came back empty after a restart. Missing route records must
    never erase the supervision requirement, and a standing grant must not
    bypass it: the normal assignment executor requests approval.
    """
    _prepare_gate(world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    # Decision log lost entirely after the restart.
    log = DecisionLog(tmp_path / "decisions.json")
    from core.assignment_executor import AssignmentExecutor

    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        denial = executor._autonomy_gate(
            _gate_assignment(marker=_route_marker()), _gate_step(),
            run_id="run-route-1")
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert denial.get("source") == "repeat_task_route_recheck"
    assert "missing" in str(denial.get("reason"))


def test_effect_gate_supervises_when_decision_log_unreadable(
        world, tmp_path, monkeypatch):
    _prepare_gate(world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    from core.assignment_executor import AssignmentExecutor

    def broken_get_decisions(run_id):
        raise OSError("decision log unavailable")

    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=broken_get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        # With the durable marker present, the unreadable log cannot quietly
        # restore an execute outcome.
        denial = executor._autonomy_gate(
            _gate_assignment(marker=_route_marker()), _gate_step(),
            run_id="run-route-1")
        assert denial is not None
        assert denial["outcome"] == ap.OUTCOME_PROPOSE
        assert "could not be read" in str(denial.get("reason"))
        # And even without a marker, unavailable decision state fails closed
        # for a mutating effect claim.
        denial = executor._autonomy_gate(
            _gate_assignment(), _gate_step(), run_id="run-route-1")
        assert denial is not None
        assert denial["outcome"] == ap.OUTCOME_PROPOSE


def test_effect_gate_refuses_foreign_route_marker(
        world, tmp_path, monkeypatch):
    _prepare_gate(world, monkeypatch)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision("run-route-1", {
        "kind": ROUTE_DECISION_KIND,
        "agent_id": AGENT,
        "route_state": STATE_PINNED,
        "identity_state": IDENTITY_VERIFIED,
    })
    from core.assignment_executor import AssignmentExecutor

    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        denial = executor._autonomy_gate(
            _gate_assignment(marker=_route_marker(agent_id="other-agent")),
            _gate_step(), run_id="run-route-1")
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert "different agent" in str(denial.get("reason"))


def test_effect_gate_marker_survives_restart_and_requires_fresh_pin(
        world, tmp_path, monkeypatch):
    """Marker + surviving records still revalidate through a fresh world."""
    _prepare_gate(world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision("run-route-1", {
        "kind": ROUTE_DECISION_KIND,
        "agent_id": AGENT,
        "route_state": STATE_PINNED,
        "selected_route": {"provider": BASELINE[0], "model": BASELINE[1]},
        "identity_state": IDENTITY_VERIFIED,
        "autonomous_eligible": True,
    })
    from core.assignment_executor import AssignmentExecutor

    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        assert executor._autonomy_gate(
            _gate_assignment(marker=_route_marker()), _gate_step(),
            run_id="run-route-1") is None

    # After a restart with aged evidence, the marker still binds the
    # requirement and the fresh world demotes the effect.
    world.age_all_observations(days=45)
    world.reopen()
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        denial = executor._autonomy_gate(
            _gate_assignment(marker=_route_marker()), _gate_step(),
            run_id="run-route-1")
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert denial.get("source") == "repeat_task_route_recheck"


# --- Candidate discovery (normal path, no operator pin) ---------------------


def test_discovery_selects_replacement_without_operator_pin(world):
    """An ordinary assignment discovers a fresh eligible replacement.

    No candidates are passed: the compared set is populated from the scoped
    current evidence plus the existing capability profile policy, and the
    stronger candidate is pinned — no operator pin involved.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh))
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    assert decision["candidate_source"] == "discovered"
    assert decision["selected_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    compared = {
        (route["provider"], route["model"])
        for route in decision["candidate_routes"]}
    assert {BASELINE, CANDIDATE} <= compared


def test_discovery_excludes_failed_replacement_and_baseline_still_pins(world):
    """A replacement whose writer-verdict is negative is not discovered.

    A failed run is valid negative evidence: it never enters the trusted
    discovery cohort, and the receipt's own eligible baseline route is
    selected instead of it.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh),
        failed_case="reconcile")
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    assert decision["candidate_source"] == "discovered"
    assert decision["selected_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}
    compared = {
        (route["provider"], route["model"])
        for route in decision["candidate_routes"]}
    assert CANDIDATE not in compared


def test_discovery_excludes_quarantined_route(world):
    """Measured unsafe evidence removes the route from the discovery cohort.

    Without this, a quarantined route would win selection on benchmark score
    alone and its attempt-time refusal would demote the whole resolution
    while the eligible baseline route was available.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh))
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            measured_evidence={
                f"{CANDIDATE[0]}/{CANDIDATE[1]}": {
                    "samples": 3, "unsafe_failures": 1},
            })
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    assert decision["selected_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}
    excluded = {
        item.get("route"): item.get("reasons")
        for item in (decision["discovery"] or {}).get("excluded") or []}
    assert "measured_unsafe_action" in (excluded.get(
        f"{CANDIDATE[0]}/{CANDIDATE[1]}") or [])


def test_explicit_unscored_replacement_never_clears_baseline_floor(world):
    """A passing replacement without an accuracy score never qualifies.

    An older durable writer generation may record a passing benchmark verdict
    without a comparable accuracy score (the current writer always scores, so
    the shape is supplied here as validated comparison rows). Discovery
    already refuses such a route: the capability profile's workload floor
    cannot be demonstrated, so it is excluded as ``below_quality_prior``. The
    explicit operator path must not bypass that floor just because the route
    was named: a passing result with no score cannot show it meets the
    baseline, and a baseline whose own score is unrecorded is not a floor to
    relax below.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        rows = load_repeat_task_evidence(db, agent)

    baseline_row = dict(rows[0])
    baseline_row["accuracy"] = None
    replacement_row = {
        **baseline_row,
        "provider": CANDIDATE[0],
        "model": CANDIDATE[1],
        "model_provenance": {
            "provider": CANDIDATE[0], "model": CANDIDATE[1]},
        "evidence_id": "employee-benchmark:test:unscored-replacement",
        "observed_at": _newer(fresh).isoformat(),
        "passed": True,
        "accuracy": None,
    }
    replacement_row.pop("resolved_model", None)
    evidence = [baseline_row, replacement_row]

    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        discovered = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            evidence_rows=evidence)
        explicit = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            candidates=[CANDIDATE], evidence_rows=evidence)

    # Normal discovery cannot admit the unscored route at all.
    assert discovered["route_state"] == STATE_SUPERVISED
    assert discovered["candidate_source"] == "discovered"
    assert discovered["selected_route"] is None
    assert "no_profile_eligible_candidate" in discovered["reasons"]
    assert any(
        "below_quality_prior" in (item.get("reasons") or [])
        for item in discovered["discovery"]["excluded"])

    # Naming the same route explicitly compares it, but it still cannot clear
    # the baseline floor without a score.
    assert explicit["route_state"] == STATE_SUPERVISED
    assert explicit["candidate_source"] == "operator"
    assert explicit["selected_route"] is None
    assert explicit["autonomous_eligible"] is False
    candidate = explicit["comparison"]["candidates"][0]
    assert candidate["passed"] is True
    assert candidate["score"] is None
    assert candidate["evidence_state"] == "failed"
    assert candidate["reasons"] == ["baseline_not_met"]
    assert explicit["comparison"]["ranked"] == []


# --- Validated campaign-writer evidence (the only route evidence) -----------


def test_writer_records_are_the_route_evidence(world):
    """Eligible records come from the ACTUAL writer, end to end.

    A sealed campaign journal, the frozen scoring and the authoritative
    execution completion time produce one digest-sealed record; the loader
    turns that validated record into the comparison row that pins the
    receipt's baseline route. Re-running the writer for the same run
    cannot refresh or duplicate the result.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-writer", *BASELINE, observed_at=fresh)
    stored = world.stored_benchmark_records("exec-writer")
    assert len(stored) == 1
    record = stored[0]
    assert record["authority"] == {
        "producer": bench_evidence.PRODUCER_ID,
        "intake": "server",
        "caller_claims": "rejected",
    }
    assert record["observed_at_source"] == "execution_completion"
    assert record["served_identity"]["provider"] == BASELINE[0]
    assert record["served_identity"]["model"] == BASELINE[1]

    # Idempotency: replaying the same run through a new sealed journal
    # neither duplicates nor refreshes the durable observation.
    from core.employee_benchmark_evidence import (
        open_campaign_transport_journal,
        produce_employee_benchmark_evidence,
    )

    replay = open_campaign_transport_journal(
        campaign_id="heldout-replay", execution_id="exec-writer")
    replay.record_call(
        accepted=True,
        response_identity={"provider": BASELINE[0], "model": BASELINE[1]},
    )
    replay.seal(completed_at=fresh)
    again = produce_employee_benchmark_evidence(
        execution_id="exec-writer",
        observation=_heldout_observation(),
        transport_journal=replay,
        session_factory=world.Session,
    )
    assert again["status"] == "already_recorded", again
    assert world.stored_benchmark_records("exec-writer") == stored

    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        rows = load_repeat_task_evidence(db, agent)
        assert [row["evidence_id"] for row in rows] == [
            f"employee-benchmark:{BENCHMARK_ID}:exec-writer"]
        row = rows[0]
        assert row["source"] == "employee_benchmark"
        assert row["provider"] == BASELINE[0] and row["model"] == BASELINE[1]
        assert row["passed"] is True and row["accuracy"] == 1.0
        assert row["dataset_id"] == BENCHMARK_ID
        assert row["dataset_sha256"] == DATASET_SHA
        assert row["rubric_version"] == RUBRIC
        assert row["observed_at"] == fresh.isoformat()
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    assert decision["selected_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}
    assert decision["autonomous_eligible"] is True


# --- Provider build vs callable route --------------------------------------


ALIAS = ("openai", "gpt-5.4")
ALIAS_BUILD = "gpt-5.4-2026-03"
ALIAS_OTHER_BUILD = "gpt-5.4-2026-07"


def test_versioned_provider_echo_keeps_callable_route_through_durable_read(
        tmp_path):
    """A versioned provider echo is the build of the selected route.

    The campaign's accepted call names the callable route (``gpt-5.4``) while
    the provider echoes a concrete build (``gpt-5.4-2026-03``). Campaign
    finish must record the callable route with the build kept separately; the
    durable writer must validate it; and the validated read must pin the
    callable route — never the provider build — for dispatch.
    """
    world = World(
        tmp_path, baseline_route=ALIAS, baseline_build=ALIAS_BUILD)
    fresh = _utc_now() - timedelta(days=2)
    from core.employee_campaign_intake import (
        complete_campaign_execution,
        record_campaign_evidence,
    )

    # The runner's real finish path: the durable execution is completed with
    # the provider echo, then the campaign-owned journal is assembled from
    # the transport decisions and handed to the production producer.
    assert complete_campaign_execution(
        db_path=world.db_path,
        execution_id="exec-versioned",
        assignment={
            "employee_id": AGENT,
            "tenant_id": TENANT,
            "workspace_id": WORKSPACE,
            "objective": "held-out repeat task",
            "status": "completed",
            "run_id": "run-route-1",
        },
        completed_at=fresh,
        served_identity={"provider": ALIAS[0], "model": ALIAS_BUILD},
    )
    result = record_campaign_evidence(
        db_path=world.db_path,
        execution_id="exec-versioned",
        campaign="employee-heldout-two-domain",
        observation=_heldout_observation(),
        completed_at=fresh,
        decisions=[{
            "kind": "employee_route",
            "accepted": True,
            "attempt_id": "attempt-versioned",
            "requested_route": {
                "provider": ALIAS[0], "model": ALIAS[1]},
            "served_route": {
                "provider": ALIAS[0], "model": ALIAS[1]},
            "response_identity": {
                "provider": ALIAS[0], "model": ALIAS_BUILD},
        }],
    )
    assert result["status"] == "recorded", result
    assert result["served_identity"] == {
        "provider": ALIAS[0], "model": ALIAS[1],
        "resolved_model": ALIAS_BUILD}

    record = world.stored_benchmark_records("exec-versioned")[0]
    assert record["provider"] == ALIAS[0]
    assert record["model"] == ALIAS[1]
    assert record["resolved_model"] == ALIAS_BUILD
    assert record["served_identity"]["model"] == ALIAS[1]
    assert record["served_identity"]["resolved_model"] == ALIAS_BUILD

    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        rows = load_repeat_task_evidence(db, agent)
        assert [row["evidence_id"] for row in rows] == [
            f"employee-benchmark:{BENCHMARK_ID}:exec-versioned"]
        assert rows[0]["provider"] == ALIAS[0]
        assert rows[0]["model"] == ALIAS[1]
        assert rows[0]["resolved_model"] == ALIAS_BUILD
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    assert decision["baseline_route"] == {
        "provider": ALIAS[0], "model": ALIAS[1]}
    assert decision["selected_route"] == {
        "provider": ALIAS[0], "model": ALIAS[1]}
    selected_evidence = decision["comparison"]["selected"]["evidence"]
    assert selected_evidence["model_build"] == ALIAS_BUILD

    # The structured pin names the callable route, not the echoed build: the
    # build is evidence about the route, never a dispatch alias of its own.
    llm = ScriptedLLM(clients=("openai",))
    allowed = filter_route_for_attempt(
        decision["selected_route"], quality=1.0, llm_service=llm,
        workspace_id=WORKSPACE, tenant_id=TENANT, evidence={})
    assert allowed["allowed"] is True, allowed["reasons"]
    assert allowed["pin"] == ALIAS

    # The provider response identity check accepts a build of the pinned
    # route, and still rejects a genuinely different model.
    assert validate_served_identity(ALIAS, {
        "served_route": {"provider": ALIAS[0], "model": ALIAS[1]},
        "resolved_model": ALIAS_BUILD,
    }) == IDENTITY_VERIFIED
    assert validate_served_identity(ALIAS, {
        "served_route": {"provider": ALIAS[0], "model": "gpt-5.5"},
        "resolved_model": "gpt-5.5-2026-03",
    }) == IDENTITY_CONFLICT


def test_genuine_conflicting_echo_and_mismatched_provider_are_rejected(
        tmp_path):
    """Only a version of the accepted route may differ from its alias."""
    world = World(tmp_path)
    fresh = _utc_now() - timedelta(days=2)

    # A different model family is a genuine conflicting echo, not a build.
    family = world.produce_benchmark_evidence(
        "exec-echo-family", *ALIAS, observed_at=fresh,
        echo_model="gpt-5.5-2026-03")
    assert family["status"] == "rejected", family
    assert bench_evidence.REASON_IDENTITY_CONFLICT in family["reasons"]

    # The echo must come from the provider that accepted the route.
    provider = world.produce_benchmark_evidence(
        "exec-echo-provider", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD, echo_provider="other")
    assert provider["status"] == "rejected", provider
    assert bench_evidence.REASON_IDENTITY_CONFLICT in provider["reasons"]

    # Same family is not enough when the accepted route is itself a concrete
    # build: a different build cannot be relabelled as a version of it.
    changed_build = world.produce_benchmark_evidence(
        "exec-echo-build-route", ALIAS[0], ALIAS_BUILD,
        observed_at=fresh, echo_model=ALIAS_OTHER_BUILD)
    assert changed_build["status"] == "rejected", changed_build
    assert bench_evidence.REASON_IDENTITY_CONFLICT in changed_build["reasons"]

    assert world.stored_benchmark_records("exec-echo-family") == []
    assert world.stored_benchmark_records("exec-echo-provider") == []
    assert world.stored_benchmark_records("exec-echo-build-route") == []


def test_alias_alone_cannot_authorize_a_changed_build(tmp_path):
    """A durable build witness must match the provider echo exactly.

    The execution row records the callable route plus the build it observed;
    the journal echoes a different build of the same family. The alias
    matches, but the build does not, so the run is ineligible — family
    membership alone never authorizes a changed build.
    """
    world = World(tmp_path)
    fresh = _utc_now() - timedelta(days=2)
    result = world.produce_benchmark_evidence(
        "exec-changed-build", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD,
        execution_provenance={
            "model_provenance": {
                "provider": ALIAS[0],
                "model": ALIAS[1],
                "resolved_model": ALIAS_OTHER_BUILD,
                "serving_models": [
                    {"provider": ALIAS[0], "model": ALIAS[1]}],
            },
        },
    )
    assert result["status"] == "rejected", result
    assert bench_evidence.REASON_IDENTITY_CONFLICT in result["reasons"]
    assert world.stored_benchmark_records("exec-changed-build") == []


def test_two_latest_builds_under_one_alias_are_ambiguous(tmp_path):
    """The validated read never treats the alias as build continuity.

    Two current observations of the same callable route were served by
    different provider builds. Their route alias is identical, but the build
    conflict makes the evidence ambiguous: no route is pinned and the normal
    supervised path applies.
    """
    world = World(
        tmp_path, baseline_route=ALIAS, baseline_build=ALIAS_BUILD)
    observed_at = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-build-one", *ALIAS, observed_at=observed_at,
        echo_model=ALIAS_BUILD)
    world.add_benchmark_evidence(
        "exec-build-two", *ALIAS, observed_at=observed_at,
        echo_model=ALIAS_OTHER_BUILD)
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert decision["route_state"] == STATE_SUPERVISED
    assert decision["autonomous_eligible"] is False
    assert "ambiguous_evidence" in decision["reasons"]
    candidate = next(
        item for item in decision["comparison"]["candidates"]
        if (item["provider"], item["model"]) == ALIAS)
    assert candidate["evidence_state"] == "insufficient"
    assert candidate["reasons"] == ["model_build_conflict"]


def test_generic_metadata_is_never_route_evidence(world):
    """Generic execution metadata is not benchmark authority.

    The old-style trusted shape (a ``benchmark_identity`` plus free
    ``passed``/``accuracy``/``observed_at`` and a claimed provenance) is
    exactly what the loader no longer trusts: without a validated writer
    record the row contributes no evidence, and a route whose only
    "support" is generic metadata is never selected.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    with world.Session() as db:
        db.add(AgentExecution(
            id="exec-generic", agent_id=AGENT, tenant_id=TENANT,
            workspace_id=WORKSPACE, status="completed",
            input_summary="held-out scored task",
            result_summary="caller-scored benchmark observation",
            completed_at=_newer(fresh),
            metadata_json={
                "benchmark_identity": {
                    "dataset_sha256": DATASET_SHA,
                    "rubric_version": RUBRIC,
                    "task_scope": dict(SCOPE),
                },
                "model_provenance": {
                    "provider": CANDIDATE[0], "model": CANDIDATE[1],
                    "serving_models": [
                        {"provider": CANDIDATE[0], "model": CANDIDATE[1]}],
                },
                "passed": True,
                "accuracy": 0.99,
                "observed_at": _newer(fresh).isoformat(),
            },
        ))
        db.commit()
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        rows = load_repeat_task_evidence(db, agent)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert [row["evidence_id"] for row in rows] == [
        f"employee-benchmark:{BENCHMARK_ID}:exec-baseline"]
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    assert decision["selected_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}
    compared = {
        (route["provider"], route["model"])
        for route in decision["candidate_routes"]}
    assert CANDIDATE not in compared


def test_forged_benchmark_records_are_rejected(world):
    """A caller-injected or altered record is discarded, never scored.

    Both attacks start from a REAL stored record: one swaps the served
    route to the candidate (any mutation breaks the digest), one drops the
    integrity block entirely. Neither may qualify the candidate route, and
    the eligible baseline route is still selected from validated records.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    source_record = world.stored_benchmark_records("exec-baseline")[0]

    swapped = dict(source_record)
    swapped["provider"] = CANDIDATE[0]
    swapped["model"] = CANDIDATE[1]
    swapped["resolved_model"] = CANDIDATE[1]
    swapped["served_identity"] = {
        "provider": CANDIDATE[0], "model": CANDIDATE[1],
        "resolved_model": CANDIDATE[1],
        "source": "provider_response", "identity_source": "transport_journal",
    }
    fabricated = {
        key: value for key, value in source_record.items()
        if key != "integrity"
    }
    fabricated["provider"] = CANDIDATE[0]
    fabricated["model"] = CANDIDATE[1]
    fabricated["resolved_model"] = CANDIDATE[1]
    fabricated["served_identity"] = {
        "provider": CANDIDATE[0], "model": CANDIDATE[1],
        "resolved_model": CANDIDATE[1],
        "source": "provider_response", "identity_source": "transport_journal",
    }
    with world.Session() as db:
        db.add(AgentExecution(
            id="exec-forged", agent_id=AGENT, tenant_id=TENANT,
            workspace_id=WORKSPACE, status="completed",
            input_summary="held-out campaign run",
            result_summary="campaign observation",
            completed_at=_newer(fresh),
            metadata_json={"benchmark_evidence": [swapped, fabricated]},
        ))
        db.commit()

    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        row = db.get(AgentExecution, "exec-forged")
        inspection = bench_evidence.inspect_employee_benchmark_evidence(
            row.metadata_json)
        assert inspection["records"] == []
        rejected = {
            item["evidence_id"]: set(item["reasons"])
            for item in inspection["rejected"]}
        assert set(rejected) == {
            source_record["evidence_id"]}
        assert rejected[source_record["evidence_id"]] == {
            bench_evidence.REASON_METADATA_TAMPERED}
        rows = load_repeat_task_evidence(db, agent)
        # The forged claim named the candidate route with a fresh pass: it
        # must not be discoverable, and the validated baseline still pins.
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment())
    assert [item["evidence_id"] for item in rows] == [
        f"employee-benchmark:{BENCHMARK_ID}:exec-baseline"]
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    assert decision["selected_route"] == {
        "provider": BASELINE[0], "model": BASELINE[1]}
    compared = {
        (route["provider"], route["model"])
        for route in decision["candidate_routes"]}
    assert CANDIDATE not in compared


def test_operator_constraint_is_compared_exactly_not_substituted(world):
    """An explicit operator route constraint is never replaced by discovery.

    The candidate's benchmark run failed (discovery would never propose it),
    but the operator asked about THIS route: it is compared exactly as
    proposed, its negative evidence is valid and the outcome is supervision —
    the eligible baseline is never silently substituted for it.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh),
        failed_case="reconcile")
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        decision = resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            candidates=[CANDIDATE])
    assert decision["route_state"] == STATE_SUPERVISED
    assert decision["candidate_source"] == "operator"
    assert decision["selected_route"] is None
    assert decision["candidate_routes"] == [
        {"provider": CANDIDATE[0], "model": CANDIDATE[1]}]
    assert any(
        "evidence_not_passed" in reasons
        for candidate in decision["comparison"]["candidates"]
        for reasons in [candidate["reasons"]])


# --- Normal assignment creation path ----------------------------------------


APPROVAL_TASK = "cfg-open-approval"
DIGEST_TASK = "cfg-email-digest"
REVOKED_TASK = "cfg-revoked-open-approval"
UNRELATED_SCOPE = {
    "task_policy": "Summarize unread email threads for the digest.",
    "decision_options": ["SEND", "HOLD"],
    "subject_field": "Thread",
}


def _resolved_document_source(path) -> dict:
    """A server-resolved document source (the shape the planner accepts)."""
    path.write_text(json.dumps({"records": []}))
    return {
        "kind": "document", "path": str(path),
        "resource_id": "route-doc", "dataset_name": "route-doc",
        "source_version": "v1",
        "coverage": {"known": True, "truncated": False},
        "internal_fixture": True,
    }


def _registry_file(tmp_path) -> str:
    """A server-controlled qualification registry with registered tasks."""
    path = tmp_path / "assessment-qualification.json"
    path.write_text(json.dumps({
        "schema": "atom-assessment-qualification-1",
        "configurations": [
            {
                "id": APPROVAL_TASK,
                "capability": "canvas_assessment.model_judgment",
                "provider": "openai", "model": "gpt-x",
                "status": "qualified", "revoked": False,
                "scope": dict(SCOPE),
            },
            {
                "id": DIGEST_TASK,
                "capability": "canvas_assessment.model_judgment",
                "provider": "openai", "model": "gpt-x",
                "status": "qualified", "revoked": False,
                "scope": dict(UNRELATED_SCOPE),
            },
            {
                "id": REVOKED_TASK,
                "capability": "canvas_assessment.model_judgment",
                "provider": "openai", "model": "gpt-x",
                "status": "qualified", "revoked": True,
                "scope": dict(SCOPE),
            },
        ],
    }))
    return str(path)


def test_registered_workload_scope_is_server_resolved(tmp_path, monkeypatch):
    """Only the task REFERENCE is caller input; the scope is server-owned."""
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    from core.canvas_capability_service import registered_workload_scope

    scope = registered_workload_scope(APPROVAL_TASK)
    assert scope == {
        "task_policy": SCOPE["task_policy"],
        "decision_options": list(SCOPE["decision_options"]),
        "subject_field": SCOPE["subject_field"],
    }
    # An unknown reference stays unknown, and a revoked registration no
    # longer defines the workload — both leave the assignment supervised.
    assert registered_workload_scope("cfg-unknown") is None
    assert registered_workload_scope(REVOKED_TASK) is None
    assert registered_workload_scope("") is None


def test_registered_task_scope_requires_the_registered_work(
        tmp_path, monkeypatch):
    """Naming a registered task is not authority over its workload.

    The canonical scope is stamped only when the caller's own work restates
    the registered task's policy text. The SAME valid registration ID
    paired with an unrelated objective stays workload-unknown, exactly like
    an unknown reference — the normal supervised path. The check is
    deterministic caller-text matching: no model, no scoring, no
    model-specific branching.
    """
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    from core.canvas_capability_service import registered_workload_scope

    policy = SCOPE["task_policy"]
    expected = {
        "task_policy": SCOPE["task_policy"],
        "decision_options": list(SCOPE["decision_options"]),
        "subject_field": SCOPE["subject_field"],
    }
    # The caller's work restates the registered policy: identity holds,
    # whether the restatement is verbatim or embedded in a larger objective.
    assert registered_workload_scope(APPROVAL_TASK, work=policy) == expected
    assert registered_workload_scope(
        APPROVAL_TASK, work=f"Run the registered repeat task: {policy}",
    ) == expected
    assert registered_workload_scope(
        APPROVAL_TASK, work=policy.casefold()) == expected
    # A conflicting variant of the policy is NOT the registered workload:
    # the identity is load-bearing, not interchangeable prose.
    assert registered_workload_scope(
        APPROVAL_TASK,
        work="Deliver an inaccurate, uncited industrial quote from the "
             "unauthorized price list under untaught terms.",
    ) is None
    # The SAME valid registration ID with unrelated work fails closed to
    # workload-unknown.
    assert registered_workload_scope(
        APPROVAL_TASK, work="summarize unread email threads") is None
    # Without work there is nothing to verify (pure registry lookup), and
    # the validation never rescues an unknown reference.
    assert registered_workload_scope(APPROVAL_TASK) == expected
    assert registered_workload_scope("cfg-unknown", work=policy) is None
    assert registered_workload_scope(REVOKED_TASK, work=policy) is None


def test_plan_persists_server_scope_and_never_a_caller_claim(
        tmp_path, monkeypatch):
    """The durable plan's workload scope is the server-derived identity.

    The caller's asserted scope material travels only as ordinary request
    payload (provenance); the persisted ``workload_scope`` comes solely from
    the server's registered-task lookup, and no request field reaches it.
    """
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    from core.canvas_capability_service import registered_workload_scope

    source = tmp_path / "records.json"
    source.write_text(json.dumps({"records": []}))
    caller_claim = {"task_policy": "Caller assertion", "subject_field": "X"}
    plan = plan_assignment(
        objective="held-out repeat task",
        sources=[_resolved_document_source(source)],
        calculation={"expression": "2*10", "output_unit": "USD"},
        authorized_actions=["retrieve", "calculate"],
        employee_id=OWNER, workspace_id=WORKSPACE, tenant_id=TENANT,
        agent_id=AGENT,
        workload_scope=registered_workload_scope(APPROVAL_TASK),
        provenance={
            "requester_id": OWNER,
            # The caller tries to assert the workload identity itself.
            "workload_scope": caller_claim,
        },
    )
    assert plan["workload_scope"] == registered_workload_scope(APPROVAL_TASK)
    # The caller's claim is preserved as untrusted payload only.
    assert plan["provenance"]["workload_scope"] == caller_claim
    # Without a registered reference, the plan stays workload-unknown.
    unknown = plan_assignment(
        objective="ad-hoc task",
        sources=[_resolved_document_source(source)],
        calculation={"expression": "2*10", "output_unit": "USD"},
        authorized_actions=["retrieve", "calculate"],
        employee_id=OWNER, workspace_id=WORKSPACE, tenant_id=TENANT,
        agent_id=AGENT,
    )
    assert "workload_scope" not in unknown or unknown["workload_scope"] is None


def test_entry_point_discovers_replacement_for_registered_task(
        world, tmp_path, monkeypatch):
    """Replacement selection through the normal entry point, no operator pin.

    The assignment plan is composed by the server's registered-task path
    (``plan_assignment`` + the server-owned scope lookup) — the workload
    scope is never inserted by a fixture. With no operator pin at all, the
    fresh eligible replacement is discovered from the trusted benchmark
    cohort and dispatched strictly.
    """
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    from core.canvas_capability_service import registered_workload_scope

    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh))
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": CANDIDATE[0], "model": CANDIDATE[1]},
            "resolved_model": "gpt-5.5-mini-2026-01",
        })
    log = DecisionLog(tmp_path / "decisions.json")
    plan = plan_assignment(
        objective="held-out repeat task",
        sources=[_resolved_document_source(tmp_path / "records.json")],
        calculation={"expression": "2*10", "output_unit": "USD"},
        authorized_actions=["retrieve", "calculate"],
        employee_id=OWNER, workspace_id=WORKSPACE, tenant_id=TENANT,
        agent_id=AGENT,
        workload_scope=registered_workload_scope(APPROVAL_TASK),
        provenance={"requester_id": OWNER},
    )
    record = {
        "run_id": "run-route-1",
        "task_revision": {"task_revision": 1, "unresolved": []},
        "assignment": plan,
    }
    executor = stub_executor(world, log, record)

    from api.assignment_routes import _advance_employee_work

    rounds = asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=None))

    assert rounds
    # The server-persisted scope matched the receipt binding, and discovery
    # selected the replacement without any operator pin or candidate list.
    assert record["assignment"]["workload_scope"] == dict(
        registered_workload_scope(APPROVAL_TASK))
    assert calls[0]["provider_model"] == CANDIDATE
    assert calls[0]["strict_pin"] is True
    entries = log.route_entries()
    assert entries
    final = entries[-1]
    assert final["route_state"] == STATE_PINNED
    assert final["candidate_source"] == "discovered"
    assert final["selected_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    assert final["identity_state"] == IDENTITY_VERIFIED
    assert final["autonomous_eligible"] is True


def test_entry_point_supervises_unrelated_registered_task(
        world, tmp_path, monkeypatch):
    """A registered UNRELATED task never inherits the receipt baseline."""
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    from core.canvas_capability_service import registered_workload_scope

    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "exec-candidate", *CANDIDATE, observed_at=_newer(fresh))
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": "other", "model": "legacy-model"},
        })
    log = DecisionLog(tmp_path / "decisions.json")
    plan = plan_assignment(
        objective="summarize unread email threads",
        sources=[_resolved_document_source(tmp_path / "records.json")],
        calculation={"expression": "2*10", "output_unit": "USD"},
        authorized_actions=["retrieve", "calculate"],
        employee_id=OWNER, workspace_id=WORKSPACE, tenant_id=TENANT,
        agent_id=AGENT,
        workload_scope=registered_workload_scope(DIGEST_TASK),
        provenance={"requester_id": OWNER},
    )
    record = {
        "run_id": "run-route-1",
        "task_revision": {"task_revision": 1, "unresolved": []},
        "assignment": plan,
    }
    executor = stub_executor(world, log, record)

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=None))

    # The server-persisted scope is the digest task's, the caller's routing
    # is untouched, and the outcome is the normal supervised path.
    assert record["assignment"]["workload_scope"] == dict(
        registered_workload_scope(DIGEST_TASK))
    assert calls[0]["provider_model"] is None
    assert calls[0].get("strict_pin") is None
    entries = log.route_entries()
    assert entries
    final = entries[-1]
    assert final["route_state"] == STATE_SUPERVISED
    assert "workload_scope_mismatch" in final["reasons"]
    assert final["autonomous_eligible"] is False


def test_entry_point_without_registered_task_stays_workload_unknown(
        world, tmp_path, monkeypatch):
    """An ordinary ad-hoc assignment (no registered task) is supervised.

    Even with fresh passing evidence on the receipt's benchmark, an
    assignment the server composed without a workload scope is workload-
    unknown: the baseline is never inherited.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": "other", "model": "legacy-model"},
        })
    log = DecisionLog(tmp_path / "decisions.json")
    plan = plan_assignment(
        objective="ad-hoc task",
        sources=[_resolved_document_source(tmp_path / "records.json")],
        calculation={"expression": "2*10", "output_unit": "USD"},
        authorized_actions=["retrieve", "calculate"],
        employee_id=OWNER, workspace_id=WORKSPACE, tenant_id=TENANT,
        agent_id=AGENT,
        provenance={"requester_id": OWNER},
    )
    record = {
        "run_id": "run-route-1",
        "task_revision": {"task_revision": 1, "unresolved": []},
        "assignment": plan,
    }
    executor = stub_executor(world, log, record)

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=("other", "legacy-model")))

    assert calls[0]["provider_model"] == ("other", "legacy-model")
    assert calls[0].get("strict_pin") is None
    entries = log.route_entries()
    assert entries
    final = entries[-1]
    assert final["route_state"] == STATE_SUPERVISED
    assert "workload_scope_unknown" in final["reasons"]


def _api_discovery_fake(calls: list, routing: dict):
    """A scripted transport for the NORMAL from-objective creation path.

    The proposal is the same shape the model proposal validator/compiler
    accepts: one scoped evidence read per authorized source.
    """
    from core.llm.pinned_planning import routing_snapshot

    async def fake_discovery(context, **kwargs):
        calls.append(kwargs)
        provenance: dict = {}
        for key, value in (
                ("mode", "pinned" if kwargs.get("provider_model") else "unpinned"),
                ("requested_route", (
                    {"provider": kwargs["provider_model"][0],
                     "model": kwargs["provider_model"][1]}
                    if kwargs.get("provider_model") else None)),
                ("served_route", routing.get("served_route")),
                ("resolved_model", routing.get("resolved_model")),
        ):
            if value is not None:
                provenance[key] = value
        return {
            "proposal": {
                "proposal_kind": "evidence_read",
                "reason": "scoped read of authorized evidence",
                "evidence_reads": [
                    {"step_id": f"evidence-{index}",
                     "title": "Read authorized source",
                     "source_id": source["source_id"]}
                    for index, source in enumerate(
                        context.get("sources") or [], 1)
                ],
            },
            "source": "model",
            "technical_fallback": False,
            "errors": [],
            "attempt_id": "attempt-1",
            "routing": routing_snapshot(provenance),
        }

    return fake_discovery


def test_api_registered_task_persists_scope_and_routes_without_operator_pin(
        route_env, tmp_path, monkeypatch):
    """The NORMAL assignment creation path, end to end over the public API.

    The assignment is created through ``POST /api/assignments/from-objective``
    (the registered server-owned task path): the server resolves and
    persists the workload scope from its own registry — the caller only
    names the task and actually asks for the registered work, and a
    caller-asserted scope in the request payload never qualifies. With no
    operator pin configured, candidate discovery selects the fresh eligible
    replacement and dispatches it strictly. The SAME valid registration ID
    named alongside an unrelated objective stamps nothing: the assignment
    stays workload-unknown and the normal supervised path applies.
    """
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    from core.canvas_capability_service import registered_workload_scope

    world = World(
        tmp_path,
        session_factory=route_env["factory"],
        ids={
            "tenant": "tenant-1", "workspace": "ws-1",
            "supervisor": "route-api-supervisor", "admin": "route-api-admin",
            "agent": "route-api-agent",
        },
    )
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "api-exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "api-exec-candidate", *CANDIDATE, observed_at=_newer(fresh))

    source = tmp_path / "records.json"
    source.write_text(json.dumps({"records": []}))
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": CANDIDATE[0], "model": CANDIDATE[1]},
            "resolved_model": "gpt-5.5-mini-2026-01",
        })
    # Replace the entry-fake discovery with the normal-path compiling
    # proposal; the adaptation fake is kept. The real executor calls
    # open_unresolved_questions too, so it must keep returning a LIST.
    import core.task_lifecycle as task_lifecycle

    monkeypatch.setattr(
        task_lifecycle, "open_unresolved_questions", lambda record: [])
    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work",
        _api_discovery_fake(calls, {
            "served_route": {"provider": CANDIDATE[0], "model": CANDIDATE[1]},
            "resolved_model": "gpt-5.5-mini-2026-01",
        }))
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *a, **k: ScriptedLLM(clients=("openai",)))

    # The caller asserts a workload scope of its own in the request payload;
    # the registered task reference plus the registered WORK are the only
    # accepted identity sources.
    caller_claim = {"task_policy": "Caller assertion", "subject_field": "X"}
    response = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": (
                "Run the registered repeat task: " + SCOPE["task_policy"]),
            "agent_id": "route-api-agent",
            "sources": [{"path": str(source)}],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
            "registered_task_id": APPROVAL_TASK,
            "task_context": {"workload_scope": caller_claim},
        })
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    plan = route_env["lifecycle"].get_assignment(run_id)
    # The persisted workload scope is the server-derived registered identity;
    # the caller's asserted scope did not qualify it.
    assert plan["workload_scope"] == dict(
        registered_workload_scope(APPROVAL_TASK))
    assert plan["workload_scope"] != caller_claim

    entries = [
        entry for entry in route_env["runs"].get_decisions(run_id)
        if str(entry.get("kind") or "") == ROUTE_DECISION_KIND]
    assert entries, "a durable route decision must be recorded"
    final = entries[-1]
    assert final["route_state"] == STATE_PINNED, final.get("reasons")
    assert final["candidate_source"] == "discovered"
    assert final["selected_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    assert final["identity_state"] == IDENTITY_VERIFIED
    assert final["autonomous_eligible"] is True
    # The dispatch was strict and used no operator pin. calls[0] is the
    # from-objective route's initial proposal (no operator pin configured);
    # the pinned strict dispatch is the advance round's discovery call.
    assert calls, "the scripted transport must have been called"
    dispatch_calls = [call for call in calls if "strict_pin" in call]
    assert dispatch_calls, calls
    assert dispatch_calls[0]["provider_model"] == CANDIDATE
    assert dispatch_calls[0]["strict_pin"] is True

    # The SAME valid registration ID named alongside an unrelated objective:
    # naming the qualification task is not authority over its workload. The
    # server stamps nothing, the assignment stays workload-unknown on the
    # normal supervised path, and no qualification route or strict dispatch
    # is ever produced for the unrelated work.
    calls.clear()
    unrelated = route_env["client"].post(
        "/api/assignments/from-objective",
        json={
            "objective": "summarize unread email threads",
            "agent_id": "route-api-agent",
            "sources": [{"path": str(source)}],
            "authorized_actions": ["retrieve", "calculate"],
            "use_model": True,
            "registered_task_id": APPROVAL_TASK,
        })
    assert unrelated.status_code == 200, unrelated.text
    unrelated_run = unrelated.json()["run_id"]
    plan = route_env["lifecycle"].get_assignment(unrelated_run)
    assert not plan.get("workload_scope"), plan.get("workload_scope")
    entries = [
        entry for entry in route_env["runs"].get_decisions(unrelated_run)
        if str(entry.get("kind") or "") == ROUTE_DECISION_KIND]
    assert entries
    final = entries[-1]
    assert final["route_state"] == STATE_SUPERVISED
    assert "workload_scope_unknown" in final["reasons"]
    assert final["autonomous_eligible"] is False
    # The durable marker binds the supervised outcome to the plan itself.
    assert (plan.get("repeat_task_route") or {}).get(
        "route_state") == STATE_SUPERVISED
    # The normal supervised path: no strict pin was forced onto any call.
    assert not any(call.get("strict_pin") for call in calls)


def test_api_start_assignment_registered_task_twins(
        route_env, tmp_path, monkeypatch):  # noqa: F811 — imported fixture
    """The direct creation path, end to end over the public API.

    ``POST /api/assignments`` composes the plan itself from the accepted
    objective. The SAME valid registration ID (``APPROVAL_TASK``) is proved
    twice at this boundary: when the objective restates the registered
    workload the server stamps its canonical scope and the durable
    repeat-task route resolves against the qualification baseline; when the
    same ID is named alongside an unrelated objective nothing is stamped —
    the assignment stays workload-unknown, the durable route decision
    requires supervision, and no qualification dispatch or effect follows.
    """
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    from core.canvas_capability_service import registered_workload_scope

    world = World(
        tmp_path,
        session_factory=route_env["factory"],
        ids={
            "tenant": "tenant-1", "workspace": "ws-1",
            "supervisor": "route-api-supervisor", "admin": "route-api-admin",
            "agent": "route-api-agent",
        },
    )
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "api-exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "api-exec-candidate", *CANDIDATE, observed_at=_newer(fresh))

    source = tmp_path / "records.json"
    source.write_text(json.dumps({"records": []}))
    calls: list = []
    # Scripted transports only: the advance round's proposal/adaptation
    # consumers are replaced, so no code path under test can reach a live
    # provider even if the job ends in an unexpected state.
    _install_entry_fakes(monkeypatch, calls=calls, routing={})
    import core.task_lifecycle as task_lifecycle

    monkeypatch.setattr(
        task_lifecycle, "open_unresolved_questions", lambda record: [])
    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work",
        _api_discovery_fake(calls, {
            "served_route": {"provider": CANDIDATE[0], "model": CANDIDATE[1]},
            "resolved_model": "gpt-5.5-mini-2026-01",
        }))
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *a, **k: ScriptedLLM(clients=("openai",)))

    def _create(objective: str):
        return route_env["client"].post("/api/assignments", json={
            "objective": objective,
            "agent_id": "route-api-agent",
            "sources": [{"kind": "document", "path": str(source)}],
            "deliverables": [{
                "kind": "document",
                "description": "Registered repeat task decisions",
                "content": (
                    "Approval decisions grounded in the authorized "
                    "records."),
            }],
            "calculation": {"expression": "2*10", "output_unit": "USD"},
            "registered_task_id": APPROVAL_TASK,
        })

    def _route_entries(run_id: str):
        return [
            entry
            for entry in route_env["runs"].get_decisions(run_id)
            if str(entry.get("kind") or "") == ROUTE_DECISION_KIND]

    # Matching twin: the objective IS the registered workload, so the
    # server-stamped canonical scope qualifies the durable route resolution
    # (discovery selects the fresh eligible replacement, no operator pin).
    matching = _create(
        "Run the registered repeat task: " + SCOPE["task_policy"])
    assert matching.status_code == 200, matching.text
    matching_run = matching.json()["run_id"]
    plan = route_env["lifecycle"].get_assignment(matching_run)
    assert plan["workload_scope"] == dict(
        registered_workload_scope(APPROVAL_TASK))

    advanced = route_env["client"].post(
        f"/api/assignments/{matching_run}/advance", json={"use_model": True})
    assert advanced.status_code == 200, advanced.text
    entries = _route_entries(matching_run)
    assert entries, "a durable route decision must be recorded"
    final = entries[-1]
    assert final["route_state"] == STATE_PINNED, final.get("reasons")
    assert final["candidate_source"] == "discovered"
    assert final["selected_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    plan = route_env["lifecycle"].get_assignment(matching_run)
    assert (plan.get("repeat_task_route") or {}).get(
        "route_state") == STATE_PINNED

    # Unrelated twin: the SAME valid registration ID names a workload the
    # caller is not asking for. Nothing is stamped and no qualification
    # route, dispatch or effect follows — the normal supervised path.
    calls.clear()
    unrelated = _create("summarize unread email threads")
    assert unrelated.status_code == 200, unrelated.text
    unrelated_run = unrelated.json()["run_id"]
    plan = route_env["lifecycle"].get_assignment(unrelated_run)
    assert not plan.get("workload_scope"), plan.get("workload_scope")

    advanced = route_env["client"].post(
        f"/api/assignments/{unrelated_run}/advance", json={"use_model": True})
    assert advanced.status_code == 200, advanced.text
    entries = _route_entries(unrelated_run)
    assert entries
    final = entries[-1]
    assert final["route_state"] == STATE_SUPERVISED
    assert "workload_scope_unknown" in final["reasons"]
    assert final["autonomous_eligible"] is False
    plan = route_env["lifecycle"].get_assignment(unrelated_run)
    assert (plan.get("repeat_task_route") or {}).get(
        "route_state") == STATE_SUPERVISED
    # No strict qualification dispatch was forced onto any scripted call.
    assert not any(call.get("strict_pin") for call in calls)


# --- Compiled-work contract (server-owned) -----------------------------------


def _composed_plan(tmp_path, *, objective: str, deliverable: dict) -> dict:
    """A server-composed plan whose steps come from the caller descriptors."""
    from core.canvas_capability_service import registered_workload_scope

    return plan_assignment(
        objective=objective,
        sources=[_resolved_document_source(tmp_path / "records.json")],
        deliverables=[dict(deliverable, path=str(tmp_path / "out.md"))],
        calculation={"expression": "2*10", "output_unit": "USD"},
        authorized_actions=["retrieve", "calculate", "present"],
        employee_id=OWNER, workspace_id=WORKSPACE, tenant_id=TENANT,
        agent_id=AGENT,
        workload_scope=registered_workload_scope(APPROVAL_TASK),
        provenance={"requester_id": OWNER},
    )


def test_compiled_work_contract_binds_the_registered_task(
        tmp_path, monkeypatch):
    """The compiled work — not the caller's objective — satisfies the contract.

    The exact valid registration ID and the registered objective can still
    compile UNRELATED work, because the server composes the actual steps
    from the caller's descriptors. The server-owned contract rejects
    compiled work that performs a different registered task's workload
    (the stamp is stripped, the plan stays workload-unknown), binds the
    validated work by fingerprint, and fails closed when the plan changes
    or carries no compiled steps at all.
    """
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    from core.canvas_capability_service import (
        bind_compiled_registered_work,
        compiled_work_contract,
        compiled_work_fingerprint,
        registered_workload_scope,
    )

    objective = "Run the registered repeat task: " + SCOPE["task_policy"]
    unrelated = {
        "kind": "document",
        "description": UNRELATED_SCOPE["task_policy"],
        "content": UNRELATED_SCOPE["task_policy"],
    }
    plan = _composed_plan(tmp_path, objective=objective, deliverable=unrelated)
    # The wording gate alone passed: the stamped scope is on the composed
    # plan. The compiled-work hold strips it before the run is created.
    assert plan["workload_scope"] == dict(registered_workload_scope(APPROVAL_TASK))
    bind_compiled_registered_work(plan, APPROVAL_TASK)
    assert not plan.get("workload_scope"), plan.get("workload_scope")
    assert "workload_work" not in plan

    # Registered work compiles: the stamp survives and the validated steps
    # are fingerprint-bound on the plan.
    registered = {
        "kind": "document",
        "description": SCOPE["task_policy"],
        "content": SCOPE["task_policy"],
    }
    stamped = _composed_plan(
        tmp_path, objective=objective, deliverable=registered)
    bind_compiled_registered_work(stamped, APPROVAL_TASK)
    assert stamped["workload_scope"] == dict(
        registered_workload_scope(APPROVAL_TASK))
    binding = stamped.get("workload_work")
    assert binding and binding["task_id"] == APPROVAL_TASK
    assert binding["compiled_fingerprint"] == compiled_work_fingerprint(stamped)

    # The SAME compiled work still satisfies the contract...
    assert compiled_work_contract(
        stamped["workload_scope"], stamped, binding=binding)["ok"]
    # ...a plan change does not: the fingerprint no longer matches.
    altered = {
        **stamped,
        "steps": [
            dict(step, adapter="email.draft")
            if step.get("adapter") == "artifact.document" else dict(step)
            for step in stamped["steps"]
        ],
    }
    check = compiled_work_contract(
        stamped["workload_scope"], altered, binding=binding)
    assert not check["ok"]
    assert "compiled_work_changed" in check["reasons"]
    # Without compiled steps there is nothing the contract can bind.
    empty = dict(stamped, steps=[])
    check = compiled_work_contract(
        stamped["workload_scope"], empty, binding=binding)
    assert not check["ok"]
    assert "compiled_work_missing" in check["reasons"]


def _compiled_gate_assignment():
    """A stamped plan with real compiled steps for the effect-gate tests."""
    return {
        "assignment_id": "asg-route-1",
        "employee_id": OWNER,
        "provenance": {"agent_id": AGENT, "user_id": OWNER},
        "workload_scope": dict(SCOPE),
        "steps": [{
            "step_id": "deliverable-1",
            "title": "Render the registered approval decisions",
            "operation_type": "present",
            "adapter": "artifact.document",
            "depends_on": [],
            "inputs": {
                "content": (
                    "Approval decisions grounded in the authorized "
                    "records."),
            },
            "effect": "local",
        }],
    }


def test_effect_gate_revalidates_compiled_work_before_effect(
        world, tmp_path, monkeypatch):
    """Unchanged compiled work: the effect claim proceeds as before.

    The stamp-time binding matches the durable steps, so the compiled-work
    half of the effect gate passes and the (fresh, verified) route-evidence
    half still decides the outcome.
    """
    _prepare_gate(world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision("run-route-1", {
        "kind": ROUTE_DECISION_KIND,
        "agent_id": AGENT,
        "route_state": STATE_PINNED,
        "selected_route": {"provider": BASELINE[0], "model": BASELINE[1]},
        "identity_state": IDENTITY_VERIFIED,
        "autonomous_eligible": True,
    })
    from core.assignment_executor import AssignmentExecutor
    from core.canvas_capability_service import compiled_work_binding

    assignment = _compiled_gate_assignment()
    binding = compiled_work_binding(APPROVAL_TASK, assignment)
    assert binding is not None
    assignment["workload_work"] = binding
    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        assert executor._autonomy_gate(
            assignment, _gate_step(), run_id="run-route-1") is None


def test_effect_gate_supervises_compiled_work_change_after_restart(
        world, tmp_path, monkeypatch):
    """A plan change (re-derived after a restart) cannot claim the effect.

    The durable steps no longer match the stamp-time fingerprint and their
    substance performs the UNRELATED registered task's work: the compiled
    work fails the server-owned contract and the effect claim is demoted to
    human approval before anything autonomous happens.
    """
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))
    _prepare_gate(world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision("run-route-1", {
        "kind": ROUTE_DECISION_KIND,
        "agent_id": AGENT,
        "route_state": STATE_PINNED,
        "identity_state": IDENTITY_VERIFIED,
        "autonomous_eligible": True,
    })
    from core.assignment_executor import AssignmentExecutor
    from core.canvas_capability_service import compiled_work_binding

    assignment = _compiled_gate_assignment()
    binding = compiled_work_binding(APPROVAL_TASK, assignment)
    assignment["workload_work"] = binding
    # The plan changed after the stamp: the compiled work now performs the
    # digest task's registered workload.
    assignment["steps"][0]["title"] = (
        "Render " + UNRELATED_SCOPE["task_policy"])
    assignment["steps"][0]["inputs"]["content"] = UNRELATED_SCOPE["task_policy"]
    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        denial = executor._autonomy_gate(
            assignment, _gate_step(), run_id="run-route-1")
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert denial["source"] == "repeat_task_route_recheck"
    assert "compiled work" in denial["reason"]
    assert "compiled_work_changed" in denial["reason"]
    assert "compiled_work_conflict" in denial["reason"]


def test_api_registered_task_matching_objective_unrelated_compiled_work(
        route_env, tmp_path, monkeypatch):  # noqa: F811 — imported fixture
    """The exact valid ID AND objective of the positive twin — unrelated work.

    The caller restates the registered workload and names the valid task,
    yet the descriptors it submits compile the UNRELATED registered task's
    work. The server-owned compiled-work contract strips the stamp before
    the run is created: the plan stays workload-unknown, the durable route
    decision requires supervision, the marker binds that outcome, and no
    qualification dispatch or effect follows. The wording-only gate alone
    would have stamped the scope and dispatched the qualification route.
    """
    monkeypatch.setenv(
        "ATOM_ASSESSMENT_QUALIFICATION_FILE", _registry_file(tmp_path))

    world = World(
        tmp_path,
        session_factory=route_env["factory"],
        ids={
            "tenant": "tenant-1", "workspace": "ws-1",
            "supervisor": "route-api-supervisor", "admin": "route-api-admin",
            "agent": "route-api-agent",
        },
    )
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "api-exec-baseline", *BASELINE, observed_at=fresh)
    world.add_benchmark_evidence(
        "api-exec-candidate", *CANDIDATE, observed_at=_newer(fresh))

    source = tmp_path / "records.json"
    source.write_text(json.dumps({"records": []}))
    calls: list = []
    # Scripted transports only: no code path under test can reach a live
    # provider even if the job ends in an unexpected state.
    _install_entry_fakes(monkeypatch, calls=calls, routing={})
    import core.task_lifecycle as task_lifecycle

    monkeypatch.setattr(
        task_lifecycle, "open_unresolved_questions", lambda record: [])
    monkeypatch.setattr(
        "api.assignment_routes.propose_employee_work",
        _api_discovery_fake(calls, {
            "served_route": {"provider": CANDIDATE[0], "model": CANDIDATE[1]},
            "resolved_model": "gpt-5.5-mini-2026-01",
        }))
    monkeypatch.setattr(
        "api.assignment_routes._employee_llm",
        lambda *a, **k: ScriptedLLM(clients=("openai",)))

    # EXACTLY the positive twin's task ID and objective; only the compiled
    # work differs — the deliverable compiles the digest task's workload.
    response = route_env["client"].post("/api/assignments", json={
        "objective": (
            "Run the registered repeat task: " + SCOPE["task_policy"]),
        "agent_id": "route-api-agent",
        "sources": [{"kind": "document", "path": str(source)}],
        "deliverables": [{
            "kind": "document",
            "description": UNRELATED_SCOPE["task_policy"],
            "content": UNRELATED_SCOPE["task_policy"],
        }],
        "calculation": {"expression": "2*10", "output_unit": "USD"},
        "registered_task_id": APPROVAL_TASK,
    })
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    plan = route_env["lifecycle"].get_assignment(run_id)
    # The compiled work performs a different registered task: nothing is
    # stamped and no fingerprint binding is ever written.
    assert not plan.get("workload_scope"), plan.get("workload_scope")
    assert not plan.get("workload_work")

    advanced = route_env["client"].post(
        f"/api/assignments/{run_id}/advance", json={"use_model": True})
    assert advanced.status_code == 200, advanced.text
    entries = [
        entry for entry in route_env["runs"].get_decisions(run_id)
        if str(entry.get("kind") or "") == ROUTE_DECISION_KIND]
    assert entries, "a durable route decision must be recorded"
    final = entries[-1]
    assert final["route_state"] == STATE_SUPERVISED
    assert "workload_scope_unknown" in final["reasons"]
    assert final["autonomous_eligible"] is False
    plan = route_env["lifecycle"].get_assignment(run_id)
    # The durable marker binds the supervised outcome to the plan itself.
    assert (plan.get("repeat_task_route") or {}).get(
        "route_state") == STATE_SUPERVISED
    # The normal supervised path: no strict qualification dispatch was
    # forced onto any scripted call, and no route/effect is authorized.
    assert not any(call.get("strict_pin") for call in calls)


def test_route_marker_passes_assignment_plan_validation():
    """The durable marker is written through the validated plan write path."""
    from core.assignment_plan import validate_assignment

    assignment = {
        "schema_version": 1,
        "assignment_id": "asg-marker-1",
        "objective": "held-out repeat task",
        "status": "planned",
        "steps": [{
            "step_id": "s-1",
            "operation_type": "outbound",
            "adapter": "crm.update_record",
            "status": "pending",
            "effect": "external",
        }],
        "repeat_task_route": {
            "schema": "atom-repeat-task-route-marker-1",
            "kind": ROUTE_DECISION_KIND,
            "agent_id": AGENT,
            "route_state": STATE_PINNED,
            "recorded_at": _utc_now().isoformat(),
        },
    }
    validate_assignment(assignment)


def test_entry_point_marker_write_failure_keeps_log_applicability(
        world, tmp_path, monkeypatch):
    """A failed durable marker write must not silently erase the record.

    The decision log remains the applicability source: the route decision is
    still recorded, and the effect gate still demotes stale evidence.
    """
    fresh = _utc_now() - timedelta(days=2)
    world.add_benchmark_evidence(
        "exec-baseline", *BASELINE, observed_at=fresh)
    calls: list = []
    _install_entry_fakes(
        monkeypatch, calls=calls,
        routing={
            "served_route": {"provider": BASELINE[0], "model": BASELINE[1]},
        })
    log = DecisionLog(tmp_path / "decisions.json")
    record = _assignment_record()

    def failing_mutate(run_id, compute, *, rationale=""):
        raise RuntimeError("plan write unavailable")

    runs = SimpleNamespace(
        _sessions=lambda: world.Session,
        append_decision=log.append_decision,
        get_decisions=log.get_decisions,
    )
    executor = SimpleNamespace(lifecycle=SimpleNamespace(
        runs=runs,
        get_task=lambda run_id: dict(record),
        mutate_assignment=failing_mutate,
    ))

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, "run-route-1", ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=None))

    # The route decision was recorded; the plan was left unchanged (no
    # marker), and dispatch still used the pinned baseline strictly.
    assert record["assignment"].get("repeat_task_route") is None
    entries = log.route_entries()
    assert entries
    assert calls[0]["provider_model"] == BASELINE
    assert calls[0]["strict_pin"] is True

    # Log-only applicability still demotes the effect once evidence ages out.
    world.age_all_observations(days=45)
    world.reopen()
    _prepare_gate(world, monkeypatch)
    from core.assignment_executor import AssignmentExecutor

    gate_executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        denial = gate_executor._autonomy_gate(
            _gate_assignment(), _gate_step(), run_id="run-route-1")
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
