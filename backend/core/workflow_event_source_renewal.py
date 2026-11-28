"""Durable native lease renewal on the existing source/operation ledgers.

No runner or implicit re-creation: unknown PATCH outcomes reconcile by GET only.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import uuid
from sqlalchemy import update
from core import outbound_operation_claim as operations
from core import workflow_event_source_registration as registry
from core.connection_service import ConnectionService
from core.models import AuditLog, TenantSetting, TaskOperationRecord, UserConnection
from core.workflow_event_source_enrollment import source_credentials, EnrollmentRefused

_ACTION = 'renew_workflow_event_source'


def _time(value):
    try:
        value = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise ValueError()
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise registry.SourceRegistrationError('SOURCE_LEASE_TIME_INVALID') from None


def _hash(document, intent):
    identity = document['identity']
    return operations.operation_payload_sha256(
        workspace_id=identity['workspace_id'], tenant_id=identity['tenant_id'],
        actor_id=identity['user_id'], agent_id=None, execution_id=intent['operation_id'],
        actor_kind='user', execution_kind='source_renewal', action=_ACTION,
        frozen_args={'source_operation_id': document['operation_id'],
                     'source_request_digest': document['request_digest'], 'intent': intent})


def _receipt(document, intent):
    return dict(operation_id=intent['operation_id'], source_operation_id=document['operation_id'],
                source=document['source'], connection_id=document['connection_id'],
                subscription_id=document['provider_subscription_id'],
                plan_digest=registry._digest(intent['plan']))


def _lease(document, intent):
    return dict(intent=intent, receipt_digest=registry._digest(_receipt(document, intent)))


def verify_current_lease(db, document):
    """Exact current lease proof, inside the registry reader's own transaction."""
    lease = document.get('current_lease')
    if not isinstance(lease, dict) or set(lease) != {'intent', 'receipt_digest'}:
        raise registry.SourceRegistrationError('SOURCE_LEASE_UNVERIFIED')
    intent = lease['intent']
    _verify_intent(document, intent)
    _verify_superseded(db, document, intent)
    identity = document['identity']
    rows = db.query(TaskOperationRecord).filter(
        TaskOperationRecord.workspace_id == identity['workspace_id'],
        TaskOperationRecord.tenant_id == identity['tenant_id'],
        TaskOperationRecord.operation_id == intent['operation_id']).all()
    receipt = _receipt(document, intent)
    if (len(rows) != 1 or rows[0].status != operations.SUCCEEDED
            or rows[0].run_id != intent['operation_id']
            or rows[0].idempotency_key != intent['operation_id']
            or rows[0].operation_type != 'generic:agent:' + _ACTION
            or rows[0].payload_sha256 != _hash(document, intent)
            or rows[0].result_json != receipt
            or lease['receipt_digest'] != registry._digest(receipt)):
        raise registry.SourceRegistrationError('SOURCE_LEASE_UNVERIFIED')


def _verify_intent(document, intent):
    required = {'operation_id', 'requested_at', 'previous_plan', 'plan', 'authority',
                'source_operation_id', 'subscription_id'}
    optional = {'lifecycle_request', 'supersedes'}
    if (not isinstance(intent, dict) or not required <= set(intent)
            or not set(intent) <= required | optional
            or not isinstance(intent['operation_id'], str) or not intent['operation_id']
            or intent['source_operation_id'] != document['operation_id']
            or intent['subscription_id'] != document['provider_subscription_id']
            or not isinstance(intent['authority'], dict)
            or set(intent['authority']) != {'actor', 'connection', 'credential_commitment'}):
        raise registry.SourceRegistrationError('SOURCE_RENEWAL_UNVERIFIED')
    if ('lifecycle_request' in intent and (not isinstance(intent['lifecycle_request'], str)
            or not intent['lifecycle_request'])):
        raise registry.SourceRegistrationError('SOURCE_RENEWAL_UNVERIFIED')
    if 'supersedes' in intent:
        link = intent['supersedes']
        if (not isinstance(link, dict) or set(link) != {'operation_id', 'payload_sha256'}
                or not isinstance(link['operation_id'], str) or not link['operation_id']
                or link['operation_id'] == intent['operation_id']
                or not isinstance(link['payload_sha256'], str) or len(link['payload_sha256']) != 64):
            raise registry.SourceRegistrationError('SOURCE_RENEWAL_UNVERIFIED')
    from core.workflow_event_source_adapters import source_adapter
    adapter = source_adapter(document['source'])
    try:
        expected = adapter.renewal_material(document, now=_time(intent['requested_at']))
        adapter._renewal_plan(document, intent['previous_plan'])
        if expected != intent['plan']:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise registry.SourceRegistrationError('SOURCE_RENEWAL_UNVERIFIED') from None


