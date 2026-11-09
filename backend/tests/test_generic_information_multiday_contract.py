"""Controlled-clock multi-day acceptance extension; not elapsed soak or restart proof."""
from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
from typing import get_args

import pytest

pytestmark = pytest.mark.freeze_time(real_asyncio=True)

# ``tasks.create`` is a real registered action, but its handler lazily imports
# ``core.board_service`` / ``api.schemas.board_schemas`` on the dispatch path.
# Pydantic builds those schemas at class-creation time from the ``datetime``
# class in module globals.  If that first import happens while the marker above
# has frozen the clock, the schema captures ``freezegun.api.FakeDatetime`` and
# the real action fails before it touches the board.  Import the production
# module here -- collection runs before any test-level freeze -- so the
# acceptance path exercises the real action instead of an import-order
# artifact.  No expected task, receipt, or Oracle assertion is changed.
import core.board_service  # noqa: E402,F401

from core.models import AgentExecution, HITLAction, User  # noqa: E402
from core.models_board import BoardTask  # noqa: E402
from core.react_models import (  # noqa: E402
    InformationWaitRequest,
    ReActStep,
    ToolCall,
)

import tests.test_agent_generic_information_wait as original  # noqa: E402
from tests.test_agent_run_outcome_join_contract import real_env  # noqa: E402

# Freezegun replaces direct module aliases too. A tuple preserves the real
# type reference so the guard compares schema types, not a patched alias.
_REAL_DATETIME = (datetime,)


def _delay_answers(monkeypatch, freezer, days):
    answer = original._wait_answer
    observed = []
    def delayed(*args, **kwargs):
        freezer.tick(timedelta(days=days))
        observed.append(days)
        return answer(*args, **kwargs)
    monkeypatch.setattr(original, '_wait_answer', delayed)
    return observed


def test_action_schema_was_built_with_real_datetime():
    """Positive/negative isolation for the hosted import-order failure.

    The production ``TaskCreate`` schema must be built from the real
    ``datetime`` class while this module's clock is frozen.  Before the
    module-level preload above, the first ``tasks.create`` import happened
    inside the frozen resumed pass, so Pydantic rejected
    ``freezegun.api.FakeDatetime`` and the real action failed before writing.
    This control invokes no action, server, or model.
    """
    from api.schemas.board_schemas import TaskCreate

    annotation = TaskCreate.model_fields["due_at"].annotation
    assert _REAL_DATETIME[0] in get_args(annotation)
    assert "FakeDatetime" not in repr(annotation)


@pytest.mark.parametrize('days', [3, 14])
def test_same_job_verified_result_after_multiday_wait(real_env, monkeypatch, freezer, days):
    observed = _delay_answers(monkeypatch, freezer, days)
    original.test_generic_info_wait_resumes_same_job_to_verified_result(real_env, monkeypatch)
    assert observed == [days]


def test_two_missing_facts_span_two_weeks_same_job(real_env, monkeypatch, freezer):
    observed = _delay_answers(monkeypatch, freezer, 7)
    original.test_second_missing_fact_waits_again_then_completes(real_env, monkeypatch)
    assert observed == [7, 7]


def test_late_multiday_answer_cannot_revive_cancelled_job(real_env, monkeypatch, freezer):
    observed = _delay_answers(monkeypatch, freezer, 14)
    original.test_answer_after_cancellation_cannot_revive_the_job(real_env, monkeypatch)
    assert observed == [14]


@pytest.mark.parametrize("preload", [False, True])
def test_task_schema_cold_import_freezer_negative_and_valid_twin(preload):
    # Fresh interpreters prevent another collected module from accidentally
    # preloading the schema and making this import-order control vacuous.
    setup = "from api.schemas.board_schemas import TaskCreate\n" if preload else ""
    code = setup + (
        "from freezegun import freeze_time\n"
        "with freeze_time(real_asyncio=True):\n"
        "    from api.schemas.board_schemas import TaskCreate\n"
        "    print(repr(TaskCreate.model_fields['due_at'].annotation))\n"
        "print('schema-ready')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "TESTING": "1"},
        capture_output=True, text=True, timeout=30,
    )
    if preload:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().endswith("schema-ready")
        assert "FakeDatetime" not in result.stdout
    else:
        # Pydantic initialization order/version can either reject the fake
        # type (as hosted CI did) or compile it. Neither is a real-type schema
        # qualification: detect the fake annotation even when import succeeds.
        if result.returncode == 0:
            assert "FakeDatetime" in result.stdout
        else:
            assert "FakeDatetime" in result.stderr
            assert "schema" in result.stderr.lower()


