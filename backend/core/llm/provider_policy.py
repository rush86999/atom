"""Installation-level provider policy: allowed destinations vs preference.

A saved BYOK credential is permission to *store* a key, not permission to
send every request to that provider. This module is the single policy
resolver used before ranking and immediately before dispatch.

Policy value (``ATOM_LLM_PROVIDER_POLICY``)::

    {
      "mode": "automatic" | "selected",
      "allowed_providers": ["ollama", "deepseek"],
      "preferred": {"provider": "ollama", "model": "llama3.1:8b"} | null
    }

Unset means the documented legacy behavior (all configured providers are
eligible). ``selected`` with an empty list means no routes; it never means
"unrestricted". Malformed or unreadable restrictive configuration fails
closed.

The store is the existing installation ``runtime_settings`` row; provider
credentials stay in the existing BYOK stores and are never copied or
rewritten here.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

PROVIDER_POLICY_KEY = "ATOM_LLM_PROVIDER_POLICY"
_VALID_MODES = {"automatic", "selected"}


class ProviderPolicyError(ValueError):
    """A policy value that must not be interpreted as unrestricted."""


def known_provider_ids() -> set[str]:
    """Provider ids from the live BYOK registry (lazy import: no cycle)."""
    try:
        from core.byok_endpoints import get_byok_manager

        return set(get_byok_manager().providers.keys())
    except Exception as exc:  # noqa: BLE001 — validation is best-effort
        logger.debug("provider registry unavailable for policy validation: %s", exc)
        return set()


def validate_provider_policy(
        raw: Any, *, known_ids: Optional[Iterable[str]] = None) -> dict:
    """Return a canonical policy dict or raise ``ProviderPolicyError``.

    Unknown provider ids are rejected. A selected policy with an empty
    allowed list is valid and means "no routes".
    """
    if not isinstance(raw, dict):
        raise ProviderPolicyError("policy must be an object")
    mode = str(raw.get("mode") or "").strip().lower()
    if mode not in _VALID_MODES:
        raise ProviderPolicyError("mode must be 'automatic' or 'selected'")

    allowed_raw = raw.get("allowed_providers")
    if allowed_raw is None:
        allowed_raw = []
    if not isinstance(allowed_raw, list):
        raise ProviderPolicyError("allowed_providers must be a list")
    allowed: list[str] = []
    for item in allowed_raw:
        if not isinstance(item, str) or not item.strip():
            raise ProviderPolicyError("allowed_providers entries must be ids")
        pid = item.strip()
        if pid not in allowed:
            allowed.append(pid)

    known = set(known_ids) if known_ids is not None else known_provider_ids()
    if known:
        unknown = sorted(set(allowed) - known)
        if unknown:
            raise ProviderPolicyError(
                "unknown provider id(s): " + ", ".join(unknown))

    preferred_raw = raw.get("preferred")
    preferred: Optional[dict] = None
    if preferred_raw is not None:
        if not isinstance(preferred_raw, dict):
            raise ProviderPolicyError("preferred must be an object or null")
        provider = str(preferred_raw.get("provider") or "").strip()
        model = str(preferred_raw.get("model") or "").strip()
        if not provider or not model:
            raise ProviderPolicyError(
                "preferred requires provider and model")
        if known and provider not in known:
            raise ProviderPolicyError(
                f"unknown preferred provider: {provider}")
        if mode == "selected" and provider not in allowed:
            raise ProviderPolicyError(
                "preferred provider must be in allowed_providers")
        preferred = {"provider": provider, "model": model}

    canonical = {
        "mode": mode,
        "allowed_providers": allowed,
        "preferred": preferred,
    }
    return canonical


def _revision(canonical: dict) -> str:
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class ProviderPolicy:
    mode: str = "unset"  # unset | automatic | selected | invalid
    allowed_providers: frozenset[str] = field(default_factory=frozenset)
    preferred: Optional[tuple[str, str]] = None
    source: str = "default"  # env | db | default | invalid
    revision: str = ""
    error: Optional[str] = None

    @property
    def managed_by_env(self) -> bool:
        return self.source == "env"

    @property
    def enforced(self) -> bool:
        return self.mode == "selected"

    def allows_provider(self, provider_id: Any) -> bool:
        if self.error or self.mode == "invalid":
            return False
        if self.mode in ("unset", "automatic"):
            return True
        if self.mode == "selected":
            return str(provider_id or "").strip() in self.allowed_providers
        return False

    def allows(self, provider_id: Any, model: Any = None) -> bool:
        # Capability/model checks stay in the existing routing layers; this
        # boundary answers only "may this provider receive content?".
        return self.allows_provider(provider_id)

    def filter_routes(self, routes: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
        return [(p, m) for p, m in routes if self.allows(p, m)]

    def public_dict(self) -> dict:
        return {
            "mode": self.mode,
            "allowed_providers": sorted(self.allowed_providers),
            "preferred": (
                {"provider": self.preferred[0], "model": self.preferred[1]}
                if self.preferred else None),
            "source": self.source,
            "managed_by_env": self.managed_by_env,
            "revision": self.revision,
            "error": self.error,
            "scope": "installation",
        }

    @classmethod
    def invalid(
            cls, error: str, source: str = "invalid") -> "ProviderPolicy":
        return cls(mode="invalid", source=source, error=error,
                   revision="invalid")


def resolve_provider_policy(
        workspace_id: Optional[str] = None,
        tenant_id: Optional[str] = None) -> ProviderPolicy:
    """Resolve the installation policy, failing closed on bad values.

    ``workspace_id``/``tenant_id`` are accepted for call-site symmetry and
    future scoped storage; the current release is installation-level (the
    single-tenant pilot has one installation policy). They are never used
    to borrow another scope's credentials.
    """
    from core.runtime_settings import StrictSettingError, resolve_setting_strict

    try:
        resolved = resolve_setting_strict(PROVIDER_POLICY_KEY)
    except StrictSettingError as exc:
        logger.error("provider policy unreadable — failing closed: %s", exc)
        # Preserve the authority signal: a malformed env override must
        # still render as "Managed by this installation" in the UI, even
        # though no usable policy could be parsed.
        source = ("env" if os.environ.get(PROVIDER_POLICY_KEY) is not None
                  else "invalid")
        return ProviderPolicy.invalid(str(exc), source=source)

    raw = resolved.value
    if raw is None:
        if os.environ.get(PROVIDER_POLICY_KEY) is not None:
            return ProviderPolicy.invalid(
                "provider policy must be an object, not null", source="env")
        return ProviderPolicy(mode="unset", source=resolved.source or "default")
    if raw == "":
        return ProviderPolicy(mode="unset", source=resolved.source or "default")
    try:
        canonical = validate_provider_policy(raw)
    except ProviderPolicyError as exc:
        logger.error("provider policy invalid (%s) — failing closed: %s",
                     resolved.source, exc)
        return ProviderPolicy.invalid(str(exc), source=resolved.source or "invalid")
    preferred = canonical.get("preferred")
    return ProviderPolicy(
        mode=canonical["mode"],
        allowed_providers=frozenset(canonical["allowed_providers"]),
        preferred=((preferred["provider"], preferred["model"])
                   if preferred else None),
        source=resolved.source or "db",
        revision=_revision(canonical),
    )
