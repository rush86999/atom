"""
W7 — global-search time travel: community snapshot history.

RED: `global_search` accepts no ``as_of`` (TypeError), and re-running
community detection wipes the previous generation outright — there is no
history to travel to. Both are pinned here via the new
``GraphCommunitySnapshot`` archive.

Contracts pinned here:
  - archiving: when `_persist_communities` replaces a workspace's
    communities, the outgoing generation is copied into
    graph_community_snapshots with valid_from = its created_at and
    invalid_at = the replacement instant; node memberships ride along as a
    JSON id array; the incoming generation is untouched in graph_communities.
  - repeated runs chain intervals (gen1: [t0, t1), gen2: [t1, t2), ...);
    the live table always holds exactly the newest generation.
  - global_search(as_of=T) synthesizes from the generation whose interval
    contains T; result records "as_of" (ISO). No as_of = byte-identical
    legacy behavior over live rows.
  - as_of after the last replacement reads the LIVE rows (not snapshots).
  - as_of before any snapshot exists degrades to the empty answer, not an
    error.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.graphrag.community_detection import (
    Community,
    CommunityDetectionService,
    DetectionResult,
)
from core.graphrag_engine import GraphRAGEngine
from core.models import GraphCommunity, GraphCommunitySnapshot, GraphEdge, GraphNode

UTC = timezone.utc


def _utc(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=UTC)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _seed_graph(db):
    _node(db, "A", _utc(2026, 1, 1))
    _node(db, "B", _utc(2026, 1, 1))
    _node(db, "C", _utc(2026, 1, 1))
    _edge(db, "e-ab", "A", "B", _utc(2026, 1, 1))
    _edge(db, "e-bc", "B", "C", _utc(2026, 1, 1))
    db.commit()


def _node(db, nid, created_at):
    db.add(GraphNode(id=nid, workspace_id="ws-1", name=nid, type="company",
                     created_at=created_at))


def _edge(db, eid, src, tgt, valid_from):
    db.add(GraphEdge(id=eid, workspace_id="ws-1", source_node_id=src,
                     target_node_id=tgt, relationship_type="related_to",
                     valid_from=valid_from))


def _detect_result(tag: str, nodes, summary: str) -> DetectionResult:
    c = Community(id=f"comm_{tag}", level=0, nodes=set(nodes),
                  summary=summary, keywords=[tag])
    c.__post_init__()
    return DetectionResult(communities=[c], num_communities=1,
                           modularity=0.5, coverage=1.0)


class TestGenerationArchival:
    def test_first_store_writes_no_snapshots(self, db):
        _seed_graph(db)
        svc = CommunityDetectionService()
        with patch.object(svc.leiden, "detect",
                          return_value=_detect_result("g1", {"A", "B"}, "gen one")):
            svc.detect_communities("ws-1", session=db, store_results=True)
        assert db.query(GraphCommunitySnapshot).count() == 0
        assert db.query(GraphCommunity).filter(
            GraphCommunity.workspace_id == "ws-1").count() == 1

    def test_second_store_archives_first_generation(self, db):
        _seed_graph(db)
        svc = CommunityDetectionService()
        with patch.object(svc.leiden, "detect",
                          return_value=_detect_result("g1", {"A", "B"}, "gen one")):
            svc.detect_communities("ws-1", session=db, store_results=True)
        first = db.query(GraphCommunity).filter(
            GraphCommunity.workspace_id == "ws-1").one()
        first_created = first.created_at
        # _enrich_communities rewrites keywords from node names pre-persist;
        # the contract is that the archive preserves the OUTGOING row as-is.
        first_keywords = first.keywords

        with patch.object(svc.leiden, "detect",
                          return_value=_detect_result("g2", {"A", "B", "C"}, "gen two")):
            svc.detect_communities("ws-1", session=db, store_results=True)

        snaps = db.query(GraphCommunitySnapshot).all()
        assert len(snaps) == 1
        snap = snaps[0]
        assert snap.summary == "gen one"
        assert snap.keywords == first_keywords
        assert set(snap.node_ids) == {"A", "B"}
        assert snap.level == 0
        assert snap.valid_from is not None
        assert snap.invalid_at is not None
        # interval starts when the archived generation was born
        assert snap.valid_from.replace(tzinfo=None) == first_created.replace(tzinfo=None)

        live = db.query(GraphCommunity).filter(
            GraphCommunity.workspace_id == "ws-1").all()
        assert len(live) == 1 and live[0].summary == "gen two"

    def test_three_runs_chain_intervals(self, db):
        _seed_graph(db)
        svc = CommunityDetectionService()
        for i, nodes in enumerate(({"A"}, {"A", "B"}, {"A", "B", "C"})):
            with patch.object(svc.leiden, "detect",
                              return_value=_detect_result(f"g{i}", nodes, f"gen {i}")):
                svc.detect_communities("ws-1", session=db, store_results=True)
        snaps = db.query(GraphCommunitySnapshot).order_by(
            GraphCommunitySnapshot.invalid_at).all()
        assert len(snaps) == 2
        # gen1's invalid_at == gen2's valid_from (chained, no gaps)
        assert snaps[0].invalid_at == snaps[1].valid_from
        assert [s.summary for s in snaps] == ["gen 0", "gen 1"]

    def test_workspaces_isolated(self, db):
        _seed_graph(db)
        svc = CommunityDetectionService()
        with patch.object(svc.leiden, "detect",
                          return_value=_detect_result("g1", {"A", "B"}, "gen one")):
            svc.detect_communities("ws-1", session=db, store_results=True)
        with patch.object(svc.leiden, "detect",
                          return_value=_detect_result("g1", {"A", "B"}, "other ws")):
            svc.detect_communities("ws-2", session=db, store_results=True)
        # ws-2's store must not archive ws-1's live generation
        assert db.query(GraphCommunitySnapshot).filter(
            GraphCommunitySnapshot.workspace_id == "ws-1").count() == 0


class TestGlobalSearchAsOf:
    def _two_generations(self, db):
        """Two detection runs; returns (midpoint_of_archived_interval,
        instant_after_last_replacement)."""
        _seed_graph(db)
        svc = CommunityDetectionService()
        with patch.object(svc.leiden, "detect",
                          return_value=_detect_result("g1", {"A", "B"}, "gen one")):
            svc.detect_communities("ws-1", session=db, store_results=True)
        with patch.object(svc.leiden, "detect",
                          return_value=_detect_result("g2", {"A", "B", "C"}, "gen two")):
            svc.detect_communities("ws-1", session=db, store_results=True)
        snap = db.query(GraphCommunitySnapshot).one()
        vf = snap.valid_from if snap.valid_from.tzinfo else snap.valid_from.replace(tzinfo=UTC)
        ia = snap.invalid_at if snap.invalid_at.tzinfo else snap.invalid_at.replace(tzinfo=UTC)
        midpoint = vf + (ia - vf) / 2
        after = ia + timedelta(days=1)
        return midpoint, after

    def _engine(self, db):
        eng = GraphRAGEngine(workspace_id="ws-1", tenant_id="default")
        eng.llm_service = SimpleNamespace(
            generate_completion=AsyncMock(return_value={"content": "synthesized"}))
        return eng

    @pytest.mark.asyncio
    async def test_as_of_in_archived_interval_reads_snapshot(self, db):
        midpoint, _after = self._two_generations(db)
        eng = self._engine(db)
        with patch("core.graphrag_engine.get_db_session", return_value=_Ctx(db)):
            result = await eng.global_search("ws-1", "default", "query", as_of=midpoint)
        assert result["as_of"] == midpoint.isoformat()
        assert result["summaries"] == ["gen one"]

    @pytest.mark.asyncio
    async def test_as_of_after_last_replacement_reads_live_rows(self, db):
        _midpoint, after = self._two_generations(db)
        eng = self._engine(db)
        with patch("core.graphrag_engine.get_db_session", return_value=_Ctx(db)):
            result = await eng.global_search("ws-1", "default", "query", as_of=after)
        assert result["summaries"] == ["gen two"]
        assert result["as_of"] == after.isoformat()

    @pytest.mark.asyncio
    async def test_no_as_of_is_legacy_live_rows(self, db):
        _midpoint, _after = self._two_generations(db)
        eng = self._engine(db)
        with patch("core.graphrag_engine.get_db_session", return_value=_Ctx(db)):
            result = await eng.global_search("ws-1", "default", "query")
        assert result["summaries"] == ["gen two"]
        assert "as_of" not in result

    @pytest.mark.asyncio
    async def test_as_of_before_any_history_degrades_to_empty(self, db):
        _midpoint, _after = self._two_generations(db)
        eng = self._engine(db)
        ancient = datetime.now(timezone.utc) - timedelta(days=3650)
        with patch("core.graphrag_engine.get_db_session", return_value=_Ctx(db)):
            result = await eng.global_search("ws-1", "default", "query", as_of=ancient)
        assert result["summaries"] == []
        assert "No community data" in result["answer"]


class _Ctx:
    """`with get_db_session() as s` -> the fixture session."""

    def __init__(self, session):
        self._s = session

    def __enter__(self):
        return self._s

    def __exit__(self, *exc):
        return False