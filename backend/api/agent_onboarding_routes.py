"""
Employee-friendly agent onboarding and automation suggestions.

Design goal (per Brennan Machinery product direction):
- ANY employee (not just admins) can create an agent by describing the job
  in plain language. The guided factory designs the agent; it always starts
  at STUDENT maturity so it is spoon-fed until it graduates.
- Workflow automation suggestions are mined from real workspace history.
- Autonomous agents can use the same endpoint on their own behalf,
  gated by their trust policy / maturity: if governance denies, an HITL
  approval is created (pause-and-ask, never silent failure).
"""

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.guided_automation_service import (
    get_automation_suggestion_service,
    get_guided_agent_factory,
)
from core.models import AgentRegistry, AgentStatus
from core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/agents", tags=["Agent Onboarding"])

# Students are ROLE-based by design: the role (template specialty or
# category) decides the curriculum topics the student starts mastering and
# which workspace events are relevant to observe. "general" is the fallback
# for generic students, who observe everything but start with no curriculum.
ROLE_CURRICULUM = {
    "finance_analyst": ["invoices", "reconciliation", "expense_analysis", "budget_tracking"],
    "sales_assistant": ["lead_scoring", "crm_sync", "email_outreach", "deal_management"],
    "ops_coordinator": ["inventory", "order_tracking", "vendor_management", "logistics"],
    "hr_assistant": ["onboarding", "policy_lookup", "leave_tracking"],
    "procurement_specialist": ["po_extraction", "draft_orders", "integration_sync"],
    "knowledge_analyst": ["knowledge_ingestion", "research", "summarization"],
    "marketing_analyst": ["campaign_tracking", "content_calendar", "social_media"],
}


def _role_for(blueprint: dict) -> str:
    """Template specialty if the blueprint used one, else category."""
    template = blueprint.get("template")
    if template and template != "custom":
        return template
    return (blueprint.get("category") or "general").lower()


class GuidedAgentRequest(BaseModel):
    """Plain-language agent creation request — one required field."""

    goal: str = Field(min_length=5, max_length=2000, description="What should this agent do, in plain language")
    context: Optional[str] = Field(None, max_length=4000, description="Optional extra context (tools, examples, constraints)")
    schedule_config: Optional[Dict[str, Any]] = None
    # Set when an AGENT (not a human employee) is creating on its own behalf.
    acting_agent_id: Optional[str] = None


