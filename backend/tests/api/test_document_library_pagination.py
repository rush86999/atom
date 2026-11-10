"""Real scratch LanceDB + SQL auth tests for document-library pagination.

Covers the repaired public ``GET /api/documents`` contract and the shared
``LanceDBHandler.list_documents`` ordering semantics:

* global ``created_at`` desc + opaque ``id`` desc ordering applied before
  offset/limit, so pages are disjoint and complete even when rows were
  inserted in reverse/non-chronological order;
* equal-timestamp tie-break across a page boundary;
* truthful native total/count/has_more/continuation metadata;
* empty/1/100/101 boundaries, offset beyond the end and the existing 100 cap;
* foreign-workspace/distractor isolation with the real auth dependency;
* fresh-handler restart readback (same order/count).

No live database, no live provider/model, no browser.
"""
from __future__ import annotations

import datetime
import json
import uuid

import pytest
import pyarrow as pa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.document_routes import router as documents_router
from core.auth import create_access_token
from core.database import Base, get_db
from core.lancedb_handler import (
    DocumentListingUnavailable,
    LanceDBHandler,
)
from core.models import DocumentIngestion, Tenant, User, Workspace

VECTOR = [0.0] * 384


def _now_plus(minutes: int) -> str:
    return (
        datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        + datetime.timedelta(minutes=minutes)
    ).isoformat()


def _record(ws: str, user_id: str, doc_id: str, created_at: str) -> dict:
    return {
        "id": doc_id,
        "user_id": user_id,
        "workspace_id": ws,
        "text": f"synthetic text for {doc_id}",
        "source": "scratch-pagination-test",
        "metadata": json.dumps({"title": f"Title {doc_id}"}),
        "created_at": created_at,
        "vector": VECTOR,
        "freshness_status": "fresh",
        "source_modified_at": "",
        "source_url": "",
    }


def _seed_store(tmp_path, ws: str, records: list[dict], tenant: str) -> LanceDBHandler:
    handler = LanceDBHandler(
        db_path=str(tmp_path / "store" / ws),
        workspace_id=ws,
        tenant_id=tenant,
    )
    handler._ensure_db()
    table = handler.create_table("documents", vector_size=384)
    if records:
        table.add(records)
    return handler


