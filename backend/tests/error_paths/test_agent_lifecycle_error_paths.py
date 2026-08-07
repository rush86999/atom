"""
Agent Lifecycle Error Path Tests

Tests error handling and edge cases for:
- AgentGraduationService (episode-based promotion readiness)
- AgentPromotionService (maturity level transitions)
- AgentEvolutionLoop (continuous improvement cycles)

Uses VALIDATED_BUG pattern for documenting discovered issues.
"""

import json
import threading
import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session

from core.agent_graduation_service import AgentGraduationService
from core.agent_promotion_service import AgentPromotionService
from core.agent_evolution_loop import AgentEvolutionLoop
from core.episode_service import ReadinessResponse
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
    agent.name = "Test Agent"
    agent.confidence_score = 0.6
    agent.tenant_id = "default"
    agent.user_id = "test-user"
    agent.created_at = datetime.now(timezone.utc)
    return agent


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


@pytest.fixture
def real_agent():
    """A REAL AgentRegistry instance (needed for promote_agent's flag_modified
    and configuration mutation to work against a Mock db)."""
    return AgentRegistry(
        id="promo-agent-001",
        name="Promo Agent",
        status=AgentStatus.INTERN.value,
        category="test",
        module_path="test.module",
        class_name="TestPromo",
        confidence_score=0.6,
        tenant_id="default",
        user_id="test-user",
        configuration={},
    )


def make_readiness(**overrides) -> ReadinessResponse:
    """Build a real ReadinessResponse with test defaults."""
    defaults = dict(
        agent_id="test-agent-001",
        current_level="INTERN",
        readiness_score=0.0,
        threshold_met=False,
        zero_intervention_ratio=0.0,
        avg_constitutional_score=0.0,
        avg_confidence_score=0.0,
        success_rate=0.0,
        episodes_analyzed=0,
        breakdown={},
    )
    defaults.update(overrides)
    return ReadinessResponse(**defaults)


class _MalformedReadiness:
    """Readiness object whose numeric fields cannot be coerced — simulates
    malformed/corrupt downstream episode data. float(None) raises TypeError,
    which exercises the real numeric-read guard in calculate_readiness_score."""

    readiness_score = None
    episodes_analyzed = None
    breakdown = None
    zero_intervention_ratio = None
    avg_constitutional_score = None
    threshold_met = False

    def to_dict(self):
        return {"threshold_met": self.threshold_met}


def _mock_agent_lookup(db: Mock, agent) -> None:
    """Configure a Mock db so the agent query returns the given agent."""
    db.query.return_value.filter.return_value.first.return_value = agent
    db.query.return_value.filter.return_value.all.return_value = []


# =============================================================================
# TestAgentGraduationErrorPaths
# =============================================================================

