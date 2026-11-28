"""Private source-registration state in existing settings and audit storage.

Preparing a registration performs no provider call. Subsequent enrollment must
use the existing outbound operation arbiter; it is not implemented here. This
record preserves the same operation and encrypted receiver state across
restarts and retries.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from core.models import User, UserConnection, TenantSetting, AuditLog
from core.connection_service import ConnectionService
from core.workflow_event_worker import _actor_is_active, _actor_has_run_permission


class SourceRegistrationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def receiver_state_matches(document, value):
    expected = document.get('receiver_state_digest')
    return (isinstance(value, str) and isinstance(expected, str)
            and hmac.compare_digest(hashlib.sha256(value.encode()).hexdigest(), expected))


def _key(connection_id, source):
    return 'workflow_event_source:' + _digest([connection_id, source])


def _authority(db, actor_id, connection_id, source):
    from core.workflow_endpoints import _caller_scope
    from core.rbac_service import Permission, RBACService
    actor = db.query(User).filter(User.id == actor_id).first()
    if (actor is None or not _actor_is_active(actor) or not _actor_has_run_permission(actor)
            or not RBACService.check_permission(actor, Permission.WORKFLOW_MANAGE)):
        raise SourceRegistrationError('SOURCE_OWNER_UNAVAILABLE')
    raw = {field: getattr(actor, field) for field in
           ('id', 'role', 'status', 'is_active', 'tenant_id', 'workspace_id')}
    connection = ConnectionService.get_scoped_connection_metadata(
        db, user_id=str(actor.id), tenant_id=actor.tenant_id, workspace_id=actor.workspace_id,
        connection_id=connection_id, integration_id=source)
    if connection is None:
        raise SourceRegistrationError('SOURCE_CONNECTION_UNAVAILABLE')
    return raw, _caller_scope(actor), connection


def _claim(db, actor, connection):
    principal = db.execute(update(User).where(*(
        getattr(User, k) == v for k, v in actor.items()
    )).values(status=User.status, updated_at=User.updated_at).execution_options(synchronize_session=False))
    target = db.execute(update(UserConnection).where(*(
        getattr(UserConnection, k) == v for k, v in connection.items()
    )).values(status=UserConnection.status, updated_at=UserConnection.updated_at).execution_options(synchronize_session=False))
    if principal.rowcount != 1 or target.rowcount != 1:
        raise SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')



def _claim_registration_authority(db, actor, identity, connection, credential_snapshot=None):
    if credential_snapshot is None:
        return _claim(db, actor, connection)
    from core.workflow_event_source_binding import claim
    if (credential_snapshot['actor'] != actor or credential_snapshot['identity'] != identity
            or credential_snapshot['connection'] != connection):
        raise SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
    claim(db, credential_snapshot)

def _read_document(row):
    try:
        value = json.loads(row.setting_value)
        if not isinstance(value, dict) or value.get('schema') != 'workflow.event_source.v1':
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise SourceRegistrationError('SOURCE_REGISTRATION_UNREADABLE') from None


def _verified_replay(db, row, request_digest, identity, connection_id, source):
    document = _read_document(row)
    if document.get('request_digest') != request_digest:
        raise SourceRegistrationError('SOURCE_REGISTRATION_CONFLICT')
    expected = dict(operation_id=document.get('operation_id'), source=source,
                    request_digest=request_digest, result_digest=_digest(document))
    matches = 0
    for audit in db.query(AuditLog).filter(
            AuditLog.event_type.in_(['workflow_event_source_prepared', 'workflow_event_source_activated',
                'workflow_event_source_renewal_prepared', 'workflow_event_source_renewed',
                'workflow_event_source_lifecycle_received']),
            AuditLog.user_id == identity['user_id'], AuditLog.tenant_id == identity['tenant_id'],
            AuditLog.workspace_id == identity['workspace_id'], AuditLog.resource == connection_id,
            AuditLog.success.is_(True)).all():
        try:
            expected_action = {
                'workflow_event_source_prepared': 'prepare_workflow_event_source',
                'workflow_event_source_activated': 'activate_workflow_event_source',
                'workflow_event_source_renewal_prepared': 'prepare_workflow_event_source_renewal',
                'workflow_event_source_renewed': 'renew_workflow_event_source',
                'workflow_event_source_lifecycle_received': 'record_workflow_event_source_lifecycle',
            }[audit.event_type]
            if audit.action != expected_action:
                continue
            if json.loads(audit.metadata_json) == expected:
                matches += 1
        except (ValueError, TypeError):
            continue
    if matches != 1:
        raise SourceRegistrationError('SOURCE_REGISTRATION_UNVERIFIED')
    if document.get('current_lease') is not None:
        from core.workflow_event_source_renewal import verify_current_lease
        verify_current_lease(db, document)
    # Bind the actual document observed before returning a verified replay.
    result = db.execute(update(TenantSetting).where(
        TenantSetting.id == row.id, TenantSetting.tenant_id == identity['tenant_id'],
        TenantSetting.setting_key == row.setting_key,
        TenantSetting.setting_value == row.setting_value,
    ).values(setting_value=TenantSetting.setting_value, updated_at=TenantSetting.updated_at).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
    return document


def prepare_source_registration(*, actor_id, connection_id, source, event_types,
                                callback_base_url, db_factory=None, lifecycle_events=None,
                                probe_only=False, provider_binding=None, credential_snapshot=None):
    """Prepare once; changed enrollment material requires explicit correction.

    The caller supplies a server-generated callback URL and adapter-owned event
    types, not arbitrary client destinations. No caller transaction is committed.
    """
    if any(not isinstance(v, str) or not v.strip() for v in
           (actor_id, connection_id, source, callback_base_url)):
        raise SourceRegistrationError('INVALID_SOURCE_REGISTRATION')
    if (not isinstance(event_types, list) or not event_types
            or any(not isinstance(v, str) or not v.strip() for v in event_types)
            or len(set(event_types)) != len(event_types)):
        raise SourceRegistrationError('INVALID_SOURCE_EVENTS')
    if lifecycle_events is not None and (not isinstance(lifecycle_events, list)
            or any(not isinstance(v, str) or not v.strip() for v in lifecycle_events)
            or len(set(lifecycle_events)) != len(lifecycle_events)):
        raise SourceRegistrationError('INVALID_SOURCE_LIFECYCLE_EVENTS')
    if type(probe_only) is not bool:
        raise SourceRegistrationError('INVALID_SOURCE_REGISTRATION')
    if provider_binding is not None and (not isinstance(provider_binding, dict) or not provider_binding
            or credential_snapshot is None):
        raise SourceRegistrationError('INVALID_SOURCE_PROVIDER_BINDING')
    url = urlsplit(callback_base_url)
    if url.scheme != 'https' or not url.netloc or url.username or url.password or url.fragment:
        raise SourceRegistrationError('INVALID_SOURCE_CALLBACK')
    if any(k == 'registration' for k, v in parse_qsl(url.query)):
        raise SourceRegistrationError('INVALID_SOURCE_CALLBACK')
    if db_factory is None:
        from core.database import get_db_session
        db_factory = get_db_session
    key = _key(connection_id, source)
    with db_factory() as db:
        try:
            actor, identity, connection = _authority(db, actor_id, connection_id, source)
            material = dict(identity=identity, raw_actor=actor, connection=connection,
                            event_types=sorted(event_types), callback_base_url=callback_base_url)
            request_digest = _digest(material)
            row = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == identity['tenant_id'], TenantSetting.setting_key == key).first()
            if row is not None:
                _claim_registration_authority(db, actor, identity, connection, credential_snapshot)
                document = _verified_replay(db, row, request_digest, identity, connection_id, source)
                db.commit()
                return document
            if probe_only:
                return None
            _claim_registration_authority(db, actor, identity, connection, credential_snapshot)
            operation_id = str(uuid.uuid4())
            receiver_state = secrets.token_urlsafe(32)
            encrypted_state = ConnectionService()._encrypt({'client_state': receiver_state})
            if not isinstance(encrypted_state, str) or not encrypted_state:
                raise SourceRegistrationError('SOURCE_STATE_UNAVAILABLE')
            query = parse_qsl(url.query) + [('registration', operation_id)]
            callback_url = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), ''))
            document = dict(schema='workflow.event_source.v1', phase='prepared', enabled=False,
                            prepared_at=datetime.now(timezone.utc).isoformat(),
                            operation_id=operation_id, source=source, connection_id=connection_id,
                            identity=identity, request_digest=request_digest,
                            event_types=sorted(event_types), callback_url=callback_url,
                            callback_base_url=callback_base_url,
                            receiver_state_ciphertext=encrypted_state,
                            receiver_state_digest=hashlib.sha256(receiver_state.encode()).hexdigest())
            if lifecycle_events:
                document['lifecycle_events'] = sorted(lifecycle_events)
            if provider_binding is not None:
                document['provider_binding'] = json.loads(_json(provider_binding))
            db.add(TenantSetting(tenant_id=identity['tenant_id'], setting_key=key,
                                 setting_value=_json(document)))
            db.add(AuditLog(event_type='workflow_event_source_prepared', security_level='INFO',
                threat_level='NONE', user_id=actor_id, tenant_id=identity['tenant_id'],
                workspace_id=identity['workspace_id'], resource=connection_id,
                action='prepare_workflow_event_source', description='Workflow event source prepared',
                success=True, metadata_json=_json({'operation_id': operation_id,
                    'source': source, 'request_digest': request_digest,
                    'result_digest': _digest(document)})))
            db.commit()
            return document
        except IntegrityError:
            db.rollback()
            # A concurrent initializer may have won the unique settings key.
            # Retry in a fresh session; never overwrite its state or identity.
        except SourceRegistrationError:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise SourceRegistrationError('SOURCE_REGISTRATION_UNAVAILABLE') from exc
    with db_factory() as db:
        actor, identity, connection = _authority(db, actor_id, connection_id, source)
        current_digest = _digest(dict(identity=identity, raw_actor=actor, connection=connection,
            event_types=sorted(event_types), callback_base_url=callback_base_url))
        row = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == identity['tenant_id'], TenantSetting.setting_key == key).first()
        if row is not None:
            if current_digest == request_digest:
                _claim_registration_authority(db, actor, identity, connection, credential_snapshot)
                document = _verified_replay(db, row, request_digest, identity, connection_id, source)
                db.commit()
                return document
    raise SourceRegistrationError('SOURCE_REGISTRATION_CONFLICT')


def public_registration(document):
    """No receiver secret, commitment, raw authority, or operation digest leaves the service."""
    return {key: document.get(key) for key in (
        'operation_id', 'source', 'connection_id', 'event_types', 'phase', 'enabled')}


def activate_source_registration(document, receipt, *, db_factory=None, credential_snapshot=None):
    """CAS the observed registration and its activation audit in one transaction."""
    if db_factory is None:
        from core.database import get_db_session
        db_factory = get_db_session
    identity = document['identity']
    with db_factory() as db:
        try:
            actor, current_identity, connection = _authority(
                db, identity['user_id'], document['connection_id'], document['source'])
            if current_identity != identity:
                raise SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
            _claim_registration_authority(db, actor, current_identity, connection, credential_snapshot)
            row = db.query(TenantSetting).filter(
                TenantSetting.tenant_id == identity['tenant_id'],
                TenantSetting.setting_key == _key(document['connection_id'], document['source'])).first()
            if row is None:
                raise SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
            current = _verified_replay(db, row, document['request_digest'], identity,
                                       document['connection_id'], document['source'])
            if current != document:
                raise SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
            if document.get('phase') == 'registered':
                if document.get('provider_subscription_id') != receipt['subscription_id']:
                    raise SourceRegistrationError('SOURCE_REGISTRATION_CONFLICT')
                db.commit()
                return current
            activated = dict(document, phase='registered', enabled=True,
                             provider_subscription_id=receipt['subscription_id'],
                             provider_receipt_digest=_digest(receipt))
            changed = db.execute(update(TenantSetting).where(
                TenantSetting.id == row.id, TenantSetting.setting_value == row.setting_value,
            ).values(setting_value=_json(activated)).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                raise SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
            db.add(AuditLog(event_type='workflow_event_source_activated', security_level='INFO',
                threat_level='NONE', user_id=identity['user_id'], tenant_id=identity['tenant_id'],
                workspace_id=identity['workspace_id'], resource=document['connection_id'],
                action='activate_workflow_event_source', description='Workflow event source activated',
                success=True, metadata_json=_json({'operation_id': document['operation_id'],
                    'source': document['source'], 'request_digest': document['request_digest'],
                    'result_digest': _digest(activated)})))
            db.commit()
            return activated
        except SourceRegistrationError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise SourceRegistrationError('SOURCE_ACTIVATION_UNAVAILABLE') from None


def read_delivery_registration(connection_id, registration_id, *, db_factory=None):
    """Resolve current source owner from server rows; expose private state only internally."""
    from core import outbound_operation_claim as operations
    from core.workflow_endpoints import _caller_scope
    from core.workflow_event_worker import _load_current_actor
    if db_factory is None:
        from core.database import get_db_session
        db_factory = get_db_session
    with db_factory() as db:
        row = db.query(UserConnection.id, UserConnection.user_id,
                       UserConnection.integration_id).filter(
            UserConnection.id == connection_id, UserConnection.status == 'active').first()
        if row is None:
            raise SourceRegistrationError('SOURCE_CONNECTION_UNAVAILABLE')
        actor = _load_current_actor(db, row.user_id)
        if actor is None or not _actor_is_active(actor) or not _actor_has_run_permission(actor):
            raise SourceRegistrationError('SOURCE_OWNER_UNAVAILABLE')
        identity = _caller_scope(actor)
        if ConnectionService.get_scoped_connection_metadata(db, user_id=str(actor.id),
                tenant_id=actor.tenant_id, workspace_id=actor.workspace_id,
                connection_id=connection_id, integration_id=row.integration_id) is None:
            raise SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
        setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == identity['tenant_id'],
            TenantSetting.setting_key == _key(connection_id, row.integration_id)).first()
        if setting is None:
            raise SourceRegistrationError('SOURCE_REGISTRATION_UNAVAILABLE')
        document = _read_document(setting)
        if (document.get('operation_id') != registration_id or document.get('identity') != identity
                or document.get('source') != row.integration_id or document.get('connection_id') != connection_id):
            raise SourceRegistrationError('SOURCE_REGISTRATION_UNAVAILABLE')
        document = _verified_replay(db, setting, document['request_digest'], identity,
                                    connection_id, row.integration_id)
        if document.get('phase') == 'registered':
            claims = operations.generic_operations(identity['workspace_id'], registration_id,
                                                   db_factory=db_factory, strict=True)
            if (len(claims) != 1 or claims[0].get('status') != operations.SUCCEEDED
                    or _digest(claims[0].get('result_json')) != document.get('provider_receipt_digest')):
                raise SourceRegistrationError('SOURCE_REGISTRATION_UNVERIFIED')
        return document
