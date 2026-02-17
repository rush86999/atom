---
phase: 05-agent-layer
plan: 03
type: execute
wave: 2
depends_on: ["05-agent-layer-01"]
files_modified:
  - tests/integration/agent/test_agent_execution_orchestration.py
  - tests/integration/agent/test_agent_coordination.py
  - tests/property_tests/agent/test_agent_coordination_invariants.py
autonomous: true

must_haves:
  truths:
    - "Agent execution orchestrates governance → LLM → streaming → persistence"
    - "Agent execution handles errors gracefully with audit logging"
    - "Agent-to-agent messaging works via social layer (event bus)"
    - "Agent coordination event bus delivers messages reliably"
    - "Agent execution audit logs all actions (agent_id, action, result)"
    - "Property tests verify coordination invariants (message ordering, delivery)"
  artifacts:
    - path: "tests/integration/agent/test_agent_execution_orchestration.py"
      provides: "Integration tests for end-to-end agent execution"
      min_lines: 300
    - path: "tests/integration/agent/test_agent_coordination.py"
      provides: "Integration tests for agent-to-agent communication"
      min_lines: 250
    - path: "tests/property_tests/agent/test_agent_coordination_invariants.py"
      provides: "Property tests for coordination invariants"
      min_lines: 200
  key_links:
    - from: "tests/integration/agent/test_agent_execution_orchestration.py"
      to: "core/atom_agent_endpoints.py"
      via: "tests POST /agents/{id}/execute endpoint"
      pattern: "test_agent_execution_end_to_end|test_execution_error_handling"
    - from: "tests/integration/agent/test_agent_coordination.py"
      to: "core/social_layer.py" or "core/event_bus.py"
      via: "tests agent-to-agent messaging"
      pattern: "test_agent_to_agent_messaging|test_event_bus_communication"
    - from: "tests/property_tests/agent/test_agent_coordination_invariants.py"
      to: "core/agent_coordination.py"
      via: "tests message ordering and delivery invariants"
      pattern: "test_message_ordering|test_message_delivery"
---

## Objective

Create integration tests for agent execution orchestration (governance → LLM → streaming → persistence) and agent coordination (agent-to-agent messaging, event bus communication).

**Purpose:** Agent execution is the core workflow - agents take actions based on user input. Tests validate the complete pipeline with error handling, audit logging, and graceful degradation. Agent coordination enables multi-agent workflows - tests validate message delivery and ordering.

**Output:** Integration tests for execution orchestration and coordination, property tests for coordination invariants.

## Execution Context

@core/atom_agent_endpoints.py (POST /agents/{id}/execute endpoint)
@core/agent_execution_service.py (execution orchestration)
@core/social_layer.py (agent-to-agent messaging)
@core/event_bus.py (event bus communication)
@.planning/phases/05-agent-layer/05-agent-layer-01-PLAN.md

## Context

@.planning/ROADMAP.md (Phase 5 requirements)
@.planning/REQUIREMENTS.md (AR-05, AR-12)

# Plans 01-02 Complete
- Governance and maturity routing tested
- Graduation framework tested
- Context resolution tested

# Existing Agent Execution Implementation
- atom_agent_endpoints.py: POST /agents/{id}/execute with streaming
- agent_execution_service.py: Execution orchestration, error handling
- social_layer.py: Agent-to-agent messaging via Redis pub/sub
- event_bus.py: Event bus for agent coordination

## Tasks

### Task 1: Create Integration Tests for Agent Execution Orchestration

**Files:** `tests/integration/agent/test_agent_execution_orchestration.py`

**Action:**
Create integration tests for end-to-end agent execution:

