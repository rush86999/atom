# -*- coding: utf-8 -*-
"""Coverage wave 85 — core/reflection_service (never-wave-tested).

Covers the self-critique reflection pool:
- add_critique: table-unavailable -> False; success -> embedding generated,
  record (id/tenant/timestamp/vector) added to Lance table; exception -> False.
- get_relevant_critiques: table-unavailable -> []; success -> search chain
  (query-vector, agent+tenant filter, limit) and pandas rows mapped to dicts;
  exception -> [].

LanceDBService + EmbeddingService fully mocked (no network, zero LLM spend).
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

import core.reflection_service as rs
from core.reflection_service import ReflectionService


def _table_mock(results_df=None):
    search = MagicMock()
    if results_df is not None:
        search.return_value.where.return_value.limit.return_value.to_pandas.return_value = results_df
    else:
        search.return_value.where.return_value.limit.return_value.to_pandas.return_value = None
    table = MagicMock()
    table.search = search
    return table


def _service(tenant_id="t1", table=None, embedding=None):
    with patch.object(rs, "LanceDBService") as lancedb_cls, \
         patch.object(rs, "EmbeddingService") as emb_cls:
        lancedb_cls.return_value.get_or_create_reflection_pool_table.return_value = table
        emb_cls.return_value.generate_embedding = embedding or AsyncMock(return_value=[0.1, 0.2])
        return ReflectionService(tenant_id=tenant_id), lancedb_cls, emb_cls


class TestAddCritique:
    def test_table_unavailable_returns_false(self):
        svc, _, _ = _service(table=None)
        result = asyncio.run(svc.add_critique("agent-1", "intent", "act", "outcome", "crit"))
        assert result is False

    def test_success_adds_embedded_record(self):
        table = _table_mock()
        svc, lancedb_cls, emb_cls = _service(table=table)
        result = asyncio.run(svc.add_critique(
            "agent-1", "close deal", "sent email", "awaiting reply", "follow up sooner"
        ))
        assert result is True
        table.add.assert_called_once()
        record = table.add.call_args.args[0][0]
        assert record["agent_id"] == "agent-1"
        assert record["tenant_id"] == "t1"
        assert record["intent"] == "close deal"
        assert record["action_taken"] == "sent email"
        assert record["outcome_state"] == "awaiting reply"
        assert record["critique"] == "follow up sooner"
        assert record["vector"] == [0.1, 0.2]
        assert record["id"]
        assert "Intent: close deal" in emb_cls.return_value.generate_embedding.call_args.args[0]
        # timestamp is ISO-formatted aware UTC
        parsed = datetime.fromisoformat(record["timestamp"])
        assert parsed.tzinfo is not None

    def test_exception_returns_false(self):
        table = _table_mock()
        svc, _, _ = _service(table=table, embedding=AsyncMock(side_effect=RuntimeError("embed down")))
        result = asyncio.run(svc.add_critique("agent-1", "i", "a", "o", "c"))
        assert result is False
        table.add.assert_not_called()


class TestGetRelevantCritiques:
    def _df(self):
        return pd.DataFrame([
            {"intent": "close deal", "action_taken": "email", "outcome_state": "won",
             "critique": "follow up sooner", "timestamp": "2026-01-01T00:00:00+00:00"},
            {"intent": "close deal", "action_taken": "call", "outcome_state": "lost",
             "critique": "qualify earlier", "timestamp": "2026-01-02T00:00:00+00:00"},
        ])

    def test_table_unavailable_returns_empty(self):
        svc, _, _ = _service(table=None)
        assert asyncio.run(svc.get_relevant_critiques("agent-1", "close deal")) == []

    def test_success_maps_rows(self):
        table = _table_mock(results_df=self._df())
        svc, _, emb_cls = _service(table=table)
        critiques = asyncio.run(svc.get_relevant_critiques("agent-1", "close deal", limit=3))
        assert len(critiques) == 2
        first = critiques[0]
        assert first["intent"] == "close deal"
        assert first["critique"] == "follow up sooner"
        assert first["timestamp"] == "2026-01-01T00:00:00+00:00"
        # query vector embedded from current intent
        emb_cls.return_value.generate_embedding.assert_awaited_once_with("close deal")
        # filter isolates the agent + tenant
        table.search.assert_called_once()
        where_call = table.search.return_value.where
        filter_str = where_call.call_args.args[0]
        assert "agent_id == 'agent-1'" in filter_str
        assert "tenant_id == 't1'" in filter_str
        where_call.return_value.limit.assert_called_once_with(3)

    def test_exception_returns_empty(self):
        table = _table_mock()
        table.search.side_effect = RuntimeError("lance down")
        svc, _, _ = _service(table=table)
        assert asyncio.run(svc.get_relevant_critiques("agent-1", "intent")) == []
