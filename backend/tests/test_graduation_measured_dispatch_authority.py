"""Dispatch-floor measured authority (PhaseC): the qualified route survives.

The probe (`/private/tmp/atom-graduation-measured-authority-probe-summary-
20261117.md`) localized the gap: a route that the campaign producer sealed, the
canonical reader validated, the review/receipt chain bound and the comparator
selected was still refused by the BYOK pin gate because that gate re-derived
the quality input from the STATIC prior (unknown name -> 70 < 80).

This file is the executable counter-proof for the repair. Every record is
produced by the ACTUAL producer from a sealed campaign journal and the frozen
in-repo benchmark registry; the review/receipt/promotion/resolver/service/
handler/SDK path is real; only the HTTP boundary is an in-process
``httpx.MockTransport`` (no socket, no provider, no credential). Scores are
synthetic accepted transport outcomes -- never a model-quality claim.

Covered:
  * full chain: producer -> validator -> review -> receipt -> promotion ->
    resolver -> authority -> real handler -> SDK double -> consumer model work;
  * the SAME world WITHOUT the authority still refuses ``below_quality_prior``
    with zero wire calls (the authority is what changed the floor input);
  * tampering/missing/foreign/wrong-build/wrong-receipt/wrong-dataset/
    wrong-rubric/wrong-scoring/superseded/newer/stale authority is refused,
    with zero wire calls;
  * the measured value still has to clear the profile floor, and an unsafe
    feedback quarantine stays independent of measured quality;
  * the authority is request-scoped: it applies only to the pinned attempt,
    never to the unpinned retry, a later call, or a concurrent different task.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("TESTING", "1")

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.agent_graduation_service as grad
import core.employee_benchmark_evidence as bench_evidence
from core.agent_graduation_service import (
    commit_qualified_transition,
    list_qualification_evidence_bundles,
    request_qualification_review,
    resolve_runtime_qualification_baseline,
    validate_qualification_review_binding,
    write_qualification_receipt_from_review,
)
from core.database import Base
from core.employee_proposal import (
    EmployeeWorkProposal,
    build_employee_context,
    propose_employee_work,
)
from core.llm.qualification_authority import (
    revalidate_qualification_authority,
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

TENANT = "measured-dispatch-tenant"
WORKSPACE = "measured-dispatch-workspace"
OTHER_WORKSPACE = "measured-dispatch-other-workspace"
SUPERVISOR = "measured-dispatch-supervisor"
ADMIN = "measured-dispatch-admin"
AGENT = "measured-dispatch-agent"
OTHER_AGENT = "measured-dispatch-other-agent"

PROVIDER = "probe_gateway"
BASELINE = (PROVIDER, "established-base")
BASELINE_BUILD = "established-base-2026-01"
CANDIDATE = (PROVIDER, "heldout-alpha")
CANDIDATE_BUILD = "heldout-alpha-2026-01"

_BENCHMARK_REGISTRY_PATH = bench_evidence.benchmark_registry_path()
_FROZEN_BENCHMARK, _FROZEN_REGISTRY, _FROZEN_REASONS = (
    bench_evidence._prepare_benchmark(None))
assert _FROZEN_BENCHMARK is not None, _FROZEN_REASONS
DATASET_SHA = _FROZEN_BENCHMARK["dataset_sha256"]
RUBRIC = _FROZEN_BENCHMARK["rubric_version"]
SCOPE = dict(_FROZEN_BENCHMARK["task_scope"])

PROPOSAL_JSON = {
    "proposal_kind": "evidence_read",
    "reason": "read the authorized note",
    "evidence_reads": [{
        "step_id": "evidence-1",
        "title": "Read note",
        "source_id": "doc-1",
    }],
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _heldout_observation(*, failed_case: str | None = None) -> dict:
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


def _matching_assignment(**overrides) -> dict:
    assignment = {
        "assignment_id": "asg-measured-dispatch",
        "objective": "repeat the held-out workload",
        "workspace_id": WORKSPACE,
        "tenant_id": TENANT,
        "workload_scope": dict(SCOPE),
        "provenance": {"agent_id": AGENT},
    }
    assignment.update(overrides)
    return assignment


@pytest.fixture(autouse=True)
def _pinned_server_config(monkeypatch):
    monkeypatch.setenv(
        "ATOM_EMPLOYEE_BENCHMARK_FILE", str(_BENCHMARK_REGISTRY_PATH))
    policy = dict(DEFAULT_ASSESSMENT_POLICY)
    policy["rubric_version"] = RUBRIC
    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
    monkeypatch.delenv("ATOM_EMPLOYEE_PROVIDER_MODEL", raising=False)


class World:
    """Scratch SQLite world with real campaign-produced evidence."""

    def __init__(self, tmp_path):
        self.db_path = tmp_path / "measured-dispatch.db"
        self._connect()
        self.now = _utc_now()
        with self.Session() as db:
            db.add(Tenant(
                id=TENANT, name="Measured Dispatch",
                subdomain=f"md-{uuid.uuid4().hex[:8]}", edition="personal",
                is_active=True,
            ))
            db.add_all([
                Workspace(id=WORKSPACE, name="Measured", tenant_id=TENANT),
                Workspace(
                    id=OTHER_WORKSPACE, name="Other", tenant_id=TENANT),
            ])
            db.add_all([
                User(
                    id=SUPERVISOR, tenant_id=TENANT, workspace_id=WORKSPACE,
                    email="sup@measured.test", first_name="S", last_name="V",
                    role="team_lead", status="active", is_active=True,
                ),
                User(
                    id=ADMIN, tenant_id=TENANT, workspace_id=WORKSPACE,
                    email="admin@measured.test", first_name="A", last_name="V",
                    role="admin", status="active", is_active=True,
                ),
            ])
            for agent_id, name, workspace in (
                    (AGENT, "Measured Candidate", WORKSPACE),
                    (OTHER_AGENT, "Measured Peer", OTHER_WORKSPACE)):
                db.add(AgentRegistry(
                    id=agent_id, name=name, category="operations",
                    role="agent", type="personal", capabilities=[],
                    module_path="core.generic_agent",
                    class_name="GenericAgent",
                    user_id=SUPERVISOR, workspace_id=workspace,
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

    # --- real producer ----------------------------------------------------

    def campaign(
        self,
        execution_id: str,
        provider: str,
        model: str,
        *,
        observed_at: datetime,
        echo_model: str | None = None,
        agent_id: str = AGENT,
        failed_case: str | None = None,
    ) -> dict:
        route = {"provider": provider, "model": model}
        build = echo_model or model
        with self.Session() as db:
            db.add(AgentExecution(
                id=execution_id, agent_id=agent_id, tenant_id=TENANT,
                workspace_id=WORKSPACE, status="completed",
                input_summary="held-out benchmark campaign",
                result_summary="completed",
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

    # --- real review / receipt / promotion --------------------------------

    def bundles(self, *, agent_id: str = AGENT) -> dict:
        with self.Session() as db:
            agent = db.get(AgentRegistry, agent_id)
            return list_qualification_evidence_bundles(
                db, agent, "INTERN", TENANT, WORKSPACE, limit=10)

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
            action.reviewed_at = _utc_now()
            db.commit()
        with self.Session() as db:
            written = write_qualification_receipt_from_review(
                db, action_id=action_id, approved=True, reviewer_id=ADMIN,
            )
            assert written["state"] == "valid", written
            return written["receipt_id"]

    def promote(self, operation_id: str = "measured-dispatch-promotion") -> str:
        with self.Session() as db:
            result = commit_qualified_transition(
                db,
                agent_id=AGENT,
                target_level="INTERN",
                actor_id=SUPERVISOR,
                readiness={"ready": True, "score": 0.88, "gaps": []},
                source="measured-dispatch-test",
                operation_id=operation_id,
            )
            assert result["status"] == "verified", result
            return result["data"]["promotion_history_id"]

    def qualify(self) -> str:
        """Review -> real receipt -> committed STUDENT -> INTERN transition."""
        item = self.bundles()["items"][0]
        assert item["binding"]["binding_state"] == "bound", item
        receipt_id = self.approve_and_write(
            self.request(item["evidence_refs"]))
        self.promote()
        return receipt_id

    def receipt(self, receipt_id: str) -> dict:
        with self.Session() as db:
            return dict(db.get(GraduationExam, receipt_id).metadata_json or {})

    def baseline_resolution(self, agent_id: str = AGENT) -> dict:
        with self.Session() as db:
            return resolve_runtime_qualification_baseline(
                db, db.get(AgentRegistry, agent_id))


class _RunsFacade:
    """Durable-run stand-in for the resolver's audit writes."""

    def __init__(self, world: World):
        self.world = world
        self.decisions: dict = {}

    def _sessions(self):
        return self.world.Session

    def append_decision(self, run_id: str, entry: dict) -> None:
        self.decisions.setdefault(run_id, []).append(copy.deepcopy(entry))

    def get_decisions(self, run_id: str) -> list:
        return copy.deepcopy(self.decisions.get(run_id, []))


