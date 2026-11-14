"""Generic job waits: owner-set absolute deadline, age projection, expiry.

The public run/answer/read routes, the real admission service and the real
``GenericAgent`` wait/resume consumer run against a scratch SQLite database.
Only the model transport is doubled. Deadline coverage is controlled-clock
plus a simulated boot pass; the separate actual-process restart test lives in
``test_agent_generic_information_wait_process.py``.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from core.models import AgentExecution, AgentJob, HITLAction, User  # noqa: E402
from core.react_models import (  # noqa: E402
    InformationWaitRequest,
    ReActStep,
)

import tests.test_agent_generic_information_wait as original  # noqa: E402
from tests.test_agent_run_outcome_join_contract import (  # noqa: E402
    real_env,
)

ANSWER = "Quarterly close checklist"


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _deadline_in(seconds: float) -> str:
    return _iso(datetime.now(timezone.utc) + timedelta(seconds=seconds))


def _wait_step(question: str, fact: str):
    def step(task_input, history, context):
        return ReActStep(
            thought=f"Need {fact} before continuing.",
            information_wait=InformationWaitRequest(
                question=question,
                missing_fact=fact,
            ),
        )

    return step


def _resumed_to_final(answer: str):
    def step(task_input, history, context):
        assert context["information_answer"] == answer
        assert context["information_wait_resume"] is True
        return ReActStep(
            thought="The authorized fact is available.",
            final_answer="Completed with the authorized fact.",
        )

    return step


def _start_wait(
    env, monkeypatch, *, operation_id: str, deadline=None,
    steps=None, task_input="Create the closing task",
):
    installed = original._install_model(
        monkeypatch,
        steps or [_wait_step("What title should the task have?", "title")],
    )
    body = {
        "parameters": {"sync": True, "task_input": task_input},
    }
    if deadline is not None:
        body["deadline"] = deadline
    response = original._client(env).post(
        f"/api/agents/a1/run?operation_id={operation_id}", json=body)
    return response, installed


def _read(env, job_id):
    return original._client(env).get(f"/api/agents/a1/jobs/{job_id}")


def _durable(env, job_id, action_id, execution_id):
    with env.SessionLocal() as db:
        job = db.get(AgentJob, job_id)
        action = db.get(HITLAction, action_id)
        execution = db.get(AgentExecution, execution_id)
        return (
            job,
            json.loads(job.result_summary or "{}"),
            action,
            execution,
        )


def _accept_wait_directly(env, action_id: str, answer: str) -> None:
    """Simulate an answer accepted just before the process died."""
    with env.SessionLocal() as db:
        action = db.get(HITLAction, action_id)
        action.status = "approved"
        action.user_feedback = answer
        action.reviewed_by = "member-1"
        action.reviewed_at = datetime.now(timezone.utc)
        db.commit()


def _use_scratch_recovery(monkeypatch, env) -> None:
    """Point the production recovery owners at this test's scratch DB."""
    import core.database as database

    monkeypatch.setattr(database, "SessionLocal", env.SessionLocal)
    monkeypatch.setattr(database, "engine", env.engine)


def test_deadline_is_stored_and_projected_without_mutating(
    real_env, monkeypatch,
):
    deadline = _deadline_in(3600)
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-stored", deadline=deadline)
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    action_id = data["wait_receipt"]["hitl_action_id"]
    assert len(calls) == 1

    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "waiting"
    assert payload["deadline"] == deadline
    assert payload["waiting_since"]
    assert action.status == "pending"
    assert execution.status == "waiting"

    read = _read(real_env, job_id)
    assert read.status_code == 200, read.text
    body = read.json()["data"]
    assert body["job_status"] == "waiting"
    assert body["deadline"] == deadline
    assert body["deadline_passed"] is False
    assert body["waiting_since"] == payload["waiting_since"]
    assert body["waiting_age_seconds"] >= 0
    wait = body["wait"]
    assert wait["deadline"] == deadline
    assert wait["waiting_since"] == payload["waiting_since"]
    assert wait["deadline_passed"] is False
    assert wait["can_answer"] is True

    # A read is pure: it neither expires nor claims.
    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "waiting"
    assert action.status == "pending"
    assert execution.status == "waiting"


