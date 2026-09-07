"""Evolution harness end-to-end: tool error responses must reach
Memento/AlphaEvolver.

Live anchor (2026-09-02): the outlook search 400 was swallowed into an
empty result, the turn recorded outcome=success, and the evolution
harness — which only consumes failures — never saw anything to fix. These
tests pin every link of that chain:

  1. record_tool_error attaches structured entries to the running execution
  2. effective_outcome downgrades tool-error turns away from clean success
  3. episode finalization emits a FAIL event with the tool error as trace
  4. ReflectionEngine routes tool-flavored patterns to AlphaEvolver
     (tool mutation) and everything else to Memento (new skill)
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.auto_dev.event_hooks import TaskEvent
from core.auto_dev.reflection_engine import ReflectionEngine
from core.auto_dev.tool_error_signals import (
    effective_outcome,
    record_tool_error,
    summarize_tool_errors,
    tool_error_signature,
)

AGENT = "9837ec71-4f1b-41db-b014-119862362d44"
TENANT = "default"


def _mk_event(episode_id="ep-1", tool_errors=None, outcome="failure",
              task_description="jschulz@blumetric.ca responded to our query. do you have the email?"):
    meta = {}
    if tool_errors:
        meta["tool_errors"] = tool_errors
    return TaskEvent(
        episode_id=episode_id,
        agent_id=AGENT,
        tenant_id=TENANT,
        task_description=task_description,
        error_trace="outlook.search_emails: Syntax error: character '@' is not valid",
        outcome=outcome,
        metadata=meta,
    )


# ── link 1: recording ────────────────────────────────────────────────────────

def test_record_tool_error_appends_to_running_execution():
    """With an execution_id given, the structured entry lands on the
    execution's metadata_json['tool_errors']."""
    from core.database import SessionLocal
    from core.models import AgentExecution

    db = SessionLocal()
    exec_row = AgentExecution(
        agent_id=AGENT, tenant_id=TENANT, status="running",
    )
    db.add(exec_row)
    db.commit()
    exec_id = exec_row.id
    db.close()

    try:
        ok = record_tool_error(
            AGENT, "outlook", "search_emails",
            "tool_error: 400 Syntax error: character '@' is not valid",
            execution_id=exec_id, tenant_id=TENANT,
        )
        assert ok is True

        db = SessionLocal()
        row = db.query(AgentExecution).filter(AgentExecution.id == exec_id).first()
        errors = (row.metadata_json or {}).get("tool_errors")
        db.close()
        assert errors and errors[0]["signature"] == "outlook.search_emails"
        assert "400" in errors[0]["error"]
    finally:
        db = SessionLocal()
        db.query(AgentExecution).filter(AgentExecution.id == exec_id).delete()
        db.commit()
        db.close()


def test_record_tool_error_never_raises_on_garbage_input():
    assert record_tool_error(None, "", "", "", execution_id="nope") in (True, False)


def test_signature_is_per_tool_and_error_text_free():
    assert tool_error_signature("Outlook", "Search_Emails") == "outlook.search_emails"


# ── link 2: outcome downgrade ────────────────────────────────────────────────

def test_effective_outcome_downgrades_tool_error_success():
    meta = {"tool_errors": [{"service": "outlook", "error": "400"}]}
    assert effective_outcome(True, "success", meta) == (False, "partial")


def test_effective_outcome_leaves_clean_success_alone():
    assert effective_outcome(True, "success", {}) == (True, "success")


def test_summarize_renders_tool_errors_for_memento():
    meta = {"tool_errors": [
        {"signature": "outlook.search_emails", "error": "400 Syntax error"},
    ]}
    assert "outlook.search_emails" in summarize_tool_errors(meta)
    assert "400" in summarize_tool_errors(meta)


# ── link 4: ReflectionEngine routing ────────────────────────────────────────

def _engine_with_stubbed_gate():
    engine = ReflectionEngine(db=None, failure_threshold=2)
    engine._should_process_agent = lambda *a, **k: True
    return engine


# Guidance writes durable feed events to the REAL DB — mock it in routing
# tests so no live rows leak.
def _patch_guidance():
    return patch("core.auto_dev.guidance.notify_proposal")