class _LifecycleFacade:
    def __init__(self, world: World, record: dict):
        self.runs = _RunsFacade(world)
        self.record = record

    def get_task(self, run_id: str) -> dict:
        return copy.deepcopy(self.record)

    def mutate_assignment(self, run_id: str, compute, *, rationale=""):
        updated, marker = compute(
            self.record, self.record.get("assignment"))
        self.record["assignment"] = updated
        return marker


def _executor(world: World, record: dict):
    from types import SimpleNamespace

    return SimpleNamespace(lifecycle=_LifecycleFacade(world, record))


class _PlanState:
    def __init__(self):
        self.calls: list = []
        self.content: dict = dict(PROPOSAL_JSON)
        self.echo: str = CANDIDATE_BUILD
        self.status: int = 200


class _LocalTransport:
    """In-process OpenAI-compatible HTTP double (no socket is opened)."""

    def __init__(self, plan: _PlanState):
        self.plan = plan

    def __call__(self, request):
        try:
            body = json.loads(request.content.decode("utf-8"))
        except Exception:
            body = {}
        model = str(body.get("model") or "")
        self.plan.calls.append({
            "model": model,
            "path": request.url.path,
            "status": int(self.plan.status),
        })
        if self.plan.status != 200:
            return httpx.Response(self.plan.status, json={"error": {
                "message": "controlled transport failure",
                "type": "invalid_request_error"}})
        return httpx.Response(200, json={
            "id": "chatcmpl-measured-dispatch",
            "object": "chat.completion",
            "created": 0,
            "model": self.plan.echo or model,
            "choices": [{
                "index": 0, "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(self.plan.content),
                },
            }],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "total_tokens": 140,
            },
        })


