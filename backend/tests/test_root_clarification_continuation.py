"""A durable question answer must reach the existing typed-work consumer.

Controlled proposal transport only; real public routes, lifecycle, source
verification, compiler and quote executor. No live inference or external effect.
"""
import uuid

import pytest

from tests.test_assignment_routes import route_env, _run, _route_source_authority
from tests.source_authority_fixtures import bind_applied_read
from tests.test_employee_work_requests import (
    _verified_quote_evidence, _quote_request, _terms_teaching,
)
from core.assignment_plan import new_assignment
from core.employee_adaptation import WorkAdaptationProposal


def _create_ready_job(route_env, tmp_path, *, use_model=True):
    read = bind_applied_read(
        _verified_quote_evidence(), _route_source_authority(tmp_path),
        "clarification-prices.json")
    plan = new_assignment(
        objective="Prepare the requested quote after the owner confirms scope",
        employee_id="lead-1", workspace_id="ws-1", tenant_id="tenant-1",
        steps=[read], teaching_snapshot=_terms_teaching(),
        authorized_actions=["retrieve", "calculate"],
        provenance={"use_model": use_model, "started_from": "employee_objective"},
        completion_criteria=[
            {"kind": "required_work_complete", "required": True},
            {"criterion_id": "employee_result:objective",
             "kind": "employee_result", "required": True,
             "verifier": "employee_result"},
        ])
    record = route_env["executor"].create_assignment(
        "conv-clarify-" + uuid.uuid4().hex, plan["objective"], assignment=plan)
    run_id = record["run_id"]
    return run_id


@pytest.mark.parametrize("answer_route,use_model,model_question", [
    ("gap", True, False), ("response", True, False),
    ("gap", False, False), ("response", False, False),
    ("gap", True, True),
])
def test_question_only_answer_continues_same_job(
        route_env, tmp_path, monkeypatch, answer_route, use_model, model_question):
    from api.assignment_routes import _record_information_wait

    run_id = _create_ready_job(route_env, tmp_path, use_model=use_model)
    if model_question:
        async def clarify(context, observations, **kwargs):
            return {
                "source": "model", "technical_fallback": False, "errors": [],
                "proposal": WorkAdaptationProposal(
                    decision="clarify", reason="confirm the owner scope",
                    observation_ids=[v["observation_id"] for v in observations],
                    clarification={"question": "Confirm the scope?",
                                   "concept": "requested_scope",
                                   "unblocks": "the requested quote"}).model_dump(),
            }
        monkeypatch.setattr("api.assignment_routes.propose_adaptation", clarify)
        monkeypatch.setattr("api.assignment_routes._employee_llm", lambda *_: object())
        asked = route_env["client"].post(
            f"/api/assignments/{run_id}/advance",
            json={"use_model": True, "deadline_seconds": 30})
        assert asked.status_code == 200, asked.text
        questions = route_env["executor"].status(run_id)["open_gaps"]
        assert len(questions) == 1, asked.json()
        question_id = questions[0]["question_id"]
        assert not questions[0].get("source_operation")
    else:
        questions = _run(_record_information_wait(
            route_env["executor"], run_id, [{
                "kind": "missing_evidence", "item": "requested scope",
                "concept": "requested_scope", "question": "Confirm the scope?",
                "next_action": "Answer the requested scope question",
                "waiting": {"state": "waiting_for_person", "party": "owner",
                            "event": "human_input", "resume_on": "answer",
                            "correlation_id": "scope-confirmation"},
            }]))
        question_id = questions[0]["question_id"]
    assert route_env["executor"].status(run_id)["open_gaps"]
    selected = []

    async def proposal(context, observations, **kwargs):
        assert observations
        import json
        assert "Use the accepted price rows" in json.dumps(context)
        from core.employee_adaptation import _compact_single_request_prompt
        compact = _compact_single_request_prompt(context, observations)
        assert "Use the accepted price rows" in compact
        selected.append(run_id)
        return {
            "source": "model", "technical_fallback": False, "errors": [],
            "proposal": WorkAdaptationProposal(
                decision="replan", reason="owner answered; use accepted rows",
                observation_ids=[v["observation_id"] for v in observations],
                work_request=_quote_request()).model_dump(),
        }

    monkeypatch.setattr("api.assignment_routes.propose_adaptation", proposal)
    monkeypatch.setattr("api.assignment_routes._employee_llm", lambda *_: object())
    if answer_route == "gap":
        path = f"/api/assignments/{run_id}/gaps/{question_id}/resolve"
        body = {"resolution": "Use the accepted price rows", "evidence": "owner"}
    else:
        path = f"/api/assignments/{run_id}/responses/scope-confirmation"
        body = {"reply_id": "scope-answer-1", "response": "Use the accepted price rows",
                "source": "owner", "evidence": "owner"}
    response = route_env["client"].post(path, json=body)
    assert response.status_code == 200, response.text
    assignment = route_env["lifecycle"].get_assignment(run_id)
    quotes = [v for v in assignment["steps"]
              if v.get("adapter") == "quote.calculate" and v.get("status") == "applied"]
    if use_model:
        assert selected == [run_id], response.json()
        assert len(quotes) == 1, response.json()
        assert quotes[0]["result"]["value"] == "370.00"
        assert assignment["status"] == "completed"
    else:
        assert selected == []
        assert quotes == []
        assert assignment["status"] != "completed"
    snapshot = route_env["lifecycle"].get_task(run_id)
    replay = route_env["client"].post(path, json=body)
    assert replay.status_code == 200, replay.text
    assert route_env["lifecycle"].get_task(run_id) == snapshot
    assert selected == ([run_id] if use_model else [])

    if answer_route == "response":
        changed = dict(body, response="Changed scope")
        conflict = route_env["client"].post(path, json=changed)
        assert conflict.status_code == 409, conflict.text
        assert route_env["lifecycle"].get_task(run_id) == snapshot


