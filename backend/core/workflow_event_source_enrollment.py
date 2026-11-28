"""Enroll prepared sources using the existing outbound operation arbiter."""
from contextlib import contextmanager
import hashlib
from core import outbound_operation_claim as operations
from core import workflow_event_source_registration as registrations
from core.connection_service import ConnectionService
from core.models import TenantSetting


class EnrollmentRefused(ValueError):
    """Adapter evidence proves this attempt did not create a subscription."""


def _outcome(document, status, effect, **extra):
    return dict(registrations.public_registration(document), status=status,
                effect=effect, do_not_repeat=effect in ('unknown', 'committed'), **extra)


async def source_credentials(document, adapter, db_factory):
    """Use the exact registered owner and existing durable credential refresh."""
    identity = document['identity']
    try:
        return await ConnectionService().ensure_scoped_connection_credentials(
            user_id=identity['user_id'], tenant_id=identity['tenant_id'], workspace_id=identity['workspace_id'],
            connection_id=document['connection_id'], integration_id=adapter.source,
            provider=adapter.oauth_provider, db_factory=db_factory)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('Source credential read unavailable (%s)', type(exc).__name__)
        return None


def verify_source_subscription(adapter, document, receipt, observed, db_factory):
    """A renewed expiry is usable only after fresh exact local lease proof."""
    if document.get('current_lease') is None:
        return adapter.verify(document, receipt, observed)
    verified = registrations.read_delivery_registration(document['connection_id'],
        document['operation_id'], db_factory=db_factory)
    if verified != document:
        return False
    return adapter.verify_renewal(document, receipt, observed,
                                  verified['current_lease']['intent']['plan'])


