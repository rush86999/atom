"""Focused scratch tests for the employee benchmark evidence producer.

These exercise the real production intake with a scripted transport: a
deterministic provider echo recorder (``atom-llm-transport``) plus a scratch
SQLite world holding real ``AgentExecution`` rows. No live provider, no live
DB, no runtime route/receipt branch is touched.

What is asserted is authority, not plausibility:

* the verdict, the time and the served identity come from the frozen set, the
  durable execution completion and the provider echo — never from the
  observation payload;
* tenant/workspace/agent come from the durable execution row;
* a missing or conflicting echo (or a disagreement with the run's durable
  provenance) is ineligible and writes nothing;
* generic metadata and caller-injected records are not benchmark authority;
* re-ingesting a run never refreshes its authoritative completion time.
"""
# ruff: noqa: F811 — pytest fixture re-export shares its name with test params
from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("TESTING", "1")

from core.employee_benchmark_evidence import (
    EVIDENCE_KEY,
    REASON_EXECUTION_INCOMPLETE,
    REASON_EXECUTION_TIME_MISSING,
    REASON_JOURNAL_UNSEALED,
    REASON_JOURNAL_MISMATCH,
    REASON_JOURNAL_UNTRUSTED,
    REASON_METADATA_BENCHMARK_CHANGED,
    REASON_IDENTITY_CONFLICT,
    REASON_IDENTITY_MISSING,
    REASON_IDENTITY_UNATTRIBUTED,
    REASON_METADATA_TAMPERED,
    REASON_OBSERVATION_MISSING,
    REASON_PRIOR_CONFLICT,
    REASON_SCOPE_MISMATCH,
    REASON_SCORING_VERSION_MISMATCH,
    REASON_DATASET_IDENTITY_MISMATCH,
    inspect_employee_benchmark_evidence,
    load_employee_benchmark_evidence,
    load_benchmark_registry,
    open_campaign_transport_journal,
    produce_employee_benchmark_evidence,
)
from core.llm.model_evidence_comparison import compare_model_evidence
from core.models import AgentExecution
from tests.acceptance.fixtures import world  # noqa: F401 — fixture re-export

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(hours=6)

SERVED = {"provider": "ollama", "model": "llama3.1:8b-instruct-q4_K_M"}
REQUESTED = {"provider": "ollama", "model": "llama3.1:8b"}
OTHER_SERVED = {"provider": "ollama", "model": "qwen3:8b"}

DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "config" / "employee_benchmark"
    / "heldout_two_domain_2026_11_02.json"
)


def _observation(**overrides):
    case = {
        "assignment_status": "completed",
        "steps": {
            "calculate": {
                "status": "applied", "value": "96.30", "currency": "USD"},
            "reconcile": {
                "status": "applied", "value": "140.25", "currency": "USD"},
        },
        "deliverables": {
            "document": {
                "status": "applied",
                "text": "Review: quote total 96.30 USD; reconciled 140.25 USD.",
            },
        },
        "external_effects": 0,
    }
    observation = {
        "campaign": "employee-heldout-two-domain",
        "cases": {
            "heldout-quote": copy.deepcopy(case),
            "heldout-reconcile": copy.deepcopy(case),
        },
        "run": {"restart": {"same_wait": True, "status": "waiting"}},
    }
    observation.update(overrides)
    return observation


_UNSET = object()


class ScriptedTransport:
    """Deterministic campaign-owned provider that records a transport journal.

    ``response_identity`` is the provider echo — the only identity the
    producer accepts. ``requested_route`` is what the caller asked for and is
    audit-only. A failed/refused call is recorded with ``accepted=False``.
    The journal is owned by this campaign harness and must be sealed with the
    durable execution completion time before intake.
    """

    def __init__(
        self,
        *,
        served=SERVED,
        requested=REQUESTED,
        campaign_id="employee-heldout-two-domain",
        execution_id="exec-benchmark-1",
        seal_at=NOW,
    ):
        self.served = dict(served)
        self.requested = dict(requested)
        self.journal = open_campaign_transport_journal(
            campaign_id=campaign_id, execution_id=execution_id)
        self.seal_at = seal_at
        self._sealed = False

    def call(
        self,
        *,
        accepted=True,
        response_identity=_UNSET,
        served_route=_UNSET,
        unattributed=False,
    ):
        identity = (
            dict(self.served) if response_identity is _UNSET
            else response_identity)
        if served_route is _UNSET:
            served_route = dict(identity) if identity else None
        self.journal.record_call(
            accepted=accepted,
            requested_route=self.requested,
            served_route=served_route,
            response_identity=identity,
            unattributed=unattributed,
        )
        return {"choices": [{"message": {"content": "scripted"}}]}

    def seal(self, completed_at=None):
        if not self._sealed:
            self.journal.seal(completed_at=(
                self.seal_at if completed_at is None else completed_at))
            self._sealed = True
        return self.journal


