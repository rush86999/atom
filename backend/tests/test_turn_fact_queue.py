# -*- coding: utf-8 -*-
"""
TDD tests for the ExtractionQueue (Phase 5).

Verifies:
- enqueue is non-blocking + returns False when flag disabled
- worker drains items via the extractor (mocked)
- queue full → drop + counter increment, never raises
- worker never dies on exception
"""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import turn_fact_queue as qmod
from core.turn_fact_queue import ExtractionQueue, get_extraction_queue


@pytest.fixture()
def queue():
    return ExtractionQueue(maxsize=3)


class TestEnqueue:
    def test_disabled_flag_returns_false(self, queue):
        with patch.object(qmod, "TURN_FACT_PRE_COMPRESS_ENABLED", False):
            assert queue.enqueue(prompt="x", workspace_id="ws") is False

    def test_empty_prompt_returns_false(self, queue):
        assert queue.enqueue(prompt="", workspace_id="ws") is False

    def test_happy_path_queues(self, queue):
        assert queue.enqueue(prompt="x", workspace_id="ws") is True
        assert queue._q.qsize() == 1

    def test_full_queue_drops(self, queue):
        for i in range(3):
            assert queue.enqueue(prompt=f"p{i}", workspace_id="ws") is True
        # 4th must be dropped, not raise
        assert queue.enqueue(prompt="p4", workspace_id="ws") is False
        assert queue._dropped_count == 1


class TestWorker:
    @pytest.mark.asyncio
    async def test_drain_once_processes_item(self, queue):
        with patch.object(qmod, "get_turn_fact_extractor") as get_ex:
            ex = MagicMock()
            ex.extract_from_prompt_before_truncation = AsyncMock(return_value=[])
            get_ex.return_value = ex
            queue.enqueue(prompt="must use Stripe", workspace_id="ws")
            n = await queue.drain_once()
            assert n == 0  # extractor returned []
            assert queue._drained_count == 1
            ex.extract_from_prompt_before_truncation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_drain_once_empty_queue(self, queue):
        n = await queue.drain_once()
        assert n == 0

    @pytest.mark.asyncio
    async def test_worker_survives_exception(self, queue):
        with patch.object(qmod, "get_turn_fact_extractor") as get_ex:
            ex = MagicMock()
            ex.extract_from_prompt_before_truncation = AsyncMock(
                side_effect=RuntimeError("boom")
            )
            get_ex.return_value = ex
            queue.enqueue(prompt="x", workspace_id="ws")
            n = await queue.drain_once()  # must not raise
            assert n == 0


class TestSingleton:
    def test_get_extraction_queue_returns_same_instance(self):
        a = get_extraction_queue()
        b = get_extraction_queue()
        assert a is b
