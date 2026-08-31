"""OAuthConfig journey/e2e URL overrides.

The generic OAuth flow (api/oauth_routes.py) is provider-agnostic; only the
provider's authorize/token endpoints differ. Journey tests point those at a
local mock via {PREFIX}_AUTHORIZE_URL / {PREFIX}_TOKEN_URL, derived from each
config's client-id env name — the same pattern as MICROSOFT_AUTHORITY_BASE
and ZOHO_ACCOUNTS_BASE. These tests lock the derivation so a renamed env
var cannot silently strand a provider on its real domain.
"""

import os
from unittest.mock import patch

from core.oauth_handler import (
    MICROSOFT_OAUTH_CONFIG,
    PROVIDER_CONFIGS,
    OAuthConfig,
)


def _config_for(client_id_env: str) -> OAuthConfig:
    return OAuthConfig(
        client_id_env=client_id_env,
        client_secret_env="X_CLIENT_SECRET",
        redirect_uri_env="X_REDIRECT_URI",
        auth_url="https://real.example.com/authorize",
        token_url="https://real.example.com/token",
        scopes=["scope"],
    )


def test_override_derived_from_client_id_env():
    with patch.dict(
        os.environ,
        {
            "GOOGLE_AUTHORIZE_URL": "http://127.0.0.1:9/google/authorize",
            "GOOGLE_TOKEN_URL": "http://127.0.0.1:9/google/token",
        },
    ):
        config = _config_for("GOOGLE_CLIENT_ID")
    assert config.auth_url == "http://127.0.0.1:9/google/authorize"
    assert config.token_url == "http://127.0.0.1:9/google/token"


def test_no_override_keeps_real_endpoints():
    config = _config_for("SLACK_CLIENT_ID")
    assert config.auth_url == "https://real.example.com/authorize"
    assert config.token_url == "https://real.example.com/token"


def test_every_provider_config_resolves_a_unique_prefix():
    """Each catalog config must derive a distinct override prefix — two
    providers collapsing onto one prefix would let a single env var move
    both providers' endpoints."""
    def prefix_of(client_id_env: str) -> str:
        if client_id_env.endswith("_CLIENT_ID"):
            return client_id_env[: -len("_CLIENT_ID")]
        if client_id_env.endswith("_API_KEY"):
            return client_id_env[: -len("_API_KEY")]
        return client_id_env

    prefixes = [prefix_of(c._client_id_env) for c in PROVIDER_CONFIGS.values()]
    assert len(prefixes) == len(set(prefixes)), (
        f"override prefixes collide: {sorted(prefixes)}"
    )
    # Trello's client-id env is TRELLO_API_KEY — its override prefix must
    # still be the plain provider name.
    assert prefix_of("TRELLO_API_KEY") == "TRELLO"
    # Microsoft keeps its dedicated authority override too.
    assert "login.microsoftonline.com" in MICROSOFT_OAUTH_CONFIG.auth_url
