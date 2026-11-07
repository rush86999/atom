#!/usr/bin/env python3
"""Read-only child-backend readback across a stop/start boundary.

NOT EXECUTED by the code-only worker. It logs in through the normal public auth
route, verifies the exact actor/scope, reads the scoped canvas and goal, and
requires the canvas office binding to be the exact target artifact. It hashes
both the target bytes and the bytes returned by the existing authenticated
office download route, parses the DOCX, and verifies the SQL document/dataset
rows plus their managed files.

It also proves every original ``canvas_audit`` row is byte-identical after
restore/startup/read and that exactly one restore-owned event exists with the
honest scope/provenance. The login's own ``users.last_login`` and auth audit
writes are disclosed separately as authentication bookkeeping; no business
write route is called.

No token, password, password hash, SQL parameter values, provider call or model
dispatch is persisted or logged. Memory is excluded and explicitly carries no
LanceDB/public-document-search claim.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import sqlite3
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restore_child_smoke as smoke  # noqa: E402

SCHEMA = "atom-child-restore-readback-2"
BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"


class ReadbackError(smoke.HarnessError):
    """A safe refusal in the child readback."""


def _safe_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _write_report(path: Path, report: Mapping[str, Any]) -> None:
    smoke._write_json(Path(path), report)


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_password(path: Path) -> str:
    try:
        st = Path(path).stat()
    except OSError as exc:
        raise ReadbackError(f"password file is unavailable: {exc}") from exc
    import stat as stat_module
    if not stat_module.S_ISREG(st.st_mode):
        raise ReadbackError("password file is not a regular file")
    if stat_module.S_IMODE(st.st_mode) & 0o077:
        raise ReadbackError("password file mode must be 0600")
    password = Path(path).read_text(encoding="utf-8").strip()
    if not password:
        raise ReadbackError("password file is empty")
    return password


def _db_connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(
        f"file:{Path(db_path).resolve().as_posix()}?mode=ro",
        uri=True, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def _query(
    con: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = (),
) -> Tuple[List[str], List[Dict[str, Any]]]:
    cur = con.execute(sql, params)
    columns = [item[0] for item in cur.description]
    rows = [dict(row) for row in cur.fetchall()]
    return columns, rows


def _one(
    con: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = (),
) -> Optional[Dict[str, Any]]:
    _columns, rows = _query(con, sql, params)
    return rows[0] if rows else None


def _canonical_hash(rows: List[Mapping[str, Any]]) -> str:
    text = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Client:
    """Loopback-only HTTP client with no environment proxy and no token output."""

    def __init__(self, base: str):
        parts = urlsplit(base)
        if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost"):
            raise ReadbackError("API base must be loopback http")
        self.host = parts.hostname or "127.0.0.1"
        self.port = int(parts.port or 80)
        self.base = base.rstrip("/")
        self.token = ""

    def request(
        self, method: str, path: str, body: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[int, Dict[str, str], bytes]:
        data = None
        headers = {"Accept": "*/*"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json"
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        conn = http.client.HTTPConnection(self.host, self.port, timeout=60)
        try:
            conn.request(method, path, body=data, headers=headers)
            response = conn.getresponse()
            payload = response.read()
            response_headers = {
                str(name).lower(): str(value)
                for name, value in response.getheaders()
            }
            return response.status, response_headers, payload
        finally:
            conn.close()

    def json(
        self, method: str, path: str, body: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[int, Dict[str, str], Dict[str, Any]]:
        status, headers, payload = self.request(method, path, body=body)
        try:
            parsed = json.loads(payload.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            parsed = {}
        return status, headers, parsed if isinstance(parsed, dict) else {}


def _docx_check(data: bytes, expected_text: str) -> Dict[str, Any]:
    valid_zip = False
    text = ""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            valid_zip = "word/document.xml" in archive.namelist()
        from docx import Document
        document = Document(io.BytesIO(data))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception:  # noqa: BLE001 - invalid DOCX is a failed check
        return {"valid": False, "text_exact": False, "text": ""}
    return {
        "valid": valid_zip,
        "text_exact": bool(expected_text) and expected_text in text,
        "text": text,
    }


def _parquet_check(path: Path, expected_columns: List[str],
                   expected_rows: List[List[Any]]) -> Dict[str, Any]:
    try:
        import pandas as pd
        frame = pd.read_parquet(path)
    except Exception:  # noqa: BLE001 - unreadable parquet is a failed check
        return {"readable": False, "columns_exact": False, "rows_exact": False,
                "columns": [], "rows": []}
    columns = [str(name) for name in frame.columns]
    try:
        rows = frame[columns].values.tolist()
    except Exception:  # noqa: BLE001
        rows = []
    return {
        "readable": True,
        "columns_exact": columns == list(expected_columns),
        "rows_exact": rows == expected_rows,
        "columns": columns,
        "rows": rows,
    }


def _audit_result(db_path: Path, baseline: Mapping[str, Any],
                  ids: Mapping[str, Any]) -> Dict[str, Any]:
    baseline_rows = [dict(row) for row in baseline["audit"]["rows"]]
    baseline_columns = list(baseline["audit"]["columns"])
    baseline_by_id = {str(row["id"]): row for row in baseline_rows}
    con = _db_connect(db_path)
    try:
        columns, rows = _query(con, "SELECT * FROM canvas_audit ORDER BY id")
    finally:
        con.close()
    columns_exact = columns == baseline_columns
    target_by_id = {str(row["id"]): row for row in rows}
    original_present = all(identity in target_by_id for identity in baseline_by_id)
    original_unchanged = original_present and all(
        target_by_id[identity] == row for identity, row in baseline_by_id.items())
    original_subset = [
        target_by_id[identity] for identity in sorted(baseline_by_id)
        if identity in target_by_id
    ]
    original_hash = _canonical_hash(original_subset)
    new_rows = [row for row in rows if str(row["id"]) not in baseline_by_id]
    restore_rows = [
        row for row in new_rows if str(row.get("action_type")) == "restore"
    ]
    non_restore_new = [
        row for row in new_rows if str(row.get("action_type")) != "restore"
    ]
    event = restore_rows[0] if len(restore_rows) == 1 else None
    details = _safe_json(event.get("details_json")) if event else {}
    provenance = _safe_json(details.get("restored_from")) if details else {}
    forbidden_keys = [
        key for key in ids.get("forbidden_authority_keys", [])
        if key in details
    ]
    blob = json.dumps(details, sort_keys=True, default=str)
    markers = [
        marker for marker in ids.get("forbidden_markers", [])
        if str(marker) in blob
    ]
    expected_manifest = (baseline.get("restore") or {}).get("manifest_sha256")
    expected_source_dir = (baseline.get("restore") or {}).get("source_data_dir")
    expected_target_dir = (baseline.get("restore") or {}).get("target_data_dir")
    tenant = str(ids.get("tenant_id"))
    provenance_checks = {
        "audit_id": str(provenance.get("audit_id")) == str(ids.get("audit_id")),
        "restore_event_id": str(provenance.get("restore_event_id")) == str(
            event.get("id") if event else ""),
        "manifest_sha256": provenance.get("manifest_sha256") == expected_manifest,
        "original_details_sha256": provenance.get("original_details_sha256") == (
            baseline["audit"]["original_details_sha256"]),
        "source_data_dir": provenance.get("source_data_dir") == expected_source_dir,
        "target_data_dir": provenance.get("target_data_dir") == expected_target_dir,
        "binding": provenance.get("binding") == "rebased_to_target",
        "source_canvas_tenant_id": str(
            provenance.get("source_canvas_tenant_id")) == tenant,
        "source_audit_tenant_id": str(
            provenance.get("source_audit_tenant_id")) == tenant,
    }
    event_actor_none = bool(
        event is not None
        and event.get("user_id") is None
        and event.get("agent_id") is None
        and event.get("session_id") is None
        and event.get("episode_id") is None
    )
    event_scope_checks = {
        "event_present": event is not None,
        "event_one": len(restore_rows) == 1,
        "event_no_non_restore_new": not non_restore_new,
        "event_tenant_exact": bool(event is not None
                                   and str(event.get("tenant_id")) == tenant),
        "event_canvas_exact": bool(event is not None
                                   and str(event.get("canvas_id")) == str(ids.get("canvas_id"))),
        "event_action_restore": bool(event is not None
                                     and str(event.get("action_type")) == "restore"),
        "event_actor_none": event_actor_none,
    }
    return {
        "columns_exact": columns_exact,
        "original_present": original_present,
        "original_unchanged": original_unchanged,
        "original_rows_count": len(baseline_rows),
        "original_rows_sha256": original_hash,
        "baseline_original_rows_sha256": baseline["audit"]["original_rows_sha256"],
        "new_row_count": len(new_rows),
        "restore_row_count": len(restore_rows),
        "non_restore_new_rows": len(non_restore_new),
        "restore_event": {
            "id": event.get("id") if event else None,
            "canvas_id": event.get("canvas_id") if event else None,
            "tenant_id": event.get("tenant_id") if event else None,
            "action_type": event.get("action_type") if event else None,
            "user_id": event.get("user_id") if event else None,
            "agent_id": event.get("agent_id") if event else None,
            "session_id": event.get("session_id") if event else None,
            "episode_id": event.get("episode_id") if event else None,
            "canvas_type": event.get("canvas_type") if event else None,
            "restored_from": {
                key: provenance.get(key) for key in (
                    "audit_id", "created_at", "action_type",
                    "original_details_sha256", "manifest_sha256",
                    "source_data_dir", "target_data_dir", "restore_event_id",
                    "source_canvas_tenant_id", "source_audit_tenant_id",
                    "binding", "note",
                )
            },
            "forbidden_keys_present": forbidden_keys,
            "forbidden_markers_present": markers,
        },
        "provenance_checks": provenance_checks,
        "event_scope_checks": event_scope_checks,
        "forbidden_keys_present": forbidden_keys,
        "forbidden_markers_present": markers,
        "ok": bool(
            columns_exact and original_unchanged and len(restore_rows) == 1
            and not non_restore_new and all(provenance_checks.values())
            and all(event_scope_checks.values()) and not forbidden_keys and not markers
        ),
    }


def _user_result(db_path: Path, me: Mapping[str, Any],
                 ids: Mapping[str, Any], baseline: Mapping[str, Any]) -> Dict[str, Any]:
    con = _db_connect(db_path)
    try:
        user = _one(
            con,
            "SELECT id, email, role, status, tenant_id, workspace_id, last_login "
            "FROM users WHERE id=?", (ids.get("user_id"),))
        audit_count_row = _one(
            con,
            "SELECT count(*) AS count FROM saas_audit_logs "
            "WHERE action='login_success' AND user_id=?",
            (ids.get("user_id"),))
    finally:
        con.close()
    if user is None:
        raise ReadbackError("scratch user row is missing from the target")
    before_count = int(baseline.get("login_audit_count_before") or 0)
    after_count = int((audit_count_row or {}).get("count") or 0)
    actor_checks = {
        "me_id": str(me.get("id")) == str(ids.get("user_id")),
        "me_email": str(me.get("email")) == str(ids.get("email")),
        "me_role": str(me.get("role")) == str(ids.get("seeded_role")),
        "me_status": str(me.get("status")) == "active",
        "me_workspace": str(me.get("workspace_id")) == str(ids.get("workspace_id")),
        "db_id": str(user.get("id")) == str(ids.get("user_id")),
        "db_email": str(user.get("email")) == str(ids.get("email")),
        "db_role": str(user.get("role")) == str(ids.get("seeded_role")),
        "db_status": str(user.get("status")) == "active",
        "db_tenant": str(user.get("tenant_id")) == str(ids.get("tenant_id")),
        "db_workspace": str(user.get("workspace_id")) == str(ids.get("workspace_id")),
    }
    last_login_updated = user.get("last_login") not in (None, "")
    auth_count_added = after_count - before_count
    auth_bookkeeping_observed = bool(last_login_updated and auth_count_added >= 1)
    return {
        "actor": {
            "id": user.get("id"),
            "email": user.get("email"),
            "role": user.get("role"),
            "status": user.get("status"),
            "tenant_id": user.get("tenant_id"),
            "workspace_id": user.get("workspace_id"),
        },
        "actor_checks": actor_checks,
        "auth_bookkeeping_observed": auth_bookkeeping_observed,
        "bookkeeping": {
            "business_mutations_after_restore": False,
            "business_mutation_basis": (
                "No business write route was called; original canvas_audit "
                "rows are unchanged and the canvas/goal/document/dataset "
                "fixture rows match the restored target after startup."),
            "authentication": {
                "disclosed": True,
                "last_login_updated": last_login_updated,
                "login_audit_rows_before": before_count,
                "login_audit_rows_after": after_count,
                "login_audit_rows_added": auth_count_added,
            },
            "http_write_methods_called": ["POST /api/auth/login"],
            "business_write_methods_called": [],
            "startup_bookkeeping": (
                "Startup may write the product wipe-check fingerprint, the "
                "product-generated bootstrap password file (0600 in scratch), "
                "and operational/auth receipts; no business write route was "
                "called by this readback."),
        },
        "ok": all(actor_checks.values()) and auth_bookkeeping_observed,
    }


def _goal_result(db_path: Path, goal_http: Mapping[str, Any],
                 ids: Mapping[str, Any]) -> Dict[str, Any]:
    con = _db_connect(db_path)
    try:
        goal = _one(
            con,
            "SELECT id, title, description, status, owner_id, workspace_id, "
            "tenant_id, source FROM goal_objectives WHERE id=?",
            (ids.get("goal_id"),))
    finally:
        con.close()
    if goal is None:
        raise ReadbackError("scratch goal row is missing from the target")
    checks = {
        "goal_http_id": str(goal_http.get("id")) == str(ids.get("goal_id")),
        "goal_http_title": str(goal_http.get("title")) == str(goal.get("title")),
        "goal_http_owner": str(goal_http.get("owner_id")) == str(ids.get("user_id")),
        "goal_http_status": str(goal_http.get("status")) == str(goal.get("status")),
        "goal_http_source": str(goal_http.get("source")) == str(goal.get("source")),
        "goal_db_id": str(goal.get("id")) == str(ids.get("goal_id")),
        "goal_db_owner": str(goal.get("owner_id")) == str(ids.get("user_id")),
        "goal_db_workspace": str(goal.get("workspace_id")) == str(ids.get("workspace_id")),
        "goal_db_tenant": str(goal.get("tenant_id")) == str(ids.get("tenant_id")),
    }
    return {
        "goal": {
            "id": goal.get("id"),
            "title": goal.get("title"),
            "status": goal.get("status"),
            "owner_id": goal.get("owner_id"),
            "workspace_id": goal.get("workspace_id"),
            "tenant_id": goal.get("tenant_id"),
            "source": goal.get("source"),
            "http_id": goal_http.get("id"),
            "http_title": goal_http.get("title"),
            "http_owner_id": goal_http.get("owner_id"),
        },
        "checks": checks,
        "ok": all(checks.values()),
    }


def _canvas_result(db_path: Path, canvas_http: Mapping[str, Any],
                   ids: Mapping[str, Any], baseline: Mapping[str, Any]) -> Dict[str, Any]:
    con = _db_connect(db_path)
    try:
        canvas = _one(
            con,
            "SELECT id, tenant_id, workspace_id, created_by, canvas_type, name, "
            "status, content FROM canvases WHERE id=?",
            (ids.get("canvas_id"),))
    finally:
        con.close()
    if canvas is None:
        raise ReadbackError("scratch canvas row is missing from the target")
    content = _safe_json(canvas.get("content"))
    expected = baseline["expected_target_paths"]["office_artifact"]
    binding = smoke.resolve_target_managed_path(
        content.get("office_file"), expected=expected,
        target_root=baseline["target_root"],
        missing_source_root=baseline["source_root"],
        preserved_source_root=baseline["preserved_source_root"],
        must_exist=True)
    checks = {
        "canvas_db_id": str(canvas.get("id")) == str(ids.get("canvas_id")),
        "canvas_db_tenant": str(canvas.get("tenant_id")) == str(ids.get("tenant_id")),
        "canvas_db_workspace": str(canvas.get("workspace_id")) == str(ids.get("workspace_id")),
        "canvas_db_creator": str(canvas.get("created_by")) == str(ids.get("user_id")),
        "canvas_db_type": str(canvas.get("canvas_type")) == str(ids.get("canvas_type")),
        "canvas_db_content_binding_exact": binding["checks"]["exact_expected_path"],
        "canvas_db_content_under_target": binding["checks"]["under_target_root"],
    }
    return {
        "canvas": {
            "id": canvas.get("id"),
            "tenant_id": canvas.get("tenant_id"),
            "workspace_id": canvas.get("workspace_id"),
            "created_by": canvas.get("created_by"),
            "canvas_type": canvas.get("canvas_type"),
            "name": canvas.get("name"),
            "content": content,
            "http": {
                key: canvas_http.get(key) for key in (
                    "canvas_id", "canvas_type", "action_type", "audit_id",
                    "title", "operation_id", "review_status", "content")
            },
        },
        "checks": checks,
        "binding": binding,
        "ok": all(checks.values()),
    }


def _document_result(db_path: Path, ids: Mapping[str, Any],
                     baseline: Mapping[str, Any]) -> Dict[str, Any]:
    con = _db_connect(db_path)
    try:
        row = _one(
            con,
            "SELECT id, file_name, file_path, file_size_bytes, tenant_id, "
            "workspace_id FROM ingested_documents WHERE id=?",
            (ids.get("document_id"),))
    finally:
        con.close()
    if row is None:
        raise ReadbackError("ingested document row is missing from the target")
    expected = baseline["expected_target_paths"]["document"]
    managed = smoke.validate_managed_file(
        row.get("file_path"), expected=expected,
        target_root=baseline["target_root"],
        missing_source_root=baseline["source_root"],
        preserved_source_root=baseline["preserved_source_root"],
        expected_sha256=ids["document_sha256"])
    text = ""
    if managed["resolved"]:
        try:
            text = Path(managed["resolved"]).read_text(encoding="utf-8")
        except OSError:
            text = ""
    checks = {
        "document_row_present": True,
        "document_id_exact": str(row.get("id")) == str(ids.get("document_id")),
        "document_tenant_exact": str(row.get("tenant_id")) == str(ids.get("tenant_id")),
        "document_workspace_exact": str(row.get("workspace_id")) == str(ids.get("workspace_id")),
        "document_exact_path": managed["checks"]["exact_expected_path"],
        "document_under_target": managed["checks"]["under_target_root"],
        "document_not_source": (
            managed["checks"]["not_original_source"]
            and managed["checks"]["not_preserved_source"]),
        "document_hash_exact": managed["checks"]["sha256_exact"],
        "document_text_exact": text == ids["document_text"],
    }
    return {
        "document": {
            "id": row.get("id"),
            "file_name": row.get("file_name"),
            "file_path": row.get("file_path"),
            "sha256": managed.get("sha256"),
            "text": text,
            "scope": "sql_row_plus_managed_file; not public document search",
        },
        "checks": checks,
        "ok": all(checks.values()),
    }


def _dataset_result(db_path: Path, ids: Mapping[str, Any],
                    baseline: Mapping[str, Any]) -> Dict[str, Any]:
    con = _db_connect(db_path)
    try:
        row = _one(
            con,
            "SELECT id, file_name, parquet_path, row_count, column_count, "
            "tenant_id, workspace_id, status FROM dataset_entries WHERE id=?",
            (ids.get("dataset_id"),))
    finally:
        con.close()
    if row is None:
        raise ReadbackError("dataset row is missing from the target")
    expected = baseline["expected_target_paths"]["parquet"]
    managed = smoke.validate_managed_file(
        row.get("parquet_path"), expected=expected,
        target_root=baseline["target_root"],
        missing_source_root=baseline["source_root"],
        preserved_source_root=baseline["preserved_source_root"],
        expected_sha256=ids["parquet_sha256"])
    parquet = _parquet_check(
        Path(managed["resolved"]) if managed["resolved"] else Path(expected),
        list(ids.get("parquet_columns") or []),
        [list(item) for item in (ids.get("parquet_rows") or [])])
    checks = {
        "dataset_row_present": True,
        "dataset_id_exact": str(row.get("id")) == str(ids.get("dataset_id")),
        "dataset_tenant_exact": str(row.get("tenant_id")) == str(ids.get("tenant_id")),
        "dataset_workspace_exact": str(row.get("workspace_id")) == str(ids.get("workspace_id")),
        "dataset_exact_path": managed["checks"]["exact_expected_path"],
        "dataset_under_target": managed["checks"]["under_target_root"],
        "dataset_not_source": (
            managed["checks"]["not_original_source"]
            and managed["checks"]["not_preserved_source"]),
        "dataset_hash_exact": managed["checks"]["sha256_exact"],
        "dataset_readable": parquet["readable"],
        "dataset_columns_exact": parquet["columns_exact"],
        "dataset_rows_exact": parquet["rows_exact"],
    }
    return {
        "dataset": {
            "id": row.get("id"),
            "file_name": row.get("file_name"),
            "parquet_path": row.get("parquet_path"),
            "sha256": managed.get("sha256"),
            "columns": parquet.get("columns"),
            "rows": parquet.get("rows"),
            "scope": "sql_row_plus_parquet_file; not public document search",
        },
        "checks": checks,
        "ok": all(checks.values()),
    }


def _artifact_result(
    client: Client, canvas_http: Mapping[str, Any], ids: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> Dict[str, Any]:
    expected = baseline["expected_target_paths"]["office_artifact"]
    returned = (canvas_http.get("content") or {}).get("office_file")
    disk_sha = _sha256_file(Path(expected)) if Path(expected).is_file() else None
    download_status = 0
    download_headers: Dict[str, str] = {}
    download_bytes = b""
    if returned:
        query = urlencode({
            "file_path": str(returned),
            "canvas_id": str(ids.get("canvas_id")),
        })
        download_status, download_headers, download_bytes = client.request(
            "GET", f"/api/v1/office/download?{query}")
    download_sha = (
        _sha256_bytes(download_bytes) if download_status == 200 and download_bytes
        else None)
    docx = _docx_check(download_bytes, str(ids.get("office_artifact_text") or ""))
    content_type = download_headers.get("content-type", "")
    binding = smoke.validate_exact_artifact(
        returned_binding=returned, expected_path=expected,
        target_root=baseline["target_root"],
        missing_source_root=baseline["source_root"],
        preserved_source_root=baseline["preserved_source_root"],
        expected_sha256=ids["office_artifact_sha256"],
        disk_sha256=disk_sha, download_sha256=download_sha,
        docx_valid=docx["valid"], text_exact=docx["text_exact"])
    checks = dict(binding["checks"])
    checks.update({
        "office_download_http_200": download_status == 200,
        "office_download_content_type": (
            "wordprocessingml" in content_type or "octet-stream" in content_type),
        "office_download_nonempty": bool(download_bytes),
    })
    return {
        "artifact": {
            "expected_path": str(expected),
            "bound_path": str(returned) if returned else None,
            "disk_sha256": disk_sha,
            "download_sha256": download_sha,
            "download_status": download_status,
            "content_type": content_type,
            "size_bytes": len(download_bytes),
            "docx_valid": docx["valid"],
            "docx_text_exact": docx["text_exact"],
            "docx_text": docx["text"],
            "scope": "authenticated office download route",
        },
        "checks": checks,
        "binding": binding,
        "ok": all(checks.values()),
    }


def _serving_result(
    health_status: int, health: Mapping[str, Any], args: argparse.Namespace,
    target_db: Path,
) -> Dict[str, Any]:
    identity = health.get("identity") or {}
    report = smoke.validate_health_identity(
        identity, pid=args.expected_pid, port=urlsplit(args.api_base).port or 0,
        backend_root=BACKEND_ROOT, target_db=target_db,
        expected_revision=args.expected_revision)
    checks = dict(report["checks"])
    checks["health_http_200"] = health_status == 200
    checks["health_status_present"] = bool(health.get("status"))
    checks["expected_instance_exact"] = (
        str(identity.get("instance_id")) == str(args.expected_instance_id)
        if args.expected_instance_id
        else bool(identity.get("instance_id")))
    return {
        "serving": {
            "pid": identity.get("pid"),
            "instance_id": identity.get("instance_id"),
            "source_id": identity.get("source_id"),
            "revision": identity.get("revision"),
            "database": identity.get("database"),
            "cwd": identity.get("cwd"),
            "backend_path": identity.get("backend_path"),
            "dirty": identity.get("dirty"),
            "dirty_paths": identity.get("dirty_paths") or [],
            "untracked_paths": identity.get("untracked_paths") or [],
        },
        "checks": checks,
        "ok": all(checks.values()),
    }


def _compare_restart(before: Mapping[str, Any],
                     after: Mapping[str, Any]) -> Dict[str, Any]:
    stable_fields = (
        "actor", "canvas", "goal", "document", "dataset", "artifact",
        "audit", "memory",
    )
    mismatches = {
        field: {"before": before.get(field), "after": after.get(field)}
        for field in stable_fields
        if before.get(field) != after.get(field)
    }
    before_serving = before.get("serving") or {}
    after_serving = after.get("serving") or {}
    serving_checks = {
        "pid_changed": before_serving.get("pid") != after_serving.get("pid"),
        "instance_id_changed": (
            before_serving.get("instance_id") != after_serving.get("instance_id")),
        "source_id_same": (
            before_serving.get("source_id") == after_serving.get("source_id")),
        "database_same": (
            before_serving.get("database") == after_serving.get("database")),
        "cwd_same": before_serving.get("cwd") == after_serving.get("cwd"),
        "backend_path_same": (
            before_serving.get("backend_path") == after_serving.get("backend_path")),
        "revision_same": (
            before_serving.get("revision") == after_serving.get("revision")),
    }
    return {
        "fields": list(stable_fields),
        "mismatches": mismatches,
        "serving_checks": serving_checks,
        "ok": not mismatches and all(serving_checks.values()),
    }


def _build_checks(
    *, args: argparse.Namespace, ids: Mapping[str, Any],
    baseline: Mapping[str, Any], audit: Mapping[str, Any],
    user: Mapping[str, Any], goal: Mapping[str, Any],
    canvas: Mapping[str, Any], document: Mapping[str, Any],
    dataset: Mapping[str, Any], artifact: Mapping[str, Any],
    serving: Mapping[str, Any], login_status: int, token: str,
    me_status: int, canvas_status: int, goal_status: int,
    restart: Optional[Mapping[str, Any]], target_db: Path,
) -> Dict[str, Any]:
    canvas_http = (canvas.get("canvas") or {}).get("http") or {}
    checks: Dict[str, bool] = {
        "source_original_missing": not Path(args.missing_source_root).exists(),
        "source_preserved_exists": Path(args.preserved_source_root).is_dir(),
        "target_db_exact": (
            _same_path(args.target_db, baseline.get("target_db"))
            and smoke._is_within(target_db, baseline.get("target_root"))),
        "login_http_200": login_status == 200,
        "token_present": bool(token),
        "me_http_200": me_status == 200,
        "me_actor_exact": bool(user.get("ok")),
        "me_scope_exact": bool(user.get("ok")),
        "canvas_http_200": canvas_status == 200,
        "canvas_success": bool(canvas_http.get("success")),
        "canvas_id_exact": str(canvas_http.get("canvas_id")) == str(ids.get("canvas_id")),
        "canvas_action_restore": str(canvas_http.get("action_type")) == "restore",
        "canvas_audit_event_exact": bool(
            (audit.get("restore_event") or {}).get("id"))
        and str(canvas_http.get("audit_id")) == str(
            (audit.get("restore_event") or {}).get("id")),
        "canvas_type_exact": str(canvas_http.get("canvas_type")) == str(
            ids.get("canvas_type")),
        "canvas_title_exact": str(canvas_http.get("title")) == str(
            ids.get("canvas_title")),
        "canvas_no_historical_operation": canvas_http.get("operation_id") is None,
        "canvas_review_status_unknown": (
            str(canvas_http.get("review_status")) == "unknown"),
        "canvas_row_scope_exact": bool(canvas.get("ok")),
        "goal_http_200": goal_status == 200,
        "goal_identity_exact": bool(goal.get("ok")),
        "goal_scope_exact": bool(goal.get("ok")),
        "goal_id_exact": bool((goal.get("checks") or {}).get("goal_http_id")),
        "goal_owner_exact": bool((goal.get("checks") or {}).get("goal_http_owner")),
        "goal_workspace_exact": bool(
            (goal.get("checks") or {}).get("goal_db_workspace")),
        "goal_tenant_exact": bool(
            (goal.get("checks") or {}).get("goal_db_tenant")),
        "canvas_db_scope_exact": bool(canvas.get("ok")),
        "canvas_db_content_binding_exact": bool(
            (canvas.get("checks") or {}).get("canvas_db_content_binding_exact")),
        "document_ok": bool(document.get("ok")),
        "document_row_present": bool(document.get("checks", {}).get("document_row_present")),
        "document_path_exact": bool(
            (document.get("checks") or {}).get("document_exact_path")),
        "document_hash_exact": bool(
            (document.get("checks") or {}).get("document_hash_exact")),
        "document_text_exact": bool(
            (document.get("checks") or {}).get("document_text_exact")),
        "dataset_ok": bool(dataset.get("ok")),
        "dataset_row_present": bool(dataset.get("checks", {}).get("dataset_row_present")),
        "dataset_path_exact": bool(
            (dataset.get("checks") or {}).get("dataset_exact_path")),
        "dataset_hash_exact": bool(
            (dataset.get("checks") or {}).get("dataset_hash_exact")),
        "dataset_rows_exact": bool(
            (dataset.get("checks") or {}).get("dataset_rows_exact")),
        "artifact_ok": bool(artifact.get("ok")),
        "office_binding_exact": bool(
            artifact.get("binding", {}).get("checks", {}).get("exact_expected_path")),
        "office_binding_under_target": bool(
            artifact.get("binding", {}).get("checks", {}).get("under_target_root")),
        "office_binding_not_source": bool(
            artifact.get("binding", {}).get("checks", {}).get("not_original_source")
            and artifact.get("binding", {}).get("checks", {}).get("not_preserved_source")),
        "office_file_hash_exact": bool(
            artifact.get("checks", {}).get("disk_sha256_exact")),
        "office_download_http_200": bool(
            artifact.get("checks", {}).get("office_download_http_200")),
        "office_download_content_type": bool(
            artifact.get("checks", {}).get("office_download_content_type")),
        "office_download_hash_exact": bool(
            artifact.get("checks", {}).get("download_sha256_exact")),
        "office_download_docx_valid": bool(
            artifact.get("checks", {}).get("docx_valid")),
        "office_download_text_exact": bool(
            artifact.get("checks", {}).get("docx_text_exact")),
        "original_audit_rows_unchanged": bool(audit.get("original_unchanged")),
        "original_audit_columns_exact": bool(audit.get("columns_exact")),
        "original_audit_hash_exact": (
            audit.get("original_rows_sha256")
            == baseline["audit"]["original_rows_sha256"]),
        "restore_event_present": bool(
            (audit.get("event_scope_checks") or {}).get("event_present")),
        "restore_event_one": bool(
            (audit.get("event_scope_checks") or {}).get("event_one")),
        "restore_event_no_non_restore_new": bool(
            (audit.get("event_scope_checks") or {}).get("event_no_non_restore_new")),
        "restore_event_tenant_exact": bool(
            (audit.get("event_scope_checks") or {}).get("event_tenant_exact")),
        "restore_event_canvas_exact": bool(
            (audit.get("event_scope_checks") or {}).get("event_canvas_exact")),
        "restore_event_action_restore": bool(
            (audit.get("event_scope_checks") or {}).get("event_action_restore")),
        "restore_event_actor_none": bool(
            (audit.get("event_scope_checks") or {}).get("event_actor_none")),
        "restore_event_provenance_exact": (
            bool(audit.get("provenance_checks"))
            and all((audit.get("provenance_checks") or {}).values())),
        "restore_event_scope_exact": (
            bool(audit.get("event_scope_checks"))
            and all((audit.get("event_scope_checks") or {}).values())),
        "restore_event_no_authority": not (
            audit.get("forbidden_keys_present")
            or audit.get("forbidden_markers_present")),
        "serving_identity_exact": bool(serving.get("ok")),
        "serving_pid_exact": bool(
            (serving.get("checks") or {}).get("pid_exact")),
        "serving_database_exact": bool(
            (serving.get("checks") or {}).get("database_exact")),
        "serving_revision_exact": bool(
            (serving.get("checks") or {}).get("revision_exact")),
        "serving_cwd_exact": bool(
            (serving.get("checks") or {}).get("cwd_exact")),
        "serving_instance_exact": bool(
            serving.get("checks", {}).get("expected_instance_exact")),
        "memory_excluded_labeled": (
            (ids.get("memory") or {}).get("included") is False
            and (baseline.get("memory") or {}).get("included") is False),
        "no_lancedb_claim": (
            (ids.get("memory") or {}).get("lancedb_search_claimed") is False
            and (baseline.get("memory") or {}).get("lancedb_search_claimed") is False),
        "no_public_document_search_claim": (
            (ids.get("memory") or {}).get(
                "public_document_search_claimed") is False
            and (baseline.get("memory") or {}).get(
                "public_document_search_claimed") is False),
        "business_mutations_after_restore_false": (
            (user.get("bookkeeping") or {}).get(
                "business_mutations_after_restore") is False),
        "auth_bookkeeping_disclosed": (
            (user.get("bookkeeping") or {}).get(
                "authentication", {}).get("disclosed") is True),
        "auth_bookkeeping_observed": bool(user.get("auth_bookkeeping_observed")),
        "no_business_write_methods": (
            (user.get("bookkeeping") or {}).get(
                "business_write_methods_called") == []),
    }
    if restart is not None:
        checks["restart_agreement_ok"] = bool(restart.get("ok"))
    return checks


def _same_path(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return False
    try:
        return Path(str(left)).expanduser().resolve(strict=False) == Path(
            str(right)).expanduser().resolve(strict=False)
    except (OSError, ValueError):
        return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--ids", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--missing-source-root", required=True)
    parser.add_argument("--preserved-source-root", required=True)
    parser.add_argument("--expected-pid", type=int, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-instance-id", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--compare-to", default="")
    args = parser.parse_args(argv)

    report: Dict[str, Any] = {
        "schema": SCHEMA,
        "ok": False,
        "checks": {},
        "failed_checks": [],
        "memory": {
            "included": False,
            "lancedb_search_claimed": False,
            "public_document_search_claimed": False,
        },
        "model_dispatched": False,
        "business_completion_claimed": False,
        "timestamp": smoke._now(),
    }
    try:
        missing = Path(args.missing_source_root).expanduser()
        preserved = Path(args.preserved_source_root).expanduser()
        if missing.exists():
            raise ReadbackError(
                f"original source is still available: {missing}")
        if not preserved.is_dir():
            raise ReadbackError(
                f"preserved source is not present: {preserved}")
        ids = _read_json(Path(args.ids))
        baseline = _read_json(Path(args.baseline))
        if not (baseline.get("restore") or {}).get("manifest_sha256"):
            raise ReadbackError("baseline lacks the verified restore manifest")
        password = _read_password(Path(args.password_file))

        target_root = Path(args.target_root).expanduser().resolve()
        target_db = Path(args.target_db).expanduser().resolve()
        if target_root != Path(baseline["target_root"]).resolve():
            raise ReadbackError("target root differs from the frozen baseline")
        if target_db != Path(baseline["target_db"]).resolve():
            raise ReadbackError("target database differs from the frozen baseline")
        if not target_db.is_file():
            raise ReadbackError("target database is missing")

        client = Client(args.api_base)
        login_status, _login_headers, login_body = client.json(
            "POST", "/api/auth/login",
            {"username": args.email, "password": password})
        token = str(login_body.get("access_token") or "")
        if login_status == 200 and token:
            client.token = token
        me_status, _me_headers, me = client.json("GET", "/api/auth/me")
        canvas_status, _canvas_headers, canvas_http = client.json(
            "GET", f"/api/canvas/{ids.get('canvas_id')}")
        goal_status, _goal_headers, goal_http = client.json(
            "GET", f"/api/goals/{ids.get('goal_id')}")
        health_status, _health_headers, health = client.json(
            "GET", "/api/health")

        audit = _audit_result(target_db, baseline, ids)
        user = _user_result(target_db, me, ids, baseline)
        goal = _goal_result(target_db, goal_http, ids)
        canvas = _canvas_result(target_db, canvas_http, ids, baseline)
        document = _document_result(target_db, ids, baseline)
        dataset = _dataset_result(target_db, ids, baseline)
        artifact = _artifact_result(client, canvas_http, ids, baseline)
        serving = _serving_result(health_status, health, args, target_db)

        report.update({
            "serving": serving["serving"],
            "actor": user["actor"],
            "bookkeeping": user["bookkeeping"],
            "canvas": canvas["canvas"],
            "goal": goal["goal"],
            "document": document["document"],
            "dataset": dataset["dataset"],
            "artifact": artifact["artifact"],
            "audit": {
                "columns_exact": audit["columns_exact"],
                "original_rows_count": audit["original_rows_count"],
                "original_rows_sha256": audit["original_rows_sha256"],
                "baseline_original_rows_sha256": audit[
                    "baseline_original_rows_sha256"],
                "original_unchanged": audit["original_unchanged"],
                "new_row_count": audit["new_row_count"],
                "restore_row_count": audit["restore_row_count"],
                "non_restore_new_rows": audit["non_restore_new_rows"],
                "restore_event": audit["restore_event"],
                "provenance_checks": audit["provenance_checks"],
                "event_scope_checks": audit["event_scope_checks"],
                "forbidden_keys_present": audit["forbidden_keys_present"],
                "forbidden_markers_present": audit[
                    "forbidden_markers_present"],
            },
            "http": {
                "login": {"method": "POST", "path": "/api/auth/login",
                          "status": login_status},
                "me": {"method": "GET", "path": "/api/auth/me",
                       "status": me_status},
                "canvas": {"method": "GET",
                           "path": f"/api/canvas/{ids.get('canvas_id')}",
                           "status": canvas_status},
                "goal": {"method": "GET",
                         "path": f"/api/goals/{ids.get('goal_id')}",
                         "status": goal_status},
                "office_download": {
                    "method": "GET", "path": "/api/v1/office/download",
                    "status": artifact["artifact"]["download_status"]},
                "health": {"method": "GET", "path": "/api/health",
                           "status": health_status},
            },
        })
        checks = _build_checks(
            args=args, ids=ids, baseline=baseline, audit=audit, user=user,
            goal=goal, canvas=canvas, document=document, dataset=dataset,
            artifact=artifact, serving=serving, login_status=login_status,
            token=token, me_status=me_status, canvas_status=canvas_status,
            goal_status=goal_status, restart=None, target_db=target_db)
        restart = None
        if args.compare_to:
            before = _read_json(Path(args.compare_to))
            restart = _compare_restart(before, report)
            checks = _build_checks(
                args=args, ids=ids, baseline=baseline, audit=audit,
                user=user, goal=goal, canvas=canvas, document=document,
                dataset=dataset, artifact=artifact, serving=serving,
                login_status=login_status, token=token, me_status=me_status,
                canvas_status=canvas_status, goal_status=goal_status,
                restart=restart, target_db=target_db)
            report["restart_agreement"] = restart
        evaluation = smoke.check_named_booleans(checks, label="readback")
        report["checks"] = checks
        report["failed_checks"] = evaluation["failed_checks"]
        report["ok"] = evaluation["ok"]
        _write_report(Path(args.out), report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if evaluation["ok"] else 1
    except Exception as exc:  # noqa: BLE001 - always write a safe failure report
        report["checks"] = {"readback_completed": False}
        report["failed_checks"] = ["readback_completed"]
        report["error"] = f"{type(exc).__name__}: {exc}"
        _write_report(Path(args.out), report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
