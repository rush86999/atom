"""
TDD regression tests for Round 25 bug hunt - LLM & cognitive systems auth.

Critical: byok_routes.store_api_key and llm_oauth_routes credential routes
had NO auth — API key/credential tampering by unauthenticated users.
"""

from __future__ import annotations

import inspect


def _has_auth_dependency(func) -> bool:
    deps = []
    for p in inspect.signature(func).parameters.values():
        if p.default is inspect.Parameter.empty:
            continue
        if hasattr(p.default, "dependency"):
            name = getattr(p.default.dependency, "__name__", "") or p.default.dependency.__class__.__name__
            deps.append(name)
        elif hasattr(p.default, "__name__"):
            deps.append(p.default.__name__)
    markers = ("get_current_user", "verify_token", "require_user", "require_auth",
               "require_permission", "require_governance", "get_current_active_user",
               "require_admin")
    return any(any(m in d for m in markers) for d in deps)


class TestByokRoutesRequireAuth:
    def _load(self):
        from api import byok_routes as mod
        return mod

    def test_store_api_key_requires_auth(self):
        assert _has_auth_dependency(self._load().store_api_key), (
            "POST store_api_key has no auth — unauthenticated API key storage"
        )

    def test_get_ai_providers_requires_auth(self):
        assert _has_auth_dependency(self._load().get_ai_providers), (
            "GET get_ai_providers has no auth — provider/key enumeration"
        )


class TestLlmOauthRoutesRequireAuth:
    def _load(self):
        from api import llm_oauth_routes as mod
        return mod

    def test_list_credentials_requires_auth(self):
        assert _has_auth_dependency(self._load().list_credentials), (
            "GET list_credentials has no auth — credential enumeration"
        )

    def test_revoke_credential_requires_auth(self):
        assert _has_auth_dependency(self._load().revoke_credential), (
            "POST revoke_credential has no auth — anyone can revoke credentials (DoS)"
        )

    def test_refresh_credential_requires_auth(self):
        assert _has_auth_dependency(self._load().refresh_credential), (
            "POST refresh_credential has no auth"
        )


class TestCognitiveTierRoutesRequireAuth:
    def _load(self):
        from api import cognitive_tier_routes as mod
        return mod

    def test_update_budget_requires_auth(self):
        assert _has_auth_dependency(self._load().update_budget), (
            "POST update_budget has no auth — anyone can change LLM budget"
        )

    def test_delete_preferences_requires_auth(self):
        assert _has_auth_dependency(self._load().delete_preferences), (
            "DELETE delete_preferences has no auth"
        )
