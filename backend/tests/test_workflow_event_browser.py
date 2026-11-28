"""Opt-in browser acceptance: real Next editor/API/worker, seeded session and Graph wire.

Run only with ATOM_EVENT_BROWSER_ACCEPTANCE=1 and an explicitly provisioned
ATOM_WORLD_STORAGE_PATHS. No production account, credential or provider is used.
"""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.request import urlopen
import pytest
from core.models import User, Notification, WorkflowExecution
from tests.test_workflow_event_source_http import http_world, save_rule
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db

pytestmark = pytest.mark.skipif(os.getenv('ATOM_EVENT_BROWSER_ACCEPTANCE') != '1', reason='explicit isolated browser world required')


def test_real_editor_source_enrollment_save_reopen_and_event_effect(http_world, tmp_path, monkeypatch):
    import uvicorn
    from playwright.sync_api import sync_playwright
    from core.world_storage_guard import assert_worlds_root_usable
    from core.workflow_engine import WorkflowEngine
    from core.execution_state_manager import ExecutionStateManager
    from core.workflow_event_worker import process_pending_event_executions_once
    assert_worlds_root_usable(where='workflow event browser acceptance')
    client, factory, provider, principal, adapter = http_world
    save_rule(client)
    seeded = client.get('/api/v1/workflows/workflows/mail-rule').json()
    for index, node in enumerate(seeded['nodes']):
        node['position'] = {'x': index * 420, 'y': 100}
    arranged = client.put('/api/v1/workflows/workflows/mail-rule', json={
        'revision': seeded['revision'], 'reason': 'Arrange scratch browser fixture', 'nodes': seeded['nodes']})
    assert arranged.status_code == 200, arranged.text
    app = client.app
    from api.product_profile_routes import router as profile_router
    from core import product_profile
    app.include_router(profile_router)
    monkeypatch.setenv('ATOM_PRODUCT_PROFILE', 'core')
    monkeypatch.setattr(product_profile, '_PROFILE_CACHE', None)
    @app.get('/api/v1/external-integrations/')
    def no_external_bridge_pieces():
        # The native event adapter is under test, not the optional pieces bridge.
        return []
    @app.get('/api/auth/me')
    def synthetic_current_session():
        # Principal transport is controlled, as in the HTTP fixture. Read the
        # same authoritative scratch User row; no live login is claimed.
        with factory() as db:
            actor = db.get(User, 'owner')
            return {key: getattr(actor, key) for key in ('id', 'email', 'role', 'status',
                'tenant_id', 'workspace_id', 'first_name', 'last_name')}
    root = Path(__file__).resolve().parents[2]
    frontend = root / 'frontend-nextjs'
    assert not (frontend / '.next').is_symlink()
    backend_socket = socket.socket(); backend_socket.bind(('127.0.0.1', 0)); backend_socket.listen(128)
    backend_port = backend_socket.getsockname()[1]
    free = socket.socket(); free.bind(('127.0.0.1', 0)); frontend_port = free.getsockname()[1]; free.close()
    origin = f'http://127.0.0.1:{frontend_port}'
    backend = f'http://127.0.0.1:{backend_port}'
    from starlette.middleware.cors import CORSMiddleware
    served_app = CORSMiddleware(app, allow_origins=[origin], allow_credentials=True,
        allow_methods=['*'], allow_headers=['*'])
    server = uvicorn.Server(uvicorn.Config(served_app, log_level='warning', lifespan='off'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [backend_socket]}, daemon=True)
    thread.start()
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR') if k in os.environ}
    env.update(NODE_ENV='development', BACKEND_URL=backend, NEXT_PUBLIC_API_URL=backend,
        NEXT_PUBLIC_ALLOW_LOOPBACK='1', NEXTAUTH_URL=origin,
        NEXTAUTH_SECRET='synthetic-isolated-workflow-web-session', ATOM_PRODUCT_PROFILE='core',
        NEXT_PUBLIC_ATOM_PRODUCT_PROFILE='core', NEXT_TELEMETRY_DISABLED='1')
    log = (tmp_path / 'frontend.log').open('w')
    frontend_process = subprocess.Popen(['node', 'node_modules/next/dist/bin/next', 'dev', '--webpack', '-H', '127.0.0.1', '-p', str(frontend_port)],
        cwd=frontend, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    browser = None
    try:
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            assert frontend_process.poll() is None, 'isolated frontend exited'
            try:
                with urlopen(origin + '/api/health', timeout=3) as response:
                    if response.status == 200: break
            except Exception: time.sleep(0.5)
        else: pytest.fail('isolated frontend did not become healthy')
        # Use installed NextAuth's own encoder, with the isolated server key.
        encoded = subprocess.check_output(['node', '-e',
            "require('next-auth/jwt').encode({secret:process.env.NEXTAUTH_SECRET,token:{id:'owner',sub:'owner',backendToken:'synthetic-session'}}).then(v=>process.stdout.write(v))"],
            cwd=frontend, env=env, text=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': 'next-auth.session-token', 'value': encoded, 'url': origin, 'httpOnly': True}])
            context.add_init_script("localStorage.setItem('auth_token','synthetic-session')")
            page = context.new_page()
            page.goto(origin + '/automations', wait_until='domcontentloaded', timeout=90000)
            try:
                page.get_by_role('heading', name='Automations is not part of this release', exact=True).wait_for(timeout=30000)
            except Exception:
                page.screenshot(path=str(tmp_path / 'core-page-failure.png'))
                (tmp_path / 'core-page-failure.txt').write_text(page.locator('body').inner_text())
                raise
            page.screenshot(path=str(tmp_path / 'core-scope.png'))
            monkeypatch.setenv('ATOM_PRODUCT_PROFILE', 'full')
            monkeypatch.setattr(product_profile, '_PROFILE_CACHE', None)
            page.reload(wait_until='domcontentloaded')
            page.get_by_role('button', name='My Workflows', exact=True).click()
            try:
                page.get_by_text('Mail source rule', exact=True).wait_for(timeout=45000)
            except Exception:
                page.screenshot(path=str(tmp_path / 'page-failure.png'))
                (tmp_path / 'page-failure.txt').write_text(page.locator('body').inner_text())
                raise
            page.get_by_role('button', name='Edit workflow', exact=True).first.click()
            page.locator('.react-flow__node[data-id="source-trigger"]').click()
            page.get_by_label('Event connection', exact=True).wait_for(timeout=15000)
            page.get_by_label('Event connection', exact=True).select_option('connection')
            page.get_by_label('Event', exact=True).select_option('message.created')
            page.get_by_role('button', name='Connect event delivery', exact=True).click()
            page.get_by_text('Event delivery registered', exact=True).wait_for()
            page.get_by_role('region', name='Connected event source').evaluate(
                "async el => { const pane = el.closest('.animate-in'); if (pane) await Promise.all(pane.getAnimations().filter(a => a.effect.getTiming().iterations !== Infinity).map(a => a.finished)); }")
            page.screenshot(path=str(tmp_path / 'source-enrolled.png'))
            page.get_by_role('button', name='Save Step', exact=True).click()
            with page.expect_response(lambda r: r.request.method == 'PUT' and '/workflows/mail-rule' in r.url) as saved:
                page.get_by_role('button', name='Save', exact=True).click()
            assert saved.value.status == 200
            persisted = client.get('/api/v1/workflows/workflows/mail-rule').json()
            assert persisted['event_subscriptions'][0]['event_type'] == 'message.created'
            page.reload(wait_until='domcontentloaded')
            page.get_by_role('button', name='My Workflows', exact=True).click()
            page.get_by_text('Mail source rule', exact=True).wait_for(timeout=30000)
            page.get_by_role('button', name='Edit workflow', exact=True).first.click()
            page.locator('.react-flow__node[data-id="source-trigger"]').click()
            assert page.get_by_label('Event connection', exact=True).input_value() == 'connection'
            assert page.get_by_label('Event', exact=True).input_value() == 'message.created'
            page.get_by_text('Event delivery registered', exact=True).wait_for()
            page.get_by_role('region', name='Connected event source').evaluate(
                "async el => { const pane = el.closest('.animate-in'); if (pane) await Promise.all(pane.getAnimations().filter(a => a.effect.getTiming().iterations !== Infinity).map(a => a.finished)); }")
            page.screenshot(path=str(tmp_path / 'source-reopened.png'))
            panel = page.get_by_role('region', name='Connected event source').bounding_box()
            assert panel is not None and panel['x'] >= 0 and panel['x'] + panel['width'] <= 1441, panel
            browser.close(); browser = None
        from urllib.parse import urlsplit
        created = next(call[2] for call in provider['calls'] if call[0] == 'POST')
        callback = urlsplit(created['notificationUrl'])
        event = {'subscriptionId': 'provider-subscription', 'clientState': created['clientState'],
            'changeType': 'created', 'resourceData': {'id': 'message-one'}}
        assert client.post(callback.path + '?' + callback.query, json={'value': [event]}).status_code == 200
        async def drain():
            engine = WorkflowEngine(); engine.state_manager = ExecutionStateManager()
            assert await process_pending_event_executions_once(engine=engine) == 1
            await asyncio.gather(*list(engine._background_tasks))
        asyncio.run(drain())
        with factory() as db:
            notification = db.query(Notification).one()
            assert notification.user_id == 'owner' and notification.message == 'invoice'
            assert db.query(WorkflowExecution).one().status == 'COMPLETED'
        assert sum(call[0] == 'POST' for call in provider['calls']) == 1
        (tmp_path / 'browser-result.json').write_text(json.dumps({'source': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'browser_save_reopen': True, 'provider_creates': 1, 'notifications': 1,
            'settled_panel_bounds': panel, 'viewport_width': 1440, 'core_refused': True, 'editor_profile': 'full',
            'principal_transport': 'seeded scratch session', 'provider_transport': 'controlled Graph wire'}))
    finally:
        import signal
        if frontend_process.poll() is None:
            os.killpg(frontend_process.pid, signal.SIGTERM)
            try: frontend_process.wait(timeout=15)
            except subprocess.TimeoutExpired: os.killpg(frontend_process.pid, signal.SIGKILL); frontend_process.wait(timeout=5)
        log.close()
        server.should_exit = True; thread.join(timeout=10); backend_socket.close()
