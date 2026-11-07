import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
import sqlite3
import uuid
from sqlalchemy import create_engine,event,update,text
from sqlalchemy.orm import sessionmaker
from core.models import Base,TaskOperationRecord
from core import outbound_operation_claim as claims
from tests.test_generic_oracle_mutation_contract import scratch_db,_agent

def test_status_guard_is_database_cas(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'race.db'))
    @event.listens_for(engine,'connect')
    def wal(conn,_):
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')
    TaskOperationRecord.__table__.create(engine)
    Session=sessionmaker(bind=engine)
    with Session() as db:
        db.add(TaskOperationRecord(id='r',workspace_id='w',tenant_id='t',run_id='run',idempotency_key='key',payload_sha256='p',operation_id='op',operation_type='generic:agent',status=claims.CLAIMED));db.commit()
    armed=[True]
    @event.listens_for(engine,'after_cursor_execute')
    def peer(conn,cursor,statement,params,ctx,many):
        if armed[0] and statement.lstrip().upper().startswith('SELECT') and 'task_operation_records' in statement:
            armed[0]=False
            with Session() as p:
                p.execute(update(TaskOperationRecord).where(TaskOperationRecord.id=='r').values(status=claims.UNCERTAIN_EFFECT));p.commit()
    @contextmanager
    def factory():
        with Session() as db:yield db
    changed=claims.mark_status('r',claims.DISPATCHING,expected_status=claims.CLAIMED,db_factory=factory)
    with Session() as db:actual=db.get(TaskOperationRecord,'r').status
    assert changed is False and actual==claims.UNCERTAIN_EFFECT,(changed,actual)

def test_successful_claim_cannot_certify_refuted_replay(monkeypatch,scratch_db):
    from core.action_registry import action_registry
    from core.oracle import register_postcondition,OracleResult
    name='lead.generic.replay.'+uuid.uuid4().hex
    calls=[]
    async def leaf(tool,args,context=None):
        calls.append(tool)
        with sqlite3.connect(scratch_db['path']) as db:db.execute('insert into effects values (?,?)',('one','landed'))
        return {'success':True,'status':'success','action_result':'applied'}
    async def verifier(ctx):
        row=ctx['db'].execute(text("select value from effects where id='one'")).first()
        return OracleResult(name,bool(row and row[0]=='landed'),'fresh actual readback')
    action_registry.register(name,leaf,effects=[{'effect':'create','scope':'local'}]);register_postcondition(name)(verifier)
    context={'operation_id':'stable-op','workspace_id':'w','tenant_id':'t','user_id':'u','execution_id':'exec'}
    first=asyncio.run(_agent(leaf)._step_act_unaudited(name,{},context=dict(context),pre_approved=True))
    assert first.get('oracle_verified') is True,first
    with sqlite3.connect(scratch_db['path']) as db:db.execute('delete from effects')
    fresh_context=dict(context)
    second=asyncio.run(_agent(leaf)._step_act_unaudited(name,{},context=fresh_context,pre_approved=True))
    assert len(calls)==1,calls
    assert second.get('success') is not True and second.get('requires_reconciliation') is True,second
