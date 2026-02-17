# Architecture Research: AI/LLM System Testing

**Domain:** AI/LLM System Testing Architecture
**Researched:** February 16, 2026
**Confidence:** HIGH

## Executive Summary

AI/LLM systems require fundamentally different testing architectures than traditional software due to **non-deterministic outputs**, **probabilistic behavior**, and **emergent properties**. Based on research of current best practices and analysis of Atom's existing property-based testing infrastructure, this document outlines a comprehensive testing architecture for achieving 80% coverage across AI components including LLM integration, agent governance, episodic memory, multi-agent coordination, and social features.

**Key Finding**: The testing architecture must balance **deterministic property-based testing** (40% of tests) for invariants, **integration testing** (30%) for component interactions, **LLM-specific testing** (20%) for prompt/response validation, and **chaos engineering** (10%) for resilience.

## Standard Architecture for AI/LLM System Testing

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Test Layer Boundaries                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐  │
│  │   Unit Tests │  │Property Tests│  │Integration   │  │E2E Tests│  │
│  │    (40%)     │  │    (40%)     │  │   Tests      │  │  (5%)   │  │
│  │              │  │              │  │   (15%)      │  │         │  │
│  │ • Mock LLM   │  │ • Invariants │  │ • Real LLM   │  │ • Full  │  │
│  │ • Isolated   │  │ • Hypothesis │  │ • DB Session │  │  Stack  │  │
│  │ • Fast       │  │ • Generated  │  │ • Mock Ext.  │  │ • Slow  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                      AI-Specific Test Layers                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐  │
│  │  LLM Output  │  │  Agent       │  │  Memory      │  │  Social │  │
│  │  Validation  │  │  Governance  │  │  System      │  │  Layer  │  │
│  │              │  │              │  │              │  │         │  │
│  │ • Semantics  │  │ • Maturity   │  │ • Episodes   │  │ • Feed  │  │
│  │ • Format     │  │ • Graduation │  │ • Retrieval  │  │ • Pub/  │  │
│  │ • Safety     │  │ • Triggers   │  │ • Lifecycle  │  │   Sub   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                      Test Data & Mocking Layer                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Fixtures, Factories, Mocks, Fakes              │   │
│  │  • db_session (SQLite in-memory)                            │   │
│  │  • test_agent (all maturity levels)                         │   │
│  │  • mock_llm_response (deterministic outputs)                │   │
│  │  • mock_embedding_vectors (controlled similarity)           │   │
│  │  • fake_redis (in-memory pub/sub)                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│                      Test Infrastructure                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │  pytest    │  │ Hypothesis │  │  pytest-   │  │  mutmut   │   │
│  │  (runner)  │  │  (PBT)     │  │  asyncio   │  │ (mutation)│   │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation | AI-Specific Considerations |
|-----------|----------------|------------------------|---------------------------|
| **Unit Tests** | Verify individual functions/classes in isolation | pytest + unittest.mock | Mock LLM calls with deterministic responses |
| **Property Tests** | Verify invariants across generated inputs | Hypothesis + strategies | Test governance rules, memory constraints |
| **Integration Tests** | Verify component interactions | pytest + real DB + mock external | Test agent-to-agent, memory-to-retrieval |
| **LLM Validation Tests** | Verify prompt/response quality | Custom assertion framework | Check semantics, format, safety, cost |
| **Chaos Tests** | Verify system resilience | pytest + failure injection | Test LLM failures, DB crashes, Redis down |
| **Mutation Tests** | Verify test quality | mutmut | Ensure tests catch AI logic bugs |

## Recommended Project Structure

