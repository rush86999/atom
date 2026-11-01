"""One reusable isolated acceptance world.

File-backed SQLite with foreign keys ON, explicit tenant/workspace/user/agent
rows, a replaceable session factory, an observable controlled-effect ledger and
simple fault-injection points. New acceptance tests should use this instead of
growing another local fixture.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from core.database import Base
from core.models import AgentRegistry, Tenant, User, Workspace


class EffectLedger:
    """Observable controlled effects: one row per attempted action."""

    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    def record(self, action: str, **fields: Any) -> int:
        self.rows.append({"action": action, **fields})
        return len(self.rows)

    def count(self, action: Optional[str] = None) -> int:
        if action is None:
            return len(self.rows)
        return sum(1 for row in self.rows if row["action"] == action)


class FaultInjector:
    """Deterministic failure points (armed per test, never global)."""

    def __init__(self) -> None:
        self._armed: Dict[str, BaseException] = {}

    def arm(self, point: str, error: Optional[BaseException] = None) -> None:
        self._armed[point] = error or RuntimeError(f"injected: {point}")

    def check(self, point: str) -> None:
        if point in self._armed:
            raise self._armed[point]

    def disarm(self, point: str) -> None:
        self._armed.pop(point, None)


@dataclass
class World:
    engine: Any
    Session: Any
    session: Any
    ledger: EffectLedger = field(default_factory=EffectLedger)
    faults: FaultInjector = field(default_factory=FaultInjector)
    tenant_id: str = "tenant-1"
    workspace_id: str = "ws-1"
    user_id: str = "user-1"
    agent_id: str = "agent-1"


@pytest.fixture()
def world(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'acceptance-world.db'}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Tenant(id="tenant-1", name="Tenant One", subdomain="tenant-one"))
    session.add(Workspace(id="ws-1", name="Workspace One", tenant_id="tenant-1"))
    session.add(User(
        id="user-1", email="user@example.invalid", first_name="User",
        last_name="One", role="workspace_admin", status="active",
    ))
    session.add(AgentRegistry(
        id="agent-1", name="Agent One", category="test",
        module_path="tests.acceptance", class_name="AcceptanceAgent",
        tenant_id="tenant-1", workspace_id="ws-1",
    ))
    session.commit()
    instance = World(engine=engine, Session=Session, session=session)
    try:
        yield instance
    finally:
        session.close()
        engine.dispose()
