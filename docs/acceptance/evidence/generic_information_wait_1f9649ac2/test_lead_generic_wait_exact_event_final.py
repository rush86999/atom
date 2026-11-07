"""Final protocol controls use raw requests, not a helper that fills identities."""
import pytest
from core.models import HITLAction
from core.react_models import ReActStep,InformationWaitRequest
from tests.test_agent_run_outcome_join_contract import real_env,_run,_client
from tests.test_agent_generic_information_wait import _install_model,_seed_board

@pytest.mark.parametrize('event',['missing','old'])
def test_raw_information_event_cannot_settle_an_unidentified_or_later_wait(real_env,monkeypatch,event):
    _seed_board(real_env)
    def title(task,history,context):return ReActStep(thought='Need title',information_wait=InformationWaitRequest(question='Title?',missing_fact='title'))
    def priority(task,history,context):return ReActStep(thought='Need priority',information_wait=InformationWaitRequest(question='Priority?',missing_fact='priority'))
    calls=_install_model(monkeypatch,[title,priority]);client=_client(real_env)
    started=_run(real_env,operation_id='root-final-event-'+event,parameters={'sync':True,'task_input':'Create a task after its title and priority are known'})
    assert started.status_code==202,started.text
    data=started.json()['data'];first=data['wait_receipt'];url=f"/api/agents/a1/jobs/{data['job_id']}/answer"
    if event=='missing':
        reply=client.post(url,json={'answer':'Closing task'})
        assert reply.status_code in (409,422),reply.text
        current=first;expected_calls=1
    else:
        original={'answer':'Closing task','correlation_id':first['correlation_id']}
        accepted=client.post(url,json=original);assert accepted.status_code==202,accepted.text
        current=accepted.json()['data']['wait_receipt'];assert current['hitl_action_id']!=first['hitl_action_id']
        reply=client.post(url,json=original)
        assert reply.status_code in (200,409),reply.text
        expected_calls=2
    assert len(calls)==expected_calls,'old/unbound answer dispatched model work'
    with real_env.SessionLocal() as db:assert db.get(HITLAction,current['hitl_action_id']).status=='pending'