```
backend/
├── tests/
│   ├── property_tests/              # Property-based tests (Hypothesis)
│   │   ├── conftest.py              # Shared fixtures, Hypothesis settings
│   │   ├── README.md                # Property testing guide
│   │   │
│   │   ├── llm/                     # LLM layer tests
│   │   │   ├── test_byok_handler_invariants.py
│   │   │   ├── test_llm_operations_invariants.py
│   │   │   └── test_prompt_validation_invariants.py
│   │   │
│   │   ├── agents/                  # Agent layer tests
│   │   │   ├── test_agent_governance_invariants.py
│   │   │   ├── test_agent_graduation_invariants.py
│   │   │   ├── test_trigger_interceptor_invariants.py
│   │   │   └── test_supervision_invariants.py
│   │   │
│   │   ├── memory/                  # Memory layer tests
│   │   │   ├── test_episode_segmentation_invariants.py
│   │   │   ├── test_episode_retrieval_invariants.py
│   │   │   ├── test_episode_lifecycle_invariants.py
│   │   │   └── test_memory_consistency_invariants.py
│   │   │
│   │   ├── social/                  # Social layer tests
│   │   │   ├── test_agent_communication_invariants.py
│   │   │   ├── test_feed_generation_invariants.py
│   │   │   ├── test_social_interaction_invariants.py
│   │   │   └── test_redis_pubsub_invariants.py
│   │   │
│   │   ├── skills/                  # Skills layer tests
│   │   │   ├── test_skill_parsing_invariants.py
│   │   │   ├── test_skill_adaptation_invariants.py
│   │   │   ├── test_sandbox_isolation_invariants.py
│   │   │   └── test_skill_registry_invariants.py
│   │   │
│   │   ├── local_agent/             # Local agent tests
│   │   │   ├── test_shell_security_invariants.py
│   │   │   ├── test_file_access_invariants.py
│   │   │   ├── test_command_whitelist_invariants.py
│   │   │   └── test_permission_boundary_invariants.py
│   │   │
│   │   ├── im_layer/                # IM layer tests
│   │   │   ├── test_webhook_handling_invariants.py
│   │   │   ├── test_rate_limiting_invariants.py
│   │   │   └── test_im_integration_invariants.py
│   │   │
│   │   ├── governance/              # Governance tests
│   │   │   ├── test_governance_cache_invariants.py
│   │   │   ├── test_maturity_routing_invariants.py
│   │   │   └── test_action_complexity_invariants.py
│   │   │
│   │   ├── api/                     # API contract tests
│   │   │   ├── test_api_response_invariants.py
│   │   │   ├── test_api_governance_invariants.py
│   │   │   └── test_websocket_invariants.py
│   │   │
│   │   ├── database/                # Database tests
│   │   │   ├── test_database_invariants.py
│   │   │   ├── test_database_atomicity.py
│   │   │   └── test_database_transaction_invariants.py
│   │   │
│   │   ├── security/                # Security tests
│   │   │   ├── test_auth_invariants.py
│   │   │   ├── test_encryption_invariants.py
│   │   │   └── test_pii_redaction_invariants.py
│   │   │
│   │   └── performance/             # Performance tests
│   │       ├── test_cache_invariants.py
│   │       ├── test_concurrent_operations_invariants.py
│   │       └── test_latency_invariants.py
│   │
│   ├── integration/                 # Integration tests
│   │   ├── test_llm_agent_integration.py
│   │   ├── test_memory_retrieval_integration.py
│   │   ├── test_multi_agent_coordination.py
│   │   ├── test_social_feed_integration.py
│   │   ├── test_skill_execution_integration.py
│   │   └── test_local_agent_integration.py
│   │
│   ├── llm_validation/              # LLM-specific validation
│   │   ├── test_prompt_quality.py
│   │   ├── test_response_semantics.py
│   │   ├── test_safety_validation.py
│   │   ├── test_cost_validation.py
│   │   └── test_format_validation.py
│   │
│   ├── chaos/                       # Chaos engineering
│   │   ├── test_llm_failure_resilience.py
│   │   ├── test_database_failure_recovery.py
│   │   ├── test_redis_failure_handling.py
│   │   ├── test_network_partition.py
│   │   └── test_resource_exhaustion.py
│   │
│   ├── fuzzy_tests/                 # Fuzzy testing (future)
│   │   ├── test_input_validation_fuzz.py
│   │   └── test_protocol_parsing_fuzz.py
│   │
│   ├── test_p1_regression.py        # Critical regression tests
│   ├── test_supervision_learning_integration.py
│   ├── test_graduation_integration.py
│   ├── test_proposal_episode_creation.py
│   ├── test_supervision_episode_creation.py
│   │
│   ├── conftest.py                  # Root conftest (if needed)
│   ├── TESTING_GUIDE.md             # Comprehensive testing guide
│   └── COLLECTION_ERROR_INVESTIGATION.md
│
├── .planning/
│   └── research/
│       └── ARCHITECTURE.md          # This file
│
├── core/                            # System under test
│   ├── llm/
│   ├── agents/
│   ├── memory/
│   ├── social/
│   └── ...
│
├── pytest.ini                       # Pytest configuration
├── .hypothesis/                     # Hypothesis database (gitignored)
└── pyproject.toml                   # Test dependencies
```

### Structure Rationale

- **`property_tests/`**: Organized by architectural layer (LLM, agents, memory, social, skills, local, IM) for clear ownership. Each layer has dedicated invariants tests.
- **`integration/`**: Cross-layer tests that verify component interactions work correctly (e.g., agent execution creates episodes, episodes are retrieved for context).
- **`llm_validation/`**: Specialized tests for LLM-specific concerns (prompt quality, response semantics, safety, cost) that require different assertions than traditional tests.
- **`chaos/`**: Resilience tests that inject failures (LLM timeout, DB crash, Redis down) to verify graceful degradation.
- **`fuzzy_tests/`**: Future expansion for fuzz testing input parsing and protocol handling.

## Architectural Patterns

### Pattern 1: Deterministic LLM Mocking

**What:** Replace non-deterministic LLM calls with deterministic mock responses that can be controlled per test.

**When to use:** Unit tests and property tests where LLM output is an input to the system under test.

**Trade-offs:**
- ✅ Fast, repeatable, no API costs
- ❌ Doesn't catch real LLM integration bugs

**Example:**
```python
import pytest
from unittest.mock import Mock, patch
from core.llm.byok_handler import BYOKHandler

def test_agent_execution_with_mocked_llm(db_session):
    """
    Test agent execution logic with deterministic LLM response.
    """
    # Arrange: Mock LLM response
    mock_llm = Mock()
    mock_llm.complete.return_value = "Test response"

    with patch('core.llm.byok_handler.OpenAI') as mock_openai:
        mock_openai.return_value = mock_llm

        handler = BYOKHandler()
        response = handler.complete("test prompt")

        # Assert: Verify agent uses LLM response correctly
        assert response == "Test response"
        mock_llm.complete.assert_called_once()
```

