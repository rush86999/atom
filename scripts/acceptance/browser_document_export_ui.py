#!/usr/bin/env python3
"""Prepared ordinary-UI episode for the stored-text Documents export.

PREPARATION ONLY BY DEFAULT (root owns the actual browser episode)
==================================================================
With no mode flag (or with ``--preflight``) this driver launches nothing. It
reads Git/source/config, proves the retained API evidence still describes the
current bytes, and proves whether the existing FastEmbed cache/runtime is
usable offline. ``--execute`` is root-owned and runs one ordinary UI episode in
a fresh marked isolated world.

The episode is deliberately narrow:

  normal admin login -> public onboarding wizard (visible, durable) -> Data ->
  synthetic TXT upload through the real file input -> list shows the exact
  document -> card opens /documents/<doc_id> -> reload same id/content ->
  Text / Markdown / JSON from the existing detail export control -> real
  browser Blob/object-URL download -> compare the downloaded bytes with the
  actual export API response bytes, full stored text and tail, filenames,
  content type and provenance/scope headers -> read-only SQL/index readback.

Reused existing infrastructure (no new engine):
  * ``backend/scripts/orchestration_acceptance/run_isolated.py``
    (world build, storage guard, sandboxed server launch)
  * ``backend/scripts/orchestration_acceptance/case5_browser_recovery.py``
    (``start_frontend_copy``, ``NetWatch``)
  * ``backend/scripts/orchestration_acceptance/browser_verify.py``
    (``ui_login`` real form)
  * ``scripts/acceptance/browser_agent_job_wait.py``
    (source/health/source-binding/API/DB/screenshot/wait helpers)

Credential isolation: the general launcher installs value-free
``.env``/``.env.local`` guards at the world root and backend farm root before
Popen. Without them a bare ``load_dotenv()`` in world code walks up from
``backend/data/acceptance_worlds`` and can load the live ``backend/.env``
(operator model config, BYOK Fernet key, API keys) into the sandboxed server.
The driver explicitly sets ``ATOM_AGENT_EVOLUTION_ENABLED=false`` before launch
and the launcher whitelist forwards it; the actual child process env is the
only positive worker-flag proof. Source/profile shape is diagnostic only.

Why the retained 37-case API suite is referenced, not re-run
------------------------------------------------------------
``docs/acceptance/evidence/document_export_lead_011b8373e`` retains the
accepted 37 public-route controls for missing source, foreign scope, revoked,
stale, wrong revision, unsafe headers and nullable scope. The preflight proves
the product/API/frontend source bytes are the same bytes that suite ran
against. This episode therefore exercises only the missing ordinary-browser
download boundary; it does not repeat the API matrix.

What this episode does NOT claim
--------------------------------
Original-binary download (TXT extraction happens to equal the bytes for plain
text, so this is explicitly not called binary coverage), search/grounding,
model/provider quality, a model call, a backend/frontend restart, PostgreSQL,
soak, multi-worker or whole-app acceptance. A local FastEmbed index write is
not claimed as provider embedding quality.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.orchestration_acceptance import run_isolated as R  # noqa: E402


def _load_d3():
    path = REPO / "scripts" / "acceptance" / "browser_agent_job_wait.py"
    spec = importlib.util.spec_from_file_location("browser_agent_job_wait", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D3 = _load_d3()

ADMIN_EMAIL = D3.ADMIN_EMAIL
WORLD_PREFIX = "document_export_ui_"
EXPORT_FORMATS = ("text", "markdown", "json")
FORMAT_EXTENSION = {"text": "txt", "markdown": "md", "json": "json"}
FORMAT_LABEL = {
    "text": "Text (.txt)",
    "markdown": "Markdown (.md)",
    "json": "JSON (.json)",
}
FORMAT_CONTENT_TYPE = {
    "text": "text/plain; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
}
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_FASTEMBED_REPO = "models--qdrant--bge-small-en-v1.5-onnx-q"
FASTEMBED_REQUIRED_FILES = (
    "model_optimized.onnx",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
)
HEAVY_THRESHOLD_BYTES = 4 * 1024 * 1024 * 1024
DOC_ID_RE = re.compile(r"^doc_[0-9a-f]{24}$")
EXTRACTION_RE = re.compile(r"^ev4:[0-9a-f]{64}$")

WORLDS_ROOT = BACKEND / "data" / "acceptance_worlds"
RETAINED_EVIDENCE = (
    REPO / "docs" / "acceptance" / "evidence"
    / "document_export_lead_011b8373e" / "MANIFEST.json"
)

SOURCE_FILES = [
    "backend/api/document_routes.py",
    "backend/core/auto_document_ingestion.py",
    "backend/core/doc_freshness_service.py",
    "backend/core/embedding_service.py",
    "backend/core/lancedb_handler.py",
    "backend/core/personal_scope.py",
    "backend/core/product_profile.py",
    "backend/core/world_storage_guard.py",
    "backend/scripts/orchestration_acceptance/run_isolated.py",
    "backend/scripts/orchestration_acceptance/browser_verify.py",
    "backend/scripts/orchestration_acceptance/case5_browser_recovery.py",
    "frontend-nextjs/components/layout/Sidebar.tsx",
    "frontend-nextjs/lib/api.ts",
    "frontend-nextjs/pages/documents.tsx",
    "frontend-nextjs/pages/documents/[docId].tsx",
    "scripts/acceptance/browser_agent_job_wait.py",
    "scripts/acceptance/browser_document_export_ui.py",
    "scripts/acceptance/evidence_git_check.py",
    "scripts/tests/test_browser_document_export_ui.py",
]
FRONTEND_SOURCE_FILES = [
    "frontend-nextjs/components/layout/Sidebar.tsx",
    "frontend-nextjs/lib/api.ts",
    "frontend-nextjs/pages/documents.tsx",
    "frontend-nextjs/pages/documents/[docId].tsx",
]
LAUNCHER_FILES = (
    "backend/scripts/orchestration_acceptance/run_isolated.py",
    "backend/scripts/orchestration_acceptance/provider_shim.py",
    "backend/scripts/orchestration_acceptance/case5_browser_recovery.py",
    "backend/scripts/orchestration_acceptance/browser_verify.py",
    "scripts/acceptance/browser_agent_job_wait.py",
)
# run_isolated.build_world writes <ACC>/venv_freeze.txt in addition to the
# per-world copy, and it does so WITHOUT creating <ACC> first. The directory
# must therefore already exist and be writable before the builder is called.
# venv_freeze.txt is GENERATED output (a recorded virtualenv freeze); it is not
# a tracked fixture and committing one would only hide this defect.
ACC_DIR = REPO / "docs" / "architecture" / "orchestration_migration" / "acceptance"
FIXTURES_DIR = ACC_DIR / "fixtures"
FIXTURE_CHECKSUMS = FIXTURES_DIR / "SHA256SUMS"
FIXTURE_ENTRY_COUNT = 55
FIXTURE_CHECKSUM_NAME = "SHA256SUMS"

LABELS = {
    "fixture": (
        "SYNTHETIC USER FILE: a generated plain-text document with recognizable "
        "head/tail markers. It is not business data, not a model result and not "
        "a fabricated UI response."
    ),
    "account": (
        "Normal bootstrap admin created by the existing core.admin_bootstrap "
        "path and signed in through the real form. No token/cookie seed and no "
        "broad role was granted."
    ),
    "embedding": (
        "The upload uses the product's default local FastEmbed provider and the "
        "pre-existing model cache. Only local index-write availability is "
        "claimed; no provider or embedding-quality claim is made."
    ),
    "legacy_fixtures": (
        "LEGACY FRAMEWORK INPUTS: the 55 files named by the tracked "
        "docs/architecture/orchestration_migration/acceptance/fixtures/"
        "SHA256SUMS are existing acceptance inputs required by "
        "run_isolated.build_world (workbook parquet sheets plus old "
        "conversation/provider fixtures). They are NOT the document uploaded "
        "by this episode, they are not new business rows, and most are unused "
        "by the Documents export path. The uploaded TXT is generated and "
        "disclosed separately as synthetic user content."
    ),
    "production_boundary": (
        "The public document upload/detail/export routes, DocumentParser, "
        "LanceDB stored-text row, SQL IngestedDocument mirror, Personal "
        "NULL/default scope resolution, the normal login form and the existing "
        "Documents pages run in production code."
    ),
    "not_claimed": [
        "original-binary download (this is the stored-text export route; TXT "
        "extraction equals the source bytes for plain text, which is not used "
        "as a binary-download claim)",
        "document search, cross-surface search, grounding or retrieval quality",
        "model/provider/embedding quality or any model call during readiness",
        "a backend/frontend restart (reload + fresh SQL/index readback is used)",
        "member-role or foreign-workspace API negatives (retained unchanged in "
        "the referenced 37-case API evidence)",
        "PostgreSQL, multi-worker, soak, deployment or whole-app acceptance",
        "a production credential, operator .env, live database or BYOK read",
    ],
}


class PreflightError(RuntimeError):
    pass


class DriverError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# small pure helpers (unit-tested by scripts/tests)
# ---------------------------------------------------------------------------
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _query_param(url: str, key: str) -> Optional[str]:
    values = parse_qs(urlparse(url).query).get(key)
    return values[0] if values else None


def _query_dict(url: str) -> Dict[str, str]:
    allowed = ("format", "q", "limit", "operation_id")
    out: Dict[str, str] = {}
    parsed = parse_qs(urlparse(url).query)
    for key in allowed:
        if parsed.get(key):
            out[key] = parsed[key][0]
    return out


def _query_key_names(url: str) -> List[str]:
    return sorted(parse_qs(urlparse(url).query).keys())


FORBIDDEN_EXPORT_QUERY_PARAMS = (
    "path", "url", "file_path", "locator", "download", "kind",
    "content_kind", "original",
)


def _has_forbidden_export_query(url: str) -> bool:
    keys = set(_query_key_names(url))
    return any(key in keys for key in FORBIDDEN_EXPORT_QUERY_PARAMS)


def _fixture_document(run_id: str) -> Tuple[str, str, str]:
    """Build one deterministic synthetic TXT whose tail is past 20k chars."""
    safe = re.sub(r"[^a-z0-9]+", "-", str(run_id).lower()).strip("-")
    safe = safe or "fixture"
    filename = f"synthetic-document-export-{safe}.txt"
    head = (
        "[SYNTHETIC USER FILE] Stored-text export acceptance fixture. "
        "This is generated text, not business data and not a model result."
    )
    lines = [head]
    index = 0
    while len("\n".join(lines)) < 24000:
        lines.append(
            f"Line {index:05d}: synthetic stored export content; "
            "the full text must survive storage and export.")
        index += 1
    tail = f"EXPORT-EPISODE-TAIL-{safe.upper()}-END"
    text = "\n".join(lines + [tail]) + "\n"
    return filename, text, tail


def _expected_download_name(title: str, export_format: str,
                            doc_id: str) -> str:
    stem = re.sub(r"\.[a-z0-9]{1,8}$", "", str(title or ""), flags=re.I)
    stem = re.sub(r'[\\/:*?"<>|\r\n]+', "_", stem).strip()[:100]
    if not stem:
        stem = f"document-{str(doc_id)[:12]}"
    return f"{stem}.{FORMAT_EXTENSION[export_format]}"


def _parse_content_disposition(value: str) -> Dict[str, Optional[str]]:
    raw = str(value or "")
    out: Dict[str, Optional[str]] = {
        "filename": None, "filename_star": None, "decoded": None}
    match = re.search(r'filename="([^"]*)"', raw)
    if match:
        out["filename"] = match.group(1)
    match = re.search(r"filename\*=utf-8''([^;]+)", raw, flags=re.I)
    if match:
        from urllib.parse import unquote
        out["filename_star"] = unquote(match.group(1))
    out["decoded"] = out["filename_star"] or out["filename"]
    return out


def _checkset(checks: Dict[str, Any], label: str = "checks") -> Dict[str, Any]:
    """Reject an empty checkset or any value that is not literally True."""
    if not isinstance(checks, dict) or not checks:
        raise DriverError(f"{label}: empty checkset is not evidence")
    bad = [name for name, value in checks.items() if value is not True]
    if bad:
        raise DriverError(f"{label}: non-passing checks {bad}")
    return checks


def _verify_export_payload(
    export_format: str,
    api_bytes: bytes,
    downloaded_bytes: bytes,
    expected_text: str,
    tail_marker: str,
    doc_id: str,
    expected_version: str,
    headers: Dict[str, str],
    expected_filename: str,
    source_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare the actual API bytes, browser download bytes and provenance.

    This is the decisive anti-false-positive helper: a separate API download,
    an expected hash with a different binding, a 20k-truncated tail, a wrong
    document id or a mismatched source version all fail here.
    """
    lower = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    expected_text_bytes = expected_text.encode("utf-8")
    expected_sha = _sha256_bytes(expected_text_bytes)
    disposition = _parse_content_disposition(
        lower.get("content-disposition", ""))
    checks: Dict[str, Any] = {
        "api_bytes_nonempty": len(api_bytes) > 0,
        "download_bytes_nonempty": len(downloaded_bytes) > 0,
        "download_equals_api_bytes": downloaded_bytes == api_bytes,
        "download_sha256_equals_api": (
            _sha256_bytes(downloaded_bytes) == _sha256_bytes(api_bytes)),
        "content_type_exact": (
            lower.get("content-type") == FORMAT_CONTENT_TYPE[export_format]),
        "content_disposition_attachment": lower.get(
            "content-disposition", "").startswith("attachment;"),
        "content_disposition_filename": (
            disposition["decoded"] == expected_filename),
        "cache_control_no_store": (
            lower.get("cache-control") == "no-store"),
        "x_content_type_options_nosniff": (
            lower.get("x-content-type-options") == "nosniff"),
        "x_document_id_exact": lower.get("x-document-id") == doc_id,
        "x_document_content_kind": (
            lower.get("x-document-content-kind") == "extracted_text"),
        "x_document_provenance_authoritative": (
            lower.get("x-document-provenance") == "authoritative"),
        "x_document_source_version_exact": (
            lower.get("x-document-source-version") == expected_version),
        "x_document_source_version_kind": (
            lower.get("x-document-source-version-kind") == "versioned"),
        "x_document_source_version_status": (
            lower.get("x-document-source-version-status") == "matched"),
        "x_document_freshness_fresh": (
            lower.get("x-document-freshness") == "fresh"),
        "x_document_stored_text_sha256": (
            lower.get("x-document-stored-text-sha256") == expected_sha),
        "x_document_export_sha256": (
            lower.get("x-document-export-sha256")
            == _sha256_bytes(api_bytes)),
        "expected_full_text_over_20k": len(expected_text) > 20000,
        "expected_tail_marker_present": tail_marker in expected_text,
    }
    json_summary: Optional[Dict[str, Any]] = None
    if export_format in ("text", "markdown"):
        try:
            body_text = api_bytes.decode("utf-8")
        except UnicodeDecodeError:
            body_text = ""
        checks.update({
            "body_equals_full_stored_text": body_text == expected_text,
            "body_length_exact": len(api_bytes) == len(expected_text_bytes),
            "body_contains_tail_marker": tail_marker in body_text,
            "body_beyond_20k_present": (
                len(body_text) > 20000
                and body_text[20000:20040]
                == expected_text[20000:20040]),
            "download_sha256_equals_stored_text": (
                _sha256_bytes(downloaded_bytes) == expected_sha),
            "markdown_transform_header": (
                lower.get("x-document-export-transform") == "none"
                if export_format == "markdown" else True),
        })
    else:
        try:
            payload = json.loads(api_bytes.decode("utf-8"))
        except Exception:
            payload = {}
        json_summary = {
            "document_id": payload.get("document_id"),
            "format": payload.get("format"),
            "content_kind": payload.get("content_kind"),
            "source_version": payload.get("source_version"),
            "source_version_kind": payload.get("source_version_kind"),
            "source_version_status": payload.get("source_version_status"),
            "provenance_status": payload.get("provenance_status"),
            "freshness_status": payload.get("freshness_status"),
            "stored_text_bytes": payload.get("stored_text_bytes"),
            "stored_text_sha256": payload.get("stored_text_sha256"),
            "title": payload.get("title"),
            "file_name": payload.get("file_name"),
            "content_length": len(str(payload.get("content") or "")),
        }
        checks.update({
            "json_parsed": bool(payload),
            "json_document_id": payload.get("document_id") == doc_id,
            "json_content_equals_full_stored_text": (
                payload.get("content") == expected_text),
            "json_content_tail_marker": (
                tail_marker in str(payload.get("content") or "")),
            "json_content_length_exact": (
                len(str(payload.get("content") or ""))
                == len(expected_text)),
            "json_stored_text_bytes": (
                payload.get("stored_text_bytes")
                == len(expected_text_bytes)),
            "json_stored_text_sha256": (
                payload.get("stored_text_sha256") == expected_sha),
            "json_source_version_exact": (
                payload.get("source_version") == expected_version),
            "json_source_version_kind": (
                payload.get("source_version_kind") == "versioned"),
            "json_source_version_status": (
                payload.get("source_version_status") == "matched"),
            "json_provenance_authoritative": (
                payload.get("provenance_status") == "authoritative"),
            "json_freshness_fresh": (
                payload.get("freshness_status") == "fresh"),
            "json_format": payload.get("format") == "json",
            "json_content_kind": (
                payload.get("content_kind") == "extracted_text"),
            "json_file_name_expected": (
                payload.get("file_name")
                == (source_filename or expected_filename)),
            "json_title_expected": (
                payload.get("title")
                == (source_filename or expected_filename)),
            "json_reader": (
                payload.get("reader")
                == "lancedb.documents.get_document_by_id"),
        })
    failures = [name for name, value in checks.items() if value is not True]
    return {
        "ok": not failures,
        "checks": checks,
        "failures": failures,
        "api_sha256": _sha256_bytes(api_bytes),
        "download_sha256": _sha256_bytes(downloaded_bytes),
        "api_bytes": len(api_bytes),
        "download_bytes": len(downloaded_bytes),
        "stored_text_sha256": expected_sha,
        "expected_filename": expected_filename,
        "disposition": disposition,
        "headers": {
            key: lower.get(key) for key in (
                "content-type", "content-disposition", "cache-control",
                "x-content-type-options", "x-document-id",
                "x-document-content-kind", "x-document-provenance",
                "x-document-source-version",
                "x-document-source-version-kind",
                "x-document-source-version-status",
                "x-document-freshness",
                "x-document-stored-text-sha256",
                "x-document-export-sha256", "x-document-export-transform",
                "content-length",
            ) if lower.get(key) is not None
        },
        "json": json_summary,
    }


