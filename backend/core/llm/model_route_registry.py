# -*- coding: utf-8 -*-
"""Executable model routes: catalog knowledge vs what a provider actually serves.

WHY THIS EXISTS
===============

BPC ranks candidates from a *catalog* (quality scores + pricing). A catalog
entry says a model EXISTS and what it costs — it says nothing about whether a
configured endpoint in THIS install serves it, under which identifier. The
incident this closes: every ranked rung named an identifier the configured
providers reject — ``openrouter`` answered "not a valid model ID" and
``opencode-go`` answered 401 — so the ladder walked three independent providers
and failed on all of them. Provider diversity does not help when every rung is
unservable.

Three things follow, and this module owns all three.

1. ROUTE IDENTITY
   A route is ``(provider_id, model_id)`` where ``model_id`` is the identifier
   THAT provider accepts. The same underlying model is exposed under different
   provider-specific identifiers (``deepseek-v4-pro`` on the ``deepseek``
   provider, ``deepseek/deepseek-v4-flash-0731`` on ``openrouter``); a route
   never transplants one provider's identifier into another gateway.

2. CATALOG KNOWLEDGE vs EXECUTABLE ROUTES
   :class:`ProviderModelCatalog` records which model identifiers each provider
   was last observed to serve, WHEN that was observed, and whether the
   observation is still fresh. Eligibility is decided from that record —
   *not* from "the gateway accepts anything".

   * discovery **succeeded** → that set is authoritative for the provider;
   * discovery **failed** → the previously verified set is KEPT and marked
     stale. Failure never means "everything is supported"; it also never
     erases what was verified earlier.
   * **never discovered** → ``unknown``. Unknown is not eligible: an
     unverified route is not dispatched automatically. The caller may still
     name it explicitly (an operator who knows their endpoint), which is why
     eligibility is a property of the ROUTE, not a veto on the provider.

3. FAILURE CAUSE
   ``401`` is not one thing. A credential the provider rejects and a model the
   provider does not serve are different failures with different responses:
   the first should stop asking that provider for other models, the second
   should not disable an otherwise working provider. :func:`classify_failure`
   separates invalid credential / unsupported model / entitlement / quota /
   rate limit / malformed request / transport, and never leaks credential
   material into the recorded detail.

Discovery itself is the provider's own ``models`` endpoint — the same one the
Settings "Test" button uses. That endpoint can answer without validating the
key (observed live: ``opencode-go`` answers ``models.list()`` while a
completion returns 401), which is exactly why discovery and authentication are
recorded as SEPARATE facts.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: How long a successful discovery stays "fresh". After this the set is still
#: used (previously verified beats unknown) but flagged stale.
DEFAULT_FRESHNESS_SECONDS = 6 * 60 * 60

#: Providers whose model list is not discoverable over an HTTP catalogue call.
#: Ollama is probed through its own runtime endpoint and is handled by the
#: caller; a provider listed here is never assumed to serve anything.
NON_CATALOG_PROVIDERS = frozenset({"ollama", "vllm", "lmstudio", "local"})


def _now() -> float:
    return time.time()


def _iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Failure causes
# ---------------------------------------------------------------------------

class FailureCause:
    """Why one provider attempt failed. Distinct causes demand distinct
    responses, which is the whole point of separating them."""

    INVALID_CREDENTIAL = "invalid_credential"
    UNSUPPORTED_MODEL = "unsupported_model"
    ENTITLEMENT = "entitlement"
    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMITED = "rate_limited"
    MALFORMED_REQUEST = "malformed_request"
    TRANSPORT = "transport"
    EMPTY_OUTPUT = "empty_output"
    UNKNOWN = "unknown"

    #: Causes that mean "this PROVIDER cannot be used right now": asking it for
    #: a different model will fail the same way.
    PROVIDER_SCOPED = frozenset({
        INVALID_CREDENTIAL, ENTITLEMENT, QUOTA_EXHAUSTED, RATE_LIMITED,
    })
    #: Causes scoped to the ROUTE (provider + model): the provider may be
    #: perfectly healthy for other models.
    ROUTE_SCOPED = frozenset({UNSUPPORTED_MODEL, MALFORMED_REQUEST})
    ALL = frozenset({
        INVALID_CREDENTIAL, UNSUPPORTED_MODEL, ENTITLEMENT, QUOTA_EXHAUSTED,
        RATE_LIMITED, MALFORMED_REQUEST, TRANSPORT, EMPTY_OUTPUT, UNKNOWN,
    })


_CREDENTIAL_RE = re.compile(
    r"invalid\s+api\s*key|incorrect\s+api\s*key|unauthorized|authentication|"
    r"auth(?:entication)?\s+error|invalid\s+token|api\s*key\s+(?:is\s+)?"
    r"(?:invalid|missing|expired|revoked)|no\s+auth",
    re.IGNORECASE)
_MODEL_RE = re.compile(
    r"not\s+a\s+valid\s+model|model[_\s]?(?:id|name)?\s*(?:is\s+)?"
    r"(?:not\s+found|unknown|unsupported|invalid|does\s+not\s+exist|"
    r"not\s+exist)|unsupported\s+model|no\s+such\s+model|"
    r"unknown\s+model|does\s+not\s+support\s+(?:the\s+)?model",
    re.IGNORECASE)
_ENTITLEMENT_RE = re.compile(
    r"not\s+entitled|entitlement|plan\s+(?:does\s+not|doesn't|not)\s+"
    r"(?:include|support)|upgrade\s+your\s+plan|subscription\s+(?:required|"
    r"inactive|expired)|permission\s+denied|forbidden",
    re.IGNORECASE)
_QUOTA_RE = re.compile(
    r"insufficient\s+(?:balance|credits?|funds|quota)|quota\s+exceeded|"
    r"out\s+of\s+credits|exceeded\s+your\s+(?:current\s+)?quota|"
    r"billing|payment\s+required|credit\s+limit",
    re.IGNORECASE)
_RATE_RE = re.compile(
    r"rate\s*limit|too\s+many\s+requests|429|slow\s+down|retry\s+after",
    re.IGNORECASE)
_MALFORMED_RE = re.compile(
    r"invalid\s+(?:request|parameter|argument|schema|json)|"
    r"validation\s+error|unprocessable|missing\s+(?:required\s+)?(?:field|"
    r"parameter)|malformed",
    re.IGNORECASE)
_TRANSPORT_RE = re.compile(
    r"timed?\s*out|timeout|connection|connect|network|unreachable|"
    r"temporary\s+failure|ssl|socket|reset\s+by\s+peer|502|503|504",
    re.IGNORECASE)


def _status_of(exc: BaseException) -> Optional[int]:
    for attr in ("status_code", "http_status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    for attr in ("status_code", "status"):
        value = getattr(response, attr, None)
        if isinstance(value, int):
            return value
    return None


def sanitize_error_text(text: Any, limit: int = 400) -> str:
    """Provider error text with credential-shaped material removed.

    Error bodies quote the request; a leaked key in a log line is a real
    incident. Keeps enough to act on (status + wording), drops anything that
    looks like a secret.
    """
    s = str(text or "")
    s = re.sub(r"\b(sk|pk|rk|ghp|xox[baprs])-[A-Za-z0-9_\-]{6,}", "[redacted-key]", s)
    s = re.sub(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{8,}", r"\1 [redacted]", s)
    s = re.sub(r"(?i)(api[_\s-]?key\"?\s*[:=]\s*\"?)[^\s\"',}]{6,}",
               r"\1[redacted]", s)
    return s[:limit]


def classify_failure(
    exc: Optional[BaseException] = None,
    *,
    status: Optional[int] = None,
    body: Optional[str] = None,
    empty_output: bool = False,
) -> Tuple[str, str, Optional[int]]:
    """Return ``(cause, sanitized_detail, http_status)`` for one attempt.

    Model-rejection is checked BEFORE credential-rejection on purpose: some
    gateways answer an unsupported model with ``401`` and a body that names the
    model. Reading that as a credential failure disables a working provider and
    sends the operator to rotate a perfectly good key (observed live
    2026-09-16: ``opencode-go`` 401s with "not a valid model ID" text while its
    own ``models.list()`` answers).
    """
    detail = sanitize_error_text(body if body is not None else exc)
    http_status = status if status is not None else _status_of(exc) if exc else None

    if http_status is None and empty_output:
        return FailureCause.EMPTY_OUTPUT, detail or "empty output", None

    text = detail or ""
    status_class = http_status // 100 if isinstance(http_status, int) else None

    # Model rejection first — regardless of status code.
    if _MODEL_RE.search(text):
        return FailureCause.UNSUPPORTED_MODEL, text, http_status

    if _CREDENTIAL_RE.search(text) and (status_class == 4 or http_status is None):
        return FailureCause.INVALID_CREDENTIAL, text, http_status
    if _ENTITLEMENT_RE.search(text):
        return FailureCause.ENTITLEMENT, text, http_status
    if _QUOTA_RE.search(text):
        return FailureCause.QUOTA_EXHAUSTED, text, http_status
    if _RATE_RE.search(text) or http_status == 429:
        return FailureCause.RATE_LIMITED, text, http_status
    if _MALFORMED_RE.search(text):
        return FailureCause.MALFORMED_REQUEST, text, http_status

    if http_status == 401 or http_status == 403:
        return FailureCause.INVALID_CREDENTIAL, text, http_status
    if http_status == 402:
        return FailureCause.QUOTA_EXHAUSTED, text, http_status
    if http_status == 404:
        # A 404 from a gateway is ambiguous; without model wording it is more
        # often a wrong route than a wrong key, and treating it as a credential
        # problem would disable the provider. Route-scoped is the safe read.
        return FailureCause.UNSUPPORTED_MODEL, text, http_status
    if http_status == 400:
        return FailureCause.MALFORMED_REQUEST, text, http_status
    if _TRANSPORT_RE.search(text) or (status_class == 5):
        return FailureCause.TRANSPORT, text, http_status
    if empty_output:
        return FailureCause.EMPTY_OUTPUT, text, http_status
    return FailureCause.UNKNOWN, text, http_status


# ---------------------------------------------------------------------------
# Provider model catalog
# ---------------------------------------------------------------------------

@dataclass
class ProviderObservation:
    """What was last observed about one provider's served model identifiers."""

    provider_id: str
    served: Optional[List[str]] = None      # None = never successfully discovered
    verified_at: Optional[float] = None
    last_attempt_at: Optional[float] = None
    last_error: Optional[str] = None
    last_error_cause: Optional[str] = None
    consecutive_failures: int = 0
    #: Whether a MINIMAL REAL COMPLETION authenticated — deliberately separate
    #: from discovery, because a provider can answer its catalogue and still
    #: reject every completion (observed live on opencode-go).
    auth_ok: Optional[bool] = None
    auth_checked_at: Optional[float] = None
    auth_detail: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "served_count": len(self.served) if self.served is not None else None,
            "served_sample": (self.served or [])[:8],
            "verified_at": _iso(self.verified_at),
            "last_attempt_at": _iso(self.last_attempt_at),
            "last_error": self.last_error,
            "last_error_cause": self.last_error_cause,
            "consecutive_failures": self.consecutive_failures,
            "auth_ok": self.auth_ok,
            "auth_checked_at": _iso(self.auth_checked_at),
            "auth_detail": self.auth_detail,
        }


