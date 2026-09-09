"""Email send policy gate — deterministic, LLM-free send-boundary checks.

RELATIONSHIP TO core/email_policy.py (read before extending either):

  core/email_policy.py is the SAFETY gate (BLOCK/APPROVE/ALLOW) — recipient
  egress allowlist, content sensitivity/taint, rate caps — wired at the
  dispatch/HITL layer (mcp_service send_email, chat_orchestrator,
  canvas_email_service, email_agent). THIS module is the transport-level
  gate, wired at the universal-service send boundary. Both are deterministic
  and both must pass for an agent send to leave the system: safety first
  (dispatch layer), then transport hygiene (here). They intentionally do
  NOT share a module: safety policy is per-install security data; the
  checks here are properties of the email medium itself.

SCOPE — medium hygiene only. NO business rules, deliberately.

  The one rule enforced here is ``reply_without_thread``: a reply-shaped
  send (subject with a Re:/Fwd:-style prefix) must carry a thread linkage
  taken from the search result. It passes the swap-the-business test — a
  bakery, a law firm and a machine dealer all need agent replies to land
  in the customer's existing thread — so it is platform-level, the same
  way the safety gate's recipient mechanics are.

  An earlier revision of this module also enforced one business's sales
  rules (price verification, item specs, alternatives, customer intro).
  They were removed (PR #611 review, 2026-09-09) because they cannot be
  written correctly in code for a platform that serves any-category small
  businesses:

  - Even their authoring business prices more than one way — a
    consolidated price list AND manual calculation — so a single
    "price_verified=true" attestation shape was wrong for the very
    business it came from. It also verified nothing: the attestation
    comes from the same model that drafted the price.
  - Hardcoded business rules cannot follow a dynamic business process.
    This is the documented failure mode of hardcoded rules in general
    (Higson, "The Hidden Costs of Hardcoded Business Rules";
    Medeiros 2023, "The Hidden Cost of Hardcoded Pricing Rules") and the
    reason rules engines exist.

  Established practice for when business rules return (researched
  2026-09-09, per AGENTS.md #3):

  - Engine/data separation: Open Policy Agent (CNCF graduated) decouples
    policy decision-making from enforcement so policy owners read,
    write, version and distribute rules independently of application
    code. Business rules should arrive as per-workspace rule DATA, never
    as checks in core.
  - Pricing provenance is a binding, not a boolean: CPQ systems treat
    list-price vs manually-calculated prices as different approval
    conditions (e.g. Salesforce CPQ manual pricing overrides + Advanced
    Approvals keyed on variance from list) — configured per deployment,
    never one hardcoded rule shape for all pricing.

  Target home for business rules: per-workspace rule packs authored
  through the supervisor training loop (a rejected draft's correction
  becomes a candidate rule, consent-gated), evaluated by this module's
  machinery — trigger/param/data-binding primitives, not bespoke checks.
  Until that exists, this module enforces nothing business-specific and
  the platform ships no business vocabulary on the send_email tool.

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


def check_send_message(params: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return the list of policy violations for an email send/draft call.

    ``params`` mirrors the tool-call arguments (to/subject/body/content,
    thread_id/conversation_id/reply_to_message_id/message_id). Empty list =
    allowed. Business rules are out of scope by design — see the module
    docstring.
    """
    subject = str(params.get("subject") or "")
    violations: List[Dict[str, str]] = []

    # Same-thread rule (medium hygiene): a reply-shaped send must be
    # linked to the thread it replies to.
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