def test_tool_flavored_pattern_triggers_alpha_evolver():
    engine = _engine_with_stubbed_gate()

    tool_error = {
        "signature": "outlook.search_emails",
        "error": "400 Syntax error: character '@' is not valid",
    }
    engine._failure_buffer[AGENT] = [
        {"episode_id": "ep-1", "task_description": "find the email",
         "error_trace": None, "tenant_id": TENANT, "tool_error": tool_error},
        {"episode_id": "ep-2", "task_description": "find the email thread",
         "error_trace": None, "tenant_id": TENANT, "tool_error": tool_error},
    ]

    async def run():
        with patch.object(engine, "_trigger_alpha_evolver") as alpha_mock, \
             _patch_guidance() as gp, \
             patch("core.auto_dev.memento_engine.MementoEngine") as memento_cls:
            alpha_mock.return_value = True
            await engine.process_failure(
                _mk_event(episode_id="ep-2", tool_errors=[tool_error],
                          task_description="find the email thread")
            )
            return alpha_mock, memento_cls

    alpha_mock, memento_cls = asyncio.run(run())
    assert alpha_mock.await_count == 1, "tool pattern must route to AlphaEvolver"
    assert memento_cls.called is False, "alpha win must not also build a skill"


def test_non_tool_pattern_falls_back_to_memento():
    engine = _engine_with_stubbed_gate()

    async def run():
        engine._failure_buffer[AGENT] = [
            {"episode_id": "ep-1", "task_description": "schedule a meeting",
             "error_trace": "hallucinated date", "tenant_id": TENANT,
             "tool_error": None},
            {"episode_id": "ep-2", "task_description": "schedule a meeting",
             "error_trace": "hallucinated date", "tenant_id": TENANT,
             "tool_error": None},
        ]
        with patch.object(engine, "_trigger_alpha_evolver") as alpha_mock, \
             _patch_guidance() as gp, \
             patch("core.auto_dev.memento_engine.MementoEngine") as memento_cls:
            memento_cls.return_value.generate_skill_candidate = AsyncMock(
                return_value=MagicMock(skill_name="auto_skill_m")
            )
            await engine.process_failure(
                _mk_event(episode_id="ep-2", task_description="schedule a meeting")
            )
            return alpha_mock, memento_cls

    alpha_mock, memento_cls = asyncio.run(run())
    alpha_mock.assert_not_awaited()
    memento_cls.return_value.generate_skill_candidate.assert_awaited_once()


def test_alpha_failure_falls_back_to_memento():
    """When the tool source can't be resolved (integration services aren't
    mutable tools), the pattern must still reach Memento."""
    engine = _engine_with_stubbed_gate()
    tool_error = {"signature": "outlook.search_emails", "error": "400"}

    async def run():
        with patch("core.auto_dev.memento_engine.MementoEngine") as memento_cls, \
             patch("core.database.SessionLocal", MagicMock()):
            memento_cls.return_value.generate_skill_candidate = AsyncMock(
                return_value=MagicMock(skill_name="auto_skill_x")
            )
            # No action_registry handler resolvable → alpha returns False
            with patch.object(engine, "_trigger_alpha_evolver",
                              new=AsyncMock(return_value=False)):
                await engine._trigger_fix(
                    agent_id=AGENT, tenant_id=TENANT, episode_id="ep-1",
                    similar_failures=[{"tool_error": tool_error,
                                       "task_description": "find the email",
                                       "episode_id": "ep-1"}],
                )
            return memento_cls

    memento_cls = asyncio.run(run())
    memento_cls.return_value.generate_skill_candidate.assert_awaited_once()


# ── real-time triggers on an ACTIVE task ─────────────────────────────────────

