"""Does a planned lookup actually address the user's CURRENT request?

RCA 2026-09-17 finding 2 (canvas a1a13834): the planner answered an OLD
request — the final scorecard turn executed ``outlook.search "PRICE VIPUL
price list attachment"`` and its result was accepted as this turn's
evidence. Prevention upstream (transcript labels) lives in the planner;
this module is the acceptance gate: whatever a leg PLANS to execute (or
reuses) must name something the current message names.

Deliberately conservative — a false "irrelevant" declines good evidence,
so the verdict is IRRELEVANT only when the overlap is ZERO-shaped: no
strong identifier of the message (numbers, codes, quoted phrases) appears
in the query AND fewer than two ordinary content words are shared. A query
that is absent or token-free is "unknown" (fail-open): intents like
documents.read can carry their target in kwargs rather than the query.
"""

import re
from typing import Any, Dict, List, NamedTuple, Optional, Set

#: Pure function words only — content words (price, scorecard, vendor) must
#: survive or the overlap test has nothing to overlap.
_STOPWORDS = frozenset({
    "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is",
    "are", "was", "were", "be", "been", "being", "with", "about", "as",
    "at", "by", "from", "that", "this", "these", "those", "it", "its",
    "me", "my", "we", "our", "you", "your", "i", "do", "does", "did",
    "can", "could", "would", "should", "will", "shall", "may", "might",
    "up", "out", "into", "over", "under", "again", "then", "than", "so",
    "too", "very", "just", "now", "also", "please", "find", "search",
    "look", "show", "tell", "give", "get", "need", "want", "check",
    "see", "us", "via", "per", "if", "when", "where", "how", "what",
    "which", "who", "there", "here",
})

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._+\-]*")
_QUOTED_RE = re.compile(r"[\"'“”‘’]([^\"'“”‘’]{3,80})[\"'“”‘’]")
_ALLCAPS_RE = re.compile(r"\b[A-Z]{2,}\d*\b")
#: Opaque message-id shape (Graph ids are 40+ base64url chars, may carry '='
#: padding). An id NAMES its target explicitly — it is not subject vocabulary,
#: so lexical subject matching never applies to an id-directed lookup.
_MAIL_ID_SHAPE_RE = re.compile(r"[A-Za-z0-9_\-=/]{40,}")


def content_tokens(text: str) -> Set[str]:
    """Lowercase content words of ``text`` — minus stopwords, single
    characters, and bare 1-digit numbers.

    Sentence-final periods are stripped from token edges (RCA 2026-09-22:
    "…to those machinery." tokenized to ``machinery.``, which matched nothing
    — the period is punctuation, not part of the word; INTERNAL dots survive
    for decimals and file-like codes)."""
    out: Set[str] = set()
    for tok in _TOKEN_RE.findall((text or "").lower()):
        tok = tok.strip(".")
        if not tok or tok in _STOPWORDS or len(tok) < 2:
            continue
        if tok.isdigit() and len(tok) < 2:
            continue
        out.add(tok)
    return out


def strong_tokens(text: str) -> Set[str]:
    """Identifiers a query must honor to claim it addresses the ask:
    numbers with a decimal or 3+ digits (0.87, 7519), codes with digits
    or hyphens (wg-350dsav, r235), and ALL-CAPS words (RFQ, VIPUL)."""
    out: Set[str] = set()
    lowered = (text or "").lower()
    for tok in _TOKEN_RE.findall(lowered):
        if any(ch.isdigit() for ch in tok) and (
                "." in tok or "-" in tok or len(tok) >= 3):
            out.add(tok)
    for m in _ALLCAPS_RE.findall(text or ""):
        out.add(m.lower())
    return out


def quoted_phrases(text: str) -> List[str]:
    """Quoted spans, normalized for substring matching."""
    return [" ".join(m.group(1).split()).lower()
            for m in _QUOTED_RE.finditer(text or "")]


def relevance_verdict(
    query: str, message: str, history: Optional[List[Dict[str, Any]]] = None,
    extra_topic: Optional[str] = None,
    allow_canvas_target: bool = True,
) -> str:
    """``relevant`` | ``irrelevant`` | ``unknown`` (fail-open) for a
    planned lookup query against the current user message.

    See :func:`relevance_basis` for the rule-by-rule contract; this is its
    verdict-only view."""
    return relevance_basis(
        query, message, history=history, extra_topic=extra_topic,
        allow_canvas_target=allow_canvas_target,
    )[0]


