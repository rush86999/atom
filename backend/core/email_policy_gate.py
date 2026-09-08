"""Email send policy gate — deterministic, LLM-free enforcement at the send boundary.

Level B email rules. Unlike the taught-lesson prompts (Level A, which ask the
model to behave), this module BLOCKS a send/draft call that violates a rule,
with a machine-readable reason the agent can correct against. No model call:
every check runs on the tool-call arguments + content alone (a DB-backed
inventory/customer phase can strengthen rules 3-5 once those tables are
seeded).

Rules enforced here:

1. ``reply_without_thread`` (same-thread rule) — a reply-shaped send (subject
   with a Re:/Fwd:-style prefix) MUST carry a thread linkage
   (``thread_id`` / ``conversation_id`` / ``reply_to_message_id`` /
   ``message_id``) taken from the search result. A standalone NEW email (no
   reply prefix, no linkage) passes — not every send is a reply.

2. ``unverified_price`` (price rule) — a body that quotes a currency amount
   MUST declare ``price_verified=true`` (optionally with ``price_source``).

3. ``quote_without_item`` (specs rule) — a price-bearing reply MUST name the
   item being quoted (``item_model``). Quoting a price without an item means
   the agent assumed a machine the customer never specified — when the
   original request lacks model/quantity/condition, the correct move is to
   ASK for the missing details, not to invent an item.

4. ``unavailable_without_alternatives`` (alternatives rule) — a body telling
   the customer a machine is NOT available MUST offer same-category
   alternatives (``alternatives`` param, list or text). "No" without options
   violates the lesson; if stock is genuinely unknown the reply should say it
   will check, not flatly refuse.

5. ``new_customer_without_intro`` (intro rule) — when the agent declares
   ``customer_is_new=true``, the reply MUST introduce the company: the
   ``company_name`` param is required and must actually appear in the body
   (substring-verified), so the intro is present in the outbound text, not
   just claimed.

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
# ("SR48P", "5000 rpm") never trigger the price rules.
_PRICE_CLAIM = re.compile(
    r"(?<![A-Za-z0-9])(?:US\$|USD|INR|CAD|AUD|EUR|₹|Rs\.?|€|£|\$)\s?"
    r"[0-9][0-9,]*(?:\.[0-9]{1,2})?",
    re.IGNORECASE,
)

# Phrases that tell the customer a requested machine is not available.
_UNAVAILABLE_PHRASE = re.compile(
    r"(?i)(not available|no longer (?:available|stocked|carried)|"
    r"(?:do|does|don't|doesn't) not? (?:have|carry|stock)|out of stock|"
    r"unavailable|cannot supply|can't supply)"
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


def _flag_is_true(params: Dict[str, Any], key: str) -> bool:
    raw = params.get(key)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() == "true"


def _has_alternatives(params: Dict[str, Any]) -> bool:
    alts = params.get("alternatives")
    if isinstance(alts, (list, tuple)):
        return len([a for a in alts if str(a or "").strip()]) > 0
    return bool(str(alts or "").strip())


def check_send_message(params: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return the list of policy violations for an email send/draft call.

    ``params`` mirrors the tool-call arguments (to/subject/body/content,
    thread_id/conversation_id/reply_to_message_id/message_id,
    price_verified/price_source, item_model, alternatives,
    customer_is_new, company_name). Empty list = allowed.
    """
    subject = str(params.get("subject") or "")
    body = str(params.get("body") or params.get("content") or "")
    body_lower = body.lower()
    violations: List[Dict[str, str]] = []

    # 1. Same-thread rule.
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

    price_claimed = bool(_PRICE_CLAIM.search(body))

    # 2. Price rule: never quote an unverified price.
    if price_claimed and not _price_declared_verified(params):
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

    # 3. Specs rule: a price-bearing reply must name the item being quoted.
    if price_claimed and not str(params.get("item_model") or "").strip():
        violations.append({
            "code": "quote_without_item",
            "rule": "missing_details",
            "reason": (
                "Body quotes a price but no item_model is given. A quote must name "
                "the machine (model number). If the customer's request lacks the "
                "model/quantity/condition, ASK for the missing details instead of "
                "assuming an item."
            ),
            "fix": "pass item_model (or ask the customer for the missing details first)",
        })

    # 4. Alternatives rule: "not available" must come with options.
    if _UNAVAILABLE_PHRASE.search(body) and not _has_alternatives(params):
        violations.append({
            "code": "unavailable_without_alternatives",
            "rule": "offer_alternatives",
            "reason": (
                "Body says the requested machine is not available but no alternatives "
                "are offered. Suggest same-category machines (other brands/series) "
                "instead of replying no; if stock is unknown, say you will check."
            ),
            "fix": "repass with alternatives=[same-category machines] or check stock first",
        })

    # 5. Intro rule: new customers get a company introduction in the body.
    if _flag_is_true(params, "customer_is_new"):
        company = str(params.get("company_name") or "").strip()
        if not company:
            violations.append({
                "code": "new_customer_without_intro",
                "rule": "customer_intro",
                "reason": (
                    "customer_is_new=true but no company_name is given. For new "
                    "customers, introduce the company briefly, confirm the machine, "
                    "give the verified price, and invite follow-up."
                ),
                "fix": "pass company_name used in the intro",
            })
        elif company.lower() not in body_lower:
            violations.append({
                "code": "new_customer_without_intro",
                "rule": "customer_intro",
                "reason": (
                    f"customer_is_new=true but the body does not mention the company "
                    f"({company!r}). Introduce the company briefly in the reply."
                ),
                "fix": "include the company intro in the body text",
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