def _verify_superseded(db, document, intent):
    link = intent.get('supersedes')
    if link is None:
        return
    identity = document['identity']
    rows = db.query(TaskOperationRecord).filter(
        TaskOperationRecord.workspace_id == identity['workspace_id'],
        TaskOperationRecord.tenant_id == identity['tenant_id'],
        TaskOperationRecord.operation_id == link['operation_id']).all()
    if (len(rows) != 1 or rows[0].status != operations.FAILED_BEFORE_EFFECT
            or rows[0].result_json is not None
            or rows[0].run_id != link['operation_id']
            or rows[0].idempotency_key != link['operation_id']
            or rows[0].operation_type != 'generic:agent:' + _ACTION
            or rows[0].payload_sha256 != link['payload_sha256']):
        raise registry.SourceRegistrationError('SOURCE_LEASE_UNVERIFIED')


def _credential_commitment(db, connection_id):
    row = db.get(UserConnection, connection_id)
    if row is None or not isinstance(row.credentials, str):
        raise registry.SourceRegistrationError('SOURCE_CREDENTIALS_UNAVAILABLE')
    material = registry._json({'credentials': row.credentials,
                              'expires_at': row.expires_at.isoformat() if row.expires_at else None})
    return hmac.new(ConnectionService().security_config.secret_key.encode(),
                    material.encode(), hashlib.sha256).hexdigest()


def _row(db, document):
    return db.query(TenantSetting).filter(
        TenantSetting.tenant_id == document['identity']['tenant_id'],
        TenantSetting.setting_key == registry._key(document['connection_id'], document['source'])).first()


def _audit(db, document, event_type, action):
    identity = document['identity']
    db.add(AuditLog(event_type=event_type, security_level='INFO', threat_level='NONE',
        user_id=identity['user_id'], tenant_id=identity['tenant_id'],
        workspace_id=identity['workspace_id'], resource=document['connection_id'], action=action,
        description='Workflow event source lease transition', success=True,
        metadata_json=registry._json({'operation_id': document['operation_id'],
            'source': document['source'], 'request_digest': document['request_digest'],
            'result_digest': registry._digest(document)})))


