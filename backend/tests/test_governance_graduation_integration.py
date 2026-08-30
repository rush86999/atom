"""
Three-layer graduation governance (core/governance/) — engine, manager,
and their enforcement wiring.

Context: the original core/governance package was deleted 2026-08-20 for
having no live wiring. This suite pins the reintroduced graduation-scoped
version AND the fact that it is wired in:
- GraduationExamService.conduct_exam consults it (Stage 5.5); a policy
  DENY fails the exam, and a STRATEGIC pass withholds the promotion for
  human approval (agents can no longer auto-promote to AUTONOMOUS).
- AgentGraduationService.promote_agent (the supervisor endpoint's
  service) re-evaluates the strategic policy against live evidence before
  granting AUTONOMOUS.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from core.governance import (
    DynamicGovernanceManager,
    GovernanceLayer,
    GovernancePolicy,
    PolicyEngine,
    PolicyPriority,
    default_graduation_policies,
    layer_for_action,
)
from core.episode_service import ReadinessThresholds


STRONG_CONTEXT = {
    "episode_count": 60,
    "readiness_score": 0.96,
    "success_rate": 0.97,
    "constitutional_score": 0.97,
    "intervention_rate": 0.05,
    "confidence_score": 0.93,
}


class TestPolicyEngine:
    def test_documented_example_denies_with_reasons(self):
        """The usage example from docs/agents/graduation.md must DENY with
        per-rule reasons (episodes < 50, intervention > 0, score < 0.95)."""
        engine = PolicyEngine()
        engine.register_policy(GovernancePolicy(
            policy_id="graduation_policy",
            priority=PolicyPriority.HIGH,
            condition="action == 'graduate_to_autonomous'",
            effect="DENY",
            layer="strategic",
            rules={
                "min_episodes": 50,
                "max_intervention_rate": 0.0,
                "min_constitutional_score": 0.95,
            },
        ))
        result = engine.evaluate(
            agent_id="agent_123",
            action="graduate_to_autonomous",
            layer="strategic",
            context={
                "episode_count": 48,
                "intervention_rate": 0.02,
                "constitutional_score": 0.92,
            },
        )
        assert result.decision == "deny"
        joined = " ".join(result.reasons)
        assert "episode_count 48 below min_episodes 50" in joined
        assert "intervention_rate 0.02 exceeds max_intervention_rate 0" in joined
        assert "constitutional_score 0.92 below min_constitutional_score 0.95" in joined

    def test_unregulated_action_allows(self):
        engine = PolicyEngine()
        result = engine.evaluate("a", "read_chart", "operational", {})
        assert result.allowed

    def test_missing_context_counts_as_violation(self):
        engine = PolicyEngine()
        result = engine.evaluate("a", "graduate_to_intern", "operational", {})
        assert result.decision == "deny"
        assert any("not provided" in r for r in result.reasons)

    def test_duplicate_policy_id_rejected(self):
        engine = PolicyEngine(include_defaults=False)
        policy = GovernancePolicy(policy_id="p1", condition="action == 'x'", layer="operational")
        engine.register_policy(policy)
        with pytest.raises(ValueError):
            engine.register_policy(GovernancePolicy(policy_id="p1"))

    def test_unregister_policy(self):
        engine = PolicyEngine(include_defaults=False)
        engine.register_policy(GovernancePolicy(policy_id="p1", condition="action == 'x'", layer="operational"))
        assert engine.unregister_policy("p1") is True
        assert engine.unregister_policy("p1") is False


class TestDefaultGraduationPolicies:
    def test_defaults_mirror_readiness_thresholds(self):
        """Default policies must be derived from ReadinessThresholds and
        the per-level minimum episode counts — no drift from the exam."""
        by_id = {p.policy_id: p for p in default_graduation_policies()}
        assert by_id["graduation_policy_intern"].rules["min_readiness_score"] == \
            ReadinessThresholds.STUDENT_TO_INTERN["overall"]
        assert by_id["graduation_policy_supervised"].rules["min_readiness_score"] == \
            ReadinessThresholds.INTERN_TO_SUPERVISED["overall"]
        assert by_id["graduation_policy_autonomous"].rules["min_readiness_score"] == \
            ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS["overall"]
        assert by_id["graduation_policy_intern"].rules["min_episodes"] == 10
        assert by_id["graduation_policy_supervised"].rules["min_episodes"] == 25
        assert by_id["graduation_policy_autonomous"].rules["min_episodes"] == 50
        assert by_id["graduation_policy_autonomous"].rules["max_intervention_rate"] == \
            pytest.approx(1.0 - ReadinessThresholds.SUPERVISED_TO_AUTONOMOUS["zero_intervention_ratio"])

    def test_layers_match_doc(self):
        by_id = {p.policy_id: p for p in default_graduation_policies()}
        assert by_id["graduation_policy_intern"].layer == "operational"
        assert by_id["graduation_policy_supervised"].layer == "tactical"
        assert by_id["graduation_policy_autonomous"].layer == "strategic"


class TestDynamicGovernanceManager:
    def test_layer_for_action_mapping(self):
        assert layer_for_action("graduate_to_intern") is GovernanceLayer.OPERATIONAL
        assert layer_for_action("graduate_to_supervised") is GovernanceLayer.TACTICAL
        assert layer_for_action("graduate_to_autonomous") is GovernanceLayer.STRATEGIC
        # Unknown graduation actions default to policy review, never silent
        # operational automation.
        assert layer_for_action("graduate_to_tenant_admin") is GovernanceLayer.TACTICAL

    def test_strategic_pass_requires_human(self):
        """The core STRATEGIC contract: policies passing is not enough —
        a human must approve the promotion."""
        decision = DynamicGovernanceManager().decide(
            agent_id="a",
            action="graduate_to_autonomous",
            layer=GovernanceLayer.STRATEGIC,
            context=STRONG_CONTEXT,
        )
        assert decision.allowed is True
        assert decision.requires_human is True

    def test_operational_pass_is_automated(self):
        decision = DynamicGovernanceManager().decide(
            agent_id="a",
            action="graduate_to_intern",
            layer=GovernanceLayer.OPERATIONAL,
            context={
                "episode_count": 12, "readiness_score": 0.75, "success_rate": 0.8,
                "constitutional_score": 0.8, "intervention_rate": 0.5,
                "confidence_score": 0.55,
            },
        )
        assert decision.allowed is True
        assert decision.requires_human is False

    def test_denied_has_no_human_step(self):
        decision = DynamicGovernanceManager().decide(
            agent_id="a",
            action="graduate_to_autonomous",
            layer=GovernanceLayer.STRATEGIC,
            context={"episode_count": 3},
        )
        assert decision.allowed is False
        assert decision.requires_human is False
        assert decision.reasons

    def test_layer_inferred_when_omitted(self):
        decision = DynamicGovernanceManager().decide(
            "a", "graduate_to_supervised", None,
            {
                "episode_count": 30, "readiness_score": 0.85, "success_rate": 0.9,
                "constitutional_score": 0.9, "intervention_rate": 0.3,
                "confidence_score": 0.75,
            },
        )
        assert decision.layer is GovernanceLayer.TACTICAL
        assert decision.allowed is True


class TestConductExamGovernanceWiring:
    """conduct_exam must consult the governance manager: policy DENY fails
    the exam; STRATEGIC pass withholds the promotion."""

    def _run_conduct_exam(self, target_level, readiness_overrides=None, current_level="supervised"):
        """Drive GraduationExamService.execute_graduation_exam with every
        stage mocked to PASS, so only the governance gate decides the
        outcome."""
        from core.graduation_exam import GraduationExamService

        base = dict(
            readiness_score=0.96, threshold_met=True,
            zero_intervention_ratio=0.95, avg_constitutional_score=0.97,
            avg_confidence_score=0.93, success_rate=0.97, episodes_analyzed=60,
        )
        base.update(readiness_overrides or {})
        readiness = SimpleNamespace(**base)
        exam_row = SimpleNamespace(
            id="exam-1", passed=None, promoted=None, promoted_at=None,
            failure_reason=None, metadata_json=None,
        )
        agent = SimpleNamespace(
            status=current_level, promotion_count=0, last_promotion_at=None,
            last_exam_id=None, exam_eligible_at=None,
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        service = GraduationExamService(db)

        with patch.object(service, "_run_edge_case_simulations", return_value={"all_passed": True}), \
             patch.object(service, "_constitutional_guardrail_check", return_value={"passed": True, "violations": []}), \
             patch.object(service, "_skill_performance_check", return_value={"requirements_met": True}), \
             patch.object(service, "_record_promotion_history"), \
             patch("core.graduation_exam.EpisodeService") as episode_svc, \
             patch("core.graduation_exam.GraduationExam", return_value=exam_row):
            episode_svc.return_value.get_graduation_readiness.return_value = readiness
            result = service.execute_graduation_exam(
                agent_id="agent-1",
                tenant_id="t-1",
                promoted_by="supervisor-1",
                target_level=target_level,
            )
        return result, agent, exam_row

    def test_autonomous_pass_withholds_promotion_for_human(self):
        result, agent, exam_row = self._run_conduct_exam("autonomous")
        assert result.passed is True
        assert result.promoted is False                     # withheld
        assert result.awaiting_human_approval is True
        assert agent.status == "supervised"                 # level unchanged
        assert exam_row.metadata_json["governance"]["awaiting_human_approval"] is True

    def test_supervised_pass_still_auto_promotes(self):
        result, agent, _ = self._run_conduct_exam(
            "supervised",
            current_level="intern",
            readiness_overrides=dict(
                readiness_score=0.85, zero_intervention_ratio=0.7,
                avg_constitutional_score=0.9, avg_confidence_score=0.75,
                success_rate=0.9, episodes_analyzed=30,
            ),
        )
        assert result.passed is True
        assert result.promoted is True
        assert result.awaiting_human_approval is False
        assert agent.status == "supervised"  # auto-promoted (TACTICAL tier)

    def test_policy_deny_fails_exam_with_reason(self):
        result, _, exam_row = self._run_conduct_exam(
            "autonomous",
            readiness_overrides=dict(
                readiness_score=0.90,                      # below 0.95 policy floor
                zero_intervention_ratio=0.95,
                avg_constitutional_score=0.97, avg_confidence_score=0.93,
                success_rate=0.97, episodes_analyzed=60,
            ),
        )
        assert result.passed is False
        assert result.promoted is False
        assert result.awaiting_human_approval is False
        assert "Governance policy denied" in (exam_row.failure_reason or "")
        assert "readiness_score 0.9" in exam_row.failure_reason


class TestPromoteAgentStrategicGate:
    """AgentGraduationService.promote_agent (supervisor endpoint) must
    re-check the strategic policy against live evidence for AUTONOMOUS."""

    @pytest.mark.asyncio
    async def test_autonomous_denied_on_weak_evidence(self):
        from core.agent_graduation_service import AgentGraduationService

        agent = SimpleNamespace(
            id="a1", status="supervised", tenant_id="t1", user_id="u1",
            configuration={}, updated_at=None, name="Sales Assistant",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        service = AgentGraduationService(db)

        weak = SimpleNamespace(
            readiness_score=0.92, zero_intervention_ratio=0.95,
            avg_constitutional_score=0.97, avg_confidence_score=0.93,
            success_rate=0.97, episodes_analyzed=40,  # < 50 floor
        )
        with patch("core.agent_graduation_service.EpisodeService") as episode_svc, \
             patch("core.agent_graduation_service.get_lancedb_handler"), \
             patch("core.agent_graduation_service.flag_modified"):
            episode_svc.return_value.get_graduation_readiness.return_value = weak
            result = await service.promote_agent("a1", "AUTONOMOUS", "supervisor-1")
        assert result is False
        assert agent.status == "supervised"

    @pytest.mark.asyncio
    async def test_autonomous_allowed_on_strong_evidence(self):
        from core.agent_graduation_service import AgentGraduationService

        agent = SimpleNamespace(
            id="a2", status="supervised", tenant_id="t1", user_id="u1",
            configuration={}, updated_at=None, name="SDR Hire",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        service = AgentGraduationService(db)

        strong = SimpleNamespace(
            readiness_score=0.96, zero_intervention_ratio=0.95,
            avg_constitutional_score=0.97, avg_confidence_score=0.93,
            success_rate=0.97, episodes_analyzed=60,
        )
        with patch("core.agent_graduation_service.EpisodeService") as episode_svc, \
             patch("core.agent_graduation_service.get_lancedb_handler"), \
             patch("core.agent_graduation_service.flag_modified"):
            episode_svc.return_value.get_graduation_readiness.return_value = strong
            result = await service.promote_agent("a2", "AUTONOMOUS", "supervisor-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_lower_tiers_untouched_by_gate(self):
        from core.agent_graduation_service import AgentGraduationService

        agent = SimpleNamespace(
            id="a3", status="student", tenant_id="t1", user_id="u1",
            configuration={}, updated_at=None, name="Intern Candidate",
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = agent
        service = AgentGraduationService(db)
        with patch("core.agent_graduation_service.EpisodeService") as episode_svc, \
             patch("core.agent_graduation_service.get_lancedb_handler"), \
             patch("core.agent_graduation_service.flag_modified"):
            result = await service.promote_agent("a3", "INTERN", "supervisor-1")
        assert result is True
        episode_svc.return_value.get_graduation_readiness.assert_not_called()
