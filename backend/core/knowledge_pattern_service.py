"""Knowledge pattern store — the WikiSkill wiki layer (W2 + W3).

Google's WikiSkill (arXiv:2608.27454) keeps a persistent, growing wiki
between immutable execution traces and the active skill files:

* ``wiki/patterns/`` — one page per failure mode / successful strategy,
  with root cause + workaround;
* ``wiki/index.md`` — the catalog the Skill Proposer reads first.

This module is the structured equivalent: ``knowledge_patterns`` rows
maintained by the sleep-time loop, consumed by the OFFLINE evolver prompts
via :func:`pattern_index`. The runtime agent never reads the wiki (W4).

Sampling discipline is the paper's: per maintainer cycle, up to
``MAX_FAILING`` failing AND up to ``MAX_PASSING`` passing traces — passing
traces matter as much as failing ones (strategies, not just failures), a
signal every pre-existing Atom learning loop ignored. Traces are capped at
``TRACE_CAP_CHARS`` characters like the paper's 15k.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_FAILING = 5
MAX_PASSING = 3
TRACE_CAP_CHARS = 15000
MAX_PATTERNS_IN_INDEX = 30
_EVIDENCE_CAP = 20
_WINDOW_DAYS = 7
_LLM_PATTERNS_CAP = 6


def pattern_fingerprint(tenant_id: str, kind: str, name: str) -> str:
    return hashlib.sha1(f"{tenant_id}|{kind}|{(name or '')[:200]}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Write side: upsert (the wiki grows — it never stacks duplicates)
# ---------------------------------------------------------------------------

def upsert_pattern(
    db: Any,
    *,
    tenant_id: str,
    name: str,
    kind: str,
    root_cause: str = "",
    workaround: str = "",
    workspace_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
    source: str = "maintainer",
) -> tuple[Any, bool]:
    """Create-or-bump one pattern page. Returns (row, created). Never
    raises — the maintainer is fault-isolated by the sleep-time cycle."""
    from core.models import KnowledgePattern

    if kind not in ("failure_mode", "success_strategy"):
        kind = "failure_mode"
    name = (name or "").strip()[:255]
    if not name:
        raise ValueError("pattern name required")

    fp = pattern_fingerprint(tenant_id, kind, name)
    try:
        row = db.query(KnowledgePattern).filter(
            KnowledgePattern.fingerprint == fp).first()
        created = row is None
        if row is None:
            row = KnowledgePattern(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                name=name,
                kind=kind,
                fingerprint=fp,
                source=source,
            )
            db.add(row)
        # Refresh the page with the newest evidence; occurrence bumps —
        # the wiki layer never resets.
        row.root_cause = (root_cause or row.root_cause or "")[:4000] or row.root_cause
        row.workaround = (workaround or row.workaround or "")[:4000] or row.workaround
        row.workspace_id = row.workspace_id or workspace_id
        row.occurrence_count = (row.occurrence_count or 1) + (0 if created else 1)
        if row.occurrence_count is None:
            row.occurrence_count = 1
        evidence = [e for e in (row.evidence_ids or []) if isinstance(e, str)]
        if evidence_id and evidence_id not in evidence:
            evidence.append(evidence_id)
        row.evidence_ids = evidence[-_EVIDENCE_CAP:]
        row.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        return row, created
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        logger.debug("knowledge pattern upsert skipped: %s", e)
        raise


# ---------------------------------------------------------------------------
# Read side: the index (wiki/index.md analog) — evolver prompts only
# ---------------------------------------------------------------------------

def recent_patterns(db: Any, tenant_id: str, workspace_id: Optional[str] = None,
                    kind: Optional[str] = None,
                    limit: int = MAX_PATTERNS_IN_INDEX) -> List[Any]:
    from core.models import KnowledgePattern

    q = db.query(KnowledgePattern).filter(
        KnowledgePattern.tenant_id == tenant_id,
        KnowledgePattern.status == "active",
    )
    if workspace_id:
        q = q.filter((KnowledgePattern.workspace_id == workspace_id)
                     | (KnowledgePattern.workspace_id.is_(None)))
    if kind:
        q = q.filter(KnowledgePattern.kind == kind)
    return (q.order_by(KnowledgePattern.occurrence_count.desc(),
                       KnowledgePattern.updated_at.desc())
            .limit(limit).all())


def pattern_index(db: Any, tenant_id: str, workspace_id: Optional[str] = None,
                  limit: int = MAX_PATTERNS_IN_INDEX) -> str:
    """Compact catalog for the evolver prompt (the proposer reads the index,
    then pulls patterns on demand — the paper's two-step retrieval)."""
    rows = recent_patterns(db, tenant_id, workspace_id=workspace_id, limit=limit)
    if not rows:
        return ""
    lines = ["KNOWLEDGE PATTERN INDEX — distilled experience (wiki layer):"]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"  {i}. [{r.kind}] {r.name} (seen {r.occurrence_count}x): "
            f"{(r.root_cause or '')[:160]}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Balanced trace sampling (W3)
# ---------------------------------------------------------------------------

def _trace_view(ep: Any) -> Dict[str, Any]:
    """Compact view of one episode trace, capped like the paper's 15k."""
    meta = ep.metadata_json or {}
    tool_errors = meta.get("tool_errors") or []
    error_text = "; ".join(
        f"{te.get('signature', '?')}: {str(te.get('error', ''))[:200]}"
        for te in tool_errors[-3:] if isinstance(te, dict)
    )
    return {
        "episode_id": ep.id,
        "task": (ep.task_description or "")[:500],
        "outcome": ep.outcome or ("success" if ep.success else "failure"),
        "error": error_text[:800],
        "rating": ep.supervisor_rating,
    }


def sample_traces(db: Any, tenant_id: str,
                  max_failing: int = MAX_FAILING,
                  max_passing: int = MAX_PASSING,
                  window_days: int = _WINDOW_DAYS) -> Dict[str, List[Dict[str, Any]]]:
    """The paper's balanced sample: ≤5 failing, ≤3 passing recent traces."""
    from core.models import AgentEpisode

    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    base = db.query(AgentEpisode).filter(
        AgentEpisode.tenant_id == tenant_id,
        AgentEpisode.created_at >= since,
    )

    failing = (
        base.filter(AgentEpisode.success.is_(False))
        .order_by(AgentEpisode.created_at.desc()).limit(max_failing).all()
    )
    passing_q = base.filter(
        AgentEpisode.success.is_(True),
        AgentEpisode.supervisor_rating.isnot(None),
        AgentEpisode.supervisor_rating >= 4,
    )
    passing = passing_q.order_by(AgentEpisode.created_at.desc()).limit(max_passing).all()

    return {
        "failing": [_trace_view(e) for e in failing],
        "passing": [_trace_view(e) for e in passing],
    }


# ---------------------------------------------------------------------------
# The maintainer (Wiki Maintainer analog) — deterministic + LLM paths
# ---------------------------------------------------------------------------

async def distill_from_traces(
    db: Any,
    tenant_id: str,
    workspace_id: Optional[str] = None,
    llm_service: Any = None,
    max_failing: int = MAX_FAILING,
    max_passing: int = MAX_PASSING,
) -> Dict[str, Any]:
    """One Wiki-Maintainer iteration for a tenant. Tries the LLM path on the
    balanced sample; falls back to deterministic distillation from incident
    evals + tool-error signatures when no LLM is reachable (CI / air-gapped
    installs still accumulate wiki). Returns a summary for the cycle log."""
    summary: Dict[str, Any] = {"created": 0, "bumped": 0, "mode": "deterministic"}
    traces = sample_traces(db, tenant_id, max_failing=max_failing,
                           max_passing=max_passing)

    if llm_service is not None:
        try:
            llm_summary = await _distill_with_llm(
                db, tenant_id, workspace_id, llm_service, traces)
            summary.update(llm_summary)
            summary["mode"] = "llm"
        except Exception as e:
            logger.debug("pattern maintainer LLM path failed (%s); deterministic", e)

    if summary["created"] == 0 and summary["bumped"] == 0:
        det = _distill_deterministic(db, tenant_id, workspace_id, traces)
        summary["created"] += det["created"]
        summary["bumped"] += det["bumped"]
    return summary


async def _distill_with_llm(db: Any, tenant_id: str, workspace_id: Optional[str],
                            llm_service: Any, traces: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    system = (
        "You are the Wiki Maintainer. Analyze the execution traces and distill "
        "durable knowledge: FAILURE MODES (root cause + actionable workaround) "
        "from failing tasks and SUCCESS STRATEGIES from passing tasks. "
        "Respond ONLY with JSON: {\"patterns\": [{\"name\": str, \"kind\": "
        "\"failure_mode\"|\"success_strategy\", \"root_cause\": str, "
        "\"workaround\": str, \"evidence\": str}]}. Max 6 patterns; prefer "
        "updating recurring themes over trivia."
    )
    sample_text = json.dumps(traces)[:TRACE_CAP_CHARS]
    response = await llm_service.generate_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Traces:\n{sample_text}"},
        ],
        model="auto",
        task_type="analysis",
    )
    content = (response or {}).get("content", "")
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        return {"created": 0, "bumped": 0}
    data = json.loads(content[start:end + 1])

    created = bumped = 0
    for p in (data.get("patterns") or [])[:_LLM_PATTERNS_CAP]:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        try:
            _, was_created = upsert_pattern(
                db, tenant_id=tenant_id, workspace_id=workspace_id,
                name=str(p.get("name"))[:255],
                kind=str(p.get("kind") or "failure_mode"),
                root_cause=str(p.get("root_cause") or "")[:4000],
                workaround=str(p.get("workaround") or "")[:4000],
                evidence_id=(p.get("evidence") or None),
                source="maintainer",
            )
        except Exception:
            continue
        if was_created:
            created += 1
        else:
            bumped += 1
    return {"created": created, "bumped": bumped}


