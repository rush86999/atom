"""Original enrollment receipt must bind scope, kind, identity and material."""
import asyncio
import copy
import pytest
from core import workflow_event_source_registration as registry
from core.workflow_event_source_enrollment import enroll_source
from core import workflow_event_source_renewal as renewal
from core.models import TaskOperationRecord, WorkflowExecution, AuditLog
from tests.test_workflow_event_source_binding import binding_world, saved
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db
from tests.test_workflow_event_source_http import http_world, setup_source, save_rule
from tests.test_workflow_event_source_renewal import due_world


@pytest.mark.parametrize('field,value', [
    ('tenant_id','foreign-tenant'),
    ('operation_type','generic:agent:unrelated_action'),
    ('run_id','foreign-run'),
    ('idempotency_key','foreign-key'),
    ('payload_sha256','0'*64),
    ('status','uncertain_effect'),
    ('workspace_id','foreign-workspace'),
    ('operation_id','foreign-operation'),
    ('result_json',{'subscription_id':'foreign-subscription'}),
])
def test_corrupted_original_receipt_cannot_certify_source(binding_world, field, value):
    factory, params, args, provider = binding_world
    first=asyncio.run(enroll_source(**args))
    document=saved(factory)
    with factory() as peer:
        operation=peer.query(TaskOperationRecord).one()
        setattr(operation, field, copy.deepcopy(value))
        peer.commit()
    with pytest.raises(registry.SourceRegistrationError):
        registry.read_delivery_registration('connection',first['operation_id'],db_factory=factory)
    assert saved(factory) == document
    assert sum(c[0]=='POST' for c in provider['calls']) == 1
    with factory() as db:
        assert db.query(TaskOperationRecord).count() == 1
        assert db.query(AuditLog).count() == 2


def test_valid_original_receipt_is_read_only_and_reconciles(binding_world):
    factory, params, args, provider = binding_world
    first=asyncio.run(enroll_source(**args))
    with factory() as db:
        row=db.query(TaskOperationRecord).one()
        before=(row.id,row.updated_at,row.payload_sha256,copy.deepcopy(row.result_json))
    assert registry.read_delivery_registration('connection',first['operation_id'],db_factory=factory)==saved(factory)
    with factory() as db:
        row=db.query(TaskOperationRecord).one()
        assert (row.id,row.updated_at,row.payload_sha256,row.result_json)==before


def test_original_payload_corruption_prevents_renewal_before_any_provider_call(due_world):
    factory, args, provider, original, call=due_world
    with factory() as peer:
        peer.query(TaskOperationRecord).filter(TaskOperationRecord.operation_id==original['operation_id']).one().payload_sha256='0'*64
        peer.commit()
    calls=len(provider['calls'])
    with pytest.raises(registry.SourceRegistrationError):
        asyncio.run(renewal.renew_source(**call))
    assert len(provider['calls'])==calls
    with factory() as db: assert db.query(TaskOperationRecord).count()==1


def test_public_callback_cannot_use_a_wrong_original_payload_proof(http_world):
    client,factory,provider,principal,adapter=http_world
    setup,callback,item=setup_source(client,provider)
    save_rule(client)
    with factory() as peer:
        peer.query(TaskOperationRecord).one().payload_sha256='0'*64
        peer.commit()
    before=len(provider['calls'])
    response=client.post(callback,json={'value':[item]})
    assert response.status_code==503,response.text
    assert len(provider['calls'])==before
    with factory() as db: assert db.query(WorkflowExecution).count()==0
