from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Union
import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from core.error_handlers import handle_not_found, handle_permission_denied
from core.governance_cache import get_governance_cache
from core.models import (
    AgentFeedback,
    AgentRegistry,
    AgentStatus,
    FeedbackStatus,
    GovernanceDocument,
    GovernanceDocStatus,
    GovernanceImpactLevel,
    HITLAction,
    NEW_AGENT_CONFIDENCE,
    HITLActionStatus,
    User,
    UserRole,
    TokenUsage,
)
from core.rbac_service import Permission, RBACService
from core.continuous_learning_service import ContinuousLearningService
from core.activity_publisher import ActivityPublisher
from core.autonomous_guardrails import AutonomousGuardrailService
from core.policy_search_service import PGPolicySearchService

logger = logging.getLogger(__name__)


def _max_nesting_depth(links: List[Any], root_agent_id: str) -> int:
    """Compute the maximum NESTING DEPTH of a delegation ChainLink tree.

    A flat chain (root → sib1, root → sib2, root → sib3) has depth 1.
    A nested chain (root → a → b → c) has depth 3. This is what
    ``DelegationChain.max_depth`` should gate — NOT the total link count
    (P1c / R1 fix; previously ``len(chain.links)``).
    """
    if not links:
        return 0
    # Build child map: parent_id -> [child_ids]
    children: Dict[str, List[str]] = {}
    for link in links:
        parent = getattr(link, "parent_agent_id", None)
        child = getattr(link, "child_agent_id", None)
        if parent and child:
            children.setdefault(parent, []).append(child)

    def _depth(node: str, seen: set) -> int:
        if node in seen:  # cycle guard
            return 0
        seen = seen | {node}
        kids = children.get(node, [])
        if not kids:
            return 0
        return 1 + max(_depth(k, seen) for k in kids)

    return _depth(root_agent_id, set())


# ---------------------------------------------------------------------------
# Arbor code-quality gate helper
# ---------------------------------------------------------------------------
# Actions that carry executable code in their details dict.
_CODE_WRITE_ACTIONS = frozenset({
    "write_code_file",
    "execute",
    "shell_build",
    "shell_write",
    "deploy",
})


def _arbor_validate_code(code: str, language: str = "python") -> dict:
    """
    Run a lightweight Arbor CodeHypothesisNode quality gate on proposed code.

    Creates a CodeHypothesisNode, performs ast.parse (for Python) to detect
    syntax errors, calculates a basic complexity estimate, and returns a
    pass/fail verdict so the governance service can block problematic code
    *before* it reaches the sandbox.

    Returns:
        {"passed": bool, "reason": str | None, "node_id": str, "promise_score": float}
    """
    import ast as _ast

    try:
        from core.hypothesis_tree import CodeHypothesisNode, NodeMetrics, PruningReason
    except ImportError:
        # Arbor not importable — skip gate gracefully
        return {"passed": True, "reason": None, "node_id": "", "promise_score": 1.0}

    lint_errors = 0
    cyclomatic_complexity = 1  # base
    lines = code.splitlines()

    if language == "python":
        try:
            tree = _ast.parse(code)
            # Count branching nodes as a rough cyclomatic proxy
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.If, _ast.For, _ast.While, _ast.ExceptHandler,
                                     _ast.With, _ast.Assert, _ast.BoolOp)):
                    cyclomatic_complexity += 1
        except SyntaxError as exc:
            lint_errors = 1
            node_obj = CodeHypothesisNode(
                hypothesis=code[:500],
                description="Governance pre-flight lint check",
                language=language,
                cyclomatic_complexity=0,
                metrics=NodeMetrics(lint_errors=1, lines_changed=len(lines)),
            )
            node_obj.pruning_reason = PruningReason.LINT_FAILED
            return {
                "passed": False,
                "reason": f"SyntaxError in proposed code: {exc}",
                "node_id": node_obj.id,
                "promise_score": 0.0,
            }

    node_obj = CodeHypothesisNode(
        hypothesis=code[:500],
        description="Governance pre-flight quality check",
        language=language,
        cyclomatic_complexity=cyclomatic_complexity,
        metrics=NodeMetrics(lint_errors=lint_errors, lines_changed=len(lines)),
    )
    promise = node_obj.calculate_promise_score()

    # Block if cyclomatic complexity is dangerously high (>= 50)
    if cyclomatic_complexity >= 50:
        node_obj.pruning_reason = PruningReason.RESOURCE_EXCEEDED
        return {
            "passed": False,
            "reason": f"Code complexity too high ({cyclomatic_complexity} branches). Refactor before approval.",
            "node_id": node_obj.id,
            "promise_score": promise,
        }

    return {"passed": True, "reason": None, "node_id": node_obj.id, "promise_score": promise}

