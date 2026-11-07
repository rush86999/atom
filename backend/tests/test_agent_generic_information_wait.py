"""GenericAgent durable information wait -> same-job authorized resume.

Real public routes, real GenericAgent/lifecycle/registry, real AgentJob and
HITL wait row, scratch SQLite.  Only the model transport is doubled and is
labelled as such.  The post-answer work is a REAL registered ``tasks.create``
action verified by the default oracle against the scratch board row.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.generic_agent as real_generic
from core.models import AgentExecution, AgentJob, AgentRegistry, HITLAction, User
from core.models_board import Board, BoardColumn, BoardTask
from core.react_models import InformationWaitRequest, ReActStep, ToolCall
from tests.test_agent_run_outcome_join_contract import (
    _client,
    _job_payload,
    _run,
    real_env,
)

# The ``real_env`` fixture replaces ``_react_step`` with a small mechanics
# double. Keep a handle to the production consumer so the qualification test
# below can exercise the real prompt/schema path; the fixture patch happens
# after this module is imported.
_PRODUCTION_REACT_STEP = real_generic.GenericAgent._react_step


def _seed_board(env):
    board_id = "board-generic-wait"
    column_id = "column-generic-wait"
    session = env.SessionLocal()
    try:
        # The post-answer work is a registered mutation. This test is about
        # the wait/resume join, not the separate maturity-approval gate, so
        # use an autonomous test agent (the approval path is still covered by
        # its own existing contracts).
        agent = session.get(AgentRegistry, "a1")
        agent.status = "autonomous"
        session.add(Board(
            id=board_id, name="Wait board", owner_user_id="member-1"))
        session.add(BoardColumn(
            id=column_id, board_id=board_id, name="Backlog", position=0))
        session.commit()
    finally:
        session.close()
    return board_id, column_id


def _install_model(monkeypatch, steps):
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


def _wait_answer(env, job_id, answer, correlation_id=None):
    body = {"answer": answer}
    if correlation_id is not None:
        body["correlation_id"] = correlation_id
    return _client(env).post(
        f"/api/agents/a1/jobs/{job_id}/answer", json=body)


def _assert_same_execution(env, job_id, execution_id):
    job, payload = _job_payload(env, job_id)
    assert str(payload.get("execution_id")
               or payload.get("dispatch_execution_id")) == str(execution_id)
    return job, payload


def test_generic_info_wait_resumes_same_job_to_verified_result(
    real_env, monkeypatch,
):
    board_id, column_id = _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="I need the exact task title before creating the task.",
            information_wait=InformationWaitRequest(
                question="What title should the closing task have?",
                missing_fact="task title",
                subject="closing task",
            ),
        )

    def resumed(task_input, history, context):
        # The authorized answer and the useful prior work must both survive
        # into the SAME execution (no new job/objective, no injected plan).
        assert context["information_answer"] == "Quarterly close checklist"
        assert "I need the exact task title" in history
        return ReActStep(
            thought="The authorized title is available; create the task.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id,
                    "column_id": column_id,
                    "title": context["information_answer"],
                    "status": "backlog",
                },
            ),
        )

    def finished(task_input, history, context):
        return ReActStep(
            thought="The task exists and was verified.",
            final_answer="Created the task from the authorized title.",
        )

    calls = _install_model(monkeypatch, [first, resumed, finished])

    response = _run(
        real_env,
        operation_id="generic-info-wait",
        parameters={"sync": True, "task_input": "Create the closing task"},
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    receipt = data["wait_receipt"]
    assert data["job_status"] == "waiting"
    assert data["next_action"] == "await_information"
    assert receipt["kind"] == "information_request"
    assert receipt["verified"] is True
    assert receipt["question"] == "What title should the closing task have?"
    assert receipt["correlation_id"]
    assert len(calls) == 1, "a wait must not poll the model"

    job, payload = _assert_same_execution(real_env, job_id, execution_id)
    assert job.status == "waiting" and job.end_time is None
    assert payload["finished"] is False
    assert payload["wait_receipt"]["hitl_action_id"] == receipt["hitl_action_id"]
    with real_env.SessionLocal() as db:
        first_execution = db.get(AgentExecution, execution_id)
        assert first_execution is not None
        assert first_execution.status == "waiting"
        assert first_execution.metadata_json["resume_state"]["history"]

    answer = _wait_answer(
        real_env, job_id, "Quarterly close checklist",
        correlation_id=receipt["correlation_id"])
    assert answer.status_code == 200, answer.text
    body = answer.json()["data"]
    assert body["job_status"] == "success"
    assert body["execution_id"] == execution_id
    assert body["result"]["output"] == (
        "Created the task from the authorized title.")
    # The registered action produced an independently verified result; the
    # answer/status alone is not used as completion evidence.
    task_steps = [
        step for step in body["result"].get("steps") or []
        if (step.get("action") or {}).get("tool") == "tasks.create"
    ]
    assert task_steps
    assert task_steps[0]["output"].get("oracle_verified") is True

    job, payload = _assert_same_execution(real_env, job_id, execution_id)
    assert job.status == "success"
    assert payload["outcome"] == "success"
    with real_env.SessionLocal() as db:
        tasks = db.query(BoardTask).filter(
            BoardTask.board_id == board_id).all()
        assert len(tasks) == 1
        assert tasks[0].title == "Quarterly close checklist"
        execution = db.get(AgentExecution, execution_id)
        assert execution is not None
        assert execution.status == "success"
        assert "resume_state" not in (execution.metadata_json or {})
        rows = db.query(HITLAction).filter(
            HITLAction.action_type == "agent_information_request").all()
        assert [row.id for row in rows] == [receipt["hitl_action_id"]]
    assert calls[-1]["context"]["information_wait_resume"] is True
    assert calls[-1]["context"]["job_id"] == job_id
    assert calls[-1]["context"]["execution_id"] == execution_id


def test_wrong_correlation_cannot_resume_the_wait(real_env, monkeypatch):
    board_id, column_id = _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="Need one fact.",
            information_wait=InformationWaitRequest(
                question="Which account id?",
                missing_fact="account id"),
        )

    calls = _install_model(monkeypatch, [first])
    response = _run(
        real_env, operation_id="generic-wrong-correlation",
        parameters={"sync": True, "task_input": "Look up the account"})
    assert response.status_code == 202, response.text
    data = response.json()["data"]

    bad = _wait_answer(
        real_env, data["job_id"], "ACC-1", correlation_id="wrong-correlation")
    assert bad.status_code == 409, bad.text
    job, _ = _assert_same_execution(
        real_env, data["job_id"], data["execution_id"])
    assert job.status == "waiting"
    assert len(calls) == 1


def test_duplicate_answer_does_not_dispatch_again(real_env, monkeypatch):
    board_id, column_id = _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="Need the title.",
            information_wait=InformationWaitRequest(
                question="Title?", missing_fact="title"))

    def resumed(task_input, history, context):
        return ReActStep(
            thought="Create once.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id, "column_id": column_id,
                    "title": context["information_answer"]}))

    def finished(task_input, history, context):
        return ReActStep(thought="done", final_answer="done")

    calls = _install_model(monkeypatch, [first, resumed, finished])
    response = _run(
        real_env, operation_id="generic-duplicate-answer",
        parameters={"sync": True, "task_input": "create a task"})
    data = response.json()["data"]
    correlation_id = data["wait_receipt"]["correlation_id"]
    first_answer = _wait_answer(
        real_env, data["job_id"], "Unique title",
        correlation_id=correlation_id)
    assert first_answer.status_code == 200, first_answer.text
    calls_after_first = len(calls)

    replay = _wait_answer(
        real_env, data["job_id"], "Unique title",
        correlation_id=correlation_id)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"].get("already_resumed") is True
    assert len(calls) == calls_after_first
    with real_env.SessionLocal() as db:
        assert db.query(BoardTask).filter(
            BoardTask.board_id == board_id).count() == 1


def test_answer_after_cancellation_cannot_revive_the_job(
    real_env, monkeypatch,
):
    _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="Need the code.",
            information_wait=InformationWaitRequest(
                question="Which code?", missing_fact="code"))

    calls = _install_model(monkeypatch, [first])
    response = _run(
        real_env, operation_id="generic-cancelled-wait",
        parameters={"sync": True, "task_input": "use the code"})
    data = response.json()["data"]
    with real_env.SessionLocal() as db:
        job = db.get(AgentJob, data["job_id"])
        job.status = "cancelled"
        db.commit()

    late = _wait_answer(
        real_env, data["job_id"], "CODE-9",
        correlation_id=data["wait_receipt"]["correlation_id"])
    assert late.status_code == 409, late.text
    assert len(calls) == 1
    job, payload = _assert_same_execution(
        real_env, data["job_id"], data["execution_id"])
    assert job.status == "cancelled"
    assert payload["wait_receipt"]["hitl_action_id"]


def test_legacy_approvals_input_surface_resumes_the_same_wait(
    real_env, monkeypatch,
):
    board_id, column_id = _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="Need the title.",
            information_wait=InformationWaitRequest(
                question="Approvals title?", missing_fact="title"))

    def resumed(task_input, history, context):
        assert context["information_answer"] == "Title from approvals"
        return ReActStep(
            thought="Create from the approval-surface answer.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id, "column_id": column_id,
                    "title": context["information_answer"]}))

    def finished(task_input, history, context):
        return ReActStep(thought="done", final_answer="created")

    calls = _install_model(monkeypatch, [first, resumed, finished])
    start = _run(
        real_env, operation_id="generic-approvals-input",
        parameters={"sync": True, "task_input": "create from approvals"})
    data = start.json()["data"]
    wait_id = data["wait_receipt"]["hitl_action_id"]

    # The shared approvals surface requires AGENT_MANAGE; the wait actor is
    # promoted for this input-surface test without changing the run actor.
    with real_env.SessionLocal() as db:
        user = db.get(User, "member-1")
        user.role = "admin"
        db.commit()
    real_env.actors["member-1"].role = "admin"

    decided = _client(real_env).post(
        f"/api/agents/approvals/{wait_id}",
        json={"decision": "approved", "feedback": "Title from approvals"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["data"]["resume"]["resumed"] is True
    job, payload = _assert_same_execution(
        real_env, data["job_id"], data["execution_id"])
    assert job.status == "success"
    with real_env.SessionLocal() as db:
        task = db.query(BoardTask).filter(
            BoardTask.board_id == board_id).one()
        assert task.title == "Title from approvals"
    calls_after = len(calls)

    # A different replay answer is refused; the same one is idempotent and
    # does not dispatch the model again.
    conflict = _client(real_env).post(
        f"/api/agents/approvals/{wait_id}",
        json={"decision": "approved", "feedback": "Different answer"},
    )
    assert conflict.status_code == 409, conflict.text
    same = _client(real_env).post(
        f"/api/agents/approvals/{wait_id}",
        json={"decision": "approved", "feedback": "Title from approvals"},
    )
    assert same.status_code == 200, same.text
    assert len(calls) == calls_after


def test_second_missing_fact_waits_again_then_completes(
    real_env, monkeypatch,
):
    board_id, column_id = _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="Need the title.",
            information_wait=InformationWaitRequest(
                question="Title?", missing_fact="title"))

    def second(task_input, history, context):
        assert context["information_answer"] == "First answer"
        assert "Need the title" in history
        return ReActStep(
            thought="Now I need the priority.",
            information_wait=InformationWaitRequest(
                question="Priority?", missing_fact="priority"))

    def third(task_input, history, context):
        assert context["information_answer"] == "high"
        assert "First answer" in history
        assert "Priority?" in history
        return ReActStep(
            thought="Create with both facts.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id, "column_id": column_id,
                    "title": "Second pass title",
                    "priority": context["information_answer"]}))

    def finished(task_input, history, context):
        return ReActStep(thought="done", final_answer="created")

    calls = _install_model(monkeypatch, [first, second, third, finished])
    start = _run(
        real_env, operation_id="generic-second-prerequisite",
        parameters={"sync": True, "task_input": "prepare the task"})
    first_data = start.json()["data"]
    first_job_id = first_data["job_id"]
    execution_id = first_data["execution_id"]
    first_wait = first_data["wait_receipt"]

    # The first answer is useful retained work, not completion.
    answer1 = _wait_answer(
        real_env, first_job_id, "First answer",
        correlation_id=first_wait["correlation_id"])
    assert answer1.status_code == 202, answer1.text
    second_data = answer1.json()["data"]
    assert second_data["job_status"] == "waiting"
    assert second_data["execution_id"] == execution_id
    second_wait = second_data["wait_receipt"]
    assert second_wait["hitl_action_id"] != first_wait["hitl_action_id"]
    assert second_wait["question"] == "Priority?"

    answer2 = _wait_answer(
        real_env, first_job_id, "high",
        correlation_id=second_wait["correlation_id"])
    assert answer2.status_code == 200, answer2.text
    assert answer2.json()["data"]["job_status"] == "success"
    job, payload = _assert_same_execution(
        real_env, first_job_id, execution_id)
    assert job.status == "success"
    with real_env.SessionLocal() as db:
        tasks = db.query(BoardTask).filter(
            BoardTask.board_id == board_id).all()
        assert len(tasks) == 1
        assert tasks[0].title == "Second pass title"
        assert tasks[0].priority == "high"
        waits = db.query(HITLAction).filter(
            HITLAction.action_type == "agent_information_request"
        ).order_by(HITLAction.created_at.asc()).all()
        assert len(waits) == 2
        assert {row.status for row in waits} == {"approved"}
    assert len(calls) == 4


def test_answer_without_wait_identity_is_refused_before_acceptance(
    real_env, monkeypatch,
):
    """A job id alone never selects whichever wait happens to be current."""
    _seed_board(real_env)

    def first(task_input, history, context):
        return ReActStep(
            thought="Need the title.",
            information_wait=InformationWaitRequest(
                question="Which title?", missing_fact="title"))

    calls = _install_model(monkeypatch, [first])
    start = _run(
        real_env, operation_id="generic-unbound-answer",
        parameters={"sync": True, "task_input": "create a task"})
    assert start.status_code == 202, start.text
    data = start.json()["data"]
    job_id = data["job_id"]
    first_wait = data["wait_receipt"]

    # No correlation_id at all: the new route refuses instead of guessing.
    unbound = _wait_answer(real_env, job_id, "Unbound title")
    assert unbound.status_code == 422, unbound.text
    job, _payload = _assert_same_execution(
        real_env, job_id, data["execution_id"])
    assert job.status == "waiting"
    with real_env.SessionLocal() as db:
        row = db.get(HITLAction, first_wait["hitl_action_id"])
        assert row.status == "pending"
    assert len(calls) == 1

    # The exact server-owned identity still answers the original wait.
    bound = _wait_answer(
        real_env, job_id, "Bound title",
        correlation_id=first_wait["correlation_id"])
    assert bound.status_code == 200, bound.text
    assert bound.json()["data"]["job_status"] == "success"


def test_old_answer_cannot_settle_the_next_wait(real_env, monkeypatch):
    """Repeated byte-identical delivery cannot answer a later prerequisite."""
    board_id, column_id = _seed_board(real_env)

    def title(task_input, history, context):
        return ReActStep(
            thought="Need the title.",
            information_wait=InformationWaitRequest(
                question="What title?", missing_fact="title"))

    def priority(task_input, history, context):
        assert context["information_answer"] == "Closing task"
        return ReActStep(
            thought="Now the priority is missing.",
            information_wait=InformationWaitRequest(
                question="What priority?", missing_fact="priority"))

    def create(task_input, history, context):
        return ReActStep(
            thought="Both facts are authorized; create the task.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id,
                    "column_id": column_id,
                    "title": "Closing task",
                    "priority": context["information_answer"],
                }))

    def finished(task_input, history, context):
        return ReActStep(thought="done", final_answer="created")

    calls = _install_model(monkeypatch, [title, priority, create, finished])
    start = _run(
        real_env, operation_id="generic-repeated-prerequisite",
        parameters={
            "sync": True,
            "task_input": "Create a task after obtaining its title and priority",
        })
    assert start.status_code == 202, start.text
    data = start.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    first_wait = data["wait_receipt"]

    first = _wait_answer(
        real_env, job_id, "Closing task",
        correlation_id=first_wait["correlation_id"])
    assert first.status_code == 202, first.text
    second_wait = first.json()["data"]["wait_receipt"]
    assert second_wait["hitl_action_id"] != first_wait["hitl_action_id"]
    assert second_wait["question"] == "What priority?"
    calls_after_second_wait = len(calls)

    # The exact old event is replayed byte-for-byte (same answer body and the
    # correlation from the FIRST receipt). It must refuse, not settle the new
    # priority wait or invoke the model again.
    replay = _wait_answer(
        real_env, job_id, "Closing task",
        correlation_id=first_wait["correlation_id"])
    assert replay.status_code == 409, replay.text
    # A body with no identity is refused too: it cannot mean "current wait".
    unbound = _wait_answer(real_env, job_id, "Closing task")
    assert unbound.status_code == 422, unbound.text
    assert len(calls) == calls_after_second_wait
    with real_env.SessionLocal() as db:
        row = db.get(HITLAction, second_wait["hitl_action_id"])
        assert row.status == "pending"
        original = db.get(HITLAction, first_wait["hitl_action_id"])
        assert original.status == "approved"
        assert original.user_feedback == "Closing task"
        assert db.query(BoardTask).filter(
            BoardTask.board_id == board_id).count() == 0

    # The NEW wait is answered only with its own server-owned correlation.
    second = _wait_answer(
        real_env, job_id, "high",
        correlation_id=second_wait["correlation_id"])
    assert second.status_code == 200, second.text
    assert second.json()["data"]["job_status"] == "success"
    job, _payload = _assert_same_execution(real_env, job_id, execution_id)
    assert job.status == "success"
    with real_env.SessionLocal() as db:
        tasks = db.query(BoardTask).filter(
            BoardTask.board_id == board_id).all()
        assert len(tasks) == 1
        assert tasks[0].title == "Closing task"
        assert tasks[0].priority == "high"
    assert len(calls) == calls_after_second_wait + 2


def test_real_react_step_consumer_answers_wait_and_verifies_effect(
    real_env, monkeypatch,
):
    """Qualify the real ``_react_step`` schema/prompt consumer, not a double.

    Transport is controlled at the ``LLMService.generate_structured``
    boundary: the production method still builds the ReAct prompt, the real
    ``response_model`` validates the scripted step, and the resumed execution
    history carries the authorized answer into that prompt. No live
    inference/provider is used, and the server-owned wait identity/authority
    is never placed in the model request.
    """
    board_id, column_id = _seed_board(real_env)
    monkeypatch.setattr(
        real_generic.GenericAgent, "_react_step", _PRODUCTION_REACT_STEP)

    scripted = [
        {
            "thought": "The task title is missing.",
            "information_wait": {
                "question": "What title should the closing task have?",
                "missing_fact": "title",
            },
        },
        {
            "thought": "The authorized title is available; create the task.",
            "action": {
                "tool": "tasks.create",
                "params": {
                    "board_id": board_id,
                    "column_id": column_id,
                    "title": "Quarterly close checklist",
                    "status": "backlog",
                },
            },
        },
        {
            "thought": "The registered action result was verified.",
            "final_answer": "Created the task from the authorized title.",
        },
    ]
    transport = []

    async def controlled_structured(
        self, prompt, response_model, system_instruction="", **kwargs
    ):
        # Same production schema/validation path the real service uses.
        payload = scripted.pop(0)
        transport.append({
            "prompt": prompt,
            "system_instruction": system_instruction,
            "response_model": response_model,
            "kwargs": dict(kwargs),
        })
        return response_model.model_validate(payload)

    monkeypatch.setattr(
        real_generic.LLMService, "generate_structured", controlled_structured)

    start = _run(
        real_env, operation_id="generic-real-react-consumer",
        parameters={"sync": True, "task_input": "Create the closing task"})
    assert start.status_code == 202, start.text
    data = start.json()["data"]
    receipt = data["wait_receipt"]
    assert receipt["kind"] == "information_request"
    assert len(transport) == 1
    assert transport[0]["response_model"] is ReActStep
    assert "AVAILABLE TOOLS:" in transport[0]["system_instruction"]
    assert "information_wait" in transport[0]["system_instruction"]
    # The server-owned wait identity/authority is not taught to the model.
    assert receipt["correlation_id"] not in transport[0]["prompt"]
    assert receipt["correlation_id"] not in transport[0]["system_instruction"]
    assert receipt["hitl_action_id"] not in transport[0]["prompt"]
    assert data["job_status"] == "waiting"

    answer = _wait_answer(
        real_env, data["job_id"], "Quarterly close checklist",
        correlation_id=receipt["correlation_id"])
    assert answer.status_code == 200, answer.text
    body = answer.json()["data"]
    assert body["job_status"] == "success"
    assert body["execution_id"] == data["execution_id"]
    assert len(transport) == 3
    # The real consumer received the answer through the same execution
    # history it builds for an ordinary ReAct step.
    resumed_prompt = transport[1]["prompt"]
    assert "AUTHORIZED INFORMATION ANSWER" in resumed_prompt
    assert "Quarterly close checklist" in resumed_prompt
    assert "What title should the closing task have?" in resumed_prompt

    task_steps = [
        step for step in body["result"].get("steps") or []
        if (step.get("action") or {}).get("tool") == "tasks.create"
    ]
    assert task_steps
    assert task_steps[0]["output"].get("oracle_verified") is True
    with real_env.SessionLocal() as db:
        task = db.query(BoardTask).filter(
            BoardTask.board_id == board_id).one()
        assert task.title == "Quarterly close checklist"
