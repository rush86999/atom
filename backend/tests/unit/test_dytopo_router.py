"""
Unit tests for core.dytopo_router.DyTopoRouter (single-tenant upstream port).

Same surface as the SaaS tests, minus the tenant_id threading case
(single-tenant: there is no tenant_id to thread).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from core import dytopo_router as dytopo_module
from core.dytopo_router import DyTopoRouter


@pytest.fixture
def fake_llm():
    llm = Mock()
    llm.generate_embedding = AsyncMock()
    llm.generate_embeddings_batch = AsyncMock()
    llm.generate_structured_response = AsyncMock()
    return llm


@pytest.fixture
def fake_db():
    return Mock()


@pytest.fixture
def router(fake_db, fake_llm, monkeypatch):
    monkeypatch.setattr(dytopo_module, "DYTOPO_ROUTING_ENABLED", True)
    return DyTopoRouter(db=fake_db, llm=fake_llm)


def _make_agent(agent_id: str, name: str | None = None):
    a = Mock()
    a.id = agent_id
    a.name = name or agent_id
    a.category = "specialist"
    a.configuration = {}
    return a


def _embedding_from_text(text: str, dim: int = 16) -> list[float]:
    vec = np.zeros(dim, dtype=float)
    for i, ch in enumerate(text):
        vec[i % dim] += ord(ch) % 97
    norm = np.linalg.norm(vec)
    if norm == 0:
        vec[0] = 1.0
        norm = 1.0
    return (vec / norm).tolist()


@pytest.mark.asyncio
async def test_dag_enforcement_no_cycles(router, fake_llm):
    agents = [_make_agent("A"), _make_agent("B"), _make_agent("C")]

    async def fake_extract(agent, observation):
        return (f"need:{agent.id}", f"offer:{agent.id}")

    router.extract_descriptor = fake_extract

    async def fake_batch(texts, **kwargs):
        return [_embedding_from_text(t) for t in texts]

    fake_llm.generate_embeddings_batch = fake_batch

    result = await router.compute_round_topology(
        execution_id="exec-1", specialists=agents, prior_state=None
    )
    adjacency = result["adjacency"]
    import networkx as nx

    g = nx.DiGraph()
    for node in ["A", "B", "C"]:
        g.add_node(node)
    for src, dsts in adjacency.items():
        for d in dsts:
            g.add_edge(src, d)
    assert nx.is_directed_acyclic_graph(g), f"cycle in {adjacency}"


@pytest.mark.asyncio
async def test_out_degree_cap_respected(router, fake_llm):
    agents = [_make_agent(f"A{i}") for i in range(8)]

    async def fake_extract(agent, observation):
        return (f"need from {agent.id}", f"offer from {agent.id}")

    router.extract_descriptor = fake_extract

    async def fake_batch(texts, **kwargs):
        v = _embedding_from_text("shared")
        return [v for _ in texts]

    fake_llm.generate_embeddings_batch = fake_batch

    result = await router.compute_round_topology(
        execution_id="exec-2", specialists=agents, prior_state=None
    )
    adjacency = result["adjacency"]
    max_cap = DyTopoRouter.MAX_OUT_DEGREE
    for src, dsts in adjacency.items():
        assert len(dsts) <= max_cap, f"out-degree {len(dsts)} > {max_cap} for {src}"


@pytest.mark.asyncio
async def test_threshold_gating_excludes_low_similarity(router, fake_llm):
    agents = [_make_agent("X1"), _make_agent("X2"), _make_agent("Y1"), _make_agent("Y2")]

    async def fake_extract(agent, observation):
        if agent.id.startswith("X"):
            return ("cats cats", "cats cats")
        return ("zzz qqq", "zzz qqq")

    router.extract_descriptor = fake_extract

    async def fake_batch(texts, **kwargs):
        return [_embedding_from_text(t) for t in texts]

    fake_llm.generate_embeddings_batch = fake_batch

    result = await router.compute_round_topology(
        execution_id="exec-3", specialists=agents, prior_state=None
    )
    adjacency = result["adjacency"]
    x_ids = {"X1", "X2"}
    y_ids = {"Y1", "Y2"}
    for src, dsts in adjacency.items():
        if src in x_ids:
            assert all(d in x_ids for d in dsts), f"low-sim edge: {src} -> {dsts}"
        if src in y_ids:
            assert all(d in y_ids for d in dsts), f"low-sim edge: {src} -> {dsts}"


@pytest.mark.asyncio
async def test_descriptor_extraction_shape(router, fake_llm):
    fake_llm.generate_structured_response = AsyncMock(
        return_value={"query_need": "I need sales numbers", "key_offer": "I have Q3 revenue"}
    )
    q, k = await router.extract_descriptor(_make_agent("A"), "Sales analysis task")
    assert isinstance(q, str) and isinstance(k, str)
    assert q.strip() and k.strip()


@pytest.mark.asyncio
async def test_flag_disabled_is_noop(fake_db, fake_llm, monkeypatch):
    monkeypatch.setattr(dytopo_module, "DYTOPO_ROUTING_ENABLED", False)
    router = DyTopoRouter(db=fake_db, llm=fake_llm)
    result = await router.compute_round_topology(
        execution_id="exec-off", specialists=[_make_agent("A")], prior_state=None
    )
    assert result["adjacency"] == {}
    assert result.get("enabled") is False
