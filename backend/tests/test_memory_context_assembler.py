"""
Memory Context Assembler tests — the P0 unified turn-time retrieval block.

All external legs (GraphRAG, comm search, episodes, turn facts) are patched;
these tests pin the contract: fault isolation, budgets, flag gating, block
rendering.
"""

import os
os.environ.setdefault("TESTING", "1")

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import core.memory_context_assembler as mca
from core.memory_context_assembler import (
    assemble_memory_context,
    assembly_enabled,
    _bounded_lines,
)


def test_flag_defaults_on(monkeypatch):
    monkeypatch.delenv("MEMORY_CONTEXT_ASSEMBLY", raising=False)
    assert assembly_enabled() is True


def test_flag_off(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "false")
    assert assembly_enabled() is False


def test_bounded_lines_respects_cap():
    lines = ["x" * 100 for _ in range(10)]
    out = _bounded_lines(lines, cap=250)
    # Each line costs 101 chars ("- " + 100); cap 250 → 2 lines fit
    assert out.count("\n") == 1


def test_bounded_lines_skips_empty():
    assert _bounded_lines(["", "ok"], cap=100) == "- ok"


@pytest.mark.asyncio
async def test_all_legs_rendered(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def fake_graph(message, ws, tn):
        return "ACME Fabrication — raised inquiry about press brake"

    async def fake_comms(message, ws):
        return ["[slack 2026-08-19] Sarah needs a quote on the press brake"]

    async def fake_episodes(message, agent):
        return ["Created quote Q-2024-0142 for ACME (outcome: success)"]

    async def fake_facts(message, ws):
        return ["ACME Fab budget is around $80K"]

    with patch.object(mca, "_graph_leg", fake_graph), \
         patch.object(mca, "_comms_leg", fake_comms), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", fake_episodes), \
         patch.object(mca, "_facts_leg", fake_facts):
        block = await assemble_memory_context("what did ACME ask about?")

    assert block is not None
    assert block.startswith("RELEVANT MEMORY")
    for expected in (
        "KNOWLEDGE GRAPH CONTEXT",
        "ACME Fabrication",
        "RELATED CONVERSATIONS",
        "RELEVANT PAST EPISODES",
        "DURABLE FACTS",
        "$80K",
    ):
        assert expected in block, f"missing {expected!r}"


@pytest.mark.asyncio
async def test_leg_failure_isolated(monkeypatch):
    """A raising leg yields an empty block, others still render."""
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def boom(*a, **k):
        raise RuntimeError("store down")

    async def fine_graph(message, ws, tn):
        return "graph context here"

    with patch.object(mca, "_graph_leg", fine_graph), \
         patch.object(mca, "_comms_leg", boom), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", boom), \
         patch.object(mca, "_facts_leg", boom):
        block = await assemble_memory_context("anything")

    assert block is not None
    assert "graph context here" in block
    assert "RELATED CONVERSATIONS" not in block


@pytest.mark.asyncio
async def test_leg_timeout_isolated(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def slow_graph(message, ws, tn):
        await asyncio.sleep(5)
        return "too late"

    async def fast_facts(message, ws):
        return ["a durable fact"]

    with patch.object(mca, "_graph_leg", slow_graph), \
         patch.object(mca, "_comms_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", fast_facts):
        block = await asyncio.wait_for(
            assemble_memory_context("anything"), timeout=3
        )

    assert block is not None
    assert "a durable fact" in block
    assert "too late" not in block


@pytest.mark.asyncio
async def test_no_memory_returns_none(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")
    with patch.object(mca, "_graph_leg", AsyncMock(return_value="")), \
         patch.object(mca, "_comms_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])):
        assert await assemble_memory_context("hello") is None


@pytest.mark.asyncio
async def test_empty_message_short_circuits():
    assert await assemble_memory_context("   ") is None


@pytest.mark.asyncio
async def test_total_budget_enforced(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def huge_graph(message, ws, tn):
        return "G" * 50_000

    with patch.object(mca, "_graph_leg", huge_graph), \
         patch.object(mca, "_comms_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])):
        block = await assemble_memory_context("anything")

    # Graph leg caps at 3200 and total caps at 10k — either way, well short of 50k
    assert len(block) < mca.TOTAL_CHAR_BUDGET + 200


# --------------------------------------------------------------------------- #
# Universal ingestion (shape-based comm routing) + integration-records leg
# --------------------------------------------------------------------------- #

class TestCommunicationRecordClassifier:
    def test_known_comm_integration_always_routes(self):
        from core.ingestion_pipeline import IngestionPipelineService
        for app in ("telegram", "whatsapp", "slack", "gmail", "outlook"):
            assert IngestionPipelineService._is_communication_record(app, {}) is True

    def test_message_shaped_record_from_unknown_integration_routes(self):
        from core.ingestion_pipeline import IngestionPipelineService
        record = {"content": "Sarah needs a quote", "sender": "sarah@acme.com", "timestamp": "2026-08-19"}
        assert IngestionPipelineService._is_communication_record("some_new_app", record) is True

    def test_non_conversational_record_does_not_route(self):
        from core.ingestion_pipeline import IngestionPipelineService
        # Product/invoice-like record: has text but no actor/timestamp shape
        record = {"name": "Press Brake", "price": 84500.0, "sku": "BP-50T"}
        assert IngestionPipelineService._is_communication_record("zoho_inventory", record) is False

    def test_text_without_actor_or_time_does_not_route(self):
        from core.ingestion_pipeline import IngestionPipelineService
        assert IngestionPipelineService._is_communication_record("x", {"text": "just text"}) is False

    def test_non_dict_is_safe(self):
        from core.ingestion_pipeline import IngestionPipelineService
        assert IngestionPipelineService._is_communication_record("x", "not a dict") is False


@pytest.mark.asyncio
async def test_integration_records_leg_rendered(monkeypatch):
    monkeypatch.setenv("MEMORY_CONTEXT_ASSEMBLY", "true")

    async def fake_integration(message, ws):
        return ["[zoho_crm] ACME Fabrication — raised inquiry about press brake"]

    with patch.object(mca, "_graph_leg", AsyncMock(return_value="")), \
         patch.object(mca, "_comms_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_integration_records_leg", fake_integration), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])):
        block = await assemble_memory_context("what did ACME ask about?")

    assert block is not None
    assert "RELATED INTEGRATION RECORDS" in block
    assert "ACME Fabrication" in block
