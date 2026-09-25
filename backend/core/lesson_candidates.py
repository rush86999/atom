"""Versioned, gated candidates for reusable capability lessons."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Dict, List, Mapping, Optional

from core.feedback_classifier import KIND_STRATEGY, classify_feedback

CANDIDATE_VERSION = 1
STATES = ("shadow", "eval", "limited", "active", "rejected", "rolled_back")
_TRANSITIONS = {
    "shadow": {"eval", "rejected"},
    "eval": {"limited", "rejected", "rolled_back"},
    "limited": {"active", "eval", "rejected", "rolled_back"},
    "active": {"rolled_back", "rejected"},
    "rejected": {"shadow"},
    "rolled_back": {"shadow"},
}
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "min_goal_completion_gain": 0.05,
    "max_unsupported_claims_regression": 0.0,
    "max_unnecessary_clarification_regression": 0.02,
    "max_repeated_retrieval_regression": 0.1,
    "max_latency_p90_regression_pct": 15.0,
    "max_domain_goal_regression": 0.0,
    "min_samples_per_domain": 20.0,
}

PILOT_RESUMPTION_LESSON: Dict[str, Any] = {
    "candidate_id": "lesson-confirmed-source-resumption-001",
    "experimental_claim": (
        "EXPERIMENT SCOPE (2026-09-24 review): this pilot tests a "
        "CONFIGURABLE WAIT-POLICY intervention (resume-turn planner wait "
        "cap) through the learning loop's plumbing — NOT the "
        "effectiveness of the generalized learning process. Demonstrating "
        "the broader process requires tracing feedback -> candidate -> "
        "evaluation -> approved behavior -> verified improvement, which "
        "awaits the frozen evaluation."),
    "runtime_overrides": {
        "resume_planner_wait_max_seconds": 55.0,
    },
    "version": CANDIDATE_VERSION,
    "state": "shadow",
    "title": "A confirmed source identity resumes an unresolved lookup",
    "preconditions": [
        "a prior turn requested a scoped retrieval from a named source",
        "the retrieval did not complete",
        "the current turn confirms the source identity or approves the read",
    ],
    "applicability": {
        "domains": "any",
        "capabilities": [
            "clarification and task resumption",
            "source resolution and coverage",
            "retry, restart, and delivery recovery",
        ],
        "model_scope": "all",
    },
    "expected_behavioral_change": (
        "execute the confirmed scoped read directly and deliver its "
        "deterministic structured result"
    ),
    "observable_metrics": [
        "goal_completion_rate",
        "unnecessary_clarification_rate",
        "repeated_retrieval_count",
        "unsupported_claims",
        "latency_p90",
    ],
    "supporting_examples": [
        {
            "domain": "source-scoped retrieval",
            "scenario": "read a confirmed source after an interrupted lookup",
            "outcome": "a deterministic result with provenance",
        }
    ],
    "counter_examples": [
        {
            "scenario": "a new substantive request supersedes the stored one",
            "must_not_apply": True,
        },
        {
            "scenario": "a result was already delivered",
            "must_not_apply": True,
        },
    ],
    "rationale": "The lesson concerns recovery mechanics rather than a business workflow.",
    "expiry": {
        "revalidate_after_outcomes": 500,
        "expires_if": "held-out goal completion regresses",
    },
    "rollback_reference": "disable only the candidate's scoped intervention",
    "evidence_refs": [],
    "policy_version": "learning-loop-v1",
}


def _copy_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(dict(candidate))
    result.setdefault("version", CANDIDATE_VERSION)
    result.setdefault("state", "shadow")
    result.setdefault("candidate_id", "lesson-unknown")
    result.setdefault("title", "")
    result.setdefault("applicability", {"domains": "any", "capabilities": []})
    result.setdefault("evidence_refs", [])
    result.setdefault("scope", {})
    return result


def _redact_lesson_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"https?://\S+", "<source>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[\w./\\-]+\.(?:xlsx|xls|csv|tsv|pdf|docx?)\b", "<file>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "<contact>", text)
    text = re.sub(r"[$€£]\s?[\d,.]+|\b\d+(?:\.\d+)?\b", "<value>", text)
    text = re.sub(r"[\"“][^\"”\n]+[\"”]", "<source_quote>", text)
    return re.sub(r"\s+", " ", text).strip()[:500]


def extract_lesson_candidate(
    text: str,
    *,
    evidence_refs: Optional[List[Dict[str, Any]]] = None,
    scope: Optional[Dict[str, Any]] = None,
    candidate_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a shadow candidate only from an explicit strategy request."""
    classification = classify_feedback(text)
    if classification.get("kind") != KIND_STRATEGY:
        return None
    instruction = _redact_lesson_text(text)
    identifier = candidate_id or "lesson-feedback-" + hashlib.sha256(
        instruction.encode("utf-8")
    ).hexdigest()[:16]
    return {
        "candidate_id": identifier,
        "version": CANDIDATE_VERSION,
        "state": "shadow",
        "title": "A user-requested strategy improvement",
        "preconditions": ["the stated verification step is relevant to the task"],
        "applicability": {
            "domains": "any",
            "capabilities": ["task execution and verification"],
            "model_scope": "all",
        },
        "expected_behavioral_change": (
            "apply the explicitly requested verification step before "
            "answering when its precondition is present"
        ),
        "strategy_fingerprint": hashlib.sha256(
            instruction.encode("utf-8")
        ).hexdigest(),
        "observable_metrics": [
            "goal_completion",
            "unsupported_claims",
            "unnecessary_clarification",
            "repeated_retrieval",
            "latency_p90",
        ],
        "supporting_examples": [],
        "counter_examples": [{"scenario": "a new or unrelated task", "must_not_apply": True}],
        "rationale": "Extracted from an explicit strategy request; business facts stay in evidence.",
        "evidence_refs": list(evidence_refs or []),
        "scope": dict(scope or {}),
        "policy_version": "learning-loop-v1",
    }