def _fastembed_cache_proof(
    cache_dir: Path,
    repo_name: str = DEFAULT_FASTEMBED_REPO,
    required_files: Tuple[str, ...] = FASTEMBED_REQUIRED_FILES,
) -> Dict[str, Any]:
    """Read-only proof that the exact local ONNX cache is present and complete.

    This never imports fastembed, starts ONNX, opens a socket or downloads.
    """
    base = Path(cache_dir)
    repo = base / repo_name
    metadata_path = repo / "files_metadata.json"
    files: Dict[str, Any] = {}
    problems: List[str] = []
    if not base.is_dir():
        problems.append(f"cache directory missing: {base}")
    if not repo.is_dir():
        problems.append(f"model repository directory missing: {repo}")
    metadata: Dict[str, Any] = {}
    if not metadata_path.is_file():
        problems.append(f"files_metadata.json missing: {metadata_path}")
    else:
        try:
            metadata = _read_json(metadata_path)
        except Exception as exc:
            problems.append(
                f"files_metadata.json unreadable: {type(exc).__name__}")
            metadata = {}
    if not isinstance(metadata, dict):
        problems.append("files_metadata.json is not an object")
        metadata = {}
    present_basenames = set()
    total_bytes = 0
    for rel, meta in metadata.items():
        if not isinstance(meta, dict):
            continue
        name = Path(str(rel)).name
        path = repo / str(rel)
        expected_size = meta.get("size")
        actual_size = path.stat().st_size if path.is_file() else None
        digest = _sha256_file(path) if path.is_file() else None
        entry = {
            "path": str(path),
            "expected_size": expected_size,
            "actual_size": actual_size,
            "size_matches": (
                isinstance(expected_size, int)
                and actual_size == expected_size),
            "sha256": digest,
            "blob_id": meta.get("blob_id"),
        }
        files[rel] = entry
        if path.is_file():
            present_basenames.add(name)
        if entry["size_matches"] and actual_size is not None:
            total_bytes += actual_size
        else:
            problems.append(f"size mismatch or missing file: {rel}")
    missing_required = sorted(
        set(required_files) - present_basenames)
    if missing_required:
        problems.append(f"required model files missing: {missing_required}")
    refs_path = repo / "refs" / "main"
    refs_revision = (
        refs_path.read_text(encoding="utf-8").strip()
        if refs_path.is_file() else None)
    snapshot_revisions = sorted({
        Path(str(rel)).parts[1]
        for rel in metadata
        if len(Path(str(rel)).parts) > 2
        and Path(str(rel)).parts[0] == "snapshots"
    })
    refs_match = bool(
        refs_revision and refs_revision in snapshot_revisions)
    if not refs_match:
        problems.append("refs/main is missing or does not match a snapshot")
    return {
        "ok": not problems,
        "cache_dir": str(base),
        "repo_dir": str(repo),
        "metadata_path": str(metadata_path),
        "metadata_sha256": (
            _sha256_file(metadata_path) if metadata_path.is_file() else None),
        "files": files,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "required_files": list(required_files),
        "missing_required": missing_required,
        "refs_main": refs_revision,
        "snapshot_revisions": snapshot_revisions,
        "refs_matches_snapshot": refs_match,
        "problems": problems,
        "downloaded_or_imported": False,
    }


def _output_target_probe(
    target: Path,
    worlds_root: Path = WORLDS_ROOT,
    require_empty: bool = False,
) -> Dict[str, Any]:
    """Refuse a wrong output: inside the worlds tree, a file, or unmarked reuse."""
    resolved = Path(target).resolve()
    root = Path(worlds_root).resolve()
    inside_worlds = resolved == root or root in resolved.parents
    exists = resolved.exists()
    is_dir = resolved.is_dir() if exists else True
    entries: List[str] = []
    if exists and is_dir:
        try:
            entries = sorted(p.name for p in resolved.iterdir())
        except OSError:
            entries = ["<unreadable>"]
    allowed = {"preflight.json"} if require_empty else set()
    unknown = [name for name in entries if name not in allowed]
    probe = resolved.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    writable = probe.exists() and os.access(probe, os.W_OK)
    problems: List[str] = []
    if inside_worlds:
        problems.append("output resolves inside the worlds root")
    if exists and not is_dir:
        problems.append("output path is an existing file, not a directory")
    if require_empty and unknown:
        problems.append(f"output is not fresh/marked; unexpected entries: {unknown}")
    if not writable:
        problems.append("nearest existing output ancestor is not writable")
    return {
        "ok": not problems,
        "target": str(resolved),
        "parent": str(resolved.parent),
        "existing_ancestor": str(probe),
        "existing_ancestor_writable": writable,
        "inside_worlds_root": inside_worlds,
        "exists": exists,
        "is_directory": is_dir,
        "entries": entries[:50],
        "allowed_entries": sorted(allowed),
        "unknown_entries": unknown[:50],
        "require_empty": require_empty,
        "problems": problems,
    }


def _world_name_for(source: Dict[str, Any], requested: Optional[str]) -> str:
    head = str(source.get("head") or "")
    name = requested or (WORLD_PREFIX + head[:10])
    if not name.startswith(WORLD_PREFIX):
        raise PreflightError(
            f"--world must start with {WORLD_PREFIX!r}; got {name!r}")
    if "/" in name or name in {".", ".."} or "\\" in name:
        raise PreflightError(f"--world is not a plain directory name: {name!r}")
    return name


def _world_path(name: str) -> Path:
    return D3._world_path(name)


# ---------------------------------------------------------------------------
# source / profile / cache preflight
# ---------------------------------------------------------------------------
def _git_bytes(path: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "show", f"HEAD:{path}"],
        capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise PreflightError(
            f"git show HEAD:{path} failed: "
            f"{proc.stderr.decode('utf-8', 'replace')[:300]}")
    return proc.stdout