_CANVAS_TOPIC_NOISE = frozenset({
    "email", "quote", "quotation", "draft", "prepared", "prepared", "page",
    "table", "row", "rows", "unit", "price", "prices", "delivery", "lead",
    "time", "term", "terms", "payment", "cad", "fob", "tbd", "valid",
    "days", "day", "footer", "signature", "regards", "visit", "website",
    "web", "site", "rate", "performance", "brennan", "machinery", "inc",
    "requested", "alternative", "alternatives", "option", "options",
    "vendor", "supplier", "product", "products", "equipment", "model",
    "series", "industrial", "customer", "client", "company", "amount",
    "cost", "value", "figure", "request", "requests", "update", "apply",
    "actual", "customer", "client", "lead", "time", "term", "terms",
})


def _canvas_topic_tokens(text: str) -> Set[str]:
    tokens = content_tokens(text)
    return {
        token for token in tokens
        if token not in _CANVAS_TOPIC_NOISE
        and not re.fullmatch(r"(?:19|20)\d{2}", token)
    }


def _canvas_topic_variants(tokens: Set[str]) -> Set[str]:
    variants = set(tokens)
    for token in tokens:
        if token.endswith("ies") and len(token) > 3:
            variants.add(token[:-3] + "y")
        if token.endswith("es") and len(token) > 3:
            variants.add(token[:-2])
        if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
            variants.add(token[:-1])
    return variants


def _canvas_topic_strong_tokens(text: str) -> Set[str]:
    strong = set(strong_tokens(text))
    return {
        token for token in strong
        if token not in _CANVAS_TOPIC_NOISE
        and not re.fullmatch(r"(?:19|20)\d{2}", token)
    }


def canvas_topic_text(canvas: Optional[Dict[str, Any]]) -> str:
    """Judgeable subject text of the canvas a request operates on: the
    title plus the readable text of its content and participants (HTML tags
    stripped), so a retrieval query naming the canvas's own subject can be
    recognized.

    Live 2026-09-23 (canvas 0e4defa5): the edit instruction "update with
    actual prices in the email" shares ZERO words with the correct
    evidence query — the products being priced (roll bender, bead roller,
    slitters) live in the CANVAS the instruction points at ("the email"),
    not in the sentence. The canvas target is therefore part of what a
    canvas-edit lookup legitimately names. Tolerates both context shapes
    (editor ``{title, content…}`` and orchestrator ``_resolve_canvas_ctx``)
    and returns "" when nothing usable is present."""
    if not isinstance(canvas, dict):
        return ""
    parts: List[str] = []
    for key in ("title", "name", "subject"):
        val = canvas.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
    content = canvas.get("content")
    if isinstance(content, dict):
        for key in (
            "subject", "title", "to", "from", "sender", "cc", "participants",
            "body", "content", "text",
        ):
            val = content.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(re.sub(r"<[^>]+>", " ", val))
            elif isinstance(val, (list, tuple)):
                parts.extend(str(item) for item in val if str(item).strip())
    elif isinstance(content, str) and content.strip():
        parts.append(re.sub(r"<[^>]+>", " ", content))
    return " ".join(parts)[:8000]


