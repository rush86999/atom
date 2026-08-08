# -*- coding: utf-8 -*-
"""
Coverage + bug-hunt tests for core/mini_app_service.py.

Exercises the pure validation helpers, the state-envelope/storage/record op
helpers, the async integration callback handler (scope gate), and the DB-backed
logic-checkpoint + publish/install + status-probe code paths against a real
in-memory SQLite DB. Bug-hunt tests use the ``BUG:`` docstring convention and
were written to FAIL before the source fix.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

import core.mini_app_service as svc
from core.models import (
    Canvas,
    CanvasAudit,
    CanvasState,
    ComponentInstallation,
    MiniApp,
    MiniAppAsset,
)


# ---------------------------------------------------------------------------
# Real-DB fixture (in-memory SQLite, all tables, FKs off).
# ---------------------------------------------------------------------------
@pytest.fixture
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from core.models_registration import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def canvas(db):
    c = Canvas(
        id="canvas-1", tenant_id="t1", created_by="u1", name="c",
        canvas_type="mini_app", content={"blocks": []}, style={},
    )
    db.add(c)
    db.commit()
    return c


@pytest.fixture
def app(db, canvas):
    a = MiniApp(
        id="app-1", tenant_id="t1", created_by="u1", name="App",
        version="1.0.0", manifest={"declared_scopes": ["canvas_render"]},
        blueprint_canvas_id=canvas.id, status="draft", runtime_version=0,
    )
    db.add(a)
    db.commit()
    return a


# ===========================================================================
# Manifest validation
# ===========================================================================
class TestValidateManifest:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be an object"):
            svc.validate_manifest("not a dict")

    def test_empty_scopes_raises(self):
        with pytest.raises(ValueError, match="declared_scopes"):
            svc.validate_manifest({"declared_scopes": []})

    def test_scopes_not_list_raises(self):
        with pytest.raises(ValueError, match="declared_scopes"):
            svc.validate_manifest({"declared_scopes": "x"})

    def test_star_scope_ok(self):
        svc.validate_manifest({"declared_scopes": ["*"]})

    def test_known_scope_ok(self):
        svc.validate_manifest({"declared_scopes": ["canvas_render"]})

    def test_unknown_scope_raises(self):
        with pytest.raises(ValueError, match="unknown declared scope"):
            svc.validate_manifest({"declared_scopes": ["bogus_scope"]})

    def test_dependencies_not_list_raises(self):
        with pytest.raises(ValueError, match="dependencies"):
            svc.validate_manifest({"declared_scopes": ["*"], "dependencies": "x"})

    def test_dependencies_wrong_elem_raises(self):
        with pytest.raises(ValueError, match="dependencies"):
            svc.validate_manifest({"declared_scopes": ["*"], "dependencies": [1]})

    def test_bad_base_image_raises(self):
        with pytest.raises(ValueError, match="base_image"):
            svc.validate_manifest({"declared_scopes": ["*"], "base_image": "ubuntu:x"})

    def test_storage_enabled_not_bool(self):
        with pytest.raises(ValueError, match="storage.enabled"):
            svc.validate_manifest({"declared_scopes": ["*"], "storage": {"enabled": "x"}})

    def test_storage_bad_backend(self):
        with pytest.raises(ValueError, match="storage.backend"):
            svc.validate_manifest({"declared_scopes": ["*"], "storage": {"backend": "s3"}})

    def test_storage_max_bytes_zero(self):
        with pytest.raises(ValueError, match="max_bytes_per_object"):
            svc.validate_manifest({"declared_scopes": ["*"], "storage": {"max_bytes_per_object": 0}})

    def test_storage_max_bytes_str(self):
        with pytest.raises(ValueError, match="max_bytes_per_object"):
            svc.validate_manifest({"declared_scopes": ["*"], "storage": {"max_bytes_per_object": "5"}})

    def test_db_not_dict(self):
        with pytest.raises(ValueError, match="manifest.db must be an object"):
            svc.validate_manifest({"declared_scopes": ["*"], "db": "x"})

    def test_db_enabled_not_bool(self):
        with pytest.raises(ValueError, match="db.enabled"):
            svc.validate_manifest({"declared_scopes": ["*"], "db": {"enabled": 1}})

    def test_db_max_records_neg(self):
        with pytest.raises(ValueError, match="max_records_per_series"):
            svc.validate_manifest({"declared_scopes": ["*"], "db": {"max_records_per_series": -1}})

    def test_db_max_record_bytes_float(self):
        with pytest.raises(ValueError, match="max_record_bytes"):
            svc.validate_manifest({"declared_scopes": ["*"], "db": {"max_record_bytes": 1.5}})

    def test_record_queries_non_str(self):
        with pytest.raises(ValueError, match="record_queries"):
            svc.validate_manifest({"declared_scopes": ["*"], "db": {"record_queries": [1]}})

    def test_record_queries_bad_pattern(self):
        with pytest.raises(ValueError, match="record_queries entry"):
            svc.validate_manifest({"declared_scopes": ["*"], "db": {"record_queries": ["Has Space"]}})

    def test_record_queries_good(self):
        svc.validate_manifest({"declared_scopes": ["*"], "db": {"record_queries": ["series_1"]}})

    def test_data_sources_not_list(self):
        with pytest.raises(ValueError, match="data_sources must be a list"):
            svc.validate_manifest({"declared_scopes": ["*"], "data_sources": "x"})

    def test_data_sources_entry_not_dict(self):
        with pytest.raises(ValueError, match="data_sources entry"):
            svc.validate_manifest({"declared_scopes": ["*"], "data_sources": ["x"]})

    def test_data_sources_bad_type(self):
        with pytest.raises(ValueError, match="data_sources type"):
            svc.validate_manifest({"declared_scopes": ["*"], "data_sources": [{"type": "unknown"}]})

    def test_data_sources_ok(self):
        svc.validate_manifest({
            "declared_scopes": ["*"],
            "data_sources": [{"type": "documents.search", "query": "q"}],
        })

    def test_integrations_not_list(self):
        with pytest.raises(ValueError, match="integrations must be a list"):
            svc.validate_manifest({"declared_scopes": ["*"], "integrations": "x"})

    def test_integration_missing_service(self):
        with pytest.raises(ValueError, match=r"integrations\[\]\.service"):
            svc.validate_manifest({"declared_scopes": ["*"], "integrations": [{"action": "a"}]})

    def test_integration_missing_action(self):
        with pytest.raises(ValueError, match=r"integrations\[\]\.action"):
            svc.validate_manifest({"declared_scopes": ["*"], "integrations": [{"service": "s"}]})

    def test_integration_params_not_dict(self):
        with pytest.raises(ValueError, match="params must be an object"):
            svc.validate_manifest({
                "declared_scopes": ["*"],
                "integrations": [{"service": "s", "action": "a", "params": []}],
            })

    def test_integration_ok(self):
        svc.validate_manifest({
            "declared_scopes": ["*"],
            "integrations": [{"service": "s", "action": "a", "params": {"q": 1}}],
        })

    def test_mcp_servers_alias_ok(self, caplog):
        with caplog.at_level("WARNING", logger="core.mini_app_service"):
            svc.validate_manifest({
                "declared_scopes": ["*"],
                "mcp_servers": [{"service": "s", "action": "a"}],
            })
        assert any("deprecated" in r.message for r in caplog.records)

    def test_assets_not_list(self):
        with pytest.raises(ValueError, match="assets must be a list"):
            svc.validate_manifest({"declared_scopes": ["*"], "assets": "x"})

    def test_assets_wrong_elem(self):
        with pytest.raises(ValueError, match="assets must be a list"):
            svc.validate_manifest({"declared_scopes": ["*"], "assets": [1]})

    def test_tests_block_validated(self):
        with pytest.raises(ValueError, match="test.expect_state"):
            svc.validate_manifest({"declared_scopes": ["*"], "tests": [{"expect_state": "x"}]})


# ===========================================================================
# validate_tests
# ===========================================================================
class TestValidateTests:
    def test_not_list(self):
        with pytest.raises(ValueError, match="tests must be a list"):
            svc.validate_tests("x")

    def test_case_not_dict(self):
        with pytest.raises(ValueError, match="each test case"):
            svc.validate_tests(["x"])

    def test_no_assertion(self):
        with pytest.raises(ValueError, match="expect_state and/or expect_ops"):
            svc.validate_tests([{"name": "n"}])

    def test_expect_ops_not_list(self):
        with pytest.raises(ValueError, match="expect_ops must be a list"):
            svc.validate_tests([{"expect_ops": "x"}])

    def test_name_not_str(self):
        with pytest.raises(ValueError, match="test.name must be a string"):
            svc.validate_tests([{"name": 1, "expect_state": {}}])

    def test_initial_state_not_dict(self):
        with pytest.raises(ValueError, match="initial_state must be an object"):
            svc.validate_tests([{"initial_state": "x", "expect_state": {}}])

    def test_inputs_not_dict(self):
        with pytest.raises(ValueError, match="inputs must be an object"):
            svc.validate_tests([{"inputs": "x", "expect_state": {}}])

    def test_valid_case(self):
        svc.validate_tests([{"name": "ok", "expect_state": {"a": 1}, "expect_ops": [{"op": "put", "key": "k"}]}])


# ===========================================================================
# resolve_effective_scopes — never-widens guarantee
# ===========================================================================
class TestResolveEffectiveScopes:
    def test_star_student_never_widens(self):
        result = svc.resolve_effective_scopes({"declared_scopes": ["*"]}, tier="student")
        # Student floor has no wildcard.
        assert "*" not in result
        assert "canvas_render" in result

    def test_star_autonomous_wildcard(self):
        result = svc.resolve_effective_scopes({"declared_scopes": ["*"]}, tier="autonomous")
        assert result == ("*",)

    def test_specific_scopes_intersected(self):
        result = svc.resolve_effective_scopes(
            {"declared_scopes": ["canvas_render"]}, tier="student"
        )
        assert result == ("canvas_render",)

    def test_no_declared_defaults_star(self):
        # Missing declared_scopes -> treated as ['*'].
        result = svc.resolve_effective_scopes({}, tier="intern")
        assert len(result) > 0

    def test_viewer_object_tier(self):
        viewer = SimpleNamespace(tier="supervised")
        result = svc.resolve_effective_scopes({"declared_scopes": ["*"]}, viewer=viewer)
        assert "*" not in result  # supervised floor, not wildcard

    def test_viewer_none_defaults_student(self):
        result = svc.resolve_effective_scopes({"declared_scopes": ["*"]}, viewer=None)
        assert "*" not in result


# ===========================================================================
# syntax_check
# ===========================================================================
class TestSyntaxCheck:
    def test_valid(self):
        svc.syntax_check("x = 1\n")

    def test_empty_raises(self):
        with pytest.raises(SyntaxError, match="Empty"):
            svc.syntax_check("")

    def test_whitespace_only_raises(self):
        with pytest.raises(SyntaxError, match="Empty"):
            svc.syntax_check("   \n  ")

    def test_invalid_raises(self):
        with pytest.raises(SyntaxError):
            svc.syntax_check("def f(:\n")


# ===========================================================================
# _wrap_source / _parse_envelope / _json_bytes
# ===========================================================================
class TestEnvelopeHelpers:
    def test_wrap_source_includes_marker(self):
        out = svc._wrap_source("state['x'] = 1")
        assert "try:" in out
        assert "__MINIAPP_STATE__:" in out
        assert "storage_ops" in out
        assert "record_ops" in out

    def test_wrap_source_empty_body(self):
        out = svc._wrap_source("")
        assert "try:" in out

    def test_parse_envelope_empty(self):
        assert svc._parse_envelope("") is None

    def test_parse_envelope_no_marker(self):
        assert svc._parse_envelope("hello world") is None

    def test_parse_envelope_valid(self):
        out = "log\n__MINIAPP_STATE__:" + '{"state": {"runs": 1}, "storage_ops": []}'
        env = svc._parse_envelope(out)
        assert env == {"state": {"runs": 1}, "storage_ops": []}

    def test_parse_envelope_takes_last(self):
        out = (
            '__MINIAPP_STATE__:{"state": {"v": 1}}\n'
            'tail\n'
            '__MINIAPP_STATE__:{"state": {"v": 2}}'
        )
        env = svc._parse_envelope(out)
        assert env["state"] == {"v": 2}

    def test_parse_envelope_bad_json(self):
        out = "__MINIAPP_STATE__:{not valid json"
        assert svc._parse_envelope(out) is None

    def test_json_bytes_serializable(self):
        assert svc._json_bytes({"a": 1}) == 8  # '{"a": 1}'

    def test_json_bytes_unserializable(self):
        # Unserializable -> returns cap+1 (treated as too large).
        assert svc._json_bytes(object()) > svc._DEFAULT_DATA_SOURCE_CAP


# ===========================================================================
# _validate_storage_op
# ===========================================================================
class TestValidateStorageOp:
    def test_non_dict(self):
        assert svc._validate_storage_op("x", 100) is None

    def test_bad_op(self):
        assert svc._validate_storage_op({"op": "foo", "key": "k"}, 100) is None

    def test_missing_key(self):
        assert svc._validate_storage_op({"op": "put"}, 100) is None

    def test_empty_key(self):
        assert svc._validate_storage_op({"op": "put", "key": ""}, 100) is None

    def test_long_key(self):
        assert svc._validate_storage_op({"op": "put", "key": "k" * 501, "data": "d"}, 100) is None

    def test_put_no_data(self):
        assert svc._validate_storage_op({"op": "put", "key": "k"}, 100) is None

    def test_put_str_data(self):
        r = svc._validate_storage_op({"op": "put", "key": "k", "data": "hi"}, 100)
        assert r == {"op": "put", "key": "k", "data": b"hi", "content_type": None}

    def test_put_bytes_data(self):
        r = svc._validate_storage_op({"op": "put", "key": "k", "data": b"\x00\x01"}, 100)
        assert r["data"] == b"\x00\x01"

    def test_put_base64_data(self):
        r = svc._validate_storage_op({"op": "put", "key": "k", "data": "aGk=", "encoding": "base64"}, 100)
        assert r["data"] == b"hi"

    def test_put_base64_invalid(self):
        assert svc._validate_storage_op({"op": "put", "key": "k", "data": "@@@", "encoding": "base64"}, 100) is None

    def test_put_base64_non_str(self):
        assert svc._validate_storage_op({"op": "put", "key": "k", "data": 123, "encoding": "base64"}, 100) is None

    def test_put_bad_data_type(self):
        assert svc._validate_storage_op({"op": "put", "key": "k", "data": 123}, 100) is None

    def test_put_too_large(self):
        assert svc._validate_storage_op({"op": "put", "key": "k", "data": "x" * 200}, 100) is None

    def test_put_with_content_type(self):
        r = svc._validate_storage_op(
            {"op": "put", "key": "k", "data": "hi", "content_type": "text/plain"}, 100
        )
        assert r["content_type"] == "text/plain"

    def test_get(self):
        assert svc._validate_storage_op({"op": "get", "key": "k"}, 100) == {"op": "get", "key": "k"}

    def test_delete(self):
        assert svc._validate_storage_op({"op": "delete", "key": "k"}, 100) == {"op": "delete", "key": "k"}


# ===========================================================================
# _validate_record_op
# ===========================================================================
class TestValidateRecordOp:
    def _mb(self):
        from core.mini_app_db_service import DEFAULT_MAX_RECORD_BYTES
        return DEFAULT_MAX_RECORD_BYTES

    def test_non_dict(self):
        assert svc._validate_record_op("x", self._mb()) is None

    def test_unknown_op(self):
        assert svc._validate_record_op({"op": "bogus"}, self._mb()) is None

    def test_append_ok(self):
        r = svc._validate_record_op({"op": "append", "series": "s", "data": {"x": 1}}, self._mb())
        assert r["op"] == "append" and r["data"] == {"x": 1} and r["id"] is None

    def test_append_with_id(self):
        r = svc._validate_record_op({"op": "append", "series": "s", "data": {"x": 1}, "id": "r1"}, self._mb())
        assert r["id"] == "r1"

    def test_append_empty_id_rejected(self):
        assert svc._validate_record_op({"op": "append", "series": "s", "data": {"x": 1}, "id": ""}, self._mb()) is None

    def test_append_bad_series(self):
        assert svc._validate_record_op({"op": "append", "series": "BAD!", "data": {"x": 1}}, self._mb()) is None

    def test_append_missing_data(self):
        assert svc._validate_record_op({"op": "append", "series": "s"}, self._mb()) is None

    def test_get_ok(self):
        r = svc._validate_record_op({"op": "get", "series": "s", "id": "r1"}, self._mb())
        assert r["id"] == "r1"

    def test_get_missing_id(self):
        assert svc._validate_record_op({"op": "get", "series": "s"}, self._mb()) is None

    def test_query_defaults(self):
        r = svc._validate_record_op({"op": "query", "series": "s"}, self._mb())
        assert r["limit"] == 100 and r["order"] == "desc" and r["filter"] == {}

    def test_query_limit_too_small(self):
        assert svc._validate_record_op({"op": "query", "series": "s", "limit": 0}, self._mb()) is None

    def test_query_limit_too_large(self):
        assert svc._validate_record_op({"op": "query", "series": "s", "limit": 50000}, self._mb()) is None

    def test_query_bad_order(self):
        assert svc._validate_record_op({"op": "query", "series": "s", "order": "x"}, self._mb()) is None

    def test_count_ok(self):
        r = svc._validate_record_op({"op": "count", "series": "s"}, self._mb())
        assert r["filter"] == {}

    def test_update_ok(self):
        r = svc._validate_record_op({"op": "update", "series": "s", "id": "r1", "data": {"x": 2}}, self._mb())
        assert r["data"] == {"x": 2}

    def test_update_missing_id(self):
        assert svc._validate_record_op({"op": "update", "series": "s", "data": {"x": 2}}, self._mb()) is None

    def test_update_many_with_filter(self):
        r = svc._validate_record_op({"op": "update_many", "series": "s", "data": {"x": 2}, "filter": {"a": 1}}, self._mb())
        assert r["filter"] == {"a": 1}

    def test_update_many_no_filter(self):
        r = svc._validate_record_op({"op": "update_many", "series": "s", "data": {"x": 2}}, self._mb())
        assert r["filter"] == {}

    def test_delete_ok(self):
        r = svc._validate_record_op({"op": "delete", "series": "s", "id": "r1"}, self._mb())
        assert r["id"] == "r1"

    def test_delete_series(self):
        r = svc._validate_record_op({"op": "delete_series", "series": "s"}, self._mb())
        assert r["op"] == "delete_series"

    def test_clear_no_series(self):
        r = svc._validate_record_op({"op": "clear"}, self._mb())
        assert r["op"] == "clear" and r["series"] is None

    def test_list_series_no_series(self):
        r = svc._validate_record_op({"op": "list_series"}, self._mb())
        assert r["op"] == "list_series"


# ===========================================================================
# _execute_storage_op (real DB)
# ===========================================================================
class TestExecuteStorageOp:
    def _setup(self, db, canvas, app):
        storage = MagicMock()
        storage.store.return_value = "file:///data/k"
        storage.retrieve.return_value = b"hello"
        return storage

    def test_put_creates_asset_row(self, db, canvas, app):
        storage = self._setup(db, canvas, app)
        valid = {"op": "put", "key": "k", "data": b"hello", "content_type": "text/plain"}
        r = svc._execute_storage_op(valid, storage, db, canvas, app)
        assert r["ok"] is True and r["uri"] == "file:///data/k"
        row = db.query(MiniAppAsset).filter(MiniAppAsset.key == "k").one()
        assert row.size == 5

    def test_put_updates_existing_row(self, db, canvas, app):
        storage = self._setup(db, canvas, app)
        svc._execute_storage_op({"op": "put", "key": "k", "data": b"hello"}, storage, db, canvas, app)
        storage.store.return_value = "file:///data/k2"
        r = svc._execute_storage_op({"op": "put", "key": "k", "data": b"bye"}, storage, db, canvas, app)
        assert r["ok"] is True
        rows = db.query(MiniAppAsset).filter(MiniAppAsset.key == "k").all()
        assert len(rows) == 1
        assert rows[0].uri == "file:///data/k2"

    def test_get_returns_base64(self, db, canvas, app):
        storage = self._setup(db, canvas, app)
        r = svc._execute_storage_op({"op": "get", "key": "k"}, storage, db, canvas, app)
        import base64
        assert r["ok"] is True
        assert base64.b64decode(r["data"]) == b"hello"
        assert r["encoding"] == "base64"

    def test_get_not_found(self, db, canvas, app):
        storage = self._setup(db, canvas, app)
        storage.retrieve.return_value = None
        r = svc._execute_storage_op({"op": "get", "key": "k"}, storage, db, canvas, app)
        assert r["ok"] is False and r["error"] == "not_found"

    def test_delete_removes_row(self, db, canvas, app):
        storage = self._setup(db, canvas, app)
        svc._execute_storage_op({"op": "put", "key": "k", "data": b"x"}, storage, db, canvas, app)
        storage.delete.return_value = True
        r = svc._execute_storage_op({"op": "delete", "key": "k"}, storage, db, canvas, app)
        assert r["ok"] is True
        assert db.query(MiniAppAsset).filter(MiniAppAsset.key == "k").count() == 0

    def test_delete_not_in_store(self, db, canvas, app):
        storage = self._setup(db, canvas, app)
        storage.delete.return_value = False
        r = svc._execute_storage_op({"op": "delete", "key": "k"}, storage, db, canvas, app)
        assert r["ok"] is False

    def test_unknown_op(self, db, canvas, app):
        storage = self._setup(db, canvas, app)
        r = svc._execute_storage_op({"op": "foo", "key": "k"}, storage, db, canvas, app)
        assert r["ok"] is False and r["error"] == "unknown_op"

    def test_exception_returns_failed(self, db, canvas, app):
        storage = self._setup(db, canvas, app)
        storage.store.side_effect = RuntimeError("disk full")
        r = svc._execute_storage_op({"op": "put", "key": "k", "data": b"x"}, storage, db, canvas, app)
        assert r["ok"] is False and r["error"] == "failed"


# ===========================================================================
# _execute_record_op (real DB)
# ===========================================================================
class TestExecuteRecordOp:
    def test_append_and_get(self, db, canvas, app):
        r = svc._execute_record_op(
            {"op": "append", "series": "s1", "data": {"v": 1}}, db, canvas, app, "u1"
        )
        assert r["ok"] is True and r["seq"] == 1
        got = svc._execute_record_op(
            {"op": "get", "series": "s1", "id": r["id"]}, db, canvas, app, "u1"
        )
        assert got["ok"] is True and got["record"]["data"] == {"v": 1}

    def test_get_not_found(self, db, canvas, app):
        r = svc._execute_record_op(
            {"op": "get", "series": "s1", "id": "missing"}, db, canvas, app, "u1"
        )
        assert r["ok"] is False and r["error"] == "not_found"

    def test_query_and_count(self, db, canvas, app):
        for i in range(3):
            svc._execute_record_op(
                {"op": "append", "series": "s1", "data": {"v": i}}, db, canvas, app, "u1"
            )
        q = svc._execute_record_op(
            {"op": "query", "series": "s1", "filter": {}, "limit": 10, "order": "desc"},
            db, canvas, app, "u1",
        )
        assert q["count"] == 3
        c = svc._execute_record_op(
            {"op": "count", "series": "s1", "filter": {}}, db, canvas, app, "u1"
        )
        assert c["count"] == 3

    def test_update_and_update_many(self, db, canvas, app):
        a = svc._execute_record_op(
            {"op": "append", "series": "s1", "data": {"v": 1}}, db, canvas, app, "u1"
        )
        u = svc._execute_record_op(
            {"op": "update", "series": "s1", "id": a["id"], "data": {"v": 99}},
            db, canvas, app, "u1",
        )
        assert u["ok"] is True and u["record"]["data"] == {"v": 99}
        svc._execute_record_op(
            {"op": "append", "series": "s1", "data": {"v": 2}}, db, canvas, app, "u1"
        )
        um = svc._execute_record_op(
            {"op": "update_many", "series": "s1", "filter": {}, "data": {"flag": True}},
            db, canvas, app, "u1",
        )
        assert um["ok"] is True and um["updated"] == 2

    def test_update_not_found(self, db, canvas, app):
        r = svc._execute_record_op(
            {"op": "update", "series": "s1", "id": "ghost", "data": {"v": 1}},
            db, canvas, app, "u1",
        )
        assert r["ok"] is False and r["error"] == "not_found"

    def test_delete_and_delete_series(self, db, canvas, app):
        a = svc._execute_record_op(
            {"op": "append", "series": "s1", "data": {"v": 1}}, db, canvas, app, "u1"
        )
        d = svc._execute_record_op(
            {"op": "delete", "series": "s1", "id": a["id"]}, db, canvas, app, "u1"
        )
        assert d["ok"] is True
        svc._execute_record_op(
            {"op": "append", "series": "s1", "data": {"v": 2}}, db, canvas, app, "u1"
        )
        ds = svc._execute_record_op(
            {"op": "delete_series", "series": "s1"}, db, canvas, app, "u1"
        )
        assert ds["ok"] is True and ds["deleted"] == 1

    def test_clear_and_list_series(self, db, canvas, app):
        svc._execute_record_op(
            {"op": "append", "series": "s1", "data": {"v": 1}}, db, canvas, app, "u1"
        )
        svc._execute_record_op(
            {"op": "append", "series": "s2", "data": {"v": 2}}, db, canvas, app, "u1"
        )
        ls = svc._execute_record_op({"op": "list_series"}, db, canvas, app, "u1")
        assert ls["ok"] is True
        cl = svc._execute_record_op({"op": "clear"}, db, canvas, app, "u1")
        assert cl["ok"] is True and cl["deleted"] == 2

    def test_unknown_op(self, db, canvas, app):
        r = svc._execute_record_op(
            {"op": "bogus", "series": "s1"}, db, canvas, app, "u1"
        )
        assert r["ok"] is False and r["error"] == "unknown_op"


# ===========================================================================
# _make_callback_handler (async scope gate)
# ===========================================================================
class TestCallbackHandler:
    @pytest.mark.asyncio
    async def test_unknown_kind(self):
        handler = svc._make_callback_handler(None, "t1", ("*",), None, "u1")
        r = await handler({"kind": "bogus"})
        assert r["ok"] is False and "unknown" in r["error"]

    @pytest.mark.asyncio
    async def test_star_scope_allows(self):
        handler = svc._make_callback_handler(None, "t1", ("*",), None, "u1")
        with patch("core.mini_app_integration_dispatch.resolve_backend",
                   new=AsyncMock(return_value=("native", None))), \
             patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": True, "data": {"x": 1}, "backend": "native"})):
            r = await handler({"kind": "fetch_integration", "service": "any", "action": "x", "params": {}})
        assert r["ok"] is True and r["data"] == {"x": 1}

    @pytest.mark.asyncio
    async def test_specific_scope_allowed(self):
        handler = svc._make_callback_handler(None, "t1", ("integrations.notion",), None, "u1")
        with patch("core.mini_app_integration_dispatch.resolve_backend",
                   new=AsyncMock(return_value=("native", None))), \
             patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": True, "data": {}, "backend": "native"})):
            r = await handler({"kind": "fetch_integration", "service": "notion", "action": "search", "params": {}})
        assert r["ok"] is True

    @pytest.mark.asyncio
    async def test_specific_scope_denied(self):
        handler = svc._make_callback_handler(None, "t1", ("integrations.notion",), None, "u1")
        with patch("core.mini_app_integration_dispatch.resolve_backend",
                   new=AsyncMock(return_value=("native", None))):
            r = await handler({"kind": "fetch_integration", "service": "github", "action": "x", "params": {}})
        assert r["ok"] is False and r["error"] == "scope_denied"

    @pytest.mark.asyncio
    async def test_mcp_scope_allowed(self):
        handler = svc._make_callback_handler(None, "t1", ("mcp.server1",), None, "u1")
        with patch("core.mini_app_integration_dispatch.resolve_backend",
                   new=AsyncMock(return_value=("mcp", "server1"))), \
             patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": True, "data": {}, "backend": "mcp"})):
            r = await handler({"kind": "fetch_integration", "service": "svc", "action": "x", "params": {}})
        assert r["ok"] is True

    @pytest.mark.asyncio
    async def test_result_too_large(self):
        handler = svc._make_callback_handler(None, "t1", ("*",), None, "u1")
        big = {"x": "y" * (6 * 1024 * 1024)}
        with patch("core.mini_app_integration_dispatch.resolve_backend",
                   new=AsyncMock(return_value=("native", None))), \
             patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": True, "data": big, "backend": "native"})):
            r = await handler({"kind": "fetch_integration", "service": "any", "action": "x", "params": {}})
        assert r["ok"] is False and r["error"] == "result_too_large"

    @pytest.mark.asyncio
    async def test_dispatch_failure(self):
        handler = svc._make_callback_handler(None, "t1", ("*",), None, "u1")
        with patch("core.mini_app_integration_dispatch.resolve_backend",
                   new=AsyncMock(return_value=("native", None))), \
             patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = await handler({"kind": "fetch_integration", "service": "any", "action": "x", "params": {}})
        assert r["ok"] is False and r["error"] == "failed"


# ===========================================================================
# _inject_integration_sources / _inject_data_sources (async, skipped-on-fail)
# ===========================================================================
class TestInjectSources:
    @pytest.mark.asyncio
    async def test_inject_integration_ok(self):
        manifest = {"integrations": [{"service": "notion", "action": "search", "params": {"q": "x"}}]}
        with patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": True, "data": {"results": [1]}, "backend": "native"})):
            out = await svc._inject_integration_sources(manifest, "t1", None, None, None)
        assert out == {"notion": {"results": [1]}}

    @pytest.mark.asyncio
    async def test_inject_integration_not_ok_skipped(self):
        manifest = {"integrations": [{"service": "x", "action": "y", "params": {}}]}
        with patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": False})):
            out = await svc._inject_integration_sources(manifest, "t1", None, None, None)
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_integration_missing_fields_skipped(self):
        manifest = {"integrations": [{"service": "", "action": ""}]}
        out = await svc._inject_integration_sources(manifest, "t1", None, None, None)
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_integration_exception_skipped(self):
        manifest = {"integrations": [{"service": "x", "action": "y", "params": {}}]}
        with patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(side_effect=RuntimeError("boom"))):
            out = await svc._inject_integration_sources(manifest, "t1", None, None, None)
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_integration_mcp_alias(self):
        # mcp_servers deprecated alias is read when integrations absent.
        manifest = {"mcp_servers": [{"service": "x", "action": "y", "params": {}}]}
        with patch("core.mini_app_integration_dispatch.dispatch",
                   new=AsyncMock(return_value={"ok": True, "data": [1, 2], "backend": "mcp"})):
            out = await svc._inject_integration_sources(manifest, "t1", None, None, None)
        assert out == {"x": [1, 2]}

    @pytest.mark.asyncio
    async def test_inject_data_sources_documents_empty_query_skipped(self):
        manifest = {"data_sources": [{"type": "documents.search", "query": ""}]}
        out = await svc._inject_data_sources(manifest, "t1", None, "u1")
        assert out == {}

    @pytest.mark.asyncio
    async def test_inject_data_sources_documents_ok(self):
        manifest = {"data_sources": [{"type": "documents.search", "query": "hello", "limit": 5}]}
        fake_registry = MagicMock()
        with patch("core.mini_app_service._safe_action_call",
                   new=AsyncMock(return_value={"data": {"results": [{"id": "d1"}]}})):
            out = await svc._inject_data_sources(manifest, "t1", "ws1", "u1")
        assert out.get("documents") == [{"id": "d1"}]

    @pytest.mark.asyncio
    async def test_inject_data_sources_too_large_skipped(self):
        big = {"results": ["x" * (6 * 1024 * 1024)]}
        manifest = {"data_sources": [{"type": "documents.search", "query": "hello"}]}
        with patch("core.mini_app_service._safe_action_call",
                   new=AsyncMock(return_value={"data": big})):
            out = await svc._inject_data_sources(manifest, "t1", None, "u1")
        assert out == {}


# ===========================================================================
# Logic checkpoints (real DB)
# ===========================================================================
class TestLogicCheckpoints:
    def test_record_and_list(self, db, canvas, app):
        v1 = svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "code v1", actor_id="u1")
        v2 = svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "code v2", actor_id="u1")
        assert v1["version"] == 1 and v2["version"] == 2
        hist = svc.list_logic_history(app, db)
        assert [h["version"] for h in hist] == [1, 2]
        assert hist[1]["preview"] == "code v2"

    def test_logic_version_number_increments(self, db, canvas, app):
        assert svc._logic_version_number(db, canvas.id) == 1
        svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "x")
        assert svc._logic_version_number(db, canvas.id) == 2

    def test_list_history_empty_preview(self, db, canvas, app):
        # Insert a snapshot row directly with empty source.
        db.add(CanvasAudit(
            canvas_id=canvas.id, tenant_id="t1", action_type="mini_app_logic",
            user_id="u1", canvas_type="mini_app",
            details_json={"app_id": app.id, "version": 1, "source": ""},
        ))
        db.commit()
        hist = svc.list_logic_history(app, db)
        assert hist[0]["preview"] == ""

    def test_revert_restores_source(self, db, canvas, app):
        svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "code v1", actor_id="u1")
        svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "code v2", actor_id="u1")
        result = svc.revert_logic(app, db, 1, actor_id="u1")
        assert result["source"] == "code v1"
        # The reverted-to source is now the latest checkpoint.
        hist = svc.list_logic_history(app, db)
        assert hist[-1]["preview"] == "code v1"

    def test_revert_missing_version_raises(self, db, canvas, app):
        svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "code v1", actor_id="u1")
        with pytest.raises(ValueError, match="Logic version 99 not found"):
            svc.revert_logic(app, db, 99)


# ===========================================================================
# _read_state / _inject_assets / _inject_record_queries
# ===========================================================================
class TestReadBridgeHelpers:
    def test_read_state_missing_returns_empty(self, db):
        state, version = svc._read_state(db, "nope")
        assert state == {} and version == 0

    def test_read_state_returns_dict_copy(self, db, canvas):
        db.add(CanvasState(canvas_id=canvas.id, tenant_id="t1", state={"a": 1}, version=3))
        db.commit()
        state, version = svc._read_state(db, canvas.id)
        assert state == {"a": 1} and version == 3
        # Mutating the returned dict must not touch the stored row.
        state["a"] = 999
        state2, _ = svc._read_state(db, canvas.id)
        assert state2 == {"a": 1}

    def test_inject_assets_skips_missing(self, db):
        manifest = {"assets": ["a", "b"], "storage": {"max_bytes_per_object": 1024}}
        with patch("core.mini_app_storage.get_mini_app_storage") as get_storage:
            storage = MagicMock()
            storage.retrieve.side_effect = [b"data-a", None]  # b missing
            get_storage.return_value = storage
            out = svc._inject_assets(manifest, "t1", "c1")
        assert out == {"a": "data-a"}

    def test_inject_assets_skips_oversized(self, db, caplog):
        manifest = {"assets": ["big"], "storage": {"max_bytes_per_object": 3}}
        with patch("core.mini_app_storage.get_mini_app_storage") as get_storage:
            storage = MagicMock()
            storage.retrieve.return_value = b"way-too-big-bytes"
            get_storage.return_value = storage
            with caplog.at_level("WARNING", logger="core.mini_app_service"):
                out = svc._inject_assets(manifest, "t1", "c1")
        assert out == {}
        assert any("exceeds injection cap" in r.message for r in caplog.records)

    def test_inject_assets_decode_error_skipped(self, db):
        manifest = {"assets": ["bad"], "storage": {}}
        with patch("core.mini_app_storage.get_mini_app_storage") as get_storage:
            storage = MagicMock()
            storage.retrieve.side_effect = RuntimeError("boom")
            get_storage.return_value = storage
            out = svc._inject_assets(manifest, "t1", "c1")
        assert out == {}

    def test_inject_record_queries_prefetch(self, db, canvas):
        manifest = {"db": {"record_queries": ["s1", "s2"], "record_query_limit": 5}}
        with patch("core.mini_app_db_service.query_records", return_value=[{"v": 1}]) as qr:
            out = svc._inject_record_queries(manifest, db, canvas.id)
        assert out == {"s1": [{"v": 1}], "s2": [{"v": 1}]}
        assert qr.call_count == 2

    def test_inject_record_queries_failure_skipped(self, db, canvas):
        manifest = {"db": {"record_queries": ["s1"]}}
        with patch("core.mini_app_db_service.query_records", side_effect=RuntimeError("boom")):
            out = svc._inject_record_queries(manifest, db, canvas.id)
        assert out == {}


# ===========================================================================
# run_stateful (error paths — no runtime needed)
# ===========================================================================
class TestRunStatefulErrors:
    @pytest.mark.asyncio
    async def test_canvas_not_found(self, db):
        # run_stateful imports get_db_session from core.database at call time.
        class _Ctx:
            def __enter__(self_inner):
                return db
            def __exit__(self_inner, *a):
                pass
        with patch("core.database.get_db_session", return_value=_Ctx()):
            r = await svc.run_stateful("no-such-canvas")
        assert r["success"] is False
        assert "not found" in r["error"]

    @pytest.mark.asyncio
    async def test_canvas_not_mini_app(self, db, canvas):
        # canvas with no mini_app_id
        class _Ctx:
            def __enter__(self_inner):
                return db
            def __exit__(self_inner, *a):
                pass
        with patch("core.database.get_db_session", return_value=_Ctx()):
            r = await svc.run_stateful(canvas.id)
        assert r["success"] is False
        assert "not a mini-app" in r["error"]

    @pytest.mark.asyncio
    async def test_app_not_found(self, db, canvas):
        canvas.mini_app_id = "ghost-app"
        db.commit()
        class _Ctx:
            def __enter__(self_inner):
                return db
            def __exit__(self_inner, *a):
                pass
        with patch("core.database.get_db_session", return_value=_Ctx()):
            r = await svc.run_stateful(canvas.id)
        assert r["success"] is False
        assert "MiniApp" in r["error"]


# ===========================================================================
# status_probe
# ===========================================================================
class TestStatusProbe:
    def test_status_basic(self, db, canvas, app):
        result = svc.status_probe(app, db)
        assert result["app_id"] == "app-1"
        assert result["logic"]["syntax_ok"] in (True, False)
        assert result["runtime"]["available"] in (True, False)
        assert result["db"]["enabled"] in (True, False)
        assert result["scopes"]["declared"] == ["canvas_render"]

    def test_status_with_bad_logic_syntax(self, db, canvas, app):
        # Save logic with a syntax error.
        from core.canvas_logic_service import CanvasLogicService
        CanvasLogicService(db).save_logic(canvas_id=canvas.id, source="def f(:", created_by="u1")
        result = svc.status_probe(app, db)
        assert result["logic"]["syntax_ok"] is False
        assert result["logic"]["syntax_error"] is not None

    def test_status_with_dependencies_and_scan_error(self, db, canvas, app):
        app.manifest = {"declared_scopes": ["*"], "dependencies": ["numpy"]}
        db.commit()
        with patch("core.mini_app_runtime.get_miniapp_runtime", side_effect=RuntimeError("no FC")), \
             patch("core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
                   side_effect=RuntimeError("scan boom")):
            result = svc.status_probe(app, db)
        assert result["runtime"]["available"] is False
        assert result["dependencies"]["scan"]["safe"] is False
        assert result["rootfs"] is not None


# ===========================================================================
# _safe_action_call (async timeout/safety)
# ===========================================================================
class TestSafeActionCall:
    @pytest.mark.asyncio
    async def test_returns_result(self):
        reg = MagicMock()
        reg.execute_action = AsyncMock(return_value={"data": 1})
        r = await svc._safe_action_call(reg, "x", {}, {})
        assert r == {"data": 1}

    @pytest.mark.asyncio
    async def test_swallows_exception(self):
        reg = MagicMock()
        reg.execute_action = AsyncMock(side_effect=RuntimeError("boom"))
        r = await svc._safe_action_call(reg, "x", {}, {})
        assert r == {}


# ===========================================================================
# publish / install (real DB)
# ===========================================================================
class TestPublishInstall:
    def test_publish_snapshots_blueprint_and_state(self, db, canvas, app):
        # Seed a CanvasState for initial_state.
        db.add(CanvasState(canvas_id=canvas.id, tenant_id="t1", state={"runs": 5}, version=1))
        db.commit()
        # prepare_runtime: no deps -> None
        with patch("core.mini_app_service.prepare_runtime", return_value=None):
            result = svc.publish(app, db)
        assert result["success"] is True
        db.refresh(app)
        assert app.status == "published"
        assert app.manifest["initial_state"] == {"runs": 5}
        assert "blueprint" in app.manifest
        assert "content" in app.manifest["blueprint"]

    def test_publish_missing_canvas_raises(self, db, app):
        app.blueprint_canvas_id = "ghost-canvas"
        db.commit()
        with patch("core.mini_app_service.prepare_runtime", return_value=None):
            with pytest.raises(ValueError, match="Blueprint canvas"):
                svc.publish(app, db)

    def test_publish_public_mints_share_token(self, db, canvas, app):
        with patch("core.mini_app_service.prepare_runtime", return_value=None):
            svc.publish(app, db, public=True)
        db.refresh(app)
        assert app.is_public is True
        assert app.share_token

    def test_publish_strips_credentials_from_initial_state(self, db, canvas, app):
        db.add(CanvasState(
            canvas_id=canvas.id, tenant_id="t1",
            state={"api_key": "secret", "ok": "data"}, version=1,
        ))
        db.commit()
        with patch("core.mini_app_service.prepare_runtime", return_value=None):
            svc.publish(app, db)
        db.refresh(app)
        # api_key must be scrubbed from initial_state; benign key survives.
        assert "api_key" not in app.manifest["initial_state"]
        assert app.manifest["initial_state"]["ok"] == "data"

    def test_install_creates_instance_canvas(self, db, canvas, app):
        # Publish first so blueprint exists.
        db.add(CanvasState(canvas_id=canvas.id, tenant_id="t1", state={"x": 1}, version=1))
        db.commit()
        with patch("core.mini_app_service.prepare_runtime", return_value=None):
            svc.publish(app, db)
        viewer = SimpleNamespace(id="u2", tenant_id="t2", workspace_id="ws2")
        new_id = svc.install(app, viewer, db)
        new_canvas = db.query(Canvas).filter(Canvas.id == new_id).one()
        assert new_canvas.mini_app_id == app.id
        assert new_canvas.tenant_id == "t2"  # installer's tenant
        # CanvasState version 1 created.
        st = db.query(CanvasState).filter(CanvasState.canvas_id == new_id).one()
        assert st.version == 1 and st.state == {"x": 1}
        # Exactly one install audit row.
        audits = db.query(CanvasAudit).filter(
            CanvasAudit.canvas_id == new_id,
            CanvasAudit.action_type == "mini_app_install",
        ).all()
        assert len(audits) == 1

    def test_install_unpublished_raises(self, db, canvas, app):
        viewer = SimpleNamespace(id="u2", tenant_id="t2", workspace_id="ws2")
        with pytest.raises(ValueError, match="not published"):
            svc.install(app, viewer, db)

    def test_install_copies_logic_and_components(self, db, canvas, app):
        from core.canvas_logic_service import CanvasLogicService
        CanvasLogicService(db).save_logic(canvas_id=canvas.id, source="state['x']=1", created_by="u1")
        db.add(CanvasState(canvas_id=canvas.id, tenant_id="t1", state={}, version=1))
        # A component installation on the blueprint canvas.
        db.add(ComponentInstallation(
            tenant_id="t1", canvas_id=canvas.id, component_id="comp1",
            config={"api_key": "leak"}, position=0, z_index=0,
        ))
        db.commit()
        with patch("core.mini_app_service.prepare_runtime", return_value=None):
            svc.publish(app, db)
        viewer = SimpleNamespace(id="u2", tenant_id="t2", workspace_id="ws2")
        new_id = svc.install(app, viewer, db)
        # Logic copied.
        logic = CanvasLogicService(db).load_logic(new_id)
        assert logic["source"] == "state['x']=1"
        # Component installed + credentials stripped.
        installs = db.query(ComponentInstallation).filter(
            ComponentInstallation.canvas_id == new_id
        ).all()
        assert len(installs) == 1
        assert "api_key" not in (installs[0].config or {})


# ===========================================================================
# prepare_runtime
# ===========================================================================
class TestPrepareRuntime:
    def test_no_deps_clears_runtime_image(self, db, app):
        app.manifest = {"declared_scopes": ["*"]}
        app.runtime_image = "old.ext4"
        db.commit()
        result = svc.prepare_runtime(app, db)
        assert result is None
        db.refresh(app)
        assert app.runtime_image is None

    def test_no_deps_no_existing_image(self, db, app):
        app.manifest = {"declared_scopes": ["*"]}
        db.commit()
        assert svc.prepare_runtime(app, db) is None

    def test_unsafe_deps_raises(self, db, app):
        app.manifest = {"declared_scopes": ["*"], "dependencies": ["badpkg"]}
        db.commit()
        with patch("core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
                   return_value={"safe": False, "vulnerabilities": ["v1"], "conflicts": []}):
            with pytest.raises(ValueError, match="Dependency scan failed"):
                svc.prepare_runtime(app, db)

    def test_missing_rootfs_raises(self, db, app):
        app.manifest = {"declared_scopes": ["*"], "dependencies": ["numpy"]}
        db.commit()
        with patch("core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
                   return_value={"safe": True}), \
             patch("core.mini_app_service.get_miniapp_rootfs_dir", return_value="/tmp/miniapp-rootfs"), \
             patch("os.path.isfile", return_value=False):
            with pytest.raises(RuntimeError, match="Rootfs for app"):
                svc.prepare_runtime(app, db)

    def test_sets_runtime_image_and_version(self, db, app, tmp_path):
        app.manifest = {"declared_scopes": ["*"], "dependencies": ["numpy"]}
        app.runtime_version = 0
        db.commit()
        rootfs = tmp_path / "miniapp-app-1.ext4"
        rootfs.write_bytes(b"")
        with patch("core.package_dependency_scanner.PackageDependencyScanner.scan_packages",
                   return_value={"safe": True}), \
             patch("core.mini_app_service.get_miniapp_rootfs_dir", return_value=str(tmp_path)):
            result = svc.prepare_runtime(app, db)
        db.refresh(app)
        assert result == str(rootfs)
        assert app.runtime_image == str(rootfs)
        assert app.runtime_version == 1


# ===========================================================================
# _run_async (worker-thread coro runner)
# ---------------------------------------------------------------------------
# _run_async spawns a worker thread with its own event loop. Running it under
# pytest-cov --cov-branch produces a per-thread coverage data file that fails
# to combine with the main (branch) file ("branch data with statement data").
# To keep ``--cov`` working we drive _run_async's inner logic in-process: we
# patch ``threading.Thread`` to a shim that runs the target synchronously on
# the calling (already coverage-instrumented) thread, which exercises the same
# code paths (loop creation, run, error capture, box return) without spawning.
# ===========================================================================
class _SyncThread:
    """A threading.Thread stand-in that runs the target synchronously."""
    def __init__(self, target):
        self._target = target
    def start(self):
        self._target()
    def join(self):
        pass


class TestRunAsync:
    def test_returns_result(self):
        async def coro():
            return 42
        with patch("core.mini_app_service.threading.Thread", _SyncThread):
            # threading is imported lazily inside _run_async; patch the module
            # attribute after import by re-importing is fragile, so patch the
            # global threading module's Thread instead.
            import threading
            with patch.object(threading, "Thread", _SyncThread):
                assert svc._run_async(coro()) == 42

    def test_propagates_exception(self):
        async def coro():
            raise ValueError("boom")
        import threading
        with patch.object(threading, "Thread", _SyncThread):
            with pytest.raises(ValueError, match="boom"):
                svc._run_async(coro())


# ===========================================================================
# _known_scope_names
# ===========================================================================
class TestKnownScopes:
    def test_includes_raw_tools(self):
        names = svc._known_scope_names()
        for t in svc._RAW_TOOL_SCOPES:
            assert t in names

    def test_handles_registry_failure(self):
        with patch("core.action_registry.action_registry.list_actions",
                   side_effect=RuntimeError("boom")):
            names = svc._known_scope_names()
        # Falls back to just raw tools.
        assert set(names) == set(svc._RAW_TOOL_SCOPES)


# ===========================================================================
# _build_starter_manifest
# ===========================================================================
class TestStarterManifest:
    def test_defaults(self):
        m = svc._build_starter_manifest("App", [], [], "python:3.11-slim")
        assert m["declared_scopes"] == ["canvas_render", "canvas_get_state"]
        assert m["dependencies"] == []
        assert m["storage"]["enabled"] is True
        assert m["db"]["enabled"] is True

    def test_provided_values(self):
        m = svc._build_starter_manifest(
            "App", ["canvas_render"], ["numpy"], "python:3.11-slim"
        )
        assert m["declared_scopes"] == ["canvas_render"]
        assert m["dependencies"] == ["numpy"]


# ===========================================================================
# BUG-HUNT (TDD) — failing test written BEFORE the fix
# ===========================================================================
class TestBugs:
    def test_bug_revert_logic_returns_target_not_new_checkpoint_version(self, db, canvas, app):
        """BUG: revert_logic returned ``version`` = the reverted-to TARGET
        version, not the NEW checkpoint version it just wrote. Callers
        (mini_app_revert_logic tool) therefore reported a stale "current
        version" to the agent after a revert. E.g. with versions 1,2,3
        present, reverting to v2 wrote a new v4 checkpoint but reported
        version=2 as current. Function: revert_logic (line ~1682).
        """
        svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "code v1", actor_id="u1")
        svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "code v2", actor_id="u1")
        svc.record_logic_snapshot(db, canvas.id, "t1", app.id, "code v3", actor_id="u1")
        result = svc.revert_logic(app, db, 2, actor_id="u1")
        # After reverting, a NEW checkpoint was written -> version 4 is the
        # current head. The returned version must be 4 (the new checkpoint),
        # and reverted_to tracks the source target (2).
        assert result["version"] == 4
        assert result["reverted_to"] == 2
        hist = svc.list_logic_history(app, db)
        assert hist[-1]["version"] == 4
        assert hist[-1]["preview"] == "code v2"
