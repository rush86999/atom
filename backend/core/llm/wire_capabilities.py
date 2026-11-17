"""Documented wire capabilities for structured (schema-bound) LLM calls.

Why this module exists
======================

The structured path wraps an OpenAI-compatible client with Instructor. Its
default protocol is function calling: one synthetic tool plus a forced,
named ``tool_choice``. That is a strong, validating protocol, but it is not
universally supported by the model behind an OpenAI-compatible route.

DeepSeek's current Chat Completions API documents two facts that matter here
(<https://api-docs.deepseek.com/api/create-chat-completion/> and
<https://api-docs.deepseek.com/guides/thinking_mode/>):

* thinking is enabled by default unless the request disables it
  (``thinking: {"type": "disabled"}`` or ``reasoning_effort: "none"``);
* ``tool_choice: "required"`` and named tool choices are rejected with HTTP
  400 while thinking is enabled.

The same incompatibility was observed live on the OpenCode Go DeepSeek route
(2026-10-18, ``Thinking mode does not support this tool_choice``), where the
JSON-mode transport succeeded instead.

This module records that provider/model capability ONCE, declaratively, so the
structured handler can select a supported protocol before the first wire call
instead of re-learning a deterministic compatibility rejection per stage.
Unknown routes keep the historical behavior exactly: this is a declaration
layer, not a guess about an arbitrary endpoint.

Sources
-------
* DeepSeek Chat Completions: https://api-docs.deepseek.com/api/create-chat-completion/
* DeepSeek thinking mode: https://api-docs.deepseek.com/guides/thinking_mode/
* DeepSeek tool calls: https://api-docs.deepseek.com/guides/tool_calls/
* OpenCode Go endpoint: https://opencode.ai/docs/console/go
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Mapping, Optional

from core.llm.model_provenance import normalize_model_family

#: Structured protocol names used by ``generate_structured_response``.
STRUCTURED_PROTOCOL_TOOLS = "tools"
STRUCTURED_PROTOCOL_JSON = "json"

#: OpenAI-compatible gateways that serve model families from other vendors.
#: A model-family declaration still applies through them because the gateway
#: preserves the upstream model's documented chat semantics.
_GATEWAY_PROVIDERS: FrozenSet[str] = frozenset(
    {"opencode-go", "opencode", "zen"})

#: Native providers whose chat-completions surface is documented by the model
#: vendor itself.
_NATIVE_DEEPSEEK_PROVIDERS: FrozenSet[str] = frozenset({"deepseek"})


@dataclass(frozen=True)
class StructuredWireContract:
    """How one route can carry a schema-bound request.

    ``protocol`` is the transport the structured handler should use:
    ``"tools"`` for the historical forced function-call scaffold or ``"json"``
    for Instructor's schema-in-prompt JSON mode.

    ``thinking_disable_extra`` is the provider-documented request extension
    that disables hidden thinking when it is required for the selected
    protocol (or when the caller asked for ``disable_reasoning``). It is
    ``None`` when the vendor documents no such switch; in that case the
    handler omits the field rather than inventing one.

    A declared route never receives the OpenRouter-style ``reasoning``
    extension: it is a gateway extension, not an OpenAI-compatible field.
    Undeclared routes keep their historical payload.
    """

    family: str
    protocol: str
    thinking_disable_extra: Optional[Mapping[str, Any]] = None
    thinking_disable_key: Optional[str] = None
    requires_thinking_disabled: bool = False
    #: Whether the route accepts the optional soft-self-consistency
    #: ``logprobs`` request field. It is never required for validation; a
    #: documented/observed rejection is skipped BEFORE dispatch because the
    #: field only weights samples and its rejection would otherwise waste a
    #: deterministic compatibility round trip.
    supports_logprobs: bool = True
    documented: str = ""

    def extra_body(self) -> Optional[Dict[str, Any]]:
        if self.thinking_disable_extra is None:
            return None
        return {
            str(key): (dict(value) if isinstance(value, Mapping) else value)
            for key, value in self.thinking_disable_extra.items()
        }


@dataclass(frozen=True)
class _FamilyDeclaration:
    """A model family's documented structured-output capabilities."""

    family: str
    protocol: str
    thinking_disable_extra: Optional[Mapping[str, Any]] = None
    thinking_disable_key: Optional[str] = None
    requires_thinking_disabled: bool = False
    supports_logprobs: bool = True
    documented: str = ""


