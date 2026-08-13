"""Self-healing request repair for LLM provider 4xx errors.

When a provider rejects a request with a repairable 4xx (400/404/422), this
module inspects the error and the request payload and returns a patched
payload that can be retried once before falling back to another model.

Two layers:
  1. Rule-based patches (instant, deterministic) — handle the ~80% of repairable
     4xx errors that are parameter/format mistakes (param renames, unsupported
     params, multimodal rejection, context overflow, response_format rejection).
  2. LLM fallback healer (rules miss only) — gated behind
     ``ATOM_LLM_HEALER_ENABLED=true``. Sends the failed request + error to a
     small/fast model that returns a JSON patch. Off by default.

Inspired by Manifest's (mnfst/manifest) Phoenix self-healing service, but
rule-first to avoid adding latency/cost on the common cases.

Error classification:
  REPAIRABLE_4XX    (400/404/422) -> run healer
  NON_REPAIRABLE_4XX (401/403/429) -> skip (auth/rate-limit are not body problems)
  5XX / transient   -> skip (server-side, not a request bug)
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# --- Error classification ----------------------------------------------------

# HTTP status codes that indicate a *repairable* request-body problem.
REPAIRABLE_STATUSES = frozenset({400, 404, 422})
# Auth/quota errors — the body is fine; the credentials or limits are the issue.
NON_REPAIRABLE_STATUSES = frozenset({401, 403, 429})


def classify_error(exc: BaseException) -> str:
    """Classify a provider exception into an error category.

    Returns one of: ``"repairable_4xx"``, ``"non_repairable_4xx"``,
    ``"server_error"``, ``"transient"``, ``"unknown"``.

    Inspects OpenAI SDK ``APIStatusError`` subclasses when available; falls
    back to substring matching on the error message for non-SDK errors.
    """
    # OpenAI SDK typed errors carry .status_code.
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        if status_code in REPAIRABLE_STATUSES:
            return "repairable_4xx"
        if status_code in NON_REPAIRABLE_STATUSES:
            return "non_repairable_4xx"
        if 500 <= status_code < 600:
            return "server_error"
        if status_code == 408:
            return "transient"
        return "unknown"

    # Substring fallback for non-SDK or wrapped errors.
    msg = str(exc).lower()
    if any(s in msg for s in ("timeout", "timed out", "connection reset", "connection aborted")):
        return "transient"
    if any(s in msg for s in ("429", "rate limit", "quota")):
        return "non_repairable_4xx"
    if any(s in msg for s in ("401", "403", "unauthorized", "forbidden", "authentication")):
        return "non_repairable_4xx"
    if any(s in msg for s in ("500", "502", "503", "504", "internal server error", "bad gateway", "service unavailable")):
        return "server_error"
    if any(s in msg for s in ("400", "404", "422", "bad request", "not found", "unprocessable")):
        return "repairable_4xx"
    return "unknown"


def is_repairable(exc: BaseException) -> bool:
    """Return True if the error is a repairable 4xx worth a heal attempt."""
    return classify_error(exc) == "repairable_4xx"


# --- Healing result ---------------------------------------------------------


@dataclass
class HealingResult:
    """Outcome of a heal attempt.

    ``patched_kwargs`` is the mutated request kwargs to retry with (or None
    when the error was not repairable / no rule matched). ``rule`` names the
    applied rule (or ``"llm"`` for the LLM healer) for observability.
    """

    patched_kwargs: Optional[Dict[str, Any]]
    rule: Optional[str]
    patched_keys: List[str] = field(default_factory=list)


# --- Rule registry ----------------------------------------------------------


class HealingRule:
    """A single deterministic request-repair rule.

    Subclasses implement ``matches`` (does this error+payload fit?) and
    ``apply`` (return patched kwargs). ``apply`` MUST NOT mutate the input
    kwargs in place — return a shallow-copied dict.
    """

    name: str = "base"

    def matches(
        self,
        error: BaseException,
        kwargs: Dict[str, Any],
        provider: str,
        model: str,
    ) -> bool:
        raise NotImplementedError

    def apply(self, kwargs: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """Return (patched_kwargs, patched_keys)."""
        raise NotImplementedError


class _ParamRenameRule(HealingRule):
    """Rename ``max_tokens`` -> ``max_output_tokens`` / ``max_completion_tokens``.

    Gemini/Claude reject ``max_tokens``; newer OpenAI reasoning models want
    ``max_completion_tokens``. Detected via error-message keywords.
    """

    name = "param_rename_max_tokens"

    def matches(self, error, kwargs, provider, model):
        if "max_tokens" not in kwargs:
            return False
        msg = str(error).lower()
        return any(
            s in msg
            for s in (
                "max_tokens",
                "unexpected parameter",
                "unknown argument",
                "unrecognized arguments",
                "max_tokens is not supported",
                "does not support max_tokens",
            )
        )

    def apply(self, kwargs):
        patched = dict(kwargs)
        old = patched.pop("max_tokens", None)
        if old is None:
            return patched, []
        # Gemini/Anthropic prefer max_output_tokens; OpenAI reasoning models
        # prefer max_completion_tokens. Default to max_output_tokens (the more
        # widely accepted name across OpenAI-compatible endpoints).
        patched["max_output_tokens"] = old
        return patched, ["max_tokens->max_output_tokens"]


class _DropTemperatureRule(HealingRule):
    """Drop ``temperature`` for o-series reasoning models that reject it."""

    name = "drop_temperature_o_series"

    _REASONING_PREFIXES = ("o1", "o3", "o4", "o1-", "o3-", "o4-")

    def matches(self, error, kwargs, provider, model):
        if "temperature" not in kwargs:
            return False
        if not model or not any(model.lower().startswith(p) for p in self._REASONING_PREFIXES):
            return False
        msg = str(error).lower()
        return "temperature" in msg or "unsupported parameter" in msg

    def apply(self, kwargs):
        patched = dict(kwargs)
        patched.pop("temperature", None)
        return patched, ["temperature"]


class _StripMultimodalRule(HealingRule):
    """Collapse multimodal image_url content to text-only.

    Some providers/endpoints reject multimodal content. Strip the image parts
    and keep the text, so the request can still succeed (without vision).
    """

    name = "strip_multimodal"

    def matches(self, error, kwargs, provider, model):
        msg = str(error).lower()
        if not any(
            s in msg
            for s in ("image", "multimodal", "unsupported content type", "vision", "image_url")
        ):
            return False
        messages = kwargs.get("messages") or []
        for m in messages:
            content = m.get("content") if isinstance(m, dict) else None
            if isinstance(content, list):
                if any(isinstance(part, dict) and part.get("type") == "image_url" for part in content):
                    return True
        return False

    def apply(self, kwargs):
        patched = dict(kwargs)
        messages = list(patched.get("messages") or [])
        changed = False
        for i, m in enumerate(messages):
            if not isinstance(m, dict):
                continue
            content = m.get("content")
            if not isinstance(content, list):
                continue
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            if text_parts:
                messages[i] = {**m, "content": "\n".join(text_parts)}
                changed = True
        if changed:
            patched["messages"] = messages
        return patched, ["messages(strip image_url)"] if changed else []


class _TruncateContextRule(HealingRule):
    """Truncate messages to the last N turns on context-length errors."""

    name = "truncate_context"
    _MAX_TURNS_AFTER_TRUNCATE = 4

    def matches(self, error, kwargs, provider, model):
        msg = str(error).lower()
        return any(
            s in msg
            for s in ("context length", "context window", "too long", "maximum context", "token limit", "reduce the length")
        )

    def apply(self, kwargs):
        patched = dict(kwargs)
        messages = list(patched.get("messages") or [])
        if len(messages) <= self._MAX_TURNS_AFTER_TRUNCATE + 1:
            return patched, []  # already short; nothing to truncate
        # Keep the system message (first) + last N turns.
        system = [messages[0]] if messages and isinstance(messages[0], dict) and messages[0].get("role") == "system" else []
        rest = messages[1:] if system else messages
        truncated = system + rest[-self._MAX_TURNS_AFTER_TRUNCATE:]
        patched["messages"] = truncated
        return patched, [f"messages(truncated to last {len(truncated)})"]


class _DropResponseFormatRule(HealingRule):
    """Drop ``response_format`` for providers that reject JSON-mode params."""

    name = "drop_response_format"

    def matches(self, error, kwargs, provider, model):
        if "response_format" not in kwargs:
            return False
        msg = str(error).lower()
        return any(s in msg for s in ("response_format", "json_object", "json mode", "response format"))

    def apply(self, kwargs):
        patched = dict(kwargs)
        patched.pop("response_format", None)
        return patched, ["response_format"]


# Ordered rule list. First match wins.
_DEFAULT_RULES: List[HealingRule] = [
    _ParamRenameRule(),
    _DropTemperatureRule(),
    _StripMultimodalRule(),
    _TruncateContextRule(),
    _DropResponseFormatRule(),
]


# --- Healer -----------------------------------------------------------------


class RequestHealer:
    """Self-healing request repair engine.

    Tries deterministic rules first; optionally falls back to an LLM healer
    when no rule matches (gated behind ATOM_LLM_HEALER_ENABLED).
    """

    def __init__(
        self,
        rules: Optional[List[HealingRule]] = None,
        llm_healer: Optional[Callable] = None,
    ):
        self.rules = rules if rules is not None else list(_DEFAULT_RULES)
        # llm_healer is an async callable(error, kwargs, provider, model) ->
        # Optional[Tuple[Dict, List[str]]]. Injected to avoid coupling to the
        # BYOK client here.
        self._llm_healer = llm_healer

    def heal(
        self,
        error: BaseException,
        kwargs: Dict[str, Any],
        provider: str,
        model: str,
    ) -> HealingResult:
        """Attempt to repair a request that failed with a 4xx.

        Returns a HealingResult. ``patched_kwargs`` is None when no repair was
        possible (non-repairable error, or no rule matched and LLM healer is
        off/failed).
        """
        if not is_repairable(error):
            return HealingResult(patched_kwargs=None, rule=None)

        # 1. Try deterministic rules (first match wins).
        for rule in self.rules:
            try:
                if rule.matches(error, kwargs, provider, model):
                    patched, keys = rule.apply(kwargs)
                    if keys:  # only count as a patch if something changed
                        logger.info(
                            f"[RequestHealer] rule '{rule.name}' patched "
                            f"{keys} for {provider}/{model}"
                        )
                        return HealingResult(
                            patched_kwargs=patched, rule=rule.name, patched_keys=keys
                        )
            except Exception:
                logger.debug(
                    f"[RequestHealer] rule '{rule.name}' raised; skipping",
                    exc_info=True,
                )

        # 2. Optional LLM healer fallback.
        if self._llm_healer is not None and os.getenv("ATOM_LLM_HEALER_ENABLED", "false").lower() == "true":
            try:
                llm_result = self._llm_healer(error, kwargs, provider, model)
                # The documented contract is an async callable (see
                # make_default_llm_healer); bridge it here so injecting the
                # module's own factory actually works instead of silently
                # failing on the coroutine unpack.
                if inspect.isawaitable(llm_result):
                    llm_result = asyncio.run(llm_result)  # type: ignore[arg-type]
                if llm_result is not None:
                    patched, keys = llm_result
                    logger.info(
                        f"[RequestHealer] LLM healer patched {keys} for "
                        f"{provider}/{model}"
                    )
                    return HealingResult(
                        patched_kwargs=patched, rule="llm", patched_keys=keys
                    )
            except Exception:
                logger.debug("[RequestHealer] LLM healer raised; skipping", exc_info=True)

        return HealingResult(patched_kwargs=None, rule=None)


# --- Default LLM healer factory (lazy, avoids importing byok at module load) -


def make_default_llm_healer(handler):
    """Build an LLM-based healer closure bound to a BYOKHandler instance.

    The healer sends the failed request + error to the cheapest available
    model and asks for a JSON patch. Returns None if the patch is invalid or
    touches disallowed keys. Designed to be injected into RequestHealer.
    """

    # Keys the LLM healer is allowed to mutate. Never model/auth/headers.
    _ALLOWED_KEYS = frozenset({
        "messages", "max_tokens", "max_output_tokens", "max_completion_tokens",
        "temperature", "top_p", "frequency_penalty", "presence_penalty",
        "response_format", "stop", "seed",
    })

    async def _heal(error, kwargs, provider, model):
        import asyncio
        try:
            error_text = str(error)[:2000]
            # Trim the payload for the healer prompt (avoid sending huge contexts).
            payload_summary = {
                k: (v if k != "messages" else _summarize_messages(v))
                for k, v in kwargs.items()
                if k in _ALLOWED_KEYS or k in ("model", "stream")
            }
            prompt = (
                "A request to an LLM API failed with this error:\n\n"
                f"{error_text}\n\n"
                "Here is the request payload (messages summarized):\n\n"
                f"{json.dumps(payload_summary, default=str)[:4000]}\n\n"
                "Return ONLY a JSON object with a 'patch' key containing the "
                "FULL corrected request body (all keys, not just the changed "
                "ones). Only change keys that fix the error. If the error is "
                "not a request-body problem, return {\"patch\": null}."
            )
            # Use the handler's own completion path with a cheap model. Strict
            # timeout — healing must not add more than a few seconds.
            healed_text = await asyncio.wait_for(
                handler.generate_response(
                    prompt=prompt,
                    system_instruction="You are a JSON-patch generator. Output only JSON.",
                    model_type="auto",
                    temperature=0.0,
                    max_tokens=500,
                ),
                timeout=5.0,
            )
            parsed = json.loads(healed_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
            patch = parsed.get("patch")
            if not isinstance(patch, dict):
                return None
            # Reconstruct full kwargs: start from original, apply only allowed
            # keys from the patch.
            patched = dict(kwargs)
            changed_keys = []
            for k, v in patch.items():
                if k in _ALLOWED_KEYS:
                    if patched.get(k) != v:
                        patched[k] = v
                        changed_keys.append(k)
            return (patched, changed_keys) if changed_keys else None
        except Exception:
            return None

    return _heal


def _summarize_messages(messages: Any) -> List[Dict[str, str]]:
    """Reduce messages to role+truncated-content for the healer prompt."""
    if not isinstance(messages, list):
        return [{"role": "unknown", "content": str(messages)[:200]}]
    out = []
    for m in messages[-6:]:  # last 6 messages only
        if isinstance(m, dict):
            role = m.get("role", "unknown")
            content = m.get("content", "")
            if isinstance(content, list):
                # Multimodal: summarize parts.
                parts = []
                for p in content:
                    if isinstance(p, dict):
                        parts.append(f"[{p.get('type', '?')}]")
                content = " ".join(parts) or "(multimodal)"
            out.append({"role": role, "content": str(content)[:300]})
    return out


# Module-level singleton (stateless; safe to share).
_default_healer: Optional[RequestHealer] = None


def get_request_healer() -> RequestHealer:
    """Return a process-wide default RequestHealer (rules-only; no LLM)."""
    global _default_healer
    if _default_healer is None:
        _default_healer = RequestHealer()
    return _default_healer
