"""Failure-first consumer diagnostics; not a verified-result qualification.

Completed synthetic links have no authoritative verifier receipt. A real
verified-result producer/positive twin is still required before accepting a fix.
"""
from copy import deepcopy

from sqlalchemy.orm import sessionmaker

from core.contribution_credit import compute_chain_credit, record_chain_credit
from core.models import (
    AgentExecution,
    AgentRegistry,
    DelegationChain,
    FleetRoutingAudit,
)
from tests.test_contribution_credit_p4 import chain_db, _seed_fleet


def _completed_without_verifier(db):
    _seed_fleet(db, link_statuses=["completed"])
    audit = db.query(FleetRoutingAudit).filter_by(execution_id="exec-9").one()
    audit.tenant_id = "t1"
    audit.workspace_id = "w1"
    audit.agent_id = "atom_main"
    audit.success = True
    audit.enforced = True
    audit.decision_source = "fleet_eligible"
    if db.get(AgentExecution, "exec-9") is None:
        db.add(AgentExecution(
            id="exec-9", agent_id="atom_main", tenant_id="t1",
            workspace_id="w1", status="completed"))
    chain = db.query(DelegationChain).filter_by(id="chain-1").one()
    chain.status = "completed"
    chain.metadata_json = {"workspace_id": "w1"}
    for agent in db.query(AgentRegistry).all():
        agent.tenant_id = "t1"
        agent.workspace_id = "w1"
    db.commit()


def _stats(db):
    db.expire_all()
    agent = db.query(AgentRegistry).filter_by(id="ag-x").one()
    return deepcopy((agent.configuration or {}).get("capability_stats", {}).get("finance", {}))


def test_completed_status_and_weight_do_not_create_verified_evidence(chain_db, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    _completed_without_verifier(chain_db)
    record_chain_credit("exec-9", db=chain_db)
    assert int(_stats(chain_db).get("verified_success", 0)) == 0


def test_same_chain_credit_replay_does_not_add_more_usage(chain_db, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "true")
    _completed_without_verifier(chain_db)
    record_chain_credit("exec-9", db=chain_db)
    before = _stats(chain_db)
    Session = sessionmaker(bind=chain_db.get_bind())
    chain_db.close()
    with Session() as fresh:
        record_chain_credit("exec-9", db=fresh)
        after = _stats(fresh)
    assert {k: after.get(k, 0) for k in ("total", "success", "verified_success")} == {
        k: before.get(k, 0) for k in ("total", "success", "verified_success")}


def test_disabled_feature_still_has_no_effect(chain_db, monkeypatch):
    monkeypatch.setenv("ATOM_CONTRIBUTION_CREDIT_ENABLED", "false")
    _completed_without_verifier(chain_db)
    assert record_chain_credit("exec-9", db=chain_db) is False
    assert _stats(chain_db) == {}


def test_contribution_weights_are_not_the_verification_authority():
    # Preserve the existing math while testing its downstream interpretation.
    assert compute_chain_credit([{"agent_id": "a", "status": "completed"}]) == {"a": 1.0}
