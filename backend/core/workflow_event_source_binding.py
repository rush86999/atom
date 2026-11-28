"""Private source grant snapshots and exact transactional authority claims.

Reuses the existing registry and encryption service. No provider I/O, commit,
queue or credential fallback; callers own the transaction and private snapshot.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

from sqlalchemy import update

from core import workflow_event_source_registration as registry
from core.connection_service import ConnectionService
from core.models import UserConnection


def _fail(code):
    raise registry.SourceRegistrationError(code) from None


def _commitment(row):
    if row is None or not isinstance(row.credentials, str):
        _fail('SOURCE_CREDENTIALS_UNAVAILABLE')
    material = registry._json({
        'credentials': row.credentials,
        'expires_at': row.expires_at.isoformat() if row.expires_at else None,
    })
    return hmac.new(
        ConnectionService().security_config.secret_key.encode(),
        material.encode(),
        hashlib.sha256,
    ).hexdigest()


def credential_commitment(db, connection_id):
    return _commitment(db.get(UserConnection, connection_id))


def _encrypted(value):
    if not isinstance(value, str):
        _fail('SOURCE_CREDENTIALS_UNAVAILABLE')
    text = value.strip()
    if not text:
        _fail('SOURCE_CREDENTIALS_UNAVAILABLE')
    try:
        json.loads(text)
    except (TypeError, ValueError):
        return value
    _fail('SOURCE_CREDENTIALS_UNAVAILABLE')


def _usable_token(credentials):
    if not isinstance(credentials, dict):
        _fail('SOURCE_CREDENTIALS_UNAVAILABLE')
    token = credentials.get('access_token')
    if (not isinstance(token, str) or not token.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in token)):
        _fail('SOURCE_ACCESS_TOKEN_UNAVAILABLE')


def snapshot(db, actor_id, connection_id, source, expected_credentials=None, *, require_manage=True):
    actor, identity, connection = registry._authority(
        db, actor_id, connection_id, source, require_manage=require_manage)
    row = db.get(UserConnection, connection_id)
    if row is None:
        _fail('SOURCE_CREDENTIALS_UNAVAILABLE')
    encrypted = _encrypted(row.credentials)
    service = ConnectionService()
    normalized_expiry = service._ensure_aware_datetime(row.expires_at)
    if (normalized_expiry is not None
            and normalized_expiry <= datetime.now(timezone.utc)):
        _fail('SOURCE_CREDENTIALS_EXPIRED')
    try:
        credentials = service._decrypt(encrypted)
    except Exception:
        _fail('SOURCE_CREDENTIALS_UNAVAILABLE')
    if not isinstance(credentials, dict):
        _fail('SOURCE_CREDENTIALS_UNAVAILABLE')
    _usable_token(credentials)
    if (expected_credentials is not None
            and registry._json(credentials) != registry._json(expected_credentials)):
        _fail('SOURCE_CREDENTIALS_CHANGED')
    return {
        'require_manage': require_manage,
        'actor': actor,
        'identity': identity,
        'connection': connection,
        'credential_commitment': _commitment(row),
        'credentials': credentials,
        'encrypted_credentials': encrypted,
        'expires_at': row.expires_at,
    }


def _field(value, key):
    try:
        return value[key]
    except (KeyError, TypeError):
        _fail('SOURCE_AUTHORITY_CHANGED')


def claim(db, snapshot):
    actor = _field(snapshot, 'actor')
    identity = _field(snapshot, 'identity')
    connection = _field(snapshot, 'connection')
    encrypted = _field(snapshot, 'encrypted_credentials')
    expires_at = _field(snapshot, 'expires_at')
    normalized_expiry = ConnectionService()._ensure_aware_datetime(expires_at)
    if normalized_expiry is not None and normalized_expiry <= datetime.now(timezone.utc):
        _fail('SOURCE_CREDENTIALS_EXPIRED')
    actor_id = _field(actor, 'id')
    connection_id = _field(connection, 'id')
    source = _field(connection, 'integration_id')
    fresh = registry._authority(db, actor_id, connection_id, source,
                                require_manage=snapshot.get('require_manage', True))
    if fresh != (actor, identity, connection):
        _fail('SOURCE_AUTHORITY_CHANGED')
    registry._claim(db, actor, connection)
    bound = dict(connection)
    bound['credentials'] = encrypted
    bound['expires_at'] = expires_at
    target = db.execute(
        update(UserConnection)
        .where(*(getattr(UserConnection, key) == value
                  for key, value in bound.items()))
        .values(status=UserConnection.status,
                updated_at=UserConnection.updated_at)
        .execution_options(synchronize_session=False)
    )
    if target.rowcount != 1:
        _fail('SOURCE_AUTHORITY_CHANGED')
