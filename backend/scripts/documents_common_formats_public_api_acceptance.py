"""Finite public-API acceptance for DOCX/PDF/CSV document search & deletion.

Run from ``backend/`` with the cached interpreter, e.g.::

    /private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python \
        scripts/documents_common_formats_public_api_acceptance.py \
        --scratch /private/tmp/atom-goal3-docs-acceptance

The script owns an absolute scratch SQLite + LanceDB + office/sheet tree, sets
the bounded test environment BEFORE importing the app, and calls the ordinary
HTTP surface with real JWTs for two real users in different workspaces. It
uses the production parsers (python-docx/pypdf/csv), the real LanceDB store,
and the cached local FastEmbed model (offline). It makes no LLM/provider calls
and downloads nothing.

This is an API-boundary harness, not a browser journey and not whole-Goal-3
acceptance. One synthetic file per format.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import subprocess
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _scratch_dir(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        root = Path("/private/tmp") / f"atom-goal3-docs-acceptance-{uuid.uuid4().hex[:8]}"
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "office").mkdir(parents=True, exist_ok=True)
    return root


def _configure_environment(scratch: Path) -> dict:
    """Absolute scratch wiring, set before any backend import."""
    db_path = scratch / "atom-acceptance.db"
    data_dir = scratch / "data"
    env = {
        "TESTING": "1",
        "SECRET_KEY": f"goal3-acceptance-{uuid.uuid4().hex}",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "ATOM_DATA_DIR": str(data_dir),
        "LANCEDB_URI_BASE": str(data_dir / "lancedb"),
        "ATOM_OFFICE_DIR": str(scratch / "office"),
        "EMBEDDING_PROVIDER": "fastembed",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "ATOM_KNOWLEDGE_VFS_ENABLED": "true",
    }
    # Use an existing local FastEmbed cache when present; never download.
    cache = os.getenv("FASTEMBED_CACHE_PATH")
    if not cache:
        candidates = [
            "/private/tmp/fastembed_cache",
            str(Path.home() / ".cache" / "fastembed"),
        ]
        cache = next((p for p in candidates if Path(p).is_dir()), "")
    if cache:
        env["FASTEMBED_CACHE_PATH"] = cache
    os.environ.update(env)
    return env


def _git_source() -> dict:
    def _git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=Path(__file__).resolve().parents[2],
                capture_output=True, text=True, check=False,
            ).stdout.strip()
        except Exception:
            return ""

    return {
        "revision": _git("rev-parse", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
    }


def _make_docx(marker: str) -> bytes:
    from docx import Document

    doc = Document()
    doc.add_heading("Falcon program", level=1)
    doc.add_paragraph(
        f"Project Falcon budget was approved at {marker} dollars.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Milestone"
    table.cell(0, 1).text = "Date"
    table.cell(1, 0).text = "Falcon launch"
    table.cell(1, 1).text = "2032-06-03"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pdf(marker: str) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf)
    pdf.drawString(72, 720, f"Vendor Zephyr contract renewal date is {marker}.")
    pdf.drawString(72, 700, "Annual support fee is 41250 dollars.")
    pdf.save()
    return buf.getvalue()


def _make_csv(marker: str) -> bytes:
    return (
        "region,metric,value\n"
        f"North,Orchid units,{marker}\n"
        "South,Tulip units,1180\n"
    ).encode("utf-8")


FORMATS = (
    {
        "name": "DOCX",
        "filename": "Falcon.docx",
        "content_type": (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"),
        "build": lambda: _make_docx("847,300"),
        "fact": "Project Falcon budget was approved at 847,300 dollars.",
        "query": "Project Falcon approved budget amount",
        "file_type": "docx",
    },
    {
        "name": "PDF",
        "filename": "Zephyr.pdf",
        "content_type": "application/pdf",
        "build": lambda: _make_pdf("2031-04-19"),
        "fact": "Vendor Zephyr contract renewal date is 2031-04-19.",
        "query": "Zephyr contract renewal date",
        "file_type": "pdf",
    },
    {
        "name": "CSV",
        "filename": "Orchid.csv",
        "content_type": "text/csv",
        "build": lambda: _make_csv("9241"),
        "fact": "North | Orchid units | 9241",
        "query": "Orchid units in the North region",
        "file_type": "csv",
    },
)


def _rpc(client, headers, action: str, params: dict) -> dict:
    response = client.post(
        f"/api/rpc/{action}", json={"params": params}, headers=headers)
    return {
        "status": response.status_code,
        "body": response.json() if response.content else None,
    }


def run(scratch: Path, env: dict) -> dict:
    # Import order matters: core.database reads the environment at import.
    import core.database as database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import core.models  # noqa: F401 - register the full model graph

    engine = create_engine(
        env["DATABASE_URL"], connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    # TESTING=1 forces core.database's own DB unless pytest is importing.
    # Point every service-level get_db_session() at this scratch file too.
    database.engine = engine
    database.SessionLocal = SessionLocal

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import api.document_routes as document_routes
    import api.rpc_routes as rpc_routes
    from core.auth import create_access_token
    from core.hybrid_search.fts_bootstrap import ensure_documents_fts_for_session
    from core.models import IngestedDocument, DatasetEntry, Tenant, User, Workspace

    tag = uuid.uuid4().hex[:8]
    tenant_id = f"tenant-{tag}"
    ws_a = f"ws-a-{tag}"
    ws_b = f"ws-b-{tag}"
    with SessionLocal() as session:
        session.add(Tenant(id=tenant_id, name=tenant_id, subdomain=tenant_id))
        session.add(Workspace(id=ws_a, tenant_id=tenant_id, name=ws_a))
        session.add(Workspace(id=ws_b, tenant_id=tenant_id, name=ws_b))
        user_a = User(
            id=f"user-a-{tag}", tenant_id=tenant_id, workspace_id=ws_a,
            email=f"a-{tag}@example.invalid", first_name="Acceptance",
            last_name="Owner", role="member", status="active", is_active=True,
        )
        user_b = User(
            id=f"user-b-{tag}", tenant_id=tenant_id, workspace_id=ws_b,
            email=f"b-{tag}@example.invalid", first_name="Acceptance",
            last_name="Peer", role="member", status="active", is_active=True,
        )
        session.add_all([user_a, user_b])
        session.commit()
        ensure_documents_fts_for_session(session)
        headers_a = {
            "Authorization": "Bearer " + create_access_token(
                {"sub": user_a.id}, user=user_a)}
        headers_b = {
            "Authorization": "Bearer " + create_access_token(
                {"sub": user_b.id}, user=user_b)}

    app = FastAPI()
    app.include_router(document_routes.router)
    app.include_router(rpc_routes.router)
    client = TestClient(app)

    retrieval = {"status": "unknown", "provider": "fastembed",
                 "cache": env.get("FASTEMBED_CACHE_PATH")}
    try:
        from core.embedding_service import EmbeddingService

        probe = asyncio.run(EmbeddingService().generate_embedding(
            "document retrieval acceptance probe"))
        retrieval.update(status="available", dimensions=len(probe))
    except Exception as exc:  # exact limitation, never a semantic claim
        retrieval.update(status="unavailable",
                         error=f"{type(exc).__name__}: {exc}")

    results = {
        "status": "failed",
        "source": _git_source(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "boundary": "public HTTP API (TestClient), real JWTs, real parsers/stores",
        "retrieval": retrieval,
        "scratch": {
            "root": str(scratch),
            "database_url": env["DATABASE_URL"],
            "atom_data_dir": env["ATOM_DATA_DIR"],
            "lancedb_uri_base": env["LANCEDB_URI_BASE"],
            "office_dir": env["ATOM_OFFICE_DIR"],
        },
        "users": {"owner": user_a.id, "peer": user_b.id,
                  "owner_workspace": ws_a, "peer_workspace": ws_b},
        "formats": [],
        "limitations": [
            "API boundary only; no browser UI journey is claimed.",
            "One synthetic file per format; not every parser/format variant.",
            "No generative/provider call; semantic search uses cached local FastEmbed.",
            "Stored-text export, not original-binary download.",
            "CSV also creates the separate Goal-4 sheet-dataset catalog; this "
            "document slice neither claims nor purges that derived catalog.",
            "Not live WorkDrive, connector breadth, restart, or whole Goal 3.",
        ],
    }

    for spec in FORMATS:
        record = {"format": spec["name"], "stages": {}, "ok": False}
        try:
            data = spec["build"]()
            record["fixture"] = {
                "synthetic": True,
                "filename": spec["filename"],
                "bytes": len(data),
                "sha256": _sha256(data),
            }
            stages = record["stages"]

            upload = client.post(
                "/api/documents/upload",
                files={"file": (spec["filename"], data, spec["content_type"])},
                headers=headers_a,
            )
            stages["upload"] = {"status": upload.status_code}
            assert upload.status_code == 200, upload.text
            doc_id = upload.json()["id"]
            record["document_id"] = doc_id

            opened = client.get(f"/api/documents/{doc_id}", headers=headers_a)
            assert opened.status_code == 200, opened.text
            body = opened.json()["data"]
            assert spec["fact"] in body["content"]
            assert body["metadata"]["file_type"] == spec["file_type"]
            assert body["metadata"].get("filename") == spec["filename"]
            stages["owner_open"] = {
                "status": 200,
                "fact_present": True,
                "file_type": body["metadata"]["file_type"],
                "filename": body["metadata"].get("filename"),
            }

            exported = client.get(
                f"/api/documents/{doc_id}/export",
                params={"format": "json"}, headers=headers_a)
            assert exported.status_code == 200, exported.text
            export_body = exported.json()
            assert spec["fact"] in export_body["content"]
            assert export_body["document_id"] == doc_id
            assert export_body["provenance_status"] == "authoritative"
            assert export_body["source_version_status"] == "matched"
            stages["owner_download"] = {
                "status": 200,
                "content_kind": export_body["content_kind"],
                "provenance_status": export_body["provenance_status"],
                "source_version_kind": export_body["source_version_kind"],
                "fact_present": True,
            }

            search = client.get(
                "/api/documents/search", params={"q": spec["query"]},
                headers=headers_a)
            assert search.status_code == 200, search.text
            hits = search.json()["results"]
            target = next((h for h in hits if h["id"] == doc_id), None)
            assert target is not None, hits
            assert spec["fact"] in target["content_preview"]
            assert target["metadata"].get("file_type") == spec["file_type"]
            assert target["metadata"].get("filename") == spec["filename"]
            stages["owner_search"] = {
                "status": 200,
                "rank": hits.index(target) + 1,
                "score": target["score"],
                "provenance": {
                    "file_type": target["metadata"].get("file_type"),
                    "filename": target["metadata"].get("filename"),
                    "source": target["metadata"].get("source"),
                },
            }

            hybrid = _rpc(client, headers_a, "documents.search",
                          {"query": spec["query"], "limit": 10})
            hybrid_body = hybrid["body"]["data"]
            hybrid_ids = {r.get("id") for r in hybrid_body.get("results", [])}
            assert hybrid["status"] == 200 and doc_id in hybrid_ids, hybrid
            stages["owner_agent_search"] = {
                "status": hybrid["status"],
                "hybrid": hybrid_body.get("hybrid"),
                "status_detail": hybrid_body.get("status"),
                "target_present": True,
            }

            peer_search = client.get(
                "/api/documents/search", params={"q": spec["query"]},
                headers=headers_b)
            assert peer_search.status_code == 200, peer_search.text
            assert doc_id not in {h["id"] for h in peer_search.json()["results"]}
            peer_search_text = json.dumps(peer_search.json())
            assert spec["fact"] not in peer_search_text
            stages["peer_search_denied"] = {"status": 200, "target_absent": True}

            for label, path, params in (
                ("peer_open_denied", f"/api/documents/{doc_id}", None),
                ("peer_download_denied", f"/api/documents/{doc_id}/export",
                 {"format": "json"}),
            ):
                denied = client.get(path, params=params, headers=headers_b)
                assert denied.status_code == 404, denied.text
                stages[label] = {"status": 404}

            unsigned = client.get(
                f"/api/documents/{doc_id}/export", params={"format": "json"})
            assert unsigned.status_code in (401, 403), unsigned.text
            stages["unsigned_download_denied"] = {
                "status": unsigned.status_code}

            owner_cat = _rpc(
                client, headers_a, "documents.cat",
                {"path": f"knowledge/documents/{doc_id}/content.lines"})
            owner_content = (owner_cat["body"] or {}).get("data", {}).get(
                "content", "")
            assert spec["fact"] in owner_content, owner_cat
            stages["owner_agent_open"] = {
                "status": owner_cat["status"], "fact_present": True}

            owner_grep = _rpc(
                client, headers_a, "documents.grep",
                {"pattern": spec["fact"], "path_prefix": "knowledge"})
            owner_matches = (owner_grep["body"] or {}).get(
                "data", {}).get("matches", [])
            assert any(spec["fact"] in (m.get("snippet") or "")
                       for m in owner_matches), owner_grep
            stages["owner_agent_grep"] = {
                "status": owner_grep["status"], "matches": len(owner_matches)}

            peer_grep = _rpc(
                client, headers_b, "documents.grep",
                {"pattern": spec["fact"], "path_prefix": "knowledge"})
            peer_matches = (peer_grep["body"] or {}).get(
                "data", {}).get("matches", [])
            assert peer_matches == [], peer_grep
            stages["peer_agent_grep_denied"] = {
                "status": peer_grep["status"], "matches": 0}

            peer_cat = _rpc(
                client, headers_b, "documents.cat",
                {"path": f"knowledge/documents/{doc_id}/content.lines"})
            peer_content = (peer_cat["body"] or {}).get("data", {}).get(
                "content", "")
            assert spec["fact"] not in peer_content, peer_cat
            stages["peer_agent_open_denied"] = {
                "status": peer_cat["status"], "fact_absent": True}

            delete = client.delete(f"/api/documents/{doc_id}", headers=headers_a)
            assert delete.status_code == 200, delete.text
            receipt = delete.json()
            deleted_data = receipt.get("data", {})
            verification = deleted_data.get("verification", {})
            assert verification.get("status") == "verified", receipt
            assert deleted_data.get("complete") is True, receipt
            assert deleted_data.get("deleted") is True, receipt
            stages["delete"] = {
                "status": 200,
                "verification": verification,
                "effects": deleted_data.get("effects"),
            }

            assert client.get(
                f"/api/documents/{doc_id}", headers=headers_a).status_code == 404
            assert client.get(
                f"/api/documents/{doc_id}/export",
                params={"format": "json"}, headers=headers_a
            ).status_code == 404
            after_search = client.get(
                "/api/documents/search", params={"q": spec["query"]},
                headers=headers_a)
            assert after_search.status_code == 200, after_search.text
            after_text = json.dumps(after_search.json())
            assert doc_id not in after_text and spec["fact"] not in after_text
            stages["post_delete_search_absent"] = {"status": 200}

            after_hybrid = _rpc(
                client, headers_a, "documents.search",
                {"query": spec["query"], "limit": 10})
            after_hybrid_ids = {
                r.get("id") for r in
                (after_hybrid["body"] or {}).get("data", {}).get("results", [])}
            assert doc_id not in after_hybrid_ids, after_hybrid
            stages["post_delete_agent_search_absent"] = {
                "status": after_hybrid["status"]}

            after_cat = _rpc(
                client, headers_a, "documents.cat",
                {"path": f"knowledge/documents/{doc_id}/content.lines"})
            after_content = (after_cat["body"] or {}).get("data", {}).get(
                "content", "")
            assert spec["fact"] not in after_content, after_cat
            stages["post_delete_agent_open_empty"] = {
                "status": after_cat["status"], "fact_absent": True}

            after_ls = _rpc(
                client, headers_a, "documents.ls",
                {"path": "knowledge/documents"})
            ls_text = json.dumps(after_ls["body"])
            assert doc_id not in ls_text, after_ls
            stages["post_delete_agent_ls_absent"] = {
                "status": after_ls["status"]}

            after_grep = _rpc(
                client, headers_a, "documents.grep",
                {"pattern": spec["fact"], "path_prefix": "knowledge"})
            grep_matches = (after_grep["body"] or {}).get(
                "data", {}).get("matches", [])
            assert grep_matches == [], after_grep
            stages["post_delete_agent_grep_absent"] = {
                "status": after_grep["status"], "matches": 0}

            # Durable-store readback (evidence, not a user boundary).
            with SessionLocal() as session:
                row = session.get(IngestedDocument, doc_id)
                fts_rows = 0
                try:
                    from sqlalchemy import text as sql_text
                    fts_rows = int(session.execute(sql_text(
                        "SELECT COUNT(*) FROM ingested_documents_fts "
                        "WHERE rowid = (SELECT rowid FROM ingested_documents "
                        "WHERE id = :id)"), {"id": doc_id}).scalar() or 0)
                except Exception:
                    fts_rows = -1
                from core.hybrid_search.lexical_ranker import (
                    search_documents_lexical,
                )
                lexical_after = search_documents_lexical(
                    session, spec["fact"], workspace_id=ws_a)
                materialized = Path(row.file_path) if row and row.file_path else None
                from core.lancedb_handler import get_lancedb_handler
                handler = get_lancedb_handler(ws_a)
                vector_rows = handler.count_document_rows_by_id(
                    "documents", doc_id)
            assert row is not None and row.freshness_status == "removed"
            # The SQL tombstone and its FTS mirror are intentionally retained
            # for receipt/replay identity; retrieval must filter them.
            assert lexical_after == []
            assert vector_rows == 0
            assert materialized is not None and not materialized.exists()
            stages["durable_store_readback"] = {
                "sql_tombstone": "removed",
                "fts_rows_retained_but_filtered": fts_rows,
                "lexical_results_after_delete": 0,
                "lancedb_rows": vector_rows,
                "materialized_file_absent": True,
            }
            with SessionLocal() as session:
                derived = session.query(DatasetEntry).filter(
                    DatasetEntry.workspace_id == ws_a,
                    DatasetEntry.source == "upload",
                    DatasetEntry.file_name == spec["filename"],
                ).all()
                record["derived_catalog_observation"] = {
                    "entries_after_document_delete": len(derived),
                    "statuses": [d.status for d in derived],
                    "in_document_read_search_export_boundary": False,
                    "note": (
                        "CSV upload also materializes the separate Goal-4 "
                        "sheet-dataset catalog; this document slice does not "
                        "claim or purge that derived analysis catalog."),
                }
            record["ok"] = True
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["traceback"] = traceback.format_exc()[-4000:]
        results["formats"].append(record)

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    passed = all(r.get("ok") for r in results["formats"])
    if retrieval.get("status") != "available":
        results["status"] = "bounded"
        results["limitation_detail"] = (
            "Local cached FastEmbed retrieval was unavailable; semantic search "
            f"is not claimed ({retrieval.get('error')}).")
    elif passed:
        results["status"] = "passed"
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    scratch = _scratch_dir(args.scratch)
    env = _configure_environment(scratch)
    try:
        result = run(scratch, env)
    except Exception as exc:
        result = {
            "status": "failed",
            "source": _git_source(),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "scratch": {"root": str(scratch)},
        }
    out = Path(args.out) if args.out else scratch / "result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({
        "status": result.get("status"),
        "out": str(out),
        "formats": [
            {"format": f.get("format"), "ok": f.get("ok"),
             "error": f.get("error")}
            for f in result.get("formats", [])
        ],
        "retrieval": result.get("retrieval", {}).get("status"),
    }, indent=2))
    return 0 if result.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
