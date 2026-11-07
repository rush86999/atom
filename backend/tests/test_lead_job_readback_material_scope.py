"""Independent public readback scope drift controls; reasoning controlled."""
import pytest
from core.models import HITLAction, AgentExecution
from tests.test_agent_job_readback import _waiting_job, _job_readback
from tests.test_agent_run_outcome_join_contract import real_env

@pytest.mark.parametrize(('field','value'), [('workspace_id','ws2'),('tenant_id','foreign-tenant'),('user_id','peer-user')])
def test_wait_projection_refuses_changed_authoritative_scope(real_env, monkeypatch, field, value):
    data,calls=_waiting_job(real_env,monkeypatch,question='Which private account?',missing_fact='account')
    before=len(calls)
    with real_env.SessionLocal() as db:
        action=db.get(HITLAction,data['wait_receipt']['hitl_action_id'])
        setattr(action,field,value)
        db.commit()
    body=_job_readback(real_env,data['job_id'])
    assert body.get('wait_unavailable') is True, body
    assert 'wait' not in body
    assert len(calls)==before
