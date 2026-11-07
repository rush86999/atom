"""G4: two Generic jobs keep two waits/answers/effects isolated.

Real public run/answer routes, real Generic consumer/lifecycle, real registered
``tasks.create`` and default Oracle, scratch SQLite. Only the model transport is
doubled. Answering A must not wake, call, or create the task for B; a stale A
correlation delivered to B is refused; each job produces exactly one task.
"""
from __future__ import annotations

from core.models import AgentExecution, AgentJob, HITLAction
from core.models_board import BoardTask
from core.react_models import InformationWaitRequest, ReActStep, ToolCall

import core.generic_agent as real_generic

from tests.test_agent_generic_information_wait import _seed_board, _wait_answer
from tests.test_agent_run_outcome_join_contract import (
    _job_payload,
    _run,
    real_env,  # noqa: F401
)


def _label(task_input: str) -> str:
    return "A" if "task A" in task_input else "B"


def test_two_generic_jobs_keep_waits_and_answers_isolated(
        real_env, monkeypatch):
    board_id, column_id = _seed_board(real_env)
    calls = []
    stages = {"A": 0, "B": 0}

    async def _step(self, task_input, memory, history, context=None,
                    utility_delta=None):
        label = _label(task_input)
        calls.append({"label": label, "task_input": task_input,
                      "context": dict(context or {})})
        answer = str((context or {}).get("information_answer") or "")
        stage = stages[label]
        stages[label] += 1
        if stage == 0:
            return ReActStep(
                thought=f"Need the exact title for task {label}.",
                information_wait=InformationWaitRequest(
                    question=f"What title should task {label} have?",
                    missing_fact="task title",
                    subject=f"closing task {label}",
                ),
            )
        if stage == 1:
            assert answer, "the resumed call must carry the authorized answer"
            return ReActStep(
                thought=f"The authorized title for {label} is available.",
                action=ToolCall(
                    tool="tasks.create",
                    params={
                        "board_id": board_id,
                        "column_id": column_id,
                        "title": answer,
                        "status": "backlog",
                    },
                ),
            )
        return ReActStep(
            thought=f"Task {label} was verified.",
            final_answer=f"Created task {label}.",
        )

    monkeypatch.setattr(real_generic.GenericAgent, "_react_step", _step)

    run_a = _run(
        real_env, operation_id="generic-two-job-a",
        parameters={"sync": True, "task_input": "Create task A"})
    run_b = _run(
        real_env, operation_id="generic-two-job-b",
        parameters={"sync": True, "task_input": "Create task B"})
    assert run_a.status_code == 202, run_a.text
    assert run_b.status_code == 202, run_b.text
    data_a = run_a.json()["data"]
    data_b = run_b.json()["data"]
    job_a, exec_a = data_a["job_id"], data_a["execution_id"]
    job_b, exec_b = data_b["job_id"], data_b["execution_id"]
    receipt_a = data_a["wait_receipt"]
    receipt_b = data_b["wait_receipt"]
    assert job_a != job_b and exec_a != exec_b
    assert receipt_a["correlation_id"] != receipt_b["correlation_id"]
    assert [call["label"] for call in calls] == ["A", "B"], calls

    answer_a = _wait_answer(
        real_env, job_a, "Alpha", correlation_id=receipt_a["correlation_id"])
    assert answer_a.status_code == 200, answer_a.text
    assert answer_a.json()["data"]["job_status"] == "success"

    # B is still waiting: same wait/correlation, no new model call, no task.
    job_row_b, payload_b = _job_payload(real_env, job_b)
    assert job_row_b.status == "waiting", job_row_b.status
    assert payload_b["wait_receipt"]["correlation_id"] == (
        receipt_b["correlation_id"])
    assert sum(1 for call in calls if call["label"] == "B") == 1, calls
    with real_env.SessionLocal() as db:
        tasks = db.query(BoardTask).filter(
            BoardTask.board_id == board_id).all()
        assert [task.title for task in tasks] == ["Alpha"], tasks
        pending_b = db.query(HITLAction).filter(
            HITLAction.id == receipt_b["hitl_action_id"]).one()
        assert pending_b.status == "pending"

    # A stale A answer delivered to B is refused and changes nothing.
    stale = _wait_answer(
        real_env, job_b, "Alpha", correlation_id=receipt_a["correlation_id"])
    assert stale.status_code == 409, stale.text
    assert sum(1 for call in calls if call["label"] == "B") == 1, calls
    job_row_b, payload_b = _job_payload(real_env, job_b)
    assert job_row_b.status == "waiting"
    assert payload_b["wait_receipt"]["correlation_id"] == (
        receipt_b["correlation_id"])

    answer_b = _wait_answer(
        real_env, job_b, "Beta", correlation_id=receipt_b["correlation_id"])
    assert answer_b.status_code == 200, answer_b.text
    assert answer_b.json()["data"]["job_status"] == "success"

    # One effect per job, each execution terminal, no duplicate/foreign wake.
    with real_env.SessionLocal() as db:
        tasks = db.query(BoardTask).filter(
            BoardTask.board_id == board_id).all()
        assert sorted(task.title for task in tasks) == ["Alpha", "Beta"], tasks
        assert len(tasks) == 2, tasks
        for job_id, execution_id, title in (
                (job_a, exec_a, "Alpha"), (job_b, exec_b, "Beta")):
            job = db.get(AgentJob, job_id)
            execution = db.get(AgentExecution, execution_id)
            assert job is not None and job.status == "success"
            assert execution is not None and execution.status == "success"
            assert [task.title for task in tasks if task.title == title] == [
                title]
        waits = db.query(HITLAction).filter(
            HITLAction.action_type == "agent_information_request").all()
        assert len(waits) == 2, waits
        assert {row.status for row in waits} == {"approved"}
        assert {row.id for row in waits} == {
            receipt_a["hitl_action_id"], receipt_b["hitl_action_id"]}
