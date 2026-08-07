"""TDD bug-hunt: ScalingOperation ORM model (R80 follow-up).

``FleetScalerService._persist_operation`` / ``_get_recent_operations`` import
``core.models.ScalingOperation`` which does not exist — the persist path
swallows the ImportError and fleet scaling operations are never recorded
(no audit trail, no recent-operations view).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db():
    from core.database import Base
    import core.fleet_orchestration.fleet_scaler_service  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_scaling_operation_model_exists_and_round_trips(db):
    from core.models import ScalingOperation

    row = ScalingOperation(
        id="op-1",
        chain_id="chain-1",
        proposal_id="prop-1",
        operation_type="expand",
        from_size=2,
        to_size=4,
        agents_added=["agent-3", "agent-4"],
        agents_removed=[],
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        error_message=None,
        metadata_json={"reason": "load spike"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    assert row.id == "op-1"
    assert row.chain_id == "chain-1"
    assert row.agents_added == ["agent-3", "agent-4"]


@pytest.mark.asyncio
async def test_fleet_scaler_persists_and_reads_operations(db):
    from core.fleet_orchestration.fleet_scaler_service import (
        FleetScalerService,
        ScalingOperation,
        ScalingOperationStatus,
    )

    scaler = FleetScalerService(db=db)

    op = ScalingOperation(
        id="op-2",
        chain_id="chain-9",
        proposal_id="prop-9",
        operation_type="expand",
        from_size=1,
        to_size=3,
        agents_added=["agent-a"],
        agents_removed=[],
        status=ScalingOperationStatus.COMPLETED,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        metadata={"reason": "growth"},
    )
    await scaler._persist_operation(op)

    recent = await scaler._get_recent_operations("chain-9", limit=5)

    assert len(recent) == 1
    assert recent[0].id == "op-2"
    assert recent[0].agents_added == ["agent-a"]
    assert recent[0].status == ScalingOperationStatus.COMPLETED