### Pattern 2: Property-Based Invariant Testing

**What:** Use Hypothesis to generate hundreds of random inputs and verify system invariants always hold.

**When to use:** Testing critical invariants (governance rules, memory constraints, security boundaries).

**Trade-offs:**
- ✅ Catches edge cases humans miss
- ✅ Provides counterexamples when invariants fail
- ❌ Slower than unit tests (50-200 iterations per test)
- ❌ Requires careful invariant definition

**Example:**
```python
from hypothesis import given, strategies as st, settings
from core.agent_governance_service import AgentGovernanceService

@given(
    confidence_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
)
@settings(max_examples=200)
def test_confidence_score_bounds(db_session, confidence_score):
    """
    INVARIANT: Confidence scores MUST always be in [0.0, 1.0].

    This is safety-critical for AI decision-making.
    """
    agent = AgentRegistry(
        name="TestAgent",
        confidence_score=confidence_score,
        status=AgentStatus.INTERN.value
    )
    db_session.add(agent)
    db_session.commit()

    # Verify invariant holds
    assert 0.0 <= agent.confidence_score <= 1.0
```

### Pattern 3: Semantic Similarity Testing for LLM Outputs

**What:** Instead of exact string matching, use semantic similarity to validate LLM responses are "correct enough."

**When to use:** LLM validation tests where exact output doesn't matter, but meaning does.

**Trade-offs:**
- ✅ Handles LLM non-determinism
- ✅ Validates semantic correctness
- ❌ Requires embedding model (adds latency)
- ❌ Threshold tuning is subjective

**Example:**
```python
import pytest
from core.embedding_service import EmbeddingService

def test_llm_response_semantics(db_session):
    """
    Test that LLM response is semantically similar to expected output.
    """
    # Arrange
    embedding_service = EmbeddingService()
    expected = "The agent completed the task successfully"
    actual = llm.generate("Summarize the agent's action")

    # Act: Compute semantic similarity
    similarity = embedding_service.similarity(expected, actual)

    # Assert: Require high semantic similarity
    assert similarity > 0.85, f"Response not semantically similar: {similarity}"
```

### Pattern 4: Episode-Based Memory Testing

**What:** Test episodic memory by creating episodes, retrieving them, and verifying correctness.

**When to use:** Testing memory segmentation, retrieval, and lifecycle.

**Trade-offs:**
- ✅ Tests real memory behavior
- ❌ Slower due to DB operations

**Example:**
```python
from datetime import datetime, timedelta

def test_episode_retrieval_by_temporal_proximity(db_session):
    """
    Test that episodes are retrieved correctly by time range.
    """
    # Arrange: Create episodes with different timestamps
    episodes = []
    base_time = datetime(2024, 1, 1, 12, 0, 0)

    for i in range(10):
        episode = Episode(
            agent_id="agent_123",
            start_time=base_time + timedelta(hours=i*2),
            end_time=base_time + timedelta(hours=i*2 + 1),
            summary=f"Episode {i}"
        )
        db_session.add(episode)
        episodes.append(episode)

    db_session.commit()

    # Act: Retrieve episodes within time range
    service = EpisodeRetrievalService()
    result = service.retrieve_episodes(
        agent_id="agent_123",
        start_time=base_time,
        end_time=base_time + timedelta(hours=6)
    )

    # Assert: Should retrieve 4 episodes (0, 1, 2, 3)
    assert len(result) == 4
    assert all(ep.start_time >= base_time for ep in result)
    assert all(ep.start_time <= base_time + timedelta(hours=6) for ep in result)
```

### Pattern 5: Multi-Agent Coordination Testing

**What:** Test agent-to-agent communication, task distribution, and conflict resolution.

**When to use:** Testing social layer, feed generation, agent coordination.

**Trade-offs:**
- ✅ Validates emergent behavior
- ❌ Complex test setup (multiple agents)
- ❌ Slow (real coordination overhead)

**Example:**
```python
def test_multi_agent_task_distribution(db_session):
    """
    Test that tasks are distributed evenly across agents.
    """
    # Arrange: Create multiple agents
    agents = []
    for i in range(5):
        agent = AgentRegistry(
            name=f"agent_{i}",
            status=AgentStatus.AUTONOMOUS.value,
            capabilities=["test_task"]
        )
        db_session.add(agent)
        agents.append(agent)

    db_session.commit()

    # Act: Distribute 20 tasks across 5 agents
    tasks = [f"task_{i}" for i in range(20)]
    coordinator = MultiAgentCoordinator()
    distribution = coordinator.distribute_tasks(tasks, agents)

    # Assert: Tasks distributed evenly (4-5 per agent)
    tasks_per_agent = [len(dist) for dist in distribution.values()]
    assert all(3 <= count <= 5 for count in tasks_per_agent), \
        f"Uneven distribution: {tasks_per_agent}"
```