def _event(
    db: Any,
    candidate: Mapping[str, Any],
    *,
    stage: str,
    reason: str,
    actor_id: Optional[str],
) -> Optional[str]:
    from core.auto_dev.skill_impact_ledger import record_outcome

    result = record_outcome(
        db,
        tenant_id=str((candidate.get("scope") or {}).get("tenant_id") or "default"),
        agent_id=(candidate.get("scope") or {}).get("agent_id"),
        target=f"lesson:{candidate.get('candidate_id')}",
        source="learning_loop",
        status="accepted",
        stage=stage,
        reason=reason,
        proposal_summary=str(candidate.get("title") or "")[:500],
        payload={
            "candidate": copy.deepcopy(dict(candidate)),
            "actor_id": actor_id,
            "event": "candidate_state",
        },
    )
    return str(result) if result else None


def register_candidate(
    candidate: Dict[str, Any],
    *,
    actor_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
    db: Any = None,
) -> bool:
    """Record a new candidate in shadow state without changing behavior."""
    item = _copy_candidate(candidate)
    if item.get("state") != "shadow":
        return False
    if scope:
        item["scope"] = dict(scope)
    if not item.get("candidate_id") or item["candidate_id"] == "lesson-unknown":
        return False
    try:
        if db is None:
            from core.database import get_db_session

            with get_db_session() as session:
                return bool(_event(session, item, stage="shadow", reason="candidate registered in shadow", actor_id=actor_id))
        return bool(_event(db, item, stage="shadow", reason="candidate registered in shadow", actor_id=actor_id))
    except Exception:
        return False