def _begin_multiday_wait(env, monkeypatch, *, operation_id, title):
    """Start one real public-route job that pauses on a missing title."""
    board_id, column_id = original._seed_board(env)
    question = "What title should the multi-day task have?"

    def first(task_input, history, context):
        return ReActStep(
            thought="Need the exact title before creating the task.",
            information_wait=InformationWaitRequest(
                question=question,
                missing_fact="task title",
                subject="multi-day task",
            ),
        )

    def resumed(task_input, history, context):
        # The authorized answer and the useful prior work must both survive
        # into the SAME execution, not a fresh job or an injected result.
        assert context["information_answer"] == title
        assert context["information_wait_resume"] is True
        assert question in history
        return ReActStep(
            thought="The authorized title is available; create the task.",
            action=ToolCall(
                tool="tasks.create",
                params={
                    "board_id": board_id,
                    "column_id": column_id,
                    "title": context["information_answer"],
                },
            ),
        )

    def finished(task_input, history, context):
        return ReActStep(
            thought="The registered action was independently verified.",
            final_answer="Created the task after the multi-day wait.",
        )

    calls = original._install_model(monkeypatch, [first, resumed, finished])
    response = original._run(
        env,
        operation_id=operation_id,
        parameters={"sync": True, "task_input": "Create the task"},
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["job_status"] == "waiting"
    assert data["next_action"] == "await_information"
    receipt = data["wait_receipt"]
    assert receipt["kind"] == "information_request"
    assert receipt["verified"] is True
    assert receipt["correlation_id"]
    assert len(calls) == 1, "creating the wait must not poll the model"
    return {
        "board_id": board_id,
        "job_id": data["job_id"],
        "execution_id": data["execution_id"],
        "receipt": receipt,
        "calls": calls,
    }


def _assert_multiday_identity(env, scenario):
    """Read the wait through the public route and fresh durable sessions."""
    job_id = scenario["job_id"]
    execution_id = scenario["execution_id"]
    receipt = scenario["receipt"]

    # A new client/session must project the exact same still-open wait. This
    # read is a pure public route: it may not claim or dispatch the job.
    read = original._client(env).get(f"/api/agents/a1/jobs/{job_id}")
    assert read.status_code == 200, read.text
    payload = read.json()["data"]
    assert payload["job_status"] == "waiting"
    assert payload["execution_id"] == execution_id
    wait = payload["wait"]
    assert wait["id"] == receipt["hitl_action_id"]
    assert wait["correlation_id"] == receipt["correlation_id"]
    assert wait["status"] == "pending"
    assert wait["can_answer"] is True

    # Fresh SessionLocal: job/execution/wait correlation is durable, not a
    # response-object echo.
    job, durable = original._job_payload(env, job_id)
    assert job.status == "waiting" and job.end_time is None
    assert durable["finished"] is False
    assert durable["wait_receipt"]["hitl_action_id"] == (
        receipt["hitl_action_id"])
    assert durable["wait_receipt"]["correlation_id"] == (
        receipt["correlation_id"])

    with env.SessionLocal() as db:
        execution = db.get(AgentExecution, execution_id)
        assert execution is not None
        assert execution.agent_id == "a1"
        assert execution.status == "waiting"
        assert execution.metadata_json["resume_state"]["history"]

        wait_row = db.get(HITLAction, receipt["hitl_action_id"])
        assert wait_row is not None
        assert wait_row.status == "pending"
        assert wait_row.action_type == "agent_information_request"
        assert wait_row.user_feedback is None
        snapshot = wait_row.context_snapshot or {}
        assert snapshot["job_id"] == job_id
        assert snapshot["execution_id"] == execution_id
        assert snapshot["correlation_id"] == receipt["correlation_id"]


@pytest.mark.parametrize("days", [7, 30])
def test_multiday_wait_keeps_identity_and_one_verified_effect(
        real_env, monkeypatch, freezer, days):
    """Seven and thirty controlled days preserve the same real effect."""
    title = f"Multi-day task {days}"
    scenario = _begin_multiday_wait(
        real_env, monkeypatch,
        operation_id=f"generic-multiday-{days}", title=title)

    freezer.tick(timedelta(days=days))
    _assert_multiday_identity(real_env, scenario)
    assert len(scenario["calls"]) == 1, "reads must not poll the model"

    answer = original._wait_answer(
        real_env, scenario["job_id"], title,
        correlation_id=scenario["receipt"]["correlation_id"])
    assert answer.status_code == 200, answer.text
    body = answer.json()["data"]
    assert body["job_status"] == "success"
    assert body["execution_id"] == scenario["execution_id"]
    assert body["result"]["output"] == (
        "Created the task after the multi-day wait.")

    # The effect is the real registered tasks.create result, independently
    # verified by the default Oracle; the answer/status is not the evidence.
    task_steps = [
        step for step in body["result"].get("steps") or []
        if (step.get("action") or {}).get("tool") == "tasks.create"
    ]
    assert task_steps
    assert task_steps[0]["output"].get("oracle_verified") is True

    job, durable = original._job_payload(real_env, scenario["job_id"])
    assert job.status == "success"
    assert durable["outcome"] == "success"
    assert scenario["calls"][-1]["context"]["job_id"] == scenario["job_id"]
    assert scenario["calls"][-1]["context"]["execution_id"] == (
        scenario["execution_id"])

    with real_env.SessionLocal() as db:
        tasks = db.query(BoardTask).filter(
            BoardTask.board_id == scenario["board_id"]).all()
        assert len(tasks) == 1
        assert tasks[0].title == title
        execution = db.get(AgentExecution, scenario["execution_id"])
        assert execution is not None
        assert execution.status == "success"
        assert "resume_state" not in (execution.metadata_json or {})
        waits = db.query(HITLAction).filter(
            HITLAction.action_type == "agent_information_request").all()
        assert [row.id for row in waits] == [
            scenario["receipt"]["hitl_action_id"]]
        assert waits[0].status == "approved"
        assert waits[0].user_feedback == title

    calls_after_success = len(scenario["calls"])
    replay = original._wait_answer(
        real_env, scenario["job_id"], title,
        correlation_id=scenario["receipt"]["correlation_id"])
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"].get("already_resumed") is True
    assert len(scenario["calls"]) == calls_after_success
    with real_env.SessionLocal() as db:
        # A duplicate answer cannot create a second durable BoardTask or
        # dispatch the model again.
        assert db.query(BoardTask).filter(
            BoardTask.board_id == scenario["board_id"]).count() == 1


@pytest.mark.parametrize("days", [7, 30])
def test_revoked_actor_after_multiday_wait_cannot_resume(
        real_env, monkeypatch, freezer, days):
    """Current authority, not the old receipt, gates a late answer."""
    title = f"Revoked task {days}"
    scenario = _begin_multiday_wait(
        real_env, monkeypatch,
        operation_id=f"generic-multiday-revoked-{days}", title=title)

    freezer.tick(timedelta(days=days))
    _assert_multiday_identity(real_env, scenario)

    # A peer transition deactivates the admitted actor after the wait. The
    # HTTP dependency still holds the fixture's older User object, so this
    # exercises the route's current-SQL authority claim rather than an
    # already-dead token.
    with real_env.SessionLocal() as db:
        user = db.get(User, "member-1")
        user.is_active = False
        user.status = "inactive"
        db.commit()

    refused = original._wait_answer(
        real_env, scenario["job_id"], title,
        correlation_id=scenario["receipt"]["correlation_id"])
    assert refused.status_code == 409, refused.text
    assert len(scenario["calls"]) == 1
    job, _durable = original._job_payload(real_env, scenario["job_id"])
    assert job.status == "waiting"
    with real_env.SessionLocal() as db:
        wait_row = db.get(HITLAction, scenario["receipt"]["hitl_action_id"])
        assert wait_row is not None
        assert wait_row.status == "pending"
        assert wait_row.user_feedback is None
        assert db.query(BoardTask).filter(
            BoardTask.board_id == scenario["board_id"]).count() == 0

    # Restoring the exact current authority proves the refusal above was
    # authority drift, not a damaged wait identity: the same correlation still
    # resumes the same job and creates exactly one verified effect.
    with real_env.SessionLocal() as db:
        user = db.get(User, "member-1")
        user.is_active = True
        user.status = "active"
        db.commit()

    restored = original._wait_answer(
        real_env, scenario["job_id"], title,
        correlation_id=scenario["receipt"]["correlation_id"])
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["job_status"] == "success"
    with real_env.SessionLocal() as db:
        tasks = db.query(BoardTask).filter(
            BoardTask.board_id == scenario["board_id"]).all()
        assert len(tasks) == 1
        assert tasks[0].title == title
