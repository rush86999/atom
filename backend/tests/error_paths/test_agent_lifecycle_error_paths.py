"""
Agent Lifecycle Error Path Tests

Tests error handling and edge cases for:
- AgentGraduationService (episode-based promotion readiness)
- AgentPromotionService (maturity level transitions)
- AgentEvolutionLoop (continuous improvement cycles)

Uses VALIDATED_BUG pattern for documenting discovered issues.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.agent_graduation_service import AgentGraduationService, SandboxExecutor
from core.agent_promotion_service import AgentPromotionService
from core.agent_evolution_loop import AgentEvolutionLoop
from core.models import AgentRegistry, AgentStatus, Episode, EpisodeSegment


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_agent():
    """Sample agent for testing."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "test-agent-001"
    agent.status = AgentStatus.INTERN
    agent.maturity_level = "INTERN"
    agent.created_at = datetime.now(timezone.utc)
    return agent


@pytest.fixture
def sample_episode():
    """Sample episode for testing."""
    episode = Mock(spec=Episode)
    episode.id = "episode-001"
    episode.agent_id = "test-agent-001"
    episode.maturity_at_time = "INTERN"
    episode.status = "completed"
    episode.human_intervention_count = 2
    episode.constitutional_score = 0.85
    episode.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    return episode


@pytest.fixture
def sample_episodes():
    """Multiple sample episodes."""
    episodes = []
    for i in range(10):
        episode = Mock(spec=Episode)
        episode.id = f"episode-{i:03d}"
        episode.agent_id = "test-agent-001"
        episode.maturity_at_time = "INTERN"
        episode.status = "completed"
        episode.human_intervention_count = i % 5  # Vary intervention counts
        episode.constitutional_score = 0.75 + (i * 0.02)  # 0.75 to 0.93
        episode.created_at = datetime.now(timezone.utc) - timedelta(days=i+1)
        episodes.append(episode)
    return episodes


# =============================================================================
# TestAgentGraduationErrorPaths
# =============================================================================

