"""Private source-registration state in existing settings and audit storage.

Preparing a registration performs no provider call. Subsequent enrollment must
use the existing outbound operation arbiter; it is not implemented here. This
record preserves the same operation and encrypted receiver state across
restarts and retries.
"""
from __future__ import annotations
import hashlib
import json
import secrets
import uuid
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
    )).values(status=User.status).execution_options(synchronize_session=False))
    target = db.execute(update(UserConnection).where(*(
        getattr(UserConnection, k) == v for k, v in connection.items()
    )).values(status=UserConnection.status).execution_options(synchronize_session=False))
    if principal.rowcount != 1 or target.rowcount != 1:
        raise SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')


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
            AuditLog.event_type == 'workflow_event_source_prepared',
            AuditLog.user_id == identity['user_id'], AuditLog.tenant_id == identity['tenant_id'],
            AuditLog.workspace_id == identity['workspace_id'], AuditLog.resource == connection_id,
            AuditLog.success.is_(True)).all():
        try:
            if json.loads(audit.metadata_json) == expected:
                matches += 1
        except (ValueError, TypeError):
            continue
    if matches != 1:
        raise SourceRegistrationError('SOURCE_REGISTRATION_UNVERIFIED')
    # Bind the actual document observed before returning a verified replay.
    result = db.execute(update(TenantSetting).where(
        TenantSetting.id == row.id, TenantSetting.tenant_id == identity['tenant_id'],
        TenantSetting.setting_key == row.setting_key,
        TenantSetting.setting_value == row.setting_value,
    ).values(setting_value=TenantSetting.setting_value).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
    return document


def prepare_source_registration(*, actor_id, connection_id, source, event_types,
                                callback_base_url, db_factory=None):
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
                _claim(db, actor, connection)
                document = _verified_replay(db, row, request_digest, identity, connection_id, source)
                db.commit()
                return document
            _claim(db, actor, connection)
            operation_id = str(uuid.uuid4())
            receiver_state = secrets.token_urlsafe(32)
            encrypted_state = ConnectionService()._encrypt({'client_state': receiver_state})
            if not isinstance(encrypted_state, str) or not encrypted_state:
                raise SourceRegistrationError('SOURCE_STATE_UNAVAILABLE')
            query = parse_qsl(url.query) + [('registration', operation_id)]
            callback_url = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query), ''))
            document = dict(schema='workflow.event_source.v1', phase='prepared', enabled=False,
                            operation_id=operation_id, source=source, connection_id=connection_id,
                            identity=identity, request_digest=request_digest,
                            event_types=sorted(event_types), callback_url=callback_url,
                            receiver_state_ciphertext=encrypted_state,
                            receiver_state_digest=hashlib.sha256(receiver_state.encode()).hexdigest())
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
                _claim(db, actor, connection)
                document = _verified_replay(db, row, request_digest, identity, connection_id, source)
                db.commit()
                return document
    raise SourceRegistrationError('SOURCE_REGISTRATION_CONFLICT')


def public_registration(document):
    """No receiver secret, commitment, raw authority, or operation digest leaves the service."""
    return {key: document.get(key) for key in (
        'operation_id', 'source', 'connection_id', 'event_types', 'phase', 'enabled')}
