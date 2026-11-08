"""A failed assignment wake must not switch to a different execution engine."""
import asyncio
import logging
import sys
import types

import pytest

from core.goals.goal_run_events import _resume_woken_run


@pytest.mark.parametrize("failure_stage", ["lookup", "reply", "resume"])
def test_assignment_wake_failure_never_advances_general_router(monkeypatch, caplog, failure_stage):
    private_detail = "PRIVATE_WAKE_FAILURE_DETAIL"
    calls = []

    class Lifecycle:
        def __init__(self, svc):
            pass

        def get_task(self, run_id):
            if failure_stage == "lookup":
                raise RuntimeError(private_detail)
            return {"assignment": {"id": run_id}}

    class Executor:
        def __init__(self, lifecycle):
            pass

        def record_external_response(self, *args, **kwargs):
            if failure_stage == "reply":
                raise RuntimeError(private_detail)
            return {"status": "accepted"}

        async def resume(self, run_id):
            raise RuntimeError(private_detail)

    class Service:
        async def advance(self, *args, **kwargs):
            calls.append("general-router")
            return {"status": "advanced"}

    lifecycle_module = types.ModuleType("core.task_lifecycle")
    lifecycle_module.TaskLifecycle = Lifecycle
    executor_module = types.ModuleType("core.assignment_executor")
    executor_module.AssignmentExecutor = Executor
    monkeypatch.setitem(sys.modules, "core.task_lifecycle", lifecycle_module)
    monkeypatch.setitem(sys.modules, "core.assignment_executor", executor_module)
    with caplog.at_level(logging.WARNING):
        result = asyncio.run(_resume_woken_run(
            Service(), "run-exact", {"correlation_id": "reply-exact"}))
    assert calls == []
    assert result == {"status": "unavailable",
                      "code": "assignment_wake_resume_unavailable", "run_id": "run-exact"}
    assert private_detail not in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.parametrize("reply_status,replayed,should_resume", [
    ("blocked", False, False), ("", False, False),
    ("future_refusal", False, False), ("resolved", False, True),
    ("resumed", False, True), ("resolved", True, False),
    ("resumed", True, False),
])
def test_only_new_accepted_reply_can_resume_assignment(
        monkeypatch, reply_status, replayed, should_resume):
    calls = []

    class Lifecycle:
        def __init__(self, svc):
            pass

        def get_task(self, run_id):
            return {"assignment": {"id": run_id}}

    class Executor:
        def __init__(self, lifecycle):
            pass

        def record_external_response(self, *args, **kwargs):
            return {"status": reply_status, "replayed": replayed}

        async def resume(self, run_id):
            calls.append("assignment")
            return {"status": "executed"}

    class Service:
        async def advance(self, *args, **kwargs):
            calls.append("general")

    lifecycle_module = types.ModuleType("core.task_lifecycle")
    lifecycle_module.TaskLifecycle = Lifecycle
    executor_module = types.ModuleType("core.assignment_executor")
    executor_module.AssignmentExecutor = Executor
    monkeypatch.setitem(sys.modules, "core.task_lifecycle", lifecycle_module)
    monkeypatch.setitem(sys.modules, "core.assignment_executor", executor_module)
    result = asyncio.run(_resume_woken_run(
        Service(), "run-exact", {"correlation_id": "reply-exact"}))
    assert calls == (["assignment"] if should_resume else [])
    assert result == ({"status": "executed"} if should_resume else
                      {"status": reply_status, "replayed": replayed})
