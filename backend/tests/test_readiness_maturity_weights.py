"""
Maturity-adjusted graduation readiness scoring.

Regression scope: get_graduation_readiness's score assembly was a single
hardcoded 7-factor expression in which two factors (skill_diversity,
proposal_quality) have no telemetry writer and one (supervision) was capped
by a never-written column — capping every agent's score at ~0.86 against a
0.95 autonomous threshold, and averaging unrecorded constitutional scores
in as 0.0, which made the 0.70 student→intern threshold unreachable for
chat-trained agents with PERFECT runs.

The formula is now per-target-level weights (ReadinessWeights) renormalized
over factors with recorded evidence. These tests pin that behavior.
"""

from unittest.mock import Mock
from sqlalchemy.orm import Session

import pytest

from core.episode_service import EpisodeService, ReadinessWeights
from core.models import AgentEpisode


def make_episode(**overrides) -> AgentEpisode:
    base = dict(
        success=True,
        human_intervention_count=0,
        constitutional_score=None,
        confidence_score=None,
        outcome="success",
        step_efficiency=1.0,
        proposal_id=None,
        supervision_decision=None,
        supervisor_type=None,
        execution_followed_proposal=None,
    )
    base.update(overrides)
    return AgentEpisode(**base)


@pytest.fixture
def service() -> EpisodeService:
    return EpisodeService(db=Mock(spec=Session))


class TestReadinessWeightTables:
    def test_each_tier_weights_sum_to_one(self):
        for name in ("STUDENT_TO_INTERN", "INTERN_TO_SUPERVISED", "SUPERVISED_TO_AUTONOMOUS"):
            weights = getattr(ReadinessWeights, name)
            assert sum(weights.values()) == pytest.approx(1.0), name

    def test_unwritten_telemetry_factors_carry_zero_weight(self):
        """skill_diversity / proposal_quality have no episode writers."""
        for name in ("STUDENT_TO_INTERN", "INTERN_TO_SUPERVISED", "SUPERVISED_TO_AUTONOMOUS"):
            weights = getattr(ReadinessWeights, name)
            assert weights["skill_diversity"] == 0.0, name
            assert weights["proposal_quality"] == 0.0, name

    def test_student_tier_excludes_supervision(self):
        """Students cannot create proposals — supervision is unreachable."""
        assert ReadinessWeights.STUDENT_TO_INTERN["supervision"] == 0.0

    def test_weights_for_target_levels(self):
        assert EpisodeService._readiness_weights_for("intern") is ReadinessWeights.STUDENT_TO_INTERN
        assert EpisodeService._readiness_weights_for("supervised") is ReadinessWeights.INTERN_TO_SUPERVISED
        assert EpisodeService._readiness_weights_for("autonomous") is ReadinessWeights.SUPERVISED_TO_AUTONOMOUS
        # Unknown levels fall back to the student table (most conservative).
        assert EpisodeService._readiness_weights_for("nonsense") is ReadinessWeights.STUDENT_TO_INTERN


class TestStudentToInternReachable:
    def test_chat_trained_student_can_reach_threshold(self):
        """THE regression: chat-segmented episodes record no constitutional
        score. Previously that averaged in as 0.0 → max score 0.475 against
        the 0.70 threshold even for perfect runs. Now the factor is
        excluded and the rest renormalized."""
        episodes = [
            make_episode(confidence_score=0.5) for _ in range(3)
        ]
        service = EpisodeService(db=Mock(spec=Session))
        metrics = service.calculate_readiness_metrics(episodes)
        supervision = service.calculate_supervision_metrics(episodes)

        score, applied, excluded = service._compute_readiness_score(
            weights=EpisodeService._readiness_weights_for("intern"),
            metrics=metrics,
            supervision_metrics=supervision,
            skill_metrics={"skill_diversity_score": 0.0, "unique_skill_count": 0},
            proposal_quality_metrics={"proposal_quality_score": 0.0, "proposal_episode_count": 0},
        )
        # (0.35×1.0 + 0.20×0.5 + 0.20×1.0) / 0.75
        assert score == pytest.approx(0.8667, abs=0.001)
        assert "constitutional" in excluded
        assert "supervision" not in excluded  # zero weight — skipped, not excluded
        assert set(applied) == {"zero_intervention", "confidence", "success"}
        assert score >= 0.70  # STUDENT_TO_INTERN overall threshold

    def test_constitutional_counts_when_recorded(self):
        episodes = [make_episode(constitutional_score=0.9) for _ in range(2)]
        service = EpisodeService(db=Mock(spec=Session))
        metrics = service.calculate_readiness_metrics(episodes)
        assert metrics["avg_constitutional_score"] == pytest.approx(0.9)
        assert metrics["constitutional_recorded"] == 2


class TestRecordedOnlyAveraging:
    def test_constitutional_none_does_not_deflate_average(self):
        episodes = [
            make_episode(constitutional_score=1.0),
            make_episode(constitutional_score=None),
        ]
        metrics = EpisodeService(Mock(spec=Session)).calculate_readiness_metrics(episodes)
        assert metrics["avg_constitutional_score"] == pytest.approx(1.0)
        assert metrics["constitutional_recorded"] == 1

    def test_confidence_none_excluded_from_average(self):
        episodes = [
            make_episode(confidence_score=0.8),
            make_episode(confidence_score=None),
        ]
        metrics = EpisodeService(Mock(spec=Session)).calculate_readiness_metrics(episodes)
        assert metrics["avg_confidence_score"] == pytest.approx(0.8)
        assert metrics["confidence_recorded"] == 1

    def test_all_unrecorded_gives_zero_average_and_zero_count(self):
        episodes = [make_episode() for _ in range(2)]
        metrics = EpisodeService(Mock(spec=Session)).calculate_readiness_metrics(episodes)
        assert metrics["avg_constitutional_score"] == 0.0
        assert metrics["constitutional_recorded"] == 0