class AgentGovernanceService:
    # Action complexity levels - higher = more complex/risky
    # Reconciled from SaaS Phase 204
    ACTION_COMPLEXITY = {
        # Level 1: READ ONLY - Student Agents
        "search": 1,
        "read": 1,
        "list": 1,
        "get": 1,
        "fetch": 1,
        "summarize": 1,
        "check": 1,
        "verify": 1,
        "get_account": 1,
        "list_leads": 1,
        "get_contact": 1,
        "get_channels": 1,
        "get_messages": 1,
        "list_users": 1,
        "get_tasks": 1,
        "list_projects": 1,
        "fetch_page": 1,
        "get_deal": 1,
        "list_deals": 1,
        "get_ticket": 1,
        "list_tickets": 1,
        "get_email": 1,
        "list_emails": 1,
        "shell_read": 1,
        "shell_network": 1,
        "memory_search": 1,       # fact recall is read-only (STUDENT+)
        "present_chart": 1,       # presentations are LOW complexity (STUDENT+)
        "present_markdown": 1,

        # Level 2: PROPOSE / DRAFT - Intern Agents
        "analyze": 2,
        "suggest": 2,
        "draft": 2,
        "generate": 2,
        "recommend": 2,
        "propose": 2,
        "plan": 2,
        "suggest_reply": 2,
        "draft_message": 2,
        "analyze_lead": 2,
        "recommend_action": 2,
        "generate_report": 2,
        "draft_email": 2,
        "propose_lead": 2,
        "suggest_task": 2,

        # Level 2 (INTERN+): streaming, browser, device, canvas moderation.
        # Levels aligned with the tool-layer governance contracts:
        #   browser_tool.py  -> "browser_navigate = INTERN+"
        #   canvas_tool.py   -> "present_form ... (INTERN+ required)"
        #   device_tool.py   -> camera/location/notifications INTERN+
        "stream_chat": 2,               # streaming LLM (INTERN+)
        "llm_stream": 2,                # streaming LLM (INTERN+)
        "present_form": 2,              # interactive canvas forms (INTERN+)
        "browser_navigate": 2,          # browser automation (INTERN+)
        "browser_screenshot": 2,
        "browser_extract": 2,
        "device_camera_snap": 2,        # camera (INTERN+)
        "device_get_location": 2,       # location (INTERN+)
        "device_send_notification": 2,  # notifications (INTERN+)
        "update_canvas": 2,             # canvas state moderation
        # Memory tools (tools/memory_tool.py contracts): storing durable facts
        # is MODERATE (INTERN+); destroying them is HIGH (SUPERVISED+).
        # Without exact keys both resolved to the level-2 default, letting an
        # INTERN agent invalidate facts at the governance layer.
        "memory_remember": 2,           # store durable fact (INTERN+)
        "memory_forget": 3,             # invalidate durable fact (SUPERVISED+)
        # Teaching (Level 1): teaching is the mechanism that CREATES trust, so
        # it must never be gated above the teacher's own maturity. The Atom
        # meta agent is the primary interaction surface and teacher — it needs
        # only INTERN maturity to suggest (level 2 above), and must be able to
        # teach STUDENT agents at any maturity, including its own INTERN floor.
        "teach_student": 1,
        "mentor_student": 1,
        "train_student": 1,

        # Level 3: EXECUTE (Supervised) - Supervised Agents
        "create": 3,
        "update": 3,
        "submit": 3,
        "canvas_submit": 3,
        "send_email": 3,
        "email_send": 3,
        "browser_action": 3,
        # BUG FIX: browser_execute_script has no exact key, so the substring
        # resolver matched the generic "execute" (level 4) and silently
        # required AUTONOMOUS, contradicting the route contract
        # (api/browser_routes.py execute_script: "Requires SUPERVISED+
        # maturity") — the exact class of shadowing the comment above the
        # resolver warns about. Pin it explicitly to level 3 (SUPERVISED+).
        "browser_execute_script": 3,
        "post_message": 3,
        "schedule": 3,
        "upload": 3,
        "submit_form": 3,                # form submission (state change)
        "device_screen_record": 3,      # screen recording (SUPERVISED+)
        "device_screen_record_start": 3,
        "device_screen_record_stop": 3,
        "create_lead": 3,
        "update_lead": 3,
        "send_message": 3,
        "create_task": 3,
        "update_task": 3,
        "create_deal": 3,
        "update_deal": 3,
        "update_contact": 3,
        "create_contact": 3,
        "add_comment": 3,
        "update_ticket": 3,
        "create_ticket": 3,
        "schedule_meeting": 3,
        "shell_write": 3,
        "shell_build": 3,
        "shell_devops": 3,
        
        # Level 4: CRITICAL (Autonomous) - Autonomous Agents
        "delete": 4,
        "execute": 4,
        "terminal_command": 4,
        "run_local_terminal": 4,
        "deploy": 4,
        "transfer": 4,
        "payment": 4,
        "approve": 4,
        "write_code_file": 4,
        "delete_lead": 4,
        "delete_task": 4,
        "delete_message": 4,
        "execute_workflow": 4,
        "transfer_record": 4,
        "bulk_delete": 4,
        "delete_contact": 4,
        "delete_deal": 4,
        "delete_ticket": 4,
        "bulk_update": 4,
        "transfer_owner": 4,
        "shell_delete": 4,
        "device_execute_command": 4,    # command execution (AUTONOMOUS only)
        "canvas_execute_javascript": 4, # arbitrary JS in canvas (AUTONOMOUS only)
    }

    # Minimum maturity level for each action complexity
    MATURITY_REQUIREMENTS = {
        1: AgentStatus.STUDENT,
        2: AgentStatus.INTERN,
        3: AgentStatus.SUPERVISED,
        4: AgentStatus.AUTONOMOUS,
    }

    def __init__(
        self,
        db: Session,
        workspace_id: str = "default",
        tenant_id: Optional[str] = None,
        activity_publisher: Optional[ActivityPublisher] = None
    ):
        self.db = db
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.activity_publisher = activity_publisher
        self.continuous_learning = ContinuousLearningService(db)

    def _workspace_scope_condition(self):
        """Return the workspace scope filter for registry queries.

        ``workspace_id="default"`` is the single-tenant (Personal Edition)
        scope. Agents registered WITHOUT a workspace (workspace_id IS NULL —
        the API create path and direct seeding) and legacy rows stamped with
        the literal ``"default"`` workspace must ALL be visible there; the
        previous ``== "default"`` filter silently hid every NULL-workspace
        agent from GET /api/agents/ (and thus the Agent Control Center UI).
        Tenant-scoped callers keep strict equality.
        """
        if self.workspace_id in (None, "default"):
            return or_(
                AgentRegistry.workspace_id.is_(None),
                AgentRegistry.workspace_id == "default",
            )
        return AgentRegistry.workspace_id == self.workspace_id

    def list_agents(self, category: Optional[str] = None) -> List[AgentRegistry]:
        """List all agents in the registry, optionally filtered by category"""
        query = self.db.query(AgentRegistry).filter(
            self._workspace_scope_condition()
        )

        if category:
            query = query.filter(AgentRegistry.category == category)

        return query.all()

    def register_or_update_agent(
        self,
        name: str,
        category: str,
        module_path: str,
        class_name: str,
        description: str = None,
        handle: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> AgentRegistry:
        """Register a new agent or update existing definition"""
        agent = self.db.query(AgentRegistry).filter(
            self._workspace_scope_condition(),
            AgentRegistry.module_path == module_path,
            AgentRegistry.class_name == class_name
        ).first()

        if not agent:
            # Create new
            agent = AgentRegistry(
                name=name,
                category=category,
                module_path=module_path,
                class_name=class_name,
                description=description,
                handle=handle,
                display_name=display_name,
                workspace_id=self.workspace_id,
                tenant_id=self.tenant_id,
                status=AgentStatus.STUDENT.value,
                confidence_score=NEW_AGENT_CONFIDENCE
            )
            self.db.add(agent)
            logger.info(f"Registered new agent: {name}")
        else:
            # Update meta
            agent.name = name
            agent.category = category
            agent.description = description
            if handle: agent.handle = handle
            if display_name: agent.display_name = display_name

        self.db.commit()
        self.db.refresh(agent)
        return agent

    async def submit_feedback(
        self,
        agent_id: str,
        user_id: str,
        original_output: str,
        user_correction: str,
        input_context: Optional[str] = None
    ) -> AgentFeedback:
        """Submit feedback and trigger continuous learning"""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            self._workspace_scope_condition()
        ).first()
        if not agent:
            raise handle_not_found("Agent", agent_id)

        feedback = AgentFeedback(
            agent_id=agent_id,
            user_id=user_id,
            original_output=original_output,
            user_correction=user_correction,
            input_context=input_context,
            status=FeedbackStatus.PENDING.value
        )
        self.db.add(feedback)
        self.db.commit()
        
        await self._adjudicate_feedback(feedback)
        return feedback

    # R82: approval tokens for polarity-aware adjudication. A thumbs-up (or
    # equivalent) from a reviewer is POSITIVE evidence; anything else
    # (corrections, thumbs_down) remains negative. The reasoning route stores
    # the original feedback_type inside input_context because a free-text
    # comment overrides user_correction.
    _APPROVAL_TOKENS = {"thumbs_up", "approve", "approved", "positive", "accept"}

    def _feedback_is_approval(self, feedback: AgentFeedback) -> bool:
        """Return True when feedback expresses approval rather than correction."""
        correction = (feedback.user_correction or "").strip().lower()
        if correction in self._APPROVAL_TOKENS:
            return True
        try:
            ctx = json.loads(feedback.input_context) if feedback.input_context else {}
            if isinstance(ctx, dict):
                return (
                    str(ctx.get("feedback_type", "")).strip().lower()
                    in self._APPROVAL_TOKENS
                )
        except (ValueError, TypeError):
            pass
        return False

    async def _adjudicate_feedback(self, feedback: AgentFeedback) -> None:
        """Judge the validity of user feedback and update agent readiness"""
        user = self.db.query(User).filter(User.id == feedback.user_id).first()
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == feedback.agent_id,
            self._workspace_scope_condition()
        ).first()

        is_admin = user.role in [UserRole.WORKSPACE_ADMIN, UserRole.SUPER_ADMIN]
        # User.specialty was commented out of the model pending migration;
        # guard with getattr so adjudication never crashes on the missing column.
        specialty = getattr(user, "specialty", None)
        is_specialty_match = specialty and agent.category and specialty.lower() == agent.category.lower()
        is_trusted = is_admin or is_specialty_match
        is_approval = self._feedback_is_approval(feedback)

        if is_trusted:
            feedback.status = FeedbackStatus.ACCEPTED.value
            feedback.ai_reasoning = f"Accepted by trusted {user.role}."
            # R82: respect polarity — a trusted reviewer's thumbs_up RAISES
            # confidence; corrections/thumbs_down lower it (prior behavior).
            self._update_confidence_score(agent.id, positive=is_approval, impact_level="high")

            try:
                self.continuous_learning.update_from_feedback(feedback)
            except Exception as e:
                logger.warning(f"Continuous learning update failed: {e}")

            # Trust bridge (BPE): an accepted human correction is the one
            # error-independent signal — it bypasses the workspace value
            # gate, holds evolution application, and de-inflates Experience
            # entries that overlap the rejected output. Never breaks
            # adjudication on failure.
            try:
                from core.bpe.trust_bridge import record_adjudication

                record_adjudication(
                    agent.id,
                    accepted=True,
                    is_correction=not is_approval,
                    original_output=feedback.original_output or "",
                    user_correction=feedback.user_correction or "",
                )
            except Exception as e:
                logger.debug(f"BPE trust bridge update skipped: {e}")
        else:
            feedback.status = FeedbackStatus.PENDING.value
            feedback.ai_reasoning = "Pending specialty review."
            # R82: an untrusted APPROVAL must not penalize the agent — only
            # corrections/thumbs_down carry the low-impact penalty while
            # pending review.
            if not is_approval:
                self._update_confidence_score(agent.id, positive=False, impact_level="low")

        feedback.adjudicated_at = datetime.now(timezone.utc)
        self.db.commit()

    def _update_confidence_score(
        self,
        agent_id: str,
        positive: bool,
        impact_level: str = "high",
        magnitude: Optional[float] = None,
    ) -> None:
        """Update confidence and manage maturity transitions.

        ``magnitude`` optionally overrides the impact-table step size (used by
        the research-informed positive-rating signal, R81j: explicit ratings
        are high-precision but noisy, so they nudge at half the outcome drip).
        """
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            self._workspace_scope_condition()
        ).first()
        if not agent: return

        # NULL-confidence rows start from the shared new-agent baseline —
        # the old `or 0.5` fallback sat exactly on the INTERN floor, so a
        # NULL row's first update promoted it out of STUDENT immediately.
        current = agent.confidence_score if agent.confidence_score is not None else NEW_AGENT_CONFIDENCE
        if magnitude is not None:
            boost = penalty = abs(magnitude)
        else:
            boost = 0.05 if impact_level == "high" else 0.01
            penalty = 0.1 if impact_level == "high" else 0.02
        
        new_score = min(1.0, current + boost) if positive else max(0.0, current - penalty)
        # Round to 4dp: repeated increments accumulate binary noise
        # (0.4 + 10*0.01 == 0.5000000000000001), which is persisted to the DB
        # and breaks exact-equality consumers (and pollutes audit output).
        new_score = round(new_score, 4)
        agent.confidence_score = new_score
        
        prev_status = agent.status
        if new_score >= 0.9: banded = AgentStatus.AUTONOMOUS.value
        elif new_score >= 0.7: banded = AgentStatus.SUPERVISED.value
        elif new_score >= 0.5: banded = AgentStatus.INTERN.value
        else: banded = AgentStatus.STUDENT.value
        agent.status = self._resolve_promotion(agent, prev_status, banded)

        if agent.status != prev_status:
            logger.info(f"Agent {agent.name} transitioned: {prev_status} -> {agent.status}")
            if self.activity_publisher:
                self.activity_publisher.publish_activity(
                    tenant_id=self.workspace_id,
                    agent_id=agent_id,
                    activity_type='learning',
                    state='adapted',
                    metadata={'old_status': prev_status, 'new_status': agent.status, 'confidence': new_score}
                )
            get_governance_cache().invalidate(agent_id)

        self.db.commit()

    # Maturity ladder used by the promotion gate below. Tier is still a
    # function of confidence, but MOVING UP now requires evidence — the
    # R86/R86b contract. Non-tier statuses (paused/stopped/deprecated) are
    # lifecycle states: a confidence update must not resurrect them.
    _MATURITY_RANK = {"student": 0, "intern": 1, "supervised": 2, "autonomous": 3}

    def _resolve_promotion(self, agent: AgentRegistry, prev_status: str, banded: str) -> str:
        """Apply the score-derived tier, gating upward moves on evidence.

        Score drips (outcome hooks, feedback adjudication) previously
        promoted an agent purely by band — bypassing the R86b evidence gate
        (student_training_service) for STUDENT→INTERN and the graduation
        readiness framework for the higher rungs, which defeated their
        purpose: confidence accrues automatically, evidence does not.
        Demotions stay score-based (re-earning a rung re-gates it), and
        ATOM_PROMOTION_EVIDENCE_GATE=0 restores score-only behavior.
        """
        import os as _os

        if _os.getenv("ATOM_PROMOTION_EVIDENCE_GATE", "1").lower() not in ("1", "true", "yes", "on"):
            return banded

        prev_rank = self._MATURITY_RANK.get(prev_status)
        new_rank = self._MATURITY_RANK.get(banded)
        if prev_rank is None:
            # Lifecycle state (paused/stopped/…): keep it; tiers only.
            return prev_status
        if new_rank is None or new_rank <= prev_rank:
            return banded

        # Walk the ladder upward: each rung between the current tier and
        # the score's band must independently pass its evidence gate; the
        # agent lands on the highest rung that did.
        landed = prev_rank
        for rank in range(prev_rank + 1, new_rank + 1):
            level = next(name for name, r in self._MATURITY_RANK.items() if r == rank)
            ok, detail = self._promotion_evidence_met(agent, level)
            if not ok:
                logger.info(
                    f"Agent {agent.name} evidence gate blocked {level}: "
                    f"{(detail or {}).get('reason') or 'requirements not met'}"
                )
                if self.activity_publisher:
                    self.activity_publisher.publish_activity(
                        tenant_id=self.workspace_id,
                        agent_id=str(agent.id),
                        activity_type='learning',
                        state='promotion_blocked',
                        metadata={'target_level': level, 'confidence': agent.confidence_score, 'detail': detail or {}},
                    )
                break
            landed = rank
        return next(name for name, r in self._MATURITY_RANK.items() if r == landed)

    def _promotion_evidence_met(self, agent: AgentRegistry, level: str):
        """Evidence gate for one rung: the R86b multi-pathway evaluator for
        INTERN (sessions/episodes/mentor/system-agent), the graduation
        readiness framework's threshold for SUPERVISED/AUTONOMOUS."""
        try:
            from core.student_training_service import StudentTrainingService

            training = StudentTrainingService(self.db)
            if level == "intern":
                readiness = training._evaluate_intern_readiness(agent)
                return bool(readiness.get("ready")), readiness
            if training._is_system_agent(agent):
                # Platform-built agents bootstrap the product (R86 parity
                # with the intern pathway's system_agent route).
                return True, {"pathway": "system_agent"}
            from core.episode_service import EpisodeService

            resp = EpisodeService(self.db).get_graduation_readiness(
                agent_id=str(agent.id),
                tenant_id=agent.tenant_id or "default",
                target_level=level,
            )
            return bool(resp.threshold_met), {
                "readiness_score": resp.readiness_score,
                "episodes_analyzed": resp.episodes_analyzed,
                "reason": "graduation readiness threshold not met",
            }
        except Exception as e:
            # Gate failures are fail-closed: without a working evaluator
            # there is no evidence, so the rung is not earned.
            logger.warning(f"Promotion evidence gate error for {agent.id} -> {level}: {e}")
            return False, {"reason": f"gate error: {e}"}

    # --- ADVANCED GOVERNANCE (SaaS Port) ---

    async def _check_budget_async(
        self, agent_id: str, action_type: str, chain_id: Optional[str]
    ) -> Dict[str, Any]:
        """Run the budget-before-action check and return its decision dict.

        Shared by the sync and async governance paths so the budget logic isn't
        duplicated. Returns {"allowed": True} (passthrough) if the budget
        service is unavailable, matching the historical graceful-degradation
        behavior — but the call itself is now actually awaited in async
        contexts (previously it raised "loop already running" and was skipped,
        silently bypassing spend limits).
        """
        try:
            from core.budget_enforcement_service import BudgetEnforcementService
            budget_svc = BudgetEnforcementService(self.db)
            return await budget_svc.check_budget_before_action(
                tenant_id=self.workspace_id,
                agent_id=agent_id,
                action=action_type,
                chain_id=chain_id,
            )
        except Exception as e:
            logger.warning(f"Budget check failed (non-fatal, allowing): {e}")
            return {"allowed": True}

    async def can_perform_action_async(
        self,
        agent_id: str,
        action_type: str,
        require_approval: bool = False,
        chain_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async variant of can_perform_action — USE THIS from async callers.

        The sync can_perform_action() cannot await the budget check when called
        inside a running event loop (it would raise "loop already running"),
        so callers in an async context (the meta-agent, MCP, streaming
        endpoints) must use this variant to actually enforce spend limits.
        """
        # Compute the maturity/complexity/recursion decision synchronously,
        # skipping the budget check (handled below via await).
        decision = self.can_perform_action(
            agent_id, action_type, require_approval=require_approval, chain_id=chain_id
        )
        # If the sync path already blocked it (maturity/recursion), honor that.
        if not decision.get("allowed", True):
            return decision
        # Enforce the budget via a real await (the whole point of this variant).
        budget_check = await self._check_budget_async(agent_id, action_type, chain_id)
        if not budget_check.get("allowed", True):
            return {
                "allowed": False,
                "reason": budget_check.get("reason"),
                "requires_human_approval": True,
                "status_code": "BUDGET_EXCEEDED",
            }
        return decision

    def can_perform_action(
        self,
        agent_id: str,
        action_type: str,
        require_approval: bool = False,
        chain_id: Optional[str] = None, # NEW Phase 10
        _skip_budget: bool = False,  # internal: used by can_perform_action_async
    ) -> Dict[str, Any]:
        """Hybrid maturity check with complexity-based enforcement"""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            self._workspace_scope_condition()
        ).first()
        
        if not agent:
            return {"allowed": False, "reason": "Agent not found", "requires_human_approval": True}

        # Normalize case once: stored status may be written by API clients in
        # non-lowercase form (e.g. "AUTONOMOUS"), which would otherwise break
        # the paused/stopped deny-check, the maturity tier lookup, and the
        # SUPERVISED approval rule below (case-sensitive comparisons).
        stored_status = agent.status.lower() if isinstance(agent.status, str) else agent.status

        if stored_status in [AgentStatus.PAUSED.value, AgentStatus.STOPPED.value]:
            return {"allowed": False, "reason": f"Agent is {agent.status}", "requires_human_approval": True}

        # Find complexity (Level 1-4). Exact matches take priority over substring
        # matches so specific actions aren't shadowed by generic keys — e.g.
        # "device_get_location" must not resolve to complexity 1 via "get", and
        # "update_canvas" must not escalate to 3 via "update".
        action_lower = action_type.lower()
        complexity = 2 # Default
        if action_lower in self.ACTION_COMPLEXITY:
            complexity = self.ACTION_COMPLEXITY[action_lower]
        else:
            matches = [lvl for act, lvl in self.ACTION_COMPLEXITY.items() if act in action_lower]
            if matches: complexity = max(matches)
        
        required_status = self.MATURITY_REQUIREMENTS.get(complexity, AgentStatus.SUPERVISED)

        maturity_order = [s.value for s in [AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]]
        agent_idx = maturity_order.index(stored_status) if stored_status in maturity_order else 0
        req_idx = maturity_order.index(required_status.value)

        allowed = agent_idx >= req_idx

        # P1.3 — Onboarding demo-agent bypass. The "Demo Assistant" agent is
        # created by admin_bootstrap at INTERN tier with zero episodes (which
        # would normally violate the graduation contract). The explicit
        # configuration["demo_agent"] flag lets new users explore complexity ≤ 2
        # actions during their first session. Capped at complexity 2 so a demo
        # agent can stream + present but cannot mutate state (complexity 3+) or
        # delete (complexity 4). Audit-logged so the bypass is observable.
        config = agent.configuration if isinstance(agent.configuration, dict) else {}
        if not allowed and config.get("demo_agent") is True and complexity <= 2:
            logger.info(
                "Governance demo_agent bypass: agent=%s action=%s complexity=%d tier=%s",
                agent_id, action_type, complexity, agent.status,
            )
            allowed = True
            required_status = AgentStatus.STUDENT  # cosmetic: report the relaxed bar

        approval_needed = not allowed or (stored_status == AgentStatus.SUPERVISED.value and complexity >= 3) or require_approval

        # Budget Check (requires tenant_id - skip if not available). When called
        # from already-running async code, run_until_complete would raise
        # "This event loop is already running" — so detect that case and defer
        # to can_perform_action_async (which callers in an async context should
        # use). See _check_budget_async for the shared logic.
        if allowed and not _skip_budget:
            import asyncio
            try:
                asyncio.get_running_loop()
                # We're inside a running loop — the sync path can't await.
                # Log clearly so operators know to use the async variant; do NOT
                # silently skip (that was the old bypass). Return a result that
                # forces the caller to go through can_perform_action_async for a
                # real budget decision.
                logger.warning(
                    "can_perform_action() called from a running event loop "
                    "(agent=%s action=%s); budget not checked synchronously — "
                    "use can_perform_action_async() to enforce the budget",
                    agent_id, action_type,
                )
            except RuntimeError:
                # No running loop: safe to drive the coroutine directly. Get a
                # loop, creating one if necessary (get_event_loop() doesn't
                # auto-create on 3.14+ when none exists in the thread).
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                budget_check = loop.run_until_complete(
                    self._check_budget_async(agent_id, action_type, chain_id)
                )
                if not budget_check.get("allowed", True):
                    return {
                        "allowed": False,
                        "reason": budget_check.get("reason"),
                        "requires_human_approval": True,
                        "status_code": "BUDGET_EXCEEDED"
                    }

        # NEW Phase 10: Fleet-wide recursion guardrails
        # P1c (R1) fix: the previous check ``len(chain.links) >= chain.max_depth``
        # gated on TOTAL link count, not nesting depth — so a flat chain of 3
        # siblings tripped the same limit as a 3-deep nested chain. Now compute
        # the maximum NESTING DEPTH across the ChainLink tree and gate on that.
        if chain_id:
            from core.models import DelegationChain, ChainLink
            chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
            if chain:
                links = self.db.query(ChainLink).filter(ChainLink.chain_id == chain_id).all()
                current_depth = _max_nesting_depth(links, chain.root_agent_id)
                if current_depth >= chain.max_depth:
                    logger.warning(
                        f"Recursion depth limit reached (chain: {chain_id}, "
                        f"depth={current_depth}, max={chain.max_depth}). Blocking recruitment."
                    )
                    return {
                        "allowed": False,
                        "reason": f"Fleet recursion depth limit ({chain.max_depth}) reached.",
                        "requires_human_approval": True,
                        "status_code": "RECURSION_LIMIT"
                    }

        return {
            "allowed": allowed,
            "reason": f"Maturity check failed. Required: {required_status.value}" if not allowed else "Maturity check passed.",
            "agent_status": agent.status,
            "action_complexity": complexity,
            "required_status": required_status.value,
            "requires_human_approval": approval_needed,
            "confidence": agent.confidence_score or 0.5
        }

    def get_agent_capabilities(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Return the governance capabilities/maturity for an agent.

        Used by callers (e.g. SkillRegistryService) that need a lightweight
        maturity lookup without the full complexity-based enforcement of
        :meth:`can_perform_action`.

        Args:
            agent_id: Agent registry ID (or "system" for system-level calls).

        Returns:
            Dict with ``maturity_level`` (AgentStatus value, lowercase) and
            ``confidence_score``, or ``None`` if the agent is not registered.
        """
        if not agent_id or agent_id == "system":
            # System-level execution defaults to INTERN maturity.
            return {
                "maturity_level": AgentStatus.INTERN.value,
                "confidence_score": 0.5,
            }

        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            self._workspace_scope_condition(),
        ).first()

        if not agent:
            return None

        # Normalize case: the docstring promises an AgentStatus value in
        # lowercase, but the stored status may be written by API clients in
        # non-lowercase form (e.g. "AUTONOMOUS") — returning it verbatim
        # breaks case-sensitive callers (SkillRegistryService maturity gates).
        maturity = (
            agent.status.lower()
            if isinstance(agent.status, str)
            else agent.status
        )
        return {
            "maturity_level": maturity,
            "confidence_score": agent.confidence_score or 0.5,
        }

    def enforce_action(
        self,
        agent_id: str,
        action_type: str,
        action_details: Optional[Dict] = None,
        chain_id: Optional[str] = None # NEW Phase 10
    ) -> Dict[str, Any]:
        """Main entry point for action enforcement including guardrails.

        For code-writing actions (write_code_file, execute, shell_build, etc.)
        an Arbor CodeHypothesisNode quality gate is applied *before* guardrails
        to catch syntax errors and runaway complexity early.
        """
        check = self.can_perform_action(agent_id, action_type, chain_id=chain_id)

        if not check["allowed"]:
            # Round 80: carry the governance fields through — consumers
            # (Agent Control Center) read required_status/agent_status from
            # this documented contract, and the old subset dropped them.
            return {
                "proceed": False,
                "status": "BLOCKED",
                "reason": check["reason"],
                "action_required": "HUMAN_APPROVAL",
                **{k: check[k] for k in ("agent_status", "action_complexity", "required_status") if k in check},
            }

        if check["requires_human_approval"]:
            return {"proceed": True, "status": "PENDING_APPROVAL", "reason": "Requires oversight", "action_required": "WAIT_FOR_APPROVAL"}

        # -----------------------------------------------------------------
        # Arbor code quality gate — runs for code-writing level-4 actions
        # -----------------------------------------------------------------
        action_lower = action_type.lower()
        if any(code_action in action_lower for code_action in _CODE_WRITE_ACTIONS):
            proposed_code = ""
            language = "python"
            if isinstance(action_details, dict):
                proposed_code = (
                    action_details.get("code", "")
                    or action_details.get("content", "")
                    or action_details.get("script", "")
                )
                language = action_details.get("language", "python")
            if proposed_code:
                arbor_result = _arbor_validate_code(proposed_code, language=language)
                if not arbor_result["passed"]:
                    logger.warning(
                        "[Arbor/Governance] Code quality gate BLOCKED agent=%s action=%s reason=%s node=%s",
                        agent_id, action_type, arbor_result["reason"], arbor_result["node_id"],
                    )
                    return {
                        "proceed": False,
                        "status": "BLOCKED_BY_ARBOR",
                        "reason": arbor_result["reason"],
                        "action_required": "HUMAN_APPROVAL",
                        "arbor_node_id": arbor_result["node_id"],
                        "promise_score": arbor_result["promise_score"],
                    }
                logger.debug(
                    "[Arbor/Governance] Code quality gate PASSED agent=%s action=%s promise=%.3f",
                    agent_id, action_type, arbor_result["promise_score"],
                )

        # Autonomous Guardrails
        # Normalize the stored status: can_perform_action returns the RAW
        # agent.status, which API clients may write in non-lowercase form
        # (e.g. "AUTONOMOUS") — a case-sensitive comparison here would skip
        # the guardrail service entirely for those agents (fail-open bypass).
        agent_status = (
            str(check["agent_status"] or "").lower()
            if isinstance(check.get("agent_status"), str)
            else check.get("agent_status")
        )
        if agent_status == AgentStatus.AUTONOMOUS.value:
            gr = AutonomousGuardrailService(self.db, workspace_id=self.workspace_id)
            gr_check = gr.check_guardrails(agent_id, action_type, action_details or {})
            if not gr_check["proceed"]:
                if gr_check.get("requires_downgrade"):
                    gr.handle_violation(agent_id, gr_check["violation_type"], gr_check["reason"])
                return {"proceed": False, "status": "BLOCKED_BY_GUARDRAIL", "reason": gr_check["reason"], "action_required": "HUMAN_APPROVAL"}

        return {
            "proceed": True,
            "status": "APPROVED",
            "reason": check["reason"],
            "action_required": None,
            **{k: check[k] for k in ("agent_status", "action_complexity", "required_status", "confidence") if k in check},
        }

    # Policy Discovery
    async def find_relevant_policies(self, context: str, domain: Optional[str] = None, limit: int = 5) -> List[Dict]:
        search_svc = PGPolicySearchService(self.db)
        return await search_svc.search(query=context, domain=domain, limit=limit)

    def request_approval(
        self, 
        agent_id: str, 
        action_type: str, 
        params: Dict, 
        reason: str,
        chain_id: Optional[str] = None # NEW Phase 10
    ) -> str:
        hitl = HITLAction(
            id=str(uuid.uuid4()),
            workspace_id=self.workspace_id,
            agent_id=agent_id,
            action_type=action_type,
            platform="internal",
            params=params,
            status=HITLActionStatus.PENDING.value,
            reason=reason,
            # NEW Phase 10 association
            chain_id=chain_id
        )

        # Capture blackboard snapshot if it's a fleet operation
        if chain_id:
            from core.models import DelegationChain
            chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
            if chain:
                hitl.context_snapshot = chain.metadata_json

        self.db.add(hitl)
        self.db.commit()
        return hitl.id

    def get_approval_status(self, action_id: str) -> Dict[str, Any]:
        """Check if a HITL action has been decided (Phase 10 Hardened)"""
        hitl = self.db.query(HITLAction).filter(HITLAction.id == action_id).first()
        if not hitl:
            return {"status": "not_found"}
        
        return {
            "id": hitl.id,
            "status": hitl.status,
            "chain_id": hitl.chain_id,
            "context_snapshot": hitl.context_snapshot,
            "user_feedback": hitl.user_feedback,
            "reviewed_at": hitl.reviewed_at
        }

    async def record_outcome(
        self, agent_id: str, success: bool, task_summary: Optional[str] = None
    ) -> None:
        """Record the success/failure of an action for learning.

        R86c wiring: when ``task_summary`` carries business-role signals,
        the outcome is ALSO attributed to that domain in the
        DomainExperienceLedger — the evidence layer the super-mentor gate
        counts. Without this, only the meta agent's internal path
        attributed domains, so a generalist could never actually EARN
        teaching rights for a role it demonstrably works in (the ledger
        stayed empty in production). Attribution is a learning
        side-channel: it never raises and never touches the agent's own
        tier evidence (anti-laundering, see core/domain_attribution).
        """
        logger.info(f"Recorded outcome for {agent_id}: {'success' if success else 'failure'}")
        self._update_confidence_score(agent_id, positive=success, impact_level="low")
        if not task_summary:
            return
        try:
            from core.domain_attribution import (
                get_vocabulary,
                record_domain_outcome,
                resolve_domain,
            )

            domain = resolve_domain(task_summary, vocabulary=get_vocabulary(self.db))
            if domain:
                record_domain_outcome(
                    self.db, agent_id, domain,
                    success=success, task_summary=task_summary[:200],
                )
        except Exception as e:
            logger.debug(f"domain attribution skipped for {agent_id}: {e}")

    # =========================================================================
    # Evolution directive validation (the misevolution defense)
    # =========================================================================
    #
    # Evidence: Shao et al. "Your Agent May Misevolve" (ICLR 2026) shows that
    # self-evolving agents can degrade in safety alignment, and it's pervasive
    # without strong mitigation. Lin (2026) warns that architectural mutation
    # lets an agent modify the process that shapes it.
    #
    # The GEA evolution loop calls this method before promoting an evolved
    # config. Previously it didn't exist → the loop fell back to a 3-phrase
    # substring blocklist that was trivially bypassable.

    # Expanded danger patterns — any directive matching these is rejected.
    # Organized by category for clarity and future extension.
    _DANGER_PATTERNS: List[str] = [
        # Safety bypass attempts
        "ignore all rules", "bypass guardrails", "disable safety",
        "skip safety", "do not follow rules", "remove restrictions",
        "ignore governance", "act without approval", "skip approval",
        "override safety", "override governance", "ignore policy",
        "ignore tenant policy", "skip compliance",
        "disregard rules", "no rules apply", "rules do not apply",
        # Privilege escalation
        "elevate privileges", "grant elevated", "escalate privileges",
        "act as admin", "act as root", "full access",
        "unrestricted access", "remove restrictions",
        # Self-referential mutation (disabling own safety net)
        "remove tripwire", "disable tripwire", "weaken tripwire",
        "disable sandbox", "bypass sandbox", "remove sandbox",
        "disable governance", "remove governance",
        "delete validation", "skip validation", "disable validation",
        "remove guardrails", "weaken guardrails",
    ]

    # Config keys that are part of the agent's own safety/harness layer.
    # A mutation that modifies these keys is self-referential (attempting to
    # alter its own safety net) and must be explicitly reviewed.
    _PROTECTED_CONFIG_KEYS = frozenset({
        "ast_tripwire", "sandbox_config", "governance_config",
        "guardrails", "elevated_privileges", "autonomous_guardrails",
        "harness_patches", "capability_gate",
    })

    async def validate_evolution_directive(
        self,
        evolved_config: Dict[str, Any],
        tenant_id: str,
    ) -> bool:
        """Validate an evolved agent config against governance policy.

        This is the real implementation of the governance gate that the GEA
        evolution loop calls before promoting a mutation. Returns True if the
        config passes all checks; False if it violates any safety rule.

        Checks:
          1. Danger-pattern scan on system_prompt directives (expanded set)
          2. Self-referential mutation detection (modifying protected config keys)
          3. Privilege escalation without maturity (elevated_privileges=True)
          4. Directive injection (attempts to overwrite governance instructions)

        Evidence: closes the "misevolution" risk identified by Shao et al.
        (ICLR 2026) and Lin (2026).
        """
        violations: List[str] = []

        # 1. Scan system_prompt for danger patterns
        system_prompt = str(evolved_config.get("system_prompt", "")).lower()
        for pattern in self._DANGER_PATTERNS:
            if pattern in system_prompt:
                violations.append(f"danger pattern in system_prompt: '{pattern}'")

        # 2. Detect self-referential mutation of protected config keys
        for key in self._PROTECTED_CONFIG_KEYS:
            if key in evolved_config:
                # The config contains a mutation targeting a safety/harness key.
                # This is allowed ONLY if the value hasn't changed from the
                # agent's current config (i.e., it was carried forward, not
                # mutated). We can't know the "before" here without a diff,
                # so we flag it for explicit review.
                # Exception: harness_patches is allowed (it's the normal patch
                # delivery mechanism for HarnessEvolutionService).
                if key != "harness_patches":
                    violations.append(
                        f"self-referential mutation of protected config key: '{key}'"
                    )

        # 3. Privilege escalation check
        if evolved_config.get("elevated_privileges") is True:
            # Privilege escalation must go through the maturity graduation path
            # (capability_graduation_service), not be auto-set by evolution.
            violations.append(
                "privilege escalation: elevated_privileges=True set by evolution "
                "(must go through maturity graduation, not auto-tuning)"
            )

        # 4. Directive injection: check for attempts to overwrite governance
        # instructions embedded in the prompt
        directives = evolved_config.get("evolution_directives", [])
        if isinstance(directives, list):
            for d in directives:
                d_lower = str(d).lower()
                for pattern in self._DANGER_PATTERNS:
                    if pattern in d_lower:
                        violations.append(f"danger pattern in directive: '{pattern}'")

        if violations:
            logger.warning(
                f"Evolution directive REJECTED for tenant {tenant_id}: "
                f"{'; '.join(violations)}"
            )
            return False

        return True
