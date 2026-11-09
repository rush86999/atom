"""Recovery must be available at the exact auth router mounted by normal main."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.auth_routes import router


@pytest.fixture
def recovery_client(db_session, monkeypatch):
    # This is the same router main_api_app mounts. It does not mount the
    # unrelated safe-app core auth router or perform a mail/provider action.
    app=FastAPI()
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


def test_normal_recovery_mount_reuses_one_existing_handler_per_path():
    from core.auth_endpoints import forgot_password,verify_token,reset_password
    expected={'/api/auth/forgot-password':forgot_password,
              '/api/auth/verify-token':verify_token,
              '/api/auth/reset-password':reset_password}
    for path,handler in expected.items():
        matches=[route for route in router.routes if route.path==path and 'POST' in route.methods]
        assert len(matches)==1
        assert matches[0].endpoint is handler


def known_recovery_user(client):
    from core.models import Tenant
    from tests.test_covpush_canvasroutes import _make_user
    from core.auth import get_password_hash
    db=client.recovery_db
    for identity in ['default','t1','foreign-tenant']:
        if db.get(Tenant,identity) is None:
            db.add(Tenant(id=identity,name=identity,subdomain='recovery-'+identity))
    db.commit()
    user=_make_user(db)
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
    unknown=recovery_client.post('/api/auth/forgot-password',json={'email':'absent@example.test'})
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
