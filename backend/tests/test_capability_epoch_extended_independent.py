"""Independent positive ladder and late-old-proof controls; scratch SQL only."""
from copy import deepcopy
import pytest
import uuid
from core.autonomy_policy import reset_autonomy_cycle,autonomy_cycle
from core.capability_graduation_service import CapabilityGraduationService
from core.models import AgentRegistry,AgentExecution,ChainLink
from tests.test_autonomy_revocation import store
from tests.test_fleet_credit_receipt_integration import (
    fleet_world,_restore_oracle_verifiers,_produce_verified_operation,
    _seed_fleet,_credit,_stats,TENANT,WORKSPACE,
)

@pytest.mark.parametrize('historical',[5,25,50])
def test_correction_earns_ladder_from_new_successes_only(store,historical):
    Session,db=store;row=db.get(AgentRegistry,'agent-revocation-1');cfg=deepcopy(row.configuration)
    cfg['capability_stats']['canvas_edit'].update(success=historical,total=historical,verified_success=historical)
    cfg['capability_stats']['unrelated']={'verified_success':17,'success':17,'total':17}
    cfg['capability_maturities']['unrelated']='intern';cfg['capability_maturities']['canvas_edit']='autonomous'
    row.configuration=cfg;db.commit();assert reset_autonomy_cycle(db,row.id,'canvas_edit')
    db.close()
    with Session() as fresh:
        service=CapabilityGraduationService(fresh)
        for count in range(1,51):
            service.record_usage('agent-revocation-1','canvas_edit',True,'verified')
            expected='student' if count<5 else 'intern' if count<20 else 'supervised' if count<50 else 'autonomous'
            assert service.get_maturity('agent-revocation-1','canvas_edit')==expected
            assert autonomy_cycle(fresh,'agent-revocation-1','canvas_edit')['ok'] is (count>=5)
        cfg=fresh.get(AgentRegistry,'agent-revocation-1').configuration
        assert cfg['capability_stats']['canvas_edit']['verified_success']==historical+50
        assert cfg['capability_stats']['canvas_edit'].get('failures_verified',0)==0
        assert cfg['capability_stats']['unrelated']=={'verified_success':17,'success':17,'total':17}
        assert cfg['capability_maturities']['unrelated']=='intern'


def test_old_receipt_is_not_new_work_after_reentry_marker_clears(fleet_world,monkeypatch):
    monkeypatch.setenv('ATOM_CONTRIBUTION_CREDIT_ENABLED','true');world=fleet_world
    action='canvas.late_epoch.'+uuid.uuid4().hex
    _produce_verified_operation(world,child_execution_id='old-child',action_name=action,operation_id='old-late-proof')
    _seed_fleet(world,child_executions=[('fresh-child',action)])
    with world.Session() as db:
        agent=db.get(AgentRegistry,'ag-fleet')
        agent.configuration={'capability_stats':{action:{'success':50,'total':50,'verified_success':50}},'capability_maturities':{action:'autonomous'}}
        db.commit();assert CapabilityGraduationService(db).record_usage('ag-fleet',action,False,'failed_verification') is True
    for index in range(20):
        _produce_verified_operation(world,child_execution_id='fresh-child',action_name=action,operation_id='fresh-epoch-proof-'+str(index))
    with world.Session() as db:
        assert _credit(db) is True
        cfg=db.get(AgentRegistry,'ag-fleet').configuration
        assert cfg['capability_maturities'][action]=='intern'
        assert action not in cfg.get('autonomy_revocations',{})
        assert _stats(db,action)['verified_success']==70
        db.add(AgentExecution(id='old-child',agent_id='ag-fleet',tenant_id=TENANT,workspace_id=WORKSPACE,status='completed'))
        db.add(ChainLink(id='late-old-link',chain_id='chain-credit',parent_agent_id='atom-fleet',child_agent_id='ag-fleet',task_description='late arrival of previously verified work',context_json={'domain':'finance'},result_json={'execution_id':'old-child','agent_id':'ag-fleet','status':'completed'},status='completed',link_order=1))
        db.commit()
        _credit(db)
        assert _stats(db,action)['verified_success']==70
        assert db.get(AgentRegistry,'ag-fleet').configuration['capability_maturities'][action]=='intern'
        assert _credit(db) is False


