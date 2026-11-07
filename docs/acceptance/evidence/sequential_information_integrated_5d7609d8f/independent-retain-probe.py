from tests.test_task_wait_two_fact_events import route_env, _fixtures, _install_transport, _start, _questions, _reconciliations, _applied_artifacts

def test_answering_all_facts_without_business_work_does_not_complete(route_env,tmp_path,monkeypatch):
    from api import assignment_routes as routes
    from core.employee_adaptation import WorkAdaptationProposal
    monkeypatch.setenv("ATOM_ASSIGNMENT_OUTPUT_DIR",str(tmp_path/"reports"))
    po,invoice,receiving=_fixtures(tmp_path)
    _install_transport(monkeypatch)
    original=routes.propose_adaptation
    calls=[]
    async def retain_when_ready(context,observations,**kwargs):
        caps=context.get("available_business_operations") or []
        if any(c.get("operation")=="invoice_reconciliation" and c.get("status")=="ready" for c in caps):
            calls.append("retain-ready")
            return {"proposal":WorkAdaptationProposal(decision="retain",reason="No business work selected",observation_ids=[o["observation_id"] for o in observations]).model_dump(),"source":"model","technical_fallback":False,"errors":[]}
        return await original(context,observations,**kwargs)
    monkeypatch.setattr(routes,"propose_adaptation",retain_when_ready)
    client=route_env["client"];life=route_env["lifecycle"];run=_start(client,po)
    for path in [invoice,receiving]:
        response=client.post(f"/api/assignments/{run}/sources",json={"source":{"path":str(path)}})
        assert response.status_code==200,response.text
    final=life.get_assignment(run)
    assert calls,"the controlled model must actually reach the ready-but-retain boundary"
    assert _reconciliations(final)==[],final
    assert final["status"]!="completed", "Evidence arrival and model retain completed the job without reconciliation: "+str(final)
    assert _applied_artifacts(final)==[],"No final report without the required result"
