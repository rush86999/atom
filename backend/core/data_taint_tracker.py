"""
Data Taint Tracker — P4 (Cloudflare OS G4).

Tracks the sensitivity of data an agent observed during a run and blocks (or
escalates to HITL) risky outbound actions when sensitive data is headed to an
external destination. Emits the previously-reserved ``VT_PROVENANCE`` violation
type (``core/sandbox_policy.py:72``) for the first time.

Sensitivity levels (ascending): public < internal < confidential < restricted.
PII patterns (SSN, credit cards, API keys) auto-classify as ``restricted``.

Stamps into the correct JSON columns (corrections from the original plan):
- AgentExecution.metadata_json (exists)
- CanvasAudit.details_json (NOT metadata_json)
- HITLAction.context_snapshot (NOT metadata_json)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Set

from core.sandbox_policy import VT_PROVENANCE

logger = logging.getLogger(__name__)

# Sensitivity levels in ascending order of severity.
SENSITIVITY_ORDER = ("public", "internal", "confidential", "restricted")
_SENSITIVITY_RANK = {label: i for i, label in enumerate(SENSITIVITY_ORDER)}


# Keyword -> sensitivity mapping for explicit classification. Matched as
# whole-word, case-insensitive substrings.
_EXPLICIT_KEYWORDS: Dict[str, str] = {
    "public": "public",
    "internal": "internal",
    "confidential": "confidential",
    "restricted": "restricted",
}

# PII / secret patterns -> always restricted.
_PII_PATTERNS = [
    # Email address
    re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    # US phone numbers (with separators)
    re.compile(r"\b\d{3}[-.)]\s?\d{3}[-.]\d{4}\b"),
    # IPv4 address (octets 0-255)
    re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
    # SSN xxx-xx-xxxx
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # Stripe-style API keys
    re.compile(r"\bsk-(?:live|test)-[a-zA-Z0-9]{16,}\b"),
    # AWS access keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Generic long hex/base64 secrets (40+ chars) — conservative
    re.compile(r"\b(?:password|secret|api[_-]?key|token)\s*[:=]\s*[\w\-]{20,}\b", re.IGNORECASE),
]

# Credit-card-shaped digit runs (13-16 digits, optional separators). Matched
# separately and gated on the Luhn checksum so arbitrary order numbers,
# timestamps, and serials are not misclassified as payment cards.
_CC_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){12,15}\d\b")


def _luhn_valid(digits: str) -> bool:
    """Standard ISO/IEC 7812 Luhn checksum over a digit string."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _is_credit_card(text: str) -> bool:
    for match in _CC_CANDIDATE_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if 13 <= len(digits) <= 16 and _luhn_valid(digits):
            return True
    return False


def classify_sensitivity(text: str) -> str:
    """Classify a text blob's sensitivity.

    Order of precedence (highest wins):
      1. PII / secret pattern match -> ``restricted``
      2. Explicit sensitivity keyword -> that label (highest if multiple)
      3. Default -> ``internal``

    Args:
        text: the content to classify.

    Returns:
        One of ``public``/``internal``/``confidential``/``restricted``.
    """
    if not text:
        return "internal"

    # 1. PII / secrets -> restricted. Credit cards first (Luhn-validated so
    # numeric identifiers do not trip the classifier).
    if _is_credit_card(text):
        return "restricted"
    for pattern in _PII_PATTERNS:
        if pattern.search(text):
            return "restricted"

    lowered = text.lower()
    # 2. Explicit keywords (highest wins).
    found_rank = -1
    found_label = None
    for keyword, label in _EXPLICIT_KEYWORDS.items():
        if keyword in lowered:
            r = _SENSITIVITY_RANK[label]
            if r > found_rank:
                found_rank = r
                found_label = label
    if found_label is not None:
        return found_label

    # 3. Default.
    return "internal"


def higher_sensitivity(a: str, b: str) -> str:
    """Return the more sensitive of two labels."""
    return a if _SENSITIVITY_RANK.get(a, 1) >= _SENSITIVITY_RANK.get(b, 1) else b


