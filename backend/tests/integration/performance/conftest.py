"""
Shared fixtures for performance benchmark tests.

This module provides pytest fixtures and configuration for performance
benchmarking using pytest-benchmark. All benchmarks use historical tracking
for regression detection without hard-coded time assertions.

Reference: Phase 208 Plan 03 - Performance Benchmarking
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import MagicMock, AsyncMock
import uuid

import pytest

# Try to import pytest_benchmark, but don't fail if not available
try:
    import pytest_benchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False
    pytest_benchmark = None

# Skip all benchmark tests if pytest-benchmark is not available
pytestmark = pytest.mark.skipif(
    not BENCHMARK_AVAILABLE,
    reason="pytest-benchmark plugin not installed. Install with: pip install pytest-benchmark"
)


@pytest.fixture(scope="session")
def benchmark_config():
    """
    Configure pytest-benchmark settings.

    Settings:
    - warmup: 2 iterations for JIT compilation warmup
    - min_rounds: 5 minimum benchmark iterations
    - timer: time.perf_counter for high-resolution timing
    - disable_gc: True to avoid GC timing noise
    """
    return {
        "warmup": True,  # Enable warmup iterations
        "warmup_iterations": 2,  # Number of warmup rounds
        "min_rounds": 5,  # Minimum benchmark iterations
        "timer": time.perf_counter,  # High-resolution timer
        "disable_gc": True,  # Disable garbage collection during benchmarks
        "histogram": True,  # Enable histogram tracking for percentiles
    }


@pytest.fixture
def skip_benchmark():
    """
    Skip benchmarks if pytest-benchmark not available.

    Provides clear skip message when pytest-benchmark is not installed.
    """
    if not BENCHMARK_AVAILABLE:
        pytest.skip(
            "pytest-benchmark plugin not installed. "
            "Install with: pip install pytest-benchmark"
        )


@pytest.fixture
def small_workflow():
    """
    Pre-created 2-step workflow for benchmarks.

    Provides a simple workflow for testing basic operations without
    incurring setup time during benchmark measurement.

    Returns:
        Dict: Workflow definition with 2 linear steps
    """
    return {
        "id": "small_workflow",
        "name": "Small Test Workflow",
        "nodes": [
            {
                "id": "step1",
                "type": "action",
                "config": {
                    "action": "test_action_1",
                    "service": "test_service"
                }
            },
            {
                "id": "step2",
                "type": "action",
                "config": {
                    "action": "test_action_2",
                    "service": "test_service"
                }
            }
        ],
        "connections": [
            {"source": "step1", "target": "step2"}
        ]
    }


@pytest.fixture
def medium_workflow():
    """
    Pre-created 5-step workflow with branching for benchmarks.

    Provides a realistic workflow with conditional logic for testing
    medium-complexity operations.

    Returns:
        Dict: Workflow definition with 5 steps and branching logic
    """
    return {
        "id": "medium_workflow",
        "name": "Medium Test Workflow",
        "nodes": [
            {
                "id": "start",
                "type": "action",
                "config": {
                    "action": "initialize",
                    "service": "test_service"
                }
            },
            {
                "id": "branch1",
                "type": "condition",
                "config": {
                    "condition": "status == 'active'",
                    "service": "test_service"
                }
            },
            {
                "id": "branch2",
                "type": "condition",
                "config": {
                    "condition": "status == 'pending'",
                    "service": "test_service"
                }
            },
            {
                "id": "merge",
                "type": "action",
                "config": {
                    "action": "finalize",
                    "service": "test_service"
                }
            },
            {
                "id": "end",
                "type": "action",
                "config": {
                    "action": "complete",
                    "service": "test_service"
                }
            }
        ],
        "connections": [
            {"source": "start", "target": "branch1"},
            {"source": "start", "target": "branch2"},
            {"source": "branch1", "target": "merge"},
            {"source": "branch2", "target": "merge"},
            {"source": "merge", "target": "end"}
        ]
    }


@pytest.fixture
def complex_workflow():
    """
    Pre-created 20-step workflow with complex branching for benchmarks.

    Provides a large workflow for testing performance at scale.
    Tests realistic workflow complexity encountered in production.

    Returns:
        Dict: Workflow definition with 20 steps and complex DAG structure
    """
    nodes = []
    connections = []

    # Create 20 nodes
    for i in range(20):
        nodes.append({
            "id": f"step{i}",
            "type": "action" if i % 3 != 0 else "condition",
            "config": {
                "action": f"action_{i}",
                "service": "test_service"
            }
        })

    # Create connections forming a DAG
    for i in range(19):
        connections.append({"source": f"step{i}", "target": f"step{i+1}"})

    # Add some branching
    connections.append({"source": "step5", "target": "step10"})
    connections.append({"source": "step5", "target": "step15"})
    connections.append({"source": "step10", "target": "step18"})
    connections.append({"source": "step15", "target": "step18"})

    return {
        "id": "complex_workflow",
        "name": "Complex Test Workflow",
        "nodes": nodes,
        "connections": connections
    }


@pytest.fixture
def sample_episode_context():
    """
    Pre-created episode context for benchmarks.

    Provides sample data for episode segmentation benchmarks with
    10 messages, canvas reference, and feedback.

    Returns:
        Dict: Episode context with messages, canvas, and feedback
    """
    base_time = datetime.utcnow()

    # Create 10 messages with varying timestamps
    messages = []
    for i in range(10):
        messages.append({
            "id": f"msg_{i}",
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Test message {i} with some content",
            "created_at": base_time + timedelta(minutes=i * 5),  # 5-min intervals
            "agent_id": f"agent_{uuid.uuid4().hex[:8]}",
            "session_id": f"session_{uuid.uuid4().hex[:8]}"
        })

    return {
        "agent_id": f"agent_{uuid.uuid4().hex[:8]}",
        "session_id": f"session_{uuid.uuid4().hex[:8]}",
        "messages": messages,
        "canvas_context": {
            "canvas_id": f"canvas_{uuid.uuid4().hex[:8]}",
            "canvas_type": "chart",
            "presented_at": base_time
        },
        "feedback_context": {
            "feedback_score": 0.8,
            "feedback_count": 5
        }
    }


@pytest.fixture
def large_episode_context():
    """
    Pre-created large episode context for benchmarks.

    Provides 50 messages for testing large episode performance.

    Returns:
        Dict: Episode context with 50 messages
    """
    base_time = datetime.utcnow()

    # Create 50 messages with time gaps
    messages = []
    for i in range(50):
        # Add time gap every 10 messages
        if i % 10 == 0:
            time_offset = i * 30  # 30-min gaps
        else:
            time_offset = i * 2  # 2-min intervals

        messages.append({
            "id": f"msg_{i}",
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Test message {i} with some content for testing",
            "created_at": base_time + timedelta(minutes=time_offset),
            "agent_id": f"agent_{uuid.uuid4().hex[:8]}",
            "session_id": f"session_{uuid.uuid4().hex[:8]}"
        })

    return {
        "agent_id": f"agent_{uuid.uuid4().hex[:8]}",
        "session_id": f"session_{uuid.uuid4().hex[:8]}",
        "messages": messages
    }


@pytest.fixture
def populated_governance_cache():
    """
    Pre-populated governance cache for benchmarks.

    Provides a cache with 100 entries for testing cache operations.

    Returns:
        GovernanceCache: Cache populated with test data
    """
    from core.governance_cache import GovernanceCache

    cache = GovernanceCache(max_size=1000, ttl_seconds=60)

    # Populate with 100 entries
    for i in range(100):
        agent_id = f"agent_{i}"
        action_type = f"action_{i % 5}"  # 5 different action types

        cache.set(
            agent_id=agent_id,
            action_type=action_type,
            data={
                "allowed": i % 2 == 0,  # Alternate allowed/denied
                "maturity_level": ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"][i % 4],
                "action_complexity": i % 5
            }
        )

    return cache


@pytest.fixture
def mock_llm_service():
    """
    Mock LLM service for episode benchmarks.

    Provides fast, deterministic responses for LLM-dependent benchmarks.
    Mocks embedding generation and summary generation to avoid network calls.

    Returns:
        MagicMock: Mocked LLM service
    """
    mock_llm = MagicMock()

    # Mock embedding generation (return fixed vector)
    mock_llm.generate_embedding.return_value = [0.1] * 384  # 384-dim vector

    # Mock summary generation
    mock_llm.generate_summary.return_value = "Test episode summary for benchmarking"

    return mock_llm


@pytest.fixture
def mock_db_session():
    """
    Mock database session for benchmarks.

    Provides a mock SQLAlchemy session for testing without database overhead.

    Returns:
        MagicMock: Mocked database session
    """
    db = MagicMock()

    # Mock query behavior
    mock_query = MagicMock()
    db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []

    return db


# Benchmark groups for organization
@pytest.fixture
def workflow_benchmark_groups():
    """
    Define benchmark groups for workflow tests.

    Groups:
    - workflow-validation: Schema and DAG validation tests
    - workflow-sort: Topological sort tests
    - workflow-params: Parameter resolution tests
    - workflow-conditions: Condition evaluation tests
    - workflow-state: State management tests
    """
    return {
        "workflow-validation": "Schema and DAG validation",
        "workflow-sort": "Topological sort",
        "workflow-params": "Parameter resolution",
        "workflow-conditions": "Condition evaluation",
        "workflow-state": "State management"
    }


@pytest.fixture
def episode_benchmark_groups():
    """
    Define benchmark groups for episode tests.

    Groups:
    - episode-detection: Boundary detection (time, topic)
    - episode-creation: Episode creation with messages
    - episode-segmentation: Batch segmentation
    """
    return {
        "episode-detection": "Boundary detection (time, topic)",
        "episode-creation": "Episode creation",
        "episode-segmentation": "Batch segmentation"
    }


@pytest.fixture
def governance_benchmark_groups():
    """
    Define benchmark groups for governance tests.

    Groups:
    - governance-cache: Cache operations (get, set, invalidate)
    - governance-check: Full governance checks
    """
    return {
        "governance-cache": "Cache operations",
        "governance-check": "Governance checks"
    }
