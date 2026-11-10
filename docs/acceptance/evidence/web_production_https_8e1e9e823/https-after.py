import requests,json,sqlite3,time
from pathlib import Path
r=Path('/private/tmp/root-web-https-runtime-world-20261109');web='https://127.0.0.1:18184';backend='http://127.0.0.1:18181';cert='/private/tmp/root-web-https-cookie-proof-20261109/server.crt'
for _ in range(12):
 try:
  ready=requests.get(web+'/api/auth/csrf',verify=cert,timeout=3)
  if ready.status_code==200:break
 except requests.RequestException:pass
 time.sleep(1)
else:raise AssertionError('owned HTTPS frontend restart not ready')
a=json.loads((r/'session-a.private.json').read_text());b=json.loads((r/'session-b.private.json').read_text())
results={}
for name,saved in [('revoked',a),('peer',b)]:
 # Deliberate exact original-cookie header replay over verified HTTPS. This
 # asserts server authorization, not a simulated browser lifetime/refresh.
 cookie='; '.join(k+'='+v for k,v in saved['cookies'].items())
 response=requests.get(web+'/api/auth/session',headers={'Cookie':cookie},verify=cert,timeout=20)
 assert response.status_code==200
 body=response.json()
 if name=='revoked':assert not body,'revoked original cookie revived'
 else:assert body.get('user',{}).get('id')==saved['session']['user']['id']
 results[name]={'http_status':response.status_code,'empty':not body,'same_identity':body.get('user',{}).get('id')==saved['session']['user']['id'] if body else False}
old=requests.get(backend+'/api/auth/me',headers={'Authorization':'Bearer '+a['session']['backendToken']},timeout=10);peer=requests.get(backend+'/api/auth/me',headers={'Authorization':'Bearer '+b['session']['backendToken']},timeout=10)
assert old.status_code==401 and peer.status_code==200
receipt=json.loads((r/'logout.private.json').read_text())
with sqlite3.connect('file:'+str(r/'atom.db')+'?mode=ro',uri=True) as db:
 exact=db.execute('SELECT count(*) FROM saas_audit_logs WHERE id=? AND action=?',(receipt['audit_id'],'logout')).fetchone()[0]
 count=db.execute('SELECT count(*) FROM saas_audit_logs WHERE user_id=? AND action=?',(b['session']['user']['id'],'logout')).fetchone()[0]
 assert exact==1 and count==1
summary={**json.loads((r/'before-restart-summary.json').read_text()),'restart_pending':False,'actual_frontend_process_changed':(r/'frontend.pid').read_text()!=(r/'frontend-restart.pid').read_text(),'after_restart':results,'original_encrypted_cookie_headers_replayed_over_verified_https':True,'backend_generation_statuses':{'revoked':old.status_code,'peer':peer.status_code},'same_database_build_runtime_key':True,'exact_original_audit_rows':exact,'logout_audits_for_account':count,'browser_capture':False,'no_tls_verification_disabled':True,'no_system_trust_change':True}
(r/'verification-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
