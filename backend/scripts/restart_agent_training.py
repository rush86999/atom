"""Restart an agent's training — convert-then-wipe, per the Installation
Adaptation Plan runbook (docs/architecture/INSTALLATION_ADAPTATION_PLAN.md).

The problem this solves: training data accumulated while the platform had
known failure modes (false-success edits, guessed identity, unverified
claims) pollutes the agent's lessons and RLHF signal. A restart moves the
DURABLE knowledge out (incident evals + playbook drafts, which the
supervisor approves once) and wipes the PER-AGENT learned state, so the
agent relearns on a clean slate while the installation keeps its knowledge.

Steps
  1. BACKUP  every affected row to data/agent_training_backup_<id>_<ts>.json
  2. CONVERT each canvas correction → incident_eval (deduped) +
             correction_reflection draft playbook (deduped, needs approval)
  3. WIPE    agent_feedback rows, canvas user_corrections, the permanent
             lesson log (registry.configuration.learning.log), the
             agent_learning aggregate, and resets confidence to 0.5

Usage:
  python scripts/restart_agent_training.py --agent-id <uuid> [--convert-only] [--yes]

Skips the wipe unless --yes is given; conversion is always safe (it only
adds deduplicated rows).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("restart_training")


def backup(db, agent_id: str) -> Path:
    from core.models import AgentFeedback, CanvasContext

    out = {
        "agent_id": agent_id,
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "agent_feedback": [
            {"id": r.id, "feedback_type": r.feedback_type,
             "original_output": r.original_output,
             "user_correction": r.user_correction,
             "input_context": r.input_context}
            for r in db.query(AgentFeedback).filter(
                AgentFeedback.agent_id == agent_id).all()
        ],
        "canvas_contexts": [
            {"canvas_id": c.canvas_id, "canvas_type": c.canvas_type,
             "user_corrections": c.user_corrections or []}
            for c in db.query(CanvasContext).filter(
                CanvasContext.agent_id == agent_id).all()
        ],
    }
    agent = _agent(db, agent_id)
    config = agent.configuration if agent else {}
    learning = config.get("learning") if isinstance(config, dict) else None
    out["agent_learning_log"] = (learning or {}).get("log") if isinstance(learning, dict) else None
    out["confidence_score"] = getattr(agent, "confidence_score", None)

    path = (Path(__file__).resolve().parent.parent / "data" /
            f"agent_training_backup_{agent_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    path.write_text(json.dumps(out, indent=2, default=str))
    return path


def _agent(db, agent_id: str):
    from core.models import AgentRegistry
    return db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()


def convert(db, agent_id: str) -> Dict[str, int]:
    """Correction → incident_eval + reflection draft playbook."""
    from core.correction_reflection_service import reflect_on_correction
    from core.failure_taxonomy import classify_correction
    from core.incident_eval_service import generate_from_correction
    from core.models import CanvasContext

    stats = {"corrections": 0, "evals": 0, "reflections": 0}
    contexts = db.query(CanvasContext).filter(
        CanvasContext.agent_id == agent_id).all()
    for ctx in contexts:
        for entry in ctx.user_corrections or []:
            original = (entry.get("original") or {}).get("content")
            corrected = (entry.get("corrected") or {}).get("content")
            if original is None or corrected is None:
                continue
            stats["corrections"] += 1
            label, _sig = classify_correction(original, corrected)
            before_count = _eval_count(db, agent_tenant(db, agent_id))
            generate_from_correction(
                db, agent_tenant(db, agent_id), ctx.canvas_id,
                ctx.canvas_type, snapshot={"canvas_type": ctx.canvas_type,
                                           "title": None,
                                           "content": original},
                original=original, corrected=corrected,
                instruction=entry.get("context"))
            if _eval_count(db, agent_tenant(db, agent_id)) > before_count:
                stats["evals"] += 1
            row = reflect_on_correction(
                db, agent_tenant(db, agent_id), ctx.canvas_id,
                ctx.canvas_type, original, corrected, label,
                instruction=entry.get("context"))
            if row is not None:
                stats["reflections"] += 1
    db.commit()
    return stats


def _eval_count(db, tenant_id: str) -> int:
    from core.models import IncidentEval
    return db.query(IncidentEval).filter(
        IncidentEval.tenant_id == tenant_id).count()


def agent_tenant(db, agent_id: str) -> str:
    agent = _agent(db, agent_id)
    return getattr(agent, "tenant_id", None) or "default"


def wipe(db, agent_id: str) -> Dict[str, int]:
    from core.models import AgentFeedback, CanvasContext

    deleted_feedback = db.query(AgentFeedback).filter(
        AgentFeedback.agent_id == agent_id).delete()

    cleared_contexts = 0
    for ctx in db.query(CanvasContext).filter(
            CanvasContext.agent_id == agent_id).all():
        ctx.user_corrections = []
        cleared_contexts += 1

    agent = _agent(db, agent_id)
    config = agent.configuration if isinstance(agent.configuration, dict) else {}
    learning = config.get("learning")
    log_len = 0
    if isinstance(learning, dict):
        log_len = len(learning.get("log") or [])
        # Fresh dicts (not in-place mutation): SQLAlchemy only flushes a
        # JSON column when the assigned object's identity/content changes.
        config = {**config, "learning": {**learning, "log": []}}
        agent.configuration = config
    if agent is not None and agent.confidence_score is not None:
        agent.confidence_score = 0.5
    if agent is not None:
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(agent, "configuration")

    from core.models import AgentLearning
    reset_aggregates = db.query(AgentLearning).filter(
        AgentLearning.agent_id == agent_id).update({
            "total_feedback": 0, "positive_feedback": 0,
            "negative_feedback": 0, "avg_rating": None,
        })

    db.commit()
    return {"feedback_deleted": deleted_feedback,
            "contexts_cleared": cleared_contexts,
            "lessons_cleared": log_len,
            "aggregate_rows_reset": reset_aggregates}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--convert-only", action="store_true",
                        help="run the conversion without wiping")
    parser.add_argument("--yes", action="store_true",
                        help="required to perform the destructive wipe")
    args = parser.parse_args()

    from core.database import SessionLocal

    db = SessionLocal()
    try:
        if _agent(db, args.agent_id) is None:
            log.error("agent %s not found", args.agent_id)
            sys.exit(1)

        path = backup(db, args.agent_id)
        log.info("✓ backup written: %s", path)

        stats = convert(db, args.agent_id)
        log.info("✓ converted: %s", stats)

        if args.convert_only:
            log.info("convert-only mode — learned state untouched")
            return

        if not args.yes:
            log.warning("wipe requires --yes (destructive, irreversible)")
            sys.exit(2)

        wiped = wipe(db, args.agent_id)
        log.info("✓ wiped: %s", wiped)
        log.info("agent restart complete — approve playbook drafts via "
                 "GET/POST /api/playbooks, review evals via the runner")
    finally:
        db.close()


if __name__ == "__main__":
    from typing import Dict  # noqa: E402  (used in type comments above)
    main()
