import asyncio
from types import SimpleNamespace
import pytest
from tests.test_employee_business_feedback import (feedback_db,fresh_router,_handler,_configure_pool,_service,_context,_valid_proposal,_route_aware_instructor,_rows)
from unittest.mock import patch

@pytest.mark.parametrize('workspace,tenant',[('ws-other','tenant-ctrl'),('ws-ctrl','tenant-other')])
def test_wrong_scope_evaluation_cannot_modify_generation(feedback_db,fresh_router,monkeypatch,workspace,tenant):
 from core.employee_proposal import propose_employee_work
 from core.employee_routing_feedback import record_business_outcome
 h=_handler();_configure_pool(h,monkeypatch)
 with patch('core.llm.byok_handler.instructor.from_openai',_route_aware_instructor([],invalid_client=None,valid_proposal=_valid_proposal())):
  result=asyncio.run(propose_employee_work(_context(),llm_service=_service(h)))
 assert result['source']=='model'
 before=_rows(feedback_db);assert len(before)==1 and before[0].success is True
 asyncio.run(record_business_outcome(result,stage='employee_adaptation',outcome={'objective_met':False,'failure':{'owner':'capability','layer':'discovery','basis':'controlled wrong-scope annotation'}},workspace_id=workspace,tenant_id=tenant))
 after=_rows(feedback_db)
 assert len(after)==1
 assert after[0].success is True and after[0].quality_satisfied is True,after[0].prompt_features
 assert (after[0].prompt_features or {}).get('business_outcome')!='failed'

@pytest.mark.asyncio
async def test_generation_receipt_survives_child_task_deadline_boundary(monkeypatch):
 import core.employee_proposal as ep
 from core.llm.model_provenance import clear_route_attribution,set_served_route,set_routing_profile,set_feedback_id
 clear_route_attribution()
 # Python 3.11 wait_for and explicitly scheduled tasks isolate ContextVars.
 async def child_wait_for(coro,timeout):
  return await asyncio.wait_for(asyncio.create_task(coro),timeout)
 monkeypatch.setattr(ep,'asyncio',SimpleNamespace(wait_for=child_wait_for,TimeoutError=asyncio.TimeoutError))
 class LLM:
  async def generate_structured_response(self,**kwargs):
   set_served_route('controlled','model-a');set_routing_profile('employee_evidence_selection','2026-11-04.1');set_feedback_id('generation-a')
   return _valid_proposal()
 result=await ep.propose_employee_work(_context(),llm_service=LLM())
 assert result['source']=='model'
 assert result['routing_result_id']=='generation-a',result['routing']
 assert result['routing']['served_route']=={'provider':'controlled','model':'model-a'}
