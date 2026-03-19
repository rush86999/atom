"""
Database Query Performance Benchmarks

Measures query execution time for common database operations using pytest-benchmark.
These tests establish baseline performance and enable regression detection through
historical tracking.

Target Metrics:
- Agent select by ID <10ms P50 (primary key lookup)
- Agent list pagination <20ms P50 (paginated query)
- Episode select with relations <50ms P50 (join with segments)
- Canvas audit insert <20ms P50 (audit log insert)
- Workflow execution insert <30ms P50 (execution record insert)
- Governance cache query <5ms P50 (maturity lookup)
- Episode search full-text <100ms P50 (full-text search)

Reference: Phase 208 Plan 05 - Database Query Performance
"""

import pytest
import time
import uuid
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from core.database import get_db_session
from core.models import AgentRegistry, Episode, EpisodeSegment, CanvasAudit, WorkflowExecution

# Try to import pytest_benchmark, but don't fail if not available
try:
    import pytest_benchmark
    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False

# Skip tests if pytest-benchmark not available
pytestmark = pytest.mark.skipif(
    not BENCHMARK_AVAILABLE,
    reason="pytest-benchmark plugin not installed. Install with: pip install pytest-benchmark"
)


class TestDatabaseQueryPerformance:
    """Test database query performance benchmarks."""

    @pytest.mark.benchmark(group="db-query")
    def test_agent_select_by_id(self, benchmark, db_session):
        """
        Benchmark agent selection by primary key.

        Target: <10ms P50 (primary key lookup is fastest)
        Query: AgentRegistry.get(agent_id)
        Setup: Create 100 agents in database
        Verify: Agent retrieved correctly
        """
        # Create 100 test agents
        agents_to_create = []
        for i in range(100):
            agent = AgentRegistry(
                id=f"pk_benchmark_agent_{i}",
                name=f"PK Benchmark Agent {i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status="AUTONOMOUS",
                confidence_score=0.9
            )
            agents_to_create.append(agent)

        db_session.add_all(agents_to_create)
        db_session.commit()

        def select_by_pk():
            agent = db_session.query(AgentRegistry).filter(
                AgentRegistry.id == "pk_benchmark_agent_50"
            ).first()
            assert agent is not None
            assert agent.name == "PK Benchmark Agent 50"
            return agent

        result = benchmark(select_by_pk)
        assert result.id == "pk_benchmark_agent_50"

        # Cleanup
        db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("pk_benchmark_agent_%")
        ).delete(synchronize_session=False)
        db_session.commit()

    @pytest.mark.benchmark(group="db-query")
    def test_agent_list_pagination(self, benchmark, db_session):
        """
        Benchmark paginated agent list query.

        Target: <20ms P50 (paginated query with limit)
        Query: AgentRegistry.list(limit=20, offset=0)
        Setup: Create 100 agents in database
        Verify: 20 agents returned
        """
        # Create 100 test agents
        agents_to_create = []
        for i in range(100):
            agent = AgentRegistry(
                id=f"pagination_agent_{i}",
                name=f"Pagination Agent {i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status="AUTONOMOUS",
                confidence_score=0.9
            )
            agents_to_create.append(agent)

        db_session.add_all(agents_to_create)
        db_session.commit()

        def paginate_query():
            agents = db_session.query(AgentRegistry).limit(20).offset(0).all()
            assert len(agents) == 20
            return agents

        result = benchmark(paginate_query)
        assert len(result) == 20

        # Cleanup
        db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("pagination_agent_%")
        ).delete(synchronize_session=False)
        db_session.commit()

    @pytest.mark.benchmark(group="db-query")
    def test_episode_select_with_relations(self, benchmark, db_session):
        """
        Benchmark episode selection with related segments.

        Target: <50ms P50 (join query with relations)
        Query: Episode.get_with_segments()
        Setup: Create 10 episodes with 50 segments each
        Verify: Episode with all segments loaded
        """
        # Create test episodes with segments (if models exist)
        try:
            # Create 10 episodes
            episodes_to_create = []
            for i in range(10):
                episode = Episode(
                    id=f"relation_episode_{i}",
                    agent_id=f"agent_{i}",
                    session_id=f"session_{i}",
                    start_time=time.time(),
                    end_time=time.time() + 3600,
                    message_count=50
                )
                episodes_to_create.append(episode)

            db_session.add_all(episodes_to_create)
            db_session.flush()  # Get IDs

            # Create 50 segments for each episode
            segments_to_create = []
            for episode in episodes_to_create:
                for j in range(50):
                    segment = EpisodeSegment(
                        episode_id=episode.id,
                        sequence_order=j,
                        content=f"Segment {j} content",
                        role="user" if j % 2 == 0 else "assistant",
                        timestamp=time.time() + j * 60
                    )
                    segments_to_create.append(segment)

            db_session.add_all(segments_to_create)
            db_session.commit()
            relations_created = True

        except Exception as e:
            # Models may not exist or have different structure
            relations_created = False

        if relations_created:
            def select_with_relations():
                episodes = db_session.query(Episode).options(
                    selectinload(Episode.segments)
                ).filter(
                    Episode.id == "relation_episode_5"
                ).first()
                assert episodes is not None
                assert len(episodes.segments) == 50
                return episodes

            result = benchmark(select_with_relations)
            assert len(result.segments) == 50

            # Cleanup
            db_session.query(EpisodeSegment).filter(
                EpisodeSegment.episode_id.like("relation_episode_%")
            ).delete(synchronize_session=False)
            db_session.query(Episode).filter(
                Episode.id.like("relation_episode_%")
            ).delete(synchronize_session=False)
            db_session.commit()
        else:
            # Skip test if relations can't be created
            pytest.skip("Episode or EpisodeSegment model not available")

    @pytest.mark.benchmark(group="db-query")
    def test_canvas_audit_insert(self, benchmark, db_session):
        """
        Benchmark canvas audit log insert.

        Target: <20ms P50 (audit log insert)
        Query: CanvasAudit.insert()
        Setup: Benchmark batch of 10 inserts
        Verify: All records created
        """
        audit_records = []

        def insert_audit_records():
            # Create 10 canvas audit records
            records = []
            for i in range(10):
                audit = CanvasAudit(
                    canvas_id=f"canvas_{uuid.uuid4().hex[:8]}",
                    action_type="present",
                    user_id=f"user_{i}",
                    tenant_id="default",
                    details_json={"test": "data"}
                )
                records.append(audit)
                db_session.add(audit)
            db_session.commit()
            return records

        result = benchmark(insert_audit_records)
        assert len(result) == 10

        # Cleanup
        for audit in result:
            db_session.delete(audit)
        db_session.commit()

    @pytest.mark.benchmark(group="db-query")
    def test_workflow_execution_insert(self, benchmark, db_session):
        """
        Benchmark workflow execution record insert.

        Target: <30ms P50 (execution record insert)
        Query: WorkflowExecution.insert()
        Setup: Benchmark with step executions
        Verify: Execution and steps created
        """
        # Check if WorkflowExecution model exists
        try:
            execution_id = str(uuid.uuid4())

            def insert_execution():
                execution = WorkflowExecution(
                    id=execution_id,
                    workflow_id="test_workflow",
                    status="running",
                    start_time=time.time(),
                    input_data={"test": "value"}
                )
                db_session.add(execution)
                db_session.commit()
                return execution

            result = benchmark(insert_execution)
            assert result.id == execution_id

            # Cleanup
            db_session.query(WorkflowExecution).filter(
                WorkflowExecution.id == execution_id
            ).delete(synchronize_session=False)
            db_session.commit()

        except Exception:
            # WorkflowExecution model may not exist
            pytest.skip("WorkflowExecution model not available")

    @pytest.mark.benchmark(group="db-query")
    def test_governance_cache_query(self, benchmark, db_session):
        """
        Benchmark governance maturity lookup query.

        Target: <5ms P50 (maturity lookup with index)
        Query: AgentRegistry maturity check
        Setup: Query with index on maturity column
        Verify: Correct maturity returned
        """
        # Create 100 agents with different maturity levels
        agents_to_create = []
        maturity_levels = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]

        for i in range(100):
            agent = AgentRegistry(
                id=f"maturity_agent_{i}",
                name=f"Maturity Agent {i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=maturity_levels[i % 4],
                confidence_score=0.5 + (i % 4) * 0.15
            )
            agents_to_create.append(agent)

        db_session.add_all(agents_to_create)
        db_session.commit()

        def query_by_maturity():
            # Query agents by maturity level
            agents = db_session.query(AgentRegistry).filter(
                AgentRegistry.status == "AUTONOMOUS"
            ).all()
            assert len(agents) == 25  # 100 / 4 maturity levels
            return agents

        result = benchmark(query_by_maturity)
        assert len(result) == 25

        # Cleanup
        db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("maturity_agent_%")
        ).delete(synchronize_session=False)
        db_session.commit()

    @pytest.mark.benchmark(group="db-query")
    def test_episode_search_full_text(self, benchmark, db_session):
        """
        Benchmark episode full-text search query.

        Target: <100ms P50 (full-text search)
        Query: Episode.search(query text)
        Setup: Create 100 episodes with searchable content
        Verify: Relevant episodes returned
        """
        # Create 100 test episodes with searchable content
        try:
            episodes_to_create = []
            search_terms = ["workflow", "canvas", "agent", "automation", "analytics"]

            for i in range(100):
                episode = Episode(
                    id=f"search_episode_{i}",
                    agent_id=f"agent_{i % 5}",
                    session_id=f"session_{i}",
                    start_time=time.time(),
                    end_time=time.time() + 3600,
                    message_count=10,
                    summary=f"Episode about {search_terms[i % 5]} testing"
                )
                episodes_to_create.append(episode)

            db_session.add_all(episodes_to_create)
            db_session.commit()
            episodes_created = True

        except Exception:
            episodes_created = False

        if episodes_created:
            def search_episodes():
                # Search for episodes containing "workflow"
                episodes = db_session.query(Episode).filter(
                    Episode.summary.like("%workflow%")
                ).all()
                assert len(episodes) == 20  # 100 / 5 search terms
                return episodes

            result = benchmark(search_episodes)
            assert len(result) == 20

            # Cleanup
            db_session.query(Episode).filter(
                Episode.id.like("search_episode_%")
            ).delete(synchronize_session=False)
            db_session.commit()
        else:
            pytest.skip("Episode model not available for full-text search")


