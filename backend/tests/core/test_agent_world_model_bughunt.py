"""
TDD Bug-Hunt Tests for core/agent_world_model.py

Each test reproduces a specific, real bug found by close reading of the module.
Tests are minimal and isolated: the LanceDB handler is mocked so no real
services are required. Every test asserts the *correct* behavior so it
genuinely fails because of the bug (not for an import / mock reason).
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

from core.agent_world_model import (
    WorldModelService,
    AgentExperience,
    BusinessFact,
    DetailLevel,
)


# ----------------------------------------------------------------------------
# Shared fixtures (mirror the patterns in tests/test_world_model.py)
# ----------------------------------------------------------------------------

@pytest.fixture
def mock_lancedb_handler():
    """A mock LanceDBHandler. db.db is truthy so methods that gate on
    `if self.db.db is None` still execute their body."""
    mock_db = Mock()
    mock_db.db = Mock(table_names=Mock(return_value=[]))  # truthy
    mock_db.workspace_id = "default"
    mock_db.add_document = Mock(return_value=True)
    mock_db.search = Mock(return_value=[])
    return mock_db


@pytest.fixture
def world_model_service(mock_lancedb_handler):
    """WorldModelService instance wired to the mocked handler."""
    with patch(
        "core.agent_world_model.get_lancedb_handler",
        return_value=mock_lancedb_handler,
    ):
        service = WorldModelService(workspace_id="default")
        service.db = mock_lancedb_handler
        return service


# ============================================================================
# BUG 1: recall_integration_experiences leaves "Input: " prefix in input_summary
# ============================================================================

class TestRecallIntegrationExperiencesInputSummary:
    @pytest.mark.asyncio
    async def test_recall_integration_experiences_strips_input_prefix(
        self, world_model_service, mock_lancedb_handler
    ):
        """BUG: recall_integration_experiences keeps the "Input: " prefix in
        input_summary instead of stripping it (unlike recall_experiences which
        does .replace("Input: ", ""))."""
        # Simulate a stored experience text exactly as record_experience writes it
        stored_text = (
            "Task: reconciliation\n"
            "Input: Reconcile SKU-123\n"
            "Outcome: Success\n"
            "Learnings: Matched on amount"
        )

        mock_lancedb_handler.search = Mock(
            return_value=[
                {
                    "id": "exp-1",
                    "text": stored_text,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "agent_id": "agent_finance",
                        "task_type": "integration_stripe_charge",
                        "outcome": "Success",
                        "confidence_score": 0.7,
                    },
                }
            ]
        )

        experiences = await world_model_service.recall_integration_experiences(
            agent_role="Finance",
            connector_id="stripe",
            operation_name="charge",
            limit=5,
        )

        assert len(experiences) == 1
        # The prefix should be stripped so the summary is the raw value.
        assert experiences[0].input_summary == "Reconcile SKU-123"


# ============================================================================
# BUG 2: boost_experience_confidence can produce a NEGATIVE confidence_score
# ============================================================================

class TestBoostExperienceConfidenceLowerBound:
    @pytest.mark.asyncio
    async def test_boost_confidence_does_not_go_negative(
        self, world_model_service, mock_lancedb_handler
    ):
        """BUG: boost_experience_confidence caps confidence at 1.0 (upper
        bound) but has NO lower bound. A negative boost_amount (or a large
        boost applied to a low-confidence experience) yields a negative
        confidence_score, which is invalid per the 0.0..1.0 contract."""
        mock_lancedb_handler.search = Mock(
            return_value=[
                {
                    "id": "exp-low",
                    "text": "Task: x\nOutcome: Success\nLearnings: y",
                    "source": "agent_1",
                    "metadata": {
                        "confidence_score": 0.2,
                    },
                }
            ]
        )
        mock_lancedb_handler.add_document = Mock(return_value=True)

        result = await world_model_service.boost_experience_confidence(
            experience_id="exp-low",
            boost_amount=-0.5,  # 0.2 + (-0.5) = -0.3  -> invalid
        )

        assert result is True
        new_confidence = (
            mock_lancedb_handler.add_document.call_args[1]["metadata"][
                "confidence_score"
            ]
        )
        # confidence_score must never be negative.
        assert new_confidence >= 0.0, (
            f"expected confidence >= 0.0, got {new_confidence}"
        )


# ============================================================================
# BUG 3: _extract_canvas_insights adds canvases with no canvas_type to
#         high_engagement_canvases (skips the guard used in the counting loop)
# ============================================================================

class TestExtractCanvasInsightsHighEngagementGuard:
    def test_high_engagement_skips_canvas_without_type(
        self, world_model_service
    ):
        """BUG: in _extract_canvas_insights, the first loop guards
        `if not canvas_type: continue` before counting a canvas. But the
        high_engagement_canvases block (lines ~2415-2423) iterates
        canvas_context AGAIN without that guard, so canvas entries missing a
        `canvas_type` get appended to high_engagement_canvases, leaking
        null-typed records into the output."""
        enriched_episodes = [
            {
                "canvas_context": [
                    {
                        "id": "c1",
                        "canvas_type": "charts",
                        "action": "present",
                    },
                    {
                        # No canvas_type -- should be ignored everywhere
                        "id": "c2",
                        "action": "present",
                    },
                ],
                "feedback_context": [
                    {"rating": 5},  # avg >= 4 -> high engagement
                ],
            }
        ]

        insights = world_model_service._extract_canvas_insights(
            enriched_episodes
        )

        high = insights["high_engagement_canvases"]
        # Every entry in high_engagement_canvases must have a real canvas_type.
        for entry in high:
            assert entry["canvas_type"] is not None, (
                f"found high-engagement canvas with null canvas_type: {entry}"
            )
        assert len(high) == 1  # only "charts" qualifies


# ============================================================================
# BUG 4: get_canvas_type_preferences defaults feedback_score to 0.0, masking
#         "no feedback" and corrupting avg_feedback_score / recommendations
# ============================================================================

class TestCanvasTypePreferencesFeedbackDefault:
    @pytest.mark.asyncio
    async def test_mixed_present_absent_feedback_averages_only_present(
        self, world_model_service, mock_lancedb_handler
    ):
        """BUG (companion to above): one experience with explicit
        feedback_score=0.8 and one with feedback_score ABSENT should average
        to 0.8, but the 0.0 default makes it (0.8 + 0.0) / 2 = 0.4."""
        mock_lancedb_handler.search = Mock(
            return_value=[
                {
                    "metadata": {
                        "agent_id": "agent_y",
                        "canvas_types": ["charts"],
                        "outcome": "Success",
                        "feedback_score": 0.8,
                    }
                },
                {
                    "metadata": {
                        "agent_id": "agent_y",
                        "canvas_types": ["charts"],
                        "outcome": "Success",
                        # feedback_score ABSENT -> wrongly becomes 0.0
                    }
                },
            ]
        )

        prefs = await world_model_service.get_canvas_type_preferences(
            agent_id="agent_y"
        )

        assert prefs["charts"]["count"] == 2
        # Correct behavior: average over the single real rating = 0.8.
        assert prefs["charts"]["avg_feedback_score"] == pytest.approx(0.8)


# ============================================================================
# BUG 5: recall_experiences failure filter is case-sensitive, so a low-
#         confidence failure stored as "Failed"/"Failure" is NOT filtered out
# ============================================================================

class TestRecallExperiencesFailureFilterCase:
    @pytest.mark.asyncio
    async def test_low_confidence_failure_with_capital_F_is_filtered(
        self, world_model_service, mock_lancedb_handler
    ):
        """BUG: recall_experiences filters failures with
            if outcome == "failed" and confidence < 0.8: continue
        (line ~1033) using a CASE-SENSITIVE comparison against the literal
        "failed". record_experience stores the outcome verbatim (e.g.
        "Failed", "Failure", "FAILED"), and get_experience_statistics
        correctly lower-cases the outcome before comparing -- so this filter
        silently lets through low-confidence failures whose outcome string
        is capitalized, contradicting the method's documented "ignore
        failures" behavior. Both experiences below should be excluded."""
        # Two low-confidence failures: one lower-case, one capitalized.
        call_count = [0]

        def search_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # agent_experience table
                return [
                    {
                        "id": "e_cap",
                        "text": "Task: t\nOutcome: Failed\nLearnings: x",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "score": 0.5,
                        "metadata": {
                            "agent_id": "agent_sales",
                            "outcome": "Failed",  # capitalized
                            "agent_role": "Sales",
                            "confidence_score": 0.3,  # low
                        },
                    },
                    {
                        "id": "e_low",
                        "text": "Task: t\nOutcome: failed\nLearnings: y",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "score": 0.5,
                        "metadata": {
                            "agent_id": "agent_sales",
                            "outcome": "failed",  # lower-case
                            "agent_role": "Sales",
                            "confidence_score": 0.3,  # low
                        },
                    },
                ]
            return []

        mock_lancedb_handler.search = Mock(side_effect=search_side_effect)

        agent = Mock()
        agent.id = "agent_sales"
        agent.category = "Sales"

        with patch("core.graphrag_engine.graphrag_engine") as mock_graph, \
                patch("core.formula_memory.get_formula_manager") as mock_fm, \
                patch("core.agent_world_model.SessionLocal") as mock_db, \
                patch(
                    "core.episode_retrieval_service.EpisodeRetrievalService"
                ) as mock_ep:
            mock_graph.get_context_for_ai = AsyncMock(return_value="")
            mock_fm.return_value.search_formulas.return_value = []
            mock_session = Mock()
            mock_session.query.return_value.filter.return_value.order_by \
                .return_value.limit.return_value.all.return_value = []
            mock_db.return_value = mock_session
            mock_ep.return_value.retrieve_contextual = AsyncMock(
                return_value={"episodes": []}
            )

            result = await world_model_service.recall_experiences(
                agent=agent,
                current_task_description="customer outreach",
                limit=5,
            )

        # BOTH low-confidence failures must be excluded regardless of the
        # case used to store the outcome string.
        assert result["experiences"] == [], (
            "expected both low-confidence failures filtered out, got: "
            f"{[e.outcome for e in result['experiences']]}"
        )


