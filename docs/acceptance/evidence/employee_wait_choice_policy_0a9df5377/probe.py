import asyncio
from tests.test_employee_wait_choice import _context,_observations,_assignment
from core.employee_adaptation import propose_adaptation

def test_all_read_ambiguity_cannot_expand_clarify_only_policy_into_wait(monkeypatch):
 c=_context();c['missing_prerequisites'][0].update(status='ambiguous',missing=[])
 for s in c['sources']:s['read']=True
 c['rules']['allowed_proposal_kinds']=['clarify','retain'];c['rules']['allowed_work_requests']=[]
 async def fake_pinned(_llm,*,response_model,**kw):
  return response_model.model_validate({'decision':'replan','reason':'await current invoice','fact':'current supplier invoice','subject':'purchase order PO-WAIT-520','expected_from':'authorized procurement source','expected_answer_type':'text','blocks_operation':'invoice_reconciliation'})
 monkeypatch.setattr('core.llm.pinned_planning.pinned_structured_call',fake_pinned)
 r=asyncio.run(propose_adaptation(c,_observations(),assignment=_assignment(),llm_service=object()))
 assert (r.get('proposal') or {}).get('decision') in ('clarify','retain'),r
 assert not (r.get('proposal') or {}).get('work_request')