def _dispatch_world(world: World, monkeypatch, models=None):
    """Real LLMService + real BYOKHandler + in-process SDK transport."""
    import openai

    import core.dynamic_pricing_fetcher as dpf
    import core.llm.byok_handler as byok_mod
    from core.dynamic_pricing_fetcher import get_pricing_fetcher
    from core.llm.byok_handler import BYOKHandler
    from core.llm_service import LLMService

    plan = _PlanState()
    session = world.Session()
    service = LLMService(
        db=session, workspace_id=WORKSPACE, tenant_id=TENANT)
    handler = BYOKHandler(
        workspace_id=WORKSPACE, tenant_id=TENANT, db_session=session)
    handler.clients[PROVIDER] = openai.OpenAI(
        api_key="sk-measured-dispatch-fake",
        base_url="http://127.0.0.1:9/v1",
        http_client=httpx.Client(
            transport=httpx.MockTransport(_LocalTransport(plan))),
    )
    # No _local_routes: these are gateway/BYOK-style names whose ONLY static
    # input is get_quality_score(model). This is the unknown-brand case.
    handler._load_local_providers = lambda: None
    fetcher = get_pricing_fetcher()
    fetcher.pricing_cache = {
        model: {"litellm_provider": "probe", "max_input_tokens": 131072}
        for model in (models or ("established-base", "heldout-alpha"))
    }
    monkeypatch.setattr(
        byok_mod, "get_pricing_fetcher_initialized_sync",
        lambda auto_refresh=True, force_refresh=False: fetcher)
    dpf._pricing_initialized = True
    # Route every runtime reader (capability evidence, spend/billing admission,
    # identity feedback) at the SAME scratch world this test owns. This is the
    # production shape -- one durable store -- without touching any live DB.
    import core.database as database_module

    monkeypatch.setattr(
        database_module, "SessionLocal", world.Session)
    service.handler = handler
    assert service._get_handler(
        workspace_id=WORKSPACE, tenant_id=TENANT) is handler
    return service, handler, plan


def _proposal_context():
    return build_employee_context(
        objective="Read the authorized evidence",
        workspace_id=WORKSPACE,
        tenant_id=TENANT,
        sources=[{
            "kind": "document",
            "representation": "document_text",
            "resource_id": "doc-1",
            "file_name": "note.txt",
        }],
        stage="discovery",
    )


@pytest.fixture()
def qualified_world(tmp_path):
    """Receipt/promotion from the baseline, then a fresh candidate record."""
    world = World(tmp_path)
    world.baseline(echo_model=BASELINE_BUILD)
    world.qualify()
    world.candidate(echo_model=CANDIDATE_BUILD)
    return world


def _resolve(world: World, service):
    from api.assignment_routes import _resolve_assignment_graduation_route

    record = {"assignment": _matching_assignment()}
    executor = _executor(world, record)
    resolved = _resolve_assignment_graduation_route(
        executor, "run-measured-dispatch", record, service)
    return executor, resolved


def _pin_entries(workspace_id: str = WORKSPACE) -> list:
    from core.llm.capability_profiles import capability_decisions

    return [
        item for item in capability_decisions(
            200, workspace_id=workspace_id, tenant_id=TENANT)
        if item.get("event") in ("pin", "pin_refused")
    ]


@pytest.fixture(autouse=True)
def _fresh_journals():
    from core.llm.byok_handler import BYOKHandler
    from core.llm.capability_profiles import (
        reset_capability_evidence_cache,
        reset_capability_journal_memory,
    )

    reset_capability_journal_memory()
    reset_capability_evidence_cache()
    BYOKHandler.invalidate_provider_failures()
    yield
    BYOKHandler.invalidate_provider_failures()
    reset_capability_journal_memory()
    reset_capability_evidence_cache()


