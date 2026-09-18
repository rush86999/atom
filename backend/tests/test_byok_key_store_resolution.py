# -*- coding: utf-8 -*-
"""BYOK key-store resolution contract (audit item 5c / review item 1).

Two writers persist into the SAME store with different id shapes:

  * ``BYOKManager.store_api_key``          → ``{provider}_{name}_{env}``
  * the tenant-scoped API route            → ``tenant_{tenant}_{provider}_{name}_{env}``

``get_api_key`` only ever looked up the first shape. Every entry in
``data/byok_keys.json`` is tenant-prefixed, so the whole local store was
unreachable at runtime — reproduced 2026-09-16:

    openrouter   id='openrouter_default_production'  in api_keys=False  resolve=SET
    deepseek     id='deepseek_default_production'    in api_keys=False  resolve=None
    opencode-go  id='opencode-go_default_production' in api_keys=False  resolve=None

``openrouter`` resolved only because ``OPENROUTER_API_KEY`` is also set in the
environment. ``deepseek`` and ``opencode-go`` have no env fallback, so they
never became clients — ``BYOKHandler.clients == ['ollama', 'openrouter']`` and
the routing ladder returned 9/9 candidates from one provider with all
fallbacks sharing that upstream.

THE CONTRACT (one resolver, both managers)
==========================================

A stored entry has an IDENTITY of ``(scope, provider_id, key_name,
environment)``, where ``scope`` is the owning tenant recorded on the entry or —
for rows written before that field existed — recovered from the id shape. An
entry with no scope is the operator's GLOBAL entry.

Resolution for ``(provider_id, key_name, environment)``:

1. Only entries whose fields match EXACTLY are candidates, and only if
   ``is_active``. Fields — never the dict id — decide the match, because key
   names may contain underscores and spaces (``openrouter (onboarding)``).
2. A caller that declares a tenant gets **its own scoped entry**, else the
   global entry. It never receives another tenant's credential.
3. A caller that declares no tenant gets the global entry; failing that, a
   single-scope store resolves to that one scope (the single-operator local
   install whose every key is tenant-prefixed, which is the live shape). Two
   or more distinct scopes are AMBIGUOUS and resolve to ``None`` — a scoped
   credential must never silently become another owner's global fallback.
4. The environment variable is consulted only when the store yields nothing,
   and is never persisted.

These tests pin the invariant the handler depends on: **if ``is_configured``
says a provider has a credential for a caller, ``get_api_key`` must return one
for that same caller and scope.** The handler gates on one and retrieves with
the other; when they disagree the provider silently loses its client.
"""
import json
import os
from datetime import datetime

import pytest

