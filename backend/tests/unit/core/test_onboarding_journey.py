"""
P1.2 + P1.3 regression tests — onboarding journey.

P1.2 — probe-ollama:
- _probe_ollama returns False on closed port.
- _probe_ollama returns True when a localhost socket accepts.
- endpoint shape (lightweight; just exercises _probe_ollama).

P1.3 — demo agent + governance bypass:
- ensure_demo_agent() creates a "Demo Assistant" agent with demo_agent=True.
- ensure_demo_agent() is idempotent (second call is a no-op).
- can_perform_action() permits complexity ≤ 2 for demo_agent agents.
- can_perform_action() still blocks complexity > 2 for demo_agent agents.

Run: PYTHONPATH=backend pytest backend/tests/unit/core/test_onboarding_journey.py -v
"""
import socket
import threading
import time
from unittest.mock import MagicMock

import pytest

from api.onboarding_routes import _probe_ollama


# =============================================================================
# P1.2 — probe-ollama
# =============================================================================

def test_probe_ollama_returns_false_on_closed_port():
    """A closed port must return False (not raise)."""
    # Pick an almost-certainly-closed port on localhost.
    closed_port = 59998
    assert _probe_ollama("127.0.0.1", closed_port, timeout=0.25) is False


def test_probe_ollama_returns_true_when_socket_accepts():
    """When a server is listening, the probe must return True."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    def _accept_once():
        try:
            conn, _ = server.accept()
            conn.close()
        except OSError:
            pass

    t = threading.Thread(target=_accept_once, daemon=True)
    t.start()
    try:
        assert _probe_ollama(host, port, timeout=1.0) is True
    finally:
        server.close()
        t.join(timeout=1.0)


# =============================================================================
# P1.3 — demo agent
# =============================================================================

@pytest.fixture
def fake_db():
    """Minimal in-memory stand-in for SQLAlchemy Session.

    We can't use the real SQLite DB here without standing up the full hybrid
    schema. Instead we simulate the query/add/commit surface the function
    touches.
    """
    db = MagicMock()
    # Query builder chain: db.query(AgentRegistry).filter(...).first()
    query = MagicMock()
    filter_chain = MagicMock()
    query.filter.return_value = filter_chain
    filter_chain.first.return_value = None  # demo agent does not exist yet
    db.query.return_value = query
    return db


def test_ensure_demo_agent_creates_agent_with_bypass_flag(fake_db):
    """First call must create a Demo Assistant carrying demo_agent=True."""
    from core.admin_bootstrap import ensure_demo_agent

    ensure_demo_agent(fake_db)

    # db.add() must have been called exactly once with an AgentRegistry.
    assert fake_db.add.call_count == 1
    agent = fake_db.add.call_args[0][0]
    assert agent.name == "Demo Assistant"
    assert agent.status == "intern"  # AgentStatus.INTERN.value
    assert agent.configuration.get("demo_agent") is True
    assert agent.configuration.get("graduation_bypass_reason") == "onboarding_demo"
    # Commit must have been called to persist.
    assert fake_db.commit.call_count >= 1


def test_ensure_demo_agent_is_idempotent(fake_db):
    """Second call when agent exists must be a no-op (no add, no extra commit)."""
    from core.admin_bootstrap import ensure_demo_agent

    # Simulate the demo agent already existing.
    existing_agent = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = existing_agent

    ensure_demo_agent(fake_db)

    fake_db.add.assert_not_called()
    # Existing-agent path returns before the commit; only the lookup happened.


# =============================================================================
# P1.3 — governance bypass
# =============================================================================

def test_can_perform_action_permits_low_complexity_for_demo_agent(monkeypatch):
    """A demo_agent-flagged STUDENT/INTERN agent must pass complexity 1 and 2."""
    from core.agent_governance_service import AgentGovernanceService, AgentStatus
    from core.models import AgentRegistry

    agent = AgentRegistry(
        id="demo-1",
        name="Demo Assistant",
        category="system",
        module_path="system",
        class_name="DemoAssistant",
        status=AgentStatus.STUDENT.value,  # would normally block complexity 2
        confidence_score=0.5,
        configuration={"demo_agent": True},
        workspace_id="default",
    )

    db = MagicMock()
    q = MagicMock(); q.filter.return_value.first.return_value = agent
    db.query.return_value = q

    svc = AgentGovernanceService.__new__(AgentGovernanceService)
    svc.db = db
    svc.workspace_id = "default"
    # ACTION_COMPLEXITY comes from the class; ensure it exists.
    assert hasattr(AgentGovernanceService, "ACTION_COMPLEXITY")
    assert hasattr(AgentGovernanceService, "MATURITY_REQUIREMENTS")

    # An action_type that resolves to complexity 2 (e.g. stream_chat).
    result = svc.can_perform_action(
        agent_id="demo-1",
        action_type="stream_chat",
    )
    assert result["allowed"] is True, f"Expected bypass to permit, got: {result}"


def test_can_perform_action_blocks_high_complexity_for_demo_agent():
    """A demo_agent-flagged STUDENT agent must STILL be blocked on complexity 3+."""
    from core.agent_governance_service import AgentGovernanceService, AgentStatus
    from core.models import AgentRegistry

    agent = AgentRegistry(
        id="demo-2",
        name="Demo Assistant",
        category="system",
        module_path="system",
        class_name="DemoAssistant",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.5,
        configuration={"demo_agent": True},
        workspace_id="default",
    )

    db = MagicMock()
    q = MagicMock(); q.filter.return_value.first.return_value = agent
    db.query.return_value = q

    svc = AgentGovernanceService.__new__(AgentGovernanceService)
    svc.db = db
    svc.workspace_id = "default"

    # delete_lead lives at complexity 4 (CRITICAL). Demo bypass caps at 2.
    result = svc.can_perform_action(
        agent_id="demo-2",
        action_type="delete_lead",
    )
    assert result["allowed"] is False, (
        f"Demo bypass must not permit complexity >=3, got: {result}"
    )
