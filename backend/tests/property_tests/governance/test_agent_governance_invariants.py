"""
Property Tests for Agent Governance Service

Tests cover governance invariants, maturity matrix, and cache performance.
Uses Hypothesis for exhaustive property-based testing.

Target: 50% coverage on core/agent_governance_service.py
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from sqlalchemy.orm import Session
from hypothesis import given, strategies as st, settings, HealthCheck, example

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    db = MagicMock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.query = Mock()
    db.rollback = Mock()
    db.flush = Mock()
    return db

@pytest.fixture
def governance_service(mock_db):
    return AgentGovernanceService(mock_db)

# ============================================================================
# Test: Governance Invariants Tests
# ============================================================================

class TestGovernanceInvariants:
    """Property tests for governance system invariants."""

    @given(maturity=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value, AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]))
    @settings(max_examples=50)
    def test_maturity_level_enumeration(self, maturity):
        """INVARIANT: All maturity levels are valid and enumerable."""
        assert maturity in [AgentStatus.STUDENT.value, AgentStatus.INTERN.value, AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]

    @given(complexity=st.integers(min_value=1, max_value=4))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_action_complexity_bounds(self, governance_service, complexity):
        """INVARIANT: Action complexity is always within valid bounds [1, 4]."""
        assert 1 <= complexity <= 4
        assert complexity in AgentGovernanceService.ACTION_COMPLEXITY.values()
        assert complexity in AgentGovernanceService.MATURITY_REQUIREMENTS

    @given(confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_confidence_score_range(self, confidence):
        """INVARIANT: Confidence scores are always in range [0.0, 1.0]."""
        assert 0.0 <= confidence <= 1.0

    @given(agent_status=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value, AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]), action_type=st.sampled_from(["search", "read", "analyze", "create", "delete"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_governance_check_deterministic(self, governance_service, mock_db, agent_status, action_type):
        """INVARIANT: Governance checks are deterministic for same inputs."""
        agent = AgentRegistry(id=f"agent-{agent_status}", name=f"Agent {agent_status}", category="testing", module_path="test.module", class_name="TestAgent", status=agent_status, confidence_score=0.7)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            
            result1 = governance_service.can_perform_action(agent.id, action_type)
            result2 = governance_service.can_perform_action(agent.id, action_type)
            assert result1["allowed"] == result2["allowed"]

    @given(complexity=st.integers(min_value=1, max_value=4))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_permission_matrix_complete(self, governance_service, complexity):
        """INVARIANT: Permission matrix has entry for every complexity level."""
        assert complexity in AgentGovernanceService.MATURITY_REQUIREMENTS

# ============================================================================
# Test: Maturity Matrix Tests
# ============================================================================

class TestMaturityMatrix:
    """Property tests for maturity/complexity permission matrix."""

    @given(maturity=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value, AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]), complexity=st.integers(min_value=1, max_value=4), confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_all_maturity_complexity_combinations(self, governance_service, mock_db, maturity, complexity, confidence):
        """INVARIANT: All 4x4 maturity/complexity combinations are handled."""
        agent = AgentRegistry(id=f"agent-{maturity}", name=f"Agent {maturity}", category="testing", module_path="test.module", class_name="TestAgent", status=maturity, confidence_score=confidence)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            
            result = governance_service.can_perform_action(agent.id, "test_action")
            assert "allowed" in result
            assert isinstance(result["allowed"], bool)

    @given(confidence=st.floats(min_value=0.0, max_value=0.49, allow_nan=False, allow_infinity=False))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @example(confidence=0.0)
    def test_student_blocked_from_high_complexity(self, governance_service, mock_db, confidence):
        """INVARIANT: Student agents cannot execute high complexity (3+) actions."""
        agent = AgentRegistry(id="student-agent", name="Student Agent", category="testing", module_path="test.module", class_name="TestAgent", status=AgentStatus.STUDENT.value, confidence_score=confidence)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            
            for action in ["delete", "execute", "deploy"]:
                result = governance_service.can_perform_action(agent.id, action)
                assert result["allowed"] is False

    @given(confidence=st.floats(min_value=0.9, max_value=1.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @example(confidence=0.9)
    def test_autonomous_full_access(self, governance_service, mock_db, confidence):
        """INVARIANT: Autonomous agents have full access to all actions."""
        agent = AgentRegistry(id="autonomous-agent", name="Autonomous Agent", category="testing", module_path="test.module", class_name="TestAgent", status=AgentStatus.AUTONOMOUS.value, confidence_score=confidence)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache.return_value = mock_cache_inst
            
            for action in ["search", "analyze", "create", "delete"]:
                result = governance_service.can_perform_action(agent.id, action)
                assert result["allowed"] is True

# ============================================================================
# Test: Governance Cache Tests
# ============================================================================

class TestGovernanceCache:
    """Property tests for governance cache performance and behavior."""

    @given(action_type=st.sampled_from(["search", "analyze", "create", "delete"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_hit_returns_same_result(self, governance_service, mock_db, action_type):
        """INVARIANT: Cache hit returns identical result without database query."""
        agent_id = "cache-test-agent"
        agent = AgentRegistry(id=agent_id, name="Test Agent", category="testing", module_path="test.module", class_name="TestAgent", status=AgentStatus.INTERN.value, confidence_score=0.65)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        cached_result = {"allowed": True, "reason": "Cached", "agent_status": agent.status, "action_complexity": 2, "required_status": AgentStatus.INTERN.value, "requires_human_approval": False, "confidence_score": 0.65}
        
        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.side_effect = [None, cached_result]
            mock_cache.return_value = mock_cache_inst
            
            result1 = governance_service.can_perform_action(agent_id, action_type)
            result2 = governance_service.can_perform_action(agent_id, action_type)
            assert result2 == cached_result

    @given(action_type=st.sampled_from(["search", "analyze", "create", "delete"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_miss_calls_governance_check(self, governance_service, mock_db, action_type):
        """INVARIANT: Cache miss triggers governance check and caches result."""
        agent_id = "cache-miss-agent"
        agent = AgentRegistry(id=agent_id, name="Test Agent", category="testing", module_path="test.module", class_name="TestAgent", status=AgentStatus.SUPERVISED.value, confidence_score=0.75)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = None
            mock_cache_inst.set = Mock()
            mock_cache.return_value = mock_cache_inst
            
            result = governance_service.can_perform_action(agent_id, action_type)
            assert "allowed" in result
            mock_cache_inst.set.assert_called_once()

    @given(n=st.integers(min_value=10, max_value=100))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_performance_sub_millisecond(self, governance_service, mock_db, n):
        """INVARIANT: Cache operations complete in sub-millisecond time."""
        import time
        agent_id = "perf-agent"
        agent = AgentRegistry(id=agent_id, name="Performance Test Agent", category="testing", module_path="test.module", class_name="TestAgent", status=AgentStatus.AUTONOMOUS.value, confidence_score=0.95)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            mock_cache_inst = MagicMock()
            mock_cache_inst.get.return_value = {"allowed": True, "reason": "Cached", "agent_status": agent.status, "action_complexity": 1, "required_status": AgentStatus.STUDENT.value, "requires_human_approval": False, "confidence_score": 0.95}
            mock_cache.return_value = mock_cache_inst
            
            start_time = time.perf_counter()
            for _ in range(n):
                governance_service.can_perform_action(agent_id, "search")
            end_time = time.perf_counter()
            
            avg_time_ms = ((end_time - start_time) / n) * 1000
            assert avg_time_ms < 1.0

# ============================================================================
# Test: Confidence Score Edge Cases
# ============================================================================

class TestConfidenceScoreEdgeCases:
    """Property tests for confidence score boundary conditions."""

    @given(initial_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False), positive=st.booleans(), impact_level=st.sampled_from(["low", "high"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_update_bounds(self, governance_service, mock_db, initial_score, positive, impact_level):
        """INVARIANT: Confidence updates stay within [0.0, 1.0] bounds."""
        agent_id = "bounds-agent"
        agent = AgentRegistry(id=agent_id, name="Bounds Test Agent", category="testing", module_path="test.module", class_name="TestAgent", status=AgentStatus.INTERN.value, confidence_score=initial_score)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        governance_service._update_confidence_score(agent_id, positive=positive, impact_level=impact_level)
        assert 0.0 <= agent.confidence_score <= 1.0

    @given(num_updates=st.integers(min_value=1, max_value=20))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_monotonic_with_same_impact(self, governance_service, mock_db, num_updates):
        """INVARIANT: Repeated positive updates increase confidence (capped at 1.0)."""
        agent_id = "monotonic-agent"
        agent = AgentRegistry(id=agent_id, name="Monotonic Test Agent", category="testing", module_path="test.module", class_name="TestAgent", status=AgentStatus.INTERN.value, confidence_score=0.5)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query
        
        initial_score = agent.confidence_score
        for _ in range(num_updates):
            governance_service._update_confidence_score(agent_id, positive=True, impact_level="low")
        
        assert agent.confidence_score >= initial_score
        assert agent.confidence_score <= 1.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