def _write(db, before, after, event_type, action):
    row = _row(db, before)
    if row is None or registry._digest(registry._read_document(row)) != registry._digest(before):
        raise registry.SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
    # Validate strict JSON material, then bind the actual observed storage
    # bytes. Re-serializing before the CAS falsely rejects equivalent spacing.
    observed_value = row.setting_value
    changed = db.execute(update(TenantSetting).where(TenantSetting.id == row.id,
        TenantSetting.setting_value == observed_value).values(
        setting_value=registry._json(after)).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise registry.SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
    _audit(db, after, event_type, action)


def _new_intent(document, adapter, at, actor, connection, credential_commitment,
                supersedes=None):
    intent = dict(operation_id=str(uuid.uuid4()), requested_at=at.isoformat(),
        previous_plan=_current_plan(document, adapter),
        plan=adapter.renewal_material(document, now=at),
        authority=dict(actor=actor, connection=connection,
            credential_commitment=credential_commitment),
        source_operation_id=document['operation_id'],
        subscription_id=document['provider_subscription_id'])
    challenge = document.get('lifecycle_requests', {}).get('reauthorizationRequired')
    if challenge is not None:
        intent['lifecycle_request'] = challenge['digest']
    if supersedes is not None:
        intent['supersedes'] = {'operation_id': supersedes['operation_id'],
                                'payload_sha256': supersedes['payload_sha256']}
    _verify_intent(document, intent)
    return intent


def _prepare(document, adapter, at, db_factory):
    identity = document['identity']
    with db_factory() as db:
        actor, current, connection = registry._authority(db, identity['user_id'],
            document['connection_id'], document['source'])
        if current != identity:
            raise registry.SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
        registry._claim(db, actor, connection)
        intent = _new_intent(document, adapter, at, actor, connection,
                             _credential_commitment(db, document['connection_id']))
        updated = dict(document, pending_lease=intent)
        _write(db, document, updated, 'workflow_event_source_renewal_prepared',
               'prepare_workflow_event_source_renewal')
        db.commit()
        return updated


def _current_plan(document, adapter):
    lease = document.get('current_lease')
    return lease['intent']['plan'] if lease is not None else adapter.material(document)


def _claim_dispatch(db, document, intent):
    _verify_superseded(db, document, intent)
    identity = document['identity']
    actor, current, connection = registry._authority(db, identity['user_id'],
        document['connection_id'], document['source'])
    authority = intent['authority']
    if (current != identity or actor != authority['actor'] or connection != authority['connection']
            or _credential_commitment(db, document['connection_id']) != authority['credential_commitment']):
        raise registry.SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
    registry._claim(db, actor, connection)
    # Recheck original enrollment proof in this transaction as well as the
    # registry read. A stale initial read cannot authorize a now-refuted source.
    original = db.query(TaskOperationRecord).filter(
        TaskOperationRecord.workspace_id == identity['workspace_id'],
        TaskOperationRecord.tenant_id == identity['tenant_id'],
        TaskOperationRecord.operation_id == document['operation_id']).with_for_update().all()
    if (len(original) != 1 or original[0].status != operations.SUCCEEDED
            or original[0].operation_type != 'generic:agent:enroll_workflow_event_source'
            or original[0].run_id != document['operation_id']
            or original[0].idempotency_key != document['operation_id']
            or registry._digest(original[0].result_json) != document['provider_receipt_digest']):
        raise registry.SourceRegistrationError('SOURCE_ENROLLMENT_UNVERIFIED')
    # Also bind exact encrypted grant/expiry to the SQL claim, not only a read.
    grant = db.get(UserConnection, document['connection_id'])
    changed = db.execute(update(UserConnection).where(UserConnection.id == grant.id,
        UserConnection.credentials == grant.credentials, UserConnection.expires_at == grant.expires_at
    ).values(updated_at=UserConnection.updated_at).execution_options(synchronize_session=False))
    row = _row(db, document)
    if changed.rowcount != 1 or row is None or registry._verified_replay(db, row,
            document['request_digest'], identity, document['connection_id'], document['source']) != document:
        raise registry.SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')


def _same_source_scope(document, intent, identity, actor, connection):
    if identity != document['identity']:
        return False
    for current, previous, fields in (
            (actor, intent['authority']['actor'], ('id', 'tenant_id', 'workspace_id')),
            (connection, intent['authority']['connection'],
             ('id', 'user_id', 'tenant_id', 'workspace_id', 'integration_id'))):
        if not isinstance(previous, dict):
            return False
        for key in fields:
            if (key not in current or key not in previous
                    or type(current[key]) is not type(previous[key]) or current[key] != previous[key]):
                return False
    return True


def _supersession_state(document, intent, payload_hash, record_id, db_factory):
    identity = document['identity']
    with db_factory() as db:
        row = db.query(TaskOperationRecord).filter(
            TaskOperationRecord.id == record_id,
            TaskOperationRecord.workspace_id == identity['workspace_id'],
            TaskOperationRecord.tenant_id == identity['tenant_id'],
            TaskOperationRecord.operation_id == intent['operation_id']).first()
        if (row is None
                or row.status not in (operations.CLAIMED, operations.FAILED_BEFORE_EFFECT)
                or row.result_json is not None
                or row.run_id != intent['operation_id']
                or row.idempotency_key != intent['operation_id']
                or row.operation_type != 'generic:agent:' + _ACTION
                or row.payload_sha256 != payload_hash):
            return 'blocked'
        actor, current, connection = registry._authority(
            db, identity['user_id'], document['connection_id'], document['source'])
        if not _same_source_scope(document, intent, current, actor, connection):
            return 'scope_changed'
        try:
            commitment = _credential_commitment(db, document['connection_id'])
        except registry.SourceRegistrationError as exc:
            if exc.code == 'SOURCE_CREDENTIALS_UNAVAILABLE':
                return 'credentials_unavailable'
            raise
        authority = intent['authority']
        if (actor == authority['actor'] and connection == authority['connection']
                and commitment == authority['credential_commitment']):
            return 'unchanged'
        return 'changed'


def _supersede(document, adapter, at, intent, payload_hash, record_id, db_factory):
    identity = document['identity']
    authority = intent['authority']
    prepared = {}

    def effect(db):
        actor, current, connection = registry._authority(
            db, identity['user_id'], document['connection_id'], document['source'])
        if not _same_source_scope(document, intent, current, actor, connection):
            raise registry.SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
        commitment = _credential_commitment(db, document['connection_id'])
        if (actor == authority['actor'] and connection == authority['connection']
                and commitment == authority['credential_commitment']):
            raise registry.SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
        replacement = _new_intent(
            document, adapter, at, actor, connection, commitment,
            supersedes={'operation_id': intent['operation_id'],
                        'payload_sha256': payload_hash})
        _claim_dispatch(db, document, replacement)
        updated = dict(document, pending_lease=replacement)
        _write(db, document, updated, 'workflow_event_source_renewal_prepared',
               'prepare_workflow_event_source_renewal')
        prepared['document'] = updated
    if not operations.mark_status(record_id, operations.FAILED_BEFORE_EFFECT,
            expected_status=(operations.CLAIMED, operations.FAILED_BEFORE_EFFECT),
            expected_payload_sha256=payload_hash, db_factory=db_factory,
            transition_effect=effect):
        return None
    return prepared.get('document')


def _finish(document, intent):
    def effect(db):
        # Provider already ran; authority drift may block certification, never relabel effect=none.
        _claim_dispatch(db, document, intent)
        updated = dict(document, current_lease=_lease(document, intent))
        updated.pop('pending_lease', None)
        challenge = intent.get('lifecycle_request')
        requests = dict(document.get('lifecycle_requests', {}))
        reauthorization = requests.get('reauthorizationRequired')
        if challenge is None and isinstance(reauthorization, dict):
            material = reauthorization.get('material', {})
            if (material.get('subscription_id') == document['provider_subscription_id']
                    and material.get('expires_at') == _time(intent['previous_plan']['expires_at']).isoformat()):
                # A challenge received while this lease was pending is also
                # satisfied by the same subsequent renewing/reauthorizing PATCH.
                challenge = reauthorization['digest']
        if challenge and requests.get('reauthorizationRequired', {}).get('digest') == challenge:
            requests.pop('reauthorizationRequired')
            updated['lifecycle_requests'] = requests
            history = list(document.get('lifecycle_history', []))
            if challenge not in history:
                history.append(challenge)
            updated['lifecycle_history'] = history[-32:]
        _write(db, document, updated, 'workflow_event_source_renewed', _ACTION)
    return effect


def _outcome(document, status, effect, intent=None, **extra):
    return dict(registry.public_registration(document), status=status, effect=effect,
                do_not_repeat=effect in ('unknown', 'committed'),
                **({'renewal_operation_id': intent['operation_id']} if intent else {}), **extra)


async def renew_source(connection_id, registration_id, adapter, db_factory=None, now=None):
    """Renew the original lease once; unresolved operations only read/reconcile."""
    if db_factory is None:
        from core.database import get_db_session
        db_factory = get_db_session
    at = _time(datetime.now(timezone.utc) if now is None else now)
    try:
        document = registry.read_delivery_registration(connection_id, registration_id, db_factory=db_factory)
    except registry.SourceRegistrationError:
        raise
    except Exception:
        raise registry.SourceRegistrationError('SOURCE_RENEWAL_UNAVAILABLE') from None
    if document['source'] != adapter.source or document.get('phase') != 'registered':
        return _outcome(document, 'refused', 'none', reason='SOURCE_SUBSCRIPTION_MISSING')
    intent = document.get('pending_lease')
    if intent is None:
        expires = _time(_current_plan(document, adapter)['expires_at'])
        if expires <= at:
            return _outcome(document, 'refused', 'none', reason='SOURCE_SUBSCRIPTION_EXPIRED')
        challenge = document.get('lifecycle_requests', {}).get('reauthorizationRequired')
        if expires > at + timedelta(hours=24) and challenge is None:
            return _outcome(document, 'not_due', 'none')
        if challenge is not None and _time(adapter.renewal_material(document, now=at)['expires_at']) <= expires:
            # GET cannot prove reauthorization when old/new lease values are
            # identical. Wait for a strictly later frozen expiry, no busy retry.
            return _outcome(document, 'reauthorization_deferred', 'none')
        # Refresh only before freezing a fresh intent; unknown intent reconciliation below
        # cannot acquire a new identity or redo the provider effect.
        if not await source_credentials(document, adapter, db_factory):
            return _outcome(document, 'credentials_unavailable', 'none')
        try:
            document = _prepare(document, adapter, at, db_factory)
        except registry.SourceRegistrationError as exc:
            if exc.code != 'SOURCE_REGISTRATION_CHANGED':
                return _outcome(document, 'refused', 'none', reason=exc.code)
            document = registry.read_delivery_registration(connection_id, registration_id, db_factory=db_factory)
        except Exception:
            return _outcome(document, 'registration_unavailable', 'unknown')
        intent = document.get('pending_lease')
        if intent is None:
            return _outcome(document, 'already_applied', 'committed')
    _verify_intent(document, intent)
    payload_hash = _hash(document, intent)
    identity = document['identity']
    claim = operations.claim_generic_operation(workspace_id=identity['workspace_id'],
        tenant_id=identity['tenant_id'], operation_id=intent['operation_id'], action=_ACTION,
        payload_hash=payload_hash, execution_id=intent['operation_id'], db_factory=db_factory)
    status = claim.get('status')
    record_id = claim.get('record_id')
    if record_id and status in (operations.CLAIMED, operations.FAILED_BEFORE_EFFECT):
        try:
            state = _supersession_state(document, intent, payload_hash, record_id, db_factory)
        except registry.SourceRegistrationError as exc:
            return _outcome(document, 'authority_unavailable', 'unknown', intent, reason=exc.code)
        except Exception:
            return _outcome(document, 'operation_unavailable', 'unknown', intent)
        if state in ('blocked', 'scope_changed'):
            return _outcome(document, 'operation_unavailable', 'unknown', intent)
        if state == 'credentials_unavailable':
            return _outcome(document, 'credentials_unavailable', 'unknown', intent)
        if state == 'changed':
            private = await source_credentials(document, adapter, db_factory)
            if not isinstance(private, dict) or not private.get('access_token'):
                return _outcome(document, 'credentials_unavailable', 'unknown', intent)
            replacement = _supersede(document, adapter, at, intent, payload_hash, record_id, db_factory)
            if replacement is None:
                return _outcome(document, 'effect_unknown', 'unknown', intent)
            # At most one supersession per call; reload credentials below so a
            # concurrent reconnect cannot send the pre-supersession grant.
            document = replacement
            intent = document['pending_lease']
            _verify_intent(document, intent)
            payload_hash = _hash(document, intent)
            claim = operations.claim_generic_operation(workspace_id=identity['workspace_id'],
                tenant_id=identity['tenant_id'], operation_id=intent['operation_id'], action=_ACTION,
                payload_hash=payload_hash, execution_id=intent['operation_id'], db_factory=db_factory)
            status = claim.get('status')
    if status == operations.FAILED_BEFORE_EFFECT:
        return _outcome(document, 'not_applied', 'none', intent)
    if status not in (operations.CLAIMED, operations.DISPATCHING, operations.UNCERTAIN_EFFECT) or not claim.get('record_id'):
        return _outcome(document, 'operation_unavailable', 'unknown', intent)
    credentials = await source_credentials(document, adapter, db_factory)
    if not isinstance(credentials, dict) or not credentials.get('access_token'):
        return _outcome(document, 'effect_unknown' if status != operations.CLAIMED else
                        'credentials_unavailable', 'unknown', intent)
    record_id = claim['record_id']
    if status == operations.CLAIMED:
        # All provider reads precede the final transactional dispatch authority claim.
        try:
            observed = await adapter.read(document['provider_subscription_id'], credentials)
            if not adapter.verify_renewal(document, _receipt(document, intent), observed, intent['previous_plan']):
                refused = operations.mark_status(record_id, operations.FAILED_BEFORE_EFFECT,
                    expected_status=operations.CLAIMED, expected_payload_sha256=payload_hash, db_factory=db_factory)
                return _outcome(document, 'refused' if refused else 'effect_unknown',
                    'none' if refused else 'unknown', intent, reason='SOURCE_RENEWAL_TARGET_CHANGED')
        except Exception:
            return _outcome(document, 'readback_unavailable', 'unknown', intent)
        failures = []
        def dispatch(db):
            try:
                _claim_dispatch(db, document, intent)
            except registry.SourceRegistrationError as exc:
                failures.append(exc.code)
                raise
        if not operations.mark_status(record_id, operations.DISPATCHING,
                expected_status=operations.CLAIMED, expected_payload_sha256=payload_hash,
                db_factory=db_factory, transition_effect=dispatch):
            return _outcome(document, 'refused' if failures else 'effect_unknown',
                            'none' if failures else 'unknown', intent)
        try:
            await adapter.renew(document, credentials, intent['plan'])
        except EnrollmentRefused:
            recorded = operations.mark_status(record_id, operations.FAILED_BEFORE_EFFECT,
                expected_status=operations.DISPATCHING, expected_payload_sha256=payload_hash, db_factory=db_factory)
            return _outcome(document, 'not_applied' if recorded else 'effect_unknown',
                            'none' if recorded else 'unknown', intent)
        except Exception:
            operations.mark_status(record_id, operations.UNCERTAIN_EFFECT,
                expected_status=operations.DISPATCHING, expected_payload_sha256=payload_hash, db_factory=db_factory)
            return _outcome(document, 'effect_unknown', 'unknown', intent)
        status = operations.DISPATCHING
    committed = False
    try:
        observed = await adapter.read(document['provider_subscription_id'], credentials)
        if not adapter.verify_renewal(document, _receipt(document, intent), observed, intent['plan']):
            return _outcome(document, 'effect_unknown', 'unknown', intent)
        if not operations.mark_status(record_id, operations.SUCCEEDED,
                expected_status=status, expected_payload_sha256=payload_hash,
                result=_receipt(document, intent), db_factory=db_factory,
                transition_effect=_finish(document, intent)):
            return _outcome(document, 'effect_unknown', 'unknown', intent)
        committed = True
        verified = registry.read_delivery_registration(connection_id, registration_id, db_factory=db_factory)
        if verified.get('current_lease') != _lease(document, intent):
            return _outcome(document, 'committed_unverified', 'committed', intent)
        return _outcome(verified, 'renewed' if claim['status'] == operations.CLAIMED else
                        'already_applied', 'committed', intent)
    except Exception:
        return _outcome(document, 'committed_unverified' if committed else 'effect_unknown',
                        'committed' if committed else 'unknown', intent)
