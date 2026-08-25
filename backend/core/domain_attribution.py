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


def resolve_domain(text: Optional[str]) -> Optional[str]:
    """
    Best-effort role attribution for a task/request string.

    Scores each domain by distinct keyword hits and requires at least one
    hit; ties go to the domain with the rarer (longest) matched keyword.
    Returns None for unattributable work — callers must not guess.
    """
    if not text:
        return None
    words = set(_WORD.findall((text or "").lower()))
    best_domain: Optional[str] = None
    best_hits = 0
    best_len = 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = [k for k in keywords if k in words or k in (text or "").lower()]
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
