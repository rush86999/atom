"""
P2.1 deferred half — LLM-review consolidation pass tests.

Covers: op parsing, subject candidate grouping, per-op application
(supersede_fact / invalidate_edge / add_fact / update_fact), flag gating,
LLM failure tolerance, and never-raises guarantees. All DB access is a
patched in-memory SQLite session — never the dev store.
"""

import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import GraphEdge, GraphNode, TurnFact
from core.models_registration import Base


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng, tables=[
        TurnFact.__table__, GraphEdge.__table__, GraphNode.__table__,
    ])
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.query(TurnFact).delete()
    db.query(GraphEdge).delete()
    db.query(GraphNode).delete()
    db.commit()
    db.close()


@pytest.fixture
def db_ctx(db_session):
    @contextmanager
    def _ctx():
        yield db_session
    return _ctx


@pytest.fixture(autouse=True)
def patch_db(db_ctx, monkeypatch):
    monkeypatch.setattr("core.database.get_db_session", db_ctx)
    yield


# --------------------------------------------------------------------------- #
# Op parsing
# --------------------------------------------------------------------------- #

class TestParseOps:
    def test_plain_array(self):
        from core.memory_consolidator import _parse_ops
        assert _parse_ops('[{"op": "supersede_fact", "fact_id": "a"}]') == [
            {"op": "supersede_fact", "fact_id": "a"}
        ]

    def test_wrapped_in_ops_key(self):
        from core.memory_consolidator import _parse_ops
        assert _parse_ops('{"ops": [{"op": "add_fact", "text": "x"}]}') == [
            {"op": "add_fact", "text": "x"}
        ]

    def test_markdown_fenced(self):
        from core.memory_consolidator import _parse_ops
        raw = '```json\n[{"op": "invalidate_edge", "edge_id": "e1"}]\n```'
        assert _parse_ops(raw) == [{"op": "invalidate_edge", "edge_id": "e1"}]

    def test_garbage_returns_empty(self):
        from core.memory_consolidator import _parse_ops
        assert _parse_ops("I don't think anything needs changing.") == []
        assert _parse_ops("") == []
        assert _parse_ops(None) == []

    def test_filters_non_dicts(self):
        from core.memory_consolidator import _parse_ops
        assert _parse_ops('[{"op": "add_fact"}, "junk", 3]') == [{"op": "add_fact"}]


# --------------------------------------------------------------------------- #
# Subject candidate grouping
# --------------------------------------------------------------------------- #

class TestSubjectCandidates:
    def test_groups_and_requires_two(self):
        from core.memory_consolidator import _subject_candidates
        f1 = SimpleNamespace(fact_text="ACME budget total is 80k dollars", category="exact_value")
        f2 = SimpleNamespace(fact_text="ACME budget total is 95k dollars", category="exact_value")
        f3 = SimpleNamespace(fact_text="SigmaMax supplies lasers", category="exact_value")
        cands = _subject_candidates([f1, f2, f3])
        assert len(cands) == 1
        assert cands[0][0] == "acme budget total is"
        assert len(cands[0][1]) == 2

    def test_caps_subjects(self, monkeypatch):
        import core.memory_consolidator as mc
        monkeypatch.setattr(mc, "llm_review_max_subjects", lambda: 1)
        from core.memory_consolidator import _subject_candidates
        facts = [
            SimpleNamespace(fact_text=f"subject{i} alpha value {i}", category="exact_value")
            for i in range(2)
        ] + [
            SimpleNamespace(fact_text=f"subject{i} alpha value {i} again", category="exact_value")
            for i in range(2)
        ]
        cands = _subject_candidates(facts)
        assert len(cands) == 1


# --------------------------------------------------------------------------- #
# consolidate_with_llm
# --------------------------------------------------------------------------- #

@pytest.fixture
def enable_llm(monkeypatch):
    import core.memory_consolidator as mc
    monkeypatch.setattr(mc, "llm_review_enabled", lambda: True)
    return mc


