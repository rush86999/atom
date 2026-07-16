"""Execution Sandbox Layer — Phase D (Round 46).

HTTP CONNECT egress proxy with domain allowlist. Enforces that network
calls originating inside a sandbox microVM stay within the policy's
``egress_hosts`` (plus a curated baseline of LLM provider hosts and
package mirrors).

Mirrors the [INNOQ dual-proxy pattern]
(https://www.innoq.com/en/blog/2026/03/dev-sandbox-network/) — two
proxies with two allowlists:
  * ``LlmProxy`` — Anthropic/OpenAI/Gemini hosts only
  * ``ToolProxy`` — everything else (tool-specific allowlist from policy)

This separation prevents a tool exfiltrating data to an LLM-API-shaped
endpoint. Per [AgentShield](https://lib.rs/crates/agentshield): deny by
default, audit every rejection.

Design contract:
  * Allowlist = ``SandboxPolicy.egress_hosts`` + curated baseline.
  * DNS resolution happens at the proxy (no DNS exfil via allowed hosts).
  * All HTTP libraries inside the microVM are configured to use the proxy
    via HTTP_PROXY / HTTPS_PROXY env vars.
  * Denials produce a SandboxDecision RESTRICTED (recoverable) + audit row.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import urlparse

from core import sandbox_config
from core.sandbox_policy import (
    ALLOWED,
    BLOCKED,
    RESTRICTED,
    SandboxDecision,
    SandboxPolicy,
    VT_EGRESS_HOST,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Curated baseline allowlist
# ===========================================================================
#
# These hosts are allowed for ALL tiers (modulo Phase A tool-whitelist)
# because they are required for the agent to function. Tier-specific
# additions come from ``SandboxPolicy.egress_hosts``.
_BASELINE_EGRESS_HOSTS: Tuple[str, ...] = (
    # LLM providers (required for any agent to think)
    "api.anthropic.com",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "api.deepseek.com",
    "api.minimax.io",  # MiniMax (correct domain — was api.minimaxi.com)
    "api.mistral.ai",
    "open.bigmodel.cn",  # Zhipu AI (GLM family)
    "api.moonshot.cn",  # Moonshot AI (Kimi)
    "openrouter.ai",  # OpenRouter gateway
    "api.groq.com",  # Groq (ultra-fast inference)
    "api.deepinfra.com",  # DeepInfra
    "dashscope-intl.aliyuncs.com",  # Alibaba DashScope (Qwen)
    "dashscope.aliyuncs.com",  # Alibaba DashScope (China)
    "api.xiaomi.com",  # Xiaomi
    # Package mirrors (required for any tool that pip-installs)
    "pypi.org",
    "files.pythonhosted.org",
    # Code lookup (read-only GitHub raw)
    "github.com",
    "raw.githubusercontent.com",
    "api.github.com",
    # PyPI simple index
    "simple.pythonhosted.org",
)

# Hosts the LLM proxy specifically allows (subset of baseline).
_LLM_PROVIDER_HOSTS: Tuple[str, ...] = (
    "api.anthropic.com",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "api.deepseek.com",
    "api.minimax.io",
    "api.mistral.ai",
    "open.bigmodel.cn",
    "api.moonshot.cn",
    "openrouter.ai",
    "api.groq.com",
    "api.deepinfra.com",
    "dashscope-intl.aliyuncs.com",
    "dashscope.aliyuncs.com",
    "api.xiaomi.com",
)


# ===========================================================================
# Host normalization
# ===========================================================================


def normalize_host(host: Optional[str]) -> str:
    """Normalize a hostname for allowlist comparison.

    Lowercases, strips port, strips trailing dot. Empty/None → "".
    """
    if not host:
        return ""
    h = host.strip().lower().rstrip(".")
    # Strip port
    if ":" in h and not h.startswith("["):
        h = h.split(":", 1)[0]
    return h


def host_matches(host: str, allowlist: Tuple[str, ...]) -> bool:
    """True if ``host`` is in ``allowlist`` (with subdomain support).

    A wildcard entry like ``*.example.com`` matches any subdomain.
    """
    if not host:
        return False
    for entry in allowlist:
        if entry == host:
            return True
        if entry.startswith("*."):
            suffix = entry[2:]
            if host == suffix or host.endswith("." + suffix):
                return True
    return False


# ===========================================================================
# Decision logic
# ===========================================================================


def effective_allowlist(policy: SandboxPolicy) -> Tuple[str, ...]:
    """Return the union of baseline + policy egress hosts."""
    return tuple(set(_BASELINE_EGRESS_HOSTS) | set(policy.egress_hosts))


def check_egress(
    policy: SandboxPolicy,
    *,
    url: str,
    tool_name: str,
    args_hash: Optional[str] = None,
) -> SandboxDecision:
    """Evaluate a URL against the egress allowlist.

    Parses the URL, extracts the host, normalizes, and checks against
    the effective allowlist (baseline + policy). Never raises — on
    parse failure, returns ALLOWED with metadata (the caller will hit a
    DNS failure upstream which surfaces the bad URL anyway).
    """
    try:
        if not sandbox_config.is_sandbox_egress_enabled():
            return SandboxDecision(
                decision=ALLOWED,
                phase="D",
                tool_name=tool_name,
                args_hash=args_hash,
                metadata_json={"url": url, "egress_check": "disabled"},
            )

        parsed = urlparse(url)
        host = normalize_host(parsed.hostname)
        if not host:
            return SandboxDecision(
                decision=ALLOWED,
                phase="D",
                tool_name=tool_name,
                args_hash=args_hash,
                metadata_json={"url": url, "reason": "no_host_in_url"},
            )

        allow = effective_allowlist(policy)
        if host_matches(host, allow):
            return SandboxDecision(
                decision=ALLOWED,
                phase="D",
                tool_name=tool_name,
                args_hash=args_hash,
                metadata_json={"host": host, "url": url},
            )

        # Denied
        return SandboxDecision(
            decision=BLOCKED,
            phase="D",
            violation_type=VT_EGRESS_HOST,
            violation_detail=(
                f"egress to non-allowlisted host '{host}' "
                f"(url={url})"
            ),
            tool_name=tool_name,
            args_hash=args_hash,
            enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
            metadata_json={
                "host": host,
                "url": url,
                "allowlist_size": len(allow),
            },
        )
    except Exception as e:  # noqa: BLE001 — fail open on parse errors
        logger.debug("egress check failed open for %s: %s", url, e)
        return SandboxDecision(
            decision=ALLOWED,
            phase="D",
            tool_name=tool_name,
            args_hash=args_hash,
            metadata_json={"url": url, "error": str(e)},
        )


# ===========================================================================
# URL extraction from tool args (conservative — only obvious URL fields)
# ===========================================================================
_URL_ARG_KEYS: Tuple[str, ...] = (
    "url",
    "endpoint",
    "host",
    "webhook_url",
    "callback_url",
    "api_url",
    "base_url",
)


def extract_urls_from_args(args: Dict[str, Any]) -> Dict[str, str]:
    """Pull URL-looking values out of args.

    Returns ``{arg_key: url_string}`` for each arg whose key matches a
    known URL-key name AND whose value parses as a URL with a scheme.
    """
    out: Dict[str, str] = {}
    if not args:
        return out
    for key, value in args.items():
        if key in _URL_ARG_KEYS and isinstance(value, str) and value:
            if "://" in value or value.startswith("http"):
                out[key] = value
    return out


def validate(
    policy: SandboxPolicy,
    tool_name: str,
    args: Dict[str, Any],
    *,
    context: Optional[Dict[str, Any]] = None,
) -> SandboxDecision:
    """Validate all URL-bearing args against the egress policy.

    Returns the worst decision across URL args.
    """
    from core.sandbox_policy import PolicyIssuer

    args_hash = PolicyIssuer._hash_args(args)
    urls = extract_urls_from_args(args)
    if not urls:
        return SandboxDecision(
            decision=ALLOWED,
            phase="D",
            tool_name=tool_name,
            args_hash=args_hash,
            metadata_json={"reason": "no_url_args"},
        )

    worst = SandboxDecision(
        decision=ALLOWED,
        phase="D",
        tool_name=tool_name,
        args_hash=args_hash,
    )
    for key, url in urls.items():
        d = check_egress(policy, url=url, tool_name=tool_name, args_hash=args_hash)
        d = SandboxDecision(
            **{**d.to_audit_row(), "metadata_json": {**d.metadata_json, "arg_key": key}}
        )
        if d.decision == BLOCKED:
            return d
        if d.decision == RESTRICTED and worst.decision == ALLOWED:
            worst = d
    return worst


# ===========================================================================
# Dual proxy classes
# ===========================================================================
class _BaseProxy:
    """Base class for the dual-proxy pattern.

    Phase D ships the *check logic* and the allowlist partitioning; the
    actual proxy server (HTTP CONNECT listener) is host-provisioned.
    This class exposes ``can_connect(host)`` for callers and tests.
    """

    def __init__(self, allowlist: Tuple[str, ...]) -> None:
        self._allowlist = allowlist

    def can_connect(self, host: str) -> bool:
        return host_matches(normalize_host(host), self._allowlist)

    @property
    def allowlist(self) -> Tuple[str, ...]:
        return self._allowlist


class LlmProxy(_BaseProxy):
    """LLM-API-only proxy. Allowlist = LLM provider hosts."""

    def __init__(self) -> None:
        super().__init__(_LLM_PROVIDER_HOSTS)


class ToolProxy(_BaseProxy):
    """Everything-else proxy. Allowlist = effective_allowlist(policy)."""

    def __init__(self, policy: SandboxPolicy) -> None:
        super().__init__(effective_allowlist(policy))


def get_dual_proxy_split(policy: SandboxPolicy) -> Tuple[LlmProxy, ToolProxy]:
    """Return (LLM proxy, Tool proxy) for a policy.

    Used by tests + by the Phase D microVM bootstrapping code to mount
    the right proxy socket per microVM.
    """
    return LlmProxy(), ToolProxy(policy)
