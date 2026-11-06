import asyncio
from types import SimpleNamespace
import pytest
from core.agents.workflow_blueprint import compile_blueprint, BlueprintValidationError
from tests.test_orch01_checkpoint_contract import _compile,_orchestrator,_steps,_run
from advanced_workflow_orchestrator import WorkflowDefinition, WorkflowContext, WorkflowStatus

def test_unsupported_known_word_action_is_not_changed_to_create():
    draft={'architecture_name':'delete a record','nodes':[{'id':'record','type':'entity','name':'Delete existing record','action':{'kind':'write','service':'knowledge','action':'delete'},'metadata':{'entity_name':'existing record','entity_type':'business_record'}}]}
    try: compiled=compile_blueprint(draft,workspace_id='ws-1',tenant_id='tenant-1')
    except BlueprintValidationError:return
    if not compiled.get('execution_ready'):return
    action=next(s['parameters']['action'] for s in compiled['steps'] if s['step_id']=='record')
    assert action=='delete',compiled

@pytest.mark.parametrize('approval_status',['pending','rejected'])
def test_resume_does_not_dispatch_without_authoritative_approval(monkeypatch,approval_status):
    compiled=_compile([{'id':'write','type':'entity','name':'Write','action':{'kind':'write'},'metadata':{'entity_name':'record','entity_type':'record'}}])
    approval=SimpleNamespace(status=approval_status,id='hitl-not-approved')
    orch=_orchestrator(monkeypatch,enforce={'proceed':True,'status':'APPROVED'},approval_row=approval)
    effects=[]
    # Leave the context at a real pending checkpoint before calling the public resume consumer.
    if approval_status=='pending':
        ctx=_run(orch,compiled,effects)
    else:
        ctx=WorkflowContext(workflow_id=compiled['workflow_id'])
        ctx.status=WorkflowStatus.WAITING_APPROVAL
        ctx.results[compiled['start_step']]={'status':'waiting_approval','hitl_action_id':approval.id}
        async def dispatch(workflow,step,context):
            effects.append(step.step_id);return {'status':'completed'}
        orch._execute_step_by_type=dispatch
    assert effects==[]
    wf=WorkflowDefinition(workflow_id=compiled['workflow_id'],name='controlled',description='',steps=_steps(compiled),start_step=compiled['start_step'])
    orch.workflows={wf.workflow_id:wf};orch.active_contexts={ctx.workflow_id:ctx};orch._save_execution_state=lambda *args:None
    asyncio.run(orch.resume_workflow(ctx.workflow_id,compiled['start_step']))
    assert effects==[],(approval_status,effects,ctx.results)

def test_top_level_execution_does_not_complete_after_blocked_checkpoint(monkeypatch):
    compiled=_compile([{'id':'write','type':'entity','name':'Write','action':{'kind':'write'},'metadata':{'entity_name':'record','entity_type':'record'}}])
    orch=_orchestrator(monkeypatch,enforce={'proceed':False,'status':'BLOCKED','reason':'no authority'})
    effects=[]
    async def dispatch(workflow,step,ctx):
        if step.step_type.value=='approval_required':
            return await orch._execute_approval_required_step(step,ctx)
        effects.append(step.step_id);return {'status':'completed'}
    orch._execute_step_by_type=dispatch
    wf=WorkflowDefinition(workflow_id=compiled['workflow_id'],name='controlled',description='',steps=_steps(compiled),start_step=compiled['start_step'])
    orch.workflows={wf.workflow_id:wf};orch.active_contexts={};orch.ai_service=None;orch._save_execution_state=lambda *args:None
    result=asyncio.run(orch.execute_workflow(wf.workflow_id,{}))
    assert effects==[]
    assert result.status!=WorkflowStatus.COMPLETED,(result.status,result.results)
