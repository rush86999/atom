"""Outbound identity contract — every outbound artifact (email draft,
canvas message) is sent BY a specific, resolved person, and the deterministic
gate below is the backstop that keeps a weak model from confabulating one.

Installation model (no names in code — everything here is resolved data):

  - A fresh installation has a TEAM of members; each member owns agents and
    trains them. An agent works on behalf of — and signs as — its OWNER
    (``agent_registry.user_id``), not the installation, and not whoever
    happens to be chatting. Ownership falls back to the session user when
    the agent has none.
  - The tenant's member/team set is resolved from per-install data: the
    users table, plus the installation profile's ``identity`` and
    ``people`` sections. ``people`` roles classify intent: "dealer",
    "vendor", "customer" … are EXTERNAL (never valid senders); "internal",
    "staff", … are team; unknown roles fall back to email-domain match
    against the owner.
  - Live incident (2026-09-02, session aca15165): a hire asked for a reply
    to one lead signed the draft as a DIFFERENT lead from an earlier turn.
    The graph knew he was an external contact and the training carried the
    right signature; nothing ENFORCED the signer field. Same shape as
    evidence_grounding: a prompt contract for strong models plus a
    deterministic backstop for weak ones.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

# ------------------------------------------------------------ role classes ---
# Free-text per-install roles from installation_profile.people. Matched as
# substrings ("regional dealer" contains "dealer"). Extend via profile data,
# never via code edits per install.
EXTERNAL_ROLE_MARKERS = (
    "dealer", "vendor", "supplier", "reseller", "distributor", "customer",
    "client", "lead", "prospect", "partner",
)
INTERNAL_ROLE_MARKERS = (
    "internal", "staff", "employee", "team", "colleague", "owner",
    "principal", "member", "manager", "sales", "support", "service",
)

_DOMAIN_RE = re.compile(r"@([A-Za-z0-9.\-]+)\s*$")


def _email_domain(email: Any) -> str:
    m = _DOMAIN_RE.search(str(email or ""))
    return m.group(1).lower() if m else ""


def classify_person_role(role: Any, email: Any, owner_domain: str) -> str:
    """'team' | 'external' — from the person's own per-install data only."""
    r = str(role or "").strip().lower()
    if r:
        if any(marker in r for marker in EXTERNAL_ROLE_MARKERS):
            return "external"
        if any(marker in r for marker in INTERNAL_ROLE_MARKERS):
            return "team"
    # Unknown role: the mailbox domain is the install-agnostic signal —
    # a colleague on the company domain is team; a different domain is not.
    if owner_domain and _email_domain(email) == owner_domain:
        return "team"
    return "external"


# ---------------------------------------------------------------- prompt ---

