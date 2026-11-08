"""A late old receipt cannot earn current-epoch credit across a peer reset."""
import uuid
from sqlalchemy import event
from core.capability_graduation_service import CapabilityGraduationService
from core.models import AgentRegistry, TaskOperationRecord
from tests.test_fleet_credit_receipt_integration import (
    fleet_world,_restore_oracle_verifiers,_produce_verified_operation,
    _seed_fleet,_credit,_stats,
)


def test_peer_regression_cannot_turn_old_receipt_into_new_epoch_work(fleet_world,monkeypatch):
    monkeypatch.setenv('ATOM_CONTRIBUTION_CREDIT_ENABLED','true')
    world=fleet_world;action='canvas.epoch_race.'+uuid.uuid4().hex;child='child-old-proof'
    _produce_verified_operation(world,child_execution_id=child,action_name=action,operation_id='old-proof-operation')
    _seed_fleet(world,child_executions=[(child,action)])
    with world.Session() as db:
        agent=db.get(AgentRegistry,'ag-fleet')
        agent.configuration={'capability_stats':{action:{'success':50,'total':50,'verified_success':50}},'capability_maturities':{action:'autonomous'}}
        db.commit()
    armed=[True]
    def regress_before_credit_claim(conn,cursor,statement,params,ctx,many):
        if armed[0] and statement.lstrip().upper().startswith('INSERT INTO TASK_OPERATION_RECORDS'):
            armed[0]=False
            with world.Session() as peer:
                assert CapabilityGraduationService(peer).record_usage('ag-fleet',action,False,'failed_verification') is True
    event.listen(world.engine,'before_cursor_execute',regress_before_credit_claim)
    try:
        with world.Session() as db:
            _credit(db)
    finally:
        event.remove(world.engine,'before_cursor_execute',regress_before_credit_claim)
    assert armed==[False]
    with world.Session() as fresh:
        stats=_stats(fresh,action)
        assert stats['verified_success']==50
        cfg=fresh.get(AgentRegistry,'ag-fleet').configuration
        assert cfg['autonomy_revocations'][action]['reentry_successes']==0
        receipts=fresh.query(TaskOperationRecord).filter_by(operation_type='fleet:capability_credit:v1').all()
        assert all((r.result_json or {}).get('verified') is False for r in receipts)
