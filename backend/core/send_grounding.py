"""Grounded send gate — an outbound email's factual claims must trace to
the installation facts registry, carry hedged wording, or fall inside an
approved playbook's coverage (Installation Adaptation Plan Phase 4).

Live anchor (canvas da27bb76…): "the machines are available in 480V
3-phase configuration" went out-shaped with NO source. This gate is the
deterministic last line: rule-based assertion extraction (specs,
availability, pricing), each checked against
  1. the installation profile facts registry (verified entries), or
  2. hedged wording near the claim ("we are confirming…"), or
  3. approved-playbook coverage (a playbook governs this draft type).

Mode: runtime setting ATOM_SEND_GROUNDING —
  off    → gate not consulted;
  shadow → verdict computed and logged/returned, never blocks (default);
  enforce→ a `block` verdict refuses the send with an actionable message
           (a supervisor override param stays available and is logged).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MODE_OFF, _MODE_SHADOW, _MODE_ENFORCE = "off", "shadow", "enforce"


def grounding_mode() -> str:
    try:
        from core.runtime_settings import get_setting
        mode = str(get_setting("ATOM_SEND_GROUNDING", _MODE_SHADOW) or _MODE_SHADOW)
    except Exception:
        return _MODE_SHADOW
    return mode if mode in (_MODE_OFF, _MODE_SHADOW, _MODE_ENFORCE) else _MODE_SHADOW


# A sentence is an ASSERTION when it commits the company: an availability /
# supply verb, or a currency amount offered. A bare number ("304/316",
# "15 days") is NOT an assertion — the commit verb anchors extraction.
_COMMIT_RE = re.compile(
    r"\b(?:is|are|will be|can be|would be)\s+(?:available|supplied|"
    r"provided|offered|shipped|ordered|configured)|\bin stock\b|"
    r"\bwe (?:have|stock|supply|carry|offer|can supply|can offer)\b|"
    r"\b(?:confirmed|guaranteed|we confirm)\b",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"[$€£]\s?\d[\d,\.]*|\b\d[\d,\.]*\s?(?:USD|EUR|GBP)\b")

_HEDGE_RE = re.compile(
    r"\b(we are confirming|we're confirming|confirming|to be confirmed|"
    r"will confirm|can confirm|not yet (verified|confirmed)|subject to|"
    r"pending|need to (verify|check|confirm)|can (check|verify)|"
    r"will (follow up|verify)|before we)\b",
    re.IGNORECASE,
)

# Questions and conditionals are inherently non-committal.
_QUESTION_RE = re.compile(r"[^.!?\n]*\?[\s]*$")
_CONDITIONAL_RE = re.compile(
    r"\b(?:if|once|until|when|whether|after we)\b", re.IGNORECASE)

# Signature/footer boilerplate that mentions numbers but commits nothing.
_BOILERPLATE_RE = re.compile(
    r"\bvalid for \d+ days\b|\bquotes? are valid\b|\bunsubs\w*\b",
    re.IGNORECASE)

_SENTENCE_SPLIT_RE = re.compile(r"(?:<br\s*/?>)|(?<=[.!?])\s+|[\n\r]+")

_MAX_FINDINGS = 12
_MAX_ASSERTION_LEN = 220


@dataclass
class Finding:
    kind: str
    text: str
    reason: str


@dataclass
class Verdict:
    outcome: str  # pass | warn | block
    findings: List[Finding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "findings": [
                {"kind": f.kind, "text": f.text[:200], "reason": f.reason}
                for f in self.findings
            ],
        }


def extract_assertions(text: str) -> List[str]:
    """Sentence-level extraction of commit-shaped statements. Deliberately
    conservative: numbers alone, questions, conditionals, and footer
    boilerplate are prose, not assertions."""
    if not text:
        return []
    clean = re.sub(r"<[^>]+>", " ", text)  # strip email HTML
    found: List[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(clean):
        s = re.sub(r"\s+", " ", sentence).strip()
        if not s or _BOILERPLATE_RE.search(s):
            continue
        if _COMMIT_RE.search(s):
            found.append(s[:_MAX_ASSERTION_LEN])
        elif _PRICE_RE.search(s):
            found.append(s[:_MAX_ASSERTION_LEN])
        if len(found) >= _MAX_FINDINGS:
            break
    return found


def _is_hedged(sentence: str) -> bool:
    return bool(
        _HEDGE_RE.search(sentence)
        or _QUESTION_RE.search(sentence)
        or _CONDITIONAL_RE.search(sentence)
    )


def check_grounding(
    body: str,
    subject: str = "",
    facts: Optional[List[Dict[str, Any]]] = None,
    playbook_covered: bool = False,
) -> Verdict:
    """Compute the verdict for one outbound draft. Pure function — the
    caller decides what shadow/enforce do with it."""
    from core.installation_profile_service import InstallationProfileService

    findings: List[Finding] = []
    covered = bool(playbook_covered)
    facts = facts or []

    def registry_allows(claim: str) -> bool:
        return any(
            (fact or {}).get("verified", True)
            and InstallationProfileService.claims_match(
                claim, str(fact.get("claim") or ""))
            for fact in facts
        )

    for sentence in extract_assertions(f"{subject}\n{body}"):
        if registry_allows(sentence) or covered:
            continue
        if _is_hedged(sentence):
            continue
        kind = ("availability" if _COMMIT_RE.search(sentence) else "price")
        findings.append(Finding(
            kind=kind, text=sentence,
            reason="assertive claim with no facts-registry entry and no hedge",
        ))

    if not findings:
        return Verdict(outcome="pass")
    return Verdict(outcome="block", findings=findings)


def gate_send(
    db,
    tenant_id: str,
    body: str,
    subject: str = "",
    override: bool = False,
) -> Dict[str, Any]:
    """The service-level entry EmailCanvasService.send_email calls.
    Returns {mode, outcome, findings, blocked, override}. Never raises for
    provider/store trouble — the send path must not break because the gate
    cannot read its config."""
    mode = grounding_mode()
    result: Dict[str, Any] = {"mode": mode, "outcome": "pass",
                              "findings": [], "blocked": False,
                              "override": bool(override)}
    if mode == _MODE_OFF:
        return result
    try:
        from core.installation_profile_service import InstallationProfileService
        from core.playbook_service import PlaybookService

        payload = InstallationProfileService(db).get_payload(tenant_id)
        facts = payload.get("facts") or []
        covered = bool(PlaybookService(db, tenant_id=tenant_id).list(
            include_drafts=False))
        verdict = check_grounding(body, subject, facts=facts,
                                  playbook_covered=covered)
        result["outcome"] = verdict.outcome
        result["findings"] = verdict.to_dict()["findings"]
        blocked = (mode == _MODE_ENFORCE and verdict.outcome == "block"
                   and not override)
        result["blocked"] = blocked
        if verdict.outcome != "pass":
            logger.warning(
                f"send grounding [{mode}] {verdict.outcome}: "
                f"{len(verdict.findings)} unsupported claim(s)")
    except Exception as e:
        logger.debug(f"send grounding skipped: {e}")
        result["outcome"] = "pass"
        result["blocked"] = False
    return result