def relevance_basis(
    query: str, message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    extra_topic: Optional[str] = None,
    allow_canvas_target: bool = True,
) -> "tuple[str, str]":
    """``(verdict, basis)`` — the verdict plus the RULE that produced it.

    2026-09-22: this function existed as an import in the planner's stamp
    wrapper since R4 (2026-09-17) but was never defined — the wrapper's
    fault-isolation silently stamped every plan ``("unknown",
    "module-unavailable")``. Unknown is fail-open everywhere, so nothing
    broke, but the stamp of record carried no information. Now real: the
    basis strings name the deciding rule, so a stamp can be audited
    ("why was this plan accepted?").

    Review R4 (2026-09-17) fixed three defects in the rules. The verdict is
    consulted by the planner AND re-run by the editor/chat gates, so a wrong
    ``irrelevant`` BLOCKS valid work — the more damaging direction, and the
    one the rules below are shaped around.

    1. REFERENTIAL REQUESTS. "Open the attachment from that email you just found"
       names its target by anaphora; the referent is in the conversation, not the
       sentence, so lexical matching cannot see it and returned ``irrelevant`` —
       blocking a lookup the planner had already validated by provenance. Such a
       message is ``unknown`` (inspect/replan), never ``irrelevant``.
    2. A SHARED NUMBER IS NOT A SHARED SUBJECT. ``strong_tokens`` alone accepted
       "PRICE VIPUL 0.87" for "what is the vendor scorecard reliability 0.87"
       purely because both contain 0.87. A strong token now needs corroboration
       from a content word — unless the message is nothing BUT the identifier
       ("show me row 235"), where the identifier is the subject.
    3. Ambiguous lexical signal (some overlap, not enough) is ``unknown`` rather
       than ``irrelevant``: insufficient evidence to accept is not proof of
       mismatch.

    2026-09-22 (request-reference resolution): when ``history`` is supplied the
    caller gets referent resolution first (:func:`resolve_request_reference`).
    A RESOLVED approval/referential ("yes go ahead") is judged against the
    resolved TOPIC — current message plus the exchange it points at — and the
    referential shortcut no longer fires, because the referent is no longer
    missing; the shortcut stays in force for UNRESOLVED/AMBIGUOUS/DIRECT
    messages. An UNRESOLVED or AMBIGUOUS approval can never be declined
    lexically (the terminal ``irrelevant`` becomes ``unknown``): a bare
    "yes go ahead" names no subject, and lexical absence is not proof of
    mismatch. Without ``history`` the behaviour is byte-identical to the
    pre-resolution rules.

    2026-09-23 (canvas-target acceptance, ``extra_topic``): an edit turn's
    evidence query names the SUBJECT OF THE CANVAS being edited, while the
    instruction names the artifact and the fields to fill ("update with
    actual prices in the email") — zero lexical overlap by construction.
    When ``extra_topic`` (the canvas's subject text, see
    :func:`canvas_topic_text`) is supplied, a query sharing two content
    words with it — or one word that is a strong identifier of it — is
    ``relevant`` (basis ``canvas-target``/``canvas-target-identifier``)
    instead of ``irrelevant``. A stale query shares nothing with the target
    and still declines. Callers that pass no ``extra_topic`` see
    byte-identical behaviour.
    """
    if not query or not str(query).strip():
        return "unknown", "empty-query"
    # An id-directed lookup names its target EXPLICITLY (opaque message ids
    # carried from conversation handles). Subject-word overlap cannot judge
    # it and must never decline it — this is the completion flow's whole
    # point ("yes go ahead" → read the unresolved messages by id).
    if _MAIL_ID_SHAPE_RE.search(str(query)):
        return "relevant", "id-directed"
    # Resolution ALWAYS runs: with no history an approval/referential turn is
    # UNRESOLVED (never lexically declined — that is the 2026-09-22 incident
    # shape), and a substantive message resolves to DIRECT with legacy
    # behaviour byte-identical.
    ref = resolve_request_reference(message, history or [])
    if ref.kind in (REF_UNRESOLVED, REF_AMBIGUOUS, REF_RESOLVED):
        judge_text = ref.topic_text
    else:
        judge_text = message
    q_norm = " ".join(str(query).lower().split())
    msg_tokens = content_tokens(judge_text)
    if not msg_tokens:
        return "unknown", "no-content-tokens"
    query_tokens = content_tokens(q_norm)

    for phrase in quoted_phrases(judge_text):
        if phrase in q_norm:
            return "relevant", "quoted-phrase"

    strong_hits = strong_tokens(judge_text) & query_tokens
    overlap = msg_tokens & query_tokens

    # (1) A referential message cannot be judged lexically. Checked BEFORE the
    # identifier shortcut so an anaphoric ask is never declined for lacking
    # terms it resolves elsewhere. A RESOLVED reference has already had its
    # referent appended to the judged text, so the shortcut is intentionally
    # skipped there — the missing referent is missing no more.
    if ref.kind != REF_RESOLVED and _REFERENTIAL_RE.search(str(message or "")):
        return "unknown", "referential-fail-open"

    # (2) An identifier must be corroborated by a content word.
    if strong_hits and (overlap - strong_hits):
        return "relevant", "identifier-corroborated"
    if strong_hits and len(msg_tokens) <= 2:
        return "relevant", "identifier-only-message"

    if len(overlap) >= 2:
        return "relevant", "token-overlap"
    # Short asks ("price of WG-350?") share one word legitimately — the
    # hyphenated code may be re-tokenized in the query ("wg 350 price").
    if len(overlap) >= 1 and len(msg_tokens) <= 4 and not strong_hits:
        return "relevant", "short-ask-single-overlap"
    # A message this short with zero overlap carries too little signal to
    # judge ("hi", "ok thanks") — fail open rather than decline.
    if not overlap and len(msg_tokens) <= 2:
        return "unknown", "content-free-message"
    # (3) Some signal but not enough to accept: hand it back to the caller.
    if overlap:
        return "unknown", "insufficient-overlap"
    if strong_hits:
        # An identifier with no `msg_tokens` branch above means the message had
        # nothing else to corroborate it with — still inspect rather than decline.
        return "unknown", "uncorroborated-identifier"
    # A SHARED FIGURE IS A SHARED TARGET. "FW: RFQ - Foot shear" and "search for
    # this one: $ 5,350.00 - 10 % in stock" share no WORD, but 5,350 is exactly
    # what identifies the message — the quoted-body-to-subject mapping the planner
    # already exempts from its own lexical check. Digit runs are compared, not the
    # whole decorated token, so "5,350.00" and "5350" agree.
    if _digit_runs(judge_text) & _digit_runs(query):
        return "unknown", "digit-runs"
    # An approval/referential turn whose referent could not be resolved names no
    # subject of its own — lexical absence is not proof of mismatch (live
    # 2026-09-22: "yes go ahead" tokenized to {ahead}, zero overlap with the
    # machinery query, hard-"irrelevant", and the lookup was declined). Hand it
    # back to the caller (inspect/replan/clarify), never decline.
    if ref.kind in (REF_UNRESOLVED, REF_AMBIGUOUS):
        return "unknown", "unresolved-reference"
    # CANVAS-TARGET RULE (2026-09-23, canvas 0e4defa5): an edit turn's
    # evidence lookup legitimately names the SUBJECT OF THE CANVAS being
    # edited, not the wording of the instruction — "update with actual
    # prices in the email" vs the mailbox search for the quoted products
    # is zero-overlap BY CONSTRUCTION, the same shape as the
    # provenance-quote exemption above (query = thread SUBJECT, message =
    # pasted BODY). When the query names what the canvas names — two
    # content words, or one word that is a strong identifier of the canvas
    # (a model code, a figure) — it addresses the request. A genuinely
    # stale query (RCA 2026-09-17: "PRICE VIPUL price list" against a
    # scorecard canvas) still shares nothing with the target and declines.
    if extra_topic and allow_canvas_target:
        topic_tokens = _canvas_topic_variants(_canvas_topic_tokens(extra_topic))
        query_topic_tokens = _canvas_topic_variants(
            _canvas_topic_tokens(q_norm))
        topic_overlap = query_topic_tokens & topic_tokens
        if topic_overlap & _canvas_topic_strong_tokens(extra_topic):
            return "relevant", "canvas-target-identifier"
        if len(topic_overlap) >= 2 or (
                len(topic_overlap) == 1
                and any(len(token) >= 4 for token in topic_overlap)):
            return "relevant", "canvas-target"
    # NO shared signal at all: the query and the request are about different
    # subjects, which is the one case lexical evidence can settle.
    return "irrelevant", "zero-overlap"


