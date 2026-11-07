"""Scoped readback of an admitted Generic job's information wait.

Exercises the real public GET route, the real admission receipt, the real
GenericAgent/AgentJob/HITL producers and a scratch SQLite database.  The
high-level ReAct reasoning is controlled at ``GenericAgent._react_step`` (a
labelled reasoning double), so this qualifies the wait/readback join, not model
quality; no live model/provider is used.  The read path must never claim the
job, answer the wait, dispatch a continuation or invoke the model.
"""
from __future__ import annotations

import json

from core.models import AgentExecution, AgentJob, HITLAction, User
from core.react_models import InformationWaitRequest, ReActStep

from tests.test_agent_run_outcome_join_contract import (
    _client,
    _job_payload,
    _run,
    real_env,
)


def _install_model(monkeypatch, steps):
    import core.generic_agent as real_generic

    calls = []

    async def _step(
        self, task_input, memory, history, context=None,
        utility_delta=None,
    ):
        calls.append({
            "task_input": task_input,
            "history": history,
            "context": dict(context or {}),
        })
        index = len(calls) - 1
        if index >= len(steps):
            return ReActStep(thought="done", final_answer="done")
        return steps[index](task_input, history, context or {})

    monkeypatch.setattr(real_generic.GenericAgent, "_react_step", _step)
    return calls


def _read_job(env, job_id, *, user_id="member-1", agent_id="a1"):
    return _client(env, user_id).get(
        f"/api/agents/{agent_id}/jobs/{job_id}")


