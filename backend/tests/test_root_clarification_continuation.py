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


@pytest.mark.parametrize("answer_route,use_model,model_question", [
    ("gap", True, False), ("response", True, False),
    ("gap", False, False), ("response", False, False),
    ("gap", True, True),
])
def test_question_only_answer_continues_same_job(
        route_env, tmp_path, monkeypatch, answer_route, use_model, model_question):
    from api.assignment_routes import _record_information_wait

    read = bind_applied_read(
        _verified_quote_evidence(), _route_source_authority(tmp_path),
        "clarification-prices.json")
    plan = new_assignment(
        objective="Prepare the requested quote after the owner confirms scope",
        employee_id="lead-1", workspace_id="ws-1", tenant_id="tenant-1",
        steps=[read], teaching_snapshot=_terms_teaching(),
        authorized_actions=["retrieve", "calculate"],
        provenance={"use_model": use_model, "employee_objective": True},
        completion_criteria=[
            {"kind": "required_work_complete", "required": True},
            {"criterion_id": "employee_result:objective",
             "kind": "employee_result", "required": True,
             "verifier": "employee_result"},
        ])
    record = route_env["executor"].create_assignment(
        "conv-clarify-" + uuid.uuid4().hex, plan["objective"], assignment=plan)
    run_id = record["run_id"]
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
