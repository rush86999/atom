#!/usr/bin/env python3
"""Prepared child full-app restore/login/read/restart smoke harness.

NOT EXECUTED by the code-only worker. This file freezes the harness for root to
run with the shared HEAVY gate, fresh scratch paths and the normal product
entrypoint. It deliberately contains only stdlib imports so preflight and the
helper control tests cannot bind a product database.

Boundaries:
* Default mode is ``--preflight``: validate paths/disk/repo/python/sandbox and
  write nothing. The scratch path is never created before validation.
* ``--execute`` is the root-only mode. It seeds one synthetic scratch account,
  calls the existing release-kit backup/restore exactly once, renames the
  original scratch source to a preserved path, starts the real
  ``main_api_app:app`` under uvicorn, runs the readback, stops it, starts the
  same world again on the same database and repeats the readback.
* No live DB/world/acceptance root, provider, account, send, spend, install,
  deploy, model or download is used. The child runs under the existing seatbelt
  loopback-only pattern and the repo's existing background-worker off switches.
* ``TESTING=0`` is explicit for the seed/child because ``core.database``
  forces ``backend/test_integration.db`` under ``TESTING=1``. Every database and
  managed path points at the fresh scratch target instead. This is the
  documented explicit-DB exception in AGENTS.md, not a TESTING=1 claim.
* No delete/reset of the scratch world. Only this harness's own child PIDs are
  stopped; negative output, logs and the preserved source stay on disk.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

SCRATCH_PARENT = Path("/private/tmp")
DISK_FLOOR_BYTES = 4 * 1024**3
MIN_PORT = 1024
MAX_PORT = 65535
# exchange_memory_maintenance first sleeps 120s before its first cycle. A child
# is stopped inside this budget so that existing background poller cannot run
# against the smoke; no product flag is invented for that delay.
CHILD_FIRST_MAINTENANCE_DELAY_SECONDS = 120
CHILD_RUN_BUDGET_SECONDS = 110
SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
REPO_ROOT = Path(__file__).resolve().parents[2]
KIT_ROOT = REPO_ROOT / "scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9"
SEED_SCRIPT = Path(__file__).resolve().parent / "restore_child_seed.py"
READBACK_SCRIPT = Path(__file__).resolve().parent / "restore_child_readback.py"
RELEASE_TOOL = KIT_ROOT / "release_tool.py"
BACKEND_ROOT = REPO_ROOT / "backend"

# Untracked files that are handoff/agent configuration, not product source. The
# child source identity may be dirty only for these; any tracked modification or
# other untracked path refuses the run.
NON_PRODUCT_UNTRACKED = (
    "LEAD_NEXT.md",
    "opencode.jsonc",
    "docs/acceptance/evidence/",
    "docs/acceptance/",
)

# Provider credentials must never reach the scratch child. The child env is
# built from scratch anyway; this list is also a preflight audit.
PROVIDER_ENV_NAMES = (
    "OPENAI_API_KEY",
    "OPENAI_ORG_ID",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
    "GROQ_API_KEY",
    "TOGETHER_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "STRIPE_SECRET_KEY",
    "SENDGRID_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
    "SLACK_BOT_TOKEN",
)


class HarnessError(RuntimeError):
    """A safe, operator-readable refusal or readiness failure."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_resolve(path: Any) -> Optional[Path]:
    if path is None or str(path).strip() == "":
        return None
    try:
        return Path(str(path)).expanduser().resolve(strict=False)
    except (OSError, ValueError):
        return None


def _same_path(value: Any, expected: Any) -> bool:
    left = _safe_resolve(value)
    right = _safe_resolve(expected)
    return left is not None and right is not None and left == right


def _is_within(path: Any, root: Any) -> bool:
    left = _safe_resolve(path)
    right = _safe_resolve(root)
    if left is None or right is None:
        return False
    try:
        left.relative_to(right)
    except ValueError:
        return False
    return True


def _symlink_component(path: Path) -> Optional[Path]:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            return current
    return None