def _git_blob(path: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", f"HEAD:{path}"],
        capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise PreflightError(f"git rev-parse HEAD:{path} failed")
    return proc.stdout.strip()


def _per_file_source_proof() -> Dict[str, Any]:
    files: Dict[str, Any] = {}
    ok = True
    for path in SOURCE_FILES:
        git_blob = _git_bytes(path)
        worktree = REPO / path
        actual = worktree.read_bytes() if worktree.is_file() else b""
        entry = {
            "git_blob": _git_blob(path),
            "git_sha256": _sha256_bytes(git_blob),
            "git_bytes": len(git_blob),
            "worktree_sha256": _sha256_bytes(actual),
            "worktree_bytes": len(actual),
            "matches": bool(actual) and actual == git_blob,
        }
        ok = ok and entry["matches"]
        files[path] = entry
    return {"ok": ok, "files": files}


def _source_contract_checks(
    head: Any,
    tracked_clean: bool,
    backend_clean: bool,
    expected_ok: bool,
    per_file_ok: bool,
) -> Dict[str, Any]:
    return {
        "head_present": bool(head),
        "tracked_tree_clean": tracked_clean is True,
        "backend_tree_clean": backend_clean is True,
        "expected_sha_ok": expected_ok is True,
        "per_file_git_source_proof": per_file_ok is True,
    }


def _profile_contract_checks(
    profile: Any,
    documents: Any,
    search: Any,
    tasks: Any,
    boards: Any,
    route: Any,
    worker_defaults: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "profile_core": profile == "core",
        "documents_enabled": documents is True,
        "documents_route": route == "documents",
        "search_deferred": search is False,
        "tasks_not_forced": tasks is False,
        "boards_not_forced": boards is False,
        "background_worker_defaults_off": all(
            worker_defaults.get(key) == "false"
            for key in ("ENABLE_SCHEDULER", "ENABLE_INGESTION_SYNC",
                        "ATOM_AGENT_EVOLUTION_ENABLED")),
    }


def _source_proof(expected_sha: Optional[str]) -> Dict[str, Any]:
    source = D3._source_probe(expected_sha)
    per_file = _per_file_source_proof()
    tracked_clean = source.get("tracked_dirty_count") == 0
    backend_clean = source.get("backend_dirty_count") == 0
    expected_ok = source.get("matches_expected") is not False
    checks = _source_contract_checks(
        source.get("head"), tracked_clean, backend_clean, expected_ok,
        per_file["ok"])
    return {
        **source,
        "tracked_tree_clean": tracked_clean,
        "backend_tree_clean": backend_clean,
        "expected_sha_ok": expected_ok,
        "per_file": per_file,
        "checks": checks,
        "source_proof_ok": all(checks.values()),
    }


def _retained_evidence_probe(
        evidence: Optional[str] = None,
        evidence_ref: str = "HEAD") -> Dict[str, Any]:
    """Check a committed API packet and its declared source against current bytes.

    Packet integrity is not a substitute for independent review of the recorded
    test outcome. A newer qualification must have its own packet; historical
    packets and their source hashes are never rewritten to match a repair.
    """
    directory = Path(evidence) if evidence else RETAINED_EVIDENCE.parent
    if not directory.is_absolute():
        directory = REPO / directory
    checker_path = Path(__file__).resolve().parents[2] / "scripts/acceptance/evidence_git_check.py"
    spec = importlib.util.spec_from_file_location("document_api_git_checker", checker_path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    if evidence_ref in checker.INDEX_REFS:
        return {"ok": False, "error": "API evidence requires a committed Git ref", "files": {}}
    verified = checker.verify(REPO, directory, evidence_ref, True)
    if not verified.get("passed"):
        return {"ok": False, "error": "committed API evidence verification failed",
                "git_verification": verified, "files": {}}
    relative = verified["evidence_path"] + "/MANIFEST.json"
    manifest = json.loads(checker._blob(REPO, verified["evidence_ref_commit"], relative))
    declared = manifest.get("source_files") or {}
    files: Dict[str, Any] = {}
    for path, expected in declared.items():
        target = REPO / path
        data = target.read_bytes() if target.is_file() else None
        files[path] = {
            "expected_sha256": expected,
            "actual_sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
            "matches": data is not None and checker._matches_sha256(data, expected),
        }
    return {
        "ok": bool(files and all(item["matches"] for item in files.values())),
        "path": str(directory),
        "evidence_ref_commit": verified["evidence_ref_commit"],
        "executed_source": verified.get("executed_source_commit"),
        "git_verification": verified,
        "files": files,
        "reuse_note": (
            "Committed packet and declared API/test source bytes verified. "
            "Test outcome and qualification scope require independent review; "
            "this probe does not execute tests or certify manifest completeness."),
    }


def _profile_probe() -> Dict[str, Any]:
    try:
        from core.product_profile import (
            active_profile, apply_runtime_defaults, capability_enabled,
            route_capability,
        )
        profile = active_profile()
        worker_keys = (
            "ENABLE_SCHEDULER",
            "ENABLE_INGESTION_SYNC",
            "ATOM_AGENT_EVOLUTION_ENABLED",
        )
        saved_worker_env = {
            key: os.environ.pop(key, None) for key in worker_keys}
        try:
            # Trace the core profile's intended defaults, not an operator
            # shell override that launch_server would not forward anyway.
            applied = apply_runtime_defaults()
        finally:
            for key, value in saved_worker_env.items():
                if value is not None:
                    os.environ[key] = value
        documents = capability_enabled("documents")
        search = capability_enabled("search")
        tasks = capability_enabled("tasks")
        boards = capability_enabled("boards")
        route = route_capability("/documents")
        checks = _profile_contract_checks(
            profile, documents, search, tasks, boards, route, applied)
        # The worker-default dict is a driver-process source diagnostic, not
        # proof of the sandboxed server's actual env. Exclude it from `ok`;
        # the execute step proves the three flags from the real child process.
        authority_checks = {
            key: value for key, value in checks.items()
            if key != "background_worker_defaults_off"}
        return {
            **checks,
            "ok": all(authority_checks.values()),
            "profile": profile,
            "documents_enabled": documents,
            "search_enabled": search,
            "tasks_enabled": tasks,
            "boards_enabled": boards,
            "documents_route": route,
            "runtime_defaults": applied,
            "worker_defaults_diagnostic": checks.get(
                "background_worker_defaults_off"),
            "worker_defaults_positive_authority": False,
            "checks": checks,
        }
    except Exception as exc:  # noqa: BLE001 - reported, not hidden
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "checks": {},
        }


def _static_source_contract_probe() -> Dict[str, Any]:
    """Freeze the exact product strings this browser episode depends on."""
    try:
        routes = (BACKEND / "api" / "document_routes.py").read_text(
            encoding="utf-8")
        upload_page = (REPO / "frontend-nextjs" / "pages" / "documents.tsx"
                       ).read_text(encoding="utf-8")
        detail_page = (REPO / "frontend-nextjs" / "pages" / "documents"
                       / "[docId].tsx").read_text(encoding="utf-8")
        sidebar = (REPO / "frontend-nextjs" / "components" / "layout"
                   / "Sidebar.tsx").read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    checks = {
        "export_route_present": '@router.get("/{doc_id}/export")' in routes,
        "export_formats_declared": (
            'DOCUMENT_EXPORT_FORMATS = ("text", "markdown", "json")' in routes),
        "export_bounded_2mib": (
            "MAX_DOCUMENT_EXPORT_BYTES = 2 * 1024 * 1024" in routes),
        "export_forbidden_client_params": (
            "_FORBIDDEN_EXPORT_PARAMS" in routes),
        "export_reads_full_stored_text": (
            'text = str(document.get("text") or "")' in routes),
        "export_auth_dependency": (
            "current_user: User = Depends(get_current_user)" in routes),
        "upload_accepts_txt": '"txt"' in routes,
        "upload_parses_txt_bytes": (
            "await DocumentParser.parse_document(content_bytes, file_ext, "
            "filename)" in routes),
        "upload_stores_extraction_revision": (
            '"source_content_hash": extraction_content_hash(content)' in routes),
        "upload_stores_fresh_sql_row": (
            '_row.freshness_status = "fresh"' in routes),
        "upload_binds_pg_join_key": '"pg_document_id": doc_id' in routes,
        "frontend_upload_endpoint": (
            "api.post('/api/documents/upload'" in upload_page),
        "frontend_list_card_link": (
            "router.push(`/documents/${doc.id}`)" in upload_page),
        "frontend_export_control": (
            'data-testid="document-export"' in detail_page
            and 'data-testid="document-export-format"' in detail_page
            and 'data-testid="document-export-submit"' in detail_page),
        "frontend_export_error_surface": (
            'data-testid="document-export-error"' in detail_page),
        "frontend_export_uses_document_id": (
            "/api/documents/${encodeURIComponent(document.id)}/export"
            in detail_page),
        "frontend_export_requests_blob": (
            "responseType: 'blob'" in detail_page),
        "frontend_export_real_blob_url": (
            "window.URL.createObjectURL(blob)" in detail_page
            and "link.download =" in detail_page
            and "link.click();" in detail_page),
        "sidebar_documents_link": (
            'label: "Data", icon: FileText, path: "/documents", '
            'capability: "documents"' in sidebar),
    }
    return {"ok": all(checks.values()), "checks": checks}


def _effective_cache_probe() -> Dict[str, Any]:
    """Resolve the cache path the sandboxed server will actually use."""
    effective = Path(tempfile.gettempdir()) / "fastembed_cache"
    override = os.environ.get("FASTEMBED_CACHE_PATH")
    override_path = Path(override).expanduser().resolve() if override else None
    effective_path = effective.resolve()
    tmpdir_forwarded = "TMPDIR" in R.SERVER_ENV_WHITELIST
    cache_env_forwarded = "FASTEMBED_CACHE_PATH" in R.SERVER_ENV_WHITELIST
    proof = _fastembed_cache_proof(effective_path)
    problems: List[str] = []
    if not tmpdir_forwarded:
        problems.append(
            "TMPDIR is not forwarded by launch_server; the server would use a "
            "different fastembed cache")
    if override and override_path != effective_path:
        problems.append(
            "FASTEMBED_CACHE_PATH is set but launch_server does not forward it; "
            "the effective server cache remains TMPDIR/fastembed_cache")
    if not proof["ok"]:
        problems.extend(proof["problems"])
    return {
        "ok": not problems,
        "tmpdir": tempfile.gettempdir(),
        "tmpdir_forwarded_by_launcher": tmpdir_forwarded,
        "cache_path_env_set": bool(override),
        "cache_path_env_forwarded_by_launcher": cache_env_forwarded,
        "effective_cache_dir": str(effective_path),
        "override_path": str(override_path) if override_path else None,
        "model": DEFAULT_EMBEDDING_MODEL,
        "repo_name": DEFAULT_FASTEMBED_REPO,
        "proof": proof,
        "problems": problems,
        "imported_or_started": False,
    }


def _fastembed_runtime_probe() -> Dict[str, Any]:
    """Read the installed package source; never import/instantiate/run it."""
    venv = BACKEND / "venv314"
    matches = sorted(venv.glob(
        "lib/python*/site-packages/fastembed/common/utils.py"))
    if not matches:
        return {
            "ok": False,
            "venv": str(venv),
            "error": (
                "backend/venv314 fastembed package is absent in this worktree; "
                "root must run from a prepared capture worktree"),
            "checks": {},
        }
    utils = matches[-1]
    site = utils.parents[2]
    models = site / "fastembed" / "common" / "model_management.py"
    onnx = site / "fastembed" / "text" / "onnx_embedding.py"
    dist = sorted(site.glob("fastembed-*.dist-info")) or sorted(
        site.glob("fastembed-*dist-info"))
    version = None
    if dist:
        metadata = dist[-1] / "METADATA"
        if metadata.is_file():
            for line in metadata.read_text(encoding="utf-8").splitlines():
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    break
    utils_text = utils.read_text(encoding="utf-8")
    models_text = models.read_text(encoding="utf-8") if models.is_file() else ""
    onnx_text = onnx.read_text(encoding="utf-8") if onnx.is_file() else ""
    checks = {
        "package_present": bool(dist),
        "version_recorded": bool(version),
        "default_cache_uses_tmpdir_fastembed_cache": (
            'tempfile.gettempdir(), "fastembed_cache"' in utils_text),
        "cache_path_env_supported": (
            'os.getenv("FASTEMBED_CACHE_PATH"' in utils_text),
        "hf_offline_respected_when_forwarded": (
            "HF_HUB_OFFLINE" in models_text),
        "local_files_only_attempted_first": (
            'cache_kwargs["local_files_only"] = True' in models_text),
        "bge_small_onnx_source_known": (
            "qdrant/bge-small-en-v1.5-onnx-q" in onnx_text),
    }
    return {
        **checks,
        "ok": all(checks.values()),
        "venv": str(venv),
        "version": version,
        "utils_path": str(utils),
        "utils_sha256": _sha256_file(utils),
        "model_management_sha256": (
            _sha256_file(models) if models.is_file() else None),
        "onnx_embedding_sha256": (
            _sha256_file(onnx) if onnx.is_file() else None),
        "note": (
            "fastembed 0.8.0 first calls download_files_from_huggingface with "
            "local_files_only=True, so a complete TMPDIR cache loads without "
            "an external network call; the sandbox denies external network "
            "anyway. It falls back to a remote metadata/download path only if "
            "the local cache is incomplete. FASTEMBED_CACHE_PATH/HF_HUB_OFFLINE "
            "are not forwarded by launch_server, so the effective path is the "
            "inherited TMPDIR/fastembed_cache. No model is started here."),
        "checks": checks,
    }


def _storage_probe() -> Dict[str, Any]:
    try:
        import core.world_storage_guard as WSG
        cfg = WSG.load_config()
        config = {
            "enabled": getattr(cfg, "enabled", None),
            "layout": getattr(cfg, "layout", None),
            "root": str(getattr(cfg, "root", "") or ""),
        }
        try:
            report = WSG.preflight()
            return {
                "ok": bool(getattr(report, "ok", False)),
                "config": config,
                "checks": list(getattr(report, "checks", []) or []),
                "problems": list(getattr(report, "problems", []) or []),
                "worlds_root": str(WORLDS_ROOT),
                "worlds_root_exists": WORLDS_ROOT.exists(),
                "worlds_root_is_symlink": WORLDS_ROOT.is_symlink(),
                "mkdir_in_preflight": False,
                "guard_invoked": True,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "config": config,
                "error": f"{type(exc).__name__}: {exc}",
                "worlds_root": str(WORLDS_ROOT),
                "worlds_root_exists": WORLDS_ROOT.exists(),
                "mkdir_in_preflight": False,
                "guard_invoked": True,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "worlds_root": str(WORLDS_ROOT),
            "mkdir_in_preflight": False,
            "guard_invoked": False,
        }


def _repo_relative(git_root: Path, path: Path) -> str:
    """Return a POSIX path relative to the Git worktree, or "" when outside."""
    try:
        return Path(path).resolve().relative_to(
            Path(git_root).resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def _git_blob_oid(data: bytes) -> str:
    """Hash raw bytes exactly as Git hashes a blob (no clean/smudge filters)."""
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _git_path_tracked(rel_path: str, git_root: Path = REPO) -> bool:
    if not rel_path:
        return False
    proc = subprocess.run(
        ["git", "-C", str(git_root), "ls-files", "--error-unmatch", "--",
         rel_path],
        capture_output=True, text=True, timeout=60)
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _git_tree_entries(git_root: Path, rel_dir: str) -> Dict[str, Any]:
    """Read the frozen HEAD tree for one directory (read-only, no checkout)."""
    if not rel_dir:
        return {
            "ok": False,
            "entries": {},
            "error": "directory is outside the Git worktree",
        }
    proc = subprocess.run(
        ["git", "-C", str(git_root), "ls-tree", "-r", "-z", "HEAD", "--",
         rel_dir],
        capture_output=True, timeout=120)
    if proc.returncode != 0:
        return {
            "ok": False,
            "entries": {},
            "error": (
                proc.stderr.decode("utf-8", "replace")[-300:]
                or f"git ls-tree exited {proc.returncode}"),
        }
    entries: Dict[str, Dict[str, str]] = {}
    for record in proc.stdout.split(b"\0"):
        if not record:
            continue
        meta, sep, raw_path = record.partition(b"\t")
        if not sep:
            continue
        parts = meta.decode("utf-8", "replace").split(" ")
        if len(parts) != 3:
            continue
        mode, kind, oid = parts
        entries[raw_path.decode("utf-8", "surrogateescape")] = {
            "mode": mode,
            "type": kind,
            "oid": oid,
        }
    return {"ok": True, "entries": entries, "root": rel_dir, "error": None}


def _parse_checksum_inventory(
    text: str,
    expected_count: int = FIXTURE_ENTRY_COUNT,
) -> Dict[str, Any]:
    """Parse SHA256SUMS strictly; empty, malformed, duplicate or escaping
    entries are all evidence failures, never silently skipped."""
    entries: Dict[str, str] = {}
    empty_lines: List[int] = []
    malformed: List[Dict[str, Any]] = []
    duplicate_names: List[str] = []
    escaped_names: List[str] = []
    lines = text.splitlines()
    for lineno, raw in enumerate(lines, 1):
        if not raw.strip():
            empty_lines.append(lineno)
            continue
        digest, sep, name = raw.partition("  ")
        digest = digest.strip()
        name = name.strip()
        if (not sep or not re.fullmatch(r"[0-9a-f]{64}", digest) or not name):
            malformed.append({"line": lineno, "text": raw[:120]})
            continue
        normalized = name
        while normalized.startswith("./"):
            normalized = normalized[2:]
        parts = normalized.split("/")
        if (not normalized or normalized.startswith("/")
                or "\\" in normalized or "//" in normalized
                or any(part in ("", ".", "..") for part in parts)):
            escaped_names.append(name)
            continue
        if normalized in entries:
            duplicate_names.append(normalized)
            continue
        entries[normalized] = digest
    checks = {
        "inventory_non_empty": bool(lines) and not empty_lines,
        "no_malformed_entries": not malformed,
        "entry_count_exact": len(entries) == int(expected_count),
        "no_duplicate_names": not duplicate_names,
        "no_path_escape": not escaped_names,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "entries": entries,
        "entry_count": len(entries),
        "expected_entry_count": int(expected_count),
        "line_count": len(lines),
        "empty_lines": empty_lines,
        "malformed_entries": malformed,
        "duplicate_names": duplicate_names,
        "escaped_names": escaped_names,
    }


def _fixture_checksum_probe(
    fixtures_dir: Path = FIXTURES_DIR,
    checksums_path: Optional[Path] = None,
    expected_count: int = FIXTURE_ENTRY_COUNT,
    git_root: Path = REPO,
) -> Dict[str, Any]:
    """Prove the legacy acceptance fixture set is real, complete and Git-exact.

    This is read-only: it never creates, repairs, downloads or regenerates a
    fixture. A missing/empty/duplicated/escaping inventory, a wrong digest, a
    missing file, a symlink (borrowed bytes) or a file whose bytes are not the
    HEAD blob all make the probe not-ready.
    """
    fixtures_dir = Path(fixtures_dir)
    checksums = (Path(checksums_path) if checksums_path is not None
                 else fixtures_dir / FIXTURE_CHECKSUM_NAME)
    fixtures_rel = _repo_relative(git_root, fixtures_dir)
    checksums_rel = _repo_relative(git_root, checksums)
    tree = _git_tree_entries(git_root, fixtures_rel)
    tree_entries = tree.get("entries") or {}
    problems: List[str] = []

    fixtures_regular = fixtures_dir.is_dir() and not fixtures_dir.is_symlink()
    checksums_regular = checksums.is_file() and not checksums.is_symlink()
    checksums_blob = (checksums.read_bytes() if checksums_regular else b"")
    checksums_sha = _sha256_bytes(checksums_blob) if checksums_regular else None
    checksums_tree = tree_entries.get(checksums_rel) if checksums_rel else None
    checksums_git_exact = bool(
        checksums_regular and checksums_tree
        and checksums_tree.get("oid") == _git_blob_oid(checksums_blob))
    if not fixtures_regular:
        problems.append("fixtures directory is missing, not a directory or is a symlink")
    if not checksums_regular:
        problems.append("fixtures/SHA256SUMS is missing, not a regular file or is a symlink")
    if not checksums_tree:
        problems.append("SHA256SUMS is not tracked in the current Git HEAD tree")
    elif not checksums_git_exact:
        problems.append("SHA256SUMS worktree bytes differ from the Git HEAD blob")

    if checksums_regular:
        try:
            inventory = _parse_checksum_inventory(
                checksums_blob.decode("utf-8"), expected_count)
        except UnicodeDecodeError as exc:
            inventory = {
                "ok": False,
                "checks": {"inventory_utf8": False},
                "entries": {},
                "entry_count": 0,
                "expected_entry_count": int(expected_count),
                "line_count": 0,
                "empty_lines": [],
                "malformed_entries": [{"line": 0, "text": str(exc)}],
                "duplicate_names": [],
                "escaped_names": [],
            }
    else:
        inventory = {
            "ok": False,
            "checks": {"inventory_file_present": False},
            "entries": {},
            "entry_count": 0,
            "expected_entry_count": int(expected_count),
            "line_count": 0,
            "empty_lines": [],
            "malformed_entries": [],
            "duplicate_names": [],
            "escaped_names": [],
        }

    records: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    symlinked: List[str] = []
    outside: List[str] = []
    digest_mismatches: List[str] = []
    git_missing: List[str] = []
    git_mismatches: List[str] = []
    git_symlink_modes: List[str] = []
    for name, digest in inventory.get("entries", {}).items():
        path = fixtures_dir / name
        entry: Dict[str, Any] = {
            "path": str(path),
            "expected_sha256": digest,
            "exists": False,
            "regular_file": False,
            "symlink": path.is_symlink(),
            "sha256": None,
            "bytes": None,
            "digest_matches": False,
            "inside_fixtures_dir": False,
            "git_tracked": False,
            "git_mode": None,
            "git_oid": None,
            "git_exact": False,
        }
        if entry["symlink"]:
            symlinked.append(name)
            problems.append(f"fixture is a symlink (borrowed bytes): {name}")
        elif not path.is_file():
            missing.append(name)
            problems.append(f"fixture is missing or not a file: {name}")
        else:
            entry["exists"] = True
            entry["regular_file"] = True
            data = path.read_bytes()
            entry["bytes"] = len(data)
            entry["sha256"] = _sha256_bytes(data)
            entry["digest_matches"] = entry["sha256"] == digest
            if not entry["digest_matches"]:
                digest_mismatches.append(name)
                problems.append(f"fixture sha256 does not match SHA256SUMS: {name}")
            try:
                resolved_root = fixtures_dir.resolve()
                resolved = path.resolve()
                entry["inside_fixtures_dir"] = resolved_root in resolved.parents
            except OSError:
                entry["inside_fixtures_dir"] = False
            if not entry["inside_fixtures_dir"]:
                outside.append(name)
                problems.append(f"fixture resolves outside the fixtures dir: {name}")
            rel = _repo_relative(git_root, path)
            tree_entry = tree_entries.get(rel) if rel else None
            entry["git_tracked"] = bool(tree_entry)
            if tree_entry:
                entry["git_mode"] = tree_entry.get("mode")
                entry["git_oid"] = tree_entry.get("oid")
                if tree_entry.get("mode") == "120000":
                    git_symlink_modes.append(name)
                    problems.append(f"fixture is a Git symlink entry: {name}")
                entry["git_exact"] = (
                    tree_entry.get("oid") == _git_blob_oid(data))
                if not entry["git_exact"]:
                    git_mismatches.append(name)
                    problems.append(
                        f"fixture bytes differ from the Git HEAD blob: {name}")
            else:
                git_missing.append(name)
                problems.append(f"fixture is not tracked in the Git HEAD tree: {name}")
        records[name] = entry

    complete = bool(records) and len(records) == int(expected_count)
    checks = {
        "fixtures_dir_regular": fixtures_regular,
        "checksums_file_regular": checksums_regular,
        "checksums_git_tracked": bool(checksums_tree),
        "checksums_git_exact": checksums_git_exact,
        "inventory_parsed": inventory.get("ok") is True,
        "entry_count_exact": (
            int(inventory.get("entry_count") or 0) == int(expected_count)),
        "no_duplicate_names": not inventory.get("duplicate_names"),
        "no_path_escape": not inventory.get("escaped_names"),
        "all_fixtures_present": complete and not missing and not symlinked,
        "all_fixture_hashes_match": (
            complete and not missing and not symlinked
            and not digest_mismatches),
        "no_symlinked_fixtures": not symlinked and not git_symlink_modes,
        "all_fixtures_inside_fixtures_dir": complete and not outside,
        "all_fixtures_git_tracked": (
            complete and not missing and not symlinked and not git_missing),
        "all_fixtures_git_exact": (
            complete and not git_mismatches and not git_symlink_modes),
    }
    all_git_exact = bool(records) and all(
        entry["git_exact"] for entry in records.values())
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "fixtures_dir": str(fixtures_dir),
        "fixtures_git_relpath": fixtures_rel,
        "checksums_path": str(checksums),
        "checksums_git_relpath": checksums_rel,
        "checksums_sha256": checksums_sha,
        "checksums_bytes": len(checksums_blob) if checksums_regular else None,
        "checksums_git_blob": (
            checksums_tree.get("oid") if checksums_tree else None),
        "checksums_git_tracked": bool(checksums_tree),
        "checksums_git_exact": checksums_git_exact,
        "entry_count": int(inventory.get("entry_count") or 0),
        "expected_entry_count": int(expected_count),
        "line_count": int(inventory.get("line_count") or 0),
        "empty_lines": inventory.get("empty_lines") or [],
        "malformed_entries": inventory.get("malformed_entries") or [],
        "duplicate_names": inventory.get("duplicate_names") or [],
        "escaped_names": inventory.get("escaped_names") or [],
        "entries": inventory.get("entries") or {},
        "files": records,
        "missing_fixtures": missing,
        "symlinked_fixtures": symlinked,
        "outside_fixtures_dir": outside,
        "digest_mismatches": digest_mismatches,
        "git_missing": git_missing,
        "git_mismatches": git_mismatches,
        "git_symlink_modes": git_symlink_modes,
        "all_files_git_exact": all_git_exact,
        "git_tree_ok": tree.get("ok") is True,
        "git_tree_error": tree.get("error"),
        "problems": problems,
        "generated_or_repaired": False,
        "legacy_framework_inputs": True,
        "uploaded_as_user_document": False,
    }


def _checksum_source_binding(proof: Dict[str, Any]) -> Dict[str, Any]:
    """Bind the checksum input into the source-proof record."""
    return {
        "path": proof.get("checksums_path"),
        "git_relpath": proof.get("checksums_git_relpath"),
        "git_blob": proof.get("checksums_git_blob"),
        "sha256": proof.get("checksums_sha256"),
        "bytes": proof.get("checksums_bytes"),
        "git_tracked": proof.get("checksums_git_tracked") is True,
        "git_exact": proof.get("checksums_git_exact") is True,
        "ok": proof.get("ok") is True,
    }


def _acc_metadata_probe(
    acc_dir: Path = ACC_DIR,
    git_root: Path = REPO,
) -> Dict[str, Any]:
    """Read-only proof that build_world can write <ACC>/venv_freeze.txt.

    ``run_isolated.build_world`` writes that file but never creates <ACC>.
    The file itself is GENERATED output, not a tracked fixture, so a missing
    directory must fail here rather than be papered over with a committed
    venv_freeze.txt. This helper never mkdirs or writes.
    """
    acc_dir = Path(acc_dir)
    exists = acc_dir.is_dir()
    writable = bool(exists and os.access(acc_dir, os.W_OK))
    venv_freeze = acc_dir / "venv_freeze.txt"
    rel = _repo_relative(git_root, venv_freeze)
    tracked = _git_path_tracked(rel, git_root) if rel else False
    checks = {
        "acc_dir_exists": exists,
        "acc_dir_writable": writable,
        "venv_freeze_not_tracked": not tracked,
    }
    problems: List[str] = []
    if not exists:
        problems.append(
            "acceptance metadata directory is missing; build_world writes "
            "ACC/venv_freeze.txt without creating it")
    elif not writable:
        problems.append(
            "acceptance metadata directory is not writable; build_world "
            "cannot write ACC/venv_freeze.txt")
    if tracked:
        problems.append(
            "ACC/venv_freeze.txt is tracked in Git, but it is generated "
            "output, not a fixture; remove it and make ACC writable")
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "path": str(acc_dir),
        "exists": exists,
        "writable": writable,
        "venv_freeze_path": str(venv_freeze),
        "venv_freeze_tracked": tracked,
        "venv_freeze_is_generated_output": True,
        "mkdir_in_preflight": False,
        "write_in_preflight": False,
        "problems": problems,
    }


def _launcher_paths_probe() -> Dict[str, Any]:
    files = {path: (REPO / path).is_file() for path in LAUNCHER_FILES}
    acc = _acc_metadata_probe()
    checksums_present = (
        FIXTURE_CHECKSUMS.is_file()
        and not FIXTURE_CHECKSUMS.is_symlink())
    worlds_present = WORLDS_ROOT.exists()
    worlds_resolves = bool(
        worlds_present
        and (not WORLDS_ROOT.is_symlink() or WORLDS_ROOT.resolve().is_dir()))
    return {
        "ok": (all(files.values()) and acc["ok"] and checksums_present
               and worlds_resolves),
        "files": files,
        "acc_metadata": acc,
        "acc_dir": str(ACC_DIR),
        "acc_dir_writable": acc["writable"],
        "fixtures_checksums_present": checksums_present,
        "fixtures_checksums_path": str(FIXTURE_CHECKSUMS),
        "worlds_root": str(WORLDS_ROOT),
        "worlds_root_exists": worlds_present,
        "worlds_root_is_symlink": WORLDS_ROOT.is_symlink(),
        "worlds_root_resolves": worlds_resolves,
    }


def _prebuild_support_probe() -> Dict[str, Any]:
    """All launcher/ACC/fixture prerequisites, used by preflight and again
    immediately before build_world. Never creates or repairs anything."""
    launcher = _launcher_paths_probe()
    fixture_inventory = _fixture_checksum_probe()
    acc = launcher.get("acc_metadata") or {}
    checks = {
        "launcher_files_present": (
            bool(launcher.get("files"))
            and all(launcher.get("files", {}).values())),
        "acc_metadata_dir_exists": acc.get("exists") is True,
        "acc_metadata_dir_writable": acc.get("writable") is True,
        "acc_venv_freeze_not_tracked": (
            acc.get("venv_freeze_tracked") is False),
        "fixtures_checksums_present": (
            launcher.get("fixtures_checksums_present") is True),
        "worlds_root_resolves": launcher.get("worlds_root_resolves") is True,
        "legacy_fixture_inventory_verified": (
            fixture_inventory.get("ok") is True),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "launcher": launcher,
        "fixture_inventory": fixture_inventory,
    }