### Pattern 6: Chaos Engineering for AI Systems

**What:** Inject failures (LLM timeout, DB crash, Redis down) to verify graceful degradation.

**When to use:** Testing resilience, error handling, recovery mechanisms.

**Trade-offs:**
- ✅ Catches production failure modes
- ❌ Complex test setup
- ❌ Can be slow (timeout simulations)

**Example:**
```python
import pytest
from unittest.mock import patch
from core.llm.byok_handler import BYOKHandler

def test_llm_timeout_graceful_degradation(db_session):
    """
    Test that LLM timeout is handled gracefully.
    """
    handler = BYOKHandler()

    # Mock LLM client that times out
    with patch('core.llm.byok_handler.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = TimeoutError("LLM timeout")
        mock_openai.return_value = mock_client

        # Act: Should fallback to next provider or cached response
        response = handler.complete("test prompt", timeout=5)

        # Assert: Should not crash, return fallback response
        assert response is not None
        assert "fallback" in response.lower() or response != ""
```

## Data Flow

### Test Data Flow

```
[Test File] → [Hypothesis Strategies] → [Generated Inputs]
     ↓                                      ↓
[Fixtures] ← [db_session] ← [SQLite In-Memory DB]
     ↓                                      ↓
[System Under Test] → [Execution] → [Assertions]
     ↓                                      ↓
[Mock Objects] → [Deterministic Responses] → [Validation]
```

### Test Fixture Flow

```
conftest.py
    ├── db_session (SQLite in-memory, per-test)
    │   ├── Create tables
    │   ├── Return session
    │   └── Cleanup (drop tables)
    │
    ├── test_agent (all maturity levels)
    │   ├── STUDENT agent
    │   ├── INTERN agent
    │   ├── SUPERVISED agent
    │   └── AUTONOMOUS agent
    │
    ├── mock_llm_response (deterministic outputs)
    │   ├── Success response
    │   ├── Timeout error
    │   └── Rate limit error
    │
    ├── fake_redis (in-memory pub/sub)
    │   ├── Message publishing
    │   ├── Channel subscription
    │   └── Message receiving
    │
    └── test_data (factory methods)
        ├── create_episode()
        ├── create_agent()
        └── create_skill()
```

## AI-Specific Architecture Patterns

### 1. Handling Non-Determinism

**Problem:** LLM outputs are non-deterministic, making tests flaky.

**Solutions:**

| Approach | When to Use | Pros | Cons |
|----------|-------------|------|------|
| **Mock LLM responses** | Unit tests, property tests | Fast, deterministic | Doesn't test real LLM |
| **Semantic similarity** | Integration tests | Tests semantics | Requires embeddings, threshold tuning |
| **Format validation** | All tests | Tests structure | Doesn't test content |
| **Seed random generation** | Reproducibility | Debuggable | Not always possible with LLMs |

**Recommended Pattern:** Use mocked LLM responses for 80% of tests (unit + property), real LLM with semantic similarity for 20% (integration).

### 2. Testing Agent Maturity-Dependent Behavior

**Problem:** Agent behavior changes based on maturity level (STUDENT → INTERN → SUPERVISED → AUTONOMOUS).

**Solution:** Parameterized tests with fixtures for each maturity level.

**Example:**
```python
import pytest

@pytest.mark.parametrize("maturity", [
    AgentStatus.STUDENT,
    AgentStatus.INTERN,
    AgentStatus.SUPERVISED,
    AgentStatus.AUTONOMOUS
])
def test_action_complexity_enforcement(db_session, maturity):
    """
    Test that action complexity is enforced per maturity level.
    """
    agent = AgentRegistry(
        name="test_agent",
        status=maturity.value,
        confidence_score=0.5
    )
    db_session.add(agent)
    db_session.commit()

    governance = AgentGovernanceService()

    # STUDENT can't perform CRITICAL actions
    if maturity == AgentStatus.STUDENT:
        decision = governance.check_permission(agent, action_complexity=4)
        assert decision.allowed == False
        assert decision.reason == "Insufficient maturity"

    # AUTONOMOUS can perform all actions
    elif maturity == AgentStatus.AUTONOMOUS:
        decision = governance.check_permission(agent, action_complexity=4)
        assert decision.allowed == True
```

### 3. Testing Probabilistic Memory Retrieval

**Problem:** Episode retrieval uses semantic search with probabilistic results.

**Solution:** Test retrieval invariants (order, relevance, bounds) rather than exact results.

**Example:**
```python
def test_episode_retrieval_invariants(db_session):
    """
    Test that episode retrieval maintains invariants.
    """
    # Arrange: Create episodes with known content
    episodes = [
        Episode(summary="Machine learning tutorial"),
        Episode(summary="Cooking recipes"),
        Episode(summary="Deep learning frameworks")
    ]
    for ep in episodes:
        db_session.add(ep)
    db_session.commit()

    # Act: Retrieve episodes about "machine learning"
    service = EpisodeRetrievalService()
    results = service.retrieve_episodes(
        query="machine learning",
        limit=10
    )

    # Assert: Invariants (not exact results)
    assert len(results) <= 10, "Should respect limit"
    assert all(hasattr(ep, 'summary') for ep in results), "All results have summary"
    assert results[0].relevance_score >= results[-1].relevance_score, "Sorted by relevance"
```

