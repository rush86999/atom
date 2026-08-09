"""
Coverage-push + bug-hunt tests for the governance trio:
- core/governance/dynamic_governance.py (three-layer governance, dynamic adaptation)
- core/jit_verification_cache.py (L1/L2/L3 JIT verification cache)
- core/proposal_service.py (INTERN proposal approval state machine)

Target: >=75% coverage per module. TDD: each bug has a failing test first.

BUGS PROVEN RED HERE (fixed in the source modules):
  JIT-1 (HIGH)   jit_verification_cache.get_business_facts passes ``tenant_id`` to
                 WorldModelService.__init__ which only accepts ``workspace_id`` ->
                 TypeError on every uncached fact lookup.
  JIT-2 (MED)    query cache keys are ambiguous: ("x:1", 5, None) and ("x", 1, "5")
                 hash to the same key -> cross-query cache poisoning.
  JIT-3 (MED)    L1MemoryCache.set_query raises KeyError when max_size < 4
                 (query_max_size = max_size // 4 == 0 -> popitem on empty dict).
  JIT-4 (LOW)    L1MemoryCache.set_verification raises KeyError when max_size == 0.
  JIT-5 (MED)    verify_citation on a local directory path raises IsADirectoryError.
  GOV-1 (MED)    ESCALATE decisions never reach the human-intervention queue
                 (confidence 0.95 > 0.5 threshold) -> human-in-the-loop dead.
  GOV-2 (LOW)    _determine_layer ignores string decision_type ("escalation" ->
                 OPERATIONAL instead of STRATEGIC).
  PROP-1 (MED)   autonomous_approve_or_reject rejection path has no PENDING_APPROVAL
                 guard -> an already-EXECUTED proposal can be flipped to REJECTED,
                 rewriting the audit trail (same bug class as reject_proposal R-round).
  PROP-2 (MED)   approve_proposal marks EXECUTION_FAILED results as EXECUTED, and
                 execution exceptions leave the row in-memory APPROVED/uncommitted
                 (retry re-executes -> double side effects).
  PROP-3 (LOW)   create_action_proposal crashes on agents with confidence_score=None.
  PROP-4 (MED)   _calculate_proposal_importance reads proposal.modifications which is
                 never set except on approve-with-modifications -> AttributeError is
                 swallowed by _create_proposal_episode -> episodes are silently never
                 created for rejected / no-modification approvals.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.governance.dynamic_governance import (
    DecisionOutcome,
    DecisionType,
    DynamicGovernanceManager,
    GovernanceConfig,
    GovernanceDecision,
    GovernanceLayer,
    GovernancePolicy,
    LayerMetrics,
    ThreeLayerGovernance,
    get_governance_manager,
    _governance_manager_instance,
)
from core.jit_verification_cache import (
    BusinessFactQueryResult,
    CitationVerificationResult,
    L1MemoryCache,
    L2RedisCache,
    JITVerificationCache,
    get_jit_verification_cache,
    _jit_cache,
)
from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    ProposalStatus,
    ProposalType,
)
from core.proposal_service import ProposalService

# ============================================================================
# Helpers
# ============================================================================


def _decision(**overrides) -> GovernanceDecision:
    base = dict(
        decision_id="dec-test",
        agent_id="agent-1",
        action="run",
        context={},
    )
    base.update(overrides)
    return GovernanceDecision(**base)


def _proposal(**overrides) -> AgentProposal:
    reasoning = overrides.pop("reasoning", None)
    execution_result = overrides.pop("execution_result", "MISSING")
    base = dict(
        id="prop-1",
        tenant_id="default",
        user_id="user-1",
        agent_id="agent-1",
        agent_name="Test Agent",
        proposal_type=ProposalType.ACTION.value,
        proposal_data={"action_type": "canvas_present", "canvas_type": "chart"},
        status=ProposalStatus.PENDING_APPROVAL.value,
        title="Test Proposal",
        created_at=datetime.now(),
    )
    base.update(overrides)
    proposal = AgentProposal(**base)
    if reasoning is not None:
        proposal.proposal_data = dict(proposal.proposal_data or {})
        proposal.proposal_data["reasoning"] = reasoning
    if execution_result != "MISSING":
        proposal.execution_result = execution_result
    return proposal


def _mock_db(proposal=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = proposal
    return db


def _citation(citation: str = "s3://bucket/doc.pdf", exists: bool = True):
    return CitationVerificationResult(
        exists=exists,
        checked_at=datetime.now(),
        citation=citation,
        size=1024 if exists else None,
    )


@pytest.fixture(autouse=True)
def _isolate_globals():
    yield
    import core.jit_verification_cache as jvc
    import core.governance.dynamic_governance as dg
    jvc._jit_cache = None
    dg._governance_manager_instance = None


# ============================================================================
# 1. dynamic_governance.py
# ============================================================================


class TestGovernanceEnums:
    def test_layer_values(self):
        assert GovernanceLayer.OPERATIONAL.value == "operational"
        assert GovernanceLayer.TACTICAL.value == "tactical"
        assert GovernanceLayer.STRATEGIC.value == "strategic"

    def test_decision_type_values(self):
        assert DecisionType.PERMISSION.value == "permission"
        assert DecisionType.LIMIT.value == "limit"
        assert DecisionType.ESCALATION.value == "escalation"
        assert DecisionType.POLICY.value == "policy"
        assert DecisionType.CREATION.value == "creation"

    def test_outcome_values(self):
        assert DecisionOutcome.ALLOW.value == "allow"
        assert DecisionOutcome.DENY.value == "deny"
        assert DecisionOutcome.ALLOW_WITH_CONDITIONS.value == "allow_with_conditions"
        assert DecisionOutcome.ESCALATE.value == "escalate"
        assert DecisionOutcome.DEFER.value == "defer"


class TestGovernanceDecision:
    def test_is_allowed(self):
        assert _decision(outcome=DecisionOutcome.ALLOW).is_allowed() is True
        assert _decision(outcome=DecisionOutcome.ALLOW_WITH_CONDITIONS).is_allowed() is True
        assert _decision(outcome=DecisionOutcome.DENY).is_allowed() is False
        assert _decision(outcome=DecisionOutcome.ESCALATE).is_allowed() is False

    def test_requires_approval(self):
        assert _decision().requires_approval() is False
        assert _decision(confidence=0.5).requires_approval() is True
        assert _decision(required_approvals=["human_review"]).requires_approval() is True

    def test_defaults(self):
        d = GovernanceDecision()
        assert d.decision_id == ""
        assert d.created_by == "system"
        assert d.outcome == DecisionOutcome.ALLOW
        assert d.confidence == 1.0


class TestThreeLayerGovernanceOperational:
    def setup_method(self):
        self.gov = ThreeLayerGovernance()

    def test_operational_allow(self):
        d = self.gov.decide(
            GovernanceLayer.OPERATIONAL,
            "a1", "browser_navigate",
            {"maturity": "INTERN", "complexity": 2},
        )
        assert d.outcome == DecisionOutcome.ALLOW
        assert d.confidence == 0.9
        assert "allows" in d.reasoning

    def test_operational_escalate_when_complexity_exceeds(self):
        d = self.gov.decide(
            GovernanceLayer.OPERATIONAL,
            "a1", "browser_navigate",
            {"maturity": "INTERN", "complexity": 4},
        )
        assert d.outcome == DecisionOutcome.ESCALATE
        assert d.confidence == 0.95
        assert "insufficient" in d.reasoning

    def test_operational_unknown_maturity_uses_student_floor(self):
        d = self.gov.decide(
            GovernanceLayer.OPERATIONAL,
            "a1", "act", {"maturity": "SUPERHUMAN", "complexity": 5},
        )
        assert d.outcome == DecisionOutcome.ESCALATE

    def test_operational_metrics_tracked(self):
        self.gov.decide(GovernanceLayer.OPERATIONAL, "a1", "x", {"maturity": "AUTONOMOUS", "complexity": 1})
        self.gov.decide(GovernanceLayer.OPERATIONAL, "a1", "x", {"maturity": "STUDENT", "complexity": 3})
        self.gov.decide(GovernanceLayer.OPERATIONAL, "a1", "x", {"maturity": "AUTONOMOUS", "complexity": 1})
        m = self.gov.get_layer_metrics(GovernanceLayer.OPERATIONAL)
        assert m.total_decisions == 3
        assert m.allowed_decisions == 2
        assert m.escalated_decisions == 1
        assert m.denied_decisions == 0

    def test_missing_layer_metrics_returns_default(self):
        m = self.gov.get_layer_metrics(GovernanceLayer.TACTICAL)
        assert m.total_decisions == 0
        assert isinstance(m, LayerMetrics)


class TestThreeLayerGovernanceTactical:
    def setup_method(self):
        self.gov = ThreeLayerGovernance()

    def test_policy_applies_and_returns_outcome(self):
        self.gov.add_policy(GovernancePolicy(
            policy_id="p1", name="Block uploads", layer=GovernanceLayer.TACTICAL,
            default_outcome=DecisionOutcome.DENY,
            applies_to_actions=["upload_file"],
            conditions=["must_review"],
        ))
        d = self.gov.decide(
            GovernanceLayer.TACTICAL, "a1", "upload_file", {},
        )
        assert d.outcome == DecisionOutcome.DENY
        assert d.conditions == ["must_review"]
        assert "Block uploads" in d.reasoning

    def test_policy_applies_to_context_filter(self):
        self.gov.add_policy(GovernancePolicy(
            policy_id="p2", name="Limit billing", layer=GovernanceLayer.TACTICAL,
            default_outcome=DecisionOutcome.DENY,
            applies_to={"resource": "billing"},
        ))
        denied = self.gov.decide(GovernanceLayer.TACTICAL, "a1", "read", {"resource": "billing"})
        allowed = self.gov.decide(GovernanceLayer.TACTICAL, "a1", "read", {"resource": "sales"})
        assert denied.outcome == DecisionOutcome.DENY
        assert allowed.outcome == DecisionOutcome.ALLOW

    def test_inactive_policy_skipped(self):
        self.gov.add_policy(GovernancePolicy(
            policy_id="p3", name="Inactive", layer=GovernanceLayer.TACTICAL,
            active=False, default_outcome=DecisionOutcome.DENY,
            applies_to_actions=["anything"],
        ))
        d = self.gov.decide(GovernanceLayer.TACTICAL, "a1", "anything", {})
        assert d.outcome == DecisionOutcome.ALLOW
        assert d.confidence == 0.7
        assert "No applicable tactical policies" in d.reasoning

    def test_non_tactical_policy_skipped(self):
        self.gov.add_policy(GovernancePolicy(
            policy_id="p4", name="Operational", layer=GovernanceLayer.OPERATIONAL,
            default_outcome=DecisionOutcome.DENY,
            applies_to_actions=["anything"],
        ))
        d = self.gov.decide(GovernanceLayer.TACTICAL, "a1", "anything", {})
        assert d.outcome == DecisionOutcome.ALLOW

    def test_action_filter_mismatch_skips_policy(self):
        self.gov.add_policy(GovernancePolicy(
            policy_id="p5", name="Only deletes", layer=GovernanceLayer.TACTICAL,
            default_outcome=DecisionOutcome.DENY, applies_to_actions=["delete"],
        ))
        d = self.gov.decide(GovernanceLayer.TACTICAL, "a1", "create", {})
        assert d.outcome == DecisionOutcome.ALLOW

    def test_first_matching_policy_wins(self):
        self.gov.add_policy(GovernancePolicy(
            policy_id="pa", name="A", layer=GovernanceLayer.TACTICAL,
            default_outcome=DecisionOutcome.DENY, applies_to_actions=["x"],
        ))
        self.gov.add_policy(GovernancePolicy(
            policy_id="pb", name="B", layer=GovernanceLayer.TACTICAL,
            default_outcome=DecisionOutcome.ALLOW_WITH_CONDITIONS, applies_to_actions=["x"],
        ))
        d = self.gov.decide(GovernanceLayer.TACTICAL, "a1", "x", {})
        assert d.outcome == DecisionOutcome.DENY

    def test_remove_policy(self):
        self.gov.add_policy(GovernancePolicy(policy_id="p9", name="X"))
        assert self.gov.remove_policy("p9") is True
        assert self.gov.remove_policy("p9") is False


class TestThreeLayerGovernanceStrategic:
    def setup_method(self):
        self.gov = ThreeLayerGovernance()

    def test_escalation_allowed_with_performance(self):
        d = self.gov.decide(
            GovernanceLayer.STRATEGIC, "a1", "escalate",
            {"decision_type": DecisionType.ESCALATION, "current_maturity": "INTERN",
             "performance_score": 0.95},
        )
        assert d.outcome == DecisionOutcome.ALLOW
        assert "Escalate to SUPERVISED" in d.conditions

    def test_escalation_denied_low_performance(self):
        d = self.gov.decide(
            GovernanceLayer.STRATEGIC, "a1", "escalate",
            {"decision_type": DecisionType.ESCALATION, "current_maturity": "INTERN",
             "performance_score": 0.5},
        )
        assert d.outcome == DecisionOutcome.DENY

    def test_escalation_at_max_maturity(self):
        d = self.gov.decide(
            GovernanceLayer.STRATEGIC, "a1", "escalate",
            {"decision_type": DecisionType.ESCALATION, "current_maturity": "AUTONOMOUS",
             "performance_score": 0.99},
        )
        assert d.outcome == DecisionOutcome.DENY

    def test_escalation_unknown_maturity(self):
        d = self.gov.decide(
            GovernanceLayer.STRATEGIC, "a1", "escalate",
            {"decision_type": DecisionType.ESCALATION, "current_maturity": "GOD",
             "performance_score": 0.99},
        )
        assert d.outcome == DecisionOutcome.ALLOW
        assert "Escalate to INTERN" in d.conditions

    def test_policy_type(self):
        d = self.gov.decide(
            GovernanceLayer.STRATEGIC, "a1", "change_policy",
            {"decision_type": DecisionType.POLICY},
        )
        assert d.outcome == DecisionOutcome.ALLOW_WITH_CONDITIONS
        assert d.confidence == 0.6

    def test_unhandled_type_allowed(self):
        d = self.gov.decide(
            GovernanceLayer.STRATEGIC, "a1", "anything",
            {"decision_type": DecisionType.CREATION},
        )
        assert d.outcome == DecisionOutcome.ALLOW
        assert d.confidence == 0.5


class TestDynamicGovernanceManager:
    def setup_method(self):
        self.mgr = DynamicGovernanceManager()

    def test_decide_determines_operational_layer(self):
        d = self.mgr.decide("a1", "browser_navigate", {"maturity": "STUDENT", "complexity": 1})
        assert d.layer == GovernanceLayer.OPERATIONAL
        assert d.outcome == DecisionOutcome.ALLOW

    def test_decide_strategic_for_escalation(self):
        d = self.mgr.decide("a1", "escalate", {"decision_type": DecisionType.ESCALATION})
        assert d.layer == GovernanceLayer.STRATEGIC

    def test_decide_strategic_for_creation(self):
        d = self.mgr.decide("a1", "create", {"decision_type": DecisionType.CREATION})
        assert d.layer == GovernanceLayer.STRATEGIC

    def test_decide_strategic_for_policy(self):
        d = self.mgr.decide("a1", "policy", {"decision_type": DecisionType.POLICY})
        assert d.layer == GovernanceLayer.STRATEGIC

    def test_decide_tactical_for_limit(self):
        d = self.mgr.decide("a1", "adjust", {"decision_type": DecisionType.LIMIT})
        assert d.layer == GovernanceLayer.TACTICAL

    def test_decide_explicit_layer(self):
        d = self.mgr.decide("a1", "x", {}, layer=GovernanceLayer.TACTICAL)
        assert d.layer == GovernanceLayer.TACTICAL

    def test_low_confidence_queues_intervention(self):
        config = GovernanceConfig(human_intervention_threshold=0.8)
        mgr = DynamicGovernanceManager(config)
        d = mgr.decide("a1", "x", {"decision_type": DecisionType.CREATION})
        assert "human_review" in d.required_approvals
        assert d in mgr.get_intervention_queue()

    def test_get_intervention_queue_returns_copy(self):
        queue = self.mgr.get_intervention_queue()
        queue.append(_decision())
        assert self.mgr.get_intervention_queue() == []

    # ---- GOV-1 (RED): ESCALATE must reach the human-intervention queue ----
    def test_escalate_decision_queued_for_intervention(self):
        d = self.mgr.decide(
            "a1", "act",
            {"maturity": "STUDENT", "complexity": 3},
            layer=GovernanceLayer.OPERATIONAL,
        )
        assert d.outcome == DecisionOutcome.ESCALATE
        assert "human_review" in d.required_approvals
        assert d in self.mgr.get_intervention_queue()

    # ---- GOV-2 (RED): string decision_type must map to the right layer ----
    def test_determine_layer_accepts_string_decision_type(self):
        assert self.mgr._determine_layer({"decision_type": "escalation"}) == GovernanceLayer.STRATEGIC
        assert self.mgr._determine_layer({"decision_type": "limit"}) == GovernanceLayer.TACTICAL
        assert self.mgr._determine_layer({"decision_type": "permission"}) == GovernanceLayer.OPERATIONAL
        assert self.mgr._determine_layer({"decision_type": "garbage"}) == GovernanceLayer.OPERATIONAL

    def test_resolve_intervention_found(self):
        mgr = DynamicGovernanceManager(GovernanceConfig(human_intervention_threshold=0.8))
        d = mgr.decide("a1", "x", {"decision_type": DecisionType.CREATION},
                       layer=GovernanceLayer.STRATEGIC)
        assert d in mgr.get_intervention_queue()
        assert mgr.resolve_intervention(d.decision_id, DecisionOutcome.ALLOW) is True
        assert mgr.get_intervention_queue() == []
        stats = mgr.get_statistics()
        assert stats["resolved_interventions"] == 1

    def test_resolve_intervention_missing(self):
        assert self.mgr.resolve_intervention("nope", DecisionOutcome.ALLOW) is False

    def test_record_performance_triggers_escalation_adaptation(self):
        for _ in range(100):
            self.mgr.record_performance("a1", 0.99)
        assert any(a["adaptation_type"] == "escalation" for a in self.mgr._adaptations)

    def test_record_performance_triggers_intervention_adaptation(self):
        for _ in range(100):
            self.mgr.record_performance("a2", 0.1)
        assert any(a["adaptation_type"] == "intervention" for a in self.mgr._adaptations)

    def test_record_performance_mid_range_no_adaptation(self):
        for _ in range(100):
            self.mgr.record_performance("a3", 0.7)
        assert self.mgr._adaptations == []

    def test_record_performance_uses_only_last_100(self):
        for _ in range(100):
            self.mgr.record_performance("a4", 0.99)  # triggers escalation
        for _ in range(50):
            self.mgr.record_performance("a4", 0.5)
        # the 100x0.99 prefix has left the window; last-100 average is 0.745,
        # so no intervention adaptation despite the low tail
        assert [a["adaptation_type"] for a in self.mgr._adaptations] == ["escalation"]

    def test_record_feedback(self):
        self.mgr.record_feedback("a1", 0.8)
        assert self.mgr._feedback_history["a1"] == [0.8]

    def test_get_statistics(self):
        stats = self.mgr.get_statistics()
        assert stats["total_interventions"] == 0
        assert stats["adaptations_suggested"] == 0
        assert stats["layer_metrics"]["operational"]["total_decisions"] == 0
        self.mgr.decide("a1", "x", {"maturity": "STUDENT", "complexity": 1})
        stats = self.mgr.get_statistics()
        assert stats["layer_metrics"]["operational"]["total_decisions"] == 1

    def test_singleton_factory(self):
        a = get_governance_manager()
        b = get_governance_manager()
        assert a is b
        fresh = get_governance_manager(GovernanceConfig())
        assert fresh is a  # config ignored once created


# ============================================================================
# 2. jit_verification_cache.py
# ============================================================================


class TestCacheResultModels:
    def test_citation_roundtrip(self):
        r = CitationVerificationResult(
            exists=True, checked_at=datetime(2026, 1, 15, 10, 30),
            citation="s3://b/f.pdf", size=10, last_modified=datetime(2026, 1, 1),
        )
        r2 = CitationVerificationResult.from_dict(r.to_dict())
        assert r2.exists == r.exists
        assert r2.checked_at == r.checked_at
        assert r2.citation == r.citation
        assert r2.size == r.size
        assert r2.last_modified == r.last_modified

    def test_citation_roundtrip_optional_none(self):
        r = _citation()
        r2 = CitationVerificationResult.from_dict(r.to_dict())
        assert r2.size == 1024
        assert r2.last_modified is None

    def test_query_roundtrip(self):
        q = BusinessFactQueryResult(
            facts=[{"id": "f1"}], cached_at=datetime(2026, 1, 15, 10, 30),
            query="q", limit=5, domain="finance",
        )
        q2 = BusinessFactQueryResult.from_dict(q.to_dict())
        assert q2.facts == q.facts
        assert q2.cached_at == q.cached_at
        assert q2.query == "q"
        assert q2.limit == 5
        assert q2.domain == "finance"

    def test_query_roundtrip_no_domain(self):
        q = BusinessFactQueryResult(facts=[], cached_at=datetime.now(), query="q", limit=1)
        q2 = BusinessFactQueryResult.from_dict(q.to_dict())
        assert q2.domain is None


class TestL1MemoryCache:
    def test_verification_hit_and_miss_counts(self):
        cache = L1MemoryCache(max_size=10)
        cache.set_verification("s3://b/a.pdf", _citation("s3://b/a.pdf"))
        assert cache.get_verification("s3://b/a.pdf") is not None
        assert cache.get_verification("s3://b/missing.pdf") is None
        stats = cache.get_stats()
        assert stats["l1_verification_hits"] == 1
        assert stats["l1_verification_misses"] == 1
        assert stats["l1_verification_hit_rate"] == 0.5

    def test_verification_ttl_expiry(self):
        cache = L1MemoryCache(max_size=10, verification_ttl=1)
        old = CitationVerificationResult(
            exists=True, checked_at=datetime.now() - timedelta(seconds=2),
            citation="s3://b/a.pdf",
        )
        cache.set_verification("s3://b/a.pdf", old)
        assert cache.get_verification("s3://b/a.pdf") is None
        assert cache.get_stats()["l1_evictions"] == 1

    def test_verification_ttl_not_expired(self):
        cache = L1MemoryCache(max_size=10, verification_ttl=300)
        fresh = CitationVerificationResult(
            exists=True, checked_at=datetime.now(), citation="s3://b/a.pdf",
        )
        cache.set_verification("s3://b/a.pdf", fresh)
        assert cache.get_verification("s3://b/a.pdf") is not None

    def test_verification_lru_eviction(self):
        cache = L1MemoryCache(max_size=2)
        cache.set_verification("k1", _citation("k1"))
        cache.set_verification("k2", _citation("k2"))
        cache.get_verification("k1")  # touch k1 -> k2 becomes LRU
        cache.set_verification("k3", _citation("k3"))
        assert cache.get_verification("k2") is None
        assert cache.get_verification("k1") is not None
        assert cache.get_stats()["l1_evictions"] == 1

    def test_query_hit_miss_ttl(self):
        cache = L1MemoryCache(max_size=16, query_ttl=1)
        q = BusinessFactQueryResult(facts=[{"id": "f"}], cached_at=datetime.now(), query="q", limit=5)
        cache.set_query("q", 5, None, q)
        assert cache.get_query("q", 5, None) is not None
        assert cache.get_query("q", 6, None) is None
        old_q = BusinessFactQueryResult(
            facts=[], cached_at=datetime.now() - timedelta(seconds=2), query="q2", limit=5,
        )
        cache.set_query("q2", 5, None, old_q)
        assert cache.get_query("q2", 5, None) is None
        assert cache.get_stats()["l1_query_hits"] == 1
        assert cache.get_stats()["l1_query_misses"] == 2

    def test_query_domain_partitions(self):
        cache = L1MemoryCache(max_size=16)
        cache.set_query("q", 5, "finance", BusinessFactQueryResult(facts=[{"id": "fin"}], cached_at=datetime.now(), query="q", limit=5, domain="finance"))
        cache.set_query("q", 5, None, BusinessFactQueryResult(facts=[{"id": "all"}], cached_at=datetime.now(), query="q", limit=5))
        assert cache.get_query("q", 5, "finance").facts == [{"id": "fin"}]
        assert cache.get_query("q", 5, None).facts == [{"id": "all"}]

    def test_query_lru_eviction_quarter_capacity(self):
        cache = L1MemoryCache(max_size=16)  # query capacity 4
        for i in range(5):
            cache.set_query(f"q{i}", 5, None, BusinessFactQueryResult(facts=[{"id": str(i)}], cached_at=datetime.now(), query=f"q{i}", limit=5))
        assert cache.get_query("q0", 5, None) is None
        assert cache.get_query("q4", 5, None) is not None

    # ---- JIT-2 (RED): colliding query keys must not share cache entries ----
    def test_query_key_no_collision_across_query_domain_forms(self):
        cache = L1MemoryCache(max_size=64)
        cache.set_query("x:1", 5, None, BusinessFactQueryResult(facts=[{"id": "A"}], cached_at=datetime.now(), query="x:1", limit=5))
        assert cache.get_query("x", 1, "5") is None

    # ---- JIT-3 (RED): set_query must not crash when max_size < 4 ----
    def test_set_query_small_max_size(self):
        cache = L1MemoryCache(max_size=2)
        result = BusinessFactQueryResult(facts=[{"id": "f"}], cached_at=datetime.now(), query="q", limit=5)
        cache.set_query("q", 5, None, result)
        assert cache.get_query("q", 5, None) is not None

    # ---- JIT-4 (RED): set_verification must not crash when max_size == 0 ----
    def test_set_verification_zero_max_size(self):
        cache = L1MemoryCache(max_size=0)
        cache.set_verification("s3://b/a.pdf", _citation("s3://b/a.pdf"))

    def test_invalidate_verification(self):
        cache = L1MemoryCache(max_size=10)
        cache.set_verification("s3://b/a.pdf", _citation("s3://b/a.pdf"))
        cache.invalidate_citation("s3://b/a.pdf")
        assert cache.get_verification("s3://b/a.pdf") is None
        cache.invalidate_citation("s3://b/never.pdf")  # no-op

    def test_invalidate_query(self):
        cache = L1MemoryCache(max_size=16)
        cache.set_query("q", 5, None, BusinessFactQueryResult(facts=[], cached_at=datetime.now(), query="q", limit=5))
        cache.invalidate_query("q", 5, None)
        assert cache.get_query("q", 5, None) is None
        cache.invalidate_query("q", 5, "nope")  # no-op

    def test_clear(self):
        cache = L1MemoryCache(max_size=16)
        cache.set_verification("s3://b/a.pdf", _citation("s3://b/a.pdf"))
        cache.set_query("q", 5, None, BusinessFactQueryResult(facts=[], cached_at=datetime.now(), query="q", limit=5))
        cache.clear()
        assert cache.get_verification("s3://b/a.pdf") is None
        assert cache.get_query("q", 5, None) is None

    def test_stats_zero_division_safe(self):
        cache = L1MemoryCache(max_size=10)
        stats = cache.get_stats()
        assert stats["l1_verification_hit_rate"] == 0
        assert stats["l1_query_hit_rate"] == 0


class TestL2RedisCache:
    @pytest.fixture
    def redis_client(self):
        client = MagicMock()
        client.ping.return_value = True
        return client

    def test_init_redis_unavailable(self):
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", False):
            cache = L2RedisCache()
        assert cache._enabled is False

    def test_init_redis_available_url(self, redis_client):
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        assert cache._enabled is True
        redis_client.ping.assert_called_once()

    def test_init_redis_env_vars(self, redis_client):
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.Redis", return_value=redis_client) as m:
                with patch("os.getenv", side_effect=lambda k, d=None: {"REDIS_HOST": "redis0", "REDIS_PORT": "6380", "REDIS_DB": "2"}.get(k, d)):
                    cache = L2RedisCache()
        assert cache._enabled is True
        assert m.call_args.kwargs["host"] == "redis0"
        assert m.call_args.kwargs["port"] == 6380
        assert m.call_args.kwargs["db"] == 2

    def test_init_redis_connection_failure(self, redis_client):
        redis_client.ping.side_effect = Exception("down")
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        assert cache._enabled is False

    @pytest.mark.asyncio
    async def test_disabled_ops_noop(self):
        cache = L2RedisCache()
        assert await cache.get_verification("s3://b/a.pdf") is None
        await cache.set_verification("s3://b/a.pdf", _citation("s3://b/a.pdf"))
        assert await cache.get_query("q", 5, None) is None
        await cache.set_query("q", 5, None, BusinessFactQueryResult(facts=[], cached_at=datetime.now(), query="q", limit=5))
        cache.invalidate_citation("s3://b/a.pdf")
        cache.clear()

    @pytest.mark.asyncio
    async def test_get_verification_parses_json(self, redis_client):
        redis_client.get.return_value = json.dumps(_citation("s3://b/a.pdf").to_dict()).encode()
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        result = await cache.get_verification("s3://b/a.pdf")
        assert result is not None
        assert result.exists is True
        assert result.citation == "s3://b/a.pdf"

    @pytest.mark.asyncio
    async def test_get_verification_missing(self, redis_client):
        redis_client.get.return_value = None
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        assert await cache.get_verification("s3://b/a.pdf") is None

    @pytest.mark.asyncio
    async def test_get_verification_redis_error(self, redis_client):
        redis_client.get.side_effect = RuntimeError("boom")
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        assert await cache.get_verification("s3://b/a.pdf") is None

    @pytest.mark.asyncio
    async def test_set_verification_uses_setex(self, redis_client):
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0", verification_ttl=123)
        await cache.set_verification("s3://b/a.pdf", _citation("s3://b/a.pdf"))
        redis_client.setex.assert_called_once()
        args = redis_client.setex.call_args.args
        assert args[1] == 123

    @pytest.mark.asyncio
    async def test_set_verification_redis_error_no_raise(self, redis_client):
        redis_client.setex.side_effect = RuntimeError("boom")
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        await cache.set_verification("s3://b/a.pdf", _citation("s3://b/a.pdf"))

    @pytest.mark.asyncio
    async def test_query_get_set(self, redis_client):
        q = BusinessFactQueryResult(facts=[{"id": "f"}], cached_at=datetime.now(), query="q", limit=5, domain="fin")
        redis_client.get.return_value = json.dumps(q.to_dict()).encode()
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0", query_ttl=456)
        result = await cache.get_query("q", 5, "fin")
        assert result is not None
        assert result.facts == [{"id": "f"}]
        await cache.set_query("q", 5, "fin", q)
        redis_client.setex.assert_called_once()
        assert redis_client.setex.call_args.args[1] == 456

    @pytest.mark.asyncio
    async def test_query_get_redis_error(self, redis_client):
        redis_client.get.side_effect = RuntimeError("boom")
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        assert await cache.get_query("q", 5, None) is None

    def test_invalidate_citation(self, redis_client):
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        cache.invalidate_citation("s3://b/a.pdf")
        redis_client.delete.assert_called_once()

    def test_invalidate_citation_error_no_raise(self, redis_client):
        redis_client.delete.side_effect = RuntimeError("boom")
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        cache.invalidate_citation("s3://b/a.pdf")

    def test_clear_scans_and_deletes(self, redis_client):
        redis_client.scan_iter.return_value = ["atom:jit:verify:x", "atom:jit:query:y"]
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        cache.clear()
        assert redis_client.delete.call_count == 2

    def test_clear_error_no_raise(self, redis_client):
        redis_client.scan_iter.side_effect = RuntimeError("boom")
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", True):
            with patch("core.jit_verification_cache.redis.from_url", return_value=redis_client):
                cache = L2RedisCache(redis_url="redis://localhost:6379/0")
        cache.clear()


class TestJITVerificationCacheCitations:
    def make_cache(self):
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", False):
            return JITVerificationCache(l1_max_size=100, redis_url=None)

    def test_local_file_exists(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"content")
            path = f.name
        try:
            cache = self.make_cache()
            result = asyncio.run(cache.verify_citation(path))
            assert result.exists is True
            assert result.size == len(b"content")
        finally:
            os.unlink(path)

    def test_local_file_missing(self):
        cache = self.make_cache()
        result = asyncio.run(cache.verify_citation("/nonexistent/path/file.pdf"))
        assert result.exists is False
        assert result.size is None

    # ---- JIT-5 (RED): directory citation must not raise ----
    def test_local_directory_citation_no_raise(self):
        with tempfile.TemporaryDirectory() as d:
            cache = self.make_cache()
            result = asyncio.run(cache.verify_citation(d))
            assert result.exists is False

    def test_s3_exists(self):
        storage = MagicMock()
        storage.bucket = "atom-saas"
        storage.s3.head_object.return_value = {
            "ContentLength": 2048,
            "LastModified": datetime.now(),
        }
        cache = self.make_cache()
        cache._storage = storage
        result = asyncio.run(cache.verify_citation("s3://atom-saas/path/file.pdf"))
        assert result.exists is True
        assert result.size == 2048

    def test_s3_missing(self):
        storage = MagicMock()
        storage.bucket = "atom-saas"
        storage.s3.head_object.side_effect = Exception("NotFound")
        cache = self.make_cache()
        cache._storage = storage
        result = asyncio.run(cache.verify_citation("s3://atom-saas/path/missing.pdf"))
        assert result.exists is False

    def test_s3_other_bucket_not_matched(self):
        storage = MagicMock()
        storage.bucket = "atom-saas"
        cache = self.make_cache()
        cache._storage = storage
        result = asyncio.run(cache.verify_citation("s3://other-bucket/file.pdf"))
        assert result.exists is False
        storage.s3.head_object.assert_not_called()

    def test_s3_verification_error_logged(self):
        storage = MagicMock()
        storage.bucket = "atom-saas"
        storage.s3.head_object.side_effect = Exception("boom")
        cache = self.make_cache()
        cache._storage = storage
        result = asyncio.run(cache.verify_citation("s3://atom-saas/x.pdf"))
        assert result.exists is False

    def test_cached_l1_no_storage_call(self):
        storage = MagicMock()
        storage.bucket = "atom-saas"
        cache = self.make_cache()
        cache._storage = storage
        asyncio.run(cache.verify_citation("s3://atom-saas/a.pdf"))
        storage.s3.head_object.reset_mock()
        asyncio.run(cache.verify_citation("s3://atom-saas/a.pdf"))
        storage.s3.head_object.assert_not_called()

    def test_force_refresh_bypasses_cache(self):
        storage = MagicMock()
        storage.bucket = "atom-saas"
        storage.s3.head_object.return_value = {"ContentLength": 1, "LastModified": datetime.now()}
        cache = self.make_cache()
        cache._storage = storage
        asyncio.run(cache.verify_citation("s3://atom-saas/a.pdf"))
        storage.s3.head_object.reset_mock()
        asyncio.run(cache.verify_citation("s3://atom-saas/a.pdf", force_refresh=True))
        storage.s3.head_object.assert_called_once()

    def test_l2_promotes_to_l1(self):
        cache = self.make_cache()
        l2 = MagicMock()
        l2._enabled = True
        l2.get_verification = AsyncMock(return_value=_citation("s3://b/c.pdf"))
        cache.l2 = l2
        storage = MagicMock()
        storage.bucket = "atom-saas"
        cache._storage = storage
        result = asyncio.run(cache.verify_citation("s3://b/c.pdf"))
        assert result.exists is True
        assert cache.l1.get_verification("s3://b/c.pdf") is not None
        storage.s3.head_object.assert_not_called()

    def test_batch(self):
        storage = MagicMock()
        storage.bucket = "atom-saas"
        storage.s3.head_object.return_value = {"ContentLength": 1, "LastModified": datetime.now()}
        cache = self.make_cache()
        cache._storage = storage
        results = asyncio.run(cache.verify_citations_batch(
            ["s3://atom-saas/a.pdf", "s3://atom-saas/b.pdf", "/nonexistent/c.pdf"]
        ))
        assert len(results) == 3
        assert results[0].exists is True
        assert results[2].exists is False

    def test_invalidate_citation_forces_reverify(self):
        storage = MagicMock()
        storage.bucket = "atom-saas"
        storage.s3.head_object.return_value = {"ContentLength": 1, "LastModified": datetime.now()}
        cache = self.make_cache()
        cache._storage = storage
        asyncio.run(cache.verify_citation("s3://atom-saas/a.pdf"))
        cache.invalidate_citation("s3://atom-saas/a.pdf")
        storage.s3.head_object.reset_mock()
        asyncio.run(cache.verify_citation("s3://atom-saas/a.pdf"))
        storage.s3.head_object.assert_called_once()

    def test_get_stats_shape(self):
        cache = self.make_cache()
        stats = cache.get_stats()
        assert "l1" in stats and "l2_enabled" in stats

    def test_clear_all(self):
        cache = self.make_cache()
        cache.set_verification_probe = True
        with patch.object(cache.l1, "clear") as l1c, patch.object(cache.l2, "clear") as l2c:
            cache.clear_all()
        l1c.assert_called_once()
        l2c.assert_called_once()

    def test_invalidate_query_l1_only(self):
        cache = self.make_cache()
        q = BusinessFactQueryResult(facts=[], cached_at=datetime.now(), query="q", limit=5)
        cache.l1.set_query("q", 5, None, q)
        cache.invalidate_query("q", 5, None)
        assert cache.l1.get_query("q", 5, None) is None


class TestJITVerificationCacheFacts:
    @pytest.fixture
    def fact(self):
        return SimpleNamespace(
            id="fact-1", fact="VP approval for >$500",
            citations=["policy.pdf:p4"], reason="Approval policy",
            verification_status="verified", created_at=datetime(2026, 1, 1),
            last_verified=datetime(2026, 1, 2),
        )

    def make_cache(self):
        with patch("core.jit_verification_cache.REDIS_AVAILABLE", False):
            return JITVerificationCache(l1_max_size=100, redis_url=None)

    # ---- JIT-1 (RED): get_business_facts must construct WorldModelService
    # with only the supported ``workspace_id`` kwarg ----
    @pytest.mark.asyncio
    async def test_get_business_facts_uncached(self, fact):
        with patch("core.agent_world_model.WorldModelService") as wm_cls:
            wm_cls.return_value.list_all_facts = AsyncMock(return_value=[fact])
            cache = self.make_cache()
            facts = await cache.get_business_facts("approval", force_refresh=True)
        assert facts[0]["id"] == "fact-1"
        assert facts[0]["fact"] == "VP approval for >$500"
        assert facts[0]["verification_status"] == "verified"
        wm_cls.assert_called_once_with(workspace_id="default")

    @pytest.mark.asyncio
    async def test_get_business_facts_cached_l1(self, fact):
        with patch("core.agent_world_model.WorldModelService") as wm_cls:
            wm_cls.return_value.list_all_facts = AsyncMock(return_value=[fact])
            cache = self.make_cache()
            await cache.get_business_facts("approval")
            wm_cls.return_value.list_all_facts.reset_mock()
            facts = await cache.get_business_facts("approval")
        assert facts[0]["id"] == "fact-1"
        wm_cls.return_value.list_all_facts.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_business_facts_force_refresh(self, fact):
        with patch("core.agent_world_model.WorldModelService") as wm_cls:
            wm_cls.return_value.list_all_facts = AsyncMock(return_value=[fact])
            cache = self.make_cache()
            await cache.get_business_facts("approval")
            facts = await cache.get_business_facts("approval", force_refresh=True)
        assert facts[0]["id"] == "fact-1"
        assert wm_cls.return_value.list_all_facts.call_count == 2

    @pytest.mark.asyncio
    async def test_get_business_facts_l2_promote(self, fact):
        cache = self.make_cache()
        l2 = MagicMock()
        l2._enabled = True
        l2.get_query = AsyncMock(return_value=BusinessFactQueryResult(
            facts=[{"id": "l2-fact"}], cached_at=datetime.now(), query="approval", limit=5,
        ))
        cache.l2 = l2
        with patch("core.agent_world_model.WorldModelService") as wm_cls:
            facts = await cache.get_business_facts("approval")
        assert facts[0]["id"] == "l2-fact"
        wm_cls.assert_not_called()
        assert cache.l1.get_query("approval", 5, None) is not None

    @pytest.mark.asyncio
    async def test_get_business_facts_passes_domain(self, fact):
        with patch("core.agent_world_model.WorldModelService") as wm_cls:
            wm_cls.return_value.list_all_facts = AsyncMock(return_value=[fact])
            cache = self.make_cache()
            await cache.get_business_facts("approval", domain="finance", force_refresh=True)
            wm_cls.return_value.list_all_facts.assert_awaited_once_with(limit=5, domain="finance")


class TestJITGlobalInstance:
    def test_singleton(self):
        a = get_jit_verification_cache()
        b = get_jit_verification_cache()
        assert a is b


# ============================================================================
# 3. proposal_service.py
# ============================================================================


@pytest.fixture
def ps_patches():
    with patch("core.proposal_service.AgentLearningEnhanced") as learning_cls, \
         patch("core.episode_segmentation_service.EpisodeSegmentationService") as seg_cls:
        learning_cls.return_value.record_user_correction = AsyncMock()
        learning_cls.return_value.record_rejection = AsyncMock()
        yield SimpleNamespace(learning=learning_cls, segments=seg_cls)


class TestCreateActionProposal:
    def test_create_intern_agent(self, ps_patches):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.status = AgentStatus.INTERN.value
        agent.name = "Intern A"
        agent.category = "testing"
        agent.confidence_score = 0.6
        agent.tenant_id = None
        agent.user_id = None
        db = _mock_db(agent)
        service = ProposalService(db)
        proposal = asyncio.run(service.create_action_proposal(
            intern_agent_id="agent-1", trigger_context={},
            proposed_action={"action_type": "canvas_present"}, reasoning="because",
        ))
        assert proposal.agent_id == "agent-1"
        assert proposal.status == ProposalStatus.PENDING_APPROVAL.value
        assert proposal.proposal_type == ProposalType.ACTION.value
        assert proposal.user_id == "system"
        assert proposal.tenant_id == "default"
        assert proposal.title == "Action Proposal: Intern A"
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_create_with_selector_candidates(self, ps_patches):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.status = AgentStatus.INTERN.value
        agent.name = "Intern A"
        agent.category = "testing"
        agent.confidence_score = 0.6
        agent.tenant_id = "t1"
        agent.user_id = "u1"
        db = _mock_db(agent)
        service = ProposalService(db)
        proposal = asyncio.run(service.create_action_proposal(
            intern_agent_id="agent-1", trigger_context={},
            proposed_action={
                "action_type": "browser_automate",
                "selector_candidates": [
                    {"selector": "#btn", "match_count": 2, "is_text_only": False},
                    "fallback candidate",
                ],
                "match_rationale": "2 matches",
                "match_score": 0.7,
                "chosen_index": 0,
                "per_field_confidence": {"#btn": {"level": "high", "score": 0.9}},
            },
            reasoning="because",
        ))
        assert "Selector candidates (2)" in proposal.description
        assert "Match rationale:" in proposal.description and "2 matches" in proposal.description
        assert "Per-field confidence" in proposal.description
        assert "`#btn`" in proposal.description
        assert "fallback candidate" in proposal.description

    def test_create_selector_candidates_dict_missing_keys(self, ps_patches):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.status = AgentStatus.INTERN.value
        agent.name = "A"
        agent.category = "testing"
        agent.confidence_score = 0.6
        db = _mock_db(agent)
        service = ProposalService(db)
        proposal = asyncio.run(service.create_action_proposal(
            intern_agent_id="agent-1", trigger_context={},
            proposed_action={"action_type": "browser_automate", "selector_candidates": [{"selector": "x"}]},
            reasoning="r",
        ))
        assert "match_count=?" in proposal.description

    def test_create_non_intern_blocked(self, ps_patches):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.status = AgentStatus.STUDENT.value
        db = _mock_db(agent)
        service = ProposalService(db)
        with pytest.raises(PermissionError) as e:
            asyncio.run(service.create_action_proposal(
                intern_agent_id="agent-1", trigger_context={},
                proposed_action={}, reasoning="r",
            ))
        assert "INTERN" in str(e.value)

    def test_create_agent_not_found(self, ps_patches):
        db = _mock_db(None)
        service = ProposalService(db)
        with pytest.raises(ValueError):
            asyncio.run(service.create_action_proposal(
                intern_agent_id="missing", trigger_context={},
                proposed_action={}, reasoning="r",
            ))

    # ---- PROP-3 (RED): confidence_score=None must not crash ----
    def test_create_agent_without_confidence_score(self, ps_patches):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.status = AgentStatus.INTERN.value
        agent.name = "A"
        agent.category = "testing"
        agent.confidence_score = None
        db = _mock_db(agent)
        service = ProposalService(db)
        proposal = asyncio.run(service.create_action_proposal(
            intern_agent_id="agent-1", trigger_context={},
            proposed_action={"action_type": "canvas_present"}, reasoning="r",
        ))
        assert proposal is not None
        assert "0.00" in proposal.description

    def test_create_custom_title_and_attachments(self, ps_patches):
        agent = MagicMock()
        agent.id = "agent-1"
        agent.status = AgentStatus.INTERN.value
        agent.name = "A"
        agent.category = "testing"
        agent.confidence_score = 0.6
        db = _mock_db(agent)
        service = ProposalService(db)
        proposal = asyncio.run(service.create_action_proposal(
            intern_agent_id="agent-1", trigger_context={},
            proposed_action={"action_type": "canvas_present"}, reasoning="r",
            canvas_id="c1", session_id="s1", title="My Title",
        ))
        assert proposal.canvas_id == "c1"
        assert proposal.session_id == "s1"
        assert proposal.title == "My Title"
        assert proposal.description.startswith("Agent is proposing")


class TestSubmitForApproval:
    def test_submit_ok(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        service = ProposalService(db)
        asyncio.run(service.submit_for_approval(proposal))

    def test_submit_wrong_status(self):
        proposal = _proposal(status=ProposalStatus.APPROVED.value)
        db = _mock_db(proposal)
        service = ProposalService(db)
        with pytest.raises(ValueError):
            asyncio.run(service.submit_for_approval(proposal))


class TestApproveProposal:
    @pytest.fixture
    def service_db(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        return proposal, db, ProposalService(db)

    def test_approve_not_found(self):
        db = _mock_db(None)
        service = ProposalService(db)
        with pytest.raises(ValueError):
            asyncio.run(service.approve_proposal("prop-x", user_id="u"))

    def test_approve_wrong_status(self):
        proposal = _proposal(status=ProposalStatus.REJECTED.value)
        db = _mock_db(proposal)
        service = ProposalService(db)
        with pytest.raises(ValueError):
            asyncio.run(service.approve_proposal("prop-1", user_id="u"))

    def test_approve_success(self, service_db):
        proposal, db, service = service_db
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True, "result": "ok"}
            result = asyncio.run(service.approve_proposal("prop-1", user_id="approver-1"))
        assert result["success"] is True
        assert proposal.status == ProposalStatus.EXECUTED.value
        assert proposal.approved_by == "approver-1"
        assert proposal.approved_at is not None
        assert proposal.executed_at is not None
        assert proposal.execution_result == {"success": True, "result": "ok"}
        db.commit.assert_called()
        db.refresh.assert_called()

    def test_approve_creates_episode(self, service_db):
        proposal, db, service = service_db
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            asyncio.run(service.approve_proposal("prop-1", user_id="approver-1"))
        added = [c for c in db.add.call_args_list]
        assert any(isinstance(c.args[0], Episode) for c in added)
        episode = next(c.args[0] for c in added if isinstance(c.args[0], Episode))
        assert episode.proposal_id == "prop-1"
        assert episode.supervision_decision == "approved"

    def test_approve_with_modifications_merges_and_records(self, service_db, ps_patches):
        proposal, db, service = service_db
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            asyncio.run(service.approve_proposal(
                "prop-1", user_id="approver-1",
                modifications={"canvas_type": "table", "title": "New"},
            ))
        assert proposal.proposal_data["canvas_type"] == "table"
        assert proposal.proposal_data["title"] == "New"
        assert proposal.proposal_data["action_type"] == "canvas_present"
        assert proposal.modifications == {"canvas_type": "table", "title": "New"}
        ps_patches.learning.return_value.record_user_correction.assert_awaited_once()

    def test_approve_modifications_without_proposed_action(self, ps_patches):
        proposal = _proposal(proposal_data=None)
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            asyncio.run(service.approve_proposal(
                "prop-1", user_id="u", modifications={"a": 1},
            ))
        assert proposal.modifications == {"a": 1}

    def test_approve_modifications_episode_uses_normalized_list(self, service_db):
        proposal, db, service = service_db
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            asyncio.run(service.approve_proposal(
                "prop-1", user_id="u", modifications={"a": 1, "b": 2},
            ))
        added = [c.args[0] for c in db.add.call_args_list]
        episode = next(c for c in added if isinstance(c, Episode))
        assert episode.metadata_json["human_edits"] == [{"a": 1}, {"b": 2}]

    # ---- PROP-2a (RED): failed execution must mark EXECUTION_FAILED, not EXECUTED ----
    def test_approve_failed_execution_marks_execution_failed(self, service_db):
        proposal, db, service = service_db
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": False, "error": "boom"}
            asyncio.run(service.approve_proposal("prop-1", user_id="u"))
        assert proposal.status == ProposalStatus.EXECUTION_FAILED.value
        added = [c.args[0] for c in db.add.call_args_list]
        episode = next(c for c in added if isinstance(c, Episode))
        assert episode.supervision_decision == "failed"

    # ---- PROP-2b (RED): execution exception must persist EXECUTION_FAILED then re-raise ----
    def test_approve_execution_exception_marks_execution_failed(self, service_db):
        proposal, db, service = service_db
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("exec failed")
            with pytest.raises(RuntimeError):
                asyncio.run(service.approve_proposal("prop-1", user_id="u"))
        assert proposal.status == ProposalStatus.EXECUTION_FAILED.value
        assert proposal.execution_result["success"] is False
        assert proposal.executed_at is not None
        db.commit.assert_called()

    def test_double_approve_raises(self, service_db):
        proposal, db, service = service_db
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            asyncio.run(service.approve_proposal("prop-1", user_id="u"))
        with pytest.raises(ValueError):
            asyncio.run(service.approve_proposal("prop-1", user_id="u2"))


class TestRejectProposal:
    @pytest.fixture
    def service_db(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        return proposal, db, ProposalService(db)

    def test_reject_not_found(self):
        db = _mock_db(None)
        service = ProposalService(db)
        with pytest.raises(ValueError):
            asyncio.run(service.reject_proposal("prop-x", user_id="u", reason="no"))

    def test_reject_wrong_status(self):
        proposal = _proposal(status=ProposalStatus.EXECUTED.value)
        db = _mock_db(proposal)
        service = ProposalService(db)
        with pytest.raises(ValueError):
            asyncio.run(service.reject_proposal("prop-1", user_id="u", reason="no"))

    def test_reject_success(self, service_db, ps_patches):
        proposal, db, service = service_db
        asyncio.run(service.reject_proposal("prop-1", user_id="reviewer-1", reason="not needed"))
        assert proposal.status == ProposalStatus.REJECTED.value
        assert proposal.approved_by == "reviewer-1"
        assert proposal.execution_result["rejected"] is True
        assert proposal.execution_result["reason"] == "not needed"
        ps_patches.learning.return_value.record_rejection.assert_awaited_once()

    # ---- PROP-4 (RED): rejected proposal must still create an episode ----
    def test_reject_creates_episode(self, service_db):
        proposal, db, service = service_db
        asyncio.run(service.reject_proposal("prop-1", user_id="reviewer-1", reason="no"))
        added = [c.args[0] for c in db.add.call_args_list]
        episode = next((c for c in added if isinstance(c, Episode)), None)
        assert episode is not None
        assert episode.supervision_decision == "rejected"
        assert episode.supervision_reasoning == "no"
        assert episode.importance_score == 0.8

    def test_reject_twice_raises(self, service_db, ps_patches):
        proposal, db, service = service_db
        asyncio.run(service.reject_proposal("prop-1", user_id="u", reason="first"))
        with pytest.raises(ValueError):
            asyncio.run(service.reject_proposal("prop-1", user_id="u", reason="again"))


class TestGetPendingAndHistory:
    def test_pending_no_filters(self):
        db = MagicMock()
        q = MagicMock()
        q.order_by.return_value.limit.return_value.all.return_value = ["p1"]
        db.query.return_value.filter.return_value = q
        service = ProposalService(db)
        result = asyncio.run(service.get_pending_proposals())
        assert result == ["p1"]

    def test_pending_all_filters(self):
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value.limit.return_value.all.return_value = ["p1"]
        db.query.return_value.filter.return_value = q
        service = ProposalService(db)
        asyncio.run(service.get_pending_proposals(agent_id="a", canvas_id="c", tenant_id="t", limit=10))
        assert q.filter.call_count == 3
        assert q.order_by.call_count == 1
        q.order_by.return_value.limit.assert_called_once_with(10)

    def test_history_includes_execution_result(self):
        p1 = _proposal(
            id="p1", approved_at=datetime(2026, 1, 1), approved_by="u",
            execution_result=None,
        )
        p2 = _proposal(id="p2", approved_at=None, approved_by=None)
        db = MagicMock()
        q = MagicMock()
        q.order_by.return_value.limit.return_value.all.return_value = [p1, p2]
        db.query.return_value.filter.return_value = q
        service = ProposalService(db)
        history = asyncio.run(service.get_proposal_history("agent-1"))
        assert len(history) == 2
        assert history[0]["execution_result"] is None
        assert history[1]["approved_at"] is None
        assert history[1]["execution_result"] is None


class TestExecuteProposedAction:
    @pytest.fixture
    def proposal(self):
        return _proposal(proposal_data={"action_type": "unknown"})

    def test_execution_disabled_flag(self, proposal):
        with patch("core.proposal_service.PROPOSAL_EXECUTION_ENABLED", False):
            db = _mock_db(proposal)
            service = ProposalService(db)
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert result["skipped"] is True

    def test_unknown_action_type(self, proposal):
        db = _mock_db(proposal)
        service = ProposalService(db)
        result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "Unknown action type" in result["error"]

    def test_no_proposal_data(self):
        proposal = _proposal(proposal_data=None)
        db = _mock_db(proposal)
        service = ProposalService(db)
        result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False

    def test_browser_action_success(self):
        proposal = _proposal(proposal_data={"action_type": "browser_automate", "url": "https://x.com", "actions": [{"type": "click", "selector": "#b"}]})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("tools.browser_tool.browser_create_session", new_callable=AsyncMock) as cs, \
             patch("tools.browser_tool.browser_navigate", new_callable=AsyncMock) as nav, \
             patch("tools.browser_tool.browser_click", new_callable=AsyncMock) as click, \
             patch("tools.browser_tool.browser_close_session", new_callable=AsyncMock):
            cs.return_value = {"session_id": "s-1"}
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is True
        assert result["action_type"] == "browser_automate"
        nav.assert_awaited_once()
        click.assert_awaited_once()

    def test_browser_action_requires_url_or_session(self):
        proposal = _proposal(proposal_data={"action_type": "browser_automate"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "url or session_id" not in result["error"]

    def test_browser_action_runtime_error_returns_failure(self):
        proposal = _proposal(proposal_data={"action_type": "browser_automate", "url": "https://x.com"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("tools.browser_tool.browser_create_session", new_callable=AsyncMock) as cs:
            cs.side_effect = RuntimeError("cdp down")
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "cdp down" not in result["error"]

    def test_canvas_action(self):
        proposal = _proposal(proposal_data={"action_type": "canvas_present", "canvas_type": "markdown", "content": {"text": "hi"}})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("tools.canvas_tool.present_to_canvas", new_callable=AsyncMock) as m:
            m.return_value = "canvas-9"
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is True
        assert result["canvas_id"] == "canvas-9"

    def test_canvas_action_exception_caught(self):
        proposal = _proposal(proposal_data={"action_type": "canvas_present"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("tools.canvas_tool.present_to_canvas", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("canvas down")
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "canvas down" not in result["error"]

    def test_integration_action(self):
        proposal = _proposal(proposal_data={"action_type": "integration_connect", "integration_type": "slack", "operation": "send_message", "parameters": {"text": "hi"}})
        db = _mock_db(proposal)
        service = ProposalService(db)
        inst = MagicMock()
        inst.execute = AsyncMock(return_value={"ok": True})
        with patch("integrations.universal_integration_service.UniversalIntegrationService", return_value=inst):
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is True
        assert result["integration_type"] == "slack"

    def test_integration_action_failure(self):
        proposal = _proposal(proposal_data={"action_type": "integration_connect", "integration_type": "slack"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        inst = MagicMock()
        inst.execute = AsyncMock(return_value={"ok": False})
        with patch("integrations.universal_integration_service.UniversalIntegrationService", return_value=inst):
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False

    def test_integration_action_exception_returns_failure(self):
        proposal = _proposal(proposal_data={"action_type": "integration_connect", "integration_type": "slack"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        inst = MagicMock()
        inst.execute = AsyncMock(side_effect=RuntimeError("svc down"))
        with patch("integrations.universal_integration_service.UniversalIntegrationService", return_value=inst):
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "svc down" not in result["error"]

    def test_workflow_action(self):
        proposal = _proposal(proposal_data={"action_type": "workflow_trigger", "workflow_id": "wf-1", "parameters": {"a": 1}})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("core.workflow_endpoints.load_workflows", return_value=[{"id": "wf-1", "steps": []}]), \
             patch("core.workflow_engine.WorkflowEngine") as we_cls:
            engine = MagicMock()
            engine.start_workflow = AsyncMock(return_value="exec-1")
            we_cls.return_value = engine
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is True
        assert result["workflow_id"] == "wf-1"

    def test_workflow_action_missing_workflow(self):
        proposal = _proposal(proposal_data={"action_type": "workflow_trigger", "workflow_id": "wf-1"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("core.workflow_endpoints.load_workflows", return_value=[]):
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "not found" not in result["error"]

    def test_workflow_action_exception_returns_failure(self):
        proposal = _proposal(proposal_data={"action_type": "workflow_trigger", "workflow_id": "wf-1"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("core.workflow_endpoints.load_workflows", return_value=[{"id": "wf-1", "steps": []}]), \
             patch("core.workflow_engine.WorkflowEngine") as we_cls:
            engine = MagicMock()
            engine.start_workflow = AsyncMock(side_effect=RuntimeError("wf down"))
            we_cls.return_value = engine
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "wf down" not in result["error"]

    def test_device_action(self):
        proposal = _proposal(proposal_data={"action_type": "device_command", "device_id": "dev-1", "command_type": "camera"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("tools.device_tool.execute_device_command", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is True

    def test_device_action_exception_caught(self):
        proposal = _proposal(proposal_data={"action_type": "device_command", "device_id": "dev-1"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch("tools.device_tool.execute_device_command", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("device down")
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "device down" not in result["error"]

    def test_agent_action(self):
        proposal = _proposal(proposal_data={"action_type": "agent_execute", "target_agent_id": "agent-2", "prompt": "do it"})
        db = _mock_db(proposal)
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="agent-2"
        )
        service = ProposalService(db)
        agent = MagicMock()
        agent.execute = AsyncMock(return_value={"success": True})
        with patch("core.generic_agent.GenericAgent", return_value=agent):
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is True
        assert result["target_agent_id"] == "agent-2"

    def test_agent_action_exception_returns_failure(self):
        proposal = _proposal(proposal_data={"action_type": "agent_execute", "target_agent_id": "agent-2"})
        db = _mock_db(proposal)
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
            id="agent-2"
        )
        service = ProposalService(db)
        agent = MagicMock()
        agent.execute = AsyncMock(side_effect=RuntimeError("agent down"))
        with patch("core.generic_agent.GenericAgent", return_value=agent):
            result = asyncio.run(service._execute_proposed_action(proposal))
        assert result["success"] is False
        assert "agent down" not in result["error"]

    def test_execute_with_prepared_action_swaps_and_restores(self):
        proposal = _proposal(proposal_data={"action_type": "canvas_present"})
        db = _mock_db(proposal)
        service = ProposalService(db)
        captured = []
        async def capture(prop):
            captured.append(dict(prop.proposal_data))
            return {"success": True}
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.side_effect = capture
            result = asyncio.run(service._execute_proposed_action_with(
                proposal, {"action_type": "workflow_trigger", "workflow_id": "wf-x"},
            ))
        assert result["success"] is True
        assert captured[0]["workflow_id"] == "wf-x"
        assert proposal.proposal_data == {"action_type": "canvas_present"}

    def test_execute_with_none_action(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch.object(service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            result = asyncio.run(service._execute_proposed_action_with(proposal, None))
        assert result["success"] is True
        m.assert_awaited_once()


class TestProposalEpisodeHelpers:
    def test_format_proposal_content(self):
        proposal = _proposal(reasoning="because")
        service = ProposalService(MagicMock())
        content = service._format_proposal_content(proposal, "approved")
        assert "Proposal Title: Test Proposal" in content
        assert "Agent: Test Agent" in content
        assert "Reasoning:" in content
        assert "canvas_present" in content

    def test_format_proposal_outcome_approved_with_mods(self):
        proposal = _proposal()
        service = ProposalService(MagicMock())
        out = service._format_proposal_outcome(
            proposal, "approved",
            modifications={"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6},
            execution_result={"success": True},
        )
        assert "SUCCESS" in out
        assert "Modifications Applied: 6" in out
        assert len([l for l in out.splitlines() if l.startswith("  - ")]) == 5

    def test_format_proposal_outcome_approved_no_mods(self):
        proposal = _proposal()
        service = ProposalService(MagicMock())
        out = service._format_proposal_outcome(proposal, "approved", modifications=[], execution_result={"success": False})
        assert "FAILED" in out
        assert "Modifications" not in out

    def test_format_proposal_outcome_approved_mods_as_list(self):
        proposal = _proposal()
        service = ProposalService(MagicMock())
        out = service._format_proposal_outcome(proposal, "approved", modifications=["changed x"])
        assert "changed x" in out

    def test_format_proposal_outcome_rejected(self):
        proposal = _proposal()
        service = ProposalService(MagicMock())
        out = service._format_proposal_outcome(proposal, "rejected", rejection_reason="no")
        assert "Rejection Reason: no" in out

    def test_format_proposal_outcome_default_reason(self):
        proposal = _proposal()
        service = ProposalService(MagicMock())
        out = service._format_proposal_outcome(proposal, "rejected")
        assert "No reason provided" in out

    def test_extract_topics(self):
        proposal = _proposal(
            title="Financial Report Analysis",
            reasoning="Analyzing quarterly numbers",
            proposal_data={"action_type": "canvas_present"},
        )
        service = ProposalService(MagicMock())
        topics = service._extract_proposal_topics(proposal)
        assert topics[0] == ProposalType.ACTION.value
        assert "canvas_present" in topics
        assert len(topics) <= 5

    def test_extract_topics_no_title_reasoning(self):
        proposal = _proposal(title=None, reasoning=None, proposal_data={})
        service = ProposalService(MagicMock())
        topics = service._extract_proposal_topics(proposal)
        assert topics == [ProposalType.ACTION.value]

    def test_extract_entities(self):
        proposal = _proposal(approved_by="reviewer-1", proposal_data={"action_type": "canvas_present", "canvas_type": "chart"})
        service = ProposalService(MagicMock())
        entities = service._extract_proposal_entities(proposal)
        assert "proposal:prop-1" in entities
        assert "agent:agent-1" in entities
        assert "reviewer:reviewer-1" in entities
        assert "chart" in entities

    def test_extract_entities_no_approved_by(self):
        proposal = _proposal(approved_by=None)
        service = ProposalService(MagicMock())
        entities = service._extract_proposal_entities(proposal)
        assert not any("reviewer:" in e for e in entities)

    def test_importance_score(self):
        proposal = _proposal()
        service = ProposalService(MagicMock())
        assert service._calculate_proposal_importance("rejected", proposal) == 0.8
        assert service._calculate_proposal_importance("approved", proposal) == 0.6
        proposal.modifications = {"a": 1}
        assert service._calculate_proposal_importance("approved", proposal) == 0.7

    def test_create_episode_exception_swallowed(self):
        proposal = _proposal()
        db = MagicMock()
        service = ProposalService(db)
        with patch("core.episode_segmentation_service.EpisodeSegmentationService",
                   side_effect=RuntimeError("seg down")):
            asyncio.run(service._create_proposal_episode(proposal, "approved"))

    def test_create_episode_rejected_agent_status_enum(self):
        proposal = _proposal()
        db = MagicMock()
        agent = MagicMock()
        agent.status = AgentStatus.INTERN  # enum, not string
        db.query.return_value.filter.return_value.first.return_value = agent
        service = ProposalService(db)
        asyncio.run(service._create_proposal_episode(proposal, "approved"))
        added = [c.args[0] for c in db.add.call_args_list]
        episode = next(c for c in added if isinstance(c, Episode))
        assert episode.maturity_at_time == AgentStatus.INTERN.value


class TestAutonomousSupervisor:
    @pytest.fixture
    def proposal(self):
        return _proposal()

    def test_human_supervisor_available(self, proposal):
        db = MagicMock()
        service = ProposalService(db)
        with patch("core.user_activity_service.UserActivityService") as uas_cls, \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService") as as_cls:
            uas_cls.return_value.get_available_supervisors = AsyncMock(
                return_value=[{"user_id": "u-1", "name": "Bob"}]
            )
            result = asyncio.run(service.review_with_autonomous_supervisor(proposal))
        assert result["supervisor_type"] == "human"
        assert result["supervisor_id"] == "u-1"
        as_cls.assert_not_called()

    def test_no_human_no_agent_returns_none(self, proposal):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        service = ProposalService(db)
        with patch("core.user_activity_service.UserActivityService") as uas_cls:
            uas_cls.return_value.get_available_supervisors = AsyncMock(return_value=[])
            result = asyncio.run(service.review_with_autonomous_supervisor(proposal))
        assert result is None

    def test_no_supervisor_found(self, proposal):
        db = MagicMock()
        agent = MagicMock()
        agent.id = "agent-1"
        db.query.return_value.filter.return_value.first.return_value = agent
        service = ProposalService(db)
        with patch("core.user_activity_service.UserActivityService") as uas_cls, \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService") as as_cls:
            uas_cls.return_value.get_available_supervisors = AsyncMock(return_value=[])
            as_cls.return_value.find_autonomous_supervisor = AsyncMock(return_value=None)
            result = asyncio.run(service.review_with_autonomous_supervisor(proposal))
        assert result is None

    def test_autonomous_review(self, proposal):
        db = MagicMock()
        agent = MagicMock()
        agent.id = "agent-1"
        db.query.return_value.filter.return_value.first.return_value = agent
        supervisor = SimpleNamespace(id="sup-1", name="Sup One")
        review = SimpleNamespace(
            approved=True, confidence_score=0.9, risk_level="low",
            reasoning="ok", suggested_modifications=["x"],
        )
        service = ProposalService(db)
        with patch("core.user_activity_service.UserActivityService") as uas_cls, \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService") as as_cls:
            uas_cls.return_value.get_available_supervisors = AsyncMock(return_value=[])
            as_cls.return_value.find_autonomous_supervisor = AsyncMock(return_value=supervisor)
            as_cls.return_value.review_proposal = AsyncMock(return_value=review)
            result = asyncio.run(service.review_with_autonomous_supervisor(proposal))
        assert result["supervisor_type"] == "autonomous"
        assert result["review"]["approved"] is True
        assert result["review"]["suggested_modifications"] == ["x"]

    def test_autonomous_approve_or_reject_not_found(self):
        db = _mock_db(None)
        service = ProposalService(db)
        with pytest.raises(ValueError):
            asyncio.run(service.autonomous_approve_or_reject("prop-x"))

    def test_autonomous_no_supervisor(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch.object(service, "review_with_autonomous_supervisor", new_callable=AsyncMock) as m:
            m.return_value = None
            result = asyncio.run(service.autonomous_approve_or_reject("prop-1"))
        assert result["success"] is False
        assert "No supervisor available" in result["message"]

    def test_autonomous_human_waiting(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        service = ProposalService(db)
        with patch.object(service, "review_with_autonomous_supervisor", new_callable=AsyncMock) as m:
            m.return_value = {"supervisor_type": "human", "supervisor_id": "u-1"}
            result = asyncio.run(service.autonomous_approve_or_reject("prop-1"))
        assert result["success"] is False
        assert "awaiting manual approval" in result["message"]

    def test_autonomous_approve_success(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        service = ProposalService(db)
        review = {
            "approved": True, "confidence_score": 0.9, "risk_level": "low",
            "reasoning": "ok", "suggested_modifications": [],
        }
        with patch.object(service, "review_with_autonomous_supervisor", new_callable=AsyncMock) as m, \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService") as as_cls:
            m.return_value = {
                "supervisor_type": "autonomous", "supervisor_id": "sup-1",
                "review": review,
            }
            as_cls.return_value.approve_proposal = AsyncMock(return_value=True)
            result = asyncio.run(service.autonomous_approve_or_reject("prop-1"))
        assert result["success"] is True
        as_cls.return_value.approve_proposal.assert_awaited_once()

    def test_autonomous_approve_failure(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        service = ProposalService(db)
        review = {
            "approved": True, "confidence_score": 0.9, "risk_level": "low",
            "reasoning": "ok",
        }
        with patch.object(service, "review_with_autonomous_supervisor", new_callable=AsyncMock) as m, \
             patch("core.autonomous_supervisor_service.AutonomousSupervisorService") as as_cls:
            m.return_value = {
                "supervisor_type": "autonomous", "supervisor_id": "sup-1", "review": review,
            }
            as_cls.return_value.approve_proposal = AsyncMock(return_value=False)
            result = asyncio.run(service.autonomous_approve_or_reject("prop-1"))
        assert result["success"] is False
        assert "Failed to process" in result["message"]

    def test_autonomous_reject(self):
        proposal = _proposal()
        db = _mock_db(proposal)
        service = ProposalService(db)
        review = {
            "approved": False, "confidence_score": 0.9, "risk_level": "high",
            "reasoning": "risky", "suggested_modifications": [],
        }
        with patch.object(service, "review_with_autonomous_supervisor", new_callable=AsyncMock) as m:
            m.return_value = {
                "supervisor_type": "autonomous", "supervisor_id": "sup-1", "review": review,
            }
            result = asyncio.run(service.autonomous_approve_or_reject("prop-1"))
        assert result["success"] is False
        assert "rejected by autonomous supervisor" in result["message"]
        assert proposal.status == ProposalStatus.REJECTED.value
        assert proposal.execution_result["autonomous_rejection"] is True

    # ---- PROP-1 (RED): autonomous reject must not flip a non-pending proposal ----
    def test_autonomous_reject_executed_proposal_raises(self):
        proposal = _proposal(status=ProposalStatus.EXECUTED.value)
        db = _mock_db(proposal)
        service = ProposalService(db)
        review = {
            "approved": False, "confidence_score": 0.9, "risk_level": "high",
            "reasoning": "risky",
        }
        with patch.object(service, "review_with_autonomous_supervisor", new_callable=AsyncMock) as m:
            m.return_value = {
                "supervisor_type": "autonomous", "supervisor_id": "sup-1", "review": review,
            }
            with pytest.raises(ValueError):
                asyncio.run(service.autonomous_approve_or_reject("prop-1"))
        assert proposal.status == ProposalStatus.EXECUTED.value


# ============================================================================
# 4. Integration (real in-memory SQLite DB)
# ============================================================================


@pytest.fixture
def db(worker_database):
    session = worker_database()
    session.query(EpisodeSegment).delete()
    session.query(Episode).delete()
    session.query(AgentProposal).delete()
    session.query(AgentRegistry).delete()
    session.commit()
    yield session
    session.close()


@pytest.fixture
def intern_agent(db):
    agent = AgentRegistry(
        id="covpush-intern",
        name="CovPush Intern",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture
def proposal_service(db):
    with patch("core.proposal_service.AgentLearningEnhanced") as learning:
        learning.return_value.record_user_correction = AsyncMock()
        learning.return_value.record_rejection = AsyncMock()
        yield ProposalService(db)


class TestIntegrationProposalFlow:
    @pytest.mark.asyncio
    async def test_full_approve_flow(self, db, intern_agent, proposal_service):
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present", "canvas_type": "chart"},
            reasoning="integration approve",
        )
        with patch.object(proposal_service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            result = await proposal_service.approve_proposal(proposal.id, user_id="approver-1")
        assert result["success"] is True
        db.refresh(proposal)
        assert proposal.status == ProposalStatus.EXECUTED.value
        episode = db.query(Episode).filter(Episode.proposal_id == proposal.id).first()
        assert episode is not None
        assert episode.supervision_decision == "approved"
        assert episode.human_intervention_count == 1
        segments = db.query(EpisodeSegment).filter(EpisodeSegment.episode_id == episode.id).all()
        assert len(segments) >= 2

    @pytest.mark.asyncio
    async def test_full_reject_flow(self, db, intern_agent, proposal_service):
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present"},
            reasoning="integration reject",
        )
        await proposal_service.reject_proposal(proposal.id, user_id="reviewer-1", reason="not now")
        db.refresh(proposal)
        assert proposal.status == ProposalStatus.REJECTED.value
        episode = db.query(Episode).filter(Episode.proposal_id == proposal.id).first()
        assert episode is not None
        assert episode.supervision_decision == "rejected"
        assert episode.supervision_reasoning == "not now"

    @pytest.mark.asyncio
    async def test_approve_then_approve_raises(self, db, intern_agent, proposal_service):
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present"},
            reasoning="double approve",
        )
        with patch.object(proposal_service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            await proposal_service.approve_proposal(proposal.id, user_id="u1")
        with pytest.raises(ValueError):
            with patch.object(proposal_service, "_execute_proposed_action", new_callable=AsyncMock) as m2:
                await proposal_service.approve_proposal(proposal.id, user_id="u2")

    @pytest.mark.asyncio
    async def test_reject_then_approve_raises(self, db, intern_agent, proposal_service):
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present"},
            reasoning="reject then approve",
        )
        await proposal_service.reject_proposal(proposal.id, user_id="u1", reason="no")
        with pytest.raises(ValueError):
            with patch.object(proposal_service, "_execute_proposed_action", new_callable=AsyncMock) as m:
                await proposal_service.approve_proposal(proposal.id, user_id="u2")

    @pytest.mark.asyncio
    async def test_approve_with_modifications_integration(self, db, intern_agent, proposal_service):
        proposal = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id,
            trigger_context={},
            proposed_action={"action_type": "canvas_present", "canvas_type": "chart"},
            reasoning="mods",
        )
        with patch.object(proposal_service, "_execute_proposed_action", new_callable=AsyncMock) as m:
            m.return_value = {"success": True}
            await proposal_service.approve_proposal(
                proposal.id, user_id="u1", modifications={"canvas_type": "table"},
            )
        db.refresh(proposal)
        assert proposal.proposed_action["canvas_type"] == "table"
        episode = db.query(Episode).filter(Episode.proposal_id == proposal.id).first()
        assert episode.metadata_json["human_edits"] == [{"canvas_type": "table"}]

    @pytest.mark.asyncio
    async def test_get_pending_proposals_integration(self, db, intern_agent, proposal_service):
        p1 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id, trigger_context={},
            proposed_action={"action_type": "canvas_present"}, reasoning="pending 1",
        )
        p2 = await proposal_service.create_action_proposal(
            intern_agent_id=intern_agent.id, trigger_context={},
            proposed_action={"action_type": "canvas_present"}, reasoning="pending 2",
        )
        pending = await proposal_service.get_pending_proposals(agent_id=intern_agent.id)
        ids = {p.id for p in pending}
        assert p1.id in ids and p2.id in ids
        history = await proposal_service.get_proposal_history(intern_agent.id)
        assert len(history) == 2
