"""Independent negative: existing bearer must not survive verified recovery."""
from tests.test_web_password_recovery_contract import recovery_client, known_recovery_user, request_captured_recovery

def test_pre_recovery_bearer_is_rejected_after_verified_password_recovery(recovery_client):
    user=known_recovery_user(recovery_client)
    login=recovery_client.post('/api/auth/login',json={'username':user.email,'password':'InitialPassword1!'})
    assert login.status_code==200,login.text
    bearer=login.json()['access_token']
    headers={'Authorization':'Bearer '+bearer}
    assert recovery_client.get('/api/auth/me',headers=headers).status_code==200
    _,_,token=request_captured_recovery(recovery_client,user)
    result=recovery_client.post('/api/auth/reset-password',json={'token':token,'password':'RecoveredPassword1!'})
    assert result.status_code==200,result.text
    assert result.json()['verification']['status']=='verified'
    after_status=recovery_client.get('/api/auth/me',headers=headers).status_code
    assert after_status==401


def recovered_session_pair(client):
    user=known_recovery_user(client)
    email=user.email
    before=client.post('/api/auth/login',json={'username':email,'password':'InitialPassword1!'}).json()['access_token']
    _,_,token=request_captured_recovery(client,user)
    reset=client.post('/api/auth/reset-password',json={'token':token,'password':'RecoveredPassword1!'})
    assert reset.status_code==200
    after=client.post('/api/auth/login',json={'username':email,'password':'RecoveredPassword1!'}).json()['access_token']
    return user.id,before,after


def test_old_session_cannot_refresh_but_fresh_login_can(recovery_client):
    _,before,after=recovered_session_pair(recovery_client)
    old_status=recovery_client.post('/api/auth/refresh',headers={'Authorization':'Bearer '+before}).status_code
    assert old_status==401
    fresh=recovery_client.post('/api/auth/refresh',headers={'Authorization':'Bearer '+after})
    assert fresh.status_code==200
    renewed=fresh.json()['access_token']
    new_status=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+renewed}).status_code
    assert new_status==200


def test_core_and_shared_websocket_readers_reject_old_session(recovery_client):
    import asyncio
    from core.auth import get_current_user_ws
    from core.security_dependencies import get_current_user_websocket
    _,before,after=recovered_session_pair(recovery_client)
    db=recovery_client.recovery_db
    for reader in (lambda token:get_current_user_ws(token,db),lambda token:get_current_user_websocket(None,token,db)):
        old_allowed=asyncio.run(reader(before)) is not None
        new_allowed=asyncio.run(reader(after)) is not None
        assert old_allowed is False
        assert new_allowed is True


def test_session_binding_survives_a_new_python_process(recovery_client,tmp_path):
    import json,os,subprocess,sys
    import core.auth as auth
    _,before,after=recovered_session_pair(recovery_client)
    env=dict(os.environ,SECRET_KEY=auth.SECRET_KEY,TESTING='1')
    program="""import sys,json,asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from core.auth import get_current_user_ws
p=json.load(sys.stdin)
with Session(bind=create_engine(p['database'])) as db:
 print(json.dumps([asyncio.run(get_current_user_ws(token,db)) is not None for token in p['tokens']]))
"""
    # The shared fixture uses SQLite memory. Persist its exact post-reset
    # state with SQLite backup, then read that file in a genuinely new process.
    import sqlite3
    snapshot=tmp_path/'session-restart.db'
    source=recovery_client.recovery_db.connection().connection.driver_connection
    with sqlite3.connect(snapshot) as target:
        source.backup(target)
    result=subprocess.run([sys.executable,'-c',program],input=json.dumps({'database':'sqlite:///'+str(snapshot),'tokens':[before,after]}),env=env,text=True,capture_output=True,timeout=45)
    assert result.returncode==0
    allowed=json.loads(result.stdout.splitlines()[-1])
    assert allowed==[False,True]


def test_shared_mobile_and_enterprise_tokens_bind_the_current_credential(recovery_client):
    from core.auth import create_mobile_token,verify_mobile_token
    from core.enterprise_auth_service import EnterpriseAuthService
    from core.models import User
    user=known_recovery_user(recovery_client);uid=user.id
    mobile=create_mobile_token(user,'fixture-device')
    service=EnterpriseAuthService()
    enterprise=service.create_access_token(uid,user=user)
    refresh=service.create_refresh_token(uid,user=user)
    db=recovery_client.recovery_db
    assert verify_mobile_token(mobile['access_token'],db) is not None
    assert service.verify_token(enterprise,db=db) is not None
    _,_,token=request_captured_recovery(recovery_client,user)
    assert recovery_client.post('/api/auth/reset-password',json={'token':token,'password':'RecoveredPassword1!'}).status_code==200
    db.expire_all();current=db.get(User,uid)
    old_mobile_allowed=verify_mobile_token(mobile['access_token'],db) is not None
    old_enterprise_allowed=service.verify_token(enterprise,db=db) is not None
    old_refresh_allowed=service.verify_token(refresh,db=db,allow_refresh=True) is not None
    assert (old_mobile_allowed,old_enterprise_allowed,old_refresh_allowed)==(False,False,False)
    assert verify_mobile_token(create_mobile_token(current,'fixture-device')['access_token'],db) is not None
    assert service.verify_token(service.create_access_token(uid,user=current),db=db) is not None


