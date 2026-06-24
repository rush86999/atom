# -*- coding: utf-8 -*-
"""
TDD regression tests for the Turn Fact Extraction layer (Phases 1-6).

Covers:
- Schema: TurnFact model + dedup unique constraint
- Pre-filter regex gate (no LLM call when no fact indicators)
- JSON-array parse robustness (incl. wrapped/dirty outputs)
- Hash-based dedup: new insert, EWMA bump on near-duplicate, supersede on strong beat
- Maturity gate: STUDENT agents are read-only
- Sample rate: 0.0 disables extraction entirely
- 2s timeout + LLM failure → returns [] (never raises)
- LanceDB write failure never blocks SQL success
- Tier-1 retrieval: get_active_facts_for_prompt() ordering

Pattern: Red-Green-Refactor (see docs/testing/BUG_FIX_PROCESS.md).
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
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
    _clamp,
    _compose_turn_text,
    _extract_json_array,
    _likely_contains_fact,
    _normalize_fact_text,
    _TTLSet,
    compute_content_hash,
    get_active_facts_for_prompt,
    get_failure_counts,
    prefetch_relevant_facts,
)
from core.turn_fact_categories import ALL_FACT_CATEGORIES, FactCategory


# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite with the TurnFact table
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

    # Patch SessionLocal where the extractor imports it
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
    # No-op vector writer by default
    ex._write_vectors_best_effort = lambda rows, source_text="": None
    return ex


# ===========================================================================
# Phase 1 — Schema + categories
# ===========================================================================
class TestSchema:
    def test_turn_fact_table_exists(self, memory_db):
        from core.models import TurnFact

        with memory_db() as db:
            row = TurnFact(
                id="tf-1",
                workspace_id="ws-test",
                extraction_source="turn",
                fact_text="must use Stripe",
                category="hard_constraint",
                confidence=0.9,
                content_hash=compute_content_hash("ws-test", "must use Stripe"),
            )
            db.add(row)
            db.commit()
            assert db.get(TurnFact, "tf-1") is not None

    def test_unique_constraint_blocks_exact_duplicate(self, memory_db):
        """
        Two ACTIVE rows with the same (workspace, hash) are blocked by the
        application-layer dedup in TurnFactExtractor (SQLite) or the partial
        unique index on Postgres. We verify the extractor's behavior in
        TestDedup; here we just confirm the table accepts superseded rows
        with a duplicate hash (audit history).
        """
        from core.models import TurnFact

        h = compute_content_hash("ws-test", "must use Stripe")
        with memory_db() as db:
            db.add(
                TurnFact(
                    id="tf-active",
                    workspace_id="ws-test",
                    extraction_source="turn",
                    fact_text="must use Stripe",
                    category="hard_constraint",
                    confidence=0.9,
                    content_hash=h,
                    status="active",
                )
            )
            db.add(
                TurnFact(
                    id="tf-old",
                    workspace_id="ws-test",
                    extraction_source="turn",
                    fact_text="must use Stripe",
                    category="hard_constraint",
                    confidence=0.5,
                    content_hash=h,
                    status="superseded",
                )
            )
            # Both rows must coexist (audit history)
            db.commit()
            assert db.query(TurnFact).filter_by(status="active").count() == 1
            assert db.query(TurnFact).filter_by(status="superseded").count() == 1

    def test_categories_are_exactly_five(self):
        assert len(ALL_FACT_CATEGORIES) == 5
        for c in ALL_FACT_CATEGORIES:
            assert FactCategory(c)  # valid enum value


# ===========================================================================
# Phase 2a — Regex pre-filter (no LLM call)
# ===========================================================================
class TestRegexPreFilter:
    @pytest.mark.parametrize(
        "text",
        [
            "must use Stripe for all payments",
            "$50K MRR last quarter",
            "launch on March 14",
            "we decided to use Postgres because scaling",
            "prefers terse responses",
            "blocks onboarding v2",
            "7-day SLA",
            "we have 3 new customers",
        ],
    )
    def test_likely_contains_fact_true(self, text):
        assert _likely_contains_fact(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "hi",
            "ok thanks",
            "sure",
            "        ",
            "abc",  # too short, no indicators
        ],
    )
    def test_likely_contains_fact_false(self, text):
        assert _likely_contains_fact(text) is False


# ===========================================================================
# Phase 2b — Normalization + hash
# ===========================================================================
class TestHashNormalization:
    def test_paraphrases_collide(self):
        # Punctuation + case differences must not change the hash
        a = compute_content_hash("ws", "Must use Stripe!")
        b = compute_content_hash("ws", "must use stripe")
        assert a == b

    def test_whitespace_collapse(self):
        a = compute_content_hash("ws", "must   use    stripe")
        b = compute_content_hash("ws", "must use stripe")
        assert a == b

    def test_workspace_scoping(self):
        # Same text in different workspaces must NOT collide
        a = compute_content_hash("ws-A", "must use Stripe")
        b = compute_content_hash("ws-B", "must use Stripe")
        assert a != b

    def test_normalize_helper(self):
        assert _normalize_fact_text("  Hello,  WORLD!! ") == "hello world"
        assert _normalize_fact_text("") == ""


# ===========================================================================
# Phase 2c — JSON parse robustness
# ===========================================================================
class TestJsonParse:
    def test_clean_array(self):
        assert _extract_json_array('[{"fact":"x","category":"exact_value"}]') == [
            {"fact": "x", "category": "exact_value"}
        ]

    def test_wrapped_object(self):
        out = _extract_json_array('{"facts": [{"fact":"x","category":"exact_value"}]}')
        assert out and out[0]["fact"] == "x"

    def test_dirty_with_prose(self):
        raw = 'Here are the facts:\n[{"fact":"x","category":"exact_value"}]\nDone.'
        assert _extract_json_array(raw) == [{"fact": "x", "category": "exact_value"}]

    def test_empty_array(self):
        assert _extract_json_array("[]") == []

    def test_garbage_returns_none(self):
        # NEVER silently drop — None lets the caller log + increment failure counter
        assert _extract_json_array("totally not json") is None
        assert _extract_json_array("") is None


# ===========================================================================
# Phase 2d — Extract core: end-to-end with mocked LLM
# ===========================================================================
class TestExtractCore:
    @pytest.mark.asyncio
    async def test_happy_path_inserts_row(self, extractor, memory_db):
        extractor.llm.generate = AsyncMock(
            return_value=(
                '[{"fact":"must use Stripe","category":"hard_constraint",'
                '"domain":"finance","confidence":0.95}]'
            )
        )
        rows = await extractor.extract_from_turn(
            user_request="setup payments",
            thought="we must use Stripe for compliance",
            maturity="INTERN",
        )
        assert len(rows) == 1
        assert rows[0].category == "hard_constraint"
        assert rows[0].confidence == 0.95
        assert rows[0].fact_text == "must use Stripe"

    @pytest.mark.asyncio
    async def test_prefilter_skips_trivial_turn(self, extractor):
        # No fact indicators → no LLM call
        extractor.llm.generate = AsyncMock(return_value="SHOULD_NOT_BE_CALLED")
        rows = await extractor.extract_from_turn(
            user_request="hi",
            thought="ok",
            maturity="INTERN",
        )
        assert rows == []
        extractor.llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_category_dropped(self, extractor, memory_db):
        extractor.llm.generate = AsyncMock(
            return_value=(
                '[{"fact":"x","category":"bogus"},{"fact":"must use Stripe",'
                '"category":"hard_constraint"}]'
            )
        )
        rows = await extractor.extract_from_turn(
            user_request="setup payments",
            thought="we must use Stripe",
            maturity="INTERN",
        )
        assert len(rows) == 1
        assert rows[0].category == "hard_constraint"

    @pytest.mark.asyncio
    async def test_max_per_turn_cap(self, extractor, memory_db):
        with patch.object(tfe_mod, "TURN_FACT_MAX_PER_TURN", 2):
            extractor.llm.generate = AsyncMock(
                return_value=(
                    '[{"fact":"a 5","category":"exact_value"},'
                    '{"fact":"b 6","category":"exact_value"},'
                    '{"fact":"c 7","category":"exact_value"}]'
                )
            )
            rows = await extractor.extract_from_turn(
                user_request="stuff", thought="numbers 5 6 7", maturity="INTERN"
            )
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_empty_llm_response_returns_empty(self, extractor):
        extractor.llm.generate = AsyncMock(return_value="[]")
        rows = await extractor.extract_from_turn(
            user_request="setup payments", thought="must use Stripe", maturity="INTERN"
        )
        assert rows == []

    @pytest.mark.asyncio
    async def test_parse_failure_increments_counter(self, extractor):
        before = get_failure_counts().get("parse_error", 0)
        extractor.llm.generate = AsyncMock(return_value="totally not json")
        rows = await extractor.extract_from_turn(
            user_request="setup payments", thought="must use Stripe", maturity="INTERN"
        )
        assert rows == []
        after = get_failure_counts().get("parse_error", 0)
        assert after > before


# ===========================================================================
# Phase 2e — Dedup branches
# ===========================================================================
class TestDedup:
    @pytest.mark.asyncio
    async def test_ewma_bump_on_near_duplicate(self, extractor, memory_db):
        extractor.llm.generate = AsyncMock(
            return_value=(
                '[{"fact":"must use Stripe","category":"hard_constraint",'
                '"confidence":0.85}]'
            )
        )
        await extractor.extract_from_turn(
            user_request="x", thought="we must use Stripe", maturity="INTERN"
        )

        # Simulate the anti-thrashing TTL window expiring between turns
        # (in production this is 5 min; the test exercises the dedup-on-collision
        # codepath, not the throttling).
        extractor._recent_hashes._store.clear()

        # Near-duplicate (same normalized text, close confidence)
        extractor.llm.generate = AsyncMock(
            return_value=(
                '[{"fact":"Must use Stripe!","category":"hard_constraint",'
                '"confidence":0.88}]'
            )
        )
        rows = await extractor.extract_from_turn(
            user_request="x", thought="we Must use Stripe!", maturity="INTERN"
        )
        # Should NOT create a second row — should return the existing, bumped
        assert len(rows) == 1
        from core.models import TurnFact

        with memory_db() as db:
            all_rows = (
                db.query(TurnFact)
                .filter(TurnFact.workspace_id == "ws-test")
                .all()
            )
            assert len(all_rows) == 1
            assert 0.85 < all_rows[0].confidence <= 0.88

    @pytest.mark.asyncio
    async def test_supersede_on_strong_beat(self, extractor, memory_db):
        # Existing fact at 0.5
        extractor.llm.generate = AsyncMock(
            return_value=(
                '[{"fact":"must use Stripe","category":"hard_constraint",'
                '"confidence":0.5}]'
            )
        )
        await extractor.extract_from_turn(
            user_request="x", thought="we must use Stripe", maturity="INTERN"
        )

        # TTL window expired
        extractor._recent_hashes._store.clear()

        # New fact beats by >0.1 → supersede + insert new active
        extractor.llm.generate = AsyncMock(
            return_value=(
                '[{"fact":"must use Stripe","category":"hard_constraint",'
                '"confidence":0.95}]'
            )
        )
        await extractor.extract_from_turn(
            user_request="x", thought="we must use Stripe", maturity="INTERN"
        )

        from core.models import TurnFact

        with memory_db() as db:
            facts = (
                db.query(TurnFact)
                .filter(TurnFact.workspace_id == "ws-test")
                .all()
            )
            assert len(facts) == 2
            active = [f for f in facts if f.status == "active"]
            superseded = [f for f in facts if f.status == "superseded"]
            assert len(active) == 1
            assert len(superseded) == 1
            assert active[0].confidence == 0.95
            assert superseded[0].superseded_at is not None


# ===========================================================================
# Phase 2f — Maturity gate + sample rate
# ===========================================================================
class TestGates:
    @pytest.mark.asyncio
    async def test_student_maturity_blocks_extraction(self, extractor):
        extractor.llm.generate = AsyncMock(return_value='[{"fact":"x 1","category":"exact_value"}]')
        rows = await extractor.extract_from_turn(
            user_request="x", thought="number 1", maturity="STUDENT"
        )
        assert rows == []
        extractor.llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_maturity_allows(self, extractor, memory_db):
        extractor.llm.generate = AsyncMock(return_value='[{"fact":"x 1","category":"exact_value"}]')
        rows = await extractor.extract_from_turn(
            user_request="x", thought="number 1", maturity=None
        )
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_sample_rate_zero_blocks_all(self, extractor):
        with patch.object(tfe_mod, "TURN_FACT_EXTRACTION_SAMPLE_RATE", 0.0):
            rows = await extractor.extract_from_turn(
                user_request="x", thought="must use Stripe", maturity="INTERN"
            )
        assert rows == []
        extractor.llm.generate.assert_not_called()


# ===========================================================================
# Phase 2g — Failure modes (never raise)
# ===========================================================================
class TestFailureModes:
    @pytest.mark.asyncio
    async def test_llm_raises_returns_empty(self, extractor):
        extractor.llm.generate = AsyncMock(side_effect=RuntimeError("provider down"))
        rows = await extractor.extract_from_turn(
            user_request="x", thought="must use Stripe", maturity="INTERN"
        )
        assert rows == []  # never raises

    @pytest.mark.asyncio
    async def test_timeout_returns_empty(self, extractor):
        async def slow(*a, **kw):
            await asyncio.sleep(5)
            return "[]"

        extractor.llm.generate = AsyncMock(side_effect=slow)
        rows = await extractor.extract_from_turn(
            user_request="x", thought="must use Stripe", maturity="INTERN"
        )
        assert rows == []

    @pytest.mark.asyncio
    async def test_lancedb_failure_does_not_block_sql(self, extractor, memory_db):
        extractor.llm.generate = AsyncMock(
            return_value=(
                '[{"fact":"must use Stripe","category":"hard_constraint",'
                '"confidence":0.9}]'
            )
        )

        def boom(rows, source_text=""):
            raise RuntimeError("lancedb corrupted")

        extractor._write_vectors_best_effort = boom
        # Must NOT raise — LanceDB failure is best-effort
        rows = await extractor.extract_from_turn(
            user_request="x", thought="we must use Stripe", maturity="INTERN"
        )
        assert len(rows) == 1  # SQL row still persisted

    @pytest.mark.asyncio
    async def test_pre_compress_entrypoint_never_raises(self, extractor):
        extractor.llm.generate = AsyncMock(side_effect=RuntimeError("down"))
        rows = await extractor.extract_from_prompt_before_truncation(prompt="must use Stripe")
        assert rows == []


# ===========================================================================
# Phase 2h — Anti-thrashing TTLSet
# ===========================================================================
class TestTTLSet:
    def test_add_then_contains(self):
        s = _TTLSet(ttl=60)
        assert "k" not in s
        s.add("k")
        assert "k" in s

    def test_maxsize_evicts_oldest(self):
        s = _TTLSet(maxsize=2, ttl=60)
        s.add("a")
        s.add("b")
        s.add("c")
        # One of the older entries must have been evicted
        assert len({"a", "b", "c"} - {k for k in ("a", "b", "c") if k in s}) >= 1


# ===========================================================================
# Phase 2i — Utilities
# ===========================================================================
class TestUtilities:
    def test_clamp(self):
        assert _clamp(1.5, 0.0, 1.0) == 1.0
        assert _clamp(-1.0, 0.0, 1.0) == 0.0
        assert _clamp(0.5, 0.0, 1.0) == 0.5

    def test_compose_turn_text(self):
        out = _compose_turn_text(
            user_request="hi",
            thought="think",
            action={"tool": "x"},
            observation="obs",
            final_answer="ans",
        )
        assert "USER: hi" in out
        assert "THOUGHT: think" in out
        assert "ACTION:" in out
        assert "OBSERVATION: obs" in out
        assert "ANSWER: ans" in out


# ===========================================================================
# Phase 4 — Tier-1 retrieval
# ===========================================================================
class TestTier1Retrieval:
    def test_returns_recent_active_ordered(self, memory_db):
        from core.models import TurnFact

        now = datetime.now(timezone.utc)
        with memory_db() as db:
            for i in range(7):
                db.add(
                    TurnFact(
                        id=f"tf-{i}",
                        workspace_id="ws-1",
                        extraction_source="turn",
                        fact_text=f"fact {i}",
                        category="exact_value",
                        confidence=0.5 + i * 0.05,
                        content_hash=f"h{i}",
                        created_at=now - timedelta(seconds=10 - i),
                    )
                )
            # One superseded — must NOT appear
            db.add(
                TurnFact(
                    id="tf-sup",
                    workspace_id="ws-1",
                    extraction_source="turn",
                    fact_text="old",
                    category="exact_value",
                    confidence=0.99,
                    content_hash="h-sup",
                    status="superseded",
                    created_at=now,
                )
            )
            db.commit()

            results = get_active_facts_for_prompt(db, "ws-1", limit=5)
            assert len(results) == 5
            assert all(r.status == "active" for r in results)
            # Most recent first
            assert results[0].fact_text == "fact 6"

    def test_category_filter(self, memory_db):
        from core.models import TurnFact

        with memory_db() as db:
            db.add(
                TurnFact(
                    id="tf-a",
                    workspace_id="ws-1",
                    extraction_source="turn",
                    fact_text="rule",
                    category="hard_constraint",
                    confidence=0.9,
                    content_hash="ha",
                )
            )
            db.add(
                TurnFact(
                    id="tf-b",
                    workspace_id="ws-1",
                    extraction_source="turn",
                    fact_text="amount 5",
                    category="exact_value",
                    confidence=0.9,
                    content_hash="hb",
                )
            )
            db.commit()

            only_constraints = get_active_facts_for_prompt(
                db, "ws-1", limit=5, categories=("hard_constraint",)
            )
            assert len(only_constraints) == 1
            assert only_constraints[0].category == "hard_constraint"

    def test_empty_workspace(self, memory_db):
        with memory_db() as db:
            assert get_active_facts_for_prompt(db, "ws-empty") == []

    def test_failure_returns_empty(self, memory_db):
        # Closed session → query error → swallowed
        sess = memory_db()
        sess.close()
        assert get_active_facts_for_prompt(sess, "ws-1") == []


# ===========================================================================
# Phase 7 — LANCEDB_CLOUD_ENABLED flag (gates S3/R2 paths)
# ===========================================================================
class TestCloudGateFlag:
    def test_flag_defaults_false(self):
        # Re-import fresh to read the env at import time
        import importlib

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LANCEDB_CLOUD_ENABLED", None)
            # The config module reads env; verify default by calling the predicate
            from core import lancedb_config as cfg

            # Public helper must exist and default to False when S3_BUCKET unset
            assert hasattr(cfg, "LanceDBConfig")
            assert cfg.LanceDBConfig.is_cloud_enabled() is False


# ===========================================================================
# Phase 6 — Tier-2 vector recall (LanceDB-backed)
# ===========================================================================
class TestTier2VectorRecall:
    def test_flag_off_returns_empty(self):
        with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", False):
            assert prefetch_relevant_facts("ws", "any query") == []

    def test_trivial_query_skipped(self):
        with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", True):
            for q in ("hi", "thanks", "ok", "hey"):
                assert prefetch_relevant_facts("ws", q) == []

    def test_short_query_skipped(self):
        with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", True):
            assert prefetch_relevant_facts("ws", "ab") == []

    def test_happy_path_hydrates(self, memory_db):
        from core.models import TurnFact

        with memory_db() as db:
            db.add(
                TurnFact(
                    id="tf-vec-1",
                    workspace_id="ws-v",
                    extraction_source="turn",
                    fact_text="must use Stripe",
                    category="hard_constraint",
                    confidence=0.9,
                    content_hash="hv1",
                )
            )
            db.commit()

        with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", True), \
             patch("core.turn_fact_vector_store.search_relevant_fact_ids",
                   return_value=["tf-vec-1"]):
            rows = prefetch_relevant_facts("ws-v", "setup payments")
            assert len(rows) == 1
            assert rows[0].id == "tf-vec-1"

    def test_lancedb_failure_returns_empty(self, memory_db):
        with patch.object(tfe_mod, "TURN_FACT_VECTOR_RECALL_ENABLED", True), \
             patch("core.turn_fact_vector_store.search_relevant_fact_ids",
                   side_effect=RuntimeError("lancedb down")):
            assert prefetch_relevant_facts("ws", "setup payments") == []
