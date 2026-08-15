"""Coverage wave 86a — identity & trust package.

Closes the remaining gaps in the 7 assigned modules (baselines measured with
``coverage run`` — the pytest-cov plugin under-measures in this repo due to
stale data-file merging):

  1. core/identity/did_manager.py            92% → 100% (full lifecycle port:
                                                generate/resolve/verify/rotate/
                                                deactivate/persist/load/stats/
                                                federation + import fallback)
  2. core/identity/verifiable_credentials.py 98% → 100% (import-fallback via
                                                sys.modules blocking + reload,
                                                _sign_with_key no-crypto,
                                                presentation with invalid VC,
                                                full lifecycle port)
  3. core/selector_confidence_service.py     69% → 100% (property matrix,
                                                score bands, penalties, empty
                                                candidates, coercion,
                                                attach_tiebreak states)
  4. core/specialist_matcher.py              91% → 100% (import/query failure
                                                fallbacks, empty required-key
                                                iterator, real-metric ranking)
  5. core/intent_classifier.py               49% → 100% (LLM path, JSON
                                                parsing, heuristic fallback,
                                                singleton)
  6. core/agent_context_resolver.py          91% → 100% (resolution chain,
                                                legacy heal, system-default
                                                creation, session agent)
  7. core/autonomous_supervisor_service.py   95% → ~96% (monitor not-found +
                                                error, approve wrong-status,
                                                find/review/monitor/approve/
                                                helpers; line 141 provably
                                                unreachable — see report)

Style: mocked deps only; zero LLM spend / no network / no real DB (in-memory
SQLite for persistence paths, patched get_db_session); async entry points
driven through ``asyncio.run``; import-failure branches exercised via
``builtins.__import__``/``sys.modules`` blocking + ``importlib.reload``.
"""
from __future__ import annotations

import asyncio
import builtins
import importlib
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core import selector_confidence_service as scs
from core import specialist_matcher as sm_module
from core.autonomous_supervisor_service import (
    AutonomousSupervisorService,
    ProposalReview,
    SupervisionEvent,
)
from core.identity import did_manager as dm_module
from core.identity import verifiable_credentials as vc_module
from core.selector_confidence_service import (
    AMBIGUOUS,
    EXTERNAL_REFUTED,
    EXTERNAL_VERIFIED,
    HIGH,
    MatchConfidence,
    NEEDS_EXTERNAL_VALIDATION,
    PARTIAL,
    SelectorCandidate,
    attach_tiebreak,
    coerce_match_level_for_storage,
    level_from_score,
    score_candidates,
)


def _run(coro):
    return asyncio.run(coro)


# ===========================================================================
# Shared helpers
# ===========================================================================


