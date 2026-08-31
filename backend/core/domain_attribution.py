"""
Domain Attribution (Round 86c)

Gives the generalist meta agent a PER-ROLE learning record so it can earn
super-mentor status domain by domain ("super mentor for everyone" is an
achievement, not a default).

Two pieces:
  - resolve_domain(text): lightweight keyword routing over task text using
    the fleet's DOMAIN_ALIASES vocabulary. Conservative — returns None when
    no role signals are present; unattributed work stays on the generalist
    record only.
  - DomainExperienceLedger: precise SQL ledger of attributed outcomes.
    The world-model experience remains the semantic/vector layer; this table
    is the exact-count evidence layer that promotion gates can trust.

Anti-laundering: ledger wins qualify atom_main to MENTOR a role; they never
inflate the student's own episode counts or the student's confidence.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Role keyword vocabulary (subset of SpecialistMatcher.DOMAIN_ALIASES plus a
# few high-precision business terms). Order matters only for readability;
# matching scores by hit count so richer matches win.
DOMAIN_KEYWORDS = {
    "sales": ["crm", "lead", "deal", "pipeline", "opportunity", "prospect",
              "quote", "quota", "cold outreach", "follow-up email"],
    "finance": ["invoice", "billing", "reconciliation", "expense",
                "accounting", "budget", "tax", "payment terms"],
    "marketing": ["campaign", "seo", "ad copy", "newsletter", "social post",
                  "content calendar"],
    "support": ["ticket", "refund", "customer complaint", "helpdesk",
                "sla breach", "escalation"],
    "operations": ["inventory", "fulfillment", "supply order", "logistics",
                   "vendor management", "stock level"],
    "hr": ["payroll", "onboarding checklist", "job description",
           "candidate pipeline", "benefits enrollment"],
}

_WORD = re.compile(r"[a-z0-9-]+")

# Tokens too common to be discriminative when mining learned vocabulary.
_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "update",
    "check", "create", "make", "send", "draft", "review", "manage", "help",
    "please", "about", "after", "before", "schedule", "report", "summary",
    "status", "list", "data", "record", "records", "task", "tasks", "work",
    "email", "customer", "team", "weekly", "daily", "monthly", "today",
}


def build_domain_vocabulary(db, min_docs: int = 3,
                            max_other_ratio: float = 0.2) -> dict:
    """
    Mine DISTINCTIVE role terms from real work history — this is what makes
    roles dynamic. Every business has edge roles ("landscaping",
    "veterinary", "equipment leasing"); a fixed keyword list can never
    attribute them.

    Source pairs (task text -> role):
      - AgentEpisode.task_description via the episode's agent category
      - DomainExperienceLedger.task_summary (already attributed)

    A term enters a role's vocabulary when it appears in >= ``min_docs``
    documents of that role AND <= ``max_other_ratio`` of all other-role
    documents carrying it. Callers should invoke once per execution-recording
    pass, not per token.
    """
    from collections import Counter, defaultdict

    rows = []
    try:
        from core.models import AgentEpisode, AgentRegistry

        rows = (
            db.query(
                AgentRegistry.category,
                AgentEpisode.task_description,
            )
            .join(AgentRegistry, AgentEpisode.agent_id == AgentRegistry.id)
            .filter(AgentEpisode.task_description.isnot(None))
            .all()
        )
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"episode vocabulary source unavailable: {e}")

    docs_by_role: dict[str, Counter] = defaultdict(Counter)
    doc_counts: Counter = Counter()

    def _ingest(role: str, text: str) -> None:
        role_l = (role or "").lower()
        if not role_l or not text:
            return
        doc_counts[role_l] += 1
        seen = set(_WORD.findall(text.lower()))
        docs_by_role[role_l].update(w for w in seen if w not in _STOPWORDS)

    for role, text in rows:
        _ingest(role, text)

    try:
        from core.models import DomainExperienceLedger
        for row in db.query(DomainExperienceLedger).all():
            _ingest(row.domain, row.task_summary or "")
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"ledger vocabulary source unavailable: {e}")

    total_by_role = {r: c for r, c in doc_counts.items()}

    vocabulary: dict[str, list[str]] = {}
    for role, term_counter in docs_by_role.items():
        picked = []
        for term, in_docs in term_counter.items():
            if in_docs < min_docs:
                continue
            other_docs = sum(
                other.get(term, 0)
                for other_role, other in docs_by_role.items()
                if other_role != role
            )
            other_total = sum(n for r, n in total_by_role.items() if r != role)
            if other_total > 0 and (other_docs / other_total) > max_other_ratio:
                continue
            picked.append(term)
            if len(picked) >= 20:
                break
        if picked:
            vocabulary[role] = picked
    return vocabulary


def resolve_domain(text: Optional[str], vocabulary: Optional[dict] = None) -> Optional[str]:
    """
    Best-effort role attribution for a task/request string.

    Matches the static keyword table MERGED with any learned ``vocabulary``
    (build_domain_vocabulary — mined from real work history so edge roles
    attribute without code changes). Scores each domain by distinct hits;
    ties go to the rarer (longer) match. Returns None when nothing matches
    — callers must not guess.
    """
    if not text:
        return None
    merged: dict[str, list[str]] = {
        d: list(kws) for d, kws in DOMAIN_KEYWORDS.items()
    }
    for domain, terms in (vocabulary or {}).items():
        merged.setdefault(domain.lower(), [])
        merged[domain.lower()] = list(set(merged[domain.lower()]) | set(t.lower() for t in terms))

    lower = (text or "").lower()
    words = set(_WORD.findall(lower))
    best_domain: Optional[str] = None
    best_hits = 0
    best_len = 0
    for domain, keywords in merged.items():
        hits = [k for k in keywords if k in words or k in lower]
        if not hits:
            continue
        score = len(hits)
        rarity = max(len(k) for k in hits)
        if score > best_hits or (score == best_hits and rarity > best_len):
            best_domain, best_hits, best_len = domain, score, rarity
    return best_domain


def record_domain_outcome(db, agent_id: str, domain: Optional[str],
                          success: bool, task_summary: str = "") -> bool:
    """
    Append one attributed outcome row. Never raises — the ledger is a
    learning side-channel and must not break execution recording.
    """
    if not domain:
        return False
    try:
        from core.models import DomainExperienceLedger
        db.add(DomainExperienceLedger(
            agent_id=agent_id,
            domain=(domain or "").lower().strip(),
            outcome="success" if success else "failure",
            task_summary=(task_summary or "")[:500],
        ))
        db.commit()
        return True
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"domain ledger write skipped: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False


def count_domain_wins(db, agent_id: str, domain: str) -> int:
    """Verified successes for one agent in one role (the mentor bar).

    Callers pass student CATEGORIES, which are title-cased in the registry
    ("Sales"), while ledger domains are lowercase ("sales") — normalize so
    casing never silently zeroes an earned record.
    """
    try:
        from core.models import DomainExperienceLedger
        domain = (domain or "").lower().strip()
        return db.query(DomainExperienceLedger).filter(
            DomainExperienceLedger.agent_id == agent_id,
            DomainExperienceLedger.domain == domain,
            DomainExperienceLedger.outcome == "success",
        ).count()
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"domain ledger read failed: {e}")
        return 0


def top_domain_cases(db, agent_id: str, domain: str, limit: int = 5):
    """Most recent verified cases for playbook construction."""
    try:
        from core.models import DomainExperienceLedger
        domain = (domain or "").lower().strip()
        return db.query(DomainExperienceLedger).filter(
            DomainExperienceLedger.agent_id == agent_id,
            DomainExperienceLedger.domain == domain,
            DomainExperienceLedger.outcome == "success",
        ).order_by(DomainExperienceLedger.created_at.desc()).limit(limit).all()
    except Exception as e:  # pragma: no cover - defensive
        logger.debug(f"domain ledger case query failed: {e}")
        return []


# Per-process vocabulary cache: mining scans episodes + ledger, and
# attribution now runs on EVERY recorded outcome (the shared
# record_outcome path) — per-run mining would dwarf the write itself.
# 5-minute TTL keeps learned edge roles fresh without the cost.
_VOCAB_CACHE: dict = {"at": 0.0, "vocab": {}}
_VOCAB_TTL_SECONDS = 300.0


def get_vocabulary(db, force_refresh: bool = False) -> dict:
    """Mined role vocabulary with a process-wide TTL.

    Falls back to the empty (static-keyword-only) vocabulary when mining
    fails — attribution then still works for the built-in roles.
    """
    import time as _time

    now = _time.time()
    if not force_refresh and now - _VOCAB_CACHE["at"] < _VOCAB_TTL_SECONDS:
        return _VOCAB_CACHE["vocab"]
    try:
        vocab = build_domain_vocabulary(db)
    except Exception as e:
        logger.debug(f"vocabulary mining failed, using static keywords: {e}")
        vocab = {}
    _VOCAB_CACHE["at"] = now
    _VOCAB_CACHE["vocab"] = vocab
    return vocab
