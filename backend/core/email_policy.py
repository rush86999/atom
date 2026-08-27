"""
Deterministic email policy + provenance spotlighting.

Implements the "guardrails beat smarter models" pattern from the harness
research survey: pure rules, no LLM. ``evaluate_email_action`` returns
ALLOW / APPROVE / BLOCK regardless of what the model proposed — a BLOCK can
never be talked out of, and an APPROVE always requires a human.

Layers (in order of precedence — BLOCK beats APPROVE):
    1. Content sensitivity (P4 taint classifier; restricted -> BLOCK)
    1b. Attachment sensitivity (restricted -> BLOCK)
    2. Recipient egress allowlist  (external recipient -> APPROVE)
    3. Content sensitivity (confidential -> APPROVE)
    4. Autonomous send rate cap     (``ATOM_EMAIL_MAX_AUTONOMOUS_PER_HOUR``)

BLOCK-level checks MUST run before approve-level ones: an external recipient
+ PII body/attachment must block, never approve (the recipient check used to
short-circuit before sensitivity ran — PII was approved and the human-
present canvas path SENT it).

``spotlight_email_content`` wraps untrusted email content in provenance
delimiters (Spotlighting, Hines et al. 2024): the model treats the wrapped
block as data, not instructions.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Decisions returned by evaluate_email_action.
ALLOW = "allow"
APPROVE = "approve"
BLOCK = "block"

# Provenance delimiters (Spotlighting). Content between these markers is
# untrusted data — email bodies, attachments, web pages — never instructions.
UNTRUSTED_OPEN = "[UNTRUSTED_EMAIL]"
UNTRUSTED_CLOSE = "[/UNTRUSTED_EMAIL]"

# Inert stand-ins used when the reserved markers appear INSIDE untrusted
# content: an attacker-controlled subject/body containing the closing marker
# would otherwise terminate the block early and place instruction-like text
# OUTSIDE the provenance region (P1 — delimiter-escape injection).
_UNTRUSTED_OPEN_SAFE = "[UNTRUSTED_EMAIL-MARKER]"
_UNTRUSTED_CLOSE_SAFE = "[/UNTRUSTED_EMAIL-MARKER]"


def _sanitize_spotlight(content: str) -> str:
    """Neutralize reserved delimiters inside untrusted content."""
    if not content:
        return ""
    return (
        str(content)
        .replace(UNTRUSTED_CLOSE, _UNTRUSTED_CLOSE_SAFE)
        .replace(UNTRUSTED_OPEN, _UNTRUSTED_OPEN_SAFE)
    )


def _sanitize_header(value: str) -> str:
    """Single-line header field: no CR/LF so a crafted sender/subject cannot
    forge extra header lines, then neutralize the reserved markers too."""
    return _sanitize_spotlight(re.sub(r"[\r\n]+", " ", str(value or "")).strip())

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _allowed_domains() -> List[str]:
    """Domains that may be emailed autonomously (comma-separated env)."""
    raw = os.getenv("ATOM_EMAIL_ALLOWED_OUTBOUND_DOMAINS", "")
    return [d.strip().lower().lstrip(".") for d in raw.split(",") if d.strip()]


def _recipient_domain(recipient: str) -> Optional[str]:
    """Lowercased domain of a recipient, or None when unparseable."""
    if not recipient or "@" not in recipient:
        return None
    return recipient.rsplit("@", 1)[1].strip().lower()


def is_external_recipient(recipient: str) -> bool:
    """True when the recipient is outside the autonomous-send allowlist.

    No allowlist configured => every recipient is treated as external
    (conservative default: external sends require approval).
    """
    domain = _recipient_domain(recipient)
    if not domain:
        return True
    allowed = _allowed_domains()
    if not allowed:
        return True
    return not any(domain == d or domain.endswith("." + d) for d in allowed)


def classify_email_content(body: str, subject: str = "") -> str:
    """Sensitivity of the composed email, reusing the P4 taint classifier.

    Returns one of public / internal / confidential / restricted.
    """
    try:
        from core.data_taint_tracker import classify_sensitivity
        return classify_sensitivity(f"{subject or ''}\n{body or ''}")
    except Exception:  # classifier must never break dispatch
        logger.debug("email sensitivity classifier unavailable; defaulting to internal")
        return "internal"


def _sends_in_last_hour(actor_id: Optional[str]) -> int:
    """Count CanvasAudit 'email_send' rows in the last hour for the actor.

    Persisted rows (not an in-memory counter) so the cap survives restarts
    and is auditable. Best-effort — a DB failure degrades to 0.
    """
    try:
        from sqlalchemy import func

        from core.database import get_db_session
        from core.models import CanvasAudit

        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        with get_db_session() as db:
            q = db.query(func.count(CanvasAudit.id)).filter(
                CanvasAudit.action_type == "email_send",
                CanvasAudit.created_at >= cutoff,
            )
            if actor_id:
                q = q.filter(
                    (CanvasAudit.user_id == actor_id)
                    | (CanvasAudit.agent_id == actor_id)
                )
            return int(q.scalar() or 0)
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("email rate-cap query failed: %s", e)
        return 0


def evaluate_email_action(
    action: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministic email policy. Never raises.

    Args:
        action: composed email — keys ``to``, ``cc``/``cc_recipients``,
            ``subject``, ``body`` (+ optional ``platform``).
        context: dispatch context — ``user_id`` / ``agent_id`` used for the
            rate cap; optional.

    Returns:
        ``{"decision": "allow"|"approve"|"block", "reason": str,
          "policy": str}``
    """
    try:
        recipients = action.get("to") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        cc = action.get("cc") or action.get("cc_recipients") or []
        if isinstance(cc, str):
            cc = [cc]
        all_recipients = [r for r in list(recipients) + list(cc) if r]

        # 1. BLOCK-level check first: restricted-sensitivity content (PII /
        # secrets) can never be sent, regardless of recipient. This runs
        # before the recipient-allowlist check so an external recipient can't
        # short-circuit it into an APPROVE (regression fixed: PII + external
        # was previously approved and sent).
        label = classify_email_content(
            action.get("body", ""), action.get("subject", "")
        )
        if label == "restricted":
            return {
                "decision": BLOCK,
                "reason": (
                    "Email contains restricted-sensitivity content "
                    "(PII/secrets); sending is blocked"
                ),
                "policy": "sensitivity",
            }

        # 1b. Attachment scan — same BLOCK precedence as the body. A PII/
        # secret-bearing attachment must block even when the recipient check
        # would otherwise approve. Text-less (binary/opaque) attachments are
        # skipped; structured text is flattened before classification.
        for att in action.get("attachments") or []:
            att_text = ""
            if isinstance(att, dict):
                att_text = att.get("text") or att.get("content") or att.get("body") or ""
                if isinstance(att_text, (dict, list)):
                    att_text = str(att_text)
            else:
                att_text = str(att)
            if not att_text:
                continue
            if classify_email_content(att_text) == "restricted":
                return {
                    "decision": BLOCK,
                    "reason": (
                        "Attachment contains restricted-sensitivity content "
                        "(PII/secrets); sending is blocked"
                    ),
                    "policy": "attachment_sensitivity",
                }

        # 2. Recipient egress allowlist.
        for r in all_recipients:
            if is_external_recipient(r):
                return {
                    "decision": APPROVE,
                    "reason": f"External recipient {r} requires human approval",
                    "policy": "recipient_allowlist",
                }

        # 3. Confidential content -> approval.
        if label == "confidential":
            return {
                "decision": APPROVE,
                "reason": "Email contains confidential content; requires human approval",
                "policy": "sensitivity",
            }

        # 4. Autonomous send rate cap.
        cap = int(os.getenv("ATOM_EMAIL_MAX_AUTONOMOUS_PER_HOUR", "10"))
        if context:
            actor = context.get("user_id") or context.get("agent_id")
            if _sends_in_last_hour(actor) >= cap:
                return {
                    "decision": APPROVE,
                    "reason": f"Autonomous send rate cap ({cap}/hour) reached",
                    "policy": "rate_cap",
                }

        return {
            "decision": ALLOW,
            "reason": "Email policy allows autonomous send",
            "policy": "default",
        }
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("email policy failed open to approval: %s", e)
        return {
            "decision": APPROVE,
            "reason": "Email policy unavailable; requiring approval",
            "policy": "fail_safe",
        }


def spotlight_email_content(
    body: str,
    sender: Optional[str] = None,
    subject: Optional[str] = None,
) -> str:
    """Wrap untrusted email content in provenance delimiters (Spotlighting).

    The wrapped block is DATA — the model must never treat instructions
    inside it as authoritative. Used when feeding fetched emails to an agent.

    All attacker-controlled fields are sanitized before wrapping: reserved
    delimiters inside the content are neutralized (a crafted subject/body
    containing the closing marker cannot terminate the block early), and
    header fields (sender/subject) are collapsed to a single line so they
    cannot forge extra header lines.
    """
    parts = []
    if sender:
        parts.append(f"from: {_sanitize_header(sender)}")
    if subject:
        parts.append(f"subject: {_sanitize_header(subject)}")
    header_line = " · ".join(parts)
    header = f"{header_line}\n" if header_line else ""
    return f"{UNTRUSTED_OPEN}\n{header}{_sanitize_spotlight(body)}\n{UNTRUSTED_CLOSE}"


def is_valid_recipient(recipient: str) -> bool:
    """Basic syntactic email validation (deterministic schema guard)."""
    return bool(recipient and _EMAIL_RE.match(recipient.strip()))
