"""Mini-app DB store — service CRUD tests (host-mediated record store).

TDD contract: cross-instance isolation, seq semantics, filter/order/limit,
caps, and the structured no-str(e) error surface.
"""
import uuid

import pytest

from core.models import Canvas, CanvasLogic, CanvasState, MiniApp


def _make_app(db, name="store"):
    canvas_id = f"c-{uuid.uuid4().hex[:12]}"
    app_id = f"app-{uuid.uuid4().hex[:12]}"
    db.add(Canvas(
        id=canvas_id, tenant_id="t1", created_by="u1", name=name,
        canvas_type="mini_app", content={"blocks": []}, style={}, status="active",
        mini_app_id=app_id,
    ))
    db.add(CanvasLogic(canvas_id=canvas_id, language="python", source="state = state", created_by="u1"))
    db.add(MiniApp(
        id=app_id, tenant_id="t1", workspace_id="w1", created_by="u1", name=name,
        manifest={"declared_scopes": ["*"], "mcp_servers": [], "dependencies": [],
                  "base_image": "python:3.11-slim", "assets": [], "storage": {},
                  "initial_state": {}, "blueprint": {}},
        blueprint_canvas_id=canvas_id, status="draft",
    ))
    db.add(CanvasState(canvas_id=canvas_id, tenant_id="t1", state={}, version=1))
    db.commit()
    return app_id, canvas_id


@pytest.fixture
def canvas_fixture(db_session):
    return _make_app(db_session)


