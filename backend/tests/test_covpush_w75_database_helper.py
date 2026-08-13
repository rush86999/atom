"""Coverage wave 75 — core/database_helper.py (97% → 95%+).

Closes the helper surface: get_or_404 (found/404/custom message), get_by_id,
get_by_field, get_all (filters/limit/offset/order asc-desc), create_record,
update_record (incl. unknown-field skip), delete_record, soft_delete_record
(incl. deleted_by + deleted_at timestamp), check_exists, count_records,
bulk_create, get_or_create (found/created), execute_safe (success/error 500),
paginate_query (metadata incl. empty-page). Real in-memory SQLite.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.database_helper import (
    bulk_create,
    check_exists,
    count_records,
    create_record,
    delete_record,
    execute_safe,
    get_all,
    get_by_field,
    get_by_id,
    get_or_404,
    get_or_create,
    paginate_query,
    soft_delete_record,
    update_record,
)
from core.models import Workspace

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def ws(db):
    ws = Workspace(id="ws-1", name="Alpha")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def _make(db, name, wsid="ws-1"):
    ws = Workspace(id=wsid, name=name)
    db.add(ws)
    db.commit()
    return ws


class TestGetOr404:
    def test_found(self, db, ws):
        assert get_or_404(db, Workspace, ws.id).id == ws.id

    def test_custom_id_field(self, db, ws):
        assert get_or_404(db, Workspace, ws.name, id_field="name").id == ws.id

    def test_not_found_default_message(self, db):
        with pytest.raises(HTTPException) as ei:
            get_or_404(db, Workspace, "nope")
        assert ei.value.status_code == 404
        assert "Workspace not found" == ei.value.detail

    def test_not_found_custom_message(self, db):
        with pytest.raises(HTTPException) as ei:
            get_or_404(db, Workspace, "nope", "Custom missing")
        assert ei.value.status_code == 404
        assert ei.value.detail == "Custom missing"


class TestGetters:
    def test_get_by_id(self, db, ws):
        assert get_by_id(db, Workspace, ws.id).id == ws.id
        assert get_by_id(db, Workspace, "missing") is None

    def test_get_by_field(self, db, ws):
        assert get_by_field(db, Workspace, "name", "Alpha").id == ws.id
        assert get_by_field(db, Workspace, "name", "Beta") is None

    def test_get_all_no_filters(self, db):
        _make(db, "A", "w1")
        _make(db, "B", "w2")
        _make(db, "C", "w3")
        assert len(get_all(db, Workspace)) == 3

    def test_get_all_filters_and_pagination(self, db):
        _make(db, "A", "w1")
        _make(db, "B", "w2")
        _make(db, "C", "w3")
        _make(db, "D", "w4")
        two = get_all(db, Workspace, limit=2)
        assert len(two) == 2
        offset = get_all(db, Workspace, offset=2)
        assert len(offset) == 2
        filtered = get_all(db, Workspace, filters={"name": "B"})
        assert len(filtered) == 1
        filtered[0].name == "B"

    def test_get_all_ordering(self, db):
        _make(db, "B", "w1")
        _make(db, "A", "w2")
        asc = get_all(db, Workspace, order_by="name")
        assert [w.name for w in asc] == ["A", "B"]
        desc = get_all(db, Workspace, order_by="-name")
        assert [w.name for w in desc] == ["B", "A"]


class TestCrud:
    def test_create_record(self, db):
        rec = create_record(db, Workspace, id="new-ws", name="New")
        assert rec.id == "new-ws"
        assert db.query(Workspace).count() == 1

    def test_update_record(self, db, ws):
        updated = update_record(db, ws, name="Renamed", not_a_column="ignored")
        assert updated.name == "Renamed"

    def test_delete_record(self, db, ws):
        assert delete_record(db, ws) is True
        assert db.query(Workspace).count() == 0

    def test_soft_delete_status(self, db, ws):
        soft = soft_delete_record(db, ws)
        assert soft.status == "deleted"
        assert db.query(Workspace).filter_by(id=ws.id).first().status == "deleted"

    def test_soft_delete_with_audit_fields(self, db):
        class Rec:
            def __init__(self):
                self.status = "active"
                self.deleted_by = None
                self.deleted_at = None

        rec = Rec()
        mdb = MagicMock()
        out = soft_delete_record(mdb, rec, deleted_by="user-9")
        assert out.status == "deleted"
        assert out.deleted_by == "user-9"
        assert out.deleted_at is not None

    def test_soft_delete_skips_missing_attrs(self, db):
        rec = Workspace(id="ws-x", name="X")
        db.add(rec)
        db.commit()
        out = soft_delete_record(db, rec)
        assert out.status == "deleted"


class TestChecksAndCounts:
    def test_check_exists(self, db, ws):
        assert check_exists(db, Workspace, "name", "Alpha") is True
        assert check_exists(db, Workspace, "name", "Zeta") is False

    def test_count_records(self, db):
        _make(db, "A", "w1")
        _make(db, "B", "w2")
        assert count_records(db, Workspace) == 2
        assert count_records(db, Workspace, {"name": "A"}) == 1


class TestBulkAndGetOrCreate:
    def test_bulk_create(self, db):
        recs = bulk_create(db, Workspace, [
            {"id": "b1", "name": "One"},
            {"id": "b2", "name": "Two"},
        ])
        assert len(recs) == 2
        assert db.query(Workspace).count() == 2

    def test_get_or_create_found(self, db, ws):
        rec, created = get_or_create(db, Workspace, {"name": "Alpha"})
        assert created is False
        assert rec.id == ws.id

    def test_get_or_create_new(self, db):
        rec, created = get_or_create(db, Workspace, {"name": "Gamma"},
                                     defaults={"id": "g1"})
        assert created is True
        assert rec.id == "g1"
        assert db.query(Workspace).count() == 1


class TestExecuteSafe:
    def test_success(self, db):
        assert execute_safe(db, lambda: 42) == 42

    def test_error_raises_500(self, db):
        def boom():
            raise RuntimeError("nope")
        with pytest.raises(HTTPException) as ei:
            execute_safe(db, boom, "Failed to fetch agents")
        assert ei.value.status_code == 500
        assert ei.value.detail == "Failed to fetch agents"

    def test_error_default_message(self, db):
        with pytest.raises(HTTPException) as ei:
            execute_safe(db, lambda: 1 / 0)
        assert ei.value.detail == "Database operation failed"


class TestPaginate:
    def test_paginate_metadata(self, db):
        for i in range(5):
            _make(db, f"N{i}", f"w{i}")
        result = paginate_query(db, Workspace, page=2, page_size=2)
        assert result["total"] == 5
        assert result["page"] == 2
        assert result["page_size"] == 2
        assert result["total_pages"] == 3
        assert len(result["items"]) == 2

    def test_paginate_empty(self, db):
        result = paginate_query(db, Workspace)
        assert result["total"] == 0
        assert result["total_pages"] == 0
        assert result["items"] == []

    def test_paginate_filters_and_order(self, db):
        for i in range(3):
            _make(db, f"N{i}", f"w{i}")
        result = paginate_query(db, Workspace, filters={"name": "N1"}, order_by="-name")
        assert result["total"] == 1
        assert result["items"][0].name == "N1"
