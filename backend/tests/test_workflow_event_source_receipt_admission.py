"""Delivery proof must be current in the transaction reserving a workflow."""
import json
import pytest
from core.models import TaskOperationRecord,TenantSetting,WorkflowExecution
from tests.test_workflow_event_source_http import http_world,setup_source,save_rule
from tests.test_workflow_event_source_enrollment import enrollment_world
from tests.test_workflow_event_source_registration import source_world
from tests.test_workflow_event_reservation import event_db


@pytest.mark.parametrize('target',['receipt','source'])
def test_proof_changed_during_content_fetch_cannot_reserve_execution(http_world,target):
    client,factory,provider,principal,adapter=http_world
    setup,callback,item=setup_source(client,provider)
    save_rule(client)
    def move():
        with factory() as peer:
            if target=='receipt':peer.query(TaskOperationRecord).one().payload_sha256='0'*64
            else:
                row=peer.query(TenantSetting).one()
                value=json.loads(row.setting_value);value['enabled']=False
                row.setting_value=json.dumps(value)
            peer.commit()
    provider['after_content']=move
    response=client.post(callback,json={'value':[item]})
    assert response.status_code==503,response.text
    with factory() as db:
        assert db.query(WorkflowExecution).count()==0
        if target=='receipt':assert db.query(TaskOperationRecord).one().payload_sha256=='0'*64
        else:assert json.loads(db.query(TenantSetting).one().setting_value)['enabled'] is False


def test_grant_changed_during_content_fetch_cannot_reserve_execution(http_world):
    from core.models import UserConnection
    from core.connection_service import ConnectionService
    client,factory,provider,principal,adapter=http_world
    setup,callback,item=setup_source(client,provider)
    save_rule(client)
    def move():
        with factory() as peer:
            peer.get(UserConnection,'connection').credentials=ConnectionService()._encrypt({'access_token':'changed-private-grant'})
            peer.commit()
    provider['after_content']=move
    response=client.post(callback,json={'value':[item]})
    assert response.status_code==503,response.text
    with factory() as db:
        assert db.query(WorkflowExecution).count()==0
        assert ConnectionService()._decrypt(db.get(UserConnection,'connection').credentials)['access_token']=='changed-private-grant'


def test_existing_run_permission_remains_sufficient_for_delivery(http_world):
    from core.models import User
    client,factory,provider,principal,adapter=http_world
    setup,callback,item=setup_source(client,provider)
    save_rule(client)
    with factory() as db:
        db.get(User,'owner').role='member';db.commit()
    assert client.post('/api/v1/workflows/event-sources/connection/enroll',json={}).status_code==403
    response=client.post(callback,json={'value':[item]})
    assert response.status_code==200 and response.json()['admitted']==1,response.text


def test_guard_repeats_inside_the_actual_reservation_transaction(http_world,monkeypatch):
    from core.execution_state_manager import ExecutionStateManager
    client,factory,provider,principal,adapter=http_world
    setup,callback,item=setup_source(client,provider)
    save_rule(client)
    reserve=ExecutionStateManager.reserve_event_execution;changed=[]
    async def moved(self,*args,**kwargs):
        if not changed:
            changed.append(True)
            with factory() as peer:
                peer.query(TaskOperationRecord).one().payload_sha256='0'*64;peer.commit()
        return await reserve(self,*args,**kwargs)
    monkeypatch.setattr(ExecutionStateManager,'reserve_event_execution',moved)
    response=client.post(callback,json={'value':[item]})
    assert changed and response.status_code==503,response.text
    with factory() as db:assert db.query(WorkflowExecution).count()==0


def test_unverified_duplicate_does_not_acknowledge_or_replace_original_execution(http_world):
    client,factory,provider,principal,adapter=http_world
    setup,callback,item=setup_source(client,provider)
    save_rule(client)
    first=client.post(callback,json={'value':[item]})
    assert first.status_code==200 and first.json()['admitted']==1
    def moved():
        with factory() as peer:
            peer.query(TaskOperationRecord).one().payload_sha256='0'*64;peer.commit()
    provider['after_content']=moved
    response=client.post(callback,json={'value':[item]})
    assert response.status_code==503,response.text
    with factory() as db:assert db.query(WorkflowExecution).count()==1
