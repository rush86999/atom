# -*- coding: utf-8 -*-
"""
TDD tests for FTS5 lexical session search (gap-analysis #6).

Covers:
- happy-path search returns ranked results
- exact-match queries surface error strings / IDs that semantic recall misses
- trivial queries (<3 chars) are skipped
- special characters in the query don't crash FTS5 syntax
- execution_id scoping filter
- graceful degradation when the FTS table is missing
- _query_safe_tokens sanitization
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Base
from core import turn_fact_extractor as tfe_mod
from core.turn_fact_extractor import (
    _query_safe_tokens,
    search_reasoning_steps_lexical,
)
from core.models import AgentReasoningStep, AgentExecution


@pytest.fixture()
def fts_db():
    """In-memory SQLite with the FTS5 virtual table + triggers set up."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine, checkfirst=True)
    # Create the FTS5 table + triggers (mirrors the migration)
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE VIRTUAL TABLE agent_reasoning_steps_fts USING fts5("
            "thought, observation, content='agent_reasoning_steps', content_rowid='rowid')"
        ))
        conn.execute(text(
            "CREATE TRIGGER agent_reasoning_steps_ai AFTER INSERT ON agent_reasoning_steps BEGIN "
            "INSERT INTO agent_reasoning_steps_fts(rowid, thought, observation) "
            "VALUES (new.rowid, COALESCE(new.thought,''), COALESCE(new.observation,'')); END"
        ))
        conn.commit()
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with patch.object(tfe_mod, "SessionLocal", Session):
        yield Session
    engine.dispose()


def _seed_steps(session_factory, steps):
    """Insert reasoning steps (the trigger auto-indexes them into FTS5)."""
    with session_factory() as db:
        # AgentExecution FK is nullable but execution_id column is not — create a stub
        for i, (thought, obs, exec_id) in enumerate(steps):
            db.add(AgentReasoningStep(
                id=f"step-{i}",
                execution_id=exec_id,
                step_number=i,
                step_type="thought",
                thought=thought,
                observation=obs,
                confidence=0.8,
            ))
        db.commit()


class TestFTSSearch:
    def test_happy_path_returns_results(self, fts_db):
        _seed_steps(fts_db, [
            ("We must use Stripe for payments", "Stripe connected", "exec-A"),
            ("Checking the weather", "Sunny", "exec-B"),
            ("Stripe webhook returned 402", "Payment required error", "exec-A"),
        ])
        results = search_reasoning_steps_lexical("ws", "Stripe")
        assert len(results) >= 2
        # Both Stripe-related steps should surface
        thoughts = " ".join(r["thought"] for r in results)
        assert "Stripe" in thoughts

    def test_exact_error_string_match(self, fts_db):
        """The key use case: semantic recall misses exact error tokens."""
        _seed_steps(fts_db, [
            ("Calling the API", "Error: ValueError: invalid literal at line 42", "exec-E"),
            ("Another step", "All good", "exec-E"),
        ])
        results = search_reasoning_steps_lexical("ws", "ValueError line 42")
        assert len(results) >= 1
        assert "ValueError" in results[0]["observation"]

    def test_trivial_query_skipped(self, fts_db):
        _seed_steps(fts_db, [("thinking about x", "obs", "exec")])
        assert search_reasoning_steps_lexical("ws", "hi") == []
        assert search_reasoning_steps_lexical("ws", "") == []
        assert search_reasoning_steps_lexical("ws", "ab") == []

    def test_special_chars_dont_crash_fts(self, fts_db):
        _seed_steps(fts_db, [("step", "ConnectionError: (os error 10061)", "exec")])
        # Parentheses, colons, parens would normally break FTS5 syntax —
        # _query_safe_tokens strips them.
        results = search_reasoning_steps_lexical("ws", "(os error) 10061:")
        assert isinstance(results, list)  # didn't crash

    def test_execution_id_scope(self, fts_db):
        _seed_steps(fts_db, [
            ("Stripe setup", "ok", "exec-1"),
            ("Stripe webhook", "ok", "exec-2"),
        ])
        scoped = search_reasoning_steps_lexical("ws", "Stripe", execution_id="exec-1")
        assert all(r["execution_id"] == "exec-1" for r in scoped)
        assert len(scoped) == 1

    def test_graceful_when_fts_table_missing(self):
        """If the FTS table doesn't exist (pre-migration), returns []."""
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)  # NO fts table
        Session = sessionmaker(bind=engine)
        with patch.object(tfe_mod, "SessionLocal", Session):
            results = search_reasoning_steps_lexical("ws", "anything searchable")
        assert results == []

    def test_limit_respected(self, fts_db):
        _seed_steps(fts_db, [
            (f"Stripe note {i}", "obs", "exec") for i in range(10)
        ])
        results = search_reasoning_steps_lexical("ws", "Stripe", limit=3)
        assert len(results) <= 3


class TestQuerySafeTokens:
    def test_strips_special_chars(self):
        assert _query_safe_tokens("hello (world)! 42") == ["hello", "world", "42"]

    def test_lowercases(self):
        assert _query_safe_tokens("Stripe STRIPE") == ["stripe", "stripe"]

    def test_drops_single_chars(self):
        assert _query_safe_tokens("a bc") == ["bc"]

    def test_empty(self):
        assert _query_safe_tokens("") == []
        assert _query_safe_tokens("!@#") == []
