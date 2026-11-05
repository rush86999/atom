"""Independent verifier scope/no-change/stale-audit probes (2026-11-05).

Retained as repair regressions for the direct HTTP canvas slice.
"""
import pytest
from datetime import datetime, timezone, timedelta
from core.models import Canvas,CanvasAudit
from tests.test_covpush_canvasroutes import client,users,_make_user,_make_canvas

@pytest.fixture
def db_session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.database import Base
    engine=create_engine(f'sqlite:///{tmp_path}/verifier-canvas.db',connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    yield db
    db.close();engine.dispose()

@pytest.mark.parametrize('scope',['workspace','tenant'])
@pytest.mark.parametrize('operation',['put','restore'])
def test_out_of_scope_canvas_refuses_before_mutation(client,db_session,users,scope,operation):
    user=_make_user(db_session);user.workspace_id='ws-current';users['current']=user
    canvas=_make_canvas(db_session,user.id,content={'text':'current'})
    canvas.workspace_id='ws-other' if scope=='workspace' else 'ws-current'
    if scope=='tenant':canvas.tenant_id='t-other'
    target=CanvasAudit(canvas_id=canvas.id,tenant_id=canvas.tenant_id,action_type='update',user_id=user.id,canvas_type='generic',details_json={'content':{'text':'old'}},created_at=datetime.now(timezone.utc)-timedelta(days=1))
    db_session.add(target);db_session.commit()
    target_id=target.id;before=db_session.query(CanvasAudit).filter_by(canvas_id=canvas.id).count();old=canvas.content
    if operation=='put':response=client.put(f'/api/canvas/{canvas.id}',json={'text':'unauthorized change'})
    else:response=client.post(f'/api/canvas/{canvas.id}/restore',json={'audit_id':target_id})
    db_session.expire_all()
    count=db_session.query(CanvasAudit).filter_by(canvas_id=canvas.id).count()
    current=db_session.query(Canvas).filter_by(id=canvas.id).one()
    assert count==before and current.content==old,(response.status_code,response.json(),before,count,old,current.content)
    assert response.status_code in (403,404),response.text


def test_no_change_restore_does_not_verify_a_stale_mirror(client,db_session,users):
    user=_make_user(db_session);users['current']=user
    canvas=_make_canvas(db_session,user.id,content={'text':'accepted'})
    target=db_session.query(CanvasAudit).filter_by(canvas_id=canvas.id).one()
    canvas.content={'text':'stale mirror'};db_session.commit()
    response=client.post(f'/api/canvas/{canvas.id}/restore',json={'audit_id':target.id})
    body=response.json()
    db_session.expire_all()
    current=db_session.query(Canvas).filter_by(id=canvas.id).one()
    assert body.get('verification',{}).get('status')!='verified' or current.content=={'text':'accepted'},(body,current.content)

def test_manual_save_cannot_be_verified_by_old_identical_audit(client,db_session,users,monkeypatch):
    user=_make_user(db_session);users['current']=user
    payload={'text':'same material'}
    canvas=_make_canvas(db_session,user.id,content=payload)
    old=CanvasAudit(canvas_id=canvas.id,tenant_id=user.tenant_id,action_type='update',user_id=user.id,canvas_type='generic',details_json={'content':payload,'review_status':'accepted'})
    db_session.add(old);db_session.commit();old_id=old.id
    before=db_session.query(CanvasAudit).filter_by(canvas_id=canvas.id).count()
    async def stale_result(**kwargs):
        return {'success':True,'write_outcome':'committed','canvas_id':canvas.id,'audit_id':old_id,'already_applied':False}
    monkeypatch.setattr('core.canvas_write_service.update_canvas_content',stale_result)
    response=client.put(f'/api/canvas/{canvas.id}',json=payload)
    body=response.json()
    assert db_session.query(CanvasAudit).filter_by(canvas_id=canvas.id).count()==before
    assert body.get('verification',{}).get('status')!='verified',body
