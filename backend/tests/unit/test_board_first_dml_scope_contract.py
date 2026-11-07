"""Peer wins before first authoritative DML, not after a locked claim."""
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,event,update
from sqlalchemy.orm import sessionmaker
from core.database import Base,get_db
from core.auth import get_current_user
from core.models import User
from core.models_board import Board,BoardColumn
from api.board_routes import router

@pytest.mark.parametrize("race",["none","owner_transfer","actor_deactivated"])
def test_board_write_rechecks_scope_in_its_actual_claim(tmp_path,race):
    engine=create_engine("sqlite:///"+str(tmp_path/"atomic-board.db"),connect_args={"check_same_thread":False,"timeout":2})
    Base.metadata.create_all(engine)
    with engine.connect() as conn:conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Factory=sessionmaker(bind=engine,expire_on_commit=False)
    actor,peer,bid=[str(uuid.uuid4()) for _ in range(3)]
    with Factory() as setup:
        for uid in [actor,peer]:setup.add(User(id=uid,email=uid+"@example.test",first_name="Scratch",last_name="User",hashed_password="not-a-login-secret",role="member",status="active",is_active=True))
        setup.add(Board(id=bid,name="Atomic owned board",owner_user_id=actor));setup.commit()
    writer=Factory();connection=writer.connection();fired=[]
    def before_first_dml(conn,cursor,statement,parameters,context,executemany):
        if conn is not connection or fired or not statement.lstrip().upper().startswith(("UPDATE ","INSERT ","DELETE ")):return
        fired.append(True)
        if race!="none":
            with Factory() as winner:
                if race=="owner_transfer":winner.execute(update(Board).where(Board.id==bid).values(owner_user_id=peer))
                else:winner.execute(update(User).where(User.id==actor).values(is_active=False))
                winner.commit()
    event.listen(engine,"before_cursor_execute",before_first_dml)
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:writer
    app.dependency_overrides[get_current_user]=lambda:writer.get(User,actor)
    try:
        with TestClient(app,raise_server_exceptions=False) as client:
            response=client.post("/api/boards/"+bid+"/columns",json={"name":"Authorized only before peer wins"})
        with Factory() as observer:
            count=observer.query(BoardColumn).filter(BoardColumn.board_id==bid).count()
            if race=="owner_transfer":assert observer.get(Board,bid).owner_user_id==peer
            if race=="actor_deactivated":assert observer.get(User,actor).is_active is False
        assert fired,"must exercise the real effect/claim boundary"
        if race=="none":assert response.status_code==201 and count==1,(response.status_code,response.text,count)
        else:assert response.status_code in (403,404,409) and count==0,(response.status_code,response.text,count)
    finally:
        event.remove(engine,"before_cursor_execute",before_first_dml);writer.close();engine.dispose()