def _heavy_probe(world: Path) -> Dict[str, Any]:
    try:
        disk = R._check_disk_before_world(world).as_dict()
    except Exception as exc:  # noqa: BLE001 - report, do not crash preflight
        disk = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "required_bytes": 0,
            "shortfall_bytes": None,
        }
    required = int(disk.get("required_bytes") or 0)
    return {
        "disk": disk,
        "required_bytes": required,
        "heavy_threshold_bytes": HEAVY_THRESHOLD_BYTES,
        "requires_root_heavy_approval": required >= HEAVY_THRESHOLD_BYTES,
        "approved": False,
    }


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------
def _run_preflight(args: argparse.Namespace) -> int:
    try:
        ctx = D3._require_scratch_env()
        source = _source_proof(args.expect_source_sha)
        if args.expect_source_sha and not source.get("expected_sha_ok"):
            raise PreflightError(
                f"HEAD {source.get('head')} does not match "
                f"--expect-source-sha {args.expect_source_sha}")
        if not source.get("tracked_tree_clean"):
            raise PreflightError(
                "tracked worktree is dirty; a browser episode must bind to a "
                "frozen commit, not an in-flight tree")
        if not source.get("per_file", {}).get("ok"):
            raise PreflightError("per-file Git source proof failed")
        retained = _retained_evidence_probe(
            getattr(args, "api_evidence", None),
            getattr(args, "api_evidence_ref", "HEAD"))
        if not retained.get("ok"):
            raise PreflightError(
                "committed API packet/source does not qualify reuse "
                f"without review: {retained}")
        profile = _profile_probe()
        if not profile.get("ok"):
            raise PreflightError(
                f"core Documents profile is not enabled as expected: {profile}")
        static = _static_source_contract_probe()
        if not static.get("ok"):
            raise PreflightError(
                f"current Documents/export source does not match the frozen "
                f"contract: {static.get('checks')}")

        world_name = _world_name_for(source, args.world)
        world = _world_path(world_name)
        try:
            under_root = world.parent.resolve() == WORLDS_ROOT.resolve()
        except Exception:
            under_root = False
        if not under_root:
            raise PreflightError(
                f"--world {world_name!r} resolves outside the configured "
                f"worlds root {WORLDS_ROOT}")
        target = Path(args.report) if args.report else (
            Path(args.out) / "preflight.json" if args.out else None)
        if target is None:
            raise PreflightError("--preflight needs --report or --out")
        output = _output_target_probe(
            target, require_empty=(args.report is None))
        if not output["ok"]:
            raise PreflightError(f"preflight report output refused: {output}")

        deps = D3._dependency_probe()
        cache = _effective_cache_probe()
        fastembed_runtime = _fastembed_runtime_probe()
        support = _prebuild_support_probe()
        launcher = support["launcher"]
        fixture_inventory = support["fixture_inventory"]
        source["fixture_checksum"] = _checksum_source_binding(
            fixture_inventory)
        storage = _storage_probe()
        heavy = _heavy_probe(world)
        fixture_filename, fixture_text, fixture_tail = _fixture_document(
            "preflight")
        fixture = {
            "filename": fixture_filename,
            "chars": len(fixture_text),
            "utf8_bytes": len(fixture_text.encode("utf-8")),
            "sha256": _sha256_text(fixture_text),
            "tail_marker": fixture_tail,
            "over_20k": len(fixture_text) > 20000,
            "tail_is_last_content": fixture_text.rstrip("\n").endswith(
                fixture_tail),
            "synthetic_user_file": True,
            "ok": (
                len(fixture_text) > 20000
                and fixture_text.count(fixture_tail) == 1
                and fixture_text.rstrip("\n").endswith(fixture_tail)),
        }
        if not fixture["ok"]:
            raise PreflightError(f"generated fixture proof failed: {fixture}")

        ports = {
            str(p): D3._port_free(p)
            for p in (args.backend_port, args.frontend_port)
        }
        forbidden_port_used = [
            p for p in (args.backend_port, args.frontend_port)
            if p in D3.FORBIDDEN_PORTS
        ]
        if forbidden_port_used:
            raise PreflightError(
                f"refusing known live ports: {forbidden_port_used}")

        checks = {
            "scratch_environment": ctx["scratch_ok"] is True,
            "source_head_recorded": bool(source.get("head")),
            "source_expected_sha_ok": source.get("expected_sha_ok") is True,
            "tracked_tree_clean": source.get("tracked_tree_clean") is True,
            "backend_tree_clean": source.get("backend_tree_clean") is True,
            "per_file_git_source_proof": (
                source.get("per_file", {}).get("ok") is True),
            "committed_api_packet_and_current_source_match": (
                retained.get("ok") is True),
            "core_documents_profile_enabled": profile.get("ok") is True,
            "search_deferred": profile.get("search_enabled") is False,
            "frozen_source_contract_present": static.get("ok") is True,
            "launcher_paths_present": (
                support["checks"]["launcher_files_present"]),
            "acc_metadata_dir_writable": (
                support["checks"]["acc_metadata_dir_writable"]),
            "acc_venv_freeze_not_tracked": (
                support["checks"]["acc_venv_freeze_not_tracked"]),
            "legacy_fixture_set_55_verified": (
                support["checks"]["legacy_fixture_inventory_verified"]),
            "fresh_world_name": (
                world_name.startswith(WORLD_PREFIX)
                and not world.exists() and under_root),
            "backend_frontend_ports_free": all(ports.values()),
            "backend_frontend_ports_not_live": not forbidden_port_used,
            "output_allowed": output["ok"] is True,
            "storage_guard_configured": storage.get("ok") is True,
            "test_venv_present": deps.get("venv314_python") is True,
            "frontend_node_modules_present": (
                deps.get("frontend_node_modules") is True),
            "node_present": bool(deps.get("node")),
            "chrome_present": deps.get("chrome_app") is True,
            "fastembed_cache_complete": cache.get("ok") is True,
            "fastembed_runtime_source_present": (
                fastembed_runtime.get("ok") is True),
            "disk_space_ok": heavy["disk"].get("ok") is True,
            "fixture_over_20k_with_tail": fixture["ok"] is True,
        }
        checkset = _checkset(checks) if all(checks.values()) else checks
        warnings: List[str] = []
        for name, present in deps["modules"].items():
            if not present and name in ("httpx", "playwright", "sqlalchemy",
                                        "fastapi"):
                warnings.append(f"python module missing: {name}")
        if not deps.get("venv314_python"):
            warnings.append(
                "backend/venv314/bin/python is absent in this worktree; "
                "--execute needs a prepared capture worktree")
        if not deps.get("frontend_node_modules"):
            warnings.append(
                "frontend-nextjs/node_modules is absent; no install is permitted")
        if not storage.get("ok"):
            warnings.append(
                "worlds storage guard is not ready: "
                f"{storage.get('problems') or storage.get('error')}")
        if not support["checks"]["acc_metadata_dir_writable"]:
            warnings.append(
                "acceptance metadata dir is missing/unwritable; build_world "
                "writes ACC/venv_freeze.txt without creating ACC: "
                f"{launcher['acc_metadata'].get('problems')}")
        if not support["checks"]["legacy_fixture_inventory_verified"]:
            warnings.append(
                "legacy fixture inventory is not Git-exact/complete: "
                f"{fixture_inventory.get('problems')}")
        if not cache.get("ok"):
            warnings.append(
                f"fastembed cache prerequisite missing: {cache.get('problems')}")
        if not fastembed_runtime.get("ok"):
            warnings.append(
                f"fastembed runtime prerequisite missing: "
                f"{fastembed_runtime.get('error') or fastembed_runtime.get('checks')}")
        if world.exists():
            warnings.append(
                f"world {world_name!r} already exists; --execute refuses one")
        if not all(ports.values()):
            warnings.append(f"port not free: {ports}")
        if not heavy["disk"].get("ok"):
            warnings.append(
                f"disk estimate/space check failed: {heavy['disk']}")
        if heavy["requires_root_heavy_approval"]:
            warnings.append(
                "world build estimate is >=4GiB; --execute requires "
                "--root-heavy-approved and root ownership")
        report = {
            "kind": "browser_document_export_ui_preflight",
            "status": "preparation-only",
            "generated_at": _now(),
            "ok": all(checks.values()),
            "checks": checkset,
            "labels": LABELS,
            "driver": {
                "path": str(Path(__file__).resolve()),
                "sha256": _sha256_file(Path(__file__).resolve()),
            },
            "source": source,
            "retained_evidence": retained,
            "profile": profile,
            "static_contract": static,
            "fixture": fixture,
            "launcher": launcher,
            "acc_metadata": launcher["acc_metadata"],
            "fixture_inventory": fixture_inventory,
            "prebuild_support": support["checks"],
            "environment": ctx,
            "dependencies": deps,
            "ports": ports,
            "world": {
                "name": world_name,
                "path": str(world),
                "exists": world.exists(),
                "under_worlds_root": under_root,
                "required_prefix": WORLD_PREFIX,
                "required_fresh": True,
            },
            "output": output,
            "storage": storage,
            "heavy": heavy,
            "fastembed_cache": cache,
            "fastembed_runtime": fastembed_runtime,
            "warnings": warnings,
            "not_exercised": [
                "world build / storage-guard acceptance",
                "backend or frontend launch",
                "Playwright login/onboarding or ordinary upload",
                "FastEmbed/ONNX load or any embedding computation",
                "SQL/LanceDB durable readback or browser download",
                "any model/provider/network/send/spend/install/deploy action",
            ],
            "remaining_inputs": [
                "prepared capture worktree with backend/venv314 and "
                "frontend-nextjs/node_modules (this prep-only worktree may lack "
                "backend/venv314)",
                "writable docs/architecture/orchestration_migration/acceptance "
                "parent and the exact 55 Git-tracked fixtures "
                "(git sparse-checkout add .../acceptance/fixtures)",
                "world storage guard ready (local or drive-backed per config)",
                "complete existing FastEmbed cache under TMPDIR/fastembed_cache",
                "Google Chrome.app and node on PATH",
                "unique fresh --world starting document_export_ui_",
                "free --backend-port and --frontend-port",
                "admin password source: --admin-password-file (0600), "
                "ATOM_PREVIEW_PASSWORD, world bootstrap file, or "
                "--provision-admin-password",
                "explicit --execute --expect-source-sha; this preparation does "
                "not run it",
            ],
            "exact_preparation_command": (
                "TESTING=1 DATABASE_URL=sqlite:///<fresh>/atom.db "
                "ATOM_DATA_DIR=<fresh>/data ATOM_OFFICE_DIR=<fresh>/office "
                "ATOM_PRODUCT_PROFILE=core "
                "python3 scripts/acceptance/browser_document_export_ui.py "
                "--preflight --expect-source-sha <frozen-sha> --out <report-dir>"),
            "exact_execute_command": (
                "TESTING=1 DATABASE_URL=sqlite:///<scratch>/preflight.db "
                "ATOM_DATA_DIR=<scratch>/data ATOM_OFFICE_DIR=<scratch>/office "
                "ATOM_PRODUCT_PROFILE=core "
                "python3 scripts/acceptance/browser_document_export_ui.py "
                "--execute --expect-source-sha <frozen-sha> "
                "--world document_export_ui_<sha10> --backend-port 8047 "
                "--frontend-port 3147 --out <evidence-dir> "
                "--provision-admin-password[ --root-heavy-approved]"),
        }
        target = target.resolve()
        _write_json(target, report)
        print(f"[preflight] ok={report['ok']} report={target}")
        print(f"[preflight] source={source.get('head')} "
              f"files={len(source.get('per_file', {}).get('files', {}))} "
              f"retained={retained.get('ok')} profile={profile.get('ok')}")
        print(f"[preflight] cache={cache.get('ok')} "
              f"runtime={fastembed_runtime.get('ok')} "
              f"storage={storage.get('ok')} "
              f"heavy={heavy['required_bytes']}B")
        print(f"[preflight] acc={support['checks']['acc_metadata_dir_writable']} "
              f"fixtures={fixture_inventory.get('entry_count')}/"
              f"{fixture_inventory.get('expected_entry_count')} "
              f"git_exact={fixture_inventory.get('all_files_git_exact')} "
              f"launcher={sum(1 for v in launcher['files'].values() if v)}/"
              f"{len(launcher['files'])}")
        for warning in warnings:
            print(f"[preflight] warning: {warning}")
        return 0 if report["ok"] else 1
    except PreflightError as exc:
        print(f"[preflight] REFUSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - preparation must fail loud
        print(f"[preflight] ERROR: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 3


# ---------------------------------------------------------------------------
# execute helpers
# ---------------------------------------------------------------------------
def _execute_ready(args: argparse.Namespace) -> Dict[str, Any]:
    deps = D3._dependency_probe()
    missing = [
        name for name, present in deps["modules"].items()
        if name in ("httpx", "playwright") and not present
    ]
    if missing:
        raise DriverError(f"missing python modules for --execute: {missing}")
    if not deps["node"]:
        raise DriverError("node is not on PATH")
    if not deps["chrome_app"]:
        raise DriverError(
            "Google Chrome.app not found; the driver never installs a browser")
    if not deps["venv314_python"]:
        raise DriverError(
            "backend/venv314/bin/python is absent; run --execute from the "
            "prepared frozen capture worktree, not the prep-only worktree")
    if not deps["frontend_node_modules"]:
        raise DriverError(
            "frontend-nextjs/node_modules is absent; no npm install is "
            "permitted")
    ports = {p: D3._port_free(p) for p in
             (args.backend_port, args.frontend_port)}
    busy = [p for p, free in ports.items() if not free]
    if busy:
        raise DriverError(f"ports already in use: {busy}")
    return {"dependencies": deps, "ports": {str(k): v for k, v in ports.items()}}


def _build_world(world: Path, source_sha: str,
                 heavy_approved: bool) -> Dict[str, Any]:
    from core.world_storage_guard import require_storage_ready
    if os.environ.get("ATOM_WORLD_STORAGE_BYPASS"):
        raise DriverError(
            "ATOM_WORLD_STORAGE_BYPASS is set; this harness never bypasses "
            "the storage guard")
    heavy = _heavy_probe(world)
    if not heavy["disk"].get("ok"):
        raise DriverError(
            "insufficient disk for the world build: "
            f"{heavy['disk'].get('shortfall_bytes')} bytes short")
    if heavy["requires_root_heavy_approval"] and not heavy_approved:
        raise DriverError(
            "world build estimate is >=4GiB; root must pass "
            "--root-heavy-approved for this explicit episode")
    require_storage_ready()
    if world.exists():
        raise DriverError(
            f"world {world.name!r} already exists; this driver requires a "
            "unique fresh world and never deletes or rebuilds one")
    # build_world writes <ACC>/venv_freeze.txt and reads every legacy fixture
    # named by SHA256SUMS, so re-prove both AFTER the storage guard and BEFORE
    # the builder/any world mkdir. A missing ACC parent must fail here, not
    # after a database has been allocated inside a half-built world.
    support = _prebuild_support_probe()
    if not support["ok"]:
        raise DriverError(
            "launcher/ACC/fixture prerequisites failed before build_world: "
            f"{support['checks']}")
    R.WORKTREE = REPO
    R.build_world.snapshot_working_tree = True
    R.build_world.full_dev_db = False
    R.build_world(world, refreeze_db=True)
    manifest = world / "MANIFEST.json"
    fixture = world / "fixture" / "atom.db"
    if not manifest.exists() or not fixture.exists():
        raise DriverError("world build did not produce MANIFEST.json/fixture/atom.db")
    manifest_doc = _read_json(manifest)
    pre = R.preflight(world)
    code_manifest = _read_json(world / "code_manifest.json")
    export_tree = R._tree_manifest(world / "code")
    if pre.get("source_revision") != source_sha:
        raise DriverError(
            "harness preflight source revision does not match the frozen "
            f"source: {pre.get('source_revision')!r} != {source_sha!r}")
    if export_tree != code_manifest:
        raise DriverError(
            "exported code tree does not match code_manifest.json; the files "
            "that would run are not the frozen snapshot")
    marker = {
        "schema": "atom-document-stored-export-ui-world-1",
        "kind": "ordinary_stored_text_export",
        "source_sha": source_sha,
        "world": world.name,
        "fixture": LABELS["fixture"],
        "account": LABELS["account"],
        "embedding": LABELS["embedding"],
        "not_original_binary": True,
        "created_at": _now(),
    }
    marker_path = world / "DOCUMENT_EXPORT_UI_EPISODE.json"
    _write_json(marker_path, marker)
    readback = _read_json(marker_path)
    return {
        "world": str(world),
        "disk_preflight": heavy["disk"],
        "heavy": heavy,
        "launcher": support["launcher"],
        "acc_metadata": support["launcher"]["acc_metadata"],
        "fixture_inventory": support["fixture_inventory"],
        "prebuild_support": support["checks"],
        "manifest_path": str(manifest),
        "fixture_path": str(fixture),
        "preflight": pre,
        "manifest_doc": manifest_doc,
        "code_manifest": code_manifest,
        "export_tree": export_tree,
        "source_revision": manifest_doc.get("source_revision"),
        "code_snapshot_sha256": manifest_doc.get("code_snapshot_sha256"),
        "code_archive_sha256": manifest_doc.get("code_archive_sha256"),
        "marker_path": str(marker_path),
        "marker": readback,
    }


def _frontend_export_proof(world: Path) -> Dict[str, Any]:
    root = world / "frontend_snapshot"
    files: Dict[str, Any] = {}
    ok = True
    for path in FRONTEND_SOURCE_FILES:
        rel = path.split("frontend-nextjs/", 1)[1]
        exported = root / rel
        git_blob = _git_bytes(path)
        actual = exported.read_bytes() if exported.is_file() else b""
        entry = {
            "path": path,
            "snapshot_path": str(exported),
            "git_sha256": _sha256_bytes(git_blob),
            "snapshot_sha256": _sha256_bytes(actual),
            "matches": bool(actual) and actual == git_blob,
        }
        ok = ok and entry["matches"]
        files[path] = entry
    return {"ok": ok, "files": files}


def _api_login_as(port: int, email: str,
                  password: str) -> Tuple[str, Dict[str, Any]]:
    with D3._api_client(port) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": email, "password": password})
    if response.status_code != 200:
        raise DriverError(
            f"login failed for {email} ({response.status_code}): "
            f"{D3._safe_error_body(response)}")
    body = response.json()
    if body.get("two_factor_required"):
        raise DriverError(f"{email} unexpectedly requires 2FA")
    token = str(body.get("access_token") or "")
    if not token:
        raise DriverError(f"{email} login returned no access_token")
    return token, {"status": response.status_code, "token_present": True}


def _actor_scope(db_path: Path, public_user: Dict[str, Any]) -> Dict[str, Any]:
    """Bind public identity to the exact scratch SQL actor (read-only)."""
    from types import SimpleNamespace
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    user_id = str(public_user.get("id") or "")
    rows = D3._db_rows(
        db_path,
        "SELECT id, workspace_id, tenant_id, role, status FROM users WHERE id=?",
        (user_id,))
    if not user_id or len(rows) != 1:
        raise DriverError("public authenticated identity has no exact SQL actor")
    row = rows[0]
    if public_user.get("workspace_id") != row[1]:
        raise DriverError("public authenticated workspace disagrees with SQL")
    actor = SimpleNamespace(workspace_id=row[1], tenant_id=row[2])
    return {
        "actor_id": user_id,
        "public_workspace_id": public_user.get("workspace_id"),
        "raw_workspace_id": row[1],
        "raw_tenant_id": row[2],
        "role": row[3],
        "status": row[4],
        "route_workspace_id": row[1],
        "effective_workspace_id": resolve_workspace_id(actor),
        "effective_tenant_id": resolve_tenant_id(actor),
        "source": (
            "exact public identity + read-only scratch SQL + existing "
            "personal_scope resolvers"),
    }


def _complete_onboarding_if_present(page: Any, api: Any) -> Dict[str, Any]:
    """Wait for the authoritative status, then finish the visible wizard."""
    def status() -> bool:
        response = api.get("/api/onboarding/status")
        if response.status_code != 200:
            raise DriverError("onboarding status unavailable")
        body = response.json()
        data = body.get("data") or body
        value = data.get("onboarding_completed")
        if not isinstance(value, bool):
            raise DriverError("onboarding status missing completion evidence")
        return value

    out = {"wizard_seen": False, "dismissed": False,
           "completion_durable": False}
    welcome = page.get_by_role("heading", name="Welcome to Atom", exact=True)
    if status():
        welcome.wait_for(state="hidden", timeout=30000)
        out["completion_durable"] = True
        return out
    welcome.wait_for(state="visible", timeout=30000)
    out["wizard_seen"] = True
    for _ in range(3):
        page.get_by_role("button", name="Next", exact=True).click()
    page.get_by_role("button", name="Start Automating", exact=True).click()
    welcome.wait_for(state="hidden", timeout=30000)
    deadline = time.monotonic() + 30
    while not status():
        if time.monotonic() >= deadline:
            raise DriverError("onboarding UI closed without durable completion")
        time.sleep(0.2)
    out.update(dismissed=True, completion_durable=True)
    return out


def _open_documents(page: Any) -> None:
    link = page.locator('a[href="/documents"]').first
    link.wait_for(state="visible", timeout=120000)
    link.click()
    page.wait_for_url(
        lambda url: D3._path_of(url) == "/documents", timeout=120000)
    # Native upload inputs are intentionally hidden; the visible label opens them.
    # Playwright set_input_files requires an attached input, not visible CSS.
    page.locator("#file-upload").wait_for(state="attached", timeout=120000)
    page.get_by_role("heading", name="Knowledge Base",
                     exact=True).wait_for(state="visible", timeout=120000)


def _sql_document(db_path: Path, doc_id: str) -> Dict[str, Any]:
    rows = D3._db_rows(
        db_path,
        "SELECT id, workspace_id, tenant_id, integration_id, external_id, "
        "file_name, file_type, source_content_hash, freshness_status, "
        "file_size_bytes FROM ingested_documents WHERE id=?",
        (doc_id,))
    if not rows:
        return {"found": False}
    row = rows[0]
    return {
        "found": True,
        "id": row[0],
        "workspace_id": row[1],
        "tenant_id": row[2],
        "integration_id": row[3],
        "external_id": row[4],
        "file_name": row[5],
        "file_type": row[6],
        "source_content_hash": row[7],
        "freshness_status": row[8],
        "file_size_bytes": row[9],
    }


def _pid_alive(pid: int) -> bool:
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "pid="],
            capture_output=True, text=True, timeout=10)
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except Exception:
        return False


