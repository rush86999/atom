"""Public authenticated lifecycle -> durable receipt -> existing maintenance worker."""
import asyncio
from datetime import datetime, timedelta
import pytest
from core import workflow_event_source_registration as registry
from core import workflow_event_source_renewal as renewal
from core import workflow_event_source_lifecycle as lifecycle
from core import workflow_event_worker as worker
from core.models import AuditLog, User, WorkflowExecution, Notification
from tests.test_workflow_event_source_http import http_world, setup_source, save_rule
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db
from tests.test_workflow_event_source_renewal import document, count


def advance(monkeypatch, original, minutes=10):
    at = datetime.fromisoformat(original['prepared_at']) + timedelta(minutes=minutes)
    class ClockMeta(type):
        def __instancecheck__(cls, value): return isinstance(value, datetime)
    class Clock(datetime, metaclass=ClockMeta):
        @classmethod
        def now(cls, tz=None): return at.astimezone(tz) if tz else at.replace(tzinfo=None)
    monkeypatch.setattr('core.workflow_event_source_adapters.datetime', Clock)
    monkeypatch.setattr(renewal, 'datetime', Clock)
    return at


def report(provider, content_item, event='reauthorizationRequired'):
    return {'subscriptionId': content_item['subscriptionId'], 'clientState': content_item['clientState'],
            'subscriptionExpirationDateTime': provider['record']['expirationDateTime'],
            'lifecycleEvent': event, 'tenantId': 'not-atom-authority'}


def maintain(factory, adapter):
    return asyncio.run(worker.maintain_source_leases_once(db_factory=factory,
        adapter_factory=lambda source: adapter))


def test_public_challenge_reauthorizes_once_then_content_reaches_real_worker(http_world, monkeypatch):
    client, factory, provider, principal, adapter = http_world
    setup, callback, content = setup_source(client, provider)
    native = next(c[2] for c in provider['calls'] if c[0] == 'POST')
    assert native['lifecycleNotificationUrl'] == native['notificationUrl']
    original = document(factory)
    advance(monkeypatch, original)
    save_rule(client)
    principal['signed_in'] = False
    item = report(provider, content)
    before_intake = len(provider['calls'])
    first = client.post(callback, json={'value': [item]})
    assert len(provider['calls']) == before_intake
    assert first.status_code == 202 and first.json()['lifecycle_received'] == 1, first.text
    assert content['clientState'] not in first.text
    assert client.post(callback, json={'value': [item]}).json()['lifecycle_duplicates'] == 1
    assert count(provider, 'PATCH') == 0
    assert maintain(factory, adapter)['attempted'] == 1
    current = document(factory)
    assert 'reauthorizationRequired' not in current['lifecycle_requests']
    assert len(current['lifecycle_history']) == 1
    for key, value in original.items(): assert current[key] == value
    assert client.post(callback, json={'value': [item]}).json()['lifecycle_duplicates'] == 1
    maintain(factory, adapter)
    assert count(provider, 'PATCH') == count(provider, 'POST') == 1
    delivered = client.post(callback, json={'value': [content]})
    assert delivered.status_code == 200 and delivered.json()['admitted'] == 1, delivered.text
    async def drain():
        from core.workflow_engine import WorkflowEngine
        from core.execution_state_manager import ExecutionStateManager
        engine = WorkflowEngine(); engine.state_manager = ExecutionStateManager()
        assert await worker.process_pending_event_executions_once(engine=engine) == 1
        await asyncio.gather(*list(engine._background_tasks))
    asyncio.run(asyncio.wait_for(drain(), timeout=30))
    with factory() as db:
        assert db.query(WorkflowExecution).one().status == 'COMPLETED'
        result = db.query(Notification).one()
        assert (result.user_id, result.tenant_id, result.workspace_id) == ('owner', 'tenant', 'workspace')
        assert db.query(AuditLog).filter(AuditLog.event_type.like('workflow_event_source%')).count() == 5


