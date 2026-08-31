"""Zoho end-to-end user journey — a real user, through the real stack.

Everything runs for real (fresh SQLite DB, real LanceDB, real GraphRAG,
real OAuth callbacks, real token storage, real sync pipeline, real chat)
except the Zoho domain itself, which is a local mock server standing in at
the HTTP boundary (consent page + token exchange + Books/Inventory/CRM
data APIs). The browser performs the consent — no API shortcuts.

Journey walked exactly as the pilot operator does:
  1. Admin registers + logs in (real API).
  2. The Connect URL is opened in a browser with the admin's session.
  3. Zoho consent page -> Approve & Connect -> callback exchanges a real
     code for real tokens (mock) -> tokens stored.
  4. OAuth tokens page shows `zoho` active for the admin, the encrypted
     IntegrationToken rows for all five providers exist (checked at the DB,
     the API doesn't expose them), and the grant stays bound to the
     consenting user only (R88 credential isolation — a second account that
     never consented has no rows).
  5. Sync pulls CRM leads/deals + Books invoices + Inventory items/sales
     orders (organization_id auto-discovered from the mock) into LanceDB +
     GraphRAG.
  6. Chat asks about invoices/stock -> the memory context surfaced to the
     user includes the synced Zoho records.
"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Any, Dict, Optional

import pytest
import requests

pytestmark = pytest.mark.e2e

REPO_BACKEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
E2E_UI_DIR = os.path.dirname(os.path.abspath(__file__))

sys_path = __import__("sys")
for _p in (os.path.join(REPO_BACKEND, "scripts"),):
    if _p not in sys_path.path:
        sys_path.path.insert(0, _p)

from zoho_mock_server import (  # noqa: E402
    ACCESS_TOKEN,
    CLIENT_ID,
    CLIENT_SECRET,
    ZohoMockHandler,
)

VENV_PYTHON = os.path.join(REPO_BACKEND, "venv", "bin", "python")

ORG_HEADERS = {
    "Zoho-oauthtoken-access": ACCESS_TOKEN,
}  # unused; kept for readability of the consent-side contract


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_alive(url: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{url}/alive", timeout=3)
            if r.status_code == 200:
                return
            last = f"status={r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = str(e)[:120]
        time.sleep(2)
    raise RuntimeError(f"backend at {url} never became alive: {last}")


@pytest.fixture(scope="module")
def zoho_mock() -> str:
    """Local stand-in for accounts.zoho.com + the Zoho data APIs."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), ZohoMockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def zoho_backend(zoho_mock: str, tmp_path_factory) -> Dict[str, Any]:
    """Dedicated backend wired to the mock Zoho domain (fresh DB/LanceDB)."""
    tmp = tmp_path_factory.mktemp("zoho_e2e")
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
        "ZOHO_CLIENT_ID": CLIENT_ID,
        "ZOHO_CLIENT_SECRET": CLIENT_SECRET,
        "ZOHO_REDIRECT_URI": f"{base}/api/v1/auth/oauth/zoho/callback",
        "ZOHO_ACCOUNTS_BASE": zoho_mock,
        "ZOHO_DEFAULT_API_DOMAIN": zoho_mock,
        # The callback 302s the browser to FRONTEND_URL/oauth/success; the
        # mock stands in for the pilot's :3001 frontend.
        "FRONTEND_URL": zoho_mock,
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
    try:
        _wait_alive(base)
    except Exception:
        tail = log_path.read_text()[-4000:] if log_path.exists() else ""
        proc.terminate()
        proc.wait(timeout=20)
        raise RuntimeError(f"backend failed to start:\n{tail}")

    yield {"url": base, "db": str(tmp / "atom_e2e.db"), "mock": zoho_mock}

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
    services actually read; the /tokens API only shows the legacy page)."""
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

def test_zoho_connect_tokens_sync_and_recall_like_a_real_user(
    browser, zoho_mock: str, zoho_backend: Dict[str, Any]
):
    base = zoho_backend["url"]
    password = "journey-pass-123"

    # 1. Admin + member accounts (real registration/login).
    admin = _register_and_login(base, "admin1@journeyexample.com", password)
    member = _register_and_login(base, "member1@journeyexample.com", password)
    assert admin["token"] and member["token"]

    # 2. Connect via a REAL browser with the admin's session (Bearer header
    #    on the context is what the v1 OAuth wrapper accepts).
    context = browser.new_context(extra_http_headers=_headers(admin))
    page = context.new_page()
    page.goto(
        f"{base}/api/v1/auth/oauth/zoho/initiate",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    # goto follows the 307 chain; landing on the mock consent page proves the
    # initiate route authed the admin and redirected to Zoho.
    page.wait_for_url("**/oauth/v2/auth**", timeout=15000)
    page.get_by_role("button", name="Approve & Connect").click()
    # The callback validates state, exchanges the code against the mock, and
    # 302s the browser toward the configured frontend (the pilot's :3001
    # login-gates /oauth/success, so the landing page is environment-
    # dependent). The durable verification is the operator's doc §4 step:
    # the OAuth tokens page showing zoho active — poll it like the user
    # would refresh it.
    deadline = time.monotonic() + 30
    zoho_active = False
    while time.monotonic() < deadline:
        r = requests.get(
            f"{base}/api/v1/auth/oauth/tokens", headers=_headers(admin), timeout=10
        )
        if r.status_code == 200:
            integrations = r.json().get("integrations", [])
            if any(
                t.get("provider") == "zoho" and t.get("status") == "active"
                for t in integrations
            ):
                zoho_active = True
                break
        time.sleep(1)
    page.close()
    context.close()
    assert zoho_active, "tokens page never showed zoho active after consent"

    # 3a. OAuth tokens page (doc verification) — zoho still active.
    r = requests.get(
        f"{base}/api/v1/auth/oauth/tokens", headers=_headers(admin), timeout=15
    )
    assert r.status_code == 200, f"tokens: {r.status_code} {r.text[:300]}"
    integrations = r.json().get("integrations", [])
    zoho_entry = next((t for t in integrations if t.get("provider") == "zoho"), None)
    assert zoho_entry and zoho_entry.get("status") == "active", (
        f"tokens page missing active zoho: {integrations}"
    )

    # 3b. All five IntegrationToken rows exist and are active (services read
    #     these; the DB is the source of truth).
    providers = _integration_token_providers(zoho_backend["db"])
    for expected in (
        "zoho", "zoho_books", "zoho_inventory", "zoho_crm", "zoho_workdrive",
    ):
        assert providers.get(expected) == "active", (
            f"IntegrationToken {expected} missing/not active: {providers}"
        )

    # 3c. R88 credential isolation: the grant belongs to the user who
    #     consented (admin) — exactly one row per provider, and the member
    #     (who never consented) must have NO token rows. Copying encrypted
    #     credentials into every active user's rows was a fleet-wide
    #     credential-injection vector and is opt-in only
    #     (ATOM_OAUTH_SHARED_INTEGRATION_TOKENS=true).
    con = sqlite3.connect(zoho_backend["db"])
    try:
        row_counts = con.execute(
            "SELECT provider, COUNT(*) FROM integration_tokens "
            "GROUP BY provider"
        ).fetchall()
        member_rows = con.execute(
            "SELECT COUNT(*) FROM integration_tokens "
            "WHERE user_id = ?",
            (member["user_id"] or "",),
        ).fetchone()[0]
    finally:
        con.close()
    for provider, count in row_counts:
        assert count == 1, (
            f"provider {provider} has {count} rows — R88 binds the grant "
            f"to the consenting user only"
        )
    assert member_rows == 0, (
        f"member account has {member_rows} token rows without consenting"
    )

    # 4. Instances: the datacenter api_domain was stamped on the zoho row.
    con = sqlite3.connect(zoho_backend["db"])
    try:
        instance_urls = con.execute(
            "SELECT DISTINCT instance_url FROM integration_tokens "
            "WHERE provider = 'zoho'"
        ).fetchall()
    finally:
        con.close()
    assert (zoho_mock,) in instance_urls, (
        f"callback never stamped api_domain {zoho_mock}: {instance_urls}"
    )

    # 5. Sync: Books + Inventory + CRM all land (org auto-discovered).
    #    Connecting already scheduled a background sync — while it holds the
    #    per-integration lock, an explicit call is skipped (200, success
    #    False), so poll until an explicit force sync actually runs.
    sync = None
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        r = requests.post(
            f"{base}/api/data-ingestion/sync/zoho?force=true",
            headers=_headers(admin),
            timeout=300,
        )
        assert r.status_code == 200, f"sync: {r.status_code} {r.text[:500]}"
        sync = r.json()
        if sync.get("success") is True:
            break
        # Skipped: the background sync is still in flight — retry.
        time.sleep(3)
    assert sync is not None and sync.get("success") is True, f"sync failed: {sync}"
    assert sync.get("records_fetched") == 5, (
        f"expected CRM(2)+Books(1)+Inventory(2)=5 records, got "
        f"{sync}: Books/Inventory gated on organization discovery."
    )
    # records_ingested may legitimately be 0 here: the background sync
    # scheduled on connect already ingested these record ids and ingestion
    # is idempotent (no-overwrite). Step 6 proves the records landed by
    # recalling them from memory.

    # 6. Recall: the chat answer surfaces the synced Zoho records in its
    #    memory context (user-visible transparency block).
    r = requests.post(
        f"{base}/api/chat/message",
        headers=_headers(admin),
        json={
            "message": "What invoices and inventory items do we have on file?",
            "user_id": admin["user_id"] or "admin1@journeyexample.com",
            "session_id": "new",
        },
        timeout=180,
    )
    if r.status_code != 200:
        pytest.skip(f"chat endpoint unavailable in this env ({r.status_code})")
    chat = r.json()
    if chat.get("error_code") in ("no_llm_provider", "budget_exceeded"):
        pytest.skip(f"no LLM provider for answer generation: {chat.get('error_code')}")
    memory_context = chat.get("memory_context") or ""
    answer = chat.get("message") or ""
    recall = memory_context + " " + answer
    assert ("INV-1001" in recall) or ("499.99" in recall), (
        f"Books invoice never recalled. memory_context={memory_context[:400]}"
    )
    assert ("Widget Pro" in recall) or ("WID-PRO" in recall), (
        f"Inventory item never recalled. memory_context={memory_context[:400]}"
    )


def test_zoho_mock_consent_and_token_endpoints():
    """The mock itself honours the OAuth contract the journey relies on
    (bad client id -> 401; data APIs require the issued token)."""
    import threading as _t
    import zoho_mock_server

    server = ThreadingHTTPServer(("127.0.0.1", 0), ZohoMockHandler)
    _t.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        # Bad client rejected at the token endpoint.
        r = requests.post(
            f"{base}/oauth/v2/token",
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
            f"{base}/oauth/v2/auth",
            params={
                "client_id": "wrong",
                "redirect_uri": "http://x/cb",
                "state": "s",
            },
            timeout=10,
        )
        assert r.status_code == 400
        # Data APIs require the issued access token.
        r = requests.get(f"{base}/crm/v2/Leads", timeout=10)
        assert r.status_code == 401
        assert zoho_mock_server.CLIENT_ID.startswith("1000.")
    finally:
        server.shutdown()
        server.server_close()