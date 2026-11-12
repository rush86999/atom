"""Durable fleet blackboard regression tests.

Isolated SQLite only: no live database, provider, or network access.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agent_fleet_service import AgentFleetService
from core.database import Base
from core.fleet_admiral import FleetAdmiral, TaskAnalysis
from core.models import DelegationChain

CHAIN = "chain-blackboard"


@pytest.fixture()
def scratch(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/blackboard.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield engine, Session
    finally:
        engine.dispose()


def _seed_chain(Session) -> None:
    db = Session()
    try:
        db.add(DelegationChain(
            id=CHAIN,
            tenant_id="tenant-blackboard",
            root_agent_id="root-blackboard",
            root_task="Draft the operations checklist",
            status="active",
            metadata_json={"workspace_id": "workspace-blackboard",
                           "phase": "in_progress"},
        ))
        db.commit()
    finally:
        db.close()


def test_update_blackboard_is_visible_to_a_fresh_session(scratch):
    """In-place JSON mutation used to emit no UPDATE and silently vanish."""
    _engine, Session = scratch
    _seed_chain(Session)

    writer = Session()
    try:
        AgentFleetService(writer).update_blackboard(CHAIN, {
            "recruitment_phase": "complete",
            "recruitment_plan": {"domain_rationale": {
                "operations": "the goal asks for a checklist"}},
        })
    finally:
        writer.close()

    fresh = Session()
    try:
        metadata = fresh.query(DelegationChain).filter(
            DelegationChain.id == CHAIN).one().metadata_json
    finally:
        fresh.close()

    assert metadata["phase"] == "in_progress"  # pre-existing key preserved
    assert metadata["recruitment_phase"] == "complete"
    assert metadata["recruitment_plan"]["domain_rationale"] == {
        "operations": "the goal asks for a checklist"}


@pytest.mark.asyncio
async def test_fleet_admiral_persists_allowlisted_decision_evidence(scratch):
    _engine, Session = scratch
    db = Session()
    try:
        admiral = FleetAdmiral(db=db, llm=Mock())
        admiral.llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="medium",
                required_capabilities=["operations"],
                estimated_duration="30 minutes",
                specialist_count=1,
                reasoning="one operations specialist",
            ))
        admiral.recruitment_intelligence = Mock()
        admiral.recruitment_intelligence.orchestrate_recruitment = AsyncMock(
            return_value={
                "success": True,
                "recruitment_plan": {
                    "goal_analysis": "checklist work",
                    "required_domains": ["operations"],
                    "domain_rationale": {
                        "operations": "the goal asks for a checklist"},
                    "complexity_estimate": "medium",
                    "estimated_parallelizable": False,
                    "suggested_specialist_count": 1,
                    "unexpected_model_field": "must not persist",
                },
                "recruitment_roster": [{
                    "agent_id": "ops-agent",
                    "agent_name": "Ops Specialist",
                    "domain": "operations",
                    "capability_score": 0.91,
                    "optimization": {"tier": "premium"},
                    "unexpected_model_field": "must not persist",
                }],
            })

        result = await admiral.recruit_and_execute(
            task="Draft the operations checklist",
            user_id="user-blackboard",
            tenant_id="tenant-blackboard",
            workspace_id="workspace-blackboard",
        )
        chain_id = result["chain_id"]
    finally:
        db.close()

    assert "recruitment_plan" not in result  # baseline caller contract

    fresh = Session()
    try:
        metadata = fresh.query(DelegationChain).filter(
            DelegationChain.id == chain_id).one().metadata_json
    finally:
        fresh.close()

    assert metadata["workspace_id"] == "workspace-blackboard"
    assert metadata["recruitment_phase"] == "complete"
    assert metadata["recruitment_plan"]["domain_rationale"] == {
        "operations": "the goal asks for a checklist"}
    assert "unexpected_model_field" not in metadata["recruitment_plan"]
    assert metadata["recruitment_roster"] == [{
        "agent_id": "ops-agent",
        "agent_name": "Ops Specialist",
        "domain": "operations",
        "capability_score": 0.91,
    }]
    assert metadata["specialists_recruited"] == [{
        "agent_id": "ops-agent",
        "agent_name": "Ops Specialist",
        "domain": "operations",
    }]
