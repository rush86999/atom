"""Exact, sourced wire-capability declarations for structured LLM calls.

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

The exact OpenCode Go ``deepseek-v4-pro`` route has the same rejection in-repo
(see :data:`_DECLARATIONS`), and its JSON-mode retry served.

Scope rule: EXACT ROUTES ONLY
=============================

A declaration is one EXACT ``(provider_id, model_id)`` pair, in the identifier
that provider serves, with a dated source. Model-family vocabulary (a brand
token such as ``deepseek``) is used for *provenance*, never as wire-capability
proof: a future, legacy, renamed, or differently-translated model on the same
endpoint can accept a different request shape. Therefore:

* ``opencode-go``/``deepseek-v4-pro`` is declared because that exact route was
  served and its rejection/retry was captured;
* ``opencode-go``/``deepseek-v4.1-flash`` is NOT declared — the Go Flash route
  has no attesting structured-wire evidence in this repo, so it keeps the
  historical payload + reactive typed-error recovery;
* ``opencode-go``/``deepseek-unannounced-synthetic-v999`` and native
  ``deepseek``/``deepseek-r1-distill-synthetic`` are NOT declared — an
  unverified/future/legacy identifier inherits nothing from its brand name;
* ``opencode``, ``zen``, ``openrouter`` and every other gateway are NOT
  declared for DeepSeek models — no source establishes their translation, so
  Go evidence is never transplanted to them.

No model-name regex, vendor-path strip, date-tail strip, or family-prefix
match is used here. Identifier normalization is case/whitespace only, the same
exact-matching rule ``core.llm.model_route_registry`` uses for executable
routes.

Sources
-------
* Native served identifiers: ``core/llm/model_route_registry.py`` records the
  first-party endpoint's observed 400 (2026-09-16) naming
  ``deepseek-flash`` and ``deepseek-v4-pro`` as the supported API model names.
  The public API reference (retrieved 2026-11-17) lists exactly
  ``model: deepseek-flash, deepseek-v4-pro``.
* DeepSeek Chat Completions (retrieved 2026-11-17): thinking is enabled by
  default; ``reasoning_effort: "none"`` disables it; ``required`` and named
  ``tool_choice`` are not supported in thinking mode (HTTP 400); ``logprobs``
  is a documented boolean:
  https://api-docs.deepseek.com/api/create-chat-completion/
* DeepSeek thinking mode (retrieved 2026-11-17): the toggle/effort table and
  the instruction to disable thinking before forced tool choice:
  https://api-docs.deepseek.com/guides/thinking_mode/
* DeepSeek tool calls: https://api-docs.deepseek.com/guides/tool_calls/
* OpenCode Go exact route evidence:
  ``backend/scripts/orchestration_acceptance/journey_matrix/l1_s6_successor_served_20261018/README.md``
  (frozen ``ATOM_ASYNC_EDIT_PLAN_MODEL: opencode-go/deepseek-v4-pro``; run 1
  "Thinking mode does not support this tool_choice" then one JSON-mode retry;
  run 2 dispatched cleanly).
* OpenCode Go logprobs rejection (bounded policy input only): the existing
  recovery comments in ``core/llm/byok_handler.py`` record the Go endpoint's
  2026-09-21 logprobs rejection and the 2026-10-01 DFLASH singular
  ``return_logprob`` rejection.

Unknowns (deliberately not encoded)
-----------------------------------
The private relay rewrote the 2026-11-17 upstream 400s as generic 502s and
discarded the bodies, so the exact cause of those failures remains unknown.
Nothing here claims the fleet run failed for the reason a declaration selects;
this is a documented-route compatibility layer, not a diagnosis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

#: Structured protocol names used by ``generate_structured_response``.
STRUCTURED_PROTOCOL_TOOLS = "tools"
STRUCTURED_PROTOCOL_JSON = "json"


@dataclass(frozen=True)
class RouteWireDeclaration:
    """One exact route's sourced structured-output capability.

    ``protocol`` is the transport the structured handler should use:
    ``"tools"`` for the historical forced function-call scaffold or ``"json"``
    for Instructor's schema-in-prompt JSON mode.

    ``thinking_disable_extra`` is the provider-documented request extension
    that disables hidden thinking when it is required for the selected
    protocol (or when the caller asked for ``disable_reasoning``). It is
    ``None`` when the vendor documents no such switch; in that case the
    handler omits the field rather than inventing one.
    """

    provider_id: str
    model_id: str
    protocol: str
    observed_on: str
    evidence: str
    thinking_disable_extra: Optional[Mapping[str, Any]] = None
    thinking_disable_key: Optional[str] = None
    requires_thinking_disabled: bool = False
    #: Whether the route accepts the optional soft-self-consistency
    #: ``logprobs`` request field. It is never required for validation; a
    #: documented/observed rejection is skipped BEFORE dispatch because the
    #: field only weights samples and its rejection would otherwise waste a
    #: deterministic compatibility round trip. ``logprobs_note`` must state
    #: when the value is a conservative request policy rather than a claim
    #: about the model family.
    supports_logprobs: bool = True
    logprobs_note: str = ""


@dataclass(frozen=True)
class StructuredWireContract:
    """The resolved contract for one declared route (public handler view)."""

    provider_id: str
    model_id: str
    protocol: str
    thinking_disable_extra: Optional[Mapping[str, Any]] = None
    thinking_disable_key: Optional[str] = None
    requires_thinking_disabled: bool = False
    supports_logprobs: bool = True
    observed_on: str = ""
    documented: str = ""

    def extra_body(self) -> Optional[Dict[str, Any]]:
        if self.thinking_disable_extra is None:
            return None
        return {
            str(key): (dict(value) if isinstance(value, Mapping) else value)
            for key, value in self.thinking_disable_extra.items()
        }


# DeepSeek's OpenAI-format toggle. ``reasoning_effort: "none"`` is documented
# as disabling thinking mode (the ``thinking`` object is the explicit object
# form used in the vendor's OpenAI-SDK example).
_DEEPSEEK_THINKING_OFF = {"reasoning_effort": "none"}

#: The verifier-facing capability catalogue. EXACT route keys only.
#:
#: Native identifiers are limited to the two the first-party endpoint itself
#: reported as supported (2026-09-16). Go is limited to the single route with
#: served evidence (2026-10-18). Everything else resolves to ``None`` and
#: keeps the historical payload plus reactive recovery.
_DECLARATIONS: Tuple[RouteWireDeclaration, ...] = (
    RouteWireDeclaration(
        provider_id="deepseek",
        model_id="deepseek-flash",
        protocol=STRUCTURED_PROTOCOL_TOOLS,
        observed_on="2026-09-16",
        evidence=(
            "core/llm/model_route_registry.py: first-party endpoint reported "
            "supported API model names deepseek-flash, deepseek-v4-pro "
            "(observed 2026-09-16); DeepSeek API reference/thinking guide "
            "(retrieved 2026-11-17) lists the same two model ids and "
            "documents thinking-by-default, reasoning_effort=none, the "
            "thinking-mode tool_choice 400, and logprobs"),
        thinking_disable_extra=_DEEPSEEK_THINKING_OFF,
        thinking_disable_key="reasoning_effort",
        requires_thinking_disabled=True,
        supports_logprobs=True,
        logprobs_note=(
            "DeepSeek's current Chat Completions API documents logprobs; the "
            "optional soft-SC weighting is retained on this native route"),
    ),
    RouteWireDeclaration(
        provider_id="deepseek",
        model_id="deepseek-v4-pro",
        protocol=STRUCTURED_PROTOCOL_TOOLS,
        observed_on="2026-09-16",
        evidence=(
            "core/llm/model_route_registry.py: first-party endpoint reported "
            "supported API model names deepseek-flash, deepseek-v4-pro "
            "(observed 2026-09-16); DeepSeek API reference/thinking guide "
            "(retrieved 2026-11-17) lists the same two model ids and "
            "documents thinking-by-default, reasoning_effort=none, the "
            "thinking-mode tool_choice 400, and logprobs"),
        thinking_disable_extra=_DEEPSEEK_THINKING_OFF,
        thinking_disable_key="reasoning_effort",
        requires_thinking_disabled=True,
        supports_logprobs=True,
        logprobs_note=(
            "DeepSeek's current Chat Completions API documents logprobs; the "
            "optional soft-SC weighting is retained on this native route"),
    ),
    RouteWireDeclaration(
        provider_id="opencode-go",
        model_id="deepseek-v4-pro",
        protocol=STRUCTURED_PROTOCOL_JSON,
        observed_on="2026-10-18",
        evidence=(
            "backend/scripts/orchestration_acceptance/journey_matrix/"
            "l1_s6_successor_served_20261018/README.md: frozen pin "
            "opencode-go/deepseek-v4-pro; run 1 forced tool_choice rejected "
            "('Thinking mode does not support this tool_choice') then ONE "
            "JSON-mode retry served; run 2 dispatched cleanly on this exact "
            "route. JSON was the attested post-rejection transport; the "
            "gateway's forwarding of reasoning_effort is NOT separately "
            "attested, so a rejection is dropped once and memoized"),
        thinking_disable_extra=_DEEPSEEK_THINKING_OFF,
        thinking_disable_key="reasoning_effort",
        # JSON output is valid in thinking mode; the switch is only sent when
        # the caller asked to disable reasoning.
        requires_thinking_disabled=False,
        supports_logprobs=False,
        logprobs_note=(
            "CONSERVATIVE REQUEST POLICY, not a model-family claim: this "
            "repo's existing reactive-recovery comments in "
            "core/llm/byok_handler.py record the Go endpoint's 2026-09-21 "
            "logprobs rejection and the 2026-10-01 DFLASH 'does not support "
            "return_logprob yet'. Those are code comments, not preserved "
            "response bodies. Native DeepSeek's current docs DO document "
            "logprobs and keep it."),
    ),
)

#: Case/whitespace-normalised exact route index. Deliberately NOT a family,
#: prefix, vendor-tail or date-tail match.
_DECLARATIONS_BY_ROUTE = {
    (declaration.provider_id.strip().lower(),
     declaration.model_id.strip().lower()): declaration
    for declaration in _DECLARATIONS
}


def declared_routes() -> Tuple[RouteWireDeclaration, ...]:
    """The complete catalogue, for review/audit and offline regressions."""
    return _DECLARATIONS


def _route_key(provider_id: str, model: str) -> Tuple[str, str]:
    return (
        str(provider_id or "").strip().lower(),
        str(model or "").strip().lower(),
    )


def resolve_structured_wire_contract(
    provider_id: str,
    model: str,
) -> Optional[StructuredWireContract]:
    """Return the declared contract for an EXACT route, or ``None``.

    ``None`` means "no declaration": the caller keeps its historical
    behavior byte-for-byte, including the OpenRouter-style reasoning
    extension for an undeclared route and the reactive typed-error recovery.
    A declaration is only returned for a ``(provider, model)`` pair that has a
    dated source in :data:`_DECLARATIONS`.
    """
    declaration = _DECLARATIONS_BY_ROUTE.get(_route_key(provider_id, model))
    if declaration is None:
        return None
    return StructuredWireContract(
        provider_id=declaration.provider_id,
        model_id=declaration.model_id,
        protocol=declaration.protocol,
        thinking_disable_extra=declaration.thinking_disable_extra,
        thinking_disable_key=declaration.thinking_disable_key,
        requires_thinking_disabled=declaration.requires_thinking_disabled,
        supports_logprobs=declaration.supports_logprobs,
        observed_on=declaration.observed_on,
        documented=(
            f"{declaration.evidence}"
            + (f"; logprobs: {declaration.logprobs_note}"
               if declaration.logprobs_note else "")
        ),
    )