@pytest.fixture
def db_session():
    """In-memory SQLite session with the full schema (mirrors the repo
    conftest's StaticPool pattern)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from core.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


class _CommitCM:
    """Mirror core.database.get_db_session: commit on context exit."""

    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, *exc):
        self._session.commit()


# ===========================================================================
# 1. core/selector_confidence_service
# ===========================================================================


def _cand(**kw) -> SelectorCandidate:
    defaults = dict(
        selector="#id",
        match_count=1,
        is_text_only=False,
        appeared_after_ms=0,
        tag_hint="button",
    )
    defaults.update(kw)
    return SelectorCandidate(**defaults)


class TestSelectorConfidencePropertyMatrix:
    """Tri-state + external-tier property matrix (lines 144, 150, 159,
    164-167)."""

    def test_is_high_true(self):
        assert MatchConfidence(level=HIGH, score=0.9, rationale="r").is_high is True

    def test_is_high_false(self):
        assert MatchConfidence(level=PARTIAL, score=0.6, rationale="r").is_high is False

    def test_requires_review_partial(self):
        assert MatchConfidence(level=PARTIAL, score=0.6, rationale="r").requires_review is True

    def test_requires_review_ambiguous(self):
        assert MatchConfidence(level=AMBIGUOUS, score=0.3, rationale="r").requires_review is True

    def test_requires_review_bridge_state(self):
        assert (
            MatchConfidence(level=NEEDS_EXTERNAL_VALIDATION, score=0.6, rationale="r")
            .requires_review
            is True
        )

    def test_requires_review_high_false(self):
        assert MatchConfidence(level=HIGH, score=0.9, rationale="r").requires_review is False

    def test_is_credible_external_verified(self):
        assert (
            MatchConfidence(level=EXTERNAL_VERIFIED, score=0.9, rationale="r").is_credible
            is True
        )

    def test_is_credible_internal_high_false(self):
        assert MatchConfidence(level=HIGH, score=0.95, rationale="r").is_credible is False

    def test_needs_external_validation_high(self):
        assert (
            MatchConfidence(level=HIGH, score=0.9, rationale="r").needs_external_validation
            is True
        )

    def test_needs_external_validation_partial(self):
        assert (
            MatchConfidence(level=PARTIAL, score=0.6, rationale="r")
            .needs_external_validation
            is True
        )

    def test_needs_external_validation_external_provenance_false(self):
        assert (
            MatchConfidence(level=HIGH, score=0.9, rationale="r", provenance="external")
            .needs_external_validation
            is False
        )

    def test_to_dict_serializes(self):
        cand = _cand(selector="#btn", attributes={"data-testid": "save"})
        conf = MatchConfidence(
            level=PARTIAL,
            score=0.6,
            rationale="two candidates",
            candidates=[cand],
            chosen_index=0,
        )
        d = conf.to_dict()
        assert d["level"] == PARTIAL
        assert d["score"] == 0.6
        assert d["chosen_index"] == 0
        assert d["provenance"] == "internal"
        assert d["external_score"] is None
        assert d["candidates"][0]["selector"] == "#btn"
        assert d["candidates"][0]["attributes"] == {"data-testid": "save"}


class TestSelectorConfidenceScoringBands:
    """level_from_score band boundaries (lines 190-192) + empty candidates
    (lines 214-220) + zero-match non-empty candidates (line 228)."""

    def test_level_partial_band(self):
        assert level_from_score(0.70) == PARTIAL
        assert level_from_score(0.50) == PARTIAL

    def test_level_ambiguous_band(self):
        assert level_from_score(0.49) == AMBIGUOUS
        assert level_from_score(0.0) == AMBIGUOUS

    def test_level_high_band(self):
        assert level_from_score(0.85) == HIGH

    def test_score_empty_candidates(self):
        result = score_candidates([])
        assert result.level == AMBIGUOUS
        assert result.score == 0.0
        assert result.rationale == "0 matches within timeout"
        assert result.candidates == []
        assert result.chosen_index == -1

    def test_score_zero_match_candidate_never_confident(self):
        result = score_candidates([_cand(match_count=0)])
        assert result.level == AMBIGUOUS
        assert result.score == 0.0
        assert result.rationale == "0 matches within timeout"
        assert len(result.candidates) == 1
        assert result.chosen_index == -1


class TestSelectorConfidencePenalties:
    """Multiplicity / text-only / late-appearance penalties (lines 239-258)
    and the 0.0 floor."""

    def test_multiplicity_penalty(self):
        result = score_candidates([_cand(match_count=3)])
        assert result.score == pytest.approx(0.40)
        assert result.level == AMBIGUOUS
        assert "3 matches (-0.60)" in result.rationale

    def test_text_only_penalty(self):
        result = score_candidates([_cand(is_text_only=True)])
        assert result.score == pytest.approx(0.85)
        assert result.level == HIGH
        assert "text-only selector (-0.15)" in result.rationale

    def test_late_appearance_penalty(self):
        result = score_candidates([_cand(appeared_after_ms=2000)])
        assert result.score == pytest.approx(0.90)
        assert result.level == HIGH
        assert "appeared after 2000ms (-0.10)" in result.rationale

    def test_combined_penalties_floor_at_zero(self):
        result = score_candidates(
            [_cand(match_count=5, is_text_only=True, appeared_after_ms=5000)]
        )
        assert result.score == 0.0
        assert result.level == AMBIGUOUS
        assert result.chosen_index == 0

    def test_single_match_no_penalty_rationale(self):
        result = score_candidates([_cand(match_count=1)])
        assert "single match" in result.rationale


class TestSelectorConfidenceStorageCoercion:
    """coerce_match_level_for_storage passthrough (lines 287-289)."""

    def test_valid_levels_pass_through(self):
        for level in (
            HIGH,
            PARTIAL,
            AMBIGUOUS,
            EXTERNAL_VERIFIED,
            EXTERNAL_REFUTED,
            NEEDS_EXTERNAL_VALIDATION,
        ):
            assert coerce_match_level_for_storage(level) == level

    def test_invalid_level_defaults_to_ambiguous(self):
        assert coerce_match_level_for_storage("bogus") == AMBIGUOUS
        assert coerce_match_level_for_storage(None) == AMBIGUOUS


class TestSelectorConfidenceAttachTiebreak:
    """attach_tiebreak state machine (lines 318-344)."""

    def _partial(self) -> MatchConfidence:
        return MatchConfidence(
            level=PARTIAL,
            score=0.6,
            rationale="two candidates",
            candidates=[_cand(match_count=2), _cand(selector="#alt")],
        )

    def test_non_partial_returns_unchanged(self):
        conf = MatchConfidence(level=HIGH, score=0.9, rationale="r")
        result = _run(attach_tiebreak(conf, {}, Mock()))
        assert result is conf

    def test_no_llm_service_returns_unchanged(self):
        conf = self._partial()
        result = _run(attach_tiebreak(conf, {}, None))
        assert result is conf

    def test_llm_exception_returns_unchanged(self):
        conf = self._partial()
        with patch(
            "core.llm.match_confidence_tiebreaker.break_tie",
            AsyncMock(side_effect=RuntimeError("llm down")),
        ):
            result = _run(attach_tiebreak(conf, {}, Mock()))
        assert result is conf

    def test_llm_unused_returns_unchanged(self):
        conf = self._partial()
        with patch(
            "core.llm.match_confidence_tiebreaker.break_tie",
            AsyncMock(return_value=SimpleNamespace(used_llm=False, chosen_index=1, rationale="x")),
        ):
            result = _run(attach_tiebreak(conf, {}, Mock()))
        assert result is conf

    def test_llm_no_choice_returns_unchanged(self):
        conf = self._partial()
        with patch(
            "core.llm.match_confidence_tiebreaker.break_tie",
            AsyncMock(return_value=SimpleNamespace(used_llm=True, chosen_index=-1, rationale="x")),
        ):
            result = _run(attach_tiebreak(conf, {}, Mock()))
        assert result is conf

    def test_llm_pick_promotes_to_bridge_state(self):
        conf = self._partial()
        with patch(
            "core.llm.match_confidence_tiebreaker.break_tie",
            AsyncMock(
                return_value=SimpleNamespace(
                    used_llm=True, chosen_index=1, rationale="second candidate is the button"
                )
            ),
        ):
            result = _run(attach_tiebreak(conf, {"url": "https://x"}, Mock()))
        assert result.level == NEEDS_EXTERNAL_VALIDATION
        assert result.score == conf.score
        assert result.chosen_index == 1
        assert result.provenance == "internal"
        assert "LLM tiebreak (needs external validation)" in result.rationale
        assert result.requires_review is True


# ===========================================================================
# 2. core/specialist_matcher
# ===========================================================================


def _agent(
    db,
    *,
    name,
    category,
    capabilities,
    status="autonomous",
    confidence=0.5,
    days_ago=0,
    enabled=True,
):
    """Insert an AgentRegistry row and return it."""
    from core.models import AgentRegistry

    ag = AgentRegistry(
        id=f"agent-{name.lower().replace(' ', '-')}",
        name=name,
        category=category,
        capabilities=capabilities,
        status=status,
        confidence_score=confidence,
        self_healed_count=0,
        last_request_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
        module_path="core.generic_agent",
        class_name="GenericAgent",
        enabled=enabled,
    )
    db.add(ag)
    db.commit()
    return ag


def _block_core_models():
    """Context that makes `from core.models import ...` raise ImportError."""
    dummy = types.ModuleType("core.models")
    return patch.dict(sys.modules, {"core.models": dummy})


class _RaisingDb:
    """Fake session whose query() always raises."""

    def query(self, *args, **kwargs):
        raise RuntimeError("db down")


class TestSpecialistMatcherGaps:
    def test_capability_overlap_empty_required_iterator(self):
        # A truthy-but-empty iterator: `not required` is False, so the empty
        # required_lower guard (line 86) is the branch that fires.
        assert sm_module._capability_overlap(iter([]), ["budget"]) == 0.0

    def test_verified_episode_ratio_import_failure_returns_neutral(self):
        with _block_core_models():
            assert sm_module._verified_episode_ratio(Mock(), "agent-1") == 0.5

    def test_get_all_available_domains_import_failure(self):
        m = sm_module.SpecialistMatcher(Mock())
        with _block_core_models():
            assert m.get_all_available_domains() == list(sm_module.DOMAIN_ALIASES.keys())

    def test_find_specialists_import_failure(self):
        m = sm_module.SpecialistMatcher(Mock())
        with _block_core_models():
            assert m.find_specialists_for_domains(["finance", "sales"]) == {
                "finance": [],
                "sales": [],
            }

    def test_match_specialists_import_failure(self):
        m = sm_module.SpecialistMatcher(Mock())
        with _block_core_models():
            assert m.match_specialists(["budget"]) == []

    def test_match_specialists_query_failure_returns_empty(self):
        m = sm_module.SpecialistMatcher(_RaisingDb())
        assert m.match_specialists(["budget"]) == []

    def test_find_specialists_query_failure_returns_empty_per_domain(self):
        m = sm_module.SpecialistMatcher(_RaisingDb())
        assert m.find_specialists_for_domains(["finance"]) == {"finance": []}

    def test_verified_episode_ratio_query_failure_returns_neutral(self):
        # import succeeds, but the DB query raises → 0.5 neutral
        assert sm_module._verified_episode_ratio(_RaisingDb(), "agent-1") == 0.5

    def test_get_all_available_domains_query_failure(self):
        m = sm_module.SpecialistMatcher(_RaisingDb())
        assert m.get_all_available_domains() == list(sm_module.DOMAIN_ALIASES.keys())


class TestSpecialistMatcherScoring:
    """Real-metric ranking against seeded AgentRegistry rows (no DB mocks)."""

    def test_matcher_exposes_required_symbols(self):
        assert hasattr(sm_module.SpecialistMatcher, "find_specialists_for_domains")
        assert hasattr(sm_module.SpecialistMatcher, "get_all_available_domains")
        assert sm_module.SpecialistMatcher.DOMAIN_ALIASES is sm_module.DOMAIN_ALIASES

    def test_tier_floor_weight_lookup(self):
        assert sm_module._tier_floor_weight("autonomous") == 1.0
        assert sm_module._tier_floor_weight("supervised") == 0.8
        assert sm_module._tier_floor_weight("intern") == 0.55
        assert sm_module._tier_floor_weight(None) == 0.3
        assert sm_module._tier_floor_weight("mystery") == 0.3

    def test_recency_bonus_paths(self):
        assert sm_module._recency_bonus(None) == 0.0
        assert sm_module._recency_bonus(datetime.now(timezone.utc)) == 1.0
        assert sm_module._recency_bonus(
            datetime.now(timezone.utc) - timedelta(days=400)
        ) == 0.0
        middle = datetime.now(timezone.utc) - timedelta(days=15)
        assert sm_module._recency_bonus(middle) == pytest.approx(0.5)
        # ISO-string inputs
        assert sm_module._recency_bonus(
            (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        ) == 0.0
        assert sm_module._recency_bonus("not-a-date") == 0.0

    def test_capability_overlap_string_and_list(self):
        assert sm_module._capability_overlap(["BUDGET", "invoice"], ["budget"]) == pytest.approx(0.5)
        # string capabilities are treated as a single token — no partial match
        assert sm_module._capability_overlap(["budget"], "budget, accounting") == 0.0
        assert sm_module._capability_overlap([], ["anything"]) == 0.0

    def test_find_specialists_ranks_by_score(self, db_session):
        _agent(
            db_session,
            name="Full Finance",
            category="finance",
            capabilities=["budget", "invoice", "reconciliation"],
            confidence=0.95,
            days_ago=1,
        )
        _agent(
            db_session,
            name="Junior Finance",
            category="finance",
            capabilities=["budget"],
            status="intern",
            confidence=0.6,
            days_ago=40,
        )
        _agent(
            db_session,
            name="Wrong Domain",
            category="sales",
            capabilities=["budget"],
            confidence=0.9,
        )
        m = sm_module.SpecialistMatcher(db_session)
        result = m.find_specialists_for_domains(["finance"], limit_per_domain=2)
        ranked = result["finance"]
        assert [r["agent_id"] for r in ranked] == [
            "agent-full-finance",
            "agent-junior-finance",
        ]
        assert ranked[0]["capability_score"] > ranked[1]["capability_score"]
        assert ranked[0]["category"] == "finance"
        assert ranked[0]["tier"] == "autonomous"

    def test_get_all_available_domains_from_registry(self, db_session):
        _agent(db_session, name="A", category="finance", capabilities=[])
        _agent(db_session, name="B", category="sales", capabilities=[])
        _agent(db_session, name="C", category="", capabilities=[])
        m = sm_module.SpecialistMatcher(db_session)
        assert set(m.get_all_available_domains()) == {"finance", "sales"}

    def test_unknown_domain_returns_empty(self, db_session):
        _agent(db_session, name="A", category="finance", capabilities=["budget"])
        m = sm_module.SpecialistMatcher(db_session)
        assert m.find_specialists_for_domains(["quantum"]) == {"quantum": []}

    def test_match_specialists_backward_compat(self, db_session):
        _agent(
            db_session,
            name="Top",
            category="finance",
            capabilities=["budget", "invoice"],
            confidence=0.9,
        )
        _agent(
            db_session,
            name="Low",
            category="finance",
            capabilities=["budget"],
            status="student",
            confidence=0.3,
        )
        m = sm_module.SpecialistMatcher(db_session)
        result = m.match_specialists(["budget", "invoice"], count=1)
        assert result[0]["agent_id"] == "agent-top"
        assert result[0]["capability_score"] == pytest.approx(0.6 * 1.0 + 0.4 * 0.9)
        assert "name" in result[0]

    def test_verified_episode_ratio_real_path(self, db_session):
        from core.models import AgentEpisode, AgentExecution, AgentReasoningStep, Tenant

        tenant = Tenant(id="t1", name="T", subdomain="t1.example.com")
        db_session.add(tenant)
        ag = _agent(db_session, name="Epi", category="finance", capabilities=["budget"])
        exec_a = AgentExecution(id="exec-a", agent_id=ag.id, tenant_id="t1")
        exec_b = AgentExecution(id="exec-b", agent_id=ag.id, tenant_id="t1")
        db_session.add_all([exec_a, exec_b])
        db_session.commit()
        for ex, verified in (("exec-a", "verified"), ("exec-b", "unverified")):
            ep = AgentEpisode(
                agent_id=ag.id,
                tenant_id="t1",
                execution_id=ex,
                maturity_at_time="autonomous",
                outcome="success",
            )
            db_session.add(ep)
            db_session.commit()
            db_session.add(
                AgentReasoningStep(
                    execution_id=ex,
                    tenant_id="t1",
                    step_number=1,
                    step_type="observation",
                    verified=verified,
                )
            )
        db_session.commit()

        ratio = sm_module._verified_episode_ratio(db_session, ag.id)
        assert ratio == pytest.approx(0.5)

    def test_verified_episode_ratio_zero_episodes_neutral(self, db_session):
        ag = _agent(db_session, name="Newbie", category="finance", capabilities=[])
        assert sm_module._verified_episode_ratio(db_session, ag.id) == 0.5

    def test_analyze_domain_requirements(self):
        m = sm_module.SpecialistMatcher(Mock())
        out = m.analyze_domain_requirements(
            "Invoice reconciliation and tax accounting with budget forecasting"
        )
        assert out["required_domains"]
        assert out["specialist_count"] == min(len(out["required_domains"]), 5)
        assert out["complexity"] in ("low", "medium", "high")
        low = m.analyze_domain_requirements("hello world nothing here")
        assert low["required_domains"] == ["finance"]
        assert low["complexity"] == "low"


# ===========================================================================
# 3. core/autonomous_supervisor_service
# ===========================================================================


async def _collect_events(svc, execution_id, supervisor):
    return [e async for e in svc.monitor_execution(execution_id, supervisor)]


class TestAutonomousSupervisorGaps:
    """monitor not-found + error paths, approve wrong-status path."""

    def test_monitor_execution_not_found(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = AutonomousSupervisorService(db, poll_interval=0.01)
        supervisor = Mock(id="auto-1", name="Auto")

        events = _run(_collect_events(svc, "ex-ghost", supervisor))

        assert [e.event_type for e in events] == ["monitoring_started", "error"]
        assert "not found" in events[1].data["error"].lower()

    def test_monitor_execution_db_error_yields_monitoring_error(self):
        db = Mock()
        db.query.side_effect = RuntimeError("db down")
        svc = AutonomousSupervisorService(db, poll_interval=0.01)
        supervisor = Mock(id="auto-1", name="Auto")

        events = _run(_collect_events(svc, "ex-1", supervisor))

        assert [e.event_type for e in events] == ["monitoring_started", "monitoring_error"]
        assert "db down" in events[1].data["error"]

    def test_approve_proposal_wrong_status_returns_false(self):
        db = Mock()
        proposal = Mock(id="p-1", status="approved")
        db.query.return_value.filter.return_value.first.return_value = proposal
        svc = AutonomousSupervisorService(db)
        review = ProposalReview(
            approved=True,
            confidence_score=0.9,
            risk_level="safe",
            reasoning="ok",
        )
        assert _run(svc.approve_proposal("p-1", "auto-1", review)) is False
        db.commit.assert_not_called()


class TestAutonomousSupervisorFind:
    def _registry(self, **kw):
        from core.models import AgentRegistry, AgentStatus

        defaults = dict(
            id="auto-1",
            name="Auto",
            category="finance",
            confidence_score=0.95,
            status=AgentStatus.AUTONOMOUS.value,
        )
        defaults.update(kw)
        return AgentRegistry(**defaults)

    def _svc_with_supervisors(self, supervisors):
        db = Mock()
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = (
            supervisors
        )
        return AutonomousSupervisorService(db)

    def test_no_supervisors_returns_none(self):
        svc = self._svc_with_supervisors([])
        intern = self._registry(id="intern-1", category="finance")
        assert _run(svc.find_autonomous_supervisor(intern)) is None

    def test_fallback_to_highest_confidence(self):
        low = self._registry(id="auto-low", confidence_score=0.91)
        high = self._registry(id="auto-high", confidence_score=0.98)
        svc = self._svc_with_supervisors([low, high])
        intern = self._registry(id="intern-1", category="finance")
        assert _run(svc.find_autonomous_supervisor(intern)) is high

    def test_adversarial_picks_trait_mismatch(self):
        s1 = self._registry(id="auto-1", confidence_score=0.95)
        s1.diversity_profile = {"risk_profile": "aggressive"}
        s2 = self._registry(id="auto-2", confidence_score=0.99)
        s2.diversity_profile = {"risk_profile": "conservative"}
        svc = self._svc_with_supervisors([s1, s2])
        intern = self._registry(id="intern-1", category="finance")
        intern.diversity_profile = {"risk_profile": "conservative"}
        assert _run(svc.find_autonomous_supervisor(intern, adversarial=True)) is s1

    def test_adversarial_falls_back_when_no_mismatch(self):
        s1 = self._registry(id="auto-1", confidence_score=0.95)
        s1.diversity_profile = {"risk_profile": "aggressive"}
        svc = self._svc_with_supervisors([s1])
        intern = self._registry(id="intern-1", category="finance")
        intern.diversity_profile = {"risk_profile": "aggressive"}
        assert _run(svc.find_autonomous_supervisor(intern, adversarial=True)) is s1

    def test_explicit_category_filter_used(self):
        db = Mock()
        query = db.query.return_value
        query.filter.return_value = query  # chain filter() twice
        query.all.return_value = [self._registry()]
        svc = AutonomousSupervisorService(db)
        intern = self._registry(id="intern-1", category="finance")
        result = _run(svc.find_autonomous_supervisor(intern, category="finance"))
        assert result is not None


class TestAutonomousSupervisorReview:
    """review_proposal — heuristic LLM analysis mocked at the WorldModelService
    boundary only (zero LLM spend; the analysis itself is deterministic)."""

    @staticmethod
    def _make_proposal():
        return Mock(
            id="p-1",
            agent_id="agent-1",
            proposed_action={"action_type": "canvas_present"},
            reasoning="User asked for a chart",
        )

    def _review(self, action_type: str, supervisor_confidence: float):
        db = Mock()
        proposal = Mock(
            id="p-1",
            agent_id="agent-1",
            proposed_action={"action_type": action_type},
            reasoning="some reasoning",
        )
        supervisor = self._supervisor(supervisor_confidence)
        with patch(
            "core.agent_world_model.WorldModelService",
            Mock(
                return_value=Mock(
                    get_experience_statistics=AsyncMock(
                        return_value={"success_rate": 0.8}
                    )
                )
            ),
        ):
            svc = AutonomousSupervisorService(db)
            return _run(svc.review_proposal(proposal, supervisor))

    @staticmethod
    def _supervisor(confidence: float):
        from core.models import AgentRegistry

        return AgentRegistry(
            id="auto-1",
            name="Auto",
            category="finance",
            confidence_score=confidence,
            status="autonomous",
        )

    def test_safe_action_approved(self):
        review = self._review("canvas_present", 0.90)
        assert review.approved is True
        assert review.risk_level == "safe"
        assert review.confidence_score == pytest.approx(1.0)

    def test_workflow_trigger_safe_approved(self):
        review = self._review("workflow_trigger", 0.90)
        assert review.approved is True

    def test_medium_action_approved(self):
        review = self._review("agent_execute", 0.92)
        assert review.approved is True
        assert review.risk_level == "medium"

    def test_medium_action_rejected_on_low_supervisor(self):
        review = self._review("browser_automate", 0.85)
        assert review.approved is False

    def test_high_risk_device_command_rejected(self):
        review = self._review("device_command", 0.90)
        assert review.approved is False
        assert review.risk_level == "high"

    def test_unknown_action_defaults_medium(self):
        review = self._review("mystery_action", 0.98)
        assert review.risk_level == "medium"
        assert review.approved is True  # conf 0.98 >= 0.85, sup 0.98 >= 0.90
        assert "mystery_action" in review.reasoning


class TestAutonomousSupervisorMonitorPaths:
    def test_monitor_completed_execution(self):
        db = Mock()
        exec_mock = Mock(
            status="completed", duration_seconds=5, result_summary="all good"
        )
        db.query.return_value.filter.return_value.first.return_value = exec_mock
        svc = AutonomousSupervisorService(db, poll_interval=0.01)
        supervisor = Mock(id="auto-1", name="Auto")

        events = _run(_collect_events(svc, "ex-1", supervisor))

        assert [e.event_type for e in events] == ["monitoring_started", "execution_completed"]
        assert events[1].data["result_summary"] == "all good"

    def test_monitor_failed_execution(self):
        db = Mock()
        exec_mock = Mock(status="failed", error_message="boom")
        db.query.return_value.filter.return_value.first.return_value = exec_mock
        svc = AutonomousSupervisorService(db, poll_interval=0.01)
        supervisor = Mock(id="auto-1", name="Auto")

        events = _run(_collect_events(svc, "ex-1", supervisor))

        assert [e.event_type for e in events] == ["monitoring_started", "execution_failed"]
        assert events[1].data["error_message"] == "boom"
        assert events[1].data["error_analysis"]["error_type"] == "execution_error"

    def test_monitor_running_then_completed(self):
        db = Mock()
        running = Mock(status="running")
        completed = Mock(status="completed", duration_seconds=9, result_summary="done")
        db.query.return_value.filter.return_value.first.side_effect = [running, completed]
        svc = AutonomousSupervisorService(db, poll_interval=0.01)
        supervisor = Mock(id="auto-1", name="Auto")

        events = _run(_collect_events(svc, "ex-1", supervisor))

        assert [e.event_type for e in events] == ["monitoring_started", "execution_completed"]

    def test_monitor_running_with_concerns(self):
        db = Mock()
        running = Mock(status="running")
        completed = Mock(status="completed", duration_seconds=9, result_summary="done")
        db.query.return_value.filter.return_value.first.side_effect = [running, completed]
        svc = AutonomousSupervisorService(db, poll_interval=0.01)
        supervisor = Mock(id="auto-1", name="Auto")

        async def _fake_concerns(execution, supervisor):
            return {"has_concerns": True, "concerns": ["churning"], "severity": "high"}

        svc._check_execution_concerns = _fake_concerns

        events = _run(_collect_events(svc, "ex-1", supervisor))

        assert [e.event_type for e in events] == [
            "monitoring_started",
            "concern_detected",
            "execution_completed",
        ]
        assert events[1].data["concerns"] == ["churning"]
        assert events[1].data["severity"] == "high"


class TestAutonomousSupervisorApprove:
    def test_approve_proposal_happy_path(self):
        db = Mock()
        proposal = Mock(id="p-1", status="pending_approval")
        db.query.return_value.filter.return_value.first.return_value = proposal
        svc = AutonomousSupervisorService(db)
        review = ProposalReview(
            approved=True,
            confidence_score=0.92,
            risk_level="medium",
            reasoning="looks fine",
            suggested_modifications=["add logging"],
        )
        assert _run(svc.approve_proposal("p-1", "auto-1", review)) is True
        assert proposal.status == "executed"
        assert proposal.approved_by == "auto-1"
        assert proposal.supervision_metadata["autonomous_approval"] is True
        assert proposal.supervision_metadata["review"]["risk_level"] == "medium"
        db.commit.assert_called_once()

    def test_approve_proposal_missing_returns_false(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = AutonomousSupervisorService(db)
        review = ProposalReview(approved=True, confidence_score=0.9, risk_level="safe", reasoning="ok")
        assert _run(svc.approve_proposal("p-ghost", "auto-1", review)) is False

    def test_get_available_supervisors(self):
        from core.models import AgentRegistry

        db = Mock()
        order = db.query.return_value.filter.return_value.filter.return_value.order_by
        order.return_value.all.return_value = [AgentRegistry(id="a1", name="A", status="autonomous")]
        svc = AutonomousSupervisorService(db)
        result = _run(svc.get_available_supervisors("finance"))
        assert [a.id for a in result] == ["a1"]

    def test_get_available_supervisors_no_category(self):
        db = Mock()
        first = db.query.return_value
        first.filter.return_value.order_by.return_value.all.return_value = []
        svc = AutonomousSupervisorService(db)
        assert _run(svc.get_available_supervisors()) == []


class TestAutonomousSupervisorHelpers:
    async def test_analyze_execution_result_and_error(self):
        svc = AutonomousSupervisorService(Mock())
        exec_mock = Mock(status="completed")
        sup = Mock(id="s1")
        assert await svc._analyze_execution_result(exec_mock, sup) == {
            "success": True,
            "quality_score": 0.8,
            "compliant": True,
        }
        assert await svc._analyze_execution_error(exec_mock, sup) == {
            "error_type": "execution_error",
            "root_cause": "unknown",
            "suggestions": ["retry", "check_inputs"],
        }
        assert await svc._check_execution_concerns(exec_mock, sup) == {
            "has_concerns": False,
            "concerns": [],
            "severity": "low",
        }


# ===========================================================================
# 4. core/identity/did_manager
# ===========================================================================


class TestDidPrimitives:
    def test_base58_validation(self):
        assert dm_module._is_valid_base58("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        assert dm_module._is_valid_base58("") is True
        assert dm_module._is_valid_base58("0OIl") is False

    def test_config_defaults(self):
        cfg = dm_module.DIDConfig()
        assert cfg.method == dm_module.DIDMethod.ATOM
        assert cfg.key_rotation_days == 90
        assert cfg.resolution_timeout_ms == 5000
        assert cfg.cache_ttl_seconds == 300
        assert cfg.federation_resolution is True
        assert cfg.trust_anchor_dids == []

    def test_didkey_hash(self):
        k1 = dm_module.DIDKey(id="k1")
        k2 = dm_module.DIDKey(id="k1")
        assert hash(k1) == hash(k2)

    def test_did_document_to_dict(self):
        doc = dm_module.DIDDocument(
            id="did:atom:agent:x",
            controller="did:atom:instance:i",
            verification_method=[dm_module.DIDVerificationMethod(id="vm1", public_key_base58="pk")],
            authentication=["vm1"],
            service=[dm_module.DIDService(id="s1", service_endpoint="https://x")],
            deactivated=False,
        )
        d = doc.to_dict()
        assert d["@context"] == doc.context
        assert d["verificationMethod"][0]["publicKeyBase58"] == "pk"
        assert d["service"][0]["serviceEndpoint"] == "https://x"
        assert d["deactivated"] is False

    def test_resolution_result_to_dict(self):
        r = dm_module.DIDResolutionResult(did="did:atom:x", resolution_metadata={"m": 1})
        d = r.to_dict()
        assert d["did"] == "did:atom:x"
        assert d["didDocument"] is None
        assert d["resolutionMetadata"] == {"m": 1}


class TestDidGenerate:
    def test_generate_atom_with_and_without_instance(self):
        m = dm_module.DIDManager()
        assert m.generate_did(dm_module.DIDType.AGENT, "agent-1") == "did:atom:agent:agent-1"
        assert (
            m.generate_did(dm_module.DIDType.INSTANCE, "inst-1", instance_id="i1")
            == "did:atom:i1:instance:inst-1"
        )

    def test_generate_key_method(self):
        m = dm_module.DIDManager(config=dm_module.DIDConfig(method=dm_module.DIDMethod.KEY))
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        assert did.startswith("did:key:z")
        assert len(did) == len("did:key:z") + 16

    def test_generate_web_falls_back_to_atom(self):
        m = dm_module.DIDManager(config=dm_module.DIDConfig(method=dm_module.DIDMethod.WEB))
        assert m.generate_did(dm_module.DIDType.USER, "u1").startswith("did:atom:")


class TestDidResolve:
    def test_create_and_resolve_local(self):
        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, dm_module.DIDType.AGENT)
        assert doc.authentication and doc.assertion_method
        assert len(doc.verification_method) == 1
        result = m.resolve_did(did)
        assert result.did_document is doc
        assert result.resolution_metadata == {"resolved": "locally"}

    def test_cache_hit_and_expiry(self):
        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, dm_module.DIDType.AGENT)
        m.resolve_did(did)
        cached = m.resolve_did(did)
        assert cached.resolution_metadata == {"from_cache": True}
        # expired entry → re-resolve from store
        m._resolution_cache[did] = (doc, datetime.now() - timedelta(seconds=9999))
        fresh = m.resolve_did(did)
        assert fresh.resolution_metadata == {"resolved": "locally"}

    def test_cache_disabled(self):
        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        m.create_did_document(did, dm_module.DIDType.AGENT)
        result = m.resolve_did(did, use_cache=False)
        assert result.resolution_metadata == {"resolved": "locally"}
        assert len(m._resolution_cache) == 0

    def test_unsupported_method(self):
        m = dm_module.DIDManager()
        result = m.resolve_did("did:eth:0xabc")
        assert result.resolution_metadata == {"error": "Unsupported DID method"}

    def test_unknown_atom_did(self):
        m = dm_module.DIDManager()
        result = m.resolve_did("did:atom:agent:ghost")
        assert result.resolution_metadata == {"error": "DID not found"}

    def test_federation_resolution_attempted(self):
        m = dm_module.DIDManager()
        m.register_federation_instance("i1", "https://peer1")
        result = m.resolve_did("did:atom:i1:agent:remote-1")
        assert result.resolution_metadata == {"error": "Federation resolution not implemented"}

    def test_federation_resolution_when_disabled(self):
        m = dm_module.DIDManager(
            config=dm_module.DIDConfig(federation_resolution=False)
        )
        result = m.resolve_did("did:atom:i1:agent:remote-1")
        assert result.resolution_metadata == {"error": "DID not found"}

    def test_web_did(self):
        m = dm_module.DIDManager()
        result = m.resolve_did("did:web:example.com")
        assert result.resolution_metadata == {"error": "Web resolution not implemented"}

    def test_resolve_web_did_invalid_format_direct_call(self):
        # Unreachable through resolve_did (any "did:web:*" input has >= 3
        # colon-parts, and bare "did:web" routes to the unsupported-method
        # branch) — covered via the private method directly.
        m = dm_module.DIDManager()
        result = m._resolve_web_did("did:web")
        assert result.resolution_metadata == {"error": "Invalid did:web format"}

    def test_key_did_valid_and_invalid(self):
        m = dm_module.DIDManager()
        good = m.resolve_did("did:key:z6Mk123456789abcdefghijkmno123456789")
        assert good.did_document is not None
        assert good.resolution_metadata == {"resolved": "inline"}
        bad = m.resolve_did("did:key:zGARBAGE!")
        assert bad.resolution_metadata == {"error": "Invalid did:key: suffix is not valid base58"}
        short = m.resolve_did("did:key:notz")
        assert short.resolution_metadata == {"error": "Invalid did:key format"}

    def test_extract_instance_id(self):
        m = dm_module.DIDManager()
        assert m._extract_instance_id_from_did("did:atom:i1:agent:x") == "i1"
        assert m._extract_instance_id_from_did("did:atom:agent:x") is None


class TestDidSignatures:
    def test_verify_signature_no_crypto(self):
        with patch("core.identity.did_manager.CRYPTO_AVAILABLE", False):
            m = dm_module.DIDManager()
            assert m.verify_signature("did:atom:x", b"m", b"s") is False

    def test_verify_signature_no_doc_and_no_vm(self):
        m = dm_module.DIDManager()
        assert m.verify_signature("did:atom:ghost", b"m", b"s") is False
        doc = dm_module.DIDDocument(id="did:atom:a")
        m._did_documents["did:atom:a"] = doc
        assert m.verify_signature("did:atom:a", b"m", b"s") is False

    def test_verify_signature_roundtrip_and_tamper(self):
        if not dm_module.CRYPTO_AVAILABLE:
            pytest.skip("cryptography not installed")
        from cryptography.hazmat.primitives.asymmetric import ed25519

        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, dm_module.DIDType.AGENT)
        key = m._keys[doc.authentication[0]]
        priv = ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(key.private_key_base58)
        )
        msg = b"hello"
        sig = priv.sign(msg)
        assert m.verify_signature(did, msg, sig) is True
        assert m.verify_signature(did, b"tampered", sig) is False

    def test_verify_signature_key_not_found_false(self):
        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        m.create_did_document(did, dm_module.DIDType.AGENT)
        m._keys.clear()
        assert m.verify_signature(did, b"m", b"s") is False

    def test_verify_signature_by_public_key_match(self):
        if not dm_module.CRYPTO_AVAILABLE:
            pytest.skip("cryptography not installed")
        from cryptography.hazmat.primitives.asymmetric import ed25519

        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, dm_module.DIDType.AGENT)
        vm = doc.verification_method[0]
        original = m._keys[doc.authentication[0]]
        priv = ed25519.Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(original.private_key_base58)
        )
        sig = priv.sign(b"msg")
        m._keys.clear()
        m._keys["other"] = dm_module.DIDKey(
            id="other", public_key_base58=vm.public_key_base58,
            private_key_base58=original.private_key_base58,
        )
        assert m.verify_signature(did, b"msg", sig) is True

    def test_verify_with_key_revoked_and_bad_key(self):
        m = dm_module.DIDManager()
        revoked = dm_module.DIDKey(id="k", public_key_base58="00" * 32, revoked=True)
        assert m._verify_with_key(revoked, b"m", b"s") is False
        bad = dm_module.DIDKey(id="k2", public_key_base58="not-hex!")
        assert m._verify_with_key(bad, b"m", b"s") is False


class TestDidLifecycle:
    def test_rotate_key(self):
        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, dm_module.DIDType.AGENT)
        assert m.rotate_key(did) is True
        assert len(doc.verification_method) == 2
        assert doc.version_id
        assert doc.authentication[-1] in m._keys
        assert m.rotate_key("did:atom:nope") is False

    def test_deactivate_did(self):
        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, dm_module.DIDType.AGENT)
        assert m.deactivate_did(did) is True
        assert doc.deactivated is True
        assert all(k.revoked for k in m._keys.values())
        assert m.deactivate_did("did:atom:nope") is False

    def test_statistics(self):
        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        m.create_did_document(did, dm_module.DIDType.AGENT)
        m.register_federation_instance("i1", "https://x")
        m.resolve_did(did)
        stats = m.get_statistics()
        assert stats["total_dids"] == 1
        assert stats["total_keys"] >= 1
        assert stats["active_dids"] == 1
        assert stats["federation_instances"] == 1
        assert stats["cache_size"] == 1

    def test_register_federation_instance(self):
        m = dm_module.DIDManager()
        m.register_federation_instance("i2", "https://peer2")
        assert m._federation_registry["i2"] == "https://peer2"

    def test_generate_keypair_crypto_available(self):
        if not dm_module.CRYPTO_AVAILABLE:
            pytest.skip("cryptography not installed")
        m = dm_module.DIDManager()
        key = m._generate_keypair()
        assert len(key.public_key_base58) == 64
        assert len(key.private_key_base58 or "") == 64

    def test_version_id_shape(self):
        m = dm_module.DIDManager()
        vid = m._generate_version_id()
        assert len(vid) == 16
        assert all(c in "0123456789abcdef" for c in vid)

    def test_generate_keypair_fallback_without_crypto(self):
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("cryptography"):
                raise ImportError("cryptography not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=blocked):
            importlib.reload(dm_module)
            assert dm_module.CRYPTO_AVAILABLE is False
            key = dm_module.DIDManager()._generate_keypair()
            assert len(key.private_key_base58) == 64
        importlib.reload(dm_module)
        assert dm_module.CRYPTO_AVAILABLE is True


class TestDidPersistence:
    def test_persist_writes_and_updates(self, db_session):
        from core.models import FederationDID

        m = dm_module.DIDManager()
        did = m.generate_did(dm_module.DIDType.AGENT, "agent-1")
        doc = m.create_did_document(did, dm_module.DIDType.AGENT)
        key = list(m._keys.values())[0]
        with patch("core.database.get_db_session", return_value=_CommitCM(db_session)):
            m._persist_did(did, dm_module.DIDType.AGENT, doc, key)
            row = db_session.query(FederationDID).filter(FederationDID.did == did).first()
            assert row is not None
            assert row.entity_type == "agent"
            m._persist_did(did, dm_module.DIDType.AGENT, doc, key)  # update path
            db_session.flush()
        assert db_session.query(FederationDID).count() == 1

    def test_persist_exception_swallowed(self):
        m = dm_module.DIDManager()
        doc = dm_module.DIDDocument(id="did:atom:a")
        key = dm_module.DIDKey(id="k", public_key_base58="pk")
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            m._persist_did("did:atom:a", dm_module.DIDType.AGENT, doc, key)

    def test_load_dids_from_db(self, db_session):
        from core.models import FederationDID

        m = dm_module.DIDManager()
        row = FederationDID(
            did="did:atom:agent:loaded-1",
            entity_type="agent",
            entity_id="loaded-1",
            document_json={
                "id": "did:atom:agent:loaded-1",
                "authentication": ["did:atom:agent:loaded-1#key-1"],
                "created": "2026-01-01T00:00:00",
                "version_id": "v9",
            },
            public_key_pem="pk",
            is_active=True,
        )
        db_session.add(row)
        db_session.commit()
        with patch("core.database.get_db_session", return_value=db_session):
            assert m.load_dids_from_db() == 1
            assert m.load_dids_from_db() == 0  # idempotent
        doc = m._did_documents["did:atom:agent:loaded-1"]
        assert doc.authentication == ["did:atom:agent:loaded-1#key-1"]
        assert doc.version_id == "v9"

    def test_load_dids_missing_created(self, db_session):
        from core.models import FederationDID

        db_session.add(
            FederationDID(
                did="did:atom:agent:no-created",
                entity_type="agent",
                entity_id="no-created",
                document_json={"id": "did:atom:agent:no-created", "authentication": []},
                public_key_pem="pk",
                is_active=True,
            )
        )
        db_session.commit()
        m = dm_module.DIDManager()
        with patch("core.database.get_db_session", return_value=db_session):
            assert m.load_dids_from_db() == 1

    def test_load_dids_exception_returns_zero(self):
        m = dm_module.DIDManager()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            assert m.load_dids_from_db() == 0

    def test_get_did_manager_singleton(self):
        with patch("core.identity.did_manager._did_manager_instance", None):
            m1 = dm_module.get_did_manager()
            m2 = dm_module.get_did_manager()
            assert m1 is m2
        dm_module._did_manager_instance = None


# ===========================================================================
# 5. core/identity/verifiable_credentials
# ===========================================================================


class TestVCDataclasses:
    def test_vc_to_dict_full_and_minimal(self):
        vc = vc_module.VerifiableCredential(
            id="vc-1",
            issuer="did:atom:issuer",
            credential_subject={"id": "did:atom:sub"},
            expiration_date=datetime.now() + timedelta(days=1),
            credential_status={"id": "status-1"},
            refresh_service={"type": "refresh"},
            terms_of_use=[{"type": "ToU"}],
            evidence=[{"type": "evidence"}],
            proof=vc_module.VCProof(
                created=datetime.now(),
                proof_value="abc",
                challenge="ch",
                domain="dom",
            ),
        )
        d = vc.to_dict(include_proof=False)
        assert "proof" not in d
        assert d["expirationDate"] == vc.expiration_date.isoformat()
        assert d["credentialStatus"]["id"] == "status-1"
        full = vc.to_dict()
        assert full["proof"]["proofValue"] == "abc"
        assert full["proof"]["challenge"] == "ch"
        assert full["proof"]["domain"] == "dom"
        bare = vc_module.VerifiableCredential().to_dict()
        assert "expirationDate" not in bare

    def test_vc_is_valid_age_expiry(self):
        vc = vc_module.VerifiableCredential(
            expiration_date=datetime.now() + timedelta(days=10)
        )
        assert vc.is_valid() is True
        assert vc.is_valid(datetime.now() + timedelta(days=20)) is False
        vc.revoked = True
        assert vc.is_valid() is False
        vc2 = vc_module.VerifiableCredential(status=vc_module.VCStatus.SUSPENDED)
        assert vc2.is_valid() is False
        assert vc2.get_age().days == 0
        assert vc2.get_time_until_expiry() is None
        vc3 = vc_module.VerifiableCredential(
            expiration_date=datetime.now() + timedelta(days=5)
        )
        remaining = vc3.get_time_until_expiry()
        assert 0 < remaining.total_seconds() < 5 * 86400

    def test_presentation_to_dict(self):
        vp = vc_module.VCPresentation(
            id="pres-1",
            holder="did:atom:holder",
            verifiable_credential=[vc_module.VerifiableCredential(id="vc-1")],
            proof=vc_module.VCProof(proof_value="sig"),
        )
        d = vp.to_dict(include_proof=False)
        assert "proof" not in d
        assert d["holder"] == "did:atom:holder"
        assert d["verifiableCredential"][0]["id"] == "vc-1"
        assert vp.to_dict()["proof"]["proofValue"] == "sig"


class TestVCLifecycle:
    """create/sign/verify round trips with a real in-memory DID manager."""

    @staticmethod
    def _manager_with_issuer():
        mgr = vc_module.VerifiableCredentialManager()
        did_m = dm_module.DIDManager()
        did = did_m.generate_did(dm_module.DIDType.AGENT, "issuer-1")
        did_m.create_did_document(did, dm_module.DIDType.AGENT)
        mgr.did_manager = did_m
        return mgr, did

    def test_create_signed_and_verify_roundtrip(self):
        if not vc_module.CRYPTO_AVAILABLE:
            pytest.skip("cryptography not installed")
        mgr, issuer = self._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            vc = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.AGENT_IDENTITY,
                subject_did="did:atom:subject",
                claims={"agentName": "worker"},
            )
        assert vc.proof is not None
        assert vc.proof.proof_value
        assert vc.credential_subject["id"] == "did:atom:subject"
        assert vc.credential_subject["type"] == "AgentIdentityCredential"
        assert vc.credential_subject["agentName"] == "worker"
        # spoofing attempt: caller cannot override subject id/type
        vc2 = mgr.create_credential(
            issuer_did=issuer,
            credential_type=vc_module.VCType.ACCESS_TOKEN,
            subject_did="did:atom:subject",
            claims={"id": "evil", "type": "evil", "token": "t"},
        )
        assert vc2.credential_subject["id"] == "did:atom:subject"
        assert vc2.credential_subject["token"] == "t"
        assert vc2.credential_subject.get("type") == "AccessTokenCredential"

        result = mgr.verify_credential(vc)
        assert result.is_valid is True
        assert result.signature_verified is True
        assert result.issuer_verified is True
        assert result.status == vc_module.VCStatus.VALID

    def test_create_expiry_capped(self):
        mgr, issuer = self._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            vc = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
                expiry_days=10 ** 6,
            )
        assert vc.expiration_date - vc.issuance_date <= timedelta(days=365)

    def test_expired_and_revoked_and_bad_signature(self):
        if not vc_module.CRYPTO_AVAILABLE:
            pytest.skip("cryptography not installed")
        mgr, issuer = self._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            vc = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
                credential_id="vc-exp",
            )
        past = datetime.now() - timedelta(days=5)
        expired = mgr.verify_credential(vc, at_time=datetime.now() + timedelta(days=400))
        assert expired.status == vc_module.VCStatus.EXPIRED
        assert "expired" in expired.errors[0]

        assert mgr.revoke_credential("vc-exp") is True
        revoked = mgr.verify_credential(vc)
        assert revoked.status == vc_module.VCStatus.REVOKED
        assert mgr._is_revoked("vc-exp") is True
        assert mgr.revoke_credential("vc-ghost") is False

        vc.proof.proof_value = "00"
        bad = mgr.verify_credential(vc, check_revocation=False)
        assert bad.signature_verified is False
        assert "Invalid signature" in bad.errors

    def test_revocation_disabled_refuses(self):
        mgr, issuer = self._manager_with_issuer()
        mgr.config.enable_revocation = False
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            vc = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
            )
        assert mgr.revoke_credential(vc.id) is False
        assert mgr._is_revoked(vc.id) is False

    def test_verify_unresolvable_issuer(self):
        mgr, issuer = self._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            vc = mgr.create_credential(
                issuer_did="did:atom:ghost-issuer",
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
            )
        result = mgr.verify_credential(vc)
        assert result.issuer_verified is False
        assert any("Cannot resolve issuer DID" in e for e in result.errors)

    def test_verify_no_did_manager(self):
        mgr = vc_module.VerifiableCredentialManager()
        mgr.did_manager = None
        vc = vc_module.VerifiableCredential(
            id="vc-unsigned",
            issuer="did:atom:x",
            proof=vc_module.VCProof(proof_value="00" * 32),
        )
        result = mgr.verify_credential(vc)
        assert result.signature_verified is False
        assert result.is_valid is False

    def test_sign_with_key_crypto_unavailable(self):
        mgr = vc_module.VerifiableCredentialManager()
        key = SimpleNamespace(private_key_base58="00" * 32)
        with patch("core.identity.verifiable_credentials.CRYPTO_AVAILABLE", False):
            assert mgr._sign_with_key(key, b"msg") == ""

    def test_sign_failure_returns_empty(self):
        if not vc_module.CRYPTO_AVAILABLE:
            pytest.skip("cryptography not installed")
        mgr = vc_module.VerifiableCredentialManager()
        key = SimpleNamespace(private_key_base58="not-hex!")
        assert mgr._sign_with_key(key, b"msg") == ""

    def test_sign_credential_without_crypto_or_did_manager(self):
        # _sign_credential early-returns when crypto is unavailable or the
        # manager has no DID manager (both branches, direct call).
        vc = vc_module.VerifiableCredential(id="vc-nosign")
        mgr = vc_module.VerifiableCredentialManager()
        with patch("core.identity.verifiable_credentials.CRYPTO_AVAILABLE", False):
            assert mgr._sign_credential(vc, "did:atom:issuer") is vc
        mgr.did_manager = None
        assert mgr._sign_credential(vc, "did:atom:issuer") is vc

    def test_verify_signature_missing_proof_value(self):
        # _verify_signature with a proof that has no proof_value → False.
        vc = vc_module.VerifiableCredential(
            id="vc-novalue", proof=vc_module.VCProof(proof_value=None)
        )
        mgr = vc_module.VerifiableCredentialManager()
        assert mgr._verify_signature(vc) is False


class TestVCPresentations:
    def test_create_signed_presentation_and_verify(self):
        if not vc_module.CRYPTO_AVAILABLE:
            pytest.skip("cryptography not installed")
        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        holder = issuer  # reuse issuer as holder
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            vc = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
                credential_id="vc-pres",
            )
        vp = mgr.create_presentation([vc], holder_did=holder, challenge="chal-1")
        assert vp.proof is not None
        assert vp.proof.challenge == "chal-1"
        assert vp.proof.proof_value
        result = mgr.verify_presentation(vp, challenge="chal-1")
        assert result.is_valid is True
        assert result.status == vc_module.VCStatus.VALID
        assert result.signature_verified is True

    def test_presentation_challenge_mismatch(self):
        mgr = vc_module.VerifiableCredentialManager()
        mgr.config.require_challenge = True
        vp = vc_module.VCPresentation(
            id="pres-1", holder="did:atom:h",
            proof=vc_module.VCProof(proof_value="x", challenge="expected"),
        )
        result = mgr.verify_presentation(vp, challenge="different")
        assert "Challenge mismatch" in result.errors
        assert result.is_valid is False

    def test_presentation_non_hex_proof_does_not_crash(self):
        # Regression: non-hex proof_value used to raise ValueError out of
        # verify_presentation (uncaught) — now a verification error instead.
        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        vp = vc_module.VCPresentation(
            id="pres-1",
            holder=issuer,
            proof=vc_module.VCProof(proof_value="not-hex!"),
        )
        result = mgr.verify_presentation(vp)
        assert result.is_valid is False
        assert any("encoding" in e.lower() for e in result.errors)

    def test_verify_credential_non_hex_proof_does_not_crash(self):
        # Regression: _verify_signature raised ValueError on non-hex
        # proof_value — verify_credential now fails closed instead.
        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        vc = vc_module.VerifiableCredential(
            id="vc-badhex",
            issuer=issuer,
            proof=vc_module.VCProof(proof_value="not-hex!"),
        )
        result = mgr.verify_credential(vc)
        assert result.signature_verified is False
        assert "Invalid signature" in result.errors

    def test_presentation_with_invalid_credential_propagates_errors(self):
        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            good = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
                credential_id="vc-good",
            )
            bad = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
                credential_id="vc-bad",
            )
        assert mgr.revoke_credential("vc-bad") is True
        vp = mgr.create_presentation([good, bad])
        result = mgr.verify_presentation(vp)
        assert result.is_valid is False
        assert any("revoked" in e.lower() for e in result.errors)

    def test_presentation_signature_verified_false_when_no_proof_value(self):
        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        vp = vc_module.VCPresentation(
            id="pres-1",
            holder=issuer,
            proof=vc_module.VCProof(proof_value=None),
        )
        result = mgr.verify_presentation(vp)
        assert result.is_valid is True  # no creds, no errors


class TestVCConvenienceAndStorage:
    def test_agent_identity_and_federation_credentials(self):
        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            ag = mgr.create_agent_identity_credential(
                issuer_did=issuer,
                agent_did="did:atom:agent:a1",
                agent_id="a1",
                agent_name="Alpha",
                capabilities=["chat"],
                instance_id="inst-1",
            )
            fed = mgr.create_federation_membership_credential(
                issuer_did=issuer,
                instance_did="did:atom:instance:i1",
                instance_id="i1",
                instance_name="Peer",
                federation_role="admin",
            )
        assert ag.credential_subject["agentId"] == "a1"
        assert ag.credential_subject["maturityLevel"] == "STUDENT"
        assert fed.credential_subject["federationRole"] == "admin"
        assert fed.credential_subject["permissions"] == ["read", "write", "delete", "admin"]

    def test_default_permissions_by_role(self):
        mgr = vc_module.VerifiableCredentialManager()
        assert mgr._get_default_permissions("member") == ["read", "write"]
        assert mgr._get_default_permissions("observer") == ["read"]
        assert mgr._get_default_permissions("weird") == ["read"]

    def test_get_credentials_by_id_and_subject(self):
        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            a = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.AGENT_IDENTITY,
                subject_did="did:atom:sub-a",
                claims={},
                credential_id="vc-a",
            )
            mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:sub-b",
                claims={},
                credential_id="vc-b",
            )
        assert mgr.get_credential_by_id("vc-a") is a
        assert mgr.get_credential_by_id("vc-missing") is None
        by_subject = mgr.get_credentials_by_subject("did:atom:sub-a")
        assert [c.id for c in by_subject] == ["vc-a"]
        filtered = mgr.get_credentials_by_subject(
            "did:atom:sub-b", vc_module.VCType.ACCESS_TOKEN
        )
        assert [c.id for c in filtered] == ["vc-b"]
        none = mgr.get_credentials_by_subject("did:atom:sub-b", vc_module.VCType.STATUS)
        assert none == []

    def test_persist_and_load(self, db_session):
        from core.models import FederationCredential

        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            vc = mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={"k": "v"},
                credential_id="vc-persist",
            )
        with patch("core.database.get_db_session", return_value=_CommitCM(db_session)):
            mgr._persist_credential(vc)
            row = db_session.query(FederationCredential).filter(
                FederationCredential.credential_id == "vc-persist"
            ).first()
            assert row is not None
            assert row.status == "active"
            assert row.subject_did == "did:atom:subject"
            # update path with revocation
            mgr._persist_credential(vc, revoked=True, revocation_reason="rotated")
            db_session.flush()
        db_session.refresh(row)
        assert row.status == "revoked"
        assert row.revocation_reason == "rotated"

    def test_persist_exception_swallowed(self):
        mgr = vc_module.VerifiableCredentialManager()
        vc = vc_module.VerifiableCredential(id="vc-x")
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            mgr._persist_credential(vc)  # must not raise

    def test_load_credentials_from_db(self, db_session):
        from core.models import FederationCredential

        db_session.add_all(
            [
                FederationCredential(
                    credential_id="vc-live",
                    issuer_did="did:atom:issuer",
                    subject_did="did:atom:s",
                    credential_type="AccessTokenCredential",
                    status="active",
                ),
                FederationCredential(
                    credential_id="vc-dead",
                    issuer_did="did:atom:issuer",
                    subject_did="did:atom:s",
                    credential_type="AccessTokenCredential",
                    status="revoked",
                ),
            ]
        )
        db_session.commit()
        mgr = vc_module.VerifiableCredentialManager()
        with patch("core.database.get_db_session", return_value=db_session):
            assert mgr.load_credentials_from_db() == 2
            assert mgr._status_list["vc-live"] == "active"
            assert mgr._status_list["vc-dead"] == "revoked"
            assert "vc-dead" in mgr._revocation_list
            assert mgr.load_credentials_from_db() == 0  # idempotent

    def test_load_credentials_exception_returns_zero(self):
        mgr = vc_module.VerifiableCredentialManager()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            assert mgr.load_credentials_from_db() == 0

    def test_statistics(self):
        mgr, issuer = TestVCLifecycle._manager_with_issuer()
        with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
            mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
                credential_id="vc-1",
            )
            mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
                credential_id="vc-2",
            )
            mgr.create_credential(
                issuer_did=issuer,
                credential_type=vc_module.VCType.ACCESS_TOKEN,
                subject_did="did:atom:subject",
                claims={},
                credential_id="vc-3",
            )
        mgr.revoke_credential("vc-2")
        stats = mgr.get_statistics()
        assert stats["total_credentials"] == 3
        assert stats["active_credentials"] == 2
        assert stats["expired_credentials"] == 0
        assert stats["revoked_credentials"] == 1

    def test_get_vc_manager_singleton(self):
        with patch("core.identity.verifiable_credentials._vc_manager_instance", None):
            m1 = vc_module.get_vc_manager()
            m2 = vc_module.get_vc_manager()
            assert m1 is m2
        vc_module._vc_manager_instance = None


class TestVCImportFallbacks:
    """Module import-failure branches (reload with blocked deps)."""

    @staticmethod
    def _blocked_crypto():
        return patch.dict(
            sys.modules,
            {
                "cryptography": None,
                "cryptography.hazmat": None,
                "cryptography.hazmat.primitives": None,
                "cryptography.hazmat.primitives.asymmetric": None,
                "cryptography.hazmat.primitives.serialization": None,
                "cryptography.hazmat.backends": None,
            },
        )

    def test_module_import_fallback_without_cryptography(self):
        with self._blocked_crypto():
            importlib.reload(vc_module)
            assert vc_module.CRYPTO_AVAILABLE is False
        importlib.reload(vc_module)
        assert vc_module.CRYPTO_AVAILABLE is True

    def test_module_import_fallback_without_did_manager(self):
        with patch.dict(sys.modules, {"core.identity.did_manager": None}):
            importlib.reload(vc_module)
            assert vc_module.DID_AVAILABLE is False
            mgr = vc_module.VerifiableCredentialManager()
            assert mgr.did_manager is None
            with patch("core.database.get_db_session", side_effect=RuntimeError("db down")):
                vc = mgr.create_credential(
                    issuer_did="did:atom:issuer",
                    credential_type=vc_module.VCType.AGENT_IDENTITY,
                    subject_did="did:atom:subject",
                    claims={"agentName": "worker"},
                )
            assert vc.proof is None  # no DID manager → unsigned
        importlib.reload(vc_module)
        assert vc_module.DID_AVAILABLE is True


# ===========================================================================
# 6. core/intent_classifier
# ===========================================================================


class TestIntentClassifier:
    """LLM path + JSON parsing + heuristic fallback (mocked LLM service)."""

    @staticmethod
    def _make(llm_call):
        fake_llm = AsyncMock()
        fake_llm.call.return_value = {"content": llm_call}
        with patch("core.intent_classifier.get_llm_service", return_value=fake_llm):
            from core.intent_classifier import IntentClassifier

            return IntentClassifier()

    def test_llm_chat_category(self):
        ic = self._make('{"category": "chat", "confidence": 0.9, "reasoning": "simple"}')
        result = _run(ic.classify_intent("What is the weather?"))
        assert result.category.value == "chat"
        assert result.suggested_handler == "llm_service"
        assert result.requires_execution is False

    def test_llm_workflow_category(self):
        ic = self._make('{"category": "workflow", "confidence": 0.8, "reasoning": "steps"}')
        result = _run(ic.classify_intent("Run the monthly report automation"))
        assert result.category.value == "workflow"
        assert result.suggested_handler == "queen_agent"
        assert result.requires_execution is True
        assert result.is_structured is True
        assert result.blueprint_applicable is True

    def test_llm_task_category(self):
        ic = self._make('{"category": "task", "confidence": 0.7, "reasoning": "multi"}')
        result = _run(ic.classify_intent("Research competitors and build integration"))
        assert result.category.value == "task"
        assert result.suggested_handler == "fleet_admiral"
        assert result.is_long_horizon is True
        assert result.requires_agent_recruitment is True

    def test_llm_unknown_category_defaults_chat(self):
        ic = self._make('{"category": "bogus", "confidence": 0.5, "reasoning": "?"}')
        result = _run(ic.classify_intent("anything"))
        assert result.category.value == "chat"

    def test_llm_category_aliases(self):
        ic = self._make('{"category": "general_query", "confidence": 0.5, "reasoning": "x"}')
        assert _run(ic.classify_intent("hi")).category.value == "chat"
        ic2 = self._make('{"category": "automation", "confidence": 0.5, "reasoning": "x"}')
        assert _run(ic2.classify_intent("hi")).category.value == "workflow"
        ic3 = self._make('{"category": "unstructured", "confidence": 0.5, "reasoning": "x"}')
        assert _run(ic3.classify_intent("hi")).category.value == "task"

    def test_markdown_fenced_json(self):
        ic = self._make('```json\n{"category": "workflow", "confidence": 0.8}\n```')
        result = _run(ic.classify_intent("Run the pipeline"))
        assert result.category.value == "workflow"

    def test_plain_fence_json(self):
        ic = self._make('```\n{"category": "task", "confidence": 0.7}\n```')
        result = _run(ic.classify_intent("Build the thing"))
        assert result.category.value == "task"

    def test_parse_error_defaults_chat(self):
        ic = self._make("this is not json")
        result = _run(ic.classify_intent("anything"))
        assert result.category.value == "chat"
        assert result.confidence == 0.5

    def test_llm_error_falls_back_to_heuristic(self):
        fake_llm = AsyncMock()
        fake_llm.call.side_effect = RuntimeError("llm down")
        with patch("core.intent_classifier.get_llm_service", return_value=fake_llm):
            from core.intent_classifier import IntentClassifier

            ic = IntentClassifier()
        result = _run(ic.classify_intent("Run the weekly report automation"))
        assert result.category.value == "workflow"

    def test_heuristic_chat(self):
        ic = self._make("ignored")
        result = ic._heuristic_classify("tell me about maturity")
        assert result.category.value == "chat"
        assert result.suggested_handler == "llm_service"

    def test_heuristic_task_wins_over_chat(self):
        ic = self._make("ignored")
        result = ic._heuristic_classify("research competitors and analyze markets")
        assert result.category.value == "task"
        assert result.suggested_handler == "fleet_admiral"
        assert result.requires_agent_recruitment is True

    def test_get_intent_classifier_singleton(self):
        from core.intent_classifier import get_intent_classifier

        with patch("core.intent_classifier._intent_classifier_instance", None):
            with patch("core.intent_classifier.get_llm_service", return_value=AsyncMock()):
                c1 = get_intent_classifier()
                c2 = get_intent_classifier()
            assert c1 is c2
        import core.intent_classifier as ic_mod

        ic_mod._intent_classifier_instance = None


# ===========================================================================
# 7. core/agent_context_resolver
# ===========================================================================


class _FakeQuery:
    """Mini query double: filter() returns self, first() returns configured.

    NOTE: Mocks are callable, so never use a callable-result protocol here —
    pass a ``seq`` list for call-by-call sequencing instead.
    """

    def __init__(self, first_result=None, raises=False, seq=None):
        self._first = first_result
        self._raises = raises
        self._seq = seq

    def filter(self, *args, **kwargs):
        if self._raises:
            raise RuntimeError("db down")
        return self

    def first(self):
        if self._raises:
            raise RuntimeError("db down")
        if self._seq is not None:
            return self._seq.pop(0)
        return self._first


class _FakeDb:
    """Fake session routing query(model) to per-model query doubles.

    ``seq`` (optional) is a call-by-call sequence served to every registry
    query — used to simulate "first lookup misses, second hits".
    """

    def __init__(self, registry=None, chat=None, raises=False, seq=None):
        self._registry = registry
        self._chat = chat
        self._raises = raises
        self._seq = seq
        self.committed = 0

    def query(self, model):
        name = getattr(model, "__name__", str(model))
        if name == "AgentRegistry":
            return _FakeQuery(self._registry, raises=self._raises, seq=self._seq)
        if name == "ChatSession":
            return _FakeQuery(self._chat, raises=self._raises)
        return _FakeQuery(None)
    def add(self, obj):
        self.added = getattr(self, "added", []) + [obj]

    def commit(self):
        self.committed += 1

    def refresh(self, obj):
        pass


class TestAgentContextResolver:
    def _resolver(self, db):
        with patch("core.agent_context_resolver.AgentGovernanceService") as g:
            from core.agent_context_resolver import AgentContextResolver

            resolver = AgentContextResolver(db)
        resolver.governance = g.return_value
        return resolver

    def test_explicit_agent_resolved(self):
        agent = Mock(id="a1", name="Alpha")
        db = _FakeDb(registry=agent)
        resolver = self._resolver(db)
        result, ctx = _run(
            resolver.resolve_agent_for_request("u1", requested_agent_id="a1")
        )
        assert result is agent
        assert ctx["resolution_path"] == ["explicit_agent_id"]

    def test_explicit_agent_not_found_then_session(self):
        agent = Mock(id="a2", name="Beta")
        session = Mock(metadata_json={"agent_id": "a2"})
        # first registry lookup (explicit id) misses, second (session agent) hits
        db = _FakeDb(registry=Mock(), chat=session, seq=[None, agent])
        resolver = self._resolver(db)
        result, ctx = _run(
            resolver.resolve_agent_for_request("u1", session_id="s1", requested_agent_id="a2")
        )
        assert result is agent
        assert ctx["resolution_path"] == ["explicit_agent_id_not_found", "session_agent"]

    def test_session_no_metadata_falls_to_system_default(self):
        agent = Mock(id="sys1", name="Chat Assistant", workspace_id="default", tenant_id="t")
        db = _FakeDb(registry=agent, chat=Mock(metadata_json=None))
        resolver = self._resolver(db)
        result, ctx = _run(resolver.resolve_agent_for_request("u1", session_id="s1"))
        assert result is agent
        assert ctx["resolution_path"] == ["no_session_agent", "system_default"]

    def test_system_default_created_when_missing(self):
        from core.models import AgentRegistry

        db = _FakeDb(registry=None, chat=Mock(metadata_json=None))
        resolver = self._resolver(db)
        db._registry = None
        result, ctx = _run(resolver.resolve_agent_for_request("u1"))
        assert result is not None
        assert isinstance(result, AgentRegistry)
        assert ctx["resolution_path"] == ["system_default"]
        assert db.committed >= 1

    def test_legacy_row_backfilled_workspace_tenant(self):
        legacy = Mock(id="sys1", name="Chat Assistant", workspace_id=None, tenant_id=None)
        db = _FakeDb(registry=legacy, chat=Mock(metadata_json=None))
        resolver = self._resolver(db)
        result, ctx = _run(resolver.resolve_agent_for_request("u1"))
        assert result is legacy
        assert legacy.workspace_id == "default"
        assert legacy.tenant_id is not None
        assert ctx["resolution_path"] == ["system_default"]

    def test_system_default_error_resolution_failed(self):
        db = _FakeDb(registry=None)
        resolver = self._resolver(db)
        with patch.object(
            type(resolver), "_get_or_create_system_default", return_value=None
        ):
            result, ctx = _run(resolver.resolve_agent_for_request("u1"))
        assert result is None
        assert ctx["resolution_path"] == ["resolution_failed"]

    def test_get_agent_exception_returns_none(self):
        db = _FakeDb(registry=None, raises=True)
        resolver = self._resolver(db)
        assert resolver._get_agent("a1") is None

    def test_get_session_agent_variants(self):
        resolver = self._resolver(_FakeDb(registry=Mock(id="a1"), chat=None))
        assert resolver._get_session_agent("s-missing") is None
        resolver2 = self._resolver(_FakeDb(registry=None, chat=Mock(metadata_json={"agent_id": "a1"})))
        assert resolver2._get_session_agent("s1") is None  # agent not found
        agent = Mock(id="a1")
        resolver3 = self._resolver(_FakeDb(registry=agent, chat=Mock(metadata_json={"agent_id": "a1"})))
        assert resolver3._get_session_agent("s1") is agent
        resolver4 = self._resolver(_FakeDb(registry=agent, chat=Mock(metadata_json=None)))
        assert resolver4._get_session_agent("s1") is None

    def test_get_session_agent_db_error_returns_none(self):
        resolver = self._resolver(_FakeDb(registry=None, raises=True))
        assert resolver._get_session_agent("s1") is None

    def test_system_default_db_error_returns_none(self):
        resolver = self._resolver(_FakeDb(registry=None, raises=True))
        assert resolver._get_or_create_system_default() is None

    def test_set_session_agent_db_error_returns_false(self):
        resolver = self._resolver(_FakeDb(registry=None, raises=True))
        assert resolver.set_session_agent("s1", "a1") is False

    def test_set_session_agent_paths(self):
        resolver = self._resolver(_FakeDb(registry=Mock(id="a1"), chat=None))
        assert resolver.set_session_agent("s-missing", "a1") is False
        resolver2 = self._resolver(_FakeDb(registry=None, chat=Mock(metadata_json={})))
        assert resolver2.set_session_agent("s1", "a1") is False
        session = Mock(metadata_json={"other": 1})
        resolver3 = self._resolver(_FakeDb(registry=Mock(id="a1"), chat=session))
        assert resolver3.set_session_agent("s1", "a1") is True
        assert session.metadata_json == {"other": 1, "agent_id": "a1"}
        assert resolver3.db.committed == 1

    def test_validate_agent_for_action(self):
        db = _FakeDb(registry=None)
        resolver = self._resolver(db)
        resolver.governance.can_perform_action.return_value = {"allowed": True}
        agent = Mock(id="a1")
        assert resolver.validate_agent_for_action(agent, "chat") == {"allowed": True}
        resolver.governance.can_perform_action.assert_called_once_with(
            agent_id="a1", action_type="chat", require_approval=False
        )
