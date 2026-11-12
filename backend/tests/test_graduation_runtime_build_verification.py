"""Runtime build verification for repeat-task graduation routing.

The benchmark evidence binds a callable route (the alias that is dispatched)
and the concrete provider build that answered the benchmark run. The runtime
must carry that build into the durable decision and prove that the accepted
provider response echoed the same build before any autonomous effect:

* a matched build pins the callable alias and verifies the echo;
* a same-family but different build is rejected;
* a missing provider echo is rejected (never substituted from the served or
  requested route);
* after a durable restart, a new benchmark observation of the same alias with
  a different build demotes the effect to supervision;
* an exact versioned request cannot be proven by a shorter/unversioned echo.

Both the normal assignment entry point (``_advance_employee_work``) and the
executor's effect gate (``_autonomy_gate``) are exercised, with a positive and
a negative twin for each boundary.

Offline only: scratch sqlite worlds, the real campaign writer with a sealed
scripted journal, ``TESTING=1`` and process-level network denial supplied by
the runner (see the session note). No live provider, no live DB.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("TESTING", "1")

import pytest  # noqa: E402

from core import autonomy_policy as ap  # noqa: E402
from core.llm.graduation_route import (  # noqa: E402
    IDENTITY_CONFLICT,
    IDENTITY_MISSING,
    IDENTITY_VERIFIED,
    STATE_PINNED,
    filter_route_for_attempt,
    resolve_repeat_task_route,
    revalidate_repeat_task_effect,
    validate_served_identity,
)
from core.models import AgentRegistry  # noqa: E402
from core.promotion_policy_service import (  # noqa: E402
    ASSESSMENT_POLICY_KEY,
    DEFAULT_ASSESSMENT_POLICY,
)

# The shared scratch world and its scripted entry/effect doubles live in the
# route-runtime suite. Reuse them rather than duplicating the receipt writer,
# campaign writer and assignment-entry harness.
from tests.test_graduation_route_runtime import (  # noqa: E402
    ALIAS,
    ALIAS_BUILD,
    ALIAS_OTHER_BUILD,
    RUBRIC,
    World,
    _assignment_record,
    _gate_assignment,
    _gate_step,
    _governance_ok,
    _install_entry_fakes,
    _matching_assignment,
    _newer,
    _prepare_gate,
    _route_marker,
    _utc_now,
    _BENCHMARK_REGISTRY_PATH,
    DecisionLog,
    ScriptedLLM,
    stub_executor,
)

AGENT = "route-agent"
OWNER = "route-owner"
RUN_ID = "run-route-1"


@pytest.fixture(autouse=True)
def _default_policy(monkeypatch):
    """Pin the server-controlled benchmark and assessment policy per test."""
    monkeypatch.setenv(
        "ATOM_EMPLOYEE_BENCHMARK_FILE", str(_BENCHMARK_REGISTRY_PATH))
    policy = dict(DEFAULT_ASSESSMENT_POLICY)
    policy["rubric_version"] = RUBRIC
    monkeypatch.setenv(ASSESSMENT_POLICY_KEY, json.dumps(policy))
    monkeypatch.delenv("ATOM_EMPLOYEE_PROVIDER_MODEL", raising=False)


@pytest.fixture()
def alias_world(tmp_path):
    """A receipt whose baseline is the callable alias, build recorded apart."""
    return World(
        tmp_path, baseline_route=ALIAS, baseline_build=ALIAS_BUILD)


def _resolved_decision(world, evidence_rows=None):
    with world.Session() as db:
        agent = db.get(AgentRegistry, AGENT)
        return resolve_repeat_task_route(
            db, agent, assignment=_matching_assignment(),
            evidence_rows=evidence_rows)


def _validated_decision(
    world, *, actual_build,
):
    """A durable resolution whose accepted echo was checked like dispatch."""
    decision = _resolved_decision(world)
    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    identity = validate_served_identity(
        decision["selected_route"],
        {
            "served_route": dict(decision["selected_route"]),
            "resolved_model": actual_build,
        },
        expected_build=decision["selected_build"],
    )
    decision["identity_state"] = identity
    decision["identity_build"] = actual_build
    decision["autonomous_eligible"] = identity == IDENTITY_VERIFIED
    return decision


# --- Resolver/classification contract --------------------------------------


def test_resolution_binds_callable_alias_and_benchmark_build(alias_world):
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)

    decision = _resolved_decision(alias_world)

    assert decision["route_state"] == STATE_PINNED, decision["reasons"]
    # The callable route remains the alias that is dispatched.
    assert decision["selected_route"] == {
        "provider": ALIAS[0], "model": ALIAS[1]}
    # The benchmark's actual provider build is bound separately.
    assert decision["selected_build"] == ALIAS_BUILD
    ranked = {
        f"{item['provider']}/{item['model']}": item
        for item in decision["ranked_routes"]}
    assert ranked["openai/gpt-5.4"]["build"] == ALIAS_BUILD

    llm = ScriptedLLM(clients=("openai",))
    allowed = filter_route_for_attempt(
        decision["selected_route"], quality=1.0, llm_service=llm,
        workspace_id="route-runtime-workspace",
        tenant_id="route-runtime-tenant", evidence={})
    assert allowed["allowed"] is True, allowed["reasons"]
    # The structured qualification pin names the alias, not the echo build.
    assert allowed["pin"] == ALIAS


def test_served_identity_build_twins():
    echo = lambda model: {  # noqa: E731 - compact twin table
        "served_route": {"provider": ALIAS[0], "model": ALIAS[1]},
        "resolved_model": model,
    }

    # Matched build: the echo is exactly the benchmark build.
    assert validate_served_identity(
        ALIAS, echo(ALIAS_BUILD), expected_build=ALIAS_BUILD,
    ) == IDENTITY_VERIFIED

    # Same-family changed build: never accepted as the bound build.
    assert validate_served_identity(
        ALIAS, echo(ALIAS_OTHER_BUILD), expected_build=ALIAS_BUILD,
    ) == IDENTITY_CONFLICT

    # Missing echo: no served/requested-route substitution.
    assert validate_served_identity(
        ALIAS, {"served_route": {"provider": ALIAS[0], "model": ALIAS[1]}},
        expected_build=ALIAS_BUILD,
    ) == IDENTITY_MISSING

    # A shorter/unversioned echo is not proof for an exact versioned build.
    assert validate_served_identity(
        ALIAS, echo(ALIAS[1]), expected_build=ALIAS_BUILD,
    ) == IDENTITY_CONFLICT

    # The accepted transport echo is the identity source.
    assert validate_served_identity(ALIAS, {
        "served_route": {"provider": ALIAS[0], "model": ALIAS[1]},
        "transport": {
            "accepted": True,
            "response_identity": {
                "provider": ALIAS[0], "model": ALIAS_BUILD},
        },
    }, expected_build=ALIAS_BUILD) == IDENTITY_VERIFIED
    assert validate_served_identity(ALIAS, {
        "served_route": {"provider": ALIAS[0], "model": ALIAS[1]},
        "transport": {"accepted": True, "response_identity": None},
    }, expected_build=ALIAS_BUILD) == IDENTITY_MISSING
    assert validate_served_identity(ALIAS, {
        "served_route": {"provider": ALIAS[0], "model": ALIAS[1]},
        "resolved_model": ALIAS_BUILD,
        "transport": {"accepted": False, "response_identity": None},
    }, expected_build=ALIAS_BUILD) == IDENTITY_MISSING


# --- Normal assignment entry point -----------------------------------------


def _run_entry(alias_world, monkeypatch, tmp_path, *, routing, calls):
    _install_entry_fakes(monkeypatch, calls=calls, routing=routing)
    log = DecisionLog(tmp_path / "decisions.json")
    record = _assignment_record()
    executor = stub_executor(alias_world, log, record)

    from api.assignment_routes import _advance_employee_work

    asyncio.run(_advance_employee_work(
        executor, RUN_ID, ScriptedLLM(clients=("openai",)),
        max_rounds=1, provider_model=("other", "legacy-model")))
    return log, record


def test_normal_entry_matched_build_is_autonomous(
        alias_world, tmp_path, monkeypatch):
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    calls: list = []
    log, record = _run_entry(
        alias_world, monkeypatch, tmp_path, calls=calls,
        routing={
            "served_route": {"provider": ALIAS[0], "model": ALIAS[1]},
            "resolved_model": ALIAS_BUILD,
        })

    # Strict alias dispatch, not the echoed build.
    assert calls[0]["provider_model"] == ALIAS
    assert calls[0]["strict_pin"] is True
    final = log.route_entries()[-1]
    assert final["route_state"] == STATE_PINNED
    assert final["selected_route"] == {
        "provider": ALIAS[0], "model": ALIAS[1]}
    assert final["selected_build"] == ALIAS_BUILD
    assert final["identity_build"] == ALIAS_BUILD
    assert final["identity_state"] == IDENTITY_VERIFIED
    assert final["autonomous_eligible"] is True
    marker = record["assignment"]["repeat_task_route"]
    assert marker["selected_route"] == {
        "provider": ALIAS[0], "model": ALIAS[1]}
    assert marker["selected_build"] == ALIAS_BUILD


def test_normal_entry_changed_same_family_build_is_ineligible(
        alias_world, tmp_path, monkeypatch):
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    calls: list = []
    log, _record = _run_entry(
        alias_world, monkeypatch, tmp_path, calls=calls,
        routing={
            "served_route": {"provider": ALIAS[0], "model": ALIAS[1]},
            "resolved_model": ALIAS_OTHER_BUILD,
        })

    assert calls[0]["provider_model"] == ALIAS
    final = log.route_entries()[-1]
    assert final["selected_build"] == ALIAS_BUILD
    assert final["identity_build"] == ALIAS_OTHER_BUILD
    assert final["identity_state"] == IDENTITY_CONFLICT
    assert final["autonomous_eligible"] is False


def test_normal_entry_missing_echo_is_ineligible(
        alias_world, tmp_path, monkeypatch):
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    calls: list = []
    log, _record = _run_entry(
        alias_world, monkeypatch, tmp_path, calls=calls,
        routing={
            "served_route": {"provider": ALIAS[0], "model": ALIAS[1]},
        })

    assert calls[0]["provider_model"] == ALIAS
    final = log.route_entries()[-1]
    assert final["selected_build"] == ALIAS_BUILD
    assert final["identity_build"] is None
    assert final["identity_state"] == IDENTITY_MISSING
    assert final["autonomous_eligible"] is False


# --- Effect gate ------------------------------------------------------------


def _effect_gate(world, log):
    from core.assignment_executor import AssignmentExecutor

    executor = AssignmentExecutor(SimpleNamespace(runs=SimpleNamespace(
        _sessions=lambda: world.Session,
        get_decisions=log.get_decisions,
    )))
    with patch(
        "core.service_factory.ServiceFactory.get_governance_service",
        return_value=_governance_ok(),
    ):
        return executor._autonomy_gate(
            _gate_assignment(marker=_route_marker()), _gate_step(),
            run_id=RUN_ID)


def test_effect_gate_matched_build_executes_after_restart(
        alias_world, tmp_path, monkeypatch):
    _prepare_gate(alias_world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    decision = _validated_decision(alias_world, actual_build=ALIAS_BUILD)
    assert decision["identity_state"] == IDENTITY_VERIFIED
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision(RUN_ID, decision)

    # Fresh process, same durable world.
    alias_world.reopen()
    assert _effect_gate(alias_world, log) is None


def test_effect_gate_new_benchmark_for_same_alias_changes_build(
        alias_world, tmp_path, monkeypatch):
    _prepare_gate(alias_world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    decision = _validated_decision(alias_world, actual_build=ALIAS_BUILD)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision(RUN_ID, decision)

    # A new campaign observation of the SAME callable alias was served by a
    # different concrete provider build.
    alias_world.add_benchmark_evidence(
        "exec-build-new", *ALIAS, observed_at=_newer(fresh),
        echo_model=ALIAS_OTHER_BUILD)
    alias_world.reopen()

    denial = _effect_gate(alias_world, log)
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert denial.get("source") == "repeat_task_route_recheck"
    assert denial.get("build_state") == "changed"
    assert "build" in str(denial.get("reason"))


def test_effect_gate_missing_dispatch_echo_is_not_autonomous(
        alias_world, tmp_path, monkeypatch):
    _prepare_gate(alias_world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    decision = _resolved_decision(alias_world)
    assert decision["route_state"] == STATE_PINNED
    decision["identity_state"] = IDENTITY_MISSING
    decision["identity_build"] = None
    decision["autonomous_eligible"] = False
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision(RUN_ID, decision)

    denial = _effect_gate(alias_world, log)
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert denial.get("source") == "repeat_task_route_recheck"
    assert "identity" in str(denial.get("reason"))


def test_effect_gate_verified_without_build_witness_is_not_autonomous(
        alias_world, tmp_path, monkeypatch):
    """A durable decision claiming verification still needs the echoed build."""
    _prepare_gate(alias_world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    decision = _resolved_decision(alias_world)
    assert decision["selected_build"] == ALIAS_BUILD
    decision["identity_state"] = IDENTITY_VERIFIED
    decision["identity_build"] = None
    decision["autonomous_eligible"] = True
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision(RUN_ID, decision)

    denial = _effect_gate(alias_world, log)
    assert denial is not None
    assert denial["outcome"] == ap.OUTCOME_PROPOSE
    assert denial.get("build_state") == "missing"
    assert "build" in str(denial.get("reason"))


def test_effect_gate_restart_new_benchmark_same_build_executes(
        alias_world, tmp_path, monkeypatch):
    """The positive restart twin: a new observation of the SAME build stays."""
    _prepare_gate(alias_world, monkeypatch)
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    decision = _validated_decision(alias_world, actual_build=ALIAS_BUILD)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision(RUN_ID, decision)

    alias_world.add_benchmark_evidence(
        "exec-build-new", *ALIAS, observed_at=_newer(fresh),
        echo_model=ALIAS_BUILD)
    alias_world.reopen()

    assert _effect_gate(alias_world, log) is None


def test_revalidate_route_level_matched_and_changed_builds(
        alias_world, tmp_path):
    """Direct contract: execute for the same build, propose for a new one."""
    fresh = _utc_now() - timedelta(days=2)
    alias_world.add_benchmark_evidence(
        "exec-build-bench", *ALIAS, observed_at=fresh,
        echo_model=ALIAS_BUILD)
    decision = _validated_decision(alias_world, actual_build=ALIAS_BUILD)
    log = DecisionLog(tmp_path / "decisions.json")
    log.append_decision(RUN_ID, decision)

    with alias_world.Session() as db:
        allowed = revalidate_repeat_task_effect(
            db, agent_id=AGENT, decisions=log.get_decisions(RUN_ID),
            assignment=_matching_assignment())
    assert allowed is not None
    assert allowed["outcome"] == "execute"

    alias_world.add_benchmark_evidence(
        "exec-build-new", *ALIAS, observed_at=_newer(fresh),
        echo_model=ALIAS_OTHER_BUILD)
    with alias_world.Session() as db:
        denial = revalidate_repeat_task_effect(
            db, agent_id=AGENT, decisions=log.get_decisions(RUN_ID),
            assignment=_matching_assignment())
    assert denial is not None
    assert denial["outcome"] == "propose"
    assert denial.get("build_state") == "changed"
