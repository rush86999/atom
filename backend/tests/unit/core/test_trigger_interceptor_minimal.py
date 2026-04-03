"""
Minimal Tests for Trigger Interceptor - Fast Validation

Coverage Target: Core logic only
Priority: P0 (Critical Safety Rail)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

pytestmark = [pytest.mark.unit, pytest.mark.fast]

from core.trigger_interceptor import (
    TriggerInterceptor,
    TriggerDecision,
    MaturityLevel,
    RoutingDecision,
)


class TestMaturityLevelBasics:
    """Basic maturity level tests - no DB dependencies"""

    def test_student_by_status(self):
        """Test STUDENT maturity from explicit status"""
        # Create minimal mock db
        mock_db = MagicMock()
        interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
        
        result = interceptor._determine_maturity_level("student", 0.3)
        assert result == MaturityLevel.STUDENT

    def test_intern_by_status(self):
        """Test INTERN maturity from explicit status"""
        mock_db = MagicMock()
        interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
        
        result = interceptor._determine_maturity_level("intern", 0.6)
        assert result == MaturityLevel.INTERN

    def test_autonomous_by_confidence(self):
        """Test AUTONOMOUS maturity from confidence score"""
        mock_db = MagicMock()
        interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
        
        result = interceptor._determine_maturity_level("unknown", 0.95)
        assert result == MaturityLevel.AUTONOMOUS

    def test_trigger_decision_creation(self):
        """Test TriggerDecision can be created"""
        decision = TriggerDecision(
            routing_decision=RoutingDecision.EXECUTION,
            execute=True,
            agent_id="agent-001",
            agent_maturity="autonomous",
            confidence_score=0.95,
            trigger_source="manual"
        )
        
        assert decision.execute is True
        assert decision.agent_id == "agent-001"
        assert decision.routing_decision == RoutingDecision.EXECUTION


@pytest.mark.asyncio
async def test_cache_hit_path():
    """Test cache hit path - no DB query"""
    mock_db = MagicMock()
    interceptor = TriggerInterceptor(db=mock_db, workspace_id="ws-001")
    
    with patch('core.trigger_interceptor.get_async_governance_cache') as mock_get:
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value={"status": "autonomous", "confidence": 0.95})
        mock_get.return_value = mock_cache
        
        status, confidence = await interceptor._get_agent_maturity_cached("agent-001")
        
        assert status == "autonomous"
        assert confidence == 0.95
        # Verify DB was NOT queried
        mock_db.query.assert_not_called()