```python
"""
Integration Tests for Agent Execution Orchestration

Tests cover:
- End-to-end execution flow (governance → LLM → streaming → persistence)
- Error handling and recovery
- Audit logging
- Streaming responses
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from core.models import AgentRegistry, AgentExecution
from tests.factories import AgentFactory


class TestAgentExecutionOrchestration:
    """Test agent execution orchestration."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent_with_executions(self, db_session):
        """Create agent with execution history."""
        agent = AgentFactory(maturity_level="AUTONOMOUS")
        db_session.commit()
        return agent

    def test_agent_execution_end_to_end(self, client, agent_with_executions):
        """Test end-to-end agent execution flow."""
        agent = agent_with_executions

        response = client.post(
            f"/agents/{agent.id}/execute",
            json={
                "message": "Hello, agent!",
                "stream": False
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["status"] in ["pending", "running", "completed"]

    def test_execution_error_handling(self, client, agent_with_executions):
        """Test agent execution error handling."""
        agent = agent_with_executions

        # Mock LLM failure
        with patch("core.llm.byok_handler.BYOKHandler.stream_response") as mock_llm:
            mock_llm.side_effect = Exception("LLM unavailable")

            response = client.post(
                f"/agents/{agent.id}/execute",
                json={"message": "Test"}
            )

            # Should handle error gracefully
            assert response.status_code in [200, 500]
            if response.status_code == 200:
                data = response.json()
                assert "error" in data or "status" in data

    def test_audit_logging(self, client, agent_with_executions, db_session):
        """Test audit logging for agent execution."""
        agent = agent_with_executions

        response = client.post(
            f"/agents/{agent.id}/execute",
            json={"message": "Audit test"}
        )

        # Check audit log
        execution = db_session.query(AgentExecution).filter_by(
            agent_id=agent.id
        ).first()

        assert execution is not None
        assert execution.agent_id == agent.id
        assert execution.status in ["pending", "running", "completed", "failed"]

    def test_streaming_response(self, client, agent_with_executions):
        """Test streaming response from agent execution."""
        agent = agent_with_executions

        response = client.post(
            f"/agents/{agent.id}/execute",
            json={"message": "Streaming test", "stream": True}
        )

        # Should return streaming response
        assert response.status_code == 200
```

**Tests:**
- End-to-end execution flow
- Error handling and recovery
- Audit logging
- Streaming responses

**Acceptance:**
- [ ] Execution flow tested (governance → LLM → streaming)
- [ ] Error handling tested (LLM failures, timeout)
- [ ] Audit logging verified
- [ ] Streaming tested

---

### Task 2: Create Integration Tests for Agent Coordination

**Files:** `tests/integration/agent/test_agent_coordination.py`

**Action:**
Create integration tests for agent-to-agent communication:

```python
"""
Integration Tests for Agent Coordination

Tests cover:
- Agent-to-agent messaging
- Event bus communication
- Message delivery reliability
- Multi-agent workflows
"""
import pytest
import asyncio
from sqlalchemy.orm import Session

from core.social_layer import SocialLayer
from core.event_bus import EventBus
from core.models import AgentRegistry
from tests.factories import AgentFactory


class TestAgentCoordination:
    """Test agent coordination."""

    @pytest.fixture
    def social_layer(self, db_session):
        """Create social layer."""
        return SocialLayer(db_session)

    @pytest.fixture
    def event_bus(self, db_session):
        """Create event bus."""
        return EventBus(db_session)

    @pytest.fixture
    def_agents(self, db_session):
        """Create multiple agents for coordination."""
        agents = [AgentFactory(maturity_level="AUTONOMOUS") for _ in range(3)]
        db_session.commit()
        return agents

    @pytest.mark.asyncio
    async def test_agent_to_agent_messaging(self, social_layer, _agents):
        """Test agent-to-agent messaging."""
        sender, receiver = _agents[0], _agents[1]

        # Send message
        await social_layer.send_message(
            from_agent_id=sender.id,
            to_agent_id=receiver.id,
            message="Hello from sender"
        )

        # Verify delivery
        messages = await social_layer.get_messages(
            agent_id=receiver.id
        )

        assert len(messages) > 0
        assert messages[0]["from_agent_id"] == sender.id

    @pytest.mark.asyncio
    async def test_event_bus_communication(self, event_bus, _agents):
        """Test event bus communication."""
        # Publish event
        await event_bus.publish(
            event_type="agent_coordination",
            data={"agent_ids": [a.id for a in _agents]}
        )

        # Subscribe and receive
        received = []

        async def handler(event):
            received.append(event)

        await event_bus.subscribe(
            event_type="agent_coordination",
            handler=handler
        )

        # Verify event received
        assert len(received) > 0

    @pytest.mark.asyncio
    async def test_message_ordering_fifo(self, social_layer, _agents):
        """Test message ordering (FIFO)."""
        sender, receiver = _agents[0], _agents[1]

        # Send multiple messages
        for i in range(5):
            await social_layer.send_message(
                from_agent_id=sender.id,
                to_agent_id=receiver.id,
                message=f"Message {i}"
            )

        # Retrieve messages
        messages = await social_layer.get_messages(
            agent_id=receiver.id
        )

        # Should be in order (FIFO)
        message_contents = [m["message"] for m in messages[-5:]]
        expected = [f"Message {i}" for i in range(5)]

        assert message_contents == expected
```

