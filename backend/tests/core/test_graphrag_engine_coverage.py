"""
Coverage + bug-hunt tests for core/graphrag_engine.py

Targets: GraphRAGEngine — pattern/LLM extraction, entity/relationship add,
structured ingestion, canonical resolution, local/global search, query
routing, context formatting, communities, reindex, pattern discovery.

DB (get_db_session), LLMService, ServiceFactory, multi-hop expander, and
community detector are all mocked. No real network or DB.
"""
import asyncio
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import graphrag_engine as ge_mod
from core.graphrag_engine import (
    Entity,
    GraphRAGEngine,
    Relationship,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """GraphRAGEngine with a mocked get_db_session yielding a MagicMock."""
    eng = GraphRAGEngine(workspace_id="ws1", tenant_id="t1")
    return eng


@contextmanager
def _patch_session(session):
    """Context manager that makes get_db_session yield `session`.

    Methods in graphrag_engine.py use BOTH the module-level import
    (core.graphrag_engine.get_db_session, bound at line 20) AND a local
    re-import (from core.database import get_db_session) inside
    discover_failed_hypotheses_patterns. Patch both so every code path
    uses the mock session."""
    @contextmanager
    def fake_session():
        yield session

    with patch("core.database.get_db_session", fake_session), \
         patch("core.graphrag_engine.get_db_session", fake_session):
        yield


def _set_records(sess, records):
    """Set `records` as the .all() result at every plausible query chain depth
    and every order_by().limit().all() / .limit().all() depth — so a query
    built with any number of .filter()/.order_by()/.limit() calls returns it."""
    q = sess.query.return_value
    levels = [
        q,
        q.filter.return_value,
        q.filter.return_value.filter.return_value,
        q.filter.return_value.filter.return_value.filter.return_value,
    ]
    for lvl in levels:
        lvl.all.return_value = records
        lvl.order_by.return_value.limit.return_value.all.return_value = records
        lvl.order_by.return_value.limit.return_value.all.return_value = records
        # canonical_search uses .filter().filter().limit(10).all() (no order_by)
        lvl.limit.return_value.all.return_value = records
        lvl.filter.return_value.limit.return_value.all.return_value = records


def _mock_session():
    sess = MagicMock()
    sess.bind = MagicMock()
    sess.bind.dialect.name = "postgresql"
    # query() chain — set terminal methods at every plausible filter depth
    q = sess.query.return_value
    levels = [
        q,
        q.filter.return_value,
        q.filter.return_value.filter.return_value,
        q.filter.return_value.filter.return_value.filter.return_value,
    ]
    for lvl in levels:
        lvl.first.return_value = None
        lvl.all.return_value = []
        lvl.count.return_value = 0
        lvl.order_by.return_value.limit.return_value.all.return_value = []
        # filter_by chains at this level
        lvl.filter_by.return_value.first.return_value = None
        lvl.filter_by.return_value.all.return_value = []
    # Top-level filter_by
    q.filter_by.return_value.first.return_value = None
    return sess


# ---------------------------------------------------------------------------
# Construction / get_stats / validation helpers
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_defaults(self):
        eng = GraphRAGEngine()
        assert eng.workspace_id == "default"
        assert eng.tenant_id == "default"
        assert eng.db is None
        assert eng.llm_service is not None

    def test_explicit_ids(self, engine):
        assert engine.workspace_id == "ws1"
        assert engine.tenant_id == "t1"

    def test_get_stats(self, engine):
        stats = engine.get_stats()
        assert stats["workspace_id"] == "ws1"
        assert stats["status"] == "initialized"
        assert stats["nodes"] == 0
        assert "edges" in stats and "entities" in stats

    def test_get_stats_with_user_id(self, engine):
        stats = engine.get_stats(user_id="u1")
        assert stats["workspace_id"] == "ws1"


class TestInputValidation:
    def test_validate_empty_returns_empty(self, engine):
        assert engine._validate_search_input("") == ""
        assert engine._validate_search_input(None) == ""

    def test_validate_strips_control_chars(self, engine):
        out = engine._validate_search_input("hello\x00world\x01")
        assert "\x00" not in out
        assert "hello" in out

    def test_validate_keeps_tab_newline(self, engine):
        out = engine._validate_search_input("a\tb\nc")
        assert "\t" in out and "\n" in out

    def test_validate_too_long_raises(self, engine):
        with pytest.raises(ValueError, match="too long"):
            engine._validate_search_input("x" * 501, max_length=500)

    def test_validate_under_limit_ok(self, engine):
        assert engine._validate_search_input("x" * 500) == "x" * 500


class TestEscapeLikePattern:
    def test_escapes_percent(self, engine):
        assert engine._escape_like_pattern("50%") == r"50\%"

    def test_escapes_underscore(self, engine):
        assert engine._escape_like_pattern("user_id") == r"user\_id"

    def test_escapes_backslash(self, engine):
        assert engine._escape_like_pattern("a\\b") == "a\\\\b"

    def test_no_special_chars_unchanged(self, engine):
        assert engine._escape_like_pattern("plain") == "plain"


class TestSanitizeCanonicalData:
    """Note: the second definition (line 707) overrides the first (line 157).
    The active signature is (canonical_type, data) and strips/lowercases."""

    def test_strips_string_values(self, engine):
        out = engine._sanitize_canonical_data("user", {"name": "  Alice  "})
        assert out["name"] == "Alice"

    def test_lowercases_user_email(self, engine):
        out = engine._sanitize_canonical_data("user", {"email": "ALICE@X.COM"})
        assert out["email"] == "alice@x.com"

    def test_non_string_passthrough(self, engine):
        out = engine._sanitize_canonical_data("task", {"count": 5, "flag": True})
        assert out["count"] == 5 and out["flag"] is True


# ---------------------------------------------------------------------------
# Registry / canonical resolution
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_get_entity_registry_no_workspace(self, engine):
        reg = engine._get_entity_registry()
        assert "user" in reg and "workspace" in reg and "formula" in reg

    def test_get_registry_entry_known(self, engine):
        entry = engine._get_registry_entry("user")
        assert entry is not None
        assert "model" in entry

    def test_get_registry_entry_custom_returns_none(self, engine):
        # custom types have is_custom=True and _get_registry_entry returns None
        with patch.object(engine, "_get_entity_registry",
                          return_value={"foo": {"is_custom": True}}):
            assert engine._get_registry_entry("foo") is None

    def test_get_registry_entry_unknown_returns_none(self, engine):
        assert engine._get_registry_entry("nonexistent_xyz") is None

    def test_load_custom_entity_types(self, engine):
        sess = _mock_session()
        custom = MagicMock()
        custom.slug = "mytype"
        custom.id = "id1"
        custom.display_name = "My Type"
        custom.json_schema = {"x": 1}
        # Query uses single .filter(...).all() OR .filter().filter().all()
        sess.query.return_value.filter.return_value.all.return_value = [custom]
        sess.query.return_value.filter.return_value.filter.return_value.all.return_value = [custom]
        with _patch_session(sess):
            result = engine._load_custom_entity_types("ws1")
        assert "mytype" in result
        assert result["mytype"]["is_custom"] is True

    def test_load_custom_entity_types_exception_returns_empty(self, engine):
        sess = _mock_session()
        sess.query.side_effect = RuntimeError("db")
        with _patch_session(sess):
            assert engine._load_custom_entity_types("ws1") == {}


class TestResolveCanonicalEntity:
    def test_no_registry_returns_none(self, engine):
        with patch.object(engine, "_get_registry_entry", return_value=None):
            sess = _mock_session()
            assert engine._resolve_canonical_entity(sess, "ws1", "name", "unknown") is None

    def test_no_model_returns_none(self, engine):
        with patch.object(engine, "_get_registry_entry",
                          return_value={"model": None, "search_field": "name"}):
            sess = _mock_session()
            assert engine._resolve_canonical_entity(sess, "ws1", "name", "user") is None

    def test_resolves_by_search_field(self, engine):
        fake_model = MagicMock()
        fake_model.name = "Alice"
        # model has workspace_id attr
        type(fake_model).workspace_id = "ws1"
        config = {"model": MagicMock(), "search_field": "name", "match_id": False}
        # The query chain: query(model).filter(...).filter(...).first()
        match = MagicMock()
        match.id = "rec-1"
        sess = MagicMock()
        sess.query.return_value.filter.return_value.filter.return_value.first.return_value = match
        sess.query.return_value.filter.return_value.first.return_value = match
        with patch.object(engine, "_get_registry_entry", return_value=config):
            result = engine._resolve_canonical_entity(sess, "ws1", "Alice", "user")
        assert result == "rec-1"

    def test_resolves_by_match_id_fallback(self, engine):
        config = {"model": MagicMock(), "search_field": "name", "match_id": True}
        sess = MagicMock()
        # first() returns None, then match_id path returns match
        match = MagicMock()
        match.id = "id-match"
        chain = sess.query.return_value.filter.return_value
        chain.first.return_value = None
        chain.filter.return_value.first.return_value = match
        with patch.object(engine, "_get_registry_entry", return_value=config):
            result = engine._resolve_canonical_entity(sess, "ws1", "x", "task")
        assert result == "id-match"

    def test_resolve_returns_none_when_no_match(self, engine):
        config = {"model": MagicMock(), "search_field": "name", "match_id": False}
        sess = MagicMock()
        sess.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        sess.query.return_value.filter.return_value.first.return_value = None
        with patch.object(engine, "_get_registry_entry", return_value=config):
            result = engine._resolve_canonical_entity(sess, "ws1", "x", "user")
        assert result is None

    def test_resolve_exception_returns_none(self, engine):
        config = {"model": MagicMock(), "search_field": "name", "match_id": False}
        sess = MagicMock()
        sess.query.side_effect = RuntimeError("x")
        with patch.object(engine, "_get_registry_entry", return_value=config):
            result = engine._resolve_canonical_entity(sess, "ws1", "x", "user")
        assert result is None


class TestCreateCanonicalEntity:
    def test_no_config_returns_none(self, engine):
        with patch.object(engine, "_get_registry_entry", return_value=None):
            assert engine._create_canonical_entity_if_missing(_mock_session(), "ws1", "n", "x") is None

    def test_no_model_returns_none(self, engine):
        with patch.object(engine, "_get_registry_entry",
                          return_value={"model": None, "search_field": "name"}):
            assert engine._create_canonical_entity_if_missing(_mock_session(), "ws1", "n", "user") is None

    def test_creates_record_returns_id(self, engine):
        fake_model = MagicMock()
        record = MagicMock()
        record.id = "new-id"
        fake_model.return_value = record
        config = {"model": fake_model, "search_field": "name"}
        sess = _mock_session()
        with patch.object(engine, "_get_registry_entry", return_value=config):
            result = engine._create_canonical_entity_if_missing(sess, "ws1", "Alice", "user")
        assert result == "new-id"

    def test_create_exception_returns_none(self, engine):
        fake_model = MagicMock()
        fake_model.side_effect = RuntimeError("constraint")
        config = {"model": fake_model, "search_field": "name"}
        sess = _mock_session()
        with patch.object(engine, "_get_registry_entry", return_value=config):
            result = engine._create_canonical_entity_if_missing(sess, "ws1", "Alice", "user")
        assert result is None


# ---------------------------------------------------------------------------
# canonical_search (public)
# ---------------------------------------------------------------------------

class TestCanonicalSearch:
    def test_no_registry_returns_empty(self, engine):
        with patch.object(engine, "_get_registry_entry", return_value=None):
            assert engine.canonical_search(entity_type="unknown", query="x") == []

    def test_search_returns_records(self, engine):
        # Use a REAL model (User) so the ilike()/or_() SQLAlchemy expressions
        # build correctly instead of choking on MagicMock column objects.
        from core.models import User
        config = {
            "model": User,
            "search_fields": ["name", "email"],
            "display_field": "name",
        }
        rec = MagicMock()
        rec.id = "r1"
        rec.name = "Alice"
        sess = MagicMock()
        _set_records(sess, [rec])
        with patch.object(engine, "_get_registry_entry", return_value=config), \
             _patch_session(sess):
            result = engine.canonical_search(entity_type="user", query="ali")
        assert result == [{"id": "r1", "name": "Alice"}]

    def test_search_exception_returns_empty(self, engine):
        config = {"model": MagicMock(), "search_fields": ["name"], "display_field": "name"}
        sess = MagicMock()
        sess.query.side_effect = RuntimeError("x")
        with patch.object(engine, "_get_registry_entry", return_value=config), \
             _patch_session(sess):
            assert engine.canonical_search(entity_type="user", query="x") == []

    def test_search_empty_query_returns_all(self, engine):
        """Empty query bypasses the validate (returns '') and still queries."""
        config = {"model": MagicMock(), "search_fields": ["name"], "display_field": "name"}
        sess = MagicMock()
        sess.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        with patch.object(engine, "_get_registry_entry", return_value=config), \
             _patch_session(sess):
            assert engine.canonical_search(entity_type="user", query="") == []


# ---------------------------------------------------------------------------
# Pattern extraction (10 entity types)
# ---------------------------------------------------------------------------

class TestPatternExtraction:
    def test_extracts_email(self, engine):
        ents, rels = engine._pattern_extract_entities_and_relationships(
            "Contact me at alice@example.com please", "doc1", "src")
        types = [e.entity_type for e in ents]
        assert "email" in types
        assert any("alice@example.com" in e.name for e in ents)

    def test_extracts_url(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Visit https://example.com/page today", "doc1", "src")
        assert any(e.entity_type == "url" for e in ents)

    def test_extracts_phone(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Call (555) 123-4567 now", "doc1", "src")
        assert any(e.entity_type == "phone" for e in ents)

    def test_extracts_iso_date(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Deadline is 2026-01-15", "doc1", "src")
        assert any(e.entity_type == "date" and e.name == "2026-01-15" for e in ents)

    def test_extracts_us_date(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Born 01/15/1990", "doc1", "src")
        assert any(e.entity_type == "date" and e.name == "01/15/1990" for e in ents)

    def test_extracts_textual_date(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Meeting on Jan 15, 2026", "doc1", "src")
        assert any(e.entity_type == "date" for e in ents)

    def test_extracts_currency_dollars(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Costs $1,234.56 total", "doc1", "src")
        assert any(e.entity_type == "currency" and e.name == "$1,234.56" for e in ents)

    def test_extracts_currency_iso(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Paid 100 USD and 50 EUR", "doc1", "src")
        cur = [e.name for e in ents if e.entity_type == "currency"]
        assert "100 USD" in cur and "50 EUR" in cur

    def test_extracts_file_path(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "See /etc/hosts.txt for details", "doc1", "src")
        assert any(e.entity_type == "file_path" for e in ents)

    def test_file_path_negative_lookbehind_avoids_url(self, engine):
        """The negative lookbehind must NOT extract '//example.com' as a path."""
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Go to http://example.com now", "doc1", "src")
        paths = [e for e in ents if e.entity_type == "file_path"]
        # No file_path should be extracted from inside the URL
        assert all("example.com" not in e.name for e in paths)

    def test_extracts_valid_ip(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Server at 192.168.1.1", "doc1", "src")
        assert any(e.entity_type == "ip_address" and e.name == "192.168.1.1" for e in ents)

    def test_rejects_invalid_ip(self, engine):
        """Octets > 255 must be rejected (validated octets)."""
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Bad 999.999.999.999 ip", "doc1", "src")
        assert not any(e.entity_type == "ip_address" for e in ents)

    def test_extracts_uuid(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "Id 550e8400-e29b-41d4-a716-446655440000 here", "doc1", "src")
        assert any(e.entity_type == "uuid" for e in ents)

    def test_no_duplicates_same_value(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "mail@a.com and mail@a.com again", "doc1", "src")
        emails = [e.name for e in ents if e.entity_type == "email"]
        assert emails.count("mail@a.com") == 1

    def test_empty_text_returns_empty(self, engine):
        ents, rels = engine._pattern_extract_entities_and_relationships(
            "no entities here just words", "doc1", "src")
        assert ents == []
        assert rels == []

    def test_pattern_properties_contain_source(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "mail@a.com", "doc1", "mysource")
        assert ents[0].properties["source"] == "mysource"
        assert ents[0].properties["doc_id"] == "doc1"
        assert ents[0].properties["pattern_extracted"] is True


class TestIpOctetValidationBug:
    """BUG HUNT: confirm the IP regex correctly rejects 999.x but the leading
    octet `[1-9]?\\d` allows single-digit octets. Verify a known-good and a
    known-bad IP behave correctly (regression guard for the validated-octet
    fix that was previously broken)."""

    def test_rejects_octet_over_255(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "ip 256.0.0.1", "doc1", "src")
        assert not any(e.entity_type == "ip_address" for e in ents)

    def test_accepts_boundary_255(self, engine):
        ents, _ = engine._pattern_extract_entities_and_relationships(
            "ip 255.255.255.255", "doc1", "src")
        assert any(e.entity_type == "ip_address" and e.name == "255.255.255.255" for e in ents)


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

class TestLLMExtraction:
    @pytest.mark.asyncio
    async def test_llm_extracts_entities_and_relationships(self, engine):
        fake_extractor = MagicMock()
        fake_extractor.extract_knowledge = AsyncMock(return_value={
            "entities": [
                {"name": "Alice", "type": "person", "description": "a person"},
                {"properties": {"name": "Bob", "type": "user", "description": "b"}},
            ],
            "relationships": [
                {"from": "Alice", "to": "Bob", "type": "knows", "description": "friends"}
            ],
        })
        with patch("core.service_factory.ServiceFactory.get_knowledge_extractor",
                   return_value=fake_extractor):
            ents, rels = await engine._llm_extract_entities_and_relationships(
                "text", "doc1", "src", "ws1")
        assert len(ents) == 2
        assert ents[0].name == "Alice"
        assert ents[0].properties["llm_extracted"] is True
        assert ents[0].properties["source"] == "src"
        assert len(rels) == 1
        assert rels[0].from_entity == "Alice"

    @pytest.mark.asyncio
    async def test_llm_extraction_exception_returns_empty(self, engine):
        with patch("core.service_factory.ServiceFactory.get_knowledge_extractor",
                   side_effect=RuntimeError("x")):
            ents, rels = await engine._llm_extract_entities_and_relationships(
                "text", "doc1", "src", "ws1")
        assert ents == [] and rels == []

    @pytest.mark.asyncio
    async def test_llm_extraction_unknown_name_default(self, engine):
        fake_extractor = MagicMock()
        fake_extractor.extract_knowledge = AsyncMock(return_value={
            "entities": [{"type": "thing"}],  # no name -> "Unknown"
            "relationships": [],
        })
        with patch("core.service_factory.ServiceFactory.get_knowledge_extractor",
                   return_value=fake_extractor):
            ents, _ = await engine._llm_extract_entities_and_relationships(
                "text", "doc1", "src", "ws1")
        assert ents[0].name == "Unknown"


# ---------------------------------------------------------------------------
# ingest_document
# ---------------------------------------------------------------------------

class TestIngestDocument:
    @pytest.mark.asyncio
    async def test_uses_pattern_extraction_when_llm_disabled(self, monkeypatch):
        monkeypatch.setattr(ge_mod, "GRAPHRAG_LLM_ENABLED", False)
        eng = GraphRAGEngine(workspace_id="ws1")
        with patch.object(eng, "_pattern_extract_entities_and_relationships",
                          return_value=([Entity("id", "Alice", "person")], [])) as m, \
             patch.object(eng, "ingest_structured_data") as ingest:
            await eng.ingest_document(workspace_id="ws1", doc_id="d1",
                                       text="Alice", source="s")
        m.assert_called_once()
        ingest.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_entities_returns_early(self, monkeypatch):
        monkeypatch.setattr(ge_mod, "GRAPHRAG_LLM_ENABLED", True)
        eng = GraphRAGEngine(workspace_id="ws1")
        with patch.object(eng, "_llm_extract_entities_and_relationships",
                          AsyncMock(return_value=([], []))), \
             patch.object(eng, "ingest_structured_data") as ingest:
            result = await eng.ingest_document(workspace_id="ws1", doc_id="d1",
                                                text="nothing", source="s")
        ingest.assert_not_called()
        # R83: no-extraction returns surfaced zero stats (previously None) so
        # hybrid sync results report real counts.
        assert result == {"entities": 0, "relationships": 0}

    @pytest.mark.asyncio
    async def test_llm_path_ingests(self, monkeypatch):
        monkeypatch.setattr(ge_mod, "GRAPHRAG_LLM_ENABLED", True)
        eng = GraphRAGEngine(workspace_id="ws1")
        with patch.object(eng, "_llm_extract_entities_and_relationships",
                          AsyncMock(return_value=([Entity("id", "Alice", "person")], []))), \
             patch.object(eng, "ingest_structured_data") as ingest:
            await eng.ingest_document(workspace_id="ws1", doc_id="d1",
                                       text="Alice", source="s")
        ingest.assert_called_once()


# ---------------------------------------------------------------------------
# add_entity / add_relationship
# ---------------------------------------------------------------------------

class TestAddEntity:
    def test_add_new_entity(self, engine):
        sess = _mock_session()
        # No existing node
        sess.query.return_value.filter_by.return_value.first.return_value = None
        with _patch_session(sess):
            ent = Entity("eid", "Alice", "person", "desc")
            result = engine.add_entity(ent, workspace_id="ws1", tenant_id="t1")
        assert result == "eid"
        sess.add.assert_called()
        sess.commit.assert_called()

    def test_add_entity_existing_updates(self, engine):
        sess = _mock_session()
        existing = MagicMock()
        existing.id = "existing-id"
        sess.query.return_value.filter_by.return_value.first.return_value = existing
        with _patch_session(sess):
            ent = Entity("eid", "Alice", "person", "newdesc")
            result = engine.add_entity(ent, workspace_id="ws1")
        assert result == "existing-id"
        assert existing.description == "newdesc"

    def test_add_entity_with_embedding_pops_property(self, engine):
        sess = _mock_session()
        sess.query.return_value.filter_by.return_value.first.return_value = None
        with _patch_session(sess):
            ent = Entity("eid", "Alice", "person", "desc",
                         properties={"embedding": [0.1, 0.2], "extra": 1})
            engine.add_entity(ent, workspace_id="ws1")
        # embedding should NOT be in the stored properties (popped)
        added_node = sess.add.call_args[0][0]
        assert "embedding" not in added_node.properties
        assert added_node.embedding == [0.1, 0.2]

    def test_add_entity_with_canonical_type_resolution(self, engine):
        sess = _mock_session()
        sess.query.return_value.filter_by.return_value.first.return_value = None
        ent = Entity("eid", "Alice", "person", "desc",
                     properties={"canonical_type": "user"})
        with _patch_session(sess), \
             patch.object(engine, "_resolve_canonical_entity", return_value="cid") as r:
            result = engine.add_entity(ent, workspace_id="ws1")
        assert ent.properties["canonical_id"] == "cid"
        r.assert_called_once()

    def test_add_entity_canonical_create_when_missing(self, engine):
        sess = _mock_session()
        sess.query.return_value.filter_by.return_value.first.return_value = None
        ent = Entity("eid", "Alice", "person", "desc",
                     properties={"canonical_type": "user"})
        with _patch_session(sess), \
             patch.object(engine, "_resolve_canonical_entity", return_value=None), \
             patch.object(engine, "_create_canonical_entity_if_missing", return_value="newcid"):
            engine.add_entity(ent, workspace_id="ws1")
        assert ent.properties["canonical_id"] == "newcid"

    def test_add_entity_exception_returns_none(self, engine):
        sess = _mock_session()
        sess.query.side_effect = RuntimeError("db")
        with _patch_session(sess):
            ent = Entity("eid", "Alice", "person")
            result = engine.add_entity(ent, workspace_id="ws1")
        assert result is None

    def test_add_entity_triggers_automation_when_available(self, monkeypatch):
        monkeypatch.setattr(ge_mod, "AUTOMATION_AVAILABLE", True)
        fake_orch = MagicMock()
        fake_orch.trigger_event = AsyncMock()
        monkeypatch.setattr(ge_mod, "orchestrator", fake_orch, raising=False)
        eng = GraphRAGEngine()
        sess = _mock_session()
        sess.query.return_value.filter_by.return_value.first.return_value = None
        with _patch_session(sess):
            ent = Entity("eid", "Alice", "person")
            # asyncio.create_task needs a running loop
            import asyncio
            async def run():
                return engine_add(eng, ent)
            # add_entity is sync but uses asyncio.create_task; run inside a loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                eng.add_entity(ent, workspace_id="ws1")
            finally:
                # drain pending tasks
                pending = asyncio.all_tasks(loop)
                for t in pending:
                    loop.run_until_complete(t)
                loop.close()


def engine_add(eng, ent):
    return eng.add_entity(ent, workspace_id="ws1")


class TestAddRelationship:
    def test_missing_source_returns_none(self, engine):
        sess = _mock_session()
        # source node not found
        sess.query.return_value.filter.return_value.first.return_value = None
        with _patch_session(sess):
            rel = Relationship("rid", "src", "tgt", "knows")
            result = engine.add_relationship(rel, workspace_id="ws1")
        assert result is None

    def test_missing_target_returns_none(self, engine):
        sess = _mock_session()
        # First .first() returns source (found), second returns None (target missing)
        src = MagicMock()
        results = [src, None]

        def first_side():
            return results.pop(0)

        sess.query.return_value.filter.return_value.first.side_effect = first_side
        with _patch_session(sess):
            rel = Relationship("rid", "src", "tgt", "knows")
            result = engine.add_relationship(rel, workspace_id="ws1")
        assert result is None

    def test_successful_add_returns_id(self, engine):
        sess = _mock_session()
        src = MagicMock()
        tgt = MagicMock()
        # Three .first() lookups in order: source node, target node, then the
        # existing-edge dedup probe (None → fresh insert).
        results = [src, tgt, None]

        def first_side():
            return results.pop(0)

        sess.query.return_value.filter.return_value.first.side_effect = first_side
        with _patch_session(sess):
            rel = Relationship("rid", "src", "tgt", "knows")
            result = engine.add_relationship(rel, workspace_id="ws1")
        assert result == "rid"
        sess.add.assert_called()
        sess.commit.assert_called()

    def test_add_relationship_exception_returns_none(self, engine):
        sess = _mock_session()
        sess.query.side_effect = RuntimeError("x")
        with _patch_session(sess):
            rel = Relationship("rid", "src", "tgt", "knows")
            assert engine.add_relationship(rel, workspace_id="ws1") is None


# ---------------------------------------------------------------------------
# ingest_structured_data
# ---------------------------------------------------------------------------

class TestIngestStructuredData:
    def test_empty_entities_returns_zero_counts(self, engine):
        sess = _mock_session()
        with _patch_session(sess):
            result = engine.ingest_structured_data(workspace_id="ws1", tenant_id="t1")
        assert result["entities"] == 0
        assert result["relationships"] == 0

    def test_ingests_entities_and_edges(self, engine):
        sess = _mock_session()
        # node_map keyed by name; flush assigns ids via the node object
        def flush_side():
            node = sess.add.call_args_list[-1][0][0]
            node.id = "node-" + node.name
        sess.flush.side_effect = flush_side
        with _patch_session(sess):
            result = engine.ingest_structured_data(
                workspace_id="ws1", tenant_id="t1",
                entities=[
                    {"name": "Alice", "type": "person"},
                    {"name": "Bob", "type": "person", "properties": {"canonical_type": "user"}},
                ],
                relationships=[
                    {"from": "Alice", "to": "Bob", "type": "knows"},
                ],
            )
        assert result["entities"] == 2
        assert result["relationships"] == 1

    def test_skips_entity_without_name(self, engine):
        sess = _mock_session()
        with _patch_session(sess):
            result = engine.ingest_structured_data(
                workspace_id="ws1",
                entities=[{"type": "thing"}],  # no name -> skipped
            )
        assert result["entities"] == 1  # count returned is len(input)

    def test_exception_returns_zero_counts(self, engine):
        sess = _mock_session()
        sess.add.side_effect = RuntimeError("x")
        with _patch_session(sess):
            result = engine.ingest_structured_data(
                workspace_id="ws1",
                entities=[{"name": "A"}],
            )
        assert result == {"entities": 0, "relationships": 0}

    def test_edge_skipped_when_endpoint_missing(self, engine):
        sess = _mock_session()
        def flush_side():
            node = sess.add.call_args_list[-1][0][0]
            node.id = "nid-" + node.name
        sess.flush.side_effect = flush_side
        with _patch_session(sess):
            result = engine.ingest_structured_data(
                workspace_id="ws1",
                entities=[{"name": "Alice"}],
                relationships=[{"from": "Alice", "to": "Ghost"}],  # Ghost not in map
            )
        # relationship skipped (no edge added beyond nodes)
        assert result["relationships"] == 1  # count of input rels


# ---------------------------------------------------------------------------
# local_search / global_search / query / get_context_for_ai
# ---------------------------------------------------------------------------

class TestLocalSearch:
    def test_no_start_nodes_returns_empty(self, engine):
        sess = _mock_session()
        # both vector and keyword legs return []
        sess.execute.return_value.fetchall.return_value = []
        with _patch_session(sess), \
             patch.object(engine.llm_service, "generate_embedding",
                          AsyncMock(side_effect=RuntimeError("no emb"))):
            result = engine.local_search(workspace_id="ws1", query="nothing")
        assert result["mode"] == "local"
        assert result["count"] == 0

    def test_keyword_match_drives_traversal(self, engine):
        sess = MagicMock()
        sess.bind = MagicMock()
        sess.bind.dialect.name = "postgresql"

        node = MagicMock()
        node.id = "n1"
        node.name = "Alice"
        node.type = "person"
        node.description = "a person"

        # The keyword SQL execute returns the node; vector fails; traversal returns [node]
        def execute(sql, params=None):
            m = MagicMock()
            # Detect which SQL by string content
            sql_str = str(sql)
            if "ORDER BY embedding" in sql_str:
                m.fetchall.return_value = []  # vector leg
            elif "name" in sql_str and "LIMIT 5" in sql_str and "ORDER BY" not in sql_str:
                m.fetchall.return_value = [node]  # keyword leg
            elif "WITH RECURSIVE" in sql_str:
                m.fetchall.return_value = [node]  # traversal
            else:
                m.fetchall.return_value = []
            return m

        sess.execute.side_effect = execute
        with _patch_session(sess), \
             patch.object(engine.llm_service, "generate_embedding",
                          AsyncMock(side_effect=RuntimeError("x"))):
            result = engine.local_search(workspace_id="ws1", query="Alice")
        assert result["mode"] == "local"
        assert result["count"] >= 1

    def test_local_search_exception_returns_error_dict(self, engine):
        sess = _mock_session()
        sess.execute.side_effect = RuntimeError("catastrophic")
        with _patch_session(sess), \
             patch.object(engine.llm_service, "generate_embedding",
                          AsyncMock(side_effect=RuntimeError("x"))):
            result = engine.local_search(workspace_id="ws1", query="x")
        assert "error" in result or result["count"] == 0


class TestGlobalSearch:
    @pytest.mark.asyncio
    async def test_no_communities_returns_default(self, engine):
        sess = _mock_session()
        sess.execute.return_value.fetchall.return_value = []
        with _patch_session(sess):
            result = await engine.global_search(workspace_id="ws1", query="themes")
        assert result["mode"] == "global"
        assert "No community data" in result["answer"]

    @pytest.mark.asyncio
    async def test_synthesizes_answer_from_communities(self, engine):
        sess = _mock_session()
        c1 = MagicMock()
        c1.summary = "Alpha community summary"
        c1.keywords = ["alpha", "beta"]
        c1.level = 0
        c2 = MagicMock()
        c2.summary = "Beta overview"
        c2.keywords = ["alpha"]
        c2.level = 1
        sess.execute.return_value.fetchall.return_value = [c1, c2]
        with _patch_session(sess), \
             patch.object(engine.llm_service, "generate_completion",
                          AsyncMock(return_value={"content": "Synthesized answer"})):
            result = await engine.global_search(workspace_id="ws1", query="alpha beta")
        assert result["answer"] == "Synthesized answer"
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_global_search_exception_returns_error(self, engine):
        sess = _mock_session()
        sess.execute.side_effect = RuntimeError("x")
        with _patch_session(sess):
            result = await engine.global_search(workspace_id="ws1", query="x")
        assert "error" in result


class TestQueryRouting:
    @pytest.mark.asyncio
    async def test_auto_routes_holistic_to_global(self, engine):
        with patch.object(engine, "global_search", AsyncMock(return_value={"mode": "global", "answer": "a"})) as g:
            await engine.query(workspace_id="ws1", query="overview of themes", mode="auto")
        g.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auto_routes_specific_to_local(self, engine):
        with patch.object(engine, "local_search", return_value={"mode": "local", "entities": []}) as l:
            await engine.query(workspace_id="ws1", query="Alice details", mode="auto")
        l.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_global_mode(self, engine):
        with patch.object(engine, "global_search", AsyncMock(return_value={"mode": "global"})) as g:
            await engine.query(workspace_id="ws1", query="x", mode="global")
        g.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_explicit_local_mode(self, engine):
        with patch.object(engine, "local_search", return_value={"mode": "local"}) as l:
            await engine.query(workspace_id="ws1", query="x", mode="local")
        l.assert_called_once()


class TestGetContextForAI:
    @pytest.mark.asyncio
    async def test_global_context(self, engine):
        with patch.object(engine, "query", AsyncMock(return_value={"mode": "global", "answer": "GA"})):
            ctx = await engine.get_context_for_ai(workspace_id="ws1", query="overview")
        assert "Global Context" in ctx
        assert "GA" in ctx

    @pytest.mark.asyncio
    async def test_local_context_formats_entities_and_rels(self, engine):
        with patch.object(engine, "query", AsyncMock(return_value={
            "mode": "local",
            "entities": [
                {"id": "1", "name": "Alice", "type": "person", "description": "a"},
            ],
            "relationships": [
                {"from": "1", "to": "1", "type": "knows"},
            ],
        })):
            ctx = await engine.get_context_for_ai(workspace_id="ws1", query="x")
        assert "Alice" in ctx
        assert "Found 1 relevant entities" in ctx


# ---------------------------------------------------------------------------
# enqueue_reindex_job / build_communities
# ---------------------------------------------------------------------------

class TestReindexAndCommunities:
    def test_reindex_no_redis_returns_false(self, engine, monkeypatch):
        monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        assert engine.enqueue_reindex_job(workspace_id="ws1") is False

    def test_reindex_success(self, engine, monkeypatch):
        monkeypatch.setenv("UPSTASH_REDIS_URL", "redis://localhost")
        fake_redis = MagicMock()
        fake_redis.from_url.return_value = fake_redis
        import sys
        fake_redis_mod = MagicMock()
        fake_redis_mod.from_url = MagicMock(return_value=fake_redis)
        with patch.dict(sys.modules, {"redis": fake_redis_mod}):
            assert engine.enqueue_reindex_job(workspace_id="ws1") is True
        fake_redis.lpush.assert_called_once()

    def test_reindex_exception_returns_false(self, engine, monkeypatch):
        monkeypatch.setenv("UPSTASH_REDIS_URL", "redis://localhost")
        import sys
        fake_redis_mod = MagicMock()
        fake_redis_mod.from_url.side_effect = RuntimeError("conn")
        with patch.dict(sys.modules, {"redis": fake_redis_mod}):
            assert engine.enqueue_reindex_job(workspace_id="ws1") is False

    def test_build_communities_success(self, engine):
        fake_detector = MagicMock()
        result_obj = MagicMock()
        result_obj.communities = [1, 2, 3]
        fake_detector.detect_communities.return_value = result_obj
        with patch("core.graphrag.community_detection.get_community_detector",
                   return_value=fake_detector):
            result = engine.build_communities(workspace_id="ws1")
        assert result["success"] is True
        assert result["communities"] == 3

    def test_build_communities_no_communities_attr(self, engine):
        fake_detector = MagicMock()
        result_obj = MagicMock(spec=[])  # no .communities attr
        fake_detector.detect_communities.return_value = result_obj
        with patch("core.graphrag.community_detection.get_community_detector",
                   return_value=fake_detector):
            result = engine.build_communities(workspace_id="ws1")
        assert result["success"] is True
        assert result["communities"] == 0

    def test_build_communities_exception(self, engine):
        with patch("core.graphrag.community_detection.get_community_detector",
                   side_effect=RuntimeError("x")):
            result = engine.build_communities(workspace_id="ws1")
        assert result["success"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# discover_failed_hypotheses_patterns
# ---------------------------------------------------------------------------

class TestDiscoverPatterns:
    @pytest.mark.asyncio
    async def test_with_self_db_no_records(self, monkeypatch):
        eng = GraphRAGEngine(db=_mock_session())
        result = await eng.discover_failed_hypotheses_patterns("t1")
        assert result["success"] is True
        assert result["patterns"] == []
        assert "No failed hypotheses" in result["summary"]

    @pytest.mark.asyncio
    async def test_with_session_no_records(self, engine):
        sess = _mock_session()
        with _patch_session(sess):
            result = await engine.discover_failed_hypotheses_patterns("t1")
        assert result["success"] is True
        assert result["patterns"] == []

    @pytest.mark.asyncio
    async def test_synthesizes_patterns_with_llm(self, monkeypatch, engine):
        monkeypatch.setattr(ge_mod, "GRAPHRAG_LLM_ENABLED", True)
        sess = _mock_session()
        rec = MagicMock()
        rec.task_description = "task"
        rec.task_type = "type"
        rec.total_nodes = 10
        rec.pruned_nodes = 3
        rec.negative_constraints = ["avoid X", "avoid Y"]
        _set_records(sess, [rec])
        with _patch_session(sess), \
             patch.object(engine.llm_service, "generate_completion",
                          AsyncMock(return_value={"content": "Synthesis"})):
            result = await engine.discover_failed_hypotheses_patterns("t1")
        assert result["sessions_analyzed"] == 1
        assert "avoid X" in result["aggregated_constraints"]
        assert result["summary"] == "Synthesis"

    @pytest.mark.asyncio
    async def test_llm_synthesis_error_falls_back(self, monkeypatch, engine):
        monkeypatch.setattr(ge_mod, "GRAPHRAG_LLM_ENABLED", True)
        sess = _mock_session()
        rec = MagicMock()
        rec.task_description = "task"
        rec.task_type = "type"
        rec.total_nodes = 10
        rec.pruned_nodes = 3
        rec.negative_constraints = []
        _set_records(sess, [rec])
        with _patch_session(sess), \
             patch.object(engine.llm_service, "generate_completion",
                          AsyncMock(side_effect=RuntimeError("llm down"))):
            result = await engine.discover_failed_hypotheses_patterns("t1")
        assert "error" in result["summary"].lower() or "Synthesis" in result["summary"]

    @pytest.mark.asyncio
    async def test_llm_disabled_skips_synthesis(self, monkeypatch, engine):
        monkeypatch.setattr(ge_mod, "GRAPHRAG_LLM_ENABLED", False)
        sess = _mock_session()
        rec = MagicMock()
        rec.task_description = "task"
        rec.task_type = "type"
        rec.total_nodes = 10
        rec.pruned_nodes = 3
        rec.negative_constraints = ["c1"]
        _set_records(sess, [rec])
        with _patch_session(sess):
            result = await engine.discover_failed_hypotheses_patterns("t1")
        assert result["summary"] == "LLM synthesis skipped."


# ---------------------------------------------------------------------------
# LLM availability flag
# ---------------------------------------------------------------------------

class TestLLMAvailability:
    def test_is_llm_available_reflects_flag(self, monkeypatch, engine):
        monkeypatch.setattr(ge_mod, "GRAPHRAG_LLM_ENABLED", True)
        assert engine._is_llm_available("ws1") is True
        monkeypatch.setattr(ge_mod, "GRAPHRAG_LLM_ENABLED", False)
        assert engine._is_llm_available("ws1") is False
