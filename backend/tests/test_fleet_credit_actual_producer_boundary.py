"""Controlled fleet/real mutation/independent SQL Oracle join; no model inference.

The decision loop is a deterministic driver. Fleet dispatch, GenericAgent's
public wrapper, mutation claim, independent postcondition, execution recorder,
and credit consumer are real. Governance is pre-approved at the tool leaf;
this does not qualify model selection, approval policy, or broad competence.
"""
import asyncio
import sqlite3
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
from sqlalchemy import text
from core.action_registry import action_registry
from core.fleet_admiral import FleetAdmiral
from core.generic_agent import GenericAgent
from core.models import AgentExecution, DelegationChain, FleetRoutingAudit, TaskOperationRecord
from core.oracle import OracleResult, register_postcondition
from tests.test_fleet_credit_receipt_integration import (
    fleet_world, _restore_oracle_verifiers, _seed_fleet, _credit, _stats,
    TENANT, WORKSPACE, ACTOR,
)


def test_real_fleet_dispatch_produces_receipt_and_unique_credit(fleet_world, monkeypatch):
    monkeypatch.setenv('ATOM_CONTRIBUTION_CREDIT_ENABLED', 'true')
    world = fleet_world
    action = 'canvas.root_credit.' + uuid.uuid4().hex
    effect_id = 'root-effect-' + uuid.uuid4().hex
    calls = []
    async def leaf(tool, args, context=None):
        calls.append(tool)
        with sqlite3.connect(world.path) as raw:
            raw.execute('insert into effects values (?,?)', (effect_id, args['value']))
        return {'success':True, 'status':'success', 'action_result':'applied'}
    async def verifier(ctx):
        row=ctx['db'].execute(text('select value from effects where id=:id'), {'id':effect_id}).fetchone()
        return OracleResult(action, bool(row and row[0]=='landed'), 'fresh independent SQL value comparison')
    action_registry.register(action, leaf, effects=[{'effect':'create','scope':'local'}])
    register_postcondition(action)(verifier)
    class ControlledDecisionAgent(GenericAgent):
        def __init__(self, agent_model, workspace_id='default', **kwargs):
            self.id=agent_model.id; self.name=agent_model.name
            self.workspace_id=workspace_id; self.tenant_id=agent_model.tenant_id
            self.config={}; self._custom_actions={}
            self.mcp=SimpleNamespace(call_tool=leaf)
            self.world_model=SimpleNamespace(record_experience=AsyncMock())
        async def _execute_impl(self, task_input, context=None, step_callback=None):
            context=dict(context or {})
            context['operation_id']=context['execution_id']+':root-effect'
            applied=await self._step_act_unaudited(action, {'value':'landed'}, context=context, pre_approved=True)
            assert applied.get('oracle_verified') is True, applied
            result={'success':True,'status':'objective_satisfied','output':'Verified SQL work landed', 'final_output':'Verified SQL work landed','steps':[]}
            await self._record_execution(task_input, result, context)
            return result
    monkeypatch.setattr('core.generic_agent.GenericAgent', ControlledDecisionAgent)
    _seed_fleet(world, child_executions=[])
    with world.session() as db:
        audit=db.get(FleetRoutingAudit,'audit-credit'); audit.specialists_count=1
        audit.roster_json=[{'agent_id':'ag-fleet','domain':'finance'}]
        db.get(DelegationChain,'chain-credit').status='active';db.commit()
        admiral=FleetAdmiral.__new__(FleetAdmiral);admiral.db=db;admiral.llm=None
        args=dict(task='controlled verified contribution',user_id=ACTOR,chain_id='chain-credit',
                  roster=[{'agent_id':'ag-fleet','agent_name':'Fleet Specialist','domain':'finance'}],
                  tenant_id=TENANT,workspace_id=WORKSPACE,context={})
        result=asyncio.run(admiral.execute_recruited_specialists(**args))
        assert result.get('success') is True, result
        child=result['specialist_results'][0]['execution_id']
        db.expire_all()
        execution=db.get(AgentExecution,child)
        assert execution and execution.status=='completed'
        operations=db.query(TaskOperationRecord).filter_by(run_id=child,status='succeeded').all()
        assert any(o.operation_type=='generic:agent:'+action for o in operations)
        assert _credit(db) is True
        assert _stats(db,action).get('verified_success')==1
        assert _stats(db,'finance').get('verified_success',0)==0
        repeated=asyncio.run(admiral.execute_recruited_specialists(**args))
        assert repeated.get('success') is True
        assert _credit(db) is False
        assert len(calls)==1
        assert _stats(db,action).get('verified_success')==1