def _distill_deterministic(db: Any, tenant_id: str, workspace_id: Optional[str],
                           traces: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """No-LLM wiki accumulation: failure modes from tool-error signatures in
    the sampled failing traces, success strategies from highly-rated passing
    traces. Deliberately conservative — deterministic text must be factual."""
    created = bumped = 0
    for t in traces.get("failing", []):
        if not t.get("error"):
            continue
        sig = t["error"].split(":")[0].strip()[:120] or "unknown tool error"
        try:
            _, was_created = upsert_pattern(
                db, tenant_id=tenant_id, workspace_id=workspace_id,
                name=f"Tool failures — {sig}",
                kind="failure_mode",
                root_cause=t["error"][:1000],
                workaround="Check the tool's input contract and the recorded "
                           "error before retrying the same call shape.",
                evidence_id=t.get("episode_id"),
                source="trace",
            )
            created += 1 if was_created else 0
            bumped += 0 if was_created else 1
        except Exception:
            continue
    for t in traces.get("passing", []):
        topic = (t.get("task") or "")[:120]
        if not topic:
            continue
        try:
            _, was_created = upsert_pattern(
                db, tenant_id=tenant_id, workspace_id=workspace_id,
                name=f"Effective approach — {topic[:100]}",
                kind="success_strategy",
                root_cause=f"Supervisor-rated {t.get('rating')}/5 approach for: {topic}",
                workaround="",
                evidence_id=t.get("episode_id"),
                source="trace",
            )
            created += 1 if was_created else 0
            bumped += 0 if was_created else 1
        except Exception:
            continue
    return {"created": created, "bumped": bumped}