def test_invalid_or_past_deadline_is_refused_before_admission(
    real_env, monkeypatch,
):
    calls = original._install_model(monkeypatch, [])
    bad = original._client(real_env).post(
        "/api/agents/a1/run?operation_id=deadline-invalid",
        json={"parameters": {"sync": True}, "deadline": "not-a-date"})
    assert bad.status_code == 422, bad.text
    past = original._client(real_env).post(
        "/api/agents/a1/run?operation_id=deadline-past",
        json={
            "parameters": {"sync": True},
            "deadline": _deadline_in(-1),
        })
    assert past.status_code == 422, past.text
    assert calls == []
    with real_env.SessionLocal() as db:
        assert db.query(AgentJob).count() == 0


def test_replay_digest_binds_the_configured_deadline(real_env, monkeypatch):
    deadline = _deadline_in(3600)
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-replay", deadline=deadline)
    assert response.status_code == 202, response.text
    job_id = response.json()["data"]["job_id"]
    assert len(calls) == 1

    replay = original._client(real_env).post(
        "/api/agents/a1/run?operation_id=deadline-replay",
        json={
            "parameters": {
                "sync": True,
                "task_input": "Create the closing task",
            },
            "deadline": deadline,
        })
    assert replay.status_code == 202, replay.text
    assert replay.json()["data"]["job_id"] == job_id
    assert len(calls) == 1, "an exact replay must not dispatch again"

    changed = original._client(real_env).post(
        "/api/agents/a1/run?operation_id=deadline-replay",
        json={
            "parameters": {
                "sync": True,
                "task_input": "Create the closing task",
            },
            "deadline": _deadline_in(7200),
        })
    assert changed.status_code == 409, changed.text
    assert len(calls) == 1
    with real_env.SessionLocal() as db:
        job = db.get(AgentJob, job_id)
        assert job.status == "waiting"
        assert json.loads(job.result_summary)["deadline"] == deadline


def test_exact_replay_after_deadline_is_still_idempotent(
    real_env, monkeypatch, frozen_time,
):
    deadline = _deadline_in(60)
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-replay-past", deadline=deadline)
    job_id = response.json()["data"]["job_id"]
    frozen_time.tick(timedelta(seconds=61))

    replay = original._client(real_env).post(
        "/api/agents/a1/run?operation_id=deadline-replay-past",
        json={
            "parameters": {
                "sync": True,
                "task_input": "Create the closing task",
            },
            "deadline": deadline,
        })
    assert replay.status_code != 422, replay.text
    assert replay.json()["data"]["job_id"] == job_id
    assert len(calls) == 1


def test_late_answer_is_a_truthful_expiry_with_no_side_effects(
    real_env, monkeypatch, frozen_time,
):
    deadline = _deadline_in(60)
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-late-answer", deadline=deadline)
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    correlation_id = data["wait_receipt"]["correlation_id"]
    action_id = data["wait_receipt"]["hitl_action_id"]

    frozen_time.tick(timedelta(seconds=61))

    # The pure read exposes the passed deadline but does not mutate.
    read = _read(real_env, job_id)
    assert read.status_code == 200, read.text
    body = read.json()["data"]
    assert body["job_status"] == "waiting"
    assert body["deadline_passed"] is True
    assert body["wait"]["deadline_passed"] is True
    assert body["wait"]["can_answer"] is False
    job, _payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "waiting"
    assert action.status == "pending"
    assert execution.status == "waiting"

    late = original._wait_answer(
        real_env, job_id, ANSWER, correlation_id=correlation_id)
    assert late.status_code == 409, late.text
    detail = late.json()["detail"]
    assert detail["code"] == "information_wait_expired"
    assert detail["deadline"] == deadline
    assert len(calls) == 1, "a late answer must not dispatch the model"

    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "failed"
    assert job.end_time is not None
    assert payload["outcome"] == "expired"
    assert payload["reason"] == "wait_deadline_exceeded"
    assert payload["next_action"] == "review_deadline"
    assert payload["deadline"] == deadline
    assert payload["expired_at"]
    assert action.status == "expired"
    assert execution.status == "failed"

    # Replaying the same late answer stays a 409 and changes nothing.
    expired_at = payload["expired_at"]
    replay = original._wait_answer(
        real_env, job_id, ANSWER, correlation_id=correlation_id)
    assert replay.status_code == 409, replay.text
    assert replay.json()["detail"]["code"] == "information_wait_expired"
    assert len(calls) == 1
    _job, payload_again, action_again, execution_again = _durable(
        real_env, job_id, action_id, execution_id)
    assert payload_again["expired_at"] == expired_at
    assert action_again.status == "expired"
    assert execution_again.status == "failed"


