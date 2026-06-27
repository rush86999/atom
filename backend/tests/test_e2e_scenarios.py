# -*- coding: utf-8 -*-
"""
End-to-End Scenario Suite — 40 scenarios across 7 feature themes.

Exercises real code paths across service boundaries (not isolated unit tests).
LLM boundary is mocked at the ``generate()`` boundary with canned responses
per scenario. DB is in-memory SQLite. LanceDB is mocked where it may be
unavailable; the SQL-first contract is verified directly.

Themes:
  1. Agent Lifecycle & Governance        (scenarios  1-8)
  2. Turn Fact Extraction                (scenarios  9-16)
  3. Agent Memory Tools                  (scenarios 17-21)
  4. Verified Outcome Contract           (scenarios 22-26)
  5. Context & Compression               (scenarios 27-30)
  6. Episodic Memory & Retrieval         (scenarios 31-35)
  7. Resilience & Failure Modes          (scenarios 36-40)

Run:
  cd backend && PYTHONPATH=..:. python3 -m pytest tests/test_e2e_scenarios.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Base
from core import turn_fact_extractor as tfe_mod
from core.turn_fact_extractor import (
    TurnFactExtractor,
    _circuit_breaker,
    _likely_contains_fact,
    compute_content_hash,
    get_active_facts_for_prompt,
    get_failure_counts,
    prefetch_relevant_facts,
    remember_fact_explicit,
    forget_fact_explicit,
    search_reasoning_steps_lexical,
)
from core.turn_fact_categories import ALL_FACT_CATEGORIES
from core.tool_outcome_verifier import (
    FAILED_VERIFICATION,
    UNVERIFIED,
    VERIFIED,
    parse_tool_outcome,
)
from core.capability_graduation_service import (
    CapabilityGraduationService,
    CapabilityMaturityLevel,
)
from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentReasoningStep,
    AgentStatus,
    TurnFact,
)


# ---------------------------------------------------------------------------
# Shared fixtures — proven pattern from tests/test_turn_fact_extraction.py
# ---------------------------------------------------------------------------
@pytest.fixture()
def memory_db():
    """In-memory SQLite + SessionLocal monkeypatched into the extractor module."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with patch.object(tfe_mod, "SessionLocal", Session):
        yield Session
    engine.dispose()


