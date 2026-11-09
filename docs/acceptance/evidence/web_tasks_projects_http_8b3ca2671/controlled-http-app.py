"""Controlled HTTP join: real auth/task/project routers; not whole-app boot proof."""
import json, os, pathlib, secrets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
fixture = pathlib.Path(os.environ['ATOM_WEB_HTTP_FIXTURE'])
if not fixture.is_dir() or not (fixture / 'owner-marker').is_file():
    raise RuntimeError('Expected explicit owned scratch fixture')
from core.database import Base, engine, SessionLocal
from core.models import Tenant, Workspace, User
import service_delivery.models
from core.auth import get_password_hash
from core.auth_endpoints import router as auth_router
from api.nav_stub_routes import router as nav_router
Base.metadata.create_all(engine)
credentials = fixture / 'credentials.private.json'
if credentials.exists():
    account = json.loads(credentials.read_text())
else:
    account = {'username': 'web-journey@example.invalid', 'password': secrets.token_urlsafe(24)}
    credentials.write_text(json.dumps(account)); credentials.chmod(0o600)
with SessionLocal() as db:
    if db.get(User, 'web-http-user') is None:
        db.add(Tenant(id='web-http-tenant', name='Web HTTP fixture', subdomain='web-http-fixture', plan_type='free', edition='personal'))
        db.add(Workspace(id='web-http-workspace', name='Web HTTP workspace', tenant_id='web-http-tenant'))
        db.add(User(id='web-http-user', email=account['username'], hashed_password=get_password_hash(account['password']), first_name='Web', last_name='Journey', role='member', status='active', is_active=True, tenant_id='web-http-tenant', workspace_id='web-http-workspace', onboarding_completed=True, onboarding_step='completed'))
        db.commit()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:18130'], allow_credentials=True, allow_methods=['GET','POST','PUT','DELETE','OPTIONS'], allow_headers=['Authorization','Content-Type'])
app.include_router(auth_router); app.include_router(nav_router)
@app.get('/alive')
def alive(): return {'status': 'ok', 'scope': 'controlled-auth-task-project-http-fixture'}
if __name__ == '__main__': uvicorn.run(app, host='127.0.0.1', port=18131, access_log=False)
