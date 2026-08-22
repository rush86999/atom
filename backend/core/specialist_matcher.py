"""
Specialist Matcher — matches task domains to ranked specialist agents.

P1b (W4): replaces the previous self-declared stub (which returned ``[]`` and
lacked the three symbols ``RecruitmentIntelligenceService`` calls on it —
``find_specialists_for_domains``, ``get_all_available_domains``,
``DOMAIN_ALIASES`` — so the wired fleet path would have raised AttributeError).

Scoring metric (explicit, weights sum to 1.0):

    score = 0.40 * capability_overlap(required_keywords, agent.capabilities)
          + 0.25 * tier_floor_weight(agent.status)            # AUTONOMOUS=1.0 ... STUDENT=0.3
          + 0.20 * verified_episode_ratio(agent.id)           # AgentEpisode verified/total
          + 0.10 * confidence_score(agent.confidence_score)
          + 0.05 * recency_bonus(agent.last_request_date)

Scorable fields (verified on AgentRegistry, models.py:1417-1507):
``category`` (:1426), ``capabilities`` (:1431), ``status`` (:1444),
``confidence_score`` (:1445), ``self_healed_count`` (:1447),
``last_request_date`` (:1482). NOTE: ``last_active_at`` (:816) belongs to
``UserSession``, not ``AgentRegistry`` — do not use it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Canonical domain → keyword map. Keys mirror RecruitmentIntelligenceService.AVAILABLE_DOMAINS
# (recruitment_intelligence_service.py:66). Aliases are the capability strings
# an AgentRegistry row would list for that domain.
DOMAIN_ALIASES: Dict[str, List[str]] = {
    "finance": ["budget", "cost", "invoice", "reconciliation", "expense", "accounting", "tax"],
    "sales": ["crm", "lead", "deal", "pipeline", "opportunity", "revenue"],
    "marketing": ["campaign", "ad", "content", "seo", "social", "brand"],
    "operations": ["logistics", "supply", "inventory", "fulfillment", "workflow"],
    "legal": ["contract", "compliance", "policy", "regulation", "litigation"],
    "engineering": ["code", "build", "deploy", "architecture", "infrastructure", "cicd"],
    "hr": ["hiring", "payroll", "onboarding", "benefits", "recruiting"],
    "procurement": ["vendor", "purchase", "sourcing", "po", "rfq"],
    "communications": ["pr", "press", "email", "messaging", "notification"],
    "intelligence": ["analytics", "reporting", "forecast", "insight", "dashboard"],
}

# Tier floor weights (0.25 term). AUTONOMOUS agents are the most eligible;
# STUDENT the least. Matches AgentStatus (models.py) progression.
_TIER_WEIGHTS: Dict[str, float] = {
    "autonomous": 1.0,
    "supervised": 0.8,
    "intern": 0.55,
    "student": 0.3,
}

# Metric weights (sum to 1.0).
_W_OVERLAP = 0.40
_W_TIER = 0.25
_W_EPISODE = 0.20
_W_CONFIDENCE = 0.10
_W_RECENCY = 0.05

_RECENCY_WINDOW_DAYS = 30  # full recency bonus if active within this window


def _tier_floor_weight(status: Optional[str]) -> float:
    if not status:
        return _TIER_WEIGHTS["student"]
    return _TIER_WEIGHTS.get(status.lower(), _TIER_WEIGHTS["student"])


def _capability_overlap(required: List[str], capabilities: Any) -> float:
    """Fraction of required keywords present in the agent's capabilities (0.0–1.0)."""
    if not required:
        return 0.0
    caps_lower = set()
    if isinstance(capabilities, list):
        caps_lower = {str(c).lower() for c in capabilities if c}
    elif isinstance(capabilities, str):
        caps_lower = {capabilities.lower()}
    required_lower = {r.lower() for r in required}
    if not required_lower:
        return 0.0
    return len(required_lower & caps_lower) / len(required_lower)