# --- Full chain ------------------------------------------------------------


def test_measured_unknown_route_reaches_sdk_and_consumer(
        qualified_world, monkeypatch):
    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)

    executor, resolved = _resolve(world, service)
    decision = resolved["decision"]
    authority = resolved["qualification_authority"]
    assert decision["route_state"] == "pinned", decision.get("reasons")
    assert decision["selected_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    assert decision["selected_build"] == CANDIDATE_BUILD
    assert decision["capability_filter"]["allowed"] is True
    # The static prior of this unknown route is below the 80 profile floor --
    # that is the exact condition the probe localized.
    from core.benchmarks import get_quality_score

    assert get_quality_score(CANDIDATE[1]) < 80
    assert authority is not None
    assert authority["evidence_id"]
    assert authority["evidence_record_sha256"]
    assert authority["build"] == CANDIDATE_BUILD

    plan.calls.clear()
    result = asyncio.run(propose_employee_work(
        _proposal_context(),
        llm_service=service,
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        expected_route=tuple(resolved["pin"]),
        expected_build=decision["selected_build"],
        qualification_authority=authority,
    ))

    assert result["source"] == "model", result
    assert result["technical_fallback"] is False
    assert result["proposal"]["proposal_kind"] == "evidence_read"
    # The wire really was reached, for the intended route.
    assert [call["model"] for call in plan.calls] == [CANDIDATE[1]]
    routing = result["routing"]
    assert routing["served_route"] == {
        "provider": CANDIDATE[0], "model": CANDIDATE[1]}
    assert routing["resolved_model"] == CANDIDATE_BUILD

    pins = [
        item for item in _pin_entries()
        if (item.get("route") or [None])[-1] == CANDIDATE[1]]
    assert pins, "the pin decision must be journaled"
    pin = pins[-1]
    assert pin["eligible"] is True, pin
    assert pin["evidence_state"] == "measured_benchmark"
    assert pin["quality_basis"] == "measured_benchmark"
    assert pin["quality"] == 100
    assert pin["authority"]["evidence_id"] == authority["evidence_id"]
    assert pin["authority"]["receipt_id"] == authority["receipt_id"]


def test_same_world_without_authority_still_refuses_on_the_prior(
        qualified_world, monkeypatch):
    """Counter-arm: the authority, not the benchmark record, changed dispatch."""
    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)

    _executor_obj, resolved = _resolve(world, service)
    assert resolved["qualification_authority"] is not None

    plan.calls.clear()
    result = asyncio.run(propose_employee_work(
        _proposal_context(),
        llm_service=service,
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        expected_route=tuple(resolved["pin"]),
        expected_build=resolved["decision"]["selected_build"],
    ))

    assert result["source"] == "deterministic"
    assert result["technical_fallback"] is True
    assert plan.calls == []  # zero wire calls, no weaker route
    pin = [
        item for item in _pin_entries()
        if (item.get("route") or [None])[-1] == CANDIDATE[1]
    ][-1]
    assert pin["eligible"] is False
    assert "below_quality_prior" in pin["reasons"]
    assert pin["evidence_state"] == "prior"


def test_known_name_positive_still_serves_without_authority(
        tmp_path, monkeypatch):
    """A curated route (prior >= floor) keeps serving on the historical path."""
    from api.assignment_routes import _resolve_assignment_graduation_route

    world = World(tmp_path)
    world.baseline(echo_model=BASELINE_BUILD)
    world.qualify()
    world.campaign(
        "exec-known-name", PROVIDER, "deepseek-v4-flash",
        observed_at=world.now - timedelta(days=1),
        echo_model="deepseek-v4-flash-2026-01",
    )
    service, _handler, plan = _dispatch_world(
        world, monkeypatch,
        models=("deepseek-chat", "deepseek-v4-flash"))
    plan.echo = "deepseek-v4-flash-2026-01"

    record = {"assignment": _matching_assignment()}
    resolved = _resolve_assignment_graduation_route(
        _executor(world, record), "run-known-name", record, service)
    decision = resolved["decision"]
    assert decision["route_state"] == "pinned", decision.get("reasons")
    assert decision["selected_route"] == {
        "provider": PROVIDER, "model": "deepseek-v4-flash"}

    plan.calls.clear()
    result = asyncio.run(propose_employee_work(
        _proposal_context(),
        llm_service=service,
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        expected_route=tuple(resolved["pin"]),
        expected_build=decision["selected_build"],
    ))
    assert result["source"] == "model", result
    assert [call["model"] for call in plan.calls] == ["deepseek-v4-flash"]


# --- Reference tampering ---------------------------------------------------