def _nearest_existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _write_json(path: Path, payload: Mapping[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd = os.open(str(path), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def _write_private_text(path: Path, text: str) -> None:
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text + "\n")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_named_booleans(checks: Mapping[str, Any], *, label: str = "checks") -> Dict[str, Any]:
    """Evaluate an explicit non-empty named-boolean map.

    ``all({})`` is true and has hidden harnesses before; an empty map is a hard
    error here, and every value must be the literal ``True``.
    """
    if not isinstance(checks, Mapping) or not checks:
        raise HarnessError(f"{label}: no named boolean controls were supplied")
    failed = sorted(name for name, value in checks.items() if value is not True)
    return {
        "ok": not failed,
        "checks": dict(checks),
        "failed_checks": failed,
    }


def validate_scratch_path(scratch: Any, *, repo_root: Any = REPO_ROOT) -> Dict[str, Any]:
    """Validate a fresh explicit scratch path without creating anything."""
    checks: Dict[str, bool] = {}
    errors: List[str] = []
    raw = Path(str(scratch)).expanduser() if scratch is not None else None
    checks["scratch_supplied"] = raw is not None
    if raw is None:
        return {"ok": False, "checks": checks, "errors": ["--scratch is required"]}
    checks["absolute"] = raw.is_absolute()
    bad_link = _symlink_component(raw) if raw.is_absolute() else None
    checks["no_symlink_components"] = bad_link is None
    resolved = raw.resolve(strict=False) if raw.is_absolute() else raw
    parent = SCRATCH_PARENT.resolve()
    checks["under_private_tmp"] = resolved != parent and parent in resolved.parents
    repo = Path(repo_root).expanduser().resolve(strict=False)
    checks["outside_repo"] = resolved != repo and repo not in resolved.parents
    checks["not_scratch_parent"] = resolved != parent
    exists = resolved.exists()
    checks["absent_or_empty_dir"] = True
    if exists:
        checks["absent_or_empty_dir"] = resolved.is_dir() and not any(resolved.iterdir())
        if resolved.is_symlink():
            checks["absent_or_empty_dir"] = False
            errors.append("scratch path is a symlink")
        if not resolved.is_dir():
            errors.append("scratch path is not a directory")
        elif any(resolved.iterdir()):
            errors.append("scratch path is not empty")
    probe = _nearest_existing_parent(resolved)
    try:
        free = int(shutil.disk_usage(probe).free)
    except OSError as exc:
        free = 0
        errors.append(f"disk usage unavailable: {exc}")
    checks["disk_floor_ok"] = free >= DISK_FLOOR_BYTES
    if not checks["disk_floor_ok"]:
        errors.append(
            f"free space {free} is below the HEAVY floor {DISK_FLOOR_BYTES}")
    if bad_link is not None:
        errors.append(f"symlink component: {bad_link}")
    if not checks["absolute"]:
        errors.append("scratch path must be absolute")
    if not checks["under_private_tmp"]:
        errors.append("scratch path must be a fresh child under /private/tmp")
    if not checks["outside_repo"]:
        errors.append("scratch path must not be inside the product repo")
    return {
        "ok": all(checks.values()) and not errors,
        "checks": checks,
        "errors": errors,
        "scratch": str(resolved),
        "parent": str(resolved.parent),
        "exists": exists,
        "disk_free_bytes": free,
        "disk_floor_bytes": DISK_FLOOR_BYTES,
        "probe": str(probe),
    }


def build_layout(scratch: Any) -> Dict[str, Path]:
    scratch_path = Path(str(scratch)).expanduser().resolve(strict=False)
    layout = {
        "scratch": scratch_path,
        "source": scratch_path / "source",
        "source_office": scratch_path / "source" / "office",
        "preserved_source": scratch_path / "source-unavailable",
        "release": scratch_path / "release",
        "target": scratch_path / "target",
        "target_db": scratch_path / "target" / "atom.db",
        "home": scratch_path / "home",
        "tmp": scratch_path / "tmp",
        "logs": scratch_path / "logs",
        "password": scratch_path / "password",
        "ids": scratch_path / "ids.json",
        "baseline": scratch_path / "baseline.json",
        "before": scratch_path / "before-restart.json",
        "after": scratch_path / "after-restart.json",
        "run_report": scratch_path / "run-report.json",
        "sandbox_profile": scratch_path / "child.sandbox",
        "child1_meta": scratch_path / "backend-1.json",
        "child2_meta": scratch_path / "backend-2.json",
        "child1_log": scratch_path / "logs" / "backend-1.log",
        "child2_log": scratch_path / "logs" / "backend-2.log",
    }
    for name, path in layout.items():
        if name == "scratch":
            continue
        if not _is_within(path, scratch_path):
            raise HarnessError(f"layout path escapes scratch: {name}={path}")
    return layout


def _base_env(layout: Mapping[str, Path], *, root: Path) -> Dict[str, str]:
    env = {
        "PATH": os.environ.get(
            "PATH", "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"),
        "HOME": str(layout["home"]),
        "TMPDIR": str(layout["tmp"]),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", os.environ.get("LANG", "en_US.UTF-8")),
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TESTING": "0",
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite:///{root / 'atom.db'}",
        "ATOM_DATA_DIR": str(root),
        "ATOM_OFFICE_DIR": str(root / "office"),
        "ATOM_EMAIL_ATTACHMENT_DIR": str(root / "email_attachments"),
        "LANCEDB_URI": str(root / "atom_memory"),
        "LANCEDB_URI_BASE": str(root / "atom_memory"),
        "ATOM_OUTPUT_DIR": str(root / "output"),
        # Keep BYOK/config/private-key paths inside the explicit scratch root;
        # otherwise api.byok_routes defaults to backend/data/byok_* in the live
        # checkout and the child would read the operator's private key store.
        "BYOK_CONFIG_FILE": str(root / "byok_config.json"),
        "BYOK_KEYS_FILE": str(root / "byok_keys.json"),
        "BYOK_ENC_KEY_FILE": str(root / "byok_encryption_key"),
        # Other backend/data-anchored stores with explicit test overrides.
        "EMBEDDING_REGISTRY_FILE": str(root / "embedding_registry.json"),
        "ATOM_PAIR_MEMO_PATH": str(root / "llm_pair_memos.json"),
        "ATOM_BPE_DATA_DIR": str(root / "bpe_workspaces"),
        # Keep application/audit logs out of backend/logs in the checkout.
        "LOG_FILE": str(layout["logs"] / "atom.log"),
        "AUDIT_LOG_PATH": str(layout["logs"] / "audit.log"),
        "ATOM_BOOTSTRAP_PASSWORD_FILE": str(
            layout["logs"] / "bootstrap_admin_password.txt"),
        # Existing core-release/acceptance switches. These are the flags used
        # by run_isolated.launch_server, preview_stack and core.product_profile;
        # no new isolation flag is invented here.
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": "false",
        "ATOM_CHAT_STREAMING": "false",
        "MEMORY_CONSOLIDATION_ENABLED": "false",
        "ENABLE_EMAIL_ATTACHMENT_MEMORY_INDEX": "false",
        "ENABLE_BINARY_INGESTION": "false",
        # Defense in depth for the existing maintenance loop: its db-safety step
        # must never publish a snapshot into the checkout's backend/data/backups.
        # The child is also stopped before that loop's 120s first-run delay.
        "ATOM_DB_SNAPSHOT_MIN_FREE_MB": "1099511627776",
        "ATOM_EXCHANGE_MAINTENANCE_INTERVAL_MIN": "1000000",
        "ATOM_DEPLOYMENT_AUDIENCE": "development",
        "ATOM_EMAIL_SEND_DISABLED": "true",
        "ATOM_ASSIGNMENT_ALLOW_LIVE_SEND": "false",
    }
    ssl_cert = os.environ.get("SSL_CERT_FILE")
    if ssl_cert:
        env["SSL_CERT_FILE"] = ssl_cert
    return env


def _with_secret(env: Mapping[str, str], secret_key: str) -> Dict[str, str]:
    out = dict(env)
    out["SECRET_KEY"] = secret_key
    return out


def build_source_env(layout: Mapping[str, Path], *, secret_key: str) -> Dict[str, str]:
    env = _with_secret(_base_env(layout, root=layout["source"]), secret_key)
    return env


def build_child_env(
    layout: Mapping[str, Path], *, port: int, secret_key: str,
) -> Dict[str, str]:
    env = _with_secret(_base_env(layout, root=layout["target"]), secret_key)
    env["PORT"] = str(port)
    env["API_PORT"] = str(port)
    return env


def find_provider_env_keys(env: Mapping[str, str]) -> List[str]:
    return sorted(
        name for name in PROVIDER_ENV_NAMES
        if str(env.get(name) or "").strip())


def validate_explicit_env(
    env: Mapping[str, str], layout: Mapping[str, Path], *,
    port: int, secret_key: str,
) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    errors: List[str] = []
    checks["testing_is_explicit_zero"] = str(env.get("TESTING")) == "0"
    checks["environment_is_test"] = str(env.get("ENVIRONMENT")) == "test"
    checks["secret_key_supplied"] = bool(secret_key) and env.get("SECRET_KEY") == secret_key
    checks["database_url_exact"] = str(env.get("DATABASE_URL")) == (
        f"sqlite:///{layout['target_db']}")
    checks["atom_data_dir_exact"] = _same_path(
        env.get("ATOM_DATA_DIR"), layout["target"])
    checks["office_dir_exact"] = _same_path(
        env.get("ATOM_OFFICE_DIR"), layout["target"] / "office")
    checks["email_dir_exact"] = _same_path(
        env.get("ATOM_EMAIL_ATTACHMENT_DIR"), layout["target"] / "email_attachments")
    checks["lancedb_uri_exact"] = _same_path(
        env.get("LANCEDB_URI"), layout["target"] / "atom_memory")
    checks["lancedb_base_exact"] = _same_path(
        env.get("LANCEDB_URI_BASE"), layout["target"] / "atom_memory")
    checks["output_dir_exact"] = _same_path(
        env.get("ATOM_OUTPUT_DIR"), layout["target"] / "output")
    checks["byok_config_exact"] = _same_path(
        env.get("BYOK_CONFIG_FILE"), layout["target"] / "byok_config.json")
    checks["byok_keys_exact"] = _same_path(
        env.get("BYOK_KEYS_FILE"), layout["target"] / "byok_keys.json")
    checks["byok_enc_key_exact"] = _same_path(
        env.get("BYOK_ENC_KEY_FILE"), layout["target"] / "byok_encryption_key")
    checks["embedding_registry_exact"] = _same_path(
        env.get("EMBEDDING_REGISTRY_FILE"), layout["target"] / "embedding_registry.json")
    checks["pair_memo_exact"] = _same_path(
        env.get("ATOM_PAIR_MEMO_PATH"), layout["target"] / "llm_pair_memos.json")
    checks["bpe_data_exact"] = _same_path(
        env.get("ATOM_BPE_DATA_DIR"), layout["target"] / "bpe_workspaces")
    checks["log_file_scratch"] = _same_path(
        env.get("LOG_FILE"), layout["logs"] / "atom.log")
    checks["audit_log_scratch"] = _same_path(
        env.get("AUDIT_LOG_PATH"), layout["logs"] / "audit.log")
    checks["bootstrap_password_file_scratch"] = _same_path(
        env.get("ATOM_BOOTSTRAP_PASSWORD_FILE"),
        layout["logs"] / "bootstrap_admin_password.txt")
    checks["port_exact"] = str(env.get("PORT")) == str(port)
    checks["scheduler_off"] = str(env.get("ENABLE_SCHEDULER")).lower() == "false"
    checks["ingestion_off"] = str(env.get("ENABLE_INGESTION_SYNC")).lower() == "false"
    checks["chat_streaming_off"] = str(env.get("ATOM_CHAT_STREAMING")).lower() == "false"
    checks["evolution_off"] = str(
        env.get("ATOM_AGENT_EVOLUTION_ENABLED")).lower() == "false"
    checks["db_snapshot_floor_blocks_live_backups"] = (
        str(env.get("ATOM_DB_SNAPSHOT_MIN_FREE_MB")) == "1099511627776")
    checks["exchange_interval_deferred"] = (
        str(env.get("ATOM_EXCHANGE_MAINTENANCE_INTERVAL_MIN")) == "1000000")
    checks["no_provider_keys"] = not find_provider_env_keys(env)
    if find_provider_env_keys(env):
        errors.append("provider env keys present: " + ",".join(find_provider_env_keys(env)))
    return {
        "ok": all(checks.values()) and not errors,
        "checks": checks,
        "errors": errors,
        "provider_key_names_present": find_provider_env_keys(env),
    }


def _allowed_untracked(path: str) -> bool:
    normalized = str(path).replace("\\", "/").lstrip("./")
    return any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in NON_PRODUCT_UNTRACKED
    )


def validate_health_identity(
    identity: Mapping[str, Any], *, pid: int, port: int, backend_root: Any,
    target_db: Any, expected_revision: str,
) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    checks["identity_present"] = bool(identity)
    checks["pid_exact"] = int(identity.get("pid") or 0) == int(pid)
    checks["cwd_exact"] = _same_path(identity.get("cwd"), backend_root)
    checks["backend_path_exact"] = _same_path(
        identity.get("backend_path"), backend_root)
    checks["database_exact"] = _same_path(identity.get("database"), target_db)
    checks["revision_exact"] = str(identity.get("revision") or "") == str(
        expected_revision)
    revision_prefix = str(expected_revision)[:12]
    source_id = str(identity.get("source_id") or "")
    checks["source_id_bound"] = (
        source_id == revision_prefix
        or source_id.startswith(revision_prefix + "-dirty.")
    )
    dirty_paths = [str(p) for p in (identity.get("dirty_paths") or [])]
    untracked_paths = [str(p) for p in (identity.get("untracked_paths") or [])]
    checks["no_tracked_product_dirty"] = not dirty_paths
    checks["untracked_non_product_only"] = all(
        _allowed_untracked(path) for path in untracked_paths)
    checks["port_exact"] = (
        identity.get("port") in (None, "") or int(identity.get("port")) == int(port)
    )
    instance_id = str(identity.get("instance_id") or "")
    checks["instance_bound"] = instance_id.startswith(
        source_id + f".{int(pid)}.") if source_id else False
    checks["no_identity_error"] = not identity.get("error")
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "source_id": source_id,
        "dirty": bool(identity.get("dirty")),
        "dirty_paths": dirty_paths,
        "untracked_paths": untracked_paths,
        "revision": identity.get("revision"),
        "instance_id": instance_id,
    }


