"""Publish precondition failure must not commit runtime preparation."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.database import Base
from core.models import MiniApp
from core.mini_app_service import publish

@pytest.mark.parametrize('initial_image',[None,'retained-rootfs.img'])
def test_missing_blueprint_does_not_commit_preparation(tmp_path,initial_image):
    engine=create_engine('sqlite:///'+str(tmp_path/'publish.db'))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(MiniApp(id='app',tenant_id='t',created_by='u',name='App',blueprint_canvas_id='missing-source',manifest={'dependencies':[]},runtime_image=initial_image))
        db.commit()
        app=db.get(MiniApp,'app')
        with pytest.raises(ValueError,match='Blueprint canvas'):
            publish(app,db,operation_id='publish-op',request_sha256='exact-request',actor_id='u')
        db.rollback()
    with Session(engine) as db:
        actual=db.get(MiniApp,'app').runtime_image
    assert actual==initial_image,(initial_image,actual)
