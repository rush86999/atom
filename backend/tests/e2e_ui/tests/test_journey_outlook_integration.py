"""Outlook end-to-end user journey — a real user, through the real stack.

Everything runs for real (fresh SQLite DB, real OAuth callback, real token
storage, real connection-status aggregation, real Outlook data routes)
except the Microsoft domain itself, which is a local mock server standing in
at the HTTP boundary (consent page + token exchange + Graph data APIs). The
browser performs the consent — no API shortcuts.

Journey walked exactly as the user does:
  1. User registers + logs in (real API).
  2. The Connect URL is opened in a browser with the user's session.
  3. Microsoft consent page -> Approve & Connect -> callback exchanges a
     real code for real tokens (mock) -> tokens stored.
  4. The OAuth tokens page shows `microsoft` active, and the encrypted
     IntegrationToken rows for `microsoft` + `outlook` exist (checked at the
     DB; those rows are what the services actually read).
  5. The Integrations hub's connection-status shows Outlook (and the other
     Graph-backed cards) connected, sourced from the OAuth grant.
  6. The Outlook page's data calls return the user's real mailbox: emails,
     calendar events, contacts, tasks, profile — resolved through the
     stored credential (the mock Graph 401s anything else).
  7. Disconnect: revoking the integration deactivates the hub card AND the
     underlying token rows — data access stops.
"""

from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Any, Dict

import pytest
import requests

pytestmark = pytest.mark.e2e

REPO_BACKEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
sys_path = __import__("sys")
for _p in (os.path.join(REPO_BACKEND, "scripts"),):
    if _p not in sys_path.path:
        sys_path.path.insert(0, _p)

from microsoft_mock_server import (  # noqa: E402
    ACCESS_TOKEN,
    CLIENT_ID,
    CLIENT_SECRET,
    CONTACTS,
    EVENTS,
    MESSAGES,
    TASKS,
    MicrosoftMockHandler,
)