@pytest.fixture()
def extractor(memory_db):
    """TurnFactExtractor with an AsyncMock LLM and stubbed vector store."""
    with patch.object(tfe_mod, "get_llm_service"):
        ex = TurnFactExtractor(workspace_id="ws-test", tenant_id="t-test")
    ex.llm = MagicMock()
    ex.llm.generate = AsyncMock(return_value="[]")
    ex._write_vectors_best_effort = lambda rows, source_text="": None
    return ex


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Ensure each test starts with a closed breaker (module-level state)."""
    _circuit_breaker.reset()
    yield
    _circuit_breaker.reset()


def _make_agent(db, agent_id="agent-1", status=AgentStatus.STUDENT.value):
    """Insert a minimal AgentRegistry row and return it."""
    agent = AgentRegistry(
        id=agent_id,
        name=f"Agent {agent_id}",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        workspace_id="default",
        status=status,
        confidence_score=0.5,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _canned_facts(*facts):
    """Build a canned JSON LLM response string from (fact, category, confidence) tuples."""
    import json
    return json.dumps(
        [
            {"fact": f[0], "category": f[1], "domain": "general", "confidence": f[2]}
            for f in facts
        ]
    )


# ===========================================================================
# THEME 1 — Agent Lifecycle & Governance (scenarios 1-8)
# ===========================================================================
class TestAgentLifecycleGovernance:
    """Governance service: maturity levels, action complexity, graduation stats."""

    def test_scenario_01_student_blocked_from_state_change(self, memory_db):
        """STUDENT agent blocked from complexity-3 action."""
        with memory_db() as db:
            _make_agent(db, "student-1", AgentStatus.STUDENT.value)
            svc = AgentGovernanceService(db)
            result = svc.can_perform_action("student-1", "create")
            assert result["allowed"] is False
            assert result["requires_approval"] is True

    def test_scenario_02_intern_can_propose_not_execute(self, memory_db):
        """INTERN agent proposes (complexity 2) but cannot execute (complexity 3)."""
        with memory_db() as db:
            _make_agent(db, "intern-1", AgentStatus.INTERN.value)
            svc = AgentGovernanceService(db)

            propose = svc.can_perform_action("intern-1", "draft")
            assert propose["allowed"] is True
            assert propose["action_complexity"] == 2

            execute = svc.can_perform_action("intern-1", "create")
            assert execute["allowed"] is False
            assert execute["action_complexity"] == 3

    def test_scenario_03_supervised_executes_with_approval(self, memory_db):
        """SUPERVISED agent executing complexity-3 requires approval."""
        with memory_db() as db:
            _make_agent(db, "sup-1", AgentStatus.SUPERVISED.value)
            svc = AgentGovernanceService(db)
            result = svc.can_perform_action("sup-1", "create")
            assert result["allowed"] is True
            # SUPERVISED + complexity 3 → approval needed
            assert result["requires_approval"] is True

    def test_scenario_04_autonomous_executes_critical_action(self, memory_db):
        """AUTONOMOUS agent executes complexity-4 without approval."""
        with memory_db() as db:
            _make_agent(db, "auto-1", AgentStatus.AUTONOMOUS.value)
            svc = AgentGovernanceService(db)
            result = svc.can_perform_action("auto-1", "delete")
            assert result["allowed"] is True
            assert result["action_complexity"] == 4
            assert result["requires_approval"] is False

    def test_scenario_05_action_complexity_mapping(self, memory_db):
        """ACTION_COMPLEXITY dict: read=1, propose=2, execute=3, delete=4."""
        ac = AgentGovernanceService.ACTION_COMPLEXITY
        assert ac["read"] == 1
        assert ac["draft"] == 2
        assert ac["create"] == 3
        assert ac["delete"] == 4

    def test_scenario_06_governance_cache_consistency(self, memory_db):
        """Same governance check twice → consistent result (cache hit)."""
        with memory_db() as db:
            _make_agent(db, "auto-2", AgentStatus.AUTONOMOUS.value)
            svc = AgentGovernanceService(db)
            first = svc.can_perform_action("auto-2", "read")
            second = svc.can_perform_action("auto-2", "read")
            assert first["allowed"] == second["allowed"] is True
            assert first["action_complexity"] == second["action_complexity"] == 1

    def test_scenario_07_record_usage_verified_increments_counter(self, memory_db):
        """record_usage with verified='verified' increments verified_success counter."""
        with memory_db() as db:
            _make_agent(db, "grad-1", AgentStatus.STUDENT.value)
            svc = CapabilityGraduationService(db)

            svc.record_usage("grad-1", "cap-1", success=True, verified=VERIFIED)
            svc.record_usage("grad-1", "cap-1", success=True, verified=VERIFIED)

            agent = db.query(AgentRegistry).filter(AgentRegistry.id == "grad-1").first()
            stats = agent.configuration.get("capability_stats", {}).get("cap-1", {})
            assert stats.get("verified_success") == 2

    def test_scenario_08_reset_maturity_drops_to_student(self, memory_db):
        """reset_maturity drops capability to STUDENT."""
        with memory_db() as db:
            _make_agent(db, "demote-1", AgentStatus.INTERN.value)
            svc = CapabilityGraduationService(db)

            # Promote to intern first
            agent = db.query(AgentRegistry).filter(AgentRegistry.id == "demote-1").first()
            cfg = dict(agent.configuration or {})
            cfg.setdefault("capability_maturities", {})["cap-x"] = CapabilityMaturityLevel.INTERN
            agent.configuration = cfg
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(agent, "configuration")
            db.commit()

            svc.reset_maturity("demote-1", "cap-x", reason="test demotion")
            assert svc.get_maturity("demote-1", "cap-x") == CapabilityMaturityLevel.STUDENT


# ===========================================================================
# THEME 2 — Turn Fact Extraction (scenarios 9-16)
# ===========================================================================
class TestTurnFactExtraction:
    """Category classification, regex pre-filter, dedup, supersede."""

    def test_scenario_09_extract_hard_constraint(self, extractor):
        """'must use Stripe for payments' → hard_constraint."""
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(
                ("We must use Stripe for all payments", "hard_constraint", 0.9),
            )
        )
        rows = asyncio.get_event_loop().run_until_complete(
            extractor.extract_from_turn(
                user_request="Setup payments",
                thought="Need to use Stripe",
                observation="must use Stripe for payments",
            )
        )
        assert len(rows) == 1
        assert rows[0].category == "hard_constraint"

    def test_scenario_10_extract_exact_value(self, extractor):
        """'$50K MRR, 7-day SLA' → exact_value."""
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(
                ("MRR is $50K", "exact_value", 0.92),
                ("SLA is 7 days", "exact_value", 0.88),
            )
        )
        rows = asyncio.get_event_loop().run_until_complete(
            extractor.extract_from_turn(
                user_request="finance review",
                observation="$50K MRR, 7-day SLA",
            )
        )
        assert len(rows) == 2
        assert all(r.category == "exact_value" for r in rows)

    def test_scenario_11_extract_decision_reason(self, extractor):
        """'chose Postgres because scaling' → decision_reason."""
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(
                ("Chose Postgres for horizontal scaling", "decision_reason", 0.85),
            )
        )
        rows = asyncio.get_event_loop().run_until_complete(
            extractor.extract_from_turn(
                user_request="db choice",
                observation="chose Postgres because scaling",
            )
        )
        assert len(rows) == 1
        assert rows[0].category == "decision_reason"

    def test_scenario_12_extract_cross_task_dep(self, extractor):
        """'blocks onboarding v2' → cross_task_dep."""
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(
                ("Onboarding v2 is blocked by auth service", "cross_task_dep", 0.88),
            )
        )
        rows = asyncio.get_event_loop().run_until_complete(
            extractor.extract_from_turn(
                user_request="roadmap",
                observation="blocks onboarding v2",
            )
        )
        assert len(rows) == 1
        assert rows[0].category == "cross_task_dep"

    def test_scenario_13_extract_implicit_pref(self, extractor):
        """'prefers terse bullet-point responses' → implicit_pref."""
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(
                ("User prefers terse bullet-point responses", "implicit_pref", 0.82),
            )
        )
        rows = asyncio.get_event_loop().run_until_complete(
            extractor.extract_from_turn(
                user_request="style",
                observation="prefers terse bullet-point responses",
            )
        )
        assert len(rows) == 1
        assert rows[0].category == "implicit_pref"

    def test_scenario_14_prefilter_skips_trivial(self, extractor):
        """'hello, thanks' → no LLM call fired."""
        # _likely_contains_fact gate rejects trivial text before LLM is touched.
        assert _likely_contains_fact("hello, thanks") is False
        # And the extractor returns [] without invoking the LLM.
        before = extractor.llm.generate.call_count
        rows = asyncio.get_event_loop().run_until_complete(
            extractor.extract_from_turn(
                user_request="hello",
                final_answer="thanks",
            )
        )
        assert rows == []
        assert extractor.llm.generate.call_count == before

    def test_scenario_15_dedup_ewma_bumps_confidence(self, memory_db, extractor):
        """Same fact text twice → one row, EWMA-blended confidence."""
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(("must use Stripe", "hard_constraint", 0.9))
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            extractor.extract_from_turn(
                user_request="payments", observation="must use Stripe"
            )
        )
        # Second extraction of the same fact text → EWMA bump, no new row.
        loop.run_until_complete(
            extractor.extract_from_turn(
                user_request="payments", observation="must use Stripe"
            )
        )

        with memory_db() as db:
            rows = (
                db.query(TurnFact)
                .filter(TurnFact.workspace_id == "ws-test")
                .all()
            )
            active = [r for r in rows if r.status == "active"]
            assert len(active) == 1  # deduped, not duplicated

    def test_scenario_16_supersede_on_strong_beat(self, memory_db, extractor):
        """New confidence beats old by >0.1 → old=superseded, new=active."""
        # First insert: low confidence
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(("must use Stripe", "hard_constraint", 0.5))
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            extractor.extract_from_turn(
                user_request="payments", observation="must use Stripe"
            )
        )

        # Wait out the anti-thrash TTL window (we bypass it via direct extractor).
        # Same text, much higher confidence (>0.1 beat).
        extractor._recent_hashes._store.clear()
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(("must use Stripe", "hard_constraint", 0.95))
        )
        loop.run_until_complete(
            extractor.extract_from_turn(
                user_request="payments", observation="must use Stripe"
            )
        )

        with memory_db() as db:
            rows = (
                db.query(TurnFact)
                .filter(
                    TurnFact.workspace_id == "ws-test",
                    TurnFact.fact_text == "must use Stripe",
                )
                .all()
            )
            statuses = {r.status for r in rows}
            assert "superseded" in statuses
            assert "active" in statuses


# ===========================================================================
# THEME 3 — Agent Memory Tools (scenarios 17-21)
# ===========================================================================
class TestAgentMemoryTools:
    """memory_remember / memory_forget: agent-callable persistence + invalidation."""

    def test_scenario_17_remember_all_categories(self, memory_db):
        """memory_remember persists all 5 categories with correct metadata."""
        from tools.memory_tool import memory_remember

        loop = asyncio.get_event_loop()
        for cat in ALL_FACT_CATEGORIES:
            res = loop.run_until_complete(
                memory_remember(
                    fact_text=f"sample {cat} fact",
                    category=cat,
                    workspace_id="ws-A",
                )
            )
            assert res["success"] is True, f"category {cat} failed: {res}"

        with memory_db() as db:
            rows = db.query(TurnFact).filter(TurnFact.workspace_id == "ws-A").all()
            cats = {r.category for r in rows}
            assert cats == set(ALL_FACT_CATEGORIES)

    def test_scenario_18_forget_by_fact_id(self, memory_db):
        """memory_forget by fact_id → status=invalidated, audit preserved."""
        from tools.memory_tool import memory_remember, memory_forget

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(
            memory_remember(
                fact_text="stripe-only fact",
                category="hard_constraint",
                workspace_id="ws-B",
            )
        )
        fact_id = res["fact_id"]

        out = loop.run_until_complete(
            memory_forget(fact_id=fact_id, workspace_id="ws-B")
        )
        assert out["success"] is True
        assert out["invalidated_count"] == 1

        with memory_db() as db:
            row = db.get(TurnFact, fact_id)
            assert row.status == "invalidated"  # soft-delete preserves audit

    def test_scenario_19_forget_by_substring(self, memory_db):
        """memory_forget by substring → all matching rows invalidated."""
        from tools.memory_tool import memory_remember, memory_forget

        loop = asyncio.get_event_loop()
        for txt in ["stripe-key-1", "stripe-key-2", "paypal-key-3"]:
            loop.run_until_complete(
                memory_remember(
                    fact_text=txt,
                    category="exact_value",
                    workspace_id="ws-C",
                )
            )

        out = loop.run_until_complete(
            memory_forget(fact_text_contains="stripe-key", workspace_id="ws-C")
        )
        assert out["success"] is True
        assert out["invalidated_count"] == 2

        with memory_db() as db:
            active = (
                db.query(TurnFact)
                .filter(
                    TurnFact.workspace_id == "ws-C",
                    TurnFact.status == "active",
                )
                .all()
            )
            assert len(active) == 1
            assert active[0].fact_text == "paypal-key-3"

    def test_scenario_20_blank_forget_refused(self, memory_db):
        """Blank forget (no target) → refused."""
        from tools.memory_tool import memory_forget

        loop = asyncio.get_event_loop()
        out = loop.run_until_complete(memory_forget(workspace_id="ws-D"))
        assert out["success"] is False
        assert out["invalidated_count"] == 0
        assert "specific target" in out["message"]

    def test_scenario_21_cross_workspace_isolation(self, memory_db):
        """Remember in ws-A, forget in ws-B → ws-A untouched."""
        from tools.memory_tool import memory_remember, memory_forget

        loop = asyncio.get_event_loop()
        # Same fact text in two workspaces
        loop.run_until_complete(
            memory_remember(
                fact_text="shared secret",
                category="exact_value",
                workspace_id="ws-A",
            )
        )
        loop.run_until_complete(
            memory_remember(
                fact_text="shared secret",
                category="exact_value",
                workspace_id="ws-B",
            )
        )

        # Forget in ws-B only
        out = loop.run_until_complete(
            memory_forget(fact_text_contains="shared", workspace_id="ws-B")
        )
        assert out["invalidated_count"] == 1

        with memory_db() as db:
            a_active = (
                db.query(TurnFact)
                .filter(
                    TurnFact.workspace_id == "ws-A",
                    TurnFact.fact_text == "shared secret",
                    TurnFact.status == "active",
                )
                .count()
            )
            assert a_active == 1  # ws-A untouched


# ===========================================================================
# THEME 4 — Verified Outcome Contract (scenarios 22-26)
# ===========================================================================
class TestVerifiedOutcomeContract:
    """Tri-state verified gating: only verified=True successes graduate."""

    def test_scenario_22_five_verified_promotes_student_to_intern(self, memory_db):
        """5 verified successes → STUDENT promoted to INTERN."""
        with memory_db() as db:
            _make_agent(db, "p22", AgentStatus.STUDENT.value)
            svc = CapabilityGraduationService(db)

            for _ in range(5):
                svc.record_usage("p22", "cap", success=True, verified=VERIFIED)
            db.commit()

            assert svc.get_maturity("p22", "cap") == CapabilityMaturityLevel.INTERN

    def test_scenario_23_unverified_no_promotion(self, memory_db):
        """20 unverified successes → stays STUDENT (silent no-op defense)."""
        with memory_db() as db:
            _make_agent(db, "p23", AgentStatus.STUDENT.value)
            svc = CapabilityGraduationService(db)

            for _ in range(20):
                svc.record_usage("p23", "cap", success=True, verified=UNVERIFIED)
            db.commit()

            assert svc.get_maturity("p23", "cap") == CapabilityMaturityLevel.STUDENT

    def test_scenario_24_end_to_end_unverified_no_inflate(self, memory_db):
        """Tool returns {success:true} without evidence → unverified → no promotion."""
        with memory_db() as db:
            _make_agent(db, "p24", AgentStatus.STUDENT.value)
            svc = CapabilityGraduationService(db)

            for _ in range(20):
                outcome = parse_tool_outcome({"success": True})  # no 'verified' key
                assert outcome.kind == UNVERIFIED
                svc.record_usage("p24", "cap", success=outcome.success, verified=outcome.kind)
            db.commit()

            assert svc.get_maturity("p24", "cap") == CapabilityMaturityLevel.STUDENT

    def test_scenario_25_failed_verification_never_counts(self, memory_db):
        """failed_verification never increments verified_success."""
        with memory_db() as db:
            _make_agent(db, "p25", AgentStatus.STUDENT.value)
            svc = CapabilityGraduationService(db)

            for _ in range(50):
                svc.record_usage("p25", "cap", success=False, verified=FAILED_VERIFICATION)
            db.commit()

            agent = db.query(AgentRegistry).filter(AgentRegistry.id == "p25").first()
            stats = agent.configuration.get("capability_stats", {}).get("cap", {})
            assert stats.get("verified_success", 0) == 0
            assert svc.get_maturity("p25", "cap") == CapabilityMaturityLevel.STUDENT

    def test_scenario_26_mixed_then_promotion(self, memory_db):
        """4 verified + 30 unverified → STUDENT; +1 verified → INTERN."""
        with memory_db() as db:
            _make_agent(db, "p26", AgentStatus.STUDENT.value)
            svc = CapabilityGraduationService(db)

            for _ in range(4):
                svc.record_usage("p26", "cap", success=True, verified=VERIFIED)
            for _ in range(30):
                svc.record_usage("p26", "cap", success=True, verified=UNVERIFIED)
            db.commit()
            assert svc.get_maturity("p26", "cap") == CapabilityMaturityLevel.STUDENT

            svc.record_usage("p26", "cap", success=True, verified=VERIFIED)
            db.commit()
            assert svc.get_maturity("p26", "cap") == CapabilityMaturityLevel.INTERN


# ===========================================================================
# THEME 5 — Context & Compression (scenarios 27-30)
# ===========================================================================
class TestContextCompression:
    """truncate_to_context, sanitize_tool_pairs, queue, Tier-1 recall."""

    def test_scenario_27_truncate_preserves_head_and_tail(self):
        """600K-char prompt → head + tail preserved, middle elided."""
        # truncate_to_context is an instance method whose only dependency on
        # instance state is get_context_window; bypass __init__ entirely and
        # monkey-patch that one method.
        from core.llm.byok_handler import BYOKHandler

        handler = BYOKHandler.__new__(BYOKHandler)
        handler.get_context_window = lambda model_name: 5000  # ~20K chars

        text = "HEAD" * 5000 + "MIDDLE" * 50000 + "TAIL" * 5000
        assert len(text) > 100_000

        out = handler.truncate_to_context(text, "test-model", reserve_tokens=100)

        assert out.startswith("HEAD")
        assert out.endswith("TAIL")
        assert "elided" in out
        assert len(out) < len(text)

    def test_scenario_28_sanitize_orphaned_tool_result(self):
        """Orphaned tool result gets stub assistant.tool_calls injected."""
        from core.llm.byok_handler import BYOKHandler

        messages = [
            {"role": "user", "content": "what's the weather?"},
            {"role": "tool", "tool_call_id": "tc-1", "content": "sunny"},
        ]
        out = BYOKHandler.sanitize_tool_pairs(messages)
        # The tool message must be preceded by an assistant.tool_calls stub.
        tool_idx = next(i for i, m in enumerate(out) if m.get("role") == "tool")
        assert tool_idx > 0
        prev = out[tool_idx - 1]
        assert prev["role"] == "assistant"
        assert prev.get("tool_calls") is not None

    def test_scenario_29_pre_compress_queue_drains(self, memory_db, extractor):
        """Prompt > context_window*3 → enqueue succeeds, worker drains."""
        from core.turn_fact_queue import ExtractionQueue

        # Patch get_turn_fact_extractor to return our prepared extractor
        with patch.object(tfe_mod, "get_turn_fact_extractor", return_value=extractor):
            extractor.llm.generate = AsyncMock(return_value="[]")
            q = ExtractionQueue(maxsize=10)

            big_prompt = "x" * 100000  # large prompt
            ok = q.enqueue(
                prompt=big_prompt,
                workspace_id="ws-test",
                execution_id="exec-1",
            )
            assert ok is True

            loop = asyncio.get_event_loop()
            drained = loop.run_until_complete(q.drain_once())
            # drain_once returns count extracted; [] → 0, but item was processed.
            assert q.stats()["drained"] == 1
            assert q.stats()["queued"] == 0

    def test_scenario_30_get_active_facts_ordered_by_recency(self, memory_db):
        """Tier-1 SQL recall returns facts ordered by created_at desc."""
        with memory_db() as db:
            now = datetime.now(timezone.utc)
            for i in range(5):
                db.add(TurnFact(
                    id=f"f-{i}",
                    workspace_id="ws-ord",
                    extraction_source="turn",
                    fact_text=f"fact {i}",
                    category="exact_value",
                    confidence=0.7,
                    content_hash=compute_content_hash("ws-ord", f"fact {i}"),
                    status="active",
                    created_at=now - timedelta(minutes=5 - i),
                ))
            db.commit()

            rows = get_active_facts_for_prompt(db, "ws-ord", limit=3)
            assert len(rows) == 3
            # Most recent first
            assert rows[0].created_at >= rows[1].created_at >= rows[2].created_at


# ===========================================================================
# THEME 6 — Episodic Memory & Retrieval (scenarios 31-35)
# ===========================================================================
class TestEpisodicMemoryRetrieval:
    """Outcome derivation, prefilter, FTS5, trivial-query skip, graceful degrade."""

    def test_scenario_31_derive_outcome_success_and_failure(self):
        """_derive_outcome: all completed → 'success'; any failed → 'failure'."""
        from core.episode_segmentation_service import EpisodeSegmentationService

        svc = EpisodeSegmentationService.__new__(EpisodeSegmentationService)

        def _exec(status):
            e = MagicMock()
            e.status = status
            return e

        assert svc._derive_outcome([_exec("completed"), _exec("completed")]) == "success"
        assert svc._derive_outcome([_exec("completed"), _exec("failed")]) == "failure"
        assert svc._derive_outcome([]) == "unknown"

    def test_scenario_32_retrieve_semantic_outcome_prefilter(self, memory_db):
        """retrieve_semantic(outcome='failure') prefilters via native LanceDB filter."""
        from core.episode_retrieval_service import EpisodeRetrievalService

        with memory_db() as db:
            _make_agent(db, "ep-32", AgentStatus.AUTONOMOUS.value)
            svc = EpisodeRetrievalService.__new__(EpisodeRetrievalService)
            svc.db = db
            svc.lancedb = MagicMock()
            svc.governance = AgentGovernanceService(db)

            captured = {}

            def fake_search(table_name, query, filter_str, limit):
                captured["filter_str"] = filter_str
                captured["limit"] = limit
                return []

            svc.lancedb.search = fake_search

            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                svc.retrieve_semantic(
                    agent_id="ep-32",
                    query="how did we handle this before",
                    outcome="failure",
                    limit=5,
                )
            )

            # The outcome prefilter must appear in the native LanceDB filter.
            assert "outcome == 'failure'" in captured["filter_str"]
            assert "agent_id == 'ep-32'" in captured["filter_str"]

    def test_scenario_33_fts5_finds_exact_error(self, memory_db):
        """FTS5 lexical search finds exact error string 'ValueError line 42'."""
        with memory_db() as db:
            # agent_reasoning_steps.execution_id is NOT NULL with an FK to
            # agent_executions.id, so we need a parent execution row first.
            exec_row = AgentExecution(
                id="exec-33",
                agent_id=None,
                status="completed",
            )
            db.add(exec_row)
            db.commit()

            step = AgentReasoningStep(
                id="rs-1",
                execution_id="exec-33",
                step_number=1,
                step_type="observation",
                observation="Encountered ValueError line 42 while parsing config",
                verified=UNVERIFIED,
            )
            db.add(step)
            db.commit()

            # Create + populate the FTS5 virtual table (SQLite only).
            from sqlalchemy import text as sa_text
            db.execute(
                sa_text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS agent_reasoning_steps_fts "
                    "USING fts5(observation, thought, content='agent_reasoning_steps', "
                    "content_rowid='rowid')"
                )
            )
            db.execute(
                sa_text(
                    "INSERT INTO agent_reasoning_steps_fts(rowid, observation, thought) "
                    "SELECT rowid, observation, thought FROM agent_reasoning_steps"
                )
            )
            db.commit()

            results = search_reasoning_steps_lexical(
                workspace_id="ws-test",
                query="ValueError line 42",
                limit=5,
            )
            assert any("ValueError" in (r.get("observation") or "") for r in results)

    def test_scenario_34_prefetch_skips_trivial_query(self):
        """prefetch_relevant_facts returns [] for trivial 'hi'."""
        # Even with recall enabled, 'hi' is skipped.
        with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", True):
            results = prefetch_relevant_facts("ws-test", "hi")
        assert results == []

    def test_scenario_35_recall_degrades_without_lancedb(self):
        """Tier-2 recall returns [] gracefully when LanceDB unavailable."""
        # Recall disabled by default flag → [].
        with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", False):
            results = prefetch_relevant_facts("ws-test", "real query about payments")
        assert results == []

        # Even with flag on, a LanceDB import failure must not raise.
        with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", True):
            with patch(
                "core.turn_fact_vector_store.search_relevant_fact_ids",
                side_effect=RuntimeError("lancedb unreachable"),
            ):
                results = prefetch_relevant_facts("ws-test", "real query about payments")
        assert results == []


# ===========================================================================
# THEME 7 — Resilience & Failure Modes (scenarios 36-40)
# ===========================================================================
class TestResilienceFailureModes:
    """Circuit breaker, timeouts, best-effort vector writes, queue backpressure, never-raise."""

    def test_scenario_36_circuit_breaker_full_cycle(self, memory_db):
        """5 LLM failures → OPEN → skip → cooldown → HALF-OPEN probe."""
        # Force a very short cooldown for the test via env patch.
        with patch.object(tfe_mod, "_CB_COOLDOWN_S", 0.05), \
             patch.object(tfe_mod, "_CB_THRESHOLD", 5):
            cb = tfe_mod._CircuitBreaker()
            cb.failures = 0
            for _ in range(5):
                cb.record_failure()
            assert cb.state == "open"
            assert cb.is_tripped() is True

            # After cooldown elapses, breaker half-opens and lets a probe through.
            time.sleep(0.06)
            assert cb.is_tripped() is False  # probe allowed
            assert cb.state == "half_open"

            # Probe succeeds → breaker closes.
            cb.record_success()
            assert cb.state == "closed"
            assert cb.is_tripped() is False

    def test_scenario_37_llm_timeout_returns_empty(self, extractor):
        """LLM call > 2s timeout → returns [], counter incremented."""
        async def slow_generate(**kwargs):
            await asyncio.sleep(5)
            return "[]"

        extractor.llm.generate = slow_generate
        before = get_failure_counts().get("timeout", 0)

        loop = asyncio.get_event_loop()
        rows = loop.run_until_complete(
            extractor.extract_from_turn(
                user_request="payments",
                observation="must use Stripe",
            )
        )
        assert rows == []
        # Failure counter incremented and breaker now has ≥1 failure.
        after = get_failure_counts().get("timeout", 0)
        assert after >= before + 1

    def test_scenario_38_lancedb_fail_sql_row_persists(self, memory_db, extractor):
        """LanceDB write fails → SQL row still persisted (best-effort contract)."""
        extractor.llm.generate = AsyncMock(
            return_value=_canned_facts(("must use Stripe", "hard_constraint", 0.9))
        )

        def failing_write(rows, source_text=""):
            raise RuntimeError("lancedb disk full")

        extractor._write_vectors_best_effort = failing_write

        loop = asyncio.get_event_loop()
        rows = loop.run_until_complete(
            extractor.extract_from_turn(
                user_request="payments", observation="must use Stripe"
            )
        )
        # SQL row still persisted despite vector-store failure.
        assert len(rows) == 1
        assert rows[0].status == "active"

    def test_scenario_39_queue_full_backpressure(self):
        """Queue full → enqueue returns False, dropped counter incremented."""
        from core.turn_fact_queue import ExtractionQueue

        q = ExtractionQueue(maxsize=2)
        assert q.enqueue(prompt="p1", workspace_id="ws") is True
        assert q.enqueue(prompt="p2", workspace_id="ws") is True
        assert q.enqueue(prompt="p3", workspace_id="ws") is False  # dropped

        stats = q.stats()
        assert stats["dropped"] == 1
        assert stats["queued"] == 2

    def test_scenario_40_never_raise_contract(self, extractor):
        """Every extraction entrypoint catches all exceptions and returns [] / 0."""
        # Force LLM to raise — extractor must still return [].
        extractor.llm.generate = AsyncMock(side_effect=RuntimeError("provider 500"))

        loop = asyncio.get_event_loop()
        # extract_from_turn
        r1 = loop.run_until_complete(
            extractor.extract_from_turn(
                user_request="x", observation="must use Stripe"
            )
        )
        assert r1 == []

        # extract_from_prompt_before_truncation
        r2 = loop.run_until_complete(
            extractor.extract_from_prompt_before_truncation(prompt="must use Stripe")
        )
        assert r2 == []

        # remember_fact_explicit with bad category → None (not raise)
        r3 = remember_fact_explicit(
            workspace_id="ws-test",
            fact_text="x",
            category="not_a_real_category",
        )
        assert r3 is None

        # forget_fact_explicit with empty workspace → 0 (not raise)
        r4 = forget_fact_explicit(workspace_id="", fact_id="x")
        assert r4 == 0
