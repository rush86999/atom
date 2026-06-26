"""
Tool Outcome Verifier — parses tool returns into a tri-state verified flag.

Defends against silent no-op tool returns (general critique, fixed).

Contract:
  Tools MAY return a structured dict with any of:
    {success: bool, verified: bool, evidence: str}
  - ``verified=True``  → the tool actively confirmed the world changed
                         (e.g. re-queried the DOM, stat()ed the file)
  - ``verified=False`` → the tool ran a verify() step and it FAILED
                         (explicit negative — stronger than unverified)
  - ``verified`` absent → 'unverified' (default; backward-compatible)

  Tools that return a plain string, or a dict without these keys, are
  'unverified'. Existing tools degrade gracefully — no contract break.

Graduation consumes the resulting VerifiedOutcome and gates on
``kind == 'verified'`` so silent no-ops can't inflate capability stats.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Tri-state discriminator values (stored in AgentReasoningStep.verified)
VERIFIED = "verified"
UNVERIFIED = "unverified"
FAILED_VERIFICATION = "failed_verification"

_VALID_STATES = {VERIFIED, UNVERIFIED, FAILED_VERIFICATION}


@dataclass(frozen=True)
class VerifiedOutcome:
    """
    Parsed tool-return envelope.

    ``kind`` is the tri-state: 'verified' | 'unverified' | 'failed_verification'.
    ``success`` is the tool's self-reported bool (kept for audit, NOT trusted
    for graduation).
    ``evidence`` is whatever the tool offered as proof (file path, row id,
    HTTP status, screenshot hash) — stored for traceability.
    """
    kind: str
    success: bool
    evidence: Optional[str] = None
    raw: Optional[str] = None

    @property
    def is_verified(self) -> bool:
        return self.kind == VERIFIED


def parse_tool_outcome(observation: Any) -> VerifiedOutcome:
    """
    Parse a raw tool return into a VerifiedOutcome.

    Accepts:
      - dict (or JSON string of a dict) with optional success/verified/evidence
      - any other value → unverified, success inferred from truthiness

    Never raises. On any parse failure → unverified.
    """
    if observation is None:
        return VerifiedOutcome(kind=UNVERIFIED, success=False, raw=None)

    # Try to interpret as a dict — either passed directly or as a JSON string.
    payload: Optional[dict] = None
    raw_str: Optional[str]

    if isinstance(observation, dict):
        payload = observation
        raw_str = json.dumps(observation, default=str)
    elif isinstance(observation, str):
        raw_str = observation
        stripped = observation.strip()
        # Common case: tools return str({"success": True, ...}) via str(result)
        # Try JSON parse, tolerating Python repr (single quotes + True/False/None).
        candidate = stripped
        if candidate.startswith("{") and candidate.endswith("}"):
            try:
                payload = json.loads(candidate)
            except Exception:
                # Normalize Python repr → JSON: single quotes → double,
                # True/False/None → true/false/null. Best-effort.
                try:
                    normalized = (
                        candidate.replace("'", '"')
                        .replace(": True", ": true")
                        .replace(": False", ": false")
                        .replace(": None", ": null")
                        .replace("[True", "[true")
                        .replace("[False", "[false")
                        .replace("[None", "[null")
                        .replace(", True", ", true")
                        .replace(", False", ", false")
                        .replace(", None", ", null")
                    )
                    payload = json.loads(normalized)
                except Exception:
                    payload = None
    else:
        raw_str = str(observation)

    if payload is None:
        # Plain string return — no success signal available.
        return VerifiedOutcome(
            kind=UNVERIFIED,
            success=bool(raw_str),
            evidence=None,
            raw=raw_str,
        )

    success_raw = payload.get("success", None)
    # Treat explicit success=False as success=False; absent or True as True.
    success = False if success_raw is False else True

    verified_raw = payload.get("verified", None)
    evidence = payload.get("evidence") or payload.get("verification_evidence")
    if isinstance(evidence, (dict, list)):
        evidence = json.dumps(evidence, default=str)

    if verified_raw is True:
        kind = VERIFIED
    elif verified_raw is False:
        kind = FAILED_VERIFICATION
    else:
        kind = UNVERIFIED

    return VerifiedOutcome(kind=kind, success=success, evidence=evidence, raw=raw_str)


def coerce_verified_for_storage(value: Optional[str]) -> str:
    """Coerce an arbitrary value into a valid stored state."""
    if value in _VALID_STATES:
        return value
    return UNVERIFIED
