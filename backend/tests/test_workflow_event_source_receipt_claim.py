"""Exact receipt read claim rejects peer writes and never commits its caller."""
import asyncio
import copy
import json
import pytest
from sqlalchemy import text
from sqlalchemy.sql.dml import Update
from core import workflow_event_source_registration as registry
from core.workflow_event_source_enrollment import enroll_source
from core.models import TaskOperationRecord, User
from tests.test_workflow_event_source_binding import binding_world, saved
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


def enrolled(world):
    factory,params,args,provider=world
    asyncio.run(enroll_source(**args))
    return factory,saved(factory)


def test_equivalent_json_storage_is_not_false_stale(binding_world):
    from core.workflow_event_source_receipt import verify_enrollment_receipt
    factory,document=enrolled(binding_world)
    with factory() as db:
        row=db.query(TaskOperationRecord).one()
        value=json.dumps(row.result_json,sort_keys=True,indent=2)
        db.execute(text('UPDATE task_operation_records SET result_json=:value WHERE id=:id'),{'value':value,'id':row.id})
        db.commit()
    with factory() as db:
        assert verify_enrollment_receipt(db,document)['subscription_id']=='provider-subscription'
        db.rollback()


@pytest.mark.parametrize('field,value', [
    ('result_json',{'subscription_id':'peer-subscription'}),
    ('payload_sha256','0'*64),('status','uncertain_effect'),('tenant_id','peer-tenant')])
def test_peer_winning_after_read_is_preserved_and_unverified(binding_world,monkeypatch,field,value):
    from core.workflow_event_source_receipt import verify_enrollment_receipt
    factory,document=enrolled(binding_world)
    with factory() as db:
        execute=db.execute;changed=[]
        def race(statement,*args,**kwargs):
            if isinstance(statement,Update) and statement.table.name=='task_operation_records' and not changed:
                changed.append(True)
                with factory() as peer:
                    row=peer.query(TaskOperationRecord).one()
                    setattr(row,field,copy.deepcopy(value));peer.commit()
            return execute(statement,*args,**kwargs)
        monkeypatch.setattr(db,'execute',race)
        with pytest.raises(registry.SourceRegistrationError): verify_enrollment_receipt(db,document)
        db.rollback()
        assert changed
    with factory() as db: assert getattr(db.query(TaskOperationRecord).one(),field)==value


def test_stale_session_entity_cannot_shadow_changed_receipt(binding_world):
    from core.workflow_event_source_receipt import verify_enrollment_receipt
    factory,document=enrolled(binding_world)
    with factory() as db:
        cached=db.query(TaskOperationRecord).one()
        original=copy.deepcopy(cached.result_json)
        with factory() as peer:
            peer.query(TaskOperationRecord).one().result_json={'subscription_id':'peer-subscription'};peer.commit()
        assert cached.result_json==original
        with pytest.raises(registry.SourceRegistrationError): verify_enrollment_receipt(db,document)
        db.rollback()


def test_helper_does_not_commit_unrelated_caller_edit(binding_world):
    from core.workflow_event_source_receipt import verify_enrollment_receipt
    factory,document=enrolled(binding_world)
    with factory() as db:
        before=db.get(User,'owner').first_name
        db.get(User,'owner').first_name='uncommitted caller edit'
        verify_enrollment_receipt(db,document)
        db.rollback()
    with factory() as db: assert db.get(User,'owner').first_name==before


def test_missing_original_row_is_not_recreated(binding_world):
    from core.workflow_event_source_receipt import verify_enrollment_receipt
    factory,document=enrolled(binding_world)
    with factory() as db:
        db.delete(db.query(TaskOperationRecord).one());db.commit()
    with factory() as db:
        with pytest.raises(registry.SourceRegistrationError): verify_enrollment_receipt(db,document)
        db.rollback()
    with factory() as db: assert db.query(TaskOperationRecord).count()==0


