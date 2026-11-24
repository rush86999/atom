"""Durable workflow admission after a connector verifies an inbound delivery.

This internal entry is not an authentication boundary. Callers must verify the
provider delivery and resolve its exact connection before invoking it. Neither
payload ownership claims nor a first-active connection may supply that identity.
The existing pending worker owns dispatch; this module adds no queue or runner.
"""
from dataclasses import fields

from core.execution_state_manager import get_state_manager
from core.workflow_event_admission import (
    EventAdmissionError, EventAdmissionReceipt, EventScopeConflict, ReservationResult,
    WorkflowEvent, WorkflowEventAdmissionCoordinator,
)


def _receipt_from_state(state):
    admission = (state.get('context') or {}).get('_atom_event_admission')
    if not isinstance(admission, dict) or admission.get('execution_id') != state.get('execution_id'):
        raise EventAdmissionError('Stored event receipt is unavailable')
    try:
        material = {field.name: admission[field.name] for field in fields(EventAdmissionReceipt)
                    if field.name != 'input_data'}
        return EventAdmissionReceipt(**material, input_data=state.get('input_data') or {})
    except (KeyError, TypeError) as exc:
        raise EventAdmissionError('Stored event receipt is incomplete') from exc


async def admit_verified_source_event(db, *, connection_id, source, event_type,
                                      provider_event_id, payload, expected_identity=None):
    """Reserve matching saved workflows under the authoritative connection owner.

    ``provider_event_id`` identifies a delivery/event, not a mutable resource.
    Retries reconcile the original receipt before current enablement checks.
    The current actor and connection are checked even on retries.
    """
    from core.models import User, UserConnection
    from sqlalchemy import update
    from core.connection_service import ConnectionService
    from core import workflow_endpoints
    from core.workflow_event_worker import (
        _load_current_actor, _actor_is_active, _actor_has_run_permission,
    )

    if any(not isinstance(v, str) or not v.strip()
           for v in (connection_id, source, event_type, provider_event_id)):
        raise EventAdmissionError('Exact source and provider event identity are required')
    row = db.query(
        UserConnection.id, UserConnection.user_id, UserConnection.tenant_id,
        UserConnection.workspace_id, UserConnection.integration_id,
    ).filter(UserConnection.id == connection_id,
             UserConnection.integration_id == source,
             UserConnection.status == 'active').first()
    if row is None:
        raise EventAdmissionError('Source connection is unavailable')
    actor = _load_current_actor(db, row.user_id)
    if actor is None or not _actor_is_active(actor) or not _actor_has_run_permission(actor):
        raise EventAdmissionError('Source owner is unavailable')
    connection = ConnectionService.get_scoped_connection_metadata(
            db, user_id=str(actor.id), tenant_id=getattr(actor, 'tenant_id', None),
            workspace_id=getattr(actor, 'workspace_id', None),
            connection_id=connection_id, integration_id=source)
    if connection is None:
        raise EventAdmissionError('Source connection owner scope has changed')
    identity = workflow_endpoints._caller_scope(actor)
    if expected_identity is not None and expected_identity != identity:
        raise EventScopeConflict('Verified source owner no longer matches the current connection')
    authority = {name: getattr(actor, name) for name in
                 ('id', 'role', 'status', 'is_active', 'tenant_id', 'workspace_id')}

    async def claim_authority(session):
        principal = await session.execute(update(User).where(*(
            getattr(User, name) == value for name, value in authority.items()
        )).values(status=User.status, updated_at=User.updated_at))
        target = await session.execute(update(UserConnection).where(*(
            getattr(UserConnection, name) == value for name, value in connection.items()
        )).values(status=UserConnection.status, updated_at=UserConnection.updated_at))
        if principal.rowcount != 1 or target.rowcount != 1:
            raise EventScopeConflict('Verified source authority changed before reservation')

    # This also covers receipt-only replay: stale ORM snapshots cannot certify
    # current authority. New reservations repeat the claim in their insert TX.
    manager = get_state_manager()
    await manager.verify_event_authority(claim_authority)
    event = WorkflowEvent(tenant_id=identity['tenant_id'], workspace_id=identity['workspace_id'],
                          owner_id=identity['user_id'], connection_id=connection_id,
                          source=source, event_type=event_type,
                          provider_event_id=provider_event_id, payload=payload)
    # Corrupt/unavailable catalog must remain an error, never an empty success.
    workflows = workflow_endpoints.load_workflows_strict()

    async def lookup(key):
        state = await manager.get_execution_state(key.event_id)
        if not state:
            return None
        receipt = _receipt_from_state(state)
        if receipt.owner_id != identity['user_id']:
            raise EventScopeConflict('Original event receipt belongs to a different owner')
        return receipt

    async def reserve(candidate):
        state, created = await manager.reserve_event_execution(
            candidate.workflow_id, dict(candidate.input_data), execution_id=candidate.event_id,
            identity=identity, admission=candidate.admission_context,
            reservation_guard=claim_authority)
        winner = _receipt_from_state(state)
        if winner.owner_id != identity['user_id']:
            raise EventScopeConflict('Original event receipt belongs to a different owner')
        return ReservationResult(winner, created=created)

    coordinator = WorkflowEventAdmissionCoordinator(lookup, reserve)
    admitted = []
    for workflow in workflows:
        if (workflow.get('event_binding_version') != 1
                or workflow.get('created_by') != identity['user_id']
                or workflow.get('tenant_id') != identity['tenant_id']
                or workflow.get('workspace_id') != identity['workspace_id']):
            continue
        result = await coordinator.admit(event, workflow)
        if result is not None:
            admitted.append({'workflow_id': result.receipt.workflow_id,
                             'execution_id': result.event_id,
                             'status': 'already_applied' if result.duplicate else 'admitted'})
    return admitted
