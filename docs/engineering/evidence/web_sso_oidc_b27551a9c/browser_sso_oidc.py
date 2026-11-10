#!/usr/bin/env python3
"""One controlled-loopback OIDC browser episode on frozen source b27551a9c.

Real main_api_app + real Next production build + real browser + a local
PKCE-validating controlled OIDC provider. Raw tokens/codes/state, env, logs and
DB stay in a private 0700 world. No product code is edited.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
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
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

NODE20 = Path("/Users/rushiparikh/.nvm/versions/node/v20.20.2/bin/node")
PY311 = Path("/usr/local/bin/python3.11")
GATE = Path("/private/tmp/atom-agent-cli/run_bounded_test_gate.py")
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
EXPECTED_SOURCE = "b27551a9cb78ca080e97d4e8955bef49a1e220e3"
DIST_NAME = ".next-sso-web-20261109"


def iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def private_open(path: Path, mode="w"):
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    return os.fdopen(fd, mode)


def write_private_json(path: Path, doc):
    tmp = path.with_name(path.name + ".tmp")
    with private_open(tmp, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def write_boundary_checkpoint(
    world: Path,
    *,
    checks: dict,
    required_failures: dict,
    restart: dict,
    final_pathname: str,
    final_query_keys: list,
    settings: dict,
    header_records: dict,
    provider_counts: dict,
    navigation: list,
    page_heading: str | None,
    failure_screenshot: str | None,
    source: str,
    harness_sha256: str,
):
    """Atomic safe checkpoint retained before any acceptance assertion."""
    false_checks = sorted(k for k, v in checks.items() if v is False)
    unknown_checks = sorted(k for k, v in checks.items() if v is None)
    payload = {
        "source": source,
        "harness_sha256": harness_sha256,
        "checks": checks,
        "required_failures": required_failures,
        "false_checks": false_checks,
        "unknown_checks": unknown_checks,
        "restart": restart,
        "final_pathname": final_pathname,
        "final_query_keys": final_query_keys,
        "settings": settings,
        "header_records": header_records,
        "provider": provider_counts,
        "navigation": navigation,
        "page_heading": page_heading,
        "failure_screenshot": failure_screenshot,
        "captured_at": iso(),
    }
    write_private_json(world / "boundary-checks.private.json", payload)
    return payload


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


def db_user(db: Path, email: str) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT id,email,role,status,hashed_password,tenant_id,workspace_id "
            "FROM users WHERE lower(email)=lower(?) ORDER BY id", (email,)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {"count": len(rows), "rows": rows, "total_users": int(total),
                "tables": tables}
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
    def __init__(self, frontend_origin, backend_origin, issuer_origin):
        self.frontend_origin = frontend_origin
        self.allowed_ports = {urlparse(frontend_origin).port,
                              urlparse(backend_origin).port,
                              urlparse(issuer_origin).port}
        self.rows, self.external, self.failed = [], [], []
        self.console_errors = self.page_errors = 0
        self.by_request = {}
        self.headers = {}
        self.response_records = []
        self.page = None
        self.exchange_page_url = None
        self.restart_completed = False
        self.exchange_after_restart = False

    def allowed(self, url):
        if url.startswith(("data:", "blob:", "about:")):
            return True
        u = urlparse(url)
        return u.scheme in ("http", "https", "ws", "wss") and \
            u.hostname in ("localhost", "127.0.0.1") and \
            u.port in self.allowed_ports

    def route(self, route):
        u = urlparse(route.request.url)
        rec = {"method": route.request.method, "path": u.path,
               "port": u.port, "resource_type": route.request.resource_type}
        self.rows.append(rec)
        try:
            self.by_request[id(route.request)] = rec
        except Exception:
            pass

        if u.path == "/api/auth/sso/oidc/web/exchange":
            if self.page is not None:
                self.exchange_page_url = self.page.url
            if self.restart_completed:
                self.exchange_after_restart = True

        if self.allowed(route.request.url):
            route.continue_()
        else:
            self.external.append(rec)
            route.abort()

    def record_response(self, method, path, status, headers):
        self.response_records.append({
            "method": method, "path": path, "status": status,
        })
        if path in ("/auth/sso/callback",
                    "/api/auth/sso/oidc/web/callback",
                    "/api/auth/sso/oidc/web/exchange"):
            key = f"{method} {path}"
            self.headers.setdefault(key, []).append({
                "status": status,
                "cache-control": headers.get("cache-control"),
                "referrer-policy": headers.get("referrer-policy"),
                "content-type": headers.get("content-type"),
            })

    def response(self, response):
        rec = self.by_request.get(id(response.request))
        if rec is not None:
            rec["status"] = response.status
        self.record_response(
            response.request.method, urlparse(response.url).path,
            response.status, response.headers)

    def header_record(self, method, path, status=200):
        for record in reversed(self.headers.get(f"{method} {path}", [])):
            if record.get("status") == status:
                return record
        return None

    def failed_request(self, request):
        self.failed.append({"method": request.method,
                            "path": urlparse(request.url).path})

    def console(self, msg):
        if msg.type == "error":
            self.console_errors += 1

    def page_error(self, _exc):
        self.page_errors += 1

    def attach(self, page):
        self.page = page
        page.on("response", self.response)
        page.on("requestfailed", self.failed_request)
        page.on("console", self.console)
        page.on("pageerror", self.page_error)

    def counts(self, method=None, path=None):
        return sum(1 for r in self.rows
                   if (method is None or r["method"] == method)
                   and (path is None or r["path"] == path))

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
        return {"request_count": len(self.rows),
                "external_requests_aborted": len(self.external),
                "failed_request_count": len(self.failed),
                "console_error_count": self.console_errors,
                "page_error_count": self.page_errors,
                "by_method_path": grouped}


class PkceProvider:
    """Controlled OIDCProvider subclass that verifies PKCE S256 at /token."""

    def __init__(self, *args, **kwargs):
        from scripts.controlled_oidc_provider import OIDCProvider
        self._base = OIDCProvider
        self._provider = OIDCProvider(*args, **kwargs)
        self._gate_lock = threading.Lock()
        self._gate_enabled = False
        self._gate_entered = threading.Event()
        self._gate_release = threading.Event()
        self.gate_state = {"enabled": False, "entered": False,
                           "released": False, "release_timeout": False}

    def arm_authorize_gate(self):
        """Hold the next /authorize 302 before its response is written."""
        self._gate_release.clear()
        self._gate_entered.clear()
        with self._gate_lock:
            self._gate_enabled = True
            self.gate_state.update({"enabled": True, "entered": False,
                                    "released": False, "release_timeout": False})

    def wait_authorize_entered(self, timeout_s=60.0):
        return self._gate_entered.wait(timeout=timeout_s)

    def release_authorize_gate(self):
        self._gate_release.set()

    def _authorize_gate(self):
        with self._gate_lock:
            if not self._gate_enabled:
                return
            self._gate_enabled = False
            self.gate_state["entered"] = True
        self._gate_entered.set()
        released = self._gate_release.wait(timeout=600)
        self.gate_state["released"] = bool(released)
        self.gate_state["release_timeout"] = not released

    def start(self):
        self._provider.start()
        provider = self._provider
        base_authorize = provider.authorize
        base_token = provider.token

        def authorize(query):
            state = (query.get("state") or [""])[0]
            challenge = (query.get("code_challenge") or [""])[0]
            method = (query.get("code_challenge_method") or [""])[0]
            if method != "S256" or not challenge:
                return provider.redirect_uri + "?" + urlencode(
                    {"error": "invalid_request", "state": state})
            url = base_authorize(query)
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            code = (qs.get("code") or [None])[0]
            if code and code in provider._codes:
                provider._codes[code]["code_challenge"] = challenge
                provider._codes[code]["code_challenge_method"] = method
            self._authorize_gate()
            return url

        def token(form):
            code = (form.get("code") or [""])[0]
            stored = provider._codes.get(code)
            if not stored or stored.get("code_challenge_method") != "S256":
                return 400, {"error": "invalid_grant"}
            verifier = (form.get("code_verifier") or [""])[0]
            actual = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode("utf-8")).digest()
            ).rstrip(b"=").decode("ascii")
            if not hmac.compare_digest(stored.get("code_challenge", ""), actual):
                return 400, {"error": "invalid_grant"}
            return base_token(form)

        provider.authorize = authorize
        provider.token = token
        return self

    def stop(self):
        self._provider.stop()

    @property
    def issuer(self):
        return self._provider.issuer

    @property
    def records(self):
        return self._provider.records

    @property
    def email(self):
        return self._provider.email

    def counts(self):
        paths = [urlparse(r["path"]).path for r in self.records]
        return {"authorize": paths.count("/authorize"),
                "token": paths.count("/token"),
                "userinfo": paths.count("/userinfo"),
                "discovery": paths.count("/.well-known/openid-configuration"),
                "jwks": paths.count("/jwks")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/private/tmp/atom-web-task-project-20261109")
    ap.add_argument("--backend-port", type=int, default=18370)
    ap.add_argument("--frontend-port", type=int, default=18371)
    ap.add_argument("--issuer-port", type=int, default=18372)
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
    for port in (args.backend_port, args.frontend_port, args.issuer_port):
        if not free_port(port):
            raise SystemExit(f"port already in use: {port}")

    public_dir = repo / "docs" / "engineering" / "evidence" / f"web_sso_oidc_{source[:9]}"
    if public_dir.exists():
        raise SystemExit(f"public evidence dir already exists: {public_dir}")
    world = Path(tempfile.mkdtemp(prefix="root-web-sso-oidc-world-", dir="/private/tmp"))
    os.chmod(world, 0o700)
    public_dir.mkdir(parents=True, exist_ok=False)
    shots = world / "screenshots"
    shots.mkdir()
    os.chmod(shots, 0o700)
    harness_bytes = Path(__file__).read_bytes()
    harness_sha = sha256_bytes(harness_bytes)
    (public_dir / "browser_sso_oidc.py").write_bytes(harness_bytes)

    frontend_origin = f"http://localhost:{args.frontend_port}"
    backend_origin = f"http://127.0.0.1:{args.backend_port}"
    issuer_origin = f"http://127.0.0.1:{args.issuer_port}"
    stamp = time.strftime("%Y%m%d%H%M%S")
    sso_email = f"sso-web-{stamp}-{secrets.token_hex(3)}@example.com"
    client_id = f"atom-web-acceptance-{secrets.token_hex(4)}"
    client_secret = secrets.token_urlsafe(32)
    admin_password = secrets.token_urlsafe(28)
    web_secret = secrets.token_urlsafe(48)

    owner = {
        "purpose": "one ordinary controlled-loopback OIDC web handoff browser episode",
        "repo": str(repo), "source": source, "harness_sha256": harness_sha,
        "fresh_private_world": str(world), "not_live_database": True,
        "http_loopback_only": True, "controlled_oidc_issuer": issuer_origin,
        "controlled_issuer_redirect_uri": frontend_origin + "/api/auth/sso/oidc/web/callback",
        "testing_runtime": 1, "testing_import_phase": 0,
        "production_environment_or_tls_claimed": False,
    }
    write_private_json(world / "owner-marker.json", owner)

    dist_path = frontend / DIST_NAME
    next_env_before = (frontend / "next-env.d.ts").read_bytes() if (frontend / "next-env.d.ts").exists() else None
    build_record = {}
    services = {}
    backend_proc = None
    provider = None
    try:
        # ---- controlled PKCE-validating OIDC issuer ----------------------
        provider = PkceProvider(
            port=args.issuer_port,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=frontend_origin + "/api/auth/sso/oidc/web/callback",
            email=sso_email,
            given_name="Sso",
            family_name="Web",
            mode="valid",
        ).start()
        if not wait_http(f"{issuer_origin}/health", 30):
            raise RuntimeError("controlled OIDC issuer did not become ready")

        # ---- optimized Next build through existing heavy gate -------------
        build_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        build_env.update({
            "PATH": f"{NODE20.parent}:/usr/local/bin:/usr/bin:/bin",
            "NODE_ENV": "production", "NEXT_DIST_DIR": DIST_NAME,
            "NEXT_PUBLIC_API_URL": backend_origin, "NEXT_PUBLIC_ALLOW_LOOPBACK": "1",
            "NEXTAUTH_URL": frontend_origin, "NEXT_TELEMETRY_DISABLED": "1",
            "NODE_OPTIONS": "--max-old-space-size=4096",
            "DATABASE_URL": "postgresql://isolated:unavailable@127.0.0.1:18379/build_only_unavailable",
            "PGHOST": "127.0.0.1", "PGPORT": "18379", "NPM_CONFIG_OFFLINE": "true",
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

        # ---- isolated backend with env-configured constrained issuer -------
        backend_env = {k: os.environ[k] for k in ("HOME", "TMPDIR", "LANG") if k in os.environ}
        backend_env.update({
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "DATABASE_URL": f"sqlite:///{world}/atom.db", "TESTING": "1",
            "ENVIRONMENT": "development", "SECRET_KEY": secrets.token_urlsafe(48),
            "ADMIN_PASSWORD": admin_password,
            "ATOM_PRODUCT_PROFILE": "core", "ATOM_DEPLOYMENT_AUDIENCE": "development",
            "ENABLE_SCHEDULER": "false", "ENABLE_INGESTION_SYNC": "false",
            "ATOM_LOCAL_ONLY": "true", "ATOM_TURN_DECISION_ROUTING": "0",
            "ATOM_DATA_DIR": str(world / "data"),
            "LANCEDB_URI": str(world / "data/atom_memory"),
            "LANCEDB_URI_BASE": str(world / "data/atom_memory"),
            "ATOM_OFFICE_DIR": str(world / "data/office"),
            "ATOM_TASK_LOCK_DIR": str(world / "data/task_locks"),
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "APP_URL": frontend_origin,
            "ADDITIONAL_ALLOWED_ORIGINS": frontend_origin,
            "ALLOWED_HOSTS": f"localhost,127.0.0.1,127.0.0.1:{args.backend_port},{args.frontend_port},testserver",
            "SMTP_HOST": "smtp.invalid", "SMTP_PORT": "587",
            "SMTP_USER": "capture@example.com", "SMTP_PASSWORD": secrets.token_urlsafe(24),
            "OLLAMA_BASE_URL": "http://127.0.0.1:18378",
            "ATOM_OIDC_ISSUER": issuer_origin,
            "ATOM_OIDC_CLIENT_ID": client_id,
            "ATOM_OIDC_CLIENT_SECRET": client_secret,
            "ATOM_OIDC_ENABLED": "true",
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
        backend_cmd = [str(PY311), "-m", "uvicorn", "recovery_capture_app:app",
                       "--host", "127.0.0.1", "--port", str(args.backend_port)]

        def start_backend(log_name):
            with private_open(world / log_name, "wb") as log:
                return subprocess.Popen(
                    backend_cmd, cwd=str(backend), env=backend_env,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

        backend_proc = start_backend("backend.private.log")
        services["backend_first"] = backend_proc.pid
        (world / "backend.pid").write_text(str(backend_proc.pid))
        if not wait_http(f"{backend_origin}/api/health", 180):
            raise RuntimeError("backend health did not become ready")

        # Normal admin bootstrap/login. The fresh bootstrap admin is expected
        # to be workspace_admin; the existing config API may therefore refuse
        # SYSTEM_ADMIN without a forbidden direct role grant.
        admin_login = None
        for _ in range(30):
            admin_login = httpx.post(f"{backend_origin}/api/auth/login",
                                     json={"username": "admin@example.com",
                                           "password": admin_password},
                                     timeout=30, trust_env=False)
            if admin_login.status_code == 200:
                break
            time.sleep(1)
        admin_status = admin_login.status_code if admin_login is not None else None
        admin_token = ""
        admin_role = None
        if admin_login is not None and admin_status == 200:
            admin_token = admin_login.json().get("access_token") or ""
            me = httpx.get(f"{backend_origin}/api/auth/me",
                           headers={"Authorization": f"Bearer {admin_token}"},
                           timeout=30, trust_env=False)
            if me.status_code == 200:
                admin_role = me.json().get("role")
        config_status = None
        if admin_token:
            cfg = httpx.put(
                f"{backend_origin}/api/auth/sso/oidc/config",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"issuer_url": issuer_origin, "client_id": client_id,
                      "client_secret": client_secret, "enabled": True,
                      "default_role": "member", "allowed_domains": ["example.com"]},
                timeout=30, trust_env=False)
            config_status = cfg.status_code
        config_source = "database" if config_status == 200 else "environment"
        write_private_json(world / "admin-config.private.json", {
            "admin_login_status": admin_status, "admin_role": admin_role,
            "config_api_status": config_status, "config_source": config_source,
        })

        # ---- production frontend -----------------------------------------
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
            "DATABASE_URL": "postgresql://isolated:unavailable@127.0.0.1:18379/isolated_unavailable",
            "PGHOST": "127.0.0.1", "PGPORT": "18379",
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
        if not wait_http(f"{frontend_origin}/login", 120):
            raise RuntimeError("frontend login page did not become ready")

        owners = {
            "backend_listener_pid": listener_pid(args.backend_port),
            "frontend_listener_pid": listener_pid(args.frontend_port),
            "issuer_listener_pid": listener_pid(args.issuer_port),
            "backend_cwd": proc_cwd(listener_pid(args.backend_port)) if listener_pid(args.backend_port) else None,
            "frontend_cwd": proc_cwd(listener_pid(args.frontend_port)) if listener_pid(args.frontend_port) else None,
            "issuer_cwd": None,
        }
        if not owners["backend_cwd"] or not owners["backend_cwd"].startswith(str(backend)):
            raise RuntimeError(f"backend ownership failed: {owners}")
        if not owners["frontend_cwd"] or not owners["frontend_cwd"].startswith(str(frontend)):
            raise RuntimeError(f"frontend ownership failed: {owners}")
        write_private_json(world / "listener-owners.private.json", owners)

        # ---- owned issuer authorize gate / owned backend restart ---------
        # Playwright applies route handlers only to the first request of a
        # redirect chain, so a route hook cannot pause the callback. Gate the
        # OWNED issuer's real 302 instead, before it is written, and restart
        # only the owned backend while the browser waits.
        restart_state = {"enabled": True, "entered": False, "held": False,
                         "released": False, "health": False}

        def restart_owned_backend():
            nonlocal backend_proc
            restart_state["started_at"] = iso()
            restart_state["old_pid"] = backend_proc.pid if backend_proc else None
            stop_local = {}
            stop_owned(backend_proc, "old_backend", stop_local)
            restart_state["old_terminal"] = bool(
                stop_local.get("services", {}).get("old_backend", {}).get("terminal"))
            if not free_port(args.backend_port):
                deadline = time.monotonic() + 20
                while not free_port(args.backend_port) and time.monotonic() < deadline:
                    time.sleep(0.5)
            last_error = None
            for attempt in (1, 2):
                try:
                    backend_proc = start_backend(f"backend.restart{attempt}.private.log")
                    restart_state[f"restart_pid_{attempt}"] = backend_proc.pid
                    if wait_http(f"{backend_origin}/api/health", 120):
                        restart_state["new_pid"] = backend_proc.pid
                        restart_state["health"] = True
                        restart_state["attempt"] = attempt
                        services[f"backend_restart_{attempt}"] = backend_proc.pid
                        return True
                except Exception as exc:
                    last_error = type(exc).__name__
                if backend_proc is not None and backend_proc.poll() is None:
                    stop_owned(backend_proc, f"failed_restart_{attempt}", {})
            restart_state["health"] = False
            restart_state["error"] = last_error or "backend_restart_unhealthy"
            return False

        recorder = Recorder(frontend_origin, backend_origin, issuer_origin)
        result = {
            "ok": False, "source": source, "harness_sha256": harness_sha,
            "build": build_record, "owner": owners, "services": services,
            "admin": {"login_status": admin_status, "role": admin_role,
                      "config_api_status": config_status, "config_source": config_source},
            "provider": {"issuer_origin": issuer_origin},
            "freshness": {}, "signed_out_state": {},
            "restart": restart_state, "settings": {}, "session": {}, "cookie": {},
            "db": {}, "headers": {}, "browser_network": {}, "logout": {},
            "limits": [
                "HTTP loopback only; no TLS/production-transport claim.",
                "Controlled local OIDC issuer and in-process PKCE S256 validation; no live provider/account/consent.",
                "Backend SMTP transport captured/no live send; no model/provider/SMTP/spend calls.",
            ],
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=str(CHROME), headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            context.route("**/*", recorder.route)
            # Dedicated callback matcher: redirects/navigation can bypass the
            # broad matcher in some Playwright paths; same handler, narrower key.
            context.route("**/api/auth/sso/oidc/web/callback*", recorder.route)
            page = context.new_page()
            page.set_default_timeout(300000)
            recorder.attach(page)

            pre_cookies = context.cookies()
            result["freshness"]["before_navigation_cookies_empty"] = len(pre_cookies) == 0
            result["freshness"]["before_navigation_cookie_count"] = len(pre_cookies)
            page.goto(f"{frontend_origin}/bot-avatar.png", wait_until="domcontentloaded")
            pre_storage = page.evaluate(
                "() => ({local: Object.keys(localStorage).sort(), session: Object.keys(sessionStorage).sort()})")
            result["freshness"]["before_app_bootstrap_storage_empty"] = (
                len(pre_storage["local"]) == 0 and len(pre_storage["session"]) == 0)
            result["freshness"]["before_app_bootstrap_local_keys"] = pre_storage["local"]
            result["freshness"]["before_app_bootstrap_session_keys"] = pre_storage["session"]

            page.goto(
                f"{frontend_origin}/login?callbackUrl=%2Fsettings%3Fsso%3Dverified",
                wait_until="domcontentloaded")
            page.wait_for_function(
                "() => new URLSearchParams(location.search).get('callbackUrl') === '/settings?sso=verified'",
                timeout=15000)
            page.wait_for_timeout(1500)
            result["signed_out_state"]["cookies_after_bootstrap_names"] = sorted(
                {c["name"] for c in context.cookies()})
            result["signed_out_state"]["local_storage_keys_after_bootstrap"] = page.evaluate(
                "() => Object.keys(localStorage).sort()")
            result["signed_out_state"]["session_storage_keys_after_bootstrap"] = page.evaluate(
                "() => Object.keys(sessionStorage).sort()")
            no_auth_cookie = "auth_token" not in result["signed_out_state"]["cookies_after_bootstrap_names"]
            no_sdk_cookie = not any("session-token" in n for n in result["signed_out_state"]["cookies_after_bootstrap_names"])
            sess0 = context.request.get(f"{frontend_origin}/api/auth/session", timeout=30000)
            try:
                sess0_body = sess0.json()
            except Exception:
                sess0_body = None
            no_user = not (isinstance(sess0_body, dict) and sess0_body.get("user"))
            result["signed_out_state"].update({
                "no_auth_token_cookie": no_auth_cookie,
                "no_sdk_session_cookie": no_sdk_cookie,
                "nextauth_session_user_absent": no_user,
                "harmless_state_only": no_auth_cookie and no_sdk_cookie and no_user,
            })
            page.screenshot(path=str(shots / "01-login.png"), full_page=True)

            before_authorize = provider.counts()
            provider.arm_authorize_gate()
            # no_wait_after returns as soon as the click is dispatched; the
            # restarted backend is coordinated below while the browser waits
            # on the owned issuer's still-unsent 302.
            page.get_by_test_id("login-sso-button").click(no_wait_after=True)
            gate_deadline = time.monotonic() + 90
            while (not provider.gate_state.get("entered")
                   and time.monotonic() < gate_deadline):
                page.wait_for_timeout(100)
            restart_state["entered"] = bool(provider.gate_state.get("entered"))
            if restart_state["entered"]:
                restart_state["held"] = True
                restart_state["health"] = restart_owned_backend()
                if restart_state["health"]:
                    recorder.restart_completed = True
                restart_state["released"] = True
                provider.release_authorize_gate()
            else:
                restart_state["released"] = True
                provider.release_authorize_gate()
            restart_state["gate"] = dict(provider.gate_state)
            try:
                page.wait_for_url(
                    re.compile(re.escape(frontend_origin) + r"/settings\?sso=verified$"),
                    timeout=300000)
            except PWTimeout:
                result["final_error_url_safe"] = urlparse(page.url).path
                raise RuntimeError("SSO flow did not reach Settings")
            page.get_by_role("heading", name="Settings", exact=True).wait_for(timeout=30000)
            final_url = page.url
            onboarding = {"present": False}
            try:
                page.get_by_text("Welcome to Atom", exact=True).wait_for(timeout=8000)
                onboarding["present"] = True
                dialog = page.get_by_role("dialog")
                dialog.get_by_role("button", name="Next", exact=True).click()
                page.wait_for_timeout(400)
                page.locator("#role").fill("QA")
                page.locator("#goal").fill("Verify the SSO web handoff")
                dialog.get_by_role("button", name="Next", exact=True).click()
                page.wait_for_timeout(1000)
                dialog.get_by_role("button", name="Next", exact=True).click()
                page.wait_for_timeout(700)
                dialog.get_by_role("button", name="Start Automating", exact=True).click()
                page.get_by_text("Welcome to Atom", exact=True).wait_for(state="hidden", timeout=30000)
                onboarding["completed_via_ui"] = True
            except PWTimeout:
                onboarding["completed_via_ui"] = False
            result["onboarding"] = onboarding
            page.screenshot(path=str(shots / "02-settings-after-sso.png"), full_page=True)
            page.reload(wait_until="domcontentloaded")
            page.get_by_role("heading", name="Settings", exact=True).wait_for(timeout=30000)
            reload_url = page.url
            page.screenshot(path=str(shots / "03-settings-reload.png"), full_page=True)
            result["settings"] = {
                "exact_path_query": final_url == frontend_origin + "/settings?sso=verified",
                "reload_exact_path_query": reload_url == frontend_origin + "/settings?sso=verified",
                "final_url_has_access_token": "access_token" in urlparse(final_url).query,
            }

            raw = page.evaluate("() => localStorage.getItem('auth_token')")
            if not raw:
                raise RuntimeError("SSO flow did not persist the raw compatibility token")
            cookies = context.cookies()
            base = None
            parts = []
            for name in ("__Secure-next-auth.session-token", "next-auth.session-token"):
                found = [c for c in cookies if c["name"] == name or
                         re.fullmatch(re.escape(name) + r"\.\d+", c["name"])]
                if found:
                    base = name
                    found.sort(key=lambda c: int(c["name"].rsplit(".", 1)[1])
                               if re.fullmatch(re.escape(name) + r"\.\d+", c["name"]) else -1)
                    parts = found
                    break
            if not base or not parts:
                raise RuntimeError("SSO flow did not create an SDK session cookie")
            cookie_value = "".join(c["value"] for c in parts)
            decoded = decode_session(cookie_value, web_secret, frontend)
            sess = context.request.get(f"{frontend_origin}/api/auth/session", timeout=30000)
            sess_body = sess.json() if sess.status == 200 else None
            me = httpx.get(f"{backend_origin}/api/auth/me",
                           headers={"Authorization": f"Bearer {raw}"},
                           timeout=30, trust_env=False)
            if me.status_code != 200:
                raise RuntimeError(f"canonical /me failed: {me.status_code}")
            me_body = me.json()
            db = db_user(world / "atom.db", sso_email)
            if db["count"] != 1:
                raise RuntimeError("SSO did not create exactly one canonical user")
            db_row = db["rows"][0]
            session_id = (sess_body or {}).get("user", {}).get("id") if isinstance(sess_body, dict) else None
            def header_policy(method, path, header, needle):
                record = recorder.header_record(method, path, 200)
                if not record:
                    return None
                value = record.get(header)
                if value is None:
                    return None
                return needle in str(value).lower()

            checks = {
                "canonical_me_matches_session": session_id == me_body.get("id"),
                "canonical_me_matches_db": me_body.get("id") == db_row[0],
                "decoded_sdk_matches_canonical_me": decoded.get("id") == me_body.get("id"),
                "same_backend_generation": decoded.get("backendToken") == raw,
                "encrypted_not_raw": cookie_value != raw and len(cookie_value.split(".")) >= 4,
                "http_only": all(bool(c.get("httpOnly")) for c in parts),
                "secure_matches_name": all(bool(c.get("secure")) for c in parts) == base.startswith("__Secure-"),
                "production_secure_name": base == "__Secure-next-auth.session-token",
                "raw_token_not_in_url": raw not in final_url,
                "raw_token_not_in_html": raw not in page.content(),
                "landing_code_removed_before_exchange": bool(
                    recorder.exchange_page_url and
                    urlparse(recorder.exchange_page_url).path == "/auth/sso/callback" and
                    "code=" not in recorder.exchange_page_url and
                    "access_token" not in recorder.exchange_page_url),
                "one_canonical_user": db["count"] == 1 and db_row[4] is None,
                "zero_browser_password_logins": recorder.counts("POST", "/api/auth/login") == 0,
                "one_exchange": recorder.counts("POST", "/api/auth/sso/oidc/web/exchange") == 1,
                "one_sdk_callback": recorder.counts("POST", "/api/auth/callback/credentials") == 1,
                "one_issuer_authorize": provider.counts()["authorize"] == 1,
                "one_issuer_token": provider.counts()["token"] == 1,
                "issuer_gate_entered_before_302": bool(
                    provider.gate_state.get("entered")),
                "issuer_gate_released_after_restart": bool(
                    provider.gate_state.get("released")),
                "restart_health": bool(restart_state.get("health")),
                "exchange_after_restart": bool(recorder.exchange_after_restart),
                "admin_bootstrap_login_200": admin_status == 200,
                "config_api_policy_boundary": config_status in (200, 403),
                "supported_env_config_used_when_api_refused": (
                    config_status == 200
                    or (config_status == 403 and config_source == "environment")
                ),
                "settings_exact_path_query": result["settings"]["exact_path_query"],
                "settings_reload_exact_path_query": result["settings"]["reload_exact_path_query"],
                "landing_no_store": header_policy(
                    "GET", "/auth/sso/callback", "cache-control", "no-store"),
                "landing_no_referrer": header_policy(
                    "GET", "/auth/sso/callback", "referrer-policy", "no-referrer"),
                "exchange_no_store": header_policy(
                    "POST", "/api/auth/sso/oidc/web/exchange", "cache-control", "no-store"),
                "exchange_no_referrer": header_policy(
                    "POST", "/api/auth/sso/oidc/web/exchange", "referrer-policy", "no-referrer"),
            }
            restart_keys = {
                "issuer_gate_entered_before_302",
                "issuer_gate_released_after_restart",
                "restart_health",
                "exchange_after_restart",
            }
            restart_extension_ok = all(checks[k] for k in restart_keys)
            restart_keys = restart_keys | {"restart_extension_ok"}
            checks["restart_extension_ok"] = restart_extension_ok
            result["boundary_checks"] = checks
            result["restart"]["extension_ok"] = restart_extension_ok
            result["restart_gap"] = not restart_extension_ok
            required = {k: v for k, v in checks.items() if k not in restart_keys}
            required_failures = {k: v for k, v in required.items() if v is not True}
            if required_failures:
                heading = None
                try:
                    heading = page.get_by_role("heading").first.inner_text(timeout=2000)
                except Exception:
                    pass
                screenshot_name = "failure-final.png"
                try:
                    page.screenshot(path=str(world / screenshot_name), full_page=True)
                except Exception:
                    screenshot_name = None
                write_boundary_checkpoint(
                    world,
                    checks=checks,
                    required_failures=required_failures,
                    restart=restart_state,
                    final_pathname=urlparse(page.url).path,
                    final_query_keys=sorted(parse_qs(urlparse(page.url).query).keys()),
                    settings=result.get("settings", {}),
                    header_records=recorder.headers,
                    provider_counts=provider.counts(),
                    navigation=[
                        {"method": r["method"], "path": r["path"], "status": r["status"]}
                        for r in recorder.response_records
                    ],
                    page_heading=heading,
                    failure_screenshot=screenshot_name,
                    source=source,
                    harness_sha256=harness_sha,
                )
                raise RuntimeError("SSO boundary checks failed")
            result.update({
                "session": {"checks": checks, "session_status": sess.status,
                            "canonical_me_status": me.status_code,
                            "session_user_id_present": bool(session_id)},
                "cookie": {
                    "name": base, "chunk_count": len(parts),
                    "http_only": all(bool(c.get("httpOnly")) for c in parts),
                    "secure": all(bool(c.get("secure")) for c in parts),
                    "same_site": parts[0].get("sameSite"),
                    "host_only": all(not str(c.get("domain", "")).startswith(".") for c in parts),
                    "jwe_segment_count": len(cookie_value.split(".")),
                    "raw_jwt_segment_count": len(raw.split(".")),
                    "value_is_not_raw": cookie_value != raw,
                    "transport_scheme": "http", "tls_claimed": False,
                },
                "db": {
                    "sso_user_count": db["count"], "total_users": db["total_users"],
                    "role": db_row[2], "status": db_row[3],
                    "hashed_password_null": db_row[4] is None,
                    "tenant_id_present": bool(db_row[5]),
                    "workspace_id": db_row[6],
                    "same_canonical_id": me_body.get("id") == db_row[0],
                    "nextauth_adapter_tables": [
                        t for t in db["tables"]
                        if t.lower() in {"accounts", "sessions", "verification_tokens"}],
                },
                "headers": recorder.headers,
                "provider": {"issuer_origin": issuer_origin, **provider.counts()},
                "browser_network": recorder.summary(),
                "restart": restart_state,
            })

            # UI logout clears the actual SDK and raw compatibility state.
            # Navigate through the ordinary dashboard shell before using its
            # profile/logout affordance; Settings assertions already passed.
            page.goto(f"{frontend_origin}/dashboard", wait_until="domcontentloaded")
            page.get_by_test_id("dashboard-welcome-message").wait_for(timeout=30000)
            page.get_by_test_id("dashboard-user-profile-button").hover()
            page.get_by_test_id("dashboard-logout-button").click()
            page.wait_for_url(
                re.compile(re.escape(frontend_origin) + r"/auth/signin(?:\?.*)?$"),
                timeout=45000)
            deadline = time.monotonic() + 20
            cookies_after = context.cookies()
            raw_after = page.evaluate("() => localStorage.getItem('auth_token')")
            sess_after_body = None
            while time.monotonic() < deadline:
                cookies_after = context.cookies()
                raw_after = page.evaluate("() => localStorage.getItem('auth_token')")
                sess_after = context.request.get(
                    f"{frontend_origin}/api/auth/session", timeout=30000)
                try:
                    sess_after_body = sess_after.json()
                except Exception:
                    sess_after_body = None
                if (not any("session-token" in c["name"] for c in cookies_after)
                        and raw_after is None
                        and not (isinstance(sess_after_body, dict) and sess_after_body.get("user"))):
                    break
                page.wait_for_timeout(500)
            result["logout"] = {
                "sdk_cookie_absent": not any("session-token" in c["name"] for c in cookies_after),
                "raw_token_absent": raw_after is None,
                "session_user_absent": not (
                    isinstance(sess_after_body, dict) and sess_after_body.get("user")),
                "explicit_logout_marker": page.evaluate(
                    "() => localStorage.getItem('atom_explicit_logout')") == "1",
            }
            if not all(result["logout"].values()):
                raise RuntimeError(f"logout checks failed: {result['logout']}")
            page.screenshot(path=str(shots / "04-signin-after-logout.png"), full_page=True)
            result["ok"] = True
            browser.close()

        result["completed_at"] = iso()
        result["services"] = services
        write_private_json(world / "result.private.json", result)
        (public_dir / "verification.json").write_text(
            json.dumps(public_view(result), indent=2, sort_keys=True) + "\n")
        print(json.dumps(public_view(result), indent=2, sort_keys=True), flush=True)
        return 0 if result["ok"] else 1
    except Exception as exc:
        boundary_checks = locals().get("checks")
        failure = {"ok": False, "source": source, "harness_sha256": harness_sha,
                   "error_type": type(exc).__name__, "error": str(exc)[:1000],
                   "at": iso(), "build": build_record, "services": services,
                   "checks": boundary_checks,
                   "required_failures": locals().get("required_failures"),
                   "restart": locals().get("restart_state")}
        page_obj = locals().get("page")
        if page_obj is not None:
            try:
                failure["final_pathname"] = urlparse(page_obj.url).path
                failure["final_query_keys"] = sorted(
                    parse_qs(urlparse(page_obj.url).query).keys())
            except Exception:
                pass
        write_private_json(world / "failure.private.json", failure)
        (public_dir / "verification.json").write_text(
            json.dumps({"ok": False, "source": source, "harness_sha256": harness_sha,
                        "error_type": type(exc).__name__, "error": str(exc)[:1000],
                        "at": iso(), "build_exit": build_record.get("exit"),
                        "services_started": sorted(services),
                        "checks": boundary_checks,
                        "required_failures": locals().get("required_failures"),
                        "final_pathname": failure.get("final_pathname"),
                        "final_query_keys": failure.get("final_query_keys"),
                        "restart_gap": bool(
                            boundary_checks is None
                            or not boundary_checks.get("restart_extension_ok"))}, indent=2, sort_keys=True) + "\n")
        print(json.dumps(failure, indent=2, sort_keys=True), flush=True)
        return 1
    finally:
        cleanup_services = {}
        stop_owned(locals().get("frontend_proc"), "frontend", cleanup_services)
        stop_owned(locals().get("backend_proc"), "backend", cleanup_services)
        if provider is not None:
            try:
                provider.stop()
            except Exception:
                pass
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
        cleanup["issuer_port_closed"] = free_port(args.issuer_port)
        cleanup["private_world_retained"] = str(world)
        write_private_json(world / "cleanup.private.json", cleanup)
        print(json.dumps({"cleanup": cleanup}, indent=2, sort_keys=True), flush=True)


def public_view(result):
    keep = {"ok", "source", "harness_sha256", "completed_at", "build", "owner",
            "admin", "provider", "freshness", "signed_out_state", "restart",
            "restart_gap", "boundary_checks", "onboarding", "settings",
            "session", "cookie", "db", "headers", "browser_network", "logout",
            "limits", "services"}
    out = {k: result.get(k) for k in keep if k in result}
    out["private_evidence"] = "retained in 0700 scratch world; not committed"
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, "/private/tmp/atom-web-task-project-20261109/backend")
    sys.exit(main())
