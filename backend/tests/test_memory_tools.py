# -*- coding: utf-8 -*-
"""
TDD tests for the agent-callable memory tools (Phase: gap-analysis #4).

Covers:
- memory_remember: happy path, invalid category, empty fact, dedup reuse
- memory_forget: by fact_id, by substring, deletion-safety refusal, no match
- Registry registration (metadata, complexity, maturity)
- Backing helpers never raise
"""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Base
from core import turn_fact_extractor as tfe_mod
from core.turn_fact_extractor import (
    forget_fact_explicit,
    remember_fact_explicit,
)
from tools.memory_tool import (
    memory_forget,
    memory_remember,
    register_memory_tool,
)


@pytest.fixture()
def memory_db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with patch.object(tfe_mod, "SessionLocal", Session):
        yield Session
    engine.dispose()


# ===========================================================================
# memory_remember
# ===========================================================================
class TestMemoryRemember:
    @pytest.mark.asyncio
    async def test_happy_path(self, memory_db):
        result = await memory_remember(
            fact_text="We use Stripe for all payments",
            category="hard_constraint",
            domain="finance",
            workspace_id="ws-tools",
        )
        assert result["success"] is True
        assert result["fact_id"]
        assert result["category"] == "hard_constraint"

    @pytest.mark.asyncio
    async def test_invalid_category_rejected(self, memory_db):
        result = await memory_remember(
            fact_text="x",
            category="bogus_category",
            workspace_id="ws-tools",
        )
        assert result["success"] is False
        assert "exact_value" in result["message"]

    @pytest.mark.asyncio
    async def test_empty_fact_rejected(self, memory_db):
        result = await memory_remember(
            fact_text="   ",
            category="exact_value",
            workspace_id="ws-tools",
        )
        assert result["success"] is False
        assert "required" in result["message"]

    @pytest.mark.asyncio
    async def test_dedup_reuses_existing(self, memory_db):
        first = await memory_remember(
            fact_text="must use Stripe",
            category="hard_constraint",
            workspace_id="ws-dedup",
            confidence=0.9,
        )
        second = await memory_remember(
            fact_text="must use Stripe",
            category="hard_constraint",
            workspace_id="ws-dedup",
            confidence=0.9,
        )
        assert first["success"] and second["success"]
        # Same row — EWMA-bumped, not duplicated
        assert first["fact_id"] == second["fact_id"]

    @pytest.mark.asyncio
    async def test_default_workspace_when_omitted(self, memory_db):
        # Should not blow up when workspace_id is absent (uses "default")
        result = await memory_remember(
            fact_text="MRR is $40K",
            category="exact_value",
        )
        assert result["success"] is True


# ===========================================================================
# memory_forget
# ===========================================================================
class TestMemoryForget:
    @pytest.mark.asyncio
    async def test_forget_by_id(self, memory_db):
        remembered = await memory_remember(
            fact_text="old launch date is March 14",
            category="exact_value",
            workspace_id="ws-forget",
        )
        result = await memory_forget(
            fact_id=remembered["fact_id"], workspace_id="ws-forget"
        )
        assert result["success"] is True
        assert result["invalidated_count"] == 1

    @pytest.mark.asyncio
    async def test_forget_by_substring(self, memory_db):
        await memory_remember(
            fact_text="API key expires on Friday",
            category="exact_value",
            workspace_id="ws-sub",
        )
        await memory_remember(
            fact_text="The API key must rotate quarterly",
            category="hard_constraint",
            workspace_id="ws-sub",
        )
        result = await memory_forget(
            fact_text_contains="API key", workspace_id="ws-sub"
        )
        assert result["success"] is True
        assert result["invalidated_count"] == 2

    @pytest.mark.asyncio
    async def test_deletion_safety_refuses_blank(self, memory_db):
        result = await memory_forget(workspace_id="ws-x")
        assert result["success"] is False
        assert result["invalidated_count"] == 0
        assert "specific target" in result["message"]

    @pytest.mark.asyncio
    async def test_no_match(self, memory_db):
        result = await memory_forget(
            fact_text_contains="nonexistent junk xyz", workspace_id="ws-empty"
        )
        assert result["success"] is False
        assert result["invalidated_count"] == 0

    @pytest.mark.asyncio
    async def test_invalidated_facts_are_soft_deleted(self, memory_db):
        from core.models import TurnFact

        remembered = await memory_remember(
            fact_text="temporary fact 12345",
            category="exact_value",
            workspace_id="ws-soft",
        )
        await memory_forget(fact_id=remembered["fact_id"], workspace_id="ws-soft")

        with memory_db() as db:
            row = db.get(TurnFact, remembered["fact_id"])
            assert row.status == "invalidated"
            assert row.superseded_at is not None
            # Still present (audit history preserved)
            assert row.fact_text == "temporary fact 12345"


# ===========================================================================
# Backing helpers never raise
# ===========================================================================
class TestBackingHelpers:
    def test_remember_fact_explicit_bad_category(self, memory_db):
        assert remember_fact_explicit(
            workspace_id="ws", fact_text="x", category="nope"
        ) is None

    def test_remember_fact_explicit_empty(self, memory_db):
        assert remember_fact_explicit(
            workspace_id="ws", fact_text="", category="exact_value"
        ) is None

    def test_forget_fact_explicit_no_target(self, memory_db):
        assert forget_fact_explicit(workspace_id="ws") == 0

    def test_forget_fact_explicit_empty_workspace(self, memory_db):
        assert forget_fact_explicit(workspace_id="", fact_id="x") == 0


# ===========================================================================
# Registration
# ===========================================================================
class TestRegistration:
    def test_register_memory_tool(self):
        from tools.registry import ToolRegistry

        reg = ToolRegistry()
        # Don't run full initialize (it pulls in browser/device deps); just
        # register our two tools directly.
        register_memory_tool(reg)

        remember = reg.get("memory_remember")
        forget = reg.get("memory_forget")
        assert remember is not None
        assert forget is not None
        assert remember.category == "memory"
        assert remember.complexity == 2
        assert remember.maturity_required == "INTERN"
        assert forget.complexity == 3
        assert forget.maturity_required == "SUPERVISED"
