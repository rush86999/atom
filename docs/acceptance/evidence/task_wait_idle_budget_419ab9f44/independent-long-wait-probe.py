"""Idle information wait must spare active allowance, never an absolute expiry."""
import time
from datetime import datetime,timezone
import pytest
from tests.test_assignment_routes import route_env
from tests.test_task_wait_source_continuation_regressions import _write_facts,_install_controlled_transport,_add_invoice,_reconciliations

@pytest.mark.parametrize('absolute_deadline',[False,True])
def test_relevant_arrival_after_long_wait_obeys_both_budget_kinds(route_env,tmp_path,monkeypatch,absolute_deadline):
    _write_facts(tmp_path);calls=_install_controlled_transport(monkeypatch,[])
    start=time.time();budget={'max_wall_seconds':900.0}
    if absolute_deadline:budget['deadline']=datetime.fromtimestamp(start+1800,tz=timezone.utc).isoformat()
    reply=route_env['client'].post('/api/assignments/from-objective',json={'objective':'Reconcile invoice INV-TRIGGER-91 for PO-TRIGGER-63','sources':[{'path':str(tmp_path/'po.json')},{'path':str(tmp_path/'receiving.json')}],'authorized_actions':['retrieve','calculate'],'use_model':True,'budget':budget})
    assert reply.status_code==200,reply.text
    run=reply.json()['run_id'];life=route_env['lifecycle'];before=life.get_assignment(run);before_calls=len(calls)
    assert not _reconciliations(life,run)
    original_deadline=before['budget'].get('deadline')
    with monkeypatch.context() as clock:
        clock.setattr('core.assignment_executor.time.time',lambda:start+7200)
        arrived=_add_invoice(route_env['client'],run,tmp_path)
    final=life.get_assignment(run)
    assert final['budget'].get('deadline')==original_deadline,'wait cannot secretly extend an absolute deadline'
    if absolute_deadline:
        assert final['status']!='completed'
        assert not _reconciliations(life,run)
        assert len(calls)==before_calls,'expired task must not start new model work'
    else:
        assert arrived.status_code==200,arrived.text
        assert final['status']=='completed','missing-information idle time exhausted active allowance before the authorized answer could be used'
        rows=_reconciliations(life,run);assert len(rows)==1
        assert rows[0]['result']['value']=='140.25'
        assert final['budget']['paused_seconds']>=7000
        assert final['budget']['elapsed_seconds']<60