### 4. Testing Multi-Agent Social Interactions

**Problem:** Agent-to-agent communication involves concurrency, ordering, and emergent behavior.

**Solution:** Use in-memory Redis fake, controlled message ordering, and verify invariants.

**Example:**
```python
import pytest
from unittest.mock import Mock

def test_agent_communication_feed_generation(db_session):
    """
    Test that agent communication generates correct feed entries.
    """
    # Arrange: Create two agents and in-memory Redis
    agent1 = AgentRegistry(id="agent1", name="Agent1")
    agent2 = AgentRegistry(id="agent2", name="Agent2")
    db_session.add_all([agent1, agent2])
    db_session.commit()

    fake_redis = Mock()
    fake_redis.publish = Mock()

    # Act: Agent1 sends message to Agent2
    social_layer = AgentSocialLayer(redis_client=fake_redis)
    social_layer.send_message(
        from_agent="agent1",
        to_agent="agent2",
        message="Hello"
    )

    # Assert: Message published, feed entry created
    fake_redis.publish.assert_called_once()
    call_args = fake_redis.publish.call_args

    # Verify channel format
    channel = call_args[0][0]
    assert "agent:agent2:feed" in channel, "Should publish to agent2's feed"

    # Verify message structure
    message = call_args[0][1]
    import json
    parsed = json.loads(message)
    assert parsed["from_agent"] == "agent1"
    assert parsed["to_agent"] == "agent2"
    assert parsed["content"] == "Hello"
```

### 5. Testing Docker Container Isolation (Skills)

**Problem:** Skills execute in isolated Docker containers with resource limits.

**Solution:** Test sandbox invariants with real Docker (integration) or mocked Docker (unit).

**Example (Integration):**
```python
import pytest
from core.skill_sandbox import SkillSandbox

@pytest.mark.integration
def test_skill_sandbox_isolation_integration():
    """
    Test that skill execution is isolated in Docker container.
    NOTE: This test requires Docker daemon.
    """
    sandbox = SkillSandbox()

    # Act: Execute skill that tries to access host filesystem
    result = sandbox.execute_skill("""
import os
# Try to read host file (should fail)
try:
    with open('/etc/passwd', 'r') as f:
        print(f.read())
except Exception as e:
    print(f"Access denied: {e}")
    """)

    # Assert: Should not access host filesystem
    assert "Access denied" in result.output or result.return_code != 0
    assert result.execution_time < 300, "Should timeout after 5 minutes"
```

**Example (Unit with Mock):**
```python
def test_skill_sandbox_isolation_unit(db_session):
    """
    Test sandbox isolation logic without real Docker.
    """
    # Mock Docker client
    with patch('core.skill_sandbox.docker.from_env') as mock_docker:
        mock_container = Mock()
        mock_container.logs.return_value = "Access denied"
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_docker.return_value.containers.run.return_value = mock_container

        sandbox = SkillSandbox()
        result = sandbox.execute_skill("malicious code")

        # Assert: Container was created with isolation flags
        mock_docker.return_value.containers.run.assert_called_once()
        call_kwargs = mock_docker.return_value.containers.run.call_args[1]

        # Verify security flags
        assert call_kwargs["network_disabled"] is True
        assert call_kwargs["mem_limit"] == "512m"
        assert "readonly" in str(call_kwargs.get("volumes", ""))
```

## Test Layer Boundaries

### Unit Tests (40% of test suite)

**Scope:** Single function or class, isolated dependencies.

**Speed:** <0.1s per test.

**Examples:**
- `test_confidence_score_clipping()` - Verifies confidence scores are clipped to [0, 1]
- `test_episode_creation_requires_agent_id()` - Verifies episode creation fails without agent_id
- `test_command_whitelist_blocks_dangerous_commands()` - Verifies dangerous commands are blocked

**When to use:** Testing business logic, data transformations, validation rules.

### Property-Based Tests (40% of test suite)

**Scope:** System invariants across many generated inputs.

**Speed:** 5-100s per test (depending on iterations, complexity).

**Examples:**
- `test_confidence_score_never_exceeds_bounds()` - INVARIANT: All confidence scores in [0.0, 1.0]
- `test_episode_time_gap_detection()` - INVARIANT: Gaps >4 hours trigger new episode
- `test_agent_maturity_never_regresses()` - INVARIANT: Agents never downgrade maturity

**When to use:** Testing critical invariants, governance rules, security boundaries.

### Integration Tests (15% of test suite)

**Scope:** Multiple components working together, real database.

**Speed:** 1-5s per test.

**Examples:**
- `test_agent_execution_creates_episode()` - Agent execution → episode creation → retrieval
- `test_graduation_exam_with_memory()` - Graduation exam uses episodic memory correctly
- `test_multi_agent_coordination_with_feed()` - Agent communication → feed generation

**When to use:** Testing component interactions, data flows, real database behavior.

### E2E Tests (5% of test suite)

**Scope:** Full stack (API → Service → DB → External services).

**Speed:** 5-30s per test.