import core.byok_endpoints as be


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A fresh BYOK manager backed by a temp key file."""
    from cryptography.fernet import Fernet

    keys_file = tmp_path / "byok_keys.json"
    monkeypatch.setattr(be, "BYOK_KEYS_FILE", str(keys_file))
    monkeypatch.setattr(be, "BYOK_CONFIG_FILE", str(tmp_path / "byok_config.json"))
    # Real Fernet material — a free-form passphrase is rejected by _get_fernet.
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", Fernet.generate_key().decode())
    return keys_file


def _no_env(monkeypatch, *providers):
    for provider in providers:
        monkeypatch.delenv(f"{provider.upper()}_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


def _seed_tenant(manager, provider: str, secret: str, tenant: str = "default",
                 key_name: str = "default", environment: str = "production",
                 with_field: bool = False) -> str:
    """Write a key the way the tenant-scoped route does.

    ``with_field=False`` reproduces the LIVE legacy shape: the owning tenant is
    only encoded in the storage id (``tenant_id`` is dropped by the loader of
    any manager that predates the field), so the resolver must recover it.
    """
    key_id = f"tenant_{tenant}_{provider}_{key_name}_{environment}"
    fields = dict(
        provider_id=provider,
        key_name=key_name,
        encrypted_key=manager.encrypt_api_key(secret),
        key_hash="hash",
        created_at=datetime.now(),
        environment=environment,
    )
    if with_field:
        fields["tenant_id"] = tenant
    manager.api_keys[key_id] = be.APIKey(**fields)
    manager._save_configuration()
    return key_id


def _seed_global(manager, provider: str, secret: str, key_name: str = "default",
                 environment: str = "production") -> str:
    """Write a key the way ``store_api_key`` does (operator/global entry)."""
    key_id = f"{provider}_{key_name}_{environment}"
    manager.api_keys[key_id] = be.APIKey(
        provider_id=provider,
        key_name=key_name,
        encrypted_key=manager.encrypt_api_key(secret),
        key_hash="hash",
        created_at=datetime.now(),
        environment=environment,
    )
    manager._save_configuration()
    return key_id


class TestTenantPrefixedKeysResolve:
    def test_tenant_prefixed_key_is_resolvable(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-deepseek-secret")
        assert m.get_api_key("deepseek") == "sk-deepseek-secret", (
            "a key stored under the tenant-scoped id is invisible to "
            "get_api_key — this is the defect that removed deepseek and "
            "opencode-go from the routing ladder")

    def test_tenant_prefixed_key_survives_reload(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-persisted")
        reloaded = be.BYOKManager()
        assert reloaded.get_api_key("deepseek") == "sk-persisted", (
            "a key saved by the UI is silently lost across a restart")

    def test_opencode_go_hyphenated_provider_resolves(self, store, monkeypatch):
        _no_env(monkeypatch, "opencode-go")
        m = be.BYOKManager()
        _seed_tenant(m, "opencode-go", "sk-opencode")
        assert m.get_api_key("opencode-go") == "sk-opencode"

    def test_key_name_with_spaces_resolves(self, store, monkeypatch):
        """Key names are free-form ('openrouter (onboarding)') — the live store
        contains exactly that, so id-shape parsing must not be the mechanism."""
        _no_env(monkeypatch, "openrouter")
        m = be.BYOKManager()
        _seed_tenant(m, "openrouter", "sk-onboarding",
                     key_name="openrouter (onboarding)")
        assert m.get_api_key(
            "openrouter", key_name="openrouter (onboarding)") == "sk-onboarding"


class TestNoOverMatching:
    def test_a_key_does_not_resolve_for_another_provider(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek", "openai")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-deepseek")
        assert m.get_api_key("openai") is None, (
            "a deepseek key resolved for openai — the fallback is matching "
            "too loosely")

    def test_named_key_does_not_resolve_as_default(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-named", key_name="production-eu")
        assert m.get_api_key("deepseek", key_name="default") is None

    def test_environment_is_part_of_identity(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-staging", environment="staging")
        assert m.get_api_key("deepseek", environment="production") is None
        assert m.get_api_key("deepseek", environment="staging") == "sk-staging"


class TestTwoTenantCollision:
    """The defect the in-flight fix introduced: a scoped credential silently
    becoming a global fallback. Two tenants, same (provider, name, env)."""

    def test_each_tenant_gets_its_own_key(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        _seed_tenant(m, "deepseek", "sk-globex", tenant="globex")
        assert m.get_api_key("deepseek", tenant_id="acme") == "sk-acme"
        assert m.get_api_key("deepseek", tenant_id="globex") == "sk-globex"

    def test_reversed_insertion_order_is_equivalent(self, store, monkeypatch):
        """Resolution must not depend on dict/insertion order."""
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-globex", tenant="globex")
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        assert m.get_api_key("deepseek", tenant_id="acme") == "sk-acme"
        assert m.get_api_key("deepseek", tenant_id="globex") == "sk-globex"

    def test_scoped_lookup_never_returns_another_tenants_key(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        assert m.get_api_key("deepseek", tenant_id="globex") is None, (
            "tenant globex was served tenant acme's credential")

    def test_unscoped_lookup_of_two_scopes_is_ambiguous(self, store, monkeypatch):
        """THE regression test for the in-flight change: with two owners in the
        store an unscoped lookup must refuse rather than pick one."""
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        _seed_tenant(m, "deepseek", "sk-globex", tenant="globex")
        assert m.get_api_key("deepseek") is None, (
            "an unscoped lookup promoted one tenant's credential to a global "
            "fallback")
        # ...and reversed insertion order must not change the answer.
        m2 = be.BYOKManager()
        m2.api_keys.clear()
        _seed_tenant(m2, "deepseek", "sk-globex", tenant="globex")
        _seed_tenant(m2, "deepseek", "sk-acme", tenant="acme")
        assert m2.get_api_key("deepseek") is None

    def test_boundary_of_the_ambiguity_rule(self, store, monkeypatch):
        """A scoped lookup is unaffected by a second tenant's entry."""
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        _seed_tenant(m, "deepseek", "sk-globex", tenant="globex")
        assert m.get_api_key("deepseek", tenant_id="acme") == "sk-acme"
        assert m.get_api_key("deepseek", tenant_id="globex") == "sk-globex"