def test_accepted_input_during_downtime_cannot_revive_past_deadline(
    real_env, monkeypatch, frozen_time,
):
    deadline = _deadline_in(60)
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-accepted-downtime", deadline=deadline)
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    action_id = data["wait_receipt"]["hitl_action_id"]
    _accept_wait_directly(real_env, action_id, ANSWER)

    _use_scratch_recovery(monkeypatch, real_env)
    frozen_time.tick(timedelta(seconds=61))
    from core.information_wait import (
        drain_accepted_information_waits,
        expire_due_information_waits,
    )

    expiry = expire_due_information_waits()
    assert expiry["expired"] == 1, expiry
    assert expiry["details"][0]["job_id"] == job_id
    # The accepted-answer drain runs after expiry and finds nothing to resume.
    drain = asyncio.run(drain_accepted_information_waits())
    assert drain["resumed"] == 0, drain
    assert len(calls) == 1, "accepted input is not a deadline extension"

    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "failed"
    assert payload["outcome"] == "expired"
    assert payload["reason"] == "wait_deadline_exceeded"
    assert action.status == "expired"
    assert action.user_feedback == ANSWER
    assert execution.status == "failed"

    # A second boot sees no eligible work and does not change the row again.
    assert expire_due_information_waits()["expired"] == 0
    second = asyncio.run(drain_accepted_information_waits())
    assert second["resumed"] == 0, second


def test_resume_consumer_rechecks_deadline_before_dispatch(
    real_env, monkeypatch, frozen_time,
):
    deadline = _deadline_in(60)
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-resume-recheck", deadline=deadline)
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    action_id = data["wait_receipt"]["hitl_action_id"]
    correlation_id = data["wait_receipt"]["correlation_id"]
    _accept_wait_directly(real_env, action_id, ANSWER)
    _use_scratch_recovery(monkeypatch, real_env)
    frozen_time.tick(timedelta(seconds=61))

    from api import agent_routes

    result = asyncio.run(agent_routes.resume_information_wait_action(
        action_id,
        approved=True,
        answer=ANSWER,
        reviewer_id="member-1",
        bind=real_env.engine,
        correlation_id=correlation_id,
    ))
    assert result["resumed"] is False, result
    assert result["reason"] == "information_wait_expired", result
    assert len(calls) == 1, "the resume consumer must not spend model work"

    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "waiting"
    assert action.status == "approved"
    assert execution.status == "waiting"

    from core.information_wait import expire_due_information_waits

    assert expire_due_information_waits()["expired"] == 1
    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "failed"
    assert payload["outcome"] == "expired"
    assert action.status == "expired"
    assert execution.status == "failed"


def _start_source_wait(
    real_env, tmp_path, monkeypatch, *, deadline, operation_id,
):
    from tests.test_generic_source_answer_contract import _source_fixture

    doc, version = _source_fixture(real_env, tmp_path, monkeypatch)
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id=operation_id, deadline=deadline)
    assert response.status_code == 202, response.text
    return doc, version, response.json()["data"], calls


