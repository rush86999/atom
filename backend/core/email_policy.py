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


def _blocked_sender_domains() -> List[str]:
    """Inbound sender domains to reject (comma-separated env)."""
    raw = os.getenv("ATOM_EMAIL_BLOCKED_SENDER_DOMAINS", "")
    return [d.strip().lower().lstrip(".") for d in raw.split(",") if d.strip()]


_SENSITIVITY_POLICY_DEFAULTS: Dict[str, str] = {
    "restricted": BLOCK,
    "confidential": APPROVE,
}


def _sensitivity_policy() -> Dict[str, str]:
    """Label -> decision map, overridable via ATOM_EMAIL_SENSITIVITY_POLICY.

    JSON like ``{"restricted": "approve", "confidential": "block"}``.
    Invalid JSON / unknown values fall back to defaults; never raises.
    """
    raw = os.getenv("ATOM_EMAIL_SENSITIVITY_POLICY", "")
    if not raw:
        return dict(_SENSITIVITY_POLICY_DEFAULTS)
    try:
        import json as _json

        parsed = _json.loads(raw)
    except Exception:
        return dict(_SENSITIVITY_POLICY_DEFAULTS)
    if not isinstance(parsed, dict):
        return dict(_SENSITIVITY_POLICY_DEFAULTS)
    policy = dict(_SENSITIVITY_POLICY_DEFAULTS)
    for label, decision in parsed.items():
        if label in _SENSITIVITY_POLICY_DEFAULTS and decision in (ALLOW, APPROVE, BLOCK):
            policy[label] = decision
    return policy


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
    """Count successful sends (CanvasAudit 'email_send') in the last hour.

    Only action_type="email_send" rows count — blocked/failed attempts are
    recorded as "email_send_attempt" and don't consume quota. Persisted rows
    (not an in-memory counter) so the cap survives restarts and is auditable.
    Best-effort — a DB failure degrades to 0.
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
        # was previously approved and sent). The label -> decision map is
        # configurable via ATOM_EMAIL_SENSITIVITY_POLICY.
        sens_policy = _sensitivity_policy()
        label = classify_email_content(
            action.get("body", ""), action.get("subject", "")
        )
        if label in sens_policy and sens_policy[label] != ALLOW:
            decision = sens_policy[label]
            return {
                "decision": decision,
                "reason": (
                    f"Email contains {label}-sensitivity content "
                    f"(PII/secrets); sending is {decision}ed"
                ),
                "policy": "sensitivity",
            }

        # 1b. Attachment scan — same precedence as the body. A PII/secret-
        # bearing attachment must block even when the recipient check would
        # otherwise approve. Text-less (binary/opaque) attachments are
        # skipped; structured text is flattened before classification.
        attachment_block = sens_policy.get("restricted", BLOCK) == BLOCK
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
            if classify_email_content(att_text) == "restricted" and attachment_block:
                return {
                    "decision": BLOCK,
                    "reason": (
                        "Attachment contains restricted-sensitivity content "
                        "(PII/secrets); sending is blocked"
                    ),
                    "policy": "attachment_sensitivity",
                }

        # 1c. Threaded reply with no explicit recipients: the actual
        # recipients are derived from the existing thread at send time, so
        # the egress allowlist below cannot see them (and the thread's last
        # sender is attacker-influencable). Fail safe: require human
        # approval. Explicit recipients still fall through to the normal
        # allowlist checks.
        is_thread_reply = bool(
            action.get("thread_id")
            or action.get("conversation_id")
            or action.get("reply_to_message_id")
            or action.get("message_id")
        )
        if is_thread_reply and not all_recipients:
            return {
                "decision": APPROVE,
                "reason": (
                    "Threaded reply: recipients come from the existing "
                    "thread, which requires human approval"
                ),
                "policy": "thread_reply_recipients",
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
        if label == "confidential" and sens_policy.get("confidential", APPROVE) != ALLOW:
            return {
                "decision": sens_policy.get("confidential", APPROVE),
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


def spotlight_message_results(messages: Any) -> str:
    """Serialized fetched-email results wrapped in provenance delimiters.

    P1: when the agent retrieves a message via search_emails/get_message, the
    raw Outlook result must ride inside the untrusted delimiters (like the
    webhook subject) so attacker-authored content cannot steer triage, drafts
    or persisted output. Delimiters inside the content are sanitized.
    """
    if isinstance(messages, str):
        raw = messages
    else:
        try:
            import json as _json

            raw = _json.dumps(messages, default=str)
        except Exception:  # pragma: no cover - defensive
            raw = str(messages)
    return spotlight_email_content(raw)


def is_valid_recipient(recipient: str) -> bool:
    """Basic syntactic email validation (deterministic schema guard)."""
    return bool(recipient and _EMAIL_RE.match(recipient.strip()))


def is_blocked_sender_domain(domain: str) -> bool:
    """True when the inbound sender domain is on the denylist (or a subdomain)."""
    blocked = _blocked_sender_domains()
    if not blocked or not domain:
        return False
    d = domain.strip().lower()
    return any(d == b or d.endswith("." + b) for b in blocked)


def validate_sender(sender: str) -> bool:
    """Inbound sender gate (Phase-3 spoofing check).

    Requires a syntactically valid address and a domain that is not on the
    ``ATOM_EMAIL_BLOCKED_SENDER_DOMAINS`` denylist. Deterministic; never
    raises. Empty/invalid senders are rejected (fail closed).
    """
    try:
        if not sender or not is_valid_recipient(sender):
            return False
        domain = _recipient_domain(sender)
        if not domain or is_blocked_sender_domain(domain):
            return False
        return True
    except Exception:  # pragma: no cover - defensive
        return False


# ---------------------------------------------------------------------------
# Mixed-thread internal-quote guard
#
# Customer threads routinely carry internal legs (colleague notes in the same
# conversation). A reply that quotes text which exists ONLY on internal legs
# leaks internal discussion to the customer — the deterministic check: flag
# body passages that appear verbatim in internal-leg text and in NO external
# leg. Facts the customer already saw (prices quoted to them, their own
# questions) live on external legs too, so they never flag.

INTERNAL_QUOTE_MIN_WORDS = 6
# Targeted lower floors — deterministic, high-precision fragment kinds:
INTERNAL_QUOTE_NUMERIC_MIN_WORDS = 2   # fragments carrying a distinctive number ("hold at 13k")
INTERNAL_QUOTE_CAPS_MIN_WORDS = 4      # fragments with ALL-CAPS emphasis ("DO NOT QUOTE INTERNALLY")
INTERNAL_QUOTE_SHINGLE_WORDS = 8       # reworded/reordered fragments (3-gram overlap)
INTERNAL_QUOTE_SHINGLE_OVERLAP = 0.8
# Semantic tier. Calibrated 2026-09-04 on BAAI/bge-small-en-v1.5: internal vs
# paraphrase cosines 0.67-0.82, internal vs unrelated <=0.615 (n=4+16 real
# thread sentences). Threshold 0.66. Corroboration is deliberately strict:
# the pair must share a DISTINCTIVE NUMBER that appears nowhere in the
# customer-visible legs. Numbers are what internal discussion actually
# guards (pricing floors, discount caps), and published facts (the list
# price discussed internally, then quoted) carry numbers that ARE in the
# customer-visible blob — so legitimate internal incubation of customer
# answers never trips the tier, while "hold at 13k" paraphrases do.
INTERNAL_QUOTE_SEMANTIC_THRESHOLD = 0.66
INTERNAL_QUOTE_SEMANTIC_MIN_WORDS = 4
_MAX_EMBED_FRAGMENTS = 120
_MAX_EMBED_BODY_SENTENCES = 60

_MATCH_RANK = {"verbatim": 0, "numeric": 1, "caps": 2, "reworded": 3, "semantic": 4}


def _strip_email_markup(value: Any) -> str:
    """Whitespace-collapsed, lowercased email text with markup removed. Tags
    are stripped BEFORE entity-decoding so escaped text ("&lt;table&gt;") is
    never mistaken for real markup. Case is deliberately preserved OUT of
    this helper's contract — callers needing case must use
    ``_sentence_parts`` directly."""
    import html as _html

    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = _html.unescape(text)
    return " ".join(text.split()).lower()


def _sentence_parts(value: Any) -> List[str]:
    """Raw sentence parts of an email body: markup stripped, case preserved,
    split on newlines/sentence boundaries."""
    import html as _html

    text = re.sub(r"<[^>]+>", "\n", str(value or ""))
    text = _html.unescape(text)
    parts: List[str] = []
    for line in text.splitlines():
        parts.extend(re.split(r"(?<=[.!?])\s+", line))
    return [p for p in (part.strip() for part in parts) if p]


def _strong_number_token(token: str) -> bool:
    """A number distinctive enough to anchor a short fragment: has a digit,
    at least 2 chars — "13k", "25%", "$14,145.00", "10am" qualify; a lone
    "3" does not (too generic)."""
    token = token.strip("$€£(),")
    return len(token) >= 2 and any(ch.isdigit() for ch in token)


def _is_caps_token(token: str) -> bool:
    return len(token) >= 2 and token.isupper() and any(ch.isalpha() for ch in token)


def _internal_fragments(value: Any) -> List[Dict[str, Any]]:
    """Distinctive normalized fragments of an email body with the flags the
    tier floors need."""
    fragments: List[Dict[str, Any]] = []
    for part in _sentence_parts(value):
        norm = " ".join(part.split()).lower()
        tokens = norm.strip(" .;:,!?-\"'()").split()
        words = len(tokens)
        if not words:
            continue
        raw_tokens = part.split()
        fragments.append({
            "text": " ".join(tokens),
            "words": words,
            "numeric": any(_strong_number_token(t) for t in tokens),
            "caps": any(_is_caps_token(t) for t in raw_tokens),
        })
    return fragments


def _trigrams(tokens: List[str]) -> set:
    return {" ".join(tokens[i:i + 3]) for i in range(len(tokens) - 2)}


def _cosine(a: List[float], b: List[float]) -> float:
    try:
        import numpy as np

        va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        return float(np.dot(va, vb)) / denom if denom else 0.0
    except Exception:
        num = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        return num / (na * nb) if na and nb else 0.0


async def find_internal_quotes(
    body: str,
    internal_texts: List[str],
    external_texts: List[str],
    embed_fn: Optional[Any] = None,
) -> List[Dict[str, str]]:
    """Passages of ``body`` that restate internal-only thread text, never
    raised. Tiered, deterministic apart from the optional semantic tier:

    - ``verbatim``  sentence containment (floor: 6 words)
    - ``numeric``   short fragments anchored by a distinctive number (2 words)
    - ``caps``      short fragments carrying ALL-CAPS emphasis (4 words)
    - ``reworded``  >=8-word fragments whose 3-grams are >=80% present in the
      body (catches reordering and small edits)
    - ``semantic``  embedding cosine >= threshold AND the pair shares a
      distinctive number that appears nowhere in the customer-visible legs
      (when ``embed_fn`` is provided); embedder failures degrade to the
      lexical tiers only. Internal passages that were already published in
      substance — an earlier sent reply with high cosine — are exempt:
      internally-drafted customer answers are not leaks.

    Text appearing anywhere in the customer-visible legs (external senders,
    our own mail addressed externally) never flags. Returns at most 5
    entries ``{"text", "match"}``, most-sensible first."""
    norm_body = _strip_email_markup(body)
    if not norm_body:
        return []
    body_tokens = norm_body.split()
    body_trigrams = _trigrams(body_tokens)
    external_blob = _strip_email_markup(" ".join(external_texts or []))
    external_number_tokens = {
        t for t in external_blob.split() if _strong_number_token(t)
    }
    body_sentences = [
        part.lower()
        for part in _sentence_parts(body)
        if len(part.split()) >= INTERNAL_QUOTE_SEMANTIC_MIN_WORDS
    ][:_MAX_EMBED_BODY_SENTENCES]
    external_sentences = [
        part.lower()
        for part in _sentence_parts(" ".join(external_texts or []))
        if len(part.split()) >= INTERNAL_QUOTE_SEMANTIC_MIN_WORDS
    ][:_MAX_EMBED_BODY_SENTENCES]

    internal_fragments: List[Dict[str, Any]] = []
    seen_texts: set = set()
    for text in internal_texts or []:
        for fragment in _internal_fragments(text):
            if fragment["text"] in seen_texts:
                continue
            seen_texts.add(fragment["text"])
            internal_fragments.append(fragment)

    # Semantic tier inputs are chosen before flagging so the embed batch is
    # a single call.
    semantic_candidates = [
        f for f in internal_fragments
        if f["words"] >= INTERNAL_QUOTE_SEMANTIC_MIN_WORDS
    ][:_MAX_EMBED_FRAGMENTS]
    semantic_index = {f["text"]: i for i, f in enumerate(semantic_candidates)}
    frag_vectors: List[List[float]] = []
    published_vectors: List[List[float]] = []
    sent_vectors: List[List[float]] = []
    if embed_fn is not None and semantic_candidates and body_sentences:
        try:
            vectors = await embed_fn(
                [f["text"] for f in semantic_candidates]
                + external_sentences
                + body_sentences
            )
            frag_vectors = vectors[:len(semantic_candidates)]
            published_vectors = vectors[
                len(semantic_candidates):
                len(semantic_candidates) + len(external_sentences)
            ]
            sent_vectors = vectors[len(semantic_candidates) + len(external_sentences):]
        except Exception:
            frag_vectors, published_vectors, sent_vectors = [], [], []

    flagged: List[Dict[str, str]] = []
    reported: set = set()
    for fragment in internal_fragments:
        text = fragment["text"]
        if text in external_blob:
            continue
        hit = None
        if (
            fragment["words"] >= INTERNAL_QUOTE_MIN_WORDS
            or (fragment["numeric"] and fragment["words"] >= INTERNAL_QUOTE_NUMERIC_MIN_WORDS)
            or (fragment["caps"] and fragment["words"] >= INTERNAL_QUOTE_CAPS_MIN_WORDS)
        ):
            if text in norm_body:
                hit = ("numeric" if fragment["numeric"] and fragment["words"] < INTERNAL_QUOTE_MIN_WORDS
                       else "caps" if fragment["caps"] and fragment["words"] < INTERNAL_QUOTE_MIN_WORDS
                       else "verbatim")
        if hit is None and fragment["words"] >= INTERNAL_QUOTE_SHINGLE_WORDS:
            grams = _trigrams(text.split())
            if grams and len(grams & body_trigrams) / len(grams) >= INTERNAL_QUOTE_SHINGLE_OVERLAP:
                hit = "reworded"
        if hit is None and frag_vectors:
            cand_idx = semantic_index.get(text)
            if cand_idx is not None and cand_idx < len(frag_vectors):
                # In-substance publication: if this internal passage already
                # went to the customer inside one of our sent replies, its
                # ideas are published — internally-drafted customer answers
                # are not leaks, even when the wording differs.
                if any(
                    _cosine(frag_vectors[cand_idx], pv)
                    >= INTERNAL_QUOTE_SEMANTIC_THRESHOLD
                    for pv in published_vectors
                ):
                    continue
                frag_numbers = {t for t in text.split() if _strong_number_token(t)}
                for idx, sent_vector in enumerate(sent_vectors):
                    if _cosine(frag_vectors[cand_idx], sent_vector) < INTERNAL_QUOTE_SEMANTIC_THRESHOLD:
                        continue
                    # The corroborating number must itself be internal-only:
                    # a number the customer has already seen (the list price
                    # discussed internally, then quoted) marks published
                    # facts, not leaks.
                    sent_numbers = {
                        t for t in body_sentences[idx].split()
                        if _strong_number_token(t)
                    } - external_number_tokens
                    if frag_numbers & sent_numbers:
                        hit = "semantic"
                        break
        if hit and text not in reported:
            reported.add(text)
            flagged.append({"text": text, "match": hit})

    flagged.sort(key=lambda f: (_MATCH_RANK.get(f["match"], 9), len(f["text"])))
    return flagged[:5]
