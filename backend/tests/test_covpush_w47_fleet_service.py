"""Coverage wave 47 — core/agent_fleet_service (20% → 95%+).

- initialize_fleet (creates chain with metadata + started_at)
- recruit_member (link creation, context merge with optimization, total_links
  increment)
- update_blackboard (found + missing chain)
- get_blackboard (found + missing)
- update_link_status (missing link, completed duration calc, error/result
  capture, self-heal trigger)
- complete_chain (found + missing)
"""
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.agent_fleet_service import AgentFleetService
from core.database import Base
from core.models import AgentRegistry, ChainLink, DelegationChain


@pytest.fixture
def fresh_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    os.unlink(path)


@pytest.fixture
def svc(fresh_db):
    return AgentFleetService(fresh_db)


def _agent(db, agent_id=None):
    a = AgentRegistry(
        id=agent_id or f"agent-{uuid.uuid4().hex[:8]}",
        name="A", category="general", description="d",
        status="SUPERVISED", confidence_score=0.7,
        module_path="m", class_name="C", workspace_id="default",
    )
    db.add(a)
    db.commit()
    return a


class TestFleetLifecycle:
    def test_initialize_fleet(self, svc, fresh_db):
        root = _agent(fresh_db)
        chain = svc.initialize_fleet(
            tenant_id="t1", root_agent_id=root.id, root_task="Reconcile",
            root_execution_id="ex-1", initial_metadata={"phase": "start"},
        )
        assert chain.id
        assert chain.status == "active"
        assert chain.root_task == "Reconcile"
        assert chain.metadata_json == {"phase": "start"}
        assert chain.started_at is not None

    def test_recruit_member(self, svc, fresh_db):
        root = _agent(fresh_db)
        child = _agent(fresh_db)
        chain = svc.initialize_fleet("t1", root.id, "Task")
        link = svc.recruit_member(
            chain_id=chain.id, parent_agent_id=root.id, child_agent_id=child.id,
            task_description="sub", context_json={"domain": "finance"},
            link_order=1, optimization_metadata={"premium": True},
        )
        assert link.status == "pending"
        assert link.context_json["domain"] == "finance"
        assert link.context_json["optimization"] == {"premium": True}
        fresh_db.refresh(chain)
        assert chain.total_links == 1

    def test_recruit_member_no_context(self, svc, fresh_db):
        root = _agent(fresh_db)
        child = _agent(fresh_db)
        chain = svc.initialize_fleet("t1", root.id, "Task")
        link = svc.recruit_member(
            chain_id=chain.id, parent_agent_id=root.id, child_agent_id=child.id,
            task_description="sub",
        )
        assert link.context_json == {}

    def test_recruit_member_missing_chain(self, svc, fresh_db):
        root = _agent(fresh_db)
        child = _agent(fresh_db)
        link = svc.recruit_member(
            chain_id="missing", parent_agent_id=root.id, child_agent_id=child.id,
            task_description="sub",
        )
        assert link.id


class TestBlackboard:
    def test_update_blackboard(self, svc, fresh_db):
        root = _agent(fresh_db)
        chain = svc.initialize_fleet("t1", root.id, "Task")
        svc.update_blackboard(chain.id, {"status": "running", "note": "x"})
        fresh_db.refresh(chain)
        assert chain.metadata_json["status"] == "running"

    def test_update_blackboard_missing(self, svc):
        svc.update_blackboard("missing", {"a": 1})  # no raise

    def test_get_blackboard(self, svc, fresh_db):
        root = _agent(fresh_db)
        chain = svc.initialize_fleet("t1", root.id, "Task")
        svc.update_blackboard(chain.id, {"phase": "2"})
        assert svc.get_blackboard(chain.id)["phase"] == "2"

    def test_get_blackboard_missing(self, svc):
        assert svc.get_blackboard("missing") == {}


class TestLinkStatus:
    def test_update_link_status_completed(self, svc, fresh_db):
        root = _agent(fresh_db)
        child = _agent(fresh_db)
        chain = svc.initialize_fleet("t1", root.id, "Task")
        link = svc.recruit_member(chain.id, root.id, child.id, "sub")
        link.started_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        fresh_db.commit()
        with patch("core.fleet.self_heal_service.SelfHealService") as shs:
            shs.return_value.process_link_update = MagicMock()
            svc.update_link_status(link.id, "completed", result={"ok": True})
        fresh_db.refresh(link)
        assert link.status == "completed"
        assert link.result_json == {"ok": True}
        assert link.completed_at is not None
        assert link.duration_ms >= 4000
        shs.assert_called_once()

    def test_update_link_status_failed_with_error(self, svc, fresh_db):
        root = _agent(fresh_db)
        child = _agent(fresh_db)
        chain = svc.initialize_fleet("t1", root.id, "Task")
        link = svc.recruit_member(chain.id, root.id, child.id, "sub")
        with patch("core.fleet.self_heal_service.SelfHealService") as shs:
            shs.return_value.process_link_update = MagicMock()
            svc.update_link_status(link.id, "failed", error="boom")
        fresh_db.refresh(link)
        assert link.error_message == "boom"
        assert link.completed_at is not None

    def test_update_link_status_missing(self, svc):
        svc.update_link_status("missing", "completed")  # no raise

    def test_update_link_status_self_heal_failure(self, svc, fresh_db):
        root = _agent(fresh_db)
        child = _agent(fresh_db)
        chain = svc.initialize_fleet("t1", root.id, "Task")
        link = svc.recruit_member(chain.id, root.id, child.id, "sub")
        with patch("core.fleet.self_heal_service.SelfHealService",
                   side_effect=RuntimeError("heal down")):
            svc.update_link_status(link.id, "completed")
        fresh_db.refresh(link)
        assert link.status == "completed"  # status still updated


class TestCompleteChain:
    def test_complete_chain(self, svc, fresh_db):
        root = _agent(fresh_db)
        chain = svc.initialize_fleet("t1", root.id, "Task")
        svc.complete_chain(chain.id, "failed")
        fresh_db.refresh(chain)
        assert chain.status == "failed"
        assert chain.completed_at is not None

    def test_complete_chain_missing(self, svc):
        svc.complete_chain("missing")  # no raise