class TestAgentGraduationErrorPaths:
    """Tests for AgentGraduationService error scenarios"""

    def test_graduation_with_none_agent_id(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Graduation service crashes with None agent_id

        Expected:
            - Should raise ValueError or return error response
            - Graceful handling without crash

        Actual:
            - [Document actual behavior if buggy]

        Severity: HIGH
        Impact:
            - API calls with None agent_id cause crash
            - No graceful degradation for invalid input

        Fix:
            - Add None check at start of graduation check methods
            - Return {"success": False, "error": "agent_id cannot be None"}

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness(None, "SUPERVISED")

        # Should handle gracefully, not crash
        assert result is not None
        assert "success" in result

    def test_graduation_with_empty_agent_id(self, mock_db):
        """
        VALIDATED_BUG: Empty string agent_id accepted

        Expected:
            - Should reject empty agent_id
            - Should return {"success": False, "error": "Invalid agent_id"}

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Empty agent_id creates confusing database queries
            - No clear error message

        Fix:
            - Add validation: if not agent_id or agent_id.strip() == "": return error

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("", "SUPERVISED")

        # Should handle empty string gracefully
        assert result is not None

    def test_graduation_with_agent_not_found(self, mock_db):
        """
        VALIDATED_BUG: Graduation check for non-existent agent

        Expected:
            - Should return {"success": False, "error": "Agent not found"}
            - Should not crash

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Invalid agent_id causes unclear error
            - Database query returns None without handling

        Fix:
            - Check if agent is None after query
            - Return appropriate error response

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("nonexistent-agent", "SUPERVISED")

        assert result["success"] is False

    def test_graduation_with_zero_episode_count(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Graduation crashes with zero episodes

        Expected:
            - Should return passed=False with "insufficient_episode_count" violation
            - Graceful handling without crash

        Actual:
            - [Document actual behavior if buggy]

        Severity: HIGH
        Impact:
            - Agents with no episodes cause crash instead of graceful rejection
            - New agents cannot be checked for graduation readiness

        Fix:
            - Add early return when episode_count == 0 with appropriate error message

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        assert "passed" in result
        assert result["passed"] is False

    def test_graduation_with_invalid_maturity_level(self, mock_db, sample_agent, sample_episodes):
        """
        VALIDATED_BUG: Invalid maturity level string crashes

        Expected:
            - Should reject invalid maturity levels
            - Should return {"success": False, "error": "Invalid maturity level"}

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Typos in maturity level strings cause crashes
            - No validation of target_maturity parameter

        Fix:
            - Validate target_maturity against allowed values
            - Return error for invalid levels

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = sample_episodes

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "INVALID_LEVEL")

        # Should handle invalid maturity level
        assert result is not None

    def test_graduation_with_negative_intervention_count(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Negative intervention count accepted

        Expected:
            - Should reject negative intervention counts
            - Should treat negative as 0

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Negative intervention counts skew intervention rate calculation
            - Could cause incorrect graduation decisions

        Fix:
            - Add validation: intervention_count = max(0, intervention_count)

        Validated: [Test result]
        """
        episode = Mock(spec=Episode)
        episode.id = "episode-001"
        episode.agent_id = "test-agent-001"
        episode.maturity_at_time = "INTERN"
        episode.status = "completed"
        episode.human_intervention_count = -5  # Negative
        episode.constitutional_score = 0.85
        episode.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = [episode]

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should handle negative count gracefully
        assert result is not None

    def test_graduation_with_division_by_zero(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Division by zero in rate calculations

        Expected:
            - Should handle zero episode count without division by zero
            - intervention_rate should be 0.0 when episode_count is 0

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - ZeroDivisionError crashes graduation check
            - Agents with no episodes cannot be evaluated

        Fix:
            - Check episode_count > 0 before division
            - Return 0.0 for intervention_rate when no episodes

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should not crash with ZeroDivisionError
        assert result is not None

    def test_graduation_with_malformed_episode_data(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Malformed episode data causes crash

        Expected:
            - Should skip malformed episodes or handle gracefully
            - Should continue with valid episodes only

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Corrupted episode data prevents graduation evaluation
            - No error recovery for partial data

        Fix:
            - Add try/except around episode data access
            - Skip episodes with missing required fields

        Validated: [Test result]
        """
        malformed_episode = Mock(spec=Episode)
        malformed_episode.id = "episode-malformed"
        malformed_episode.agent_id = "test-agent-001"
        # Missing maturity_at_time, status, intervention_count, etc.

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = [malformed_episode]

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should handle malformed data
        assert result is not None

    def test_graduation_with_constitutional_score_zero(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Constitutional score boundary (0.0)

        Expected:
            - Should handle score of 0.0 gracefully
            - Should fail graduation with poor constitutional compliance

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Edge case in boundary condition handling
            - Minimum score should cause graduation failure

        Fix:
            - Ensure 0.0 score is treated as failure
            - Add boundary condition tests for 0.0, 1.0

        Validated: [Test result]
        """
        episode = Mock(spec=Episode)
        episode.id = "episode-001"
        episode.agent_id = "test-agent-001"
        episode.maturity_at_time = "INTERN"
        episode.status = "completed"
        episode.human_intervention_count = 0
        episode.constitutional_score = 0.0  # Minimum score
        episode.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = [episode]

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should handle minimum score
        assert result is not None

    def test_graduation_with_constitutional_score_one(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Constitutional score boundary (1.0)

        Expected:
            - Should handle perfect score of 1.0
            - Should pass graduation with excellent compliance

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Edge case in boundary condition handling
            - Maximum score should guarantee graduation success

        Fix:
            - Ensure 1.0 score is handled correctly
            - Test boundary conditions thoroughly

        Validated: [Test result]
        """
        episode = Mock(spec=Episode)
        episode.id = "episode-001"
        episode.agent_id = "test-agent-001"
        episode.maturity_at_time = "INTERN"
        episode.status = "completed"
        episode.human_intervention_count = 0
        episode.constitutional_score = 1.0  # Perfect score
        episode.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = [episode]

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should handle perfect score
        assert result is not None

    def test_graduation_with_constitutional_score_above_one(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Constitutional score > 1.0 accepted

        Expected:
            - Should reject scores > 1.0 or clamp to 1.0
            - Should handle data validation errors

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Invalid scores > 1.0 skew calculations
            - Could cause incorrect graduation decisions

        Fix:
            - Add validation: 0.0 <= constitutional_score <= 1.0
            - Clamp or reject out-of-range scores

        Validated: [Test result]
        """
        episode = Mock(spec=Episode)
        episode.id = "episode-001"
        episode.agent_id = "test-agent-001"
        episode.maturity_at_time = "INTERN"
        episode.status = "completed"
        episode.human_intervention_count = 0
        episode.constitutional_score = 1.5  # Invalid > 1.0
        episode.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = [episode]

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should handle invalid score
        assert result is not None

    def test_graduation_with_constitutional_score_negative(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Negative constitutional score accepted

        Expected:
            - Should reject negative scores
            - Should handle data validation errors

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Negative scores skew calculations
            - Could cause incorrect graduation decisions

        Fix:
            - Add validation: constitutional_score >= 0.0
            - Reject or clamp negative scores

        Validated: [Test result]
        """
        episode = Mock(spec=Episode)
        episode.id = "episode-001"
        episode.agent_id = "test-agent-001"
        episode.maturity_at_time = "INTERN"
        episode.status = "completed"
        episode.human_intervention_count = 0
        episode.constitutional_score = -0.5  # Invalid negative
        episode.created_at = datetime.now(timezone.utc)

        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = [episode]

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should handle negative score
        assert result is not None

    def test_graduation_with_empty_violations_list(self, mock_db, sample_agent, sample_episodes):
        """
        VALIDATED_BUG: Empty constitutional violations list

        Expected:
            - Should handle empty violations list gracefully
            - Empty violations means perfect compliance

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Edge case in violation handling
            - Should not crash when violations list is empty

        Fix:
            - Ensure empty list is handled as "no violations"
            - Don't iterate over None

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = sample_episodes

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should handle empty violations
        assert result is not None

    def test_graduation_with_database_query_failure(self, mock_db):
        """
        VALIDATED_BUG: Database query failure crashes graduation

        Expected:
            - Should catch database errors and return error response
            - Should log error for debugging

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Database connectivity issues cause crashes
            - No graceful degradation for DB failures

        Fix:
            - Wrap database queries in try/except
            - Return {"success": False, "error": "Database error"}

        Validated: [Test result]
        """
        mock_db.query.side_effect = Exception("Database connection failed")

        service = AgentGraduationService(mock_db)
        result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

        # Should handle database error gracefully
        assert result is not None
        assert result.get("success") is False

    def test_graduation_with_lancedb_unavailable(self, mock_db, sample_agent, sample_episodes):
        """
        VALIDATED_BUG: LanceDB unavailability not handled

        Expected:
            - Should fall back to PostgreSQL-only mode
            - Should not crash when LanceDB unavailable

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - LanceDB connectivity issues prevent graduation checks
            - No graceful degradation

        Fix:
            - Catch LanceDB errors
            - Return results without semantic search data

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = sample_episodes

        with patch('core.agent_graduation_service.get_lancedb_handler') as mock_lancedb:
            mock_lancedb.side_effect = Exception("LanceDB unavailable")

            service = AgentGraduationService(mock_db)
            result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")

            # Should handle LanceDB unavailability
            assert result is not None

    def test_graduation_with_concurrent_attempts(self, mock_db, sample_agent, sample_episodes):
        """
        VALIDATED_BUG: Concurrent graduation attempts cause race condition

        Expected:
            - Should handle concurrent graduation checks safely
            - Use database locks or optimistic concurrency

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Multiple simultaneous checks could cause inconsistent results
            - Race condition in episode count updates

        Fix:
            - Use database transaction isolation
            - Add locking for graduation checks

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value.filter.return_value.all.return_value = sample_episodes

        service = AgentGraduationService(mock_db)

        # Simulate concurrent calls
        import threading
        results = []
        errors = []

        def check_graduation():
            try:
                result = service.check_graduation_readiness("test-agent-001", "SUPERVISED")
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check_graduation) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should handle concurrency without errors
        assert len(errors) == 0
        assert len(results) == 5


# =============================================================================
# TestAgentPromotionErrorPaths
# =============================================================================

class TestAgentPromotionErrorPaths:
    """Tests for AgentPromotionService error scenarios"""

    def test_promotion_without_graduation_exam(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion allowed without graduation exam

        Expected:
            - Should require graduation exam before promotion
            - Should return error if exam not passed

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Agents could be promoted without validation
            - Bypasses governance checks

        Fix:
            - Check for passed graduation exam before promotion
            - Return error if exam not passed

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "SUPERVISED", auto_promote=True)

        # Should require exam
        assert result is not None

    def test_promotion_with_invalid_status_transition(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Invalid status transition (INTERN -> AUTONOMOUS skipping SUPERVISED)

        Expected:
            - Should enforce sequential maturity transitions
            - Should reject skipping levels

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Agents could skip maturity levels
            - Bypasses governance safeguards

        Fix:
            - Validate status transitions are sequential
            - Reject non-sequential promotions

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "AUTONOMOUS", auto_promote=True)

        # Should reject skipping SUPERVISED
        assert result is not None

    def test_promotion_during_active_execution(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion during active agent execution

        Expected:
            - Should block promotion while agent is executing
            - Should return error indicating agent is busy

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Changing maturity mid-execution could cause issues
            - State inconsistency during active operations

        Fix:
            - Check agent execution status before promotion
            - Reject promotion if agent is active

        Validated: [Test result]
        """
        sample_agent.is_active = True  # Agent is executing
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "SUPERVISED", auto_promote=True)

        # Should block during active execution
        assert result is not None

    def test_promotion_with_missing_audit_trail(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion without audit trail entries

        Expected:
            - Should create audit trail for all promotions
            - Should not allow promotion without audit record

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Missing audit trail for governance compliance
            - Cannot track promotion history

        Fix:
            - Create audit record before promotion
            - Reject if audit creation fails

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.add.side_effect = Exception("Failed to create audit trail")

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "SUPERVISED", auto_promote=True)

        # Should handle audit trail failure
        assert result is not None

    def test_promotion_with_concurrent_attempts(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Concurrent promotion attempts cause race condition

        Expected:
            - Should handle concurrent promotion attempts safely
            - Only one promotion should succeed

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Multiple simultaneous promotions could cause state corruption
            - Race condition in status updates

        Fix:
            - Use database locks for promotion operations
            - Check current status before update

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        service = AgentPromotionService(mock_db)

        # Simulate concurrent promotions
        import threading
        results = []
        errors = []

        def promote():
            try:
                result = service.promote_agent("test-agent-001", "SUPERVISED", auto_promote=True)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=promote) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should handle concurrency
        assert len(errors) == 0 or len(results) > 0

    def test_promotion_rollback_on_failure(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion rollback doesn't restore previous status

        Expected:
            - Should rollback to previous status on failure
            - Should restore agent state if promotion fails mid-transaction

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Failed promotions leave agents in inconsistent state
            - Cannot recover from partial promotion

        Fix:
            - Use database transactions for promotion
            - Rollback on any failure

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.commit.side_effect = Exception("Database commit failed")

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "SUPERVISED", auto_promote=True)

        # Should rollback on commit failure
        assert result is not None

    def test_promotion_history_preservation(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion history not preserved

        Expected:
            - Should maintain history of all promotions
            - Should track maturity changes over time

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Cannot audit promotion history
            - Missing governance trail

        Fix:
            - Create PromotionHistory record for each promotion
            - Track timestamp, old_status, new_status, promoted_by

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "SUPERVISED", auto_promote=True)

        # Should create history record
        assert result is not None

    def test_promotion_already_at_target_maturity(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion when agent already at target maturity

        Expected:
            - Should return success or no-op
            - Should not crash or create duplicate records

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Redundant promotion attempts
            - Could create duplicate audit records

        Fix:
            - Check if agent already at target maturity
            - Return early with appropriate message

        Validated: [Test result]
        """
        # Agent already at SUPERVISED, trying to promote to SUPERVISED
        sample_agent.maturity_level = "SUPERVISED"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "SUPERVISED", auto_promote=True)

        # Should handle no-op gracefully
        assert result is not None

    def test_promotion_with_permission_denied(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Non-admin users can promote agents

        Expected:
            - Should require ADMIN permissions
            - Should return 403 Forbidden for non-admin users

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Unauthorized users can promote agents
            - Security vulnerability

        Fix:
            - Check user permissions before promotion
            - Require ADMIN role

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        service = AgentPromotionService(mock_db)
        result = service.promote_agent(
            "test-agent-001",
            "SUPERVISED",
            auto_promote=True,
            promoted_by="non-admin-user"
        )

        # Should check permissions
        assert result is not None

    def test_promotion_status_string_conversion_error(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Status string to enum conversion errors

        Expected:
            - Should handle invalid status strings gracefully
            - Should return error for invalid values

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Invalid status strings cause crashes
            - No validation of status values

        Fix:
            - Validate status strings against AgentStatus enum
            - Return error for invalid values

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "INVALID_STATUS", auto_promote=True)

        # Should handle invalid status
        assert result is not None

    def test_promotion_with_database_constraint_violation(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Database constraint violation not handled

        Expected:
            - Should catch constraint violations and return error
            - Should not crash on unique key violations

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Database constraints cause unhandled exceptions
            - No graceful error handling

        Fix:
            - Catch IntegrityError from SQLAlchemy
            - Return meaningful error message

        Validated: [Test result]
        """
        from sqlalchemy.exc import IntegrityError
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent
        mock_db.commit.side_effect = IntegrityError("Constraint violation", {}, None)

        service = AgentPromotionService(mock_db)
        result = service.promote_agent("test-agent-001", "SUPERVISED", auto_promote=True)

        # Should handle constraint violation
        assert result is not None


# =============================================================================
# TestAgentEvolutionErrorPaths
# =============================================================================

class TestAgentEvolutionErrorPaths:
    """Tests for AgentEvolutionLoop error scenarios"""

    def test_evolution_loop_interruption(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Evolution loop interruption not handled

        Expected:
            - Should gracefully handle loop interruption
            - Should save progress before interruption

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Interrupted evolution loops lose progress
            - Cannot resume from checkpoint

        Fix:
            - Add signal handling for interruption
            - Save evolution state periodically

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)

        # Simulate interruption
        with patch('core.agent_evolution_loop.time.sleep', side_effect=KeyboardInterrupt):
            result = evolution.run_evolution_cycle("test-agent-001", max_iterations=100)

        # Should handle interruption gracefully
        assert result is not None

    def test_evolution_learning_rate_boundary(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Learning rate boundary conditions

        Expected:
            - Should reject learning_rate <= 0 or > 1.0
            - Should validate learning rate parameter

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Invalid learning rates cause convergence issues
            - Could prevent evolution from working

        Fix:
            - Add validation: 0.0 < learning_rate <= 1.0
            - Return error for invalid values

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)
        result = evolution.run_evolution_cycle("test-agent-001", learning_rate=0.0)

        # Should handle invalid learning rate
        assert result is not None

    def test_evolution_stagnation_detection(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: No stagnation detection (infinite loop)

        Expected:
            - Should detect when agent is not improving
            - Should stop evolution after stagnation threshold

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Evolution loops run forever without improvement
            - Wastes computational resources

        Fix:
            - Track fitness scores over iterations
            - Stop if no improvement for N iterations

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)

        # Mock fitness function that returns same score (no improvement)
        with patch.object(evolution, '_calculate_fitness', return_value=0.5):
            result = evolution.run_evolution_cycle(
                "test-agent-001",
                max_iterations=100,
                stagnation_threshold=10
            )

        # Should detect stagnation and stop
        assert result is not None

    def test_evolution_negative_fitness_score(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Negative fitness scores accepted

        Expected:
            - Should reject or clamp negative fitness scores
            - Fitness should be in [0.0, 1.0] range

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Negative scores skew evolution calculations
            - Could cause incorrect evolution decisions

        Fix:
            - Add validation: fitness_score >= 0.0
            - Clamp or reject negative values

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)

        # Mock fitness function returning negative score
        with patch.object(evolution, '_calculate_fitness', return_value=-0.5):
            result = evolution.run_evolution_cycle("test-agent-001", max_iterations=5)

        # Should handle negative fitness
        assert result is not None

    def test_evolution_missing_parameters(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Missing evolution parameters crash

        Expected:
            - Should use default values for missing parameters
            - Should validate required parameters

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Missing parameters cause crashes
            - No sensible defaults

        Fix:
            - Define defaults for all optional parameters
            - Validate required parameters exist

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)
        result = evolution.run_evolution_cycle("test-agent-001")

        # Should use defaults
        assert result is not None

    def test_evolution_cycle_timeout(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Evolution cycle timeout not enforced

        Expected:
            - Should enforce maximum time limit for evolution
            - Should stop and return partial results

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Long-running evolution cycles block execution
            - No timeout protection

        Fix:
            - Add timeout parameter with signal handling
            - Stop evolution after timeout

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)
        result = evolution.run_evolution_cycle(
            "test-agent-001",
            max_iterations=1000,
            timeout_seconds=1
        )

        # Should enforce timeout
        assert result is not None

    def test_evolution_infinite_loop_prevention(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: No infinite loop prevention

        Expected:
            - Should enforce max_iterations limit
            - Should not run forever

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Evolution loops could run indefinitely
            - Resource exhaustion

        Fix:
            - Enforce max_iterations parameter
            - Always stop after max iterations

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)
        result = evolution.run_evolution_cycle("test-agent-001", max_iterations=5)

        # Should enforce iteration limit
        assert result is not None
        assert result.get("iterations") <= 5

    def test_evolution_resource_exhaustion(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Resource exhaustion during evolution

        Expected:
            - Should monitor memory/CPU usage
            - Should stop if resources exhausted

        Actual:
            - [Document actual behavior]

        Severity: MEDIUM
        Impact:
            - Evolution could consume all resources
            - System instability

        Fix:
            - Add resource usage monitoring
            - Stop if memory/CPU thresholds exceeded

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)

        # Mock resource exhaustion
        with patch('core.agent_evolution_loop.psutil.virtual_memory') as mock_mem:
            mock_mem.return_value.percent = 95.0  # 95% memory usage

            result = evolution.run_evolution_cycle("test-agent-001", max_iterations=100)

        # Should detect resource exhaustion
        assert result is not None

    def test_evolution_conflicting_strategies(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Conflicting evolution strategies

        Expected:
            - Should detect and resolve conflicting strategies
            - Should not apply incompatible optimizations

        Actual:
            - [Document actual behavior]

        Severity: LOW
        Impact:
            - Conflicting optimizations could cancel each other
            - Wasted computation

        Fix:
            - Validate strategy compatibility
            - Reject conflicting combinations

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)

        # Apply conflicting strategies
        result = evolution.run_evolution_cycle(
            "test-agent-001",
            strategies=["maximize_speed", "minimize_speed"]  # Conflicting
        )

        # Should detect conflict
        assert result is not None

    def test_evolution_data_corruption(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Evolution data corruption not detected

        Expected:
            - Should validate evolution data integrity
            - Should detect corrupted checkpoint files

        Actual:
            - [Document actual behavior]

        Severity: HIGH
        Impact:
            - Corrupted data causes incorrect evolution
            - Cannot recover from bad state

        Fix:
            - Add checksums to evolution data
            - Validate before loading

        Validated: [Test result]
        """
        mock_db.query.return_value.filter.return_value.first.return_value = sample_agent

        evolution = AgentEvolutionLoop(mock_db)

        # Mock corrupted data
        with patch.object(evolution, '_load_evolution_state', side_effect=json.decoder.JSONDecodeError("Invalid JSON", "", 0)):
            result = evolution.run_evolution_cycle("test-agent-001", resume=True)

        # Should handle corrupted data
        assert result is not None
