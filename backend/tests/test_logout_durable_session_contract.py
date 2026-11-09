"""Logout must revoke the exact session across fresh processes."""
import json,os,subprocess,sys,sqlite3
from tests.test_web_password_recovery_contract import recovery_client,known_recovery_user

def test_logged_out_bearer_stays_refused_in_a_fresh_python_process(recovery_client,tmp_path):
    import core.auth as auth
    user=known_recovery_user(recovery_client)
    token=recovery_client.post('/api/auth/login',json={'username':user.email,'password':'InitialPassword1!'}).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    assert recovery_client.get('/api/auth/me',headers=headers).status_code==200
    logout=recovery_client.post('/api/auth/logout',headers=headers)
    assert logout.status_code==200
    after_status=recovery_client.get('/api/auth/me',headers=headers).status_code
    assert after_status==401
    snapshot=tmp_path/'logout-restart.db'
    source=recovery_client.recovery_db.connection().connection.driver_connection
    with sqlite3.connect(snapshot) as target:source.backup(target)
    program="""import sys,json,asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.auth import get_current_user_ws
p=json.load(sys.stdin)
with Session(bind=create_engine(p['database'])) as db:
 print(json.dumps({'allowed':asyncio.run(get_current_user_ws(p['token'],db)) is not None}))
"""
    result=subprocess.run([sys.executable,'-c',program],input=json.dumps({'database':'sqlite:///'+str(snapshot),'token':token}),env=dict(os.environ,SECRET_KEY=auth.SECRET_KEY,TESTING='1'),text=True,capture_output=True,timeout=45)
    assert result.returncode==0
    allowed=json.loads(result.stdout.splitlines()[-1])['allowed']
    assert allowed is False


import pytest


def logged_in(client):
    user=known_recovery_user(client)
    token=client.post('/api/auth/login',json={'username':user.email,'password':'InitialPassword1!'}).json()['access_token']
    return user,token


@pytest.mark.parametrize('transport',['cookie','secure_cookie','query'])
def test_logout_revokes_the_same_transport_that_authorized_it(recovery_client,transport):
    user,token=logged_in(recovery_client)
    options={}
    if transport=='query':options={'params':{'auth_token':token}}
    else:recovery_client.cookies.set('next-auth.session-token' if transport=='cookie' else '__Secure-next-auth.session-token',token)
    response=recovery_client.post('/api/auth/logout',**options)
    assert response.status_code==200
    assert response.json()['verification']['status']=='verified'
    status=recovery_client.get('/api/auth/me',**options).status_code
    assert status==401


def test_logout_only_revokes_the_selected_session(recovery_client):
    from core.models import RevokedToken
    user,first=logged_in(recovery_client)
    second=recovery_client.post('/api/auth/login',json={'username':user.email,'password':'InitialPassword1!'}).json()['access_token']
    assert recovery_client.post('/api/auth/logout',headers={'Authorization':'Bearer '+first}).status_code==200
    second_status=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+second}).status_code
    assert second_status==200
    assert recovery_client.recovery_db.query(RevokedToken).count()==1


def test_bearer_precedes_an_unrelated_cookie_for_logout(recovery_client):
    from core.models import RevokedToken
    first_user,first=logged_in(recovery_client)
    second_user,second=logged_in(recovery_client)
    recovery_client.cookies.set('next-auth.session-token',second)
    result=recovery_client.post('/api/auth/logout',headers={'Authorization':'Bearer '+first})
    assert result.status_code==200
    second_status=recovery_client.get('/api/auth/me').status_code
    assert second_status==200
    rows=recovery_client.recovery_db.query(RevokedToken).all()
    assert [row.user_id for row in rows]==[first_user.id]


@pytest.mark.parametrize('kind',['missing','contradictory','tenant_alias','workspace_alias','tenant_column','missing_tenant_column'])
def test_unverified_logout_audit_never_reports_success(recovery_client,monkeypatch,kind):
    import core.auth_endpoints as endpoint
    from core.models import RevokedToken
    user,token=logged_in(recovery_client)
    from core.models import Workspace
    db=recovery_client.recovery_db
    if db.get(Workspace,'default') is None:
        db.add(Workspace(id='default',name='Unrelated workspace',tenant_id='default',status='active'));db.commit()
    native=endpoint.audit_service.log_event
    def audit(*args,**kwargs):
        if kind=='missing':return None
        if kind=='tenant_alias':kwargs['metadata']={**kwargs['metadata'],'tenant_id':'default'}
        elif kind=='workspace_alias':kwargs['workspace_id']='default'
        elif kind=='tenant_column':kwargs['tenant_id']='default'
        elif kind=='missing_tenant_column':kwargs['tenant_id']=None
        else:kwargs['metadata']={**kwargs['metadata'],'operation_id':'wrong-operation'}
        return native(*args,**kwargs)
    monkeypatch.setattr(endpoint.audit_service,'log_event',audit)
    result=recovery_client.post('/api/auth/logout',headers={'Authorization':'Bearer '+token})
    assert result.status_code==503
    data=result.json()
    assert data['success'] is False
    assert data['verification']=={'status':'unavailable' if kind in ('missing','missing_tenant_column') else 'refuted','effect':'committed'}
    assert data['replay']=='do_not_repeat'
    assert recovery_client.recovery_db.query(RevokedToken).count()==1