def resolved_plan_relevance(
    plan: Any,
    message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    extra_topic: Optional[str] = None,
    allow_canvas_target: bool = True,
) -> "tuple[str, str]":
    """Resolve a plan stamp against the current request and canvas.

    A stamp is evidence from an earlier stage, not a permanent bypass. A
    provenance quote remains valid because its subject is established by the
    verified source; every other verdict is rechecked against the current
    message, history, and target canvas. This is what prevents a plan stamped
    against a stale client snapshot from executing after the durable canvas
    has changed."""
    stamped = getattr(plan, "relevance_verdict", None)
    stamped_basis = str(getattr(plan, "relevance_basis", "") or "")
    if stamped == "relevant" and stamped_basis == "provenance-quote":
        return "relevant", stamped_basis
    query = str(getattr(plan, "query", "") or "")
    current = relevance_basis(
        query, message, history=history, extra_topic=extra_topic,
        allow_canvas_target=allow_canvas_target,
    )
    if current[0] == "irrelevant":
        return current
    if stamped in (None, "", "unknown"):
        return current
    return current


def _digit_runs(text: str) -> Set[str]:
    """Digit sequences of 3+ characters (figures and codes)."""
    return {
        run for run in re.findall(r"\d{3,}", str(text or "").replace(",", ""))
    }


