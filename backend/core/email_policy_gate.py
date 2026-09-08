"""Email send policy gate — deterministic, LLM-free business-quality email rules.

RELATIONSHIP TO core/email_policy.py (read before extending either):

  core/email_policy.py is the SAFETY gate (BLOCK/APPROVE/ALLOW) — recipient
  egress allowlist, content sensitivity/taint, rate caps — wired at the
  dispatch/HITL layer (mcp_service send_email, chat_orchestrator,
  canvas_email_service, email_agent). THIS module is the BUSINESS-QUALITY
  gate — the taught sales rules (same-thread, verified price, specs,
  alternatives, customer intro) — wired at the universal-service transport
  boundary. Both are deterministic and both must pass for an agent send to
  leave the system: safety first (dispatch layer), then business quality
  (transport layer). They intentionally do NOT share a module: safety policy
  is per-install security data; these business rules are the seller's quality
  contract. If you add a rule here, ask first whether it is a safety rule
  (belongs in core/email_policy.py) or a business-quality rule (here).

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

5b. ``customer_already_known`` (intro rule, data-backed) — declaring
   ``customer_is_new=true`` for a recipient already in the customer records
   is contradicted by data (see core.email_policy_data).

Kill switch / scoping (repo convention — every policy layer ships an ATOM_*
escape hatch, see CLAUDE.md settings-catalog convention):
  - ``ATOM_EMAIL_SEND_POLICY_ENABLED=false`` disables the whole gate
  - ``ATOM_EMAIL_SEND_POLICY_RULES="code1,code2"`` limits enforcement to
    those violation codes (see ``filter_violations``). Unset = all rules.

Safety property: the *hook* in the integration layer is fail-open on gate
errors (a gate bug must never block a real send). These pure checks
themselves fail closed — a violation returns a blocked payload.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

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


# --- Kill switch + rule scoping -------------------------------------------
# Read per call (not at import) so operators/tests can toggle live.


def is_policy_enabled() -> bool:
    """Master switch: ATOM_EMAIL_SEND_POLICY_ENABLED=false disables the gate.
    Unset (or anything else) leaves it on — default-on, disable-able."""
    return os.getenv("ATOM_EMAIL_SEND_POLICY_ENABLED", "true").strip().lower() != "false"


def active_rule_codes() -> Optional[set]:
    """Rule scoping: ATOM_EMAIL_SEND_POLICY_RULES="code1,code2" limits
    enforcement to those codes; unset/empty => all rules active (None)."""
    raw = os.getenv("ATOM_EMAIL_SEND_POLICY_RULES", "").strip()
    if not raw:
        return None
    return {c.strip() for c in raw.split(",") if c.strip()}


def filter_violations(
    violations: List[Dict[str, str]],
    rule_codes: Optional[set] = None,
) -> List[Dict[str, str]]:
    """Keep only violations whose code is in ``rule_codes`` (None = all)."""
    if not violations:
        return []
    if not rule_codes:
        return violations
    return [v for v in violations if v.get("code") in rule_codes]

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


def check_send_message(
    params: Dict[str, Any],
    catalog: Any = (),
    known_customers: Any = (),
) -> List[Dict[str, str]]:
    """Return the list of policy violations for an email send/draft call.

    ``params`` mirrors the tool-call arguments (to/subject/body/content,
    thread_id/conversation_id/reply_to_message_id/message_id,
    price_verified/price_source, item_model, alternatives,
    customer_is_new, company_name). Empty list = allowed.

    ``catalog`` / ``known_customers`` are OPTIONAL data-backed context from
    the workspace (see core.email_policy_data):
    - catalog: iterable of catalogued machine model ids. When non-empty, a
      stated alternative must actually exist in the catalog (alternatives
      rule becomes DB-verified instead of self-reported). Empty catalog
      keeps the param-contract behavior.
    - known_customers: iterable of known customer emails. When a send
      declares customer_is_new=true for a recipient that is ALREADY in the
      customer table, the flag is contradicted by data and the send is
      blocked (intro is not needed for existing customers).
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
    unavailable_claimed = bool(_UNAVAILABLE_PHRASE.search(body))
    if unavailable_claimed and not _has_alternatives(params):
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

    # 4b. Alternatives DB-verify: when the workspace catalog is non-empty, a
    # stated alternative must actually exist in it (self-reported options are
    # no longer enough). Empty catalog = param-contract behavior preserved.
    catalog_ids = {str(c).strip().upper() for c in (catalog or ()) if str(c).strip()}
    if unavailable_claimed and catalog_ids and _has_alternatives(params):
        alts = params.get("alternatives")
        if isinstance(alts, str):
            alts = [alts]
        alt_ids = {str(a).strip().upper() for a in (alts or []) if str(a or "").strip()}
        if not (alt_ids & catalog_ids):
            violations.append({
                "code": "alternatives_not_in_catalog",
                "rule": "offer_alternatives",
                "reason": (
                    "Stated alternatives do not match any machine in the workspace "
                    "catalog. Offer real, same-category machines from the catalog "
                    "(check availability) instead of inventing options."
                ),
                "fix": "repass with alternatives that exist in the machine catalog",
            })

    # 5. Intro rule: new customers get a company introduction in the body.
    if _flag_is_true(params, "customer_is_new"):
        # 5b. Customer-status mismatch: an already-known recipient is NOT new
        # (data contradicts the agent's declaration).
        recipient = _first_recipient(params)
        known = {str(e).strip().lower() for e in (known_customers or ()) if str(e).strip()}
        if recipient and recipient in known:
            violations.append({
                "code": "customer_already_known",
                "rule": "customer_intro",
                "reason": (
                    f"{recipient} is already in the customer records — this is an "
                    "EXISTING customer, not new. No company intro is needed; "
                    "mark customer_is_new=false."
                ),
                "fix": "repass with customer_is_new=false (no intro required)",
            })
            return violations
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


def _first_recipient(params: Dict[str, Any]) -> str:
    """Normalized recipient email from to/to_recipients/recipients params."""
    for key in ("to", "to_recipients", "recipients"):
        raw = params.get(key)
        if isinstance(raw, (list, tuple)):
            for item in raw:
                if isinstance(item, dict):
                    item = item.get("emailAddress", {}).get("address") if isinstance(item.get("emailAddress"), dict) else item.get("address") or item.get("email")
                email = _extract_email(str(item or ""))
                if email:
                    return email
        elif raw:
            email = _extract_email(str(raw))
            if email:
                return email
    return ""


def _extract_email(text: str) -> str:
    """Pull the first bare email address out of arbitrary text."""
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")
    return m.group(0).lower() if m else ""


def blocked_payload(violations: List[Dict[str, str]]) -> Dict[str, Any]:
    """Standard blocked response shape for tool callers (agents + UI)."""
    return {
        "status": "blocked",
        "blocked": True,
        "policy": POLICY_NAME,
        "reason": " ".join(v["reason"] for v in violations),
        "violations": violations,
    }