def _mutations(authority: dict):
    def mutate(**changes):
        forged = copy.deepcopy(authority)
        forged.update(changes)
        return forged

    yield "accuracy", mutate(accuracy=0.55)
    yield "record_digest", mutate(evidence_record_sha256="0" * 64)
    yield "core_digest", mutate(evidence_core_sha256="0" * 64)
    yield "evidence_id", mutate(evidence_id="forged-record")
    yield "observed_at", mutate(observed_at="2020-01-01T00:00:00+00:00")
    yield "dataset", mutate(dataset_sha256="f" * 64)
    yield "rubric", mutate(rubric_version="foreign-rubric-v9")
    yield "scoring", mutate(scoring_version="foreign-scoring-v9")
    yield "build", mutate(build="heldout-alpha-1999-01")
    yield "receipt", mutate(receipt_id="forged-receipt")
    yield "promotion", mutate(promotion_id="forged-promotion")
    yield "revision", mutate(source_revision="forged-revision")
    yield "agent", mutate(agent_id=OTHER_AGENT)
    yield "workspace", mutate(workspace_id=OTHER_WORKSPACE)
    yield "tenant", mutate(tenant_id="foreign-tenant")
    yield "provider", mutate(provider="other_gateway")
    yield "model", mutate(model="other-model")
    yield "profile_version", mutate(measurement_profile_version="1999.1")
    yield "scope_digest", mutate(workload_scope_digest="0" * 64)
    yield "schema", mutate(schema="atom-qualification-authority-9999")


def test_forged_or_tampered_authority_never_dispatches(
        qualified_world, monkeypatch):
    from core.llm.byok_handler import NoSuitableConfiguredModelError

    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)
    authority = resolved["qualification_authority"]
    assert authority

    for label, forged in _mutations(authority):
        plan.calls.clear()
        result = asyncio.run(service.generate_structured_response(
            prompt="Read the authorized evidence",
            system_instruction="Return JSON only.",
            response_model=EmployeeWorkProposal,
            task_type="planning",
            capability_profile="employee_evidence_selection",
            provider_model=tuple(resolved["pin"]),
            strict_pin=True,
            qualification_authority=forged,
        ))
        # The handler converts its explicit pin refusal to the no-result
        # contract; the precise reason is journaled, and NOTHING is sent.
        assert result is None, label
        assert plan.calls == [], label


def test_authority_for_another_route_is_refused(qualified_world, monkeypatch):
    from core.llm.byok_handler import NoSuitableConfiguredModelError

    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)
    authority = resolved["qualification_authority"]

    plan.calls.clear()
    result = asyncio.run(service.generate_structured_response(
        prompt="Read the authorized evidence",
        system_instruction="Return JSON only.",
        response_model=EmployeeWorkProposal,
        task_type="planning",
        capability_profile="employee_evidence_selection",
        provider_model=BASELINE,
        strict_pin=True,
        qualification_authority=authority,
    ))
    assert result is None
    assert plan.calls == []


# --- Durable-state drift ---------------------------------------------------


def test_newer_validated_record_supersedes_the_authority(
        qualified_world, monkeypatch):
    from core.llm.byok_handler import NoSuitableConfiguredModelError

    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)
    authority = resolved["qualification_authority"]
    assert authority

    # A NEWER validated record for the same route/build arrives after the
    # authority was minted. The handler must not consume the older
    # observation that the resolver had selected.
    world.campaign(
        "exec-candidate-newer", *CANDIDATE,
        observed_at=world.now,
        echo_model=CANDIDATE_BUILD,
    )

    plan.calls.clear()
    result = asyncio.run(service.generate_structured_response(
        prompt="Read the authorized evidence",
        system_instruction="Return JSON only.",
        response_model=EmployeeWorkProposal,
        task_type="planning",
        capability_profile="employee_evidence_selection",
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        qualification_authority=authority,
    ))
    assert result is None
    assert plan.calls == []
    pin = [
        item for item in _pin_entries()
        if item.get("event") == "pin_refused"
    ][-1]
    assert pin["reason"].startswith("qualification_authority:")


def test_stale_evidence_is_refused_by_the_revalidator(qualified_world):
    """Freshness stays the explicit 30-day policy; it is not 'measured' forever."""
    from core.llm.graduation_route import ROUTE_PROFILE, resolve_repeat_task_route
    from core.llm.qualification_authority import (
        authority_from_route_decision,
    )

    world = qualified_world
    with world.Session() as db:
        decision = resolve_repeat_task_route(
            db, db.get(AgentRegistry, AGENT),
            assignment=_matching_assignment(),
            now=world.now,
        )
    authority = authority_from_route_decision(
        decision, profile_name=ROUTE_PROFILE)
    assert authority is not None
    with world.Session() as db:
        result = revalidate_qualification_authority(
            authority.as_dict(),
            db=db,
            provider=CANDIDATE[0],
            model=CANDIDATE[1],
            workspace_id=WORKSPACE,
            tenant_id=TENANT,
            now=world.now + timedelta(days=45),
        )
    assert result["ok"] is False
    assert result["reason"] == "authority_evidence_stale"