VENV_PYTHON = os.path.join(REPO_BACKEND, "venv", "bin", "python")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def ms_mock() -> str:
    """Local stand-in for login.microsoftonline.com + graph.microsoft.com."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), MicrosoftMockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def ms_backend(ms_mock: str, tmp_path_factory) -> Dict[str, Any]:
    """Dedicated backend wired to the mock Microsoft domain (fresh DB)."""
    tmp = tmp_path_factory.mktemp("outlook_e2e")
    port = _free_port()
    base = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    # The child backend must NOT believe it runs under pytest (the app skips
    # create_all when PYTEST_* env vars are set).
    for _k in ("PYTEST_VERSION", "PYTEST_CURRENT_TEST", "PYTEST_XDIST_WORKER"):
        env.pop(_k, None)
    env.update({
        "DATABASE_URL": f"sqlite:///{tmp}/atom_e2e.db",
        "LANCEDB_PATH": str(tmp / "lancedb"),
        "MICROSOFT_CLIENT_ID": CLIENT_ID,
        "MICROSOFT_CLIENT_SECRET": CLIENT_SECRET,
        "MICROSOFT_REDIRECT_URI": f"{base}/api/v1/auth/oauth/microsoft/callback",
        # Point the OAuth authority and the Graph data plane at the mock.
        "MICROSOFT_AUTHORITY_BASE": ms_mock,
        "MICROSOFT_GRAPH_BASE_URL": f"{ms_mock}/graph/v1.0",
        # The callback 302s the browser to FRONTEND_URL/oauth/success; the
        # mock stands in for the pilot's :3001 frontend.
        "FRONTEND_URL": ms_mock,
        "BYPASS_RATE_LIMIT": "1",
        "PORT": str(port),
        "LOG_LEVEL": "DEBUG",
        "STRUCTLOG_LEVEL": "DEBUG",
        # Deterministic local embeddings (the parent env may set a cloud
        # provider without a key, silently failing every vector leg).
        "EMBEDDING_PROVIDER": "fastembed",
        "EMBEDDING_MODEL": "BAAI/bge-small-en-v1.5",
        # Quiet the pilot background services for a focused journey.
        "TELEGRAM_BOT_TOKEN": "",
        "TURN_FACT_EXTRACTION_ENABLED": "false",
        "TURN_FACT_PRE_COMPRESS_ENABLED": "false",
        "TURN_FACT_VECTOR_RECALL_ENABLED": "false",
        "ATOM_ORG_SHARING_ENABLED": "false",
    })

    log_path = tmp / "backend.log"
    proc = subprocess.Popen(
        [
            VENV_PYTHON,
            "-m", "uvicorn",
            "main_api_app:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=REPO_BACKEND,
        env=env,
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )

    def _wait_alive(timeout: float = 180.0) -> None:
        deadline = time.monotonic() + timeout
        last = ""
        while time.monotonic() < deadline:
            try:
                r = requests.get(f"{base}/alive", timeout=3)
                if r.status_code == 200:
                    return
                last = f"status={r.status_code}"
            except Exception as e:  # noqa: BLE001
                last = str(e)[:120]
            time.sleep(2)
        raise RuntimeError(f"backend at {base} never became alive: {last}")

    try:
        _wait_alive()
    except Exception:
        tail = log_path.read_text()[-4000:] if log_path.exists() else ""
        proc.terminate()
        proc.wait(timeout=20)
        raise RuntimeError(f"backend failed to start:\n{tail}")

    yield {"url": base, "db": str(tmp / "atom_e2e.db"), "mock": ms_mock}

    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def _register_and_login(base: str, email: str, password: str) -> Dict[str, Any]:
    r = requests.post(
        f"{base}/api/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Journey",
            "last_name": "User",
        },
        timeout=20,
    )
    assert r.status_code in (200, 201), (
        f"register failed: {r.status_code} {r.text[:300]}"
    )
    r = requests.post(
        f"{base}/api/auth/login",
        json={"username": email, "password": password},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    token = (
        data.get("access_token")
        or (data.get("data") or {}).get("access_token")
    )
    assert token, f"no access_token in login response: {data}"
    return {
        "email": email,
        "password": password,
        "token": token,
        "user_id": data.get("user_id")
        or (data.get("data") or {}).get("user_id")
        or data.get("id"),
    }


def _headers(user: Dict[str, Any]) -> Dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _integration_token_providers(db_path: str) -> Dict[str, str]:
    """Providers + status from the integration_tokens table (the rows the
    services and the hub's connection-status actually read)."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT provider, status FROM integration_tokens"
        ).fetchall()
        return {p: s for p, s in rows}
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_outlook_connect_status_data_disconnect_like_a_real_user(
    browser, ms_mock: str, ms_backend: Dict[str, Any]
):
    base = ms_backend["url"]
    password = "journey-pass-123"

    # 1. Register + login (real API).
    admin = _register_and_login(base, "outlook.journey@brennan.ca", password)
    assert admin["token"]

    # 2. Connect via a REAL browser with the user's session (Bearer header
    #    on the context is what the initiate route must accept).
    context = browser.new_context(extra_http_headers=_headers(admin))
    page = context.new_page()
    page.goto(
        f"{base}/api/v1/auth/oauth/microsoft/initiate",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    # goto follows the 307 chain; landing on the mock consent page proves the
    # initiate route authed the user and redirected to Microsoft.
    page.wait_for_url("**/oauth2/v2.0/authorize**", timeout=15000)
    page.get_by_role("button", name="Approve & Connect").click()
    page.close()
    context.close()

    # 3. The OAuth tokens page shows microsoft active — poll it like the
    #    user would refresh it after the consent redirect.
    deadline = time.monotonic() + 30
    ms_active = False
    while time.monotonic() < deadline:
        r = requests.get(
            f"{base}/api/v1/auth/oauth/tokens", headers=_headers(admin), timeout=10
        )
        if r.status_code == 200:
            integrations = r.json().get("integrations", [])
            if any(
                t.get("provider") == "microsoft" and t.get("status") == "active"
                for t in integrations
            ):
                ms_active = True
                break
        time.sleep(1)
    assert ms_active, "tokens page never showed microsoft active after consent"

    # 4. IntegrationToken rows exist and are active (services read these; the
    #    DB is the source of truth). One grant fans out to microsoft+outlook.
    providers = _integration_token_providers(ms_backend["db"])
    for expected in ("microsoft", "outlook"):
        assert providers.get(expected) == "active", (
            f"IntegrationToken {expected} missing/not active: {providers}"
        )

    # 5. Hub status: the Integrations page's source of truth shows Outlook
    #    connected via the OAuth grant — plus the other Graph-backed cards
    #    the same consent covers.
    r = requests.get(
        f"{base}/api/integrations/connection-status",
        headers=_headers(admin),
        timeout=15,
    )
    assert r.status_code == 200, f"connection-status: {r.status_code} {r.text[:300]}"
    hub = r.json().get("providers") or r.json().get("data", {}).get("providers") or {}
    for provider_id in ("outlook", "microsoft365", "onedrive", "teams"):
        entry = hub.get(provider_id) or {}
        assert entry.get("connected") is True, (
            f"hub shows {provider_id} not connected after connect: "
            f"{hub.get(provider_id)}"
        )
    assert hub["outlook"].get("source") == "oauth_token", hub["outlook"]

    # 6. Data leg — the stored credential actually works against Graph (the
    #    mock rejects any token but the one issued at consent).
    r = requests.post(
        f"{base}/api/integrations/outlook/emails",
        headers=_headers(admin),
        json={"user_id": "current", "folder": "inbox", "max_results": 25},
        timeout=30,
    )
    assert r.status_code == 200, f"emails: {r.status_code} {r.text[:300]}"
    emails = r.json()
    assert emails.get("success") is True, emails
    assert emails.get("count") == len(MESSAGES), (
        f"expected {len(MESSAGES)} mock emails, got {emails.get('count')}"
    )
    subjects = {e.get("subject") for e in emails.get("data", [])}
    assert MESSAGES[0]["subject"] in subjects, subjects

    r = requests.post(
        f"{base}/api/integrations/outlook/events",
        headers=_headers(admin),
        json={"user_id": "current", "max_results": 10},
        timeout=30,
    )
    assert r.status_code == 200 and r.json().get("count") == len(EVENTS), (
        f"events: {r.status_code} {r.text[:300]}"
    )

    r = requests.post(
        f"{base}/api/integrations/outlook/contacts",
        headers=_headers(admin),
        json={"user_id": "current", "max_results": 10},
        timeout=30,
    )
    assert r.status_code == 200 and r.json().get("count") == len(CONTACTS), (
        f"contacts: {r.status_code} {r.text[:300]}"
    )

    r = requests.post(
        f"{base}/api/integrations/outlook/tasks",
        headers=_headers(admin),
        json={"user_id": "current", "max_results": 10},
        timeout=30,
    )
    assert r.status_code == 200 and r.json().get("count") == len(TASKS), (
        f"tasks: {r.status_code} {r.text[:300]}"
    )

    r = requests.get(
        f"{base}/api/integrations/outlook/profile",
        headers=_headers(admin),
        timeout=30,
    )
    assert r.status_code == 200, f"profile: {r.status_code} {r.text[:300]}"
    profile = (r.json().get("data") or {}).get("profile") or {}
    assert profile.get("displayName") == "Rish Parikh", profile

    # 7. Disconnect: revoke propagates — hub card flips off, token rows are
    #    deactivated, and data access stops.
    r = requests.delete(
        f"{base}/api/v1/auth/oauth/tokens/microsoft",
        headers=_headers(admin),
        timeout=15,
    )
    assert r.status_code == 200, f"revoke: {r.status_code} {r.text[:300]}"

    r = requests.get(
        f"{base}/api/v1/auth/oauth/tokens", headers=_headers(admin), timeout=15
    )
    integrations = r.json().get("integrations", [])
    ms_entry = next((t for t in integrations if t.get("provider") == "microsoft"), None)
    assert ms_entry and ms_entry.get("status") == "revoked", integrations

    r = requests.get(
        f"{base}/api/integrations/connection-status",
        headers=_headers(admin),
        timeout=15,
    )
    hub = r.json().get("providers") or {}
    for provider_id in ("outlook", "microsoft365"):
        entry = hub.get(provider_id) or {}
        assert entry.get("connected") is not True, (
            f"hub still shows {provider_id} connected after disconnect"
        )

    providers_after = _integration_token_providers(ms_backend["db"])
    for expected in ("microsoft", "outlook"):
        assert providers_after.get(expected) == "revoked", (
            f"IntegrationToken {expected} not revoked after disconnect: "
            f"{providers_after}"
        )

    r = requests.post(
        f"{base}/api/integrations/outlook/emails",
        headers=_headers(admin),
        json={"user_id": "current", "folder": "inbox"},
        timeout=30,
    )
    assert r.status_code == 200, f"emails after revoke: {r.status_code}"
    assert r.json().get("count") == 0, (
        f"emails still resolvable after disconnect: {r.json().get('count')}"
    )


def test_microsoft_mock_consent_and_token_endpoints():
    """The mock itself honours the OAuth contract the journey relies on
    (bad client id -> 401/400; data APIs require the issued token)."""
    import threading as _t
    import microsoft_mock_server

    server = ThreadingHTTPServer(("127.0.0.1", 0), MicrosoftMockHandler)
    _t.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        # Bad client rejected at the token endpoint.
        r = requests.post(
            f"{base}/common/oauth2/v2.0/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "wrong",
                "client_secret": "x",
                "redirect_uri": "http://x/cb",
                "code": "c",
            },
            timeout=10,
        )
        assert r.status_code == 401
        # Consent page rejects an unregistered client id.
        r = requests.get(
            f"{base}/common/oauth2/v2.0/authorize",
            params={
                "client_id": "wrong",
                "redirect_uri": "http://x/cb",
                "state": "s",
            },
            timeout=10,
        )
        assert r.status_code == 400
        # Graph APIs require the issued access token.
        r = requests.get(f"{base}/graph/v1.0/me", timeout=10)
        assert r.status_code == 401
        # ...and honour the issued one.
        r = requests.get(
            f"{base}/graph/v1.0/me",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
            timeout=10,
        )
        assert r.status_code == 200 and r.json()["displayName"]
        assert microsoft_mock_server.CLIENT_ID
    finally:
        server.shutdown()
        server.server_close()
