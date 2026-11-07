"""Public board ownership baseline; auth identity fixed, real producer/readback."""
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base,get_db
from core.auth import get_current_user
from core.models import User
from core.models_board import Board,BoardColumn
from api.board_routes import router

@pytest.mark.parametrize('same_owner',[False,True])
def test_column_creation_respects_owner(tmp_path,same_owner):
    engine=create_engine('sqlite:///'+str(tmp_path/'board.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,expire_on_commit=False)
    uid=str(uuid.uuid4());peer=str(uuid.uuid4());bid=str(uuid.uuid4())
    with Session() as db:
        for u in [uid,peer]:db.add(User(id=u,email=u+'@example.test',hashed_password='not-a-login-secret',first_name='Scratch',last_name='User',role='member',status='active',is_active=True))
        db.add(Board(id=bid,name='Owner board',owner_user_id=uid if same_owner else peer))
        db.commit()
    app=FastAPI();app.include_router(router)
    def session():
        with Session() as db:yield db
    def actor():
        with Session() as db:return db.get(User,uid)
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_current_user]=actor
    with TestClient(app) as client:
        listing=client.get('/api/boards').json()
        response=client.post('/api/boards/'+bid+'/columns',json={'name':'Added by requester'})
    with Session() as db:count=db.query(BoardColumn).filter(BoardColumn.board_id==bid).count()
    if same_owner:
        assert response.status_code==201 and count==1,(response.status_code,response.text,count)
    else:
        assert not listing,listing
        assert response.status_code in [403,404] and count==0,(response.status_code,response.text,count)