def test_receipt_drift_after_authority_is_refused(
        qualified_world, monkeypatch):
    from core.llm.byok_handler import NoSuitableConfiguredModelError

    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)
    authority = resolved["qualification_authority"]
    assert authority

    # Move the protected receipt pointer to a different (foreign) receipt:
    # the runtime baseline no longer names the receipt the authority binds.
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        agent.last_exam_id = "exec-candidate"  # not a qualification receipt
        db.commit()

    plan.calls.clear()
    result = asyncio.run(service.generate_structured_response(
        prompt="Read the authorized evidence",
        system_instruction="Return JSON only.",
        response_model=EmployeeWorkProposal,
        task_type="planning",
        capability_profile="employee_evidence_selection",
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        qualification_authority=authority,
    ))
    assert result is None
    assert plan.calls == []


# --- Independent gates -----------------------------------------------------


def test_measured_quality_still_has_to_clear_the_profile_floor(
        qualified_world):
    """The substitution is the quality INPUT, not a floor bypass."""
    from core.llm.capability_profiles import (
        get_profile,
        pin_decision,
        resolve_capability_profile,
    )
    from core.llm.graduation_route import ROUTE_PROFILE
    from core.llm.qualification_authority import (
        authority_from_route_decision,
    )
    from core.llm.graduation_route import resolve_repeat_task_route
    from core.models import AgentRegistry

    world = qualified_world
    with world.Session() as db:
        decision = resolve_repeat_task_route(
            db, db.get(AgentRegistry, AGENT),
            assignment=_matching_assignment(), now=world.now)
    authority = authority_from_route_decision(
        decision, profile_name=ROUTE_PROFILE)
    assert authority is not None

    profile = resolve_capability_profile(ROUTE_PROFILE, None, "")
    # A measured 75 is above the baseline but below this profile's floor 80:
    # the same gate that refused the static prior refuses the measurement.
    decision_low = pin_decision(
        profile, CANDIDATE[0], CANDIDATE[1], quality=75,
        quality_basis="measured_benchmark")
    assert decision_low["eligible"] is False
    assert "below_measured_quality" in decision_low["reasons"]
    assert decision_low["evidence_state"] == "measured_benchmark"

    # The static-prior label is preserved for every legacy caller.
    legacy = pin_decision(profile, CANDIDATE[0], CANDIDATE[1], quality=75)
    assert "below_quality_prior" in legacy["reasons"]
    assert legacy["evidence_state"] == "prior"


def test_unsafe_feedback_quarantine_is_independent_of_measured_quality():
    from core.llm.capability_profiles import get_profile, pin_decision

    profile = get_profile("employee_evidence_selection")
    quarantined = pin_decision(
        profile, "probe_gateway", "heldout-alpha", quality=100,
        quality_basis="measured_benchmark",
        evidence={"probe_gateway/heldout-alpha": {
            "samples": 6, "successes": 5, "retries": 0,
            "unsafe_failures": 1, "last_failure_kind": "unsafe_action",
        }},
    )
    assert quarantined["eligible"] is False
    assert "measured_unsafe_action" in quarantined["reasons"]


def test_generic_feedback_only_never_mints_authority():
    """Accepted feedback is not benchmark authority; the prior still decides."""
    from core.llm.capability_profiles import get_profile, pin_decision

    profile = get_profile("employee_evidence_selection")
    decided = pin_decision(
        profile, "probe_gateway", "heldout-alpha", quality=70,
        evidence={"probe_gateway/heldout-alpha": {
            "samples": 6, "successes": 6, "retries": 0,
            "unsafe_failures": 0, "last_failure_kind": None,
        }},
    )
    assert decided["eligible"] is False
    assert "below_quality_prior" in decided["reasons"]
    assert decided["evidence_state"] == "measured"


# --- Request scoping / concurrency ----------------------------------------


def _proposal_provenance(**kwargs):
    from core.llm.pinned_planning import routing_snapshot

    provenance = {
        "mode": "pinned",
        "requested_route": {
            "provider": kwargs["provider_model"][0],
            "model": kwargs["provider_model"][1],
        },
        "served_route": {
            "provider": kwargs["provider_model"][0],
            "model": kwargs["provider_model"][1],
        },
        "resolved_model": CANDIDATE_BUILD,
    }
    return routing_snapshot(provenance)


