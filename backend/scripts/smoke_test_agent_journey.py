#!/usr/bin/env python3
"""
verify_agent_journey.py — End-to-End Agent Journey Verification

Self-contained simulation on an isolated SQLite DB (no live DB, no LLM keys).
Walks the full agent autonomy + memory + learning journey and exits non-zero
if any link is severed:

  1. STUDENT gating: read-only allowed, state changes blocked
  2. Training journey: blocked trigger -> proposal -> approve ->
     complete -> confidence boost -> STUDENT-to-INTERN promotion
  3. INTERN gating: complexity-2 allowed, memory_forget (SUPERVISED+) denied,
     memory_remember allowed
  4. Learning loop: record_outcome drips confidence across thresholds
  5. Episodic memory: execution-based episode creation feeds graduation data
  6. HITL fail-closed: unresolvable policy check blocks risky comms

Usage:
  PYTHONPATH=.:.. python scripts/verify_agent_journey.py
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("verify_agent_journey")

# DATABASE_URL must point at the isolated DB BEFORE core.database imports.
_test_db_path = os.path.join(tempfile.gettempdir(), f"journey_{uuid.uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"

from sqlalchemy import create_engine, types  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

postgresql.JSONB = types.JSON
import sqlalchemy.dialects.postgresql.base as pg_base  # noqa: E402

pg_base.JSONB = types.JSON

ENGINE = create_engine(
    os.environ["DATABASE_URL"], connect_args={"check_same_thread": False}
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def record(name, passed, details="", skipped=False):
    status = SKIP if skipped else (PASS if passed else FAIL)
    results.append({"test": name, "passed": passed, "skipped": skipped, "details": details})
    logger.info(f"  {status} - {name}" + (f" | {details}" if details else ""))


def bootstrap():
    from core.database import Base
    import sqlalchemy.types as sql_types

    from core.models import AgentRegistry, User, Workspace, Tenant, JSONBColumn  # noqa: F401

    JSONBColumn.load_dialect_impl = lambda self, dialect: dialect.type_descriptor(
        sql_types.JSON()
    )
    Base.metadata.create_all(bind=ENGINE)
    logger.info(f"SQLite schema bootstrapped at {_test_db_path}")


def make_agent(db, agent_id="journey-agent", status="student", confidence=0.40):
    from core.models import AgentRegistry

    db.add(AgentRegistry(
        id=agent_id,
        name="Journey Agent",
        category="operations",
        module_path="core.atom_meta_agent",
        class_name="AtomMetaAgent",
        status=status,
        confidence_score=confidence,
        workspace_id="default",
        tenant_id="default",
    ))
    db.commit()
    return db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()


def phase1_student_gating(db):
    logger.info("Phase 1: STUDENT gating")
    from core.agent_governance_service import AgentGovernanceService

    agent = make_agent(db)
    gov = AgentGovernanceService(db)

    read = gov.can_perform_action(agent.id, "search_contacts", _skip_budget=True)
    record("student.read_allowed", read["allowed"] is True)

    send = gov.can_perform_action(agent.id, "send_email", _skip_budget=True)
    record(
        "student.send_email_blocked",
        send["allowed"] is False and send["requires_human_approval"] is True,
        f"complexity={send['action_complexity']}",
    )


async def phase2_training_to_intern(db):
    logger.info("Phase 2: training journey (blocked trigger -> promotion)")
    from core.models import (
        AgentProposal, BlockedTriggerContext, ProposalStatus, ProposalType,
    )
    from core.student_training_service import StudentTrainingService, TrainingOutcome

    from core.models import AgentRegistry as _AR

    agent = db.query(_AR).filter_by(id="journey-agent").first()

    trigger = BlockedTriggerContext(
        id=str(uuid.uuid4()),
        tenant_id="default",
        agent_id=agent.id,
        agent_name=agent.name,
        agent_maturity_at_block="student",
        confidence_score_at_block=agent.confidence_score,
        trigger_source="WORKFLOW_ENGINE",
        trigger_type="workflow_trigger",
        trigger_context={"task": "send weekly report"},
        routing_decision="training",
        block_reason="STUDENT agents cannot execute state changes",
    )
    db.add(trigger)
    db.commit()

    svc = StudentTrainingService(db)
    proposal = await svc.create_training_proposal(trigger)
    record(
        "training.proposal_created",
        proposal is not None
        and proposal.status == ProposalStatus.PENDING_APPROVAL.value
        and proposal.proposal_type == ProposalType.WORKFLOW.value,
    )

    session = await svc.approve_training(
        proposal_id=proposal.id, user_id="supervisor-1"
    )
    record("training.session_created", session is not None and session.status == "scheduled")

    result = await svc.complete_training_session(
        session_id=session.id,
        outcome=TrainingOutcome(
            performance_score=0.95,
            supervisor_feedback="Excellent",
            errors_count=0,
            tasks_completed=10,
            total_tasks=10,
            capabilities_developed=["email"],
            capability_gaps_remaining=[],
        ),
    )
    db.refresh(agent)
    record(
        "training.promoted_to_intern",
        result.get("promoted_to_intern") is True
        or agent.status == "intern",
        f"status={agent.status} conf={agent.confidence_score}",
    )
    return proposal


async def phase3_intern_gating(db):
    logger.info("Phase 3: INTERN gating incl. memory tiers")
    from core.agent_governance_service import AgentGovernanceService

    gov = AgentGovernanceService(db)
    analyze = gov.can_perform_action("journey-agent", "analyze_data", _skip_budget=True)
    remember = gov.can_perform_action("journey-agent", "memory_remember", _skip_budget=True)
    forget = gov.can_perform_action("journey-agent", "memory_forget", _skip_budget=True)
    record("intern.analyze_allowed", analyze["allowed"] is True)
    record("intern.memory_remember_allowed", remember["allowed"] is True)
    record("intern.memory_forget_denied", forget["allowed"] is False,
           f"complexity={forget['action_complexity']}")


async def phase4_learning_drip(db):
    logger.info("Phase 4: outcome-driven confidence drip toward SUPERVISED")
    from core.agent_governance_service import AgentGovernanceService

    gov = AgentGovernanceService(db)
    promoted = False
    for i in range(60):
        await gov.record_outcome("journey-agent", success=True)
        agent = db.query(AgentRegistry).filter_by(id="journey-agent").first()
        if agent.status == "supervised":
            promoted = True
            break
    record(
        "learning.drip_promotes_to_supervised",
        promoted,
        f"conf={agent.confidence_score} after {i + 1} successes",
    )


async def phase5_episodes(db):
    logger.info("Phase 5: episodic memory from executions")
    from core.models import AgentExecution
    from core.episode_service import EpisodeService

    execution = AgentExecution(
        id=str(uuid.uuid4()),
        agent_id="journey-agent",
        workspace_id="default",
        tenant_id="default",
        status="completed",
        input_summary="Weekly report generation",
        output_summary="Report sent to leadership",
        triggered_by="schedule",
    )
    db.add(execution)
    db.commit()

    episode = await EpisodeService(db).create_episode_from_execution(
        execution_id=execution.id,
        task_description="Weekly report generation",
        outcome="completed",
        success=True,
    )
    record("episodes.created_from_execution",
           episode is not None and episode.outcome == "completed")

    try:
        from core.agent_graduation_service import AgentGraduationService

        readiness = await AgentGraduationService(db).calculate_readiness_score(
            "journey-agent", "INTERN"
        )
        record("graduation.readiness_computed", readiness is not None,
               details=json.dumps(readiness, default=str)[:120])
    except Exception as e:
        record("graduation.readiness_computed", False,
               details=f"needs heavier services: {e}", skipped=True)


async def phase6_hitl_fail_closed():
    logger.info("Phase 6: HITL fail-closed on unresolvable policy check")
    from integrations.mcp_service import MCPService

    result = await MCPService()._check_hitl_policy(
        "workspace-that-does-not-exist", "send_email", {"to": "x@y.z"}, {}
    )
    record(
        "hitl.fail_closed_blocks_risky_send",
        isinstance(result, dict) and result.get("blocked_by") == "hitl_policy_error",
    )


async def run_all(db):
    phase1_student_gating(db)
    await phase2_training_to_intern(db)
    await phase3_intern_gating(db)
    await phase4_learning_drip(db)
    await phase5_episodes(db)
    await phase6_hitl_fail_closed()


def main() -> int:
    start = time.time()
    bootstrap()

    from core.database import SessionLocal as CoreSessionLocal  # bound via env

    db = CoreSessionLocal()
    try:
        asyncio.run(run_all(db))
    finally:
        db.close()

    elapsed = time.time() - start
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])

    print("\n" + "=" * 60)
    print("  AGENT JOURNEY VERIFICATION — COMPLETE")
    print("=" * 60)
    print(f"  Tests : {len(results)}   PASS: {passed}   FAIL: {failed}")
    print(f"  Duration: {elapsed:.2f}s")
    print("=" * 60)

    for r in results:
        if not r["passed"]:
            print(f"  {FAIL} {r['test']}: {r['details']}")

    print(json.dumps({
        "total": len(results), "passed": passed, "failed": failed,
        "duration_seconds": round(elapsed, 3), "results": results,
    }, indent=2, default=str))

    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    # Late binding: AgentRegistry used across phases.
    from core.models import AgentRegistry  # noqa: F401

    sys.exit(main())
