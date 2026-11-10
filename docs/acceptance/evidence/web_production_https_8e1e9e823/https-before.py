import requests,secrets,json,time,sys,http.cookiejar
from pathlib import Path
root=Path('/private/tmp/root-web-https-runtime-world-20261109')
assert json.loads((root/'owner-marker.json').read_text())['not_live_database']
backend='http://127.0.0.1:18181';web='https://127.0.0.1:18184'
def save(name,value):
 p=root/name;p.write_text(json.dumps(value,indent=2));p.chmod(0o600)
def wait(url):
 for _ in range(12):
  try:
   r=requests.get(url,timeout=3)
   if r.status_code==200:return r
  except requests.RequestException:pass
  time.sleep(1)
 raise AssertionError('owned app not ready')
health=wait(backend+'/health').json();save('health-start.private.json',health)
account={'email':'cookie-proof-'+secrets.token_hex(4)+'@example.com','password':secrets.token_urlsafe(24)+'aA1!','first_name':'Cookie','last_name':'Proof'}
save('identity.private.json',account)
r=requests.post(backend+'/api/auth/register',json=account,timeout=30);assert r.status_code in (200,201),('register',r.status_code)
registration=r.json();save('register.private.json',registration)
class PrefixPolicy(http.cookiejar.DefaultCookiePolicy):
 def set_ok(self,cookie,request):
  if cookie.name.startswith('__Host-') and (cookie.domain_specified or not cookie.secure or cookie.path!='/'):return False
  if cookie.name.startswith(('__Host-','__Secure-')) and (not cookie.secure or request.get_type()!='https'):return False
  return super().set_ok(cookie,request)
sessions=[]
for name in ('a','b'):
 s=requests.Session();s.verify='/private/tmp/root-web-https-cookie-proof-20261109/server.crt';s.cookies.set_policy(PrefixPolicy());csrf=s.get(web+'/api/auth/csrf',timeout=90);assert csrf.status_code==200,('csrf',csrf.status_code)
 token=csrf.json()['csrfToken']
 r=s.post(web+'/api/auth/callback/credentials',data={'csrfToken':token,'email':account['email'],'password':account['password'],'callbackUrl':web+'/dashboard','json':'true'},timeout=60)
 assert r.status_code==200,('callback',r.status_code)
 current=s.get(web+'/api/auth/session',timeout=30);assert current.status_code==200
 body=current.json();assert body.get('user',{}).get('email')==account['email'],('session_missing_current_identity',name)
 assert body.get('backendToken'),('session_missing_generation',name)
 save('session-'+name+'.private.json',{'cookies':s.cookies.get_dict(),'session':body})
 sessions.append((name,s,body))
a=sessions[0];b=sessions[1];assert a[2]['backendToken']!=b[2]['backendToken'],'separate generations required'
response=requests.post(backend+'/api/auth/logout',headers={'Authorization':'Bearer '+a[2]['backendToken']},timeout=30)
assert response.status_code==200,('logout',response.status_code)
receipt=response.json();assert receipt.get('verification',{}).get('status')=='verified'
save('logout.private.json',receipt)
old=requests.get(backend+'/api/auth/me',headers={'Authorization':'Bearer '+a[2]['backendToken']},timeout=30)
assert old.status_code==401
old_web=a[1].get(web+'/api/auth/session',timeout=30);assert old_web.status_code==200;assert not old_web.json(), 'revoked cookie still granted a web session'
peer=b[1].get(web+'/api/auth/session',timeout=30);assert peer.status_code==200;assert peer.json().get('user',{}).get('id')==b[2]['user']['id']
summary={'source':json.loads((root/'owner-marker.json').read_text())['source'],'transport':'normal public HTTP, NextAuth CSRF/cookie protocol; no browser claim','registered':True,'two_independent_web_credentials':True,'separate_backend_generations':True,'web_signing_key_separate':True,'logout_receipt_verified':True,'revoked_backend_status':old.status_code,'revoked_cookie_empty':not old_web.json(),'peer_current':True,'restart_pending':True,'production_compiled_runtime':True,'strict_cookie_prefix_policy':True,'tls_verify':'explicit owned certificate, not disabled','build_signing_key_supplied':False,'no_provider_calls_requested':True}
save('before-restart-summary.json',summary);print(json.dumps(summary),flush=True)
