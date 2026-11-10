#!/usr/bin/env python3
"""Targeted ordinary password-recovery episode on the repaired auth source.

Signed-out UI forgot-password -> private captured mail -> ordinary reset link
in Chromium -> UI reset -> old password refused -> new password sign-in with
the real NextAuth SDK session. Raw mail/code/passwords/tokens remain in a
0700 scratch world. No product code is edited here.
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
from urllib.parse import urlparse, parse_qs

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

NODE20 = Path("/Users/rushiparikh/.nvm/versions/node/v20.20.2/bin/node")
PY311 = Path("/usr/local/bin/python3.11")
GATE = Path("/private/tmp/atom-agent-cli/run_bounded_test_gate.py")
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
EXPECTED_SOURCE = "f9ef079c2a2805dc1a92b91a94a9ff2a82bd9b1b"
DIST_NAME = ".next-recovery-reset-20261109"


def iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def private_open(path: Path, mode="w"):
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
        out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return int(out[0]) if out else None
    except Exception:
        return None


def proc_cwd(pid: int):
    try:
        out = subprocess.run(["lsof", "-p", str(pid), "-a", "-d", "cwd"],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return out[-1].split()[-1] if out else None
    except Exception:
        return None


def wait_http(url: str, timeout_s=180.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=5, trust_env=False, follow_redirects=True).status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def stop_owned(proc, name, record):
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
        "pid": proc.pid, "terminal": proc.poll() is not None, "exit": proc.returncode,
    }


def user_rows(db: Path, email: str) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id, hashed_password FROM users WHERE lower(email)=lower(?) ORDER BY id",
            (email,)).fetchall()
        return {"count": len(rows), "ids": [r[0] for r in rows],
                "hashes": [r[1] for r in rows]}
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
    process.stdout.write(JSON.stringify({ ok: true, id: p && p.id, backendToken: p && p.backendToken }));
  } catch {
    process.stdout.write(JSON.stringify({ ok: false }));
  }
});
"""
    env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
    env["PATH"] = str(NODE20.parent) + ":/usr/local/bin:/usr/bin:/bin"
    proc = subprocess.run([str(NODE20), "-e", script], cwd=str(frontend), env=env,
                          input=json.dumps({"token": cookie_value, "secret": secret}),
                          capture_output=True, text=True, timeout=30)
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {"ok": False}


class Recorder:
    def __init__(self, frontend_origin, backend_origin):
        f, b = urlparse(frontend_origin), urlparse(backend_origin)
        self.frontend_port, self.backend_port = f.port, b.port
        self.rows, self.private_urls, self.external, self.failed = [], [], [], []
        self.console_errors = self.page_errors = 0
        self.by_request = {}

    def allowed(self, url):
        if url.startswith(("data:", "blob:", "about:")):
            return True
        u = urlparse(url)
        return u.scheme in ("http", "https", "ws", "wss") and \
            u.hostname in ("localhost", "127.0.0.1") and \
            u.port in (self.frontend_port, self.backend_port)

    def route(self, route):
        u = urlparse(route.request.url)
        rec = {"method": route.request.method, "path": u.path,
               "port": u.port, "resource_type": route.request.resource_type}
        self.rows.append(rec)
        self.private_urls.append(route.request.url[:1000])
        try:
            self.by_request[id(route.request)] = rec
        except Exception:
            pass
        if self.allowed(route.request.url):
            route.continue_()
        else:
            self.external.append(rec)
            route.abort()

    def response(self, response):
        rec = self.by_request.get(id(response.request))
        if rec is not None:
            rec["status"] = response.status

    def failed_request(self, request):
        self.failed.append({"method": request.method, "path": urlparse(request.url).path})

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

    def counts(self, method=None, path=None):
        return sum(1 for r in self.rows
                   if (method is None or r["method"] == method) and (path is None or r["path"] == path))

    def summary(self):
        grouped = {}
        for r in self.rows:
            if "/_next/static/" in r["path"] or "/_next/data/" in r["path"]:
                continue
            key = f'{r["method"]} {r["path"]}'
            item = grouped.setdefault(key, {"count": 0, "statuses": {}})
            item["count"] += 1
            if r.get("status") is not None:
                item["statuses"][str(r["status"])] = item["statuses"].get(str(r["status"]), 0) + 1
        return {"request_count": len(self.rows), "external_requests_aborted": len(self.external),
                "failed_request_count": len(self.failed), "console_error_count": self.console_errors,
                "page_error_count": self.page_errors, "by_method_path": grouped}


