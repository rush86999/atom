"""Email send policy gate — deterministic, LLM-free enforcement at the send boundary.

Level B (minimal) email rules. Unlike the taught-lesson prompts (Level A, which
ask the model to behave), this module BLOCKS a send/draft call that violates a
rule, with a machine-readable reason the agent can correct against. No model
call, no data dependency: every check runs on the tool-call arguments alone.

Rules enforced here:

1. ``reply_without_thread`` (same-thread rule) — a reply-shaped send (subject
   with a Re:/Fwd:-style prefix) MUST carry a thread linkage
   (``thread_id`` / ``conversation_id`` / ``reply_to_message_id`` /
   ``message_id``) taken from the search result. A standalone NEW email (no
   reply prefix, no linkage) passes — not every send is a reply.

2. ``unverified_price`` (price rule) — a body that quotes a currency amount
   MUST declare ``price_verified=true`` (optionally with ``price_source``).
   A price claim without a verified source is exactly the "never guess or
   invent a price" lesson, enforced structurally.

Safety property: the *hook* in the integration layer is fail-open on gate
errors (a gate bug must never block a real send). These pure checks
themselves fail closed — a violation returns a blocked payload.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

# Reply/fwd prefixes that mark a message as a reply to something earlier.
_REPLY_PREFIX = re.compile(r"^\s*(re|fwd|fw|aw|sv|antw|vs|答复|回复)\s*:", re.IGNORECASE)

# Currency marker + amount. The marker is required so bare model numbers
# ("SR48P", "5000 rpm") never trigger the price rule.
_PRICE_CLAIM = re.compile(
    r"(?<![A-Za-z0-9])(?:US\$|USD|INR|CAD|AUD|EUR|₹|Rs\.?|€|£|\$)\s?"
    r"[0-9][0-9,]*(?:\.[0-9]{1,2})?",
    re.IGNORECASE,
)

POLICY_NAME = "email_send_policy"

# Params that prove the send is anchored to an existing thread/conversation.
_THREAD_LINKAGE_KEYS = (
    "thread_id",
    "conversation_id",
    "reply_to_message_id",
    "message_id",
)


def _has_thread_linkage(params: Dict[str, Any]) -> bool:
    return any(params.get(k) for k in _THREAD_LINKAGE_KEYS)


def _is_reply_shaped(subject: str) -> bool:
    return bool(subject) and bool(_REPLY_PREFIX.match(subject))


def _price_declared_verified(params: Dict[str, Any]) -> bool:
    raw = params.get("price_verified")
    if isinstance(raw, bool):
        return raw
    # LLM tool callers often pass strings ("true"/"True") — tolerate them.
    return str(raw or "").strip().lower() == "true"


def check_send_message(params: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return the list of policy violations for an email send/draft call.

    ``params`` mirrors the tool-call arguments (to/subject/body/content,
    thread_id/conversation_id/reply_to_message_id/message_id,
    price_verified/price_source). Empty list = allowed.
    """
    subject = str(params.get("subject") or "")
    body = str(params.get("body") or params.get("content") or "")
    violations: List[Dict[str, str]] = []

    if not _has_thread_linkage(params) and _is_reply_shaped(subject):
        violations.append({
            "code": "reply_without_thread",
            "rule": "same_thread",
            "reason": (
                "Reply-shaped email (subject starts with Re:/Fwd:) has no thread "
                "linkage. Reply in the SAME thread: pass thread_id/conversation_id "
                "(or reply_to_message_id/message_id) from the search result instead "
                "of starting a new message."
            ),
            "fix": "repass with thread_id | conversation_id | reply_to_message_id from the search result",
        })

    if _PRICE_CLAIM.search(body) and not _price_declared_verified(params):
        violations.append({
            "code": "unverified_price",
            "rule": "price_verification",
            "reason": (
                "Body quotes a price but price_verified is not true. Verify the price "
                "from the price list or the customer's file first; never guess or "
                "invent a price."
            ),
            "fix": "verify the price, then repass with price_verified=true (+ price_source)",
        })

    return violations


def blocked_payload(violations: List[Dict[str, str]]) -> Dict[str, Any]:
    """Standard blocked response shape for tool callers (agents + UI)."""
    return {
        "status": "blocked",
        "blocked": True,
        "policy": POLICY_NAME,
        "reason": " ".join(v["reason"] for v in violations),
        "violations": violations,
    }