@pytest.mark.parametrize("baseline",[0,25])
def test_unknown_epoch_clock_is_not_evidence(store,baseline):
    from datetime import datetime,timezone,timedelta
    from core.contribution_credit import _pre_revocation
    _Session,db=store
    row=db.get(AgentRegistry,"agent-revocation-1");cfg=deepcopy(row.configuration)
    stats=cfg["capability_stats"]["canvas_edit"]
    stats["epoch_baseline_verified_success"]=baseline
    stats.pop("epoch_started_at",None)
    cfg.pop("autonomy_revocations",None)
    row.configuration=cfg;db.commit()
    before=_pre_revocation(db,row.id,"canvas_edit",datetime.now(timezone.utc))
    assert before[0] is True and before[1] is True
    assert CapabilityGraduationService(db).record_usage(row.id,"canvas_edit",True,"unverified") is True
    db.expire_all();new=db.get(AgentRegistry,row.id).configuration["capability_stats"]["canvas_edit"]
    assert new["verified_success"]==25
    assert new["epoch_time_origin"]=="legacy_first_observed"
    anchor=datetime.fromisoformat(new["epoch_started_at"])
    assert _pre_revocation(db,row.id,"canvas_edit",anchor-timedelta(seconds=1))[0] is True
    assert _pre_revocation(db,row.id,"canvas_edit",anchor+timedelta(seconds=1))[0] is False


@pytest.mark.parametrize("value",[
    "2026-11-08T12:00:00Z",
    "2026-11-08T07:00:00-05:00",
    "2026-11-08 12:00:00",
    "2026-11-08T13:00:00+01:00",
])
def test_epoch_clock_normalizes_server_timestamp_strings(value):
    from datetime import datetime,timezone
    from core.contribution_credit import _parse_time
    assert _parse_time(value)==datetime(2026,11,8,12,tzinfo=timezone.utc)


def test_epoch_clock_normalizes_sqlite_naive_datetime():
    from datetime import datetime,timezone
    from core.contribution_credit import _parse_time
    assert _parse_time(datetime(2026,11,8,12))==datetime(2026,11,8,12,tzinfo=timezone.utc)


@pytest.mark.parametrize("value",[None,"","not-a-time","2026-11-08"])
def test_incomplete_epoch_clock_is_unknown(value):
    from core.contribution_credit import _parse_time
    assert _parse_time(value) is None


@pytest.mark.parametrize("mutation",["bool_version","unknown_version","missing_version","missing_dispatch","missing_verification","reversed"])
def test_versioned_verification_clock_cannot_fall_back_to_legacy(fleet_world,monkeypatch,mutation):
    from core.models import TaskOperationRecord
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED","true")
    action="canvas.clock_schema."+uuid.uuid4().hex;child="clock-child"
    _produce_verified_operation(fleet_world,child_execution_id=child,action_name=action,operation_id="clock-effect")
    _seed_fleet(fleet_world,child_executions=[(child,action)])
    with fleet_world.Session() as db:
        row=db.query(TaskOperationRecord).filter_by(run_id=child,operation_type="generic:agent:"+action).one()
        receipt=dict(row.result_json)
        assert receipt["verification_receipt_version"]==1
        if mutation=="bool_version":receipt["verification_receipt_version"]=True
        elif mutation=="unknown_version":receipt["verification_receipt_version"]=2
        elif mutation=="missing_version":receipt.pop("verification_receipt_version")
        elif mutation=="missing_dispatch":receipt.pop("dispatch_recorded_at")
        elif mutation=="missing_verification":receipt.pop("verification_recorded_at")
        else:receipt["dispatch_recorded_at"],receipt["verification_recorded_at"]=receipt["verification_recorded_at"],receipt["dispatch_recorded_at"]
        row.result_json=receipt;db.commit()
        _credit(db)
        assert _stats(db,action).get("verified_success",0)==0


def test_real_receipt_clock_is_ordered_by_server(fleet_world):
    from datetime import datetime,timezone
    from core.models import TaskOperationRecord
    from core.contribution_credit import _parse_time
    action="canvas.clock_positive."+uuid.uuid4().hex;before=datetime.now(timezone.utc)
    _produce_verified_operation(fleet_world,child_execution_id="clock-real",action_name=action,operation_id="clock-real-effect")
    after=datetime.now(timezone.utc)
    with fleet_world.Session() as db:
        receipt=db.query(TaskOperationRecord).filter_by(run_id="clock-real",operation_type="generic:agent:"+action).one().result_json
        assert type(receipt["verification_receipt_version"]) is int
        assert before<=_parse_time(receipt["dispatch_recorded_at"])<=_parse_time(receipt["verification_recorded_at"])<=after