**Examples:**
- `test_user_chat_flow()` - User sends chat → agent responds → episode created → feed updated
- `test_skill_execution_workflow()` - User triggers skill → parsing → sandbox → execution → result

**When to use:** Testing critical user journeys, smoke tests for deployment.

### LLM Validation Tests (20% of AI-specific tests)

**Scope:** Prompt quality, response semantics, safety, cost.

**Speed:** 1-10s per test (real LLM calls).

**Examples:**
- `test_prompt_includes_required_context()` - Verify prompt structure
- `test_response_semantically_correct()` - Semantic similarity >0.85
- `test_safety_validation_blocks_harmful_content()` - Safety filters work
- `test_cost_estimation_accuracy()` - Cost within ±20% of actual

**When to use:** Testing LLM integration quality, prompt engineering, cost optimization.

### Chaos Tests (10% of AI-specific tests)

**Scope:** System resilience under failures.

**Speed:** 5-30s per test (failure injection + recovery).

**Examples:**
- `test_llm_timeout_fallback()` - LLM timeout → fallback provider
- `test_database_connection_loss_recovery()` - DB down → retry → succeed
- `test_redis_failure_degrades_gracefully()` - Redis down → fallback to in-memory

**When to use:** Testing resilience, error handling, recovery mechanisms.

## Build Order & Dependencies

### Phase 1: Foundation (Test Infrastructure)

**Priority:** P0 (blocks everything else)

**Components:**
1. `conftest.py` - Fixtures (db_session, test_agent, mock_llm)
2. `property_tests/conftest.py` - Hypothesis settings, strategies
3. Test utilities (factories, helpers, assertion libraries)

**Dependencies:** None

**Estimated Time:** 1-2 days

**Success Criteria:**
- `db_session` fixture creates clean database per test
- `test_agent` fixture creates agents at all maturity levels
- Hypothesis settings configured (max_examples=200 local, 50 CI)

### Phase 2: Core Invariants (Governance, LLM, Database)

**Priority:** P0 (safety-critical)

**Components:**
1. `property_tests/governance/` - Governance cache, maturity routing, action complexity
2. `property_tests/llm/` - BYOK handler invariants, provider selection, token counting
3. `property_tests/database/` - Database invariants, atomicity, transactions

**Dependencies:** Phase 1 (fixtures)

**Estimated Time:** 3-5 days

**Success Criteria:**
- All governance invariants tested (confidence bounds, maturity hierarchy)
- LLM routing invariants tested (provider fallback, cost calculation)
- Database invariants tested (atomicity, foreign keys, constraints)

### Phase 3: Memory Layer Tests

**Priority:** P1 (core feature)

**Components:**
1. `property_tests/memory/test_episode_segmentation_invariants.py`
2. `property_tests/memory/test_episode_retrieval_invariants.py`
3. `property_tests/memory/test_episode_lifecycle_invariants.py`
4. `integration/test_memory_retrieval_integration.py`

**Dependencies:** Phase 2 (database fixtures)

**Estimated Time:** 3-4 days

**Success Criteria:**
- Segmentation invariants tested (time gaps, topic changes)
- Retrieval invariants tested (temporal, semantic, sequential)
- Lifecycle invariants tested (decay, consolidation, archival)

### Phase 4: Agent Layer Tests

**Priority:** P1 (core feature)

**Components:**
1. `property_tests/agents/test_agent_governance_invariants.py`
2. `property_tests/agents/test_agent_graduation_invariants.py`
3. `property_tests/agents/test_trigger_interceptor_invariants.py`
4. `property_tests/agents/test_supervision_invariants.py`
5. `integration/test_supervision_learning_integration.py`

**Dependencies:** Phase 2 (governance), Phase 3 (episodes)

**Estimated Time:** 4-5 days

**Success Criteria:**
- Governance invariants tested (maturity checks, permission boundaries)
- Graduation invariants tested (readiness score, constitutional compliance)
- Trigger interceptor tested (STUDENT blocking, proposal routing)
- Supervision tested (intervention tracking, pause/correct/terminate)

### Phase 5: Social Layer Tests

**Priority:** P2 (important feature)

**Components:**
1. `property_tests/social/test_agent_communication_invariants.py`
2. `property_tests/social/test_feed_generation_invariants.py`
3. `property_tests/social/test_redis_pubsub_invariants.py`
4. `integration/test_multi_agent_coordination.py`

**Dependencies:** Phase 4 (agents), Phase 3 (episodes)

**Estimated Time:** 3-4 days

**Success Criteria:**
- Communication invariants tested (message structure, delivery)
- Feed generation tested (ordering, pagination, filtering)
- Redis pub/sub tested (channel subscriptions, message routing)

### Phase 6: Skills Layer Tests

**Priority:** P1 (security-critical)

**Components:**
1. `property_tests/skills/test_skill_parsing_invariants.py`
2. `property_tests/skills/test_skill_adaptation_invariants.py`
3. `property_tests/skills/test_sandbox_isolation_invariants.py`
4. `property_tests/skills/test_skill_registry_invariants.py`
5. `integration/test_skill_execution_integration.py`

**Dependencies:** Phase 2 (database), Phase 4 (agents)

