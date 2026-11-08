"""Independent current-target and operation-row scope controls."""
import uuid
import pytest
from core.models import AgentRegistry, TaskOperationRecord
from tests.test_fleet_credit_receipt_integration import (
    fleet_world, _restore_oracle_verifiers, _produce_verified_operation,
    _seed_fleet, _credit, _stats,
)

@pytest.mark.parametrize('mutation',['agent_tenant','agent_workspace','operation_tenant'])
def test_credit_refuses_changed_authoritative_scope(fleet_world,monkeypatch,mutation):
    monkeypatch.setenv('ATOM_CONTRIBUTION_CREDIT_ENABLED','true')
    action='canvas.scope.'+uuid.uuid4().hex
    child='child-scope-'+mutation
    _produce_verified_operation(fleet_world,child_execution_id=child,action_name=action,operation_id='scope-effect')
    _seed_fleet(fleet_world,child_executions=[(child,action)])
    with fleet_world.Session() as peer:
        if mutation=='operation_tenant':
            row=peer.query(TaskOperationRecord).filter_by(run_id=child,operation_type='generic:agent:'+action).one()
            row.tenant_id='foreign-tenant'
        else:
            row=peer.get(AgentRegistry,'ag-fleet')
            setattr(row,'tenant_id' if mutation=='agent_tenant' else 'workspace_id','foreign-scope')
        peer.commit()
    with fleet_world.Session() as db:
        assert _credit(db) is False
        assert _stats(db,action).get('verified_success',0)==0

@pytest.mark.parametrize('field',['tenant_id','workspace_id'])
def test_scope_move_after_admission_cannot_publish_credit(fleet_world,monkeypatch,field):
    from sqlalchemy import event
    monkeypatch.setenv('ATOM_CONTRIBUTION_CREDIT_ENABLED','true')
    world=fleet_world
    action='canvas.scope_race.'+uuid.uuid4().hex
    child='child-scope-race-'+field
    _produce_verified_operation(world,child_execution_id=child,action_name=action,operation_id='scope-race-effect')
    _seed_fleet(world,child_executions=[(child,action)])
    armed=[True]
    def move_before_claim(conn,cursor,statement,params,ctx,many):
        if armed[0] and statement.lstrip().upper().startswith('INSERT INTO TASK_OPERATION_RECORDS'):
            armed[0]=False
            with world.Session() as peer:
                row=peer.get(AgentRegistry,'ag-fleet');setattr(row,field,'peer-winning-scope');peer.commit()
    event.listen(world.engine,'before_cursor_execute',move_before_claim)
    try:
        with world.Session() as db:
            assert _credit(db) is False
    finally:
        event.remove(world.engine,'before_cursor_execute',move_before_claim)
    assert armed==[False], 'real peer must commit after admission and before receipt DML'
    with world.Session() as fresh:
        assert getattr(fresh.get(AgentRegistry,'ag-fleet'),field)=='peer-winning-scope'
        assert _stats(fresh,action).get('verified_success',0)==0
        assert not fresh.query(TaskOperationRecord).filter_by(operation_type='fleet:capability_credit:v1').count()
