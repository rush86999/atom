"""Draft caller guards: workspace event scope and dispatch-owned finalization."""
import asyncio,json,uuid
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.database import Base
from core.models import AgentJob
import api.agent_routes as routes

@pytest.mark.parametrize('workspace',['default','workspace-private'])
def test_step_event_has_only_its_workspace_channel(monkeypatch,workspace):
    send=AsyncMock();monkeypatch.setattr(routes.ws_manager,'broadcast',send)
    asyncio.run(routes._broadcast_agent_step('agent',{'output':'private result'},{'workspace_id':workspace,'tenant_id':'t','job_id':'j','execution_id':'e'}))
    targets=[c.args[0] for c in send.call_args_list]
    assert targets==['workspace:'+workspace],targets

@pytest.mark.parametrize('correct_dispatch',[False,True])
def test_finish_requires_exact_dispatch_identity(tmp_path,correct_dispatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'job.db'))
    Base.metadata.create_all(engine,tables=[AgentJob.__table__])
    jid=str(uuid.uuid4());original=json.dumps({'dispatch_execution_id':'winner','peer_progress':'preserve'})
    with Session(engine) as db:db.add(AgentJob(id=jid,agent_id='a',status='running',result_summary=original));db.commit()
    out=routes._execution_outcome({'status':'success'})
    routes._finish_job(jid,out,engine,execution_id='winner' if correct_dispatch else 'stale-dispatch')
    with Session(engine) as db:
        row=db.get(AgentJob,jid);status=row.status;summary=row.result_summary
    if correct_dispatch:assert status=='success',status
    else:assert status=='running' and summary==original,(status,summary)