class SuggestionCreateRequest(BaseModel):
    """Create a workflow/agent directly from a suggestion."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    trigger: Optional[str] = None
    steps: Optional[list] = None


@router.post("/guided", status_code=201)
async def create_guided_agent(
    req: GuidedAgentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an agent from a plain-language goal. Available to any employee.

    No AGENT_MANAGE permission required — this is the self-serve on-ramp.
    The generated agent always starts at STUDENT maturity (guided/HITL-gated)
    regardless of who created it.

    When `acting_agent_id` is set, an agent is creating this helper itself:
    its trust policy decides create-now vs. HITL approval. AUTONOMOUS agents
    create directly; lower maturities get a pending approval instead.
    """
    workspace_id = getattr(current_user, "workspace_id", None) or "default"
    tenant_id = getattr(current_user, "tenant_id", None) or "default"

    # --- Trust/maturity gate for agent-initiated creation ---
    if req.acting_agent_id:
        governance = ServiceFactory.get_governance_service(db, workspace_id=workspace_id, tenant_id=tenant_id)
        decision = await governance.can_perform_action_async(
            agent_id=req.acting_agent_id,
            action_type="create_agent",
        )
        allowed = decision.get("allowed", False) if isinstance(decision, dict) else bool(decision)
        if not allowed:
            reason = (decision.get("reason") if isinstance(decision, dict) else None) or "Trust policy requires human approval for agent creation"
            hitl_action_id = None
            try:
                hitl_action_id = governance.request_approval(
                    agent_id=req.acting_agent_id,
                    action_type="create_agent",
                    params={
                        "goal": req.goal,
                        "context": req.context,
                        "created_by_user": str(getattr(current_user, "id", "unknown")),
                        "tenant_id": tenant_id,
                    },
                    reason=reason,
                )
            except Exception as e:
                logger.error(f"Failed to create HITL action for guided agent creation: {e}")
            # 202 Accepted: creation is queued behind human review, not done.
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=202,
                content=router.success_response(
                    data={
                        "status": "pending_approval",
                        "hitl_action_id": hitl_action_id,
                        "reason": reason,
                    },
                    message="Agent creation requires human approval — request queued for review",
                ),
            )

    # --- Design the agent from the goal ---
    factory = get_guided_agent_factory()
    blueprint = await factory.design_agent(goal=req.goal, context=req.context)

    configuration = blueprint.get("configuration") or {}
    if not isinstance(configuration, dict):
        configuration = {}
    # Role-based student: the role drives curriculum and observation
    # relevance; learning contract declares both pathways (teacher +
    # observation), and the Atom meta agent is the designated teacher.
    role = _role_for(blueprint)
    configuration["role"] = role
    configuration["learning"] = {
        "teacher_agent_id": "atom_main",
        "pathways": ["teacher", "observation"],
        "curriculum": ROLE_CURRICULUM.get(role, []),
    }

    registry_entry = AgentRegistry(
        name=blueprint["name"],
        description=blueprint["description"],
        category=blueprint["category"],
        capabilities=blueprint.get("capabilities"),
        configuration=configuration,
        schedule_config=req.schedule_config,
        module_path="core.generic_agent",
        class_name="GenericAgent",
        # Always spoon-fed to start: employees and autonomous agents alike
        # get a STUDENT that must graduate before acting unattended.
        status=AgentStatus.STUDENT.value,
        # Spoon-fed start: fresh students begin with low confidence and earn
        # it through teaching/observation (capped below the promotion
        # threshold) — the model default of 0.5 would already sit at the
        # training-review boundary.
        confidence_score=0.1,
        user_id=str(getattr(current_user, "id", "unknown")),
        workspace_id=workspace_id,
        tenant_id=tenant_id,
    )
    if req.acting_agent_id:
        registry_entry.parent_agent_id = req.acting_agent_id

    db.add(registry_entry)
    db.commit()
    db.refresh(registry_entry)

    if req.schedule_config and req.schedule_config.get("active"):
        try:
            from core.scheduler import AgentScheduler
            AgentScheduler.get_instance().schedule_agent(registry_entry.id, req.schedule_config)
        except Exception as e:
            logger.warning(f"Failed to schedule guided agent {registry_entry.id}: {e}")

    return router.success_response(
        data={
            "agent_id": registry_entry.id,
            "name": registry_entry.name,
            "category": registry_entry.category,
            "template": blueprint.get("template"),
            "maturity": AgentStatus.STUDENT.value,
            "created_by": "agent" if req.acting_agent_id else "employee",
        },
        message=f"Agent '{registry_entry.name}' created — it starts as a STUDENT and learns with guidance",
    )