@dataclass(frozen=True)
class RouteDecision:
    """Whether one ``(provider, model)`` route may be dispatched automatically."""

    provider_id: str
    model_id: str
    eligible: bool
    #: Machine-readable reason. Every candidate gets one, so a report can say
    #: WHY a rung was used or skipped instead of showing a silent shortfall.
    reason: str
    freshness: str  # "fresh" | "stale" | "unknown"
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider_id,
            "model": self.model_id,
            "eligible": self.eligible,
            "reason": self.reason,
            "freshness": self.freshness,
            "detail": self.detail,
        }


#: Eligibility reasons (recorded per candidate).
REASON_VERIFIED = "verified_served"
REASON_STALE = "previously_verified_stale"
REASON_NOT_IN_CATALOG = "not_in_provider_catalog"
REASON_UNKNOWN_CATALOG = "provider_catalog_unknown"
REASON_PROVIDER_NOT_CONFIGURED = "provider_not_configured"
REASON_LOCAL_RUNTIME = "local_runtime_served"
REASON_EXPLICIT_REQUEST = "explicitly_requested_route"


class ProviderModelCatalog:
    """File-backed, thread-safe record of which identifiers each provider serves.

    Persisted so a restart does not erase what was verified, and so the
    freshness of that verification is visible instead of implied.
    """

    def __init__(self, path: Optional[str] = None,
                 freshness_seconds: int = DEFAULT_FRESHNESS_SECONDS):
        self.path = path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "data",
            "provider_model_catalog.json")
        self.freshness_seconds = freshness_seconds
        self._lock = threading.RLock()
        self._observations: Dict[str, ProviderObservation] = {}
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return
        except Exception as exc:  # noqa: BLE001 — a corrupt cache is not fatal
            logger.warning("provider model catalog unreadable (%s); starting "
                           "empty — routes will be treated as unknown", exc)
            return
        for provider_id, raw in (data.get("providers") or {}).items():
            if not isinstance(raw, dict):
                continue
            served = raw.get("served")
            self._observations[provider_id] = ProviderObservation(
                provider_id=provider_id,
                served=[str(m) for m in served] if isinstance(served, list) else None,
                verified_at=raw.get("verified_at"),
                last_attempt_at=raw.get("last_attempt_at"),
                last_error=raw.get("last_error"),
                last_error_cause=raw.get("last_error_cause"),
                consecutive_failures=int(raw.get("consecutive_failures") or 0),
                auth_ok=raw.get("auth_ok"),
                auth_checked_at=raw.get("auth_checked_at"),
                auth_detail=raw.get("auth_detail"),
            )

    def _save_locked(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            payload = {
                "version": 1,
                "updated_at": _iso(_now()),
                "providers": {
                    pid: {
                        "served": obs.served,
                        "verified_at": obs.verified_at,
                        "last_attempt_at": obs.last_attempt_at,
                        "last_error": obs.last_error,
                        "last_error_cause": obs.last_error_cause,
                        "consecutive_failures": obs.consecutive_failures,
                        "auth_ok": obs.auth_ok,
                        "auth_checked_at": obs.auth_checked_at,
                        "auth_detail": obs.auth_detail,
                    }
                    for pid, obs in self._observations.items()
                },
            }
            tmp = f"{self.path}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, self.path)
        except Exception as exc:  # noqa: BLE001 — cache write is best-effort
            logger.debug("provider model catalog write skipped: %s", exc)

    # -- recording --------------------------------------------------------
    def record_discovery(self, provider_id: str,
                         model_ids: Iterable[str]) -> ProviderObservation:
        """Record a SUCCESSFUL discovery of the provider's served identifiers."""
        ids = sorted({str(m).strip() for m in (model_ids or []) if str(m).strip()})
        with self._lock:
            obs = self._observations.setdefault(
                provider_id, ProviderObservation(provider_id=provider_id))
            obs.served = ids
            obs.verified_at = _now()
            obs.last_attempt_at = obs.verified_at
            obs.last_error = None
            obs.last_error_cause = None
            obs.consecutive_failures = 0
            self._save_locked()
            return obs

    def record_discovery_failure(self, provider_id: str, error: Any,
                                 cause: Optional[str] = None) -> ProviderObservation:
        """Record a FAILED discovery.

        The previously verified set is deliberately KEPT: a transient network
        failure must not downgrade a provider from "serves these 40 models" to
        "serves anything", nor to "serves nothing". The failure is visible as
        ``last_error`` plus a staleness that grows with time.
        """
        with self._lock:
            obs = self._observations.setdefault(
                provider_id, ProviderObservation(provider_id=provider_id))
            obs.last_attempt_at = _now()
            obs.last_error = sanitize_error_text(error)
            obs.last_error_cause = cause
            obs.consecutive_failures += 1
            self._save_locked()
            return obs

    def record_auth_probe(self, provider_id: str, ok: bool,
                          detail: Any = None) -> None:
        """Record whether a MINIMAL REAL COMPLETION authenticated.

        Separate from discovery on purpose: a provider can answer its model
        catalogue and still reject every completion (observed live). The two
        facts are stored apart so neither is mistaken for the other.
        """
        with self._lock:
            obs = self._observations.setdefault(
                provider_id, ProviderObservation(provider_id=provider_id))
            obs.auth_ok = bool(ok)
            obs.auth_checked_at = _now()
            obs.auth_detail = sanitize_error_text(detail) if detail else None
            self._save_locked()

    # -- reads ------------------------------------------------------------
    def observe(self, provider_id: str) -> ProviderObservation:
        with self._lock:
            obs = self._observations.get(provider_id)
            if obs is None:
                return ProviderObservation(provider_id=provider_id)
            return ProviderObservation(**{**obs.__dict__})

    def served(self, provider_id: str) -> Optional[FrozenSet[str]]:
        """The provider's served identifiers, or ``None`` when never verified."""
        obs = self.observe(provider_id)
        return frozenset(obs.served) if obs.served is not None else None

    def freshness(self, provider_id: str) -> str:
        obs = self.observe(provider_id)
        if obs.served is None or obs.verified_at is None:
            return "unknown"
        return ("fresh" if (_now() - obs.verified_at) <= self.freshness_seconds
                else "stale")

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "freshness_seconds": self.freshness_seconds,
                "providers": {
                    pid: {**obs.as_dict(), "freshness": self.freshness(pid)}
                    for pid, obs in self._observations.items()
                },
            }

    def invalidate(self, provider_id: Optional[str] = None) -> None:
        """Forget discovered sets so the next decision re-discovers.

        Called when configuration changes (a key is stored/rotated): a
        credential rejected five minutes ago may be valid now, and a catalog
        fetched with the old key may not apply to the new one.
        """
        with self._lock:
            if provider_id is None:
                self._observations.clear()
            else:
                self._observations.pop(provider_id, None)
            self._save_locked()