def transition_candidate(
    candidate: Dict[str, Any],
    target_state: str,
    *,
    actor_id: Optional[str] = None,
    evaluation: Optional[Dict[str, Any]] = None,
    reason: str = "",
    db: Any = None,
) -> Optional[Dict[str, Any]]:
    """Apply a validated, versioned lifecycle transition."""
    current = _copy_candidate(candidate)
    current_state = str(current.get("state") or "shadow")
    target = str(target_state or "")
    if target not in STATES or target not in _TRANSITIONS.get(current_state, set()):
        return None
    if target in {"limited", "active"}:
        if (
            not actor_id
            or not evaluation
            or not evaluation.get("promote")
            or not evaluation.get("threshold_hash")
        ):
            return None
    updated = copy.deepcopy(current)
    updated["parent_version"] = current.get("version", CANDIDATE_VERSION)
    updated["version"] = int(current.get("version") or CANDIDATE_VERSION) + 1
    updated["state"] = target
    updated["policy_version"] = current.get("policy_version") or "learning-loop-v1"
    updated["last_transition"] = {
        "actor_id": actor_id,
        "reason": reason[:500],
        "evaluation": copy.deepcopy(evaluation) if evaluation else None,
    }
    try:
        if db is None:
            from core.database import get_db_session

            with get_db_session() as session:
                if not _event(session, updated, stage=target, reason=reason or "lifecycle transition", actor_id=actor_id):
                    return None
        elif not _event(db, updated, stage=target, reason=reason or "lifecycle transition", actor_id=actor_id):
            return None
        return updated
    except Exception:
        return None


def promote_candidate(
    candidate: Dict[str, Any],
    evaluation: Dict[str, Any],
    *,
    actor_id: str,
    reason: str = "held-out evaluation passed",
    db: Any = None,
) -> Optional[Dict[str, Any]]:
    """Promote only through a signed, threshold-bound evaluation."""
    if not evaluation.get("promote") or not evaluation.get("threshold_hash"):
        return None
    return transition_candidate(
        candidate,
        "active",
        actor_id=actor_id,
        evaluation=evaluation,
        reason=reason,
        db=db,
    )


def rollback_candidate(
    candidate: Dict[str, Any],
    *,
    actor_id: Optional[str] = None,
    reason: str,
    db: Any = None,
) -> Optional[Dict[str, Any]]:
    """Roll back a candidate while leaving safety mechanisms enabled."""
    if not actor_id or not reason.strip():
        return None
    return transition_candidate(
        candidate,
        "rolled_back",
        actor_id=actor_id,
        reason=reason,
        db=db,
    )


def _stored_candidate(db: Any, candidate_id: str) -> Optional[Dict[str, Any]]:
    try:
        from core.auto_dev.models import SkillImpactEntry

        rows = (
            db.query(SkillImpactEntry)
            .filter(SkillImpactEntry.target == f"lesson:{candidate_id}")
            .order_by(SkillImpactEntry.created_at.desc())
            .limit(50)
            .all()
        )
        for row in rows or []:
            payload = row.payload if isinstance(row.payload, dict) else {}
            candidate = payload.get("candidate")
            if isinstance(candidate, dict):
                return _copy_candidate(candidate)
    except Exception:
        return None
    return None


def load_candidate(candidate_id: str, *, db: Any = None) -> Optional[Dict[str, Any]]:
    """Load the latest durable lifecycle snapshot for a candidate."""
    if candidate_id == PILOT_RESUMPTION_LESSON.get("candidate_id"):
        return copy.deepcopy(PILOT_RESUMPTION_LESSON)
    try:
        if db is None:
            from core.database import get_db_session

            with get_db_session() as session:
                return _stored_candidate(session, candidate_id)
        return _stored_candidate(db, candidate_id)
    except Exception:
        return None


def all_candidates(*, db: Any = None) -> List[Dict[str, Any]]:
    """Return built-in and durable candidates without activating them."""
    candidates = [copy.deepcopy(PILOT_RESUMPTION_LESSON)]
    if db is None:
        return candidates
    try:
        from core.auto_dev.models import SkillImpactEntry

        rows = (
            db.query(SkillImpactEntry)
            .filter(SkillImpactEntry.target.like("lesson:%"))
            .order_by(SkillImpactEntry.created_at.desc())
            .limit(200)
            .all()
        )
        seen = {str(item.get("candidate_id")) for item in candidates}
        for row in rows or []:
            payload = row.payload if isinstance(row.payload, dict) else {}
            candidate = payload.get("candidate")
            if not isinstance(candidate, dict):
                continue
            identifier = str(candidate.get("candidate_id") or "")
            if identifier and identifier not in seen:
                candidates.append(_copy_candidate(candidate))
                seen.add(identifier)
    except Exception:
        return candidates
    return candidates