def test_authority_is_request_scoped_and_never_leaks(
        qualified_world, monkeypatch):
    from core.employee_proposal import EmployeeWorkProposal as _Proposal

    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)
    authority = resolved["qualification_authority"]
    pin = tuple(resolved["pin"])
    calls: list = []

    async def fake_pinned(llm_service, **kwargs):
        calls.append(dict(kwargs))
        return _Proposal.model_validate(PROPOSAL_JSON)

    monkeypatch.setattr(
        "core.llm.pinned_planning.pinned_structured_call", fake_pinned)

    async def scenario():
        first = await propose_employee_work(
            _proposal_context(), llm_service=service,
            provider_model=pin, strict_pin=True,
            qualification_authority=authority)
        # A later call in the SAME request task without the authority must
        # not inherit it.
        second = await propose_employee_work(
            _proposal_context(), llm_service=service,
            provider_model=pin, strict_pin=True)
        # Two concurrent different tasks: only task A carries the authority.
        third, fourth = await asyncio.gather(
            propose_employee_work(
                _proposal_context(), llm_service=service,
                provider_model=pin, strict_pin=True,
                qualification_authority=authority),
            propose_employee_work(
                _proposal_context(), llm_service=service,
                provider_model=pin, strict_pin=True),
        )
        return first, second, third, fourth

    asyncio.run(scenario())
    assert len(calls) == 4
    assert calls[0].get("qualification_authority") is not None
    assert calls[1].get("qualification_authority") is None
    assert calls[2].get("qualification_authority") is not None
    assert calls[3].get("qualification_authority") is None


def test_authority_rides_only_the_pinned_attempt_and_never_the_fallback():
    from core.llm.pinned_planning import pinned_structured_call

    calls: list = []

    class LLM:
        async def generate_structured_response(self, **kwargs):
            calls.append(dict(kwargs))
            if kwargs.get("provider_model"):
                raise RuntimeError("controlled pinned failure")
            return {"ok": True}

    result = asyncio.run(pinned_structured_call(
        LLM(),
        prompt="x",
        response_model=dict,
        system_instruction="y",
        log_label="measured authority scope",
        call_kwargs={"provider_model": ("probe_gateway", "heldout-alpha")},
        qualification_authority={"schema": "atom-qualification-authority-1"},
        strict_pin=False,
    ))
    # The authority forced strictness: an authority can never become a
    # weaker unpinned retry, so the failed pinned attempt is the whole call.
    assert result is None
    assert len(calls) == 1
    assert calls[0]["provider_model"] == ("probe_gateway", "heldout-alpha")
    assert calls[0]["qualification_authority"] == {
        "schema": "atom-qualification-authority-1"}


def test_authority_without_a_pin_fails_explicitly():
    from core.llm.pinned_planning import pinned_structured_call

    calls: list = []

    class LLM:
        async def generate_structured_response(self, **kwargs):
            calls.append(kwargs)
            return {"ok": True}

    result = asyncio.run(pinned_structured_call(
        LLM(),
        prompt="x",
        response_model=dict,
        system_instruction="y",
        log_label="measured authority missing pin",
        qualification_authority={"schema": "atom-qualification-authority-1"},
    ))
    assert result is None
    assert calls == []


# --- Identity / Phase B still applies --------------------------------------


@pytest.mark.parametrize("echo,error_code", [
    ("unknown", "route_identity_missing"),
    ("heldout-alpha-2026-99", "route_identity_conflict"),
])
def test_authority_does_not_bypass_the_served_identity_gate(
        qualified_world, monkeypatch, echo, error_code):
    """A measured prior is not identity proof: Phase B still rejects first."""
    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)
    authority = resolved["qualification_authority"]
    assert authority

    plan.echo = echo
    plan.calls.clear()
    result = asyncio.run(propose_employee_work(
        _proposal_context(),
        llm_service=service,
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        expected_route=tuple(resolved["pin"]),
        expected_build=resolved["decision"]["selected_build"],
        qualification_authority=authority,
    ))
    assert result["source"] == "deterministic", result
    assert result["technical_fallback"] is True
    routing = result["routing"]
    assert routing["error"]["code"] == error_code, routing
    # The transport DID answer; the answer was not consumed as model work.
    assert len(plan.calls) == 1


# --- Operational gates stay independent ------------------------------------


def test_authority_never_bypasses_cooldown_or_substitutes_a_route(
        qualified_world, monkeypatch):
    world = qualified_world
    service, handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)
    authority = resolved["qualification_authority"]
    assert authority

    handler._bench_provider(PROVIDER, cause="test", seconds=60)
    plan.calls.clear()
    result = asyncio.run(propose_employee_work(
        _proposal_context(),
        llm_service=service,
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        expected_route=tuple(resolved["pin"]),
        expected_build=resolved["decision"]["selected_build"],
        qualification_authority=authority,
    ))
    assert result["source"] == "deterministic"
    assert plan.calls == []  # zero wire calls, no weaker route
    refused = [
        item for item in _pin_entries()
        if item.get("event") == "pin_refused"
    ][-1]
    assert refused["reason"] == "cooldown"