#: Process-wide catalog (the file is the shared state; instances are cheap).
_CATALOG: Optional[ProviderModelCatalog] = None
_CATALOG_LOCK = threading.Lock()


def get_provider_model_catalog() -> ProviderModelCatalog:
    global _CATALOG
    if _CATALOG is None:
        with _CATALOG_LOCK:
            if _CATALOG is None:
                _CATALOG = ProviderModelCatalog()
    return _CATALOG


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_provider_models(client: Any, provider_id: str,
                             timeout: float = 10.0) -> Tuple[Optional[List[str]], Optional[str]]:
    """Ask the provider's own catalogue endpoint which identifiers it serves.

    Returns ``(model_ids, error)``. A caller must treat ``(None, error)`` as
    UNKNOWN — never as "everything is supported". Uses the same client
    configuration the chat path uses, so a discovery result describes the
    endpoint that will actually serve requests.
    """
    try:
        models = client.models.list()
    except Exception as exc:  # noqa: BLE001 — discovery is best-effort
        return None, sanitize_error_text(exc)
    ids: List[str] = []
    for item in getattr(models, "data", None) or []:
        mid = getattr(item, "id", None)
        if mid is None and isinstance(item, dict):
            mid = item.get("id")
        if mid:
            ids.append(str(mid))
    if not ids:
        return None, "catalogue returned no model identifiers"
    return sorted(set(ids)), None


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def _identifier_aliases(provider_id: str, model_id: str) -> FrozenSet[str]:
    """The identifier forms that count as THIS provider serving THIS model.

    Exact matching, deliberately — case- and whitespace-normalised only.

    An earlier version also matched the bare TAIL of a namespaced id, so
    ``tencent/deepseek-v4-pro`` "matched" the ``deepseek`` provider because it
    ends in ``deepseek-v4-pro``. That is the transplant the review forbids: it
    dispatched another gateway's catalog identifier to a first-party endpoint,
    which answered

        400: the supported API model names are deepseek-flash,
        deepseek-v4-pro, but you passed tencent/deepseek-v4-pro

    (observed live 2026-09-16, after the first reconciliation pass). "The same
    model under different provider-specific identifiers" is covered the correct
    way: each provider's DISCOVERED catalogue carries ITS OWN identifier for
    that model (``deepseek-v4-pro`` for the ``deepseek`` provider,
    ``deepseek/deepseek-v4-flash-0731`` for ``openrouter``), and a route is
    that pair. Two names for one model are two routes — never one route with a
    borrowed name.
    """
    return frozenset({str(model_id).strip().lower()})