class ScratchWorld:
    def __init__(self, tmp_path, monkeypatch):
        self.tmp_path = tmp_path
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path / "store"))
        import core.lancedb_handler as ldbh

        ldbh._workspace_handlers.clear()
        self.engine = create_engine(
            f"sqlite:///{tmp_path / 'auth.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.tenant = f"tenant-{uuid.uuid4()}"
        self._seq = 0
        with self.Session() as db:
            db.add(Tenant(
                id=self.tenant, name="Pagination test",
                subdomain=f"pagination-{uuid.uuid4().hex[:12]}",
                edition="personal", is_active=True,
            ))
            db.commit()

    def user(self, workspace_id, status="active"):
        self._seq += 1
        uid = f"user-{self._seq}-{uuid.uuid4().hex[:8]}"
        with self.Session() as db:
            db.add(User(
                id=uid, tenant_id=self.tenant,
                email=f"{uid}@example.com",
                first_name="Page", last_name="Tester",
                role="member", status=status,
                workspace_id=workspace_id,
                is_active=(status == "active"),
            ))
            db.commit()
            return uid

    def workspace(self, name: str) -> str:
        ws = f"ws-{uuid.uuid4().hex[:12]}"
        with self.Session() as db:
            db.add(Workspace(id=ws, name=name, tenant_id=self.tenant))
            db.commit()
        return ws

    def seed(self, ws: str, user_id: str, docs: list[tuple[str, str]]):
        records = [_record(ws, user_id, doc_id, ts) for doc_id, ts in docs]
        _seed_store(self.tmp_path, ws, records, self.tenant)
        with self.Session() as db:
            for doc_id, _ in docs:
                db.add(DocumentIngestion(
                    workspace_id=ws, doc_id=doc_id,
                    content_hash=uuid.uuid4().hex,
                    source="scratch-pagination-test",
                ))
            db.commit()

    def token(self, user_id: str) -> str:
        with self.Session() as db:
            user = db.query(User).filter(User.id == user_id).one()
            return create_access_token({"sub": user.id}, user=user)

    def client(self):
        app = FastAPI()
        app.include_router(documents_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app, base_url="http://testserver")

    def call(self, client, token=None, **params):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.get("/api/documents", params=params, headers=headers)
        try:
            body = response.json()
        except Exception:
            body = {}
        return response.status_code, body


@pytest.fixture
def world(tmp_path, monkeypatch):
    return ScratchWorld(tmp_path, monkeypatch)


def _assert_page(body, expected_count, expected_total, expected_offset,
                 expected_has_more, expected_limit=100):
    assert body["success"] is True
    docs = body["data"]
    metadata = body["metadata"]
    assert len(docs) == expected_count
    assert metadata["total"] == expected_total
    assert metadata["count"] == expected_count
    assert metadata["limit"] == expected_limit
    assert metadata["offset"] == expected_offset
    assert metadata["has_more"] is expected_has_more
    return docs, metadata


def test_pages_are_globally_ordered_disjoint_and_complete(world):
    ws = world.workspace("Authorized")
    user = world.user(ws)
    # Insert in reverse order; docs 029/030 share a timestamp to force the
    # opaque-id tie-break exactly at the 100-row page boundary.
    docs = []
    for i in range(130):
        created = _now_plus(30 if i in (29, 30) else i)
        docs.append((f"w1-doc-{i:03d}", created))
    world.seed(ws, user, list(reversed(docs)))

    client = world.client()
    token = world.token(user)

    status, body0 = world.call(client, token)
    page0, meta0 = _assert_page(body0, 100, 130, 0, True)
    status, body1 = world.call(client, token, limit=100, offset=100)
    page1, meta1 = _assert_page(body1, 30, 130, 100, False)

    ids0 = [d["id"] for d in page0]
    ids1 = [d["id"] for d in page1]
    assert ids0[0] == "w1-doc-129"
    assert ids0[-1] == "w1-doc-030"  # tie-break: id desc beats 029
    assert ids1[0] == "w1-doc-029"
    assert ids1[-1] == "w1-doc-000"
    assert len(set(ids0) & set(ids1)) == 0
    assert set(ids0) | set(ids1) == {f"w1-doc-{i:03d}" for i in range(130)}
    assert meta0.get("next_offset") == 100
    assert meta1.get("previous_offset") == 0

    # Native count is truthful and the page reads did not mutate the store.
    handler = LanceDBHandler(
        db_path=str(world.tmp_path / "store" / ws),
        workspace_id=ws, tenant_id=world.tenant,
    )
    assert handler.count_documents("documents") == 130
    assert handler.get_table("documents").count_rows() == 130


def test_equal_timestamp_tiebreak_and_fresh_handler_readback(world):
    ws = world.workspace("Ties")
    user = world.user(ws)
    same = _now_plus(5)
    world.seed(ws, user, [
        ("tie-bbb", same),
        ("tie-aaa", same),
        ("tie-ccc", same),
    ])
    client = world.client()
    token = world.token(user)

    status, body = world.call(client, token, limit=2, offset=0)
    page0, _ = _assert_page(body, 2, 3, 0, True, expected_limit=2)
    assert [d["id"] for d in page0] == ["tie-ccc", "tie-bbb"]

    status, body = world.call(client, token, limit=2, offset=2)
    page1, _ = _assert_page(body, 1, 3, 2, False, expected_limit=2)
    assert [d["id"] for d in page1] == ["tie-aaa"]

    # Fresh handler, same physical store: ordering/count survive a restart.
    import core.lancedb_handler as ldbh
    ldbh._workspace_handlers.clear()
    fresh = LanceDBHandler(
        db_path=str(world.tmp_path / "store" / ws),
        workspace_id=ws, tenant_id=world.tenant,
    )
    assert fresh.count_documents("documents") == 3
    ids = [d["id"] for d in fresh.list_documents("documents", limit=3, offset=0)]
    assert ids == ["tie-ccc", "tie-bbb", "tie-aaa"]


@pytest.mark.parametrize("size,page0_count,page1_count,has_more", [
    (0, 0, None, False),
    (1, 1, None, False),
    (100, 100, None, False),
    (101, 100, 1, True),
])
def test_boundary_sizes(world, size, page0_count, page1_count, has_more):
    ws = world.workspace(f"Size {size}")
    user = world.user(ws)
    world.seed(ws, user, [
        (f"w1-doc-{i:03d}", _now_plus(i)) for i in range(size)
    ])
    client = world.client()
    token = world.token(user)

    status, body = world.call(client, token)
    page0, meta0 = _assert_page(body, page0_count, size, 0, has_more)
    if size:
        assert page0[0]["id"] == f"w1-doc-{size - 1:03d}"
    if page1_count is not None:
        status, body = world.call(client, token, limit=100, offset=100)
        page1, meta1 = _assert_page(body, page1_count, size, 100, False)
        assert page1[0]["id"] == f"w1-doc-{size - 101:03d}"

    # Offset beyond the end is a valid empty page with truthful total.
    status, body = world.call(client, token, limit=100, offset=200)
    page, meta = _assert_page(body, 0, size, 200, False)
    assert page == []


def test_limit_cap_and_validation(world):
    ws = world.workspace("Bounds")
    user = world.user(ws)
    client = world.client()
    token = world.token(user)
    for params in ({"limit": 101}, {"limit": 0}, {"offset": -1}):
        status, _ = world.call(client, token, **params)
        assert status == 422


def test_foreign_distractors_scope_and_normal_auth(world):
    ws_auth = world.workspace("Authorized")
    ws_foreign = world.workspace("Foreign")
    user_auth = world.user(ws_auth)
    user_foreign = world.user(ws_foreign)
    user_inactive = world.user(ws_auth, status="inactive")
    world.seed(ws_auth, user_auth, [
        (f"w1-doc-{i:03d}", _now_plus(i)) for i in range(130)
    ])
    world.seed(ws_foreign, user_foreign, [
        (f"w2-doc-{i:03d}", _now_plus(i)) for i in range(7)
    ])
    # default_shared distractor store (no-workspace resolution only).
    _seed_store(world.tmp_path, "default_shared", [
        _record("default_shared", "shared-user", f"shared-doc-{i:03d}", _now_plus(i))
        for i in range(3)
    ], world.tenant)

    client = world.client()
    status, body = world.call(client, None)
    assert status == 401

    status, body = world.call(client, world.token(user_inactive))
    assert status == 401

    status, body = world.call(client, world.token(user_auth))
    ids = {d["id"] for d in body["data"]}
    assert ids and all(i.startswith("w1-doc-") for i in ids)
    assert body["metadata"]["total"] == 130

    status, body = world.call(client, world.token(user_foreign))
    ids = {d["id"] for d in body["data"]}
    assert len(ids) == 7 and all(i.startswith("w2-doc-") for i in ids)
    assert body["metadata"]["total"] == 7


class _CountFails:
    def __init__(self, table):
        self._table = table

    def count_rows(self):
        raise RuntimeError("forced count failure")

    def to_lance(self):
        return self._table.to_lance()


class _OrderFails:
    def __init__(self, table):
        self._table = table

    def count_rows(self):
        return self._table.count_rows()

    def to_lance(self):
        raise RuntimeError("forced native ordering failure")


class _EmptyDataset:
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("text", pa.string()),
        pa.field("source", pa.string()),
        pa.field("metadata", pa.string()),
        pa.field("created_at", pa.string()),
    ])

    def to_table(self, columns=None, **kwargs):
        columns = columns or self.schema.names
        return pa.table({c: pa.array([], type=pa.string()) for c in columns})