#: Language that points at something ALREADY IN THE CONVERSATION. Must not match
#: an ordinary definite article — "what is the weather in Paris" contains a
#: "the"-noun pair and is not referential (that over-broad first version made
#: every such message `unknown` and broke nine of the module's own tests).
_REFERENTIAL_RE = re.compile(
    # a deictic determiner with a document noun: "that email", "those files"
    r"\b(?:that|those|these|same|previous|earlier|above|last)\s+"
    r"(?:email|e-mail|message|thread|attachment|file|document|workbook|sheet|"
    r"spreadsheet|invoice|quote|record|result|one)s?\b"
    # "the one/ones" is referential; "the email you just found" too
    r"|\bthe\s+ones?\b"
    r"|\b(?:the|that|this)\s+(?:email|e-mail|message|thread|attachment|file|"
    r"document|workbook|invoice|quote|record|result)s?\s+"
    r"(?:you|we|i|he|she|they)\b"
    r"|\b(?:you|we)\s+(?:just\s+)?(?:found|opened|mentioned|sent)\b"
    r"|\bas\s+(?:above|before|mentioned)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# REQUEST-REFERENCE RESOLUTION (2026-09-22)
# ---------------------------------------------------------------------------
# Live incident: a mailbox search for "Steve Macisaac machinery requested"
# SUCCEEDED, but the user's "yes go ahead" follow-up was validated against that
# bare phrase — tokenized to the single distinctive term "ahead" — so the
# evidence gate rejected the block, the rejection was reported as "a required
# live-data lookup failed", and the agent told the user the lookup had failed.
#
# This section resolves WHAT a conversational turn points at, so every
# relevance gate judges the resolved TOPIC instead of the bare follow-up.
#
# SCOPE CONTRACT (deliberate, do not widen): the resolver resolves the topic
# FOR VALIDATION ONLY. It never rewrites what the turn asks the system to DO —
# the current instruction stays authoritative for execution (query construction,
# actions, filters). Appending the referent to ``topic_text`` lets lexical gates
# recognize the subject; it does NOT make them enforce constraints ("excluding
# the slitter", "only September") — constraint enforcement belongs to the
# instruction, which downstream consumers keep reading verbatim.

REF_DIRECT = "direct"          # standalone substantive request
REF_RESOLVED = "resolved"      # approval/referential with a resolvable referent
REF_UNRESOLVED = "unresolved"  # approval/referential, no active referent
REF_AMBIGUOUS = "ambiguous"    # referent cannot be uniquely grounded (ordinal etc.)

_REQUEST_REF_WINDOW = 12  # turns inspected, aligned with session_sources._WINDOW


class RequestReference(NamedTuple):
    """What the current turn points at, for the relevance gates.

    kind              — DIRECT | RESOLVED | UNRESOLVED | AMBIGUOUS
    message           — the raw current turn (never rewritten)
    topic_text        — text the gates may judge evidence against: the current
                        message FIRST (authoritative), then the resolved
                        referent. EMPTY segments are skipped.
    lineage_requests  — request texts of the allowed provenance: the current
                        message plus the resolved exchange's request. A block
                        whose provenance traces here addresses THIS task even
                        with zero lexical overlap ("yes go ahead" consuming the
                        offer it approves). Lineage establishes RELEVANCE ONLY —
                        never freshness, completeness, or success.
    lineage_turn_indices — positions (in the ``history`` list passed to the
                        resolver) of the lineage turns; -1 is the current turn.
    candidates        — human-readable referent options, for clarify prompts.
    clarify_reason    — "" | no_history | superseded | fulfilled | ungrounded_ordinal | no_topic
    """

    kind: str
    message: str
    topic_text: str
    lineage_requests: List[str]
    lineage_turn_indices: List[int]
    candidates: List[str]
    clarify_reason: str = ""


def _direct_reference(message: str) -> RequestReference:
    """Reference for callers that pass no history — legacy behaviour."""
    msg = (message or "").strip()
    return RequestReference(
        REF_DIRECT, msg, msg, [msg] if msg else [], [], [], "")


# An OFFER is an assistant reply announcing a pending action the user can
# approve. Markers kept deliberately explicit; the modal forms carry a
# negation lookahead so "I can't pull that" is not an offer.
_OFFER_MARKER_RE = re.compile(
    r"\b(?:want me to|shall i|should i|would you like(?: me to)?|"
    r"do you want me to|ready to|"
    r"\bi[\s']*(?:can|could|will|ll)\b(?!['’]?(?:t|not)\b))",
    re.IGNORECASE,
)

# Approval-shaped turns: an approval phrase AND (almost) nothing else. A
# message that carries its own subject ("yes go ahead on the September list")
# still resolves — its tokens ride along in topic_text — but a QUESTION or a
# substantive request is its own ask and must never enter the approval path.
_APPROVAL_PHRASE_RE = re.compile(
    r"\b(?:yes|yeah|yep|yup|sure|ok|okay|go ahead|proceed|continue|go on|"
    r"do it|do so|carry on|sounds good|that works|please do|affirmative)\b",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(r"\bwhat about\b|\bhow about\b", re.IGNORECASE)
_APPROVAL_VOCABULARY = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "go", "ahead",
    "proceed", "continue", "sounds", "good", "great", "fine", "works",
    "cool", "affirmative", "do", "it", "that", "one", "please", "thanks",
    "thank", "carry", "on", "then", "also", "and",
    # constraint markers: a QUALIFIED approval ("yes, excluding the slitter",
    # "only September") stays approval-shaped — the qualification tokens ride
    # into topic_text and the instruction stays authoritative downstream.
    "excluding", "except", "without", "only", "besides", "minus",
    "ignoring", "skipping", "regarding", "with",
}

# Referential WITHOUT a document noun ("read it again", "check them again"):
# a bare follow-up marker plus a pronoun, or "again" on its own.
_FOLLOWUP_RE = re.compile(
    r"\b(?:it|them|that|this)\b[^\n]{0,40}?\bagain\b|\bagain\b",
    re.IGNORECASE,
)

_ORDINAL_RE = re.compile(
    r"\b(the\s+)?(first|second|third|fourth|fifth|last|latest|other|"
    r"second one|third one)\b(?=\s+(?:one|list|offer|email|message|result))?",
    re.IGNORECASE,
)
_ORDINAL_INDEX = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "last": -1, "latest": -1,
}
_NUMBERED_ITEM_RE = re.compile(
    r"(?:^|\n)\s*(\d)[\.\)]\s*([^\n]+)", re.MULTILINE)


