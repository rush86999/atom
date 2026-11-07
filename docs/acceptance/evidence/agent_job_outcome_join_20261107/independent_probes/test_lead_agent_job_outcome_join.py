"""Durable admission job must reflect the execution business outcome."""
import asyncio,uuid
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.database import Base
from core.models import AgentJob
import api.agent_routes as routes

@pytest.mark.parametrize('outcome',['uncertain','failed','blocked','cancelled','success'])
def test_job_status_preserves_execution_outcome(tmp_path,monkeypatch,outcome):
    engine=create_engine('sqlite:///'+str(tmp_path/'jobs.db'))
    Base.metadata.create_all(engine,tables=[AgentJob.__table__])
    jid=str(uuid.uuid4())
    with Session(engine) as db:db.add(AgentJob(id=jid,agent_id='a',status='pending'));db.commit()
    result={'status':outcome,'requires_reconciliation':outcome=='uncertain','output':'controlled execution result'}
    monkeypatch.setattr(routes,'execute_agent_task',AsyncMock(return_value=result))
    returned=asyncio.run(routes._dispatch_admitted_run('a',{},jid,None,engine))
    assert returned==result
    with Session(engine) as db:status=db.get(AgentJob,jid).status
    if outcome=='success':assert status=='success',status
    else:assert status!='success',(outcome,status)