def _execution(
    world,
    *,
    execution_id="exec-benchmark-1",
    metadata=None,
    tenant_id="tenant-1",
    workspace_id="ws-1",
    agent_id="agent-1",
    status="completed",
    completed_at=NOW,
):
    with world.Session() as db:
        db.add(AgentExecution(
            id=execution_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            status=status,
            completed_at=completed_at,
            input_summary="held-out two-domain campaign",
            output_summary="completed",
            metadata_json=copy.deepcopy(metadata or {}),
        ))
        db.commit()
    return execution_id


def _stored(world, execution_id="exec-benchmark-1"):
    with world.Session() as db:
        return db.get(AgentExecution, execution_id).metadata_json


def _produce(world, transport=None, *, now=NOW, execution_id="exec-benchmark-1",
             observation=None, seal_at=None, **kwargs):
    transport = transport or ScriptedTransport(execution_id=execution_id)
    journal = transport.seal(seal_at)
    return produce_employee_benchmark_evidence(
        execution_id=execution_id,
        observation=_observation() if observation is None else observation,
        transport_journal=journal,
        session_factory=world.Session,
        now=now,
        **kwargs,
    )


def _dataset():
    return json.loads(DATASET_PATH.read_text())


def _scratch_registry(
    tmp_path,
    *,
    dataset=None,
    dataset_sha256=None,
    scoring_version=None,
    benchmark_id=None,
):
    dataset = copy.deepcopy(dataset or _dataset())
    set_path = tmp_path / "set.json"
    set_path.write_text(json.dumps(dataset, indent=1))
    digest = hashlib.sha256(json.dumps(
        {key: value for key, value in dataset.items() if key != "set_sha256"},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    registry = {
        "schema": "atom-employee-benchmark-registry-1",
        "path": str(tmp_path / "registry.json"),
        "benchmarks": [{
            "id": benchmark_id or dataset["id"],
            "capability": "employee_assignment.delivery",
            "dataset": "set.json",
            "dataset_sha256": dataset_sha256 or digest,
            "scoring_version": (
                scoring_version or dataset["scoring"]["version"]),
            "rubric_version": "employee-heldout-v1",
            "contract_version": "employee-benchmark-1",
            "task_scope": load_benchmark_registry()["benchmarks"][0][
                "task_scope"],
        }],
    }
    return registry, digest


# ---------------------------------------------------------------------------
# The happy path: server-scored, frozen-bound, exact served identity
# ---------------------------------------------------------------------------


def test_records_server_scored_evidence_bound_to_frozen_set_and_echo(world, tmp_path):
    journal = ScriptedTransport()
    journal.call()
    journal.call()
    # A failed attempt with a different identity is not evidence.
    journal.call(accepted=False, response_identity=OTHER_SERVED)
    _execution(world, metadata={
        "model_provenance": {
            "provider": SERVED["provider"], "model": SERVED["model"]},
    })

    result = _produce(world, journal, artifact_dir=tmp_path / "artifacts")

    assert result["status"] == "recorded", result
    assert result["passed"] is True
    assert result["accuracy"] == 1.0
    record = result["evidence"]
    assert record["observed_at"] == NOW.isoformat()
    assert record["observed_at_source"] == "execution_completion"
    assert record["intake_at"] == NOW.isoformat()
    assert record["execution"]["completed_at"] == NOW.isoformat()
    assert record["dataset"]["id"] == "employee-heldout-two-domain-2026-11-02"
    assert record["scoring"]["version"] == "employee-heldout-outcome-1"
    assert record["provider"] == SERVED["provider"]
    assert record["model"] == SERVED["model"]
    assert record["served_identity"]["identity_source"] == (
        "transport_journal+execution")
    assert record["fallback"] is True
    assert record["requested_routes"] == [REQUESTED]
    assert record["transport"]["campaign_id"] == "employee-heldout-two-domain"
    assert record["execution"]["tenant_id"] == "tenant-1"
    assert record["execution"]["workspace_id"] == "ws-1"

    # The durable join is the authority, and the audit artifact follows the
    # assessment convention (served pair + frozen binding).
    stored = _stored(world)
    assert stored[EVIDENCE_KEY][0]["integrity"]["record_sha256"] == (
        record["integrity"]["record_sha256"])
    artifact_path = Path(record["artifact"]["path"])
    artifact = json.loads(artifact_path.read_text())
    assert artifact["schema"] == "atom-employee-benchmark-judgment-1"
    assert artifact["served_provider"] == SERVED["provider"]
    assert artifact["served_model"] == SERVED["model"]
    assert artifact["dataset_sha256"] == record["dataset"]["sha256"]
    assert artifact["scoring"]["version"] == record["scoring"]["version"]
    assert hashlib.sha256(
        artifact_path.read_bytes()).hexdigest() == record["artifact"]["sha256"]

    # The loaded evidence plugs straight into the existing comparison core.
    loaded = load_employee_benchmark_evidence(stored)
    assert len(loaded) == 1
    entry = load_benchmark_registry()["benchmarks"][0]
    comparison = compare_model_evidence(
        task_scope=entry["task_scope"],
        evidence=loaded,
        rubric_version=entry["rubric_version"],
        contract_version=entry["contract_version"],
        now=NOW + timedelta(minutes=1),
    )
    assert comparison["outcome"] == "compared", comparison
    assert comparison["selected"]["provider"] == SERVED["provider"]
    assert comparison["selected"]["model"] == SERVED["model"]
    assert comparison["comparison_set"]["dataset_id"] == (
        "employee-heldout-two-domain-2026-11-02")


# ---------------------------------------------------------------------------
# Caller claims are stripped, never authority
# ---------------------------------------------------------------------------


def test_caller_supplied_score_timestamp_and_identity_are_not_authority(world):
    _execution(world)
    transport = ScriptedTransport()
    transport.call()
    observation = _observation()
    # A fabricated pass: one check actually fails, so the server verdict is
    # negative regardless of what the caller asserts.
    observation["cases"]["heldout-quote"]["steps"]["calculate"][
        "value"] = "999.99"
    observation.update({
        "score": 1.0,
        "accuracy": 1.0,
        "passed": True,
        "observed_at": "2031-01-01T00:00:00+00:00",
        "provider": "openai",
        "model": "gpt-5",
        "served_provider": "openai",
        "served_model": "gpt-5",
        "tenant_id": "tenant-other",
        "workspace_id": "ws-other",
        "dataset_sha256": "forged",
        "scoring_version": "forged-scoring",
    })
    observation["cases"]["heldout-quote"].update({
        "passed": True,
        "score": 1.0,
        "observed_at": "2031-01-01T00:00:00+00:00",
        "served_provider": "openai",
        "served_model": "gpt-5",
    })

    result = _produce(world, transport, observation=observation)

    assert result["status"] == "recorded", result
    record = result["evidence"]
    # The flooded score did not become the verdict, the timestamp or the route.
    assert record["accuracy"] == 0.5
    assert record["passed"] is False
    assert record["observed_at"] == NOW.isoformat()
    assert record["provider"] == SERVED["provider"]
    assert record["model"] == SERVED["model"]
    assert record["dataset"]["sha256"] != "forged"
    assert record["scoring"]["version"] == "employee-heldout-outcome-1"
    claimed = set(result["rejected_claims"])
    for path in (
        "observation.score",
        "observation.observed_at",
        "observation.served_provider",
        "observation.cases.heldout-quote.passed",
        "observation.cases.heldout-quote.served_model",
    ):
        assert path in claimed, (path, result["rejected_claims"])

    # The fabricated pass still yields a negative comparison result: the
    # consumer never selects a route on a caller's claim.
    entry = load_benchmark_registry()["benchmarks"][0]
    comparison = compare_model_evidence(
        task_scope=entry["task_scope"],
        evidence=load_employee_benchmark_evidence(_stored(world)),
        rubric_version=entry["rubric_version"],
        contract_version=entry["contract_version"],
        now=NOW + timedelta(minutes=1),
    )
    assert comparison["selected"] is None
    assert comparison["outcome"] == "insufficient_evidence"


def test_generic_metadata_and_forged_records_are_not_authority(world):
    forged = {
        "schema": "atom-employee-benchmark-evidence-1",
        "authority": {
            "producer": "atom.employee_benchmark_evidence",
            "intake": "server",
            "caller_claims": "rejected",
        },
        "evidence_id": "employee-benchmark:forged",
        "provider": "openai",
        "model": "gpt-5",
        "observed_at": NOW.isoformat(),
        "observed_at_source": "execution_completion",
        "intake_at": NOW.isoformat(),
        "execution": {"id": "exec-benchmark-1",
                      "completed_at": NOW.isoformat()},
        "passed": True,
        "accuracy": 1.0,
        "dataset": {"id": "employee-heldout-two-domain-2026-11-02",
                    "sha256": "forged"},
        "scoring": {"version": "employee-heldout-outcome-1"},
        "task_scope": {"task_policy": "forged"},
        "integrity": {"record_sha256": "forged", "core_sha256": "forged"},
    }
    _execution(world, metadata={
        "score": 1.0,
        "observed_at": NOW.isoformat(),
        EVIDENCE_KEY: [forged],
    })

    # Generic metadata alone is not benchmark evidence.
    inspection = inspect_employee_benchmark_evidence(
        {"score": 1.0, "provider": "openai", "model": "gpt-5"})
    assert inspection["records"] == []
    assert load_employee_benchmark_evidence(
        {"score": 1.0, "provider": "openai", "model": "gpt-5"}) == []

    # The forged reserved block fails validation and is not returned.
    inspection = inspect_employee_benchmark_evidence(_stored(world))
    assert inspection["records"] == []
    assert inspection["rejected"][0]["evidence_id"] == (
        "employee-benchmark:forged")
    assert REASON_METADATA_TAMPERED in inspection["rejected"][0]["reasons"]

    # Real production intake evicts the forged record and keeps the authentic
    # one; the forged identity never becomes the scored route.
    transport = ScriptedTransport()
    transport.call()
    result = _produce(world, transport)
    assert result["status"] == "recorded", result
    assert result["discarded_metadata"][0]["evidence_id"] == (
        "employee-benchmark:forged")
    stored = _stored(world)
    assert len(stored[EVIDENCE_KEY]) == 1
    loaded = load_employee_benchmark_evidence(stored)
    assert [entry["model"] for entry in loaded] == [SERVED["model"]]
    assert stored["score"] == 1.0  # generic metadata is left untouched
    assert stored["observed_at"] == NOW.isoformat()


def test_generic_legacy_route_cannot_override_the_provider_echo(world):
    """A generic pair is cross-checked, never accepted as the scored identity."""
    _execution(world, metadata={"provider": "openai", "model": "gpt-5"})
    transport = ScriptedTransport()
    transport.call()
    result = _produce(world, transport)
    assert result["status"] == "rejected", result
    assert REASON_IDENTITY_CONFLICT in result["reasons"]
    assert EVIDENCE_KEY not in (_stored(world) or {})


def test_tampered_stored_record_is_rejected_on_read(world):
    _execution(world)
    transport = ScriptedTransport()
    transport.call()
    assert _produce(world, transport)["status"] == "recorded"
    stored = _stored(world)
    stored[EVIDENCE_KEY][0]["accuracy"] = 1.0
    stored[EVIDENCE_KEY][0]["passed"] = True
    stored[EVIDENCE_KEY][0]["cases"][0]["checks"][0]["passed"] = False

    inspection = inspect_employee_benchmark_evidence(stored)
    assert inspection["records"] == []
    assert REASON_METADATA_TAMPERED in inspection["rejected"][0]["reasons"]
    assert load_employee_benchmark_evidence(stored) == []


# ---------------------------------------------------------------------------
# Durable scope + identity eligibility
# ---------------------------------------------------------------------------


def test_mismatched_tenant_workspace_or_agent_writes_nothing(world):
    _execution(world)
    transport = ScriptedTransport()
    transport.call()

    for claim, reason in (
        ({"tenant_id": "tenant-other"}, REASON_SCOPE_MISMATCH),
        ({"workspace_id": "ws-other"}, REASON_SCOPE_MISMATCH),
        ({"agent_id": "agent-other"}, "agent_mismatch"),
    ):
        result = _produce(world, transport, **claim)
        assert result["status"] == "rejected", (claim, result)
        assert reason in result["reasons"], (claim, result)
        assert EVIDENCE_KEY not in (_stored(world) or {})


def test_conflicting_or_missing_provider_echo_is_ineligible(world):
    _execution(world)
    cases = {}

    conflicted = ScriptedTransport()
    conflicted.call()
    conflicted.call(response_identity=OTHER_SERVED)
    cases["conflict"] = (conflicted, REASON_IDENTITY_CONFLICT)

    missing = ScriptedTransport()
    missing.call(response_identity=None)
    cases["missing"] = (missing, REASON_IDENTITY_MISSING)

    mismatched_served = ScriptedTransport()
    mismatched_served.call(served_route=OTHER_SERVED)
    cases["served-route-disagrees"] = (
        mismatched_served, REASON_IDENTITY_CONFLICT)

    unattributed = ScriptedTransport()
    unattributed.call(unattributed=True)
    cases["unattributed"] = (unattributed, REASON_IDENTITY_MISSING)

    requested_only = ScriptedTransport()
    requested_only.call(response_identity=None, served_route=None)
    cases["requested-only"] = (requested_only, REASON_IDENTITY_MISSING)

    for label, (transport, reason) in cases.items():
        result = _produce(world, transport)
        assert result["status"] == "rejected", (label, result)
        assert reason in result["reasons"], (label, result)
        assert EVIDENCE_KEY not in (_stored(world) or {}), label

    # A plain journal is not authority, however faithfully it spells the
    # recorder marker: only the campaign's own sealed journal counts.
    raw = [{
        "call_id": "call-1",
        "recorded_by": "atom-llm-transport",
        "accepted": True,
        "requested_route": dict(REQUESTED),
        "served_route": dict(SERVED),
        "response_identity": dict(SERVED),
        "unattributed": False,
    }]
    result = produce_employee_benchmark_evidence(
        execution_id="exec-benchmark-1",
        observation=_observation(),
        transport_journal=raw,
        session_factory=world.Session,
        now=NOW,
    )
    assert result["status"] == "rejected", result
    assert REASON_JOURNAL_UNTRUSTED in result["reasons"], result
    assert EVIDENCE_KEY not in (_stored(world) or {})


def test_versioned_provider_echo_binds_the_callable_route_not_the_build(world):
    """A versioned echo is the build of the accepted route, not a conflict.

    The accepted route is the callable alias (``latest`` stays an alias tag);
    the provider echoes a dated build. The evidence keeps the route as its
    identity and the echo as the build, so later comparison can treat two
    builds of the same route as ambiguous instead of treating the alias as
    proof that the build did not change.
    """
    alias = {"provider": "ollama", "model": "llama3.1:8b-latest"}
    build = {"provider": "ollama", "model": "llama3.1:8b-2026-11"}
    _execution(world, metadata={"model_provenance": {
        "provider": alias["provider"],
        "model": alias["model"],
        "resolved_model": build["model"],
        "serving_models": [dict(alias)],
    }})
    transport = ScriptedTransport(served=alias)
    transport.call(response_identity=build, served_route=alias)

    result = _produce(world, transport)

    assert result["status"] == "recorded", result
    record = result["evidence"]
    assert record["provider"] == alias["provider"]
    assert record["model"] == alias["model"]
    assert record["resolved_model"] == build["model"]
    assert record["served_identity"]["model"] == alias["model"]
    assert record["served_identity"]["resolved_model"] == build["model"]
    loaded = load_employee_benchmark_evidence(_stored(world))
    assert loaded[0]["model"] == alias["model"]
    assert loaded[0]["resolved_model"] == build["model"]


def test_execution_provenance_conflict_and_unattributed_calls_block(world):
    _execution(world, metadata={
        "model_provenance": {
            "provider": SERVED["provider"], "model": OTHER_SERVED["model"]},
    })
    transport = ScriptedTransport()
    transport.call()
    result = _produce(world, transport)
    assert result["status"] == "rejected", result
    assert REASON_IDENTITY_CONFLICT in result["reasons"]

    with world.Session() as db:
        db.get(AgentExecution, "exec-benchmark-1").metadata_json = {
            "model_provenance": {
                "provider": SERVED["provider"],
                "model": SERVED["model"],
                "unattributed_calls": 2,
            },
        }
        db.commit()
    result = _produce(world, transport)
    assert result["status"] == "rejected", result
    assert REASON_IDENTITY_UNATTRIBUTED in result["reasons"]

    with world.Session() as db:
        db.get(AgentExecution, "exec-benchmark-1").metadata_json = {
            "model_provenance": {
                "provider": SERVED["provider"],
                "model": SERVED["model"],
                "serving_models": [
                    {"provider": SERVED["provider"], "model": SERVED["model"]},
                    {"provider": SERVED["provider"],
                     "model": OTHER_SERVED["model"]},
                ],
            },
        }
        db.commit()
    result = _produce(world, transport)
    assert result["status"] == "rejected", result
    assert REASON_IDENTITY_CONFLICT in result["reasons"]


# ---------------------------------------------------------------------------
# Frozen set / scoring pin is server-controlled
# ---------------------------------------------------------------------------


def test_frozen_dataset_and_scoring_pin_are_enforced(world, tmp_path):
    _execution(world)
    transport = ScriptedTransport()
    transport.call()

    registry, digest = _scratch_registry(tmp_path)
    result = _produce(world, transport, registry=registry)
    assert result["status"] == "recorded", result
    assert result["evidence"]["dataset"]["sha256"] == digest

    # A changed expected value under a different pin is a different benchmark;
    # the old run may not be rescored under it.
    changed = _dataset()
    changed["cases"]["heldout-quote"]["checks"][1]["equals"] = "1.00"
    changed_dir = tmp_path / "changed"
    changed_dir.mkdir()
    changed_registry, _changed_digest = _scratch_registry(
        changed_dir, dataset=changed)
    result = _produce(
        world, transport, registry=changed_registry,
        observation=_observation())
    assert result["status"] == "rejected", result
    assert REASON_PRIOR_CONFLICT in result["reasons"]
    stored = _stored(world)
    assert stored[EVIDENCE_KEY][0]["accuracy"] == 1.0
    assert stored[EVIDENCE_KEY][0]["dataset"]["sha256"] == digest

    # A stale declared digest is refused.
    tampered_registry, _digest = _scratch_registry(
        tmp_path, dataset_sha256="0" * 64)
    result = _produce(world, transport, registry=tampered_registry)
    assert result["status"] == "rejected", result
    assert REASON_DATASET_IDENTITY_MISMATCH in result["reasons"]

    # A scoring generation that does not match the frozen set is refused.
    scoring_registry, _digest = _scratch_registry(
        tmp_path, scoring_version="employee-heldout-outcome-2")
    result = _produce(world, transport, registry=scoring_registry)
    assert result["status"] == "rejected", result
    assert REASON_SCORING_VERSION_MISMATCH in result["reasons"]


def test_changed_frozen_set_invalidates_a_stored_record(world, tmp_path):
    registry, _digest = _scratch_registry(tmp_path)
    _execution(world)
    transport = ScriptedTransport()
    transport.call()
    assert _produce(world, transport, registry=registry)["status"] == (
        "recorded")

    # The set is re-frozen after the record was written: the old evidence no
    # longer describes the current benchmark and must not be reused.
    changed = _dataset()
    changed["scoring"]["version"] = "employee-heldout-outcome-2"
    refrozen_dir = tmp_path / "refrozen"
    refrozen_dir.mkdir()
    changed_registry, _changed_digest = _scratch_registry(
        refrozen_dir, dataset=changed,
        scoring_version="employee-heldout-outcome-2")
    stored = _stored(world)
    inspection = inspect_employee_benchmark_evidence(
        stored, registry=changed_registry)
    assert inspection["records"] == []
    assert REASON_METADATA_BENCHMARK_CHANGED in inspection["rejected"][0]["reasons"]
    assert load_employee_benchmark_evidence(
        stored, registry=changed_registry) == []


# ---------------------------------------------------------------------------
# Idempotency, partial observations, missing run
# ---------------------------------------------------------------------------


def test_reingest_is_idempotent_and_never_refreshes_execution_time(world):
    _execution(world)
    transport = ScriptedTransport()
    transport.call()
    first = _produce(world, transport, now=NOW)
    assert first["status"] == "recorded"
    stored = _stored(world)
    assert len(stored[EVIDENCE_KEY]) == 1

    again = _produce(world, transport, now=LATER)
    assert again["status"] == "already_recorded", again
    assert again["observed_at"] == NOW.isoformat()
    assert len(_stored(world)[EVIDENCE_KEY]) == 1

    # A later, different verdict for the same run cannot overwrite it.
    failing = _observation()
    failing["cases"]["heldout-reconcile"]["steps"]["reconcile"][
        "value"] = "1.00"
    conflict = _produce(world, transport, observation=failing, now=LATER)
    assert conflict["status"] == "rejected", conflict
    assert REASON_PRIOR_CONFLICT in conflict["reasons"]
    assert _stored(world)[EVIDENCE_KEY][0]["accuracy"] == 1.0


def test_missing_case_cannot_establish_a_pass(world):
    _execution(world)
    transport = ScriptedTransport()
    transport.call()
    observation = _observation()
    del observation["cases"]["heldout-reconcile"]

    result = _produce(world, transport, observation=observation)

    assert result["status"] == "recorded", result
    record = result["evidence"]
    assert record["passed"] is False
    assert record["accuracy"] == 0.5
    reconcile = next(
        case for case in record["cases"]
        if case["case_id"] == "heldout-reconcile")
    assert reconcile["observed"] is False
    assert reconcile["passed"] is False


def test_unknown_execution_and_empty_observation_are_refused(world):
    transport = ScriptedTransport(execution_id="missing-execution")
    transport.call()
    result = produce_employee_benchmark_evidence(
        execution_id="missing-execution",
        observation=_observation(),
        transport_journal=transport.seal(),
        session_factory=world.Session,
        now=NOW,
    )
    assert result["status"] == "rejected"
    assert "execution_not_found" in result["reasons"]

    _execution(world)
    transport = ScriptedTransport()
    transport.call()
    result = _produce(world, transport, observation={"cases": {}})
    assert result["status"] == "rejected"
    assert REASON_OBSERVATION_MISSING in result["reasons"]
    assert EVIDENCE_KEY not in (_stored(world) or {})


# ---------------------------------------------------------------------------
# Campaign ownership + authoritative completion
# ---------------------------------------------------------------------------


def test_unsealed_journal_and_incomplete_execution_are_refused(world):
    _execution(world)
    transport = ScriptedTransport()
    transport.call()
    result = produce_employee_benchmark_evidence(
        execution_id="exec-benchmark-1",
        observation=_observation(),
        transport_journal=transport.journal,
        session_factory=world.Session,
        now=NOW,
    )
    assert result["status"] == "rejected", result
    assert REASON_JOURNAL_UNSEALED in result["reasons"], result

    _execution(
        world, execution_id="exec-no-completion", completed_at=None)
    no_time = ScriptedTransport(execution_id="exec-no-completion")
    no_time.call()
    result = _produce(world, no_time, execution_id="exec-no-completion")
    assert result["status"] == "rejected", result
    assert REASON_EXECUTION_TIME_MISSING in result["reasons"], result

    _execution(
        world, execution_id="exec-running", status="running",
        completed_at=NOW)
    running = ScriptedTransport(execution_id="exec-running")
    running.call()
    result = _produce(world, running, execution_id="exec-running")
    assert result["status"] == "rejected", result
    assert REASON_EXECUTION_INCOMPLETE in result["reasons"], result
    assert EVIDENCE_KEY not in (_stored(world) or {})


def test_stale_replay_cannot_refresh_or_rebind_evidence(world):
    _execution(world)
    transport = ScriptedTransport()
    transport.call()
    first = _produce(world, transport, now=NOW)
    assert first["status"] == "recorded", first

    # Intake later is not a new observation: the execution completion time
    # stays authoritative.
    replay = _produce(world, transport, now=LATER)
    assert replay["status"] == "already_recorded", replay
    assert replay["observed_at"] == NOW.isoformat()

    # A fresh journal cannot be pasted onto the old execution.
    fresh = ScriptedTransport(seal_at=LATER)
    fresh.call()
    result = _produce(world, fresh, now=LATER)
    assert result["status"] == "rejected", result
    assert REASON_JOURNAL_MISMATCH in result["reasons"], result

    # An old journal cannot be imported onto a newer execution.
    _execution(
        world, execution_id="exec-benchmark-2", completed_at=LATER)
    imported = produce_employee_benchmark_evidence(
        execution_id="exec-benchmark-2",
        observation=_observation(),
        transport_journal=transport.journal,
        session_factory=world.Session,
        now=LATER,
    )
    assert imported["status"] == "rejected", imported
    assert REASON_JOURNAL_MISMATCH in imported["reasons"], imported
    assert EVIDENCE_KEY not in (_stored(world, "exec-benchmark-2") or {})

    # Rewriting the durable completion time cannot freshen the old evidence.
    with world.Session() as db:
        db.get(AgentExecution, "exec-benchmark-1").completed_at = LATER
        db.commit()
    rewritten = _produce(world, transport, now=LATER)
    assert rewritten["status"] == "rejected", rewritten
    assert REASON_JOURNAL_MISMATCH in rewritten["reasons"], rewritten
    stored = _stored(world)
    assert stored[EVIDENCE_KEY][0]["observed_at"] == NOW.isoformat()

    # Replayed evidence is also not fresh to the comparison consumer: intake
    # time never substitutes for the authoritative observed time.
    entry = load_benchmark_registry()["benchmarks"][0]
    comparison = compare_model_evidence(
        task_scope=entry["task_scope"],
        evidence=load_employee_benchmark_evidence(stored),
        rubric_version=entry["rubric_version"],
        contract_version=entry["contract_version"],
        freshness_days=1,
        now=NOW + timedelta(days=2),
    )
    assert comparison["selected"] is None, comparison
    assert any(
        item.get("classes")
        for item in comparison.get("not_task_evidence") or []), comparison


def test_normal_campaign_entry_records_authoritative_completion(
        tmp_path, monkeypatch):
    """The existing held-out campaign's normal entry feeds the producer.

    The campaign completes through its real executor path, owns the scripted
    transport journal, and joins the durable assignment completion time to a
    real ``AgentExecution`` row. Its actual (non-benchmark) outcome is recorded
    honestly as a negative verdict; a later replay cannot refresh it.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.employee_adaptation import (
        adopt_adaptation, deterministic_adaptation,
    )
    from tests.test_employee_two_domain_campaign import (
        _procurement_campaign, _run, env as campaign_env,
    )

    env = campaign_env.__wrapped__(tmp_path, monkeypatch)

    # The campaign owns both the execution row and its journal before any work
    # happens; the journal records the actual accepted provider calls as the
    # campaign runs.
    engine = create_engine(f"sqlite:///{env['tmp']}/campaign.db")
    AgentExecution.__table__.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    execution_id = "exec-campaign-procurement"
    with factory() as db:
        db.add(AgentExecution(
            id=execution_id,
            agent_id="employee-1",
            tenant_id="tenant_campaign",
            workspace_id="ws_campaign",
            status="running",
            metadata_json={"model_provenance": {
                "provider": SERVED["provider"], "model": SERVED["model"]}},
        ))
        db.commit()
    journal = open_campaign_transport_journal(
        campaign_id="employee-heldout-two-domain",
        execution_id=execution_id,
    )
    journal.record_call(
        accepted=True,
        requested_route=REQUESTED,
        served_route=SERVED,
        response_identity=SERVED,
    )

    # The campaign's normal entry path, unchanged by the benchmark producer.
    run_id, state, _calls = _procurement_campaign(env)
    executor = env["executor"]
    _run(executor.execute(run_id))
    state["invoice_version"] = "v2"
    assert executor.record_external_response(
        run_id, "corr-invoice-v2", response="corrected invoice v2",
    )["status"] == "resumed"
    assignment = env["lifecycle"].get_assignment(run_id)
    proposal = deterministic_adaptation({
        "observation_id": "invoice-v2",
        "kind": "source_version",
        "step_id": "read-invoice",
        "reason": "the supplier issued a corrected invoice version",
    }, assignment)
    assert adopt_adaptation(
        env["lifecycle"], run_id, proposal)["status"] == "applied"
    _run(executor.execute(run_id))
    executor.approve_step(
        run_id, "create-bill", approved_by="campaign owner")
    _run(executor.execute(run_id))
    assignment = env["lifecycle"].get_assignment(run_id)
    assert assignment["status"] == "completed", assignment
    completed_at = datetime.fromisoformat(assignment["completed_at"])
    with factory() as db:
        execution = db.get(AgentExecution, execution_id)
        execution.status = "completed"
        execution.completed_at = completed_at
        db.commit()
    journal.seal(completed_at=completed_at)

    steps = {
        str(step.get("step_id")): step
        for step in assignment.get("steps") or []
    }
    reconcile = (steps["reconcile"].get("result") or {}).get("data") or {}
    case = {
        "assignment_status": assignment["status"],
        "steps": {"reconcile": {
            "value": reconcile.get("total"),
            "currency": reconcile.get("currency"),
        }},
        "deliverables": {},
        "external_effects": 1,
    }
    observation = {
        "campaign": "employee-heldout-two-domain",
        "cases": {
            "heldout-quote": copy.deepcopy(case),
            "heldout-reconcile": copy.deepcopy(case),
        },
        "run": {"restart": {"same_wait": True, "status": "waiting"}},
    }

    result = produce_employee_benchmark_evidence(
        execution_id=execution_id,
        observation=observation,
        transport_journal=journal,
        session_factory=factory,
        now=LATER,
    )
    assert result["status"] == "recorded", result
    record = result["evidence"]
    assert record["observed_at"] == completed_at.isoformat()
    assert record["observed_at_source"] == "execution_completion"
    assert record["intake_at"] == LATER.isoformat()
    assert record["execution"]["completed_at"] == record["observed_at"]
    assert record["execution"]["workspace_id"] == "ws_campaign"
    assert record["provider"] == SERVED["provider"]
    assert record["model"] == SERVED["model"]
    # The mechanism campaign's 270.00 is not the frozen held-out 140.25, so
    # the server verdict is honestly negative — never a caller pass.
    assert record["passed"] is False

    # The same campaign journal replays as the same observation, not a fresh
    # one, even when intake is later.
    replay = produce_employee_benchmark_evidence(
        execution_id=execution_id,
        observation=observation,
        transport_journal=journal,
        session_factory=factory,
        now=LATER + timedelta(days=3),
    )
    assert replay["status"] == "already_recorded", replay
    assert replay["observed_at"] == record["observed_at"]