class DataTaintTracker:
    """Per-run tracker of observed sensitivity labels.

    A tracker is cheap and per-run; it accumulates the set of sensitivity labels
    an agent observed (from document reads, canvas reads, tool outputs) and
    decides whether an outbound action is safe given what was observed.
    """

    def __init__(self, run_id: Optional[str] = None) -> None:
        self.run_id = run_id
        self.observed_labels: Set[str] = set()
        # Sources that triggered each label, for audit.
        self._sources: Dict[str, Set[str]] = {}

    def observe(self, content: Any, source: Optional[str] = None) -> str:
        """Classify ``content`` and merge its label into the observed set.

        Args:
            content: text (or object stringified) to classify.
            source: an optional provenance id (doc id, canvas id) for audit.

        Returns:
            The sensitivity label that was observed.
        """
        text = content if isinstance(content, str) else str(content or "")
        label = classify_sensitivity(text)
        self.observed_labels.add(label)
        if source:
            self._sources.setdefault(label, set()).add(source)
        return label

    def max_observed(self) -> str:
        """Return the highest-sensitivity label observed, or 'public' if empty."""
        if not self.observed_labels:
            return "public"
        return max(self.observed_labels, key=lambda l: _SENSITIVITY_RANK.get(l, 0))

    def check_outbound(
        self,
        destination: str = "external",
        service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Decide whether an outbound action is safe given observed labels.

        Policy: if ``restricted`` (or ``confidential``) data was observed AND the
        destination is external, block (the gatekeeper P3 escalates to HITL).
        Internal destinations are always allowed.

        Returns:
            ``{"allowed": bool, "violation_type"?: VT_PROVENANCE, "reason"?: str}``
        """
        destination = (destination or "external").strip().lower()
        if destination == "internal":
            return {"allowed": True}

        sensitive = {"restricted", "confidential"} & self.observed_labels
        if sensitive:
            worst = max(sensitive, key=lambda l: _SENSITIVITY_RANK[l])
            return {
                "allowed": False,
                "violation_type": VT_PROVENANCE,
                "reason": (
                    f"Outbound action blocked: {worst}-sensitivity data observed "
                    f"this run cannot be sent to external destination "
                    f"{service or 'unknown'}"
                ),
                "max_observed": worst,
            }
        return {"allowed": True}

    def to_metadata(self) -> Dict[str, Any]:
        """Serialize the run's observed state for stamping into a JSON column."""
        return {
            "observed_labels": sorted(self.observed_labels),
            "max_observed": self.max_observed(),
            "sources": {k: sorted(v) for k, v in self._sources.items()},
            "run_id": self.run_id,
        }


# Classification sample cap — prompts can be huge; PII/secrets relevant to an
# outbound decision are overwhelmingly near the head (instructions, pasted
# credentials). Keeps the per-call regex cost bounded.
_PROMPT_SAMPLE_CHARS = 20000


def assess_prompt_outbound(
    text: str, provider_id: str, model: str
) -> Optional[Dict[str, Any]]:
    """Assess an outbound LLM prompt against the P4 sensitivity policy.

    The prompt IS the exfil payload on the LLM path: unlike integration calls,
    the full text leaves for a third-party processor. This checks the head of
    the prompt with :func:`classify_sensitivity` and flags only
    ``restricted`` classifications (PII / credential patterns or explicit
    "restricted" marking) — ordinary ``confidential`` business text is allowed
    so normal agent work is never disrupted.

    Returns:
        ``None`` when the prompt may proceed; otherwise a decision dict in the
        same shape as :meth:`DataTaintTracker.check_outbound`.
    """
    if not text:
        return None
    try:
        label = classify_sensitivity(text[:_PROMPT_SAMPLE_CHARS])
    except Exception:  # classifier must never break dispatch
        return None
    if label == "restricted":
        return {
            "allowed": False,
            "violation_type": VT_PROVENANCE,
            "reason": (
                f"Prompt classified restricted-sensitivity (potential PII or "
                f"secrets) heading to external LLM {provider_id}/{model}"
            ),
            "max_observed": "restricted",
        }
    return None
