"""
Postcondition oracle — external verification of mutating actions (W2, P3a).

Closes the self-attestation gap: ``tool_outcome_verifier`` parses a tool's
*own* return (``{verified: true, …}``) — but the entity being checked must
never grade its own work (Postcept principle). This module re-derives
success against the **system of record** (DB read-back, status endpoint),
independently of the tool's claim.

Behind ``ATOM_ORACLE_VERIFIER_ENABLED`` (default true — the checks run).
Since W2 the oracle also stamps tool outcomes post-execution (default ON via
``ATOM_ORACLE_ENFORCE``, default true): a refuted self-report is marked
UNVERIFIED on the observation so downstream confidence scoring cannot treat
it as fact. Set ``ATOM_ORACLE_ENFORCE=false`` to revert to pass-through.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def oracle_verifier_enabled() -> bool:
    """Master switch for postcondition oracle verification. Default True."""
    return _env_bool("ATOM_ORACLE_VERIFIER_ENABLED", True)


@dataclass(frozen=True)
class OracleResult:
    """Outcome of an independent postcondition check."""
    action: str
    verified: bool  # True ONLY if the system of record confirms the effect
    evidence: str   # what the oracle observed (e.g. "workflow.state == 'running'")
    claim_verified: Optional[bool] = None  # did the tool's own claim agree?

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action, "verified": self.verified,
            "evidence": self.evidence, "claim_verified": self.claim_verified,
        }


# Registry of postcondition verifiers: action_name -> async callable(ctx) -> OracleResult.
_VERIFIERS: Dict[str, Callable] = {}


def register_postcondition(action: str):
    """Decorator: register a postcondition verifier for a mutating action."""
    def deco(fn: Callable):
        _VERIFIERS[action] = fn
        return fn
    return deco


def get_postcondition(action: str) -> Optional[Callable]:
    return _VERIFIERS.get(action)


# ---------------------------------------------------------------------------
# Durable effect receipt contract
# ---------------------------------------------------------------------------
# A succeeded claim must retain enough exact identity for a later replay to
# re-read the SAME provider resource.  The shared claim persistence is domain
# neutral: it stores only the common provider/result/receipt envelope plus
# opaque store identity and digests.  Domain-specific material (for example a
# Shopify product projection) is supplied by the provider/verifier layer that
# already owns that action's postcondition, through the registries below.

_DURABLE_RECEIPT_PROJECTORS: Dict[str, Callable] = {}
_DURABLE_RECEIPT_MATCHERS: Dict[str, Callable] = {}

#: Only allowlisted opaque identity/digest fields are retained from the
#: producer's receipts.  Credentials, headers, transport objects and other
#: unbounded fields must never become durable proof text.
_DURABLE_RECEIPT_FIELDS = {
    "provider_receipt": frozenset({
        "provider", "operation", "operation_id", "payload_sha256",
        "remote_id", "resource_id", "account_id", "organization_id",
        "workspace_id", "tenant_id", "shop", "store", "store_id",
    }),
    "read_receipt": frozenset({
        "provider", "operation", "resource_id", "requested_remote_id",
        "observed_remote_id", "coverage", "account_id", "organization_id",
        "workspace_id", "tenant_id", "shop", "store", "store_id", "fields",
    }),
    "verification": frozenset({
        "status", "missing_fields", "mismatches", "operation_id",
        "payload_sha256", "resource_id", "remote_id", "coverage",
    }),
}

_STORE_IDENTITY_FIELDS = (
    "account_id", "organization_id", "store_id", "shop", "store")


def register_durable_receipt_projector(action: str):
    """Decorator: add provider-specific fields to a durable claim receipt."""
    def deco(fn: Callable):
        _DURABLE_RECEIPT_PROJECTORS[str(action)] = fn
        return fn
    return deco


def register_durable_receipt_matcher(action: str):
    """Decorator: compare a stored receipt with the current request material."""
    def deco(fn: Callable):
        _DURABLE_RECEIPT_MATCHERS[str(action)] = fn
        return fn
    return deco


def _allowlisted_receipt(value: Any, allowed: frozenset) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    import copy

    return {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if isinstance(key, str) and key in allowed
    }


def _opaque_store(*receipts: Any) -> str:
    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        for field in _STORE_IDENTITY_FIELDS:
            value = receipt.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def build_durable_effect_result(
    action: str, result: Any, expected: Dict[str, Any] | None,
) -> Optional[Dict[str, Any]]:
    """Build the domain-neutral durable result/receipt for a confirmed effect.

    Returns ``None`` when the proof cannot be represented as strict JSON.  A
    succeeded claim is then not written at all; the caller reports genuine
    uncertainty instead of certifying lossy receipt text.  Provider-specific
    material is added by a registered projector, never by shared claim code.
    """
    if not isinstance(result, dict):
        return None
    expected = expected or {}
    name = str(action or "")
    provider_receipt = _allowlisted_receipt(
        result.get("provider_receipt"),
        _DURABLE_RECEIPT_FIELDS["provider_receipt"])
    read_receipt = _allowlisted_receipt(
        result.get("read_receipt"),
        _DURABLE_RECEIPT_FIELDS["read_receipt"])
    verification = _allowlisted_receipt(
        result.get("verification"),
        _DURABLE_RECEIPT_FIELDS["verification"])

    domain: Dict[str, Any] = {}
    projector = _DURABLE_RECEIPT_PROJECTORS.get(name)
    if projector is not None:
        try:
            projected = projector(result, expected)
        except Exception:  # noqa: BLE001 - no receipt is honest uncertainty
            return None
        if not isinstance(projected, dict):
            return None
        domain = projected

    from core.outbound_operation_claim import strict_json_roundtrip

    receipt = {
        "durable_result_version": 1,
        "action": name,
        "operation_id": str(
            expected.get("_oracle_expected_operation_id")
            or result.get("operation_id") or ""),
        "payload_sha256": str(result.get("payload_sha256") or ""),
        "provider": str(result.get("provider") or ""),
        "operation": str(result.get("operation") or ""),
        "action_result": str(result.get("action_result") or "applied"),
        "status": "success",
        "success": True,
        "remote_id": str(result.get("remote_id") or "").strip(),
        "store": _opaque_store(read_receipt, provider_receipt),
        "workspace_id": str(
            expected.get("_oracle_expected_workspace_id") or ""),
        "tenant_id": str(
            expected.get("_oracle_expected_tenant_id") or ""),
        "provider_receipt": provider_receipt,
        "read_receipt": read_receipt,
        "verification": verification,
        "oracle_verified": bool(result.get("oracle_verified")),
        "oracle_evidence": str(result.get("oracle_evidence") or ""),
    }
    receipt.update(domain)
    return strict_json_roundtrip(receipt)


def durable_result_conflicts(
    action: str, expected: Dict[str, Any] | None,
    durable_result: Any,
) -> list:
    """Provider-registered comparison of stored proof with this request.

    An action with no registered matcher has no provider-specific material to
    compare; the postcondition verifier still re-reads the effect.  A matcher
    that errors is treated as a conflict (fail closed), never as a match.
    """
    matcher = _DURABLE_RECEIPT_MATCHERS.get(str(action or ""))
    if matcher is None:
        return []
    try:
        conflicts = matcher(expected or {}, durable_result or {})
    except Exception as exc:  # noqa: BLE001 - unreadable proof is not a match
        return [f"durable receipt comparison unavailable: {type(exc).__name__}"]
    if not conflicts:
        return []
    return [str(item) for item in conflicts if str(item)]


async def validate(action: str, context: Optional[Dict[str, Any]] = None) -> Optional[OracleResult]:
    """Independently re-derive whether ``action`` achieved its postcondition.

    Returns None if no verifier is registered for ``action`` (the action is
    not in the high-risk mutating set — self-report stands).
    """
    fn = get_postcondition(action)
    if fn is None:
        return None
    try:
        return await fn(context or {})
    except Exception as e:
        logger.warning(f"[Oracle] postcondition check for {action} failed: {e}")
        return OracleResult(
            action=action, verified=False,
            evidence=f"oracle check errored: {e}", claim_verified=None,
        )


async def verify_before_retry(action: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """arXiv 2608.02645 (P3b): on an ambiguous timeout, verify BEFORE retrying.

    Returns True when the postcondition is already met (the effect landed
    despite the timeout) — the caller must NOT retry, or it would duplicate
    the side effect. Returns False when verification is disabled, the action
    has no verifier (not in the high-risk mutating set), or the postcondition
    is genuinely unmet (retry is still correct).

    The flag-gated path is used because in shadow mode (default) the oracle
    is advisory; the ``ATOM_ORACLE_VERIFIER_ENABLED`` kill switch turns the
    check on end-to-end.
    """
    if not oracle_verifier_enabled():
        return False
    result = await validate(action, context)
    return result is not None and result.verified


# Import the built-in verifiers when the oracle package is imported. Callers
# that only import ``core.oracle`` (the executor consumer, generic agent, API
# startup) must not see an empty registry simply because no test imported the
# registration module first.
from . import postcondition_verifiers as _postcondition_verifiers  # noqa: E402,F401