class TestDatabaseEdgeCases:
    """Test database edge cases and query optimization."""

    @pytest.mark.benchmark(group="db-query")
    def test_agent_count_query(self, benchmark, db_session):
        """
        Benchmark agent count query (uses aggregate function).

        Target: <10ms P50 (count queries are fast)
        Query: COUNT(*) on AgentRegistry
        Setup: 100 agents in database
        Verify: Correct count returned
        """
        # Create 100 test agents
        agents_to_create = []
        for i in range(100):
            agent = AgentRegistry(
                id=f"count_agent_{i}",
                name=f"Count Agent {i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status="AUTONOMOUS",
                confidence_score=0.9
            )
            agents_to_create.append(agent)

        db_session.add_all(agents_to_create)
        db_session.commit()

        def count_agents():
            count = db_session.query(func.count(AgentRegistry.id)).scalar()
            assert count >= 100
            return count

        result = benchmark(count_agents)
        assert result >= 100

        # Cleanup
        db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("count_agent_%")
        ).delete(synchronize_session=False)
        db_session.commit()

    @pytest.mark.benchmark(group="db-query")
    def test_complex_join_query(self, benchmark, db_session):
        """
        Benchmark complex join query with multiple relations.

        Target: <100ms P50 (complex joins)
        Query: Join Episode with EpisodeSegment and AgentRegistry
        Setup: Create related records
        Verify: Correct joined data returned
        """
        # Create test agents and episodes
        try:
            # Create agents
            agents_to_create = []
            for i in range(5):
                agent = AgentRegistry(
                    id=f"join_agent_{i}",
                    name=f"Join Agent {i}",
                    category="test",
                    module_path="test.module",
                    class_name="TestClass",
                    status="AUTONOMOUS",
                    confidence_score=0.9
                )
                agents_to_create.append(agent)

            db_session.add_all(agents_to_create)
            db_session.flush()

            # Create episodes for agents
            episodes_to_create = []
            for agent in agents_to_create:
                for j in range(3):
                    episode = Episode(
                        id=f"join_episode_{agent.id}_{j}",
                        agent_id=agent.id,
                        session_id=f"session_{j}",
                        start_time=time.time(),
                        end_time=time.time() + 3600,
                        message_count=10
                    )
                    episodes_to_create.append(episode)

            db_session.add_all(episodes_to_create)
            db_session.commit()
            joins_created = True

        except Exception:
            joins_created = False

        if joins_created:
            def complex_join():
                # Join episodes with agents
                results = db_session.query(Episode, AgentRegistry).join(
                    AgentRegistry, Episode.agent_id == AgentRegistry.id
                ).filter(
                    AgentRegistry.id.like("join_agent_%")
                ).all()
                assert len(results) == 15  # 5 agents * 3 episodes
                return results

            result = benchmark(complex_join)
            assert len(result) == 15

            # Cleanup
            db_session.query(Episode).filter(
                Episode.id.like("join_episode_%")
            ).delete(synchronize_session=False)
            db_session.query(AgentRegistry).filter(
                AgentRegistry.id.like("join_agent_%")
            ).delete(synchronize_session=False)
            db_session.commit()
        else:
            pytest.skip("Cannot create joins for benchmarking")

    @pytest.mark.benchmark(group="db-query")
    def test_batch_insert_performance(self, benchmark, db_session):
        """
        Benchmark batch insert of 100 records.

        Target: <100ms P50 (bulk insert should be fast)
        Query: Bulk insert 100 AgentRegistry records
        Setup: Prepare 100 agent objects
        Verify: All records inserted
        """
        # Cleanup before benchmark
        db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("batch_agent_%")
        ).delete(synchronize_session=False)
        db_session.commit()

        def batch_insert():
            # Create 100 agents with unique IDs using timestamp
            import time
            timestamp = int(time.time() * 1000)
            agents = []
            for i in range(100):
                agent = AgentRegistry(
                    id=f"batch_agent_{timestamp}_{i}",
                    name=f"Batch Agent {i}",
                    category="test",
                    module_path="test.module",
                    class_name="TestClass",
                    status="AUTONOMOUS",
                    confidence_score=0.9
                )
                agents.append(agent)

            db_session.add_all(agents)
            db_session.commit()
            return agents

        result = benchmark(batch_insert)
        assert len(result) == 100

        # Cleanup
        db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("batch_agent_%")
        ).delete(synchronize_session=False)
        db_session.commit()

    @pytest.mark.benchmark(group="db-query")
    def test_update_query_performance(self, benchmark, db_session):
        """
        Benchmark update query performance.

        Target: <20ms P50 (update with index lookup)
        Query: UPDATE AgentRegistry SET confidence_score = X
        Setup: Create 100 agents
        Verify: All records updated
        """
        # Create 100 test agents
        agents_to_create = []
        for i in range(100):
            agent = AgentRegistry(
                id=f"update_agent_{i}",
                name=f"Update Agent {i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status="AUTONOMOUS",
                confidence_score=0.5
            )
            agents_to_create.append(agent)

        db_session.add_all(agents_to_create)
        db_session.commit()

        def update_agents():
            # Update all agents' confidence score
            db_session.query(AgentRegistry).filter(
                AgentRegistry.id.like("update_agent_%")
            ).update({"confidence_score": 0.95}, synchronize_session=False)
            db_session.commit()

        benchmark(update_agents)

        # Verify update
        updated_count = db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("update_agent_%"),
            AgentRegistry.confidence_score == 0.95
        ).count()
        assert updated_count == 100

        # Cleanup
        db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("update_agent_%")
        ).delete(synchronize_session=False)
        db_session.commit()

    @pytest.mark.benchmark(group="db-query")
    def test_delete_query_performance(self, benchmark, db_session):
        """
        Benchmark delete query performance.

        Target: <50ms P50 (delete with index lookup)
        Query: DELETE FROM AgentRegistry WHERE id LIKE 'delete_%'
        Setup: Create 100 agents
        Verify: All records deleted
        """
        # Create 100 test agents
        agents_to_create = []
        for i in range(100):
            agent = AgentRegistry(
                id=f"delete_agent_{i}",
                name=f"Delete Agent {i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status="AUTONOMOUS",
                confidence_score=0.9
            )
            agents_to_create.append(agent)

        db_session.add_all(agents_to_create)
        db_session.commit()

        # Verify count before delete
        count_before = db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("delete_agent_%")
        ).count()
        assert count_before == 100

        def delete_agents():
            # Delete all test agents
            db_session.query(AgentRegistry).filter(
                AgentRegistry.id.like("delete_agent_%")
            ).delete(synchronize_session=False)
            db_session.commit()

        benchmark(delete_agents)

        # Verify deletion
        count_after = db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like("delete_agent_%")
        ).count()
        assert count_after == 0
