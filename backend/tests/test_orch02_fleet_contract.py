"""Integrated ORCH-02 chain/cache/capability/finalizer contracts (verifier 19-batch)."""
import asyncio
import pytest
from sqlalchemy import update
from core.models import AgentExecution, DelegationChain
from core.fleet_admiral import FleetAdmiral
from core.atom_meta_agent import _execution_succeeded
from tests.test_orch02_specialist_response import env,_seed_fleet,FakeSpecialist,TENANT,WORKSPACE,REQUEST,_summary

@pytest.fixture(autouse=True)
def specialists(monkeypatch):
    FakeSpecialist.calls=[];FakeSpecialist.behavior={}
    monkeypatch.setattr('core.generic_agent.GenericAgent',FakeSpecialist)

def call(env,*,task=REQUEST,tenant=TENANT,roster=None,context=None):
    with env.Session() as db:
        fleet=FleetAdmiral(db,env.agent.llm)
        return asyncio.run(fleet.execute_recruited_specialists(task=task,user_id='user-1',chain_id='chain-controlled',roster=roster or _summary()['result']['recruitment_roster'],tenant_id=tenant,workspace_id=WORKSPACE,context=context or {}))

@pytest.mark.parametrize('cached',[False,True])
def test_foreign_chain_is_not_read_or_mutated(env,cached):
    _seed_fleet(env,a1_tenant=TENANT if cached else 'foreign-tenant',a2_tenant=TENANT if cached else 'foreign-tenant')
    if cached:assert call(env)['success'] is True
    before=len(FakeSpecialist.calls)
    with env.Session() as db:original=db.query(DelegationChain).filter_by(id='chain-controlled').one().metadata_json
    result=call(env,tenant='foreign-tenant')
    with env.Session() as db:after=db.query(DelegationChain).filter_by(id='chain-controlled').one().metadata_json
    assert result.get('success') is False and len(FakeSpecialist.calls)==before and original==after,result

def test_empty_capabilities_are_not_domain_qualification(env):
    _seed_fleet(env,a1_caps=(),a2_caps=())
    result=env.run(enforced=True)
    assert result['success'] is False and FakeSpecialist.calls==[],(result,FakeSpecialist.calls)

@pytest.mark.parametrize('change',['opaque_task_case','roster_domain'])
def test_completed_cache_binds_exact_task_and_roster_material(env,change):
    _seed_fleet(env)
    task='Inspect business record ID AbC-7302'
    first=call(env,task=task);assert first['success'] is True
    if change=='opaque_task_case':second=call(env,task='Inspect business record ID aBc-7302')
    else:
        roster=_summary()['result']['recruitment_roster'];roster[0]=dict(roster[0],domain='unsupported-procurement-role')
        second=call(env,task=task,roster=roster)
    assert second.get('cached') is not True,(change,second)

def test_cancelled_chain_does_not_return_old_completed_cache(env):
    _seed_fleet(env);assert call(env)['success'] is True
    with env.Session() as db:
        db.execute(update(DelegationChain).where(DelegationChain.id=='chain-controlled').values(status='cancelled'));db.commit()
    before=len(FakeSpecialist.calls)
    result=call(env,context={'cancelled':True})
    assert result.get('success') is False and result.get('status')=='cancelled' and len(FakeSpecialist.calls)==before,result

@pytest.mark.parametrize('mode',['success','failure','cancelled'])
def test_enforced_response_finalizes_its_durable_execution(env,mode):
    _seed_fleet(env);context={}
    if mode=='failure':FakeSpecialist.behavior={'a1':'fail','a2':'fail'}
    if mode=='cancelled':context={'fleet_cancel_check':lambda:len(FakeSpecialist.calls)>=1}
    result=env.run(enforced=True,context=context)
    with env.Session() as db:
        row=db.query(AgentExecution).filter_by(id=result['execution_id']).one()
        status=row.status;completed_at=row.completed_at
    expected={'success':'completed','failure':'failed','cancelled':'cancelled'}[mode]
    assert status==expected and completed_at is not None,(mode,status,completed_at,result['status'])
    if mode!='success':assert _execution_succeeded(result) is False,result

def test_shared_audit_bracket_uses_same_execution_and_truthful_success(env,monkeypatch):
    _seed_fleet(env);closed=[]
    monkeypatch.setattr(env.agent,'_close_audit_bracket',lambda *args,**kwargs:closed.append((args,kwargs)))
    result=env.run(enforced=True)
    assert result['success'] is True and len(closed)==1
    args,kwargs=closed[0]
    assert args[0]==result['execution_id'] and kwargs['success'] is True,(args[0],result['execution_id'],kwargs)

@pytest.mark.parametrize('raw',[{'success':False,'status':'completed','final_output':'not actually completed'},{'success':True,'status':'budget_exceeded','final_output':'Stopped at the allowed budget'}])
def test_contradictory_or_terminal_failure_is_not_specialist_success(env,monkeypatch,raw):
    _seed_fleet(env)
    async def bad_result(self,*args,**kwargs):return dict(raw)
    monkeypatch.setattr(FakeSpecialist,'execute',bad_result)
    result=env.run(enforced=True)
    assert result['success'] is False and not any(x['status']=='success' for x in result['specialist_results']),result