def capture_reset_link(mail_path: Path, frontend_origin: str, timeout_s=30.0):
    deadline = time.monotonic() + timeout_s
    pattern = re.compile(re.escape(frontend_origin) + r"/auth/reset-password\?token=[A-Za-z0-9_\-]+")
    while time.monotonic() < deadline:
        if mail_path.exists():
            for line in mail_path.read_text(errors="replace").splitlines():
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                text = json.dumps(item)
                match = pattern.search(text)
                if match:
                    return match.group(0)
        time.sleep(0.5)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/private/tmp/atom-web-task-project-20261109")
    ap.add_argument("--backend-port", type=int, default=18340)
    ap.add_argument("--frontend-port", type=int, default=18341)
    ap.add_argument("--expected-source", default=EXPECTED_SOURCE)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    frontend, backend = repo / "frontend-nextjs", repo / "backend"
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if source != args.expected_source:
        raise SystemExit(f"source mismatch: {source} != {args.expected_source}")
    if subprocess.check_output(["git", "status", "--short", "--untracked-files=no"],
                               cwd=repo, text=True).strip():
        raise SystemExit("tracked product source is dirty")
    for rel in (".env", ".env.local", "backend/.env", "frontend-nextjs/.env.local"):
        if (repo / rel).exists():
            raise SystemExit(f"unexpected env file: {rel}")
    if not all(p.exists() for p in (NODE20, PY311, GATE, CHROME)):
        raise SystemExit("required executable missing")
    if shutil.disk_usage(repo).free < 4 * 1024 ** 3:
        raise SystemExit("insufficient disk headroom for heavy gate")
    for port in (args.backend_port, args.frontend_port):
        if not free_port(port):
            raise SystemExit(f"port already in use: {port}")

    public_dir = repo / "docs" / "engineering" / "evidence" / f"web_recovery_reset_{source[:9]}"
    if public_dir.exists():
        raise SystemExit(f"public evidence dir already exists: {public_dir}")
    world = Path(tempfile.mkdtemp(prefix="root-web-recovery-reset-world-", dir="/private/tmp"))
    os.chmod(world, 0o700)
    public_dir.mkdir(parents=True, exist_ok=False)
    shots = world / "screenshots"
    shots.mkdir()
    os.chmod(shots, 0o700)
    harness_bytes = Path(__file__).read_bytes()
    harness_sha = sha256_bytes(harness_bytes)
    (public_dir / "browser_recovery_reset.py").write_bytes(harness_bytes)

    source_files = [
        "frontend-nextjs/middleware.ts",
        "frontend-nextjs/pages/auth/forgot-password.tsx",
        "frontend-nextjs/pages/auth/reset-password.tsx",
        "frontend-nextjs/pages/auth/signin.tsx",
        "frontend-nextjs/pages/api/auth/forgot-password.ts",
        "frontend-nextjs/pages/api/auth/reset-password.ts",
        "frontend-nextjs/lib/backendAuth.ts",
        "frontend-nextjs/lib/backend-credentials.ts",
        "frontend-nextjs/pages/api/auth/[...nextauth].ts",
        "frontend-nextjs/lib/web-auth-config.ts",
        "frontend-nextjs/next.config.js",
        "backend/core/auth.py",
        "backend/core/auth_endpoints.py",
        "backend/core/database.py",
        "backend/main_api_app.py",
        "backend/core/models.py",
    ]

    owner = {
        "purpose": "targeted signed-out password recovery and SDK sign-in episode",
        "repo": str(repo), "source": source, "harness_sha256": harness_sha,
        "fresh_private_world": str(world), "not_live_database": True,
        "http_loopback_only": True, "testing_runtime": 1, "testing_import_phase": 0,
        "started_at": iso(),
    }
    write_private_json(world / "owner-marker.json", owner)

    dist_path = frontend / DIST_NAME
    next_env_before = (frontend / "next-env.d.ts").read_bytes() if (frontend / "next-env.d.ts").exists() else None
    build_record = {}
    services = {}
    try:
        backend_origin = f"http://127.0.0.1:{args.backend_port}"
        frontend_origin = f"http://localhost:{args.frontend_port}"

        build_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        build_env.update({
            "PATH": f"{NODE20.parent}:/usr/local/bin:/usr/bin:/bin",
            "NODE_ENV": "production", "NEXT_DIST_DIR": DIST_NAME,
            "NEXT_PUBLIC_API_URL": backend_origin, "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
            "NEXTAUTH_URL": frontend_origin, "NEXT_TELEMETRY_DISABLED": "1",
            "NODE_OPTIONS": "--max-old-space-size=4096",
            "DATABASE_URL": "postgresql://isolated:unavailable@127.0.0.1:18349/build_only_unavailable",
            "PGHOST": "127.0.0.1", "PGPORT": "18349", "NPM_CONFIG_OFFLINE": "true",
        })
        build_cmd = ["python3", str(GATE), "--cwd", str(frontend), "--profile", "heavy", "--",
                     str(NODE20), "node_modules/next/dist/bin/next", "build"]
        started = time.time()
        with private_open(world / "build.private.log", "wb") as log:
            proc = subprocess.Popen(build_cmd, cwd=str(frontend), env=build_env,
                                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
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
            "source": source, "exit": code, "duration_s": round(time.time() - started, 1),
            "resource_pressure_abort": pressure, "minimum_free_bytes": minimum,
            "dist": DIST_NAME,
            "build_id": (dist_path / "BUILD_ID").read_text().strip() if (dist_path / "BUILD_ID").exists() else None,
            "next_version": json.loads((frontend / "package.json").read_text())["dependencies"]["next"],
            "node": subprocess.check_output([str(NODE20), "--version"], text=True).strip(),
        }
        write_private_json(world / "build.private.json", build_record)
        if code != 0:
            raise RuntimeError(f"optimized build failed exit={code}")

        web_secret = secrets.token_urlsafe(48)
        (world / "web-secret.private").write_text(web_secret)
        os.chmod(world / "web-secret.private", 0o600)
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
            "SMTP_USER": "capture@example.com", "SMTP_PASSWORD": secrets.token_urlsafe(24),
            "OLLAMA_BASE_URL": "http://127.0.0.1:18348",
            "PYTHONPATH": f"{world}:{backend}",
        })
        for k in list(backend_env):
            if k.endswith(("_API_KEY", "_ACCESS_TOKEN")) or k.startswith("AWS_"):
                backend_env.pop(k, None)
        write_private_json(world / "backend-env.private.json", backend_env)
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
        with private_open(world / "backend.private.log", "wb") as log:
            backend_proc = subprocess.Popen(
                [str(PY311), "-m", "uvicorn", "recovery_capture_app:app",
                 "--host", "127.0.0.1", "--port", str(args.backend_port)],
                cwd=str(backend), env=backend_env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
        (world / "backend.pid").write_text(str(backend_proc.pid))
        services["backend"] = backend_proc.pid
        if not wait_http(f"{backend_origin}/api/health", 180):
            raise RuntimeError("backend health did not become ready")

        frontend_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        frontend_env.update({
            "PATH": f"{NODE20.parent}:/usr/local/bin:/usr/bin:/bin",
            "NODE_ENV": "production", "NEXT_DIST_DIR": DIST_NAME,
            "NEXT_PUBLIC_API_URL": backend_origin, "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
            "PYTHON_BACKEND_URL": backend_origin, "PYTHON_API_SERVICE_BASE_URL": backend_origin,
            "API_BASE_URL": backend_origin, "NEXTAUTH_URL": frontend_origin,
            "NEXTAUTH_SECRET": web_secret, "JWT_SECRET": "distinct-unused-backend-key",
            "NEXT_PUBLIC_PRODUCT_PROFILE": "core", "ATOM_PRODUCT_PROFILE": "core",
            "NEXT_TELEMETRY_DISABLED": "1",
            "DATABASE_URL": "postgresql://isolated:unavailable@127.0.0.1:18349/isolated_unavailable",
            "PGHOST": "127.0.0.1", "PGPORT": "18349",
        })
        write_private_json(world / "frontend-env.private.json", frontend_env)
        with private_open(world / "frontend.private.log", "wb") as log:
            frontend_proc = subprocess.Popen(
                [str(NODE20), "node_modules/next/dist/bin/next", "start",
                 "--hostname", "127.0.0.1", "--port", str(args.frontend_port)],
                cwd=str(frontend), env=frontend_env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
        (world / "frontend.pid").write_text(str(frontend_proc.pid))
        services["frontend"] = frontend_proc.pid
        if not wait_http(f"{frontend_origin}/auth/forgot-password", 120):
            raise RuntimeError("frontend recovery page did not become ready")
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

        stamp = time.strftime("%Y%m%d%H%M%S")
        email = f"recovery-reset-{stamp}-{secrets.token_hex(3)}@example.com"
        old_password = f"Old-{secrets.token_urlsafe(18)}!"
        new_password = f"New-{secrets.token_urlsafe(18)}!"
        name = "Recovery Reset Member"
        reg = httpx.post(f"{backend_origin}/api/auth/register",
                         json={"email": email, "password": old_password,
                               "first_name": "Recovery", "last_name": "Reset"},
                         timeout=30, trust_env=False)
        if reg.status_code != 200 or not reg.json().get("access_token"):
            raise RuntimeError(f"fixture registration failed: {reg.status_code}")
        before = user_rows(world / "atom.db", email)
        if before["count"] != 1:
            raise RuntimeError("fixture registration did not create one user")
        write_private_json(world / "account.private.json", {
            "email": email, "old_password": old_password, "new_password": new_password,
            "name": name,
        })

        recorder = Recorder(frontend_origin, backend_origin)
        result = {
            "ok": False, "source": source, "harness_sha256": harness_sha,
            "build": build_record, "owner": owners,
            "fixture": {"user_rows_before": before["count"]},
            "freshness": {}, "signed_out_state": {},
            "forgot": {}, "mail": {}, "reset": {}, "old_password": {}, "new_password": {},
            "db": {}, "browser_network": {}, "limits": [
                "HTTP loopback only; production build Secure cookies accepted by Chromium on loopback; no TLS claim.",
                "Backend SMTP transport was replaced by private local file capture; no live SMTP sent.",
                "No provider/model calls, connector consent, sends, spend, or deployment.",
            ],
        }
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=str(CHROME), headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.route("**/*", recorder.route)
            page = context.new_page()
            recorder.attach(page)

            # Freshness before any navigation.
            pre_cookies = context.cookies()
            result["freshness"] = {
                "before_navigation_cookie_count": len(pre_cookies),
                "before_navigation_cookies_empty": len(pre_cookies) == 0,
            }
            # Establish the origin with a static public asset so storage can be
            # read before the app bootstraps. No injection, no app data created.
            page.goto(f"{frontend_origin}/bot-avatar.png", wait_until="domcontentloaded")
            pre_storage = page.evaluate(
                "() => ({local: Object.keys(localStorage).sort(), session: Object.keys(sessionStorage).sort()})")
            result["freshness"].update({
                "before_app_bootstrap_local_storage_keys": pre_storage["local"],
                "before_app_bootstrap_session_storage_keys": pre_storage["session"],
                "before_app_bootstrap_storage_empty": (
                    len(pre_storage["local"]) == 0 and len(pre_storage["session"]) == 0),
            })

            page.goto(f"{frontend_origin}/auth/forgot-password", wait_until="domcontentloaded")
            page.get_by_role("heading", name="Reset your password", exact=True).wait_for(timeout=30000)
            result["forgot"]["signed_out_page_public"] = True
            after_cookies = context.cookies()
            after_cookie_names = sorted({c["name"] for c in after_cookies})
            after_local = page.evaluate("() => Object.keys(localStorage).sort()")
            after_session = page.evaluate("() => Object.keys(sessionStorage).sort()")
            session_r = context.request.get(f"{frontend_origin}/api/auth/session", timeout=30000)
            try:
                session_body = session_r.json()
            except Exception:
                session_body = None
            no_auth_cookie = "auth_token" not in after_cookie_names
            no_sdk_cookie = not any("session-token" in name for name in after_cookie_names)
            no_session_user = not (isinstance(session_body, dict) and session_body.get("user"))
            result["signed_out_state"] = {
                "cookies_after_app_load_names": after_cookie_names,
                "local_storage_keys_after_app_load": after_local,
                "session_storage_keys_after_app_load": after_session,
                "no_auth_token_cookie": no_auth_cookie,
                "no_sdk_session_cookie": no_sdk_cookie,
                "nextauth_session_user_absent": no_session_user,
                "harmless_state_only": no_auth_cookie and no_sdk_cookie and no_session_user,
            }
            page.screenshot(path=str(shots / "01-forgot-password.png"), full_page=True)
            page.locator("#email").fill(email)
            page.get_by_role("button", name="Send reset link", exact=True).click()
            page.get_by_text(re.compile("If an account exists", re.I)).wait_for(timeout=30000)
            result["forgot"]["ui_success_message"] = True
            result["forgot"]["post_count"] = recorder.counts("POST", "/api/auth/forgot-password")

            link = capture_reset_link(world / "mail.private.jsonl", frontend_origin, 45)
            if not link:
                raise RuntimeError("private captured mail did not contain a reset link")
            parsed = urlparse(link)
            token = parse_qs(parsed.query).get("token", [None])[0]
            if not token:
                raise RuntimeError("captured reset link had no token")
            result["mail"] = {"captured": True, "reset_link_path": parsed.path,
                              "token_present": True}

            page.goto(link, wait_until="domcontentloaded")
            page.get_by_role("heading", name="Set new password", exact=True).wait_for(timeout=30000)
            result["reset"]["signed_out_page_public"] = True
            result["reset"]["verify_token_post_count"] = recorder.counts("POST", "/api/auth/verify-token")
            page.screenshot(path=str(shots / "02-reset-form.png"), full_page=True)
            page.locator("#password").fill(new_password)
            page.locator("#confirmPassword").fill(new_password)
            page.get_by_role("button", name="Reset password", exact=True).click()
            page.get_by_text(re.compile("Password reset successful", re.I)).wait_for(timeout=30000)
            result["reset"]["ui_success_message"] = True
            result["reset"]["post_count"] = recorder.counts("POST", "/api/auth/reset-password")
            page.wait_for_url(re.compile(re.escape(frontend_origin) + r"/auth/signin(?:\?.*)?$"),
                              timeout=15000)
            result["reset"]["redirected_to_signin"] = True

            # Old password must fail through the ordinary sign-in form.
            page.locator("#email").fill(email)
            page.locator("#password").fill(old_password)
            page.get_by_role("button", name="Sign In", exact=True).click()
            page.get_by_text(re.compile("Incorrect username or password|Invalid email or password", re.I)).wait_for(timeout=30000)
            result["old_password"]["ui_refused"] = True
            result["old_password"]["session_endpoint_user_absent"] = True
            session_r = context.request.get(f"{frontend_origin}/api/auth/session", timeout=30000)
            try:
                session_body = session_r.json()
            except Exception:
                session_body = None
            result["old_password"]["session_endpoint_user_absent"] = not (
                isinstance(session_body, dict) and session_body.get("user"))
            result["old_password"]["sdk_session_cookie_present"] = any(
                "session-token" in c["name"] for c in context.cookies())
            page.screenshot(path=str(shots / "03-old-password-refused.png"), full_page=True)

            # New password must sign in through the same ordinary form and SDK.
            page.locator("#password").fill(new_password)
            page.get_by_role("button", name="Sign In", exact=True).click()
            page.wait_for_url(re.compile(re.escape(frontend_origin) + r"/dashboard(?:\?.*)?$"),
                              timeout=60000)
            page.get_by_test_id("dashboard-welcome-message").wait_for(timeout=30000)
            page.screenshot(path=str(shots / "04-new-password-dashboard.png"), full_page=True)
            result["new_password"]["landed_dashboard"] = True

            raw = page.evaluate("() => localStorage.getItem('auth_token')")
            cookies = context.cookies()
            base = None
            parts = []
            for candidate in ("__Secure-next-auth.session-token", "next-auth.session-token"):
                found = [c for c in cookies if c["name"] == candidate or
                         re.fullmatch(re.escape(candidate) + r"\.\d+", c["name"])]
                if found:
                    base = candidate
                    found.sort(key=lambda c: int(c["name"].rsplit(".", 1)[1])
                               if re.fullmatch(re.escape(candidate) + r"\.\d+", c["name"]) else -1)
                    parts = found
                    break
            if not raw or not base or not parts:
                raise RuntimeError("new-password sign-in did not produce a raw token and SDK cookie")
            cookie_value = "".join(c["value"] for c in parts)
            decoded = decode_session(cookie_value, web_secret, frontend)
            sess_r = context.request.get(f"{frontend_origin}/api/auth/session", timeout=30000)
            sess = sess_r.json() if sess_r.status == 200 else None
            me = httpx.get(f"{backend_origin}/api/auth/me",
                           headers={"Authorization": f"Bearer {raw}"}, timeout=30, trust_env=False)
            if me.status_code != 200:
                raise RuntimeError(f"canonical /me failed: {me.status_code}")
            me_body = me.json()
            scratch_id = before["ids"][0]
            final_now = user_rows(world / "atom.db", email)
            session_id = sess.get("user", {}).get("id") if isinstance(sess, dict) else None
            decoded_id = decoded.get("id")
            checks = {
                "canonical_me_matches_session": session_id == me_body.get("id"),
                "canonical_me_matches_registered_scratch": me_body.get("id") == scratch_id,
                "canonical_me_matches_final_db": me_body.get("id") == (final_now["ids"][0] if final_now["ids"] else None),
                "decoded_sdk_matches_canonical_me": decoded_id == me_body.get("id"),
                "decoded_sdk_matches_registered_scratch": decoded_id == scratch_id,
                "session_matches_registered_scratch": session_id == scratch_id,
                "same_backend_generation": decoded.get("backendToken") == raw,
                "encrypted_not_raw": cookie_value != raw and len(cookie_value.split(".")) >= 4,
                "http_only": all(bool(c.get("httpOnly")) for c in parts),
                "secure_matches_cookie_name": all(bool(c.get("secure")) for c in parts) == base.startswith("__Secure-"),
                "production_secure_name": base == "__Secure-next-auth.session-token",
                "legacy_auth_token_present": any(c["name"] == "auth_token" and c["value"] == raw for c in cookies),
            }
            write_private_json(world / "user-identity.private.json", {
                "registered_scratch_id": scratch_id,
                "final_db_ids": final_now["ids"],
                "canonical_me_id": me_body.get("id"),
                "session_user_id": session_id,
                "decoded_sdk_id": decoded_id,
            })
            if not all(checks.values()):
                raise RuntimeError(f"new-password SDK checks failed: {checks}")
            result["new_password"]["sdk_checks"] = checks
            result["new_password"]["cookie"] = {
                "name": base, "chunk_count": len(parts),
                "http_only": checks["http_only"], "secure": all(bool(c.get("secure")) for c in parts),
                "same_site": parts[0].get("sameSite"), "jwe_segment_count": len(cookie_value.split(".")),
                "raw_jwt_segment_count": len(raw.split(".")), "transport_scheme": "http",
                "tls_claimed": False,
            }

            # Old password must also be refused by the canonical backend and the
            # reset token must be consumed.
            old_api = httpx.post(f"{backend_origin}/api/auth/login",
                                 json={"username": email, "password": old_password},
                                 timeout=30, trust_env=False)
            result["old_password"]["backend_status"] = old_api.status_code
            result["old_password"]["backend_refused"] = old_api.status_code == 401
            verify_after = httpx.post(f"{backend_origin}/api/auth/verify-token",
                                      json={"token": token}, timeout=30, trust_env=False)
            try:
                verify_body = verify_after.json()
            except Exception:
                verify_body = {}
            result["reset"]["token_consumed"] = verify_after.status_code == 200 and verify_body.get("valid") is False
            after = user_rows(world / "atom.db", email)
            result["db"] = {
                "user_count": after["count"],
                "same_user_id": before["ids"] == after["ids"],
                "canonical_me_matches_registered_scratch": checks["canonical_me_matches_registered_scratch"],
                "canonical_me_matches_final_db": checks["canonical_me_matches_final_db"],
                "decoded_sdk_matches_registered_scratch": checks["decoded_sdk_matches_registered_scratch"],
                "session_matches_registered_scratch": checks["session_matches_registered_scratch"],
            }
            result["browser_network"] = recorder.summary()
            result["ok"] = all([
                result["freshness"]["before_navigation_cookies_empty"],
                result["freshness"]["before_app_bootstrap_storage_empty"],
                result["signed_out_state"]["harmless_state_only"],
                result["forgot"]["signed_out_page_public"], result["forgot"]["ui_success_message"],
                result["forgot"]["post_count"] == 1, result["mail"]["captured"],
                result["reset"]["signed_out_page_public"], result["reset"]["ui_success_message"],
                result["reset"]["post_count"] == 1, result["reset"]["redirected_to_signin"],
                result["reset"]["token_consumed"], result["old_password"]["ui_refused"],
                result["old_password"]["backend_refused"], result["old_password"]["session_endpoint_user_absent"],
                not result["old_password"]["sdk_session_cookie_present"],
                result["new_password"]["landed_dashboard"], after["count"] == 1,
                before["ids"] == after["ids"], result["browser_network"]["external_requests_aborted"] == 0,
                checks["canonical_me_matches_registered_scratch"],
                checks["canonical_me_matches_final_db"],
                checks["decoded_sdk_matches_registered_scratch"],
                checks["session_matches_registered_scratch"],
            ])
            browser.close()
        result["services"] = services
        result["completed_at"] = iso()
        write_private_json(world / "result.private.json", result)
        (public_dir / "verification.json").write_text(
            json.dumps(public_view(result), indent=2, sort_keys=True) + "\n")
        print(json.dumps(public_view(result), indent=2, sort_keys=True), flush=True)
        return 0 if result["ok"] else 1
    except Exception as exc:
        failure = {"ok": False, "source": source, "harness_sha256": harness_sha,
                   "error_type": type(exc).__name__, "error": str(exc)[:500],
                   "at": iso(), "build": build_record, "services": services}
        write_private_json(world / "failure.private.json", failure)
        (public_dir / "verification.json").write_text(
            json.dumps({"ok": False, "source": source, "harness_sha256": harness_sha,
                        "error_type": type(exc).__name__, "error": str(exc)[:500],
                        "at": iso(), "build_exit": build_record.get("exit"),
                        "services_started": sorted(services)}, indent=2, sort_keys=True) + "\n")
        print(json.dumps(failure, indent=2, sort_keys=True), flush=True)
        return 1
    finally:
        cleanup_services = {}
        stop_owned(locals().get("frontend_proc"), "frontend", cleanup_services)
        stop_owned(locals().get("backend_proc"), "backend", cleanup_services)
        cleanup = {"services": cleanup_services}
        dist_bytes = 0
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


def public_view(result):
    keep = {"ok", "source", "harness_sha256", "completed_at", "build", "owner",
            "fixture", "freshness", "signed_out_state",
            "forgot", "mail", "reset", "old_password", "new_password",
            "db", "browser_network", "limits", "services"}
    out = {k: result.get(k) for k in keep if k in result}
    out["private_evidence"] = "retained in 0700 scratch world; not committed"
    return out


if __name__ == "__main__":
    sys.exit(main())
