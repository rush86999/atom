"""Authenticated provider lifecycle receipts in the existing source ledger."""
from core import workflow_event_source_registration as registry
from core.workflow_event_source_renewal import _time, _current_plan, _write, _row

_EVENTS = ('reauthorizationRequired', 'missed', 'subscriptionRemoved')


def _material(document, item):
    if not registry.receiver_state_matches(document, item.get('clientState')):
        raise registry.SourceRegistrationError('SOURCE_LIFECYCLE_REFUTED')
    event = item.get('lifecycleEvent')
    if event not in _EVENTS or event not in document.get('lifecycle_events', []):
        raise registry.SourceRegistrationError('SOURCE_LIFECYCLE_UNSUPPORTED')
    if item.get('subscriptionId') != document.get('provider_subscription_id'):
        raise registry.SourceRegistrationError('SOURCE_LIFECYCLE_REFUTED')
    expiry = _time(item.get('subscriptionExpirationDateTime')).isoformat()
    return {'event': event, 'subscription_id': document['provider_subscription_id'],
            'expires_at': expiry, 'source_operation_id': document['operation_id']}


async def record_source_lifecycle(document, item, adapter, db_factory):
    """Prove receiver state and persist exact challenge before acknowledging.

    No caller tenant or resource path supplies authority. Removed is a signed
    provider report, not proof that recreation is safe; it remains pending.
    """
    material = _material(document, item)
    digest = registry._digest(material)
    if digest in document.get('lifecycle_history', []):
        return document, False
    current_expiry = _time(_current_plan(document, adapter)['expires_at'])
    if _time(material['expires_at']) != current_expiry:
        raise registry.SourceRegistrationError('SOURCE_LIFECYCLE_STALE')
    # Intake authenticates the provider with the original private receiver
    # state (checked by the route), exact durable target/scope and lease time.
    # No provider I/O before ACK: the existing worker reads/verifies the target
    # before PATCH. This retains the challenge even while credentials are absent.
    identity = document['identity']
    try:
        with db_factory() as db:
            actor, current_identity, connection = registry._authority(db,
                identity['user_id'], document['connection_id'], document['source'])
            if current_identity != identity:
                raise registry.SourceRegistrationError('SOURCE_AUTHORITY_CHANGED')
            registry._claim(db, actor, connection)
            row = _row(db, document)
            if row is None:
                raise registry.SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
            current = registry._verified_replay(db, row, document['request_digest'], identity,
                document['connection_id'], document['source'])
            if current != document:
                # Duplicate/concurrent callbacks may adopt only an already
                # proven identical report, not unrelated changed source state.
                existing = current.get('lifecycle_requests', {}).get(material['event'])
                if (isinstance(existing, dict) and existing.get('digest') == digest
                        or digest in current.get('lifecycle_history', [])):
                    db.commit()
                    return current, False
                raise registry.SourceRegistrationError('SOURCE_REGISTRATION_CHANGED')
            requests = dict(document.get('lifecycle_requests', {}))
            existing = requests.get(material['event'])
            if existing is not None:
                if existing != {'digest': digest, 'material': material}:
                    raise registry.SourceRegistrationError('SOURCE_LIFECYCLE_CONFLICT')
                db.commit()
                return document, False
            requests[material['event']] = {'digest': digest, 'material': material}
            updated = dict(document, lifecycle_requests=requests)
            _write(db, document, updated, 'workflow_event_source_lifecycle_received',
                   'record_workflow_event_source_lifecycle')
            db.commit()
        verified = registry.read_delivery_registration(document['connection_id'],
            document['operation_id'], db_factory=db_factory)
        if verified != updated:
            raise registry.SourceRegistrationError('SOURCE_LIFECYCLE_UNVERIFIED')
        return verified, True
    except registry.SourceRegistrationError:
        raise
    except Exception:
        raise registry.SourceRegistrationError('SOURCE_LIFECYCLE_UNAVAILABLE') from None