@pytest.mark.parametrize('bad', ['state', 'subscription', 'expiry', 'event'])
def test_unverified_lifecycle_cannot_queue_or_dispatch(http_world, bad):
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    item = report(provider, content)
    if bad == 'state': item['clientState'] = 'wrong'
    elif bad == 'subscription': item['subscriptionId'] = 'foreign'
    elif bad == 'expiry': item['subscriptionExpirationDateTime'] = '2099-01-01T00:00:00Z'
    else: item['lifecycleEvent'] = 'invented'
    result = client.post(callback, json={'value': [item]})
    assert result.status_code in (401, 503), result.text
    assert 'lifecycle_requests' not in document(factory)
    assert count(provider, 'PATCH') == 0


def test_legacy_registration_does_not_gain_lifecycle_by_replay(http_world, monkeypatch):
    client, factory, provider, _, adapter = http_world
    monkeypatch.setattr(adapter, 'lifecycle_events', (), raising=False)
    _, callback, content = setup_source(client, provider)
    native = next(c[2] for c in provider['calls'] if c[0] == 'POST')
    assert 'lifecycleNotificationUrl' not in native
    monkeypatch.setattr(adapter, 'lifecycle_events', lifecycle._EVENTS)
    from core.workflow_event_source_enrollment import enroll_source
    repeated = asyncio.run(enroll_source(actor_id='owner', connection_id='connection',
        callback_base_url=document(factory)['callback_base_url'], adapter=adapter, db_factory=factory))
    assert repeated['status'] == 'already_applied'
    assert 'lifecycle_events' not in document(factory)
    assert client.post(callback, json={'value': [report(provider, content)]}).status_code == 503
    assert count(provider, 'POST') == 1


def test_audit_failure_is_unavailable_without_false_ack_or_secret_leak(http_world, monkeypatch, caplog):
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    def fail(*a, **kw): raise RuntimeError('synthetic-private-error')
    monkeypatch.setattr(lifecycle, '_write', fail)
    result = client.post(callback, json={'value': [report(provider, content)]})
    assert result.status_code == 503
    assert 'synthetic-private-error' not in result.text + caplog.text
    assert 'lifecycle_requests' not in document(factory)
    with factory() as db: assert db.query(AuditLog).count() == 2


def test_lost_local_confirmation_reconciles_duplicate_without_second_receipt(http_world, monkeypatch):
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    original = registry.read_delivery_registration
    def unavailable_after_commit(*a, **kw):
        value = original(*a, **kw)
        if value.get('lifecycle_requests'): raise registry.SourceRegistrationError('SYNTHETIC_UNAVAILABLE')
        return value
    monkeypatch.setattr(registry, 'read_delivery_registration', unavailable_after_commit)
    item = report(provider, content)
    assert client.post(callback, json={'value': [item]}).status_code == 503
    monkeypatch.setattr(registry, 'read_delivery_registration', original)
    replay = client.post(callback, json={'value': [item]})
    assert replay.status_code == 202 and replay.json()['lifecycle_duplicates'] == 1
    with factory() as db: assert db.query(AuditLog).count() == 3


@pytest.mark.parametrize('event', ['missed', 'subscriptionRemoved'])
def test_missed_or_removed_report_is_pending_not_claimed_recovered(http_world, event):
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    item = report(provider, content, event)
    if event == 'subscriptionRemoved': provider['record'] = None
    result = client.post(callback, json={'value': [item]})
    assert result.status_code == 202, result.text
    maintain(factory, adapter)
    assert event in document(factory)['lifecycle_requests']
    assert count(provider, 'PATCH') == 0 and count(provider, 'POST') == 1


def test_unknown_reauthorization_recovers_by_get_without_repeat(http_world, monkeypatch):
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    advance(monkeypatch, document(factory))
    assert client.post(callback, json={'value': [report(provider, content)]}).status_code == 202
    provider['mode'] = 'timeout'
    maintain(factory, adapter)
    pending = document(factory)
    assert 'pending_lease' in pending and 'reauthorizationRequired' in pending['lifecycle_requests']
    provider['mode'] = 'normal'
    maintain(factory, adapter)
    assert 'pending_lease' not in document(factory)
    assert 'reauthorizationRequired' not in document(factory)['lifecycle_requests']
    assert count(provider, 'PATCH') == 1


