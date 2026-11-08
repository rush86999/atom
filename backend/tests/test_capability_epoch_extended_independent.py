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
