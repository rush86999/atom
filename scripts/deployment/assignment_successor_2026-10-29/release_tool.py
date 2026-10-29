#!/usr/bin/env python3
"""Operate one assignment-successor release without touching user data.

Subcommands:
  preflight  validate release identity, runtime flags, paths and ports
  start      start backend + prebuilt frontend, verify /api/health identity
  stop       stop only this release's recorded PIDs
  backup     WAL-safe verified backup of data + config
  status     read health and startup receipt
  rollback   flip to the previous release and restart; never restores the DB
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from release_identity import (  # noqa: E402
    EXPECTED_PRODUCT_TREE_SHA256,
    RELEASE_COMMIT,
    atomic_write_json,
    load_identity,
    product_tree_sha256,
    sha256_file,
    sha256_tree,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_env(path: Path) -> dict:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        try:
            parts = shlex.split(value)
            value = parts[0] if parts else ""
        except ValueError:
            value = value.strip("'\"")
        out[key.strip()] = value
    return out


def runtime_env(root: Path) -> dict:
    env = dict(os.environ)
    env.update(read_env(root / "config" / "env.release"))
    env.update(read_env(root / "config" / "secrets.env"))
    return env


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def http_json(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{}")


def port_busy(port: int) -> bool:
    try:
        out = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True)
        return bool(out.stdout.strip())
    except Exception:
        return False


def check_source_manifest(app: Path) -> dict:
    path = app / "docs" / "acceptance" / "assignment-successor-package-2026-10-29" / "source_manifest.json"
    if not path.is_file():
        return {"ok": False, "error": "source_manifest_missing"}
    manifest = json.loads(path.read_text())
    mismatches = []
    for item in manifest.get("files", []):
        target = app / item["path"]
        if not target.is_file():
            mismatches.append({"path": item["path"], "error": "missing"})
        elif sha256_file(target) != item["sha256"]:
            mismatches.append({"path": item["path"], "error": "sha256_mismatch"})
    return {"ok": not mismatches, "checked": len(manifest.get("files", [])),
            "mismatches": mismatches[:20]}


def release_checks(root: Path, *, require_approval: bool, allow_rehearsal: bool,
                   check_ports: bool = True) -> dict:
    identity = load_identity(root)
    app = root / "current" / "app"
    checks: list[dict] = []

    def add(name: str, ok: bool, detail=None):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    commit = identity.get("release_commit")
    add("identity.release_commit", commit == RELEASE_COMMIT,
        {"expected": RELEASE_COMMIT, "actual": commit})
    add("identity.tested_runtime", identity.get("tested_runtime_commit") == "001f93472",
        identity.get("tested_runtime_commit"))
    add("identity.product_tree_sha256",
        identity.get("product_tree_sha256") == EXPECTED_PRODUCT_TREE_SHA256,
        identity.get("product_tree_sha256"))
    add("app.present", app.is_dir(), str(app))
    if app.is_dir():
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=app, text=True).strip()
        add("app.head_matches_release", head == commit, head)
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], cwd=app, text=True).strip()
        add("app.clean", not dirty, dirty[:500] or "clean")
        add("app.product_tree_matches",
            product_tree_sha256(app, "HEAD") == EXPECTED_PRODUCT_TREE_SHA256,
            product_tree_sha256(app, "HEAD"))
        manifest = check_source_manifest(app)
        add("source_manifest.hashes", manifest["ok"], manifest)
    else:
        add("app.head_matches_release", False, "app missing")
        add("app.clean", False, "app missing")
        add("app.product_tree_matches", False, "app missing")
        add("source_manifest.hashes", False, "app missing")

    env = runtime_env(root)
    audience = env.get("ATOM_DEPLOYMENT_AUDIENCE", "")
    add("audience.single_user", audience == "single_user", audience)
    add("audience.pilot_declared", bool(env.get("ATOM_PILOT_USER_EMAIL")),
        env.get("ATOM_PILOT_USER_EMAIL", ""))
    add("assignment.internal_paths_disabled",
        not truthy(env.get("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS")),
        env.get("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "<unset>"))
    add("assignment.controlled_transport_disabled",
        not truthy(env.get("ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT")),
        env.get("ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT", "<unset>"))
    add("scheduler.disabled", not truthy(env.get("ENABLE_SCHEDULER")),
        env.get("ENABLE_SCHEDULER", "<unset>"))
    add("ingestion_sync.disabled", not truthy(env.get("ENABLE_INGESTION_SYNC")),
        env.get("ENABLE_INGESTION_SYNC", "<unset>"))
    add("microsoft.client_id_present", bool(env.get("MICROSOFT_CLIENT_ID")), "<presence-only>")
    add("microsoft.client_secret_present", bool(env.get("MICROSOFT_CLIENT_SECRET")), "<presence-only>")

    policy_raw = env.get("ATOM_LLM_PROVIDER_POLICY", "")
    policy_ok = False
    policy_summary = {"mode": None, "allowed_providers": [], "preferred": None}
    try:
        policy = json.loads(policy_raw)
        allowed = [str(x) for x in (policy.get("allowed_providers") or [])]
        preferred = policy.get("preferred") or {}
        policy_ok = (
            policy.get("mode") == "selected"
            and bool(allowed)
            and str(preferred.get("provider") or "") in allowed
            and bool(preferred.get("model"))
        )
        policy_summary = {
            "mode": policy.get("mode"),
            "allowed_providers": allowed,
            "preferred": {"provider": preferred.get("provider"),
                          "model": preferred.get("model")},
        }
    except Exception as exc:  # noqa: BLE001
        policy_summary = {"error": f"{type(exc).__name__}: {exc}"}
    add("provider_policy.selected_and_valid", policy_ok, policy_summary)

    data = Path(env.get("ATOM_DATA_DIR", ""))
    office = Path(env.get("ATOM_OFFICE_DIR", ""))
    add("data.absolute_under_root", data.is_absolute() and root in data.parents, str(data))
    add("office.absolute_under_root", office.is_absolute() and root in office.parents, str(office))
    add("data.writable", os.access(data, os.W_OK), str(data))
    add("office.writable", os.access(office, os.W_OK), str(office))
    add("deployment.outbound_scope",
        identity.get("outbound_scope") == "draft_and_approval_only",
        identity.get("outbound_scope"))
    add("deployment.send_not_authorized", identity.get("send_authorized") is False,
        identity.get("send_authorized"))
    add("deployment.topology",
        identity.get("topology") == "one_worker_process_per_assignment",
        identity.get("topology"))

    approval = root / "config" / "APPROVED"
    rehearsal = root / "config" / "REHEARSAL_APPROVED"
    approval_ok = approval.is_file() or (allow_rehearsal and rehearsal.is_file())
    add("approval.present", approval_ok,
        str(approval if approval.is_file() else rehearsal if rehearsal.is_file() else approval))
    if require_approval and not approval_ok:
        checks.append({"name": "approval.required", "ok": False,
                       "detail": "create config/APPROVED after review"})

    api_port = int(env.get("API_PORT", identity.get("api_port", 8071)))
    fe_port = int(env.get("FE_PORT", identity.get("frontend_port", 3130)))
    if check_ports:
        add("ports.api_free", not port_busy(api_port), api_port)
        add("ports.frontend_free", not port_busy(fe_port), fe_port)
    add("frontend.server_present", (root / "current" / "frontend" / "server.js").is_file(),
        str(root / "current" / "frontend" / "server.js"))

    identity_ok = all(c["ok"] for c in checks
                      if not c["name"].startswith("ports."))
    return {"schema": "atom-assignment-release-preflight-1", "ok": identity_ok,
            "checked_at": now(), "root": str(root), "checks": checks,
            "identity": identity}


def stop_pid(pid: int, expected: str, label: str) -> dict:
    result = {"label": label, "pid": pid, "stopped": False}
    try:
        command = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "command="], text=True).strip()
    except subprocess.CalledProcessError:
        result["detail"] = "not_running"
        return result
    if expected and expected not in command:
        result["detail"] = "refused_pid_command_mismatch"
        result["command"] = command[:300]
        return result
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        result["stopped"] = True
        return result
    for _ in range(30):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            result["stopped"] = True
            return result
        time.sleep(0.5)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    result["stopped"] = True
    result["forced"] = True
    return result


def cmd_preflight(args) -> int:
    root = Path(args.root).resolve()
    report = release_checks(root, require_approval=not args.rehearsal,
                            allow_rehearsal=args.rehearsal,
                            check_ports=not args.ignore_running_ports)
    out = Path(args.out) if args.out else root / "run" / "preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out, report)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


def cmd_backup(args) -> int:
    root = Path(args.root).resolve()
    env = runtime_env(root)
    data = Path(env["ATOM_DATA_DIR"])
    out_root = Path(args.out_dir) if args.out_dir else root / "backups"
    label = args.label or "release"
    out = out_root / f"{label}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out.mkdir(parents=True, exist_ok=False)
    db_src = data / "atom.db"
    if not db_src.is_file():
        raise SystemExit(f"REFUSED: missing {db_src}")
    src = sqlite3.connect(f"file:{db_src}?mode=ro", uri=True)
    dst = sqlite3.connect(out / "atom.db")
    try:
        src.backup(dst)
        dst.execute("pragma wal_checkpoint(full)")
    finally:
        dst.close()
        src.close()
    integrity = sqlite3.connect(f"file:{out / 'atom.db'}?mode=ro", uri=True)
    try:
        integrity_ok = integrity.execute("pragma integrity_check").fetchone()[0] == "ok"
        counts = {}
        for table in ("users", "dataset_entries", "goal_runs", "hitl_interventions"):
            try:
                counts[table] = integrity.execute(
                    f"select count(*) from {table}").fetchone()[0]
            except sqlite3.Error:
                counts[table] = None
    finally:
        integrity.close()
    if not integrity_ok:
        raise SystemExit("REFUSED: backup sqlite integrity_check failed")
    for name in ("office", "sheet_datasets", "email_attachments"):
        src_dir = data / name
        if src_dir.is_dir():
            shutil.copytree(src_dir, out / name, symlinks=False)
    if args.include_memory:
        src_dir = data / "atom_memory"
        if src_dir.is_dir():
            shutil.copytree(src_dir, out / "atom_memory", symlinks=False)
    for name in ("byok_config.json", "byok_keys.json", "byok_encryption_key"):
        src_file = data / name
        if src_file.is_file():
            shutil.copy2(src_file, out / name)
            os.chmod(out / name, 0o600)
    cfg = out / "config"
    cfg.mkdir()
    for name in ("env.release", "secrets.env", "RELEASE_IDENTITY.json"):
        src_file = root / "config" / name if name != "RELEASE_IDENTITY.json" else root / name
        if src_file.is_file():
            shutil.copy2(src_file, cfg / name)
            os.chmod(cfg / name, 0o600)
    files = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "BACKUP_MANIFEST.json":
            files[str(path.relative_to(out))] = {
                "sha256": sha256_file(path), "bytes": path.stat().st_size}
    manifest = {
        "schema": "atom-assignment-release-backup-1",
        "created_at": now(),
        "source_data_dir": str(data),
        "label": label,
        "sqlite_backup_api": True,
        "sqlite_integrity_check": integrity_ok,
        "row_counts": counts,
        "config_copied_mode_600": True,
        "memory_included": bool(args.include_memory),
        "memory_note": (
            "atom_memory excluded by default because it is large; pass "
            "--include-memory when a full vector-store snapshot is required"
        ),
        "files": files,
        "newer_user_data_preserved": True,
    }
    atomic_write_json(out / "BACKUP_MANIFEST.json", manifest)
    print(json.dumps({"ok": True, "backup": str(out), "manifest": manifest}, indent=2))
    return 0


def wait_health(base: str, expected_commit: str, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        try:
            last = http_json(base + "/api/health", timeout=5)
            ident = last.get("identity") or {}
            if (last.get("status") in ("healthy", "ok", "degraded")
                    and ident.get("revision") == expected_commit
                    and ident.get("dirty") is False):
                return last
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError(f"health identity not ready: {json.dumps(last)[:1000]}")


def cmd_start(args) -> int:
    root = Path(args.root).resolve()
    env = runtime_env(root)
    pre = release_checks(root, require_approval=not args.rehearsal,
                         allow_rehearsal=args.rehearsal)
    atomic_write_json(root / "run" / "preflight.json", pre)
    if not pre["ok"]:
        print(json.dumps(pre, indent=2))
        return 2
    identity = pre["identity"]
    app = root / "current" / "app"
    backend = app / "backend"
    frontend = root / "current" / "frontend"
    api_port = int(env.get("API_PORT", identity["api_port"]))
    fe_port = int(env.get("FE_PORT", identity["frontend_port"]))
    python_bin = env.get("PYTHON_BIN", sys.executable)
    for name in ("backend", "frontend"):
        pidfile = root / "run" / f"{name}.pid"
        if pidfile.is_file():
            pid = int(pidfile.read_text().strip() or 0)
            if pid and port_busy(api_port if name == "backend" else fe_port):
                print(f"REFUSED: {name} already running pid={pid}")
                return 2
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    run = root / "run"
    run.mkdir(parents=True, exist_ok=True)
    backend_log = open(logs / "backend.log", "ab", buffering=0)
    backend_proc = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "main_api_app:app",
         "--host", "127.0.0.1", "--port", str(api_port)],
        cwd=backend, env=env, stdout=backend_log, stderr=subprocess.STDOUT,
        start_new_session=True)
    (run / "backend.pid").write_text(str(backend_proc.pid) + "\n")
    frontend_log = open(logs / "frontend.log", "ab", buffering=0)
    fe_env = dict(env)
    fe_env.update({"PORT": str(fe_port), "HOSTNAME": "127.0.0.1"})
    frontend_proc = subprocess.Popen(
        ["node", "server.js"], cwd=frontend, env=fe_env,
        stdout=frontend_log, stderr=subprocess.STDOUT, start_new_session=True)
    (run / "frontend.pid").write_text(str(frontend_proc.pid) + "\n")
    try:
        health = wait_health(f"http://127.0.0.1:{api_port}", identity["release_commit"])
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{fe_port}/login", timeout=5)
                break
            except Exception:
                time.sleep(1)
        receipt = {
            "schema": "atom-assignment-release-startup-1",
            "started_at": now(),
            "release_commit": identity["release_commit"],
            "api_port": api_port,
            "frontend_port": fe_port,
            "api_origin": f"http://127.0.0.1:{api_port}",
            "backend_pid": backend_proc.pid,
            "frontend_pid": frontend_proc.pid,
            "health_identity": health.get("identity"),
            "health_status": health.get("status"),
            "audience": env.get("ATOM_DEPLOYMENT_AUDIENCE"),
            "pilot_email": env.get("ATOM_PILOT_USER_EMAIL"),
            "outbound_scope": identity.get("outbound_scope"),
            "controlled_transport": env.get("ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT", "<unset>"),
            "internal_paths": env.get("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS", "<unset>"),
            "topology": identity.get("topology"),
        }
        atomic_write_json(run / "startup_receipt.json", receipt)
        print(json.dumps(receipt, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"START FAILED: {exc}")
        cmd_stop(args)
        return 3


def cmd_stop(args) -> int:
    root = Path(args.root).resolve()
    env = runtime_env(root)
    results = []
    for name, port_key in (("backend", "API_PORT"), ("frontend", "FE_PORT")):
        pidfile = root / "run" / f"{name}.pid"
        if not pidfile.is_file():
            results.append({"label": name, "stopped": True, "detail": "no_pidfile"})
            continue
        try:
            pid = int(pidfile.read_text().strip())
        except ValueError:
            pidfile.unlink(missing_ok=True)
            results.append({"label": name, "stopped": True, "detail": "invalid_pidfile"})
            continue
        expected = "main_api_app:app" if name == "backend" else "server.js"
        results.append(stop_pid(pid, expected, name))
        pidfile.unlink(missing_ok=True)
    report = {"schema": "atom-assignment-release-stop-1", "stopped_at": now(),
              "results": results}
    atomic_write_json(root / "run" / "stop_receipt.json", report)
    print(json.dumps(report, indent=2))
    return 0 if all(r["stopped"] for r in results) else 1


def cmd_status(args) -> int:
    root = Path(args.root).resolve()
    env = runtime_env(root)
    api_port = int(env.get("API_PORT", 8071))
    try:
        health = http_json(f"http://127.0.0.1:{api_port}/api/health")
    except Exception as exc:  # noqa: BLE001
        health = {"error": f"{type(exc).__name__}: {exc}"}
    receipt = root / "run" / "startup_receipt.json"
    report = {"checked_at": now(), "health": health,
              "startup_receipt": json.loads(receipt.read_text()) if receipt.is_file() else None}
    print(json.dumps(report, indent=2))
    return 0 if health.get("status") in ("healthy", "ok", "degraded") else 1


def cmd_rollback(args) -> int:
    root = Path(args.root).resolve()
    previous = root / "previous"
    if not previous.is_symlink():
        raise SystemExit("REFUSED: no previous release link")
    target = previous.resolve()
    previous_identity = json.loads((target / "RELEASE_IDENTITY.json").read_text())
    cmd_stop(args)
    current = root / "current"
    old = current.resolve()
    current.unlink()
    current.symlink_to(target)
    previous.unlink()
    previous.symlink_to(old)
    start_args = argparse.Namespace(root=str(root), rehearsal=True)
    rc = cmd_start(start_args)
    receipt = {
        "schema": "atom-assignment-release-rollback-1",
        "at": now(),
        "from_release": str(old),
        "to_release": str(target),
        "to_release_commit": previous_identity.get("release_commit"),
        "start_rc": rc,
        "database_restored": False,
        "user_data_preserved": True,
    }
    atomic_write_json(root / "run" / "rollback_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))
    return rc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preflight")
    p.add_argument("--out")
    p.add_argument("--rehearsal", action="store_true")
    p.add_argument("--ignore-running-ports", action="store_true")
    p.set_defaults(func=cmd_preflight)
    p = sub.add_parser("start")
    p.add_argument("--rehearsal", action="store_true")
    p.set_defaults(func=cmd_start)
    p = sub.add_parser("stop")
    p.set_defaults(func=cmd_stop)
    p = sub.add_parser("backup")
    p.add_argument("--out-dir")
    p.add_argument("--label")
    p.add_argument("--include-memory", action="store_true")
    p.set_defaults(func=cmd_backup)
    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("rollback")
    p.set_defaults(func=cmd_rollback)
    args = ap.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
