#!/usr/bin/env python3
"""Private read-only/scratch reproduction for WO-WEB-DOCUMENTS-BREADTH-01.

No live database, no live provider/model, no browser, no product edit.

Creates a fresh 0700 scratch world with:
  * a real SQLite scratch DB (Tenant/Workspace/User/DocumentIngestion rows),
  * per-workspace LanceDB stores with 130 authorized docs, 7 foreign-workspace
    docs, and 3 default_shared distractor docs,
  * real JWT bearer auth through the normal get_current_user dependency,
  * the real public document router mounted in FastAPI/TestClient.

Writes the safe JSON to /private/tmp/root-document-library-reproduction-20261110.json.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path

SAFE_JSON = Path(os.environ["ROOT_DOCUMENT_REPORT"])
SRC = "1605d7713116f1552d23e6a8288fd3902ce9468a"
PRODUCT_SOURCE = "c4bc1d4b623eb56d54491e4c79052885b5950cff"
MAIN = "c0427e5204690c6fdba04bdc9b08b363e284d39f"

WORLD = Path(tempfile.mkdtemp(prefix="root-doc-library-probe-", dir="/private/tmp"))
os.chmod(WORLD, 0o700)
(WORLD / "data").mkdir()
os.environ.update({
    "TESTING": "1",
    "ENVIRONMENT": "development",
    "DATABASE_URL": f"sqlite:///{WORLD}/scratch.db",
    "ATOM_DATA_DIR": str(WORLD / "data"),
    "LANCEDB_URI": str(WORLD / "store"),
    "LANCEDB_URI_BASE": str(WORLD / "store"),
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "ATOM_LOCAL_ONLY": "1",
    "ENABLE_SCHEDULER": "false",
    "SECRET_KEY": secrets.token_urlsafe(48),
    "VECTOR_STORE": "lancedb",
})

SUFFIX = secrets.token_hex(4)
WS_AUTH = f"ws-doc-authorized-{SUFFIX}"
WS_FOREIGN = f"ws-doc-foreign-{SUFFIX}"
TENANT = f"tenant-doc-repro-{SUFFIX}"
USER_AUTH = f"user-doc-authorized-{SUFFIX}"
USER_FOREIGN = f"user-doc-foreign-{SUFFIX}"
USER_INACTIVE = f"user-doc-inactive-{SUFFIX}"
USER_NO_WS = f"user-doc-nows-{SUFFIX}"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def doc_records(workspace: str, prefix: str, count: int) -> list[dict]:
    base = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    records = []
    for i in range(count):
        created = (base + datetime.timedelta(minutes=i)).isoformat()
        doc_id = f"{prefix}-{i:03d}"
        records.append({
            "id": doc_id,
            "user_id": USER_AUTH if prefix == "w1-doc" else USER_FOREIGN,
            "workspace_id": workspace,
            "text": f"synthetic document {i} for {workspace}",
            "source": "scratch-reproduction",
            "metadata": json.dumps({"title": f"{prefix} {i:03d}"}),
            "created_at": created,
            "vector": [0.0] * 384,
            "freshness_status": "fresh",
            "source_modified_at": "",
            "source_url": "",
        })
    return records


def seed_store(workspace: str, prefix: str, count: int):
    from core.lancedb_handler import LanceDBHandler
    handler = LanceDBHandler(
        db_path=str(WORLD / "store" / workspace),
        workspace_id=workspace,
        tenant_id=TENANT,
    )
    handler._ensure_db()
    table = handler.create_table("documents", vector_size=384)
    table.add(doc_records(workspace, prefix, count))
    return handler, table


def main() -> int:
    import sys
    backend = Path("/private/tmp/atom-web-task-project-20261109/backend")
    sys.path.insert(0, str(backend))

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    import core.database as cdb
    from core.auth import create_access_token
    from core.database import Base, get_db
    from core.models import DocumentIngestion, Tenant, User, Workspace
    from api.document_routes import router as documents_router

    result: dict = {
        "schema_version": 1,
        "kind": "read_only_scratch_reproduction",
        "work_order": "WO-WEB-DOCUMENTS-BREADTH-01",
        "source": SRC,
        "product_source": PRODUCT_SOURCE,
        "main_c042": MAIN,
        "private_world": str(WORLD),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    engine = cdb.engine
    resolved_url = str(engine.url)
    result["environment"] = {
        "TESTING": os.environ.get("TESTING"),
        "database_url": resolved_url,
        "database_url_is_scratch": resolved_url == f"sqlite:///{WORLD}/scratch.db",
        "atom_data_dir": os.environ.get("ATOM_DATA_DIR"),
        "lancedb_uri_base": os.environ.get("LANCEDB_URI_BASE"),
        "live_database": False,
        "live_provider_or_model": False,
        "browser_launched": False,
        "product_source_edited": False,
    }
    if not result["environment"]["database_url_is_scratch"]:
        raise RuntimeError(f"scratch DB was not honored: {resolved_url}")

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    db = SessionLocal()
    try:
        db.add(Tenant(id=TENANT, name="Doc repro", subdomain=f"doc-repro-{SUFFIX}",
                      edition="personal", is_active=True))
        db.add(Workspace(id=WS_AUTH, name="Authorized", tenant_id=TENANT))
        db.add(Workspace(id=WS_FOREIGN, name="Foreign", tenant_id=TENANT))
        db.add_all([
            User(id=USER_AUTH, tenant_id=TENANT, email=f"auth-{SUFFIX}@example.com",
                 first_name="Doc", last_name="Auth", role="member", status="active",
                 workspace_id=WS_AUTH, is_active=True),
            User(id=USER_FOREIGN, tenant_id=TENANT, email=f"foreign-{SUFFIX}@example.com",
                 first_name="Doc", last_name="Foreign", role="member", status="active",
                 workspace_id=WS_FOREIGN, is_active=True),
            User(id=USER_INACTIVE, tenant_id=TENANT, email=f"inactive-{SUFFIX}@example.com",
                 first_name="Doc", last_name="Inactive", role="member", status="inactive",
                 workspace_id=WS_AUTH, is_active=False),
            User(id=USER_NO_WS, tenant_id=TENANT, email=f"nows-{SUFFIX}@example.com",
                 first_name="Doc", last_name="NoWs", role="member", status="active",
                 workspace_id=None, is_active=True),
        ])
        db.flush()
        for workspace, prefix, count in (
                (WS_AUTH, "w1-doc", 130),
                (WS_FOREIGN, "w2-doc", 7)):
            for i in range(count):
                doc_id = f"{prefix}-{i:03d}"
                db.add(DocumentIngestion(
                    workspace_id=workspace, doc_id=doc_id,
                    content_hash=hashlib.sha256(doc_id.encode()).hexdigest(),
                    source="scratch-reproduction"))
        db.commit()
        users = {u.id: u for u in db.query(User).all()}
        tokens = {
            uid: create_access_token({"sub": uid}, user=user)
            for uid, user in users.items()
        }
        sql_counts_before = {
            "users": db.query(User).count(),
            "tenants": db.query(Tenant).count(),
            "workspaces": db.query(Workspace).count(),
            "document_ingestions": db.query(DocumentIngestion).count(),
        }
    finally:
        db.close()

    # Seed one store per workspace, plus default_shared distractors.
    handlers = {}
    table_counts_before = {}
    for workspace, prefix, count in (
            (WS_AUTH, "w1-doc", 130),
            (WS_FOREIGN, "w2-doc", 7),
            ("default_shared", "shared-doc", 3)):
        handler, table = seed_store(workspace, prefix, count)
        handlers[workspace] = handler
        table_counts_before[workspace] = int(table.count_rows())

    app = FastAPI()
    app.include_router(documents_router)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, base_url="http://testserver")

    def call(path: str, token: str | None = None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.get(path, headers=headers)
        try:
            payload = response.json()
        except Exception:
            payload = {"<non-json>": response.text[:200]}
        return response.status_code, payload

    def summarize(status: int, payload: dict) -> dict:
        data = payload.get("data")
        docs = data if isinstance(data, list) else []
        meta = payload.get("metadata")
        return {
            "status": status,
            "success": payload.get("success"),
            "data_count": len(docs),
            "data_first_id": docs[0]["id"] if docs else None,
            "data_last_id": docs[-1]["id"] if docs else None,
            "metadata": meta,
            "metadata_keys": sorted(meta.keys()) if isinstance(meta, dict) else None,
            "has_more": (meta or {}).get("has_more") if isinstance(meta, dict) else None,
            "next_cursor": (meta or {}).get("next_cursor") if isinstance(meta, dict) else None,
            "ids": [d["id"] for d in docs],
        }

    calls = {}
    status, payload = call("/api/documents")
    calls["no_auth"] = summarize(status, payload)
    status, payload = call("/api/documents", tokens[USER_AUTH])
    calls["authorized_default"] = summarize(status, payload)
    status, payload = call("/api/documents?limit=100&offset=100", tokens[USER_AUTH])
    calls["authorized_offset_100"] = summarize(status, payload)
    status, payload = call("/api/documents?limit=100&offset=130", tokens[USER_AUTH])
    calls["authorized_offset_130"] = summarize(status, payload)
    status, payload = call("/api/documents?limit=101", tokens[USER_AUTH])
    calls["limit_101"] = summarize(status, payload)
    status, payload = call("/api/documents?limit=0", tokens[USER_AUTH])
    calls["limit_0"] = summarize(status, payload)
    status, payload = call("/api/documents?offset=-1", tokens[USER_AUTH])
    calls["offset_negative"] = summarize(status, payload)
    status, payload = call("/api/documents", tokens[USER_FOREIGN])
    calls["foreign_user"] = summarize(status, payload)
    status, payload = call("/api/documents", tokens[USER_INACTIVE])
    calls["inactive_user"] = summarize(status, payload)
    status, payload = call("/api/documents", tokens[USER_NO_WS])
    calls["no_workspace_user"] = summarize(status, payload)

    page0_ids = calls["authorized_default"]["ids"]
    page1_ids = calls["authorized_offset_100"]["ids"]
    authorized_ids = {f"w1-doc-{i:03d}" for i in range(130)}
    p0, p1 = set(page0_ids), set(page1_ids)
    pagination = {
        "page0_count": len(page0_ids),
        "page1_count": len(page1_ids),
        "page0_and_page1_overlap": len(p0 & p1),
        "page0_page1_union": len(p0 | p1),
        "authorized_total": 130,
        "missing_from_both_pages": len(authorized_ids - (p0 | p1)),
        "newest_id_reachable_on_page0": "w1-doc-129" in p0,
        "oldest_id_reachable_on_page1": "w1-doc-000" in p1,
        "stable_disjoint_continuation": len(p0 & p1) == 0 and len(p0 | p1) == 130,
        "metadata_total_page0": (calls["authorized_default"]["metadata"] or {}).get("total"),
        "metadata_total_page1": (calls["authorized_offset_100"]["metadata"] or {}).get("total"),
        "metadata_total_equals_page_length": (
            (calls["authorized_default"]["metadata"] or {}).get("total") == len(page0_ids)
            and (calls["authorized_offset_100"]["metadata"] or {}).get("total") == len(page1_ids)
        ),
    }

    foreign_leak = {
        "authorized_page_contains_foreign": any(i.startswith("w2-doc-") for i in page0_ids + page1_ids),
        "authorized_page_contains_shared": any(i.startswith("shared-doc-") for i in page0_ids + page1_ids),
        "foreign_user_sees_foreign": all(i.startswith("w2-doc-") for i in calls["foreign_user"]["ids"]),
        "foreign_user_count": calls["foreign_user"]["data_count"],
        "no_workspace_user_sees_shared": all(i.startswith("shared-doc-") for i in calls["no_workspace_user"]["ids"]),
        "no_workspace_user_count": calls["no_workspace_user"]["data_count"],
    }

    table_counts_after = {
        workspace: int(handlers[workspace].get_table("documents").count_rows())
        for workspace in handlers
    }
    db = SessionLocal()
    try:
        sql_counts_after = {
            "users": db.query(User).count(),
            "tenants": db.query(Tenant).count(),
            "workspaces": db.query(Workspace).count(),
            "document_ingestions": db.query(DocumentIngestion).count(),
        }
    finally:
        db.close()

    assert pagination["stable_disjoint_continuation"] is True
    assert pagination["missing_from_both_pages"] == 0
    assert pagination["page0_and_page1_overlap"] == 0
    assert page0_ids == [f"w1-doc-{i:03d}" for i in range(129,29,-1)]
    assert page1_ids == [f"w1-doc-{i:03d}" for i in range(29,-1,-1)]
    for name in ("authorized_default", "authorized_offset_100", "authorized_offset_130"):
        assert calls[name]["status"] == 200
        assert calls[name]["metadata"]["total"] == 130
    assert calls["authorized_default"]["metadata"]["next_offset"] == 100
    assert calls["authorized_offset_100"]["has_more"] is False
    assert calls["authorized_offset_130"]["has_more"] is False
    assert calls["authorized_offset_130"]["data_count"] == 0
    assert not foreign_leak["authorized_page_contains_foreign"]
    assert not foreign_leak["authorized_page_contains_shared"]
    assert calls["no_auth"]["status"] == 401 and calls["inactive_user"]["status"] == 401
    for name in ("limit_101", "limit_0", "offset_negative"):
        assert calls[name]["status"] == 422
    assert table_counts_before == table_counts_after
    assert sql_counts_before == sql_counts_after
    result.update(kind="independent_fixed_pagination_assertions", passed=True,
                  pagination=pagination, endpoint_calls=calls, scope_isolation=foreign_leak,
                  sql_counts_unchanged=True, table_counts_unchanged=True,
                  limits=["Real scratch ASGI and LanceDB, no browser or live provider.",
                          "Reuses original independently reproduced 130-record fixture."])
    SAFE_JSON.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True,"overlap":0,"missing":0,"total":130}))
    return 0


def test_original_130_document_failure_now_has_complete_disjoint_pages():
    assert main() == 0
