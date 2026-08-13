"""Coverage wave 64l — core/turn_fact_extractor.py sanity probe (TDD, mocked
LLM, in-memory SQLite, zero spend).

The extractor was stamped 89% at R72 and pushed to 100% by wave 37
(tests/test_covpush_w37_turn_fact.py + w23 + w24 suites). This file is a
lightweight regression probe that re-drives the primary happy paths
(end-to-end turn extraction with dedup persistence, prompt-before-truncation
extraction, and the anti-thrash TTL set) so the wave-64l probe run clears
>=95% combined with the existing suites.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.turn_fact_extractor as tfe
from core.database import Base
from core.turn_fact_extractor import (
    TurnFactExtractor,
    _clamp,
    _coerce_confidence,
    compute_content_hash,
)


@pytest.fixture
def extractor():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ex = TurnFactExtractor(workspace_id="ws1", tenant_id="t1")
    ex._recent_hashes._store.clear()
    ex._recent_hashes._store.clear()
    llm = Mock()
    llm.generate = AsyncMock(
        return_value='[{"fact": "Revenue is 50k MRR", "category": "exact_value", '
                     '"confidence": 0.9, "domain": "finance", "tags": ["mrr"]}]'
    )
    ex.llm = llm
    ex._write_vectors_best_effort = Mock()
    with patch.object(tfe, "SessionLocal", Session):
        yield ex
    engine.dispose()


def run(coro):
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestExtractHappyPath:
    def test_extract_from_turn_persists_fact(self, extractor):
        rows = run(extractor.extract_from_turn(
            user_request="What is our revenue?",
            thought="Looking up revenue",
            observation="Revenue is 50k MRR",
            final_answer="Revenue is 50k MRR.",
            execution_id="exec-1",
            episode_id="ep-1",
            maturity="SUPERVISED",
        ))
        assert len(rows) == 1
        assert rows[0].fact_text == "Revenue is 50k MRR"
        assert rows[0].category == "exact_value"
        assert rows[0].confidence == 0.9

    def test_same_turn_again_is_deduped(self, extractor):
        first = run(extractor.extract_from_turn(
            user_request="Revenue?", observation="Revenue is 50k MRR",
            execution_id="exec-1", maturity="SUPERVISED",
        ))
        second = run(extractor.extract_from_turn(
            user_request="Revenue?", observation="Revenue is 50k MRR",
            execution_id="exec-1", maturity="SUPERVISED",
        ))
        assert len(first) == 1
        assert second == []

    def test_extract_from_prompt_before_truncation(self, extractor):
        extractor.llm.generate = AsyncMock(
            return_value='[{"fact": "Budget is 20k", "category": "exact_value"}]'
        )
        rows = run(extractor.extract_from_prompt_before_truncation(
            prompt="User said: Budget is 20k",
            execution_id="exec-2",
        ))
        assert len(rows) == 1
        assert rows[0].fact_text == "Budget is 20k"
        assert rows[0].extraction_source == "pre_compress"

    def test_empty_prompt_returns_no_rows(self, extractor):
        assert run(extractor.extract_from_prompt_before_truncation(prompt="")) == []


class TestPureHelpers:
    def test_content_hash_deterministic(self):
        a = compute_content_hash("ws", "same fact")
        b = compute_content_hash("ws", "same fact")
        c = compute_content_hash("ws", "different")
        assert a == b
        assert a != c

    def test_clamp_and_confidence_coercion(self):
        assert _clamp(1.5, 0.0, 1.0) == 1.0
        assert _clamp(-1, 0, 1) == 0.0
        assert _clamp(0.5, 0, 1) == 0.5
        assert _coerce_confidence("high") == 0.8  # non-numeric → default
        assert _coerce_confidence(None) == 0.8
        assert _coerce_confidence(1.2) == 1.0
        assert _coerce_confidence(0.3) == 0.3

    def test_ttl_set_membership(self):
        s = tfe._TTLSet()
        s.add("k1")
        assert "k1" in s
        assert "missing" not in s