def test_resolved_answer_rearms_old_one_shot_recovery(
        route_env, tmp_path, monkeypatch):
    """A new answer cannot inherit an earlier evidence-only retain marker."""
    from api.assignment_routes import _record_information_wait
    from tests.test_task_wait_source_continuation_regressions import _rebuilt_executor

    run_id = _create_ready_job(route_env, tmp_path)
    executor = route_env["executor"]
    record = executor.lifecycle.get_task(run_id)
    old = executor._evidence_recovery_plan(record)
    assert old is not None
    claim = executor._claim_evidence_recovery(run_id, old["key"])
    assert claim is not None
    executor._finish_evidence_recovery(
        run_id, old["key"], "attempted", claim_token=claim["claim_token"])
    questions = _run(_record_information_wait(executor, run_id, [{
        "kind": "business_decision", "concept": "scope", "question": "Use these rows?",
        "next_action": "Confirm scope", "waiting": {
            "state": "waiting_for_person", "party": "owner",
            "correlation_id": "new-scope-answer"},
    }]))
    assert executor._evidence_recovery_plan(executor.lifecycle.get_task(run_id)) is None

    async def interrupted(*args, **kwargs):
        raise RuntimeError("controlled interruption after durable answer")

    monkeypatch.setattr("api.assignment_routes._advance_employee_work", interrupted)
    monkeypatch.setattr("api.assignment_routes._employee_llm", lambda *_: object())
    with pytest.raises(RuntimeError, match="controlled interruption"):
        route_env["client"].post(
            f"/api/assignments/{run_id}/gaps/{questions[0]['question_id']}/resolve",
            json={"resolution": "Use the accepted price rows"})
    fresh = _rebuilt_executor(route_env)
    record = fresh.lifecycle.get_task(run_id)
    assert not fresh.status(run_id)["open_gaps"]
    recovery = fresh._evidence_recovery_plan(record)
    assert recovery is not None, record["assignment"].get("evidence_recovery")
    assert recovery["key"] != old["key"]


@pytest.mark.parametrize("binding", ["step_id", "source_operation"])
def test_missing_declared_question_binding_refuses_without_resolution(
        route_env, tmp_path, monkeypatch, binding):
    from core.task_lifecycle import add_unresolved_questions

    run_id = _create_ready_job(route_env, tmp_path, use_model=False)
    question = {
        "kind": "missing_evidence", "concept": "scope", "question": "Confirm scope?",
        "next_action": "Answer", "waiting": {
            "state": "waiting_for_person", "party": "owner",
            "correlation_id": "bound-question"},
    }
    kwargs = {}
    if binding == "step_id":
        question["step_id"] = "missing-step"
    else:
        kwargs["source_operation"] = "missing-operation"
    added = add_unresolved_questions(route_env["lifecycle"], run_id, [question], **kwargs)
    before = route_env["lifecycle"].get_task(run_id)
    result = route_env["client"].post(
        f"/api/assignments/{run_id}/responses/bound-question",
        json={"reply_id": "invalid-binding", "response": "confirmed"})
    assert result.status_code == 404, result.text
    after = route_env["lifecycle"].get_task(run_id)
    assert after == before
    assert after["task_revision"]["unresolved"][0]["question_id"] == added[0]["question_id"]
    assert after["task_revision"]["unresolved"][0]["status"] == "open"
