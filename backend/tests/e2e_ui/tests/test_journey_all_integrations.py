"""Every-integration user journey — the shared connect contract, per provider.

Outlook and Zoho have deep, provider-specific journeys (mocked data planes,
sync, recall). Every other integration in the catalog shares the same
user-facing skeleton, and this module walks it for real, one provider at a
time:

  1. User registers + logs in (real API).
  2. Browser consent on the provider's authorize page (local generic mock —
     the provider domain is the only thing faked).
  3. Callback stores tokens: OAuth tokens page shows the provider active,
     the IntegrationToken row exists (the rows services read).
  4. The Integrations hub's connection-status shows the provider (and its
     alias cards, e.g. google -> gmail/gdrive) connected from the grant.
  5. Disconnect revokes the grant everywhere.

Providers covered by the full journey: google, slack, github, asana, notion,
dropbox, box, salesforce, linkedin, whatsapp. Trello is initiate-only: its
real token exchange is OAuth1 (signed), which Atom's generic OAuth2 handler
does not implement, so a mock "exchange" would prove nothing.

The remaining catalog entries are API-key/env integrations: they connect
without an in-app flow and appear connected from backend credentials —
covered by test_env_credentials_connect_catalog against a dedicated backend.
"""

from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
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
for _p in (
    os.path.join(REPO_BACKEND, "scripts"),
    REPO_BACKEND,  # api.integration_status_routes (env-credential catalog)
):
    if _p not in sys_path.path:
        sys_path.path.insert(0, _p)

from generic_oauth_mock_server import (  # noqa: E402
    PROVIDERS,
    GenericOAuthMockHandler,
    client_id_for,
)

VENV_PYTHON = os.path.join(REPO_BACKEND, "venv", "bin", "python")

# provider -> OAuthConfig env-var prefix (derived from the client-id env name)
PROVIDER_PREFIXES: Dict[str, str] = {
    "google": "GOOGLE",
    "slack": "SLACK",
    "github": "GITHUB",
    "asana": "ASANA",
    "notion": "NOTION",
    "dropbox": "DROPBOX",
    "box": "BOX",
    "salesforce": "SALESFORCE",
    "linkedin": "LINKEDIN",
    "whatsapp": "WHATSAPP",
    # client_id_env is TRELLO_API_KEY → derived prefix is TRELLO; the client
    # id / secret env names are special-cased in the fixture below.
    "trello": "TRELLO",
}

FULL_JOURNEY_PROVIDERS = [p for p in PROVIDER_PREFIXES if p != "trello"]

# provider -> hub card ids connection-status must show connected
EXPECTED_HUB_IDS: Dict[str, list] = {
    "google": ["gmail", "gdrive"],  # one consent fans out to both cards
    "slack": ["slack"],
    "github": ["github"],
    "asana": ["asana"],
    "notion": ["notion"],
    "dropbox": ["dropbox"],
    "box": ["box"],
    "salesforce": ["salesforce"],
    "linkedin": ["linkedin"],
    "whatsapp": ["whatsapp"],
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_backend(env: Dict[str, str], tmp, name: str, port: int):
    base = f"http://127.0.0.1:{port}"
    env = env.copy()
    # The child backend must NOT believe it runs under pytest (the app skips
    # create_all when PYTEST_* env vars are set).
    for _k in ("PYTEST_VERSION", "PYTEST_CURRENT_TEST", "PYTEST_XDIST_WORKER"):
        env.pop(_k, None)
    env.update({
        "DATABASE_URL": f"sqlite:///{tmp}/{name}.db",
        "LANCEDB_PATH": str(tmp / f"{name}-lancedb"),
        "FRONTEND_URL": env.get("FRONTEND_URL", "http://127.0.0.1:1"),
        "BYPASS_RATE_LIMIT": "1",
        "PORT": str(port),
        "LOG_LEVEL": "WARNING",
        "STRUCTLOG_LEVEL": "WARNING",
        "EMBEDDING_PROVIDER": "fastembed",
        "EMBEDDING_MODEL": "BAAI/bge-small-en-v1.5",
        "TELEGRAM_BOT_TOKEN": env.get("TELEGRAM_BOT_TOKEN", ""),
        "TURN_FACT_EXTRACTION_ENABLED": "false",
        "TURN_FACT_PRE_COMPRESS_ENABLED": "false",
        "TURN_FACT_VECTOR_RECALL_ENABLED": "false",
        "ATOM_ORG_SHARING_ENABLED": "false",
    })

    log_path = tmp / f"{name}.log"
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

    deadline = time.monotonic() + 180
    last = ""
    while time.monotonic() < deadline:
        try:
            if requests.get(f"{base}/alive", timeout=3).status_code == 200:
                return proc, base, str(tmp / f"{name}.db")
            last = "status!=200"
        except Exception as e:  # noqa: BLE001
            last = str(e)[:120]
        time.sleep(2)
    tail = log_path.read_text()[-4000:] if log_path.exists() else ""
    proc.terminate()
    proc.wait(timeout=20)
    raise RuntimeError(f"{name} backend failed to start: {last}\n{tail}")


def _stop_backend(proc: subprocess.Popen):
    proc.terminate()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="module")
