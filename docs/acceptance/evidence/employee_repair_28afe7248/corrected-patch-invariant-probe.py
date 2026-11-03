import copy
import pytest
from tests.test_assignment_executor import env,_patch_ready_assignment
from core.employee_patch import apply_plan_patch,PlanPatchError
from core.assignment_plan import step_by_id

def patch(env,run_id,pid='p1'):
    r=env['lifecycle'].get_task(run_id)
    return {'patch_id':pid,'base_task_version':int(r['task_version']),'base_plan_revision':r['assignment']['plan_revision'],'reason':'new authoritative observation','observations':[{'kind':'event','id':'e1'}],'invalidate_steps':['read-a']}

def test_uncertain_descendant_is_not_erased_by_upstream_invalidation(env):
    rid=_patch_ready_assignment(env)
    def change(record,a):
        a=copy.deepcopy(a);s=step_by_id(a,'use-a');s['status']='uncertain';return a,{}
    env['lifecycle'].mutate_assignment(rid,change,rationale='effect uncertain')
    p=patch(env,rid)
    with pytest.raises(PlanPatchError,match='uncertain|running|reconcil'):
        apply_plan_patch(env['lifecycle'],rid,p)
    s=step_by_id(env['lifecycle'].get_assignment(rid),'use-a');assert s['status']=='uncertain' and s['operation_id']=='op-use-a'

def test_changed_task_state_invalidates_patch_without_plan_revision_change(env):
    rid=_patch_ready_assignment(env);p=patch(env,rid)
    before=env['lifecycle'].get_task(rid)['task_version']
    def change(record,a):
        a=copy.deepcopy(a);a['facts']=[{'fact_id':'eligibility','evidence_state':'established','value':False}];return a,{}
    env['lifecycle'].mutate_assignment(rid,change,rationale='business facts changed')
    assert env['lifecycle'].get_task(rid)['task_version']>before
    with pytest.raises(PlanPatchError,match='stale|version'):
        apply_plan_patch(env['lifecycle'],rid,p)

def test_changed_patch_content_cannot_replay_old_success(env):
    rid=_patch_ready_assignment(env);p=patch(env,rid)
    apply_plan_patch(env['lifecycle'],rid,p)
    different={**p,'invalidate_steps':['read-b'],'reason':'different requested patch'}
    with pytest.raises(PlanPatchError,match='conflict|reused|different|digest'):
        apply_plan_patch(env['lifecycle'],rid,different)
