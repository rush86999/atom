#!/usr/bin/env python3
"""Execute WA-045: blank canvas create -> edit -> save -> reload.

The readiness ledger left this transition unproven with the detail
``/canvas renders; no artifact transition executed``. This driver runs the
real plain-document journey on a **fresh, isolated world** and refuses to
start unless every isolation condition holds:

* the world lives under the configured ``acceptance_worlds`` root and is
  empty (never a reused world, never the live dev data tree);
* a **new** scratch SQLite database is created inside that world — no backup,
  copy, or live credential from any other checkout is read;
* backend and frontend use unique loopback ports; no provider credential
  reaches either process (keys are blanked, workers are off);
* the exact serving processes prove their identity (pid, cwd, database,
  port, source revision) before any browser mutation happens.

It reuses the repository's existing launch contract
(``validate_local_world.py``, ``core.world_storage_guard``,
``scripts/orchestration_acceptance/storage_policy.py``) and the installed
Playwright/Chrome — nothing is downloaded or installed.

The browser assertions live in ``canvas_blank_create_edit_reload.cjs``.
Raw service logs and the harness transcript stay in ``--run-dir`` (private);
only a sanitized, secret-free evidence JSON is written to ``--out-dir``.

Exit codes: 0 passed, 1 a check failed, 2 refused by preflight.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend-nextjs"
LIVE_DB = (BACKEND / "data" / "atom.db").resolve()
CONFIG_PATH = BACKEND / "config" / "world_storage.json"
HARNESS = REPO / "scripts" / "acceptance" / "canvas_blank_create_edit_reload.cjs"
VALIDATE = REPO / "scripts" / "acceptance" / "validate_local_world.py"
DEFAULT_PYTHON = "/Users/rushiparikh/projects/atom/backend/venv314/bin/python"
DEFAULT_OUT = REPO / "docs" / "acceptance" / "evidence" / "wa045_canvas_blank_20261113"
PROVIDER_CREDENTIAL_ENV = (
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY",
    "GROQ_API_KEY", "TOGETHER_API_KEY", "OPENCODE_API_KEY",
    "MISTRAL_API_KEY", "XAI_API_KEY", "AZURE_OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN", "OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET",
    "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
)
FORBIDDEN_EVIDENCE_KEY = re.compile(
    r"(token|password|secret|cookie|authorization|api[_-]?key|credential)",
    re.IGNORECASE,
)


class Refused(RuntimeError):
    """Precondition that must stop the run before anything is written."""


def fail(message: str) -> "None":
    print(f"REFUSED: {message}", file=sys.stderr)
    raise SystemExit(2)


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def configured_worlds_root(repo: Path = REPO) -> Path:
    root = BACKEND / "data" / "acceptance_worlds"
    if CONFIG_PATH.is_file():
        try:
            config = json.loads(CONFIG_PATH.read_text())
        except (OSError, ValueError) as exc:
            raise Refused(f"cannot read {CONFIG_PATH}: {exc}") from exc
        raw = ((config.get("worlds") or {}).get("root")
               or "data/acceptance_worlds")
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = BACKEND / candidate
        root = candidate
    return root.expanduser().resolve(strict=False)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def guarded_world_path(world: Path) -> Path:
    """Independent live-data refusal, before the repo validator runs."""
    resolved = world.expanduser().resolve(strict=False)
    home = Path.home().resolve()
    forbidden = {
        Path("/").resolve(),
        home,
        REPO.resolve(),
        BACKEND.resolve(),
        (BACKEND / "data").resolve(),
        FRONTEND.resolve(),
        (REPO / "docs").resolve(),
        (REPO / "scripts").resolve(),
        configured_worlds_root(),
    }
    if resolved in forbidden:
        raise Refused(f"{resolved} is a protected repository/home/worlds-root path")
    if resolved == LIVE_DB or resolved == LIVE_DB.parent:
        raise Refused(f"{resolved} is the live dev database tree")
    if resolved.name.endswith(".db"):
        raise Refused(f"{resolved} names a database file, not a world directory")
    if not is_within(resolved, configured_worlds_root()):
        raise Refused(
            f"{resolved} must be under the configured worlds root "
            f"{configured_worlds_root()}")
    if (BACKEND / "data") in resolved.parents and not is_within(resolved, configured_worlds_root()):
        raise Refused(f"{resolved} is inside the live backend data tree")
    return resolved


def git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
        check=False,
    )
    revision = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise Refused(f"cannot resolve the repository commit: {result.stderr.strip()}")
    return revision


def run_checked(argv: List[str], cwd: Path, timeout: int = 120) -> str:
    result = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise Refused(
            f"{argv[0]} failed ({result.returncode}): "
            f"{(result.stderr or result.stdout).strip()[:500]}")
    return result.stdout


def validate_world_contract(world: Path, backend_port: int, frontend_port: int) -> Dict[str, Any]:
    output = run_checked([
        sys.executable, str(VALIDATE),
        "--world", str(world), "--repo", str(REPO),
        "--backend-port", str(backend_port),
        "--frontend-port", str(frontend_port),
    ], cwd=REPO)
    try:
        return json.loads(output)
    except ValueError as exc:
        raise Refused(f"world validator produced invalid JSON: {exc}") from exc


def ensure_storage_guard(worlds_root: Path, python_bin: str) -> str:
    """Mirror the integrated launcher: create only the LOCAL worlds root."""
    layout = "local"
    if CONFIG_PATH.is_file():
        try:
            config = json.loads(CONFIG_PATH.read_text())
            layout = str(config.get("layout") or "local")
        except (OSError, ValueError) as exc:
            raise Refused(f"cannot read {CONFIG_PATH}: {exc}") from exc
    if layout == "local" and not worlds_root.exists():
        worlds_root.mkdir(parents=True)
    result = subprocess.run(
        [python_bin, "-m", "core.world_storage_guard", "check"],
        cwd=BACKEND, capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode != 0:
        raise Refused(
            "world storage guard rejected the layout:\n"
            + (result.stdout + result.stderr).strip()[:1200])
    return (result.stdout + result.stderr).strip().splitlines()[0] if (result.stdout + result.stderr).strip() else "ok"


def storage_space_check(world: Path, python_bin: str) -> None:
    run_checked([
        python_bin, "-m", "scripts.orchestration_acceptance.storage_policy",
        "space", "--world", str(world), "--no-build-cache",
    ], cwd=BACKEND, timeout=120)


def wait_json(url: str, timeout: int) -> Dict[str, Any]:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = str(exc)
            time.sleep(2)
    raise Refused(f"{url} did not become healthy: {last}")


def wait_http_ok(url: str, timeout: int) -> int:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return response.status
                last = f"status {response.status}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(1)
    raise Refused(f"{url} never returned 200: {last}")


def child_env(extra: Dict[str, str], base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = dict(base if base is not None else os.environ)
    for key in PROVIDER_CREDENTIAL_ENV:
        env[key] = ""
    # A test-mode flag would skip schema creation and admin bootstrap; the
    # world contract requires the product's real startup path.
    for key in ("PYTEST_VERSION", "PYTEST_CURRENT_TEST", "TESTING"):
        env.pop(key, None)
    env.pop("ENVIRONMENT", None)
    env.update(extra)
    return env


def stop_process(proc: Optional[subprocess.Popen], label: str) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=20)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print(f"WARNING: {label} pid {proc.pid} did not exit", file=sys.stderr)


def read_harness_record(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"status": "failed", "error": f"harness did not write {path}", "checks": []}
    try:
        return json.loads(path.read_text())
    except ValueError as exc:
        return {"status": "failed", "error": f"harness record is not JSON: {exc}", "checks": []}


def read_json_column(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def database_checks(db_path: Path, canvas_id: str, expected_text: str) -> List[Dict[str, Any]]:
    """Read the scratch DB directly (read-only) — the durable store itself."""
    checks: List[Dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    if not db_path.is_file():
        check("scratch database exists", False, str(db_path))
        return checks
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, name, canvas_type, content, created_by FROM canvases WHERE id = ?",
            (canvas_id,),
        ).fetchone()
        content = read_json_column(row["content"]) if row is not None else None
        check(
            "scratch database holds the created artifact row",
            row is not None
            and row["id"] == canvas_id
            and row["canvas_type"] == "document"
            and row["name"] == "Untitled canvas",
            {
                "found": row is not None,
                "id": row["id"] if row is not None else None,
                "name": row["name"] if row is not None else None,
                "canvas_type": row["canvas_type"] if row is not None else None,
            },
        )
        check(
            "scratch database content is the exact saved envelope",
            content == {"content": expected_text},
            {"content": content},
        )

        audits = conn.execute(
            "SELECT id, canvas_id, action_type, details_json FROM canvas_audit "
            "WHERE canvas_id = ? ORDER BY created_at ASC, id ASC",
            (canvas_id,),
        ).fetchall()
        actions = [audit["action_type"] for audit in audits]
        check(
            "scratch database has only this artifact's create+update audits",
            len(audits) == 2 and sorted(actions) == ["create", "update"],
            {"count": len(audits), "actions": actions},
        )
        update_details = next(
            (read_json_column(audit["details_json"]) for audit in audits
             if audit["action_type"] == "update"), None)
        update_content = (update_details.get("content")
                          if isinstance(update_details, dict) else None)
        check(
            "scratch database update audit stores the exact text",
            isinstance(update_details, dict)
            and update_details.get("content") == {"content": expected_text},
            {"content_sha256": sha256_text(
                update_content.get("content") if isinstance(update_content, dict) else None)},
        )
        create_details = next(
            (read_json_column(audit["details_json"]) for audit in audits
             if audit["action_type"] == "create"), None)
        check(
            "scratch database create audit is the empty document",
            isinstance(create_details, dict)
            and create_details.get("content") == {"content": ""},
            {"content": create_details.get("content") if isinstance(create_details, dict) else None},
        )
        audit_ids = [audit["id"] for audit in audits]
        check(
            "every audit row belongs to the created artifact id",
            all(audit["canvas_id"] == canvas_id for audit in audits)
            and len(set(audit_ids)) == len(audit_ids),
            {"audit_ids": audit_ids},
        )
    finally:
        conn.close()
    return checks


def sha256_text(value: Any) -> Optional[str]:
    import hashlib
    if not isinstance(value, str):
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sanitize(value: Any) -> Any:
    """Drop anything that could carry a credential from committed evidence."""
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            if FORBIDDEN_EVIDENCE_KEY.search(str(key)):
                clean[key + "_redacted"] = True
                continue
            clean[key] = sanitize(item)
        return clean
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def write_evidence(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize(payload), indent=2, sort_keys=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--world-name", default="wa045_canvas_blank_20261113")
    ap.add_argument("--world", type=Path)
    ap.add_argument("--backend-port", type=int, default=8181)
    ap.add_argument("--frontend-port", type=int, default=3181)
    ap.add_argument("--python", default=os.getenv("ATOM_ACCEPTANCE_PYTHON", DEFAULT_PYTHON))
    ap.add_argument("--node", default=os.getenv("ATOM_ACCEPTANCE_NODE") or shutil.which("node") or "node")
    ap.add_argument("--run-dir", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--browser-timeout", type=int, default=600)
    ap.add_argument("--skip-browser", action="store_true")
    args = ap.parse_args()

    python_bin = str(Path(args.python).expanduser())
    if not Path(python_bin).is_file():
        fail(f"acceptance interpreter does not exist: {python_bin}")
    if not HARNESS.is_file():
        fail(f"browser harness does not exist: {HARNESS}")
    if not (FRONTEND / "node_modules").exists():
        fail(f"frontend dependencies are not installed at {FRONTEND / 'node_modules'}")
    if args.backend_port == args.frontend_port:
        fail("backend and frontend ports must differ")

    worlds_root = configured_worlds_root()
    world = (args.world or (worlds_root / args.world_name)).expanduser()
    world = guarded_world_path(world)
    if world.exists() and any(world.iterdir()):
        fail(f"world is not fresh (non-empty): {world}")

    validation = validate_world_contract(world, args.backend_port, args.frontend_port)
    world = Path(validation["world"])
    db_path = Path(validation["database"])
    if db_path.resolve() == LIVE_DB:
        fail("validated database is the live dev database")
    revision = git_revision()

    run_dir = (args.run_dir
               or Path(os.getenv("ATOM_ACCEPTANCE_RUN_DIR", "/private/tmp/atom-wa045-lifecycle"))
               ).expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_dir.chmod(0o700)
    except OSError:
        pass
    out_dir = args.out_dir.expanduser().resolve()
    harness_dir = run_dir / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    print(f"world            {world}")
    print(f"scratch db       {db_path}")
    print(f"backend          http://127.0.0.1:{args.backend_port}")
    print(f"frontend         http://127.0.0.1:{args.frontend_port}")
    print(f"run dir (private) {run_dir}")
    print(f"evidence         {out_dir}")
    print(f"commit           {revision}")

    if args.skip_browser:
        print("preflight OK (browser skipped)")
        return 0

    ensure_storage_guard(worlds_root, python_bin)
    storage_space_check(world, python_bin)

    # ── First write happens only after every refusal above ──────────────
    secret_key = secrets.token_urlsafe(48)
    # Generated in-process for this scratch world only; handed to the browser
    # harness through its environment so no credential is ever written to disk
    # or to a committed artifact.
    admin_login = secrets.token_urlsafe(24)
    world_data = world / "data"
    for sub in ("office", "assignments", "task_locks", "email_attachments", "atom_memory"):
        (world_data / sub).mkdir(parents=True, exist_ok=True)
    (world / "evidence").mkdir(parents=True, exist_ok=True)

    marker = {
        "schema": "atom-canvas-blank-world-1",
        "world": str(world),
        "repo": str(REPO.resolve()),
        "database": str(db_path),
        "backend_port": args.backend_port,
        "frontend_port": args.frontend_port,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "live_database": str(LIVE_DB),
    }
    (world / ".atom-canvas-blank-world.json").write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n")

    backend_proc: Optional[subprocess.Popen] = None
    frontend_proc: Optional[subprocess.Popen] = None
    harness_result: Optional[subprocess.CompletedProcess] = None
    db_checks: List[Dict[str, Any]] = []
    harness_record: Dict[str, Any] = {}
    identity: Dict[str, Any] = {}
    frontend_health: Dict[str, Any] = {}
    cleanup = {"backend_stopped": False, "frontend_stopped": False}

    try:
        backend_env = child_env({
            "DATABASE_URL": f"sqlite:///{db_path}",
            "ATOM_DATA_DIR": str(world_data),
            "LANCEDB_URI": str(world_data / "atom_memory"),
            "LANCEDB_URI_BASE": str(world_data / "atom_memory"),
            "ATOM_OFFICE_DIR": str(world_data / "office"),
            "ATOM_ASSIGNMENT_OUTPUT_DIR": str(world_data / "assignments"),
            "ATOM_TASK_LOCK_DIR": str(world_data / "task_locks"),
            "ATOM_EMAIL_ATTACHMENT_DIR": str(world_data / "email_attachments"),
            "BYOK_CONFIG_FILE": str(world_data / "byok_config.json"),
            "BYOK_KEYS_FILE": str(world_data / "byok_keys.json"),
            "BYOK_ENC_KEY_FILE": str(world_data / "byok_encryption_key"),
            "SECRET_KEY": secret_key,
            "ADMIN_PASSWORD": admin_login,
            "ATOM_PRODUCT_PROFILE": "core",
            "ENABLE_SCHEDULER": "false",
            "ENABLE_INGESTION_SYNC": "false",
            "ATOM_LOCAL_ONLY": "true",
            "ATOM_TURN_DECISION_ROUTING": "0",
            "ATOM_TASK_LIFECYCLE_ENABLED": "1",
            "ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT": "1",
            "ATOM_ASSIGNMENT_OUTBOX": str(world / "controlled-outbox.jsonl"),
            "ADDITIONAL_ALLOWED_ORIGINS": (
                f"http://localhost:{args.frontend_port},"
                f"http://127.0.0.1:{args.frontend_port}"),
            "ALLOWED_HOSTS": (
                f"localhost,127.0.0.1,localhost:{args.backend_port},"
                f"127.0.0.1:{args.backend_port},localhost:{args.frontend_port},"
                f"127.0.0.1:{args.frontend_port},testserver"),
        })
        backend_log = open(run_dir / "backend.log", "wb")
        backend_proc = subprocess.Popen(
            [python_bin, "-m", "uvicorn", "main_api_app:app",
             "--host", "127.0.0.1", "--port", str(args.backend_port),
             "--timeout-keep-alive", "75"],
            cwd=BACKEND, env=backend_env, stdout=backend_log,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        (run_dir / "backend.pid").write_text(str(backend_proc.pid))
        health = wait_json(f"http://127.0.0.1:{args.backend_port}/health", 180)
        identity = health.get("identity") or {}
        identity_checks = {
            "healthy": health.get("status") in ("healthy", "ok"),
            "pid": str(identity.get("pid")) == str(backend_proc.pid),
            "cwd": Path(str(identity.get("cwd") or "")).resolve() == BACKEND.resolve(),
            "database": Path(str(identity.get("database") or "")).resolve() == db_path.resolve(),
            "port": str(identity.get("port")) == str(args.backend_port),
            "revision": str(identity.get("revision")) == revision,
            "not_live_database": Path(str(identity.get("database") or "")).resolve() != LIVE_DB,
        }
        failed = [name for name, ok in identity_checks.items() if not ok]
        if failed:
            raise Refused(f"backend identity mismatch: {failed}; identity={identity}")
        print(f"backend identity  pid={backend_proc.pid} db={db_path.name} revision={revision[:12]}")

        frontend_env = child_env({
            "NEXT_PUBLIC_API_URL": f"http://127.0.0.1:{args.backend_port}",
            "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
            "NEXT_PUBLIC_ASSIGNMENT_TRANSPORT": "controlled",
            "NEXTAUTH_SECRET": secret_key,
            "NEXTAUTH_URL": f"http://127.0.0.1:{args.frontend_port}",
            "BACKEND_URL": f"http://127.0.0.1:{args.backend_port}",
        })
        frontend_log = open(run_dir / "frontend.log", "wb")
        next_bin = FRONTEND / "node_modules" / ".bin" / "next"
        if not next_bin.is_file():
            raise Refused(f"next binary missing: {next_bin}")
        frontend_proc = subprocess.Popen(
            [str(next_bin), "dev", "-p", str(args.frontend_port),
             "-H", "127.0.0.1", "--webpack"],
            cwd=FRONTEND, env=frontend_env, stdout=frontend_log,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        (run_dir / "frontend.pid").write_text(str(frontend_proc.pid))
        frontend_health = wait_json(
            f"http://127.0.0.1:{args.frontend_port}/api/health", 180)
        if frontend_health.get("service") != "atom-frontend" or frontend_health.get("status") not in ("healthy", "ok"):
            raise Refused(f"unexpected frontend health: {frontend_health}")
        wait_http_ok(f"http://127.0.0.1:{args.frontend_port}/login", 180)
        print(f"frontend identity service={frontend_health.get('service')}")

        harness_env = dict(os.environ)
        monaco_policy = (os.getenv("CANVAS_BLANK_MONACO_CDN", "allow").strip().lower() or "allow")
        if monaco_policy not in ("allow", "deny"):
            raise Refused(
                f"CANVAS_BLANK_MONACO_CDN must be 'allow' or 'deny', got {monaco_policy!r}")
        harness_env.update({
            "CANVAS_BLANK_BASE": f"http://127.0.0.1:{args.frontend_port}",
            "CANVAS_BLANK_API": f"http://127.0.0.1:{args.backend_port}",
            "CANVAS_BLANK_ADMIN_PASSWORD": admin_login,
            "CANVAS_BLANK_OUT": str(harness_dir),
            "CANVAS_BLANK_MONACO_CDN": monaco_policy,
            "NODE_PATH": str(FRONTEND / "node_modules"),
        })
        with open(run_dir / "harness.log", "wb") as harness_log:
            harness_proc = subprocess.Popen(
                [args.node, str(HARNESS)], cwd=REPO, env=harness_env,
                stdout=harness_log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                harness_rc = harness_proc.wait(timeout=args.browser_timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(harness_proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                harness_proc.wait(timeout=10)
                harness_rc = 124
        harness_result = subprocess.CompletedProcess(
            args=[args.node, str(HARNESS)], returncode=harness_rc)
        harness_path = harness_dir / "canvas-blank-harness.json"
        harness_record = read_harness_record(harness_path)
        canvas_id = harness_record.get("canvas_id")
        print(f"harness exit      {harness_result.returncode} status={harness_record.get('status')}")
        if harness_record.get("status") != "passed" or harness_result.returncode != 0:
            # Keep the failed checks in the evidence; still collect DB truth.
            pass
        if isinstance(canvas_id, str) and canvas_id:
            db_checks = database_checks(db_path, canvas_id, harness_record.get("exact_text") or "")

        harness_ok = harness_record.get("status") == "passed" and harness_result.returncode == 0
        db_ok = bool(db_checks) and all(check["ok"] for check in db_checks)
        passed = harness_ok and db_ok

        evidence = {
            "schema": "atom-wa045-canvas-blank-lifecycle-1",
            "wa_id": "WA-045",
            "status": "passed" if passed else "failed",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "commit": revision,
            "environment": {
                "world": str(world.relative_to(REPO)) if is_within(world, REPO) else world.name,
                "world_root": str(worlds_root.relative_to(REPO)) if is_within(worlds_root, REPO) else str(worlds_root),
                "database": db_path.name,
                "fresh_scratch_database": True,
                "live_database": False,
                "backend": f"http://127.0.0.1:{args.backend_port}",
                "frontend": f"http://127.0.0.1:{args.frontend_port}",
                "backend_pid": backend_proc.pid,
                "frontend_pid": frontend_proc.pid,
                "backend_identity": {
                    "revision": identity.get("revision"),
                    "cwd": identity.get("cwd"),
                    "database": identity.get("database"),
                    "port": identity.get("port"),
                    "source_id": identity.get("source_id"),
                },
                "workers": {"ENABLE_SCHEDULER": False, "ENABLE_INGESTION_SYNC": False},
                "provider_isolation": "all provider keys blanked for both processes; no provider call made",
                "external_asset_policy": monaco_policy,
                "monaco_assets": (
                    "bundled same-origin /monaco/vs build served by the frontend; "
                    "the harness refused every non-loopback request"
                    if monaco_policy == "deny" else
                    "pinned static editor assets are fetched from cdn.jsdelivr.net "
                    "by @monaco-editor/react; GET-only, no workspace data"),
            },
            "journey": {
                "create": harness_record.get("create"),
                "save": harness_record.get("save"),
                "reload": harness_record.get("reload"),
                "exact_text_sha256": harness_record.get("exact_text_sha256"),
                "exact_text": harness_record.get("exact_text"),
                "history_count": (harness_record.get("reload") or {}).get("history_count"),
                "version_badge": (harness_record.get("reload") or {}).get("version_badge"),
                "origins": harness_record.get("origins"),
                "non_loopback": harness_record.get("non_loopback"),
                "external_traffic": harness_record.get("external_traffic"),
            },
            "browser_checks": harness_record.get("checks", []),
            "database_checks": db_checks,
            "page_errors": harness_record.get("page_errors", []),
            "console_errors": harness_record.get("console_errors", []),
            "run": {
                "harness_exit_code": harness_result.returncode,
                "private_logs": "retained outside the repository; not committed",
            },
        }
        write_evidence(out_dir / "canvas-blank-lifecycle.json", evidence)

        total = len(evidence["browser_checks"]) + len(db_checks)
        ok_count = sum(1 for check in evidence["browser_checks"] if check["ok"]) + sum(
            1 for check in db_checks if check["ok"])
        print(f"checks            {ok_count}/{total}")
        print(f"STATUS            {evidence['status'].upper()}")
        return 0 if passed else 1
    finally:
        stop_process(frontend_proc, "frontend")
        stop_process(backend_proc, "backend")
        cleanup["frontend_stopped"] = frontend_proc is None or frontend_proc.poll() is not None
        cleanup["backend_stopped"] = backend_proc is None or backend_proc.poll() is not None
        if not cleanup["backend_stopped"] or not cleanup["frontend_stopped"]:
            print(f"WARNING: cleanup incomplete: {cleanup}", file=sys.stderr)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Refused as exc:
        fail(str(exc))
