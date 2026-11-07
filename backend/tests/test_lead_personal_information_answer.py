"""Public answer route must retain Personal Edition scope compatibility."""
import pytest
from core.models import User, AgentRegistry, Tenant, Workspace
from tests.test_agent_job_readback import _waiting_job
from tests.test_agent_run_outcome_join_contract import real_env, _client

@pytest.mark.parametrize('personal',[False,True])
def test_public_information_answer_uses_effective_personal_workspace(real_env,monkeypatch,personal):
    if personal:
        with real_env.SessionLocal() as db:
            db.add(Tenant(id='default',name='Personal',subdomain='personal'))
            db.add(Workspace(id='default',name='Personal',tenant_id='default'))
            db.flush()
            user=db.get(User,'member-1');user.workspace_id=None;user.tenant_id=None;user.role='workspace_admin'
            agent=db.get(AgentRegistry,'a1');agent.workspace_id='default';agent.tenant_id='default'
            db.commit()
        real_env.actors['member-1'].workspace_id=None
        real_env.actors['member-1'].tenant_id=None
        real_env.actors['member-1'].role='workspace_admin'
    data,calls=_waiting_job(real_env,monkeypatch,question='Which exact title?',missing_fact='title')
    before=len(calls)
    response=_client(real_env).post(f"/api/agents/a1/jobs/{data['job_id']}/answer",json={'answer':'Closing checklist','correlation_id':data['wait_receipt']['correlation_id']})
    assert response.status_code in (200,202),response.text
    assert response.json()['data']['resumed'] is True
    assert len(calls)==before+1