@router.get("/automation-suggestions")
async def get_automation_suggestions(
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suggest workflow automations based on this workspace's real history.

    Mines frequent manual agent runs, frequently human-approved actions, and
    existing workflow volume, then proposes automations ranked by evidence.
    """
    workspace_id = getattr(current_user, "workspace_id", None) or "default"
    tenant_id = getattr(current_user, "tenant_id", None) or "default"

    service = get_automation_suggestion_service()
    result = await service.generate_suggestions(db, workspace_id=workspace_id, tenant_id=tenant_id, limit=limit)
    return router.success_response(
        data=result,
        message=f"{len(result.get('suggestions', []))} automation suggestions generated from workspace history",
    )


# ---------------------------------------------------------------------------
# Maturity guidance: users need to know when an agent will be useful
# ---------------------------------------------------------------------------

MATURITY_LEVELS_USER_GUIDE = [
    {
        "level": "student",
        "title": "Student — learning the ropes",
        "what_it_can_do": "Watch, search, read, and summarize. It learns from every task: the Atom meta agent teaches it and it observes what gets approved in your workspace.",
        "what_it_cannot_do": "Nothing that changes anything — no sending, creating, or updating. Expect to spoon-feed it.",
        "useful_for": "Not directly useful yet — it is building context. Days, not weeks, if you give it feedback.",
    },
    {
        "level": "intern",
        "title": "Intern — drafts and suggests",
        "what_it_can_do": "Analyze, draft, recommend, and propose. It can prepare emails, reports, and workflow suggestions for your review.",
        "what_it_cannot_do": "Execute anything on its own — every draft needs your click.",
        "useful_for": "Useful as a preparation assistant: saves drafting time immediately.",
    },
    {
        "level": "supervised",
        "title": "Supervised — executes with your approval",
        "what_it_can_do": "Create, update, send, and schedule — but each consequential action pauses for your approval (one tap to approve or reject).",
        "what_it_cannot_do": "Act unattended; destructive actions still require review.",
        "useful_for": "Genuinely useful day-to-day: it does the work, you keep the keys.",
    },
    {
        "level": "autonomous",
        "title": "Autonomous — runs on its own",
        "what_it_can_do": "Full execution including workflows, on a schedule or triggered by events, with full audit logging.",
        "what_it_cannot_do": "Nothing is hidden — every action remains auditable, and guardrails can restrict it any time.",
        "useful_for": "Set-and-forget automation; this is when the agent pays for itself.",
    },
]

_LEVEL_ORDER = ["student", "intern", "supervised", "autonomous"]
_ADVANCEMENT = {
    "student": "Complete training sessions and pass the graduation exam: confidence ≥ 0.5 plus demonstrated episodes with low intervention. Teaching and observation accelerate this.",
    "intern": "25+ quality episodes with <20% human intervention and constitutional score ≥ 0.85.",
    "supervised": "50+ quality episodes with very low intervention rate — earned through consistent, corrected real work.",
}


@router.get("/maturity-guide")
async def get_maturity_guide(
    current_user: User = Depends(get_current_user),
):
    """Plain-language guide to agent maturity levels so users know what to
    expect and when an agent becomes useful."""
    return router.success_response(
        data={"levels": MATURITY_LEVELS_USER_GUIDE},
        message="Agent maturity guide",
    )


@router.get("/{agent_id}/maturity-guide")
async def get_agent_maturity_guide(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Personalized readiness report for one agent: where it is, what it can
    do today, and exactly what advances it to the next level."""
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise router.error_response(
            error_code="AGENT_NOT_FOUND",
            message=f"Agent {agent_id} not found",
            status_code=404,
        )

    status = (agent.status or "student").lower()
    config = agent.configuration if isinstance(agent.configuration, dict) else {}
    learning = config.get("learning", {}) if isinstance(config.get("learning"), dict) else {}
    log = learning.get("log", []) or []
    confidence = float(agent.confidence_score or 0.0)

    # Example capabilities per complexity band, drawn from the governance
    # ladder so the guide never drifts from actual enforcement.
    from core.agent_governance_service import AgentGovernanceService
    bands = {1: [], 2: [], 3: [], 4: []}
    for action, complexity in AgentGovernanceService.ACTION_COMPLEXITY.items():
        if len(bands[complexity]) < 5:
            bands[complexity].append(action)
    maturity_idx = _LEVEL_ORDER.index(status) if status in _LEVEL_ORDER else 0

    # Mastery progress from the pedagogy framework (safe on missing config)
    from core.agent_pedagogy import PedagogicalFramework
    mastery = PedagogicalFramework(db).get_mastery_report(agent)

    next_level = _LEVEL_ORDER[maturity_idx + 1] if maturity_idx + 1 < len(_LEVEL_ORDER) else None
    learning_ceiling = 0.45
    at_ceiling = confidence >= learning_ceiling

    readiness = {
        "ready_for_graduation_review": at_ceiling,
        "confidence": round(confidence, 3),
        "confidence_needed_for_training_review": learning_ceiling,
        "note": (
            "Learning is capped here on purpose — a training session and "
            "graduation exam confer maturity, learning alone never does."
        ) if at_ceiling else (
            f"{round((learning_ceiling - confidence) / 0.01)} more observations "
            f"(or {round((learning_ceiling - confidence) / 0.05)} lessons) roughly reach the review threshold."
        ),
    }

    return router.success_response(
        data={
            "agent_id": agent.id,
            "agent_name": agent.name,
            "current_level": status,
            "level_guide": next(g for g in MATURITY_LEVELS_USER_GUIDE if g["level"] == status),
            "what_it_can_do_today": {
                "complexity_band": maturity_idx + 1,
                "example_actions": bands.get(maturity_idx + 1, []),
            },
            "learning_progress": {
                "role": config.get("role", "general"),
                "curriculum": learning.get("curriculum", []),
                "lessons_from_teacher": sum(1 for e in log if e.get("source") == "teacher"),
                "observations": sum(1 for e in log if e.get("source") == "observation"),
                "pathways_used": learning.get("pathways_used", []),
            },
            "mastery": mastery,
            "readiness": readiness,
            "next_level": next_level,
            "how_to_advance": _ADVANCEMENT.get(status, "Top maturity level reached."),
        },
        message=f"{agent.name} is a {status.upper()} — see readiness for what comes next",
    )


class TeachRequest(BaseModel):
    """A mentor lesson delivered to a STUDENT agent."""

    lesson: str = Field(min_length=5, max_length=4000, description="The lesson, correction, or worked example")
    topic: Optional[str] = Field(None, max_length=200)
    # When an AGENT delivers the lesson (vs a human supervisor). The agent
    # must pass the teach_student governance check and be a qualified mentor
    # for the student's role (same-category senior, or atom_main for
    # system/Meta students).
    acting_agent_id: Optional[str] = None
    # Installation Adaptation Plan (Phase 3): also capture the lesson as a
    # structured PLAYBOOK draft (process steps + question templates) —
    # opt-in so ordinary style lessons don't spawn process objects. Drafts
    # wait for supervisor approval via /api/playbooks/{id}/approve.
    as_playbook: bool = False
    playbook_canvas_type: Optional[str] = None


@router.post("/{agent_id}/teach")
async def teach_agent(
    agent_id: str,
    req: TeachRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deliver a mentor lesson to a STUDENT agent (the spoon-feeding channel).

    Humans (supervisors/employees) can always teach — that IS the guidance.
    Agents must pass governance (teach_student is level-1: any active
    maturity) AND be a qualified mentor for the student's role, mirroring
    StudentTrainingService._find_mentor: a same-category SUPERVISED+ senior
    with verified success episodes, or atom_main for system/Meta students.
    """
    workspace_id = getattr(current_user, "workspace_id", None) or "default"
    tenant_id = getattr(current_user, "tenant_id", None) or "default"

    if req.acting_agent_id:
        governance = ServiceFactory.get_governance_service(db, workspace_id=workspace_id, tenant_id=tenant_id)
        decision = await governance.can_perform_action_async(
            agent_id=req.acting_agent_id,
            action_type="teach_student",
        )
        allowed = decision.get("allowed", False) if isinstance(decision, dict) else bool(decision)
        if not allowed:
            reason = (decision.get("reason") if isinstance(decision, dict) else None) or "Teaching not permitted"
            raise router.error_response(
                error_code="TEACH_NOT_PERMITTED",
                message=reason,
                status_code=403,
            )

        # Role-specific mentorship: a mentor must have done the student's job.
        from core.student_training_service import StudentTrainingService
        student = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not student:
            raise router.error_response(
                error_code="AGENT_NOT_FOUND", message=f"Agent {agent_id} not found", status_code=404
            )
        mentor = StudentTrainingService(db)._find_mentor(student)
        if not mentor or mentor.id != req.acting_agent_id:
            raise router.error_response(
                error_code="NOT_A_QUALIFIED_MENTOR",
                message=(
                    f"Agent {req.acting_agent_id} is not a qualified mentor for a "
                    f"{student.category or 'general'} student — mentors must be "
                    "same-category seniors with verified success episodes "
                    "(atom_main mentors system/Meta students)."
                ),
                status_code=403,
            )

    from core.student_learning_service import StudentLearningService
    learning = StudentLearningService(db)
    result = learning.learn_from_teacher(
        student_agent_id=agent_id,
        teacher_agent_id=req.acting_agent_id or "human_supervisor",
        lesson=req.lesson,
        topic=req.topic,
    )
    if result.get("status") != "ok":
        # learn_from_teacher returns student_not_found for missing AND
        # non-student targets — distinguish for a correct status code.
        agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            raise router.error_response(
                error_code="AGENT_NOT_FOUND", message=f"Agent {agent_id} not found", status_code=404
            )
        if result.get("reason") == "student_not_found" and agent.id:
            # Human supervisor teaching their own hire at ANY tier: the
            # lesson still lands as permanent standing guidance (same
            # status-independent journal the canvas-correction path uses) —
            # only the STUDENT-only confidence/pedagogy circuit is skipped.
            from core.student_learning_service import journal_standing_lesson

            journaled = journal_standing_lesson(
                db, str(agent.id), req.lesson,
                source="teacher",
                topic=req.topic,
                teacher_agent_id=req.acting_agent_id or "human_supervisor",
            )
            if journaled:
                return router.success_response(
                    data={"status": "ok", "mode": "standing_guidance",
                          "agent_status": agent.status},
                    message=(f"Lesson recorded as standing guidance for {agent.name} "
                             f"({agent.status.upper()}) — it applies to all their work"),
                )
        return router.success_response(
            data={"status": "skipped", "reason": result.get("reason"),
                  "agent_status": agent.status},
            message=f"{agent.name} is a {agent.status.upper()} — teaching applies to STUDENT agents",
        )

    # Training circuit: a lesson taught while a training session is ACTIVE
    # also lands in that session's guidance record, so the training history
    # shows what was taught during the pass (best-effort — the journal and
    # confidence above are the contract).
    try:
        from core.student_training_service import StudentTrainingService

        StudentTrainingService(db).record_session_lesson(
            agent_id=agent_id, lesson=req.lesson, topic=req.topic,
        )
    except Exception as session_lesson_err:
        logger.debug(f"session lesson record skipped: {session_lesson_err}")

    # Installation Adaptation Plan (Phase 3): opt-in structured capture —
    # the lesson ALSO becomes a playbook draft (process steps + question
    # templates) awaiting supervisor approval. Fault-isolated: a playbook
    # capture failure never fails the teach itself.
    playbook_id = None
    if req.as_playbook:
        try:
            from core.playbook_service import PlaybookService

            row = PlaybookService(db, tenant_id=tenant_id, workspace_id=workspace_id).create_from_teach(
                req.lesson, agent_id=str(current_user.id),
                trigger_canvas_type=req.playbook_canvas_type,
            )
            playbook_id = row.id
        except Exception as pb_err:
            logger.debug(f"teach playbook capture skipped: {pb_err}")

    return router.success_response(
        data={**result, **({"playbook_id": playbook_id} if playbook_id else {})},
        message="Lesson recorded — the student's confidence grew"
                + (" (playbook draft created — approve it in Playbooks)" if playbook_id else ""),
    )
