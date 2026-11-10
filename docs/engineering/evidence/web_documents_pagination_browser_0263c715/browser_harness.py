#!/usr/bin/env python3
"""Prepared ordinary-browser pagination episode — DO NOT RUN until root review.

One controlled full-main-app + Next + Chromium lifecycle on the frozen
document-pagination source. It creates an ordinary account through the real
signup/onboarding UI, seeds a synthetic 130-row document fixture through the
real LanceDB handler (fixture seeding, not 130 ordinary uploads), and checks
the ordinary Documents surface and public API:

  page 1: 100 newest (129..030)
  Next:   30 oldest  (029..000)
  Previous: back to 100 newest
  reload: page 1 again with total 130 (the current UI intentionally resets
          offset on mount; this harness does not claim offset persistence)

No execution is performed by preparing this file. The caller must review the
resource plan and explicitly run it later.

Modes:
  --mode optimized  requires >= 4 GiB free; existing heavy gate builds a
                    unique Next dist, then `next start`.
  --mode dev        requires >= 2 GiB free; no build; unique Next dist via
                    `next dev` (bounded web runtime).

Raw tokens, cookies, env, DB and logs stay in a fresh 0700 world. Only safe
URLs/statuses/counts/synthetic dataset ids go to the safe result.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

NODE20 = Path("/Users/rushiparikh/.nvm/versions/node/v20.20.2/bin/node")
PY311 = Path("/usr/local/bin/python3.11")
GATE = Path("/private/tmp/atom-agent-cli/run_bounded_test_gate.py")
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
PRODUCT_SOURCE = "c4bc1d4b623eb56d54491e4c79052885b5950cff"
EVIDENCE_SOURCE = "1605d7713116f1552d23e6a8288fd3902ce9468a"
DIST_NAME = ".next-doc-pagination-20261110"
DEV_DIST_NAME = ".next-doc-pagination-dev-20261110"
PRODUCT_PATHS = (
    "backend/api/document_routes.py",
    "backend/core/lancedb_handler.py",
    "frontend-nextjs/pages/documents.tsx",
)

EXPECTED_PAGE1 = [f"w1-doc-{i:03d}" for i in range(129, 29, -1)]
EXPECTED_PAGE2 = [f"w1-doc-{i:03d}" for i in range(29, -1, -1)]
FIXTURE_PREFIXES = ("w1-doc-", "w2-doc-", "shared-doc-")
SESSION_COOKIE_NAMES = ("__Secure-next-auth.session-token", "next-auth.session-token")


def select_session_cookie(cookies: list[dict]) -> dict:
    """Select a raw or chunked SDK session cookie without parsing the
    dot-containing base name as a chunk index.

    A chunk is matched only by an exact regex suffix ``.<digits>``. The raw
    base name (which itself contains ``next-auth.session-token``) is never
    passed to ``int``. Chunks are joined in numeric suffix order.
    """
    for name in SESSION_COOKIE_NAMES:
        raw = None
        chunks = []
        for cookie in cookies:
            cookie_name = cookie.get("name") or ""
            if cookie_name == name:
                raw = cookie
                continue
            match = re.fullmatch(re.escape(name) + r"\.(\d+)", cookie_name)
            if match:
                chunks.append((int(match.group(1)), cookie))
        if chunks:
            chunks.sort(key=lambda item: item[0])
            indices = [index for index, _ in chunks]
            return {
                "name": name,
                "value": "".join(cookie["value"] for _, cookie in chunks),
                "parts": [cookie for _, cookie in chunks],
                "chunk_indices": indices,
                "kind": "chunked",
                "complete": indices == list(range(len(indices))),
            }
        if raw is not None:
            return {
                "name": name,
                "value": raw["value"],
                "parts": [raw],
                "chunk_indices": [],
                "kind": "raw",
                "complete": True,
            }
    return {"name": None, "value": None, "parts": [], "chunk_indices": [],
            "kind": None, "complete": False}


def evaluate_checks(obs: dict) -> dict:
    """Pure acceptance evaluation for the browser observations.

    Every value used as a claim is required to be exactly True/expected.
    ``None`` is unknown and fails the required check; it is never coerced to
    a passing boolean. Lists are compared in exact order.
    """
    checks: dict = {}

    def req(name, value, expected=True):
        if value is None:
            checks[name] = None
            return False
        ok = value == expected
        checks[name] = ok
        return ok

    def req_exact(name, actual, expected):
        if actual is None:
            checks[name] = None
            return False
        ok = list(actual) == list(expected)
        checks[name] = ok
        return ok

    fresh = obs.get("fresh") or {}
    req("fresh_cookies_empty", fresh.get("cookies_empty"))
    req("fresh_local_storage_empty", fresh.get("local_storage_empty"))
    req("fresh_session_storage_empty", fresh.get("session_storage_empty"))

    req("documents_page_status", obs.get("documents_page_status"), 200)

    environment = obs.get("environment") or {}
    req("environment_database_url_scratch", environment.get("database_url_scratch"))
    req("environment_atom_data_dir_scratch", environment.get("atom_data_dir_scratch"))
    req("environment_lancedb_base_scratch", environment.get("lancedb_base_scratch"))

    signup = obs.get("signup") or {}
    req("signup_landed_dashboard", signup.get("landed_dashboard"))
    req("signup_register_calls", signup.get("register_calls"), 1)
    req("signup_one_user_row", signup.get("user_rows"), 1)
    req("signup_workspace_bound", signup.get("workspace_bound"))

    onboarding = obs.get("onboarding") or {}
    req("onboarding_present", onboarding.get("present"))
    req("onboarding_completed_via_ui", onboarding.get("completed_via_ui"))

    seed = obs.get("seed") or {}
    req("seed_authorized_130", seed.get("authorized"), 130)
    req("seed_foreign_7", seed.get("foreign"), 7)
    req("seed_shared_3", seed.get("shared"), 3)
    req("seed_via_real_handler", seed.get("via_handler"))

    for label, expected, first, last, count, has_more, next_disabled, prev_disabled in (
        ("page1", EXPECTED_PAGE1, "w1-doc-129", "w1-doc-030", 100, True, False, True),
        ("page2", EXPECTED_PAGE2, "w1-doc-029", "w1-doc-000", 30, False, True, False),
    ):
        page = obs.get(label) or {}
        ids = page.get("dom_ids")
        api_ids = page.get("api_ids")
        req(f"{label}_api_status", page.get("api_status"), 200)
        req(f"{label}_total", page.get("total"), 130)
        req(f"{label}_count", page.get("count"), count)
        req(f"{label}_has_more", page.get("has_more"), has_more)
        req(f"{label}_next_offset_present", page.get("next_offset_present"), has_more)
        if has_more:
            req(f"{label}_next_offset", page.get("next_offset"), 100)
        req_exact(f"{label}_dom_exact", ids, expected)
        req_exact(f"{label}_api_exact", api_ids, expected)
        req_exact(f"{label}_dom_matches_api", ids, api_ids)
        req(f"{label}_first", ids[0] if ids else None, first)
        req(f"{label}_last", ids[-1] if ids else None, last)
        req(f"{label}_card_count", page.get("card_count"), count)
        req(f"{label}_foreign_ids", page.get("foreign_ids"), [])
        req(f"{label}_unknown_ids", page.get("unknown_ids"), [])
        req(f"{label}_duplicate_ids", page.get("duplicate_ids"), [])
        req(f"{label}_next_disabled", page.get("next_disabled"), next_disabled)
        req(f"{label}_previous_disabled", page.get("previous_disabled"), prev_disabled)

    previous = obs.get("previous") or {}
    req("previous_api_status", previous.get("api_status"), 200)
    req("previous_total", previous.get("total"), 130)
    req("previous_count", previous.get("count"), 100)
    req_exact("previous_dom_exact", previous.get("dom_ids"), EXPECTED_PAGE1)
    req_exact("previous_api_exact", previous.get("api_ids"), EXPECTED_PAGE1)
    req_exact("previous_dom_matches_api", previous.get("dom_ids"), previous.get("api_ids"))
    req("previous_next_disabled", previous.get("next_disabled"), False)
    req("previous_previous_disabled", previous.get("previous_disabled"), True)

    reload = obs.get("reload") or {}
    req("reload_api_status", reload.get("api_status"), 200)
    req("reload_total", reload.get("total"), 130)
    req("reload_count", reload.get("count"), 100)
    req_exact("reload_dom_exact", reload.get("dom_ids"), EXPECTED_PAGE1)
    req_exact("reload_api_exact", reload.get("api_ids"), EXPECTED_PAGE1)
    req("reload_next_disabled", reload.get("next_disabled"), False)
    req("reload_previous_disabled", reload.get("previous_disabled"), True)

    beyond = obs.get("beyond") or {}
    req("beyond_api_status", beyond.get("api_status"), 200)
    req("beyond_count", beyond.get("count"), 0)
    req("beyond_total", beyond.get("total"), 130)
    req("beyond_has_more", beyond.get("has_more"), False)
    req("beyond_next_offset_present", beyond.get("next_offset_present"), False)

    canonical = obs.get("canonical") or {}
    req("canonical_session_status", canonical.get("session_status"), 200)
    req("canonical_me_status", canonical.get("me_status"), 200)
    for key in (
        "me_matches_session", "me_matches_db", "decoded_sdk_matches_me",
        "same_backend_generation", "sdk_cookie_encrypted_not_raw",
        "sdk_cookie_http_only", "one_user_row", "workspace_bound",
        "workspace_ids_match",
    ):
        req(f"canonical_{key}", canonical.get(key))

    store = obs.get("store") or {}
    req("store_rows_unchanged", store.get("unchanged"))
    req("store_path_scoped", store.get("path_scoped"))
    req("store_foreign_rows", store.get("foreign_rows"), 7)
    req("store_shared_rows", store.get("shared_rows"), 3)

    failures = sorted(name for name, value in checks.items() if value is not True)
    return {"passed": not failures, "checks": checks, "failures": failures}


def iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def private_open(path: Path, mode: str = "w"):
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    return os.fdopen(fd, mode)


def write_private_json(path: Path, doc) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with private_open(tmp, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def free_port(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def listener_pid(port: int):
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return int(out[0]) if out else None
    except Exception:
        return None


def proc_cwd(pid: int):
    try:
        out = subprocess.run(
            ["lsof", "-p", str(pid), "-a", "-d", "cwd"],
            capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return out[-1].split()[-1] if out else None
    except Exception:
        return None


def wait_http(url: str, timeout_s: float = 180.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=5, trust_env=False, follow_redirects=True).status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def stop_owned(proc, name: str, record: dict) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), 15)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), 9)
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
    record.setdefault("services", {})[name] = {
        "pid": proc.pid, "terminal": proc.poll() is not None,
        "exit": proc.returncode,
    }


def db_user(db: Path, email: str) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id,email,workspace_id,tenant_id,hashed_password "
            "FROM users WHERE lower(email)=lower(?) ORDER BY id",
            (email,)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return {"count": len(rows), "rows": rows, "total_users": int(total)}
    finally:
        con.close()


def decode_session(cookie_value: str, secret: str, frontend: Path) -> dict:
    script = r"""
