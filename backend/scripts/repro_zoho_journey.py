#!/usr/bin/env python3
"""Manual repro driver for the Zoho journey (dev tooling — not a test).

Boots the mock Zoho server + a dedicated backend with the same env as the
E2E journey, then walks: register → login → initiate → consent → callback →
tokens → force sync → chat, printing the memory context and any failures.
"""
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.zoho_mock_server import CLIENT_ID, CLIENT_SECRET, ZohoMockHandler

REPO_BACKEND = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VENV_PYTHON = os.path.join(REPO_BACKEND, "venv", "bin", "python")
TMP = "/tmp/zoho_e2e_repro"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    mock = ThreadingHTTPServer(("127.0.0.1", 0), ZohoMockHandler)
    threading.Thread(target=mock.serve_forever, daemon=True).start()
    mock_base = f"http://127.0.0.1:{mock.server_address[1]}"
    print(f"mock: {mock_base}")

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    os.makedirs(TMP, exist_ok=True)
    env = os.environ.copy()
    for k in ("PYTEST_VERSION", "PYTEST_CURRENT_TEST", "PYTEST_XDIST_WORKER"):
        env.pop(k, None)
    env.update({
        "DATABASE_URL": f"sqlite:///{TMP}/atom.db",
        "LANCEDB_URI": f"{TMP}/atom_memory",
        "ZOHO_CLIENT_ID": CLIENT_ID,
        "ZOHO_CLIENT_SECRET": CLIENT_SECRET,
        "ZOHO_REDIRECT_URI": f"{base}/api/v1/auth/oauth/zoho/callback",
        "ZOHO_ACCOUNTS_BASE": mock_base,
        "ZOHO_DEFAULT_API_DOMAIN": mock_base,
        "FRONTEND_URL": mock_base,
        "BYPASS_RATE_LIMIT": "1",
        "PORT": str(port),
        "LOG_LEVEL": "DEBUG",
        "STRUCTLOG_LEVEL": "DEBUG",
        "EMBEDDING_PROVIDER": "fastembed",
        "EMBEDDING_MODEL": "BAAI/bge-small-en-v1.5",
        "TELEGRAM_BOT_TOKEN": "",
    })
    logf = open(f"{TMP}/backend.log", "w")
    proc = subprocess.Popen(
        [VENV_PYTHON, "-m", "uvicorn", "main_api_app:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "info"],
        cwd=REPO_BACKEND, env=env, stdout=logf, stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                if requests.get(f"{base}/alive", timeout=3).status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            print("backend never came alive"); return 1

        email, password = "admin@reproexample.com", "repro-pass-123"
        r = requests.post(f"{base}/api/auth/register", json={
            "email": email, "password": password, "first_name": "R", "last_name": "P"}, timeout=20)
        print("register:", r.status_code)
        r = requests.post(f"{base}/api/auth/login", json={"username": email, "password": password}, timeout=20)
        print("login:", r.status_code)
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        s = requests.Session()
        s.headers.update(h)
        r = s.get(f"{base}/api/v1/auth/oauth/zoho/initiate", allow_redirects=False, timeout=15)
        print("initiate:", r.status_code, "->", r.headers.get("Location", "")[:80])
        consent = r.headers["Location"]
        qs = parse_qs(urlparse(consent).query)
        state = qs["state"][0]
        redirect_uri = qs["redirect_uri"][0]
        r = s.get(redirect_uri, params={"code": "mock_auth_code", "state": state}, timeout=30)
        print("callback:", r.status_code, r.text[:120])

        r = s.get(f"{base}/api/v1/auth/oauth/tokens", timeout=10)
        print("tokens:", r.status_code, r.json())

        r = s.post(f"{base}/api/data-ingestion/sync/zoho?force=true", timeout=300)
        print("sync:", r.status_code, r.json())

        r = s.post(f"{base}/api/chat/message", timeout=300, json={
            "message": "What invoices and inventory items do we have on file?",
            "user_id": "admin@repro.test", "session_id": "new",
        })
        print("chat:", r.status_code)
        j = r.json()
        print("chat.message:", j.get("message", "")[:300])
        print("chat.memory_context:", repr(j.get("memory_context"))[:600])
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        mock.shutdown()


if __name__ == "__main__":
    sys.exit(main())