# DeepSeek's OpenAI-format toggle. ``reasoning_effort: "none"`` is documented
# as disabling thinking mode (the ``thinking`` object is the explicit object
# form used in the vendor's OpenAI-SDK example). The scalar form is used by
# the OpenAI-compatible gateway route; both are accepted by the native API.
_DEEPSEEK_THINKING_OFF = {"reasoning_effort": "none"}

_DEEPSEEK_NATIVE = _FamilyDeclaration(
    family="deepseek",
    # Native DeepSeek supports forced function calling in non-thinking
    # mode; keeping TOOLS preserves Instructor's schema validation.
    protocol=STRUCTURED_PROTOCOL_TOOLS,
    thinking_disable_extra=_DEEPSEEK_THINKING_OFF,
    thinking_disable_key="reasoning_effort",
    requires_thinking_disabled=True,
    # Current native DeepSeek Chat Completions documents ``logprobs``.
    supports_logprobs=True,
    documented=(
        "DeepSeek: thinking defaults on; required/named tool_choice is "
        "rejected in thinking mode; disable thinking with "
        "reasoning_effort=none (OpenAI format)"),
)

_DEEPSEEK_GATEWAY = _FamilyDeclaration(
    family="deepseek",
    # OpenCode Go's DeepSeek route has live evidence that Instructor's
    # JSON mode succeeds after the gateway rejects forced tool_choice in
    # thinking mode. JSON mode is also documented by DeepSeek and keeps
    # Instructor's parse/validation loop, so no forced tool choice is
    # sent through an unverified gateway translation.
    protocol=STRUCTURED_PROTOCOL_JSON,
    thinking_disable_extra=_DEEPSEEK_THINKING_OFF,
    thinking_disable_key="reasoning_effort",
    # JSON output is valid in thinking mode; the switch is only sent when
    # the caller asked to disable reasoning.
    requires_thinking_disabled=False,
    # In-repo live evidence (2026-10-01): the Go DeepSeek Flash route rejected
    # the optional soft-SC logprobs field ("does not support return_logprob
    # yet"). The field is optional weighting only, so declaring it
    # unsupported skips a deterministic 400 without changing validation.
    supports_logprobs=False,
    documented=(
        "OpenCode Go DeepSeek: OpenAI-compatible gateway; JSON output "
        "documented upstream; forced tool_choice rejected in thinking "
        "mode (observed live 2026-10-18); logprobs rejected (observed live "
        "2026-10-01); no OpenRouter reasoning extension"),
)


def _model_family(model: str) -> str:
    """Normalized family token for a route model identifier.

    ``normalize_model_family`` drops vendor paths, date/snapshot tails and
    free/preview tags. Comparing the first hyphen-delimited token keeps this
    a family declaration (``deepseek-v4.1-flash`` -> ``deepseek``) rather than
    an exact model-name allowlist or an integration regex.
    """
    normalized = normalize_model_family(model)
    if not normalized:
        return ""
    return normalized.split("-", 1)[0]


def _provider(provider_id: str) -> str:
    return str(provider_id or "").strip().lower()


def resolve_structured_wire_contract(
    provider_id: str,
    model: str,
) -> Optional[StructuredWireContract]:
    """Return the documented structured contract for a route, or ``None``.

    ``None`` means "no declaration": the caller keeps its historical
    behavior, including the reactive typed-error recovery. A declaration is
    only returned for a provider/model combination whose behavior is
    documented by the vendor or has direct in-repo live evidence.
    """
    provider = _provider(provider_id)
    family = _model_family(model)

    if family == "deepseek":
        if provider in _GATEWAY_PROVIDERS:
            declaration = _DEEPSEEK_GATEWAY
        elif provider in _NATIVE_DEEPSEEK_PROVIDERS:
            declaration = _DEEPSEEK_NATIVE
        else:
            # A DeepSeek-family identifier on an undeclared provider (for
            # example an arbitrary gateway) is NOT assumed to share these
            # semantics. The reactive recovery still owns that route.
            return None
        return StructuredWireContract(
            family=declaration.family,
            protocol=declaration.protocol,
            thinking_disable_extra=declaration.thinking_disable_extra,
            thinking_disable_key=declaration.thinking_disable_key,
            requires_thinking_disabled=(
                declaration.requires_thinking_disabled),
            supports_logprobs=declaration.supports_logprobs,
            documented=declaration.documented,
        )

    return None
