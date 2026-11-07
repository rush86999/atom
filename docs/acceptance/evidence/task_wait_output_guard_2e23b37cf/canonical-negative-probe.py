"""The compiler must see the lifecycle's canonical open question set."""
from types import SimpleNamespace
import pytest
from core.assignment_plan import new_assignment
from core.employee_adaptation import adopt_adaptation,WorkAdaptationProposal
from core.employee_work_requests import InvoiceReconciliationRequest
from core.task_lifecycle import open_unresolved_questions

class ObservedCompilation(RuntimeError): pass

@pytest.mark.parametrize('state',['open','resolved',None])
def test_adaptation_uses_the_authoritative_question_set(monkeypatch,state):
    question={'question_id':'history-row','question':'Earlier clarification'}
    if state is not None:question['status']=state
    record={'assignment':new_assignment(objective='Review accepted invoice',workspace_id='ws',tenant_id='tenant'),'task_version':1,'task_revision':{'unresolved':[question]}}
    captured={}
    def compile_at_boundary(request,assignment,*,context):
        captured.update(context);raise ObservedCompilation()
    monkeypatch.setattr('core.employee_adaptation.compile_work_request_patch',compile_at_boundary)
    proposal=WorkAdaptationProposal(decision='replan',reason='accepted evidence arrived',observation_ids=['new-observation'],work_request=InvoiceReconciliationRequest(operation='invoice_reconciliation',invoice_step_id='invoice',purchase_order_step_id='po',receiving_step_id='received',currency='USD'))
    with pytest.raises(ObservedCompilation):
        adopt_adaptation(SimpleNamespace(get_task=lambda run:record),'run',proposal)
    assert captured['open_obligations']==open_unresolved_questions(record),'legacy/history rows must not become a new blocking obligation'