def test_lost_logout_confirmation_preserves_identity_and_durable_refusal(recovery_client,monkeypatch,caplog):
    import core.auth_helpers as helper
    from core.models import RevokedToken
    user,token=logged_in(recovery_client)
    native=helper.revoke_token
    def lost(*args,**kwargs):
        native(*args,**kwargs)
        raise RuntimeError('private failure '+token)
    monkeypatch.setattr(helper,'revoke_token',lost)
    result=recovery_client.post('/api/auth/logout',headers={'Authorization':'Bearer '+token})
    assert result.status_code==503
    data=result.json()
    assert data['success'] is False and data['verification']['effect']=='unknown'
    row=recovery_client.recovery_db.query(RevokedToken).one()
    assert data['operation_id']=='logout:'+row.jti
    after_status=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code
    assert after_status==401
    assert token not in result.text and token not in caplog.text


def test_confirmed_logout_rollback_is_truthful_zero_effect(recovery_client,monkeypatch,caplog):
    from sqlalchemy.exc import IntegrityError
    from core.models import RevokedToken,AuditLog
    user,token=logged_in(recovery_client)
    audit_count=recovery_client.recovery_db.query(AuditLog).count()
    def fail():raise IntegrityError('private SQL',{'secret':token},RuntimeError('private failure'))
    monkeypatch.setattr(recovery_client.recovery_db,'commit',fail)
    result=recovery_client.post('/api/auth/logout',headers={'Authorization':'Bearer '+token})
    assert result.status_code==409
    assert result.json()['verification']=={'status':'refused','effect':'none'}
    assert recovery_client.recovery_db.query(RevokedToken).count()==0
    assert recovery_client.recovery_db.query(AuditLog).count()==audit_count
    still_valid=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code
    assert still_valid==200
    assert token not in result.text and token not in caplog.text


def test_unavailable_revocation_read_cannot_grant_a_session(recovery_client,monkeypatch,caplog):
    from core.models import RevokedToken
    user,token=logged_in(recovery_client)
    db=recovery_client.recovery_db;native=db.query
    def query(model,*args,**kwargs):
        if model is RevokedToken:raise RuntimeError('private detail '+token)
        return native(model,*args,**kwargs)
    monkeypatch.setattr(db,'query',query)
    status=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code
    assert status==401
    assert token not in caplog.text


def test_credential_binding_without_revocation_context_is_not_authority(recovery_client):
    from core.auth import credential_session_binding,credential_session_matches
    user=known_recovery_user(recovery_client)
    payload={'sub':user.id,'auth_binding':credential_session_binding(user),'jti':'missing-context-fixture'}
    assert credential_session_matches(payload,user) is False
    assert credential_session_matches(payload,user,db=recovery_client.recovery_db) is True


def test_revocation_read_does_not_flush_or_erase_unrelated_caller_work(recovery_client):
    from sqlalchemy import event,inspect
    from core.auth import is_token_revoked
    user,token=logged_in(recovery_client)
    db=recovery_client.recovery_db;engine=db.get_bind();statements=[]
    user.first_name='Pending caller profile edit'
    def observe(_connection,_cursor,statement,_parameters,_context,_many):statements.append(statement.lstrip().upper())
    event.listen(engine,'before_cursor_execute',observe)
    try:
        assert is_token_revoked('new-unrevoked-fixture',db=db) is False
        assert not any(text.startswith(('UPDATE','INSERT','DELETE')) for text in statements)
        assert inspect(user).attrs.first_name.history.has_changes()
    finally:
        event.remove(engine,'before_cursor_execute',observe)
    db.commit()
    assert user.first_name=='Pending caller profile edit'


@pytest.mark.parametrize('raw_scope',[None,'','default'])
def test_personal_scope_aliases_preserve_raw_identity_in_the_receipt(recovery_client,raw_scope):
    from core.models import AuditLog
    user=known_recovery_user(recovery_client)
    user.tenant_id=raw_scope;recovery_client.recovery_db.commit()
    token=recovery_client.post('/api/auth/login',json={'username':user.email,'password':'InitialPassword1!'}).json()['access_token']
    principal=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+token},params={'tenant_id':'foreign-tenant','workspace_id':'foreign-workspace'})
    assert principal.status_code==200
    assert principal.json()['id']==user.id
    assert principal.json()['tenant_id']==raw_scope
    assert principal.json()['workspace_id']==user.workspace_id
    response=recovery_client.post('/api/auth/logout',headers={'Authorization':'Bearer '+token})
    assert response.status_code==200
    assert response.json()['verification']['status']=='verified'
    audit=recovery_client.recovery_db.get(AuditLog,response.json()['audit_id'])
    metadata=json.loads(audit.metadata_json)
    assert audit.tenant_id=='default'
    assert metadata['tenant_id']=='default' and metadata['raw_tenant_id']==raw_scope
