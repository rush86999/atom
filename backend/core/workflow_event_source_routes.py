"""Authenticated setup and provider callbacks for registered workflow sources."""
import os
from typing import Optional
from urllib.parse import quote, urlsplit
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict
from core.models import User, UserConnection, TenantSetting
from core.rbac_service import Permission, RBACService
from core.security_dependencies import require_permission
from core.connection_service import ConnectionService
from core import workflow_event_source_registration as registrations
from core.workflow_event_source_adapters import source_adapter, source_event_catalog
from core.workflow_event_source_enrollment import enroll_source, source_credentials
from core.workflow_event_intake import admit_verified_source_event
from core.workflow_event_admission import EventPayloadConflict, EventScopeConflict
from core.workflow_event_worker import _actor_is_active

router = APIRouter(prefix='/event-sources', tags=['Workflow event sources'])


def _database_factory():
    from core.database import get_db_session
    return get_db_session


def _public_base():
    value = (os.getenv('ATOM_PUBLIC_WEBHOOK_BASE_URL') or os.getenv('ATOM_GRAPH_WEBHOOK_BASE_URL') or '').rstrip('/')
    try:
        url = urlsplit(value)
    except ValueError:
        raise HTTPException(503, detail={'code': 'SOURCE_CALLBACK_NOT_CONFIGURED',
            'verification': {'effect': 'none', 'status': 'unavailable'}}) from None
    if url.scheme != 'https' or not url.netloc or url.username or url.password or url.query or url.fragment:
        raise HTTPException(503, detail={'code': 'SOURCE_CALLBACK_NOT_CONFIGURED',
            'verification': {'effect': 'none', 'status': 'unavailable'}})
    return value


def _managed_actor(db, user):
    actor = db.query(User).filter(User.id == str(user.id)).first()
    if (actor is None or not _actor_is_active(actor)
            or not RBACService.check_permission(actor, Permission.WORKFLOW_MANAGE)):
        raise HTTPException(403, detail={'code': 'SOURCE_OWNER_UNAVAILABLE'})
    return actor


def _source_error(exc):
    code = exc.code
    status = 403 if code in ('SOURCE_OWNER_UNAVAILABLE', 'SOURCE_AUTHORITY_CHANGED') else (
        404 if code == 'SOURCE_CONNECTION_UNAVAILABLE' else 503)
    return HTTPException(status, detail={'code': code})


class EnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')


@router.get('')
async def available_sources(user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE))):
    from core.workflow_endpoints import _caller_scope
    factory, catalog = _database_factory(), source_event_catalog()
    try:
        configured = bool(_public_base())
    except HTTPException:
        configured = False
    with factory() as db:
        actor = _managed_actor(db, user)
        identity = _caller_scope(actor)
        rows = db.query(UserConnection.id, UserConnection.connection_name,
                        UserConnection.integration_id).filter(
            UserConnection.user_id == str(actor.id), UserConnection.tenant_id == actor.tenant_id,
            UserConnection.workspace_id == actor.workspace_id, UserConnection.status == 'active').all()
        result = []
        for row in rows:
            if row.integration_id not in catalog:
                continue
            registration = None
            setting = db.query(TenantSetting).filter(TenantSetting.tenant_id == identity['tenant_id'],
                TenantSetting.setting_key == registrations._key(row.id, row.integration_id)).first()
            if setting is not None:
                try:
                    raw = registrations._read_document(setting)
                    verified = registrations.read_delivery_registration(row.id, raw['operation_id'], db_factory=factory)
                    registration = registrations.public_registration(verified)
                except Exception:
                    registration = {'phase': 'unverified', 'enabled': False}
            result.append({'connection_id': row.id, 'name': row.connection_name, 'source': row.integration_id,
                           'events': catalog[row.integration_id], 'registration': registration})
    return {'callback_configured': configured, 'sources': result}


@router.post('/{connection_id}/enroll')
async def enroll_event_source(connection_id: str, body: Optional[EnrollmentRequest] = Body(None),
        user: User = Depends(require_permission(Permission.WORKFLOW_MANAGE))):
    factory = _database_factory()
    base = _public_base()
    with factory() as db:
        actor = _managed_actor(db, user)
        row = db.query(UserConnection.integration_id).filter(UserConnection.id == connection_id,
            UserConnection.user_id == str(actor.id), UserConnection.tenant_id == actor.tenant_id,
            UserConnection.workspace_id == actor.workspace_id, UserConnection.status == 'active').first()
        if row is None:
            raise HTTPException(404, detail={'code': 'SOURCE_CONNECTION_UNAVAILABLE'})
        source = row.integration_id
    try:
        adapter = source_adapter(source)
    except ValueError:
        raise HTTPException(400, detail={'code': 'SOURCE_NOT_SUPPORTED'}) from None
    callback = base + '/api/v1/workflows/event-sources/' + quote(connection_id, safe='') + '/notifications'
    try:
        result = await enroll_source(actor_id=str(user.id), connection_id=connection_id,
            callback_base_url=callback, adapter=adapter, db_factory=factory)
    except registrations.SourceRegistrationError as exc:
        raise _source_error(exc) from None
    code = 200 if result['status'] in ('registered', 'already_applied') else (
        409 if result['status'] in ('not_applied', 'refused', 'operation_conflict') else 503)
    return JSONResponse(result, status_code=code)