@pytest.mark.parametrize('pending', ['claimed','unknown'])
@pytest.mark.parametrize('field,value', [('tenant_id','foreign-tenant'),
    ('operation_type','generic:agent:other'),('run_id','foreign-run'),
    ('idempotency_key','foreign-key'),('workspace_id','foreign-workspace'),
    ('operation_id','foreign-operation')])
def test_pending_original_scope_is_never_adopted_or_reallocated(binding_world,monkeypatch,pending,field,value):
    from core import outbound_operation_claim as operations
    factory,params,args,provider=binding_world
    mark=operations.mark_status
    if pending=='claimed':
        monkeypatch.setattr(operations,'mark_status',lambda record,status,**kw: False if status==operations.DISPATCHING else mark(record,status,**kw))
    else: provider['mode']='timeout'
    first=asyncio.run(enroll_source(**args))
    monkeypatch.setattr(operations,'mark_status',mark)
    with factory() as db:
        row=db.query(TaskOperationRecord).one();record_id=row.id
        setattr(row,field,value);db.commit()
    before=len(provider['calls']);provider['mode']='normal'
    result=asyncio.run(enroll_source(**args,observed_subscription_id='provider-subscription'))
    assert result['status']=='effect_unknown' and result['do_not_repeat'] is True
    assert len(provider['calls'])==before
    with factory() as db:
        row=db.query(TaskOperationRecord).one()
        assert row.id==record_id and getattr(row,field)==value
        assert row.status==('claimed' if pending=='claimed' else 'uncertain_effect')


def test_registered_missing_receipt_cannot_allocate_a_second_enrollment(binding_world):
    factory,document=enrolled(binding_world)
    _,params,args,provider=binding_world
    with factory() as db:
        db.delete(db.query(TaskOperationRecord).one());db.commit()
    before=len(provider['calls'])
    result=asyncio.run(enroll_source(**args))
    assert result['status']=='committed_unverified' and result['effect']=='committed'
    assert len(provider['calls'])==before
    with factory() as db: assert db.query(TaskOperationRecord).count()==0


def test_scope_change_after_inspection_refuses_dispatch_and_preserves_peer(binding_world,monkeypatch):
    from core import outbound_operation_claim as operations
    factory,params,args,provider=binding_world
    mark=operations.mark_status;changed=[]
    def moved(record_id,status,**kwargs):
        if status==operations.DISPATCHING and not changed:
            changed.append(True)
            with factory() as peer:
                peer.get(TaskOperationRecord,record_id).tenant_id='peer-tenant';peer.commit()
        return mark(record_id,status,**kwargs)
    monkeypatch.setattr(operations,'mark_status',moved)
    result=asyncio.run(enroll_source(**args))
    assert result['status']=='effect_unknown' and result['effect']=='unknown'
    assert not any(c[0]=='POST' for c in provider['calls'])
    with factory() as db:
        row=db.query(TaskOperationRecord).one()
        assert row.tenant_id=='peer-tenant' and row.status=='claimed'


def test_unknown_reconciliation_cannot_update_a_moved_scope(binding_world,monkeypatch):
    factory,params,args,provider=binding_world
    provider['mode']='timeout'
    first=asyncio.run(enroll_source(**args))
    assert first['status']=='effect_unknown';provider['mode']='normal'
    original=args['adapter'].read
    async def moved(*a,**kw):
        result=await original(*a,**kw)
        with factory() as peer:
            peer.query(TaskOperationRecord).one().tenant_id='peer-tenant';peer.commit()
        return result
    monkeypatch.setattr(args['adapter'],'read',moved)
    result=asyncio.run(enroll_source(**args,observed_subscription_id='provider-subscription'))
    assert result['status']=='effect_unknown' and result['operation_id']==first['operation_id']
    assert sum(c[0]=='POST' for c in provider['calls'])==1
    with factory() as db:
        row=db.query(TaskOperationRecord).one()
        assert row.tenant_id=='peer-tenant' and row.status=='uncertain_effect'
