"""Integrated ORCH-07 outcome/scope/provenance contracts (verifier 19-batch)."""
import pytest
from sqlalchemy import event, update
from core.models import AgentExecution, FleetRoutingAudit
import core.fleet_orchestration.fleet_routing_stats as stats
from tests.test_orch07_fleet_audit_consumer import env,TENANT,WORKSPACE,REQUEST

def seed(env,execution='exec-probe'):
    env.add_execution(execution)
    audit=stats.record_fleet_decision(execution_id=execution,tenant_id=TENANT,workspace_id=WORKSPACE,agent_id='atom_main',request=REQUEST,recruitment_succeeded=True)
    assert audit
    return audit

@pytest.mark.parametrize('peer_change',['outcome','workspace'])
def test_outcome_write_is_atomic_against_competing_writer(env,peer_change):
    audit=seed(env);fired=[]
    def before_sql(conn,cursor,statement,parameters,context,many):
        if fired or not statement.lstrip().upper().startswith('UPDATE') or 'fleet_routing_audit' not in statement:return
        fired.append(True)
        with env.engine.begin() as peer:
            if peer_change=='outcome':peer.execute(update(FleetRoutingAudit).where(FleetRoutingAudit.id==audit).values(success=False,error='peer-authoritative',actual_model='peer-model',actual_provider='peer-provider'))
            else:peer.execute(update(AgentExecution).where(AgentExecution.id=='exec-probe').values(workspace_id='moved-workspace'))
    event.listen(env.engine,'before_cursor_execute',before_sql)
    try:result=stats.record_fleet_execution_outcome('exec-probe',True,audit_id=audit,tenant_id=TENANT,workspace_id=WORKSPACE,actual_model='stale-model',actual_provider='stale-provider')
    finally:event.remove(env.engine,'before_cursor_execute',before_sql)
    assert fired
    row=env.row_for('exec-probe')
    if peer_change=='outcome':assert row.success is False and row.actual_model=='peer-model' and result['status']=='conflict',(row.success,row.actual_model,result)
    else:assert row.success is None and result['status'] in ('conflict','scope_conflict'),(row.success,result)

def test_missing_execution_agent_is_not_caller_authority(env):
    env.add_execution('exec-no-agent')
    with env.Session() as db:
        db.execute(update(AgentExecution).where(AgentExecution.id=='exec-no-agent').values(agent_id=None));db.commit()
    audit=stats.record_fleet_decision(execution_id='exec-no-agent',tenant_id=TENANT,workspace_id=WORKSPACE,agent_id='caller-invented-agent',request=REQUEST)
    row=env.row_for('exec-no-agent')
    result=stats.record_fleet_execution_outcome('exec-no-agent',True,audit_id=audit)
    assert row.decision_source=='scope_unverified' and row.agent_id is None and result['status']!='applied',(row.decision_source,row.agent_id,result)

def test_changed_execution_agent_cannot_certify_old_decision(env):
    audit=seed(env)
    with env.Session() as db:
        db.execute(update(AgentExecution).where(AgentExecution.id=='exec-probe').values(agent_id='different-agent'));db.commit()
    result=stats.record_fleet_execution_outcome('exec-probe',True,audit_id=audit)
    assert env.row_for('exec-probe').success is None and result['status']=='conflict',result

def test_same_boolean_different_outcome_material_is_not_exact_replay(env):
    audit=seed(env)
    first=stats.record_fleet_execution_outcome('exec-probe',False,audit_id=audit,error_message='first-error',actual_model='first-model',actual_provider='first-provider')
    assert first['status']=='applied'
    second=stats.record_fleet_execution_outcome('exec-probe',False,audit_id=audit,error_message='different-error',actual_model='different-model',actual_provider='different-provider')
    assert second['status']=='conflict',second

def test_explicit_unverified_rows_never_count_for_calibration(env):
    with env.Session() as db:
        db.add(FleetRoutingAudit(id='unverified-outcome',execution_id='unknown-execution',tenant_id=TENANT,workspace_id=WORKSPACE,agent_id=None,workload_key=stats.workload_key_for(REQUEST),request_text=REQUEST,decision_source='scope_unverified',success=True,recruitment_succeeded=True,enforced=True));db.commit()
        workloads=stats._workload_stats(db);health=stats._aggregate_recruitment_health(db)
    assert sum(item['n'] for item in workloads.values())==0 and health['recruit_attempts']==0,(workloads,health)

def test_old_handler_route_does_not_certify_current_unserved_call(env):
    env.agent.llm.handler._last_used_model='earlier-model'
    env.agent.llm.handler._last_used_provider='earlier-provider'
    result=env.run(enforced=False,served=False)
    row=env.row_for(result['execution_id'])
    assert row.actual_model is None and row.actual_provider is None,(row.actual_model,row.actual_provider)