def resolve_target_managed_path(
    raw: Any, *, expected: Any, target_root: Any, missing_source_root: Any,
    preserved_source_root: Any, must_exist: bool = True,
) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    errors: List[str] = []
    resolved = _safe_resolve(raw)
    expected_resolved = _safe_resolve(expected)
    target = _safe_resolve(target_root)
    missing = _safe_resolve(missing_source_root)
    preserved = _safe_resolve(preserved_source_root)
    checks["path_present"] = resolved is not None
    checks["expected_present"] = expected_resolved is not None
    checks["target_present"] = target is not None
    checks["exact_expected_path"] = (
        resolved is not None and expected_resolved is not None
        and resolved == expected_resolved)
    checks["under_target_root"] = (
        resolved is not None and target is not None
        and resolved != target and _is_within(resolved, target))
    checks["not_original_source"] = (
        resolved is not None and missing is not None
        and not _is_within(resolved, missing))
    checks["not_preserved_source"] = (
        resolved is not None and preserved is not None
        and not _is_within(resolved, preserved))
    checks["exists_as_file"] = bool(
        resolved is not None and resolved.is_file()) if must_exist else True
    if not checks["exact_expected_path"]:
        errors.append(f"path {resolved} is not the exact expected {expected_resolved}")
    if not checks["under_target_root"]:
        errors.append(f"path {resolved} is not a child of target {target}")
    if not checks["not_original_source"]:
        errors.append(f"path {resolved} still borrows the original source")
    if not checks["not_preserved_source"]:
        errors.append(f"path {resolved} borrows the preserved source")
    if not checks["exists_as_file"]:
        errors.append(f"path {resolved} is not an existing file")
    return {
        "ok": all(checks.values()) and not errors,
        "checks": checks,
        "errors": errors,
        "resolved": str(resolved) if resolved is not None else None,
        "expected": str(expected_resolved) if expected_resolved is not None else None,
    }


def validate_managed_file(
    raw: Any, *, expected: Any, target_root: Any, missing_source_root: Any,
    preserved_source_root: Any, expected_sha256: str,
) -> Dict[str, Any]:
    report = resolve_target_managed_path(
        raw, expected=expected, target_root=target_root,
        missing_source_root=missing_source_root,
        preserved_source_root=preserved_source_root, must_exist=True)
    checks = dict(report["checks"])
    errors = list(report["errors"])
    actual_sha = None
    resolved = _safe_resolve(raw)
    if resolved is not None and resolved.is_file():
        try:
            actual_sha = _sha256_file(resolved)
        except OSError as exc:
            errors.append(f"file hash failed: {exc}")
    checks["sha256_exact"] = actual_sha == str(expected_sha256)
    if not checks["sha256_exact"]:
        errors.append(f"file hash {actual_sha} != expected {expected_sha256}")
    return {
        "ok": all(checks.values()) and not errors,
        "checks": checks,
        "errors": errors,
        "resolved": report["resolved"],
        "expected": report["expected"],
        "sha256": actual_sha,
    }


def validate_exact_artifact(
    *, returned_binding: Any, expected_path: Any, target_root: Any,
    missing_source_root: Any, preserved_source_root: Any,
    expected_sha256: str, disk_sha256: Optional[str], download_sha256: Optional[str],
    docx_valid: bool, text_exact: bool,
) -> Dict[str, Any]:
    binding = validate_managed_file(
        returned_binding, expected=expected_path, target_root=target_root,
        missing_source_root=missing_source_root,
        preserved_source_root=preserved_source_root,
        expected_sha256=expected_sha256)
    checks = dict(binding["checks"])
    errors = list(binding["errors"])
    checks["disk_sha256_exact"] = disk_sha256 == str(expected_sha256)
    checks["download_sha256_exact"] = download_sha256 == str(expected_sha256)
    checks["download_matches_disk"] = (
        disk_sha256 is not None and disk_sha256 == download_sha256)
    checks["docx_valid"] = bool(docx_valid)
    checks["docx_text_exact"] = bool(text_exact)
    if not checks["disk_sha256_exact"]:
        errors.append(f"disk sha256 {disk_sha256} != expected {expected_sha256}")
    if not checks["download_sha256_exact"]:
        errors.append(f"download sha256 {download_sha256} != expected {expected_sha256}")
    if not checks["download_matches_disk"]:
        errors.append("downloaded bytes differ from the target file")
    if not checks["docx_valid"]:
        errors.append("downloaded bytes are not a valid DOCX")
    if not checks["docx_text_exact"]:
        errors.append("downloaded DOCX text does not match the fixture")
    return {
        "ok": all(checks.values()) and not errors,
        "checks": checks,
        "errors": errors,
        "binding": binding,
        "disk_sha256": disk_sha256,
        "download_sha256": download_sha256,
    }


def sandbox_profile(port: int) -> str:
    """Same loopback-only profile pattern as run_isolated._sandbox_profile."""
    return "\n".join((
        "(version 1)",
        "(allow default)",
        "(deny network*)",
        f'(allow network-outbound (remote ip4 "localhost:{int(port)}"))',
        "(allow network-inbound (local ip4))",
        "(allow network-inbound (local ip6))",
    )) + "\n"