def _job_readback(env, job_id, **kwargs):
    response = _read_job(env, job_id, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _waiting_job(env, monkeypatch, *, question, missing_fact):
    def first(task_input, history, context):
        return ReActStep(
            thought="One fact is missing.",
            information_wait=InformationWaitRequest(
                question=question,
                missing_fact=missing_fact,
                subject="closing task",
            ),
        )

    calls = _install_model(monkeypatch, [first])
    response = _run(
        env,
        operation_id=f"readback-{missing_fact.replace(' ', '-')}",
        parameters={"sync": True, "task_input": "prepare the closing task"},
    )
    assert response.status_code == 202, response.text
    return response.json()["data"], calls


def test_owner_reads_exact_open_question_and_nothing_private(
    real_env, monkeypatch,
):
    data, calls = _waiting_job(
        real_env, monkeypatch,
        question="What title should the closing task have?",
        missing_fact="task title",
    )
    receipt = data["wait_receipt"]

    body = _job_readback(real_env, data["job_id"])
    assert body["agent_id"] == "a1"
    assert body["job_id"] == data["job_id"]
    assert body["execution_id"] == data["execution_id"]
    assert body["job_status"] == "waiting"
    assert body["next_action"] == "await_information"
    assert body["requires_reconciliation"] is False
    wait = body["wait"]
    assert wait["id"] == receipt["hitl_action_id"]
    assert wait["kind"] == "information_request"
    assert wait["status"] == "pending"
    assert wait["question"] == "What title should the closing task have?"
    assert wait["missing_fact"] == "task title"
    assert wait["subject"] == {"label": "closing task"}
    assert wait["correlation_id"] == receipt["correlation_id"]
    assert wait["can_answer"] is True

    # The read is read-only: the job is still waiting, the wait still open and
    # the model transport was not invoked again.
    job, payload = _job_payload(real_env, data["job_id"])
    assert job.status == "waiting"
    assert payload["waiting"] is True
    with real_env.SessionLocal() as db:
        action = db.get(HITLAction, receipt["hitl_action_id"])
        assert action.status == "pending"
    assert len(calls) == 1

    serialized = json.dumps(body)
    for private_key in (
        "resume_parameters", "resume_history", "resume_steps",
        "context_snapshot", "user_feedback", "claim", "reviewed_by",
        "oracle_expected", "history",
    ):
        assert private_key not in serialized


def test_peer_missing_receipt_and_wrong_scope_cannot_read(
    real_env, monkeypatch,
):
    data, _calls = _waiting_job(
        real_env, monkeypatch,
        question="Which account id?",
        missing_fact="account id",
    )
    job_id = data["job_id"]

    # A peer in the same workspace is still not the admitted actor.
    with real_env.SessionLocal() as db:
        db.add(User(
            id="peer-1", tenant_id="t1", workspace_id="ws1",
            email="peer@example.com", first_name="P", last_name="One",
            role="member", status="active", is_active=True))
        db.commit()
        real_env.actors["peer-1"] = db.get(User, "peer-1")
    peer = _read_job(real_env, job_id, user_id="peer-1")
    assert peer.status_code == 404, peer.text

    # A different tenant/workspace principal with the same permission is not
    # allowed to use the job id as a capability.
    other_scope = _read_job(real_env, job_id, user_id="admin-2")
    assert other_scope.status_code == 404, other_scope.text

    # The job must also belong to the agent named in the path.
    wrong_agent = _read_job(real_env, job_id, agent_id="a2")
    assert wrong_agent.status_code == 404, wrong_agent.text
    assert _read_job(real_env, "does-not-exist").status_code == 404

    # A legacy/forged job without its admission receipt fails closed even for
    # the same authenticated caller.
    with real_env.SessionLocal() as db:
        job = db.get(AgentJob, job_id)
        payload = json.loads(job.result_summary or "{}")
        payload.pop("operation_id", None)
        job.result_summary = json.dumps(payload)
        db.commit()
    assert _read_job(real_env, job_id).status_code == 404


def test_missing_current_wait_is_reported_as_failed_not_answerable(
    real_env, monkeypatch,
):
    data, _calls = _waiting_job(
        real_env, monkeypatch,
        question="Which code?",
        missing_fact="code",
    )
    receipt = data["wait_receipt"]

    with real_env.SessionLocal() as db:
        action = db.get(HITLAction, receipt["hitl_action_id"])
        db.delete(action)
        db.commit()

    body = _job_readback(real_env, data["job_id"])
    # The durable status is still waiting; no question is exposed and the
    # caller is sent to review rather than being told a fake terminal failure.
    assert body["job_status"] == "waiting"
    assert body["next_action"] == "review_execution"
    assert body["wait_unavailable"] is True
    assert "wait" not in body
    assert body["requires_reconciliation"] is False


def test_second_question_and_final_result_read_back_on_the_same_job(
    real_env, monkeypatch,
):
    def first(task_input, history, context):
        return ReActStep(
            thought="Need the title.",
            information_wait=InformationWaitRequest(
                question="What title?", missing_fact="title"))

    def second(task_input, history, context):
        assert context["information_answer"] == "Closing task"
        return ReActStep(
            thought="Now the priority is missing.",
            information_wait=InformationWaitRequest(
                question="What priority?", missing_fact="priority"))

    def finished(task_input, history, context):
        assert context["information_answer"] == "high"
        return ReActStep(
            thought="The authorized facts are available.",
            final_answer="Prepared the closing task with the authorized facts.")

    calls = _install_model(monkeypatch, [first, second, finished])
    start = _run(
        real_env,
        operation_id="readback-second-question",
        parameters={"sync": True, "task_input": "prepare the closing task"},
    )
    assert start.status_code == 202, start.text
    first_data = start.json()["data"]
    job_id = first_data["job_id"]
    execution_id = first_data["execution_id"]
    first_wait = first_data["wait_receipt"]

    answer1 = _client(real_env).post(
        f"/api/agents/a1/jobs/{job_id}/answer",
        json={
            "answer": "Closing task",
            "correlation_id": first_wait["correlation_id"],
        },
    )
    assert answer1.status_code == 202, answer1.text
    second_wait = answer1.json()["data"]["wait_receipt"]
    assert second_wait["hitl_action_id"] != first_wait["hitl_action_id"]

    # Reload/readback shows the NEW exact question, same job/execution.
    waiting = _job_readback(real_env, job_id)
    assert waiting["job_status"] == "waiting"
    assert waiting["execution_id"] == execution_id
    assert waiting["wait"]["id"] == second_wait["hitl_action_id"]
    assert waiting["wait"]["question"] == "What priority?"
    assert waiting["wait"]["correlation_id"] == second_wait["correlation_id"]
    assert waiting["wait"]["can_answer"] is True
    calls_before_read = len(calls)

    answer2 = _client(real_env).post(
        f"/api/agents/a1/jobs/{job_id}/answer",
        json={
            "answer": "high",
            "correlation_id": second_wait["correlation_id"],
        },
    )
    assert answer2.status_code == 200, answer2.text
    assert answer2.json()["data"]["job_status"] == "success"

    final = _job_readback(real_env, job_id)
    assert final["job_status"] == "success"
    assert final["execution_id"] == execution_id
    assert "wait" not in final
    assert final["result"] == {
        "status": "success",
        "output": "Prepared the closing task with the authorized facts.",
    }
    # Readback itself never continued the model/worker.
    assert len(calls) == calls_before_read + 1
    job, payload = _job_payload(real_env, job_id)
    assert job.status == "success"
    assert payload["outcome"] == "success"


def test_foreign_wait_scope_is_never_exposed(real_env, monkeypatch):
    data, _calls = _waiting_job(
        real_env, monkeypatch,
        question="Which account id?",
        missing_fact="account id",
    )
    receipt = data["wait_receipt"]
    with real_env.SessionLocal() as db:
        action = db.get(HITLAction, receipt["hitl_action_id"])
        action.workspace_id = "ws2"
        db.commit()

    body = _job_readback(real_env, data["job_id"])
    assert body["job_status"] == "waiting"
    assert body["wait_unavailable"] is True
    assert "wait" not in body


def test_foreign_execution_scope_does_not_expose_the_result(
    real_env, monkeypatch,
):
    def first(task_input, history, context):
        return ReActStep(
            thought="Need the title.",
            information_wait=InformationWaitRequest(
                question="What title?", missing_fact="title"))

    def finished(task_input, history, context):
        return ReActStep(thought="done", final_answer="public answer")

    _install_model(monkeypatch, [first, finished])
    start = _run(
        real_env,
        operation_id="readback-foreign-result",
        parameters={"sync": True, "task_input": "prepare the closing task"},
    )
    first_data = start.json()["data"]
    receipt = first_data["wait_receipt"]
    answered = _client(real_env).post(
        f"/api/agents/a1/jobs/{first_data['job_id']}/answer",
        json={
            "answer": "Closing task",
            "correlation_id": receipt["correlation_id"],
        },
    )
    assert answered.status_code == 200, answered.text

    with real_env.SessionLocal() as db:
        execution = db.get(AgentExecution, first_data["execution_id"])
        execution.workspace_id = "ws2"
        db.commit()

    body = _job_readback(real_env, first_data["job_id"])
    assert body["job_status"] == "success"
    assert "result" not in body