def test_post_resume_deadline_mapping_still_reports_actual_expiry(
    real_env, tmp_path, monkeypatch, frozen_time,
):
    """The public reply mapping, not only the route's early checks, expires."""
    import api.agent_routes as routes

    deadline = _deadline_in(60)
    doc, version, data, calls = _start_source_wait(
        real_env, tmp_path, monkeypatch,
        deadline=deadline, operation_id="deadline-post-resume-map")
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    action_id = data["wait_receipt"]["hitl_action_id"]

    original_read = routes._load_generic_source_payload
    reads = []

    async def source_read_then_deadline(*args, **kwargs):
        result = await original_read(*args, **kwargs)
        reads.append(result)
        # Invocation #1 is the answer route's source read. Invocation #2 is
        # the resume consumer's revalidation AFTER the route committed the
        # wait approval, so ticking here reaches the post-resume mapping.
        if len(reads) == 2:
            frozen_time.tick(timedelta(seconds=61))
        return result

    monkeypatch.setattr(
        routes, "_load_generic_source_payload", source_read_then_deadline)
    response = original._client(real_env).post(
        f"/api/agents/a1/jobs/{job_id}/answer",
        json={
            "answer": "source supplied",
            "correlation_id": data["wait_receipt"]["correlation_id"],
            "source": {"document_id": doc.id, "source_version": version},
        })
    assert len(reads) == 2, reads
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "information_wait_expired", detail
    assert detail["deadline"] == deadline, detail
    assert len(calls) == 1, "expiry must not dispatch the resumed model"

    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "waiting"
    assert payload["outcome"] == "waiting"
    assert action.status == "approved"
    assert execution.status == "waiting"


def test_post_resume_stale_wait_is_not_mislabeled_as_deadline(
    real_env, tmp_path, monkeypatch,
):
    """A peer-rejected wait keeps HEAD's truthful non-expiry refusal."""
    import api.agent_routes as routes

    deadline = _deadline_in(3600)
    doc, version, data, calls = _start_source_wait(
        real_env, tmp_path, monkeypatch,
        deadline=deadline, operation_id="deadline-post-resume-stale")
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    action_id = data["wait_receipt"]["hitl_action_id"]

    original_read = routes._load_generic_source_payload
    reads = []

    async def source_read_then_peer_reject(*args, **kwargs):
        result = await original_read(*args, **kwargs)
        reads.append(result)
        if len(reads) == 2:
            with real_env.SessionLocal() as db:
                row = db.get(HITLAction, action_id)
                row.status = "rejected"
                row.user_feedback = "peer rejected during the source read"
                db.commit()
        return result

    monkeypatch.setattr(
        routes, "_load_generic_source_payload", source_read_then_peer_reject)
    response = original._client(real_env).post(
        f"/api/agents/a1/jobs/{job_id}/answer",
        json={
            "answer": "source supplied",
            "correlation_id": data["wait_receipt"]["correlation_id"],
            "source": {"document_id": doc.id, "source_version": version},
        })
    assert len(reads) == 2, reads
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    # Pre-existing truthful refusal for a non-expiry concurrent settle. Before
    # the fix this was collapsed into an "owner-set deadline passed" lie.
    assert detail == "wait_not_current", detail
    assert len(calls) == 1, "a stale wait must not dispatch the model"

    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "waiting"
    assert payload["outcome"] == "waiting"
    assert action.status == "rejected"
    assert action.user_feedback == "peer rejected during the source read"
    assert execution.status == "waiting"


def test_deadline_survives_resume_and_a_second_wait(
    real_env, monkeypatch, frozen_time,
):
    deadline = _deadline_in(120)
    steps = [
        _wait_step("What title should the task have?", "title"),
        _wait_step("What priority should the task have?", "priority"),
    ]
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-second-wait", deadline=deadline, steps=steps)
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    first_action = data["wait_receipt"]["hitl_action_id"]
    _job, first_payload, _action, _execution = _durable(
        real_env, job_id, first_action, execution_id)
    first_waiting_since = first_payload["waiting_since"]

    first_answer = original._wait_answer(
        real_env, job_id, ANSWER,
        correlation_id=data["wait_receipt"]["correlation_id"])
    assert first_answer.status_code == 202, first_answer.text
    second = first_answer.json()["data"]
    assert second["job_status"] == "waiting"
    second_action = second["wait_receipt"]["hitl_action_id"]
    assert second_action != first_action
    assert len(calls) == 2

    job, payload, _action, _execution = _durable(
        real_env, job_id, second_action, execution_id)
    assert job.status == "waiting"
    # The read-modify-write summary transitions preserved the owner deadline.
    assert payload["deadline"] == deadline
    assert payload["waiting_since"]
    assert payload["waiting_since"] >= first_waiting_since
    assert payload["wait_receipt"]["hitl_action_id"] == second_action

    frozen_time.tick(timedelta(seconds=121))
    late = original._wait_answer(
        real_env, job_id, "high",
        correlation_id=second["wait_receipt"]["correlation_id"])
    assert late.status_code == 409, late.text
    assert late.json()["detail"]["code"] == "information_wait_expired"
    assert len(calls) == 2
    job, payload, second_row, execution = _durable(
        real_env, job_id, second_action, execution_id)
    assert job.status == "failed"
    assert payload["outcome"] == "expired"
    assert second_row.status == "expired"
    assert execution.status == "failed"
    with real_env.SessionLocal() as db:
        first_row = db.get(HITLAction, first_action)
        assert first_row.status == "approved"