def validate_port(port: Optional[int], *, require_free: bool = True) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    errors: List[str] = []
    if port is None:
        return {"ok": True, "checks": {"port_optional": True}, "errors": [],
                "port": None}
    try:
        value = int(port)
    except (TypeError, ValueError):
        return {"ok": False, "checks": {"port_integer": False},
                "errors": [f"invalid port: {port!r}"], "port": None}
    checks["port_integer"] = True
    checks["port_range"] = MIN_PORT <= value <= MAX_PORT
    in_use = _port_in_use(value)
    checks["port_free"] = not in_use if require_free else True
    if not checks["port_range"]:
        errors.append(f"port {value} outside {MIN_PORT}..{MAX_PORT}")
    if require_free and in_use:
        errors.append(f"port {value} is already in use")
    return {"ok": all(checks.values()) and not errors, "checks": checks,
            "errors": errors, "port": value}


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def choose_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    if port < MIN_PORT:
        raise HarnessError(f"ephemeral port {port} is below {MIN_PORT}")
    return port


def _git_head(repo_root: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def dependency_probe(python_bin: Path) -> Dict[str, Any]:
    checks: Dict[str, bool] = {}
    errors: List[str] = []
    checks["python_absolute"] = python_bin.is_absolute()
    checks["python_file"] = python_bin.is_file()
    checks["python_executable"] = bool(
        python_bin.is_file() and os.access(str(python_bin), os.X_OK))
    if not (checks["python_absolute"] and checks["python_file"]
            and checks["python_executable"]):
        return {"ok": False, "checks": checks, "errors": [
            f"python is not an executable absolute file: {python_bin}"],
            "python": str(python_bin), "probe_output": ""}
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    try:
        proc = subprocess.run(
            [str(python_bin), "-c", "import uvicorn, docx, pandas, pyarrow"],
            env=env, capture_output=True, text=True, timeout=180)
    except Exception as exc:  # noqa: BLE001
        checks["dependencies_import"] = False
        errors.append(f"dependency probe failed: {type(exc).__name__}: {exc}")
        return {"ok": False, "checks": checks, "errors": errors,
                "python": str(python_bin), "probe_output": ""}
    checks["dependencies_import"] = proc.returncode == 0
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        errors.append("python cannot import uvicorn/docx/pandas/pyarrow")
    return {"ok": all(checks.values()), "checks": checks, "errors": errors,
            "python": str(python_bin), "probe_output": output[-2000:]}


def collect_preflight(args: argparse.Namespace) -> Dict[str, Any]:
    repo_root = Path(args.repo_root).expanduser().resolve(strict=False)
    scratch_report = validate_scratch_path(args.scratch, repo_root=repo_root)
    layout = build_layout(args.scratch)
    python_path = Path(args.python).expanduser()
    if not python_path.is_absolute():
        python_path = python_path.absolute()
    python_report = dependency_probe(python_path)
    sandbox_ok = bool(
        SANDBOX_EXEC.is_file() and os.access(str(SANDBOX_EXEC), os.X_OK))
    port_report = validate_port(args.port, require_free=True)
    head = _git_head(repo_root)
    expected = args.expected_revision or head
    checks: Dict[str, bool] = {}
    checks["scratch_ready"] = bool(scratch_report["ok"])
    checks["repo_root_exact"] = repo_root == REPO_ROOT
    checks["repo_backend_present"] = (repo_root / "backend" / "main_api_app.py").is_file()
    checks["repo_models_present"] = (repo_root / "backend" / "core" / "models.py").is_file()
    checks["release_tool_present"] = (
        repo_root / "scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9"
        / "release_tool.py").is_file()
    checks["seed_script_present"] = SEED_SCRIPT.is_file()
    checks["readback_script_present"] = READBACK_SCRIPT.is_file()
    checks["sandbox_available"] = sandbox_ok
    checks["python_ready"] = bool(python_report["ok"])
    checks["port_ready"] = bool(port_report["ok"])
    checks["git_head_present"] = bool(head)
    checks["expected_revision_exact"] = bool(head and expected == head)
    checks["disk_floor_ok"] = bool(scratch_report["checks"].get("disk_floor_ok"))
    # core.memory_store_bootstrap reconciles <repo>/data/atom_memory into
    # backend/data/atom_memory at startup, ignoring LANCEDB_URI. Refuse if the
    # legacy live store exists so the child cannot copy live memory into the
    # checkout; the smoke never needs that migration.
    checks["legacy_live_memory_store_absent"] = not (
        repo_root / "data" / "atom_memory").exists()
    evaluation = check_named_booleans(checks, label="preflight")
    return {
        "schema": "atom-child-restore-preflight-2",
        "mode": "preflight",
        "required_mode": "execute" if args.execute else "preflight",
        "ready": evaluation["ok"],
        "checks": checks,
        "failed_checks": evaluation["failed_checks"],
        "errors": list(scratch_report["errors"]) + list(python_report["errors"])
        + list(port_report["errors"]),
        "scratch": scratch_report,
        "layout": {name: str(path) for name, path in layout.items()},
        "python": python_report,
        "sandbox": {"path": str(SANDBOX_EXEC), "available": sandbox_ok,
                    "policy": "loopback-only seatbelt; external network denied"},
        "port": port_report,
        "repo_root": str(repo_root),
        "head_revision": head,
        "expected_revision": expected,
        "parent_testing": os.environ.get("TESTING"),
        "child_testing": "0",
        "child_testing_reason": (
            "core.database forces backend/test_integration.db under TESTING=1; "
            "the child uses explicit scratch DATABASE_URL/ATOM_DATA_DIR paths"),
        "memory": {"included": False, "lancedb_search_claimed": False,
                   "public_document_search_claimed": False},
        "maintenance_delay_budget_seconds": CHILD_RUN_BUDGET_SECONDS,
        "maintenance_first_run_delay_seconds": (
            CHILD_FIRST_MAINTENANCE_DELAY_SECONDS),
        "provider_keys_present": find_provider_env_keys(os.environ),
        "parent_provider_key_names_present": find_provider_env_keys(os.environ),
        "writes_performed": False,
        "timestamp": _now(),
    }


def _open_private(path: Path, *, exclusive: bool = False):
    flags = os.O_CREAT | os.O_WRONLY
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    fd = os.open(str(path), flags, 0o600)
    return os.fdopen(fd, "wb")


def _run(
    cmd: List[Any], *, env: Mapping[str, str], cwd: Path, timeout: int,
    layout: Mapping[str, Path], label: str,
) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [str(part) for part in cmd], cwd=str(cwd), env=dict(env),
        capture_output=True, timeout=timeout)
    with _open_private(layout["logs"] / f"{label}.stdout.txt") as handle:
        handle.write(proc.stdout or b"")
    with _open_private(layout["logs"] / f"{label}.stderr.txt") as handle:
        handle.write(proc.stderr or b"")
    return proc


def _json_from_stdout(proc: subprocess.CompletedProcess, label: str) -> Dict[str, Any]:
    text = (proc.stdout or b"").decode("utf-8", "replace").strip()
    if not text:
        raise HarnessError(f"{label}: empty JSON stdout (rc={proc.returncode})")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HarnessError(f"{label}: malformed JSON stdout: {exc}") from exc
    if not isinstance(payload, dict):
        raise HarnessError(f"{label}: JSON stdout is not an object")
    return payload


def _safe_output(proc: subprocess.CompletedProcess) -> str:
    text = ((proc.stdout or b"") + (proc.stderr or b"")).decode(
        "utf-8", "replace").strip()
    return text[-2000:]


def _file_signature(path: Path) -> Optional[Dict[str, Any]]:
    try:
        st = Path(path).stat()
    except OSError:
        return None
    return {"size": int(st.st_size), "mtime_ns": int(st.st_mtime_ns),
            "inode": int(st.st_ino)}


def _dir_signature(path: Path) -> Optional[List[Any]]:
    try:
        entries = []
        with os.scandir(path) as scan:
            for entry in scan:
                try:
                    st = entry.stat()
                except OSError:
                    continue
                entries.append([entry.name, int(st.st_size), int(st.st_mtime_ns)])
        return sorted(entries)
    except OSError:
        return None