def _ps_fields(pid: int) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "pid=,ppid=,lstart=,command="],
            capture_output=True, text=True, timeout=10)
        line = proc.stdout.strip()
        return {
            "alive": proc.returncode == 0 and bool(line),
            "line": line[:500],
        }
    except Exception as exc:  # noqa: BLE001
        return {"alive": False, "error": f"{type(exc).__name__}: {exc}"}


def _process_env_probe(pid: int, keys: Tuple[str, ...]) -> Dict[str, Any]:
    """Read only selected environment keys from the actual process."""
    try:
        proc = subprocess.run(
            ["ps", "eww", "-p", str(pid)],
            capture_output=True, text=True, timeout=15)
        text = proc.stdout
        values: Dict[str, Optional[str]] = {}
        for key in keys:
            match = re.search(
                rf"(?:^|\s){re.escape(key)}=([^\s]+)", text)
            values[key] = match.group(1) if match else None
        return {
            "ok": proc.returncode == 0 and bool(text.strip()),
            "pid": pid,
            "values": values,
            "source": "ps eww selected keys only",
            "raw_env_recorded": False,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "pid": pid,
            "values": {key: None for key in keys},
            "error": f"{type(exc).__name__}: {exc}",
            "raw_env_recorded": False,
        }


def _ast_constant(node: Any) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _ast_call_name(node: Any) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _runtime_defaults_probe(
    world: Path,
    descriptor: Dict[str, Any],
    live_profile: Dict[str, Any],
) -> Dict[str, Any]:
    """Diagnostic source/profile facts; NEVER positive runtime proof.

    Source text mentioning defaults does not prove the running process has the
    flag off. Only the child process's actual environment is authoritative.
    This function always reports ``ok=False`` and is never a positive check.
    """
    profile_path = Path(world) / "code" / "backend" / "core" / "product_profile.py"
    app_path = Path(world) / "code" / "backend" / "main_api_app.py"
    problems: List[str] = []
    source_files: Dict[str, Any] = {}
    for name, path in (
            ("product_profile", profile_path),
            ("main_api_app", app_path)):
        try:
            source_files[name] = {
                "path": str(path),
                "sha256": _sha256_file(path),
            }
        except OSError as exc:
            problems.append(
                f"{name}: {type(exc).__name__}: {exc}")
            source_files[name] = {"path": str(path), "sha256": None}
    env = descriptor.get("effective_env") or {}
    live_body = (live_profile or {}).get("body") or {}
    return {
        "ok": False,
        "diagnostic_only": True,
        "positive_authority": False,
        "source_files": source_files,
        "live_profile": {
            "status": (live_profile or {}).get("status"),
            "profile": live_body.get("profile"),
        },
        "launch_env": {
            "ATOM_AGENT_EVOLUTION_ENABLED": env.get(
                "ATOM_AGENT_EVOLUTION_ENABLED"),
            "ATOM_PRODUCT_PROFILE": env.get("ATOM_PRODUCT_PROFILE"),
        },
        "evidence_note": (
            "Source/profile shape is diagnostic only. The actual child process "
            "env (ATOM_AGENT_EVOLUTION_ENABLED, ENABLE_SCHEDULER, "
            "ENABLE_INGESTION_SYNC all false) is the only positive authority."),
        "problems": problems,
    }


def _ast_expectation(node: Any) -> Dict[str, Any]:
    """Describe a provider field default: literal, env-with-default, unknown."""
    if isinstance(node, ast.Call) and _ast_call_name(node.func) in {
            "getenv", "os.getenv"}:
        args = list(node.args)
        env_var = _ast_constant(args[0]) if args else None
        default = _ast_constant(args[1]) if len(args) > 1 else None
        if isinstance(env_var, str) and (
                default is None or isinstance(default, str)):
            return {
                "kind": "env_default",
                "env_var": env_var,
                "default": default,
            }
    if isinstance(node, ast.Constant):
        return {"kind": "literal", "value": node.value}
    return {"kind": "unknown"}


def _expectation_matches(value: Any, expectation: Any) -> bool:
    if not isinstance(expectation, dict):
        return value == expectation
    kind = expectation.get("kind")
    if kind == "literal":
        return value == expectation.get("value")
    if kind == "env_default":
        # The exported source itself resolves this field from the environment;
        # accept the declared default or an environment-provided string.
        return (
            value == expectation.get("default")
            or isinstance(value, str))
    return False


def _byok_source_contract(source_text: str) -> Dict[str, Any]:
    """Read the exported BYOK manager's default-provider contract."""
    problems: List[str] = []
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        return {
            "ok": False,
            "checks": {"source_parse_ok": False},
            "provider_defaults": {},
            "allowed_fields": [],
            "problems": [f"{type(exc).__name__}: {exc}"],
        }
    manager = next((
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BYOKManager"), None)
    funcs: Dict[str, ast.FunctionDef] = {}
    if manager is not None:
        funcs = {
            node.name: node for node in manager.body
            if isinstance(node, ast.FunctionDef)
        }
    init_func = funcs.get("_initialize_default_providers")
    to_dict_func = funcs.get("_provider_to_dict")
    provider_defaults: Dict[str, Dict[str, Any]] = {}
    bad_defaults = 0
    if init_func is not None:
        for node in ast.walk(init_func):
            if not (isinstance(node, ast.Call)
                    and _ast_call_name(node.func) == "AIProviderConfig"):
                continue
            values = {kw.arg: _ast_constant(kw.value) for kw in node.keywords}
            expectations = {
                kw.arg: _ast_expectation(kw.value) for kw in node.keywords}
            provider_id = values.get("id")
            env_var = values.get("api_key_env_var")
            if not isinstance(provider_id, str) or not isinstance(env_var, str):
                bad_defaults += 1
                continue

            def _expect(field: str) -> Dict[str, Any]:
                if field in expectations:
                    return expectations[field]
                return {"kind": "literal", "value": None}

            provider_defaults[provider_id] = {
                "name": _expect("name"),
                "api_key_env_var": env_var,
                "base_url": _expect("base_url"),
                "model": _expect("model"),
            }
    allowed_fields: List[str] = []
    if to_dict_func is not None:
        for node in ast.walk(to_dict_func):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                allowed_fields = sorted({
                    key for key in (
                        _ast_constant(k) for k in node.value.keys)
                    if isinstance(key, str)
                })
                break
    checks = {
        "source_parse_ok": True,
        "manager_found": manager is not None,
        "defaults_function_found": init_func is not None,
        "defaults_have_literal_identity": (
            bool(provider_defaults) and bad_defaults == 0),
        "provider_to_dict_found": to_dict_func is not None,
        "allowed_fields_include_identity": (
            {"id", "api_key_env_var"}.issubset(set(allowed_fields))),
    }
    if manager is None:
        problems.append("BYOKManager class not found")
    if init_func is None:
        problems.append("_initialize_default_providers not found")
    if to_dict_func is None:
        problems.append("_provider_to_dict not found")
    if bad_defaults:
        problems.append(f"{bad_defaults} default provider(s) lack literal id/env")
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "provider_defaults": provider_defaults,
        "allowed_fields": allowed_fields,
        "problems": problems,
    }


def _byok_config_content_probe(
    config: Any,
    source_contract: Dict[str, Any],
) -> Dict[str, Any]:
    """Strict allow-list proof that the config is the generated default catalog."""
    problems: List[str] = []
    expected = source_contract.get("provider_defaults") or {}
    allowed = set(source_contract.get("allowed_fields") or [])
    top_level_exact = (
        isinstance(config, dict) and sorted(config.keys()) == ["providers"])
    providers = config.get("providers") if isinstance(config, dict) else None
    providers_is_list = isinstance(providers, list)
    entries = providers if isinstance(providers, list) else []
    ids: List[str] = []
    field_violations: List[str] = []
    identity_mismatches: List[str] = []
    credential_fields: List[str] = []
    type_violations: List[str] = []
    env_derived_fields: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            type_violations.append("provider entry is not an object")
            continue
        keys = set(entry.keys())
        if allowed and keys != allowed:
            field_violations.append(
                f"fields differ: {sorted(keys ^ allowed)[:5]}")
        for key in keys:
            if (re.search(
                    r"(api_key|secret|token|password|credential|ciphertext|"
                    r"encrypted_key)$", key, flags=re.I)
                    and key not in {"api_key_env_var", "cost_per_token"}):
                credential_fields.append(key)
        provider_id = entry.get("id")
        if not isinstance(provider_id, str) or not provider_id:
            type_violations.append("provider id is not a non-empty string")
            continue
        ids.append(provider_id)
        expected_entry = expected.get(provider_id)
        if expected_entry is None:
            identity_mismatches.append(f"unexpected provider {provider_id}")
        else:
            for field in ("name", "base_url", "model"):
                if not _expectation_matches(
                        entry.get(field), expected_entry.get(field)):
                    identity_mismatches.append(f"{provider_id}.{field}")
                expectation = expected_entry.get(field)
                if (isinstance(expectation, dict)
                        and expectation.get("kind") == "env_default"):
                    env_derived_fields.append(f"{provider_id}.{field}")
            if entry.get("api_key_env_var") != expected_entry.get(
                    "api_key_env_var"):
                identity_mismatches.append(
                    f"{provider_id}.api_key_env_var")
        for field in ("name", "description", "api_key_env_var"):
            if not isinstance(entry.get(field), str):
                type_violations.append(f"{provider_id}.{field} is not a string")
        for field in (
                "supports_vision", "supports_tools", "supports_cache",
                "supports_structured_output", "is_active",
                "requires_encryption"):
            if not isinstance(entry.get(field), bool):
                type_violations.append(f"{provider_id}.{field} is not a bool")
        for field in ("cost_per_token", "quality_score"):
            if not isinstance(entry.get(field), (int, float)) or isinstance(
                    entry.get(field), bool):
                type_violations.append(
                    f"{provider_id}.{field} is not a number")
        for field in (
                "reasoning_level", "max_requests_per_minute",
                "rate_limit_window"):
            if not isinstance(entry.get(field), int) or isinstance(
                    entry.get(field), bool):
                type_violations.append(f"{provider_id}.{field} is not an int")
        tasks = entry.get("supported_tasks")
        if not isinstance(tasks, list) or not all(
                isinstance(task, str) for task in tasks):
            type_violations.append(
                f"{provider_id}.supported_tasks is not a string list")
        env_var = entry.get("api_key_env_var")
        if not isinstance(env_var, str) or not re.fullmatch(
                r"[A-Z][A-Z0-9_]*", env_var):
            identity_mismatches.append(
                f"{provider_id}.api_key_env_var is not an env name")
    checks = {
        "top_level_exact": top_level_exact,
        "providers_is_list": providers_is_list,
        "provider_count_matches_source": (
            len(entries) == len(expected) and bool(expected)),
        "provider_ids_exact": (
            bool(expected) and len(ids) == len(set(ids))
            and set(ids) == set(expected)),
        "provider_fields_exact": bool(allowed) and not field_violations,
        "no_credential_value_fields": not credential_fields,
        "provider_types_valid": not type_violations,
        "default_identity_matches_source": not identity_mismatches,
    }
    problems.extend(field_violations[:5])
    problems.extend(identity_mismatches[:5])
    problems.extend(credential_fields[:5])
    problems.extend(type_violations[:5])
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "provider_count": len(entries),
        "provider_ids": sorted(ids),
        "field_names": sorted(allowed),
        "env_derived_fields": sorted(env_derived_fields),
        "problems": problems,
    }


def _byok_keys_content_probe(keys_doc: Any) -> Dict[str, Any]:
    checks = {
        "keys_top_level_object": isinstance(keys_doc, dict),
        "keys_top_level_exact": (
            isinstance(keys_doc, dict)
            and sorted(keys_doc.keys()) == ["keys"]),
        "key_store_empty": (
            isinstance(keys_doc, dict)
            and isinstance(keys_doc.get("keys"), dict)
            and len(keys_doc.get("keys") or {}) == 0),
    }
    return {"ok": all(checks.values()), "checks": checks}


def _byok_encryption_key_probe(text: str) -> Dict[str, Any]:
    value = (text or "").strip()
    checks = {
        "fernet_key_length_44": len(value) == 44,
        "fernet_key_charset": bool(
            re.fullmatch(r"[A-Za-z0-9_-]{43}=", value)),
    }
    return {"ok": all(checks.values()), "checks": checks}


def _sanitized_file(path: Path) -> Dict[str, Any]:
    if path.is_symlink():
        return {"path": str(path), "present": True, "symlink": True}
    if not path.is_file():
        return {"path": str(path), "present": False}
    return {
        "path": str(path),
        "present": True,
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "symlink": False,
    }