def _turn_texts(entry: Dict[str, Any]) -> "tuple[str, str]":
    """(user_text, assistant_text) of one history entry, tolerating legacy
    string responses and missing halves."""
    user_text = str((entry or {}).get("message") or "").strip()
    resp = (entry or {}).get("response")
    if isinstance(resp, dict):
        assistant_text = str(resp.get("message") or "").strip()
    else:
        assistant_text = str(resp or "").strip()
    return user_text, assistant_text


def _is_substantive_request(text: str) -> bool:
    """A user turn that starts a NEW exchange: carries its own subject and
    neither approves nor refers back. Approval/referential shapes are exactly
    the non-boundary continuations."""
    t = (text or "").strip()
    if not t:
        return False
    if _APPROVAL_PHRASE_RE.search(t):
        return False
    if _REFERENTIAL_RE.search(t) or _FOLLOWUP_RE.search(t):
        return False
    return bool(content_tokens(t))


def _is_approval_shaped(message: str) -> bool:
    """Approval phrase AND little else. Questions are never approvals; a
    message carrying its own subject stays approval-shaped ONLY when the
    subject is a single token ("yes go ahead with the September one") — two
    content tokens mean the turn names its own request and needs no
    resolution ("ok so what about the price" is a question anyway)."""
    t = (message or "").strip()
    if not t or "?" in t or _QUESTION_RE.search(t):
        return False
    if not _APPROVAL_PHRASE_RE.search(t):
        return False
    remaining = [
        tok for tok in content_tokens(t) if tok not in _APPROVAL_VOCABULARY
    ]
    return len(remaining) <= 1


def _is_referential(message: str) -> bool:
    return bool(
        _REFERENTIAL_RE.search(message or "") or _FOLLOWUP_RE.search(message or "")
    )


_DELIVERY_WORD_RE = re.compile(
    r"(?:sent|delivered|shared|attached|forwarded|drafted|created|pulled|"
    r"exported|uploaded|listed|compiled|completed|done|here)'?(?:s)?",
    re.IGNORECASE,
)
_DELIVERY_BLOCKERS = {
    "not", "never", "no", "cant", "can't", "cannot", "won't", "wont",
    "don't", "dont", "didn't", "didnt",
    "can", "could", "will", "would", "shall", "should", "may", "might",
    "must", "being", "about",
}