class TestSupervisionFactor:
    def test_no_proposal_episodes_excludes_factor(self):
        episodes = [make_episode() for _ in range(3)]
        service = EpisodeService(Mock(spec=Session))
        supervision = service.calculate_supervision_metrics(episodes)
        assert supervision["total_proposals"] == 0

        _, applied, excluded = service._compute_readiness_score(
            weights=EpisodeService._readiness_weights_for("supervised"),
            metrics=service.calculate_readiness_metrics(episodes),
            supervision_metrics=supervision,
            skill_metrics={"skill_diversity_score": 0.0, "unique_skill_count": 0},
            proposal_quality_metrics={"proposal_quality_score": 0.0, "proposal_episode_count": 0},
        )
        assert "supervision" in excluded
        assert "supervision" not in applied

    def test_approval_only_when_follow_through_never_recorded(self):
        """execution_followed_proposal has no writer — the 0.4 follow-through
        component must not cap supervision at 0.6."""
        episodes = [
            make_episode(proposal_id="p1", supervision_decision="approved",
                         execution_followed_proposal=None),
            make_episode(proposal_id="p2", supervision_decision="approved",
                         execution_followed_proposal=None),
        ]
        m = EpisodeService(Mock(spec=Session)).calculate_supervision_metrics(episodes)
        assert m["approval_rate"] == pytest.approx(1.0)
        assert m["supervision_success_rate"] == pytest.approx(1.0)

    def test_blend_when_follow_through_recorded(self):
        episodes = [
            make_episode(proposal_id="p1", supervision_decision="approved",
                         execution_followed_proposal=True),
            make_episode(proposal_id="p2", supervision_decision="approved",
                         execution_followed_proposal=False),
        ]
        m = EpisodeService(Mock(spec=Session)).calculate_supervision_metrics(episodes)
        # approval 1.0, execution 0.5 → 0.6×1.0 + 0.4×0.5
        assert m["supervision_success_rate"] == pytest.approx(0.8)


class TestTierScores:
    def test_intern_tier_full_evidence(self):
        """Realistic strong intern: proposal HITL caps zero-intervention
        near 0.5; constitutional recorded on execution episodes."""
        metrics = {
            "zero_intervention_ratio": 0.5,
            "avg_constitutional_score": 0.9,
            "constitutional_recorded": 10,
            "avg_confidence_score": 0.7,
            "confidence_recorded": 10,
            "success_rate": 0.9,
        }
        supervision = {"supervision_success_rate": 1.0, "total_proposals": 5}
        score, applied, excluded = EpisodeService._compute_readiness_score(
            weights=EpisodeService._readiness_weights_for("supervised"),
            metrics=metrics,
            supervision_metrics=supervision,
            skill_metrics={"skill_diversity_score": 0.0, "unique_skill_count": 0},
            proposal_quality_metrics={"proposal_quality_score": 0.0, "proposal_episode_count": 0},
        )
        # 0.25×0.5 + 0.20×0.9 + 0.15×0.7 + 0.25×0.9 + 0.15×1.0
        assert score == pytest.approx(0.785, abs=0.001)
        assert excluded == []
        assert len(applied) == 5

    def test_autonomous_max_score_reachable(self):
        """The 0.95 autonomous threshold must be mathematically reachable —
        previously the dead factors capped every agent at ~0.86."""
        metrics = {
            "zero_intervention_ratio": 1.0,
            "avg_constitutional_score": 1.0,
            "constitutional_recorded": 50,
            "avg_confidence_score": 1.0,
            "confidence_recorded": 50,
            "success_rate": 1.0,
        }
        supervision = {"supervision_success_rate": 1.0, "total_proposals": 10}
        score, _, excluded = EpisodeService._compute_readiness_score(
            weights=EpisodeService._readiness_weights_for("autonomous"),
            metrics=metrics,
            supervision_metrics=supervision,
            skill_metrics={"skill_diversity_score": 0.0, "unique_skill_count": 0},
            proposal_quality_metrics={"proposal_quality_score": 0.0, "proposal_episode_count": 0},
        )
        assert score == pytest.approx(1.0)
        assert excluded == []

    def test_future_skill_diversity_enablement_uses_availability(self):
        """If a skill-episode writer lands later and the weight is enabled,
        zero skill evidence must exclude the factor (not score it 0)."""
        metrics = {
            "zero_intervention_ratio": 1.0,
            "avg_constitutional_score": 1.0,
            "constitutional_recorded": 5,
            "avg_confidence_score": 1.0,
            "confidence_recorded": 5,
            "success_rate": 1.0,
        }
        weights = dict(ReadinessWeights.SUPERVISED_TO_AUTONOMOUS)
        weights["skill_diversity"] = 0.10
        weights["success"] = 0.10  # keep the table summing to 1.0
        score, _, excluded = EpisodeService._compute_readiness_score(
            weights=weights,
            metrics=metrics,
            supervision_metrics={"supervision_success_rate": 1.0, "total_proposals": 2},
            skill_metrics={"skill_diversity_score": 0.0, "unique_skill_count": 0},
            proposal_quality_metrics={"proposal_quality_score": 0.0, "proposal_episode_count": 0},
        )
        assert "skill_diversity" in excluded
        assert score == pytest.approx(1.0)