**Estimated Time:** 4-5 days

**Success Criteria:**
- Parsing invariants tested (SKILL.md validation, metadata extraction)
- Adaptation invariants tested (BaseTool wrapping, prompt/Python detection)
- Sandbox isolation tested (Docker security, resource limits, timeout)
- Registry tested (Untrusted → Active → Banned workflow)

### Phase 7: Local Agent Tests

**Priority:** P0 (security-critical)

**Components:**
1. `property_tests/local_agent/test_shell_security_invariants.py`
2. `property_tests/local_agent/test_file_access_invariants.py`
3. `property_tests/local_agent/test_command_whitelist_invariants.py`
4. `property_tests/local_agent/test_permission_boundary_invariants.py`
5. `integration/test_local_agent_integration.py`

**Dependencies:** Phase 2 (governance), Phase 4 (agents)

**Estimated Time:** 3-4 days

**Success Criteria:**
- Shell security tested (command injection prevention, argument sanitization)
- File access tested (directory permission checks, path traversal prevention)
- Command whitelist tested (blocked dangerous commands, AUTONOMOUS gate)
- Permission boundaries tested (AUTONOMOUS-only enforcement)

### Phase 8: IM Layer Tests

**Priority:** P2 (integration feature)

**Components:**
1. `property_tests/im_layer/test_webhook_handling_invariants.py`
2. `property_tests/im_layer/test_rate_limiting_invariants.py`
3. `property_tests/im_layer/test_im_integration_invariants.py`

**Dependencies:** Phase 2 (database), Phase 4 (agents)

**Estimated Time:** 2-3 days

**Success Criteria:**
- Webhook handling tested (signature validation, replay prevention)
- Rate limiting tested (threshold enforcement, cooldown periods)
- IM integration tested (Slack/Teams/Discord routing)

### Phase 9: LLM Validation Tests

**Priority:** P2 (quality assurance)

**Components:**
1. `llm_validation/test_prompt_quality.py`
2. `llm_validation/test_response_semantics.py`
3. `llm_validation/test_safety_validation.py`
4. `llm_validation/test_cost_validation.py`
5. `llm_validation/test_format_validation.py`

**Dependencies:** Phase 2 (LLM layer)

**Estimated Time:** 3-4 days

**Success Criteria:**
- Prompt quality tested (context inclusion, structure validation)
- Response semantics tested (similarity >0.85 for known queries)
- Safety tested (harmful content blocking, PII redaction)
- Cost tested (estimation accuracy, token counting)

### Phase 10: Chaos Engineering Tests

**Priority:** P3 (resilience verification)

**Components:**
1. `chaos/test_llm_failure_resilience.py`
2. `chaos/test_database_failure_recovery.py`
3. `chaos/test_redis_failure_handling.py`
4. `chaos/test_network_partition.py`
5. `chaos/test_resource_exhaustion.py`

**Dependencies:** All previous phases (system must be working)

**Estimated Time:** 3-4 days

**Success Criteria:**
- LLM failure tested (timeout, rate limit, provider fallback)
- Database failure tested (connection loss, retry logic, recovery)
- Redis failure tested (pub/sub fallback, in-memory degradation)
- Network partition tested (partial outage handling)

### Phase 11: Coverage Analysis & Gap Filling

**Priority:** P1 (reach 80% coverage target)

**Components:**
1. Run coverage report: `pytest --cov=core --cov=api --cov=tools --cov-report=html`
2. Identify uncovered lines: `open htmlcov/index.html`
3. Prioritize gaps: P0 (security), P1 (core features), P2 (nice-to-have)
4. Write targeted tests for uncovered code

**Dependencies:** All previous phases

**Estimated Time:** 5-7 days

**Success Criteria:**
- Overall coverage: ≥80%
- Core modules (governance, LLM, memory, agents): ≥90%
- Security modules (auth, local agent, skills): 100%

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0-1K users** | Single test database, sequential execution, <5min runtime |
| **1K-10K users** | Parallel test execution (pytest-xdist), test database pooling, <10min runtime |
| **10K+ users** | Distributed test runners, CI matrix (multiple Python versions), incremental test selection |

### Scaling Priorities

1. **First bottleneck:** Test execution time (>10min for full suite)
   - **Fix:** Use pytest-xdist for parallel execution: `pytest -n auto`
   - **Expected:** 4-8x speedup with 4-8 cores

2. **Second bottleneck:** CI/CD pipeline duration (>30min)
   - **Fix:** Split tests into stages (smoke, property, integration, chaos)
   - **Expected:** Smoke tests <2min, full suite <15min with parallelization

3. **Third bottleneck:** Flaky tests from non-determinism
   - **Fix:** Use deterministic mocks for LLM, seed random generators, retry flaky tests
   - **Expected:** <1% flaky test rate

## Anti-Patterns

### Anti-Pattern 1: Testing LLM Outputs with Exact String Matching

**What people do:**
```python
def test_llm_response_exact():
    response = llm.generate("What is 2+2?")
    assert response == "The answer is 4."  # BAD: Fragile
```

**Why it's wrong:** LLM outputs are non-deterministic. Test will fail randomly.