def test_challenge_during_prepared_normal_lease_uses_same_patch(http_world, monkeypatch):
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    original = document(factory)
    at = advance(monkeypatch, original, minutes=60 * 60)
    renewal._prepare(original, adapter, at, factory)
    assert client.post(callback, json={'value': [report(provider, content)]}).status_code == 202
    maintain(factory, adapter)
    assert 'reauthorizationRequired' not in document(factory)['lifecycle_requests']
    maintain(factory, adapter)
    assert count(provider, 'PATCH') == 1


def test_owner_revoked_before_claim_cannot_persist_challenge(http_world, monkeypatch):
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    original = registry._claim
    def changed(db, actor, connection):
        with factory() as peer:
            peer.get(User, 'owner').is_active = False; peer.commit()
        return original(db, actor, connection)
    monkeypatch.setattr(registry, '_claim', changed)
    result = client.post(callback, json={'value': [report(provider, content)]})
    assert result.status_code == 403
    assert 'lifecycle_requests' not in document(factory)
    assert count(provider, 'PATCH') == 0


def test_queued_challenge_waits_for_credentials_then_resumes(http_world, monkeypatch):
    from core.models import UserConnection
    from core.connection_service import ConnectionService
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    advance(monkeypatch, document(factory))
    with factory() as db:
        db.get(UserConnection, 'connection').credentials = None; db.commit()
    before = len(provider['calls'])
    accepted = client.post(callback, json={'value': [report(provider, content)]})
    assert accepted.status_code == 202 and len(provider['calls']) == before
    maintain(factory, adapter)
    assert 'reauthorizationRequired' in document(factory)['lifecycle_requests']
    assert 'pending_lease' not in document(factory)
    assert count(provider, 'PATCH') == 0
    with factory() as db:
        db.get(UserConnection, 'connection').credentials = ConnectionService()._encrypt({'access_token': 'synthetic'})
        db.commit()
    maintain(factory, adapter)
    assert 'reauthorizationRequired' not in document(factory)['lifecycle_requests']
    assert count(provider, 'PATCH') == 1


@pytest.mark.parametrize('state', [None, True, 'wrong'])
def test_lifecycle_service_itself_requires_receiver_proof(http_world, state):
    client, factory, provider, _, adapter = http_world
    _, _, content = setup_source(client, provider)
    item = report(provider, content); item['clientState'] = state
    with pytest.raises(registry.SourceRegistrationError, match='SOURCE_LIFECYCLE_REFUTED'):
        asyncio.run(lifecycle.record_source_lifecycle(document(factory), item, adapter, factory))
    assert 'lifecycle_requests' not in document(factory)
    assert count(provider, 'PATCH') == 0


def test_same_expiry_reauthorization_waits_for_distinguishable_lease(http_world, monkeypatch):
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    original = document(factory)
    advance(monkeypatch, original, minutes=0)
    assert client.post(callback, json={'value': [report(provider, content)]}).status_code == 202
    maintain(factory, adapter)
    assert 'pending_lease' not in document(factory)
    assert 'reauthorizationRequired' in document(factory)['lifecycle_requests']
    assert count(provider, 'PATCH') == 0
    advance(monkeypatch, original, minutes=1)
    maintain(factory, adapter)
    assert count(provider, 'PATCH') == 1
    assert 'reauthorizationRequired' not in document(factory)['lifecycle_requests']


def test_equivalent_stored_json_format_is_not_false_stale(http_world):
    import json
    from core.models import TenantSetting
    client, factory, provider, _, adapter = http_world
    _, callback, content = setup_source(client, provider)
    with factory() as db:
        row = db.query(TenantSetting).one()
        row.setting_value = json.dumps(json.loads(row.setting_value), indent=2)
        db.commit()
    result = client.post(callback, json={'value': [report(provider, content)]})
    assert result.status_code == 202, result.text
    assert 'reauthorizationRequired' in document(factory)['lifecycle_requests']
