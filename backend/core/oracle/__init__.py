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
