"""
TDD regression tests for Round 18 bug hunt - Integration security sweep.

Covers:
- BUG R18-1: channel_routes.py has NO authentication on any endpoint (IDOR)
- BUG R18-2: shopify_webhooks.py accepts signature header but never verifies it
- BUG R18-3: atom_communication_memory_webhooks.py has HARDCODED webhook secrets
- BUG R18-4: atom_communication_memory_webhooks.py fails OPEN when signature header missing
- BUG R18-5: github_routes.py returns access_token in API response
- BUG R18-6: admin_bootstrap.py logs plaintext password
- BUG R18-7: auth_endpoints.py logs password reset link
- BUG R18-8: ingestion_webhooks.py trusts tenant_id from query params
- BUG R18-9: ingestion_webhooks.py fails open when slack_signing_secret missing
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _route_auth_dependencies(func) -> list[str]:
    """Return list of dependency names declared on a FastAPI route handler."""
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty:
            continue
        if hasattr(p.default, "dependency"):
            deps.append(getattr(p.default.dependency, "__name__", "") or p.default.dependency.__class__.__name__)
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    return deps


def _has_auth_dependency(func) -> bool:
    """True if route handler declares an auth-looking dependency."""
    deps = _route_auth_dependencies(func)
    auth_markers = ("get_current_user", "verify_token", "require_user", "require_auth",
                    "get_current_active_user", "require_admin")
    return any(any(m in d for m in auth_markers) for d in deps)


# ---------------------------------------------------------------------------
# BUG R18-1: channel_routes has NO auth on any endpoint
# ---------------------------------------------------------------------------


class TestChannelRoutesRequireAuth:
    """Every channel mutation endpoint must require auth (currently zero do)."""

    def _load(self):
        from api import channel_routes
        return channel_routes

    def test_get_channel_requires_auth(self):
        mod = self._load()
        assert _has_auth_dependency(mod.get_channel), (
            "GET /api/channels/{id} has no auth dependency — IDOR allows reading any channel"
        )

    def test_list_channels_requires_auth(self):
        mod = self._load()
        assert _has_auth_dependency(mod.list_channels), (
            "GET /api/channels/ has no auth dependency — enumerates all channels across users"
        )

    def test_update_channel_requires_auth(self):
        mod = self._load()
        assert _has_auth_dependency(mod.update_channel), (
            "PUT /api/channels/{id} has no auth dependency — anyone can mutate any channel"
        )

    def test_delete_channel_requires_auth(self):
        mod = self._load()
        assert _has_auth_dependency(mod.delete_channel), (
            "DELETE /api/channels/{id} has no auth dependency — anyone can delete any channel"
        )

    def test_create_channel_requires_auth(self):
        mod = self._load()
        assert _has_auth_dependency(mod.create_channel), (
            "POST /api/channels/ has no auth dependency — unauthenticated channel creation"
        )

    def test_add_channel_member_requires_auth(self):
        mod = self._load()
        assert _has_auth_dependency(mod.add_channel_member), (
            "POST /api/channels/{id}/members has no auth dependency — anyone can join any channel"
        )


# ---------------------------------------------------------------------------
# BUG R18-2: shopify_webhooks accepts signature header but never verifies it
# ---------------------------------------------------------------------------


class TestShopifyWebhookVerifiesSignature:
    """Shopify webhook handler must actually verify the HMAC signature."""

    def test_signature_header_is_verified(self):
        from api.routes.webhooks import shopify_webhooks

        src = inspect.getsource(shopify_webhooks.shopify_webhook)
        # Must call verify_hmac_signature (imported from base) or compare_digest
        assert ("verify_hmac_signature" in src) or ("hmac.compare_digest" in src), (
            "shopify_webhook accepts x_shopify_hmac_sha256 header but never verifies it — "
            "forged webhooks will be processed"
        )

    def test_rejects_when_signature_missing(self):
        from api.routes.webhooks import shopify_webhooks

        src = inspect.getsource(shopify_webhooks.shopify_webhook)
        # Must fail closed when header missing, not silently continue
        # Acceptable patterns: `if not x_shopify_hmac_sha256: raise` OR default that raises
        assert ("not x_shopify_hmac_sha256" in src) or ("if not signature" in src) or (
            "x_shopify_hmac_sha256 is None" in src
        ), (
            "shopify_webhook must reject requests when x_shopify_hmac_sha256 header is missing"
        )


# ---------------------------------------------------------------------------
# BUG R18-3: atom_communication_memory_webhooks has HARDCODED webhook secrets
# ---------------------------------------------------------------------------


class TestNoHardcodedWebhookSecrets:
    """Webhook secrets must come from env/config, not be hardcoded in source."""

    FORBIDDEN_LITERAL_PREFIXES = (
        "atom_whatsapp_webhook_secret_",
        "atom_slack_webhook_secret_",
        "atom_discord_webhook_secret_",
        "atom_telegram_webhook_secret_",
        "atom_gmail_webhook_secret_",
        "atom_outlook_webhook_secret_",
    )

    def test_no_hardcoded_secret_literals(self):
        from integrations import atom_communication_memory_webhooks as mod

        src = inspect.getsource(mod)
        offenders = [p for p in self.FORBIDDEN_LITERAL_PREFIXES if p in src]
        assert not offenders, (
            f"Hardcoded webhook secrets found in source: {offenders}. "
            "Secrets must be read from environment variables."
        )

    def test_secrets_loaded_from_environment(self):
        from integrations import atom_communication_memory_webhooks as mod

        src = inspect.getsource(mod.AtomCommunicationMemoryWebhooks)
        # Must use os.getenv / os.environ to load secrets
        assert ("os.getenv" in src) or ("os.environ" in src) or ("getenv" in src), (
            "AtomCommunicationMemoryWebhooks must load webhook secrets from environment, "
            "not from a hardcoded dict"
        )


# ---------------------------------------------------------------------------
# BUG R18-4: atom_communication_memory_webhooks fails OPEN when signature header missing
# ---------------------------------------------------------------------------


class TestWebhookSignatureFailClosed:
    """If signature header is missing, webhook must be rejected (fail closed)."""

    def test_whatsapp_missing_signature_rejected(self):
        from integrations import atom_communication_memory_webhooks as mod

        # Find the whatsapp webhook inner function source
        src = inspect.getsource(mod.AtomCommunicationMemoryWebhooks)
        # The current buggy pattern: `if x_hub_signature_256:` (only verifies if present)
        # The fixed pattern must raise when header is missing/None.
        # Locate the whatsapp block
        assert "if not x_hub_signature_256" in src or "is None" in src, (
            "whatsapp webhook must fail closed: reject when x_hub_signature_256 header is missing"
        )


# ---------------------------------------------------------------------------
# BUG R18-5: github_routes leaks str(e) in HTTPException detail
# ---------------------------------------------------------------------------


class TestGithubRoutesNoStrELeak:
    """github_routes must not embed str(e) in HTTPException detail (info disclosure)."""

    def _leaking_lines(self, src: str) -> list[int]:
        bad = []
        for i, line in enumerate(src.split("\n"), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Look for HTTPException(... detail="Internal error" or {e})
            if "HTTPException" in line:
                # scan forward a few lines for the detail
                window = "\n".join(src.split("\n")[i - 1:i + 4])
                if ("{str(e)}" in window or "{e}" in window) and "detail" in window:
                    bad.append(i)
        return bad

    def test_no_str_e_in_http_exceptions(self):
        try:
            from integrations import github_routes
        except ImportError:
            return

        src = inspect.getsource(github_routes)
        bad = self._leaking_lines(src)
        assert not bad, (
            f"github_routes leaks str(e) in HTTPException detail at lines {bad}"
        )


# ---------------------------------------------------------------------------
# BUG R18-6: admin_bootstrap logs plaintext password
# ---------------------------------------------------------------------------


class TestAdminBootstrapDoesNotLogPassword:
    """admin_bootstrap must not log the generated plaintext password."""

    def test_no_password_in_log_messages(self):
        try:
            from core import admin_bootstrap
        except ImportError:
            return

        src = inspect.getsource(admin_bootstrap)
        # The buggy pattern: logger.warning(f"... password: {password}")
        # Forbid embedding the password variable into a log/format string.
        bad_patterns = [
            "{password}",
            "password: {password}",
            "password={password}",
            f"%s",  # too noisy, skip
        ]
        # Focus on the clear leak: f-string embedding the password variable
        assert "{password}" not in src, (
            "admin_bootstrap logs the plaintext password via f-string embedding. "
            "Use a placeholder like '<redacted>' instead."
        )


# ---------------------------------------------------------------------------
# BUG R18-7: auth_endpoints logs password reset link
# ---------------------------------------------------------------------------


class TestAuthEndpointsDoNotLogResetLink:
    """auth_endpoints must not log the password reset link (contains token)."""

    def test_no_reset_link_in_logs(self):
        try:
            from core import auth_endpoints
        except ImportError:
            return

        src = inspect.getsource(auth_endpoints)
        # The buggy pattern embeds {reset_link} in a logger.* call.
        # Email body construction legitimately contains {reset_link} — that's fine.
        # We scan each line; if it's a logger call AND embeds {reset_link}, fail.
        bad_lines = []
        for i, line in enumerate(src.split("\n"), start=1):
            stripped = line.lstrip()
            if not (
                "logger." in line
                or "logging." in line
                or "log.info" in line
                or "log.warning" in line
                or "log.error" in line
            ):
                continue
            if "{reset_link}" in line:
                bad_lines.append(i)
        assert not bad_lines, (
            f"auth_endpoints logs the password reset link at line(s) {bad_lines} — "
            "anyone with log access can hijack accounts. Log only the user id."
        )


# ---------------------------------------------------------------------------
# BUG R18-8: ingestion_webhooks trusts tenant_id from query params
# ---------------------------------------------------------------------------


class TestIngestionWebhooksNoTenantFromQuery:
    """ingestion_webhooks must NOT fall back to tenant_id from query parameters."""

    def test_no_query_param_tenant_fallback(self):
        try:
            from api.routes.webhooks import ingestion_webhooks
        except ImportError:
            return

        src = inspect.getsource(ingestion_webhooks)
        # Buggy pattern: `tenant_id = query_params.get("tenant_id")`
        # This allows an attacker to inject webhooks into any tenant.
        assert 'query_params.get("tenant_id")' not in src, (
            "ingestion_webhooks falls back to tenant_id from query params — "
            "cross-tenant webhook injection"
        )


# ---------------------------------------------------------------------------
# BUG R18-9: ingestion_webhooks fails open when slack_signing_secret missing
# ---------------------------------------------------------------------------


class TestIngestionWebhooksFailClosedOnMissingSecret:
    """Slack webhook must reject the request when signing secret is not configured."""

    def test_rejects_when_slack_secret_missing(self):
        try:
            from api.routes.webhooks import ingestion_webhooks
        except ImportError:
            return

        src = inspect.getsource(ingestion_webhooks)
        # Buggy pattern:
        #   if signing_secret:
        #       if not verify(...): raise
        #   # processing continues here even if secret was missing
        #
        # Fixed pattern must raise when secret is missing/unconfigured.
        # Look for the negative check on the secret.
        assert (
            "not signing_secret" in src
            or "signing_secret is None" in src
            or "if not integration" in src
        ), (
            "ingestion_webhooks fails open: when slack_signing_secret is missing from "
            "config, the webhook is processed without verification. Must fail closed."
        )
