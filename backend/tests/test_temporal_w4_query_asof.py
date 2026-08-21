"""
W4 — query-side time travel: GraphRAGEngine.local_search/query/get_context_for_ai
with ``as_of``.

RED: `local_search` accepts no ``as_of`` kwarg → TypeError.

Contracts pinned here:
  - as_of prunes edges that were not alive at that instant from BOTH the
    recursive CTE traversal join and the relationship listing:
    (valid_from IS NULL OR valid_from <= as_of) AND
    (invalid_at IS NULL OR invalid_at > as_of). Nodes carry no bi-temporal
    fields (only edges per P2.2) so they are not time-filtered.
  - None = byte-identical legacy behavior (``e.invalid_at IS NULL`` only) —
    verified by a control against the same DB: a not-yet-valid edge (future
    valid_from) is reachable WITHOUT as_of but unreachable WITH as_of.
  - as_of is recorded in the result dict ("as_of" ISO string) when used.
  - the in-loop multi-hop expansion receives the same as_of.
  - ``query``/``get_context_for_ai`` thread as_of into local mode; global
    mode ignores it (communities carry no validity interval to filter on).
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.graphrag_engine import GraphRAGEngine
from core.models import GraphEdge, GraphNode

UTC = timezone.utc


def _utc(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)


def _no_embedding(*args, **kwargs):
    raise RuntimeError("no embedding service in test")


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def engine(db):
    """Engine wired to the fixture DB with vector/embedding legs disabled."""
    eng = GraphRAGEngine(workspace_id="ws-1", tenant_id="default")
    eng.llm_service = SimpleNamespace(generate_embedding=_no_embedding)
    patches = [
        patch("core.graphrag_engine.get_db_session", return_value=contextual(db)),
        patch("core.lancedb_handler.get_lancedb_handler", return_value=_EmptyHandler()),
    ]
    for p in patches:
        p.start()
    yield eng
    for p in patches:
        p.stop()


def contextual(session):
    """Context-manager wrapper: ``with get_db_session() as s`` → the fixture
    session (graphrag_engine calls it in a ``with`` block)."""

    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    return _Ctx()


class _EmptyHandler:
    def search(self, table, query, limit=5, **kwargs):
        return []


def _seed(db):
    _node(db, "n-alpha", "Alpha", _utc(2026, 1, 1))
    _node(db, "n-beta", "Beta", _utc(2026, 1, 1))
    _node(db, "n-gamma", "Gamma", _utc(2026, 7, 1))
    _node(db, "n-delta", "Delta", _utc(2026, 1, 1))
    _edge(db, "e-ab", "n-alpha", "n-beta", _utc(2026, 1, 1))                      # alive always
    _edge(db, "e-ac", "n-alpha", "n-gamma", _utc(2026, 7, 1))                     # born later
    _edge(db, "e-ad", "n-alpha", "n-delta", _utc(2026, 1, 1), _utc(2026, 5, 1))   # invalidated
    db.commit()


def _node(db, nid: str, name: str, created_at):
    db.add(GraphNode(id=nid, workspace_id="ws-1", name=name, type="company",
                     created_at=created_at))


def _edge(db, eid: str, src: str, tgt: str, valid_from, invalid_at=None):
    db.add(GraphEdge(
        id=eid, workspace_id="ws-1", source_node_id=src, target_node_id=tgt,
        relationship_type="related_to", valid_from=valid_from, invalid_at=invalid_at,
    ))


def _names(entities):
    return {e["name"] for e in entities}


def _rel_types(relationships):
    return {r["type"] for r in relationships}


class TestLocalSearchAsOf:
    _KW = {"tenant_id": "default"}

    def _search(self, engine, query="alpha", **kw):
        return engine.local_search("ws-1", self._KW["tenant_id"], query, **kw)

    def test_as_of_excludes_not_yet_alive_and_invalidated_edges(self, db, engine):
        _seed(db)
        result = self._search(engine, as_of=_utc(2026, 6, 1))
        assert _names(result["entities"]) == {"Alpha", "Beta"}
        assert _rel_types(result["relationships"]) == {"related_to"}
        # Gamma (edge born Jul) and Delta (edge invalidated May) unreachable

    def test_as_of_before_invalidation_includes_edge(self, db, engine):
        _seed(db)
        result = self._search(engine, as_of=_utc(2026, 3, 1))
        assert _names(result["entities"]) == {"Alpha", "Beta", "Delta"}
        # e-ad still alive in March; e-ac (July) not yet born

    def test_no_as_of_is_legacy(self, db, engine):
        _seed(db)
        result = self._search(engine)
        # legacy = invalid_at IS NULL only: Gamma (future valid_from is NOT
        # filtered) reachable; Delta (invalidated) not.
        assert _names(result["entities"]) == {"Alpha", "Beta", "Gamma"}
        assert _rel_types(result["relationships"]) == {"related_to"}

    def test_as_of_recorded_in_result(self, db, engine):
        _seed(db)
        result = self._search(engine, as_of=_utc(2026, 6, 1))
        assert result["as_of"] == _utc(2026, 6, 1).isoformat()
        legacy = self._search(engine)
        assert "as_of" not in legacy

    def test_as_of_reaches_loop_expansion(self, db, engine):
        _seed(db)
        calls = []

        class _Spy:
            def expand_sql(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(paths=[])

        with patch("core.graphrag.multi_hop_expansion.get_sql_expander", return_value=_Spy()):
            self._search(engine, as_of=_utc(2026, 6, 1))
        assert len(calls) == 1
        assert calls[0]["as_of"] == _utc(2026, 6, 1)

        calls.clear()
        with patch("core.graphrag.multi_hop_expansion.get_sql_expander", return_value=_Spy()):
            self._search(engine)
        assert len(calls) == 1
        assert calls[0]["as_of"] is None


class TestQueryAndContextAsOf:
    """These mock the search legs on purpose: ``query`` runs local_search in
    a worker thread (embedding guard), and SQLite sessions are not
    thread-safe — a real seeded run would raise cross-thread errors, not
    exercise the threading. The sync class above already proves real as_of
    filtering; here we pin that the cutoff REACHES the query surface."""

    @pytest.mark.asyncio
    async def test_query_threads_as_of_into_local_mode(self, db, engine):
        canned = {
            "mode": "local", "entities": [], "relationships": [],
            "as_of": _utc(2026, 6, 1).isoformat(), "count": 0,
        }
        with patch.object(engine, "local_search", return_value=canned) as mock_ls:
            result = await engine.query("ws-1", "default", "alpha",
                                        as_of=_utc(2026, 6, 1))
        assert result["as_of"] == _utc(2026, 6, 1).isoformat()
        assert mock_ls.call_args.args == (
            "ws-1", "default", "alpha", 2, None, False, _utc(2026, 6, 1),
        )

    @pytest.mark.asyncio
    async def test_query_global_mode_ignores_as_of(self, db, engine):
        with patch.object(
            engine, "global_search",
            new=AsyncMock(return_value={"mode": "global", "summaries": []}),
        ) as mock_gs:
            result = await engine.query("ws-1", "default", "overview of everything",
                                        mode="global", as_of=_utc(2026, 6, 1))
        assert result["mode"] == "global"
        assert "as_of" not in result
        mock_gs.assert_awaited_once()
        assert mock_gs.call_args.args == ("ws-1", "default", "overview of everything")

    @pytest.mark.asyncio
    async def test_get_context_for_ai_threads_as_of(self, db, engine):
        canned = {
            "mode": "local",
            "entities": [
                {"id": "n-alpha", "name": "Alpha", "type": "company", "description": ""},
                {"id": "n-beta", "name": "Beta", "type": "company", "description": ""},
            ],
            "relationships": [],
        }
        with patch.object(
            engine, "query",
            new=AsyncMock(return_value=canned),
        ) as mock_q:
            context = await engine.get_context_for_ai(
                "ws-1", "default", "alpha", as_of=_utc(2026, 6, 1),
            )
        assert "Beta" in context
        mock_q.assert_awaited_once()
        assert mock_q.call_args.kwargs.get("as_of") == _utc(2026, 6, 1)