const { decode } = require('next-auth/jwt');
let data = '';
process.stdin.on('data', (d) => data += d);
process.stdin.on('end', async () => {
  try {
    const { token, secret } = JSON.parse(data);
    const p = await decode({ token, secret });
    process.stdout.write(JSON.stringify({
      ok: true, id: p && p.id, backendToken: p && p.backendToken
    }));
  } catch {
    process.stdout.write(JSON.stringify({ ok: false }));
  }
});
"""
    env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
    env["PATH"] = str(NODE20.parent) + ":/usr/local/bin:/usr/bin:/bin"
    proc = subprocess.run(
        [str(NODE20), "-e", script], cwd=str(frontend), env=env,
        input=json.dumps({"token": cookie_value, "secret": secret}),
        capture_output=True, text=True, timeout=30)
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"ok": False}


class Recorder:
    def __init__(self):
        self.requests = []
        self.responses = []

    def route(self, route):
        from urllib.parse import urlparse
        u = urlparse(route.request.url)
        self.requests.append({
            "method": route.request.method, "path": u.path,
            "resource_type": route.request.resource_type,
        })
        if u.hostname in ("localhost", "127.0.0.1"):
            route.continue_()
        else:
            route.abort()

    def response(self, response):
        from urllib.parse import urlparse
        self.responses.append({
            "method": response.request.method,
            "path": urlparse(response.url).path,
            "status": response.status,
        })

    def attach(self, page):
        page.on("response", self.response)

    def counts(self, method, path):
        return sum(1 for r in self.requests
                   if r["method"] == method and r["path"] == path)


def seed_store(base: Path, workspace: str, tenant: str,
               prefix: str, count: int, user_id: str) -> dict:
    from core.lancedb_handler import LanceDBHandler

    handler = LanceDBHandler(
        db_path=str(base / workspace),
        workspace_id=workspace,
        tenant_id=tenant or "default",
    )
    handler._ensure_db()
    table = handler.create_table("documents", vector_size=384)
    records = []
    for i in range(count):
        doc_id = f"{prefix}-{i:03d}"
        created = (
            datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
            + datetime.timedelta(minutes=i)
        ).isoformat()
        records.append({
            "id": doc_id,
            "user_id": user_id,
            "workspace_id": workspace,
            "text": f"synthetic document fixture {doc_id}",
            "source": "document-pagination-browser-fixture",
            "metadata": json.dumps({"title": doc_id}),
            "created_at": created,
            "vector": [0.0] * 384,
            "freshness_status": "fresh",
            "source_modified_at": "",
            "source_url": "",
        })
    table.add(list(reversed(records)))  # non-chronological insertion
    return {
        "workspace": workspace,
        "count": handler.count_documents("documents"),
        "path": str(base / workspace),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/private/tmp/atom-web-task-project-20261109")
    ap.add_argument("--backend-port", type=int, default=18390)
    ap.add_argument("--frontend-port", type=int, default=18391)
    ap.add_argument("--mode", choices=("optimized", "dev"), default="optimized")
    ap.add_argument("--expected-product-source", default=PRODUCT_SOURCE)
    ap.add_argument("--expected-evidence-source", default=EVIDENCE_SOURCE)
    ap.add_argument("--execute", action="store_true",
                    help="required explicit switch; without it the harness exits before side effects")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    frontend, backend = repo / "frontend-nextjs", repo / "backend"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    tracked_dirty = subprocess.check_output(
        ["git", "status", "--short", "--untracked-files=no"], cwd=repo, text=True).strip()
    if tracked_dirty:
        raise SystemExit(f"tracked product source is dirty: {tracked_dirty}")
    for rel in (".env", ".env.local", "backend/.env",
                "frontend-nextjs/.env", "frontend-nextjs/.env.local"):
        if (repo / rel).exists():
            raise SystemExit(f"unexpected env file: {rel}")
    if not all(p.exists() for p in (NODE20, PY311, GATE, CHROME)):
        raise SystemExit("required Node20/Python3.11/gate/Chrome binary missing")
    # The product bytes must match the frozen repair commit; later evidence-only
    # commits are allowed as HEAD.
    diff = subprocess.run(
        ["git", "diff", "--quiet", args.expected_product_source, head, "--",
         *PRODUCT_PATHS], cwd=repo)
    if diff.returncode != 0:
        raise SystemExit("product bytes do not match the frozen document repair source")
    required = (4 if args.mode == "optimized" else 2) * 1024 ** 3
    free = shutil.disk_usage(repo).free
    if free < required:
        raise SystemExit(
            f"insufficient disk for --mode {args.mode}: {free} < {required}")
    for port in (args.backend_port, args.frontend_port):
        if not free_port(port):
            raise SystemExit(f"port already in use: {port}")

    if not args.execute:
        print(json.dumps({
            "prepared": True, "executed": False, "mode": args.mode,
            "head": head, "product_source": args.expected_product_source,
            "free_bytes": free, "required_bytes": required,
            "ports": [args.backend_port, args.frontend_port],
            "note": "Pass --execute only after root reviews the harness and resource plan.",
        }, indent=2))
        return 0

    world = Path(tempfile.mkdtemp(prefix="root-web-doc-pagination-world-", dir="/private/tmp"))
    os.chmod(world, 0o700)
    shots = world / "screenshots"
    shots.mkdir()
    os.chmod(shots, 0o700)
    harness_sha = sha256_bytes(Path(__file__).read_bytes())
    safe = {
        "schema_version": 1,
        "kind": "ordinary_browser_document_pagination",
        "head": head,
        "product_source": args.expected_product_source,
        "harness_sha256": harness_sha,
        "mode": args.mode,
        "started_at": iso(),
        "checked": {},
        "raw_auth_material_published": False,
    }
    private = {"world": str(world), "ports": [args.backend_port, args.frontend_port]}
    # Bind the harness process itself to the private scratch world before any
    # core import (fixture seeding uses core.lancedb_handler).
    os.environ.update({
        "TESTING": "0",
        "DATABASE_URL": f"sqlite:///{world}/atom.db",
        "ATOM_DATA_DIR": str(world / "data"),
        "LANCEDB_URI": str(world / "data/atom_memory"),
        "LANCEDB_URI_BASE": str(world / "data/atom_memory"),
        "SECRET_KEY": secrets.token_urlsafe(48),
        "ENVIRONMENT": "development",
        "ENABLE_SCHEDULER": "false",
        "ATOM_LOCAL_ONLY": "true",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    })
    safe["environment"] = {
        "database_url_scratch": os.environ.get("DATABASE_URL") == f"sqlite:///{world}/atom.db",
        "atom_data_dir_scratch": os.environ.get("ATOM_DATA_DIR") == str(world / "data"),
        "lancedb_base_scratch": os.environ.get("LANCEDB_URI_BASE") == str(world / "data/atom_memory"),
        "testing_harness_process": os.environ.get("TESTING"),
        "browser_launched": False,
    }

    owner = {
        "purpose": "ordinary Documents browser pagination on frozen document source",
        "repo": str(repo), "head": head,
        "product_source": args.expected_product_source,
        "harness_sha256": harness_sha, "fresh_private_world": str(world),
        "http_loopback_only": True, "controlled_fixture_seed": True,
        "fixture_seed_rows": 130, "not_live_database": True,
        "testing_runtime": 1, "testing_import_phase": 0,
    }
    write_private_json(world / "owner-marker.json", owner)

    frontend_origin = f"http://localhost:{args.frontend_port}"
    backend_origin = f"http://127.0.0.1:{args.backend_port}"
    dist_path = frontend / (DIST_NAME if args.mode == "optimized" else DEV_DIST_NAME)
    next_env_before = ((frontend / "next-env.d.ts").read_bytes()
                       if (frontend / "next-env.d.ts").exists() else None)
    services = {}
    backend_proc = frontend_proc = None
    build_record = {}
    try:
        if dist_path.exists():
            raise RuntimeError(f"owned dist path already exists: {dist_path}")

        if args.mode == "optimized":
            build_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
            build_env.update({
                "PATH": f"{NODE20.parent}:/usr/local/bin:/usr/bin:/bin",
                "NODE_ENV": "production", "NEXT_DIST_DIR": DIST_NAME,
                "NEXT_PUBLIC_API_URL": backend_origin, "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
                "NEXTAUTH_URL": frontend_origin, "NEXT_TELEMETRY_DISABLED": "1",
                "NODE_OPTIONS": "--max-old-space-size=4096",
                "DATABASE_URL": "postgresql://isolated:unavailable@127.0.0.1:18399/build_only_unavailable",
                "PGHOST": "127.0.0.1", "PGPORT": "18399", "NPM_CONFIG_OFFLINE": "true",
            })
            cmd = ["python3", str(GATE), "--cwd", str(frontend), "--profile", "heavy", "--",
                   str(NODE20), "node_modules/next/dist/bin/next", "build"]
            started = time.time()
            with private_open(world / "build.private.log", "wb") as log:
                proc = subprocess.Popen(cmd, cwd=str(frontend), env=build_env,
                                        stdout=log, stderr=subprocess.STDOUT,
                                        start_new_session=True)
                minimum = free
                pressure = False
                while proc.poll() is None:
                    minimum = min(minimum, shutil.disk_usage(repo).free)
                    if minimum < 1250 * 1024 ** 2:
                        pressure = True
                        try:
                            os.killpg(os.getpgid(proc.pid), 15)
                        except Exception:
                            pass
                        break
                    time.sleep(3)
                code = proc.wait()
            build_record = {
                "mode": "optimized", "exit": code,
                "duration_s": round(time.time() - started, 1),
                "resource_pressure_abort": pressure,
                "minimum_free_bytes": minimum, "dist": DIST_NAME,
                "build_id": (dist_path / "BUILD_ID").read_text().strip()
                if (dist_path / "BUILD_ID").exists() else None,
                "next_version": json.loads((frontend / "package.json").read_text())["dependencies"]["next"],
                "node": subprocess.check_output([str(NODE20), "--version"], text=True).strip(),
            }
            write_private_json(world / "build.private.json", build_record)
            if code != 0:
                raise RuntimeError(f"optimized build failed exit={code}")

        backend_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        backend_env.update({
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "DATABASE_URL": f"sqlite:///{world}/atom.db", "TESTING": "1",
            "ENVIRONMENT": "development", "SECRET_KEY": secrets.token_urlsafe(48),
            "ADMIN_PASSWORD": secrets.token_urlsafe(28),
            "ATOM_PRODUCT_PROFILE": "core", "ATOM_DEPLOYMENT_AUDIENCE": "development",
            "ENABLE_SCHEDULER": "false", "ENABLE_INGESTION_SYNC": "false",
            "ATOM_LOCAL_ONLY": "true", "ATOM_TURN_DECISION_ROUTING": "0",
            "ATOM_DATA_DIR": str(world / "data"),
            "LANCEDB_URI": str(world / "data/atom_memory"),
            "LANCEDB_URI_BASE": str(world / "data/atom_memory"),
            "ATOM_OFFICE_DIR": str(world / "data/office"),
            "ATOM_TASK_LOCK_DIR": str(world / "data/task_locks"),
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "APP_URL": frontend_origin, "ADDITIONAL_ALLOWED_ORIGINS": frontend_origin,
            "ALLOWED_HOSTS": f"localhost,127.0.0.1,127.0.0.1:{args.backend_port},{args.frontend_port},testserver",
            "SMTP_HOST": "smtp.invalid", "SMTP_PORT": "587",
            "SMTP_USER": "capture@example.com",
            "SMTP_PASSWORD": secrets.token_urlsafe(24),
            "OLLAMA_BASE_URL": "http://127.0.0.1:18398",
            "PYTHONPATH": f"{world}:{backend}",
        })
        for k in list(backend_env):
            if k.endswith(("_API_KEY", "_ACCESS_TOKEN")) or k.startswith("AWS_"):
                backend_env.pop(k, None)
        write_private_json(world / "backend-env.private.json", backend_env)
        (world / "data").mkdir(parents=True, exist_ok=True)
        wrapper = world / "document_capture_app.py"
        wrapper.write_text(
            "import json, os\n"
            "from pathlib import Path\n"
            "root = Path(__file__).parent\n"
            "os.environ['TESTING'] = '0'\n"
            "import main_api_app\n"
            "os.environ['TESTING'] = '1'\n"
            "import core.auth_endpoints as recovery\n"
            "def capture(*args):\n"
            "    with (root / 'mail.private.jsonl').open('a') as out:\n"
            "        out.write(json.dumps(args) + '\\n')\n"
            "    return True\n"
            "recovery.send_smtp_email = capture\n"
            "app = main_api_app.app\n")
        os.chmod(wrapper, 0o600)
        with private_open(world / "backend.private.log", "wb") as log:
            backend_proc = subprocess.Popen(
                [str(PY311), "-m", "uvicorn", "document_capture_app:app",
                 "--host", "127.0.0.1", "--port", str(args.backend_port)],
                cwd=str(backend), env=backend_env, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True)
        services["backend"] = backend_proc.pid
        if not wait_http(f"{backend_origin}/api/health", 180):
            raise RuntimeError("backend health did not become ready")

        web_secret = secrets.token_urlsafe(48)
        (world / "web-secret.private").write_text(web_secret)
        os.chmod(world / "web-secret.private", 0o600)
        frontend_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        frontend_env.update({
            "PATH": f"{NODE20.parent}:/usr/local/bin:/usr/bin:/bin",
            "NODE_ENV": "production" if args.mode == "optimized" else "development",
            "NEXT_DIST_DIR": DIST_NAME if args.mode == "optimized" else DEV_DIST_NAME,
            "NEXT_PUBLIC_API_URL": backend_origin, "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
            "PYTHON_BACKEND_URL": backend_origin, "PYTHON_API_SERVICE_BASE_URL": backend_origin,
            "API_BASE_URL": backend_origin, "NEXTAUTH_URL": frontend_origin,
            "NEXTAUTH_SECRET": web_secret, "JWT_SECRET": "distinct-unused-backend-key",
            "NEXT_PUBLIC_PRODUCT_PROFILE": "core", "ATOM_PRODUCT_PROFILE": "core",
            "NEXT_TELEMETRY_DISABLED": "1",
            "DATABASE_URL": "postgresql://isolated:unavailable@127.0.0.1:18399/isolated_unavailable",
            "PGHOST": "127.0.0.1", "PGPORT": "18399",
        })
        write_private_json(world / "frontend-env.private.json", frontend_env)
        next_cmd = ([str(NODE20), "node_modules/next/dist/bin/next", "dev",
                     "--hostname", "127.0.0.1", "--port", str(args.frontend_port)]
                    if args.mode == "dev" else
                    [str(NODE20), "node_modules/next/dist/bin/next", "start",
                     "--hostname", "127.0.0.1", "--port", str(args.frontend_port)])
        with private_open(world / "frontend.private.log", "wb") as log:
            frontend_proc = subprocess.Popen(
                next_cmd, cwd=str(frontend), env=frontend_env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        services["frontend"] = frontend_proc.pid
        if not wait_http(f"{frontend_origin}/login", 240 if args.mode == "dev" else 180):
            raise RuntimeError("frontend login page did not become ready")

        owners = {
            "backend_listener_pid": listener_pid(args.backend_port),
            "frontend_listener_pid": listener_pid(args.frontend_port),
            "backend_cwd": proc_cwd(listener_pid(args.backend_port)) if listener_pid(args.backend_port) else None,
            "frontend_cwd": proc_cwd(listener_pid(args.frontend_port)) if listener_pid(args.frontend_port) else None,
        }
        if not owners["backend_cwd"] or not owners["backend_cwd"].startswith(str(backend)):
            raise RuntimeError(f"backend ownership failed: {owners}")
        if not owners["frontend_cwd"] or not owners["frontend_cwd"].startswith(str(frontend)):
            raise RuntimeError(f"frontend ownership failed: {owners}")
        write_private_json(world / "listener-owners.private.json", owners)

        # Seed through the real handler only after the ordinary signup created
        # the canonical user/workspace.
        email = f"doc-pagination-{secrets.token_hex(4)}@example.com"
        password = secrets.token_urlsafe(18)
        name = "Document Pagination"
        recorder = Recorder()

        def api(page, path: str) -> dict:
            out = page.evaluate(
                """async (p) => {
                    const r = await fetch(p, {credentials: 'same-origin'});
                    let b = null;
                    try { b = await r.json(); } catch {}
                    return {status: r.status, body: b};
                }""", path)
            return out

        def session_cookie(context):
            cookies = context.cookies()
            selected = select_session_cookie(cookies)
            return (selected["name"], selected["value"], cookies,
                    selected["parts"])

        def checkpoint(name: str) -> None:
            safe["phase"] = name
            safe.setdefault("checkpointed_phases", []).append(name)
            write_private_json(world / f"safe-checkpoint-{name}.private.json", safe)

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=str(CHROME), headless=True)
            safe["environment"]["browser_launched"] = True
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.route("**/*", recorder.route)
            page = context.new_page()
            page.set_default_timeout(180000)
            recorder.attach(page)

            try:
                obs = {}
                page.goto(frontend_origin + "/auth/signup", wait_until="domcontentloaded")
                storage = page.evaluate(
                    "() => ({local: localStorage.length, session: sessionStorage.length})")
                obs["fresh"] = {
                    "cookies_empty": len(context.cookies()) == 0,
                    "local_storage_empty": storage["local"] == 0,
                    "session_storage_empty": storage["session"] == 0,
                }
                safe["observations"] = obs
                checkpoint("fresh")
                if not all(v is True for v in obs["fresh"].values()):
                    raise RuntimeError(f"browser context was not fresh: {obs['fresh']}")
                page.screenshot(path=str(shots / "01-signup.png"), full_page=True)

                page.locator("#name").fill(name)
                page.locator("#email").fill(email)
                page.locator("#password").fill(password)
                page.locator("#confirmPassword").fill(password)
                page.get_by_role("button", name="Create Account", exact=True).click()
                page.wait_for_url(re.compile(re.escape(frontend_origin) + r"/dashboard(?:\?.*)?$"),
                                  timeout=120000)
                page.get_by_test_id("dashboard-welcome-message").wait_for(timeout=30000)
                user = db_user(world / "atom.db", email)
                obs["signup"] = {
                    "landed_dashboard": page.url.startswith(frontend_origin + "/dashboard"),
                    "register_calls": recorder.counts("POST", "/api/auth/register"),
                    "user_rows": user["count"],
                    "workspace_bound": bool(user["rows"] and user["rows"][0][2]),
                }
                safe["observations"] = obs
                checkpoint("signup")
                if not (obs["signup"]["landed_dashboard"] and
                        obs["signup"]["register_calls"] == 1 and
                        obs["signup"]["user_rows"] == 1 and
                        obs["signup"]["workspace_bound"]):
                    raise RuntimeError(f"ordinary signup state failed: {obs['signup']}")
                page.screenshot(path=str(shots / "02-dashboard.png"), full_page=True)

                onboarding = {"present": False, "completed_via_ui": False}
                try:
                    page.get_by_text("Welcome to Atom", exact=True).wait_for(timeout=20000)
                    onboarding["present"] = True
                    dlg = page.get_by_role("dialog")
                    dlg.get_by_role("button", name="Next", exact=True).click()
                    page.wait_for_timeout(500)
                    page.locator("#role").fill("QA")
                    page.locator("#goal").fill("Verify document pagination")
                    dlg.get_by_role("button", name="Next", exact=True).click()
                    page.wait_for_timeout(1200)
                    dlg.get_by_role("button", name="Next", exact=True).click()
                    page.wait_for_timeout(800)
                    dlg.get_by_role("button", name="Start Automating", exact=True).click()
                    page.get_by_text("Welcome to Atom", exact=True).wait_for(state="hidden",
                                                                           timeout=30000)
                    onboarding["completed_via_ui"] = True
                except PWTimeout:
                    onboarding["completed_via_ui"] = False
                obs["onboarding"] = onboarding
                safe["observations"] = obs
                checkpoint("onboarding")
                if not (onboarding["present"] and onboarding["completed_via_ui"]):
                    raise RuntimeError(f"onboarding did not complete through the UI: {onboarding}")

                user_id, workspace_id, tenant_id = (
                    user["rows"][0][0], user["rows"][0][2], user["rows"][0][3])
                os.environ.update({
                    "TESTING": "0",
                    "DATABASE_URL": f"sqlite:///{world}/atom.db",
                    "ATOM_DATA_DIR": str(world / "data"),
                    "LANCEDB_URI": str(world / "data/atom_memory"),
                    "LANCEDB_URI_BASE": str(world / "data/atom_memory"),
                    "SECRET_KEY": secrets.token_urlsafe(48),
                    "ENVIRONMENT": "development",
                    "ENABLE_SCHEDULER": "false",
                    "ATOM_LOCAL_ONLY": "true",
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                })
                if str(backend) not in sys.path:
                    sys.path.insert(0, str(backend))
                fixture = {
                    "authorized": seed_store(world / "data/atom_memory", workspace_id,
                                             tenant_id, "w1-doc", 130, user_id),
                    "foreign": seed_store(world / "data/atom_memory",
                                          f"ws-doc-foreign-{secrets.token_hex(4)}",
                                          tenant_id, "w2-doc", 7, user_id),
                    "shared": seed_store(world / "data/atom_memory", "default_shared",
                                         tenant_id, "shared-doc", 3, user_id),
                }
                obs["seed"] = {
                    "authorized": fixture["authorized"]["count"],
                    "foreign": fixture["foreign"]["count"],
                    "shared": fixture["shared"]["count"],
                    "via_handler": True,
                    "authorized_workspace": fixture["authorized"]["workspace"],
                }
                safe["observations"] = obs
                safe["fixture"] = {
                    "authorized_count": obs["seed"]["authorized"],
                    "foreign_count": obs["seed"]["foreign"],
                    "shared_count": obs["seed"]["shared"],
                    "authorized_workspace": fixture["authorized"]["workspace"],
                    "seeding": "direct real LanceDBHandler.add of synthetic rows; NOT 130 ordinary UI uploads or semantic extraction",
                }
                checkpoint("seed")
                if not (obs["seed"]["authorized"] == 130 and
                        obs["seed"]["foreign"] == 7 and
                        obs["seed"]["shared"] == 3):
                    raise RuntimeError(f"fixture seeding failed: {obs['seed']}")

                documents_response = page.goto(frontend_origin + "/documents", wait_until="domcontentloaded")
                safe["urls"] = {
                    "documents_page": "/documents",
                    "api_page0": "/api/documents?limit=100&offset=0",
                    "api_page1": "/api/documents?limit=100&offset=100",
                    "api_page0_beyond": "/api/documents?limit=100&offset=200",
                }
                obs["environment"] = {
                    "database_url_scratch": safe["environment"]["database_url_scratch"],
                    "atom_data_dir_scratch": safe["environment"]["atom_data_dir_scratch"],
                    "lancedb_base_scratch": safe["environment"]["lancedb_base_scratch"],
                }
                obs["documents_page_status"] = (documents_response.status
                                                if documents_response else None)
                safe["http_status"] = {
                    "documents_page": obs["documents_page_status"],
                }
                page.get_by_role("heading", name="Your Documents", exact=True).wait_for(timeout=30000)
                page.get_by_test_id("documents-range").wait_for(timeout=60000)

                def card_titles() -> list[str]:
                    return page.locator("div.grid.gap-4 > div").evaluate_all(
                        "(cards) => cards.map(c => (c.querySelector('h3')?.textContent || '').trim())")

                def api_page(offset: int) -> dict:
                    out = api(page, f"/api/documents?limit=100&offset={offset}")
                    body = out.get("body") or {}
                    data = body.get("data") if isinstance(body, dict) else None
                    meta = body.get("metadata") if isinstance(body, dict) else None
                    ids = [d.get("id") for d in data] if isinstance(data, list) else []
                    return {
                        "status": out["status"],
                        "ids": ids,
                        "total": (meta or {}).get("total"),
                        "has_more": (meta or {}).get("has_more"),
                        "next_offset": (meta or {}).get("next_offset"),
                        "next_offset_present": isinstance(meta, dict) and "next_offset" in meta,
                    }

                def observe_at(offset: int) -> dict:
                    cards = card_titles()
                    api_state = api_page(offset)
                    return {
                        "dom_ids": cards,
                        "api_ids": api_state["ids"],
                        "api_status": api_state["status"],
                        "total": api_state["total"],
                        "count": len(api_state["ids"]),
                        "has_more": api_state["has_more"],
                        "next_offset": api_state["next_offset"],
                        "next_offset_present": api_state["next_offset_present"],
                        "card_count": len(cards),
                        "foreign_ids": [i for i in cards if i.startswith(("w2-doc-", "shared-doc-"))],
                        "unknown_ids": [i for i in cards
                                        if not i.startswith(FIXTURE_PREFIXES)
                                        or (i.startswith("w1-doc-") and i not in EXPECTED_PAGE1 + EXPECTED_PAGE2)],
                        "duplicate_ids": sorted({i for i in cards if cards.count(i) > 1}),
                        "next_disabled": page.get_by_test_id("documents-next").is_disabled(),
                        "previous_disabled": page.get_by_test_id("documents-previous").is_disabled(),
                    }

                obs["page1"] = observe_at(0)
                safe["http_status"]["api_page0"] = obs["page1"]["api_status"]
                safe["observations"] = obs
                checkpoint("page1")
                if not (obs["page1"]["api_status"] == 200 and
                        obs["page1"]["total"] == 130 and
                        obs["page1"]["count"] == 100):
                    raise RuntimeError(f"page 1 API state failed: {obs['page1']}")
                page.screenshot(path=str(shots / "03-documents-page1.png"), full_page=True)

                page.get_by_test_id("documents-next").click()
                page.wait_for_function(
                    "() => (document.querySelector('[data-testid=\"documents-page\"]')?.textContent || '').includes('Page 2 of 2')",
                    timeout=60000,
                )
                obs["page2"] = observe_at(100)
                safe["http_status"]["api_page1"] = obs["page2"]["api_status"]
                safe["observations"] = obs
                checkpoint("page2")
                if not (obs["page2"]["api_status"] == 200 and
                        obs["page2"]["total"] == 130 and
                        obs["page2"]["count"] == 30):
                    raise RuntimeError(f"page 2 API state failed: {obs['page2']}")
                page.screenshot(path=str(shots / "04-documents-page2.png"), full_page=True)

                page.get_by_test_id("documents-previous").click()
                page.wait_for_function(
                    "() => (document.querySelector('[data-testid=\"documents-page\"]')?.textContent || '').includes('Page 1 of 2')",
                    timeout=60000,
                )
                obs["previous"] = observe_at(0)
                safe["observations"] = obs
                checkpoint("previous")

                page.reload(wait_until="domcontentloaded")
                page.get_by_test_id("documents-range").wait_for(timeout=60000)
                obs["reload"] = observe_at(0)
                safe["http_status"]["api_reload"] = obs["reload"]["api_status"]
                safe["observations"] = obs
                checkpoint("reload")
                page.screenshot(path=str(shots / "05-documents-reload.png"), full_page=True)

                beyond = api_page(200)
                safe["http_status"]["api_page0_beyond"] = beyond["status"]
                obs["beyond"] = {
                    "api_status": beyond["status"],
                    "count": len(beyond["ids"]),
                    "total": beyond["total"],
                    "has_more": beyond["has_more"],
                    "next_offset_present": beyond["next_offset_present"],
                }
                safe["observations"] = obs
                checkpoint("beyond")

                raw = page.evaluate("() => localStorage.getItem('auth_token')")
                cookie_name, cookie_value, cookies, parts = session_cookie(context)
                decoded = decode_session(cookie_value, web_secret, frontend) if cookie_value else {"ok": False}
                session = api(page, "/api/auth/session")
                me_resp = None
                if raw:
                    me_resp = httpx.get(
                        f"{backend_origin}/api/auth/me",
                        headers={"Authorization": f"Bearer {raw}", "Accept": "application/json"},
                        timeout=30000, trust_env=False,
                    )
                me_body = me_resp.json() if me_resp is not None and me_resp.status_code == 200 else {}
                session_body = session.get("body") or {}
                session_user = (session_body.get("user") or {}) if isinstance(session_body, dict) else {}
                obs["canonical"] = {
                    "session_status": session.get("status"),
                    "me_status": me_resp.status_code if me_resp is not None else None,
                    "me_matches_session": (me_body.get("id") == session_user.get("id")
                                           if me_body and session_user else None),
                    "me_matches_db": (me_body.get("id") == user_id) if me_body else None,
                    "decoded_sdk_matches_me": (decoded.get("id") == me_body.get("id")
                                               if decoded.get("ok") and me_body else None),
                    "same_backend_generation": (decoded.get("backendToken") == raw
                                                if decoded.get("ok") and raw else None),
                    "sdk_cookie_encrypted_not_raw": (cookie_value != raw and
                                                     len(cookie_value.split(".")) >= 4
                                                     if cookie_value and raw else None),
                    "sdk_cookie_http_only": (all(bool(c.get("httpOnly")) for c in parts)
                                             if parts else None),
                    "one_user_row": user["count"] == 1,
                    "workspace_bound": bool(workspace_id),
                    "workspace_ids_match": (workspace_id == fixture["authorized"]["workspace"]),
                }
                from core.lancedb_handler import LanceDBHandler
                after_handler = LanceDBHandler(
                    db_path=str(world / "data/atom_memory" / workspace_id),
                    workspace_id=workspace_id, tenant_id=tenant_id or "default",
                )
                after_count = after_handler.count_documents("documents")
                obs["store"] = {
                    "unchanged": after_count == 130,
                    "path_scoped": fixture["authorized"]["path"].startswith(
                        str(world / "data/atom_memory")),
                    "foreign_rows": fixture["foreign"]["count"],
                    "shared_rows": fixture["shared"]["count"],
                }
                safe["observations"] = obs
                checkpoint("canonical")

                evaluation = evaluate_checks(obs)
                safe["checks"] = evaluation["checks"]
                safe["failures"] = evaluation["failures"]
                checkpoint("final")
                if not evaluation["passed"]:
                    raise RuntimeError(f"browser pagination checks failed: {evaluation['failures']}")
                safe["ok"] = True
            except Exception as exc:
                failure_capture = {"screenshot_ok": False}
                try:
                    page.screenshot(path=str(shots / "failure.png"), full_page=True)
                    failure_capture["screenshot_ok"] = True
                except Exception as shot_exc:
                    failure_capture["screenshot_error"] = type(shot_exc).__name__
                safe["failure_capture"] = failure_capture
                write_private_json(world / "failure-checkpoint.private.json", {
                    "phase": safe.get("phase"),
                    "observations": safe.get("observations"),
                    "checks": safe.get("checks"),
                    "failure_capture": failure_capture,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:600],
                })
                raise
            finally:
                try:
                    browser.close()
                except Exception as close_exc:
                    safe["browser_close_error"] = type(close_exc).__name__


        safe["build"] = build_record or {
            "mode": "dev", "exit": None,
            "note": "development main-web runtime; no optimized build claimed",
        }
        safe["limits"] = [
            "130 synthetic rows were seeded directly through the real LanceDB handler; this is not 130 ordinary uploads or a semantic-extraction proof.",
            "HTTP loopback only; no TLS or deployed-production-transport claim.",
            "Controlled local app/issuer-free document fixture; no live DB/provider/model/embedding/download.",
            "The Documents UI intentionally fetches offset 0 on mount; reload shows page 1 with total 130 and does not claim offset persistence.",
            "No concurrent-write snapshot guarantee; ordering is created_at string desc then opaque id desc.",
        ]
        safe["completed_at"] = iso()
        safe["services"] = services
        write_private_json(world / "result.private.json", safe)
        print(json.dumps(safe, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        capture = safe.get("failure_capture") or {}
        failure = {
            "ok": False, "head": head, "product_source": args.expected_product_source,
            "harness_sha256": harness_sha, "mode": args.mode, "at": iso(),
            "phase": safe.get("phase"),
            "error_type": type(exc).__name__, "error": str(exc)[:600],
            "observations": safe.get("observations"),
            "checks": safe.get("checks"),
            "failures": safe.get("failures"),
            "failure_capture": capture,
            "failure_screenshot": ("screenshots/failure.png"
                                   if capture.get("screenshot_ok") else None),
            "screenshot_unknown": not capture.get("screenshot_ok"),
            "services": services,
        }
        write_private_json(world / "failure.private.json", failure)
        print(json.dumps(failure, indent=2, sort_keys=True))
        return 1
    finally:
        cleanup = {"errors": []}
        for name, proc in (("frontend", locals().get("frontend_proc")),
                           ("backend", locals().get("backend_proc"))):
            try:
                stop_owned(proc, name, cleanup)
            except Exception as stop_exc:
                cleanup["errors"].append(f"stop_{name}:{type(stop_exc).__name__}")
        dist_bytes = 0
        try:
            if dist_path.exists():
                dist_bytes = sum(p.stat().st_size for p in dist_path.rglob("*") if p.is_file())
                shutil.rmtree(dist_path, ignore_errors=True)
            cleanup["owned_generated_dist_bytes_removed"] = dist_bytes
            cleanup["dist_absent"] = not dist_path.exists()
        except Exception as dist_exc:
            cleanup["errors"].append(f"dist_cleanup:{type(dist_exc).__name__}")
            cleanup["dist_absent"] = not dist_path.exists()
        try:
            if next_env_before is not None and (frontend / "next-env.d.ts").exists():
                if (frontend / "next-env.d.ts").read_bytes() != next_env_before:
                    (frontend / "next-env.d.ts").write_bytes(next_env_before)
                    cleanup["next_env_restored"] = True
        except Exception as env_exc:
            cleanup["errors"].append(f"next_env_restore:{type(env_exc).__name__}")
        cleanup["backend_port_closed"] = free_port(args.backend_port)
        cleanup["frontend_port_closed"] = free_port(args.frontend_port)
        cleanup["ports_closed"] = (
            cleanup["backend_port_closed"] and cleanup["frontend_port_closed"])
        cleanup["private_world_retained"] = str(world)
        try:
            write_private_json(world / "cleanup.private.json", cleanup)
        except Exception as cleanup_exc:
            cleanup["errors"].append(f"cleanup_write:{type(cleanup_exc).__name__}")
        print(json.dumps({"cleanup": cleanup}, indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.path.insert(0, "/private/tmp/atom-web-task-project-20261109/backend")
    raise SystemExit(main())