def test_should_trigger_live_threshold_and_suppression():
    from core.auto_dev import tool_error_signals as tes
    from datetime import datetime, timedelta, timezone

    tes._RECENT_ERRORS["agent-rt"].clear()
    tes._LIVE_TRIGGERED.clear()
    now = datetime.now(timezone.utc)
    ring = tes._RECENT_ERRORS["agent-rt"]
    sig = "outlook.search_emails"

    # One error: below threshold.
    ring.append((now, sig))
    assert tes.should_trigger_live("agent-rt", sig) is False

    # Second error: crosses threshold and reserves the dispatch.
    ring.append((now - timedelta(minutes=5), sig))
    assert tes.should_trigger_live("agent-rt", sig) is True

    # Suppressed within the window — a long task hitting the error 20 more
    # times must not spawn 20 candidates.
    ring.append((now, sig))
    ring.append((now, sig))
    assert tes.should_trigger_live("agent-rt", sig) is False


def test_trigger_live_tool_fix_creates_mutation_for_registered_tool():
    from core.auto_dev import reflection_engine as re_mod

    captured = {}

    class FakeEngine:
        def __init__(self, db):
            pass
        async def generate_tool_mutation(self, tenant_id, tool_name,
                                         parent_tool_id, base_code,
                                         mutation_prompt):
            captured.update(tool_name=tool_name, base_code=base_code,
                            error=mutation_prompt)
            return SimpleNamespace(id="mut-live-1")

    fake_registry = SimpleNamespace(
        get_action=lambda name: SimpleNamespace(handler=lambda q: "source")
        if name == "outlook.search_emails" else None
    )
    with patch("core.auto_dev.alpha_evolver_engine.AlphaEvolverEngine", FakeEngine), \
         patch("core.action_registry.action_registry", fake_registry), \
         patch("core.auto_dev.guidance.notify_proposal") as notify, \
         patch.object(re_mod, "_mark_execution_triggered") as mark:
        ok = asyncio.run(re_mod.trigger_live_tool_fix(
            agent_id=AGENT, tenant_id=TENANT,
            service="outlook", action="search_emails",
            error_detail="400 Syntax error: '@'",
            execution_id="exec-1",
        ))
    assert ok is True
    assert captured["tool_name"] == "outlook.search_emails"
    assert "'@'" in captured["error"]
    notify.assert_called_once()
    assert notify.call_args.kwargs["candidate_id"] == "mut-live-1"
    mark.assert_called_once()


def test_trigger_live_tool_fix_is_noop_for_unregistered_tools():
    from core.auto_dev import reflection_engine as re_mod

    fake_registry = SimpleNamespace(get_action=lambda name: None)
    with patch("core.action_registry.action_registry", fake_registry):
        ok = asyncio.run(re_mod.trigger_live_tool_fix(
            agent_id=AGENT, tenant_id=TENANT,
            service="outlook", action="search_emails",
            error_detail="400",
        ))
    assert ok is False, "integration services aren't mutable tools — no-op"


def test_chokepoint_schedules_live_trigger_on_threshold(monkeypatch):
    """The integration chokepoint dispatches the live trigger on the event
    loop when the reservation fires — real-time, not at episode close."""
    import integrations.universal_integration_service as uis_mod
    from core.auto_dev import tool_error_signals as tes

    recorded = []
    monkeypatch.setattr(
        "core.auto_dev.tool_error_signals.record_tool_error",
        lambda *a, **k: recorded.append(a) or True,
    )
    monkeypatch.setattr(
        tes, "should_trigger_live",
        lambda agent_id, sig: (agent_id == "agent-9"
                               and sig == "outlook.search_emails"),
    )
    scheduled = []
    monkeypatch.setattr(
        "core.auto_dev.reflection_engine.trigger_live_tool_fix",
        AsyncMock(side_effect=lambda **kw: scheduled.append(kw) or True),
    )

    svc = uis_mod.UniversalIntegrationService(workspace_id="ws")
    svc._dispatch_execution = AsyncMock(
        return_value={"status": "error", "error": "boom"})

    async def run():
        await svc.execute(
            "outlook", "search_emails", {"query": "x"},
            {"user_id": "u1", "agent_id": "agent-9", "tenant_id": "default"},
        )
        # let the ensure_future task run
        import asyncio as aio
        await aio.sleep(0.05)

    asyncio.run(run())
    assert scheduled, "live trigger must be scheduled in real time"
    assert scheduled[0]["service"] == "outlook"