def oauth_mock(tmp_path_factory) -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), GenericOAuthMockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def oauth_backend(oauth_mock: str, tmp_path_factory):
    """Backend with every OAuth provider pointed at the generic mock and no
    env credentials (so connection-status reflects grants only)."""
    from api.integration_status_routes import _ENV_CREDENTIALS

    tmp = tmp_path_factory.mktemp("all_integrations_e2e")
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    # Scrub any inherited credential env vars so "connected" can only come
    # from the grants this journey creates (and revoke truly disconnects).
    for env_vars in _ENV_CREDENTIALS.values():
        for var in env_vars:
            env.pop(var, None)
    for provider, prefix in PROVIDER_PREFIXES.items():
        if provider == "trello":
            # Trello's config reads TRELLO_API_KEY / TRELLO_API_SECRET, not
            # the client-id-derived names.
            env["TRELLO_API_KEY"] = client_id_for(provider)
            env["TRELLO_API_SECRET"] = "mock-trello-client-secret"
            env["TRELLO_REDIRECT_URI"] = (
                f"{base}/api/v1/auth/oauth/trello/callback"
            )
            env["TRELLO_AUTHORIZE_URL"] = f"{oauth_mock}/trello/authorize"
            env["TRELLO_TOKEN_URL"] = f"{oauth_mock}/trello/token"
            continue
        env[f"{prefix}_CLIENT_ID"] = client_id_for(provider)
        env[f"{prefix}_CLIENT_SECRET"] = f"mock-{provider}-client-secret"
        # The consent button navigates the browser back to this exact URL —
        # it must be the real backend callback, reachable from the browser.
        env[f"{prefix}_REDIRECT_URI"] = (
            f"{base}/api/v1/auth/oauth/{provider}/callback"
        )
        env[f"{prefix}_AUTHORIZE_URL"] = f"{oauth_mock}/{provider}/authorize"
        env[f"{prefix}_TOKEN_URL"] = f"{oauth_mock}/{provider}/token"
    env["FRONTEND_URL"] = oauth_mock
    proc, resolved_base, db = _start_backend(env, tmp, "oauth", port)
    yield {"url": resolved_base, "db": db, "mock": oauth_mock}
    _stop_backend(proc)


@pytest.fixture(scope="module")
def env_backend(tmp_path_factory):
    """Backend with one dummy credential for every env-keyed integration —
    the catalog entries that connect without an in-app flow."""
    from api.integration_status_routes import _ENV_CREDENTIALS

    tmp = tmp_path_factory.mktemp("env_integrations_e2e")
    env = os.environ.copy()
    for env_vars in _ENV_CREDENTIALS.values():
        for var in env_vars[:1]:
            env[var] = "mock-env-credential"
    proc, base, db = _start_backend(env, tmp, "env", _free_port())
    yield {"url": base, "db": db}
    _stop_backend(proc)


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
        "token": token,
        "user_id": data.get("user_id")
        or (data.get("data") or {}).get("user_id")
        or data.get("id"),
    }