def test_no_deadline_legacy_wait_is_never_swept(
    real_env, monkeypatch, frozen_time,
):
    steps = [
        _wait_step("What title should the task have?", "title"),
        _resumed_to_final(ANSWER),
    ]
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-legacy-none", deadline=None, steps=steps)
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    action_id = data["wait_receipt"]["hitl_action_id"]
    _job, payload, _action, _execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert "deadline" not in payload
    assert payload["waiting_since"]

    _use_scratch_recovery(monkeypatch, real_env)
    frozen_time.tick(timedelta(days=30))
    from core.information_wait import expire_due_information_waits

    result = expire_due_information_waits()
    assert result["expired"] == 0, result
    read = _read(real_env, job_id)
    assert read.status_code == 200, read.text
    body = read.json()["data"]
    assert body["job_status"] == "waiting"
    assert body["wait"]["can_answer"] is True
    assert body["wait"].get("deadline") is None

    answer = original._wait_answer(
        real_env, job_id, ANSWER,
        correlation_id=data["wait_receipt"]["correlation_id"])
    assert answer.status_code == 200, answer.text
    assert answer.json()["data"]["job_status"] == "success"
    assert len(calls) == 2


def test_legacy_approval_route_cannot_resurrect_expired_wait(
    real_env, monkeypatch, frozen_time,
):
    deadline = _deadline_in(60)
    response, calls = _start_wait(
        real_env, monkeypatch,
        operation_id="deadline-legacy-approval", deadline=deadline)
    data = response.json()["data"]
    job_id = data["job_id"]
    execution_id = data["execution_id"]
    action_id = data["wait_receipt"]["hitl_action_id"]

    # Seed an admin who can use the legacy AGENT_MANAGE approval surface in
    # this same workspace (the fixture's second admin is in another tenant).
    with real_env.SessionLocal() as db:
        if db.get(User, "admin-1") is None:
            db.add(User(
                id="admin-1", tenant_id="t1", workspace_id="ws1",
                email="admin1@example.com", first_name="A", last_name="One",
                role="admin", status="active", is_active=True))
            db.commit()
        real_env.actors["admin-1"] = db.get(User, "admin-1")

    frozen_time.tick(timedelta(seconds=61))
    admin = original._client(real_env, "admin-1")
    decision = admin.post(
        f"/api/agents/approvals/{action_id}",
        json={"decision": "approved", "feedback": ANSWER})
    assert decision.status_code == 409, decision.text
    assert decision.json()["detail"]["error"]["code"] == (
        "INFORMATION_WAIT_EXPIRED")

    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "failed"
    assert payload["outcome"] == "expired"
    assert action.status == "expired"
    assert execution.status == "failed"
    assert len(calls) == 1

    # A replay is idempotent: it reports the terminal expired row and never
    # flips it back to approved.
    replay = admin.post(
        f"/api/agents/approvals/{action_id}",
        json={"decision": "approved", "feedback": ANSWER})
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["decision"] == "expired"
    job, payload, action, execution = _durable(
        real_env, job_id, action_id, execution_id)
    assert job.status == "failed"
    assert action.status == "expired"
    assert len(calls) == 1
