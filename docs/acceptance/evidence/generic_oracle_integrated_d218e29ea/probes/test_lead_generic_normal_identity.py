import asyncio
import sqlite3
import uuid
from tests.test_generic_oracle_mutation_contract import scratch_db,_agent

def test_normal_execution_without_explicit_operation_does_not_repeat_uncertain_effect(scratch_db):
    from core.action_registry import action_registry
    name='lead.generic.normal.'+uuid.uuid4().hex
    calls=[]
    async def leaf(tool,args,context=None):
        calls.append(tool)
        with sqlite3.connect(scratch_db['path']) as db:
            db.execute('insert into effects values (?,?)',(uuid.uuid4().hex,'one intended effect'))
        return {'success':True,'status':'success','action_result':'applied'}
    action_registry.register(name,leaf,effects=[{'effect':'create','scope':'local'}])
    server_context={'execution_id':'same-normal-execution','run_id':'same-normal-execution','workspace_id':'w','tenant_id':'t','user_id':'u','agent_id':'scratch-agent'}
    # The actual GenericAgent loop supplies execution context, while ToolCall
    # has only tool+params and the loop does not mint operation_id today.
    first=asyncio.run(_agent(leaf)._step_act_unaudited(name,{},context=dict(server_context),pre_approved=True))
    assert first.get('status')=='uncertain',first
    second=asyncio.run(_agent(leaf)._step_act_unaudited(name,{},context=dict(server_context),pre_approved=True))
    with sqlite3.connect(scratch_db['path']) as db:rows=db.execute('select count(*) from effects').fetchone()[0]
    assert len(calls)==1 and rows==1,(calls,rows,first,second)

def test_logical_operation_id_cannot_change_action(scratch_db):
    from contextlib import contextmanager
    from sqlalchemy.orm import sessionmaker
    from core import outbound_operation_claim as claims
    from core.models import TaskOperationRecord
    Session=sessionmaker(bind=scratch_db['engine'])
    @contextmanager
    def factory():
        with Session() as db:yield db
    def claim(action):
        digest=claims.operation_payload_sha256(workspace_id='w',tenant_id='t',actor_id='u',agent_id='a',execution_id='exec',action=action,frozen_args={'target':'same'})
        return claims.claim_generic_operation(workspace_id='w',tenant_id='t',operation_id='one-logical-operation',action=action,payload_hash=digest,db_factory=factory)
    first=claim('create')
    assert first.get('won') is True,first
    changed=claim('delete')
    with Session() as db:count=db.query(TaskOperationRecord).count()
    assert changed.get('won') is False and changed.get('status')=='conflict' and count==1,(changed,count)


def test_server_intent_slot_does_not_change_with_model_material(scratch_db):
    from core.action_registry import action_registry
    name='lead.generic.intent.'+uuid.uuid4().hex
    calls=[]
    async def leaf(tool,args,context=None):
        calls.append(dict(args))
        with sqlite3.connect(scratch_db['path']) as db:
            db.execute('insert into effects values (?,?)',(uuid.uuid4().hex,str(args)))
        return {'success':True,'action_result':'applied'}
    action_registry.register(name,leaf,effects=[{'effect':'create','scope':'local'}])
    server={'execution_id':'intent-exec','run_id':'intent-exec','workspace_id':'w','tenant_id':'t','user_id':'u','operation_slot':'server-authorized-slot-1'}
    first=asyncio.run(_agent(leaf)._step_act_unaudited(name,{'value':1},context=dict(server),pre_approved=True))
    assert first.get('requires_reconciliation') is True,first
    second=asyncio.run(_agent(leaf)._step_act_unaudited(name,{'value':2},context=dict(server),pre_approved=True))
    with sqlite3.connect(scratch_db['path']) as db: count=db.execute('select count(*) from effects').fetchone()[0]
    assert len(calls)==1 and count==1,(calls,count,first,second)


def test_server_intent_slot_cannot_change_action(scratch_db):
    from core.action_registry import action_registry
    names=['lead.generic.actionslot.'+uuid.uuid4().hex for _ in range(2)]
    calls=[]
    async def leaf(tool,args,context=None):
        calls.append(tool)
        with sqlite3.connect(scratch_db['path']) as db:db.execute('insert into effects values (?,?)',(uuid.uuid4().hex,tool))
        return {'success':True,'action_result':'applied'}
    for name in names: action_registry.register(name,leaf,effects=[{'effect':'create','scope':'local'}])
    server={'execution_id':'same-slot-exec','workspace_id':'w','tenant_id':'t','user_id':'u','operation_slot':'server-intent-1'}
    first=asyncio.run(_agent(leaf)._step_act_unaudited(names[0],{},context=dict(server),pre_approved=True))
    assert first.get('requires_reconciliation') is True,first
    second=asyncio.run(_agent(leaf)._step_act_unaudited(names[1],{},context=dict(server),pre_approved=True))
    with sqlite3.connect(scratch_db['path']) as db:count=db.execute('select count(*) from effects').fetchone()[0]
    assert len(calls)==1 and count==1,(calls,count,first,second)


def test_explicit_operation_without_workspace_cannot_dispatch(scratch_db):
    from core.action_registry import action_registry
    name='lead.generic.unscoped.'+uuid.uuid4().hex
    calls=[]
    async def leaf(tool,args,context=None):
        calls.append(tool)
        with sqlite3.connect(scratch_db['path']) as db:db.execute('insert into effects values (?,?)',(uuid.uuid4().hex,'unscoped'))
        return {'success':True,'action_result':'applied'}
    action_registry.register(name,leaf,effects=[{'effect':'create','scope':'local'}])
    result=asyncio.run(_agent(leaf)._step_act_unaudited(name,{},context={'operation_id':'unscoped-op'},pre_approved=True))
    with sqlite3.connect(scratch_db['path']) as db:count=db.execute('select count(*) from effects').fetchone()[0]
    assert not calls and count==0,(calls,count,result)
