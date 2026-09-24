"""Deterministic feedback routing before any learning or configuration write."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

KIND_FACTUAL = "factual_correction"
KIND_PREFERENCE = "preference"
KIND_EXECUTION = "execution_failure"
KIND_STRATEGY = "strategy_improvement"
KIND_PERMISSION = "permission_instruction"
KIND_SOURCE = "source_content"
KIND_UNKNOWN = "unknown"

KINDS = (
    KIND_FACTUAL,
    KIND_PREFERENCE,
    KIND_EXECUTION,
    KIND_STRATEGY,
    KIND_PERMISSION,
    KIND_SOURCE,
    KIND_UNKNOWN,
)

_FACTUAL_RE = re.compile(
    r"\b(?:that'?s\s+(?:wrong|incorrect|not\s+right)|"
    r"(?:the\s+)?(?:answer|value|price|total|amount|date|number|figure|row|"
    r"column|file|source)s?\s+(?:is|was|are|were)\s+(?:wrong|incorrect|"
    r"not\s+right|out\s+of\s+date)|actually\s*[:,]|correction\s*:|"
    r"should\s+be\s+[^.!?]+|wrong\s+(?:file|sheet|row|column|source|version|"
    r"value|answer)|not\s+the\s+right\s+(?:file|sheet|row|value|answer))\b",
    re.IGNORECASE,
)
_PREFERENCE_RE = re.compile(
    r"\b(?:i\s+(?:prefer|like|want|always|never)|"
    r"please\s+(?:always|never|use|format|answer)|from\s+now\s+on|"
    r"in\s+(?:the\s+)?future|shorter|more\s+concise|as\s+a\s+table|"
    r"in\s+table\s+form|bullet\s+points|don'?t\s+(?:use|add|include|show))\b",
    re.IGNORECASE,
)
_EXECUTION_RE = re.compile(
    r"\b(?:timed?\s*out|timeout|took\s+(?:too\s+long|forever)|failed|"
    r"error|crashed|didn'?t\s+(?:work|run|finish|load)|never\s+(?:ran|"
    r"finished|returned)|too\s+slow|unavailable|not\s+(?:loading|responding))\b",
    re.IGNORECASE,
)
_STRATEGY_RE = re.compile(
    r"\b(?:next\s+time|you\s+should\s+(?:also\s+)?(?:check|search|try|look|"
    r"verify|confirm)|also\s+(?:check|search|look|verify)|when\s+(?:i|the\s+"
    r"user)\s+(?:confirm|say)|remember\s+to|it\s+helps\s+to|try\s+"
    r"(?:searching|looking|checking)\s+(?:the|in))\b",
    re.IGNORECASE,
)
_PERMISSION_RE = re.compile(
    r"\b(?:you'?re\s+(?:not\s+)?allowed|don'?t\s+(?:ever|never)\s+"
    r"(?:search|read|open|access|send)|ask\s+me\s+before|only\s+"
    r"(?:use|search|read)|never\s+(?:search|read|open|access|send)|"
    r"permission|approve|authorization)\b",
    re.IGNORECASE,
)
_QUOTE_RE = re.compile(r"[\"“‘][^\"”’\n]{8,300}[\"”’]")


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _from_retrieved_source(text: str, evidence_text: str) -> bool:
    if not text or not evidence_text:
        return False
    normalised_text = _normalise(text)
    normalised_evidence = _normalise(evidence_text)
    if len(normalised_text) >= 8 and normalised_text in normalised_evidence:
        return True
    for quote in _QUOTE_RE.findall(text):
        inner = quote[1:-1].strip()
        if len(inner) >= 8 and _normalise(inner) in normalised_evidence:
            return True
    return False


def _destination(kind: str) -> str:
    return {
        KIND_FACTUAL: "knowledge_candidate",
        KIND_PREFERENCE: "user_configuration",
        KIND_EXECUTION: "reliability_evidence",
        KIND_STRATEGY: "lesson_candidate",
        KIND_PERMISSION: "authorization_review",
        KIND_SOURCE: "audit_only",
        KIND_UNKNOWN: "audit_only",
    }[kind]


def classify_feedback(
    text: str,
    *,
    label: Optional[str] = None,
    evidence_text: str = "",
    turn_had_failures: bool = False,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    channel: str = "chat",
) -> Dict[str, Any]:
    """Classify feedback and return its bounded learning destination."""
    value = str(text or "").strip()
    from_source = _from_retrieved_source(value, evidence_text)
    signals = {
        KIND_FACTUAL: bool(_FACTUAL_RE.search(value)),
        KIND_PREFERENCE: bool(_PREFERENCE_RE.search(value)),
        KIND_EXECUTION: bool(_EXECUTION_RE.search(value)),
        KIND_STRATEGY: bool(_STRATEGY_RE.search(value)),
        KIND_PERMISSION: bool(_PERMISSION_RE.search(value)),
    }

    if from_source:
        kind = KIND_SOURCE
    elif not value:
        kind = KIND_EXECUTION if turn_had_failures and label == "negative" else KIND_UNKNOWN
    else:
        order = (
            KIND_PERMISSION,
            KIND_FACTUAL,
            KIND_EXECUTION,
            KIND_STRATEGY,
            KIND_PREFERENCE,
        )
        kind = next((item for item in order if signals[item]), KIND_UNKNOWN)

    if kind == KIND_UNKNOWN and sum(signals.values()) > 1:
        kind = KIND_UNKNOWN

    confidence = 0.9 if kind != KIND_UNKNOWN and sum(signals.values()) == 1 else 0.4
    if kind == KIND_SOURCE:
        confidence = 0.95
    elif kind == KIND_PERMISSION and len(signals) > 1:
        confidence = 0.6

    destination = _destination(kind)
    learnable = kind == KIND_STRATEGY and not from_source
    return {
        "kind": kind,
        "confidence": confidence,
        "scope": "turn",
        "scope_dimensions": {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "channel": channel,
        },
        "signals": signals,
        "contradictory_signals": [
            item for item, hit in signals.items() if hit and item != kind
        ],
        "from_retrieved_source": from_source,
        "supporting_text": value[:500],
        "destination": destination,
        "learnable_as_instruction": learnable,
        "requires_review": kind in {
            KIND_FACTUAL,
            KIND_PERMISSION,
            KIND_STRATEGY,
            KIND_SOURCE,
            KIND_UNKNOWN,
        },
        "requires_verification": kind == KIND_FACTUAL,
        "requires_authorization": kind == KIND_PERMISSION,
    }
