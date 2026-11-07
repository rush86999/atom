"""Targeted authorized source answer must trigger same-task business continuation.

Public assignment API, real compiler/executor and scratch records; proposal
transport and authenticated-user dependency use existing controlled fixtures.
This is not model quality, ordinary-login or browser qualification.
"""
import json
import pytest
from tests.test_assignment_routes import route_env
from core.employee_adaptation import WorkAdaptationProposal
from core.employee_work_requests import InvoiceReconciliationRequest
from core.task_lifecycle import open_unresolved_questions

@pytest.mark.parametrize('separate_advance',[False,True])
def test_authorized_source_answer_continues_same_task(route_env,tmp_path,monkeypatch,separate_advance):
    facts={'po.json':{'po_id':'PO-TRIGGER-63','vendor_id':'V-6','quantity':'3','unit_price':'42.50','freight':'12.75','currency':'USD'},
           'receiving.json':{'po_id':'PO-TRIGGER-63','received_quantity':'3'},
           'invoice.json':{'po_id':'PO-TRIGGER-63','invoice_id':'INV-TRIGGER-91','quantity':'3','unit_price':'42.50','freight':'12.75','currency':'USD'}}
    for name,value in facts.items():(tmp_path/name).write_text(json.dumps(value))
    calls=[]
    async def discovery(context,**kwargs):
        return {'proposal':{'proposal_kind':'evidence_read','reason':'read authorized procurement records','evidence_reads':[{'step_id':f'evidence-{i}','title':'Read source','source_id':s['source_id']} for i,s in enumerate(context['sources'],1)]},'source':'model','technical_fallback':False,'errors':[]}
    async def adaptation(context,observations,**kwargs):
        roles={str(x.get('business_role') or ''):x['step_id'] for x in context.get('evidence_results',[]) if x.get('business_role')}
        calls.append(dict(roles))
        common={'reason':'select supported work from accepted records','observation_ids':[o['observation_id'] for o in observations]}
        if all(roles.get(k) for k in ('invoice','purchase_order','receiving')):
            proposal=WorkAdaptationProposal(decision='replan',work_request=InvoiceReconciliationRequest(operation='invoice_reconciliation',invoice_step_id=roles['invoice'],purchase_order_step_id=roles['purchase_order'],receiving_step_id=roles['receiving']),**common)
        else:
            proposal=WorkAdaptationProposal(decision='clarify',clarification={'question':'Which authorized source contains invoice INV-TRIGGER-91 for purchase order PO-TRIGGER-63?','concept':'invoice_reconciliation','unblocks':'invoice reconciliation'},**common)
        return {'proposal':proposal.model_dump(),'source':'model','technical_fallback':False,'errors':[]}
    monkeypatch.setattr('api.assignment_routes.propose_employee_work',discovery)
    monkeypatch.setattr('api.assignment_routes.propose_adaptation',adaptation)
    monkeypatch.setattr('api.assignment_routes._employee_llm',lambda *a,**k:object())
    client=route_env['client']; lifecycle=route_env['lifecycle']
    start=client.post('/api/assignments/from-objective',json={'objective':'Reconcile invoice INV-TRIGGER-91 for PO-TRIGGER-63','sources':[{'path':str(tmp_path/'po.json')},{'path':str(tmp_path/'receiving.json')}],'authorized_actions':['retrieve','calculate'],'use_model':True})
    assert start.status_code==200,start.text
    run_id=start.json()['run_id']
    assert open_unresolved_questions(lifecycle.get_task(run_id)),'must actually request missing evidence before answering'
    before=len(calls)
    answer=client.post(f'/api/assignments/{run_id}/sources',json={'source':{'path':str(tmp_path/'invoice.json')},'reason':'authorized source answers the invoice question'})
    assert answer.status_code==200,answer.text
    assert answer.json()['resolved_question_ids'],answer.json()
    if separate_advance:
        extra=client.post(f'/api/assignments/{run_id}/advance',json={'use_model':True})
        assert extra.status_code==200,extra.text
    final=lifecycle.get_assignment(run_id)
    reconciliations=[s for s in final['steps'] if s['adapter']=='invoice.reconcile' and s['status']=='applied']
    assert len(reconciliations)==1,{'status':final['status'],'separate_advance':separate_advance,'adaptations_after_answer':len(calls)-before,'steps':[(s['adapter'],s['status']) for s in final['steps']]}
    assert reconciliations[0]['result']['value']=='140.25'
    assert final['status']=='completed'