def _recency_bonus(last_request_date: Optional[datetime]) -> float:
    """1.0 if active within the window, decaying toward 0.0 afterward."""
    if not last_request_date:
        return 0.0
    if isinstance(last_request_date, str):
        try:
            last_request_date = datetime.fromisoformat(last_request_date.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return 0.0
    now = datetime.now(last_request_date.tzinfo) if last_request_date.tzinfo else datetime.now()
    days = (now - last_request_date).days
    if days <= 0:
        return 1.0
    if days >= _RECENCY_WINDOW_DAYS:
        return 0.0
    return 1.0 - (days / _RECENCY_WINDOW_DAYS)


def _verified_episode_ratio(db: Session, agent_id: str) -> float:
    """Fraction of an agent's episodes whose execution carries at least one
    outcome-verified reasoning step (0.0–1.0).

    Uses the real tri-state ``AgentReasoningStep.verified`` flag
    (models.py:1056, written by tool_outcome_verifier) instead of a
    ``confidence_score >= 0.8`` proxy — high-confidence self-reports without
    external verification must not count (graduation policy, R35).

    Defensive: if the tables aren't available, returns 0.5 (neutral) so the
    term neither rewards nor penalizes an unknown agent.
    """
    try:
        from core.models import AgentEpisode, AgentReasoningStep  # local import to avoid cycles
    except Exception:
        return 0.5
    try:
        total = db.query(AgentEpisode).filter(AgentEpisode.agent_id == agent_id).count()
        if total == 0:
            return 0.5  # neutral — no evidence either way
        verified = (
            db.query(AgentEpisode)
            .join(
                AgentReasoningStep,
                AgentReasoningStep.execution_id == AgentEpisode.execution_id,
            )
            .filter(AgentEpisode.agent_id == agent_id)
            .filter(AgentReasoningStep.verified == "verified")
            .distinct()
            .count()
        )
        return verified / total
    except Exception:
        return 0.5


class SpecialistMatcher:
    """Rank specialist agents for task domains using an explicit metric."""

    # Exposed as a class attribute so RecruitmentIntelligenceService can read
    # matcher.DOMAIN_ALIASES (recruitment_intelligence_service.py:195).
    DOMAIN_ALIASES = DOMAIN_ALIASES

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # New API (used by RecruitmentIntelligenceService)
    # ------------------------------------------------------------------
    def get_all_available_domains(self, user_id: Optional[str] = None) -> List[str]:
        """Return the distinct agent categories present in the registry."""
        try:
            from core.models import AgentRegistry
        except Exception:
            return list(DOMAIN_ALIASES.keys())
        try:
            rows = (
                self.db.query(AgentRegistry.category)
                .filter(AgentRegistry.enabled.is_(True))
                .distinct()
                .all()
            )
            return [r[0] for r in rows if r[0]]
        except Exception:
            return list(DOMAIN_ALIASES.keys())

    def find_specialists_for_domains(
        self,
        domains: List[str],
        user_id: Optional[str] = None,
        limit_per_domain: int = 3,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Return ranked specialist candidates keyed by domain.

        Each candidate dict carries the roster-shape fields
        RecruitmentIntelligenceService reads (agent_id, name, capability_score).
        """
        try:
            from core.models import AgentRegistry
        except Exception:
            return {d: [] for d in domains}

        results: Dict[str, List[Dict[str, Any]]] = {}
        for domain in domains:
            keywords = [domain] + DOMAIN_ALIASES.get(domain.lower(), [])
            try:
                agents = (
                    self.db.query(AgentRegistry)
                    .filter(AgentRegistry.enabled.is_(True))
                    .filter(AgentRegistry.category.ilike(f"%{domain}%"))
                    .all()
                )
            except Exception:
                agents = []

            scored: List[Dict[str, Any]] = []
            for ag in agents:
                overlap = _capability_overlap(keywords, getattr(ag, "capabilities", []) or [])
                tier_w = _tier_floor_weight(getattr(ag, "status", None))
                episode = _verified_episode_ratio(self.db, ag.id)
                confidence = float(getattr(ag, "confidence_score", 0.5) or 0.5)
                recency = _recency_bonus(getattr(ag, "last_request_date", None))
                # P3 skill-scoped trust (flag OFF → exact legacy behavior):
                # replaces the global-confidence term with a per-domain
                # shrunk posterior over the agent's verified capability
                # stats (laundering-capped borrowing via DOMAIN_ALIASES).
                trust_term: Optional[float] = None
                try:
                    from core.skill_scoped_trust import (
                        confidence_term,
                        skill_scoped_trust_enabled,
                    )

                    if skill_scoped_trust_enabled():
                        trust_term = confidence_term(ag, domain)
                except Exception as te:
                    logger.debug(f"skill-scoped trust skipped for {ag.id}: {te}")
                conf_component = (
                    trust_term if trust_term is not None else confidence
                )
                score = (
                    _W_OVERLAP * overlap
                    + _W_TIER * tier_w
                    + _W_EPISODE * episode
                    + _W_CONFIDENCE * conf_component
                    + _W_RECENCY * recency
                )
                entry = {
                    "agent_id": ag.id,
                    "name": getattr(ag, "name", ag.id),
                    "category": getattr(ag, "category", domain),
                    "capability_score": round(score, 4),
                    "overlap": round(overlap, 4),
                    "tier": getattr(ag, "status", None),
                    "confidence": confidence,
                }
                if trust_term is not None:
                    entry["trust"] = trust_term
                scored.append(entry)
            # Rank highest score first.
            scored.sort(key=lambda m: m["capability_score"], reverse=True)
            results[domain] = scored[:limit_per_domain]
        return results

    # ------------------------------------------------------------------
    # Backward-compatible API (pre-existing methods kept working)
    # ------------------------------------------------------------------
    def match_specialists(
        self, required_capabilities: List[str], count: int = 1
    ) -> List[Dict[str, Any]]:
        """Match specialists by capability overlap (legacy entry point)."""
        try:
            from core.models import AgentRegistry
        except Exception:
            return []
        try:
            agents = (
                self.db.query(AgentRegistry)
                .filter(AgentRegistry.enabled.is_(True))
                .all()
            )
        except Exception:
            return []
        scored: List[Dict[str, Any]] = []
        for ag in agents:
            overlap = _capability_overlap(required_capabilities, getattr(ag, "capabilities", []) or [])
            confidence = float(getattr(ag, "confidence_score", 0.5) or 0.5)
            scored.append({
                "agent_id": ag.id,
                "name": getattr(ag, "name", ag.id),
                "capability_score": round(0.6 * overlap + 0.4 * confidence, 4),
            })
        scored.sort(key=lambda m: m["capability_score"], reverse=True)
        return scored[:count]

    def analyze_domain_requirements(self, task_description: str) -> Dict[str, Any]:
        """Heuristic domain analysis from task text (legacy entry point)."""
        text = (task_description or "").lower()
        required: List[str] = []
        for domain, keywords in DOMAIN_ALIASES.items():
            if any(kw in text for kw in keywords) or domain in text:
                required.append(domain)
        if not required:
            required = [list(DOMAIN_ALIASES.keys())[0]]
        complexity = "high" if len(required) >= 3 else ("medium" if len(required) == 2 else "low")
        return {
            "required_domains": required,
            "complexity": complexity,
            "specialist_count": min(len(required), 5),
        }