def _byok_generated_default_probe(
    world: Path,
    run_dir: Path,
    descriptor: Dict[str, Any],
    source_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Prove the world's BYOK files are the product's generated default catalog.

    Read-only and sanitized: content values, API keys and the Fernet key are
    never returned; only shapes, provider ids, field names, sizes and hashes.
    Any operator-supplied provider config or non-empty key store fails closed.
    """
    data_dir = Path(run_dir) / "data"
    config_path = data_dir / "byok_config.json"
    keys_path = data_dir / "byok_keys.json"
    enc_path = data_dir / "byok_encryption_key"
    source_path = Path(world) / "code" / "backend" / "core" / "byok_endpoints.py"
    problems: List[str] = []
    if source_text is None:
        try:
            source_text = source_path.read_text(encoding="utf-8")
        except OSError as exc:
            return {
                "ok": False,
                "checks": {"source_readable": False},
                "error": f"{type(exc).__name__}: {exc}",
                "operator_config_present": False,
                "generated_default_catalog": False,
                "credential_free": False,
            }
    source_contract = _byok_source_contract(source_text)
    config_regular = config_path.is_file() and not config_path.is_symlink()
    keys_regular = keys_path.is_file() and not keys_path.is_symlink()
    enc_regular = enc_path.is_file() and not enc_path.is_symlink()
    config_doc: Any = None
    keys_doc: Any = None
    enc_text = ""
    if config_regular:
        try:
            config_doc = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"config parse failed: {type(exc).__name__}: {exc}")
    if keys_regular:
        try:
            keys_doc = json.loads(keys_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"keys parse failed: {type(exc).__name__}: {exc}")
    if enc_regular:
        try:
            enc_text = enc_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            problems.append(
                f"encryption key read failed: {type(exc).__name__}: {exc}")
    config_content = _byok_config_content_probe(config_doc, source_contract)
    keys_content = _byok_keys_content_probe(keys_doc)
    enc_content = _byok_encryption_key_probe(enc_text)
    env = descriptor.get("effective_env") or {}
    byok_env_keys = sorted(key for key in env if key.startswith("BYOK_"))
    world_code_seed = any(
        (Path(world) / "code" / "backend" / "data" / name).exists()
        for name in ("byok_config.json", "byok_keys.json",
                     "byok_encryption_key"))
    config_ok = bool(config_regular and config_content["ok"])
    keys_ok = bool(
        (not keys_path.exists())
        or (keys_regular and keys_content["ok"]))
    enc_shape_ok = bool(
        (not enc_path.exists())
        or (enc_regular and enc_content["ok"]))
    credential_free = bool(
        (not keys_path.exists()
         or (keys_regular and keys_content["checks"]["key_store_empty"]))
        and (not config_path.exists()
             or (config_regular
                 and config_content["checks"]["no_credential_value_fields"])))
    generated_default_catalog = bool(
        config_ok and keys_ok and not world_code_seed
        and not byok_env_keys and credential_free)
    operator_config_present = bool(
        (config_path.exists() and not generated_default_catalog)
        or (keys_path.exists()
            and not (keys_regular
                     and keys_content["checks"]["key_store_empty"])))
    checks = {
        "source_contract_ok": source_contract["ok"] is True,
        "config_regular_if_present": (not config_path.exists()) or config_regular,
        "keys_regular_if_present": (not keys_path.exists()) or keys_regular,
        "encryption_key_regular_if_present": (
            (not enc_path.exists()) or enc_regular),
        "config_generated_default": config_ok,
        "key_store_empty": (
            not keys_path.exists()
            or (keys_regular
                and keys_content["checks"]["key_store_empty"])),
        "encryption_key_shape_diagnostic": enc_shape_ok,
        "no_world_code_byok_seed": not world_code_seed,
        "no_byok_env_forwarded": not byok_env_keys,
        "credential_free": credential_free,
        "generated_or_absent": (
            (not config_path.exists() and not keys_path.exists())
            or generated_default_catalog),
        "no_operator_config": not operator_config_present,
    }
    if not source_contract["ok"]:
        problems.extend(source_contract.get("problems") or [])
    if config_path.exists() and not config_regular:
        problems.append("byok_config.json is a symlink or not a regular file")
    if keys_path.exists() and not keys_regular:
        problems.append("byok_keys.json is a symlink or not a regular file")
    if enc_path.exists() and not enc_regular:
        problems.append("byok_encryption_key is a symlink or not a regular file")
    if config_regular and not config_ok:
        problems.extend(config_content.get("problems") or [])
    if keys_regular and not keys_content["ok"]:
        problems.append("byok_keys.json is not the empty generated store")
    if enc_regular and not enc_content["ok"]:
        problems.append(
            "diagnostic: byok_encryption_key is not a URL-safe Fernet shape; "
            "shape alone does not establish origin")
    if world_code_seed:
        problems.append("BYOK files are seeded inside the code export")
    if byok_env_keys:
        problems.append(
            f"BYOK env override forwarded: {byok_env_keys}")
    return {
        "ok": bool(
            checks["no_operator_config"] and checks["credential_free"]
            and checks["no_world_code_byok_seed"]
            and checks["no_byok_env_forwarded"]
            and checks["generated_or_absent"]),
        "checks": checks,
        "config_present": config_regular,
        "keys_present": keys_regular,
        "encryption_key_present": enc_regular,
        "provider_count": config_content.get("provider_count"),
        "provider_ids": config_content.get("provider_ids"),
        "field_names": config_content.get("field_names"),
        "env_derived_fields": config_content.get("env_derived_fields"),
        "generated_default_catalog": generated_default_catalog,
        "operator_config_present": operator_config_present,
        "credential_free": credential_free,
        "encryption_key_shape_ok": enc_shape_ok,
        "byok_env_keys": byok_env_keys,
        "files": {
            "config": _sanitized_file(config_path),
            "keys": _sanitized_file(keys_path),
            "encryption_key": _sanitized_file(enc_path),
        },
        "problems": problems,
    }


def _worker_defaults_probe(
    pid: int,
    log_path: Path,
    runtime_defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    keys = (
        "ENABLE_SCHEDULER",
        "ENABLE_INGESTION_SYNC",
        "ATOM_AGENT_EVOLUTION_ENABLED",
        "EMBEDDING_PROVIDER",
        "FASTEMBED_MODEL",
        "FASTEMBED_CACHE_PATH",
        "HF_HUB_OFFLINE",
        "TMPDIR",
    )
    env = _process_env_probe(pid, keys)
    log_defaults: Dict[str, Any] = {}
    log_error = ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        matches = re.findall(
            r"core product profile worker defaults:\s*(\{[^\n]*\})", text)
        if matches:
            log_defaults = ast.literal_eval(matches[-1])
    except Exception as exc:  # noqa: BLE001
        log_error = f"{type(exc).__name__}: {exc}"
    values = env.get("values") or {}
    worker_keys = (
        "ENABLE_SCHEDULER",
        "ENABLE_INGESTION_SYNC",
        "ATOM_AGENT_EVOLUTION_ENABLED",
    )
    evidence: Dict[str, bool] = {
        key: values.get(key) == "false" for key in worker_keys}
    env_flags = all(evidence.values())
    log_flags = all(str(log_defaults.get(key)) == "false"
                    for key in worker_keys)
    env_ok = env.get("ok") is True
    provider_not_forwarded = (
        "EMBEDDING_PROVIDER" not in R.SERVER_ENV_WHITELIST)
    model_not_forwarded = (
        "FASTEMBED_MODEL" not in R.SERVER_ENV_WHITELIST)
    cache_env_not_forwarded = (
        "FASTEMBED_CACHE_PATH" not in R.SERVER_ENV_WHITELIST)
    tmpdir_forwarded = "TMPDIR" in R.SERVER_ENV_WHITELIST
    tmpdir_observed_match = (
        bool(values.get("TMPDIR"))
        and Path(str(values.get("TMPDIR"))).resolve()
        == Path(tempfile.gettempdir()).resolve())
    checks = {
        "env_probe_ok": env_ok,
        "worker_flags_off_from_actual_env": env_flags,
        "worker_flags_off_from_startup_log": log_flags,
        "worker_flags_proven": all(evidence.values()),
        "embedding_provider_default": (
            values.get("EMBEDDING_PROVIDER") in (None, "fastembed")
            or provider_not_forwarded),
        "fastembed_model_default": (
            values.get("FASTEMBED_MODEL") in (None, DEFAULT_EMBEDDING_MODEL)
            or model_not_forwarded),
        "fastembed_cache_env_absent": (
            values.get("FASTEMBED_CACHE_PATH") is None
            or cache_env_not_forwarded),
        "tmpdir_matches_driver": (
            tmpdir_observed_match
            or (not env_ok and tmpdir_forwarded)),
    }
    return {
        "ok": all(checks.values()),
        "pid": pid,
        "env": env,
        "worker_flag_evidence": evidence,
        "runtime_defaults": runtime_defaults,
        "runtime_defaults_diagnostic_only": (
            (runtime_defaults or {}).get("diagnostic_only") is True),
        "startup_log_defaults": log_defaults,
        "startup_log_error": log_error,
        "hf_hub_offline_present": values.get("HF_HUB_OFFLINE") is not None,
        "launcher_forwarding": {
            "EMBEDDING_PROVIDER": not provider_not_forwarded,
            "FASTEMBED_MODEL": not model_not_forwarded,
            "FASTEMBED_CACHE_PATH": not cache_env_not_forwarded,
            "TMPDIR": tmpdir_forwarded,
        },
        "checks": checks,
    }


def _stop_own_proc(proc: Any) -> Dict[str, Any]:
    """Stop only this harness's own process group and verify actual exit."""
    if proc is None:
        return {"pid": None, "was_running": False, "exited": True}
    pid = int(getattr(proc, "pid", 0) or 0)
    was_running = proc.poll() is None
    if was_running:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=15)
        except Exception:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
    return {
        "pid": pid,
        "was_running": was_running,
        "poll": proc.poll(),
        "exited": not _pid_alive(pid) if pid else True,
        "ps": _ps_fields(pid) if pid else {},
        "only_own_pid": True,
    }


def _capture_page_text(page: Any, out: Path, name: str) -> str:
    path = out / "page_text" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    text = page.locator("body").inner_text()
    path.write_text(text, encoding="utf-8")
    return str(path.relative_to(out))