def test_authority_never_bypasses_a_provider_failure_or_reuses_cooldown(
        qualified_world, monkeypatch):
    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)
    authority = resolved["qualification_authority"]
    assert authority

    plan.status = 401
    plan.calls.clear()
    first = asyncio.run(propose_employee_work(
        _proposal_context(),
        llm_service=service,
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        expected_route=tuple(resolved["pin"]),
        expected_build=resolved["decision"]["selected_build"],
        qualification_authority=authority,
    ))
    assert first["source"] == "deterministic"
    assert len(plan.calls) == 1  # the pinned attempt; no substitute route

    # The next qualified attempt is refused by the cooldown, not served by
    # the weaker baseline.
    second = asyncio.run(propose_employee_work(
        _proposal_context(),
        llm_service=service,
        provider_model=tuple(resolved["pin"]),
        strict_pin=True,
        expected_route=tuple(resolved["pin"]),
        expected_build=resolved["decision"]["selected_build"],
        qualification_authority=authority,
    ))
    assert second["source"] == "deterministic"
    assert len(plan.calls) == 1


# --- Cancellation / retry scoping ------------------------------------------


def test_cancelled_pinned_call_does_not_leak_authority_to_a_retry():
    from core.llm.pinned_planning import pinned_structured_call

    calls: list = []

    class LLM:
        async def generate_structured_response(self, **kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                raise asyncio.CancelledError()
            return {"ok": True}

    authority = {"schema": "atom-qualification-authority-1"}

    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            await pinned_structured_call(
                LLM(),
                prompt="x",
                response_model=dict,
                system_instruction="y",
                log_label="measured authority cancel",
                call_kwargs={
                    "provider_model": ("probe_gateway", "heldout-alpha")},
                qualification_authority=authority,
                strict_pin=True,
            )
        # The caller retries WITHOUT the authority: the cancelled attempt's
        # reference must not persist anywhere.
        return await pinned_structured_call(
            LLM(),
            prompt="x",
            response_model=dict,
            system_instruction="y",
            log_label="measured authority cancel retry",
            call_kwargs={
                "provider_model": ("probe_gateway", "heldout-alpha")},
            strict_pin=True,
        )

    result = asyncio.run(scenario())
    assert result == {"ok": True}
    assert calls[0].get("qualification_authority") is not None
    assert "qualification_authority" not in calls[1]


# --- Adaptation stage ------------------------------------------------------


def test_adaptation_stages_forward_the_same_authority():
    from core.assignment_plan import new_assignment
    from core.employee_adaptation import (
        WorkAdaptationProposal,
        propose_adaptation,
    )
    from core.employee_work_requests import work_request_schemas

    class CapturingLLM:
        def __init__(self):
            self.calls: list = []

        async def generate_structured_response(self, **kwargs):
            self.calls.append(dict(kwargs))
            return WorkAdaptationProposal(
                decision="retain", reason="nothing ready")

    llm = CapturingLLM()
    authority = {"schema": "atom-qualification-authority-1"}
    context = {
        "identity": {
            "workspace_id": WORKSPACE, "tenant_id": TENANT},
        "work_request_schemas": work_request_schemas(),
        "available_business_operations": [
            "quote_calculation", "invoice_reconciliation"],
        "rules": {"evidence_only": False},
    }
    assignment = new_assignment(
        objective="Quote the accepted population",
        workspace_id=WORKSPACE, tenant_id=TENANT)
    result = asyncio.run(propose_adaptation(
        context,
        [{"observation_id": "o-1", "kind": "evidence_result"}],
        assignment=assignment,
        llm_service=llm,
        provider_model=CANDIDATE,
        strict_pin=True,
        qualification_authority=authority,
    ))
    assert result["source"] == "model", result
    assert llm.calls
    assert all(
        call.get("qualification_authority") is authority
        for call in llm.calls
    ), llm.calls


def test_bare_float_or_non_reference_is_not_authority(
        qualified_world, monkeypatch):
    """A caller-supplied number can never stand in for validated evidence."""
    world = qualified_world
    service, _handler, plan = _dispatch_world(world, monkeypatch)
    _executor_obj, resolved = _resolve(world, service)

    for bogus in (1.0, 100, "qualified=true", {"qualified": True},
                  {"quality": 100}):
        plan.calls.clear()
        result = asyncio.run(service.generate_structured_response(
            prompt="Read the authorized evidence",
            system_instruction="Return JSON only.",
            response_model=EmployeeWorkProposal,
            task_type="planning",
            capability_profile="employee_evidence_selection",
            provider_model=tuple(resolved["pin"]),
            strict_pin=True,
            qualification_authority=bogus,
        ))
        assert result is None, bogus
        assert plan.calls == [], bogus
