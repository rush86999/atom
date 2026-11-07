"""G1: a prolonged Generic information wait is idle, not active execution.

The Generic run/job contract has no wall budget or absolute deadline field;
this test records that limitation instead of inventing a budget engine. It
advances a controlled clock by two hours, performs authorized job reads, and
asserts the durable wait/receipt is unchanged with no additional model call.
The existing actual-process recovery tests cover restart after the same wait.
"""
from __future__ import annotations

from datetime import timedelta

from core.models import HITLAction
from core.react_models import InformationWaitRequest, ReActStep

from tests.test_agent_generic_information_wait import (
    _install_model,
    _seed_board,
)
from tests.test_agent_run_outcome_join_contract import (
    _client,
    _job_payload,
    _run,
    real_env,  # noqa: F401
)


def test_prolonged_generic_wait_retains_receipt_without_model_poll(
        real_env, monkeypatch, freezer):
    _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="Need the exact title before creating the task.",
            information_wait=InformationWaitRequest(
                question="What title should the idle task have?",
                missing_fact="task title",
                subject="idle closing task",
            ),
        )

    calls = _install_model(monkeypatch, [first])
    response = _run(
        real_env, operation_id="generic-idle-wait",
        parameters={"sync": True, "task_input": "Create the idle task"})
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    receipt = data["wait_receipt"]
    assert data["job_status"] == "waiting"
    assert len(calls) == 1, "a durable wait must not poll the model"

    # Move the controlled clock forward without answering anything.
    freezer.tick(timedelta(hours=2))
    read = _client(real_env).get(f"/api/agents/a1/jobs/{job_id}")
    assert read.status_code == 200, read.text
    payload = read.json()["data"]
    assert payload["job_status"] == "waiting"
    assert payload["execution_id"] == execution_id
    wait = payload.get("wait") or payload.get("wait_receipt") or {}
    assert wait.get("id") == receipt["hitl_action_id"]
    assert wait.get("correlation_id") == receipt["correlation_id"]
    assert len(calls) == 1, "a read must not poll the model"

    freezer.tick(timedelta(hours=2))
    job, durable = _job_payload(real_env, job_id)
    assert job.status == "waiting"
    durable_wait = durable.get("wait_receipt") or durable.get("wait") or {}
    assert durable_wait.get("hitl_action_id") == receipt["hitl_action_id"]
    assert durable_wait.get("correlation_id") == receipt["correlation_id"]
    assert len(calls) == 1, "prolonged idle must not call the model"
    with real_env.SessionLocal() as db:
        wait = db.get(HITLAction, receipt["hitl_action_id"])
        assert wait is not None and wait.status == "pending"
        assert wait.user_feedback is None