def _delivery_confirmed(text: str) -> bool:
    """Did an assistant reply DELIVER something (vs offer/announce)?

    Token-scan, not bare substring: the user-pinned failure is "sent" inside
    "not sent" or "can be sent" deactivating a live offer. A delivery word is
    confirmed only when no negation and no modality sits within the three
    tokens before it ("can be sent" → potential, not delivery; "was sent" →
    delivery; "not sent" → not delivery)."""
    tokens = re.findall(r"[a-z'’]+", (text or "").lower())
    for i, tok in enumerate(tokens):
        if not _DELIVERY_WORD_RE.fullmatch(tok):
            continue
        if tok in ("here",):  # "here's/here is" handled by the regex below
            continue
        prior = tokens[max(0, i - 3):i]
        if any(p in _DELIVERY_BLOCKERS for p in prior):
            continue
        if "be" in prior and ("to" in prior or any(
                p in ("can", "could", "will", "would", "shall", "should")
                for p in prior)):
            continue
        return True
    # "Here's the list you asked for" — delivery by presentation.
    if re.search(r"\bhere(?:'s|\s+is)\b", (text or ""), re.IGNORECASE):
        return True
    return False


def _ground_ordinal(message: str, offer_text: str) -> Optional[str]:
    """Resolve "the second one" against an explicit numbered list in the
    offer/reply. Returns the item text, or None when the ordinal is
    ungrounded (the AMBIGUOUS case)."""
    m = _ORDINAL_RE.search(message or "")
    if not m:
        return None
    word = m.group(2).lower()
    idx = _ORDINAL_INDEX.get(word)
    if idx is None:
        return None
    items = _NUMBERED_ITEM_RE.findall(offer_text or "")
    if not items:
        return None
    if idx == -1:
        return str(items[-1][1]).strip()
    for num, body in items:
        if int(num) == idx:
            return str(body).strip()
    return None


