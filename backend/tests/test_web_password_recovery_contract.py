"""Recovery uses normal main's registry-loaded auth plus its mobile router."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.auth_routes import router


@pytest.fixture
def recovery_client(db_session, monkeypatch):
    # Main eagerly loads core auth through its existing plugin registry before
    # adding the mobile router. Mobile alone was an incomplete reproduction.
    from core.lazy_integration_registry import load_integration
    app=FastAPI()
    app.include_router(load_integration('auth', registry='api_routers'))
    app.include_router(router)
    from core.database import get_db
    import core.auth_endpoints as recovery
    from core.security.auth_rate_limit import AuthRateLimiter
    app.dependency_overrides[get_db]=lambda: db_session
    for name,limit in [('_recovery_limiter',5),('_verify_limiter',10),('_reset_limiter',5)]:
        monkeypatch.setattr(recovery,name,AuthRateLimiter(limit=limit,window_seconds=300))
    captured=[]
    monkeypatch.setattr(recovery,'send_smtp_email',lambda *args: captured.append(args) or True)
    from types import SimpleNamespace
    monkeypatch.setattr(recovery,'get_config',lambda: SimpleNamespace(server=SimpleNamespace(app_url='http://localhost:3000')))
    # Synthetic process-local settings only; SMTP itself is always doubled.
    import uuid
    for name,value in [('SMTP_HOST','smtp.invalid'),('SMTP_PORT','587'),('SMTP_USER','recovery@example.test'),('SMTP_PASSWORD',uuid.uuid4().hex)]:
        monkeypatch.setenv(name,value)
    with TestClient(app) as client:
        client.recovery_db=db_session
        client.captured_recovery_mail=captured
        yield client


@pytest.mark.parametrize('path',['forgot-password','verify-token','reset-password'])
def test_normal_mounted_auth_recovery_route_has_its_validation_boundary(recovery_client,path):
    response=recovery_client.post('/api/auth/'+path,json={})
    assert response.status_code==422,response.text


def test_normal_recovery_mount_reuses_one_existing_handler_per_path(recovery_client):
    from core.auth_endpoints import forgot_password,verify_token,reset_password
    expected={'/api/auth/forgot-password':forgot_password,
              '/api/auth/verify-token':verify_token,
              '/api/auth/reset-password':reset_password}
    for path,handler in expected.items():
        matches=[route for route in recovery_client.app.routes if route.path==path and 'POST' in route.methods]
        assert len(matches)==1
        assert matches[0].endpoint is handler


def known_recovery_user(client):
    from core.models import Tenant,Workspace
    from tests.test_covpush_canvasroutes import _make_user
    from core.auth import get_password_hash
    db=client.recovery_db
    for identity in ['default','t1','foreign-tenant']:
        if db.get(Tenant,identity) is None:
            db.add(Tenant(id=identity,name=identity,subdomain='recovery-'+identity))
    db.commit()
    if db.get(Workspace,'recovery-workspace') is None:
        db.add(Workspace(id='recovery-workspace',name='Recovery workspace',tenant_id='t1',status='active'))
        db.commit()
    user=_make_user(db)
    user.workspace_id='recovery-workspace'
    user.hashed_password=get_password_hash('InitialPassword1!')
    db.commit()
    return user


def request_captured_recovery(client,user):
    from urllib.parse import urlparse,parse_qs
    import re
    response=client.post('/api/auth/forgot-password',json={'email':user.email})
    assert response.status_code==200,response.text
    assert len(client.captured_recovery_mail)==1
    body=client.captured_recovery_mail[0][2]
    url=re.search(r'https?://\S+',body).group(0)
    return response,url,parse_qs(urlparse(url).query)['token'][0]


def test_recovery_link_reaches_the_implemented_reset_page_and_token_is_hashed(recovery_client):
    import hashlib
    from urllib.parse import urlparse
    from core.models import PasswordResetToken
    user=known_recovery_user(recovery_client)
    response,url,token=request_captured_recovery(recovery_client,user)
    assert urlparse(url).path=='/auth/reset-password'
    row=recovery_client.recovery_db.query(PasswordResetToken).one()
    assert row.token==hashlib.sha256(token.encode()).hexdigest()
    assert token not in response.text


def test_unavailable_mail_is_global_non_enumerating_and_mints_no_token(recovery_client,monkeypatch):
    from core.models import PasswordResetToken
    user=known_recovery_user(recovery_client)
    for name in ['SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD']:monkeypatch.delenv(name,raising=False)
    known=recovery_client.post('/api/auth/forgot-password',json={'email':user.email})
    unknown=recovery_client.post('/api/auth/forgot-password',json={'email':'absent@example.com'})
    assert known.status_code==unknown.status_code==503
    assert known.json()==unknown.json()
    assert recovery_client.recovery_db.query(PasswordResetToken).count()==0
    assert not recovery_client.captured_recovery_mail


def test_used_token_peer_winner_cannot_be_overwritten_by_stale_reset(recovery_client,monkeypatch):
    from sqlalchemy import update
    from sqlalchemy.orm import Session
    from datetime import datetime,timezone
    from core.models import User,PasswordResetToken
    from core.auth import verify_password
    import core.auth_endpoints as recovery
    user=known_recovery_user(recovery_client)
    _,_,token=request_captured_recovery(recovery_client,user)
    db=recovery_client.recovery_db
    reset=db.query(PasswordResetToken).one()
    reset_id,user_id=reset.id,user.id
    native_hash=recovery.get_password_hash
    winner_hash=native_hash('PeerPassword1!')
    def interleave(password):
        result=native_hash(password)
        with Session(bind=db.get_bind()) as peer:
            peer.execute(update(PasswordResetToken).where(PasswordResetToken.id==reset_id).values(used=True,used_at=datetime.now(timezone.utc)))
            peer.execute(update(User).where(User.id==user_id).values(hashed_password=winner_hash))
            peer.commit()
        return result
    monkeypatch.setattr(recovery,'get_password_hash',interleave)
    response=recovery_client.post('/api/auth/reset-password',json={'token':token,'password':'StalePassword1!'})
    assert response.status_code in (400,409),response.text
    db.expire_all()
    assert verify_password('PeerPassword1!',db.get(User,user_id).hashed_password)


def test_foreign_token_scope_cannot_change_the_current_account(recovery_client):
    import hashlib,secrets
    from datetime import datetime,timedelta,timezone
    from core.models import PasswordResetToken,User
    from core.auth import verify_password
    user=known_recovery_user(recovery_client)
    token=secrets.token_urlsafe(32)
    db=recovery_client.recovery_db
    db.add(PasswordResetToken(user_id=user.id,tenant_id='foreign-tenant',token=hashlib.sha256(token.encode()).hexdigest(),expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
    db.commit();user_id=user.id
    response=recovery_client.post('/api/auth/reset-password',json={'token':token,'password':'ForeignPassword1!'})
    assert response.status_code in (400,403,409),response.text
    db.expire_all()
    assert verify_password('InitialPassword1!',db.get(User,user_id).hashed_password)


def test_valid_recovery_is_one_use_and_normal_login_uses_the_new_credential(recovery_client):
    from core.models import PasswordResetToken
    client=recovery_client;user=known_recovery_user(client)
    email=user.email
    _,_,token=request_captured_recovery(client,user)
    assert client.post('/api/auth/verify-token',json={'token':token}).json()['valid'] is True
    response=client.post('/api/auth/reset-password',json={'token':token,'password':'ChangedPassword1!'})
    assert response.status_code==200,response.text
    assert response.json()['verification']['status']=='verified'
    assert 'access_token' not in response.json()
    assert client.recovery_db.query(PasswordResetToken).one().used is True
    assert client.post('/api/auth/reset-password',json={'token':token,'password':'SecondPassword1!'}).status_code==400
    assert client.post('/api/auth/login',json={'username':email,'password':'InitialPassword1!'}).status_code==401
    signed_in=client.post('/api/auth/login',json={'username':email,'password':'ChangedPassword1!'})
    assert signed_in.status_code==200
    assert 'access_token' in signed_in.json()


@pytest.mark.parametrize('condition',['used','expired','inactive'])
def test_unusable_recovery_keeps_the_account_unchanged(recovery_client,condition):
    from core.models import PasswordResetToken,User
    from core.auth import verify_password
    from datetime import datetime,timedelta,timezone
    client=recovery_client;user=known_recovery_user(client)
    _,_,token=request_captured_recovery(client,user)
    db=client.recovery_db;row=db.query(PasswordResetToken).one();user_id=user.id
    if condition=='used':row.used=True
    if condition=='expired':row.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)
    if condition=='inactive':user.is_active=False
    db.commit()
    assert client.post('/api/auth/verify-token',json={'token':token}).json()['valid'] is False
    response=client.post('/api/auth/reset-password',json={'token':token,'password':'DeniedPassword1!'})
    assert response.status_code==400,response.text
    db.expire_all();assert verify_password('InitialPassword1!',db.get(User,user_id).hashed_password)


@pytest.mark.parametrize('raw_tenant',[None,'','default'])
def test_personal_scope_aliases_remain_supported(recovery_client,raw_tenant):
    client=recovery_client;user=known_recovery_user(client)
    user.tenant_id=raw_tenant;user.workspace_id=None;client.recovery_db.commit()
    _,_,token=request_captured_recovery(client,user)
    response=client.post('/api/auth/reset-password',json={'token':token,'password':'PersonalPassword1!'})
    assert response.status_code==200,response.text
    assert response.json()['verification']['status']=='verified'


@pytest.mark.parametrize('fault',['lost_commit','readback'])
def test_uncertain_reset_keeps_original_identity_without_authentication_grant(recovery_client,monkeypatch,fault):
    import core.auth_endpoints as recovery
    from core.models import PasswordResetToken,User
    from core.auth import verify_password
    client=recovery_client;user=known_recovery_user(client)
    _,_,token=request_captured_recovery(client,user)
    db=client.recovery_db;reset_id=db.query(PasswordResetToken).one().id;user_id=user.id
    if fault=='lost_commit':
        native=db.commit
        def lost():
            native();raise RuntimeError('confirmation unavailable')
        monkeypatch.setattr(db,'commit',lost)
    else:
        def unavailable(*args,**kwargs):raise RuntimeError('readback unavailable')
        monkeypatch.setattr(recovery,'Session',unavailable)
    response=client.post('/api/auth/reset-password',json={'token':token,'password':'CommittedPassword1!'})
    assert response.status_code==503,response.text
    body=response.json()
    assert body['operation_id']=='password-reset:'+reset_id
    assert body['replay']=='do_not_repeat' and 'access_token' not in body
    assert body['verification']['effect']==('unknown' if fault=='lost_commit' else 'committed')
    db.expire_all()
    assert db.get(PasswordResetToken,reset_id).used is True
    assert verify_password('CommittedPassword1!',db.get(User,user_id).hashed_password)


def test_confirmed_integrity_rollback_is_no_effect_and_does_not_log_material(recovery_client,monkeypatch,caplog):
    from sqlalchemy.exc import IntegrityError
    from core.models import PasswordResetToken,User
    from core.auth import verify_password
    import secrets
    client=recovery_client;user=known_recovery_user(client)
    _,_,token=request_captured_recovery(client,user)
    db=client.recovery_db;user_id=user.id;marker=secrets.token_urlsafe(24)
    def failed():raise IntegrityError('credential update',{'private_value':marker},Exception('rejected'))
    monkeypatch.setattr(db,'commit',failed)
    response=client.post('/api/auth/reset-password',json={'token':token,'password':'RolledBackPassword1!'})
    assert response.status_code==409,response.text
    assert response.json()['verification']['effect']=='none'
    assert marker not in response.text and marker not in caplog.text
    db.expire_all()
    assert db.query(PasswordResetToken).one().used is False
    assert verify_password('InitialPassword1!',db.get(User,user_id).hashed_password)


def test_successful_recovery_invalidates_other_outstanding_links(recovery_client):
    user=known_recovery_user(recovery_client)
    _,_,first=request_captured_recovery(recovery_client,user)
    recovery_client.captured_recovery_mail.clear()
    _,_,second=request_captured_recovery(recovery_client,user)
    assert first != second
    result=recovery_client.post('/api/auth/reset-password',json={'token':first,'password':'RecoveredPassword1!'})
    assert result.status_code==200,result.text
    assert result.json()['verification']['status']=='verified'
    assert recovery_client.post('/api/auth/verify-token',json={'token':second}).json()['valid'] is False
    assert recovery_client.post('/api/auth/reset-password',json={'token':second,'password':'OldLinkPassword1!'}).status_code==400


def test_recovery_issuance_cannot_outlive_a_peer_credential_change(recovery_client,monkeypatch):
    from sqlalchemy import update
    from sqlalchemy.orm import Session
    from core.models import User,PasswordResetToken
    import core.auth_endpoints as recovery
    user=known_recovery_user(recovery_client)
    user_id,email=user.id,user.email
    native=recovery.secrets.token_urlsafe
    winner=recovery.get_password_hash('PeerWinnerPassword1!')
    def interleave(size):
        with Session(bind=recovery_client.recovery_db.get_bind()) as peer:
            peer.execute(update(User).where(User.id==user_id).values(hashed_password=winner))
            peer.commit()
        return native(size)
    monkeypatch.setattr(recovery.secrets,'token_urlsafe',interleave)
    result=recovery_client.post('/api/auth/forgot-password',json={'email':email})
    assert result.status_code==409,result.text
    db=recovery_client.recovery_db
    db.expire_all()
    assert db.get(User,user_id).hashed_password==winner
    assert db.query(PasswordResetToken).count()==0
    assert recovery_client.captured_recovery_mail==[]
