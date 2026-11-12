"""Graduation model provenance: durable episode evidence names the route.

PR #854 made directly recorded runs durable qualification evidence
(execution + episode, workspace-scoped and completed). This slice carries the
ACTUAL provider/model that served the run into that evidence:

* the serving provider/model pair is selected ATOMICALLY from one trusted,
  execution-bound source — a partial runtime result is never completed from
  a different source, so a mixed "new-provider/old-model" identity (the
  false identity reproduced in the graduation review) cannot be reported;
* route attribution is a fallback (served route only — an attempted route is
  never reported as served), and it is scoped per call: the dispatch scope
  is cleared before each ReAct LLM call, so a failed or deterministic
  branch inherits nothing;
* the shared handler ``_last_used_*`` stash is NOT a source (cross-call
  mutable state a concurrent caller can overwrite);
* provenance is a reserved episode key: caller-supplied values are stripped
  and only validated server-owned execution evidence is copied;
* multi-step runs keep the de-duplicated set of serving models, and calls
  whose attribution was unavailable count as explicit unknown coverage;
* a run with no known identity stays unknown (no "auto"/default claim), so
  historical rows are not silently relabelled.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import core.llm.model_provenance as model_provenance
from core import generic_agent as generic_agent_module
from core.llm import byok_handler
from core.agent_graduation_service import list_qualification_evidence_bundles
from core.episode_service import EpisodeService
from core.generic_agent import GenericAgent
from core.models import AgentEpisode, AgentExecution, AgentRegistry
from tests.acceptance.fixtures import world  # noqa: F401 — fixture re-export

# The real context-local reader, captured before the module-wide autouse
# stub replaces it; the scope test below exercises the actual contextvars.
_REAL_GET_ROUTE_ATTRIBUTION = model_provenance.get_route_attribution

PROBE_TASK = (
    "PROBE_TASK_7d2c9e41: produce the controlled provenance output"
)
PROBE_OUTPUT = (
    "PROBE_OUTPUT_7d2c9e41: the recorded execution output must reach the "
    "graduation picker unchanged"
)


@pytest.fixture(autouse=True)
def _no_ambient_route_attribution(monkeypatch):
    """Keep each case deterministic; route attribution has its own unit case."""
    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {})


def _scratch_session(world):
    @contextmanager
    def _session():
        db = world.Session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return _session


def _agent(world) -> GenericAgent:
    agent = GenericAgent.__new__(GenericAgent)
    agent.id = world.agent_id
    agent.name = "Agent One"
    agent.workspace_id = world.workspace_id
    agent.tenant_id = world.tenant_id
    agent.config = {}
    agent.world_model = SimpleNamespace(record_experience=AsyncMock())
    # Run-level provenance state (normally initialized in __init__).
    agent._last_model_provenance = {}
    agent._serving_models = []
    agent._unattributed_llm_calls = 0
    return agent


def _record(agent, monkeypatch, world, result, execution_id):
    monkeypatch.setattr(
        generic_agent_module, "get_db_session", _scratch_session(world))
    asyncio.run(agent._record_execution(
        PROBE_TASK,
        {
            "output": PROBE_OUTPUT,
            "steps": [],
            "complexity": "moderate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result,
        },
        {"run_id": execution_id, "trigger": "probe"},
    ))


def _rows(world, execution_id):
    with world.Session() as db:
        execution = db.get(AgentExecution, execution_id)
        episode = (
            db.query(AgentEpisode)
            .filter(AgentEpisode.execution_id == execution_id)
            .one_or_none()
        )
        return execution, episode


def _bundles(world):
    with world.Session() as db:
        agent = db.get(AgentRegistry, world.agent_id)
        return list_qualification_evidence_bundles(
            db,
            agent,
            "SUPERVISED",
            world.tenant_id,
            world.workspace_id,
            limit=10,
        )


def test_direct_recording_persists_actual_provider_and_model(world, monkeypatch):
    agent_row = world.session.get(AgentRegistry, world.agent_id)
    agent_row.status = "intern"
    agent_row.confidence_score = 0.6
    world.session.commit()

    execution_id = "probe-provenance-success-7d2c9e41"
    _record(
        _agent(world), monkeypatch, world,
        {
            "status": "objective_satisfied",
            "provider": "openai",
            "model": "gpt-5.4-2026-03",
            "requested_provider": "openai",
            "requested_model": "gpt-5.4",
            # Multi-step serving set + unknown coverage ride with the
            # runtime result and must survive the durable round-trip.
            "serving_models": [
                {"provider": "openai", "model": "gpt-5.4-2026-03"},
                {"provider": "auto", "model": "auto"},  # alias: dropped
            ],
            "unattributed_calls": 1,
        },
        execution_id,
    )

    execution, episode = _rows(world, execution_id)
    assert execution is not None and episode is not None
    for metadata in (execution.metadata_json, episode.metadata_json):
        provenance = metadata["model_provenance"]
        assert provenance["provider"] == "openai"
        assert provenance["model"] == "gpt-5.4-2026-03"
        assert provenance["requested_provider"] == "openai"
        assert provenance["requested_model"] == "gpt-5.4"
        assert provenance["fallback"] is False
        assert provenance["serving_models"] == [
            {"provider": "openai", "model": "gpt-5.4-2026-03"},
        ]
        assert provenance["unattributed_calls"] == 1
        assert metadata["provider"] == "openai"
        assert metadata["model"] == "gpt-5.4-2026-03"

    bundles = _bundles(world)
    assert len(bundles["items"]) == 1
    item = bundles["items"][0]
    assert item["episode_id"] == episode.id
    assert item["model_provenance"]["provider"] == "openai"
    assert item["model_provenance"]["model"] == "gpt-5.4-2026-03"
    assert item["model_provenance"]["serving_models"] == [
        {"provider": "openai", "model": "gpt-5.4-2026-03"},
    ]
    assert item["provider"] == "openai"
    assert item["model"] == "gpt-5.4-2026-03"


def test_fallback_served_model_is_recorded_not_the_requested_route(
    world, monkeypatch
):
    agent_row = world.session.get(AgentRegistry, world.agent_id)
    agent_row.status = "intern"
    agent_row.confidence_score = 0.6
    world.session.commit()

    execution_id = "probe-provenance-fallback-7d2c9e41"
    _record(
        _agent(world), monkeypatch, world,
        {
            "status": "objective_satisfied",
            "provider": "ollama",
            "model": "llama3.1:8b",
            "requested_provider": "openrouter",
            "requested_model": "openrouter/auto-large",
        },
        execution_id,
    )

    _execution, episode = _rows(world, execution_id)
    provenance = episode.metadata_json["model_provenance"]
    assert provenance["provider"] == "ollama"
    assert provenance["model"] == "llama3.1:8b"
    assert provenance["requested_provider"] == "openrouter"
    assert provenance["requested_model"] == "openrouter/auto-large"
    assert provenance["fallback"] is True

    item = _bundles(world)["items"][0]
    assert item["model_provenance"]["provider"] == "ollama"
    assert item["model_provenance"]["model"] == "llama3.1:8b"


def test_unknown_identity_stays_unknown_and_is_not_backfilled(
    world, monkeypatch
):
    agent_row = world.session.get(AgentRegistry, world.agent_id)
    agent_row.status = "intern"
    agent_row.confidence_score = 0.6
    world.session.commit()

    execution_id = "probe-provenance-unknown-7d2c9e41"
    _record(
        _agent(world), monkeypatch, world,
        {"status": "objective_satisfied"},
        execution_id,
    )

    execution, episode = _rows(world, execution_id)
    assert execution is not None and episode is not None
    for metadata in (execution.metadata_json, episode.metadata_json):
        assert "model_provenance" not in metadata
        assert "provider" not in metadata
        assert "model" not in metadata

    # The bundle records explicit unknown coverage: attribution was
    # evaluated and is unavailable, never silently inherited.
    item = _bundles(world)["items"][0]
    assert item["model_provenance"] == {"source": "unknown"}
    assert "provider" not in item
    assert "model" not in item


def test_recorder_does_not_inherit_a_prior_calls_ambient_route(
    world, monkeypatch
):
    """A run with no runtime result identity must not borrow stale context."""
    monkeypatch.setattr(
        model_provenance,
        "get_route_attribution",
        lambda: {
            "served_route": {
                "provider": "previous-provider",
                "model": "previous-model",
            },
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )
    agent_row = world.session.get(AgentRegistry, world.agent_id)
    agent_row.status = "intern"
    agent_row.confidence_score = 0.6
    world.session.commit()

    execution_id = "probe-provenance-stale-7d2c9e41"
    _record(
        _agent(world), monkeypatch, world,
        {"status": "objective_satisfied"},
        execution_id,
    )

    execution, episode = _rows(world, execution_id)
    assert execution is not None and episode is not None
    assert "model_provenance" not in execution.metadata_json
    assert "model_provenance" not in episode.metadata_json


def test_failed_execution_remains_failed_but_keeps_actual_attribution(
    world, monkeypatch
):
    agent_row = world.session.get(AgentRegistry, world.agent_id)
    agent_row.status = "intern"
    agent_row.confidence_score = 0.6
    world.session.commit()

    execution_id = "probe-provenance-failed-7d2c9e41"
    _record(
        _agent(world), monkeypatch, world,
        {
            "status": "failed",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "requested_provider": "deepseek",
            "requested_model": "deepseek-v4-pro",
        },
        execution_id,
    )

    execution, episode = _rows(world, execution_id)
    assert execution.status == "failed"
    assert episode.status == "failed"
    assert episode.metadata_json["model_provenance"]["provider"] == "deepseek"
    assert (
        episode.metadata_json["model_provenance"]["model"]
        == "deepseek-v4-flash"
    )
    # Failed work is durable attribution, not completed qualification evidence.
    assert _bundles(world)["items"] == []


def test_create_episode_copies_execution_provenance_without_relabelling(
    world
):
    with world.Session() as db:
        db.add(AgentExecution(
            id="probe-provenance-existing-7d2c9e41",
            agent_id=world.agent_id,
            tenant_id=world.tenant_id,
            workspace_id=world.workspace_id,
            status="completed",
            input_summary=PROBE_TASK,
            output_summary=PROBE_OUTPUT,
            metadata_json={
                "model_provenance": {
                    "provider": "anthropic",
                    "model": "claude-opus-4",
                    "requested_provider": "openai",
                    "requested_model": "gpt-5.4",
                    "fallback": True,
                    "source": "runtime_result",
                },
                "provider": "anthropic",
                "model": "claude-opus-4",
            },
        ))
        db.commit()

    with world.Session() as db:
        episode = asyncio.run(
            EpisodeService(db).create_episode_from_execution(
                execution_id="probe-provenance-existing-7d2c9e41",
                task_description=PROBE_TASK,
                outcome="success",
                success=True,
            )
        )

    provenance = episode.metadata_json["model_provenance"]
    assert provenance["provider"] == "anthropic"
    assert provenance["model"] == "claude-opus-4"
    assert provenance["requested_provider"] == "openai"
    assert provenance["requested_model"] == "gpt-5.4"
    assert provenance["fallback"] is True
    assert episode.metadata_json["provider"] == "anthropic"
    assert episode.metadata_json["model"] == "claude-opus-4"


def test_create_episode_strips_caller_provenance_overrides(world):
    """Regression (graduation review): provenance is a reserved key.

    Caller-supplied provider/model metadata must never win over (or stand
    in for) the validated server-owned execution evidence.
    """
    with world.Session() as db:
        db.add(AgentExecution(
            id="probe-provenance-reserved-7d2c9e41",
            agent_id=world.agent_id,
            tenant_id=world.tenant_id,
            workspace_id=world.workspace_id,
            status="completed",
            input_summary=PROBE_TASK,
            output_summary=PROBE_OUTPUT,
            metadata_json={
                "model_provenance": {
                    "provider": "anthropic",
                    "model": "claude-opus-4",
                    "source": "runtime_result",
                },
                "provider": "anthropic",
                "model": "claude-opus-4",
            },
        ))
        db.commit()

    with world.Session() as db:
        episode = asyncio.run(
            EpisodeService(db).create_episode_from_execution(
                execution_id="probe-provenance-reserved-7d2c9e41",
                task_description=PROBE_TASK,
                outcome="success",
                success=True,
                metadata={
                    "model_provenance": {
                        "provider": "caller",
                        "model": "caller-model",
                    },
                    "provider": "caller",
                    "model": "caller-model",
                    "requested_provider": "caller",
                    "requested_model": "caller-model",
                    "note": "kept",
                },
            )
        )

    provenance = episode.metadata_json["model_provenance"]
    assert provenance["provider"] == "anthropic"
    assert provenance["model"] == "claude-opus-4"
    assert episode.metadata_json["provider"] == "anthropic"
    assert episode.metadata_json["model"] == "claude-opus-4"
    assert "requested_provider" not in episode.metadata_json
    assert "requested_model" not in episode.metadata_json
    assert episode.metadata_json["note"] == "kept"


def test_create_episode_without_execution_provenance_stays_unknown(world):
    """Caller-supplied values are stripped even when the execution recorded
    no identity: unknown stays unknown instead of trusting the caller."""
    with world.Session() as db:
        db.add(AgentExecution(
            id="probe-provenance-calleronly-7d2c9e41",
            agent_id=world.agent_id,
            tenant_id=world.tenant_id,
            workspace_id=world.workspace_id,
            status="completed",
            input_summary=PROBE_TASK,
            output_summary=PROBE_OUTPUT,
            metadata_json={},
        ))
        db.commit()

    with world.Session() as db:
        episode = asyncio.run(
            EpisodeService(db).create_episode_from_execution(
                execution_id="probe-provenance-calleronly-7d2c9e41",
                task_description=PROBE_TASK,
                outcome="success",
                success=True,
                metadata={
                    "model_provenance": {
                        "provider": "caller",
                        "model": "caller-model",
                    },
                    "provider": "caller",
                    "model": "caller-model",
                },
            )
        )

    assert "model_provenance" not in episode.metadata_json
    assert "provider" not in episode.metadata_json
    assert "model" not in episode.metadata_json


def test_remember_ignores_shared_handler_stash(world):
    """Regression: the shared handler ``_last_used_*`` stash is not a source.

    The handler is cross-call mutable state that a concurrent caller can
    overwrite; a poisoned stash must never become provenance, and a call
    with no attributable identity counts as explicit unknown coverage.
    """
    agent = _agent(world)
    agent.llm = SimpleNamespace(
        _get_handler=lambda: SimpleNamespace(
            _last_used_provider="openai",
            _last_used_model="gpt-5.4-2026-03",
        )
    )

    agent._remember_model_provenance()

    assert agent._last_model_provenance == {}
    assert agent._serving_models == []
    assert agent._unattributed_llm_calls == 1


def test_remember_records_call_local_route_evidence(world, monkeypatch):
    """Per-call route attribution (not handler state) is the evidence."""
    agent = _agent(world)
    agent.llm = SimpleNamespace(
        _get_handler=lambda: SimpleNamespace(
            _last_used_provider="stale-provider",
            _last_used_model="stale-model",
        )
    )
    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {
            "served_route": {
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
            },
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )

    agent._remember_model_provenance()

    assert agent._last_model_provenance["provider"] == "deepseek"
    assert agent._last_model_provenance["model"] == "deepseek-v4-flash"
    assert agent._serving_models == [
        {"provider": "deepseek", "model": "deepseek-v4-flash"},
    ]
    assert agent._unattributed_llm_calls == 0


def test_dispatch_scope_clears_stale_route_attribution(monkeypatch):
    """Regression: no stale context after failed or deterministic branches.

    The scope cleared before each ReAct dispatch must remove the served
    route (and the echoed checkpoint) of any earlier call in the context,
    so only an accepted response in the current call can be attributed.
    """
    from core.llm.model_provenance import (
        clear_route_attribution,
        set_requested_route,
        set_resolved_model,
        set_served_route,
    )

    set_requested_route("old-provider", "old-model")
    set_served_route("old-provider", "old-model")
    set_resolved_model("old-model-echo")
    assert _REAL_GET_ROUTE_ATTRIBUTION()["served_route"] is not None

    GenericAgent._begin_call_provenance_scope()

    attribution = _REAL_GET_ROUTE_ATTRIBUTION()
    assert attribution["served_route"] is None
    assert attribution["requested_route"] is None
    assert attribution["resolved_model"] is None
    clear_route_attribution()


def test_serving_set_covers_multistep_runs_with_unknown_coverage(
    world, monkeypatch
):
    """Multi-step runs keep the set of serving models; unattributed calls
    count as explicit unknown coverage instead of extending the last
    known identity over those steps."""
    agent = _agent(world)

    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {
            "served_route": {"provider": "openai", "model": "gpt-5.4"},
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )
    agent._remember_model_provenance()
    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {
            "served_route": {
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
            },
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )
    agent._remember_model_provenance()
    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {
            "served_route": {"provider": "openai", "model": "gpt-5.4"},
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )
    agent._remember_model_provenance()  # repeat identity: de-duplicated
    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {},
    )
    agent._remember_model_provenance()  # accepted but unattributed call

    provenance = agent._execution_model_provenance({})

    assert provenance["provider"] == "openai"  # latest serving call
    assert provenance["model"] == "gpt-5.4"
    assert provenance["serving_models"] == [
        {"provider": "openai", "model": "gpt-5.4"},
        {"provider": "deepseek", "model": "deepseek-v4-flash"},
    ]
    assert provenance["unattributed_calls"] == 1

    # A run with no LLM calls at all stays silent.
    empty_agent = _agent(world)
    assert empty_agent._execution_model_provenance({}) == {}


def test_serving_pair_is_never_mixed_across_sources(monkeypatch):
    """Regression (graduation review): a partial runtime result must never
    be completed from route attribution — the mixed new-provider/old-model
    pair never served anything. Selection is atomic per source: a source
    that knows both members wins, otherwise the highest-priority source
    yields a partial pair."""
    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {
            "served_route": {
                "provider": "old-provider",
                "model": "old-model",
            },
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )

    # Partial runtime result: the complete call-local served route wins as
    # ONE atomic pair — the result's orphan member is dropped, not mixed in.
    provenance = model_provenance.capture_model_provenance(
        {"provider": "new-provider"})
    assert provenance["provider"] == "old-provider"
    assert provenance["model"] == "old-model"
    assert provenance["source"] == "route_attribution"
    assert "new-provider" not in provenance.values()

    # A COMPLETE runtime result outranks the route attribution.
    provenance = model_provenance.capture_model_provenance(
        {"provider": "new-provider", "model": "new-model"})
    assert provenance["provider"] == "new-provider"
    assert provenance["model"] == "new-model"
    assert provenance["source"] == "runtime_result"
    assert "old-provider" not in provenance.values()
    assert "old-model" not in provenance.values()

    # No complete source anywhere: the highest-priority source yields its
    # partial pair and the missing member stays absent.
    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {
            "served_route": {"provider": "old-provider", "model": ""},
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )
    provenance = model_provenance.capture_model_provenance(
        {"provider": "new-provider"})
    assert provenance["provider"] == "new-provider"
    assert "model" not in provenance
    assert provenance["source"] == "runtime_result"


def test_durable_round_trip_preserves_attribution_source(monkeypatch):
    """A captured attribution riding inside a result payload is not
    relabelled as a runtime result when re-captured durably."""
    captured = model_provenance.capture_model_provenance(
        {"provider": "anthropic", "model": "claude-opus-4"},
        include_route_attribution=False,
    )
    assert captured["source"] == "runtime_result"

    recaptured = model_provenance.capture_model_provenance(
        {"model_provenance": captured}, include_route_attribution=False,
    )
    assert recaptured["provider"] == "anthropic"
    assert recaptured["source"] == "runtime_result"

    monkeypatch.setattr(
        model_provenance, "get_route_attribution", lambda: {
            "served_route": {"provider": "deepseek", "model": "deepseek-v4"},
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )
    attributed = model_provenance.capture_model_provenance()
    assert attributed["source"] == "route_attribution"

    recaptured = model_provenance.capture_model_provenance(
        {"model_provenance": attributed}, include_route_attribution=False,
    )
    assert recaptured["provider"] == "deepseek"
    assert recaptured["source"] == "route_attribution"


def test_runtime_result_identity_wins_over_stale_route_attribution(
    monkeypatch
):
    monkeypatch.setattr(
        model_provenance,
        "get_route_attribution",
        lambda: {
            "served_route": {
                "provider": "previous-provider",
                "model": "previous-model",
            },
            "requested_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "mode": "unpinned",
        },
    )

    provenance = model_provenance.capture_model_provenance({
        "provider": "openai",
        "model": "gpt-5.4",
    })
    assert provenance["provider"] == "openai"
    assert provenance["model"] == "gpt-5.4"
    assert provenance["source"] == "runtime_result"


def test_capture_prefers_served_route_and_never_calls_attempted_route_served(
    monkeypatch
):
    monkeypatch.setattr(
        model_provenance,
        "get_route_attribution",
        lambda: {
            "mode": "unpinned",
            "requested_route": {
                "provider": "primary",
                "model": "primary-large",
            },
            "served_route": {
                "provider": "fallback",
                "model": "fallback-small",
            },
            "resolved_model": "fallback-small-2026-03",
            "routing_result_id": "feedback-row-1",
            "error": None,
        },
    )

    provenance = model_provenance.capture_model_provenance({})
    assert provenance["provider"] == "fallback"
    assert provenance["model"] == "fallback-small"
    assert provenance["resolved_model"] == "fallback-small-2026-03"
    assert provenance["requested_provider"] == "primary"
    assert provenance["requested_model"] == "primary-large"
    assert provenance["fallback"] is True
    assert provenance["routing_result_id"] == "feedback-row-1"
    assert provenance["source"] == "route_attribution"

    # A failed attempt (requested but never served) is not actual service.
    monkeypatch.setattr(
        model_provenance,
        "get_route_attribution",
        lambda: {
            "mode": "unpinned",
            "requested_route": {
                "provider": "primary",
                "model": "primary-large",
            },
            "served_route": None,
            "resolved_model": None,
            "routing_result_id": None,
            "error": {"code": "provider_exception"},
        },
    )
    assert model_provenance.capture_model_provenance({}) == {}


def test_alias_identities_are_not_actual_provenance(monkeypatch):
    assert model_provenance.capture_model_provenance(
        {"provider": "auto", "model": "auto"}) == {}
    assert model_provenance.capture_model_provenance(
        {"provider": "", "model": "unknown"}) == {}


def test_provenance_metadata_round_trips_serving_set():
    provenance = model_provenance.provenance_from_metadata({
        "model_provenance": {
            "provider": "openai",
            "model": "gpt-5.4",
            "serving_models": [
                {"provider": "openai", "model": "gpt-5.4"},
                {"provider": "deepseek", "model": "deepseek-v4-flash"},
                {"provider": "auto", "model": "auto"},  # alias: dropped
                "junk",  # not a pair: dropped
            ],
            "unattributed_calls": 2,
        },
    })
    assert provenance["provider"] == "openai"
    assert provenance["model"] == "gpt-5.4"
    assert provenance["serving_models"] == [
        {"provider": "openai", "model": "gpt-5.4"},
        {"provider": "deepseek", "model": "deepseek-v4-flash"},
    ]
    assert provenance["unattributed_calls"] == 2

    # An explicit unknown marker round-trips to empty, never to a value.
    assert model_provenance.provenance_from_metadata(
        model_provenance.unknown_provenance()) == {}


# ---------------------------------------------------------------------------
# Plain-text (non-structured) dispatch attribution.
#
# Regression (graduation fallback review): BYOKHandler.generate_response had
# no set_served_route success writer, so a plain-text run's accepted response
# never stamped the served pair — GenericAgent read an empty route even though
# the provider answered. These cases drive the REAL dispatch loop with doubled
# provider adapters (no network, no injected attribution) and assert the
# call-local ContextVar the agent loop already consumes.
# ---------------------------------------------------------------------------


class _FakeTextProvider:
    """Doubled provider adapter: records each dispatch, never touches network."""

    def __init__(self, provider_id, model, content="", *, fail=False):
        self.provider_id = provider_id
        self.model = model
        self.content = content
        self.fail = fail
        self.calls = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            # A connection-class failure is provider-wide: the cascade moves
            # on without a same-provider self-heal retry.
            raise RuntimeError(
                f"connection error: {self.provider_id} is unreachable")
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=self.content),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            model=f"{self.model}-echo",
        )


class _StaticPricing:
    def estimate_cost(self, *_args, **_kwargs):
        return 0.001


@contextmanager
def _empty_db():
    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _DB:
        def query(self, *_args, **_kwargs):
            return _Query()

    yield _DB()


def _plain_text_handler(monkeypatch, options, clients):
    """Bare handler with the real generate_response loop and doubled deps."""
    handler = object.__new__(byok_handler.BYOKHandler)
    handler.workspace_id = "ws-plain-text-probe"
    handler.tenant_id = "tenant-plain-text-probe"
    handler.clients = dict(clients)
    handler.env_key_providers = set(clients)
    handler.byok_manager = Mock()
    handler.byok_manager.get_tenant_api_key = Mock(return_value=None)
    handler.health_monitor = Mock()
    handler.health_monitor.record_call = Mock()
    handler.cache_router = Mock()
    handler.cache_router.record_cache_outcome = Mock()
    handler._pending_routing_result_id = None
    handler._last_used_provider = None
    handler._last_used_model = None
    handler.refresh_credentials_if_changed = lambda: None
    handler._is_trial_restricted = lambda: False
    handler.analyze_query_complexity = (
        lambda *a, **k: byok_handler.QueryComplexity.MODERATE)

    async def _optimal(*_args, **_kwargs):
        return options[0]

    async def _ranked(*_args, **_kwargs):
        return list(options)

    async def _rerank(ranked, *_args, **_kwargs):
        return ranked

    async def _feedback(*_args, **_kwargs):
        return None

    handler.get_optimal_provider = _optimal
    handler.get_ranked_providers = _ranked
    handler._rerank_with_learning = _rerank
    handler._record_outcome_feedback = _feedback
    handler._llm_taint_check = lambda *a, **k: None
    handler._model_cooldown_active = lambda *a, **k: False
    handler._provider_cooldown_active = lambda *a, **k: False
    handler._dispatch_catalog_admits = lambda *a, **k: True
    handler._reasoning_request_body = lambda *a, **k: None
    handler._claim_model_attempt = lambda *a, **k: "probe-token"
    handler._release_model_attempt = lambda *a, **k: None
    handler._retain_model_attempt = lambda *a, **k: None
    handler._admit_physical_attempt = lambda **k: 0.0
    handler._settle_physical_response = lambda **k: None
    handler._clear_model_cooldown = lambda *a, **k: None
    handler._record_auth_success = lambda *a, **k: None
    handler._bench_model = lambda *a, **k: None
    handler._bench_provider_on_quota_error = lambda *a, **k: False
    handler._track_rate_usage = lambda *a, **k: None
    handler._track_llm_call = lambda *a, **k: None
    handler._provider_models_cached = lambda *a, **k: []
    handler._local_only_active = lambda: False

    monkeypatch.setattr(byok_handler, "get_db_session", _empty_db)
    monkeypatch.setattr(
        byok_handler, "get_pricing_fetcher", lambda: _StaticPricing())
    monkeypatch.setattr(
        byok_handler,
        "llm_usage_tracker",
        Mock(is_budget_exceeded=Mock(return_value=False), record=Mock()),
    )
    # Success settlement writes the durable ledger; this probe is about
    # attribution, so the ledger boundary is doubled, not exercised.
    monkeypatch.setattr(
        "core.spend_aggregation_service.record_llm_usage",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "core.llm.model_route_registry.get_provider_model_catalog",
        lambda: SimpleNamespace(served=lambda _p: []),
    )
    return handler


def _agent_without_world():
    agent = GenericAgent.__new__(GenericAgent)
    agent._last_model_provenance = {}
    agent._serving_models = []
    agent._unattributed_llm_calls = 0
    return agent


def test_plain_text_success_stamps_the_served_route(monkeypatch):
    provider = _FakeTextProvider(
        "alpha", "alpha-model", content="plain-text answer")
    handler = _plain_text_handler(
        monkeypatch,
        [("alpha", "alpha-model")],
        {"alpha": provider},
    )
    model_provenance.clear_route_attribution()

    async def _run():
        text = await handler.generate_response(
            prompt="hello", task_type="chat")
        return text, _REAL_GET_ROUTE_ATTRIBUTION()

    text, attribution = asyncio.run(_run())

    assert text == "plain-text answer"
    assert attribution["served_route"] == {
        "provider": "alpha", "model": "alpha-model"}
    # The provider echo still rides along; it is not a substitute for the
    # accepted pair.
    assert attribution["resolved_model"] == "alpha-model-echo"
    assert len(provider.calls) == 1


def test_plain_text_fallback_stamps_the_actual_served_route(monkeypatch):
    primary = _FakeTextProvider("alpha", "alpha-large", fail=True)
    fallback = _FakeTextProvider(
        "beta", "beta-small", content="served by beta")
    handler = _plain_text_handler(
        monkeypatch,
        [("alpha", "alpha-large"), ("beta", "beta-small")],
        {"alpha": primary, "beta": fallback},
    )
    # The agent-loop consumer reads through the real module function.
    monkeypatch.setattr(
        model_provenance, "get_route_attribution",
        _REAL_GET_ROUTE_ATTRIBUTION,
    )
    agent = _agent_without_world()
    model_provenance.clear_route_attribution()

    async def _run():
        text = await handler.generate_response(
            prompt="hello", task_type="chat")
        # Consume the Evidence in the SAME task context the handler stamped:
        # contextvars do not propagate back out of asyncio.run.
        agent._remember_model_provenance()
        return text, _REAL_GET_ROUTE_ATTRIBUTION()

    text, attribution = asyncio.run(_run())

    assert text == "served by beta"
    assert attribution["served_route"] == {
        "provider": "beta", "model": "beta-small"}
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 1

    # The existing consumer path (no injected attribution) records the
    # fallback identity, not the attempted primary route.
    provenance = agent._execution_model_provenance({})
    assert provenance["provider"] == "beta"
    assert provenance["model"] == "beta-small"
    assert provenance["source"] == "route_attribution"
    assert "requested_provider" not in provenance
    assert agent._unattributed_llm_calls == 0


def test_plain_text_failed_attempt_is_never_reported_as_served(monkeypatch):
    provider = _FakeTextProvider("alpha", "alpha-model", fail=True)
    handler = _plain_text_handler(
        monkeypatch,
        [("alpha", "alpha-model")],
        {"alpha": provider},
    )
    model_provenance.clear_route_attribution()

    async def _run():
        text = await handler.generate_response(
            prompt="hello", task_type="chat")
        return text, _REAL_GET_ROUTE_ATTRIBUTION()

    text, attribution = asyncio.run(_run())

    assert "couldn't generate a response" in text
    assert attribution["served_route"] is None
    assert attribution["resolved_model"] is None