def resolve_request_reference(
    message: str, history: Optional[List[Dict[str, Any]]] = None
) -> RequestReference:
    """Resolve what a conversational turn points at, for the relevance gates.

    ACTIVE-OFFER RULE: the newest offer wins; older offers are inactive by
    construction. The scan walks newest→oldest and an offer is a candidate
    only when NOTHING after it supersedes it — a later substantive user
    message is an exchange boundary (everything before it is a completed
    exchange), and a delivery-confirmed reply after the offer means the offer
    was already fulfilled. Both deactivate the candidate; older offers are
    never resurrected past the boundary, so an old "I can…" can never capture
    a new approval.

    Referential turns ("read that email again") resolve to the ACTIVE TOPIC —
    the most recent substantive exchange — without needing an offer marker.
    Ordinals resolve only against an explicit numbered list in the candidate
    text; otherwise the reference is AMBIGUOUS (clarify)."""
    msg = (message or "").strip()
    entries: List[Dict[str, Any]] = []
    for h in (history or [])[-_REQUEST_REF_WINDOW:]:
        if isinstance(h, dict) and not h.get("error"):
            entries.append(h)

    approval = _is_approval_shaped(msg)
    referential = _is_referential(msg)
    if not approval and not referential:
        # OFFER-REFERENTIAL ARM (RCA 2026-09-22 "rebuild the draft" turn): an
        # approval may RESTATE the offered task instead of using approval
        # vocabulary — "rebuild the draft with requested quotes and
        # alternatives to those machinery" approves the offer "I'll rebuild
        # the canvas table with the full eight-line list… slitter
        # alternatives". Lexically DIRECT, referential in meaning: judged
        # bare, the machinery query looked irrelevant and the planner paid a
        # second corrective structured call. Grounded below, once the scan
        # helpers exist: an ACTIVE offer whose own text shares ≥2 content
        # tokens with the message resolves the exchange. Over-resolving
        # toward RESOLVED is the safe direction by the gate's own bias (a
        # wrongly-accepted block beats a wrongly-rejected one).
        _offer_restatement = True
    else:
        _offer_restatement = False

    if not entries:
        if _offer_restatement:
            # A substantive standalone request with no history is DIRECT —
            # only conversational (approval/referential) shapes need a
            # referent to be UNRESOLVED about.
            return _direct_reference(msg)
        return RequestReference(
            REF_UNRESOLVED, msg, msg, [msg] if msg else [], [], [],
            "no_history")

    # Newer entries sit closer to the end of the list. Walk newest→oldest.
    newest_idx = len(entries) - 1

    def _later_superseded_or_fulfilled(j: int) -> "tuple[bool, bool]":
        superseded = fulfilled = False
        for later in entries[j + 1:]:
            if _is_substantive_request(_turn_texts(later)[0]):
                superseded = True
            if _delivery_confirmed(_turn_texts(later)[1]):
                fulfilled = True
        return superseded, fulfilled

    if _offer_restatement:
        # Only the NEWEST ACTIVE offer grounds a restatement: superseded or
        # fulfilled offers deactivate it (an old "I can…" must not capture a
        # new task that merely shares its wording).
        for j in range(newest_idx, -1, -1):
            offer_text = _turn_texts(entries[j])[1]
            if not offer_text or not _OFFER_MARKER_RE.search(offer_text):
                continue
            superseded, fulfilled = _later_superseded_or_fulfilled(j)
            if superseded or fulfilled:
                break
            if len(content_tokens(msg) & content_tokens(offer_text)) >= 2:
                referent_request = _turn_texts(entries[j])[0]
                lineage_requests = [
                    r2 for r2 in (referent_request, msg) if r2]
                topic_parts = [p for p in (
                    msg, referent_request, offer_text[:500]) if p]
                return RequestReference(
                    REF_RESOLVED, msg, "\n".join(topic_parts),
                    lineage_requests, [j, -1],
                    [offer_text[:200]], "offer_restatement")
            break
        return _direct_reference(msg)

    candidate: Optional[int] = None
    candidates_text: List[str] = []
    clarify_reason = ""
    boundary_reason = ""

    # (1) Approval turns: the newest ACTIVE offer wins. The scan stops at the
    # first candidate; an exchange boundary (later substantive user message)
    # or a fulfilled offer stops the scan entirely — older offers are never
    # resurrected past it, so an old "I can…" can never capture a new
    # approval.
    if approval:
        for j in range(newest_idx, -1, -1):
            offer_text = _turn_texts(entries[j])[1]
            if not offer_text or not _OFFER_MARKER_RE.search(offer_text):
                continue
            superseded, fulfilled = _later_superseded_or_fulfilled(j)
            if superseded:
                boundary_reason = "superseded"
                break
            if fulfilled:
                boundary_reason = "fulfilled"
                break
            candidate = j
            candidates_text = [offer_text[:200]]
            break

    # (2) Active-topic fallback for BOTH shapes: the most recent substantive
    # exchange. This is the primary route for referential turns ("read that
    # email again" needs no offer marker) and the fallback when an approval
    # has no live offer (an ordinal approving an item of a listed reply, or a
    # boundary/fulfilled offer — the approval then attaches to the NEWEST
    # exchange, never to an older one).
    if candidate is None:
        for j in range(newest_idx, -1, -1):
            user_text, reply_text = _turn_texts(entries[j])
            if _is_substantive_request(user_text):
                candidate = j
                candidates_text = [reply_text[:200] or user_text[:200]]
                break
        if candidate is None:
            clarify_reason = boundary_reason or "no_topic"

    if candidate is None:
        return RequestReference(
            REF_UNRESOLVED, msg, msg, [msg] if msg else [], [], [],
            clarify_reason or "no_offer")

    referent_request, offer_text = _turn_texts(entries[candidate])
    lineage_requests = [r for r in (referent_request, msg) if r]
    lineage_indices = [candidate, -1]  # -1 = the current turn

    topic_parts = [p for p in (
        msg, referent_request, (offer_text or "")[:500]) if p]

    # An ordinal approval ("yes, the second one") is grounded ONLY by an
    # explicit numbered list in the offer/reply; otherwise AMBIGUOUS.
    if _ORDINAL_RE.search(msg):
        item = _ground_ordinal(msg, offer_text or "")
        if item:
            topic_parts.append(item)
        else:
            return RequestReference(
                REF_AMBIGUOUS, msg, msg, lineage_requests,
                lineage_indices, candidates_text, "ungrounded_ordinal")

    return RequestReference(
        REF_RESOLVED, msg, "\n".join(topic_parts), lineage_requests,
        lineage_indices, candidates_text, "")