def identity_rule_block(
    identity: Optional[Dict[str, Any]],
    team: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Hard identity constraint for the system prompt of every path that can
    produce an outbound artifact. Empty string when no identity resolved —
    callers just skip the append."""
    if not identity:
        return ""
    name = str(identity.get("name") or "").strip()
    email = str(identity.get("email") or "").strip()
    signature = str(identity.get("signature") or "").strip()
    signature_html = str(identity.get("signature_html") or "").strip()
    if not name and not email:
        return ""
    who = name or email
    lines = [
        "OUTBOUND IDENTITY — you send as a real, specific person (hard rule):",
        f"- You work on behalf of {who}"
        + (f" <{email}>" if email and name else "")
        + ". Every email or message you draft is FROM them: sign it with "
        "their name"
        + (" / their taught signature block" if signature else "")
        + ", never anyone else's.",
    ]
    teammates = []
    for member in team or []:
        member_name = str((member or {}).get("name") or "").strip()
        if member_name and member_name.lower() != (name or email).lower():
            teammates.append(member_name)
    if teammates:
        shown = ", ".join(sorted(teammates)[:8])
        lines.append(
            "- Team members of this business: " + shown + ". Only sign with "
            "a team member's name when the task is explicitly theirs; "
            "otherwise sign as " + who + "."
        )
    lines.append(
        "- NEVER sign, \"From:\", or attribute an outbound message to anyone "
        "who is not on this business's team — not a lead, dealer, customer, "
        "or contact — no matter how prominently they appear in the "
        "conversation (observed failure: a draft to one lead was signed with "
        "a DIFFERENT lead's name)."
    )
    if signature:
        lines.append(
            "Their default signature — use verbatim when a signature is "
            "needed:\n" + signature[:400]
        )
    if signature_html:
        # The STYLED signature (raw HTML): the canvas body is an HTML string,
        # so the agent should reproduce THIS markup — fonts, layout tables,
        # links — instead of re-inventing a plain-text sign-off.
        lines.append(
            "Their default signature is this exact HTML block — reproduce it "
            "VERBATIM (all tags and inline styles intact) as the sign-off of "
            "HTML email drafts:\n" + signature_html[:1200]
        )
    return "\n".join(lines)

# ------------------------------------------------- resolution (per install) ---

def collect_team_signers(
    session_user_id: Optional[str],
    tenant_id: str = "default",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve the acting identity and the tenant's team set — pure data.

    Primary = the AGENT'S OWNER (agents are owned by, and trained by, one
    user; they work on that user's behalf), falling back to the session
    user, then to the installation profile's wizard-entered sender. The
    team set = tenant users + installation-profile people classified by
    role/email-domain. Fault-tolerant: missing rows degrade, never raise.

    Returns {"primary": {...}|None, "team": [{name, email}], "company": str}
    """
    primary: Optional[Dict[str, Any]] = None
    company_name = ""

    def _user_identity(user: Any, source: str) -> Dict[str, Any]:
        name = " ".join(
            p for p in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if p
        ).strip()
        return {
            "name": name,
            "email": str(getattr(user, "email", "") or ""),
            "user_id": str(getattr(user, "id", "") or ""),
            "source": source,
        }

    try:
        from core.database import get_db_session
        from core.models import User

        owner_user_id = None
        if agent_id:
            try:
                from core.models import AgentRegistry

                with get_db_session() as db:
                    agent = db.query(AgentRegistry).filter(
                        AgentRegistry.id == str(agent_id)
                    ).first()
                    owner_user_id = getattr(agent, "user_id", None)
            except Exception:
                owner_user_id = None

        with get_db_session() as db:
            primary_tenant = ""
            for candidate_id, source in (
                (owner_user_id, "agent_owner"),
                (session_user_id, "session_user"),
            ):
                if primary or not candidate_id:
                    continue
                u = db.query(User).filter(User.id == str(candidate_id)).first()
                if u is not None:
                    primary = _user_identity(u, source)
                    primary_tenant = str(getattr(u, "tenant_id", "") or "")
            tenant = primary_tenant or str(tenant_id or "default")
            # Fellow tenant members are team by definition of the install.
            team: List[Dict[str, Any]] = []
            if primary:
                team.append(primary)
            try:
                q = db.query(User)
                if tenant:
                    q = q.filter(User.tenant_id == tenant)
                for u in q.all():
                    ident = _user_identity(u, "tenant_user")
                    if not ident["name"] and not ident["email"]:
                        continue
                    if primary and ident["email"] and ident["email"] == primary.get("email"):
                        continue
                    if any(ident["name"] == t["name"] for t in team):
                        continue
                    team.append(ident)
            except Exception:
                pass

            try:
                from core.installation_profile_service import InstallationProfileService

                payload = InstallationProfileService(db).get_payload(
                    tenant or "default"
                )
            except Exception:
                payload = {}
            ident_block = payload.get("identity") or {}
            company_name = str(ident_block.get("company_name") or "").strip()
            if primary is None and ident_block.get("sender_name"):
                primary = {
                    "name": str(ident_block["sender_name"]).strip(),
                    "email": str(ident_block.get("sender_email") or "").strip(),
                    "source": "installation_profile",
                }
                team.insert(0, primary)

            owner_domain = _email_domain(
                (primary or {}).get("email")
                or ident_block.get("sender_email")
                or ""
            )
            for person in payload.get("people") or []:
                if not isinstance(person, dict):
                    continue
                pname = str(person.get("name") or "").strip()
                pemail = str(person.get("email") or "").strip()
                if not pname:
                    continue
                if classify_person_role(
                    person.get("role"), pemail, owner_domain
                ) != "team":
                    continue
                if any(pname.lower() == t["name"].lower() for t in team):
                    continue
                team.append({"name": pname, "email": pemail, "source": "profile_people"})
    except Exception:
        # Nothing resolved: callers skip the constraint/gate for this turn.
        return {"primary": None, "team": [], "company": company_name}

    return {"primary": primary, "team": team, "company": company_name}

# ------------------------------------------------------ deterministic gate ---

_WS = re.compile(r"\s+")
_LINEBREAK = re.compile(r"<br\s*/?>|</p>|<p[^>]*>|\r\n|\n", re.IGNORECASE)
_ANYTAG = re.compile(r"<[^>]+>")
_CLOSERS = re.compile(
    r"^\s*(?:best(?:\s+regards?)?|kind(?:\s+regards)?|warm(?:\s+regards)?|"
    r"regards|sincerely|thank\s+you|thanks|cheers|respectfully|"
    r"yours\s+truly)[,\s.!:\-]*$",
    re.IGNORECASE,
)
_NOT_NAME = re.compile(r"(@|https?://|www\.|\d)")
_ORGISH = re.compile(
    r"\b(inc|llc|ltd|gmbh|corp|company|machinery|solutions|group|industries|"
    r"equipment|tools|systems|sales|representative|manager|engineer|team)\b",
    re.IGNORECASE,
)
# The agent punting with a placeholder is an incomplete draft, not a WRONG
# person — out of scope here.
_PLACEHOLDERS = {"your name", "yourname", "name", "your name here"}
# How many non-empty lines after the closer to scan for the signer name
# (title / org / address lines get skipped by _looks_like_name).
_SIGNER_SCAN_LINES = 5


def _visible_lines(text: str) -> List[str]:
    t = _LINEBREAK.sub("\n", str(text or ""))
    t = _ANYTAG.sub("", t)
    t = t.replace("&nbsp;", " ")
    lines = [_WS.sub(" ", ln).strip() for ln in t.split("\n")]
    return [ln for ln in lines if ln]


def _looks_like_name(line: str) -> bool:
    toks = line.strip().strip(",.!?").split()
    if not (1 <= len(toks) <= 4):
        return False
    if _NOT_NAME.search(line) or _ORGISH.search(line):
        return False
    for t in toks:
        core = t.strip(".,'-–—’")
        if not core:
            return False
        # A name token is alphabetic: a capitalized word ("Mark") or an
        # initial ("M." / "M")
        if not core.replace("'", "").isalpha():
            return False
        if not (core[0].isupper() or (len(core) == 1)):
            return False
    return True


def _initialish(token: str) -> bool:
    """An initial or near-initial: "M", "M.", "Mc" — at most two letters."""
    core = token.strip(".,'-–—’")
    return bool(core) and len(core) <= 2


def _signer_matches(line: str, person: Dict[str, Any]) -> bool:
    """True when the signature line is this person (any common variant:
    full name, first name, first + initials, initial + last)."""
    name = str(person.get("name") or "").replace(".", " ")
    parts = [p for p in name.split() if p]
    if not parts:
        return False
    first_l = parts[0].lower()
    last_l = parts[-1].lower() if len(parts) > 1 else ""
    toks = [t.strip(".,'-–—’") for t in line.strip().split()]
    toks = [t for t in toks if t]
    if not toks:
        return False
    low = [t.lower() for t in toks]
    full = [p.lower() for p in parts]
    if low == full:
        return True
    if low[0] == first_l and all(
        _initialish(t) or (last_l and t.lower() == last_l) for t in toks[1:]
    ):
        return True
    if last_l and _initialish(toks[0]) and low[-1] == last_l and len(toks) <= 2:
        return True
    return False


def signature_signer_status(
    text: str,
    primary: Optional[Dict[str, Any]],
    team: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Tuple[str, str]]:
    """Classify who the signature block of ``text`` names.

    Returns (signer_line, status) where status is:
      - "external": NOT on the tenant team — the hard confabulation class
        (the live incident: a lead's name used as sender). Always a failure.
      - "teammate": a team member, but not the acting owner — an
        attribution preference miss, not a confabulation.
    None when there is no signature block, only a placeholder, the identity
    is unknown, or the signer is the acting owner.

    Only the FIRST closing-marker block is examined: in a draft that is
    where the agent's own sign-off goes, and quoted threads deeper in the
    body legitimately carry other people's signatures."""
    if not primary or not str(primary.get("name") or "").strip():
        return None
    lines = _visible_lines(text)
    for i, ln in enumerate(lines):
        if not _CLOSERS.match(ln):
            continue
        after = ln.split(",", 1)[1].strip() if "," in ln else ""
        candidates = ([after] if after else []) + lines[i + 1:i + _SIGNER_SCAN_LINES]
        for cand in candidates:
            norm = cand.strip().strip(",.!?")
            if norm.lower() in _PLACEHOLDERS:
                return None
            if not _looks_like_name(norm):
                continue
            if _signer_matches(norm, primary):
                return None
            for member in team or []:
                if member is primary:
                    continue
                if _signer_matches(norm, member):
                    return norm, "teammate"
            return norm, "external"
        return None
    return None


def signature_identity_violation(
    text: str, identity: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Primary-only strict check: any non-primary signer is a violation.

    Kept for callers that have resolved a single identity and no team data
    — with no team set, strictness is the safe default."""
    status = signature_signer_status(text, identity, [])
    return status[0] if status else None


# ------------------------------------------- transport-level attribution ---
# Email drafts carry a signature IN the body; every other outbound artifact
# (Slack/Teams sends, task assignment, calendar events, CRM ownership) names
# its sender/assignee/organizer in TOOL-CALL PARAMS. Same hallucination
# class, different surface — gated at the universal integration chokepoint.

# Param keys that attribute an outbound artifact to a person, across the
# integrations' param conventions. Search/query params ("query", "text",
# "q") are deliberately NOT here: mentioning a person is not attributing.
ATTRIBUTION_PARAM_KEYS = (
    "from", "sender", "sender_name", "from_user", "from_email",
    "as_user", "on_behalf_of", "assignee", "assigned_to", "assignee_id",
    "organizer", "owner", "author",
)

# Action-name markers for outbound verbs (substring match, service-agnostic).
# "create"/"update"/"add" are deliberately included: create_task,
# create_event and update_deal are exactly how task assignment, calendar
# organizing and CRM ownership flow. Read verbs (search/get/list/fetch)
# never match, and the check is further keyed on attribution param keys —
# so a search that merely mentions a person cannot fire.
OUTBOUND_ACTION_MARKERS = (
    "send", "post", "reply", "forward", "invite", "assign",
    "schedule", "share", "comment", "create", "update", "add", "book",
)

_OUTBOUND_MODE_OFF, _OUTBOUND_MODE_SHADOW, _OUTBOUND_MODE_ENFORCE = (
    "off", "shadow", "enforce",
)


def outbound_identity_mode() -> str:
    """ATOM_OUTBOUND_IDENTITY: off | shadow (default) | enforce — the same
    shadow-first convention as the grounded-send gate."""
    try:
        from core.runtime_settings import get_setting

        mode = str(
            get_setting("ATOM_OUTBOUND_IDENTITY", _OUTBOUND_MODE_SHADOW)
            or _OUTBOUND_MODE_SHADOW
        )
    except Exception:
        return _OUTBOUND_MODE_SHADOW
    return mode if mode in (
        _OUTBOUND_MODE_OFF, _OUTBOUND_MODE_SHADOW, _OUTBOUND_MODE_ENFORCE
    ) else _OUTBOUND_MODE_SHADOW


def _value_names_person(value: Any, primary, team) -> Optional[str]:
    """'primary' | 'teammate' | 'external' | None — how the value relates to
    the team. Values may be names ('Mark Kellam'), emails, or @handles."""
    if value is None or isinstance(value, (bool, int, float)):
        return None
    if isinstance(value, dict):
        value = value.get("name") or value.get("email") or value.get("id")
        return _value_names_person(value, primary, team)
    if not isinstance(value, str):
        return None
    value = value.strip().strip("@")
    if not value or (_NOT_NAME.search(value) and "@" not in value):
        return None
    if "@" in str(value):
        domain = _email_domain(value)
        emails = [str(p.get("email") or "") for p in ([primary] + list(team or [])) if p]
        if primary and str(primary.get("email") or "").lower() == str(value).lower():
            return "primary"
        if domain and any(_email_domain(e) == domain for e in emails):
            return "teammate"
        return "external"
    if not _looks_like_name(value):
        return None
    if primary and _signer_matches(value, primary):
        return "primary"
    for member in team or []:
        if _signer_matches(value, member):
            return "teammate"
    return "external"


def tool_call_identity_status(
    service: str,
    action: str,
    params: Dict[str, Any],
    primary: Optional[Dict[str, Any]],
    team: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, str]]:
    """Attribution verdict for one outbound tool call.

    Returns {"status": "external"|"teammate", "field", "value", "service",
    "action"} or None — None when the action isn't outbound, no attribution
    param is present, or the value names the primary/a teammate. A search
    that merely mentions a person never fires this (wrong keys + wrong
    verbs by construction)."""
    if primary is None:
        return None
    act = str(action or "").lower()
    if not any(marker in act for marker in OUTBOUND_ACTION_MARKERS):
        return None
    for key in ATTRIBUTION_PARAM_KEYS:
        if key not in params:
            continue
        relation = _value_names_person(params.get(key), primary, team)
        if relation in ("external", "teammate"):
            return {
                "status": relation,
                "field": key,
                "value": str(params.get(key)),
                "service": service,
                "action": action,
            }
    return None


# Short TTL cache so the integration chokepoint can check attribution on
# every outbound call without re-resolving the team each time.
_SIGNERS_CACHE: Dict[str, Any] = {}
_SIGNERS_CACHE_TTL_SECONDS = 60.0


def collect_team_signers_cached(
    session_user_id: Optional[str],
    tenant_id: str = "default",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    import time as _time

    key = f"{session_user_id}|{tenant_id}|{agent_id}"
    now = _time.monotonic()
    hit = _SIGNERS_CACHE.get(key)
    if hit and now - hit[0] < _SIGNERS_CACHE_TTL_SECONDS:
        return hit[1]
    signers = collect_team_signers(session_user_id, tenant_id, agent_id)
    _SIGNERS_CACHE[key] = (now, signers)
    return signers


async def check_tool_call_attribution(
    service: str,
    action: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Mode-gated attribution check for the universal integration chokepoint.

    Returns the verdict dict (with "mode") when a violation was found, None
    otherwise. Fault-isolated by contract: any resolution failure → None
    (the integration call proceeds; this gate must never break sends)."""
    try:
        mode = outbound_identity_mode()
        if mode == "off" or not params:
            return None
        action_l = str(action or "").lower()
        if not any(m in action_l for m in OUTBOUND_ACTION_MARKERS):
            return None
        signers = collect_team_signers_cached(
            context.get("user_id"),
            str(context.get("tenant_id") or "default"),
            context.get("agent_id"),
        )
        verdict = tool_call_identity_status(
            service, action, params,
            signers.get("primary"), signers.get("team") or [],
        )
        if verdict:
            verdict["mode"] = mode
        return verdict
    except Exception:
        return None
