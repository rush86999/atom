"""New accepted external facts must not inherit an earlier retain marker."""
from tests.test_assignment_routes import route_env  # noqa: F401
from tests.test_assignment_external_reply_identity import _open_wait, REPLY_SOURCE


def test_accepted_external_fact_rearms_recovery(route_env, tmp_path, monkeypatch):
    import core.employee_job_runner as jobs
    run_id, correlation, _ = _open_wait(route_env, tmp_path, monkeypatch)
    executor = route_env["executor"]
    monkeypatch.setattr(jobs, "evidence_observations", lambda record: [
        {"observation_id": "retained-source-observation"}])
    before = executor.lifecycle.get_task(run_id)
    old = executor._unconsumed_evidence_key(before)
    assert old is not None
    claim = executor._claim_evidence_recovery(run_id, old["key"])
    assert claim is not None
    executor._finish_evidence_recovery(
        run_id, old["key"], "attempted", claim_token=claim["claim_token"])
    assert executor._evidence_recovery_plan(executor.lifecycle.get_task(run_id)) is None
    result = executor.record_external_response(
        run_id, correlation, response="received 2 units", source=REPLY_SOURCE,
        value="2", reply_id="new-authorized-reply")
    assert result["status"] == "resumed", result
    after = executor.lifecycle.get_task(run_id)
    plan = executor._evidence_recovery_plan(after)
    assert plan is not None, "accepted external fact inherited the pre-answer retain marker"
    assert plan["key"] != old["key"]
