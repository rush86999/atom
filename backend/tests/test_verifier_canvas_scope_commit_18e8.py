"""Independent verifier atomic scope/commit probes (2026-11-05).

Retained as repair regressions for the direct HTTP canvas slice.
"""
import pytest
from sqlalchemy.orm import sessionmaker
from core.models import Canvas, CanvasAudit
from tests.test_verifier_canvas_scope_5eede import db_session
from tests.test_covpush_canvasroutes import client,users,_make_user,_make_canvas
from datetime import datetime,timezone,timedelta

@pytest.mark.parametrize('scope',['workspace','tenant'])
@pytest.mark.parametrize('operation',['put','restore'])
def test_scope_move_after_writer_check_refuses_before_commit(client,db_session,users,monkeypatch,operation,scope):
    from tools import canvas_crud_tool as crud
    user=_make_user(db_session);user.workspace_id='ws-original';users['current']=user
    canvas=_make_canvas(db_session,user.id,content={'text':'current'})
    canvas.workspace_id='ws-original'
    target=CanvasAudit(canvas_id=canvas.id,tenant_id=user.tenant_id,action_type='update',user_id=user.id,canvas_type='generic',details_json={'content':{'text':'historical'}},created_at=datetime.now(timezone.utc)-timedelta(days=1))
    db_session.add(target);db_session.commit();canvas_id=canvas.id;target_id=target.id
    before=db_session.query(CanvasAudit).filter_by(canvas_id=canvas_id).count()
    original=crud.canvas_write_scope_error
    moved=[]
    def check_then_move(db,*args,**kwargs):
        error=original(db,*args,**kwargs)
        if error is None and kwargs.get('lock') and not moved:
            # Separate committed authoritative writer, after the final scope check.
            with sessionmaker(bind=db.get_bind())() as other:
                other.query(Canvas).filter_by(id=canvas_id).update({'workspace_id':'ws-revoked'} if scope=='workspace' else {'tenant_id':'t-revoked'})
                other.commit()
            moved.append(True)
        return error
    monkeypatch.setattr(crud,'canvas_write_scope_error',check_then_move)
    if operation=='put':response=client.put(f'/api/canvas/{canvas_id}',json={'text':'out-of-scope effect'})
    else:response=client.post(f'/api/canvas/{canvas_id}/restore',json={'audit_id':target_id})
    assert moved
    # Fresh session: check both scope winner and durable effects.
    with sessionmaker(bind=db_session.get_bind())() as read:
        row=read.query(Canvas).filter_by(id=canvas_id).one()
        count=read.query(CanvasAudit).filter_by(canvas_id=canvas_id).count()
        observed=(row.workspace_id,row.tenant_id,row.content,count)
    assert observed==('ws-revoked' if scope=='workspace' else 'ws-original','t-revoked' if scope=='tenant' else user.tenant_id,{'text':'current'},before),(response.status_code,response.json(),observed,before)
    assert response.status_code in (403,404,409),response.text
