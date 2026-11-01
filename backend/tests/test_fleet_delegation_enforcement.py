"""Delegation depth, cycles, scope and single-accountability enforcement."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.agent_fleet_service import AgentFleetService, FleetDelegationError
from core.database import Base
from core.fleet_orchestration.delegation_contracts import (
    ContractError, build_contract, validate_contract_payload,
)
from core.models import AgentRegistry, DelegationChain


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _agent(db, agent_id, *, tenant="t1", workspace="w1"):
    row = AgentRegistry(
        id=agent_id, name=agent_id, category="test",
        module_path="test.module", class_name="TestAgent",
        tenant_id=tenant, workspace_id=workspace,
    )
    db.add(row)
    db.commit()
    return row


@pytest.fixture()
def fleet(db):
    for agent_id in ("root", "a", "b", "c", "d", "e", "f"):
        _agent(db, agent_id)
    _agent(db, "other", tenant="t2", workspace="w2")
    service = AgentFleetService(db)
    chain = service.initialize_fleet("t1", "root", "test chain")
    chain.max_depth = 2
    db.commit()
    return service, chain


def _contract(accountable="root", **over):
    payload = {
        "objective": "summarize the quote",
        "output_format": "markdown",
        "tool_guidance": [],
        "task_boundaries": "only this task",
        "effort_budget": {"max_steps": 3, "max_tool_calls": 5},
        "accountable_agent_id": accountable,
    }
    payload.update(over)
    return payload


def test_nesting_beyond_max_depth_is_refused(fleet):
    service, chain = fleet
    service.recruit_member(chain.id, "root", "a", "depth 1")
    service.recruit_member(chain.id, "a", "b", "depth 2")
    with pytest.raises(FleetDelegationError) as exc:
        service.recruit_member(chain.id, "b", "c", "depth 3")
    assert exc.value.code == "depth_exceeded"
    assert exc.value.extra == {"depth": 3, "max_depth": 2}
    assert service.db.query(DelegationChain).filter(
        DelegationChain.id == chain.id).first().total_links == 2


def test_wide_shallow_chain_is_allowed(fleet):
    service, chain = fleet
    for index, child in enumerate(("a", "b", "c", "d", "e", "f")):
        service.recruit_member(
            chain.id, "root", child, f"parallel {index}", link_order=index)
    assert service.db.query(DelegationChain).filter(
        DelegationChain.id == chain.id).first().total_links == 6


def test_cycles_are_refused(fleet):
    service, chain = fleet
    with pytest.raises(FleetDelegationError) as self_cycle:
        service.recruit_member(chain.id, "root", "root", "self")
    assert self_cycle.value.code == "delegation_cycle"

    service.recruit_member(chain.id, "root", "a", "depth 1")
    service.recruit_member(chain.id, "a", "b", "depth 2")
    with pytest.raises(FleetDelegationError) as back_edge:
        service.recruit_member(chain.id, "b", "a", "back edge")
    assert back_edge.value.code == "delegation_cycle"


def test_cross_scope_child_is_refused(fleet):
    service, chain = fleet
    with pytest.raises(FleetDelegationError) as exc:
        service.recruit_member(chain.id, "root", "other", "other tenant")
    assert exc.value.code == "cross_scope"


def test_unknown_parent_is_refused(fleet):
    service, chain = fleet
    with pytest.raises(FleetDelegationError) as exc:
        service.recruit_member(chain.id, "not-in-chain", "a", "orphan")
    assert exc.value.code == "unknown_parent"


def test_contract_with_exactly_one_accountable_agent_is_accepted(fleet):
    service, chain = fleet
    link = service.recruit_member(
        chain.id, "root", "a", "with contract",
        context_json={"delegation_contract": _contract()})
    assert link.context_json["delegation_contract"]["accountable_agent_id"] == "root"


@pytest.mark.parametrize("payload,code", [
    (_contract(accountable=""), "invalid_contract"),
    (_contract(accountable=["root", "a"]), "invalid_contract"),
    ({**_contract(), "accountable_agent_id": None,
      "accountable_agent_ids": ["root", "a"]}, "invalid_contract"),
])
def test_invalid_contracts_fail_before_the_link_exists(fleet, payload, code):
    service, chain = fleet
    with pytest.raises(FleetDelegationError) as exc:
        service.recruit_member(
            chain.id, "root", "a", "bad contract",
            context_json={"delegation_contract": payload})
    assert exc.value.code == code
    assert service.db.query(DelegationChain).filter(
        DelegationChain.id == chain.id).first().total_links == 0


def test_contract_validator_reports_the_reason():
    with pytest.raises(ContractError) as missing:
        validate_contract_payload(_contract(accountable=""))
    assert missing.value.code == "accountable_missing"

    with pytest.raises(ContractError) as many:
        validate_contract_payload({**_contract(), "accountable_agent_ids": ["a", "b"]})
    assert many.value.code == "accountable_count"


def test_build_contract_requires_one_accountable_agent():
    contract = build_contract(
        goal="goal", task_desc="task", domain="sales",
        accountable_agent_id="root")
    assert contract.accountable_agent_id == "root"
    with pytest.raises(ContractError):
        build_contract(
            goal="goal", task_desc="task", domain="sales",
            accountable_agent_id="")


def test_cycle_is_refused_with_multiple_parents_in_the_graph(fleet):
    """Exact report: root->a, root->b, a->b, then b->a must be refused.

    b already has two parents (root and a); a one-parent map sees only the
    first edge and misses the a->b path that the new b->a edge would close.
    """
    service, chain = fleet
    chain.max_depth = 10
    service.db.commit()
    service.recruit_member(chain.id, "root", "a", "1")
    service.recruit_member(chain.id, "root", "b", "2")
    service.recruit_member(chain.id, "a", "b", "3")
    with pytest.raises(FleetDelegationError) as exc:
        service.recruit_member(chain.id, "b", "a", "4")
    assert exc.value.code == "delegation_cycle"


def test_depth_uses_the_longest_dag_path_not_the_shortest(fleet):
    """root->a, root->b, a->b: b is depth 2 even though root->b is depth 1."""
    service, chain = fleet
    chain.max_depth = 2
    service.db.commit()
    service.recruit_member(chain.id, "root", "a", "1")
    service.recruit_member(chain.id, "root", "b", "2")
    service.recruit_member(chain.id, "a", "b", "3")
    with pytest.raises(FleetDelegationError) as exc:
        service.recruit_member(chain.id, "b", "c", "4")
    assert exc.value.code == "depth_exceeded"
    assert exc.value.extra == {"depth": 3, "max_depth": 2}