class TestAppendQuery:
    def test_append_assigns_incrementing_seq(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, query_records
        app_id, canvas_id = canvas_fixture
        r1 = append_record(db_session, canvas_id, "t1", app_id, "chart_data", {"label": "Jan", "value": 12})
        r2 = append_record(db_session, canvas_id, "t1", app_id, "chart_data", {"label": "Feb", "value": 20})
        assert r1["seq"] == 1 and r2["seq"] == 2
        assert r1["data"] == {"label": "Jan", "value": 12}

    def test_seq_restarts_per_series(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record
        app_id, canvas_id = canvas_fixture
        append_record(db_session, canvas_id, "t1", app_id, "a", {"x": 1})
        r = append_record(db_session, canvas_id, "t1", app_id, "b", {"x": 1})
        assert r["seq"] == 1

    def test_query_desc_default_latest_first(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, query_records
        app_id, canvas_id = canvas_fixture
        for i in range(5):
            append_record(db_session, canvas_id, "t1", app_id, "s", {"i": i})
        rows = query_records(db_session, canvas_id, "s")
        assert [r["data"]["i"] for r in rows] == [4, 3, 2, 1, 0]
        assert len(rows) == 5

    def test_query_asc_and_limit(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, query_records
        app_id, canvas_id = canvas_fixture
        for i in range(10):
            append_record(db_session, canvas_id, "t1", app_id, "s", {"i": i})
        rows = query_records(db_session, canvas_id, "s", order="asc", limit=3)
        assert [r["data"]["i"] for r in rows] == [0, 1, 2]

    def test_query_equality_filter(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, query_records
        app_id, canvas_id = canvas_fixture
        append_record(db_session, canvas_id, "t1", app_id, "s", {"label": "a", "v": 1})
        append_record(db_session, canvas_id, "t1", app_id, "s", {"label": "b", "v": 2})
        append_record(db_session, canvas_id, "t1", app_id, "s", {"label": "a", "v": 3})
        rows = query_records(db_session, canvas_id, "s", f={"label": "a"})
        assert len(rows) == 2

    def test_get_hit_and_miss(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, get_record
        app_id, canvas_id = canvas_fixture
        r = append_record(db_session, canvas_id, "t1", app_id, "s", {"x": 1})
        got = get_record(db_session, canvas_id, "s", r["id"])
        assert got is not None and got["data"] == {"x": 1}
        assert get_record(db_session, canvas_id, "s", "nope") is None

    def test_append_with_client_id(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, get_record
        app_id, canvas_id = canvas_fixture
        r = append_record(db_session, canvas_id, "t1", app_id, "s", {"x": 1}, record_id="my-id")
        assert r["id"] == "my-id"
        assert get_record(db_session, canvas_id, "s", "my-id") is not None


class TestUpdateDelete:
    def test_update_merges(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, get_record, update_record
        app_id, canvas_id = canvas_fixture
        r = append_record(db_session, canvas_id, "t1", app_id, "s", {"a": 1, "b": 2})
        updated = update_record(db_session, canvas_id, "s", r["id"], {"b": 3, "c": 4})
        assert updated["data"] == {"a": 1, "b": 3, "c": 4}
        assert get_record(db_session, canvas_id, "s", r["id"])["data"] == {"a": 1, "b": 3, "c": 4}

    def test_update_missing_returns_none(self, db_session, canvas_fixture):
        from core.mini_app_db_service import update_record
        _, canvas_id = canvas_fixture
        assert update_record(db_session, canvas_id, "s", "nope", {"x": 1}) is None

    def test_update_many_matches_filter(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, query_records, update_many_records
        app_id, canvas_id = canvas_fixture
        append_record(db_session, canvas_id, "t1", app_id, "s", {"team": "a", "done": False})
        append_record(db_session, canvas_id, "t1", app_id, "s", {"team": "a", "done": False})
        append_record(db_session, canvas_id, "t1", app_id, "s", {"team": "b", "done": False})
        n = update_many_records(db_session, canvas_id, "s", {"team": "a"}, {"done": True})
        assert n == 2
        rows = query_records(db_session, canvas_id, "s", f={"done": True})
        assert len(rows) == 2

    def test_delete_record(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, count_records, delete_record
        app_id, canvas_id = canvas_fixture
        r = append_record(db_session, canvas_id, "t1", app_id, "s", {"x": 1})
        append_record(db_session, canvas_id, "t1", app_id, "s", {"x": 2})
        assert delete_record(db_session, canvas_id, "s", r["id"]) is True
        assert delete_record(db_session, canvas_id, "s", "nope") is False
        assert count_records(db_session, canvas_id) == 1

    def test_delete_series_and_clear(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, clear_records, count_records, delete_series
        app_id, canvas_id = canvas_fixture
        append_record(db_session, canvas_id, "t1", app_id, "s1", {"x": 1})
        append_record(db_session, canvas_id, "t1", app_id, "s1", {"x": 2})
        append_record(db_session, canvas_id, "t1", app_id, "s2", {"x": 3})
        assert delete_series(db_session, canvas_id, "s1") == 2
        assert count_records(db_session, canvas_id) == 1
        assert clear_records(db_session, canvas_id) == 1
        assert count_records(db_session, canvas_id) == 0

    def test_count_with_series_and_filter(self, db_session, canvas_fixture):
        from core.mini_app_db_service import append_record, count_records
        app_id, canvas_id = canvas_fixture
        append_record(db_session, canvas_id, "t1", app_id, "a", {"k": 1})
        append_record(db_session, canvas_id, "t1", app_id, "a", {"k": 2})
        append_record(db_session, canvas_id, "t1", app_id, "b", {"k": 1})
        assert count_records(db_session, canvas_id) == 3
        assert count_records(db_session, canvas_id, series="a") == 2
        assert count_records(db_session, canvas_id, series="a", f={"k": 1}) == 1


class TestIsolation:
    def test_cross_canvas_isolation(self, db_session):
        from core.mini_app_db_service import append_record, count_records, query_records
        app1, c1 = _make_app(db_session)
        app2, c2 = _make_app(db_session)
        append_record(db_session, c1, "t1", app1, "s", {"secret": True})
        append_record(db_session, c2, "t1", app2, "s", {"secret": False})
        assert query_records(db_session, c1, "s")[0]["data"]["secret"] is True
        assert query_records(db_session, c2, "s")[0]["data"]["secret"] is False
        assert count_records(db_session, c1) == 1
        assert count_records(db_session, c2) == 1

    def test_list_series_isolation(self, db_session):
        from core.mini_app_db_service import append_record, list_series
        app1, c1 = _make_app(db_session)
        _, c2 = _make_app(db_session)
        append_record(db_session, c1, "t1", app1, "only_mine", {"x": 1})
        assert [s["series"] for s in list_series(db_session, c2)] == []


class TestManifestDbValidation:
    def test_valid_db_config(self):
        from core.mini_app_service import validate_manifest
        validate_manifest({
            "declared_scopes": ["*"],
            "db": {"enabled": True, "max_records_per_series": 500, "max_record_bytes": 2048,
                   "record_queries": ["chart_data", "todos"]},
            "data_sources": [{"type": "documents.search", "query": "revenue"}],
            "mcp_servers": [{"service": "notion", "action": "search", "params": {"q": "x"}}],
        })

    def test_absent_db_allowed(self):
        from core.mini_app_service import validate_manifest
        validate_manifest({"declared_scopes": ["*"]})

    def test_bad_db_types_raise(self):
        from core.mini_app_service import validate_manifest
        for db in ({"enabled": "yes"}, {"max_records_per_series": -1},
                   {"max_record_bytes": "big"}, "nope"):
            with pytest.raises(ValueError):
                validate_manifest({"declared_scopes": ["*"], "db": db})

    def test_bad_record_query_series_raises(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "db": {"record_queries": ["Bad Name"]}})

    def test_bad_data_source_type_raises(self):
        from core.mini_app_service import validate_manifest
        with pytest.raises(ValueError):
            validate_manifest({"declared_scopes": ["*"], "data_sources": [{"type": "evil.exec"}]})

    def test_bad_mcp_server_shape_raises(self):
        from core.mini_app_service import validate_manifest
        for ms in ([{"action": "x"}], [{"service": "s"}], [{"service": "s", "action": 5}],
                   ["nope"]):
            with pytest.raises(ValueError):
                validate_manifest({"declared_scopes": ["*"], "mcp_servers": ms})

    def test_starter_manifest_has_db_block(self, db_session):
        from core.mini_app_service import _build_starter_manifest
        m = _build_starter_manifest("x", ["*"], [], "python:3.11-slim")
        assert m["db"]["enabled"] is True
        assert m["db"]["max_records_per_series"] > 0
        assert m["db"]["record_queries"] == []


class TestValidation:
    def test_validate_series(self):
        from core.mini_app_db_service import validate_series
        assert validate_series("chart_data") == "chart_data"
        assert validate_series("a" * 64) == "a" * 64
        assert validate_series("a" * 65) is None
        assert validate_series("") is None
        assert validate_series("UPPER") is None
        assert validate_series("has-dash") is None
        assert validate_series(12) is None

    def test_validate_record_data(self):
        from core.mini_app_db_service import validate_record_data
        assert validate_record_data({"a": 1}, 1024) is True
        assert validate_record_data([1, 2], 1024) is False
        assert validate_record_data({"big": "x" * 2048}, 1024) is False
        assert validate_record_data({"a": object()}, 1024) is False

    def test_validate_filter(self):
        from core.mini_app_db_service import validate_filter
        assert validate_filter({"label": "a", "n": 1}) is True
        assert validate_filter({"nested": {"x": 1}}) is False
        assert validate_filter({"x": object()}) is False
        assert validate_filter("nope") is False

    def test_db_store_enabled_default_on(self, monkeypatch):
        from core.mini_app_db_service import db_store_enabled
        monkeypatch.delenv("ATOM_MINIAPP_DB_ENABLED", raising=False)
        assert db_store_enabled() is True
        monkeypatch.setenv("ATOM_MINIAPP_DB_ENABLED", "false")
        assert db_store_enabled() is False