class TestGlobalVersusScopedPrecedence:
    def test_scoped_caller_prefers_its_own_entry(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_global(m, "deepseek", "sk-operator")
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        assert m.get_api_key("deepseek", tenant_id="acme") == "sk-acme", (
            "the caller's own scoped credential must outrank the global one")

    def test_scoped_caller_falls_back_to_global(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_global(m, "deepseek", "sk-operator")
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        assert m.get_api_key("deepseek", tenant_id="globex") == "sk-operator", (
            "a caller with no entry of its own may use the OPERATOR's global "
            "credential, but never another tenant's")

    def test_unscoped_lookup_prefers_global(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_global(m, "deepseek", "sk-operator")
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        assert m.get_api_key("deepseek") == "sk-operator"

    def test_single_scope_store_resolves_unscoped(self, store, monkeypatch):
        """The live single-operator shape: every key tenant-prefixed, one
        owner — the runtime's unscoped lookup must still find it."""
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-only-owner", tenant="default",
                     key_name="Deepseek")
        assert m.get_api_key("deepseek", key_name="Deepseek") == "sk-only-owner"

    def test_scoped_and_global_agree_after_reload(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_global(m, "deepseek", "sk-operator")
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme",
                     with_field=True)  # tenant_id round-trips through JSON
        reloaded = be.BYOKManager()
        assert reloaded.get_api_key("deepseek") == "sk-operator"
        assert reloaded.get_api_key("deepseek", tenant_id="acme") == "sk-acme"


class TestInactiveKeys:
    def test_inactive_key_is_not_retrieved(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        key_id = _seed_tenant(m, "deepseek", "sk-disabled")
        m.api_keys[key_id].is_active = False
        assert m.get_api_key("deepseek") is None

    def test_inactive_key_is_not_configured(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        key_id = _seed_tenant(m, "deepseek", "sk-disabled")
        m.api_keys[key_id].is_active = False
        assert m.is_configured("default", "deepseek") is False, (
            "is_configured claimed a credential that get_api_key refuses")

    def test_inactive_entry_does_not_shadow_an_active_one(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        dead = _seed_tenant(m, "deepseek", "sk-dead", tenant="acme")
        m.api_keys[dead].is_active = False
        _seed_global(m, "deepseek", "sk-operator")
        assert m.get_api_key("deepseek") == "sk-operator"
        assert m.get_api_key("deepseek", tenant_id="acme") == "sk-operator", (
            "with its own entry inactive, the tenant falls back to the "
            "operator key — never to a third party's")


class TestFailedDecryption:
    def test_decrypt_failure_returns_none(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-broken")
        m.api_keys["tenant_default_deepseek_default_production"].encrypted_key = "not-a-token"
        assert m.get_api_key("deepseek") is None

    def test_decrypt_failure_is_not_configured(self, store, monkeypatch):
        """A credential that cannot be decrypted is not retrievable, so the
        guard must not claim it — otherwise the handler skips the provider's
        env fallback and the provider silently loses its client."""
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-broken")
        m.api_keys["tenant_default_deepseek_default_production"].encrypted_key = "not-a-token"
        assert m.is_configured("default", "deepseek") is False


class TestConfiguredImpliesRetrievable:
    """The load-bearing invariant: the guard and the getter must agree for the
    SAME caller and scope."""

    @pytest.mark.parametrize("caller_scope", [None, "acme", "globex", "default"])
    def test_guard_and_getter_agree(self, store, monkeypatch, caller_scope):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        _seed_global(m, "deepseek", "sk-operator")

        configured = m.is_configured("default", "deepseek", tenant_id=caller_scope)
        retrievable = bool(
            m.get_api_key("deepseek", tenant_id=caller_scope))
        assert configured == retrievable, (
            f"scope={caller_scope!r}: is_configured={configured} but "
            f"retrievable={retrievable} — the handler gates on the former and "
            "retrieves with the latter")

    def test_ambiguous_store_is_not_configured_either(self, store, monkeypatch):
        """Refusing an ambiguous lookup must be visible to the guard too."""
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        _seed_tenant(m, "deepseek", "sk-globex", tenant="globex")
        assert m.is_configured("default", "deepseek") is False

    def test_credential_service_binds_the_callers_scope(self, store, monkeypatch):
        """End of the chain: LLMCredentialService must resolve the caller's own
        key, not whichever entry the store happens to hold first."""
        _no_env(monkeypatch, "deepseek")
        from core.llm_credential_service import LLMCredentialService

        manager = be.BYOKManager()
        _seed_tenant(manager, "deepseek", "sk-acme", tenant="acme")
        _seed_tenant(manager, "deepseek", "sk-globex", tenant="globex")
        # The service resolves through the process-wide singleton.
        monkeypatch.setattr(be, "_byok_manager", manager)

        acme = LLMCredentialService(tenant_id="acme", workspace_id="acme")
        globex = LLMCredentialService(tenant_id="globex", workspace_id="globex")
        assert acme._try_byok_credential("deepseek") == "sk-acme"
        assert globex._try_byok_credential("deepseek") == "sk-globex"

    def test_credential_service_without_own_key_does_not_borrow_one(
            self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        from core.llm_credential_service import LLMCredentialService

        manager = be.BYOKManager()
        _seed_tenant(manager, "deepseek", "sk-acme", tenant="acme")
        monkeypatch.setattr(be, "_byok_manager", manager)

        stranger = LLMCredentialService(tenant_id="globex", workspace_id="globex")
        assert stranger._try_byok_credential("deepseek") is None, (
            "a tenant with no stored credential was served another tenant's")


class TestEnvFallbackPreserved:
    def test_env_key_still_returned_when_store_has_none(self, store, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-from-env")
        m = be.BYOKManager()
        assert m.get_api_key("deepseek") == "sk-from-env"

    def test_store_key_wins_over_env(self, store, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-from-env")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-from-store")
        assert m.get_api_key("deepseek") == "sk-from-store", (
            "the operator's explicitly stored key must win over an ambient "
            "env var")

    def test_ambiguous_store_falls_through_to_env(self, store, monkeypatch):
        """Ambiguity is not a hard failure — env remains the last resort."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-from-env")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme")
        _seed_tenant(m, "deepseek", "sk-globex", tenant="globex")
        assert m.get_api_key("deepseek") == "sk-from-env"


class TestTenantFieldRoundTrip:
    def test_tenant_id_is_persisted_and_reloaded(self, store, monkeypatch):
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-acme", tenant="acme", with_field=True)
        raw = json.loads(open(store).read())
        assert raw["keys"]["tenant_acme_deepseek_default_production"]["tenant_id"] == "acme"
        assert be.BYOKManager().get_api_key("deepseek", tenant_id="acme") == "sk-acme"

    def test_legacy_row_without_the_field_still_resolves(self, store, monkeypatch):
        """Rows written before the field existed keep working — the scope is
        recovered from the id the tenant route itself constructed."""
        _no_env(monkeypatch, "deepseek")
        m = be.BYOKManager()
        _seed_tenant(m, "deepseek", "sk-legacy", tenant="acme", with_field=False)
        raw = json.loads(open(store).read())
        assert "tenant_id" not in raw["keys"]["tenant_acme_deepseek_default_production"] or \
            raw["keys"]["tenant_acme_deepseek_default_production"]["tenant_id"] is None
        reloaded = be.BYOKManager()
        assert reloaded.get_api_key("deepseek", tenant_id="acme") == "sk-legacy"
        assert reloaded.get_api_key("deepseek", tenant_id="globex") is None
