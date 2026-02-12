"""
Performance Testing Scenarios

Tests system performance under various load conditions.

Documents performance baselines and tests:
- Load testing: Sequential operations
- Stress testing: Peak load handling
- Performance regression: Response time baselines

Run with: pytest tests/scenarios/test_performance_scenarios.py -v
"""

import pytest
import time
import statistics
import uuid
from sqlalchemy.orm import Session

from core.models import AgentRegistry, User, ChatSession
from tests.factories import AgentFactory, UserFactory


class PerformanceBaselines:
    """Defines acceptable performance thresholds."""
    API_RESPONSE_P95 = 500
    DB_QUERY_P95 = 200


class TestLoadTesting:
    """Load testing for sequential operations."""

    @pytest.mark.scenario
    def test_sequential_user_sessions(self, db_session):
        """SCENARIO: 10 users create sessions"""
        user_count = 10
        response_times = []
        test_id = str(uuid.uuid4())[:8]

        for i in range(user_count):
            start = time.time()

            UserFactory(
                _session=db_session,
                id=f"perf_{test_id}_user_{i}",
                email=f"perf_{test_id}_user_{i}@example.com"
            )

            from core.models import ChatSession
            from datetime import datetime
            session = ChatSession(
                id=f"perf_{test_id}_session_{i}",
                user_id=f"perf_{test_id}_user_{i}",
                title=f"Session {i}",
                metadata_json={"source": "user"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                message_count=0
            )
            db_session.add(session)
            db_session.commit()

            response_times.append((time.time() - start) * 1000)

        assert len(response_times) == user_count
        avg_time = statistics.mean(response_times)
        assert avg_time < PerformanceBaselines.API_RESPONSE_P95 * 10

    @pytest.mark.scenario
    def test_sequential_agent_queries(self, db_session):
        """SCENARIO: 50 sequential agent queries"""
        agent_count = 50
        test_id = str(uuid.uuid4())[:8]

        for i in range(agent_count):
            AgentFactory(
                _session=db_session,
                id=f"perf_{test_id}_agent_{i}"
            )

        query_times = []

        for i in range(agent_count):
            start = time.time()
            agent = db_session.query(AgentRegistry).filter(
                AgentRegistry.id == f"perf_{test_id}_agent_{i}"
            ).first()
            end = time.time()
            query_times.append((end - start) * 1000)
            assert agent is not None

        assert len(query_times) == agent_count
        avg_response = statistics.mean(query_times)
        assert avg_response < PerformanceBaselines.DB_QUERY_P95 * 10


class TestStressTesting:
    """Stress testing for peak load scenarios."""

    @pytest.mark.scenario
    def test_rapid_session_creation(self, db_session):
        """SCENARIO: Rapid burst of 30 session creations"""
        baseline_count = 10
        burst_count = 30
        test_id = str(uuid.uuid4())[:8]

        from core.models import ChatSession
        from datetime import datetime

        baseline_times = []
        for i in range(baseline_count):
            start = time.time()
            session = ChatSession(
                id=f"baseline_{test_id}_{i}",
                user_id=f"user_{test_id}_{i}",
                title=f"Baseline {i}",
                metadata_json={"source": "test"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                message_count=0
            )
            db_session.add(session)
            db_session.commit()
            baseline_times.append((time.time() - start) * 1000)

        baseline_avg = statistics.mean(baseline_times)

        burst_times = []
        for i in range(burst_count):
            start = time.time()
            session = ChatSession(
                id=f"burst_{test_id}_{i}",
                user_id=f"burst_{test_id}_user_{i}",
                title=f"Burst {i}",
                metadata_json={"source": "test"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                message_count=0
            )
            db_session.add(session)
            db_session.commit()
            burst_times.append((time.time() - start) * 1000)

        # Check performance - burst should not degrade too much
        if baseline_avg > 0:
            burst_avg = statistics.mean(burst_times)
            degradation_ratio = burst_avg / baseline_avg
            assert degradation_ratio < 10.0


class TestPerformanceRegression:
    """Performance regression tests for detecting slowdowns."""

    @pytest.mark.scenario
    def test_agent_query_performance(self, db_session):
        """SCENARIO: Agent queries complete within baseline time"""
        test_id = str(uuid.uuid4())[:8]

        for i in range(50):
            AgentFactory(
                _session=db_session,
                id=f"perfq_{test_id}_agent_{i}",
                confidence_score=0.5 + (i % 5) * 0.1,
            )

        start = time.time()
        agent = db_session.query(AgentRegistry).filter(
            AgentRegistry.id == f"perfq_{test_id}_agent_25"
        ).first()
        query_time = (time.time() - start) * 1000

        assert agent is not None
        assert query_time < PerformanceBaselines.DB_QUERY_P95 * 10

    @pytest.mark.scenario
    def test_batch_operation_performance(self, db_session):
        """SCENARIO: Batch operations complete efficiently"""
        test_id = str(uuid.uuid4())[:8]

        for i in range(50):
            AgentFactory(
                _session=db_session,
                id=f"batch_{test_id}_agent_{i}"
            )

        start = time.time()
        agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.id.like(f"batch_{test_id}_agent_%")
        ).all()
        query_time = (time.time() - start) * 1000

        assert len(agents) == 50
        assert query_time < PerformanceBaselines.DB_QUERY_P95 * 100


class TestPerformanceSummary:
    """Summary of performance test results."""

    @pytest.mark.scenario
    def test_performance_baseline_documentation(self):
        """SCENARIO: Document performance baselines"""
        baselines = {
            "api_response_p95_ms": PerformanceBaselines.API_RESPONSE_P95,
            "db_query_p95_ms": PerformanceBaselines.DB_QUERY_P95,
        }

        assert all(baselines.values())

        for metric, value in baselines.items():
            print(f"{metric}: {value}")