def _http_json(port: int, path: str, *, timeout: float = 5.0) -> tuple:
    conn = http.client.HTTPConnection("127.0.0.1", int(port), timeout=timeout)
    try:
        conn.request("GET", path, headers={"Accept": "application/json"})
        response = conn.getresponse()
        body = response.read()
        payload = json.loads(body.decode("utf-8") or "{}")
        return response.status, payload
    finally:
        conn.close()


def _wait_for_child(
    proc: subprocess.Popen, *, port: int, layout: Mapping[str, Path],
    backend_root: Path, target_db: Path, expected_revision: str,
    log_path: Path, timeout: int = 180,
) -> Dict[str, Any]:
    deadline = time.time() + timeout
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        if proc.poll() is not None:
            raise HarnessError(
                f"child exited early rc={proc.returncode}; log={log_path}")
        try:
            status, body = _http_json(port, "/api/health", timeout=3)
            last = body
            if status == 200:
                identity = body.get("identity") or {}
                report = validate_health_identity(
                    identity, pid=proc.pid, port=port,
                    backend_root=backend_root, target_db=target_db,
                    expected_revision=expected_revision)
                if not report["ok"]:
                    raise HarnessError(
                        "child identity mismatch: " +
                        ",".join(report["checks"].keys()) + " failed: " +
                        json.dumps({k: v for k, v in report["checks"].items()
                                    if not v}, sort_keys=True))
                return {"health": body, "identity": identity, "report": report}
        except HarnessError:
            raise
        except Exception:
            pass
        time.sleep(1.0)
    raise HarnessError(
        f"child health/identity not ready: {json.dumps(last, sort_keys=True)[:1000]}")


