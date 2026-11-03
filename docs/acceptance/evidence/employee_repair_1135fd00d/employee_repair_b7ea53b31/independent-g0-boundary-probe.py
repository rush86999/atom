import asyncio
from sqlalchemy.orm import sessionmaker
from tests.test_goal_effect_family_controls import _file_engine,_add_goal,_hold,PLAN
from core.goals.goal_run_service import GoalRunService
from core.goals import goal_run_executors
from core.models import Canvas

def test_plan_change_after_binding_validation_cannot_win_claim(tmp_path,monkeypatch):
    engine=_file_engine(tmp_path,'plan-claim.db');factory=sessionmaker(bind=engine,expire_on_commit=False);_add_goal(factory)
    writer=GoalRunService(workspace_id='ws-a',tenant_id='t-a',session_factory=factory)
    run_id=writer.create_run('goal-family',role='sales',plan=PLAN)['id'];writer.transition(run_id,'active');_hold(writer,run_id)
    reviewed=writer.get_run(run_id)['pending_decision'];effects=[]
    async def execute(self,run,decision):
        effects.append([s['id'] for s in run['plan']]);return {'controlled_effect':True}
    monkeypatch.setattr(goal_run_executors.GoalRunExecutors,'execute',execute)
    class RacingService(GoalRunService):
        fired=False
        def get_run(self,rid):
            snapshot=super().get_run(rid)
            if not self.fired:
                self.fired=True
                writer.set_plan(rid,[{'id':'replacement','kind':'canvas_work','title':'Unreviewed work','canvas_type':'document'}])
            return snapshot
    racer=RacingService(workspace_id='ws-a',tenant_id='t-a',session_factory=factory)
    result=asyncio.run(racer.resume(run_id,True,reviewer='lead-a',expected_decision_id=reviewed['decision_id'],expected_decision_binding=reviewed['decision_binding']))
    print('observed',{'result_resumed':result.get('resumed'),'effects':effects,'plan':writer.get_run(run_id)['plan']})
    assert result.get('resumed') is False,'old approval claimed a plan changed after validation'
    assert not effects
    assert writer.get_run(run_id)['pending_decision']['decision_id']==reviewed['decision_id']

def test_assignment_projection_cannot_execute_as_native_canvas_work(tmp_path):
    engine=_file_engine(tmp_path,'projection.db');factory=sessionmaker(bind=engine,expire_on_commit=False);_add_goal(factory)
    svc=GoalRunService(workspace_id='ws-a',tenant_id='t-a',session_factory=factory)
    run_id=svc.create_run('goal-family',role='sales',plan=[{'id':'projected-read','kind':'operation','title':'Assignment operation'}],parameters={'task_lifecycle':{}})['id']
    svc.transition(run_id,'active')
    result=asyncio.run(svc.execute_decision(run_id,{'decision':'ADVANCE','human_approved':True,'rationale':'probe'}))
    with factory() as db:count=db.query(Canvas).filter(Canvas.goal_run_id==run_id).count()
    print('observed',{'result':result,'created_canvases':count})
    assert count==0,'non-executable assignment projection fell through to native canvas execution'
