"""A job moved to a peer agent after read must not be claimed by the old one."""
import json,sqlite3,uuid
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from core.database import Base
from core.models import AgentJob
import api.agent_routes as routes

@pytest.mark.parametrize('peer_moves_agent',[False,True])
def test_begin_job_guards_exact_agent_at_dml(tmp_path,peer_moves_agent):
    path=str(tmp_path/'claim.db');engine=create_engine('sqlite:///'+path)
    Base.metadata.create_all(engine,tables=[AgentJob.__table__])
    with sqlite3.connect(path) as db:db.execute('pragma journal_mode=WAL')
    jid=str(uuid.uuid4())
    with Session(engine) as db:db.add(AgentJob(id=jid,agent_id='original-agent',status='pending'));db.commit()
    moved=[]
    def after_read(conn,cursor,statement,parameters,context,executemany):
        if peer_moves_agent and not moved and statement.lstrip().startswith('SELECT') and 'FROM agent_jobs' in statement:
            moved.append(True)
            with sqlite3.connect(path) as peer:peer.execute('update agent_jobs set agent_id=? where id=?',('peer-agent',jid))
    event.listen(engine,'after_cursor_execute',after_read)
    claimed=routes._begin_job(jid,engine,agent_id='original-agent',execution_id='old-dispatch')
    event.remove(engine,'after_cursor_execute',after_read)
    with Session(engine) as db:r=db.get(AgentJob,jid);material=(r.agent_id,r.status,r.result_summary)
    if peer_moves_agent:assert claimed is False and material==('peer-agent','pending',None),(claimed,material)
    else:assert claimed is True and material[0:2]==('original-agent','running'),(claimed,material)
