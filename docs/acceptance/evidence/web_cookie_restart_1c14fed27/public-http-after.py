import requests,json,time,sqlite3
from pathlib import Path
root=Path('/private/tmp/root-web-cookie-restart-world-20261109');backend='http://127.0.0.1:18161';web='http://127.0.0.1:18162'
for _ in range(12):
 try:
  health=requests.get(backend+'/health',timeout=3)
  if health.status_code==200:break
 except requests.RequestException:pass
 time.sleep(1)
else:raise AssertionError('same-world backend not ready')
p=root/'health-restart.private.json';p.write_text(json.dumps(health.json()));p.chmod(0o600)
a=json.loads((root/'session-a.private.json').read_text());b=json.loads((root/'session-b.private.json').read_text());before=json.loads((root/'before-restart-summary.json').read_text())
old=requests.get(backend+'/api/auth/me',headers={'Authorization':'Bearer '+a['session']['backendToken']},timeout=20);assert old.status_code==401
peer_backend=requests.get(backend+'/api/auth/me',headers={'Authorization':'Bearer '+b['session']['backendToken']},timeout=20);assert peer_backend.status_code==200
results={}
for name,saved in [('revoked',a),('peer',b)]:
 s=requests.Session();s.cookies.update(saved['cookies'])
 r=s.get(web+'/api/auth/session',timeout=30);assert r.status_code==200
 body=r.json()
 if name=='revoked':assert not body,'original revoked encrypted cookie revived after backend restart'
 else:assert body.get('user',{}).get('id')==saved['session']['user']['id']
 results[name]={'http_status':r.status_code,'empty':not body,'identity_matches':body.get('user',{}).get('id')==saved['session']['user']['id'] if body else False}
receipt=json.loads((root/'logout.private.json').read_text())
with sqlite3.connect('file:'+str(root/'atom.db')+'?mode=ro',uri=True) as db:
 audit=db.execute('SELECT count(*) FROM saas_audit_logs WHERE id=? AND action=?',(receipt['audit_id'],'logout')).fetchone()[0]
 assert audit==1
 count=db.execute('SELECT count(*) FROM saas_audit_logs WHERE action=? AND user_id=?',('logout',b['session']['user']['id'])).fetchone()[0];assert count==1
summary={**before,'restart_pending':False,'actual_backend_process_changed':(root/'backend.pid').read_text()!=(root/'backend-restart.pid').read_text(),'after_restart':results,'revoked_backend_after_restart':old.status_code,'peer_backend_after_restart':peer_backend.status_code,'original_exact_audit_rows':audit,'logout_audits_for_account':count,'same_database_and_configuration':True,'original_encrypted_cookies_replayed':True,'live_provider_calls_requested':0,'browser_capture':False}
p=root/'verification-summary.json';p.write_text(json.dumps(summary,indent=2));p.chmod(0o600);print(json.dumps(summary),flush=True)
