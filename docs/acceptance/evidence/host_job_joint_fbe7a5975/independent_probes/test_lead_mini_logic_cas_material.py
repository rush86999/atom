"""Logic CAS must not erase a same-source peer language change."""
import sqlite3
import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from core.database import Base
from core.models import CanvasLogic
from core.canvas_logic_service import CanvasLogicService,LogicConflict

@pytest.mark.parametrize('peer_changes_language',[False,True])
def test_logic_cas_binds_prior_language(tmp_path,peer_changes_language):
    path=str(tmp_path/'logic.db');engine=create_engine('sqlite:///'+path)
    Base.metadata.create_all(engine)
    with sqlite3.connect(path) as db:db.execute('pragma journal_mode=WAL')
    with Session(engine) as db:db.add(CanvasLogic(id='logic',canvas_id='canvas',source='old',language='python'));db.commit()
    changed=[]
    def after_read(conn,cursor,statement,parameters,context,executemany):
        if peer_changes_language and not changed and statement.lstrip().startswith('SELECT') and 'FROM canvas_logic' in statement:
            changed.append(True)
            with sqlite3.connect(path) as peer:peer.execute("update canvas_logic set language='javascript' where id='logic'")
    event.listen(engine,'after_cursor_execute',after_read)
    refused=False
    with Session(engine) as db:
        try:CanvasLogicService(db).save_logic(canvas_id='canvas',source='new',language='python',require_cas=True)
        except LogicConflict:refused=True
    event.remove(engine,'after_cursor_execute',after_read)
    with sqlite3.connect(path) as db:row=db.execute('select source,language from canvas_logic').fetchone()
    if peer_changes_language:assert refused and row==('old','javascript'),(refused,row)
    else:assert not refused and row==('new','python'),(refused,row)