**Do this instead:**
```python
def test_llm_response_semantics():
    response = llm.generate("What is 2+2?")
    # Use semantic similarity or format validation
    assert "4" in response or "four" in response.lower()
    # Or use embedding similarity
    assert similarity(response, "The answer is 4.") > 0.85
```

### Anti-Pattern 2: Testing Implementation Details

**What people do:**
```python
def test_agent_uses_specific_function():
    agent = Agent()
    # BAD: Tests internal implementation
    assert agent._internal_state == "processing"
```

**Why it's wrong:** Test breaks when implementation changes, even if behavior is correct.

**Do this instead:**
```python
def test_agent_behavior():
    agent = Agent()
    result = agent.execute(task)
    # Test observable behavior, not internals
    assert result.status == "completed"
    assert result.output is not None
```

### Anti-Pattern 3: Ignoring Test Data Cleanup

**What people do:**
```python
def test_episode_creation(db_session):
    episode = Episode(summary="test")
    db_session.add(episode)
    db_session.commit()
    # BAD: No cleanup, pollutes database
```

**Why it's wrong:** Subsequent tests see stale data, causing flaky failures.

**Do this instead:**
```python
def test_episode_creation(db_session):
    episode = Episode(summary="test")
    db_session.add(episode)
    db_session.commit()

    try:
        # Test logic
        assert episode.id is not None
    finally:
        # Cleanup
        db_session.delete(episode)
        db_session.commit()
```

**Better:** Use fixture-scoped database (automatic cleanup):
```python
# In conftest.py
@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    engine.dispose()
```

### Anti-Pattern 4: Mocking Everything

**What people do:**
```python
def test_agent_execution():
    # BAD: Mocking database, LLM, Redis, everything
    with patch('core.database.SessionLocal'), \
         patch('core.llm.OpenAI'), \
         patch('core.redis.Redis'):
        agent = Agent()
        result = agent.execute()
        assert result is not None
```

**Why it's wrong:** Test doesn't verify real behavior, mocks can drift from implementation.

**Do this instead:**
```python
def test_agent_execution(db_session):
    # Use real database, mock only external services
    with patch('core.llm.OpenAI'):  # Only mock external LLM
        agent = Agent()
        result = agent.execute()
        assert result is not None

        # Verify database state
        executions = db_session.query(AgentExecution).all()
        assert len(executions) == 1
```

### Anti-Pattern 5: Property Tests Without Invariants

**What people do:**
```python
@given(st.text())
def test_episode_summary_generation(text):
    # BAD: No clear invariant, testing implementation
    episode = Episode(summary=text)
    assert episode.summary == text
```

**Why it's wrong:** Property tests should verify invariants, not reimplement code.

**Do this instead:**
```python
@given(st.text(min_size=1, max_size=1000))
def test_episode_summary_length_invariant(text):
    """
    INVARIANT: Episode summaries must be <=1000 chars.
    """
    episode = Episode(summary=text)

    # Truncate if too long
    if len(text) > 1000:
        assert len(episode.summary) <= 1000
    else:
        assert len(episode.summary) == len(text)
```

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **OpenAI API** | Mock in unit/integration tests, real in LLM validation | Use Mock() for deterministic responses |
| **Anthropic API** | Mock in unit/integration tests, real in LLM validation | Test provider fallback logic |
| **PostgreSQL** | SQLite in-memory for tests, real PG for chaos | Use same schema, different backend |
| **Redis** | FakeRedis for unit, real Redis for integration | Test pub/sub, caching |
| **Docker** | Mock for unit, real Docker for skills integration | Test sandbox isolation |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| **LLM Layer → Agent Layer** | Mock responses, real integration | Test agent uses LLM correctly |
| **Agent Layer → Memory Layer** | Real database, test episodes created | Verify agent execution → episode creation |
| **Memory Layer → Retrieval** | Test invariants (order, relevance) | Don't test exact results |
| **Agent Layer → Social Layer** | FakeRedis for pub/sub | Test message routing, feed generation |
| **Skills Layer → Sandbox** | Mock Docker for unit, real for integration | Test isolation, resource limits |

## Sources

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/) - Property-based testing framework
- [Testing LLM Applications: A Comprehensive Guide](https://arxiv.org/abs/2404.12260) - Academic survey of LLM testing (MEDIUM confidence)
- [Pytest Documentation](https://docs.pytest.org/) - Test runner and fixtures
- [Property-Based Testing in Python](https://www.youtube.com/watch?v=Aw44oWhUl2c) - PyCon 2019 talk
- [Chaos Engineering for AI Systems](https://chaossengineering.io/) - Chaos testing patterns
- [Atom Testing Guide](/Users/rushiparikh/projects/atom/backend/tests/TESTING_GUIDE.md) - Existing test infrastructure (HIGH confidence)
- [Atom Property Tests README](/Users/rushiparikh/projects/atom/backend/tests/property_tests/README.md) - Current property test patterns (HIGH confidence)

---

*Architecture research for: Atom 80% Test Coverage Initiative*
*Researched: February 16, 2026*
*Confidence: HIGH (based on existing Atom infrastructure + established AI testing patterns)*
