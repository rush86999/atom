"""Independent callback interleavings; run only after durable-state source freezes."""
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import event
from api import sso_oidc_routes as routes
from core.models import User, OAuthState, SSOConfiguration, Tenant
from core.personal_scope import PERSONAL_TENANT_ID

backend = Path(routes.__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('root_sso_state_fixtures', backend/'tests/api/test_sso_oidc_routes.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
engine=b.engine;db=b.db;admin=b.admin;client=b.client;provider=b.provider
concurrency_client=b.concurrency_client
_clear_oidc_caches=b._clear_oidc_caches

@pytest.mark.parametrize('change',['disable_config','deactivate_tenant','replace_state_binding'])
def test_peer_authority_wins_before_state_claim(concurrency_client, provider, monkeypatch, change):
    cl, eng, Session, db = concurrency_client
    assert b._save_config(cl,provider).status_code==200
    callback=b._provider_redirect(b._start_login(cl))
    calls={'token':0,'peer':False}
    original=provider.token
    def counted(form):
        calls['token']+=1
        return original(form)
    monkeypatch.setattr(provider,'token',counted)
    def peer_before_claim(conn,cursor,statement,parameters,context,executemany):
        lowered=statement.lower()
        if calls['peer'] or not lowered.lstrip().startswith('delete') or 'oauth_states' not in lowered:return
        calls['peer']=True
        peer=Session()
        try:
            if change=='disable_config':peer.query(SSOConfiguration).filter_by(provider='oidc').one().enabled=False
            elif change=='deactivate_tenant':peer.query(Tenant).filter_by(id=PERSONAL_TENANT_ID).one().is_active=False
            else:
                row=peer.query(OAuthState).filter_by(provider='oidc').one()
                row.extra_data={**row.extra_data,'nonce':'peer-replaced-nonce'}
            peer.commit()
        finally:peer.close()
    event.listen(eng,'before_cursor_execute',peer_before_claim)
    try:response=b._callback(cl,callback)
    finally:event.remove(eng,'before_cursor_execute',peer_before_claim)
    observed=response.status_code
    fresh=Session()
    try:
        count=fresh.query(User).filter_by(email=provider.email).count()
        retained=fresh.query(OAuthState).filter_by(provider='oidc').count()
        assert calls['peer'] is True
        assert observed in (401,409,503),{'status':observed,'token_exchanges':calls['token'],'new_users':count}
        assert calls['token']==0
        assert count==0
        assert retained==1
    finally:fresh.close()

def test_unknown_tenant_active_refuses_before_state_creation(client,provider,db):
    assert b._save_config(client,provider).status_code==200
    db.query(Tenant).filter_by(id=PERSONAL_TENANT_ID).one().is_active=None
    db.commit()
    response=client.get('/api/auth/sso/oidc/login',follow_redirects=False)
    assert response.status_code==503,{'status':response.status_code}
    assert db.query(OAuthState).count()==0

def test_environment_secret_rotation_changes_binding(db):
    common={'issuer_url':'https://issuer.example.invalid','client_id':'controlled-client','enabled':True,'default_role':'member','allowed_domains':['example.com']}
    first=routes._config_fingerprint(db,{**common,'client_secret':'controlled-first'},b.CALLBACK)
    second=routes._config_fingerprint(db,{**common,'client_secret':'controlled-second'},b.CALLBACK)
    assert first is not None and second is not None
    assert first!=second,'effective secret rotation must invalidate pending login binding'
