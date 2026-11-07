"""A normal plan may legitimately use the same create tool twice."""
import asyncio,sqlite3,uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock
from sqlalchemy import text
from tests.test_generic_oracle_mutation_contract import scratch_db,_build_execute_agent,_oracle_env_on

def test_two_verified_normal_intents_use_same_action(scratch_db,monkeypatch):
    from core.action_registry import action_registry
    from core.oracle import register_postcondition,OracleResult
    from core.react_models import ReActStep,ToolCall
    _oracle_env_on(monkeypatch)
    name='lead.generic.two-normal.'+uuid.uuid4().hex
    async def leaf(tool,args,context=None):
        with sqlite3.connect(scratch_db['path']) as db:db.execute('insert into effects values (?,?)',(args['id'],args['value']))
        return {'success':True,'status':'success','action_result':'applied'}
    async def verifier(ctx):
        row=ctx['db'].execute(text('select value from effects where id=:id'),{'id':ctx['id']}).fetchone()
        return OracleResult(name,bool(row and row[0]==ctx['value']),'fresh exact row readback')
    action_registry.register(name,leaf,effects=[{'effect':'create','scope':'local'}])
    register_postcondition(name)(verifier)
    agent=_build_execute_agent(scratch_db,monkeypatch)
    agent.mcp=SimpleNamespace(call_tool=leaf,get_all_tools=AsyncMock(return_value=[]))
    agent._react_step=AsyncMock(side_effect=[
        ReActStep(thought='first requested record',action=ToolCall(tool=name,params={'id':'a','value':'first'})),
        ReActStep(thought='second requested record',action=ToolCall(tool=name,params={'id':'b','value':'second'})),
        ReActStep(thought='done',final_answer='Both records created.')])
    result=asyncio.run(agent.execute('Create two separate records a and b',context={'workspace_id':'w','tenant_id':'t','user_id':'u','execution_id':'two-create-exec'}))
    with sqlite3.connect(scratch_db['path']) as db:rows=db.execute('select id,value from effects order by id').fetchall()
    assert rows==[('a','first'),('b','second')] and result.get('status')=='success',(rows,result)