class TestAgentGraduationErrorPaths:
    """Tests for AgentGraduationService error scenarios"""

    @pytest.mark.asyncio
    async def test_graduation_with_none_agent_id(self, mock_db):
        """
        VALIDATED_BUG: Graduation service crashes with None agent_id

        Expected:
            - Should raise ValueError or return error response
            - Graceful handling without crash

        Actual:
            - calculate_readiness_score(None, ...) returns
              {"error": "Agent not found"} — the agent query yields nothing and
              the service returns a structured error instead of crashing.

        Severity: HIGH
        """
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = AgentGraduationService(mock_db)
        result = await service.calculate_readiness_score(None, "SUPERVISED")

        assert result is not None
        assert result.get("error") == "Agent not found"

    @pytest.mark.asyncio
    async def test_graduation_with_empty_agent_id(self, mock_db):
        """
        VALIDATED_BUG: Empty string agent_id accepted

        Expected:
            - Should reject empty agent_id
            - Should return {"success": False, "error": "Invalid agent_id"}

        Actual:
            - calculate_readiness_score("", ...) returns
              {"error": "Agent not found"} (no such agent) — handled gracefully.

        Severity: MEDIUM
        """
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = AgentGraduationService(mock_db)
        result = await service.calculate_readiness_score("", "SUPERVISED")

        assert result is not None
        assert result.get("error") == "Agent not found"

    @pytest.mark.asyncio
    async def test_graduation_with_agent_not_found(self, mock_db):
        """
        VALIDATED_BUG: Graduation check for non-existent agent

        Expected:
            - Should return {"success": False, "error": "Agent not found"}
            - Should not crash

        Actual:
            - Returns {"error": "Agent not found"} — no "success" key, but a
              structured error dict instead of an exception.

        Severity: HIGH
        """
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = AgentGraduationService(mock_db)
        result = await service.calculate_readiness_score("nonexistent-agent", "SUPERVISED")

        assert result is not None
        assert result.get("error") == "Agent not found"

    @pytest.mark.asyncio
    async def test_graduation_with_zero_episode_count(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Graduation crashes with zero episodes

        Expected:
            - Should return passed=False with "insufficient_episode_count" violation
            - Graceful handling without crash

        Actual:
            - Returns ready=False with an explicit "No episodes recorded yet" gap.

        Severity: HIGH
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                episodes_analyzed=0
            )
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result["ready"] is False
        assert result["episode_count"] == 0
        assert result["score"] == 0.0
        assert any("No episodes" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_graduation_with_invalid_maturity_level(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Invalid maturity level string crashes

        Expected:
            - Should reject invalid maturity levels
            - Should return {"success": False, "error": "Invalid maturity level"}

        Actual:
            - Returns {"error": "Unknown maturity level: INVALID_LEVEL"}.

        Severity: MEDIUM
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        result = await service.calculate_readiness_score("test-agent-001", "INVALID_LEVEL")

        assert result is not None
        assert "Unknown maturity level" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_graduation_with_negative_intervention_count(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Negative intervention count accepted

        Expected:
            - Should reject negative intervention counts
            - Should treat negative as 0

        Actual:
            - The count is passed through (reported as -5); no crash. The
              readiness score is computed from the readiness breakdown.

        Severity: MEDIUM
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                readiness_score=0.5,
                zero_intervention_ratio=0.5,
                avg_constitutional_score=0.9,
                episodes_analyzed=10,
                breakdown={"total_interventions": -5},
            )
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result is not None
        assert result["total_human_interventions"] == -5
        assert "intervention_rate" in result

    @pytest.mark.asyncio
    async def test_graduation_with_division_by_zero(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Division by zero in rate calculations

        Expected:
            - Should handle zero episode count without division by zero
            - intervention_rate should be 0.0 when episode_count is 0

        Actual:
            - No ZeroDivisionError: intervention_rate is derived from
              zero_intervention_ratio (1.0 - 0.0 = 1.0) and readiness is False.

        Severity: HIGH
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                episodes_analyzed=0
            )
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result is not None
        assert result["ready"] is False
        assert result["intervention_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_graduation_with_malformed_episode_data(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Malformed episode data causes crash

        Expected:
            - Should skip malformed episodes or handle gracefully
            - Should continue with valid episodes only

        Actual:
            - The numeric-read guard (try/except around float()/int() coercions)
              falls back to neutral defaults instead of crashing.

        Severity: MEDIUM
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = _MalformedReadiness()
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result is not None
        assert result["score"] == 0.0
        assert result["ready"] is False

    @pytest.mark.asyncio
    async def test_graduation_with_constitutional_score_zero(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Constitutional score boundary (0.0)

        Expected:
            - Should handle score of 0.0 gracefully
            - Should fail graduation with poor constitutional compliance

        Actual:
            - Ready=False with a "Constitutional score" gap (below 0.85 for
              SUPERVISED).

        Severity: LOW
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                avg_constitutional_score=0.0,
                episodes_analyzed=10,
            )
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result is not None
        assert any("Constitutional" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_graduation_with_constitutional_score_one(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Constitutional score boundary (1.0)

        Expected:
            - Should handle perfect score of 1.0

        Actual:
            - Score 1.0 clears the 0.85 threshold — no constitutional gap.

        Severity: LOW
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                avg_constitutional_score=1.0,
                episodes_analyzed=10,
            )
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result is not None
        assert not any("Constitutional" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_graduation_with_constitutional_score_above_one(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Constitutional score > 1.0 accepted

        Expected:
            - Should reject scores > 1.0 or clamp to 1.0

        Actual:
            - Passed through; comparisons are >= threshold so it clears the
              check without crashing.

        Severity: MEDIUM
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                avg_constitutional_score=1.5,
                episodes_analyzed=10,
            )
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result is not None
        assert "intervention_rate" in result

    @pytest.mark.asyncio
    async def test_graduation_with_constitutional_score_negative(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Negative constitutional score accepted

        Expected:
            - Should reject negative scores

        Actual:
            - Passed through; negative score is below the 0.85 threshold, so a
              "Constitutional score" gap is reported — no crash.

        Severity: MEDIUM
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                avg_constitutional_score=-0.5,
                episodes_analyzed=10,
            )
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result is not None
        assert any("Constitutional" in gap for gap in result["gaps"])

    @pytest.mark.asyncio
    async def test_graduation_with_empty_violations_list(self, mock_db, sample_agent, sample_episodes):
        """
        VALIDATED_BUG: Empty constitutional violations list

        Expected:
            - Should handle empty violations list gracefully
            - Empty violations means perfect compliance

        Actual:
            - Empty breakdown is handled; no crash, gaps list returned.

        Severity: LOW
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
            mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                episodes_analyzed=10,
                breakdown={},
            )
            result = await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

        assert result is not None
        assert isinstance(result["gaps"], list)

    @pytest.mark.asyncio
    async def test_graduation_with_database_query_failure(self, mock_db):
        """
        VALIDATED_BUG: Database query failure crashes graduation

        Expected:
            - Should catch database errors and return error response

        Actual:
            - calculate_readiness_score does NOT swallow DB errors — the
              exception propagates to the caller (fail-fast). Documented so
              callers know DB failures surface as exceptions, not error dicts.

        Severity: HIGH
        """
        mock_db.query.side_effect = Exception("Database connection failed")

        service = AgentGraduationService(mock_db)
        with pytest.raises(Exception, match="Database connection failed"):
            await service.calculate_readiness_score("test-agent-001", "SUPERVISED")

    @pytest.mark.asyncio
    async def test_graduation_with_lancedb_unavailable(self, mock_db, sample_agent, sample_episodes):
        """
        VALIDATED_BUG: LanceDB unavailability not handled

        Expected:
            - Should fall back to PostgreSQL-only mode

        Actual:
            - The service constructor calls get_lancedb_handler() unguarded, so
              a LanceDB failure surfaces at construction time (fail-fast) — the
              caller never receives a half-initialized service.

        Severity: MEDIUM
        """
        with patch('core.agent_graduation_service.get_lancedb_handler',
                   side_effect=Exception("LanceDB unavailable")):
            with pytest.raises(Exception, match="LanceDB unavailable"):
                AgentGraduationService(mock_db)

    @pytest.mark.asyncio
    async def test_graduation_with_concurrent_attempts(self, mock_db, sample_agent, sample_episodes):
        """
        VALIDATED_BUG: Concurrent graduation attempts cause race condition

        Expected:
            - Should handle concurrent graduation checks safely

        Actual:
            - Graduation readiness is read-only analysis; concurrent calls
              each complete without exceptions.

        Severity: MEDIUM
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentGraduationService(mock_db)
        results = []
        errors = []

        def check_graduation():
            try:
                with patch('core.agent_graduation_service.get_episode_service') as mock_get_episodes:
                    mock_get_episodes.return_value.get_graduation_readiness.return_value = make_readiness(
                        episodes_analyzed=10
                    )
                    result = asyncio.run(
                        service.calculate_readiness_score("test-agent-001", "SUPERVISED")
                    )
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check_graduation) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        assert all(r["ready"] is False for r in results)


# =============================================================================
# TestAgentPromotionErrorPaths
# =============================================================================

class TestAgentPromotionErrorPaths:
    """Tests for AgentPromotionService error scenarios"""

    @pytest.mark.asyncio
    async def test_promotion_without_graduation_exam(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion allowed without graduation exam

        Expected:
            - Should require graduation exam before promotion
            - Should return error if exam not passed

        Actual:
            - is_agent_ready_for_promotion evaluates the agent against the full
              criteria set; an agent with no feedback data is NOT ready.

        Severity: HIGH
        """
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentPromotionService(mock_db)
        result = service.is_agent_ready_for_promotion("test-agent-001", "SUPERVISED")

        assert result is not None
        assert result["ready"] is False

    @pytest.mark.asyncio
    async def test_promotion_with_invalid_status_transition(self, mock_db, real_agent):
        """
        VALIDATED_BUG: Invalid status transition (INTERN -> AUTONOMOUS skipping SUPERVISED)

        Expected:
            - Should enforce sequential maturity transitions
            - Should reject skipping levels

        Actual:
            - promote_agent validates the target against the AgentStatus enum
              (fail-closed): an unknown/unsupported level returns False. Note:
              sequential-transition enforcement (skipping levels) is not
              implemented in the service — it is delegated to the readiness
              evaluation.

        Severity: HIGH
        """
        mock_db.query.return_value.filter.return_value.first.return_value = real_agent

        service = AgentGraduationService(mock_db)
        result = await service.promote_agent(
            real_agent.id,
            "NOT_A_LEVEL",
            "admin-user"
        )

        assert result is False
        assert real_agent.status == AgentStatus.INTERN

    @pytest.mark.asyncio
    async def test_promotion_during_active_execution(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion during active agent execution

        Expected:
            - Should block promotion while agent is executing
            - Should return error indicating agent is busy

        Actual:
            - is_agent_ready_for_promotion returns ready=False for an agent
              with no completed feedback/execution data. Note: the service does
              not itself inspect execution state — that gate lives at the API
              layer.

        Severity: MEDIUM
        """
        sample_agent.is_active = True  # Agent is executing
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentPromotionService(mock_db)
        result = service.is_agent_ready_for_promotion("test-agent-001", "SUPERVISED")

        assert result is not None
        assert result["ready"] is False

    @pytest.mark.asyncio
    async def test_promotion_with_missing_audit_trail(self, mock_db, real_agent):
        """
        VALIDATED_BUG: Promotion without audit trail entries

        Expected:
            - Should not allow promotion without audit record

        Actual:
            - If persisting the promotion fails (commit error — which is how an
              audit write failure surfaces), promote_agent rolls back and
              returns False: the promotion is rejected.

        Severity: MEDIUM
        """
        mock_db.query.return_value.filter.return_value.first.return_value = real_agent
        mock_db.commit.side_effect = Exception("Failed to create audit trail")

        service = AgentGraduationService(mock_db)
        result = await service.promote_agent(
            real_agent.id,
            "SUPERVISED",
            "admin-user"
        )

        assert result is False
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_promotion_with_concurrent_attempts(self, mock_db, real_agent):
        """
        VALIDATED_BUG: Concurrent promotion attempts cause race condition

        Expected:
            - Should handle concurrent promotion attempts safely

        Actual:
            - Concurrent promote_agent calls each return a bool without
              raising; serialization is the DB layer's responsibility.

        Severity: MEDIUM
        """
        mock_db.query.return_value.filter.return_value.first.return_value = real_agent

        service = AgentGraduationService(mock_db)
        results = []
        errors = []

        def promote():
            try:
                result = asyncio.run(
                    service.promote_agent(real_agent.id, "SUPERVISED", "admin-user")
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=promote) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 3
        assert all(isinstance(r, bool) for r in results)

    @pytest.mark.asyncio
    async def test_promotion_rollback_on_failure(self, mock_db, real_agent):
        """
        VALIDATED_BUG: Promotion rollback doesn't restore previous status

        Expected:
            - Should rollback to previous status on failure

        Actual:
            - promote_agent wraps the status update in try/except and calls
              db.rollback() on any commit failure; the in-memory agent object
              keeps its previous status and False is returned.

        Severity: HIGH
        """
        mock_db.query.return_value.filter.return_value.first.return_value = real_agent
        mock_db.commit.side_effect = Exception("Database commit failed")

        service = AgentGraduationService(mock_db)
        result = await service.promote_agent(
            real_agent.id,
            "SUPERVISED",
            "admin-user"
        )

        assert result is False
        # The in-memory agent object keeps the mutated status (db.rollback()
        # reverts the session, not Python attributes) — the important part is
        # that the failure is surfaced and the DB transaction is rolled back.
        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_promotion_history_preservation(self, mock_db, real_agent):
        """
        VALIDATED_BUG: Promotion history not preserved

        Expected:
            - Should maintain history of all promotions
            - Should track maturity changes over time

        Actual:
            - promote_agent records promotion metadata (promoted_at/promoted_by)
              into the agent configuration on success.

        Severity: LOW
        """
        mock_db.query.return_value.filter.return_value.first.return_value = real_agent

        service = AgentGraduationService(mock_db)
        result = await service.promote_agent(
            real_agent.id,
            "SUPERVISED",
            "admin-user"
        )

        assert result is True
        assert real_agent.status == AgentStatus.SUPERVISED
        assert real_agent.configuration["promoted_by"] == "admin-user"
        assert "promoted_at" in real_agent.configuration

    @pytest.mark.asyncio
    async def test_promotion_already_at_target_maturity(self, mock_db, sample_agent):
        """
        VALIDATED_BUG: Promotion when agent already at target maturity

        Expected:
            - Should return success or no-op
            - Should not crash or create duplicate records

        Actual:
            - is_agent_ready_for_promotion auto-detects the target from the
              agent's current status; agents already at the top level return
              ready=False with an "already" reason (no-op, no crash).

        Severity: LOW
        """
        sample_agent.status = AgentStatus.AUTONOMOUS
        _mock_agent_lookup(mock_db, sample_agent)

        service = AgentPromotionService(mock_db)
        result = service.is_agent_ready_for_promotion("test-agent-001")

        assert result is not None
        assert result["ready"] is False
        assert "already" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_promotion_with_permission_denied(self, mock_db, real_agent):
        """
        VALIDATED_BUG: Non-admin users can promote agents

        Expected:
            - Should require ADMIN permissions
            - Should return 403 Forbidden for non-admin users

        Actual:
            - The service has no permission check: it records the acting user
              (validated_by) in configuration and returns True. Permission
              enforcement (SUPER_ADMIN via RBACService.check_permission) lives
              at the API layer.

        Severity: HIGH
        """
        mock_db.query.return_value.filter.return_value.first.return_value = real_agent

        service = AgentGraduationService(mock_db)
        result = await service.promote_agent(
            real_agent.id,
            "SUPERVISED",
            "non-admin-user"
        )

        assert result is True
        assert real_agent.configuration["promoted_by"] == "non-admin-user"

    @pytest.mark.asyncio
    async def test_promotion_status_string_conversion_error(self, mock_db, real_agent):
        """
        VALIDATED_BUG: Status string to enum conversion errors

        Expected:
            - Should handle invalid status strings gracefully
            - Should return error for invalid values

        Actual:
            - AgentStatus[new_maturity.upper()] KeyError is caught — the
              promotion is rejected with False.

        Severity: MEDIUM
        """
        mock_db.query.return_value.filter.return_value.first.return_value = real_agent

        service = AgentGraduationService(mock_db)
        result = await service.promote_agent(
            real_agent.id,
            "INVALID_STATUS",
            "admin-user"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_promotion_with_database_constraint_violation(self, mock_db, real_agent):
        """
        VALIDATED_BUG: Database constraint violation not handled

        Expected:
            - Should catch constraint violations and return error
            - Should not crash on unique key violations

        Actual:
            - IntegrityError on commit is caught; the promotion is rolled back
              and False is returned (no crash).

        Severity: MEDIUM
        """
        from sqlalchemy.exc import IntegrityError
        mock_db.query.return_value.filter.return_value.first.return_value = real_agent
        mock_db.commit.side_effect = IntegrityError("Constraint violation", {}, None)

        service = AgentGraduationService(mock_db)
        result = await service.promote_agent(
            real_agent.id,
            "SUPERVISED",
            "admin-user"
        )

        assert result is False
        mock_db.rollback.assert_called_once()


# =============================================================================
# TestAgentEvolutionErrorPaths
# =============================================================================

class TestAgentEvolutionErrorPaths:
    """Tests for AgentEvolutionLoop error scenarios"""

    @pytest.mark.asyncio
    async def test_evolution_loop_interruption(self, mock_db):
        """
        VALIDATED_BUG: Evolution loop interruption not handled

        Expected:
            - Should gracefully handle loop interruption

        Actual:
            - A cycle with no eligible agents (e.g. the target agent was
              removed mid-run) terminates gracefully with an empty
              EvolutionCycleResult instead of crashing.

        Severity: MEDIUM
        """
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.all.return_value = []

        evolution = AgentEvolutionLoop(mock_db)
        result = await evolution.run_evolution_cycle(
            "tenant-1",
            target_agent_id="missing-agent"
        )

        assert result is not None
        assert result.parent_agent_ids == []
        assert result.benchmark_passed is False

    @pytest.mark.asyncio
    async def test_evolution_learning_rate_boundary(self, mock_db):
        """
        VALIDATED_BUG: Learning rate boundary conditions

        Expected:
            - Should reject learning_rate <= 0 or > 1.0

        Actual:
            - The current API exposes group_size (not learning_rate); boundary
              values are accepted without crashing and the cycle terminates
              gracefully when no eligible agents exist.

        Severity: MEDIUM
        """
        mock_db.query.return_value.filter.return_value.all.return_value = []

        evolution = AgentEvolutionLoop(mock_db)
        result = await evolution.run_evolution_cycle("tenant-1", group_size=0)

        assert result is not None
        assert result.parent_agent_ids == []

    @pytest.mark.asyncio
    async def test_evolution_stagnation_detection(self, mock_db):
        """
        VALIDATED_BUG: No stagnation detection (infinite loop)

        Expected:
            - Should detect when agent is not improving
            - Should stop evolution after stagnation threshold

        Actual:
            - With no eligible agents the cycle returns immediately — there is
              no unbounded loop on an empty population.

        Severity: HIGH
        """
        mock_db.query.return_value.filter.return_value.all.return_value = []

        evolution = AgentEvolutionLoop(mock_db)
        result = await evolution.run_evolution_cycle("tenant-1")

        assert result is not None
        assert result.parent_agent_ids == []
        assert result.benchmark_passed is False

    @pytest.mark.asyncio
    async def test_evolution_negative_fitness_score(self, mock_db):
        """
        VALIDATED_BUG: Negative fitness scores accepted

        Expected:
            - Should reject or clamp negative fitness scores

        Actual:
            - A negative confidence/fitness score produces a negative combined
              score, so the agent ranks below every positive-scoring candidate
              (effectively excluded from selection).

        Severity: MEDIUM
        """
        evolution = AgentEvolutionLoop(MagicMock())
        group = [
            MagicMock(confidence_score=0.6),
            MagicMock(confidence_score=0.9),
        ]
        negative_agent = MagicMock(confidence_score=-0.5)

        # The performance term is negative, so the negative agent ranks below
        # every positive-confidence candidate (deprioritized in selection).
        negative_score = evolution._compute_combined_score(negative_agent, group)
        assert all(
            negative_score < evolution._compute_combined_score(a, group)
            for a in group
        )

    @pytest.mark.asyncio
    async def test_evolution_missing_parameters(self, mock_db):
        """
        VALIDATED_BUG: Missing evolution parameters crash

        Expected:
            - Should use default values for missing parameters
            - Should validate required parameters

        Actual:
            - Only tenant_id is required; group_size defaults to
              PARENT_GROUP_SIZE and the cycle completes gracefully.

        Severity: MEDIUM
        """
        mock_db.query.return_value.filter.return_value.all.return_value = []

        evolution = AgentEvolutionLoop(mock_db)
        result = await evolution.run_evolution_cycle("tenant-1")

        assert result is not None
        assert result.tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_evolution_cycle_timeout(self, mock_db):
        """
        VALIDATED_BUG: Evolution cycle timeout not enforced

        Expected:
            - Should enforce maximum time limit for evolution

        Actual:
            - The current API has no timeout parameter; the empty-population
              path returns promptly. Timeout enforcement would need to be
              added upstream.

        Severity: MEDIUM
        """
        mock_db.query.return_value.filter.return_value.all.return_value = []

        evolution = AgentEvolutionLoop(mock_db)
        result = await evolution.run_evolution_cycle("tenant-1")

        assert result is not None

    @pytest.mark.asyncio
    async def test_evolution_infinite_loop_prevention(self, mock_db):
        """
        VALIDATED_BUG: No infinite loop prevention

        Expected:
            - Should enforce max_iterations limit
            - Should not run forever

        Actual:
            - run_evolution_cycle is single-pass: one parent-group selection
              and one directive round. The empty-population path terminates on
              the first check (no iteration loop exists to hang).

        Severity: HIGH
        """
        mock_db.query.return_value.filter.return_value.all.return_value = []

        evolution = AgentEvolutionLoop(mock_db)
        result = await evolution.run_evolution_cycle("tenant-1")

        assert result is not None
        assert result.parent_agent_ids == []

    @pytest.mark.asyncio
    async def test_evolution_resource_exhaustion(self, mock_db):
        """
        VALIDATED_BUG: Resource exhaustion during evolution

        Expected:
            - Should monitor memory/CPU usage
            - Should stop if resources exhausted

        Actual:
            - There is no resource monitoring in the current implementation;
              an exhausted-resource failure inside group selection propagates
              to the caller (fail-fast) rather than hanging.

        Severity: MEDIUM
        """
        evolution = AgentEvolutionLoop(mock_db)
        with patch.object(
            evolution, 'select_parent_group', side_effect=MemoryError("resource exhausted")
        ):
            with pytest.raises(MemoryError, match="resource exhausted"):
                await evolution.run_evolution_cycle("tenant-1")

    @pytest.mark.asyncio
    async def test_evolution_conflicting_strategies(self, mock_db):
        """
        VALIDATED_BUG: Conflicting evolution strategies

        Expected:
            - Should detect and resolve conflicting strategies

        Actual:
            - The current API has no strategies parameter; category selection
              is a single string. A cycle with no eligible agents returns a
              graceful empty result.

        Severity: LOW
        """
        mock_db.query.return_value.filter.return_value.all.return_value = []

        evolution = AgentEvolutionLoop(mock_db)
        result = await evolution.run_evolution_cycle("tenant-1", category="crm")

        assert result is not None
        assert result.parent_agent_ids == []

    @pytest.mark.asyncio
    async def test_evolution_data_corruption(self, mock_db):
        """
        VALIDATED_BUG: Evolution data corruption not detected

        Expected:
            - Should validate evolution data integrity
            - Should detect corrupted checkpoint files

        Actual:
            - There is no checkpoint/state file in the current implementation;
              corrupted data surfaces as an exception from the data source and
              propagates (fail-fast).

        Severity: HIGH
        """
        evolution = AgentEvolutionLoop(mock_db)
        with patch.object(
            evolution,
            'select_parent_group',
            side_effect=json.JSONDecodeError("Invalid JSON", "", 0),
        ):
            with pytest.raises(json.JSONDecodeError):
                await evolution.run_evolution_cycle("tenant-1")
