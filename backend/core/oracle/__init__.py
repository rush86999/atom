"""
Postcondition oracle — external verification of mutating actions (W2, P3a).

Closes the self-attestation gap: ``tool_outcome_verifier`` parses a tool's
*own* return (``{verified: true, …}``) — but the entity being checked must
never grade its own work (Postcept principle). This module re-derives
success against the **system of record** (DB read-back, status endpoint),
independently of the tool's claim.

Behind ``ATOM_ORACLE_VERIFIER_ENABLED`` (default false → shadow: checks
computed + audited but the existing ``verified`` flag still comes from
self-report until enforced).
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
    """Master switch for postcondition oracle verification. Default False (shadow)."""
    return _env_bool("ATOM_ORACLE_VERIFIER_ENABLED", False)


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