class TestConsolidateWithLlm:
    def test_disabled_by_default(self, monkeypatch):
        import core.memory_consolidator as mc
        monkeypatch.setattr(mc, "llm_review_enabled", lambda: False)
        report = asyncio_run(mc.consolidate_with_llm("ws-1"))
        assert report["enabled"] is False
        assert report["ops_emitted"] == 0

    def test_supersede_fact_applied(self, enable_llm, db_session):
        ws = "ws-1"
        old_f = TurnFact(id="f1", workspace_id=ws, tenant_id=None,
                         fact_text="ACME budget total is 80k dollars", category="exact_value",
                         confidence=0.8, content_hash="h1", status="active",
                         extraction_source="turn")
        new_f = TurnFact(id="f2", workspace_id=ws, tenant_id=None,
                         fact_text="ACME budget total is 95k dollars", category="exact_value",
                         confidence=0.8, content_hash="h2", status="active",
                         extraction_source="turn",
                         created_at=datetime.utcnow())
        old_f.created_at = datetime.utcnow() - timedelta(days=3)
        db_session.add(old_f)
        db_session.add(new_f)
        db_session.commit()

        llm = Mock()
        llm.generate = AsyncMock(return_value='[{"op": "supersede_fact", "fact_id": "f1", "reason": "superseded by newer"}]')
        with patch("core.llm_service.get_llm_service", return_value=llm):
            report = asyncio_run(enable_llm.consolidate_with_llm(ws))
        assert report["ops_applied"] == 1
        assert report["counts"]["supersede_fact"] == 1
        db_session.expire_all()
        assert db_session.get(TurnFact, "f1").status == "superseded"
        assert db_session.get(TurnFact, "f2").status == "active"

    def test_invalidate_edge_applied(self, enable_llm, db_session):
        ws = "ws-1"
        db_session.add(GraphNode(id="n1", workspace_id=ws, name="ACME", type="org"))
        db_session.add(GraphNode(id="n2", workspace_id=ws, name="AccurPress", type="product"))
        e = GraphEdge(id="e1", workspace_id=ws, source_node_id="n1",
                      target_node_id="n2", relationship_type="inquired_about",
                      properties={"price": 80000}, valid_from=datetime.utcnow())
        db_session.add(e)
        db_session.add(TurnFact(id="f1", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 80k dollars", category="exact_value",
                                confidence=0.8, content_hash="h1", status="active",
                                extraction_source="turn", created_at=datetime.utcnow() - timedelta(days=3)))
        db_session.add(TurnFact(id="f2", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 95k dollars", category="exact_value",
                                confidence=0.8, content_hash="h2", status="active",
                                extraction_source="turn", created_at=datetime.utcnow()))
        db_session.commit()

        llm = Mock()
        llm.generate = AsyncMock(return_value='[{"op": "invalidate_edge", "edge_id": "e1", "reason": "price changed"}]')
        with patch("core.llm_service.get_llm_service", return_value=llm):
            report = asyncio_run(enable_llm.consolidate_with_llm(ws))
        assert report["ops_applied"] == 1
        db_session.expire_all()
        edge = db_session.get(GraphEdge, "e1")
        assert edge.invalid_at is not None
        assert "price changed" in (edge.invalidation_reason or "")

    def test_add_fact_rejected_without_category(self, enable_llm, db_session):
        ws = "ws-1"
        db_session.add(TurnFact(id="f1", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 80k dollars", category="exact_value",
                                confidence=0.8, content_hash="h1", status="active",
                                extraction_source="turn", created_at=datetime.utcnow() - timedelta(days=3)))
        db_session.add(TurnFact(id="f2", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 95k dollars", category="exact_value",
                                confidence=0.8, content_hash="h2", status="active",
                                extraction_source="turn", created_at=datetime.utcnow()))
        db_session.commit()
        llm = Mock()
        llm.generate = AsyncMock(return_value='[{"op": "add_fact", "text": "sigma supplies lasers", "category": "bogus"}]')
        with patch("core.llm_service.get_llm_service", return_value=llm):
            report = asyncio_run(enable_llm.consolidate_with_llm(ws))
        assert report["ops_applied"] == 0
        assert any("bogus" in s for s in report["skipped"])

    def test_add_fact_valid_calls_remember(self, enable_llm, db_session):
        ws = "ws-1"
        db_session.add(TurnFact(id="f1", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 80k dollars", category="exact_value",
                                confidence=0.8, content_hash="h1", status="active",
                                extraction_source="turn", created_at=datetime.utcnow() - timedelta(days=3)))
        db_session.add(TurnFact(id="f2", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 95k dollars", category="exact_value",
                                confidence=0.8, content_hash="h2", status="active",
                                extraction_source="turn", created_at=datetime.utcnow()))
        db_session.commit()
        llm = Mock()
        llm.generate = AsyncMock(return_value='[{"op": "add_fact", "text": "SigmaMax supplies the fiber laser", "category": "exact_value", "reason": "missing"}]')
        remember = Mock(return_value=SimpleNamespace(id="f3"))
        with patch("core.llm_service.get_llm_service", return_value=llm), patch(
            "core.turn_fact_extractor.remember_fact_explicit", remember
        ):
            report = asyncio_run(enable_llm.consolidate_with_llm(ws))
        assert report["ops_applied"] == 1
        remember.assert_called_once()
        assert report["audit"][0]["op"] == "add_fact"

    def test_update_fact_supersedes_and_links(self, enable_llm, db_session):
        ws = "ws-1"
        old_f = TurnFact(id="f1", workspace_id=ws, tenant_id=None,
                         fact_text="ACME budget total is 80k dollars", category="exact_value",
                         confidence=0.8, content_hash="h1", status="active",
                         extraction_source="turn", created_at=datetime.utcnow() - timedelta(days=3))
        f2 = TurnFact(id="f2", workspace_id=ws, tenant_id=None,
                      fact_text="ACME budget total is 95k dollars", category="exact_value",
                      confidence=0.8, content_hash="h2", status="active",
                      extraction_source="turn", created_at=datetime.utcnow())
        db_session.add(old_f)
        db_session.add(f2)
        db_session.commit()
        llm = Mock()
        llm.generate = AsyncMock(return_value='[{"op": "update_fact", "fact_id": "f1", "text": "ACME budget is $90,000", "category": "exact_value", "reason": "corrected"}]')
        remember = Mock(return_value=SimpleNamespace(id="f3"))
        with patch("core.llm_service.get_llm_service", return_value=llm), patch(
            "core.turn_fact_extractor.remember_fact_explicit", remember
        ):
            report = asyncio_run(enable_llm.consolidate_with_llm(ws))
        assert report["ops_applied"] == 1
        db_session.expire_all()
        assert db_session.get(TurnFact, "f1").status == "superseded"

    def test_llm_failure_never_raises(self, enable_llm, db_session):
        ws = "ws-1"
        db_session.add(TurnFact(id="f1", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 80k dollars", category="exact_value",
                                confidence=0.8, content_hash="h1", status="active",
                                extraction_source="turn", created_at=datetime.utcnow() - timedelta(days=3)))
        db_session.add(TurnFact(id="f2", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 95k dollars", category="exact_value",
                                confidence=0.8, content_hash="h2", status="active",
                                extraction_source="turn", created_at=datetime.utcnow()))
        db_session.commit()
        llm = Mock()
        llm.generate = AsyncMock(side_effect=RuntimeError("provider down"))
        with patch("core.llm_service.get_llm_service", return_value=llm):
            report = asyncio_run(enable_llm.consolidate_with_llm(ws))
        assert report["ops_applied"] == 0
        assert report["ops_emitted"] == 0

    def test_evidence_failure_never_raises(self, enable_llm, monkeypatch):
        def boom():
            raise RuntimeError("db down")
        monkeypatch.setattr("core.database.get_db_session", boom)
        report = asyncio_run(enable_llm.consolidate_with_llm("ws-1"))
        assert report["ops_applied"] == 0

    def test_apply_caps_ops(self, enable_llm, db_session, monkeypatch):
        import core.memory_consolidator as mc
        monkeypatch.setattr(mc, "llm_review_max_ops", lambda: 1)
        ws = "ws-1"
        db_session.add(TurnFact(id="f1", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 80k dollars", category="exact_value",
                                confidence=0.8, content_hash="h1", status="active",
                                extraction_source="turn", created_at=datetime.utcnow() - timedelta(days=3)))
        db_session.add(TurnFact(id="f2", workspace_id=ws, tenant_id=None,
                                fact_text="ACME budget total is 95k dollars", category="exact_value",
                                confidence=0.8, content_hash="h2", status="active",
                                extraction_source="turn", created_at=datetime.utcnow()))
        db_session.commit()
        llm = Mock()
        llm.generate = AsyncMock(return_value='[{"op": "supersede_fact", "fact_id": "f1"}, {"op": "supersede_fact", "fact_id": "f2"}]')
        with patch("core.llm_service.get_llm_service", return_value=llm):
            report = asyncio_run(enable_llm.consolidate_with_llm(ws))
        assert report["ops_applied"] == 1


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)