def _headers(user: Dict[str, Any]) -> Dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _token_status(db_path: str, provider: str) -> str:
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT status FROM integration_tokens WHERE provider = ?",
            (provider,),
        ).fetchone()
        return row[0] if row else "missing"
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("provider", FULL_JOURNEY_PROVIDERS)
def test_oauth_provider_connect_status_disconnect(
    browser, provider: str, oauth_mock: str, oauth_backend: Dict[str, Any]
):
    base = oauth_backend["url"]
    user = _register_and_login(
        base, f"{provider}.journey.{os.urandom(4).hex()}@example.com", "journey-pass-123"
    )

    # 1. Browser consent with the user's session: initiate -> provider
    #    authorize page -> Approve & Connect -> callback stores tokens.
    context = browser.new_context(extra_http_headers=_headers(user))
    page = context.new_page()
    page.goto(
        f"{base}/api/v1/auth/oauth/{provider}/initiate",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    try:
        page.wait_for_url(f"**/{provider}/authorize**", timeout=15000)
    except Exception:
        # Land the real failure: the page the browser is stuck on (usually a
        # backend JSON error) names which 401/500 the initiate returned.
        raise AssertionError(
            f"initiate never redirected to {provider} consent; landed on "
            f"{page.url}: {page.content()[:400]}"
        )
    page.get_by_role("button", name="Approve & Connect").click()
    page.close()
    context.close()

    # 2. Tokens page shows the provider active.
    deadline = time.monotonic() + 30
    active = False
    while time.monotonic() < deadline:
        r = requests.get(
            f"{base}/api/v1/auth/oauth/tokens", headers=_headers(user), timeout=10
        )
        if r.status_code == 200:
            integrations = r.json().get("integrations", [])
            if any(
                t.get("provider") == provider and t.get("status") == "active"
                for t in integrations
            ):
                active = True
                break
        time.sleep(1)
    assert active, f"tokens page never showed {provider} active after consent"

    # 3. The IntegrationToken row the services read exists and is active.
    assert _token_status(oauth_backend["db"], provider) == "active", (
        f"IntegrationToken row for {provider} missing/not active"
    )

    # 4. Hub status: the provider (and alias cards) connected from the grant.
    r = requests.get(
        f"{base}/api/integrations/connection-status",
        headers=_headers(user),
        timeout=15,
    )
    assert r.status_code == 200, f"connection-status: {r.status_code} {r.text[:300]}"
    hub = r.json().get("providers") or {}
    for hub_id in EXPECTED_HUB_IDS[provider]:
        entry = hub.get(hub_id) or {}
        assert entry.get("connected") is True, (
            f"hub shows {hub_id} not connected after {provider} consent: {entry}"
        )
        assert entry.get("source") == "oauth_token", (
            f"hub source for {hub_id} is {entry.get('source')!r}, expected oauth_token"
        )

    # 5. Disconnect: the hub card flips off and the token row is revoked.
    r = requests.delete(
        f"{base}/api/v1/auth/oauth/tokens/{provider}",
        headers=_headers(user),
        timeout=15,
    )
    assert r.status_code == 200, f"revoke: {r.status_code} {r.text[:300]}"
    assert _token_status(oauth_backend["db"], provider) == "revoked", (
        f"IntegrationToken row for {provider} not revoked after disconnect"
    )
    r = requests.get(
        f"{base}/api/integrations/connection-status",
        headers=_headers(user),
        timeout=15,
    )
    hub = r.json().get("providers") or {}
    for hub_id in EXPECTED_HUB_IDS[provider]:
        entry = hub.get(hub_id) or {}
        assert entry.get("connected") is not True, (
            f"hub still shows {hub_id} connected after disconnecting {provider}"
        )


def test_trello_initiate_reaches_consent(
    browser, oauth_mock: str, oauth_backend: Dict[str, Any]
):
    """Trello is OAuth1 — Atom's generic OAuth2 exchange does not implement
    its signed token flow, so only the browser-facing leg (initiate auth +
    redirect to the provider consent) is asserted here."""
    base = oauth_backend["url"]
    user = _register_and_login(
        base, f"trello.journey.{os.urandom(4).hex()}@example.com", "journey-pass-123"
    )
    context = browser.new_context(extra_http_headers=_headers(user))
    page = context.new_page()
    page.goto(
        f"{base}/api/v1/auth/oauth/trello/initiate",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    page.wait_for_url("**/trello/authorize**", timeout=15000)
    assert page.get_by_role("button", name="Approve & Connect").count() == 1
    page.close()
    context.close()


def test_env_credentials_connect_catalog(env_backend: Dict[str, Any]):
    """Every env-keyed catalog integration shows connected from backend
    credentials — the connect-less half of the hub."""
    from api.integration_status_routes import _ENV_CREDENTIALS

    user = _register_and_login(
        env_backend["url"],
        f"env.journey.{os.urandom(4).hex()}@example.com",
        "journey-pass-123",
    )
    r = requests.get(
        f"{env_backend['url']}/api/integrations/connection-status",
        headers=_headers(user),
        timeout=15,
    )
    assert r.status_code == 200, r.text[:300]
    hub = r.json().get("providers") or {}
    missing = [
        pid for pid in _ENV_CREDENTIALS
        if (hub.get(pid) or {}).get("connected") is not True
    ]
    assert not missing, (
        f"env-keyed integrations not connected with credentials set: {missing}"
    )
    wrong_source = {
        pid: hub[pid].get("source")
        for pid in _ENV_CREDENTIALS
        if hub.get(pid, {}).get("source") != "env"
    }
    assert not wrong_source, f"env-keyed integrations with wrong source: {wrong_source}"


def test_generic_mock_rejects_bad_clients():
    """The mock honours the contract the journeys rely on: unknown provider /
    wrong client id are rejected at consent and token endpoints."""
    import threading as _t
    import generic_oauth_mock_server

    server = ThreadingHTTPServer(("127.0.0.1", 0), GenericOAuthMockHandler)
    _t.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        # Unknown provider.
        r = requests.get(
            f"{base}/not-a-provider/authorize",
            params={
                "client_id": "mock-not-a-provider-client-id",
                "redirect_uri": "http://x/cb",
                "state": "s",
            },
            timeout=10,
        )
        assert r.status_code == 400
        # Known provider, wrong client id.
        r = requests.get(
            f"{base}/slack/authorize",
            params={"client_id": "wrong", "redirect_uri": "http://x/cb", "state": "s"},
            timeout=10,
        )
        assert r.status_code == 400
        r = requests.post(
            f"{base}/slack/token",
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
        # Known provider, correct client id, bad grant type.
        r = requests.post(
            f"{base}/slack/token",
            data={
                "grant_type": "password",
                "client_id": client_id_for("slack"),
                "client_secret": "x",
                "redirect_uri": "http://x/cb",
                "code": "c",
            },
            timeout=10,
        )
        assert r.status_code == 400
    finally:
        server.shutdown()
        server.server_close()