def _start_child(
    *, layout: Mapping[str, Path], python_bin: Path, env: Mapping[str, str],
    port: int, log_path: Path, meta_path: Path,
) -> subprocess.Popen:
    log = _open_private(log_path, exclusive=True)
    cmd = [
        str(SANDBOX_EXEC), "-f", str(layout["sandbox_profile"]),
        str(python_bin), "-m", "uvicorn", "main_api_app:app",
        "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
    ]
    proc = subprocess.Popen(
        cmd, cwd=str(BACKEND_ROOT), env=dict(env),
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    log.close()
    _write_json(meta_path, {
        "schema": "atom-child-restore-backend-2",
        "pid": proc.pid,
        "port": port,
        "cwd": str(BACKEND_ROOT),
        "database": str(layout["target_db"]),
        "target_root": str(layout["target"]),
        "source_root_original": str(layout["source"]),
        "source_root_preserved": str(layout["preserved_source"]),
        "log": str(log_path),
        "started_at": _now(),
        "env_keys": sorted(env.keys()),
        "secret_key_value_logged": False,
        "password_value_logged": False,
        "command_entrypoint": "uvicorn main_api_app:app",
        "network_policy": "seatbelt loopback-only",
    })
    return proc


def _stop_child(proc: subprocess.Popen, *, timeout: int = 30) -> Dict[str, Any]:
    pid = proc.pid
    if proc.poll() is not None:
        return {"pid": pid, "graceful": True, "already_exited": True,
                "returncode": proc.returncode}
    try:
        proc.terminate()
    except ProcessLookupError:
        proc.wait(timeout=5)
        return {"pid": pid, "graceful": True, "already_exited": True,
                "returncode": proc.returncode}
    try:
        proc.wait(timeout=timeout)
        return {"pid": pid, "graceful": True, "already_exited": False,
                "returncode": proc.returncode}
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
        return {"pid": pid, "graceful": False, "already_exited": False,
                "returncode": proc.returncode, "forced_kill": True}


def _wait_port_closed(port: int, *, timeout: int = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def capture_baseline(
    backup_db: Path, ids: Mapping[str, Any], layout: Mapping[str, Path],
) -> Dict[str, Any]:
    con = sqlite3.connect(
        f"file:{Path(backup_db).resolve().as_posix()}?mode=ro",
        uri=True, timeout=15)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute("SELECT * FROM canvas_audit ORDER BY id")
        audit_columns = [item[0] for item in cur.description]
        audit_rows = [dict(row) for row in cur.fetchall()]
        original = next(
            (row for row in audit_rows if row["id"] == ids["audit_id"]), None)
        if original is None:
            raise HarnessError(
                f"baseline lacks the synthetic audit row {ids['audit_id']}")
        user = con.execute(
            "SELECT id, email, role, status, tenant_id, workspace_id, last_login "
            "FROM users WHERE id=?", (ids["user_id"],)).fetchone()
        canvas = con.execute(
            "SELECT id, tenant_id, workspace_id, created_by, canvas_type, name, "
            "status, content FROM canvases WHERE id=?", (ids["canvas_id"],)).fetchone()
        goal = con.execute(
            "SELECT id, title, description, status, owner_id, workspace_id, "
            "tenant_id, source FROM goal_objectives WHERE id=?",
            (ids["goal_id"],)).fetchone()
        document = con.execute(
            "SELECT id, file_name, file_path, file_size_bytes, tenant_id, "
            "workspace_id FROM ingested_documents WHERE id=?",
            (ids["document_id"],)).fetchone()
        dataset = con.execute(
            "SELECT id, file_name, parquet_path, row_count, column_count, "
            "tenant_id, workspace_id, status FROM dataset_entries WHERE id=?",
            (ids["dataset_id"],)).fetchone()
        tenant = con.execute(
            "SELECT id, name, subdomain, edition, is_active FROM tenants WHERE id=?",
            (ids["tenant_id"],)).fetchone()
        workspace = con.execute(
            "SELECT id, name, tenant_id, status FROM workspaces WHERE id=?",
            (ids["workspace_id"],)).fetchone()
        if not all((user, canvas, goal, document, dataset, tenant, workspace)):
            raise HarnessError("baseline is missing a seeded product row")
        login_audit_count = con.execute(
            "SELECT count(*) FROM saas_audit_logs WHERE action='login_success' "
            "AND user_id=?", (ids["user_id"],)).fetchone()[0]
    finally:
        con.close()

    canonical_original = json.dumps(
        audit_rows, sort_keys=True, separators=(",", ":"), default=str)
    original_details = str(original["details_json"])
    source_root = layout["source"]
    target_root = layout["target"]

    def target_for(source_path: Any) -> str:
        path = Path(str(source_path))
        return str(target_root / path.relative_to(source_root))

    return {
        "schema": "atom-child-restore-baseline-2",
        "fixture_class": "PRODUCT_MODEL_READBACK_FIXTURE",
        "business_completion_claimed": False,
        "real_agent_or_business_work": False,
        "ids": dict(ids),
        "source_root": str(source_root),
        "preserved_source_root": str(layout["preserved_source"]),
        "target_root": str(target_root),
        "target_db": str(layout["target_db"]),
        "audit": {
            "columns": audit_columns,
            "rows": audit_rows,
            "original_ids": [str(row["id"]) for row in audit_rows],
            "original_rows_sha256": hashlib.sha256(
                canonical_original.encode("utf-8")).hexdigest(),
            "original_audit_id": str(original["id"]),
            "original_details_sha256": hashlib.sha256(
                original_details.encode("utf-8")).hexdigest(),
        },
        "user": dict(user) if user is not None else None,
        "canvas": dict(canvas) if canvas is not None else None,
        "goal": dict(goal) if goal is not None else None,
        "document": dict(document) if document is not None else None,
        "dataset": dict(dataset) if dataset is not None else None,
        "tenant": dict(tenant) if tenant is not None else None,
        "workspace": dict(workspace) if workspace is not None else None,
        "login_audit_count_before": int(login_audit_count),
        "expected_target_paths": {
            "office_artifact": target_for(ids["office_artifact_path"]),
            "document": target_for(ids["document_file_path"]),
            "parquet": target_for(ids["parquet_path"]),
        },
        "memory": {"included": False, "lancedb_search_claimed": False,
                   "public_document_search_claimed": False},
        "captured_at": _now(),
    }


def _execute(args: argparse.Namespace) -> int:
    preflight = collect_preflight(args)
    if not preflight["ready"]:
        # Preflight must write nothing, including a scratch directory or report.
        print(json.dumps({
            "ok": False, "status": "preflight_failed",
            "failed_checks": preflight["failed_checks"],
            "errors": preflight["errors"],
        }, indent=2))
        return 2

    layout = build_layout(args.scratch)
    repo_root = Path(args.repo_root).expanduser().resolve(strict=False)
    # Do NOT resolve a venv Python symlink: resolving it to the base interpreter
    # drops the venv's site-packages. The symlink path is what preserves them.
    python_bin = Path(args.python).expanduser()
    if not python_bin.is_absolute():
        python_bin = python_bin.absolute()
    scratch = layout["scratch"]
    for name in ("source", "target", "preserved_source"):
        if layout[name].exists():
            raise HarnessError(f"execute requires absent {name}: {layout[name]}")
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ("home", "tmp", "logs", "release"):
        layout[name].mkdir(mode=0o700, parents=True, exist_ok=True)

    password = secrets.token_urlsafe(24)
    secret_key = secrets.token_urlsafe(48)
    _write_private_text(layout["password"], password)
    expected_revision = args.expected_revision or preflight["head_revision"]
    if not expected_revision:
        raise HarnessError("expected source revision is unavailable")

    records: Dict[str, Any] = {
        "schema": "atom-child-restore-run-2",
        "status": "running",
        "ok": False,
        "paths": {name: str(path) for name, path in layout.items()},
        "preflight": preflight,
        "child_testing": "0",
        "child_testing_reason": preflight["child_testing_reason"],
        "memory": preflight["memory"],
        "business_completion_claimed": False,
        "business_mutations_after_restore": False,
        "authentication_bookkeeping_disclosed": True,
        "startup_bookkeeping_disclosed": True,
    }
    child: Optional[subprocess.Popen] = None
    try:
        source_env = build_source_env(layout, secret_key=secret_key)
        seed_proc = _run(
            [python_bin, str(SEED_SCRIPT), "--repo-root", str(repo_root),
             "--source-root", str(layout["source"]),
             "--password-file", str(layout["password"]),
             "--ids-out", str(layout["ids"])],
            env=source_env, cwd=repo_root, timeout=180, layout=layout,
            label="seed")
        records["seed"] = {"returncode": seed_proc.returncode}
        if seed_proc.returncode != 0:
            raise HarnessError(
                f"seed failed rc={seed_proc.returncode}: {_safe_output(seed_proc)}")
        ids = _read_json(layout["ids"])
        required_ids = (
            "email", "user_id", "tenant_id", "workspace_id", "canvas_id",
            "audit_id", "goal_id", "document_id", "dataset_id", "source_root",
            "office_artifact_path", "office_artifact_sha256",
            "document_file_path", "document_sha256", "parquet_path",
            "parquet_sha256", "office_artifact_text", "document_text",
        )
        missing_ids = [name for name in required_ids if not ids.get(name)]
        if missing_ids:
            raise HarnessError("seed ids missing: " + ",".join(missing_ids))
        if Path(str(ids["source_root"])).resolve() != layout["source"].resolve():
            raise HarnessError("seed source root is not the explicit scratch source")
        if ids.get("fixture_class") != "PRODUCT_MODEL_READBACK_FIXTURE":
            raise HarnessError("seed fixture is not labeled as a product-model fixture")
        if ids.get("business_completion_claimed") is not False:
            raise HarnessError("seed wrongly claims business completion")
        if ids.get("real_agent_or_business_work") is not False:
            raise HarnessError("seed wrongly claims real agent/business work")
        if ids.get("seeded_role") != "member":
            raise HarnessError("seed role is not the supported least-privilege member role")
        records["ids"] = {
            "schema": ids.get("schema"),
            "fixture_class": ids.get("fixture_class"),
            "business_completion_claimed": ids.get("business_completion_claimed"),
            "real_agent_or_business_work": ids.get("real_agent_or_business_work"),
            "seeded_role": ids.get("seeded_role"),
            "role_source": ids.get("role_source"),
            "email": ids.get("email"),
            "user_id": ids.get("user_id"),
            "tenant_id": ids.get("tenant_id"),
            "workspace_id": ids.get("workspace_id"),
            "canvas_id": ids.get("canvas_id"),
            "audit_id": ids.get("audit_id"),
            "goal_id": ids.get("goal_id"),
            "document_id": ids.get("document_id"),
            "dataset_id": ids.get("dataset_id"),
        }

        backup_proc = _run(
            [python_bin, str(RELEASE_TOOL), "--root", str(layout["release"]),
             "backup", "--label", "child"],
            env=source_env, cwd=repo_root, timeout=300, layout=layout,
            label="backup")
        backup_payload = _json_from_stdout(backup_proc, "backup")
        records["backup"] = {
            "returncode": backup_proc.returncode,
            "ok": backup_payload.get("ok"),
            "backup": backup_payload.get("backup"),
        }
        if backup_proc.returncode != 0 or backup_payload.get("ok") is not True:
            raise HarnessError(
                f"backup refused: {_safe_output(backup_proc)}")
        backup_dir = Path(str(backup_payload["backup"])).expanduser().resolve()
        if not _is_within(backup_dir, layout["release"]):
            raise HarnessError(f"backup path is outside the scratch release root: {backup_dir}")
        manifest = backup_payload.get("manifest") or {}
        if manifest.get("memory_included") is not False:
            raise HarnessError("backup unexpectedly included the memory store")
        records["backup"]["manifest_memory_included"] = manifest.get("memory_included")

        baseline = capture_baseline(backup_dir / "atom.db", ids, layout)
        _write_json(layout["baseline"], baseline)

        restore_proc = _run(
            [python_bin, str(RELEASE_TOOL), "--root", str(layout["release"]),
             "restore", "--backup", str(backup_dir),
             "--target-data-dir", str(layout["target"])],
            env=source_env, cwd=repo_root, timeout=300, layout=layout,
            label="restore")
        restore_payload = _json_from_stdout(restore_proc, "restore")
        status = restore_payload.get("status")
        records["restore"] = {
            "returncode": restore_proc.returncode,
            "attempts": 1,
            "status": status,
            "manifest_sha256": restore_payload.get("manifest_sha256"),
            "target": restore_payload.get("target"),
            "source_data_dir": restore_payload.get("source_data_dir"),
            "memory_included": restore_payload.get("memory_included"),
            "memory_restored": restore_payload.get("memory_restored"),
        }
        if restore_proc.returncode != 0 or status != "verified":
            records["status"] = (
                "restore_refused" if status == "refused"
                else "restore_unverified" if status == "committed_unverified"
                else "restore_failed")
            records["ok"] = False
            records["error"] = _safe_output(restore_proc)
            _write_json(layout["run_report"], records)
            print(json.dumps({
                "ok": False, "status": records["status"],
                "restore": records["restore"],
            }, indent=2))
            return 2
        baseline["restore"] = {
            "attempts": 1,
            "status": status,
            "manifest_sha256": restore_payload.get("manifest_sha256"),
            "source_data_dir": restore_payload.get("source_data_dir"),
            "target_data_dir": restore_payload.get("target"),
            "memory_included": restore_payload.get("memory_included"),
            "memory_restored": restore_payload.get("memory_restored"),
        }
        _write_json(layout["baseline"], baseline)

        if not _same_path(restore_payload.get("target"), layout["target"]):
            raise HarnessError("restored target is not the explicit scratch target")
        if not layout["target_db"].is_file():
            raise HarnessError("restored target database is missing")
        if restore_payload.get("memory_included") is not False:
            raise HarnessError("restore unexpectedly reports included memory")
        for name in ("output", "atom_memory", "email_attachments"):
            (layout["target"] / name).mkdir(mode=0o700, parents=True, exist_ok=True)

        if layout["preserved_source"].exists():
            raise HarnessError(
                f"preserved source already exists: {layout['preserved_source']}")
        layout["source"].rename(layout["preserved_source"])
        if layout["source"].exists():
            raise HarnessError("original source still exists after rename")
        if not layout["preserved_source"].is_dir():
            raise HarnessError("preserved source is not a directory after rename")
        records["source_absence"] = {
            "original_missing": not layout["source"].exists(),
            "preserved_exists": layout["preserved_source"].is_dir(),
            "original_read_after_rename": False,
        }

        live_data_dir = repo_root / "backend" / "data"
        live_fingerprint = live_data_dir / "db_fingerprint.json"
        live_backups_dir = live_data_dir / "backups"
        startup_before = {
            "db_fingerprint": _file_signature(live_fingerprint),
            "backups": _dir_signature(live_backups_dir),
            "bootstrap_password": _file_signature(
                layout["logs"] / "bootstrap_admin_password.txt"),
            "live_bootstrap_password": _file_signature(
                repo_root / "backend" / "logs" / "bootstrap_admin_password.txt"),
            "logs": _dir_signature(repo_root / "backend" / "logs"),
        }

        port = int(args.port) if args.port else choose_free_port()
        if _port_in_use(port):
            raise HarnessError(f"selected port is already in use: {port}")
        _write_private_text(
            layout["sandbox_profile"], sandbox_profile(port).rstrip("\n"))
        child_env = build_child_env(layout, port=port, secret_key=secret_key)
        env_report = validate_explicit_env(
            child_env, layout, port=port, secret_key=secret_key)
        records["child_env"] = {
            "ok": env_report["ok"],
            "checks": env_report["checks"],
            "errors": env_report["errors"],
            "provider_key_names_present": env_report["provider_key_names_present"],
            "keys": sorted(child_env.keys()),
        }
        if not env_report["ok"]:
            raise HarnessError(
                "child environment is not explicit/clean: " +
                ",".join(env_report["errors"]))

        child = _start_child(
            layout=layout, python_bin=python_bin, env=child_env, port=port,
            log_path=layout["child1_log"], meta_path=layout["child1_meta"])
        first_pid = child.pid
        first_started = time.monotonic()
        first_wait = _wait_for_child(
            child, port=port, layout=layout, backend_root=BACKEND_ROOT,
            target_db=layout["target_db"], expected_revision=expected_revision,
            log_path=layout["child1_log"], timeout=90)
        records["child1"] = {
            "pid": first_pid,
            "port": port,
            "identity": first_wait["identity"],
            "identity_report": first_wait["report"],
        }
        readback1 = _run(
            [python_bin, str(READBACK_SCRIPT), "--api-base",
             f"http://127.0.0.1:{port}", "--email", str(ids["email"]),
             "--password-file", str(layout["password"]),
             "--ids", str(layout["ids"]), "--baseline", str(layout["baseline"]),
             "--target-root", str(layout["target"]),
             "--target-db", str(layout["target_db"]),
             "--missing-source-root", str(layout["source"]),
             "--preserved-source-root", str(layout["preserved_source"]),
             "--expected-pid", str(first_pid),
             "--expected-revision", str(expected_revision),
             "--expected-instance-id", str(
                 first_wait["identity"].get("instance_id") or ""),
             "--out", str(layout["before"])],
            env=_readback_env(layout), cwd=repo_root, timeout=60,
            layout=layout, label="readback-1")
        records["readback1"] = {"returncode": readback1.returncode}
        if readback1.returncode != 0 or not layout["before"].is_file():
            raise HarnessError(
                f"first readback failed rc={readback1.returncode}: "
                f"{_safe_output(readback1)}")
        first_elapsed = time.monotonic() - first_started
        records["child1"]["elapsed_seconds"] = round(first_elapsed, 3)
        if first_elapsed > CHILD_RUN_BUDGET_SECONDS:
            raise HarnessError(
                f"first child exceeded the {CHILD_RUN_BUDGET_SECONDS}s "
                "maintenance-delay budget; stopping before background pollers run")
        before = _read_json(layout["before"])
        records["readback1"]["ok"] = before.get("ok")
        if before.get("ok") is not True:
            raise HarnessError(
                "first readback reported failure: "
                + ",".join(before.get("failed_checks") or []))

        stop1 = _stop_child(child)
        child = None
        records["child1"]["stop"] = stop1
        if not stop1.get("graceful"):
            raise HarnessError(f"first child did not stop gracefully: {stop1}")
        if not _wait_port_closed(port):
            raise HarnessError(f"port {port} did not close after first child")

        child = _start_child(
            layout=layout, python_bin=python_bin, env=child_env, port=port,
            log_path=layout["child2_log"], meta_path=layout["child2_meta"])
        second_pid = child.pid
        if second_pid == first_pid:
            raise HarnessError("restart did not produce a distinct PID")
        second_started = time.monotonic()
        second_wait = _wait_for_child(
            child, port=port, layout=layout, backend_root=BACKEND_ROOT,
            target_db=layout["target_db"], expected_revision=expected_revision,
            log_path=layout["child2_log"], timeout=90)
        records["child2"] = {
            "pid": second_pid,
            "port": port,
            "identity": second_wait["identity"],
            "identity_report": second_wait["report"],
        }
        readback2 = _run(
            [python_bin, str(READBACK_SCRIPT), "--api-base",
             f"http://127.0.0.1:{port}", "--email", str(ids["email"]),
             "--password-file", str(layout["password"]),
             "--ids", str(layout["ids"]), "--baseline", str(layout["baseline"]),
             "--target-root", str(layout["target"]),
             "--target-db", str(layout["target_db"]),
             "--missing-source-root", str(layout["source"]),
             "--preserved-source-root", str(layout["preserved_source"]),
             "--expected-pid", str(second_pid),
             "--expected-revision", str(expected_revision),
             "--expected-instance-id", str(
                 second_wait["identity"].get("instance_id") or ""),
             "--out", str(layout["after"]),
             "--compare-to", str(layout["before"])],
            env=_readback_env(layout), cwd=repo_root, timeout=60,
            layout=layout, label="readback-2")
        records["readback2"] = {"returncode": readback2.returncode}
        if readback2.returncode != 0 or not layout["after"].is_file():
            raise HarnessError(
                f"second readback failed rc={readback2.returncode}: "
                f"{_safe_output(readback2)}")
        second_elapsed = time.monotonic() - second_started
        records["child2"]["elapsed_seconds"] = round(second_elapsed, 3)
        if second_elapsed > CHILD_RUN_BUDGET_SECONDS:
            raise HarnessError(
                f"second child exceeded the {CHILD_RUN_BUDGET_SECONDS}s "
                "maintenance-delay budget; stopping before background pollers run")
        after = _read_json(layout["after"])
        records["readback2"]["ok"] = after.get("ok")
        if after.get("ok") is not True:
            raise HarnessError(
                "second readback reported failure: "
                + ",".join(after.get("failed_checks") or []))

        stop2 = _stop_child(child)
        child = None
        records["child2"]["stop"] = stop2
        if not stop2.get("graceful"):
            raise HarnessError(f"second child did not stop gracefully: {stop2}")
        if not _wait_port_closed(port):
            raise HarnessError(f"port {port} did not close after second child")

        startup_after = {
            "db_fingerprint": _file_signature(live_fingerprint),
            "backups": _dir_signature(live_backups_dir),
            "bootstrap_password": _file_signature(
                layout["logs"] / "bootstrap_admin_password.txt"),
            "live_bootstrap_password": _file_signature(
                repo_root / "backend" / "logs" / "bootstrap_admin_password.txt"),
            "logs": _dir_signature(repo_root / "backend" / "logs"),
        }
        records["startup_bookkeeping"] = {
            "disclosed": True,
            "db_fingerprint_path": str(live_fingerprint),
            "db_fingerprint_existed_before": (
                startup_before["db_fingerprint"] is not None),
            "db_fingerprint_before": startup_before["db_fingerprint"],
            "db_fingerprint_after": startup_after["db_fingerprint"],
            "db_fingerprint_created_or_changed": (
                startup_before["db_fingerprint"]
                != startup_after["db_fingerprint"]),
            "bootstrap_password_file": str(
                layout["logs"] / "bootstrap_admin_password.txt"),
            "bootstrap_password_file_created": (
                startup_before["bootstrap_password"]
                != startup_after["bootstrap_password"]),
            "bootstrap_password_file_content_read": False,
            "live_bootstrap_password_file": str(
                repo_root / "backend" / "logs" / "bootstrap_admin_password.txt"),
            "live_bootstrap_password_file_unchanged": (
                startup_before["live_bootstrap_password"]
                == startup_after["live_bootstrap_password"]),
            "live_logs_dir": str(repo_root / "backend" / "logs"),
            "live_logs_unchanged": startup_before["logs"] == startup_after["logs"],
            "live_backups_dir": str(live_backups_dir),
            "live_backups_unchanged": (
                startup_before["backups"] == startup_after["backups"]),
            "note": (
                "Product startup may write its wipe-check fingerprint and "
                "operational/auth receipts. No business write route is called "
                "by the readback; the db-safety snapshot floor and the child "
                "budget keep the existing maintenance poller from publishing "
                "a live backup during this smoke."),
        }

        records["checks"] = {
            "scratch_ready": bool(preflight["ready"]),
            "seed_exit_zero": records["seed"]["returncode"] == 0,
            "seed_fixture_labeled": (
                ids.get("fixture_class") == "PRODUCT_MODEL_READBACK_FIXTURE"
                and ids.get("business_completion_claimed") is False
                and ids.get("real_agent_or_business_work") is False),
            "seed_role_supported_member": ids.get("seeded_role") == "member",
            "seed_role_source_explicit": str(
                ids.get("role_source") or "").startswith("core.models.UserRole."),
            "backup_exit_zero": records["backup"]["returncode"] == 0,
            "backup_memory_excluded": (
                records["backup"].get("manifest_memory_included") is False),
            "baseline_written": layout["baseline"].is_file(),
            "restore_exit_zero": records["restore"]["returncode"] == 0,
            "restore_verified": records["restore"]["status"] == "verified",
            "restore_attempts_one": records["restore"]["attempts"] == 1,
            "restore_memory_excluded": (
                records["restore"].get("memory_included") is False),
            "source_original_missing": records["source_absence"]["original_missing"],
            "source_preserved_exists": records["source_absence"]["preserved_exists"],
            "child1_identity_exact": first_wait["report"]["ok"],
            "readback1_ok": before.get("ok") is True,
            "child1_graceful_stop": stop1.get("graceful") is True,
            "child1_under_maintenance_budget": (
                records["child1"].get("elapsed_seconds", CHILD_RUN_BUDGET_SECONDS + 1)
                <= CHILD_RUN_BUDGET_SECONDS),
            "child2_distinct_pid": second_pid != first_pid,
            "child2_identity_exact": second_wait["report"]["ok"],
            "readback2_ok": after.get("ok") is True,
            "restart_agreement_ok": bool(
                (after.get("restart_agreement") or {}).get("ok")),
            "child2_graceful_stop": stop2.get("graceful") is True,
            "child2_under_maintenance_budget": (
                records["child2"].get("elapsed_seconds", CHILD_RUN_BUDGET_SECONDS + 1)
                <= CHILD_RUN_BUDGET_SECONDS),
            "no_provider_env_keys": not env_report["provider_key_names_present"],
            "child_env_explicit": bool(env_report["ok"]),
            "memory_excluded_labeled": (
                preflight["memory"]["included"] is False
                and before["memory"]["included"] is False),
            "no_lancedb_claim": before["memory"]["lancedb_search_claimed"] is False,
            "no_public_document_search_claim": (
                before["memory"]["public_document_search_claimed"] is False),
            "business_mutations_after_restore_false": (
                before["bookkeeping"]["business_mutations_after_restore"] is False
                and after["bookkeeping"]["business_mutations_after_restore"] is False),
            "auth_bookkeeping_disclosed": (
                before["bookkeeping"]["authentication"].get("disclosed") is True
                and after["bookkeeping"]["authentication"].get("disclosed") is True),
            "auth_bookkeeping_observed": (
                before.get("checks", {}).get("auth_bookkeeping_observed") is True
                and after.get("checks", {}).get("auth_bookkeeping_observed") is True),
            "startup_bookkeeping_disclosed": (
                records["startup_bookkeeping"]["disclosed"] is True),
            "no_live_backup_snapshot_created": (
                records["startup_bookkeeping"]["live_backups_unchanged"] is True),
            "no_live_bootstrap_password_file_created": (
                records["startup_bookkeeping"][
                    "live_bootstrap_password_file_unchanged"] is True),
            "no_live_logs_written": (
                records["startup_bookkeeping"]["live_logs_unchanged"] is True),
            "scratch_preserved": layout["scratch"].is_dir(),
            "byok_paths_under_scratch": bool(
                env_report["checks"].get("byok_config_exact")
                and env_report["checks"].get("byok_keys_exact")
                and env_report["checks"].get("byok_enc_key_exact")),
        }
        evaluation = check_named_booleans(records["checks"], label="execute")
        records["ok"] = evaluation["ok"]
        records["failed_checks"] = evaluation["failed_checks"]
        records["status"] = "verified" if evaluation["ok"] else "failed"
        records["completed_at"] = _now()
        _write_json(layout["run_report"], records)
        print(json.dumps({
            "ok": evaluation["ok"],
            "status": records["status"],
            "failed_checks": evaluation["failed_checks"],
            "run_report": str(layout["run_report"]),
            "scratch_preserved": str(layout["scratch"]),
        }, indent=2))
        return 0 if evaluation["ok"] else 1
    except BaseException as exc:  # noqa: BLE001 - preserve the honest failure
        records["status"] = "failed"
        records["ok"] = False
        records["failed_checks"] = records.get("failed_checks") or []
        records["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if child is not None:
            stop = _stop_child(child)
            records.setdefault("cleanup", {})["unexpected_child_stop"] = stop
        if records.get("status") == "running":
            records["status"] = "failed"
            records["ok"] = False
            records["error"] = records.get("error") or "unexpected harness failure"
        records["completed_at"] = records.get("completed_at") or _now()
        try:
            _write_json(layout["run_report"], records)
        except OSError as exc:
            records["error"] = (
                f"{records.get('error') or 'run failure'}; run-report write failed: "
                f"{type(exc).__name__}: {exc}")


def _readback_env(layout: Mapping[str, Path]) -> Dict[str, str]:
    env = {
        "PATH": os.environ.get(
            "PATH", "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"),
        "HOME": str(layout["home"]),
        "TMPDIR": str(layout["tmp"]),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", os.environ.get("LANG", "en_US.UTF-8")),
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    ssl_cert = os.environ.get("SSL_CERT_FILE")
    if ssl_cert:
        env["SSL_CERT_FILE"] = ssl_cert
    return env


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare/run the isolated child restore smoke.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true",
                      help="validate and write nothing (default)")
    mode.add_argument("--execute", action="store_true",
                      help="root-only: run the prepared child smoke")
    parser.add_argument("--scratch", required=True,
                        help="fresh absolute scratch root under /private/tmp")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--python", default=sys.executable,
                        help="absolute interpreter with uvicorn/docx/pandas/pyarrow")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--expected-revision", default=None,
                        help="exact product commit the child must load")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.execute:
        preflight = collect_preflight(args)
        print(json.dumps(preflight, indent=2))
        return 0 if preflight["ready"] else 2
    try:
        return _execute(args)
    except HarnessError as exc:
        print(json.dumps({"ok": False, "status": "failed", "error": str(exc)},
                         indent=2))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "status": "failed",
                          "error": f"{type(exc).__name__}: {exc}"},
                         indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