async def enroll_source(*, actor_id, connection_id, callback_base_url, adapter,
                        db_factory=None, observed_subscription_id=None):
    """No transport retry: a dispatching/uncertain claim needs reconciliation."""
    if db_factory is None:
        from core.database import get_db_session
        db_factory = get_db_session
    params = dict(actor_id=actor_id, connection_id=connection_id, source=adapter.source,
                  event_types=list(adapter.event_types), callback_base_url=callback_base_url,
                  db_factory=db_factory)
    document = registrations.prepare_source_registration(**params)
    identity = document['identity']
    plan = operations.strict_json_roundtrip(adapter.material(document))
    if not isinstance(plan, dict):
        raise registrations.SourceRegistrationError('SOURCE_ADAPTER_MATERIAL_INVALID')
    payload_hash = operations.operation_payload_sha256(
        workspace_id=identity['workspace_id'], tenant_id=identity['tenant_id'],
        actor_id=actor_id, agent_id=None, execution_id=document['operation_id'],
        actor_kind='user', execution_kind='source_registration', action='enroll_workflow_event_source',
        frozen_args={'request_digest': document['request_digest'], 'plan': plan,
                     'receiver_state_digest': document['receiver_state_digest']})
    claim = operations.claim_generic_operation(
        workspace_id=identity['workspace_id'], tenant_id=identity['tenant_id'],
        operation_id=document['operation_id'], action='enroll_workflow_event_source',
        payload_hash=payload_hash, execution_id=document['operation_id'], db_factory=db_factory)
    status = claim.get('status')
    recovered_readback = None
    if status in (operations.DISPATCHING, operations.UNCERTAIN_EFFECT):
        # Only a verified connector callback supplies this observation. Prove
        # the original target with a scoped read; never reissue creation.
        if not isinstance(observed_subscription_id, str) or not observed_subscription_id:
            return _outcome(document, 'effect_unknown', 'unknown')
        candidate = dict(subscription_id=observed_subscription_id, operation_id=document['operation_id'],
                         source=adapter.source, connection_id=connection_id,
                         request_digest=document['request_digest'], plan_digest=registrations._digest(plan))
        private = await source_credentials(document, adapter, db_factory)
        if not isinstance(private, dict) or not private.get('access_token'):
            return _outcome(document, 'effect_unknown', 'unknown')
        try:
            recovered_readback = await adapter.read(observed_subscription_id, private or {})
            if verify_source_subscription(adapter, document, candidate, recovered_readback, db_factory) is not True:
                return _outcome(document, 'effect_unknown', 'unknown')
            if not operations.mark_status(claim['record_id'], operations.SUCCEEDED,
                    expected_status=status, expected_payload_sha256=payload_hash,
                    result=candidate, db_factory=db_factory):
                return _outcome(document, 'effect_unknown', 'unknown')
            claim = dict(claim, status=operations.SUCCEEDED, result_json=candidate)
            status = operations.SUCCEEDED
        except Exception:
            return _outcome(document, 'effect_unknown', 'unknown')
    if status == operations.FAILED_BEFORE_EFFECT:
        return _outcome(document, 'not_applied', 'none')
    if status not in (operations.CLAIMED, operations.SUCCEEDED) or not claim.get('record_id'):
        return _outcome(document, 'operation_conflict' if status == 'conflict' else 'operation_unavailable', 'unknown')
    record_id = claim['record_id']
    credentials = {}
    authority_failure = []

    @contextmanager
    def dispatch_factory():
        with db_factory() as db:
            try:
                actor, current_identity, connection = registrations._authority(db, actor_id, connection_id, adapter.source)
                if current_identity != identity:
                    raise registrations.SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
                registrations._claim(db, actor, connection)
                row = db.query(TenantSetting).filter(
                    TenantSetting.tenant_id == identity['tenant_id'],
                    TenantSetting.setting_key == registrations._key(connection_id, adapter.source)).first()
                if row is None or registrations._verified_replay(
                        db, row, document['request_digest'], identity, connection_id, adapter.source) != document:
                    raise registrations.SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
                private = ConnectionService().get_scoped_connection_credentials(
                    user_id=actor_id, tenant_id=actor['tenant_id'], workspace_id=actor['workspace_id'],
                    connection_id=connection_id, integration_id=adapter.source)
                if (not isinstance(private, dict) or not isinstance(private.get('access_token'), str)
                        or not private['access_token'].strip()):
                    raise registrations.SourceRegistrationError('SOURCE_CREDENTIALS_UNAVAILABLE')
                credentials.update(private)
                yield db
            except registrations.SourceRegistrationError as exc:
                authority_failure.append(exc.code)
                raise

    if status == operations.CLAIMED:
        if not await source_credentials(document, adapter, db_factory):
            return _outcome(document, 'credentials_unavailable', 'unknown')
        if not operations.mark_status(record_id, operations.DISPATCHING,
                expected_status=operations.CLAIMED, expected_payload_sha256=payload_hash,
                db_factory=dispatch_factory):
            return _outcome(document, 'refused' if authority_failure else 'effect_unknown',
                            'none' if authority_failure else 'unknown')
        try:
            secret = ConnectionService()._decrypt(document['receiver_state_ciphertext']).get('client_state')
            if (not isinstance(secret, str) or not secret
                    or hashlib.sha256(secret.encode()).hexdigest() != document['receiver_state_digest']):
                # No provider attempt has occurred; retain a confirmed pre-effect refusal.
                raise EnrollmentRefused('SOURCE_STATE_UNAVAILABLE')
            created = await adapter.create(document, credentials, secret)
            subscription_id = created.get('subscription_id') if isinstance(created, dict) else None
            if not isinstance(subscription_id, str) or not subscription_id.strip():
                raise ValueError('provider identity unavailable after enrollment')
            receipt = dict(subscription_id=subscription_id, operation_id=document['operation_id'],
                           source=adapter.source, connection_id=connection_id,
                           request_digest=document['request_digest'], plan_digest=registrations._digest(plan))
            if not operations.mark_status(record_id, operations.SUCCEEDED,
                    expected_status=operations.DISPATCHING, expected_payload_sha256=payload_hash,
                    result=receipt, db_factory=db_factory):
                return _outcome(document, 'effect_unknown', 'unknown')
        except EnrollmentRefused:
            operations.mark_status(record_id, operations.FAILED_BEFORE_EFFECT,
                expected_status=operations.DISPATCHING, expected_payload_sha256=payload_hash,
                db_factory=db_factory)
            return _outcome(document, 'not_applied', 'none')
        except Exception:
            operations.mark_status(record_id, operations.UNCERTAIN_EFFECT,
                expected_status=operations.DISPATCHING, expected_payload_sha256=payload_hash,
                db_factory=db_factory)
            return _outcome(document, 'effect_unknown', 'unknown')
    else:
        receipt = claim.get('result_json')
        # Fresh scoped credentials for readback only; this path never creates.
        private = await source_credentials(document, adapter, db_factory)
        if isinstance(private, dict):
            credentials.update(private)
    expected = dict(operation_id=document['operation_id'], source=adapter.source,
                    connection_id=connection_id, request_digest=document['request_digest'],
                    plan_digest=registrations._digest(plan))
    if (not isinstance(receipt, dict) or set(receipt) != set(expected) | {'subscription_id'}
            or any(receipt.get(k) != v for k, v in expected.items())
            or not isinstance(receipt.get('subscription_id'), str) or not receipt['subscription_id']):
        return _outcome(document, 'committed_unverified', 'committed')
    try:
        observed = (recovered_readback if recovered_readback is not None
                    else await adapter.read(receipt['subscription_id'], credentials))
        if verify_source_subscription(adapter, document, receipt, observed, db_factory) is not True:
            return _outcome(document, 'committed_unverified', 'committed')
        activated = registrations.activate_source_registration(document, receipt, db_factory=db_factory)
        # Read back target/audit in an independent session before certifying.
        verified = registrations.prepare_source_registration(**params)
        if verified != activated:
            return _outcome(document, 'committed_unverified', 'committed')
        return _outcome(verified, 'already_applied' if status == operations.SUCCEEDED else 'registered',
                        'committed', subscription_id=receipt['subscription_id'])
    except Exception:
        return _outcome(document, 'committed_unverified', 'committed')
