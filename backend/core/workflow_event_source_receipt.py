"""Exact original source-operation proofs on the existing operation ledger.

No inserts, repairs, provider I/O, commits or rollbacks. Callers own the
transaction. Scalar reads avoid stale ORM entities; the no-op claim binds the
observed physical JSON representation after validating its semantic material.
"""
from sqlalchemy import String, cast, update
from core import outbound_operation_claim as operations
from core import workflow_event_source_registration as registry
from core.models import TaskOperationRecord

_ACTION = 'enroll_workflow_event_source'
_TYPE = 'generic:agent:' + _ACTION
_PENDING = (operations.CLAIMED, operations.DISPATCHING,
            operations.UNCERTAIN_EFFECT, operations.FAILED_BEFORE_EFFECT)


def _fail():
    raise registry.SourceRegistrationError('SOURCE_ENROLLMENT_UNVERIFIED') from None


def enrollment_material(document, adapter=None):
    """Use only the frozen source and its exact original actor identity."""
    try:
        if adapter is None:
            from core.workflow_event_source_adapters import source_adapter
            adapter = source_adapter(document['source'])
        identity = document['identity']
        if adapter.source != document['source']:
            _fail()
        plan = operations.strict_json_roundtrip(adapter.material(document))
        if not isinstance(plan, dict):
            _fail()
        payload_hash = operations.operation_payload_sha256(
            workspace_id=identity['workspace_id'], tenant_id=identity['tenant_id'],
            actor_id=identity['user_id'], agent_id=None, execution_id=document['operation_id'],
            actor_kind='user', execution_kind='source_registration', action=_ACTION,
            frozen_args={'request_digest': document['request_digest'], 'plan': plan,
                         'receiver_state_digest': document['receiver_state_digest']})
        return plan, payload_hash
    except Exception:
        _fail()


def _claim_operation(db, document, payload_hash, status, result, record_id=None):
    identity = document['identity']; operation_id = document['operation_id']
    expected = dict(tenant_id=identity['tenant_id'], workspace_id=identity['workspace_id'],
        operation_id=operation_id, run_id=operation_id, idempotency_key=operation_id,
        operation_type=_TYPE, status=status, payload_sha256=payload_hash)
    if not all(type(value) is str and value for value in expected.values()):
        _fail()
    columns = [TaskOperationRecord.id] + [getattr(TaskOperationRecord, key) for key in expected]
    rows = db.query(*columns, TaskOperationRecord.result_json,
        cast(TaskOperationRecord.result_json, String).label('receipt_storage')).filter(
            TaskOperationRecord.tenant_id == identity['tenant_id'],
            TaskOperationRecord.workspace_id == identity['workspace_id'],
            TaskOperationRecord.operation_id == operation_id).with_for_update().all()
    if len(rows) != 1:
        _fail()
    row = rows[0]
    if (any(type(row._mapping[key]) is not str or row._mapping[key] != value for key, value in expected.items())
            or row.result_json != result or (record_id is not None and row.id != record_id)):
        _fail()
    changed = db.execute(update(TaskOperationRecord).where(
        TaskOperationRecord.id == row.id,
        *(getattr(TaskOperationRecord, key) == value for key, value in expected.items()),
        cast(TaskOperationRecord.result_json, String) == row.receipt_storage,
    ).values(status=TaskOperationRecord.status, updated_at=TaskOperationRecord.updated_at)
      .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        _fail()
    return row.id


def verify_enrollment_receipt(db, document, receipt=None, adapter=None):
    try:
        if document.get('phase') not in ('prepared', 'registered'):
            _fail()
        plan, payload_hash = enrollment_material(document, adapter)
        registered = document['phase'] == 'registered'
        subscription_id = (document.get('provider_subscription_id') if registered
                           else receipt.get('subscription_id') if isinstance(receipt, dict) else None)
        expected = dict(subscription_id=subscription_id, operation_id=document['operation_id'],
            source=document['source'], connection_id=document['connection_id'],
            request_digest=document['request_digest'], plan_digest=registry._digest(plan))
        if (not all(type(value) is str and value for value in expected.values())
                or (receipt is not None and receipt != expected)
                or (registered and document.get('provider_receipt_digest') != registry._digest(expected))):
            _fail()
        _claim_operation(db, document, payload_hash, operations.SUCCEEDED, expected)
        return expected
    except Exception:
        _fail()


def verify_enrollment_intent(db, document, record_id, status, adapter=None):
    """Bind a pending original row before a status transition, never recreate it."""
    try:
        if document.get('phase') != 'prepared' or status not in _PENDING:
            _fail()
        _, payload_hash = enrollment_material(document, adapter)
        return _claim_operation(db, document, payload_hash, status, None, record_id)
    except Exception:
        _fail()


def inspect_enrollment_operation(db, document, adapter=None):
    """A server-generated source UUID cannot be silently moved to another slot."""
    try:
        rows = db.query(TaskOperationRecord.id, TaskOperationRecord.status,
                        TaskOperationRecord.result_json).filter(
            (TaskOperationRecord.operation_id == document['operation_id']) |
            ((TaskOperationRecord.workspace_id == document['identity']['workspace_id']) &
             (TaskOperationRecord.run_id == document['operation_id']) &
             (TaskOperationRecord.idempotency_key == document['operation_id']))).all()
        if not rows:
            if document.get('phase') == 'registered':
                _fail()
            return None
        if len(rows) != 1:
            _fail()
        row = rows[0]
        if row.status == operations.SUCCEEDED:
            verify_enrollment_receipt(db, document, receipt=row.result_json, adapter=adapter)
        else:
            verify_enrollment_intent(db, document, row.id, row.status, adapter)
        return row.status
    except Exception:
        _fail()
