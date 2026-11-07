from tests.test_agent_run_admission_contract import env
from core.models import AgentExecution

def test_member_history_does_not_expose_another_workspace_result(env):
    with env.Session() as db:
        db.add_all([
            AgentExecution(id="history-own",agent_id="a1",tenant_id="t1",workspace_id="ws1",status="success",result_summary="Own visible task result"),
            AgentExecution(id="history-peer",agent_id="a2",tenant_id="t1",workspace_id="ws2",status="success",result_summary="Private result from workspace two"),
        ]);db.commit()
    response=env.client(env.actors["member-1"]).get("/api/agents/history")
    assert response.status_code==200,response.text
    rows=response.json()
    assert any(r["id"]=="history-own" for r in rows),rows
    assert not any(r["id"]=="history-peer" for r in rows),response.json()
