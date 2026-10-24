"""Provider policy: allowed destinations vs saved credentials.

These are policy-boundary tests, not model campaigns. They prove that a
full BYOK store can remain intact while dispatch is confined, that pins
and fallback are rechecked, and that malformed/empty policy fails closed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.llm.byok_handler import BYOKHandler
from core.llm.provider_policy import (
    ProviderPolicy,
    ProviderPolicyError,
    resolve_provider_policy,
    validate_provider_policy,
)
from core.runtime_settings import ResolvedSetting, StrictSettingError


def test_validate_automatic_and_selected_policy():
    auto = validate_provider_policy(
        {"mode": "automatic", "allowed_providers": [],
         "preferred": {"provider": "ollama", "model": "llama3.1:8b"}},
        known_ids={"ollama", "deepseek", "openrouter"},
    )
    assert auto["mode"] == "automatic"
    assert auto["preferred"]["provider"] == "ollama"

    selected = validate_provider_policy(
        {"mode": "selected", "allowed_providers": ["ollama", "deepseek"],
         "preferred": {"provider": "ollama", "model": "llama3.1:8b"}},
        known_ids={"ollama", "deepseek", "openrouter"},
    )
    assert selected["allowed_providers"] == ["ollama", "deepseek"]


def test_validate_rejects_unknown_and_outside_preferred():
    with pytest.raises(ProviderPolicyError, match="unknown provider"):
        validate_provider_policy(
            {"mode": "selected", "allowed_providers": ["not-a-provider"]},
            known_ids={"ollama"})
    with pytest.raises(ProviderPolicyError, match="must be in allowed"):
        validate_provider_policy(
            {"mode": "selected", "allowed_providers": ["ollama"],
             "preferred": {"provider": "deepseek", "model": "deepseek-v4-pro"}},
            known_ids={"ollama", "deepseek"})


def test_validate_empty_selected_is_no_routes_not_unrestricted():
    canonical = validate_provider_policy(
        {"mode": "selected", "allowed_providers": []},
        known_ids={"ollama", "openrouter"})
    policy = ProviderPolicy(
        mode="selected",
        allowed_providers=frozenset(canonical["allowed_providers"]))
    assert policy.enforced is True
    assert policy.allows("ollama") is False
    assert policy.filter_routes([("ollama", "x")]) == []


def test_malformed_policy_fails_closed(monkeypatch):
    def _raise(_key):
        raise StrictSettingError("bad JSON")

    monkeypatch.setattr(
        "core.runtime_settings.resolve_setting_strict", _raise)
    policy = resolve_provider_policy()
    assert policy.mode == "invalid"
    assert policy.error
    assert policy.allows("ollama") is False


def test_strict_resolver_rejects_malformed_env(monkeypatch):
    from core.runtime_settings import resolve_setting_strict

    monkeypatch.setenv("ATOM_LLM_PROVIDER_POLICY", "{not-json")
    with pytest.raises(StrictSettingError):
        resolve_setting_strict("ATOM_LLM_PROVIDER_POLICY")


def test_malformed_env_policy_is_managed_and_fails_closed(monkeypatch):
    monkeypatch.setenv("ATOM_LLM_PROVIDER_POLICY", "{not-json")
    policy = resolve_provider_policy()
    assert policy.mode == "invalid"
    assert policy.source == "env"
    assert policy.managed_by_env is True
    assert policy.allows("openrouter") is False


def test_literal_null_env_policy_is_malformed(monkeypatch):
    monkeypatch.setenv("ATOM_LLM_PROVIDER_POLICY", "null")
    policy = resolve_provider_policy()
    assert policy.mode == "invalid"
    assert policy.managed_by_env is True
    assert policy.allows("ollama") is False


def test_unset_policy_preserves_legacy_behavior(monkeypatch):
    monkeypatch.setattr(
        "core.runtime_settings.resolve_setting_strict",
        lambda _key: ResolvedSetting(value=None, source="default"))
    policy = resolve_provider_policy()
    assert policy.mode == "unset"
    assert policy.allows("openrouter") is True
    assert policy.allows("ollama") is True


def test_selected_policy_filters_routes_and_providers():
    policy = ProviderPolicy(
        mode="selected",
        allowed_providers=frozenset({"ollama", "deepseek"}),
        revision="r1")
    assert policy.allows("ollama") is True
    assert policy.allows("openrouter") is False
    assert policy.filter_routes([
        ("openrouter", "z-ai/glm-5.3-flash"),
        ("deepseek", "deepseek-v4-pro"),
        ("ollama", "llama3.1:8b"),
    ]) == [("deepseek", "deepseek-v4-pro"),
           ("ollama", "llama3.1:8b")]


def _bare_handler(policy: ProviderPolicy):
    handler = object.__new__(BYOKHandler)
    handler.provider_policy = policy
    handler.clients = {"ollama": object(), "deepseek": object(),
                       "openrouter": object()}
    handler._local_routes = {}
    handler._ollama_runtime_state = lambda: ("up", None)
    handler._protocol_incompatible = lambda *a, **k: False
    handler._explicit_primary_requested = lambda *a, **k: True
    handler._provider_serves_model = lambda *a, **k: True
    return handler


def test_dispatch_gate_blocks_forbidden_even_for_explicit_pin():
    handler = _bare_handler(ProviderPolicy(
        mode="selected", allowed_providers=frozenset({"ollama"}),
        revision="r1"))
    assert handler._dispatch_catalog_admits(
        "openrouter", "z-ai/glm-5.3-flash", "openrouter",
        operation="text", explicit_route=True) is False
    assert handler._dispatch_catalog_admits(
        "ollama", "llama3.1:8b", "ollama",
        operation="text", explicit_route=True) is True


def test_fallback_order_cannot_include_forbidden_provider():
    handler = _bare_handler(ProviderPolicy(
        mode="selected", allowed_providers=frozenset({"ollama"}),
        revision="r1"))
    order = handler._get_provider_fallback_order("openrouter")
    assert order == ["ollama"]


def test_effective_handler_with_empty_selected_has_no_routes():
    handler = _bare_handler(ProviderPolicy(
        mode="selected", allowed_providers=frozenset(), revision="empty"))
    assert handler._get_provider_fallback_order("ollama") == []
    assert handler._dispatch_catalog_admits(
        "ollama", "llama3.1:8b", "ollama", operation="text") is False


@pytest.mark.asyncio
async def test_policy_api_rejects_unknown_and_persists_canonical(monkeypatch):
    import api.byok_routes as br

    class Admin:
        email = "owner@example.com"
        role = "workspace_admin"

    class DB:
        def __init__(self):
            self.rows = []
            self.commits = 0

        def get(self, _model, _key):
            return None

        def add(self, row):
            self.rows.append(row)

        def commit(self):
            self.commits += 1

        def rollback(self):
            pass

    manager = SimpleNamespace(providers={
        "ollama": SimpleNamespace(name="Ollama"),
        "deepseek": SimpleNamespace(name="DeepSeek"),
    })
    monkeypatch.delenv("ATOM_LLM_PROVIDER_POLICY", raising=False)
    monkeypatch.setattr(
        "core.llm.provider_policy.resolve_provider_policy",
        lambda *a, **k: ProviderPolicy(
            mode="selected", allowed_providers=frozenset({"ollama"}),
            preferred=("ollama", "llama3.1:8b"), source="db",
            revision="abc123"))

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as denied:
        await br.update_provider_policy(
            {"mode": "selected", "allowed_providers": ["unknown"]},
            admin=Admin(), byok_manager=manager, db=DB())
    assert denied.value.status_code == 400

    db = DB()
    response = await br.update_provider_policy(
        {"mode": "selected", "allowed_providers": ["ollama"],
         "preferred": {"provider": "ollama", "model": "llama3.1:8b"}},
        admin=Admin(), byok_manager=manager, db=db)
    assert response.success is True
    assert response.data["policy"]["mode"] == "selected"
    assert db.commits == 1
    assert any(getattr(r, "key", None) == "ATOM_LLM_PROVIDER_POLICY"
               for r in db.rows)


@pytest.mark.asyncio
async def test_policy_api_env_override_is_authoritative(monkeypatch):
    import api.byok_routes as br
    from fastapi import HTTPException

    monkeypatch.setenv("ATOM_LLM_PROVIDER_POLICY",
                       '{"mode":"selected","allowed_providers":["ollama"]}')
    with pytest.raises(HTTPException) as denied:
        await br.update_provider_policy(
            {"mode": "automatic", "allowed_providers": []},
            admin=SimpleNamespace(email="o@example.com",
                                  role="workspace_admin"),
            byok_manager=SimpleNamespace(providers={}),
            db=SimpleNamespace())
    assert denied.value.status_code == 409


@pytest.mark.asyncio
async def test_vision_auxiliary_cannot_use_forbidden_provider():
    handler = _bare_handler(ProviderPolicy(
        mode="selected", allowed_providers=frozenset({"ollama"}),
        revision="r1"))
    calls = []

    class VisionClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    # Production calls this through _to_thread_safe, so the
                    # fake must be synchronous or it records nothing.
                    calls.append(kwargs)
                    raise AssertionError("forbidden vision dispatch")

    handler.clients = {"gemini": VisionClient(), "openai": VisionClient()}
    handler._capture_echoed_model = lambda *a, **k: None
    out = await handler._get_coordinated_vision_description(
        "abc123", "free", True)
    assert out is None
    assert calls == []


@pytest.mark.asyncio
async def test_vision_auxiliary_uses_allowed_provider():
    handler = _bare_handler(ProviderPolicy(
        mode="selected",
        allowed_providers=frozenset({"ollama", "deepseek"}),
        revision="r2"))
    calls = []

    class VisionClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs)
                    return SimpleNamespace(
                        choices=[SimpleNamespace(
                            message=SimpleNamespace(
                                content="allowed vision description"))])

    handler.clients = {"deepseek": VisionClient()}
    handler._capture_echoed_model = lambda *a, **k: None
    out = await handler._get_coordinated_vision_description(
        "abc123", "free", True)
    assert out == "allowed vision description"
    assert calls and calls[0]["model"] == "janus-pro-7b"


@pytest.mark.asyncio
async def test_transcription_and_embeddings_fail_closed():
    handler = _bare_handler(ProviderPolicy(
        mode="selected", allowed_providers=frozenset({"ollama"}),
        revision="r1"))
    handler.async_clients = {}
    with pytest.raises(ValueError, match="policy excludes"):
        await handler.generate_transcription(file=object(), model="whisper-1")
    with pytest.raises(ValueError, match="policy excludes"):
        await handler.generate_embedding("text", "text-embedding-3-small")
    with pytest.raises(ValueError, match="policy excludes"):
        await handler.generate_embeddings_batch(
            ["a", "b"], "text-embedding-3-small")


def test_llm_service_handler_property_uses_refresh_path(monkeypatch):
    from core.llm_service import LLMService

    service = object.__new__(LLMService)
    service._scope_unresolved_reason = None
    service._handler = object()
    sentinel = object()
    service._get_handler = lambda *a, **k: sentinel
    assert service.handler is sentinel


def test_clear_provider_check_on_key_change():
    from api.byok_routes import ProviderUsage, _clear_provider_check

    usage = ProviderUsage(
        provider_id="openai",
        last_check_at="2026-10-24T12:00:00Z",
        last_check_ok=True,
        last_check_status="ready",
        last_check_message="ok",
        last_check_provider="openai",
        last_check_model="gpt-4o-mini",
        last_check_latency_ms=10,
    )

    class Manager:
        def get_tenant_usage(self, _tenant):
            return {"openai": usage}

    _clear_provider_check(Manager(), "t1", "openai")
    assert usage.last_check_at is None
    assert usage.last_check_ok is None
    assert usage.last_check_status is None


@pytest.mark.asyncio
async def test_generic_admin_settings_rejects_policy_under_env(monkeypatch):
    import api.admin_runtime_settings_routes as admin_routes
    from fastapi import HTTPException

    monkeypatch.setenv("ATOM_LLM_PROVIDER_POLICY",
                       '{"mode":"selected","allowed_providers":["ollama"]}')
    with pytest.raises(HTTPException) as denied:
        await admin_routes.update_setting(
            "ATOM_LLM_PROVIDER_POLICY",
            SimpleNamespace(value={"mode": "automatic"}),
            admin=SimpleNamespace(email="o@example.com"),
            db=SimpleNamespace())
    assert denied.value.status_code == 409


def test_forbidden_pin_is_refused_before_dispatch():
    from core.llm.pinned_planning import build_provider_model_pin

    handler = _bare_handler(ProviderPolicy(
        mode="selected", allowed_providers=frozenset({"ollama"}),
        revision="r1"))

    class Service:
        def _get_handler(self, **_kwargs):
            return handler

    assert build_provider_model_pin(
        Service(), "openrouter", "z-ai/glm-5.3-flash") == {}
    assert build_provider_model_pin(
        Service(), "ollama", "llama3.1:8b") == {
            "provider_model": ("ollama", "llama3.1:8b")}