class _EmptyPageWithRows:
    def count_rows(self):
        return 130

    def to_lance(self):
        return _EmptyDataset()


def _seeded_handler(world, size=3):
    ws = world.workspace(f"Failure {size}")
    user = world.user(ws)
    world.seed(ws, user, [
        (f"w1-doc-{i:03d}", _now_plus(i)) for i in range(size)
    ])
    handler = LanceDBHandler(
        db_path=str(world.tmp_path / "store" / ws),
        workspace_id=ws, tenant_id=world.tenant,
    )
    return ws, user, handler


def test_native_ordering_failure_is_unavailable_not_empty(world, monkeypatch):
    _, _, handler = _seeded_handler(world)
    real_table = handler.get_table("documents")
    monkeypatch.setattr(handler, "get_table", lambda name: _OrderFails(real_table))
    with pytest.raises(DocumentListingUnavailable):
        handler.list_documents_page("documents", limit=100, offset=0)
    with pytest.raises(DocumentListingUnavailable):
        handler.list_documents("documents", limit=100, offset=0)


def test_count_failure_is_unavailable(world, monkeypatch):
    _, _, handler = _seeded_handler(world)
    real_table = handler.get_table("documents")
    monkeypatch.setattr(handler, "get_table", lambda name: _CountFails(real_table))
    with pytest.raises(DocumentListingUnavailable):
        handler.list_documents_page("documents", limit=100, offset=0)
    with pytest.raises(DocumentListingUnavailable):
        handler.count_documents("documents")


def test_api_reports_503_when_native_listing_unavailable(world, monkeypatch):
    ws, user, _ = _seeded_handler(world)
    monkeypatch.setattr(
        LanceDBHandler, "list_documents_page",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(
            DocumentListingUnavailable("forced native ordering failure")),
    )
    client = world.client()
    status, body = world.call(client, world.token(user))
    assert status == 503
    assert "unavailable" in json.dumps(body).lower()
    assert body.get("success") is not True


def test_valid_empty_library_is_200_not_unavailable(world):
    ws = world.workspace("Empty")
    user = world.user(ws)
    client = world.client()
    status, body = world.call(client, world.token(user))
    assert status == 200
    assert body["data"] == []
    assert body["metadata"]["total"] == 0
    assert body["metadata"]["count"] == 0
    assert body["metadata"]["has_more"] is False
    assert "next_offset" not in body["metadata"]


def test_zero_length_page_never_self_loops(world, monkeypatch):
    _, _, handler = _seeded_handler(world)
    monkeypatch.setattr(handler, "get_table", lambda name: _EmptyPageWithRows())
    page = handler.list_documents_page("documents", limit=100, offset=100)
    assert page["total"] == 130
    assert page["count"] == 0
    assert page["has_more"] is False
    assert page["next_offset"] is None
    assert page["stale_page"] is True
