"""Independent handoff consumers; execute only against a declared frozen source."""
import importlib.util
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from sqlalchemy import event
from api import sso_oidc_routes as routes
from core.models import OAuthState
backend=Path(routes.__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('root_independent_web_sso_fixtures',backend/'tests/api/test_sso_oidc_routes.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
engine=b.engine;db=b.db;admin=b.admin;client=b.client
web_provider=b.web_provider;web_app_url=b.web_app_url
concurrency_client=b.concurrency_client;_clear_oidc_caches=b._clear_oidc_caches

def handoff(cl,p):
 assert b._save_config(cl,p).status_code==200
 login=b._web_login(cl,return_to='/settings?review=exact')
 assert login.status_code==302
 cb=b._callback(cl,b._provider_redirect(login.headers['Location']))
 assert cb.status_code==302
 assert not cb.text
 return b._web_callback_code(cb.headers['Location'])

def test_actual_web_sequence_preserves_relative_target_and_is_one_use(client,web_provider,web_app_url):
 code=handoff(client,web_provider)
 r=b._web_exchange(client,code)
 assert r.status_code==200
 body=r.json()
 assert body.get('return_to')=='/settings?review=exact'
 assert body.get('token_type')=='bearer' and body.get('access_token')
 assert r.headers.get('cache-control')=='no-store'
 assert r.headers.get('referrer-policy')=='no-referrer'
 replay=b._web_exchange(client,code)
 assert replay.status_code==401 and 'access_token' not in replay.json()

@pytest.mark.parametrize('change',['expire','replace_return','replace_browser','remove_scope'])
def test_peer_handoff_material_wins_before_claim(concurrency_client,web_provider,web_app_url,change):
 cl,eng,Session,db=concurrency_client
 code=handoff(cl,web_provider);seen={'peer':False}
 def before(conn,cursor,statement,parameters,context,many):
  if seen['peer'] or not statement.lower().lstrip().startswith('delete') or 'oauth_states' not in statement.lower():return
  seen['peer']=True
  peer=Session()
  try:
   row=peer.query(OAuthState).filter_by(provider='oidc_web_handoff').one()
   if change=='expire':row.expires_at=datetime.now(timezone.utc)-timedelta(minutes=2)
   else:
    extra=dict(row.extra_data)
    if change=='replace_return':extra['return_to']='/settings?review=peer'
    elif change=='replace_browser':extra['browser_digest']='peer-replacement'
    elif change=='remove_scope':extra.pop('source_origin',None)
    row.extra_data=extra
   peer.commit()
  finally:peer.close()
 event.listen(eng,'before_cursor_execute',before)
 try:r=b._web_exchange(cl,code)
 finally:event.remove(eng,'before_cursor_execute',before)
 assert seen['peer']
 assert r.status_code in (401,409,503)
 assert 'access_token' not in r.json()
 peer=Session()
 try:
  row=peer.query(OAuthState).filter_by(provider='oidc_web_handoff').one()
  if change=='replace_return':assert row.extra_data['return_to']=='/settings?review=peer'
  if change=='replace_browser':assert row.extra_data['browser_digest']=='peer-replacement'
  if change=='remove_scope':assert 'source_origin' not in row.extra_data
 finally:peer.close()