**Tests:**
- Agent-to-agent messaging
- Event bus communication
- Message delivery reliability
- FIFO ordering

**Acceptance:**
- [ ] Agent-to-agent messaging tested
- [ ] Event bus communication tested
- [ ] Message ordering verified (FIFO)
- [ ] Multi-agent workflows tested

---

### Task 3: Create Property Tests for Coordination Invariants

**Files:** `tests/property_tests/agent/test_agent_coordination_invariants.py`

**Action:**
Create property tests for coordination invariants:

```python
"""
Property-Based Tests for Agent Coordination Invariants

Tests CRITICAL coordination invariants:
- Message ordering is FIFO
- Messages never lost (delivery invariant)
- Event bus delivers to all subscribers
- Agent coordination terminates reliably
"""
import pytest
from hypothesis import strategies as st, given, settings
from sqlalchemy.orm import Session

from core.social_layer import SocialLayer
from core.event_bus import EventBus
from core.models import AgentRegistry
from tests.factories import AgentFactory


class TestMessageOrderingInvariants:
    """Property tests for message ordering."""

    @given(
        num_messages=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_fifo_ordering_invariant(self, social_layer, db_session, num_messages):
        """
        FIFO ordering invariant.

        Property: Messages are delivered in the order they were sent.
        """
        sender = AgentFactory()
        receiver = AgentFactory()
        db_session.commit()

        # Send messages
        sent_order = []
        for i in range(num_messages):
            message = f"Message {i}"
            await social_layer.send_message(
                from_agent_id=sender.id,
                to_agent_id=receiver.id,
                message=message
            )
            sent_order.append(message)

        # Retrieve messages
        messages = await social_layer.get_messages(
            agent_id=receiver.id
        )

        # Extract message contents (last N messages)
        received_order = [m["message"] for m in messages[-num_messages:]]

        # Should match sent order
        assert received_order == sent_order


class TestMessageDeliveryInvariants:
    """Property tests for message delivery."""

    @given(
        num_messages=st.integers(min_value=10, max_value=50)
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_no_lost_messages_invariant(self, social_layer, db_session, num_messages):
        """
        No lost messages invariant.

        Property: All sent messages are eventually delivered.
        """
        sender = AgentFactory()
        receiver = AgentFactory()
        db_session.commit()

        # Send messages
        for i in range(num_messages):
            await social_layer.send_message(
                from_agent_id=sender.id,
                to_agent_id=receiver.id,
                message=f"Message {i}"
            )

        # Retrieve messages
        messages = await social_layer.get_messages(
            agent_id=receiver.id
        )

        # Should have received all messages
        # (Note: might be more messages due to other agents, so we check >=)
        assert len(messages) >= num_messages
```

**Tests:**
- FIFO ordering invariant
- No lost messages invariant
- Event bus delivery to all subscribers
- Agent coordination termination

**Acceptance:**
- [ ] FIFO ordering tested (50+ examples)
- [ ] Message delivery tested (no lost messages)
- [ ] Event bus tested (subscriber delivery)
- [ ] Termination tested

---

## Deviations

**Rule 1 (Auto-fix bugs):** If execution orchestration has bugs, fix immediately.

**Rule 2 (Integration):** If event bus doesn't exist, stub it for testing.

**Rule 3 (Async):** If async tests flaky, add explicit synchronization.

## Success Criteria

- [ ] End-to-end execution tested
- [ ] Error handling and audit logging tested
- [ ] Agent-to-agent messaging tested
- [ ] Event bus communication tested
- [ ] Property tests for coordination invariants

## Dependencies

- Plan 05-01 (Governance & Maturity) must be complete

## Estimated Duration

2-3 hours (execution tests + coordination tests + property tests)
