"""
P1c — Real per-parent depth enforcement for DelegationChain.max_depth.

R1 (verified): the check at agent_governance_service.py:584 is
``len(chain.links) >= chain.max_depth`` — a TOTAL-link-count cap, not a
nesting-depth cap. So a flat chain of 3 siblings hits the limit the same
as a 3-deep nested chain, defeating the purpose of a recursion guard.

This suite verifies the fix: max_depth gates the maximum NESTING DEPTH
(root→A→B→C = depth 3), not the total link count (3 siblings = depth 1).

It also verifies the FK hazard (RN1): a ChainLink with a fake
child_agent_id (no matching AgentRegistry row) is caught — in SQLite that
requires PRAGMA foreign_keys=ON (the dev DB has it OFF by default), in
Postgres it's native.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import (
    AgentRegistry, AgentStatus, DelegationChain, ChainLink, User, Tenant,
    Workspace,
)


# ---------------------------------------------------------------------------
# Session with FK enforcement ON (RN1: required to demonstrate the constraint
# in SQLite; the dev DB has it off by default).
# ---------------------------------------------------------------------------
@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed_agent(db, agent_id, name=None):
    """Insert a real AgentRegistry row (so ChainLink FKs are satisfied)."""
    if not db.query(Workspace).filter(Workspace.id == "default").first():
        db.add(Workspace(id="default", name="Default Workspace"))
        db.commit()
    db.add(AgentRegistry(
        id=agent_id, name=name or agent_id,
        category="test", capabilities=[], status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.5, module_path="core.generic_agent", class_name="GenericAgent",
        workspace_id="default",  # AgentGovernanceService defaults to workspace "default"
    ))
    db.commit()


def _chain(db, *, chain_id="chain-1", max_depth=3, root_agent_id="root"):
    # DelegationChain.tenant_id is NOT NULL + FK to tenants.id; seed a tenant first.
    db.add(Tenant(id="tenant-1", name="t1", subdomain="t1"))
    db.commit()
    db.add(DelegationChain(
        id=chain_id, tenant_id="tenant-1",
        root_agent_id=root_agent_id, max_depth=max_depth,
    ))
    db.commit()
    return db.query(DelegationChain).get(chain_id)


def _link(db, *, chain, parent, child, order=0):
    db.add(ChainLink(
        chain_id=chain.id, parent_agent_id=parent, child_agent_id=child,
        task_description="t", status="completed", link_order=order,
    ))
    db.commit()


# ---------------------------------------------------------------------------
# 1. Depth, not count: a 3-deep NESTED chain blocks at max_depth=3.
# ---------------------------------------------------------------------------
def test_nested_depth_3_blocks_at_max_depth_3(db_session):
    from core.agent_governance_service import AgentGovernanceService

    for aid in ("root", "a", "b", "c"):
        _seed_agent(db_session, aid)
    chain = _chain(db_session, max_depth=3)
    # root → a → b → c  (depth 3)
    _link(db_session, chain=chain, parent="root", child="a", order=0)
    _link(db_session, chain=chain, parent="a", child="b", order=1)
    _link(db_session, chain=chain, parent="b", child="c", order=2)

    gov = AgentGovernanceService(db_session)
    decision = gov.can_perform_action("c", "recruit_specialist", chain_id=chain.id, _skip_budget=True)
    assert decision["allowed"] is False, "depth-3 chain must block further nesting at max_depth=3"
    assert decision["status_code"] == "RECURSION_LIMIT"


# ---------------------------------------------------------------------------
# 2. Depth, not count: a FLAT chain of 3 siblings (depth 1) does NOT block.
# ---------------------------------------------------------------------------
def test_flat_chain_3_siblings_does_not_block(db_session):
    from core.agent_governance_service import AgentGovernanceService

    for aid in ("root", "sib1", "sib2", "sib3"):
        _seed_agent(db_session, aid)
    chain = _chain(db_session, max_depth=3)
    # root → sib1, root → sib2, root → sib3  (all depth 1)
    for i, sib in enumerate(("sib1", "sib2", "sib3")):
        _link(db_session, chain=chain, parent="root", child=sib, order=i)

    gov = AgentGovernanceService(db_session)
    # Each sibling is at depth 1; max_depth=3 must allow further nesting.
    decision = gov.can_perform_action("sib1", "recruit_specialist", chain_id=chain.id, _skip_budget=True)
    assert decision.get("status_code") != "RECURSION_LIMIT", (
        "flat 3-sibling chain (depth 1) must NOT trip the depth-3 recursion limit "
        "— the bug counted total links (3) instead of depth (1)"
    )


# ---------------------------------------------------------------------------
# 3. FK hazard (RN1): a fake child_agent_id (no AgentRegistry row) is rejected
#    when FKs are ON.
# ---------------------------------------------------------------------------
def test_fake_child_agent_id_rejected_with_fk_on(db_session):
    _seed_agent(db_session, "root")
    chain = _chain(db_session, max_depth=5)
    # "ghost" has NO AgentRegistry row → FK violation (PRAGMA ON in this fixture).
    with pytest.raises(Exception):
        _link(db_session, chain=chain, parent="root", child="ghost-agent-deadbeef")


# ---------------------------------------------------------------------------
# 4. The division-hierarchy columns exist on AgentRegistry (migration applied).
# ---------------------------------------------------------------------------
def test_agent_registry_has_division_columns(db_session):
    cols = {c.name for c in AgentRegistry.__table__.columns}
    assert "division_id" in cols, "agent_registry must have division_id (P1c migration)"
    assert "parent_agent_id" in cols, "agent_registry must have parent_agent_id"
    assert "specialty" in cols, "agent_registry must have specialty"


def test_agent_divisions_table_exists(db_session):
    from core.models import Division
    assert Division.__tablename__ == "agent_divisions"
    cols = {c.name for c in Division.__table__.columns}
    # Core fields required by both the concurrent-agent and this workstream's schema.
    assert {"id", "name", "lead_agent_id", "parent_id", "domain"} <= cols