@router.post('/{connection_id}/notifications')
async def receive_source_notification(connection_id: str, request: Request,
        registration: Optional[str] = Query(None), validation_token: Optional[str] = Query(None, alias='validationToken')):
    factory = _database_factory()
    try:
        document = registrations.read_delivery_registration(connection_id, registration, db_factory=factory)
    except registrations.SourceRegistrationError as exc:
        raise _source_error(exc) from None
    if validation_token is not None:
        return PlainTextResponse(validation_token)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, detail={'code': 'INVALID_SOURCE_NOTIFICATION'}) from None
    if not isinstance(payload, dict) or not isinstance(payload.get('value'), list):
        raise HTTPException(400, detail={'code': 'INVALID_SOURCE_NOTIFICATION'})
    adapter = source_adapter(document['source'])
    admitted = duplicates = ignored = 0
    lifecycle_received = lifecycle_duplicates = 0
    for item in payload['value']:
        if not isinstance(item, dict):
            raise HTTPException(400, detail={'code': 'INVALID_SOURCE_NOTIFICATION'})
        state = item.get('clientState')
        if not registrations.receiver_state_matches(document, state):
            raise HTTPException(401, detail={'code': 'SOURCE_NOTIFICATION_REFUTED'})
        subscription_id = item.get('subscriptionId')
        if not isinstance(subscription_id, str) or not subscription_id:
            raise HTTPException(400, detail={'code': 'INVALID_SOURCE_NOTIFICATION'})
        if document.get('phase') != 'registered':
            try:
                recovered = await enroll_source(actor_id=document['identity']['user_id'], connection_id=connection_id,
                    callback_base_url=document['callback_base_url'], adapter=adapter, db_factory=factory,
                    observed_subscription_id=subscription_id)
                if recovered['status'] not in ('registered', 'already_applied'):
                    raise ValueError('enrollment is not verified')
                document = registrations.read_delivery_registration(connection_id, registration, db_factory=factory)
            except Exception:
                raise HTTPException(503, detail={'code': 'SOURCE_ENROLLMENT_UNVERIFIED', 'do_not_repeat': True}) from None
        if subscription_id != document.get('provider_subscription_id'):
            raise HTTPException(401, detail={'code': 'SOURCE_NOTIFICATION_REFUTED'})
        if 'lifecycleEvent' in item:
            from core.workflow_event_source_lifecycle import record_source_lifecycle
            try:
                document, received = await record_source_lifecycle(document, item, adapter, factory)
            except registrations.SourceRegistrationError as exc:
                raise _source_error(exc) from None
            lifecycle_received += int(received)
            lifecycle_duplicates += int(not received)
            continue
        if item.get('changeType') != 'created':
            ignored += 1
            continue
        if not isinstance(item.get('resourceData'), dict):
            raise HTTPException(400, detail={'code': 'INVALID_SOURCE_NOTIFICATION'})
        identity = document['identity']
        private = await source_credentials(document, adapter, factory)
        if not isinstance(private, dict) or not private.get('access_token'):
            raise HTTPException(503, detail={'code': 'SOURCE_CREDENTIALS_UNAVAILABLE'})
        try:
            from core.workflow_event_source_binding import snapshot, claim
            with factory() as db:
                grant_snapshot = snapshot(db, identity['user_id'], connection_id, document['source'],
                                          expected_credentials=private, require_manage=False)
            def source_guard(db):
                claim(db, grant_snapshot)
                registrations.claim_delivery_registration(db, document)
            receipt = {'subscription_id': subscription_id}
            observed = await adapter.read(subscription_id, private)
            from core.workflow_event_source_enrollment import verify_source_subscription
            if verify_source_subscription(adapter, document, receipt, observed, factory) is not True:
                raise ValueError('provider subscription is unverified')
            event = await adapter.message_event(item, private, document=document)
            with factory() as db:
                results = await admit_verified_source_event(db, connection_id=connection_id,
                    source=document['source'], expected_identity=identity, source_guard=source_guard, **event)
        except (EventPayloadConflict, EventScopeConflict):
            raise HTTPException(409, detail={'code': 'SOURCE_EVENT_REFUTED', 'do_not_repeat': True}) from None
        except Exception:
            # A failed content read/commit is not an accepted delivery. Let the
            # provider retry; earlier receipts in the batch reconcile normally.
            raise HTTPException(503, detail={'code': 'SOURCE_EVENT_UNAVAILABLE'}) from None
        admitted += sum(row['status'] == 'admitted' for row in results)
        duplicates += sum(row['status'] == 'already_applied' for row in results)
    result = {'status': 'accepted', 'admitted': admitted, 'duplicates': duplicates, 'ignored': ignored}
    if lifecycle_received or lifecycle_duplicates:
        result.update(lifecycle_received=lifecycle_received, lifecycle_duplicates=lifecycle_duplicates)
        return JSONResponse(result, status_code=202)
    return result