def _lsof_contains(pid: int, needle: str) -> Dict[str, Any]:
    """Check whether the actual process has an open path containing needle."""
    try:
        proc = subprocess.run(
            ["lsof", "-p", str(pid), "-Fn"],
            capture_output=True, text=True, timeout=20)
        lines = [
            line[1:] for line in proc.stdout.splitlines()
            if line.startswith("n")
        ]
        matches = [line for line in lines if needle in line]
        return {
            "ok": proc.returncode == 0,
            "pid": pid,
            "needle": needle,
            "match_count": len(matches),
            "matches": matches[:10],
            "path_count": len(lines),
            "source": "lsof -p PID -Fn (actual process)",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "pid": pid,
            "needle": needle,
            "match_count": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _export_response_predicate(doc_id: str, export_format: str):
    def predicate(response: Any) -> bool:
        try:
            if response.request.method != "GET":
                return False
            if D3._path_of(response.url) != f"/api/documents/{doc_id}/export":
                return False
            return _query_param(response.url, "format") == export_format
        except Exception:
            return False
    return predicate


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------
def _run_execute(args: argparse.Namespace) -> int:
    if not args.expect_source_sha:
        print("[execute] --expect-source-sha is required", file=sys.stderr)
        return 2
    if not args.out:
        print("[execute] --out is required for the evidence bundle",
              file=sys.stderr)
        return 2
    out = Path(args.out).resolve()
    output = _output_target_probe(out, require_empty=True)
    if not output["ok"]:
        print(f"[execute] output refused: {output}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    exec_env = D3._prepare_execute_environment(args)

    source = _source_proof(args.expect_source_sha)
    support = _prebuild_support_probe()
    launcher = support["launcher"]
    fixture_inventory = support["fixture_inventory"]
    source["fixture_checksum"] = _checksum_source_binding(fixture_inventory)
    _write_json(out / "source.json", source)
    if not source.get("source_proof_ok"):
        print("[execute] source proof failed; refusing to build/launch",
              file=sys.stderr)
        return 2
    retained = _retained_evidence_probe(
        getattr(args, "api_evidence", None),
        getattr(args, "api_evidence_ref", "HEAD"))
    if not retained.get("ok"):
        print(f"[execute] retained API/test bytes drifted: {retained}",
              file=sys.stderr)
        return 2
    profile = _profile_probe()
    if not profile.get("ok"):
        print(f"[execute] core Documents profile is not enabled: {profile}",
              file=sys.stderr)
        return 2
    static = _static_source_contract_probe()
    if not static.get("ok"):
        print(
            "[execute] current Documents/export source does not match the "
            f"frozen contract: {static.get('checks')}", file=sys.stderr)
        return 2
    if not support["ok"]:
        print(
            "[execute] launcher/ACC/fixture prerequisites failed before any "
            f"world was created: {support['checks']}", file=sys.stderr)
        _write_json(out / "prebuild_blocker.json", {
            "kind": "browser_document_export_ui_prebuild_blocker",
            "generated_at": _now(),
            "source": source,
            "checks": support["checks"],
            "launcher": launcher,
            "acc_metadata": launcher.get("acc_metadata"),
            "fixture_inventory": fixture_inventory,
            "not_executed": True,
            "world_created": False,
            "note": (
                "Read-only prebuild proof failed. No world, database, server, "
                "browser or model was started. ACC/venv_freeze.txt is "
                "generated output; materialize the exact Git fixtures instead "
                "of inventing or regenerating them."),
        })
        return 2
    cache = _effective_cache_probe()
    fastembed_runtime = _fastembed_runtime_probe()
    if not cache.get("ok") or not fastembed_runtime.get("ok"):
        print(
            "[execute] FastEmbed prerequisite unavailable; this is a "
            "truthful non-executable state, not a coverage claim: "
            f"cache={cache.get('problems')} "
            f"runtime={fastembed_runtime.get('error') or fastembed_runtime.get('checks')}",
            file=sys.stderr)
        _write_json(out / "prerequisite_blocker.json", {
            "kind": "browser_document_export_ui_prerequisite_blocker",
            "generated_at": _now(),
            "source": source,
            "driver_environment": exec_env,
            "fastembed_cache": cache,
            "fastembed_runtime": fastembed_runtime,
            "not_executed": True,
            "note": (
                "No world/server/browser/model was started. Install nothing; "
                "root decides whether a prepared cache/worktree is available."),
        })
        return 2

    try:
        world_name = _world_name_for(source, args.world)
    except PreflightError as exc:
        print(f"[execute] world refused: {exc}", file=sys.stderr)
        return 2
    world = _world_path(world_name)
    try:
        under_root = world.parent.resolve() == WORLDS_ROOT.resolve()
    except Exception:
        under_root = False
    if not under_root:
        print(f"[execute] world {world_name!r} is outside {WORLDS_ROOT}",
              file=sys.stderr)
        return 2
    if world.exists():
        print(f"[execute] world {world_name!r} already exists; refusing",
              file=sys.stderr)
        return 2
    heavy = _heavy_probe(world)
    if not heavy["disk"].get("ok"):
        print(f"[execute] insufficient disk: {heavy['disk']}", file=sys.stderr)
        return 2
    if heavy["requires_root_heavy_approval"] and not args.root_heavy_approved:
        print(
            "[execute] world build estimate is >=4GiB; root must pass "
            "--root-heavy-approved", file=sys.stderr)
        return 2
    storage = _storage_probe()
    if not storage.get("ok"):
        print(f"[execute] world storage guard refused: {storage}",
              file=sys.stderr)
        return 2
    try:
        ready = _execute_ready(args)
    except DriverError as exc:
        print(f"[execute] not ready: {exc}", file=sys.stderr)
        return 2

    run_id = secrets.token_hex(6)
    fixture_filename, fixture_text, fixture_tail = _fixture_document(run_id)
    fixture_dir = out / "fixture"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = fixture_dir / fixture_filename
    fixture_path.write_bytes(fixture_text.encode("utf-8"))
    expected_version = f"ev4:{_sha256_text(fixture_text)}"
    expected_doc_id = "doc_" + _sha256_text(fixture_text)[:24]
    expected_filename = _expected_download_name(
        fixture_filename, "text", expected_doc_id)
    expected_markdown_name = _expected_download_name(
        fixture_filename, "markdown", expected_doc_id)
    expected_json_name = _expected_download_name(
        fixture_filename, "json", expected_doc_id)

    run_marker = {
        "schema": "atom-document-stored-export-ui-run-1",
        "source_sha": source["head"],
        "world": world_name,
        "started_at": _now(),
        "fixture": {
            "filename": fixture_filename,
            "sha256": _sha256_text(fixture_text),
            "tail_marker": fixture_tail,
            "synthetic_user_file": True,
        },
        "status": "starting",
    }
    _write_json(out / "DOCUMENT_EXPORT_UI_RUN.json", run_marker)
    _write_json(out / "retained_evidence.json", retained)

    scenario: Dict[str, Any] = {
        "kind": "browser_document_export_ui_scenario",
        "status": "running",
        "started_at": _now(),
        "labels": LABELS,
        "source": source,
        "retained_evidence": retained,
        "profile_prelaunch": profile,
        "static_contract_prelaunch": static,
        "launcher_prelaunch": launcher,
        "acc_metadata_prelaunch": launcher.get("acc_metadata"),
        "fixture_inventory_prelaunch": fixture_inventory,
        "fixture": {
            "filename": fixture_filename,
            "chars": len(fixture_text),
            "utf8_bytes": len(fixture_text.encode("utf-8")),
            "sha256": _sha256_text(fixture_text),
            "tail_marker": fixture_tail,
            "over_20k": len(fixture_text) > 20000,
            "synthetic_user_file": True,
            "path": str(fixture_path),
        },
        "steps": [],
        "checks": {},
        "requests": [],
        "not_claimed": LABELS["not_claimed"],
    }
    cleanups: List[Tuple[str, Any]] = []
    browser = None
    backend_proc = None
    frontend_proc = None
    result_code = 1
    started_mono = time.monotonic()

    def step(name: str, checks: Dict[str, Any],
             details: Optional[Dict[str, Any]] = None) -> None:
        checks = dict(checks or {})
        ok = bool(checks) and all(value is True for value in checks.values())
        scenario["steps"].append({
            "name": name,
            "status": "PASS" if ok else "FAIL",
            "checks": checks,
            "details": details or {},
            "at": _now(),
        })
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        for key, value in checks.items():
            print(f"    {'ok' if value is True else 'FAIL'} {key}: {value}")
        if not ok:
            raise DriverError(f"scenario check failed: {name}")

    try:
        os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))
        scenario["driver_environment"] = exec_env
        scenario["ready"] = ready
        scenario["fastembed_cache"] = cache
        scenario["fastembed_runtime"] = fastembed_runtime
        scenario["heavy"] = heavy
        step("source_retained_profile_and_fixture_proof", {
            "source_proof_ok": source.get("source_proof_ok") is True,
            "expected_sha_ok": source.get("expected_sha_ok") is True,
            "tracked_tree_clean": source.get("tracked_tree_clean") is True,
            "per_file_match": source.get("per_file", {}).get("ok") is True,
            "retained_api_test_bytes_unchanged": retained.get("ok") is True,
            "core_documents_profile": profile.get("ok") is True,
            "frozen_source_contract": static.get("ok") is True,
            "search_deferred": profile.get("search_enabled") is False,
            "launcher_paths_present": (
                support["checks"]["launcher_files_present"]),
            "acc_metadata_dir_writable": (
                support["checks"]["acc_metadata_dir_writable"]),
            "acc_venv_freeze_not_tracked": (
                support["checks"]["acc_venv_freeze_not_tracked"]),
            "legacy_fixture_set_verified": (
                support["checks"]["legacy_fixture_inventory_verified"]),
            "fastembed_cache_complete": cache.get("ok") is True,
            "fastembed_runtime_present": fastembed_runtime.get("ok") is True,
            "fixture_over_20k_tail": (
                len(fixture_text) > 20000
                and fixture_text.rstrip("\n").endswith(fixture_tail)),
            "fixture_width_identity": len(fixture_text) == len(
                fixture_text.encode("utf-8")),
        }, details={
            "head": source.get("head"),
            "files": list(source.get("per_file", {}).get("files", {})),
            "cache_dir": cache.get("effective_cache_dir"),
        })

        build = _build_world(
            world, source["head"], args.root_heavy_approved)
        scenario["world_build"] = {
            key: value for key, value in build.items()
            if key not in ("code_manifest", "export_tree", "manifest_doc")
        }
        step("fresh_marked_world_built_once", {
            "manifest_present": Path(build["manifest_path"]).is_file(),
            "fixture_present": Path(build["fixture_path"]).is_file(),
            "marker_present": Path(build["marker_path"]).is_file(),
            "marker_source_matches": (
                build["marker"].get("source_sha") == source["head"]),
            "marker_fixture_labelled": (
                "SYNTHETIC USER FILE"
                in str(build["marker"].get("fixture"))),
            "disk_preflight_ok": bool(
                (build.get("disk_preflight") or {}).get("ok")),
            "preflight_source_matches_frozen": (
                (build.get("preflight") or {}).get("source_revision")
                == source["head"]),
            "export_tree_matches_manifest": (
                build.get("export_tree") == build.get("code_manifest")),
            "launcher_rechecked_before_build": (
                (build.get("prebuild_support") or {}).get(
                    "launcher_files_present") is True),
            "acc_metadata_rechecked_before_build": (
                (build.get("prebuild_support") or {}).get(
                    "acc_metadata_dir_writable") is True),
            "legacy_fixture_set_rechecked_before_build": (
                (build.get("prebuild_support") or {}).get(
                    "legacy_fixture_inventory_verified") is True),
            "storage_guard_was_required": True,
        }, details={"world": str(world), "marker": build["marker"]})

        os.environ["ADDITIONAL_ALLOWED_ORIGINS"] = (
            f"http://localhost:{args.frontend_port},"
            f"http://127.0.0.1:{args.frontend_port}")
        os.environ["ALLOWED_HOSTS"] = (
            f"localhost,127.0.0.1,localhost:{args.backend_port},"
            f"localhost:{args.frontend_port}")
        # Explicit safe OFF for this acceptance episode. The general launcher
        # whitelist forwards this one boolean, so the actual child process env
        # (not source shape) is the positive proof; explicit callers that set
        # it true keep that semantics.
        os.environ["ATOM_AGENT_EVOLUTION_ENABLED"] = "false"
        backend_proc = R.launch_server(
            args.backend_port, world, provider_shim=False)
        cleanups.append(("backend", backend_proc))
        run_dir = R.launch_server.last_run_dir
        descriptor = dict(R.launch_server.descriptor)
        dotenv_isolation = getattr(
            R.launch_server, "last_dotenv_isolation", {}) or {}
        scenario["dotenv_isolation"] = dotenv_isolation
        db_path = run_dir / "data" / "atom.db"
        health = D3._health(args.backend_port)
        identity = health.get("identity") or {}
        with D3._api_client(args.backend_port) as live_profile_api:
            live_profile_response = live_profile_api.get("/api/product/profile")
        live_profile = {
            "status": live_profile_response.status_code,
            "body": (
                live_profile_response.json()
                if live_profile_response.status_code == 200 else {}),
        }
        runtime_defaults = _runtime_defaults_probe(
            world, descriptor, live_profile)
        byok = _byok_generated_default_probe(world, run_dir, descriptor)
        scenario["runtime_defaults"] = runtime_defaults
        scenario["byok"] = byok
        scenario["stack"] = {
            "world": str(world),
            "run_dir": str(run_dir),
            "db_path": str(db_path),
            "lance_dir": str(run_dir / "data" / "atom_memory"),
            "backend_port": args.backend_port,
            "frontend_port": args.frontend_port,
            "backend_descriptor": descriptor,
            "health": health,
            "provider_shim": False,
            "byok_config_in_world": byok["operator_config_present"],
            "byok_generated_default_catalog": byok[
                "generated_default_catalog"],
        }
        binding = D3._backend_source_binding(
            frozen_source_sha=source["head"],
            source_head=source["head"],
            preflight=build.get("preflight") or {},
            manifest=build.get("manifest_doc") or {},
            code_manifest=build.get("code_manifest") or {},
            export_tree=build.get("export_tree") or {},
            health_identity=identity,
            descriptor=descriptor,
            world=world,
        )
        scenario["backend_source_binding"] = binding
        step("backend_source_bound_to_git_bytes", binding["checks"],
             details={
                 "git_blob_files_checked": binding.get(
                     "git_blob_files_checked"),
                 "git_backend_export": binding.get("git_backend_export")})
        backend_pid = int(descriptor.get("pid") or backend_proc.pid)
        backend_ps = _ps_fields(backend_pid)
        worker = _worker_defaults_probe(
            backend_pid, world / "server.log",
            runtime_defaults=runtime_defaults)
        effective_env_keys = sorted(
            (descriptor.get("effective_env") or {}).keys())
        credential_env_keys = [
            key for key in effective_env_keys
            if key != "SECRET_KEY"
            and re.search(r"API_KEY|PASSWORD|TOKEN|BYOK|AWS|AZURE|OPENAI|ANTHROPIC|COHERE",
                          key, flags=re.I)
        ]
        scenario["backend_process"] = {
            "pid": backend_pid,
            "ps": backend_ps,
            "worker_defaults": worker,
            "descriptor_db_path": descriptor.get("db_path"),
            "descriptor_export_path": descriptor.get("export_path"),
            "effective_env_keys": effective_env_keys,
            "credential_env_keys": credential_env_keys,
        }
        step("backend_process_identity_and_runtime_flags", {
            "pid_alive": backend_ps.get("alive") is True,
            "cwd_is_world_backend_root": (
                D3._same_path(identity.get("cwd"),
                              world / "backend_root")),
            "db_is_run_db": D3._same_path(
                descriptor.get("db_path"), db_path),
            "db_not_live_dev_db": (
                db_path.resolve()
                != (BACKEND / "data" / "atom.db").resolve()),
            "db_parent_is_run_data": (
                db_path.parent.resolve()
                == (run_dir / "data").resolve()),
            "scheduler_and_ingestion_explicitly_off": (
                (worker.get("env", {}).get("values") or {}).get(
                    "ENABLE_SCHEDULER") == "false"
                and (worker.get("env", {}).get("values") or {}).get(
                    "ENABLE_INGESTION_SYNC") == "false"),
            "evolution_flag_explicitly_false": (
                (worker.get("env", {}).get("values") or {}).get(
                    "ATOM_AGENT_EVOLUTION_ENABLED") == "false"),
            "worker_flags_proven_off": (
                worker.get("checks", {}).get("worker_flags_proven") is True),
            "dotenv_isolation_guard_installed": (
                dotenv_isolation.get("ok") is True),
            "embedding_provider_default": (
                worker.get("checks", {}).get(
                    "embedding_provider_default") is True),
            "fastembed_model_default": (
                worker.get("checks", {}).get(
                    "fastembed_model_default") is True),
            "fastembed_cache_env_absent": (
                worker.get("checks", {}).get(
                    "fastembed_cache_env_absent") is True),
            "tmpdir_matches_driver": (
                worker.get("checks", {}).get(
                    "tmpdir_matches_driver") is True),
            "no_provider_shim": (
                scenario["stack"]["provider_shim"] is False),
            "sandbox_profile_local_only": (
                (world / "local_only.sb").is_file()
                and "(deny network*)" in (
                    world / "local_only.sb").read_text(encoding="utf-8")),
            "no_byok_config_in_world": (
                byok.get("operator_config_present") is False),
            "byok_config_generated_or_absent": (
                byok.get("checks", {}).get("generated_or_absent") is True),
            "byok_key_store_empty": (
                byok.get("checks", {}).get("key_store_empty") is True),
            "byok_credential_free": (
                byok.get("credential_free") is True),
            "byok_env_not_forwarded": (
                byok.get("checks", {}).get("no_byok_env_forwarded") is True),
            "no_credential_env_forwarded": len(credential_env_keys) == 0,
        }, details={
            "descriptor": {
                key: descriptor.get(key) for key in (
                    "run_id", "pid", "port", "export_path", "db_path",
                    "expected_cwd")},
            "worker_defaults": {
                "checks": worker.get("checks"),
                "worker_flag_evidence": worker.get("worker_flag_evidence"),
                "startup_log_defaults": worker.get("startup_log_defaults"),
                "values": worker.get("env", {}).get("values"),
            },
            "runtime_defaults": runtime_defaults,
            "byok": byok,
        })

        from scripts.orchestration_acceptance import (
            case5_browser_recovery as C5,
            browser_verify as BV,
        )
        frontend_proc = C5.start_frontend_copy(
            args.backend_port, args.frontend_port, world)
        if not frontend_proc:
            raise DriverError("frontend copy failed to start")
        cleanups.append(("frontend", frontend_proc))
        fe_base = f"http://localhost:{args.frontend_port}"
        frontend_proof = _frontend_export_proof(world)
        scenario["frontend"] = {
            "pid": frontend_proc.pid,
            "base": fe_base,
            "snapshot": str(world / "frontend_snapshot"),
            "source_proof": frontend_proof,
            "node_modules_symlink": (
                (world / "frontend_snapshot" / "node_modules").is_symlink()),
        }
        frontend_env = _process_env_probe(
            int(frontend_proc.pid),
            ("NEXT_PUBLIC_API_URL", "NEXTAUTH_URL", "NODE_OPTIONS"))
        scenario["frontend"]["process"] = {
            "ps": _ps_fields(int(frontend_proc.pid)),
            "env": frontend_env,
        }
        step("frontend_source_bytes_match_git", {
            "source_proof_ok": frontend_proof["ok"] is True,
            "files_checked": len(frontend_proof["files"]) == len(
                FRONTEND_SOURCE_FILES),
            "cwd_is_world_copy": D3._frontend_cwd_matches(
                D3._process_cwd(int(frontend_proc.pid)),
                world / "frontend_snapshot"),
            "node_modules_symlinked_not_installed": (
                (world / "frontend_snapshot" / "node_modules").is_symlink()),
            "no_env_local_copied": not (
                world / "frontend_snapshot" / ".env.local").exists(),
            "api_url_bound_to_backend": (
                (frontend_env.get("values") or {}).get(
                    "NEXT_PUBLIC_API_URL")
                == f"http://localhost:{args.backend_port}"),
        }, details=frontend_proof)

        with D3._api_client(args.backend_port) as profile_api:
            profile_response = profile_api.get("/api/product/profile")
            profile_body = (
                profile_response.json()
                if profile_response.status_code == 200 else {})
        caps = profile_body.get("capabilities") or {}
        scenario["profile"] = {
            "status": profile_response.status_code,
            "body": profile_body,
            "documents_enabled": bool(
                (caps.get("documents") or {}).get("enabled")),
            "search_enabled": bool((caps.get("search") or {}).get("enabled")),
            "tasks_enabled": bool((caps.get("tasks") or {}).get("enabled")),
            "boards_enabled": bool((caps.get("boards") or {}).get("enabled")),
        }
        step("core_documents_profile_search_deferred", {
            "profile_core": profile_body.get("profile") == "core",
            "documents_enabled": scenario["profile"]["documents_enabled"],
            "search_deferred": not scenario["profile"]["search_enabled"],
            "tasks_not_forced": not scenario["profile"]["tasks_enabled"],
            "boards_not_forced": not scenario["profile"]["boards_enabled"],
        }, details=scenario["profile"])

        password, password_meta = D3._password_for_run(
            args, world, db_path, run_dir)
        scenario["admin_password_source"] = password_meta
        token, login_meta = _api_login_as(
            args.backend_port, ADMIN_EMAIL, password)
        with D3._api_client(args.backend_port, token) as api:
            me_response = api.get("/api/auth/me")
            if me_response.status_code != 200:
                raise DriverError("authenticated public identity read failed")
            me_body = me_response.json()
            actor = _actor_scope(db_path, me_body)
            scenario["actor_scope"] = actor
            scenario["api_login"] = login_meta
            step("bootstrap_account_and_null_default_scope_bound", {
                "public_id_present": bool(me_body.get("id")),
                "email_is_bootstrap_admin": me_body.get("email") == ADMIN_EMAIL,
                "sql_actor_exact": actor["actor_id"] == me_body.get("id"),
                "public_workspace_matches_sql": (
                    actor["public_workspace_id"] == actor["raw_workspace_id"]),
                "personal_default_workspace_preserved": (
                    actor["effective_workspace_id"]
                    == (actor["raw_workspace_id"] or "default")),
                "personal_default_tenant_preserved": (
                    actor["effective_tenant_id"]
                    == (actor["raw_tenant_id"] or "default")),
                "password_not_recorded": (
                    password_meta.get("password_written_to_evidence")
                    is not True),
                "normal_bootstrap_account_only": True,
            }, details={
                "actor_scope": actor,
                "password_source": password_meta.get("source"),
            })

            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=not args.headed, channel="chrome")
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    accept_downloads=True)
                page = context.new_page()
                netwatch = C5.NetWatch(
                    page, args.backend_port, args.frontend_port)
                request_log: List[Dict[str, Any]] = []
                upload_requests: List[Dict[str, Any]] = []
                export_requests: List[Dict[str, Any]] = []

                def _on_request(request: Any) -> None:
                    try:
                        path = D3._path_of(request.url)
                        if not path.startswith("/api/documents"):
                            return
                        entry = {
                            "method": request.method,
                            "path": path,
                            "query": _query_dict(request.url),
                            "query_keys": _query_key_names(request.url),
                        }
                        request_log.append(entry)
                        if (request.method == "POST"
                                and path == "/api/documents/upload"):
                            upload_requests.append(entry)
                        if (request.method == "GET"
                                and path.endswith("/export")):
                            entry["doc_id"] = path.split("/")[-2]
                            export_requests.append(entry)
                    except Exception:
                        return

                page.on("request", _on_request)
                scenario["browser"] = {
                    "accept_downloads": True,
                    "headless": not args.headed,
                }

                login = BV.ui_login(page, fe_base, ADMIN_EMAIL, password)
                if not login.get("ok"):
                    try:
                        page.wait_for_url(
                            lambda url: "/login" not in str(url),
                            timeout=30000)
                        login["ok"] = "/login" not in page.url
                        login["landed_url"] = page.url
                    except Exception:
                        pass
                step("ordinary_admin_ui_login", {
                    "attempted": login.get("attempted") is True,
                    "landed_off_login": login.get("ok") is True,
                    "token_present_after_login": bool(
                        login.get("token_present_after_login")),
                    "no_seeded_cookie": True,
                }, details=login)
                D3._screenshot(page, out, "00_admin_login.png")

                onboarding = _complete_onboarding_if_present(page, api)
                scenario["onboarding"] = onboarding
                step("public_onboarding_status_and_wizard", {
                    "completion_durable": (
                        onboarding.get("completion_durable") is True),
                    "wizard_seen_or_already_complete": (
                        onboarding.get("wizard_seen") is True
                        or onboarding.get("completion_durable") is True),
                    "dismissed_through_real_buttons": (
                        onboarding.get("dismissed") is True
                        or onboarding.get("wizard_seen") is False),
                    "not_a_fixed_visibility_race": True,
                }, details=onboarding)

                _open_documents(page)
                step("documents_surface_opened_from_ordinary_nav", {
                    "url_is_documents": (
                        D3._path_of(page.url) == "/documents"),
                    "heading_visible": page.get_by_role(
                        "heading", name="Knowledge Base",
                        exact=True).count() == 1,
                    "upload_input_present": page.locator(
                        "#file-upload").count() == 1,
                    "data_nav_link_used": page.locator(
                        'a[href="/documents"]').count() >= 1,
                    "search_deferred_copy_visible": (
                        "Search is not part of this release."
                        in page.locator("body").inner_text()),
                    "no_search_request_yet": not any(
                        "/api/documents/search" in item["path"]
                        for item in request_log),
                })
                D3._screenshot(page, out, "01_documents_before_upload.png")

                with page.expect_response(
                        lambda response: (
                            response.request.method == "POST"
                            and D3._path_of(response.url)
                            == "/api/documents/upload"),
                        timeout=180000) as upload_info:
                    page.locator("#file-upload").set_input_files(
                        str(fixture_path))
                upload_response = upload_info.value
                upload_status = upload_response.status
                try:
                    upload_body = upload_response.json()
                except Exception:
                    upload_body = {}
                doc_id = str(upload_body.get("id") or "")
                metadata = upload_body.get("metadata") or {}
                upload_version = str(
                    metadata.get("source_content_hash") or "")
                chunk_count = upload_body.get("chunk_count")
                page.get_by_text(
                    "It is now available to your agent",
                    exact=False).first.wait_for(
                        state="visible", timeout=180000)
                page.get_by_text(
                    fixture_filename, exact=True).first.wait_for(
                        state="visible", timeout=180000)
                step("ordinary_txt_upload_returns_bound_document_identity", {
                    "http_2xx": 200 <= upload_status < 300,
                    "doc_id_present": bool(doc_id),
                    "doc_id_is_content_key": (
                        doc_id == expected_doc_id),
                    "doc_id_format": bool(DOC_ID_RE.fullmatch(doc_id)),
                    "title_is_uploaded_filename": (
                        upload_body.get("title") == fixture_filename),
                    "metadata_filename": (
                        metadata.get("filename") == fixture_filename),
                    "metadata_file_type_txt": (
                        metadata.get("file_type") == "txt"),
                    "metadata_pg_join_key": (
                        metadata.get("pg_document_id") == doc_id),
                    "metadata_integration_manual_upload": (
                        metadata.get("integration_id") == "manual_upload"),
                    "source_version_is_ev4": bool(
                        EXTRACTION_RE.fullmatch(upload_version)),
                    "source_version_matches_fixture_text": (
                        upload_version == expected_version),
                    "chunk_count_from_full_text": (
                        chunk_count == max(
                            1, -(-len(fixture_text) // 500))),
                    "exactly_one_upload_request": (
                        len(upload_requests) == 1),
                    "success_message_visible": page.get_by_text(
                        "Successfully uploaded", exact=False).count() >= 1,
                }, details={
                    "status": upload_status,
                    "body": {
                        "id": upload_body.get("id"),
                        "title": upload_body.get("title"),
                        "type": upload_body.get("type"),
                        "chunk_count": chunk_count,
                        "metadata": {
                            key: metadata.get(key) for key in (
                                "filename", "file_type", "pg_document_id",
                                "integration_id", "source_content_hash",
                                "source_type", "size")},
                    },
                })
                scenario["upload"] = {
                    "status": upload_status,
                    "doc_id": doc_id,
                    "title": upload_body.get("title"),
                    "chunk_count": chunk_count,
                    "source_content_hash": upload_version,
                    "metadata": {
                        key: metadata.get(key) for key in (
                            "filename", "file_type", "pg_document_id",
                            "integration_id", "source_content_hash",
                            "source_type", "size")},
                }
                D3._screenshot(page, out, "02_uploaded_list.png")

                card = page.locator("div.cursor-pointer").filter(
                    has_text=fixture_filename).first
                card.wait_for(state="visible", timeout=180000)
                with page.expect_response(
                        lambda response: (
                            response.request.method == "GET"
                            and D3._path_of(response.url)
                            == f"/api/documents/{doc_id}"),
                        timeout=180000) as detail_info:
                    card.click()
                detail_response = detail_info.value
                detail_status = detail_response.status
                try:
                    detail_body = detail_response.json()
                except Exception:
                    detail_body = {}
                detail_data = detail_body.get("data") or {}
                detail_metadata = detail_data.get("metadata") or {}
                page.wait_for_url(
                    lambda url: D3._path_of(url)
                    == f"/documents/{doc_id}", timeout=180000)
                D3._wait_selector(
                    page, '[data-testid="document-export"]', 180000)
                page.get_by_text(doc_id, exact=True).first.wait_for(
                    state="visible", timeout=180000)
                detail_text = page.locator("body").inner_text()
                format_options = page.locator(
                    '[data-testid="document-export-format"] option'
                ).all_text_contents()
                step("list_link_opens_exact_document_with_full_content", {
                    "detail_http_200": detail_status == 200,
                    "url_doc_id_exact": (
                        D3._path_of(page.url) == f"/documents/{doc_id}"),
                    "api_data_id_exact": detail_data.get("id") == doc_id,
                    "api_title_exact": (
                        detail_data.get("title") == fixture_filename),
                    "api_content_full_text": (
                        detail_data.get("content") == fixture_text),
                    "api_content_sha256_exact": (
                        _sha256_text(str(detail_data.get("content") or ""))
                        == _sha256_text(fixture_text)),
                    "api_index_source_version": (
                        detail_metadata.get("source_content_hash")
                        == upload_version),
                    "api_content_over_20k": (
                        len(str(detail_data.get("content") or "")) > 20000),
                    "ui_doc_id_visible": doc_id in detail_text,
                    "ui_head_marker_visible": (
                        "[SYNTHETIC USER FILE]" in detail_text),
                    "ui_tail_marker_visible": fixture_tail in detail_text,
                    "export_control_visible": page.locator(
                        '[data-testid="document-export"]').count() == 1,
                    "three_export_formats": (
                        format_options == [
                            FORMAT_LABEL[fmt] for fmt in EXPORT_FORMATS]),
                    "no_export_error_before_export": page.locator(
                        '[data-testid="document-export-error"]').count() == 0,
                }, details={
                    "detail_status": detail_status,
                    "format_options": format_options,
                    "content_sha256": _sha256_text(
                        str(detail_data.get("content") or "")),
                })
                _capture_page_text(page, out, "01_document_detail.txt")
                D3._screenshot(page, out, "03_document_detail.png")

                with page.expect_response(
                        lambda response: (
                            response.request.method == "GET"
                            and D3._path_of(response.url)
                            == f"/api/documents/{doc_id}"),
                        timeout=180000) as reload_info:
                    page.reload(wait_until="domcontentloaded", timeout=180000)
                reload_response = reload_info.value
                reload_body = reload_response.json()
                reload_data = reload_body.get("data") or {}
                D3._wait_selector(
                    page, '[data-testid="document-export"]', 180000)
                reload_text = page.locator("body").inner_text()
                step("reload_preserves_same_document_and_content", {
                    "reload_http_200": reload_response.status == 200,
                    "same_url_doc_id": (
                        D3._path_of(page.url) == f"/documents/{doc_id}"),
                    "same_api_id": reload_data.get("id") == doc_id,
                    "same_content_sha256": (
                        _sha256_text(str(reload_data.get("content") or ""))
                        == _sha256_text(fixture_text)),
                    "same_index_source_version": (
                        (reload_data.get("metadata") or {}).get(
                            "source_content_hash") == upload_version),
                    "tail_still_visible": fixture_tail in reload_text,
                    "no_export_error_after_reload": page.locator(
                        '[data-testid="document-export-error"]').count() == 0,
                }, details={"reload_status": reload_response.status})
                _capture_page_text(page, out, "02_document_detail_reload.txt")
                D3._screenshot(page, out, "04_document_detail_reload.png")

                sql = _sql_document(db_path, doc_id)
                index_version = str(
                    (reload_data.get("metadata") or {}).get(
                        "source_content_hash") or "")
                lance_root = run_dir / "data" / "atom_memory"
                lance_dirs = sorted(
                    path.name for path in lance_root.iterdir()
                ) if lance_root.is_dir() else []
                lance_lsof = _lsof_contains(
                    backend_pid, str(lance_root))
                step("durable_sql_and_index_bind_uploaded_revision", {
                    "sql_row_found": sql.get("found") is True,
                    "sql_id_exact": sql.get("id") == doc_id,
                    "sql_file_name": (
                        sql.get("file_name") == fixture_filename),
                    "sql_file_type_txt": sql.get("file_type") == "txt",
                    "sql_manual_upload": (
                        sql.get("integration_id") == "manual_upload"),
                    "sql_external_id_upload_binding": (
                        sql.get("external_id") == f"upload_{doc_id}"),
                    "sql_fresh": sql.get("freshness_status") == "fresh",
                    "sql_source_version_matches_upload": (
                        sql.get("source_content_hash") == upload_version),
                    "index_source_version_matches_upload": (
                        index_version == upload_version),
                    "sql_file_size_matches_fixture": (
                        sql.get("file_size_bytes")
                        == len(fixture_text.encode("utf-8"))),
                    "sql_workspace_preserves_null_default": (
                        sql.get("workspace_id")
                        == (actor["raw_workspace_id"] or "default")),
                    "lance_store_under_run_data": (
                        lance_root.is_dir() and bool(lance_dirs)),
                    "lance_store_named_default_shared": (
                        "default_shared" in lance_dirs),
                    "sql_not_live_dev_db": (
                        db_path.resolve()
                        != (BACKEND / "data" / "atom.db").resolve()),
                }, details={
                    "sql": sql,
                    "index_version": index_version,
                    "lance_dirs": lance_dirs,
                    "lance_lsof": lance_lsof,
                })

                export_proofs: Dict[str, Any] = {}
                for export_format in EXPORT_FORMATS:
                    page.locator(
                        '[data-testid="document-export-format"]'
                    ).select_option(export_format)
                    page.wait_for_function(
                        "([selector, value]) => "
                        "document.querySelector(selector)?.value === value",
                        arg=[
                            '[data-testid="document-export-format"]',
                            export_format,
                        ],
                    )
                    with page.expect_response(
                            _export_response_predicate(
                                doc_id, export_format),
                            timeout=180000) as response_info:
                        with page.expect_download(
                                timeout=180000) as download_info:
                            page.locator(
                                '[data-testid="document-export-submit"]'
                            ).click()
                    export_response = response_info.value
                    download = download_info.value
                    try:
                        api_bytes = export_response.body()
                        body_error = None
                    except Exception as exc:  # noqa: BLE001
                        api_bytes = b""
                        body_error = f"{type(exc).__name__}: {exc}"
                    failure = download.failure()
                    suggested = download.suggested_filename
                    download_url = str(getattr(download, "url", "") or "")
                    download_dir = out / "downloads"
                    download_dir.mkdir(parents=True, exist_ok=True)
                    save_path = download_dir / (
                        f"{export_format}__{suggested}")
                    downloaded_bytes = b""
                    save_error = None
                    if failure is None:
                        try:
                            download.save_as(str(save_path))
                            downloaded_bytes = save_path.read_bytes()
                        except Exception as exc:  # noqa: BLE001
                            save_error = f"{type(exc).__name__}: {exc}"
                    headers = {
                        str(key).lower(): str(value)
                        for key, value in export_response.headers.items()
                    }
                    request_headers = {
                        str(key).lower(): str(value)
                        for key, value in export_response.request.headers.items()
                        if str(key).lower() in (
                            "accept", "content-type", "origin", "referer",
                            "x-request-id")
                    }
                    expected_name = {
                        "text": expected_filename,
                        "markdown": expected_markdown_name,
                        "json": expected_json_name,
                    }[export_format]
                    proof = _verify_export_payload(
                        export_format=export_format,
                        api_bytes=api_bytes,
                        downloaded_bytes=downloaded_bytes,
                        expected_text=fixture_text,
                        tail_marker=fixture_tail,
                        doc_id=doc_id,
                        expected_version=upload_version,
                        headers=headers,
                        expected_filename=expected_name,
                        source_filename=fixture_filename,
                    )
                    export_proofs[export_format] = {
                        "status": export_response.status,
                        "doc_id": doc_id,
                        "observed_source_version": headers.get(
                            "x-document-source-version"),
                        "request_url_path": D3._path_of(
                            export_response.url),
                        "request_query": _query_dict(export_response.url),
                        "request_method": export_response.request.method,
                        "request_headers_safe": request_headers,
                        "suggested_filename": suggested,
                        "download_url": download_url,
                        "filename_matches_expected": (
                            suggested == expected_name),
                        "download_failure": failure,
                        "save_error": save_error,
                        "body_error": body_error,
                        "saved_path": (
                            str(save_path) if save_path.exists() else None),
                        "proof": proof,
                    }
                    request_count = len([
                        item for item in export_requests
                        if item.get("query", {}).get("format")
                        == export_format])
                    step(f"browser_download_{export_format}_exact_api_bytes", {
                        "http_200": export_response.status == 200,
                        "request_path_exact": (
                            D3._path_of(export_response.url)
                            == f"/api/documents/{doc_id}/export"),
                        "request_format_exact": (
                            _query_param(export_response.url, "format")
                            == export_format),
                        "request_has_no_client_path_param": (
                            not _has_forbidden_export_query(
                                export_response.url)),
                        "exactly_one_export_request": request_count == 1,
                        "download_failure_absent": failure is None,
                        "download_saved": save_error is None,
                        "response_body_read": body_error is None,
                        "suggested_filename_exact": (
                            suggested == expected_name),
                        "download_url_is_blob_object": (
                            download_url.startswith("blob:")),
                        "payload_ok": proof["ok"] is True,
                        **{f"payload_{key}": value
                           for key, value in proof["checks"].items()},
                    }, details={
                        "status": export_response.status,
                        "suggested_filename": suggested,
                        "download_url": download_url,
                        "expected_filename": expected_name,
                        "proof": {
                            "ok": proof["ok"],
                            "failures": proof["failures"],
                            "api_sha256": proof["api_sha256"],
                            "download_sha256": proof["download_sha256"],
                            "api_bytes": proof["api_bytes"],
                            "download_bytes": proof["download_bytes"],
                            "stored_text_sha256": proof[
                                "stored_text_sha256"],
                            "headers": proof["headers"],
                            "json": proof["json"],
                        },
                    })
                    _capture_page_text(
                        page, out, f"03_after_export_{export_format}.txt")
                    D3._screenshot(
                        page, out, f"05_after_export_{export_format}.png")

                scenario["export_proofs"] = export_proofs
                scenario["sql_document"] = sql
                step("three_formats_bind_same_document_and_revision", {
                    "three_formats_proven": (
                        sorted(export_proofs) == sorted(EXPORT_FORMATS)),
                    "all_payloads_ok": all(
                        item["proof"]["ok"] is True
                        for item in export_proofs.values()),
                    "all_downloads_equal_api_bytes": all(
                        item["proof"]["download_sha256"]
                        == item["proof"]["api_sha256"]
                        for item in export_proofs.values()),
                    "all_tails_present": all(
                        (item["proof"]["checks"].get(
                            "body_contains_tail_marker") is True)
                        or (item["proof"]["checks"].get(
                            "json_content_tail_marker") is True)
                        for item in export_proofs.values()),
                    "all_source_versions_match_upload": all(
                        item["proof"]["checks"].get(
                            "x_document_source_version_exact") is True
                        for item in export_proofs.values()),
                    "all_doc_ids_match_upload": all(
                        item["proof"]["checks"].get(
                            "x_document_id_exact") is True
                        for item in export_proofs.values()),
                    "json_version_matches_upload": (
                        (export_proofs["json"]["proof"]["json"] or {}).get(
                            "source_version") == upload_version),
                    "json_version_matches_sql_and_index": (
                        (export_proofs["json"]["proof"]["json"] or {}).get(
                            "source_version")
                        == sql.get("source_content_hash")
                        == index_version),
                })

                scenario["requests"] = request_log
                step("ordinary_download_boundary_not_search_or_binary", {
                    "no_foreign_origin_requests": (
                        len(netwatch.foreign) == 0),
                    "no_search_endpoint_request": not any(
                        "/api/documents/search" in item["path"]
                        for item in request_log),
                    "no_search_page_navigation": (
                        "/search" not in str(page.url)),
                    "all_export_requests_one_doc": all(
                        item.get("doc_id") == doc_id
                        for item in export_requests),
                    "export_request_count_three": (
                        len(export_requests) == len(EXPORT_FORMATS)),
                    "upload_request_count_one": (
                        len(upload_requests) == 1),
                    "no_export_error_banner": page.locator(
                        '[data-testid="document-export-error"]').count() == 0,
                    "no_original_binary_parameter": not any(
                        key in (item.get("query_keys") or [])
                        for item in export_requests
                        for key in ("download", "kind", "content_kind",
                                    "original")),
                    "search_capability_deferred": (
                        scenario["profile"]["search_enabled"] is False),
                    "no_provider_model_call": (
                        not any(
                            "chat" in item["path"]
                            for item in request_log)),
                }, details={
                    "foreign": netwatch.foreign,
                    "console_error_count": len(netwatch.console_errors),
                    "page_error_count": len(netwatch.page_errors),
                    "export_requests": export_requests,
                    "upload_requests": upload_requests,
                })
                _write_json(
                    out / "requests.json",
                    {"requests": request_log,
                     "export_requests": export_requests,
                     "upload_requests": upload_requests,
                     "foreign": netwatch.foreign,
                     "console_errors": netwatch.console_errors,
                     "page_errors": netwatch.page_errors})
                _capture_page_text(page, out, "04_final_documents.txt")
                D3._screenshot(page, out, "06_final_documents.png")
                context.close()

        scenario["status"] = "passed"
        scenario["finished_at"] = _now()
        result_code = 0
    except Exception as exc:  # noqa: BLE001 - preserve the failure
        scenario["status"] = "failed"
        scenario["error"] = f"{type(exc).__name__}: {exc}"
        scenario["finished_at"] = _now()
        result_code = 1
        print(f"[execute] FAIL: {scenario['error']}", file=sys.stderr)
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass
        exits: Dict[str, Any] = {}
        for label, proc in reversed(cleanups):
            try:
                exits[label] = _stop_own_proc(proc)
            except Exception as exc:  # noqa: BLE001
                exits[label] = {
                    "exited": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "only_own_pid": True,
                }
        scenario["own_process_exit"] = exits
        scenario["checks"] = {
            item["name"]: {
                "status": item["status"],
                "checks": item["checks"],
            }
            for item in scenario.get("steps", [])
        }
        if scenario.get("status") == "passed" and not all(
                item.get("exited") is True for item in exits.values()):
            scenario["status"] = "failed"
            scenario["error"] = (
                "an own child process did not exit; exit truth recorded")
            result_code = 1
        scenario["finished_at"] = scenario.get(
            "finished_at") or _now()
        scenario["elapsed_s"] = round(time.monotonic() - started_mono, 3)
        _write_json(out / "scenario.json", scenario)
        _write_json(out / "network.json", {
            "requests": scenario.get("requests") or [],
            "export_proofs": {
                key: {
                    "status": value.get("status"),
                    "doc_id": value.get("doc_id"),
                    "observed_source_version": value.get(
                        "observed_source_version"),
                    "suggested_filename": value.get("suggested_filename"),
                    "request_path": value.get("request_url_path"),
                    "request_query": value.get("request_query"),
                    "request_headers_safe": value.get(
                        "request_headers_safe"),
                    "proof_ok": (value.get("proof") or {}).get("ok"),
                    "api_sha256": (value.get("proof") or {}).get(
                        "api_sha256"),
                    "download_sha256": (value.get("proof") or {}).get(
                        "download_sha256"),
                    "failures": (value.get("proof") or {}).get("failures"),
                }
                for key, value in (scenario.get("export_proofs") or {}).items()
            },
            "own_process_exit": exits,
        })
        if not (out / "requests.json").exists():
            _write_json(out / "requests.json", {
                "requests": scenario.get("requests") or [],
                "own_process_exit": exits,
            })
        _write_json(out / "DOCUMENT_EXPORT_UI_RUN.json", {
            **run_marker,
            "status": scenario.get("status"),
            "finished_at": scenario.get("finished_at"),
            "scenario": str(out / "scenario.json"),
            "world_preserved": True,
        })
        print(f"[execute] status={scenario.get('status')} "
              f"evidence={out / 'scenario.json'}")
    return result_code


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Prepared ordinary-UI stored-text Documents export episode. "
            "No mode flag is preflight-only; --execute is root-owned."))
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true",
                      help="read-only preparation checks; no launch (default)")
    mode.add_argument("--execute", action="store_true",
                      help="root-owned single ordinary UI episode")
    ap.add_argument("--expect-source-sha", required=True,
                    help="explicit frozen Git source SHA")
    ap.add_argument("--api-evidence", default=None,
                    help="committed API evidence directory; defaults to the historical packet")
    ap.add_argument("--api-evidence-ref", default="HEAD",
                    help="Git ref containing the API packet, frozen before verification")
    ap.add_argument("--world", default=None,
                    help=f"fresh world name; must start {WORLD_PREFIX!r}")
    ap.add_argument("--backend-port", type=int, default=8047)
    ap.add_argument("--frontend-port", type=int, default=3147)
    ap.add_argument("--out", default=None,
                    help="evidence output directory")
    ap.add_argument("--report", default=None,
                    help="preflight report path (or use --out/preflight.json)")
    ap.add_argument("--headed", action="store_true",
                    help="show the browser during root-owned --execute")
    ap.add_argument("--admin-password-file", default=None,
                    help="0600 file containing the scratch admin password")
    ap.add_argument("--provision-admin-password", action="store_true",
                    help="provision a scratch admin through core.admin_bootstrap")
    ap.add_argument("--root-heavy-approved", action="store_true",
                    help="root confirms ownership of a >=4GiB world build")
    args = ap.parse_args(argv)

    if args.execute:
        return _run_execute(args)
    return _run_preflight(args)


if __name__ == "__main__":
    raise SystemExit(main())