def test_legacy_unbound_session_requires_fresh_sign_in(recovery_client):
    from core.auth import create_access_token
    user=known_recovery_user(recovery_client)
    legacy=create_access_token({'sub':user.id})
    status=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+legacy}).status_code
    assert status==401


def test_credential_proof_is_private_subject_bound_and_ignores_profile_edits(recovery_client):
    from core.auth import credential_session_binding,credential_session_matches
    from types import SimpleNamespace
    user=known_recovery_user(recovery_client)
    proof=credential_session_binding(user)
    payload={'sub':user.id,'auth_binding':proof}
    raw_not_disclosed=user.hashed_password not in proof
    assert raw_not_disclosed
    user.first_name='Edited profile'
    assert credential_session_matches(payload,user)
    other=SimpleNamespace(id=user.id+'-other',hashed_password=user.hashed_password)
    assert credential_session_matches(payload,other) is False
    missing=SimpleNamespace(id=user.id,hashed_password=None)
    assert credential_session_matches(payload,missing) is False


def test_refresh_tokens_are_not_access_authority(recovery_client):
    from core.auth import create_mobile_token,SECRET_KEY
    from core.enterprise_auth_service import EnterpriseAuthService
    user=known_recovery_user(recovery_client)
    service=EnterpriseAuthService(secret_key=SECRET_KEY)
    access=service.create_access_token(user.id,user=user)
    access_status=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+access}).status_code
    assert access_status==200
    for token in (service.create_refresh_token(user.id,user=user),create_mobile_token(user,'fixture-device')['refresh_token']):
        access_status=recovery_client.get('/api/auth/me',headers={'Authorization':'Bearer '+token}).status_code
        assert access_status==401


def test_missing_password_sso_binding_is_explicit_and_changes_when_password_added(recovery_client):
    from core.auth import credential_session_binding,credential_session_matches
    from types import SimpleNamespace
    user=SimpleNamespace(id='sso-subject',hashed_password=None)
    payload={'sub':user.id,'auth_binding':credential_session_binding(user)}
    assert credential_session_matches(payload,user)
    user.hashed_password='new-durable-password-material'
    assert credential_session_matches(payload,user) is False


def test_authenticated_password_change_also_requires_a_fresh_session(recovery_client):
    user=known_recovery_user(recovery_client)
    email=user.email
    token=recovery_client.post('/api/auth/login',json={'username':email,'password':'InitialPassword1!'}).json()['access_token']
    headers={'Authorization':'Bearer '+token}
    changed=recovery_client.post('/api/auth/change-password',headers=headers,json={'current_password':'InitialPassword1!','new_password':'ChangedPassword1!'})
    assert changed.status_code==200
    assert changed.json()['requires_reauthentication'] is True
    old_status=recovery_client.get('/api/auth/me',headers=headers).status_code
    assert old_status==401
    fresh=recovery_client.post('/api/auth/login',json={'username':email,'password':'ChangedPassword1!'})
    assert fresh.status_code==200


def test_mobile_refresh_public_route_cannot_launder_a_pre_reset_session(recovery_client):
    from core.auth import create_mobile_token
    from core.models import MobileDevice,User
    user=known_recovery_user(recovery_client);uid=user.id
    device=MobileDevice(id='recovery-device',user_id=uid,device_token='synthetic-recovery-device',platform='web',status='active',tenant_id=user.tenant_id)
    db=recovery_client.recovery_db;db.add(device);db.commit()
    initial=create_mobile_token(user,device.id)['refresh_token']
    valid=recovery_client.post('/api/auth/mobile/refresh',json={'refresh_token':initial})
    assert valid.status_code==200
    _,_,reset=request_captured_recovery(recovery_client,user)
    assert recovery_client.post('/api/auth/reset-password',json={'token':reset,'password':'RecoveredPassword1!'}).status_code==200
    old_status=recovery_client.post('/api/auth/mobile/refresh',json={'refresh_token':initial}).status_code
    assert old_status==401
    db.expire_all();current=db.get(User,uid)
    fresh=create_mobile_token(current,device.id)['refresh_token']
    fresh_status=recovery_client.post('/api/auth/mobile/refresh',json={'refresh_token':fresh}).status_code
    assert fresh_status==200


def test_inflight_authenticated_change_cannot_overwrite_a_peer_reset(recovery_client,monkeypatch):
    from sqlalchemy import update
    from sqlalchemy.orm import Session
    from core.models import User
    import core.auth_endpoints as auth
    user=known_recovery_user(recovery_client);uid=user.id
    token=recovery_client.post('/api/auth/login',json={'username':user.email,'password':'InitialPassword1!'}).json()['access_token']
    native=auth.get_password_hash
    winner=native('PeerWinnerPassword1!')
    def interleave(password):
        result=native(password)
        with Session(bind=recovery_client.recovery_db.get_bind()) as peer:
            peer.execute(update(User).where(User.id==uid).values(hashed_password=winner))
            peer.commit()
        return result
    monkeypatch.setattr(auth,'get_password_hash',interleave)
    response=recovery_client.post('/api/auth/change-password',headers={'Authorization':'Bearer '+token},json={'current_password':'InitialPassword1!','new_password':'StaleWriterPassword1!'})
    assert response.status_code==409
    db=recovery_client.recovery_db;db.expire_all()
    winner_preserved=db.get(User,uid).hashed_password==winner
    assert winner_preserved