def _threshold_hash(thresholds: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(thresholds), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _number(mapping: Mapping[str, Any], key: str) -> Optional[float]:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _domain_metrics(mapping: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    domains = mapping.get("domains")
    if isinstance(domains, dict):
        return {str(name): value for name, value in domains.items() if isinstance(value, dict)}
    return {"overall": dict(mapping)}


def evaluate_promotion_gate(
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Fail closed unless held-out metrics show lift without guard regressions."""
    effective = dict(DEFAULT_THRESHOLDS)
    reasons: List[str] = []
    for key, value in (thresholds or {}).items():
        if key not in DEFAULT_THRESHOLDS:
            reasons.append(f"unknown_threshold:{key}")
            continue
        if key.startswith("min_") and value < DEFAULT_THRESHOLDS[key]:
            reasons.append(f"threshold_loosened:{key}")
        elif key.startswith("max_") and value > DEFAULT_THRESHOLDS[key]:
            reasons.append(f"threshold_loosened:{key}")
        effective[key] = value

    required = (
        "goal_completion",
        "unsupported_claims",
        "unnecessary_clarification",
        "repeated_retrieval",
        "latency_p90",
        "sample_count",
    )
    missing: List[str] = []
    baseline_domains = _domain_metrics(baseline)
    candidate_domains = _domain_metrics(candidate)
    for name, metrics in (("baseline", baseline), ("candidate", candidate)):
        for key in required:
            if _number(metrics, key) is None:
                missing.append(f"{name}.{key}")
    if missing:
        reasons.append("missing_metrics")

    baseline_goal = _number(baseline, "goal_completion")
    candidate_goal = _number(candidate, "goal_completion")
    gain = None if baseline_goal is None or candidate_goal is None else candidate_goal - baseline_goal
    if gain is None or gain < effective["min_goal_completion_gain"]:
        reasons.append("insufficient_goal_completion_gain")

    domain_regressions: List[str] = []
    for domain in sorted(set(baseline_domains) | set(candidate_domains)):
        base = baseline_domains.get(domain, {})
        cand = candidate_domains.get(domain, {})
        sample_count = _number(cand, "sample_count")
        if sample_count is None or sample_count < effective["min_samples_per_domain"]:
            reasons.append(f"insufficient_samples:{domain}")
        for key in (
            "unsupported_claims",
            "unnecessary_clarification",
            "repeated_retrieval",
        ):
            base_value = _number(base, key)
            cand_value = _number(cand, key)
            if base_value is None or cand_value is None:
                reasons.append(f"missing_domain_metric:{domain}.{key}")
            elif cand_value > base_value + effective[f"max_{key}_regression"]:
                domain_regressions.append(f"{domain}.{key}")
        base_goal = _number(base, "goal_completion")
        cand_goal = _number(cand, "goal_completion")
        if base_goal is None or cand_goal is None:
            reasons.append(f"missing_domain_metric:{domain}.goal_completion")
        elif cand_goal < base_goal - effective["max_domain_goal_regression"]:
            domain_regressions.append(f"{domain}.goal_completion")
    reasons.extend(f"domain_regression:{item}" for item in domain_regressions)

    result = {
        "promote": not reasons,
        "goal_completion_gain": None if gain is None else round(gain, 6),
        "guards_pass": not reasons,
        "reasons": sorted(set(reasons)),
        "missing_metrics": sorted(set(missing)),
        "thresholds": effective,
        "threshold_hash": _threshold_hash(effective),
        "baseline_domains": sorted(baseline_domains),
        "candidate_domains": sorted(candidate_domains),
    }
    return result
