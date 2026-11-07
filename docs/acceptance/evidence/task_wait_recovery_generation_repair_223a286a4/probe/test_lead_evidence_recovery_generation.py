"""A stale source-recovery completion must not consume a new claim."""
import copy
import inspect
import pytest
from tests.test_assignment_routes import route_env
from tests.test_task_wait_source_continuation_regressions import _write_facts,_install_controlled_transport,_start_missing_invoice,_add_invoice,_rebuilt_executor

@pytest.mark.parametrize("expired_old_claim",[False,True])
def test_finish_is_bound_to_the_claim_generation(route_env,tmp_path,monkeypatch,expired_old_claim):
    _write_facts(tmp_path);_install_controlled_transport(monkeypatch,[])
    run=_start_missing_invoice(route_env["client"],tmp_path)
    async def stop(*args,**kwargs):raise RuntimeError("controlled source consumer interruption")
    monkeypatch.setattr("api.assignment_routes._advance_employee_work",stop)
    answer=_add_invoice(route_env["client"],run,tmp_path);assert answer.status_code==200,answer.text
    lifecycle=route_env["lifecycle"];executor=_rebuilt_executor(route_env)
    plan=executor._evidence_recovery_plan(lifecycle.get_task(run));assert plan
    first=executor._claim_evidence_recovery(run,plan["key"]);assert first is not None
    first_marker=copy.deepcopy(lifecycle.get_assignment(run)["evidence_recovery"])
    if expired_old_claim:
        def expire(record,assignment):
            out=copy.deepcopy(assignment);out["evidence_recovery"]["at"]-=10000
            return out,{"status":"test clock advanced beyond lease"}
        lifecycle.mutate_assignment(run,expire,rationale="controlled elapsed claim lease")
        second=executor._claim_evidence_recovery(run,plan["key"]);assert second is not None
    before=copy.deepcopy(lifecycle.get_assignment(run)["evidence_recovery"])
    kwargs={}
    if "claim_token" in inspect.signature(executor._finish_evidence_recovery).parameters:
        kwargs["claim_token"]=first_marker.get("claim_token")
    executor._finish_evidence_recovery(run,plan["key"],"attempted",**kwargs)
    after=lifecycle.get_assignment(run)["evidence_recovery"]
    if expired_old_claim:
        assert after==before,"old completion overwrote the successor claim; next boot now treats unconsumed work as already attempted"
    else:
        assert after["status"]=="attempted"
