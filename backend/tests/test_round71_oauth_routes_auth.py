"""RED tests — Round 71: auth gaps in api/oauth_routes.py (the v1 surface).

The B7 fix added router-level auth to `oauth_status_routes.py` (the /api/auth/*
alias surface). But the *canonical* v1 OAuth router — `api/oauth_routes.py` —
has no auth dependency at all, so the same /initiate endpoint is reachable
unauthenticated at its real URL. These tests document that gap.

Findings under test:
  B14 — `GET /api/v1/auth/oauth/{provider}/initiate` has no auth; an
        unauthenticated caller gets a 302 redirect (should be 401).
        (`api/oauth_routes.py:oauth_initiate`, router has no `dependencies=`)
  B15 — `GET /api/v1/auth/oauth/tokens` and `DELETE /api/v1/auth/oauth/tokens/
        {provider}` reference OAuthToken columns that don't exist
        (`provider`, `status`, `expires_at`, `last_used`) → AttributeError 500.
        (`api/oauth_routes.py:list_oauth_tokens` / `revoke_oauth_token` vs
         `core/models.py:OAuthToken`)
  B16 — The B8 `_KNOWN_PROVIDERS` allowlist in oauth_status_routes.py is
        inconsistent with the v1 provider config: it includes `gmail` (which
        v1 rejects with 400) and omits `linkedin`/`salesforce` (which v1
        supports). An authenticated caller hitting `/api/auth/gmail/initiate`
        is bounced to a URL that then errors.

TDD: red first, then fix.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Mount only the v1 OAuth router so we exercise it in isolation."""
    from api.oauth_routes import router as oauth_router

    app = FastAPI()
    app.include_router(oauth_router)
    return TestClient(app)


# --- B14: /initiate is unauthenticated --------------------------------------


def test_v1_oauth_initiate_requires_auth(client):
    """B14: the canonical v1 /initiate endpoint must require auth, mirroring
    the B7 fix on the alias router. Without it, the alias auth gate is
    theater — an attacker just calls the v1 URL directly."""
    resp = client.get("/api/v1/auth/oauth/google/initiate", follow_redirects=False)
    assert resp.status_code in (401, 403), (
        f"B14 regression: /api/v1/auth/oauth/google/initiate returned "
        f"{resp.status_code} without auth. The v1 OAuth router has no auth "
        f"dependency, so the B7 alias fix is bypassable."
    )


# --- B15: /tokens references nonexistent OAuthToken columns -----------------


def test_v1_oauth_tokens_route_references_valid_model_attributes():
    """B15: the /tokens and /tokens/{provider} handlers read attributes that
    do not exist on the OAuthToken model. We assert statically because the
    route also double-calls get_current_user in its body (which 401s before
    the model code is reached), masking the AttributeError over HTTP — but
    the model mismatch is a latent crash that will fire the moment auth is
    wired. Catching it now (TDD) prevents the regression.

    Static check: every `t.<attr>` / `OAuthToken.<attr>` referenced in the
    handlers must exist as a column on the model."""
    import inspect
    import re as _re

    import api.oauth_routes as v1
    from core.models import OAuthToken

    valid_cols = {c.name for c in OAuthToken.__table__.columns}

    # Inspect the two handlers' source for attribute reads on token rows.
    offenders = []
    for fn_name in ("list_oauth_tokens", "revoke_oauth_token"):
        fn = getattr(v1, fn_name, None)
        assert fn is not None, f"{fn_name} not found"
        src = inspect.getsource(fn)
        # Match `t.foo` / `token.foo` row accesses and `OAuthToken.foo` filters.
        for m in _re.finditer(r"(?:t|token)\.([a-z_]+)", src):
            offenders.append((fn_name, m.group(1)))
        for m in _re.finditer(r"OAuthToken\.([a-z_]+)", src):
            offenders.append((fn_name, m.group(1)))

    missing = [(fn, attr) for fn, attr in offenders if attr not in valid_cols]
    assert not missing, (
        f"B15 regression: /tokens handlers reference OAuthToken attributes "
        f"that don't exist on the model {sorted(valid_cols)}: {missing}"
    )


# --- B16: provider allowlist inconsistent with v1 ---------------------------


def test_known_providers_match_v1_config():
    """B16: the B8 allowlist in oauth_status_routes must be consistent with the
    providers the v1 router actually supports. `gmail` is in the allowlist but
    v1 only knows `google`; `linkedin`/`salesforce` are supported by v1 but
    missing from the allowlist."""
    import inspect
    import re as _re

    import api.oauth_routes as v1
    from oauth_status_routes import _KNOWN_PROVIDERS

    # Reconstruct the set of providers v1 actually accepts (the configs dict
    # inside oauth_initiate). We assert the allowlist ⊆ accepted-v1-targets.
    src = inspect.getsource(v1.oauth_initiate)
    # The handler 400s for any provider not in its inline configs dict.
    v1_keys = set(_re.findall(r'"([a-z_]+)":\s*[A-Z]+_OAUTH_CONFIG', src))
    assert v1_keys, "could not parse v1 provider configs from oauth_initiate source"

    # Every allowlisted provider must, after alias mapping, resolve to a v1 key.
    # Use the production alias map (not a local copy) so this test tracks the
    # real wiring.
    from oauth_status_routes import _PROVIDER_ALIAS_MAP

    unresolved = []
    for p in _KNOWN_PROVIDERS:
        target = _PROVIDER_ALIAS_MAP.get(p, p)
        if target not in v1_keys:
            unresolved.append((p, target))
    assert not unresolved, (
        f"B16 regression: allowlist providers that v1 rejects: {unresolved}. "
        f"v1 supports {sorted(v1_keys)}."
    )


# --- B17: Bearer token silently ignored by the v1 auth wrapper ---------------


def test_v1_oauth_get_current_user_passes_bearer_token():
    """RED: oauth_routes.get_current_user must extract the Bearer token from
    the Authorization header and hand it to ``core.auth.get_current_user``.
    Since commit 49de5a594 the wrapper passes ``token=None`` unconditionally,
    so every Bearer-authenticated call to ``/api/v1/auth/oauth/*`` 401s with
    'Could not validate credentials' (cookie-only sessions still worked,
    masking the bug). The wrapper's own docstring promises to verify "a JWT
    (Bearer header or NextAuth cookie)", but only the cookie path ever ran."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, patch

    import api.oauth_routes as v1

    captured = {}
    fake_core = AsyncMock(return_value="user-obj")
    fake_core.side_effect = lambda request, token, db: captured.__setitem__("token", token)

    request = SimpleNamespace(
        headers={"Authorization": "Bearer abc.def.ghi"},
        query_params={},
        cookies={},
    )

    with patch("core.auth.get_current_user", fake_core):
        asyncio.run(v1.get_current_user(request, db=None))

    assert captured.get("token") == "abc.def.ghi", (
        f"B17 regression: get_current_user passed token={captured.get('token')!r} "
        f"to core.auth instead of the Bearer token. The v1 OAuth surface is "
        f"unusable over Bearer auth."
    )