def evaluate_route(
    provider_id: str,
    model_id: str,
    *,
    catalog: Optional[ProviderModelCatalog] = None,
    configured_providers: Optional[Iterable[str]] = None,
    local_runtime_models: Optional[Iterable[str]] = None,
    explicit: bool = False,
) -> RouteDecision:
    """Decide whether one route may be dispatched, WITH the reason recorded.

    ``explicit=True`` marks the route the caller named. An explicitly requested
    route is always eligible (the operator may know something discovery does
    not) but is still reported with its discovery state, so a failure can be
    attributed instead of guessed.
    """
    catalog = catalog or get_provider_model_catalog()
    configured = set(configured_providers or [])
    if configured and provider_id not in configured:
        return RouteDecision(provider_id, model_id, False,
                             REASON_PROVIDER_NOT_CONFIGURED, "unknown",
                             "no client is configured for this provider")

    if provider_id in NON_CATALOG_PROVIDERS:
        served_local = set(local_runtime_models or [])
        if served_local and _identifier_aliases(provider_id, model_id) & served_local:
            return RouteDecision(provider_id, model_id, True,
                                 REASON_LOCAL_RUNTIME, "fresh",
                                 "served by the local runtime probe")
        if explicit:
            return RouteDecision(provider_id, model_id, True,
                                 REASON_EXPLICIT_REQUEST, "fresh",
                                 "explicitly requested local model")
        return RouteDecision(provider_id, model_id, False,
                             REASON_UNKNOWN_CATALOG, "unknown",
                             "local runtime does not advertise this model")

    served = catalog.served(provider_id)
    freshness = catalog.freshness(provider_id)
    if served is None:
        # NEVER verified. Not "everything is supported", and not a veto on an
        # explicit request either.
        if explicit:
            return RouteDecision(
                provider_id, model_id, True, REASON_EXPLICIT_REQUEST, "unknown",
                "explicitly requested while the provider catalogue is unknown")
        return RouteDecision(
            provider_id, model_id, False, REASON_UNKNOWN_CATALOG,
            "unknown",
            "provider catalogue has never been discovered; support is unknown, "
            "not assumed")

    if _identifier_aliases(provider_id, model_id) & served:
        if freshness == "fresh":
            return RouteDecision(provider_id, model_id, True,
                                 REASON_VERIFIED, "fresh", "")
        return RouteDecision(
            provider_id, model_id, True, REASON_STALE, freshness,
            "verified earlier; catalogue is stale, support not re-confirmed")

    return RouteDecision(
        provider_id, model_id, False, REASON_NOT_IN_CATALOG, freshness,
        f"identifier not present in {provider_id}'s discovered catalogue "
        f"({len(served)} identifiers)")


def reconcile_routes(
    routes: Iterable[Tuple[str, str]],
    **kwargs: Any,
) -> Tuple[List[RouteDecision], List[RouteDecision]]:
    """Split candidate routes into ``(eligible, excluded)`` with reasons."""
    eligible: List[RouteDecision] = []
    excluded: List[RouteDecision] = []
    for provider_id, model_id in routes:
        decision = evaluate_route(provider_id, model_id, **kwargs)
        (eligible if decision.eligible else excluded).append(decision)
    return eligible, excluded
