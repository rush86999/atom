#!/usr/bin/env python3
"""One ordinary browser authentication episode for the combined web-auth source.

Product source is frozen at the commit recorded in owner-marker.json. This
harness only starts an isolated world, builds the existing frontend with the
existing heavy gate, drives the real UI in Chromium, and records sanitized
results. Raw credentials/cookies/tokens stay in the private 0700 world.
"""
from __future__ import annotations

import argparse
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
from urllib.parse import urlparse, parse_qs, quote

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

NODE20 = Path("/Users/rushiparikh/.nvm/versions/node/v20.20.2/bin/node")
PY311 = Path("/usr/local/bin/python3.11")
GATE = Path("/private/tmp/atom-agent-cli/run_bounded_test_gate.py")
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
EXPECTED_SOURCE = "3673b07bfc28a9541237a5bebe085c49ad6155ba"
DIST_NAME = ".next-auth-browser-20261109"


def iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def private_open(path: Path, mode: str = "w"):
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    return os.fdopen(fd, mode)


def write_private_json(path: Path, doc) -> None:
    with private_open(path, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")


def free_port(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def listener_pid(port: int):
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()
        return int(out[0]) if out else None
    except Exception:
        return None


def proc_cwd(pid: int):
    try:
        out = subprocess.run(
            ["lsof", "-p", str(pid), "-a", "-d", "cwd"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()
        return out[-1].split()[-1] if out else None
    except Exception:
        return None


def wait_http(url: str, timeout_s: float = 180.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=5, trust_env=False, follow_redirects=True)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def stop_owned(proc: subprocess.Popen | None, name: str, record: dict) -> None:
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
        "pid": proc.pid,
        "terminal": proc.poll() is not None,
        "exit": proc.returncode,
    }


def user_readback(db: Path, email: str) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, onboarding_completed, onboarding_step FROM users "
            "WHERE lower(email)=lower(?) ORDER BY id", (email,)
        ).fetchall()
        total = con.execute(
            "SELECT COUNT(*) FROM users WHERE lower(email)=lower(?)", (email,)
        ).fetchone()[0]
        return {
            "count": int(total),
            "ids": [r[0] for r in rows],
            "onboarding_completed": bool(rows[0][1]) if rows else None,
            "onboarding_step": rows[0][2] if rows else None,
        }
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
    const payload = await decode({ token, secret });
    process.stdout.write(JSON.stringify({
      ok: true,
      id: payload && payload.id,
      backendToken: payload && payload.backendToken,
      exp: payload && payload.exp,
    }));
  } catch {
    process.stdout.write(JSON.stringify({ ok: false }));
  }
});
"""
    env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
    env["PATH"] = str(NODE20.parent) + ":/usr/local/bin:/usr/bin:/bin"
    proc = subprocess.run(
        [str(NODE20), "-e", script],
        cwd=str(frontend), env=env,
        input=json.dumps({"token": cookie_value, "secret": secret}),
        capture_output=True, text=True, timeout=30,
    )
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"ok": False}


class Recorder:
    def __init__(self, frontend_origin: str, backend_origin: str):
        self.frontend = urlparse(frontend_origin)
        self.backend = urlparse(backend_origin)
        self.rows = []
        self.private_urls = []
        self.external = []
        self.failed = []
        self.console_errors = 0
        self.page_errors = 0
        self.by_request = {}

    def allowed(self, url: str) -> bool:
        if url.startswith(("data:", "blob:", "about:")):
            return True
        u = urlparse(url)
        if u.scheme not in ("http", "https", "ws", "wss"):
            return False
        host_ok = u.hostname in ("localhost", "127.0.0.1")
        if not host_ok:
            return False
        return u.port in (self.frontend.port, self.backend.port)

    def route(self, route):
        url = route.request.url
        u = urlparse(url)
        rec = {
            "method": route.request.method,
            "host": u.hostname,
            "port": u.port,
            "path": u.path,
            "scheme": u.scheme,
            "resource_type": route.request.resource_type,
        }
        self.rows.append(rec)
        self.private_urls.append(url[:1000])
        try:
            self.by_request[id(route.request)] = rec
        except Exception:
            pass
        if self.allowed(url):
            route.continue_()
        else:
            self.external.append(rec)
            route.abort()

    def response(self, response):
        rec = self.by_request.get(id(response.request))
        if rec is not None:
            rec["status"] = response.status

    def failed_request(self, request):
        u = urlparse(request.url)
        self.failed.append({"method": request.method, "path": u.path,
                            "port": u.port})

    def console(self, msg):
        if msg.type == "error":
            self.console_errors += 1

    def page_error(self, _exc):
        self.page_errors += 1

    def attach(self, page):
        page.on("response", self.response)
        page.on("requestfailed", self.failed_request)
        page.on("console", self.console)
        page.on("pageerror", self.page_error)

    def counts(self, method=None, path=None, port=None):
        return sum(
            1 for r in self.rows
            if (method is None or r["method"] == method)
            and (path is None or r["path"] == path)
            and (port is None or r["port"] == port)
        )

    def summary(self):
        grouped = {}
        for r in self.rows:
            key = f'{r["method"]} {r["path"]}'
            bucket = grouped.setdefault(key, {"count": 0, "statuses": {}})
            bucket["count"] += 1
            status = r.get("status")
            if status is not None:
                s = str(status)
                bucket["statuses"][s] = bucket["statuses"].get(s, 0) + 1
        return {
            "request_count": len(self.rows),
            "external_requests_aborted": len(self.external),
            "failed_request_count": len(self.failed),
            "console_error_count": self.console_errors,
            "page_error_count": self.page_errors,
            "by_method_path": grouped,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/private/tmp/atom-web-task-project-20261109")
    ap.add_argument("--backend-port", type=int, default=18320)
    ap.add_argument("--frontend-port", type=int, default=18321)
    ap.add_argument("--expected-source", default=EXPECTED_SOURCE)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    frontend = repo / "frontend-nextjs"
    backend = repo / "backend"
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if source != args.expected_source:
        raise SystemExit(f"source mismatch: {source} != {args.expected_source}")
    tracked_dirty = subprocess.check_output(
        ["git", "status", "--short", "--untracked-files=no"], cwd=repo, text=True
    ).strip()
    if tracked_dirty:
        raise SystemExit(f"tracked product source is dirty: {tracked_dirty}")
    for rel in (".env", ".env.local", "backend/.env",
                "frontend-nextjs/.env", "frontend-nextjs/.env.local"):
        if (repo / rel).exists():
            raise SystemExit(f"unexpected env file: {rel}")
    if not NODE20.exists() or not PY311.exists() or not GATE.exists() or not CHROME.exists():
        raise SystemExit("required Node20/Python3.11/gate/Chrome binary missing")
    if shutil.disk_usage(repo).free < 4 * 1024 ** 3:
        raise SystemExit("insufficient disk headroom for heavy gate")
    for port in (args.backend_port, args.frontend_port):
        if not free_port(port):
            raise SystemExit(f"port already in use: {port}")

    public_dir = repo / "docs" / "engineering" / "evidence" / f"web_auth_browser_{source[:9]}"
    if public_dir.exists():
        raise SystemExit(f"public evidence dir already exists: {public_dir}")

    world = Path(tempfile.mkdtemp(
        prefix="root-web-auth-browser-world-20261109-", dir="/private/tmp"))
    os.chmod(world, 0o700)
    public_dir.mkdir(parents=True, exist_ok=False)
    shots = world / "screenshots"
    shots.mkdir()
    os.chmod(shots, 0o700)

    harness_bytes = Path(__file__).read_bytes()
    harness_sha = sha256_bytes(harness_bytes)
    (public_dir / "browser_auth_episode.py").write_bytes(harness_bytes)
    owner = {
        "purpose": "one ordinary browser authentication episode on combined web-auth source",
        "repo": str(repo),
        "source": source,
        "harness_sha256": harness_sha,
        "not_live_database": True,
        "fresh_private_world": str(world),
        "backend_port": args.backend_port,
        "frontend_port": args.frontend_port,
        "dist": str(frontend / DIST_NAME),
        "started_at": iso(),
        "browser": str(CHROME),
        "http_loopback_only": True,
        "testing_runtime": 1,
        "testing_import_phase": 0,
        "testing_note": (
            "TESTING=1 is the runtime value. The wrapper imports the app with "
            "TESTING=0 only so the explicit fresh DATABASE_URL is honored; "
            "TESTING=1 forces the shared backend/test_integration.db."
        ),
    }
    write_private_json(world / "owner-marker.json", owner)
    (public_dir / "owner-marker.json").write_text(json.dumps({
        "source": source,
        "harness_sha256": harness_sha,
        "backend_port": args.backend_port,
        "frontend_port": args.frontend_port,
        "http_loopback_only": True,
        "not_live_database": True,
        "testing_runtime": 1,
        "testing_import_phase": 0,
        "testing_note": owner["testing_note"],
    }, indent=2, sort_keys=True) + "\n")

    backend_env_private = {}
    frontend_env_private = {}
    services = {}
    build_record = {}
    next_env_before = (frontend / "next-env.d.ts").read_bytes() if (frontend / "next-env.d.ts").exists() else None
    dist_path = frontend / DIST_NAME
    dist_bytes = 0
    try:
        if dist_path.exists():
            raise SystemExit(f"owned dist path already exists: {dist_path}")
        backend_origin = f"http://127.0.0.1:{args.backend_port}"
        frontend_origin = f"http://localhost:{args.frontend_port}"

        # ---- optimized build through the existing heavy gate -------------
        build_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        build_env.update({
            "PATH": f"{NODE20.parent}:/usr/local/bin:/usr/bin:/bin",
            "NODE_ENV": "production",
            "NEXT_DIST_DIR": DIST_NAME,
            "NEXT_PUBLIC_API_URL": backend_origin,
            "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
            "NEXTAUTH_URL": frontend_origin,
            "NEXT_TELEMETRY_DISABLED": "1",
            "NODE_OPTIONS": "--max-old-space-size=4096",
            "DATABASE_URL": "postgresql://isolated:unavailable@127.0.0.1:18329/build_only_unavailable",
            "PGHOST": "127.0.0.1",
            "PGPORT": "18329",
            "NPM_CONFIG_OFFLINE": "true",
        })
        build_cmd = [
            "python3", str(GATE), "--cwd", str(frontend), "--profile", "heavy", "--",
            str(NODE20), "node_modules/next/dist/bin/next", "build",
        ]
        build_log = world / "build.private.log"
        started = time.time()
        with private_open(build_log, "wb") as log:
            proc = subprocess.Popen(
                build_cmd, cwd=str(frontend), env=build_env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            )
            (world / "build.pid").write_text(str(proc.pid))
            minimum = shutil.disk_usage(repo).free
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
            "source": source,
            "exit": code,
            "duration_s": round(time.time() - started, 1),
            "resource_pressure_abort": pressure,
            "minimum_free_bytes": minimum,
            "dist": DIST_NAME,
            "build_id": (dist_path / "BUILD_ID").read_text().strip() if (dist_path / "BUILD_ID").exists() else None,
            "next_version": json.loads((frontend / "package.json").read_text())["dependencies"]["next"],
            "node": subprocess.check_output([str(NODE20), "--version"], text=True).strip(),
        }
        write_private_json(world / "build.private.json", build_record)
        if code != 0:
            raise RuntimeError(f"optimized build failed exit={code}")

        # ---- isolated backend -------------------------------------------
        web_secret = secrets.token_urlsafe(48)
        (world / "web-secret.private").write_text(web_secret)
        os.chmod(world / "web-secret.private", 0o600)
        backend_secret = secrets.token_urlsafe(48)
        backend_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        backend_env.update({
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "DATABASE_URL": f"sqlite:///{world}/atom.db",
            "TESTING": "1",
            "ENVIRONMENT": "development",
            "SECRET_KEY": backend_secret,
            "ADMIN_PASSWORD": secrets.token_urlsafe(28),
            "ATOM_PRODUCT_PROFILE": "core",
            "ATOM_DEPLOYMENT_AUDIENCE": "development",
            "ENABLE_SCHEDULER": "false",
            "ENABLE_INGESTION_SYNC": "false",
            "ATOM_LOCAL_ONLY": "true",
            "ATOM_TURN_DECISION_ROUTING": "0",
            "ATOM_DATA_DIR": str(world / "data"),
            "LANCEDB_URI": str(world / "data/atom_memory"),
            "LANCEDB_URI_BASE": str(world / "data/atom_memory"),
            "ATOM_OFFICE_DIR": str(world / "data/office"),
            "ATOM_TASK_LOCK_DIR": str(world / "data/task_locks"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "APP_URL": frontend_origin,
            "ADDITIONAL_ALLOWED_ORIGINS": frontend_origin,
            "ALLOWED_HOSTS": f"localhost,127.0.0.1,127.0.0.1:{args.backend_port},{args.frontend_port},testserver",
            "SMTP_HOST": "smtp.invalid",
            "SMTP_PORT": "587",
            "SMTP_USER": "capture@example.com",
            "SMTP_PASSWORD": secrets.token_urlsafe(24),
            "OLLAMA_BASE_URL": "http://127.0.0.1:18328",
            "PYTHONPATH": f"{world}:{backend}",
        })
        for k in list(backend_env):
            if k.endswith(("_API_KEY", "_ACCESS_TOKEN")) or k.startswith("AWS_"):
                backend_env.pop(k, None)
        backend_env_private = dict(backend_env)
        write_private_json(world / "backend-env.private.json", backend_env_private)
        (world / "data").mkdir(parents=True, exist_ok=True)
        wrapper = world / "recovery_capture_app.py"
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
            "app = main_api_app.app\n"
        )
        os.chmod(wrapper, 0o600)
        backend_log = world / "backend.private.log"
        with private_open(backend_log, "wb") as log:
            backend_proc = subprocess.Popen(
                [str(PY311), "-m", "uvicorn", "recovery_capture_app:app",
                 "--host", "127.0.0.1", "--port", str(args.backend_port)],
                cwd=str(backend), env=backend_env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        (world / "backend.pid").write_text(str(backend_proc.pid))
        services["backend"] = backend_proc.pid
        if not wait_http(f"{backend_origin}/api/health", 180):
            raise RuntimeError("backend health did not become ready")

        # ---- production frontend ----------------------------------------
        frontend_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        frontend_env.update({
            "PATH": f"{NODE20.parent}:/usr/local/bin:/usr/bin:/bin",
            "NODE_ENV": "production",
            "NEXT_DIST_DIR": DIST_NAME,
            "NEXT_PUBLIC_API_URL": backend_origin,
            "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
            "PYTHON_BACKEND_URL": backend_origin,
            "PYTHON_API_SERVICE_BASE_URL": backend_origin,
            "API_BASE_URL": backend_origin,
            "NEXTAUTH_URL": frontend_origin,
            "NEXTAUTH_SECRET": web_secret,
            "JWT_SECRET": "distinct-unused-backend-key",
            "NEXT_PUBLIC_PRODUCT_PROFILE": "core",
            "ATOM_PRODUCT_PROFILE": "core",
            "NEXT_TELEMETRY_DISABLED": "1",
            "DATABASE_URL": "postgresql://isolated:unavailable@127.0.0.1:18329/isolated_unavailable",
            "PGHOST": "127.0.0.1",
            "PGPORT": "18329",
        })
        frontend_env_private = dict(frontend_env)
        write_private_json(world / "frontend-env.private.json", frontend_env_private)
        frontend_log = world / "frontend.private.log"
        with private_open(frontend_log, "wb") as log:
            frontend_proc = subprocess.Popen(
                [str(NODE20), "node_modules/next/dist/bin/next", "start",
                 "--hostname", "127.0.0.1", "--port", str(args.frontend_port)],
                cwd=str(frontend), env=frontend_env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        (world / "frontend.pid").write_text(str(frontend_proc.pid))
        services["frontend"] = frontend_proc.pid
        if not wait_http(f"{frontend_origin}/login", 120):
            raise RuntimeError("frontend login page did not become ready")

        backend_listener = listener_pid(args.backend_port)
        frontend_listener = listener_pid(args.frontend_port)
        owners = {
            "backend_listener_pid": backend_listener,
            "backend_cwd": proc_cwd(backend_listener) if backend_listener else None,
            "frontend_listener_pid": frontend_listener,
            "frontend_cwd": proc_cwd(frontend_listener) if frontend_listener else None,
        }
        if not owners["frontend_cwd"] or not owners["frontend_cwd"].startswith(str(frontend)):
            raise RuntimeError(f"frontend ownership check failed: {owners}")
        if not owners["backend_cwd"] or not owners["backend_cwd"].startswith(str(backend)):
            raise RuntimeError(f"backend ownership check failed: {owners}")
        write_private_json(world / "listener-owners.private.json", owners)

        # ---- fresh browser context and ordinary UI episode --------------
        result = run_browser(
            repo, world, public_dir, shots, backend_origin, frontend_origin,
            args.backend_port, args.frontend_port, source, web_secret,
        )
        result["build"] = build_record
        result["listener_owners"] = owners
        result["services"] = services
        result["source"] = source
        result["harness_sha256"] = harness_sha
        result["completed_at"] = iso()
        write_private_json(world / "result.private.json", result)
        (public_dir / "verification.json").write_text(
            json.dumps(public_view(result), indent=2, sort_keys=True) + "\n")
        print(json.dumps(public_view(result), indent=2, sort_keys=True), flush=True)
        return 0 if result.get("ok") else 1
    except Exception as exc:
        failure = {
            "ok": False,
            "source": source,
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
            "at": iso(),
            "build": build_record,
            "services": services,
        }
        write_private_json(world / "failure.private.json", failure)
        (public_dir / "verification.json").write_text(
            json.dumps({
                "ok": False,
                "source": source,
                "harness_sha256": harness_sha,
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
                "at": iso(),
                "build_exit": build_record.get("exit"),
                "services_started": sorted(services),
            }, indent=2, sort_keys=True) + "\n")
        print(json.dumps(failure, indent=2, sort_keys=True), flush=True)
        return 1
    finally:
        cleanup_services = {}
        stop_owned(locals().get("frontend_proc"), "frontend", cleanup_services)
        stop_owned(locals().get("backend_proc"), "backend", cleanup_services)
        cleanup = {"services": cleanup_services}
        if dist_path.exists():
            dist_bytes = sum(p.stat().st_size for p in dist_path.rglob("*") if p.is_file())
            shutil.rmtree(dist_path, ignore_errors=True)
        cleanup["owned_generated_dist_bytes_removed"] = dist_bytes
        cleanup["dist_absent"] = not dist_path.exists()
        if next_env_before is not None and (frontend / "next-env.d.ts").exists():
            if (frontend / "next-env.d.ts").read_bytes() != next_env_before:
                (frontend / "next-env.d.ts").write_bytes(next_env_before)
                cleanup["next_env_restored"] = True
            else:
                cleanup["next_env_restored"] = False
        cleanup["backend_port_closed"] = free_port(args.backend_port)
        cleanup["frontend_port_closed"] = free_port(args.frontend_port)
        cleanup["private_world_retained"] = str(world)
        write_private_json(world / "cleanup.private.json", cleanup)
        print(json.dumps({"cleanup": cleanup}, indent=2, sort_keys=True), flush=True)


def public_view(result: dict) -> dict:
    keep = {
        "ok", "source", "harness_sha256", "completed_at", "build",
        "fresh_context", "registration", "onboarding", "settings",
        "session", "logout", "signin_login_default", "signin_auth_signin_default",
        "signin_login_deep_link", "db", "browser_network", "cookie",
        "remaining", "limits",
    }
    out = {k: result.get(k) for k in keep if k in result}
    out["private_evidence"] = "retained in 0700 scratch world; not committed"
    return out


def run_browser(repo: Path, world: Path, public_dir: Path, shots: Path,
                backend_origin: str, frontend_origin: str,
                backend_port: int, frontend_port: int,
                source: str, web_secret: str) -> dict:
    stamp = time.strftime("%Y%m%d%H%M%S")
    email = f"web-auth-{stamp}-{secrets.token_hex(3)}@example.com"
    password = f"Scratch-Auth-{secrets.token_urlsafe(18)}!"
    name = "Web Auth Member"
    callback_target = "/settings?a4dl=return20261109"
    recorder = Recorder(frontend_origin, backend_origin)
    out = {
        "ok": False,
        "source": source,
        "synthetic_account_private_only": True,
        "fresh_context": {},
        "registration": {},
        "onboarding": {},
        "settings": {},
        "session": {},
        "logout": {},
        "signin_login_default": {},
        "signin_auth_signin_default": {},
        "signin_login_deep_link": {},
        "db": {},
        "remaining": [],
        "limits": [
            "HTTP loopback only; production build emits Secure cookies accepted by Chromium on loopback.",
            "Google/GitHub/SSO handoff and 2FA live challenge were not exercised.",
            "No provider/model calls, connector consent, sends, spend, or deployment.",
        ],
    }

    def shot(page, name):
        try:
            page.screenshot(path=str(shots / name), full_page=True)
        except Exception:
            pass

    def current_raw(page):
        return page.evaluate("() => localStorage.getItem('auth_token')")

    def fetch_session(context):
        r = context.request.get(f"{frontend_origin}/api/auth/session", timeout=30000)
        try:
            body = r.json()
        except Exception:
            body = None
        return r.status, body

    def session_cookie(context):
        cookies = context.cookies()
        for base in ("__Secure-next-auth.session-token", "next-auth.session-token"):
            parts = [c for c in cookies
                     if c["name"] == base or re.fullmatch(re.escape(base) + r"\.\d+", c["name"])]
            if parts:
                parts.sort(key=lambda c: int(c["name"].rsplit(".", 1)[1])
                           if re.fullmatch(re.escape(base) + r"\.\d+", c["name"]) else -1)
                return base, "".join(c["value"] for c in parts), cookies, parts
        return None, None, cookies, []

    def check_session(page, context, label):
        raw = current_raw(page)
        if not raw:
            raise RuntimeError(f"{label}: no raw auth_token in browser storage")
        cookie_name, cookie_value, cookies, parts = session_cookie(context)
        if not cookie_name or not cookie_value:
            raise RuntimeError(f"{label}: no NextAuth session cookie")
        decoded = decode_session(cookie_value, web_secret, repo / "frontend-nextjs")
        status, sess = fetch_session(context)
        if status != 200 or not isinstance(sess, dict) or not sess.get("user"):
            raise RuntimeError(f"{label}: /api/auth/session did not return a user")
        me = httpx.get(
            f"{backend_origin}/api/auth/me",
            headers={"Authorization": f"Bearer {raw}", "Accept": "application/json"},
            timeout=30000, trust_env=False,
        )
        if me.status_code != 200:
            raise RuntimeError(f"{label}: canonical /api/auth/me status {me.status_code}")
        me_body = me.json()
        session_user_id = sess["user"].get("id")
        session_backend = sess.get("backendToken")
        decoded_backend = decoded.get("backendToken") if decoded.get("ok") else None
        decoded_id = decoded.get("id") if decoded.get("ok") else None
        secure_expected = cookie_name.startswith("__Secure-")
        flags = {
            "name": cookie_name,
            "chunk_count": len(parts),
            "http_only": all(bool(p.get("httpOnly")) for p in parts),
            "secure": all(bool(p.get("secure")) for p in parts),
            "secure_expected_from_cookie_name": secure_expected,
            "same_site": parts[0].get("sameSite") if parts else None,
            "host_only": all(not str(p.get("domain", "")).startswith(".") for p in parts),
            "value_is_not_raw_backend_token": cookie_value != raw,
            "jwe_segment_count": len(cookie_value.split(".")),
            "raw_jwt_segment_count": len(raw.split(".")),
            "transport_scheme": "http",
            "tls_claimed": False,
        }
        checks = {
            "canonical_me_user_id_matches_session_user_id": me_body.get("id") == session_user_id,
            "decoded_sdk_user_id_matches_canonical_me": decoded_id == me_body.get("id"),
            "sdk_session_contains_same_backend_generation": decoded_backend == raw,
            "session_endpoint_contains_same_backend_generation": session_backend == raw if session_backend is not None else None,
            "sdk_cookie_is_encrypted_not_raw": flags["value_is_not_raw_backend_token"] and flags["jwe_segment_count"] >= 4,
            "sdk_cookie_http_only": flags["http_only"],
            "sdk_cookie_secure_matches_cookie_name": flags["secure"] == secure_expected,
            "production_uses_secure_cookie_name": cookie_name == "__Secure-next-auth.session-token",
            "legacy_auth_token_cookie_present": any(c["name"] == "auth_token" and c["value"] == raw for c in cookies),
            "session_not_counted_from_legacy_cookie": bool(session_user_id),
        }
        if not all(v is True for k, v in checks.items() if v is not None):
            raise RuntimeError(f"{label}: session checks failed: {checks}")
        return {
            "status_ok": True,
            "checks": checks,
            "cookie": flags,
            "session_user_id_present": bool(session_user_id),
            "canonical_me_status": me.status_code,
            "session_endpoint_status": status,
        }

    def wait_session_cleared(context, timeout_s=15):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            name, val, cookies, _ = session_cookie(context)
            if not name and not val:
                return True, cookies
            time.sleep(0.5)
        _, _, cookies, _ = session_cookie(context)
        return False, cookies

    def ui_signin(page, context, path, expect_url, callback=None, label=""):
        before_login = recorder.counts("POST", "/api/auth/login", backend_port)
        before_cb = recorder.counts("POST", "/api/auth/callback/credentials", frontend_port)
        url = frontend_origin + path
        if callback is not None:
            url += "?callbackUrl=" + quote(callback, safe="")
        page.goto(url, wait_until="domcontentloaded")
        # Let the Next client router hydrate and expose router.query before a
        # fast automation click; a real user necessarily takes longer.
        if callback is not None:
            page.wait_for_function(
                "() => new URLSearchParams(location.search).get('callbackUrl') !== null",
                timeout=10000,
            )
        page.wait_for_timeout(1200)
        page.locator("#email").fill(email)
        page.locator("#password").fill(password)
        if path == "/login":
            page.get_by_test_id("login-submit-button").click()
        else:
            page.get_by_role("button", name="Sign In", exact=True).click()
        page.wait_for_url(re.compile(re.escape(expect_url) + r"(?:\?.*)?$"), timeout=60000)
        page.wait_for_load_state("domcontentloaded")
        result = check_session(page, context, label)
        result["backend_password_login_delta"] = (
            recorder.counts("POST", "/api/auth/login", backend_port) - before_login)
        result["sdk_callback_delta"] = (
            recorder.counts("POST", "/api/auth/callback/credentials", frontend_port) - before_cb)
        return result

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(CHROME), headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.route("**/*", recorder.route)
        page = context.new_page()
        recorder.attach(page)

        page.goto(frontend_origin + "/auth/signup", wait_until="domcontentloaded")
        storage = page.evaluate(
            "() => ({local: localStorage.length, session: sessionStorage.length})")
        out["fresh_context"] = {
            "cookies_empty": len(context.cookies()) == 0,
            "local_storage_empty": storage["local"] == 0,
            "session_storage_empty": storage["session"] == 0,
        }
        if not all(out["fresh_context"].values()):
            raise RuntimeError(f"browser context was not fresh: {out['fresh_context']}")
        shot(page, "01-signup.png")

        pre_register = user_readback(world / "atom.db", email)
        page.locator("#name").fill(name)
        page.locator("#email").fill(email)
        page.locator("#password").fill(password)
        page.locator("#confirmPassword").fill(password)
        page.get_by_role("button", name="Create Account", exact=True).click()
        page.wait_for_url(re.compile(re.escape(frontend_origin) + r"/dashboard(?:\?.*)?$"),
                          timeout=90000)
        page.get_by_test_id("dashboard-welcome-message").wait_for(timeout=30000)
        shot(page, "02-dashboard-after-registration.png")
        registration_session = check_session(page, context, "after registration")
        post_register = user_readback(world / "atom.db", email)
        out["registration"] = {
            "landed_dashboard": page.url.startswith(frontend_origin + "/dashboard"),
            "backend_register_calls": recorder.counts("POST", "/api/auth/register", backend_port),
            "sdk_callback_calls": recorder.counts("POST", "/api/auth/callback/credentials", frontend_port),
            "db_rows_before": pre_register["count"],
            "db_rows_after": post_register["count"],
            "session": registration_session,
        }
        if out["registration"]["backend_register_calls"] != 1:
            raise RuntimeError("registration did not use exactly one backend register call")
        if pre_register["count"] != 0 or post_register["count"] != 1:
            raise RuntimeError("registration did not create exactly one user row")

        # Ordinary supported onboarding through visible controls only.
        onboarding = {"present": False}
        try:
            page.get_by_text("Welcome to Atom", exact=True).wait_for(timeout=20000)
            onboarding["present"] = True
            shot(page, "03-onboarding-welcome.png")
            dlg = page.get_by_role("dialog")
            dlg.get_by_role("button", name="Next", exact=True).click()
            page.wait_for_timeout(500)
            page.locator("#role").fill("QA")
            page.locator("#goal").fill("Verify the web authentication session")
            dlg.get_by_role("button", name="Next", exact=True).click()
            page.wait_for_timeout(1200)
            dlg.get_by_role("button", name="Next", exact=True).click()
            page.wait_for_timeout(800)
            dlg.get_by_role("button", name="Start Automating", exact=True).click()
            page.get_by_text("Welcome to Atom", exact=True).wait_for(state="hidden", timeout=30000)
            onboarding["completed_via_ui"] = True
        except PWTimeout:
            onboarding["completed_via_ui"] = False
            onboarding["note"] = "wizard not present or did not close"
        status_raw = page.evaluate(
            """async () => {
              const t = localStorage.getItem('auth_token');
              const r = await fetch('/api/onboarding/status', {headers: t ? {Authorization: 'Bearer ' + t} : {}});
              return {status: r.status, body: await r.json().catch(() => null)};
            }""")
        body = status_raw.get("body") or {}
        data = body.get("data") if isinstance(body, dict) else None
        onboarding["status_endpoint"] = status_raw.get("status")
        onboarding["server_completed"] = bool(
            (data or {}).get("onboarding_completed", body.get("onboarding_completed")))
        if onboarding["present"] and not onboarding["server_completed"]:
            raise RuntimeError("onboarding did not persist completion through the UI")
        out["onboarding"] = onboarding

        # Protected Settings + exact path/query + reload.
        page.goto(frontend_origin + callback_target, wait_until="domcontentloaded")
        page.get_by_role("heading", name="Settings", exact=True).wait_for(timeout=30000)
        first_url = page.url
        shot(page, "04-settings.png")
        page.reload(wait_until="domcontentloaded")
        page.get_by_role("heading", name="Settings", exact=True).wait_for(timeout=30000)
        reload_url = page.url
        reload_session = check_session(page, context, "after Settings reload")
        out["settings"] = {
            "url_path_query_exact": first_url == frontend_origin + callback_target,
            "reload_url_path_query_exact": reload_url == frontend_origin + callback_target,
            "reload_session": reload_session,
        }
        if not (out["settings"]["url_path_query_exact"] and
                out["settings"]["reload_url_path_query_exact"]):
            raise RuntimeError("protected Settings path/query changed")

        # UI logout.
        page.goto(frontend_origin + "/dashboard", wait_until="domcontentloaded")
        page.get_by_test_id("dashboard-welcome-message").wait_for(timeout=30000)
        page.get_by_test_id("dashboard-user-profile-button").hover()
        page.get_by_test_id("dashboard-logout-button").click()
        page.wait_for_url(re.compile(re.escape(frontend_origin) + r"/auth/signin(?:\?.*)?$"),
                          timeout=45000)
        cleared, cookies_after = wait_session_cleared(context)
        logout_session_status, logout_session = fetch_session(context)
        local_after = page.evaluate(
            "() => ({auth: localStorage.getItem('auth_token'), mark: localStorage.getItem('atom_explicit_logout')})")
        out["logout"] = {
            "landed_auth_signin": True,
            "sdk_cookie_cleared": cleared,
            "session_endpoint_user_absent": not (isinstance(logout_session, dict) and logout_session.get("user")),
            "session_endpoint_status": logout_session_status,
            "raw_token_cleared": local_after.get("auth") is None,
            "explicit_logout_marker": local_after.get("mark") == "1",
            "nextauth_session_cookie_names_remaining": [
                c["name"] for c in cookies_after if "session-token" in c["name"]
            ],
        }
        if not (cleared and out["logout"]["session_endpoint_user_absent"] and
                out["logout"]["raw_token_cleared"]):
            raise RuntimeError("UI logout did not clear the actual session")

        # Same-account sign-in through /login (default destination).
        out["signin_login_default"] = ui_signin(
            page, context, "/login", frontend_origin + "/dashboard",
            label="login default")
        if out["signin_login_default"]["backend_password_login_delta"] != 1:
            raise RuntimeError("login default did not perform exactly one backend password login")
        shot(page, "05-login-default-dashboard.png")

        # Logout, then /auth/signin (default destination).
        page.get_by_test_id("dashboard-user-profile-button").hover()
        page.get_by_test_id("dashboard-logout-button").click()
        page.wait_for_url(re.compile(re.escape(frontend_origin) + r"/auth/signin(?:\?.*)?$"),
                          timeout=45000)
        wait_session_cleared(context)
        out["signin_auth_signin_default"] = ui_signin(
            page, context, "/auth/signin", frontend_origin + "/dashboard",
            label="auth/signin default")
        if out["signin_auth_signin_default"]["backend_password_login_delta"] != 1:
            raise RuntimeError("auth/signin default did not perform exactly one backend password login")
        shot(page, "06-auth-signin-dashboard.png")

        # Logout, then protected deep link -> /login callback -> exact path+query.
        page.get_by_test_id("dashboard-user-profile-button").hover()
        page.get_by_test_id("dashboard-logout-button").click()
        page.wait_for_url(re.compile(re.escape(frontend_origin) + r"/auth/signin(?:\?.*)?$"),
                          timeout=45000)
        wait_session_cleared(context)
        page.goto(frontend_origin + callback_target, wait_until="domcontentloaded")
        page.wait_for_url(re.compile(re.escape(frontend_origin) + r"/login\?.*"), timeout=30000)
        callback = parse_qs(urlparse(page.url).query).get("callbackUrl", [None])[0]
        out["signin_login_deep_link"]["callback_seen_before_login"] = callback
        if callback != callback_target:
            raise RuntimeError(f"callback target changed: {callback!r}")
        out["signin_login_deep_link"].update(ui_signin(
            page, context, "/login", frontend_origin + callback_target,
            callback=callback, label="login deep link"))
        out["signin_login_deep_link"]["landed_exact_path_query"] = (
            page.url == frontend_origin + callback_target)
        out["signin_login_deep_link"]["callback_after_login"] = callback
        if not out["signin_login_deep_link"]["landed_exact_path_query"]:
            raise RuntimeError("deep-link login did not land on the exact path/query")
        page.get_by_role("heading", name="Settings", exact=True).wait_for(timeout=30000)
        shot(page, "07-deep-link-settings.png")

        # Final DB readback and network summary.
        final_rows = user_readback(world / "atom.db", email)
        registration_ids = post_register["ids"]
        final_ids = final_rows["ids"]
        out["db"] = {
            "synthetic_user_row_count": final_rows["count"],
            "duplicate_user_rows": max(0, final_rows["count"] - 1),
            "onboarding_completed": final_rows["onboarding_completed"],
            "onboarding_step": final_rows["onboarding_step"],
            "same_user_id_as_registration": (
                len(registration_ids) == 1 and registration_ids == final_ids),
            "registration_id_count": len(registration_ids),
            "final_id_count": len(final_ids),
        }
        write_private_json(world / "user-identity.private.json", {
            "registration_ids": registration_ids,
            "final_ids": final_ids,
        })
        if final_rows["count"] != 1 or registration_ids != final_ids:
            raise RuntimeError("final DB readback does not show exactly the same one user row")
        out["browser_network"] = recorder.summary()
        if recorder.external:
            raise RuntimeError("browser attempted an external request despite the block")
        out["session"] = registration_session
        out["cookie"] = registration_session["cookie"]
        out["ok"] = True
        browser.close()
    # Private comparison only; public view omits these values.
    write_private_json(world / "account.private.json", {
        "email": email, "password": password, "name": name,
        "callback_target": callback_target,
        "web_secret_sha256": sha256_bytes(web_secret.encode()),
    })
    return out


if __name__ == "__main__":
    sys.exit(main())
