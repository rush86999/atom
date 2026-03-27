"""
Database Query Regression Tests

Detects performance regressions in database query performance by comparing
current benchmark results against historical baselines.

Tests:
- Agent list query with 100 records (target: <10ms)
- Episode filter query with 50 records (target: <20ms)
- Pagination query with offset/limit (target: <15ms)

Uses pytest-benchmark for historical tracking and check_regression fixture
to fail tests when performance degrades beyond 20% threshold.

Baselines stored in performance_baseline.json:
- db_agent_query: 0.010s (10ms)
- db_episode_filter: 0.020s (20ms)
- db_pagination: 0.015s (15ms)

Reference: Phase 243 Plan 02 - Performance Regression Detection
"""

import pytest
from uuid import uuid4
from sqlalchemy import func

from core.models import AgentRegistry, Episode
from core.database import get_db

# Try to import pytest_benchmark, but don't fail if not available
try:
    import pytest_benchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False

# Skip all tests if pytest-benchmark is not available
pytestmark = pytest.mark.skipif(
    not BENCHMARK_AVAILABLE,
    reason="pytest-benchmark plugin not installed. Install with: pip install pytest-benchmark"
)

pytestmark = pytest.mark.performance_regression


@pytest.mark.benchmark(group="database-query")
def test_db_agent_list_query(benchmark, db_session, check_regression):
    """
    Benchmark agent list query with 100 agents.

    Target: <10ms P50 (agent listing with 100 records)
    Query: SELECT * FROM agents LIMIT 100
    Baseline: db_agent_query (0.010s)
    Threshold: 20% regression

    Test Quality Standards (TQ-01):
    - Clear objective: Measure agent query performance with realistic load
    - Documented target: <10ms P50
    - Baseline value: 0.010s (10ms)
    - Test isolation: Uses db_session fixture for database isolation
    - Benchmark grouping: @pytest.mark.benchmark(group="database-query")
    """
    # Create 100 test agents
    agents = []
    for i in range(100):
        agent = AgentRegistry(
            id=f"perf_test_agent_{i}_{uuid4()}",
            name=f"Performance Test Agent {i}",
            category="performance_test",
            module_path="test.module",
            class_name="TestClass",
            status="AUTONOMOUS",
            confidence_score=0.9
        )
        agents.append(agent)
        db_session.add(agent)
    db_session.commit()

    def query_agents():
        # Query all agents
        result = db_session.query(AgentRegistry).limit(100).all()
        assert len(result) == 100
        return result

    result = benchmark(query_agents)

    # Check regression: should not be >20% slower than baseline
    check_regression(benchmark.stats.stats.mean, "db_agent_query", threshold=0.2)

    # Verify query succeeded
    assert len(result) == 100


@pytest.mark.benchmark(group="database-query")
def test_db_episode_filter_query(benchmark, db_session, check_regression):
    """
    Benchmark episode filter query with 50 episodes.

    Target: <20ms P50 (episode filtering with WHERE clause)
    Query: SELECT * FROM episodes WHERE agent_id = ? LIMIT 50
    Baseline: db_episode_filter (0.020s)
    Threshold: 20% regression

    Test Quality Standards (TQ-01):
    - Clear objective: Measure episode filter query performance
    - Documented target: <20ms P50
    - Baseline value: 0.020s (20ms)
    - Test isolation: Uses db_session fixture for database isolation
    - Benchmark grouping: @pytest.mark.benchmark(group="database-query")
    """
    # Create test agent
    agent_id = f"perf_test_agent_{uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Performance Test Agent",
        category="performance_test",
        module_path="test.module",
        class_name="TestClass",
        status="AUTONOMOUS",
        confidence_score=0.9
    )
    db_session.add(agent)
    db_session.commit()

    # Create 50 episodes for this agent
    episodes = []
    for i in range(50):
        episode = Episode(
            id=f"perf_test_episode_{i}_{uuid4()}",
            agent_id=agent_id,
            workspace_id="default",
            status="COMPLETED",
            title=f"Performance Test Episode {i}",
            summary={"test": f"episode_{i}"}
        )
        episodes.append(episode)
        db_session.add(episode)
    db_session.commit()

    def query_episodes():
        # Filter episodes by agent_id
        result = db_session.query(Episode).filter(
            Episode.agent_id == agent_id
        ).limit(50).all()
        assert len(result) == 50
        return result

    result = benchmark(query_episodes)

    # Check regression: should not be >20% slower than baseline
    check_regression(benchmark.stats.stats.mean, "db_episode_filter", threshold=0.2)

    # Verify query succeeded
    assert len(result) == 50


@pytest.mark.benchmark(group="database-query")
def test_db_pagination_query(benchmark, db_session, check_regression):
    """
    Benchmark pagination query with offset/limit.

    Target: <15ms P50 (pagination with OFFSET and LIMIT)
    Query: SELECT * FROM agents LIMIT 10 OFFSET 50
    Baseline: db_pagination (0.015s)
    Threshold: 20% regression

    Test Quality Standards (TQ-01):
    - Clear objective: Measure pagination query performance
    - Documented target: <15ms P50
    - Baseline value: 0.015s (15ms)
    - Test isolation: Uses db_session fixture for database isolation
    - Benchmark grouping: @pytest.mark.benchmark(group="database-query")
    """
    # Create 100 test agents for pagination
    for i in range(100):
        agent = AgentRegistry(
            id=f"perf_test_agent_pagination_{i}_{uuid4()}",
            name=f"Pagination Test Agent {i}",
            category="pagination_test",
            module_path="test.module",
            class_name="TestClass",
            status="AUTONOMOUS",
            confidence_score=0.9
        )
        db_session.add(agent)
    db_session.commit()

    def paginate_agents():
        # Query with offset and limit (simulating page 6 of 10 items per page)
        result = db_session.query(AgentRegistry).offset(50).limit(10).all()
        assert len(result) == 10
        return result

    result = benchmark(paginate_agents)

    # Check regression: should not be >20% slower than baseline
    check_regression(benchmark.stats.stats.mean, "db_pagination", threshold=0.2)

    # Verify pagination worked correctly
    assert len(result) == 10


class TestDatabaseQualityTargets:
    """
    Verify database quality targets are documented and achievable.

    These tests validate that the performance targets are reasonable
    and that the baseline values are correctly defined.
    """

    def test_db_agent_query_baseline_exists(self, performance_baseline):
        """Verify db_agent_query baseline is defined."""
        assert "db_agent_query" in performance_baseline
        assert performance_baseline["db_agent_query"] == 0.010

    def test_db_episode_filter_baseline_exists(self, performance_baseline):
        """Verify db_episode_filter baseline is defined."""
        assert "db_episode_filter" in performance_baseline
        assert performance_baseline["db_episode_filter"] == 0.020

    def test_db_pagination_baseline_exists(self, performance_baseline):
        """Verify db_pagination baseline is defined."""
        assert "db_pagination" in performance_baseline
        assert performance_baseline["db_pagination"] == 0.015
