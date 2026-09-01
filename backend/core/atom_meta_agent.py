"""
Atom Meta-Agent - Central Orchestrator for ATOM Platform
The main intelligent agent that can spawn specialty agents and access all platform features.
"""

import json
import logging
import os
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.models import (
    AgentRegistry, AgentStatus, User, HITLActionStatus, AgentExecution, NEW_AGENT_CONFIDENCE,
    Workspace, AgentReasoningStep, ExecutionStatus, AgentTriggerMode,
    ChainLink,
)
from core.database import SessionLocal
import traceback
from core.agent_world_model import WorldModelService, AgentExperience
from core.agent_governance_service import AgentGovernanceService
from core.agent_fleet_service import AgentFleetService
from analytics.fleet_optimization_service import FleetOptimizationService
from core.capability_graduation_service import CapabilityGraduationService
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from integrations.mcp_service import mcp_service
from ai.nlp_engine import NaturalLanguageEngine, CommandIntentResult, CommandType
from typing import Literal
from core.canvas_context_provider import get_canvas_provider, CanvasContext
from core.agents.queen_agent import QueenAgent
from core.react_models import ReActStep
from core.tool_outcome_verifier import parse_tool_outcome

# Per-turn durable-fact extraction (Hermes-style memory layer).
# Fire-and-forget — never blocks the ReAct loop. Feature-flag default OFF.
# See docs/architecture/CONTEXT_MEMORY.md.
from core.turn_fact_extractor import (
    TURN_FACT_EXTRACTION_ENABLED as _TURN_FACT_EXTRACTION_ENABLED,
    TURN_FACT_VECTOR_RECALL_ENABLED as _TURN_FACT_VECTOR_RECALL_ENABLED,
    get_active_facts_for_prompt as _get_active_facts_for_prompt,
    get_turn_fact_extractor,
    prefetch_relevant_facts as _prefetch_relevant_facts,
    prompt_sensitivity_ceiling as _prompt_ceiling,
)
_pending_extraction_tasks: set = set()  # module-level — prevents GC of in-flight tasks


def _is_error_observation(observation: Any) -> bool:
    """Heuristic: does a tool observation look like an error / blocked result?

    Used by the in-loop self-correction hook (Workstream A) to append a
    deterministic [CRITIQUE] directive when the model should re-plan instead
    of repeating the same failing action. Conservative marker set — a normal
    tool result that merely contains the word "error" inside JSON would be a
    false positive, so we anchor on the platform's canonical failure phrasings.
    """
    if observation is None:
        return False
    text = str(observation).lower()
    return any(
        marker in text
        for marker in (
            "tool error.",
            "tool execution failed",
            "governance blocked",
            "governance error",
            "was rejected",
            "rejected or timed out",
            "sandbox blocked",
            "sandbox error",
        )
    )


# LLM Integration:
# Uses LLMService for unified LLM interactions (BYOK key resolution, cost tracking, observability).
# Initialized via get_llm_service() singleton factory for workspace-aware service.
# All LLM calls (generate_response, generate_structured_response) go through self.llm.

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# R87: execution-outcome classification for learning signals.
#
# Module scope so it's unit-testable without the AtomMetaAgent singleton.
# The terminal failure statuses below carry canned final text with no literal
# "error" substring ("Maximum reasoning steps reached.", "Budget limit
# reached…", "Agent run killed by sandbox: …"). Classifying them via the old
# final_output heuristic recorded timeouts / budget halts / sandbox kills to
# AgentGovernanceService.record_outcome and the DomainExperienceLedger as
# SUCCESSES — a deployment that repeatedly hit limits earned super-mentor
# wins from its failures. Terminal statuses always win; the legacy heuristic
# only applies when no recognized status is present (legacy callers).
# ---------------------------------------------------------------------------
_TERMINAL_FAILURE_STATUSES = frozenset({
    "failed",
    "timeout",
    "budget_exceeded",
    "killed_sandbox",
    "error",
})


def _execution_succeeded(result: Dict) -> bool:
    """Classify a meta-agent run outcome for learning/governance signals."""
    status = str(result.get("status") or "").strip().lower()
    if status in _TERMINAL_FAILURE_STATUSES:
        return False
    if status == "success":
        return True
    final_output = result.get("final_output")
    return bool(final_output) and "error" not in str(final_output).lower()


# ---------------------------------------------------------------------------
# Execution Sandbox Layer (Round 43 / Phase A) — module-level helper.
#
# Defined at module scope so it's unit-testable without the AtomMetaAgent
# singleton. Lazy imports keep cost zero when the sandbox master switch is
# off. Mirrors the helper pattern in ``core/mcp_service.py``.
# ---------------------------------------------------------------------------
def _meta_agent_sandbox_check(tool_name: str, args: Dict[str, Any], context: Dict[str, Any]):
    """Evaluate this tool call against the run's sandbox policy.

    Returns a ``SandboxDecision`` or ``None`` when no policy is in scope.
    Writes an audit row on any non-allowed decision. Never raises — a
    broken sandbox fails open (returns ALLOWED with metadata_json.error).
    """
    try:
        from core import sandbox_config
        from core.sandbox_policy import PolicyIssuer, SandboxDecision, ALLOWED
        from core.sandbox_audit import write_violation

        if not sandbox_config.is_sandbox_enabled():
            return None

        run_id = context.get("run_id") or context.get("execution_id")
        if not run_id:
            return None

        tier = (context.get("tier_at_issuance") or context.get("tier") or "").lower()
        if not tier:
            return None

        issuer = PolicyIssuer()
        policy = issuer.issue(
            run_id=run_id,
            agent_id=context.get("agent_id", "atom_main"),
            tier_at_issuance=tier,
            workspace_data_root=context.get("workspace_data_root"),
        )
        decision = issuer.check(
            policy=policy,
            tool_name=tool_name,
            args=args,
            context=context,
            phase="A",
        )

        # Phase B: filesystem scope check (only if Phase A allowed and
        # the FS sub-feature is enabled).
        if decision.is_allowed and sandbox_config.is_sandbox_fs_enabled():
            from core.sandbox_fs import validate as fs_validate

            fs_decision = fs_validate(policy, tool_name, args, context=context)
            if fs_decision.requires_review:
                decision = fs_decision

        # Phase C: tripwires + caps (Phase C).
        if decision.is_allowed and sandbox_config.is_sandbox_tripwires_enabled():
            from core import sandbox_tripwire

            tw_decision = sandbox_tripwire.check(
                tool_name=tool_name,
                args=args,
                args_hash=decision.args_hash,
                context=context,
            )
            if tw_decision.decision != "allowed":
                decision = tw_decision
                if decision.killrun_triggered and sandbox_config.is_sandbox_force_enforce_enabled():
                    from core import sandbox_killrun

                    sandbox_killrun.trigger_killrun(
                        run_id,
                        reason=decision.violation_detail or "tripwire",
                        tripwire_id=decision.metadata_json.get("tripwire_id"),
                        execution_id=run_id,
                    )

        if decision.is_allowed and sandbox_config.is_sandbox_caps_enabled():
            from core import sandbox_caps

            cap_decision = sandbox_caps.check_caps(
                policy,
                tool_name=tool_name,
                args=args,
                args_hash=decision.args_hash,
                context=context,
            )
            if cap_decision.requires_review:
                decision = cap_decision

        # KillRun guard.
        from core import sandbox_killrun

        sandbox_killrun.guard(run_id)
        if decision.requires_review:
            write_violation(
                decision,
                tenant_id=context.get("tenant_id"),
                workspace_id=context.get("workspace_id"),
                agent_id=context.get("agent_id"),
                user_id=context.get("user_id"),
                session_id=context.get("session_id"),
                run_id=run_id,
            )
        return decision
    except Exception as e:  # noqa: BLE001
        # KillRunAborted must propagate — it's how tripwire kills abort the
        # AgentExecution. All other exceptions fail open.
        from core.sandbox_killrun import KillRunAborted

        if isinstance(e, KillRunAborted):
            raise
        logger.debug("meta-agent sandbox check failed open for %s: %s", tool_name, e)
        from core.sandbox_policy import SandboxDecision, ALLOWED

        return SandboxDecision(
            decision=ALLOWED,
            phase="A",
            tool_name=tool_name,
            metadata_json={"error": str(e)},
        )


class ToolCall(BaseModel):
    tool: str = Field(..., description="Name of the tool to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool")

class ReActStep(BaseModel):
    thought: str = Field(..., description="The reasoning behind the current action or final answer")
    action: Optional[ToolCall] = Field(None, description="The tool to call if further action is needed")
    actions: Optional[List[ToolCall]] = Field(None, description="Multiple INDEPENDENT tools to execute in parallel in this step (Workstream G). Tools that depend on each other's output must NOT be batched here.")
    final_answer: Optional[str] = Field(None, description="The final response if the task is complete")
    confidence: float = Field(0.9, description="Confidence score for this step")


# ============================================================================
# INTENT CLASSIFICATION (Phase 256-07)
# ============================================================================

class IntentCategory(Enum):
    """Categories for intent classification."""
    CHAT = "chat"
    WORKFLOW = "workflow"
    TASK = "task"


class IntentClassification(BaseModel):
    """Result of intent classification."""
    category: IntentCategory = Field(description="Classified intent category")
    confidence: float = Field(description="Classification confidence (0-1)")
    reasoning: str = Field(description="Explanation of classification")
    is_structured: bool = Field(default=False, description="Request has structured format")
    is_long_horizon: bool = Field(default=False, description="Long-running task")
    requires_agent_recruitment: bool = Field(default=False, description="Needs specialist agents")
    blueprint_applicable: bool = Field(default=False, description="Workflow blueprint applicable")


class SpecialtyAgentTemplate:
    """Templates for common specialty agents"""
    TEMPLATES = {
        "finance_analyst": {
            "name": "Finance Analyst",
            "category": "Finance",
            "description": "Analyzes financial data, reconciles accounts, generates reports",
            "capabilities": [
                "reconciliation", "expense_analysis", "budget_tracking", "query_financial_metrics",
                "ingest_knowledge_from_text", "ingest_knowledge_from_file", "query_knowledge_graph", "search_formulas",
                "create_invoice", "push_to_integration", "create_record", "update_record",
                "discover_connections", "global_search"
            ],
            "default_params": {"focus": "cost_optimization"}
        },
        "sales_assistant": {
            "name": "Sales Assistant", 
            "category": "Sales",
            "description": "Manages leads, tracks opportunities, generates outreach",
            "capabilities": [
                "lead_scoring", "crm_sync", "email_outreach",
                "ingest_knowledge_from_text", "ingest_knowledge_from_file", "query_knowledge_graph", "search_formulas",
                "update_crm_lead", "create_crm_deal", "update_crm_deal", "push_to_integration", "create_record", "update_record",
                "discover_connections", "global_search"
            ],
            "default_params": {"pipeline": "default"}
        },
        "ops_coordinator": {
            "name": "Operations Coordinator",
            "category": "Operations",
            "description": "Manages inventory, logistics, vendor relationships",
            "capabilities": [
                "inventory_check", "order_tracking", "vendor_management",
                "ingest_knowledge_from_text", "ingest_knowledge_from_file", "query_knowledge_graph", "search_formulas",
                "update_task", "push_to_integration", "create_ecommerce_order", "create_record", "update_record",
                "discover_connections", "global_search"
            ],
            "default_params": {"region": "all"}
        },
        "hr_assistant": {
            "name": "HR Assistant",
            "category": "HR",
            "description": "Handles onboarding, policy queries, leave management",
            "capabilities": [
                "onboarding", "policy_lookup", "leave_tracking",
                "ingest_knowledge_from_text", "ingest_knowledge_from_file", "query_knowledge_graph", "search_formulas",
                "update_task", "push_to_integration", "create_record", "update_record",
                "discover_connections", "global_search"
            ],
            "default_params": {}
        },
        "procurement_specialist": {
            "name": "Procurement Specialist",
            "category": "Operations",
            "description": "Handles B2B procurement, PO extraction, and integration sync",
            "capabilities": [
                "b2b_extract_po", "b2b_create_draft_order", "b2b_push_to_integrations",
                "ingest_knowledge_from_text", "ingest_knowledge_from_file", "query_knowledge_graph", "search_formulas",
                "push_to_integration"
            ],
            "default_params": {"automation_level": "high"}
        },
        "knowledge_analyst": {
            "name": "Knowledge Analyst",
            "category": "Intelligence",
            "description": "Processes unstructured data into knowledge graph and answers complex queries",
            "capabilities": [
                "ingest_knowledge_from_text", "ingest_knowledge_from_file", "query_knowledge_graph", "search_formulas", "web_search",
                "push_to_integration", "upload_file_to_storage", "create_storage_folder", "create_record", "update_record",
                "discover_connections", "global_search"
            ],
            "default_params": {"retrieval_mode": "hybrid"}
        },
        "marketing_analyst": {
            "name": "Marketing Analyst",
            "category": "Marketing",
            "description": "Analyzes campaigns, tracks metrics, generates insights",
            "capabilities": [
                "campaign_analysis", "audience_insights", "content_suggestions",
                "ingest_knowledge_from_text", "ingest_knowledge_from_file", "query_knowledge_graph", "search_formulas",
                "push_to_integration", "add_marketing_subscriber", "create_record", "update_record",
                "discover_connections", "global_search"
            ],
            "default_params": {"channels": ["email", "social"]}
        },
        "king_agent": {
            "name": "King Agent",
            "category": "Governance",
            "description": "Sovereign executive that executes blueprints and manages multi-agent swarms",
            "capabilities": ["execute_blueprint", "sovereign_governance", "delegate_task"],
            "module_path": "core.agents.king_agent",
            "class_name": "KingAgent",
            "default_params": {}
        }
    }



# LLM Integration:
# Uses LLMService for unified LLM interactions (BYOK key resolution, cost tracking, observability).
# All LLM calls (generate_completion, generate_structured_response) go through self.llm.


def ensure_atom_registry_persisted(db) -> "AgentRegistry":
    """Get-or-create the persisted ``atom_main`` registry row (R81b G6).

    ``_get_atom_registry()`` builds an ephemeral in-memory row that is never
    committed, so ``record_outcome("atom_main")`` found no DB row and silently
    no-op'd — the meta-agent's confidence-based learning loop never advanced,
    and governance lookups for the id returned "Agent not found". Idempotent:
    returns the existing row when present.
    """
    row = db.query(AgentRegistry).filter(AgentRegistry.id == "atom_main").first()
    if row:
        return row
    row = AgentRegistry(
        id="atom_main",
        name="Atom",
        category="system",  # System-agent label — matches the Chat Assistant seed convention
        description="Central orchestrator agent",
        # NOT NULL without defaults — the in-memory _get_atom_registry()
        # template omits these, which only surfaces when persisting.
        module_path="core.atom_meta_agent",
        class_name="AtomMetaAgent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=1.0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class AtomMetaAgent:
    """
    The central Atom agent that orchestrates all platform capabilities.
    Can spawn specialty agents, access memory, trigger workflows, and call integrations.
    Uses a Robust ReAct Loop with Pydantic validation at each step.
    """
    
    CORE_TOOLS_NAMES = [
        "mcp_tool_search",
        "save_business_fact",
        "verify_citation",
        "ingest_knowledge_from_text",
        "ingest_knowledge_from_file",
        "query_knowledge_graph",
        # Memory self-service (P1.1 tool equality — the meta agent could
        # query the graph but not search documents, remember/forget facts,
        # or search conversation memory):
        "documents.search",
        "search_communications",
        "recall_episodes",
        "memory_remember",
        "memory_forget",
        "trigger_workflow",
        "invoke_capability",
        "recruit_fleet",    # NEW: Multi-agent orchestration
        "delegate_task",
        "request_human_intervention",
        "get_system_health",
        "list_integrations",
        "call_integration",  # Fallback
        "canvas_tool",
        # Platform & Management Tools
        "get_platform_settings",
        "update_platform_setting",
        "update_tenant_profile",
        "set_byok_api_key",
        "list_tenant_members",
        "manage_tenant_member",
        "manage_workspace",
        "manage_team"
    ]

    def __init__(self, workspace_id: str = "default", tenant_id: Optional[str] = None, user: Optional[User] = None):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id or "default"
        self.user = user
        self.world_model = WorldModelService(workspace_id=workspace_id)
        self.orchestrator = AdvancedWorkflowOrchestrator()
        
        # Capability Graduation Integration
        with SessionLocal() as db:
            self.graduation_service = CapabilityGraduationService(db)
            
        self.spawned_agents: Dict[str, AgentRegistry] = {}
        self.mcp = mcp_service  # MCP access for tools
        
        # Access LLMService via ServiceFactory
        from core.service_factory import ServiceFactory
        self.llm = ServiceFactory.get_llm_service(
            workspace_id=self.workspace_id,
            tenant_id=self.tenant_id
        )
        
        self.session_tools: List[Dict[str, Any]] = [] # Usage: Dynamically added tools
        self.canvas_provider = get_canvas_provider()  # Canvas context provider
        self.queen = None # Lazy loaded

        # Stage router (Switchyard port): tier group of the previous ReAct
        # turn (``capable``/``efficient``), tracked so handoff notes fire on
        # group switches. None = first turn of the run.
        self._stage_group: Optional[str] = None

        
    async def execute(self, request: str, context: Dict[str, Any] = None,
                      trigger_mode: AgentTriggerMode = AgentTriggerMode.MANUAL,
                      step_callback: Optional[callable] = None,
                      execution_id: str = None,
                      canvas_context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Auditing bracket around the meta-agent run (R84c parity).

        Binds run identity (agent_id='atom_main', execution_id) for every
        log_agent_action / log_llm_call inside the loop, brackets the run
        with execution_start / execution_complete events, and runs the
        audit-completeness gate on close-out. Unbind is guaranteed on both
        success and exception paths; audit failures never break the run.
        Delegates to ``execute_unaudited`` (the ReAct body).
        """
        context = context or {}
        from core.agent_action_audit import bind_audit_context, log_agent_action

        exec_uuid = execution_id or str(uuid.uuid4())
        _audit_token = None
        try:
            _audit_token = bind_audit_context(
                "atom_main",
                exec_uuid,
                user_id=context.get("user_id"),
                workspace_id=self.workspace_id,
            )
            log_agent_action(
                action="execution_start",
                description=f"Meta-agent run started: {request[:200]}",
                metadata={"task_input": request[:2000],
                          "trigger_mode": trigger_mode.value},
                success=True,
            )
        except Exception:  # noqa: BLE001 — auditing must never block runs
            _audit_token = None

        try:
            result = await self.execute_unaudited(
                request, context=context, trigger_mode=trigger_mode,
                step_callback=step_callback, execution_id=execution_id,
                canvas_context=canvas_context,
            )
        except Exception as run_err:
            self._close_audit_bracket(
                exec_uuid, status="failed", actions_executed=[],
                success=False, error_message=str(run_err)[:2000],
                token=_audit_token,
            )
            raise

        steps = result.get("actions_executed") or []
        status = result.get("status", "success")
        self._close_audit_bracket(
            exec_uuid, status=status, actions_executed=steps,
            success=(status == "success"),
            error_message=None, token=_audit_token,
        )
        return result

    def _close_audit_bracket(self, exec_uuid: str, status: Any,
                             actions_executed: list, success: bool,
                             error_message: Optional[str], token) -> None:
        """Write execution_complete + completeness gate + unbind. Never raises."""
        try:
            from core.agent_action_audit import (
                check_execution_audit_completeness,
                log_agent_action,
                unbind_audit_context,
            )
            log_agent_action(
                action="execution_complete",
                description=f"Meta-agent run finished with status {status}",
                metadata={
                    "status": status,
                    "steps": len(actions_executed),
                    "task_input": None,
                },
                success=success,
                error_message=error_message,
            )
            tool_steps = sum(1 for s in actions_executed if s.get("action"))
            completeness = check_execution_audit_completeness(
                exec_uuid,
                expected_tool_calls=tool_steps,
                expected_llm_calls=len(actions_executed),
            )
            if not completeness.get("complete"):
                logger.error("AUDIT GAP for execution %s: %s", exec_uuid, completeness)
        except Exception as audit_close_err:  # noqa: BLE001
            logger.debug(f"audit close-out skipped: {audit_close_err}")
        finally:
            if token is not None:
                try:
                    from core.agent_action_audit import unbind_audit_context
                    unbind_audit_context(token)
                except Exception:  # noqa: BLE001
                    pass

    def _ledger_llm_decision(self, model: str, prompt: Any, response: Any,
                             provider: str = "llm_service") -> None:
        """Ledger one ReAct LLM decision into the per-decision audit trail.

        No-op outside an agent run (no bound context — log_llm_call returns
        None), so platform traffic is not flooded. Never raises into the loop.
        """
        try:
            from core.agent_action_audit import log_llm_call
            log_llm_call(
                model=str(model or "auto"),
                prompt=prompt,
                response=response,
                provider=provider,
            )
        except Exception:  # noqa: BLE001
            pass

    async def execute_unaudited(self, request: str, context: Dict[str, Any] = None,
                                trigger_mode: AgentTriggerMode = AgentTriggerMode.MANUAL,
                                step_callback: Optional[callable] = None,
                                execution_id: str = None,
                                canvas_context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Main entry point for Atom. Uses Robust ReAct Loop with Pydantic validation.
        Based on 2025 Architecture: PydanticAI wraps each step in a validation layer.
        """
        context = context or {}
        if "original_request" not in context:
            context["original_request"] = request

        logger.info(f"Atom executing request: {request[:50]}... (mode: {trigger_mode.value})")

        # Tier-2 semantic recall — called ONCE per execute(), not per ReAct step.
        # Embeds the query (10-20ms), searches LanceDB, hydrates from SQL.
        # Gated by TURN_FACT_VECTOR_RECALL_ENABLED (default OFF). Never raises.
        if _TURN_FACT_VECTOR_RECALL_ENABLED:
            try:
                prefetched = _prefetch_relevant_facts(
                    workspace_id=self.workspace_id, query=request, limit=5,
                    max_sensitivity=_prompt_ceiling(),
                )
                if prefetched:
                    context.setdefault("prefetched_facts", []).extend(prefetched)
            except Exception as e:
                logger.debug(f"vector recall prefetch failed: {e}")

        # WORKSPACE FIELD GUIDE — curated memory snapshot (Workstream E).
        # Read once per execute() (filesystem hit), cached in context, then
        # consumed in _react_step memory assembly. Never raises.
        try:
            from core.field_guide_service import get_field_guide_service
            context["_field_guide_context"] = get_field_guide_service().get_field_guide_context(self.workspace_id)
        except Exception as e:
            context["_field_guide_context"] = ""
            logger.debug(f"field guide recall failed: {e}")
        
        start_time = datetime.now(timezone.utc)
        execution_id = execution_id or str(uuid.uuid4())

        # R81b (G6): make sure the atom_main registry row actually exists so
        # governance checks and the end-of-run record_outcome() hit a real DB
        # row instead of silently no-op'ing. Never raises.
        try:
            with SessionLocal() as _reg_db:
                ensure_atom_registry_persisted(_reg_db)
        except Exception as _reg_err:
            logger.debug(f"atom_main registry ensure skipped: {_reg_err}")

        # P9: thread the run identity + tier into the dispatch context. Without
        # run_id/tier, the shared sandbox gate (and _meta_agent_sandbox_check)
        # returns None — "no policy in scope" — so the default-on sandbox never
        # engaged on this, the primary agent surface: every tool call ran
        # ungated. setdefault keeps caller-supplied values authoritative.
        try:
            _tier = (self._get_atom_registry().status or "autonomous").lower()
        except Exception:  # noqa: BLE001 — a registry hiccup must not break runs
            _tier = "autonomous"
        context.setdefault("run_id", execution_id)
        context.setdefault("execution_id", execution_id)
        context.setdefault("tier_at_issuance", _tier)

        # 0. Get Tenant ID and Create Execution Record
        tenant_id = None
        try:
            with SessionLocal() as db:
                # CRITICAL: Validate workspace exists and get tenant_id
                workspace = db.query(Workspace).filter(
                    Workspace.id == self.workspace_id
                ).first()

                if not workspace:
                    logger.error(f"Workspace {self.workspace_id} not found")
                    raise HTTPException(status_code=404, detail="Workspace not found")

                tenant_id = workspace.tenant_id or "default"
                self.tenant_id = tenant_id # Sync if resolved later

                # Create persistent execution record
                # metadata_json carries the chat session_id so the run can be
                # joined back to its conversation for trace replay (the
                # thread_id column is an FK to agent_threads, unusable here).
                _session_id = (context or {}).get("session_id")
                execution = AgentExecution(
                    id=execution_id,
                    agent_id="atom_main",
                    tenant_id=tenant_id,
                    status=ExecutionStatus.RUNNING.value,
                    input_summary=request[:200],
                    triggered_by=trigger_mode.value,
                    started_at=start_time,
                    metadata_json=(
                        {"session_id": _session_id, "channel": "chat"}
                        if _session_id else {}
                    ),
                )
                db.add(execution)
                db.commit()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create AgentExecution: {e}")

        # Initialize status + final_answer BEFORE the body so the failure
        # finalizer (the except below) always has well-defined values even when
        # an exception escapes early. start_time is already set above (line 403).
        # Previously an unhandled exception in the body bypassed the finalization
        # entirely, orphaning the AgentExecution row in "running" forever (Bug 4).
        status = "failed"
        final_answer = ""
        # `steps` is normally initialized inside the ReAct section (~line 770),
        # but a KillRunAborted raised BEFORE that point (e.g. at memory recall)
        # still flows into the kill handler, which builds result_payload with
        # actions_executed=steps — an unbound local crashed the handler with
        # UnboundLocalError, turning a clean sandbox kill into a 500. Init here
        # alongside the other pre-try state (W44b).
        steps: list = []
        # Same story for the machine-readable budget signal: failure_reason /
        # failure_mode are set inside the ReAct loop, but the result_payload
        # builder reads them unconditionally — the kill handler must not
        # UnboundLocalError on a pre-loop kill.
        failure_reason: Optional[str] = None
        failure_mode: Optional[str] = None

        # KillRunAborted handling (below) references this name at except-match
        # time — import it before the body's try so the branch is reachable.
        from core.sandbox_killrun import KillRunAborted

        # Wrap the body so an escaping exception finalizes the execution
        # as failed instead of orphaning it in 'running' (Bug 4).
        try:
            # 1. Fetch Canvas Context if provided (OPTIONAL)
            canvas_state: Optional[CanvasContext] = None
            canvas_text = ""
        
            if canvas_context and canvas_context.get("canvas_id"):
                db = SessionLocal()
                try:
                    canvas_state = await self.canvas_provider.get_canvas_context(
                        db=db,
                        canvas_id=canvas_context["canvas_id"],
                        tenant_id=tenant_id
                    )
                    if canvas_state:
                        canvas_text = self.canvas_provider.format_for_agent(canvas_state)
                        logger.info(f"Canvas context loaded: {canvas_state.artifact_count} artifacts, {len(canvas_state.comments)} comments")
                except Exception as e:
                    logger.warning(f"Failed to fetch canvas context: {e}")
                    raise  # Re-raise to prevent silent failures
                finally:
                    db.close()
        
            # 2. Access Memory with Canvas Enrichment
            # Build enriched task description for better memory retrieval
            enriched_task = request
            if canvas_state:
                enrichment_parts = [request]
                if canvas_state.canvas_id:
                    enrichment_parts.append(f"canvas: {canvas_state.canvas_id}")
                if canvas_state.comments:
                    comment_texts = [c.content for c in canvas_state.comments[:5]]
                    enrichment_parts.append(f"user context: {' '.join(comment_texts)}")
                enriched_task = " | ".join(enrichment_parts)

            memory_context = await self.world_model.recall_experiences(
                agent=self._get_atom_registry(),
                current_task_description=enriched_task  # Use enriched task
            )

            # 2.5. Explicit Canvas-Aware Episodic Recall (NEW)
            # Canvas context already enriches the semantic search via enriched_task.
            # This adds explicit episodic recall with canvas-aware boosting.
            if canvas_state and canvas_state.canvas_id:
                try:
                    episodic_context = await self.world_model.recall_episodes(
                        task_description=request,  # Use original request for episodic search
                        agent_role=self._get_atom_registry().category or "general",
                        agent_id=self._get_atom_registry().id,
                        canvas_id=canvas_state.canvas_id,  # NEW: Explicit canvas filtering
                        limit=5
                    )

                    if episodic_context:
                        # Add episodic context to memory
                        memory_context["canvas_episodes"] = episodic_context
                        logger.info(
                            f"Added {len(episodic_context)} canvas-aware episodes "
                            f"(canvas_id={canvas_state.canvas_id})"
                        )

                except Exception as e:
                    logger.warning(f"Failed to recall canvas-aware episodes: {e}")
        
            # 2. Get available tools (Core + Session Lazy Loaded)
            all_tools = await self.mcp.get_all_tools()
        
            # Filter for Core Tools + Dynamically added Session Tools
            active_tools = [t for t in all_tools if t["name"] in self.CORE_TOOLS_NAMES]
            active_tools.extend(self.session_tools)
        
            # Deduplicate
            seen_tools = set()
            unique_active_tools = []
            for t in active_tools:
                if t["name"] not in seen_tools:
                    unique_active_tools.append(t)
                    seen_tools.add(t["name"])

            # Inject special "mcp_tool_search" if not present (although it should be in core)
            TOOL_SEARCH_ALIASES = ["mcp_tool_search", "tool_search", "search_tools"]
            has_tool_search = any(t["name"] in TOOL_SEARCH_ALIASES for t in unique_active_tools)

            if not has_tool_search:
                 unique_active_tools.append({
                     "name": "mcp_tool_search",
                     "description": "Search for more capabilities/tools if you can't find what you need in the current list. Returns list of tools that you can then use in the NEXT step.",
                     "parameters": {"query": "string"}
                 })

            try:
                tool_descriptions = json.dumps(
                    [{"name": t["name"], "description": t["description"]} for t in unique_active_tools],
                    indent=2,
                    default=str  # Fallback for non-serializable objects
                )
            except (TypeError, ValueError) as e:
                logger.error(f"Failed to serialize tool descriptions: {e}")
                tool_descriptions = json.dumps([])  # Fallback to empty list


            # Initialize execution history before planning phase
            execution_history = ""

            # 3. Planning & Specialty Delegation Phase (NEW)
            # If the task is complex, we use a high-reasoning turn to plan subtasks
            # 3. Intelligent Routing Phase (NEW)
            # Fast classification to determine if we need a persistent automation or a one-off task
            from ai.nlp_engine import RouteCategory
            nlu = NaturalLanguageEngine()
            route = await nlu.classify_route(request, tenant_id=tenant_id or "default")
        
            routing_log = {
                "execution_id": execution_id,
                "step": 0,
                "step_type": "routing",
                "thought": f"[SYSTEM] Routing Request: {route.category.value.upper()} - {route.reasoning}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if step_callback: await step_callback(routing_log)
            execution_history += f"System Routing: {route.category.value.upper()} ({route.reasoning})\n"

            # --- P1a (W4): governed fleet-routing branch ---------------------
            # The previously-dead route_with_governance path (:2229) is wired in
            # here, BEHIND A FLAG (ATOM_FLEET_ROUTING_ENABLED, default false).
            # Flag off == exact pre-P1a behavior (kill-switch parity). Flag on +
            # force-enforce on -> a fleet-eligible TASK intent recruits a
            # specialist fleet and returns a recruitment summary (no auto-execute).
            # Flag on + force-enforce off (shadow) -> recruitment is computed for
            # telemetry but the request falls through to Queen→ReAct below.
            try:
                from core.fleet_routing_config import fleet_routing_enabled
                from core.fleet_orchestration.fleet_router_automation import (
                    resolved_fleet_enforce,
                )
            except Exception:
                fleet_routing_enabled = lambda: False  # noqa: E731
                resolved_fleet_enforce = lambda: False  # noqa: E731

            _fleet_eligible = (
                fleet_routing_enabled()
                and route.category == RouteCategory.ONE_OFF
                and len(request) > 40  # non-trivial long-horizon task
            )
            if _fleet_eligible:
                # Map the route result onto an IntentClassification (the governed
                # method's contract). NOTE: a bottom-of-file import re-binds
                # IntentClassification/IntentCategory to the core.intent_classifier
                # versions (a @dataclass + str-Enum), so construct with THOSE
                # fields (requires_execution, suggested_handler), not the local
                # pydantic class at line 232.
                from core.intent_classifier import (
                    IntentClassification as _FleetIntent,
                    IntentCategory as _FleetCategory,
                )
                _fleet_intent = _FleetIntent(
                    category=_FleetCategory.TASK,
                    confidence=0.7,
                    reasoning=f"fleet-eligible one-off task: {route.reasoning}",
                    requires_execution=True,
                    suggested_handler="fleet_admiral",
                    is_structured=False,
                    is_long_horizon=True,
                    requires_agent_recruitment=True,
                    blueprint_applicable=False,
                )
                try:
                    _fleet_user_id = (
                        (context.get("user_id") if context else None)
                        or (self.user.id if self.user else None)
                        or "default"
                    )
                    _fleet_result = await self.route_with_governance(
                        request, _fleet_intent, _fleet_user_id, agent_id="atom_main"
                    )
                except Exception as fleet_err:
                    logger.warning(f"Fleet routing failed, falling back to Queen→ReAct: {fleet_err}")
                    _fleet_result = None

                # Fleet routing validation (2026-08-21): audit EVERY fleet-eligible
                # decision (shadow or enforced, success or failure) so the
                # calibration pass has data. Never raises. The outcome join
                # happens at the finalize points via record_fleet_execution_outcome.
                try:
                    from core.fleet_orchestration.fleet_routing_stats import (
                        record_fleet_decision,
                    )

                    _fleet_roster = []
                    if _fleet_result:
                        _fleet_roster = (
                            _fleet_result.get("specialists")
                            or (_fleet_result.get("result") or {}).get("recruitment_roster")
                            or []
                        )
                    _fleet_recruit_ok = bool(
                        _fleet_result
                        and (_fleet_result.get("specialists_count") or 0) > 0
                        and _fleet_result.get("fleet_status") != "failed"
                    )
                    _fleet_error = None
                    if _fleet_result is None:
                        _fleet_error = (
                            str(fleet_err) if "fleet_err" in dir() else "recruitment returned empty"
                        )
                    record_fleet_decision(
                        execution_id=execution_id,
                        workspace_id=getattr(self, "workspace_id", None) or (context or {}).get("workspace_id"),
                        tenant_id=tenant_id,
                        agent_id="atom_main",
                        request=request,
                        chain_id=_fleet_result.get("chain_id") if _fleet_result else None,
                        specialists_count=(
                            _fleet_result.get("specialists_count") or 0
                        ) if _fleet_result else 0,
                        roster=_fleet_roster,
                        recruitment_succeeded=_fleet_recruit_ok,
                        enforced=resolved_fleet_enforce(),
                        error=_fleet_error,
                    )
                except Exception as _fleet_audit_err:
                    # Telemetry must never break the hot path.
                    logger.warning(f"Fleet audit write failed (non-fatal): {_fleet_audit_err}")
                    pass

                if _fleet_result is not None:
                    # Emit a synthetic recruitment-progress step (net-new: the
                    # FleetAdmiral path has no step_callback of its own) so the
                    # WS/canvas layer observes the fleet event.
                    if step_callback:
                        await step_callback({
                            "execution_id": execution_id,
                            "step": 0,
                            "step_type": "fleet_recruitment",
                            "thought": (
                                f"Fleet recruited: {_fleet_result.get('specialists_count', 0)} "
                                f"specialist(s) (chain {_fleet_result.get('chain_id')})."
                            ),
                            "action": {"tool": "route_with_governance", "params": {"intent": "task"}},
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

                    if resolved_fleet_enforce():
                        # Return the recruitment summary directly (no auto-execute;
                        # execution stays a separate explicit step — see plan P1a).
                        return {
                            "execution_id": execution_id,
                            **_fleet_result,
                            "status": _fleet_result.get("status", "fleet_recruited"),
                        }
                    # Shadow mode: fall through to Queen→ReAct (telemetry only).
            # --- end P1a -----------------------------------------------------

            # 4. Planning & Specialty Delegation Phase
            is_complex = len(request) > 100 or any(kw in request.lower() for kw in ["analyze", "create", "sync", "report", "manage"]) or route.category == RouteCategory.AUTOMATION
        
            if is_complex and trigger_mode == AgentTriggerMode.MANUAL:
                plan_record = {
                    "execution_id": execution_id,
                    "step": 0,
                    "step_type": "planning",
                    "thought": "Activating Queen Agent to design architectural blueprint...",
                    "action": {"tool": "queen_architect", "params": {"goal": request}},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                if step_callback: await step_callback(plan_record)
            
                try:
                    # 1. Queen Phase: Generate Blueprint
                    if not self.queen:
                        from core.service_factory import ServiceFactory
                        with SessionLocal() as db:
                            self.queen = ServiceFactory.get_queen_agent(db)
                
                    execution_mode = "recurring_automation" if route.category == RouteCategory.AUTOMATION else "one_off"
                    blueprint = await self.queen.generate_blueprint(
                        request, 
                        tenant_id=tenant_id or "default",
                        execution_mode=execution_mode
                    )
                
                    if blueprint and blueprint.get("nodes"):
                        plan_summary = f"Queen designed blueprint '{blueprint.get('architecture_name')}'. Transitioning to King Mode for execution."
                        plan_record["output"] = plan_summary
                        execution_history += f"System Blueprint: {plan_summary}\n"
                        if step_callback: await step_callback(plan_record)
                    
                        # 2. King Phase: Execute Blueprint nodes as "Thoughts" or "Delegations"
                        # For now, we seed the ReAct history with the blueprint nodes to guide the loop
                        nodes_desc = "\n".join([f"- {n['name']} ({n['type']}): Requires {n.get('capability_required')}" for n in blueprint['nodes']])
                        execution_history += f"Planned Execution Steps:\n{nodes_desc}\n"
                    
                        if blueprint.get("missing_capabilities"):
                            execution_history += f"Note: Identified missing capabilities: {blueprint['missing_capabilities']}. Will attempt to create or research.\n"
                except Exception as plan_error:
                    logger.warning(f"Queen planning failed, falling back to legacy orchestrator: {plan_error}")
                    # Fallback to orchestrator
                    plan = await self.orchestrator.generate_dynamic_workflow(request)
                    if plan and plan.get("nodes"):
                        plan_summary = f"Identified plan with {len(plan['nodes'])} steps. Delegating to specialized components."
                        plan_record["output"] = plan_summary
                        execution_history += f"System Plan: {plan_summary}\n"
                        if step_callback: await step_callback(plan_record)

            # 4. ReAct Loop with Pydantic Validation
            max_steps = 10
            steps = []
            final_answer = None
            status = "success"

            # BPE workspace (plan Phase 2): fresh per-episode consult counters.
            _bpe_ws = None
            try:
                from core.bpe.actions import bpe_enabled as _bpe_on
                from core.bpe.workspace import get_workspace as _get_ws

                if _bpe_on():
                    _bpe_ws = _get_ws(
                        str((context or {}).get("workspace_id") or "default"),
                        str((context or {}).get("agent_id") or "atom_main"),
                        str((context or {}).get("session_id") or execution_id or ""),
                    )
                    _bpe_ws.reset_episode_counters()
            except Exception as _bpe_err:
                logger.debug(f"bpe episode reset skipped: {_bpe_err}")

            # Machine-readable budget-failure signal (None unless the budget
            # gate halted the run). Propagated to result_payload so downstream
            # hops (orchestrator → HTTP) can surface a structured error_code
            # instead of relying on the human-readable final_answer string.
            failure_reason = None
            failure_mode = None

            # Workstream G — in-loop parallel tool execution (default ON).
            try:
                from core.hallucination_config import (
                    is_parallel_tools_enabled as _is_parallel_tools_enabled,
                )
            except Exception:  # pragma: no cover - defensive
                _is_parallel_tools_enabled = lambda: False
            _parallel_tools_enabled = _is_parallel_tools_enabled()

            for current_step in range(1, max_steps + 1):
                step_start = datetime.now(timezone.utc)

                # AgentRadio — passive awareness: absorb @mentions from the
                # team's lateral thread before planning the next step. Never
                # raises; a missing thread simply yields nothing.
                try:
                    _radio_thread = context.get("radio_thread_id")
                    if _radio_thread:
                        from core.agent_radio.radio_service import (
                            inbox_drain_text,
                        )

                        _inbox = inbox_drain_text(
                            context.get("agent_id", "atom_main"),
                            str(_radio_thread),
                        )
                        if _inbox:
                            execution_history += _inbox
                except Exception:
                    pass  # the drain must never break the agent loop

                # Spend gate: check the tenant budget BEFORE the expensive LLM
                # call (not just before tools). When the enforcement mode denies
                # the action (hard_stop, or soft_stop without an active episode),
                # break the loop cleanly with a budget-exceeded final answer.
                budget_check = await self._check_budget_before_react()
                if not budget_check.get("allowed"):
                    final_answer = (
                        f"Budget limit reached — execution halted. "
                        f"({budget_check.get('reason') or 'over budget'})"
                    )
                    status = "budget_exceeded"
                    # Capture the machine-readable signal for downstream
                    # propagation (orchestrator → HTTP error_code).
                    failure_reason = budget_check.get("reason") or "over budget"
                    failure_mode = budget_check.get("enforcement_mode")
                    logger.warning(
                        f"Budget gate halted execution {execution_id} at step "
                        f"{current_step}: {budget_check.get('reason')}"
                    )
                    break

                # Generate next step using instructor for structured output
                react_step = await self._react_step(
                    request=request,
                    memory_context=memory_context,
                    tool_descriptions=tool_descriptions,
                    execution_history=execution_history,
                    context=context,
                    canvas_text=canvas_text,
                    turn_index=current_step - 1  # NEW: Pass turn index for BPC routing
                )
            
                step_record = {
                    "execution_id": execution_id,
                    "step": current_step,
                    "step_type": "action" if react_step.action else "final_answer",
                    "thought": react_step.thought,
                    "action": react_step.action.model_dump() if react_step.action else None,
                    "output": None,
                    "confidence": getattr(react_step, 'confidence', 0.9),
                    "duration_ms": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
                # Stream to UI
                if step_callback:
                    await step_callback(step_record)
            
                execution_history += f"Thought: {react_step.thought}\n"
            
                # Check for final answer
                if react_step.final_answer:
                    step_record["final_answer"] = react_step.final_answer
                    final_answer = react_step.final_answer
                    steps.append(step_record)
                    execution_history += f"Final Answer: {react_step.final_answer}\n"
                    break
            
                # Workstream G degradation: if parallel tools are disabled but
                # the model emitted `actions`, promote the first action so the
                # step still executes through the single-action path.
                if react_step.actions and not _parallel_tools_enabled:
                    react_step.action = react_step.actions[0]

                # Safety: If no action, no actions, and no final answer, we are
                # stuck - convert thought to final answer. A step that carries
                # `actions` (but no single `action`) must NOT be converted
                # here — it flows into the parallel-execution branch below
                # (Workstream G).
                if not react_step.action and not react_step.actions:
                    final_answer = react_step.thought or "I'm sorry, I'm unable to proceed with that request."
                    step_record["final_answer"] = final_answer
                    step_record["step_type"] = "final_answer"
                    # Record it one last time to satisfy visibility
                    if step_callback: await step_callback(step_record)
                    steps.append(step_record)
                    break

                # ── Parallel tool execution (Workstream G) ──────────────────
                # Multiple independent tools emitted via `actions` — execute in
                # parallel with all-or-nothing HITL batch approval, persist one
                # AgentReasoningStep per tool (same step_number), and stream
                # each result to the UI. `continue` skips the single-action
                # path + the default persistence below.
                if react_step.actions and _parallel_tools_enabled:
                    parallel_results = await self._execute_parallel_tools(
                        react_step.actions, context, step_callback
                    )
                    for p_index, pr in enumerate(parallel_results):
                        p_tool = pr["tool_name"]
                        p_params = pr.get("params") or {}
                        p_record = {
                            "execution_id": execution_id,
                            "step": current_step,
                            "step_type": "parallel",
                            "thought": react_step.thought,
                            "action": {"tool": p_tool, "params": p_params},
                            "output": str(pr["output"])[:500],
                            "confidence": step_record["confidence"],
                            "duration_ms": (datetime.now(timezone.utc) - step_start).total_seconds() * 1000,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "_verified_kind": pr.get("verified_kind", "unverified"),
                            "_verified_evidence": pr.get("verified_evidence"),
                        }
                        # R83 #3: datamark untrusted tool output (no-op when
                        # ATOM_DATAMARKING=off).
                        try:
                            from core.prompt_datamarking import mark_observation
                            _p_obs = mark_observation(pr["output"], source=p_tool)
                        except Exception:
                            _p_obs = pr["output"]
                        execution_history += f"Action: {p_tool}({json.dumps(p_params)})\n"
                        execution_history += f"Observation: {_p_obs}\n"
                        if pr.get("verified_kind") == "failed_verification":
                            execution_history += (
                                f"[CRITIQUE] The action {p_tool} failed "
                                f"verification: "
                                f"{pr.get('verified_evidence') or 'no evidence provided'}. "
                                f"Re-plan before retrying.\n"
                            )
                        elif _is_error_observation(pr["output"]):
                            execution_history += (
                                f"[CRITIQUE] The action {p_tool} returned an error: "
                                f"{str(pr['output'])[:200]}. Re-plan before retrying.\n"
                            )
                        if step_callback:
                            await step_callback(p_record)
                        # One AgentReasoningStep per tool (same step_number);
                        # turn-fact extraction fires ONCE per batch.
                        p_record["id"] = self._persist_reasoning_step(
                            execution_id=execution_id,
                            step_number=current_step,
                            step_type="parallel",
                            thought=react_step.thought,
                            action_dict={"tool": p_tool, "params": p_params},
                            observation=str(pr["output"])[:500],
                            confidence=step_record["confidence"],
                            verified_kind=pr.get("verified_kind", "unverified"),
                            verification_evidence=pr.get("verified_evidence"),
                            duration_ms=p_record["duration_ms"],
                            request=request,
                            final_answer=final_answer,
                            context=context,
                            dispatch_turn_fact=(p_index == 0),
                        )
                        steps.append(p_record)
                    continue

                # Execute action if provided
                if react_step.action:
                    tool_name = react_step.action.tool
                    tool_args = react_step.action.params
                
                    execution_history += f"Action: {tool_name}({json.dumps(tool_args)})\n"
                
                    if tool_name == "mcp_tool_search":
                        found_tools = await self.mcp.search_tools(tool_args.get("query", ""), limit=5)

                        # Deduplicate by tool name before adding
                        existing_names = {t["name"] for t in self.session_tools}
                        new_tools = [t for t in found_tools if t["name"] not in existing_names]

                        self.session_tools.extend(new_tools)
                        observation = f"Found {len(new_tools)} new tools (total: {len(self.session_tools)}). They have been added to your toolkit for the next step: {[t['name'] for t in new_tools]}"
                    
                        step_record["output"] = str(observation)
                        execution_history += f"Observation: {observation}\n"
                        if step_callback: await step_callback(step_record)
                
                    elif tool_name == "delegate_task":
                        # Pass the main step_callback to the sub-agent for layered visibility!
                        observation = await self._execute_delegation(
                            tool_args.get("agent_name"), 
                            tool_args.get("task"), 
                            context,
                            step_callback=step_callback,
                            execution_id=execution_id
                        )
                        step_record["output"] = str(observation)
                        execution_history += f"Observation: Delegated task completed.\n"
                        if step_callback: await step_callback(step_record)
                
                    else:
                        # Execute via MCP with governance check
                        observation = await self._execute_tool_with_governance(
                            tool_name, tool_args, context, step_callback
                        )

                        step_record["output"] = str(observation)[:500]
                        # R83 #3: datamark untrusted tool output (no-op when
                        # ATOM_DATAMARKING=off).
                        try:
                            from core.prompt_datamarking import mark_observation
                            observation = mark_observation(observation, source=tool_name)
                        except Exception:
                            pass  # marking must never break the agent loop
                        execution_history += f"Observation: {observation}\n"

                        # Parse the tool return for a verification envelope
                        # {success, verified, evidence}. Silent no-ops that return
                        # success without evidence land as 'unverified' and cannot
                        # inflate graduation counters (general critique, fixed).
                        try:
                            _vo = parse_tool_outcome(observation)
                            step_record["_verified_kind"] = _vo.kind
                            step_record["_verified_evidence"] = _vo.evidence

                            # ── In-loop self-correction (Workstream A) ────────
                            # When a tool's verification hook explicitly rejected
                            # the result (or the observation is an error string),
                            # append a deterministic critique so the model re-plans
                            # the NEXT step instead of blindly retrying the same
                            # failing action. Zero LLM cost — the critique is a
                            # directive the model reads from execution_history.
                            if _vo.kind == "failed_verification":
                                execution_history += (
                                    f"[CRITIQUE] The action {tool_name} failed "
                                    f"verification: {_vo.evidence or 'no evidence provided'}. "
                                    f"Re-plan before retrying.\n"
                                )
                            elif _is_error_observation(observation):
                                execution_history += (
                                    f"[CRITIQUE] The action {tool_name} returned an error: "
                                    f"{str(observation)[:200]}. Re-plan before retrying.\n"
                                )
                        except Exception:
                            step_record["_verified_kind"] = "unverified"
                            step_record["_verified_evidence"] = None

                    # Update duration after tool execution
                    step_record["duration_ms"] = (datetime.now(timezone.utc) - step_start).total_seconds() * 1000
                    if step_callback: await step_callback(step_record)
            
                # Persist Step to DB (Phase 6: Learning Loop) + per-turn fact
                # extraction (sync_turn hook), via the shared helper so the
                # parallel branch reuses the exact same persistence semantics.
                step_record["id"] = self._persist_reasoning_step(
                    execution_id=execution_id,
                    step_number=current_step,
                    step_type=step_record["step_type"],
                    thought=react_step.thought,
                    action_dict=(
                        react_step.action.model_dump() if react_step.action else None
                    ),
                    observation=step_record.get("output"),
                    confidence=step_record["confidence"],
                    verified_kind=step_record.get("_verified_kind", "unverified"),
                    verification_evidence=step_record.get("_verified_evidence"),
                    duration_ms=step_record["duration_ms"],
                    request=request,
                    final_answer=final_answer,
                    context=context,
                )

                steps.append(step_record)
        
            # Handle max steps exceeded
            if not final_answer:
                final_answer = "Maximum reasoning steps reached. Please refine your request."
                # Map to a VALID ExecutionStatus. "max_steps_exceeded" is not in the
                # ExecutionStatus enum (pending/running/completed/failed/cancelled/
                # paused/timeout), so persisting it verbatim created an invisible
                # third state that status-filtered queries (failure dashboards, retry
                # logic) miss. TIMEOUT is the closest semantic match.
                status = "timeout"

            # on_session_end hook — final extraction pass over the whole turn.
            # Catches durable facts the per-turn hook missed (e.g. facts that only
            # became visible once the final answer was composed). Fire-and-forget.
            if _TURN_FACT_EXTRACTION_ENABLED:
                try:
                    extractor = get_turn_fact_extractor(
                        workspace_id=self.workspace_id, tenant_id=self.tenant_id
                    )
                    # Compose a compact session digest for the final pass.
                    digest_parts = [f"REQUEST: {request}"]
                    for s in steps[-6:]:  # last 6 steps keep it bounded
                        t = (s.get("thought") or "")[:200]
                        o = (s.get("output") or "")[:200]
                        if t:
                            digest_parts.append(f"THOUGHT: {t}")
                        if o:
                            digest_parts.append(f"OBSERVATION: {o}")
                    digest_parts.append(f"FINAL ANSWER: {final_answer}")
                    task = asyncio.create_task(
                        extractor.extract_from_turn(
                            user_request=request,
                            thought="\n".join(digest_parts),
                            final_answer=final_answer,
                            execution_id=execution_id,
                            session_id=context.get("session_id") if context else None,
                            user_id=context.get("user_id") if context else None,
                            maturity=None,
                        )
                    )
                    _pending_extraction_tasks.add(task)
                    task.add_done_callback(
                        lambda t, _s=_pending_extraction_tasks: _s.discard(t)
                    )
                except Exception as e:
                    logger.debug(f"on_session_end extraction dispatch failed: {e}")

        except KillRunAborted as _kill:
            # A tripwire kill reached the top of the body: finalize the run as
            # killed_sandbox and return a killed payload — do NOT re-raise
            # (that would 500 the API) and do NOT mark it 'failed' (the
            # trigger_killrun path already set the row to killed_sandbox).
            logger.warning(
                "Agent run %s killed by sandbox: %s", execution_id, _kill
            )
            status = "killed_sandbox"
            final_answer = f"Agent run killed by sandbox: {_kill}"

        except Exception as _body_err:
            logger.error(f"Agent body raised, finalizing execution as failed: {_body_err}", exc_info=True)
            status = 'failed'
            final_answer = final_answer or f'Agent error: {_body_err}'
            db = None
            try:
                db = SessionLocal()
                execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).with_for_update().first()
                if execution:
                    execution.status = 'failed'
                    execution.result_summary = str(final_answer)[:500]
                    execution.error_message = str(_body_err)[:500]
                    execution.duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
                    execution.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception as _fin_err:
                logger.error(f"Failed to finalize execution as failed: {_fin_err}")
            finally:
                if db is not None:
                    try: db.close()
                    except Exception: pass

            # Fleet routing validation: join the failed outcome onto any fleet
            # audit rows for this execution. Never raises.
            try:
                from core.fleet_orchestration.fleet_routing_stats import (
                    record_fleet_execution_outcome,
                )

                record_fleet_execution_outcome(
                    execution_id=execution_id,
                    success=False,
                    error_message=str(_body_err)[:400],
                )
            except Exception:
                pass
            raise

        # 4. Record Execution
        result_payload = {
            "final_output": final_answer,
            "actions_executed": steps,
            "trigger_mode": trigger_mode.value,
            "status": status,
            # Run identity so callers (e.g. the chat orchestrator's status
            # broadcasts) can correlate lifecycle events with this execution.
            "execution_id": execution_id,
            # Machine-readable budget-failure signal (None on success). The
            # orchestrator reads this to set error_code='budget_exceeded' on
            # the HTTP response so the frontend can render a distinct UI.
            "failure_reason": failure_reason,
            "failure_mode": failure_mode,
        }

        # BPE workspace episode close-out (plan Phase 2) — mirrors
        # GenericAgent: consolidate notes on success / drop on failure,
        # consult-policy feedback, state snapshot for the experience trace.
        try:
            if _bpe_ws is not None:
                from core.bpe.consolidation import consolidate_workspace_notes
                from core.bpe.consult_policy import get_consult_policy

                _success = status == "success"
                _bpe_consolidated = (
                    consolidate_workspace_notes(_bpe_ws) if _success
                    else {"dropped_notes": len(_bpe_ws.drain_pending_notes())}
                )
                _policy = get_consult_policy()
                _meta_agent_id = str((context or {}).get("agent_id") or "atom_main")
                _policy.record_consult_mix(_meta_agent_id, _bpe_ws.episode_commit_notes)
                _policy.record_episode(
                    _meta_agent_id,
                    _bpe_ws.episode_consults,
                    _success,
                    1.0,  # meta runs carry no step_efficiency signal; neutral
                )
                try:
                    from core.bpe.evolution import apply_best

                    apply_best(_meta_agent_id)
                except Exception as _evo_err:
                    logger.debug(f"bpe evolution apply skipped: {_evo_err}")
                result_payload["bpe"] = {
                    "consults": _bpe_ws.episode_consults,
                    "consolidated": _bpe_consolidated,
                    "state": _bpe_ws.to_dict(),
                }
                try:
                    from core.bpe.persistence import BPEWorkspaceStore

                    BPEWorkspaceStore().save(result_payload["bpe"]["state"])
                except Exception as _persist_err:
                    logger.debug(f"bpe persist skipped: {_persist_err}")
                _bpe_ws.reset_episode_counters()
        except Exception as _bpe_err:
            logger.debug(f"bpe episode close-out skipped: {_bpe_err}")

        await self._record_execution(request, result_payload, trigger_mode)
        
        # Update Execution Record with duration
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        db = SessionLocal()
        try:
            # Use WITH FOR UPDATE to lock the row and prevent race conditions
            execution = db.query(AgentExecution).filter(
                AgentExecution.id == execution_id
            ).with_for_update().first()

            if execution:
                execution.status = "completed" if status == "success" else status
                execution.result_summary = str(final_answer)[:500]
                execution.duration_seconds = duration
                execution.completed_at = end_time
                # Map budget_exceeded → a VALID ExecutionStatus for persistence.
                # Like the max_steps→timeout mapping above, budget_exceeded is
                # not in the enum; persisting it verbatim would create an
                # invisible third state that failure dashboards miss. FAILED is
                # the correct bucket, with a distinctive error_message.
                if status == "budget_exceeded":
                    execution.status = "failed"
                    execution.error_message = "Budget exceeded — execution halted by spend gate"
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update AgentExecution: {e}")
            db.rollback()
        finally:
            db.close()

        # Fleet routing validation: join the execution outcome onto any fleet
        # audit rows for this execution (single-arm calibration data). Never raises.
        try:
            from core.fleet_orchestration.fleet_routing_stats import (
                record_fleet_execution_outcome,
            )

            record_fleet_execution_outcome(
                execution_id=execution_id,
                success=(status == "success"),
                actual_latency_ms=duration * 1000.0,
                actual_model="meta_agent",
                actual_provider="internal",
            )
        except Exception:
            pass

        return result_payload

    async def _execute_delegation(self, agent_name: str, task: str, context: Dict, 
                                 step_callback: Optional[callable] = None,
                                 execution_id: str = None) -> str:
        """Delegate a task to a specialized agent."""
        try:
            from core.business_agents import get_specialized_agent
            
            agent = get_specialized_agent(agent_name, self.workspace_id)
            if not agent:
                return f"Error: Agent '{agent_name}' not found. Available agents: accounting, sales, marketing, logistics, tax, purchasing, planning, communications."
                
            logger.info(f"Delegating task to {agent.name}: {task[:50]}... (execution_id: {execution_id})")
            
            # Execute the sub-agent with the SAME callback for real-time visibility!
            # We also pass the execution_id so steps are grouped in the DB
            result = await agent.execute(task, context=context, step_callback=step_callback)
            
            final_output = result.get("final_output") or result.get("output") or str(result)
            return f"Delegation Result from {agent.name}:\n{final_output}"
            
        except Exception as e:
            logger.error(f"Delegation failed: {e}")
            return "Delegation failed. Please try again."



    def _retrieve_skill_instructions(self, request: str) -> str:
        """Prompt-time skill auto-injection (Workstream C).

        Deterministic keyword retrieval over the skill registry. Returns an
        empty string when the flag is off / no skills match / DB unavailable —
        never raises, never blocks the ReAct loop.
        """
        try:
            from core.hallucination_config import is_skill_injection_enabled
            from core.skill_retrieval_service import get_skill_retrieval_service

            if not is_skill_injection_enabled():
                return ""
            with SessionLocal() as skills_db:
                return get_skill_retrieval_service().retrieve_top_skills(
                    skills_db,
                    self.tenant_id,
                    self.workspace_id,
                    request,
                    limit=3,
                )
        except Exception as e:
            logger.debug(f"skill injection skipped: {e}")
            return ""

    async def _check_budget_before_react(self) -> Dict[str, Any]:
        """Spend gate: check the tenant budget BEFORE the expensive LLM call.

        Previously the budget was only checked per-tool (inside
        ``_execute_tool_with_governance``), so the LLM planning call ran
        ungated every iteration — a run over budget kept burning LLM spend up
        to ``max_steps``. This closes that gap: when the configured
        enforcement mode denies the action, the caller breaks the ReAct loop
        cleanly (see the gate at the top of the loop).

        Fail-open on error (returns ``allowed: True``), matching the existing
        convention in BudgetEnforcementService — we never block on an
        inability to compute spend.
        """
        try:
            from core.budget_enforcement_service import BudgetEnforcementService

            # BUG-119: Use context manager to prevent session leak.
            with BudgetEnforcementService() as svc:
                return await svc.check_budget_before_action(
                    tenant_id=self.tenant_id,
                    agent_id="atom_main",
                    action="llm_react_step",
                )
        except Exception as e:
            logger.warning(f"Budget pre-check failed (fail-open): {e}")
            return {"allowed": True, "reason": "budget-check-error", "enforcement_mode": "unknown"}

    async def _react_step(self, request: str, memory_context: Dict,
                          tool_descriptions: str, execution_history: str,
                          context: Dict, canvas_text: str = "",
                          turn_index: int = 0) -> ReActStep:
        """
        Generate a single ReAct step with Pydantic validation.
        Uses instructor to ensure structured output.
        """
        canvas_segment = f"\nCURRENT CANVAS STATE:\n{canvas_text}" if canvas_text else ""

        # BPE workspace (docs/architecture/BPE_WORKSPACE_PLAN.md, Phase 1+2):
        # same flag-gated, consult-policy-mediated block as GenericAgent —
        # flag off → prompt unchanged. Scope: session/execution bound.
        bpe_block = ""
        try:
            from core.bpe.actions import bpe_enabled
            from core.bpe.consult_policy import get_consult_policy
            from core.bpe.workspace import get_workspace

            if bpe_enabled():
                _scope_key = str(
                    (context or {}).get("session_id")
                    or (context or {}).get("execution_id")
                    or ""
                )
                _ws = get_workspace(
                    str((context or {}).get("workspace_id") or "default"),
                    str((context or {}).get("agent_id") or "atom_main"),
                    _scope_key,
                )
                _policy = get_consult_policy()
                _agent_id = str((context or {}).get("agent_id") or "atom_main")
                if _policy.should_render(_agent_id, "moderate", workspace_nonempty=True):
                    bpe_block = "\n" + _ws.render(mode=_policy.render_mode(_agent_id)) + "\n"
        except Exception as e:
            logger.debug(f"bpe workspace render skipped: {e}")

        system_prompt = """You are Atom, an intelligent business assistant.

AVAILABLE TOOLS:
{tool_descriptions}

FORMAT: You must respond with structured output containing:
- thought: Your reasoning about what to do next
- action: If you need to use a SINGLE tool, provide {{"tool": "tool_name", "params": {{...}}}}
- actions: If you need to use MULTIPLE INDEPENDENT tools at once, provide [{{"tool": "tool_name", "params": {{...}}}}, ...]. Only use this when the tools do NOT depend on each other's output — they run in parallel.
- final_answer: If you have enough information to answer, provide the response

Only provide EITHER action OR actions OR final_answer, not multiple.

POWERS:
- You can INGEST KNOWLEDGE from text and files (PDF, CSV, Excel) into your long-term memory.
- You can SEARCH FORMULAS and business logic to ensure calculation accuracy.
- You can PUSH/CREATE/UPDATE data (leads, deals, tasks, invoices, tickets, orders, files) across ALL 46+ integrations in a granular way.
- You can DISCOVER connected integrations and SEARCH across all of them simultaneously.
- You can use 'create_record' and 'update_record' for universal granular manipulation of any connected system.
- You can QUERY your Knowledge Graph for complex relationships.
- **IMPORTANT**: Use `save_business_fact` to store "Truths" (policies, rules). If you see a Fact in memory, VERIFY its citations (`verify_citation`) if it's critical.
- **IMPORTANT**: You have a large toolkit. If you don't see a tool you need, use `mcp_tool_search` to find it.

CORE DIFFERENCE:
- **trigger_workflow**: Use for structured, pre-defined, multi-step business processes (e.g., "Monthly Payroll", "Order Fulfillment").
- **invoke_capability**: Use for unstructured, complex, reasoning-heavy tasks that aren't workflows (e.g., "Advanced Market Analysis", "Deep Code Audit").

SPECIALIZED AGENTS:
You manage a team of experts. DELEGATE tasks using `delegate_task` if they match these domains:
- "accounting": Bookkeeping, transactions, reconciliation
- "sales": CRM, leads, pipeline, outreach
- "marketing": Campaigns, social media, ROI
- "logistics": Inventory, shipping, supply chain
- "tax": Tax compliance, liabilities, deadlines
- "purchasing": Procurement, vendors, purchase orders
- "planning": Strategy, forecasting, hiring
- "communications": Drafting emails, triaging messages

FLEET ADMIRALTY (NEW):
You are the Admiral of the Atom Fleet. For complex, multi-domain tasks, do NOT act alone. Use `recruit_fleet` to assemble a specialized team. 
- You can recruit multiple specialists (Sales, Finance, Engineering) in parallel.
- All recruited agents share a global 'Blackboard' context via their Delegation Chain.
- You supervise their high-level coordination while they handle the domain specifics.

{comm_instruction}

{skill_instructions}

{bpe_block}

{canvas_segment}
""".format(
            tool_descriptions=tool_descriptions,
            comm_instruction=self._get_communication_instruction(context),
            skill_instructions=self._retrieve_skill_instructions(request),
            bpe_block=bpe_block,
            canvas_segment=canvas_segment
        )

        # Stage router (Switchyard port): turn-level tier routing from
        # tool-result signals. Shadow by default — audited, never applied;
        # per-agent enforcement via configuration["stage_routing"] or the
        # global ATOM_STAGE_ROUTING_FORCE_ENFORCE. Never raises.
        _stage_model = "reasoning"
        _stage_decision = None
        _stage_policy = None
        stage_handoff_note = ""
        try:
            from core.llm.stage_router import (
                get_stage_router,
                map_decision_to_model_type,
                resolve_agent_policy,
            )

            _stage_router = get_stage_router()
            if _stage_router.enabled:
                _stage_policy = resolve_agent_policy(None, _stage_router.enforce)
                _stage_decision = await _stage_router.decide_for_history(
                    execution_history,
                    previous_group=self._stage_group,
                    use_split=True,
                    agent_id="atom_main",
                    workspace_id=self.workspace_id,
                    tenant_id=self.tenant_id,
                    step_index=turn_index,
                    policy=_stage_policy,
                )
                self._stage_group = (
                    _stage_decision.applied_group if _stage_decision else self._stage_group
                )
                _model_override = map_decision_to_model_type(
                    _stage_decision, _stage_policy.enforce
                )
                if _model_override:
                    _stage_model = _model_override
                if _stage_policy.enforce and _stage_decision and _stage_decision.handoff_note:
                    stage_handoff_note = _stage_decision.handoff_note
        except Exception as _stage_err:
            logger.debug(f"Stage router unavailable, keeping model selection: {_stage_err}")
        if stage_handoff_note:
            system_prompt += f"\n{stage_handoff_note}\n"

        # Build rich memory context for the prompt
        experiences = memory_context.get('experiences', [])
        knowledge = memory_context.get('knowledge', [])
        formulas = memory_context.get('formulas', [])
        facts = memory_context.get('business_facts', [])
        canvas_episodes = memory_context.get('canvas_episodes', [])  # NEW: Canvas-aware episodes
        # P0 (memory unification plan): these legs are fetched by
        # world_model.recall_experiences but were previously never rendered.
        knowledge_graph = memory_context.get('knowledge_graph', '')
        past_conversations = memory_context.get('conversations', [])
        recalled_episodes = memory_context.get('episodes', [])

        memory_sections = []
        if knowledge_graph:
            graph_ctx = str(knowledge_graph).strip()
            if len(graph_ctx) > 3200:
                graph_ctx = graph_ctx[:3200] + "…"
            memory_sections.append(f"KNOWLEDGE GRAPH CONTEXT (entities & relationships):\n{graph_ctx}")
        if experiences:
            exp_summaries = [f"- {getattr(e, 'input_summary', 'Task')[:80]}... → {getattr(e, 'outcome', 'completed')}" for e in experiences[:3]]
            memory_sections.append(f"PAST EXPERIENCES:\n" + "\n".join(exp_summaries))
        if recalled_episodes:
            def _episode_line(e: dict) -> str:
                task = str(e.get('task_description') or e.get('summary') or 'Task')[:80]
                line = f"- {task} → {e.get('outcome', 'completed')}"
                fb = (e.get('feedback_context') or [None])[0]
                if isinstance(fb, dict):
                    verdict = fb.get('thumbs_up_down') or fb.get('rating')
                    if verdict:
                        line += f" (user feedback: {verdict})"
                return line
            ep_summaries = [_episode_line(e) for e in recalled_episodes[:3] if isinstance(e, dict)]
            if ep_summaries:
                memory_sections.append(f"LEARNING EPISODES (prior agent work):\n" + "\n".join(ep_summaries))
        if canvas_episodes:  # NEW: Canvas-aware episodic memory
            canvas_ep_summaries = [
                f"- [{e.get('canvas_id', 'unknown')[:8]}] {e.get('task_description', 'Task')[:60]}... → {e.get('outcome', 'completed')} (boost: +{e.get('canvas_boost', 0):.2f})"
                for e in canvas_episodes[:3]
            ]
            memory_sections.append(f"CANVAS EPISODES (same workspace):\n" + "\n".join(canvas_ep_summaries))
        if past_conversations:
            conv_summaries = [
                f"- [{str(c.get('created_at', ''))[:10]}] {c.get('role', '?')}: {str(c.get('content', ''))[:120]}"
                for c in past_conversations[:3]
                if isinstance(c, dict) and c.get('content')
            ]
            if conv_summaries:
                memory_sections.append(f"RECENT CONVERSATIONS:\n" + "\n".join(conv_summaries))
        if knowledge:
            try:
                # Shared renderer (core/provenance.py): spotlighted UNTRUSTED
                # ProvenanceTags when knowledge spotlighting is on, legacy
                # bullets otherwise. One implementation for both agent files.
                from core.provenance import render_knowledge_summaries

                _k_section = render_knowledge_summaries(knowledge)
                if _k_section:
                    memory_sections.append(_k_section)
            except Exception:
                doc_summaries = [f"- {k.get('text', '')[:100]}..." for k in knowledge[:3]]
                memory_sections.append(f"RELEVANT KNOWLEDGE:\n" + "\n".join(doc_summaries))
        if formulas:
            formula_summaries = [f"- {f.get('name', 'Formula')}: {f.get('description', '')[:60]}" for f in formulas[:3]]
            memory_sections.append(f"AVAILABLE FORMULAS:\n" + "\n".join(formula_summaries))
        if facts:
            fact_summaries = [f"- [Status: {f.verification_status}] {f.fact} (Source: {f.metadata.get('source', 'unknown')})" for f in facts[:3]]
            memory_sections.append(f"TRUSTED BUSINESS FACTS:\n" + "\n".join(fact_summaries))

        # Tier-1 durable facts — pure SQL recall (sub-ms to ~3ms).
        # These survive context compression because they're fetched fresh each turn.
        try:
            with SessionLocal() as facts_db:
                durable = _get_active_facts_for_prompt(
                    facts_db, self.workspace_id, limit=5,
                    max_sensitivity=_prompt_ceiling(),
                )
            if durable:
                memory_sections.append(
                    "DURABLE FACTS (survive compression):\n"
                    + "\n".join(
                        f"- [{d.category}] {d.fact_text}" for d in durable
                    )
                )
        except Exception as e:
            logger.debug(f"durable-facts recall failed: {e}")

        # WORKSPACE FIELD GUIDE — curated memory snapshot (Workstream E).
        # Populated once per execute(); consumed here so agents read the
        # agent-curated guide alongside durable facts.
        _guide = context.get("_field_guide_context") or ""
        if _guide:
            memory_sections.append(_guide)

        # Tier-2 semantic recall — prefetched once per execute() but never
        # surfaced (dead-end). Consume it now.
        prefetched_facts = context.get("prefetched_facts", []) or []
        if prefetched_facts:
            _pf = []
            for f in prefetched_facts[:5]:
                if isinstance(f, dict):
                    _pf.append(f.get("fact_text") or f.get("text") or str(f))
                else:
                    _pf.append(str(f))
            if _pf:
                memory_sections.append(
                    "SEMANTICALLY RELATED FACTS:\n" + "\n".join(f"- {t[:200]}" for t in _pf)
                )

        memory_display = "\n\n".join(memory_sections) if memory_sections else "(No prior context)"
        
        user_prompt = f"""Request: {request}

MEMORY CONTEXT:
{memory_display}

Execution History:
{execution_history if execution_history else "(Starting fresh)"}

What is your next step?"""

        # Use unified LLMService for structured generation
        structured_result = await self.llm.generate_structured_response(
            prompt=user_prompt,
            system_instruction=system_prompt,
            response_model=ReActStep,
            temperature=0.2,
            model=_stage_model,
            agent_id="atom_main",
            stage_decision_id=_stage_decision.id if _stage_decision else None,
        )
        
        if structured_result:
            self._ledger_llm_decision(
                model=_stage_model or "auto",
                prompt=user_prompt,
                response=structured_result.model_dump()
                if hasattr(structured_result, "model_dump")
                else structured_result,
            )
            return structured_result

        # Fallback: Use LLMService for completion
        response_data = await self.llm.generate_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="fast",
            temperature=0.2
        )

        raw_response = response_data.get("content")
        self._ledger_llm_decision(model="fast", prompt=user_prompt, response=raw_response)
        
        # Handle None, empty, or error responses
        is_error = not raw_response or any(kw in str(raw_response).lower() for kw in ["not initialized", "error", "restriction", "budget", "expired", "failed", "no eligible"])
        
        if is_error:
            return ReActStep(
                thought="System encountered an issue or restriction.",
                final_answer=raw_response if raw_response else "Unable to process request - AI provider unavailable."
            )
        
        # Simple fallback parsing: If it doesn't look like JSON and has no action, treat as final answer
        return ReActStep(
            thought=raw_response[:200] if raw_response else "Reasoning generated",
            final_answer=raw_response
        )

    async def _trigger_workflow(self, workflow_id: Optional[str], params: Dict,
                                context: Dict) -> str:
        """Trigger a workflow by id via the workflow engine.

        BUG FIX (W44): this method was called from _execute_tool_with_governance
        but never defined — every ``trigger_workflow`` tool call crashed with
        AttributeError (masked as "Tool error. Please try again."). The special
        tool was dead since the Jan 2026 port. Now delegates to the workflow
        engine's execution path.
        """
        try:
            from core.workflow_engine import get_workflow_engine
            if not workflow_id:
                return "Error: workflow_id is required for trigger_workflow"
            engine = get_workflow_engine()
            input_data = params or {}
            execution_id = await engine.start_workflow(
                {"id": workflow_id}, input_data)
            return f"Workflow {workflow_id} triggered (execution {execution_id})"
        except Exception as e:
            logger.error(f"Failed to trigger workflow {workflow_id}: {e}")
            return f"Error triggering workflow {workflow_id}: {e}"

    async def _execute_tool_with_governance(self, tool_name: str, args: Dict,
                                            context: Dict, step_callback: Optional[callable] = None,
                                            pre_approved: bool = False) -> str:
        """Auditing wrapper around every meta-agent tool invocation (R84c parity).

        Mirrors GenericAgent._step_act: ledgers success, error-string results,
        and exceptions into the per-decision audit trail. The audit write is
        guarded so a downed audit store never breaks the tool call; KillRun
        aborts still audit (success=False) before re-raising. Delegates to
        ``_execute_tool_with_governance_unaudited`` for the actual work.
        """
        import time as _time
        from core.agent_action_audit import is_error_result

        _start = _time.monotonic()
        try:
            result = await self._execute_tool_with_governance_unaudited(
                tool_name, args, context, step_callback, pre_approved
            )
        except Exception as tool_err:
            try:
                from core.agent_action_audit import log_agent_action
                log_agent_action(
                    action=f"tool:{tool_name}",
                    description=f"Meta-agent tool {tool_name} raised",
                    metadata={
                        "tool": tool_name,
                        "params": args,
                        "duration_ms": round((_time.monotonic() - _start) * 1000, 1),
                    },
                    success=False,
                    error_message=str(tool_err)[:2000],
                )
            except Exception:  # noqa: BLE001 — audit must never mask the tool error
                pass
            raise

        _is_err = is_error_result(result)
        try:
            from core.agent_action_audit import log_agent_action
            log_agent_action(
                action=f"tool:{tool_name}",
                description=f"Meta-agent tool {tool_name} invoked",
                metadata={
                    "tool": tool_name,
                    "params": args,
                    "duration_ms": round((_time.monotonic() - _start) * 1000, 1),
                },
                success=not _is_err,
                error_message=result[:2000] if _is_err else None,
            )
        except Exception:  # noqa: BLE001
            pass
        return result

    async def _execute_tool_with_governance_unaudited(self, tool_name: str, args: Dict,
                                                      context: Dict, step_callback: Optional[callable] = None,
                                                      pre_approved: bool = False) -> str:
        """Execute a tool via MCP with governance checks

        ``pre_approved`` (Workstream G): when True, the governance/HITL check is
        skipped (already granted by the parallel-batch approval).
        """
        from core.sandbox_killrun import KillRunAborted

        try:
            # 1. Governance Check
            if not pre_approved:
                db = SessionLocal()
                try:
                    gov = AgentGovernanceService(db)
                    # 1. Governance Check (async variant: the sync can_perform_action
                    # can't await the budget check inside a running loop, so it
                    # would skip budget enforcement entirely — a spend bypass).
                    auth_check = await gov.can_perform_action_async("atom_main", tool_name)

                    # META AGENT CONSTRAINT: Enforce Propose-Only for all non-read actions (Complexity > 1)
                    # The user must accept or modify any state-changing task.
                    complexity = auth_check.get("action_complexity", 2)
                    if complexity > 1:
                        auth_check["requires_human_approval"] = True
                        auth_check["reason"] = f"Meta-Agent is in Propose-Only mode. Action '{tool_name}' requires confirmation."

                    if auth_check.get("requires_human_approval"):
                        # request_approval's signature is (agent_id, action_type,
                        # params, reason, chain_id=None) — it reads workspace_id off
                        # the service instance (self.workspace_id). Passing it as a
                        # kwarg raised TypeError every time, which the outer except
                        # masked as "Tool error" — making the entire HITL approval
                        # gate dead for the meta-agent.
                        action_id = gov.request_approval(
                            agent_id="atom_main",
                            action_type=tool_name,
                            params=args,
                            reason=auth_check["reason"],
                        )

                        if step_callback:
                            await step_callback({
                                "type": "hitl_paused",
                                "action_id": action_id,
                                "tool": tool_name,
                                "reason": auth_check["reason"]
                            })

                        approved = await self._wait_for_approval(action_id)
                        if not approved:
                            return f"Action {tool_name} was REJECTED or timed out."

                    elif not auth_check["allowed"]:
                        return f"Governance blocked: {auth_check['reason']}"
                finally:
                    db.close()
            
            # SPECIAL TOOLS (Internal)
            if tool_name == "trigger_workflow":
                result = await self._trigger_workflow(args.get("workflow_id"), args.get("params", {}), context)
                return result

            elif tool_name == "delegate_task":
                result = await self._execute_delegation(args.get("agent_name"), args.get("task"), context)
                return result

            elif tool_name == "recruit_fleet":
                # Handle fleet recruitment
                sub_tasks = args.get("sub_tasks", [])
                goal = args.get("goal", "Multi-Agent Coordination")
                result = await self._recruit_fleet(goal, sub_tasks, context, step_callback)
                return result

            elif tool_name == "invoke_capability":
                # Maturity-Gated Capability Invocation
                capability_name = args.get("capability_name")
                maturity = self.graduation_service.get_maturity("atom_main", capability_name)

                logger.info(f"Invoking capability '{capability_name}' at maturity level: {maturity}")

                # Enforce gating (Student level requires HITL)
                if maturity == "student":
                    return f"Action 'invoke_capability({capability_name})' blocked. Capability is at STUDENT level and requires explicit governance authorization or HITL approval."

                # Execute logic...
                result = await self.mcp.call_tool(capability_name, args.get("params", {}), context=context)

                # Record usage for graduation — parse the result envelope so
                # only VERIFIED successes can promote the capability. A silent
                # no-op returning {success: true} without evidence lands as
                # 'unverified' and cannot inflate the success ratio.
                try:
                    _cap_outcome = parse_tool_outcome(result)
                    self.graduation_service.record_usage(
                        "atom_main",
                        capability_name,
                        success=_cap_outcome.success,
                        verified=_cap_outcome.kind,
                    )
                except Exception:
                    # Never let graduation bookkeeping break the turn
                    self.graduation_service.record_usage(
                        "atom_main", capability_name,
                        success=True, verified="unverified",
                    )
                return str(result)

            # 2. Execute via MCP with governance check
            #
            # Execution Sandbox Layer (Round 43 / Phase A) — defensive
            # blast-radius check. Where governance above decides "is this
            # agent normally allowed?", sandbox decides "is this specific
            # call within bounds?". Closes the prompt-injection gap
            # (docs/security/TRUST_VS_SANDBOX.md). Shadow mode by default.
            sandbox_decision = _meta_agent_sandbox_check(tool_name, args, context)
            if sandbox_decision is not None and sandbox_decision.requires_review:
                if sandbox_decision.enforced:
                    return (
                        f"Sandbox {sandbox_decision.decision}: "
                        f"{sandbox_decision.violation_detail}"
                    )
                # Shadow mode — log + audit but proceed.
                logger.info(
                    "sandbox shadow: %s -> %s (%s)",
                    context.get("agent_id", "atom_main"),
                    tool_name,
                    sandbox_decision.violation_type,
                )

            # ── ActionJudge wiring (Workstream A) ─────────────────────────────
            # The Phase-E LLM ActionJudge was implemented but never wired into
            # the meta-agent tool path. Consult it here — but ONLY when
            # ATOM_SANDBOX_JUDGE_ENABLED is on (default off), so behavior is
            # byte-identical otherwise. BLOCK → refuse; ESCALATE → route to the
            # same HITL approval gate used for complex actions.
            try:
                from core import sandbox_config as _sc
            except Exception:  # pragma: no cover
                _sc = None
            if _sc is not None and _sc.is_sandbox_judge_enabled():
                try:
                    from core.llm.action_judge import ActionJudge, JudgeVerdict
                    judge = ActionJudge(llm_service=self.llm)
                    judge_result = await judge.evaluate(
                        action_description=f"{tool_name}({json.dumps(args, default=str)})",
                        context=context.get("original_request") or "",
                        provenance_context=None,
                    )
                    if judge_result.verdict == JudgeVerdict.BLOCK:
                        logger.warning(
                            "ActionJudge BLOCK: %s -> %s (%s)",
                            context.get("agent_id", "atom_main"),
                            tool_name,
                            judge_result.rationale,
                        )
                        return (
                            f"Action {tool_name} was blocked by the safety judge: "
                            f"{judge_result.rationale}"
                        )
                    if judge_result.verdict == JudgeVerdict.ESCALATE:
                        with SessionLocal() as judge_db:
                            gov = AgentGovernanceService(judge_db)
                            action_id = gov.request_approval(
                                agent_id="atom_main",
                                action_type=tool_name,
                                params=args,
                                reason=(
                                    f"Safety judge escalation: {judge_result.rationale}"
                                ),
                            )
                        approved = await self._wait_for_approval(action_id)
                        if not approved:
                            return (
                                f"Action {tool_name} was REJECTED or timed out "
                                f"after safety-judge escalation."
                            )
                except Exception as _judge_err:
                    logger.debug(
                        "ActionJudge consult skipped (%s): %s",
                        tool_name, _judge_err,
                    )

            result = await self.mcp.call_tool(tool_name, args, context=context)
            return str(result)

        except KillRunAborted:
            # KillRun must ABORT the run, not degrade to a "Tool error" string.
            # Swallowing it here let a tripwire-killed run keep iterating (LLM
            # spend) and finalize as "success", overwriting killed_sandbox.
            raise
        except Exception as e:
            logger.error(f"Tool error: {e}")
            return "Tool error. Please try again."

    async def _recruit_fleet(self, goal: str, sub_tasks: List[Dict[str, str]], 
                              context: Dict, step_callback: Optional[callable] = None) -> str:
        """Orchestrate a fleet of specialized agents for a complex goal."""
        try:
            from core.business_agents import get_specialized_agent
            tenant_id = self.tenant_id
            
            with SessionLocal() as db:
                fleet_service = AgentFleetService(db)
                
                # 1. Initialize the Fleet (Delegation Chain)
                chain = fleet_service.initialize_fleet(
                    tenant_id=tenant_id,
                    root_agent_id="atom_main",
                    root_task=goal,
                    root_execution_id=context.get("execution_id"),
                    initial_metadata={"goal": goal, "sub_tasks_count": len(sub_tasks)}
                )
                
                logger.info(f"Fleet initiated in Upstream: {chain.id} for goal: {goal}")
                
                fleet_members = []
                optimizer = FleetOptimizationService(db)
                
                for i, st in enumerate(sub_tasks):
                    domain = st.get("domain", "general")
                    task_desc = st.get("task", "Analyze domain sub-task")
                    use_optimizer = st.get("use_optimizer", True) # Default to true in Admiralty mode
                    
                    optimization_metadata = None
                    if use_optimizer:
                        optimization_metadata = optimizer.get_optimization_parameters(
                            tenant_id=self.tenant_id,
                            domain=domain,
                            task_description=task_desc
                        )
                        logger.info(f"Optimization for {domain}: {optimization_metadata['optimization_reason']}")

                    # 3. Recruit the specialist
                    agent = get_specialized_agent(domain, self.workspace_id)

                    # P5 integrity: self-dealing block — an agent cannot
                    # recruit itself onto the fleet it controls.
                    _child_id = agent.id if agent else f"specialist_{domain}"
                    try:
                        from core.org_integrity import self_recruitment_blocked

                        if self_recruitment_blocked("atom_main", _child_id):
                            logger.warning(
                                "Allocator integrity: self-recruitment blocked (%s)",
                                _child_id,
                            )
                            continue
                    except Exception:
                        pass

                    # P5 COI signal (shadow): prior radio contact between the
                    # coordinator and this candidate, recorded on the link.
                    _coi = False
                    try:
                        from core.org_integrity import has_radio_contact

                        _coi = has_radio_contact(db, "atom_main", _child_id)
                    except Exception:
                        pass
                    
                    # 3. Create the Link
                    # P1 delegation contract: typed handoff (objective/format/
                    # guidance/boundaries/effort) stored on the link so any
                    # executor of this task receives the full contract.
                    _contract = None
                    try:
                        from core.fleet_orchestration.delegation_contracts import (
                            maybe_contract_for_link,
                        )

                        _contract = maybe_contract_for_link(
                            goal=goal, sub_task=st
                        )
                    except Exception as ce:
                        logger.debug(f"delegation contract skipped: {ce}")

                    _link_ctx = {"fleet_goal": goal, "domain": domain}
                    if _contract is not None:
                        _link_ctx["delegation_contract"] = _contract.to_dict()
                    if _coi:
                        # Shadow signal only — informs Phase 5 calibration.
                        _link_ctx["coi_signal"] = True

                    link = fleet_service.recruit_member(
                        chain_id=chain.id,
                        parent_agent_id="atom_main",
                        child_agent_id=agent.id if agent else f"specialist_{domain}",
                        task_description=task_desc,
                        context_json=_link_ctx,
                        link_order=i,
                        optimization_metadata=optimization_metadata
                    )
                    
                    fleet_members.append({
                        "agent": agent.name if agent else domain,
                        "agent_id": agent.id if agent else f"specialist_{domain}",
                        "task": task_desc,
                        "status": "recruited"
                    })

                if step_callback:
                    await step_callback({
                        "type": "fleet_recruited",
                        "chain_id": chain.id,
                        "members": fleet_members
                })

                # P5 diversity floor (shadow): teams of >=3 spanning a single
                # declared model family are flagged (R6/R12 — homogeneous
                # pools entrench incumbents). Never blocks; telemetry only.
                try:
                    from core.org_integrity import (
                        allocator_integrity_enabled,
                        enforce_diversity_floor,
                    )
                    from core.models import AgentRegistry as _AR

                    if allocator_integrity_enabled() and len(fleet_members) >= 3:
                        _ids = [m["agent_id"] for m in fleet_members]
                        _rows = {
                            r.id: (r.diversity_profile or {})
                            for r in db.query(_AR).filter(_AR.id.in_(_ids)).all()
                            if r is not None
                        }

                        def _family_of(aid: str):
                            prof = _rows.get(aid) or {}
                            fam = prof.get("model_family") or prof.get("family")
                            return str(fam) if fam else None

                        _div = enforce_diversity_floor(_ids, _family_of)
                        if not _div.get("ok"):
                            logger.warning(
                                "Allocator integrity: diversity floor violated "
                                "for chain %s: %s",
                                chain.id, _div,
                            )
                            AgentOrgTelemetryService(db).emit(
                                "diversity_violation",
                                actor_agent_id="atom_main",
                                target_agent_id=chain.id,
                                payload=_div,
                            )
                except Exception as de:
                    logger.debug(f"diversity floor check skipped: {de}")

                # P0 org telemetry: coordinator→specialist recruit pairs
                # (incumbency baseline; write-only, never raises)
                try:
                    from core.org_telemetry_service import AgentOrgTelemetryService

                    AgentOrgTelemetryService(db).emit_fleet_recruit(
                        coordinator_agent_id="atom_main",
                        members=fleet_members,
                        chain_id=chain.id,
                        execution_id=context.get("execution_id"),
                        workspace_id=self.workspace_id,
                        tenant_id=tenant_id,
                    )
                except Exception as te:
                    logger.debug(f"org telemetry recruit emit skipped: {te}")

                # AgentRadio bridge: attach a lateral thread for the team —
                # ONLY when the task crosses responsibility breakpoints
                # (paper rule: a fixed multi-agent team is not the default;
                # bounded local work stays single-agent). The thread id flows
                # to every member's execution via context["radio_thread_id"]
                # so their ReAct loops pick up @mentions passively.
                try:
                    from core.agent_radio.radio_adapter import (
                        attach_thread_for_chain,
                    )

                    radio_thread = attach_thread_for_chain(
                        db,
                        chain_id=chain.id,
                        task_description=(
                            f"{goal}. "
                            + " ".join(
                                st.get("task", "") for st in sub_tasks
                            )
                        ),
                        team_agent_ids=[
                            m["agent_id"] for m in fleet_members
                        ],
                        created_by_agent_id="atom_main",
                        execution_id=context.get("execution_id"),
                        tenant_id=tenant_id,
                    )
                    if radio_thread is not None:
                        context["radio_thread_id"] = radio_thread.id
                        # Propagate the thread id onto every member's context_json
                        # so each specialist's ReAct loop drains the lateral inbox
                        # (passive awareness) when it runs. Without this the members
                        # would be recruited onto a thread they never listen to.
                        for link in db.query(ChainLink).filter(
                            ChainLink.chain_id == chain.id
                        ).all():
                            ctx = dict(link.context_json or {})
                            ctx["radio_thread_id"] = radio_thread.id
                            link.context_json = ctx
                        db.commit()
                except Exception as e:
                    logger.debug(f"radio thread attach skipped: {e}")

                member_summary = "\n".join([f"- {m['agent']}: {m['task']}" for m in fleet_members])
                return f"Fleet Successfully Recruited in Upstream (Chain: {chain.id}).\nMembers:\n{member_summary}\n\nAll members are now synchronized via the Fleet Blackboard."

        except Exception as e:
            logger.error(f"Fleet recruitment failed in Upstream: {e}")
            return "Fleet recruitment failed. Please try again."

    
    async def spawn_agent(self, template_name: str, custom_params: Dict[str, Any] = None,
                         persist: bool = False, db: Optional[Session] = None) -> AgentRegistry:
        """
        Spawn a specialty agent from template or custom definition.

        Args:
            template_name: Name of predefined template OR "custom"
            custom_params: Custom agent configuration
            persist: If True, register in database; else ephemeral
            db: Optional database session to use for persistence (useful for tests)
        """
        if template_name in SpecialtyAgentTemplate.TEMPLATES:
            template = SpecialtyAgentTemplate.TEMPLATES[template_name]
            
            # Extract capabilities for graduation registration
            initial_capabilities = template.get("capabilities", [])
            
            with SessionLocal() as reset_db:
                # Register capabilities at STUDENT level if they don't exist.
                # NOTE: must NOT shadow the `db` parameter — doing so made
                # the `if db is None:` fresh-session persist branch below
                # unreachable (persistence ran on the already-closed
                # reset-block session instead of a new one).
                for capability in initial_capabilities:
                    self.graduation_service.reset_maturity(
                        "atom_specialty_init",
                        capability,
                        "initial_spawn_registration"
                    )
            template = SpecialtyAgentTemplate.TEMPLATES[template_name]
        elif template_name == "custom" and custom_params:
            template = custom_params
        else:
            raise ValueError(f"Unknown agent template: {template_name}")
        
        # Create agent instance
        agent_id = f"spawned_{template_name}_{uuid.uuid4().hex[:8]}"
        
        agent = AgentRegistry(
            id=agent_id,
            name=template.get("name", f"Spawned {template_name}"),
            description=template.get("description", "Dynamically spawned agent"),
            category=template.get("category", "General"),
            status=AgentStatus.STUDENT.value,  # New agents start as STUDENT
            confidence_score=NEW_AGENT_CONFIDENCE,  # Below the INTERN floor (0.5)
            module_path="core.generic_agent",
            class_name="GenericAgent",
            configuration=custom_params or template.get("default_params", {}),
            workspace_id=self.workspace_id,  # Set workspace from AtomMetaAgent
            tenant_id=self.tenant_id       # Set tenant from AtomMetaAgent
        )

        if persist:
            # Register in database
            if db is None:
                # Create new session if none provided
                with SessionLocal() as session:
                    governance = AgentGovernanceService(
                        session,
                        workspace_id=self.workspace_id,
                        tenant_id=self.tenant_id
                    )
                    agent = governance.register_or_update_agent(
                        name=agent.name,
                        category=agent.category,
                        module_path=agent.module_path,
                        class_name=agent.class_name,
                        description=agent.description
                    )
                    logger.info(f"Persisted spawned agent: {agent.id}")
            else:
                # Use provided session (useful for tests)
                governance = AgentGovernanceService(
                    db,
                    workspace_id=self.workspace_id,
                    tenant_id=self.tenant_id
                )
                agent = governance.register_or_update_agent(
                    name=agent.name,
                    category=agent.category,
                    module_path=agent.module_path,
                    class_name=agent.class_name,
                    description=agent.description
                )
                logger.info(f"Persisted spawned agent: {agent.id}")
        else:
            # Ephemeral agent - just keep in memory
            self.spawned_agents[agent_id] = agent
            logger.info(f"Created ephemeral agent: {agent_id}")

        return agent

    async def teach_student(
        self,
        student_agent_id: str,
        lesson: str,
        topic: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Teach a STUDENT agent directly (the fast learning pathway).

        The meta agent is the primary interaction surface and the designated
        teacher, but teaching is a level-1 governance action — it is never
        blocked by the teacher's own maturity (an INTERN meta agent can
        still teach), and it only ACCELERATES learning: students also learn
        from observation via StudentLearningService.observe_workspace, and
        maturity promotion still goes through the training/graduation
        system regardless of how much was taught.
        """
        from core.student_learning_service import StudentLearningService

        session = db or SessionLocal()
        owns_session = db is None
        try:
            governance = AgentGovernanceService(
                session,
                workspace_id=self.workspace_id,
                tenant_id=self.tenant_id,
            )
            decision = await governance.can_perform_action_async(
                agent_id="atom_main",
                action_type="teach_student",
            )
            allowed = decision.get("allowed", False) if isinstance(decision, dict) else bool(decision)
            if not allowed:
                reason = (decision.get("reason") if isinstance(decision, dict) else None) or "Teaching not permitted"
                return {"status": "error", "reason": reason}

            # Anti-laundering (R86c): atom_main can share what it KNOWS
            # (world model, facts, distilled skills) with anyone, but
            # teaching transfers what it has PROVEN — domain evidence. It
            # teaches a business-role student only after earning
            # super-mentor status in that domain via the attribution ledger;
            # system/Meta students remain directly teachable. Mirrors
            # StudentTrainingService._find_mentor.
            from core.models import AgentRegistry as _AgentRow, DomainExperienceLedger
            from core.domain_attribution import count_domain_wins
            student = session.query(_AgentRow).filter(_AgentRow.id == student_agent_id).first()
            if student is not None and student.id != "atom_main":
                student_category = (student.category or "").lower()
                if student_category not in {"system", "meta"}:
                    min_wins = int(os.getenv("ATOM_SUPERMENTOR_MIN_DOMAIN_WINS", "5"))
                    ledger_domains = [
                        row[0] for row in session.query(DomainExperienceLedger.domain)
                        .filter(DomainExperienceLedger.agent_id == "atom_main")
                        .distinct().all()
                    ]
                    matching = [
                        d for d in ledger_domains
                        if d and (d in student_category or student_category in d)
                    ]
                    earned = any(
                        count_domain_wins(session, "atom_main", d) >= min_wins
                        for d in matching
                    )
                    if not earned:
                        return {
                            "status": "error",
                            "reason": (
                                f"atom_main has not earned mentorship in "
                                f"'{student.category or 'this role'}' — teaching "
                                "transfers proven domain judgment, not general "
                                f"knowledge. It qualifies as a mentor after "
                                f"{min_wins} verified wins on its "
                                f"'{student_category}' domain ledger; until then "
                                "a same-role senior should teach this student."
                            ),
                            "laundering_guard": True,
                        }

            learning = StudentLearningService(session)
            result = learning.learn_from_teacher(
                student_agent_id=student_agent_id,
                teacher_agent_id="atom_main",
                lesson=lesson,
                topic=topic,
            )
            if result.get("status") == "ok":
                logger.info(f"atom_main taught student {student_agent_id} (topic={topic or 'general'})")
            return result
        finally:
            if owns_session:
                session.close()

    async def query_memory(self, query: str, scope: str = "all") -> Dict[str, Any]:
        """
        Query the World Model for experiences and knowledge.
        
        Args:
            query: Semantic search query
            scope: "experiences", "knowledge", or "all"
        """
        result = await self.world_model.recall_experiences(
            agent=self._get_atom_registry(),
            current_task_description=query
        )
        
        if scope == "experiences":
            return {"experiences": result.get("experiences", [])}
        elif scope == "knowledge":
            return {"knowledge": result.get("knowledge", [])}
        return result
    
    async def generate_mentorship_guidance(self, student_agent_id: str, action: str, params: Dict, reason: str) -> str:
        """
        Generate guidance for a human reviewer when a Student agent requests approval for an action.
        This fulfills the requirement of 'Meta Agent guidance for Student agents'.
        """
        # specialized_supervision_check
        is_interim_supervisor = False
        student_category = "General"
        
        def _check_supervisors_sync():
            try:
                with SessionLocal() as db:
                    student = db.query(AgentRegistry).filter(AgentRegistry.id == student_agent_id).first()
                    if not student:
                        return "General", 0
                    
                    cat = student.category
                    # Check for any Supervised or Autonomous agents in same category
                    count = db.query(AgentRegistry).filter(
                        AgentRegistry.category == cat,
                        AgentRegistry.status.in_([AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]),
                        AgentRegistry.id != student_agent_id
                    ).count()
                    return cat, count
            except Exception as e:
                logger.warning(f"Failed to check for supervisors: {e}")
                # DB failure → assume NO supervisors so the Meta-Agent steps
                # in as interim supervisor (documented intent; the earlier
                # `return 1` contradicted it and left this unreachable).
                return "General", 0

        student_category, supervisors_count = await asyncio.to_thread(_check_supervisors_sync)
        
        if supervisors_count == 0:
            is_interim_supervisor = True

        supervisor_context = ""
        if is_interim_supervisor:
            supervisor_context = (
                f"NOTE: There are NO higher maturity agents (Supervised/Autonomous) in the '{student_category}' category.\n"
                f"You are the Acting Interim Supervisor for this Student.\n"
                f"Since the Student is Read-Only/Learning, you must detailedly PROPOSE the correct action logic or parameters to teach them.\n"
            )

        system_prompt = f"""You are the Atom Meta-Agent, acting as a mentor to a 'Student' agent.
A Student agent ({student_agent_id}) is requesting approval for a complex action.
Your goal is to analyze the action and provide high-quality 'Guidance' for the human reviewer.
{supervisor_context}
Analyze:
1. Is the action safe for a Student level agent (Read-Only)?
2. What are the potential risks or implications?
3. What should the human look for when approving/rejecting?
4. If the parameters look incorrect, PROPOSE the correct parameters.

Keep your guidance concise but professional and safety-conscious.
"""
        user_prompt = f"""Student Agent: {student_agent_id}
Action Requested: {action}
Parameters: {json.dumps(params, indent=2)}
Reason for Block: {reason}

Provide your Mentorship Guidance:"""

        guidance = await self.llm.generate_response(
            prompt=user_prompt,
            system_instruction=system_prompt,
            model_type="fast",
            temperature=0.3
        )
        
        return guidance or "Meta-Agent was unable to provide guidance for this action."

    # ==================== INTERNAL METHODS ====================
    
    def _get_atom_registry(self) -> AgentRegistry:
        """Get or create the Atom agent registry entry"""
        return AgentRegistry(
            id="atom_main",
            name="Atom",
            category="Meta",  # Special category for the main agent
            description="Central orchestrator agent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=1.0
        )
    
    async def _wait_for_approval(self, action_id: str) -> bool:
        """Poll for HITL decision"""
        max_wait = 600 # Default 10 mins
        interval = 5
        elapsed = 0

        while elapsed < max_wait:
            db = SessionLocal()
            try:
                gov = AgentGovernanceService(db)
                status_info = gov.get_approval_status(action_id)

                if status_info["status"] == HITLActionStatus.APPROVED.value:
                    return True
                if status_info["status"] == HITLActionStatus.REJECTED.value:
                    return False
            finally:
                db.close()

            await asyncio.sleep(interval)
            elapsed += interval

        return False # Timeout

    async def _wait_for_all_approvals(self, action_ids: List[str]) -> bool:
        """All-or-nothing HITL batch approval (Workstream G).

        Polls every action in the batch; returns True only when ALL are
        APPROVED. Any REJECTION (or the batch timeout) returns False — the
        caller must NOT execute any tool in the batch.
        """
        max_wait = 600  # Default 10 mins
        interval = 5
        elapsed = 0

        while elapsed < max_wait:
            db = SessionLocal()
            try:
                gov = AgentGovernanceService(db)
                all_approved = True
                for action_id in action_ids:
                    status_info = gov.get_approval_status(action_id)
                    if status_info["status"] == HITLActionStatus.REJECTED.value:
                        return False
                    if status_info["status"] != HITLActionStatus.APPROVED.value:
                        all_approved = False
                if all_approved:
                    return True
            finally:
                db.close()

            await asyncio.sleep(interval)
            elapsed += interval

        return False  # Timeout

    async def _execute_parallel_tools(
        self,
        actions: List["ToolCall"],
        context: Dict,
        step_callback: Optional[callable],
    ) -> List[Dict[str, Any]]:
        """Execute multiple independent tools in parallel (Workstream G).

        Governance is checked once per tool up front; any tool with complexity
        > 1 forces HITL batch approval. The batch is ALL-OR-NOTHING: if any
        approval is rejected, NO tool in the batch executes. ``mcp_tool_search``
        is executed serially because it mutates ``session_tools`` (a shared
        mutable that would race under ``asyncio.gather``). Each returned record
        maps one-to-one to an ``AgentReasoningStep`` in the loop.

        When ``ATOM_PARALLEL_TOOLS=false``, falls back to sequential execution
        of the batch (each tool through the normal governance path).
        """
        from core.hallucination_config import (
            get_max_parallel_tools,
            is_parallel_tools_enabled,
        )

        if not is_parallel_tools_enabled():
            records = []
            for act in actions[: get_max_parallel_tools()]:
                observation = await self._execute_tool_with_governance(
                    act.tool, act.params, context, step_callback
                )
                records.append({
                    "tool_name": act.tool,
                    "params": act.params,
                    "output": observation,
                    "verified_kind": "unverified",
                    "verified_evidence": None,
                })
            return records

        max_tools = get_max_parallel_tools()
        # mcp_tool_search mutates session_tools — must never run under gather.
        serial_actions = [a for a in actions if a.tool == "mcp_tool_search"]
        parallel_actions = [a for a in actions if a.tool != "mcp_tool_search"][:max_tools]

        # 1. Governance pre-check for the whole batch (all-or-nothing).
        action_ids: List[str] = []
        blocked: List["ToolCall"] = []
        with SessionLocal() as db:
            gov = AgentGovernanceService(db)
            for act in parallel_actions:
                auth_check = await gov.can_perform_action_async("atom_main", act.tool)
                complexity = auth_check.get("action_complexity", 2)
                if complexity > 1:
                    auth_check["requires_human_approval"] = True
                    auth_check["reason"] = (
                        f"Meta-Agent is in Propose-Only mode. Action "
                        f"'{act.tool}' requires confirmation."
                    )
                if auth_check.get("requires_human_approval"):
                    action_id = gov.request_approval(
                        agent_id="atom_main",
                        action_type=act.tool,
                        params=act.params,
                        reason=auth_check["reason"],
                    )
                    action_ids.append(action_id)
                    if step_callback:
                        await step_callback({
                            "type": "hitl_paused",
                            "action_id": action_id,
                            "tool": act.tool,
                            "reason": auth_check["reason"],
                            "parallel_batch": True,
                        })
                elif not auth_check["allowed"]:
                    blocked.append(act)

        if blocked:
            names = ", ".join(a.tool for a in blocked)
            return [
                {
                    "tool_name": a.tool,
                    "params": a.params,
                    "output": f"Governance blocked: {a.tool} (batch blocked by {names}).",
                    "verified_kind": "blocked",
                    "verified_evidence": None,
                }
                for a in parallel_actions
            ]

        if action_ids:
            approved = await self._wait_for_all_approvals(action_ids)
            if not approved:
                return [
                    {
                        "tool_name": a.tool,
                        "params": a.params,
                        "output": f"Action {a.tool} was REJECTED or timed out (parallel batch).",
                        "verified_kind": "rejected",
                        "verified_evidence": None,
                    }
                    for a in parallel_actions
                ]

        # 2. Execute the parallel batch. Governance already granted above.
        results = await asyncio.gather(
            *[
                self._execute_tool_with_governance(
                    a.tool, a.params, context, step_callback, pre_approved=True
                )
                for a in parallel_actions
            ],
            return_exceptions=True,
        )

        records: List[Dict[str, Any]] = []
        for act, res in zip(parallel_actions, results):
            if isinstance(res, Exception):
                # KillRun must abort the whole run, not become a per-tool
                # "Tool error" record in the batch.
                from core.sandbox_killrun import KillRunAborted
                if isinstance(res, KillRunAborted):
                    raise res
                observation = f"Tool error for {act.tool}. Please try again."
                verified_kind = "error"
                verified_evidence = None
            else:
                observation = res
                try:
                    _vo = parse_tool_outcome(observation)
                    verified_kind = _vo.kind
                    verified_evidence = _vo.evidence
                except Exception:
                    verified_kind = "unverified"
                    verified_evidence = None
            records.append({
                "tool_name": act.tool,
                "params": act.params,
                "output": observation,
                "verified_kind": verified_kind,
                "verified_evidence": verified_evidence,
            })

        # 3. Serial tool-search actions (mutate session_tools — no race).
        for act in serial_actions:
            try:
                found_tools = await self.mcp.search_tools(
                    act.params.get("query", ""), limit=5
                )
                existing_names = {t["name"] for t in self.session_tools}
                new_tools = [t for t in found_tools if t["name"] not in existing_names]
                self.session_tools.extend(new_tools)
                observation = (
                    f"Found {len(new_tools)} new tools (total: "
                    f"{len(self.session_tools)}). They have been added to your "
                    f"toolkit for the next step: {[t['name'] for t in new_tools]}"
                )
            except Exception as e:
                observation = f"Tool search failed: {e}"
            records.append({
                "tool_name": act.tool,
                "params": act.params,
                "output": observation,
                "verified_kind": "unverified",
                "verified_evidence": None,
            })

        return records

    def _persist_reasoning_step(
        self,
        execution_id: str,
        step_number: int,
        step_type: str,
        thought: str,
        action_dict: Optional[Dict[str, Any]],
        observation: Optional[str],
        confidence: float,
        verified_kind: str,
        verification_evidence: Optional[str],
        duration_ms: float,
        request: str,
        final_answer: Optional[str],
        context: Optional[Dict],
        dispatch_turn_fact: bool = True,
    ) -> str:
        """Persist one AgentReasoningStep + fire-and-forget per-turn fact extraction.

        ``dispatch_turn_fact`` (Workstream G): the parallel branch fires turn-fact
        extraction ONCE per batch (first tool's step) to avoid N redundant
        extraction calls for the same thought. Returns the DB row id (or ""
        when persistence failed).
        """
        step_id = ""
        try:
            # R82: stamp model provenance from the per-call contextvar set by
            # byok_handler._capture_echoed_model. Best-effort: absent echo →
            # NULL column, never blocks persistence.
            _resolved_model = None
            try:
                from core.llm.model_provenance import get_resolved_model

                _resolved_model = get_resolved_model()
            except Exception:
                pass
            with SessionLocal() as db:
                db_step = AgentReasoningStep(
                    id=str(uuid.uuid4()),
                    execution_id=execution_id,
                    step_number=step_number,
                    step_type=step_type,
                    thought=thought,
                    action=action_dict,
                    observation=observation,
                    confidence=confidence,
                    verified=verified_kind,
                    verification_evidence=verification_evidence,
                    duration_ms=duration_ms,
                    resolved_model=_resolved_model,
                )
                db.add(db_step)
                db.commit()
                step_id = db_step.id

                # ── Per-turn fact extraction (sync_turn hook) ──────────────
                # Fire-and-forget: a slow extraction must never block the
                # ReAct loop. STUDENT maturity is gated inside the extractor.
                if dispatch_turn_fact and _TURN_FACT_EXTRACTION_ENABLED:
                    try:
                        extractor = get_turn_fact_extractor(
                            workspace_id=self.workspace_id,
                            tenant_id=self.tenant_id,
                        )
                        maturity = None
                        if getattr(self, "graduation_service", None):
                            try:
                                maturity = self.graduation_service.get_maturity(
                                    "atom_main", "fact_extraction"
                                )
                            except Exception:
                                maturity = None

                        task = asyncio.create_task(
                            extractor.extract_from_turn(
                                user_request=request,
                                thought=thought,
                                action=action_dict,
                                observation=observation,
                                final_answer=final_answer,
                                execution_id=execution_id,
                                reasoning_step_id=db_step.id,
                                session_id=context.get("session_id")
                                if context
                                else None,
                                user_id=context.get("user_id") if context else None,
                                maturity=maturity,
                            )
                        )
                        _pending_extraction_tasks.add(task)

                        def _discard_extraction_task(t, _set=_pending_extraction_tasks):
                            _set.discard(t)

                        task.add_done_callback(_discard_extraction_task)
                    except Exception as e:
                        logger.debug(f"turn_fact extraction dispatch failed: {e}")
        except Exception as e:
            logger.error(f"Failed to persist reasoning step: {e}")
        return step_id

    async def _record_execution(self, request: str, result: Dict,
                                trigger_mode: AgentTriggerMode):
        """Record execution to World Model for future learning"""
        # R86c: attribute this run to a business role when the task text
        # carries one. This is what lets the generalist meta agent EARN
        # super-mentor status per domain (see core/domain_attribution) —
        # without it every outcome blurred into one unattributable row.
        # Vocabulary is mined from real work history so edge roles (beyond
        # the static keyword table) attribute dynamically.
        from core.domain_attribution import (
            build_domain_vocabulary, resolve_domain,
        )
        attributed_domain = None
        db = SessionLocal()
        try:
            vocabulary = build_domain_vocabulary(db)
            attributed_domain = resolve_domain(request, vocabulary=vocabulary)
        except Exception as ve:
            logger.debug(f"domain vocabulary pass skipped: {ve}")
            attributed_domain = resolve_domain(request)

        experience = AgentExperience(
            id=str(uuid.uuid4()),
            agent_id="atom_main",
            task_type="meta_orchestration",
            input_summary=request[:200],
            outcome=result.get("status", "Success") if result.get("final_output") else "Partial",
            learnings=f"Trigger: {trigger_mode.value}. Steps: {len(result.get('actions_executed', []))}",
            agent_role="Meta",
            specialty=attributed_domain,
            timestamp=datetime.now(timezone.utc)
        )
        await self.world_model.record_experience(experience)

        # 2. Update Governance Outcome — R87: terminal failure statuses
        # (timeout/budget_exceeded/killed_sandbox/failed) must never be
        # recorded as successes, even when their canned final text lacks the
        # word "error".
        success = _execution_succeeded(result)
        try:
            gov = AgentGovernanceService(db)
            # Domain attribution happens inside record_outcome now (shared
            # R86c wiring) — passing the task text here keeps the meta
            # agent's ledger row without double-writing it.
            await gov.record_outcome(
                "atom_main", success=success, task_summary=request[:200]
            )
        except Exception as ge:
            logger.error(f"Failed to record Atom governance outcome: {ge}")
        finally:
            db.close()
            
    def _get_communication_instruction(self, context: Dict) -> str:
        """Helper to fetch user communication style"""
        user_id = context.get("user_id") or (self.user.id if self.user else None)
        if not user_id: return ""

        db = None
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.metadata_json:
                c_style = user.metadata_json.get("communication_style", {})
                if c_style.get("enable_personalization"):
                    guide = c_style.get("style_guide", "")
                    if guide:
                        return f"\nCOMMUNICATION STYLE:\n{guide}\nPlease carefully mimic this style in your final answer."
            return ""
        except Exception as e:
            logger.debug(f"Failed to load user communication style: {e}")
            return ""
        finally:
            # Guard against SessionLocal() raising before `db` is bound —
            # an unbound db.close() would mask the original error with
            # UnboundLocalError and crash the ReAct prompt builder.
            if db is not None:
                db.close()

    # ============================================================================
    # GOVERNANCE-GATED ROUTING (Phase 256-07)
    # Ported from atom-saas with SaaS features removed
    # ============================================================================

    async def _check_governance(
        self,
        user_id: str,  # Changed from tenant_id
        agent_id: str,
        route_category: str
    ) -> tuple[bool, str | None]:
        """
        Check if agent has permission for routing category.

        Args:
            user_id: User UUID (single-tenant deployment)
            agent_id: Agent UUID
            route_category: Route category (chat, workflow, task)

        Returns:
            (allowed, reason) - allowed=True if governance check passes
        """
        with SessionLocal() as db:
            governance = AgentGovernanceService(db)
            decision = await governance.canPerformAction(
                user_id=user_id,  # Changed from tenant_id
                agent_id=agent_id,
                action=f"route_to_{route_category}"
            )

            if not decision.allowed:
                logger.warning(
                    "[MetaAgent] Governance denied %s routing for agent %s: %s",
                    route_category, agent_id, decision.reason,
                )
                return False, decision.reason

            return True, None

    async def route_with_governance(
        self,
        request: str,
        intent: IntentClassification,
        user_id: str,  # Changed from tenant_id
        agent_id: str = "atom_main"
    ) -> Dict[str, Any]:
        """
        Route request with governance checks.

        CHAT bypasses governance (simple conversational queries).
        WORKFLOW/TASK require governance checks.

        Args:
            request: User's natural language request
            intent: Classified intent from IntentClassifier
            user_id: User UUID (single-tenant deployment)
            agent_id: Agent UUID (default: atom_main)

        Returns:
            Routing result with handler and status
        """
        # CHAT bypasses governance
        if intent.category == IntentCategory.CHAT:
            result = await self._route_to_chat(request, user_id)
            return {
                **result,
                "decision_id": str(uuid.uuid4()),
                "governance_checked": False
            }

        # WORKFLOW/TASK require governance
        allowed, reason = await self._check_governance(
            user_id, agent_id, intent.category.value
        )

        if not allowed:
            # Auto-takeover proposal mode: propose CHAT alternative
            result = await self._propose_chat_alternative(
                original_request=request,
                denied_route=intent.category.value,
                denial_reason=reason,
                user_id=user_id
            )
            return {
                **result,
                "decision_id": str(uuid.uuid4()),
                "governance_checked": True,
                "governance_allowed": False
            }

        # Proceed with routing
        if intent.category == IntentCategory.WORKFLOW:
            result = await self._route_to_workflow(request, user_id)
            return {
                **result,
                "decision_id": str(uuid.uuid4()),
                "governance_checked": True,
                "governance_allowed": True
            }
        else:  # TASK
            result = await self._route_to_task(request, user_id, agent_id)
            return {
                **result,
                "decision_id": str(uuid.uuid4()),
                "governance_checked": True,
                "governance_allowed": True
            }

    async def _route_to_chat(
        self,
        request: str,
        user_id: str  # Changed from tenant_id
    ) -> Dict[str, Any]:
        """
        Route CHAT intent to LLMService for simple conversational response.

        Args:
            request: User's natural language request
            user_id: User UUID (single-tenant deployment)

        Returns:
            LLM response
        """
        logger.info(f"Routing CHAT intent to LLMService: {request[:50]}...")

        response = await self.llm.generate_response(
            prompt=request,
            system_prompt="You are a helpful AI assistant.",
            user_id=user_id  # Changed from tenant_id
        )

        return {
            "route": "CHAT",
            "handler": "LLMService",
            "response": response,
            "status": "chat_complete"
        }

    async def _route_to_workflow(
        self,
        request: str,
        user_id: str,  # Changed from tenant_id
        execution_mode: str = "one-off"
    ) -> Dict[str, Any]:
        """
        Route WORKFLOW intent to QueenAgent for blueprint generation.

        Args:
            request: User's natural language request
            user_id: User UUID (single-tenant deployment)
            execution_mode: Execution mode (one-off or recurring_automation)

        Returns:
            Blueprint generation result
        """
        logger.info(f"Routing WORKFLOW intent to QueenAgent: {request[:50]}...")

        with SessionLocal() as db:
            if not self.queen:
                self.queen = QueenAgent(db, self.llm, tenant_id=user_id)

            blueprint = await self.queen.generate_blueprint(
                goal=request,
                tenant_id=user_id,
                execution_mode=execution_mode
            )

            return {
                "route": "WORKFLOW",
                "handler": "QueenAgent",
                "blueprint_id": blueprint.get("blueprint_id"),
                "architecture_name": blueprint.get("architecture_name"),
                "node_count": len(blueprint.get("nodes", [])),
                "status": "blueprint_generated"
            }

    async def _route_to_task(
        self,
        request: str,
        user_id: str,  # Changed from tenant_id
        agent_id: str = "atom_main"
    ) -> Dict[str, Any]:
        """
        Route TASK intent to FleetAdmiral for dynamic agent recruitment.

        Args:
            request: User's natural language request
            user_id: User UUID (single-tenant deployment)
            agent_id: Agent UUID

        Returns:
            Fleet recruitment result
        """
        logger.info(f"Routing TASK intent to FleetAdmiral: {request[:50]}...")

        # Import FleetAdmiral
        from core.fleet_admiral import FleetAdmiral

        with SessionLocal() as db:
            admiral = FleetAdmiral(db, self.llm)

            result = await admiral.recruit_and_execute(
                task=request,
                user_id=user_id,  # Changed from tenant_id
                root_agent_id=agent_id
            )

            return {
                "route": "TASK",
                "handler": "FleetAdmiral",
                "chain_id": result.get("chain_id"),
                "specialists_count": result.get("specialists_count"),
                "status": "task_routed",
                "result": result
            }

    async def _propose_chat_alternative(
        self,
        original_request: str,
        denied_route: str,
        denial_reason: str,
        user_id: str  # Changed from tenant_id
    ) -> Dict[str, Any]:
        """
        Auto-takeover proposal mode: When governance denies WORKFLOW/TASK,
        automatically propose CHAT-based alternative without human intervention.

        This generates a helpful response explaining:
        1. Why the original request was denied (governance reason)
        2. What CHAT can do instead (limited but safe alternative)
        3. How to upgrade agent maturity for future access

        Args:
            original_request: User's original request
            denied_route: Route category that was denied (workflow/task)
            denial_reason: Governance denial reason
            user_id: User UUID (single-tenant deployment)

        Returns:
            Dict with chat_response and proposal metadata
        """
        # Generate proposal explanation using LLM
        proposal_prompt = f"""
The user requested: "{original_request}"
This was routed to {denied_route} but denied by governance because: {denial_reason}

Generate a helpful response that:
1. Acknowledges the request
2. Explains why it cannot be executed as {denied_route} (agent maturity restriction)
3. Offers to answer via CHAT mode instead (informational response, no actions)
4. Suggests upgrading agent maturity level for future {denied_route} access

Keep it concise (2-3 sentences) and helpful. Do not be apologetic - be informative.
"""

        chat_response = await self.llm.generate_response(
            prompt=proposal_prompt,
            system_prompt="You are a helpful AI assistant explaining routing decisions.",
            user_id=user_id  # Changed from tenant_id
        )

        return {
            "route": "CHAT",
            "handler": "LLMService",
            "auto_takeover": True,
            "original_route": denied_route,
            "denial_reason": denial_reason,
            "proposal": chat_response,
            "status": "auto_takeover_proposal"
        }


# ==================== TRIGGER HANDLERS ====================

async def handle_data_event_trigger(event_type: str, data: Dict[str, Any], 
                                    workspace_id: str = "default") -> Dict[str, Any]:
    """
    Handler for data-driven agent triggers.
    Called when new data arrives (webhook, ingestion, integration event, etc.)
    """
    # Build request from event
    request = f"Process {event_type} event with data: {str(data)[:100]}"
    
    # 1. Try Redis Task Queue Dispatch (Async/Scalable)
    try:
        from core.task_queue import get_task_queue
        from core.agent_worker_wrapper import execute_agent_background
        
        task_queue = get_task_queue()
        if task_queue.enabled:
            task_id = task_queue.enqueue_job(
                func=execute_agent_background,
                queue_name="workflows",
                task_data={
                    "request": request,
                    "context": {"event_type": event_type, "event_data": data},
                    "trigger_mode": AgentTriggerMode.DATA_EVENT.value,
                    "tenant_id": workspace_id
                }
            )
            if task_id:
                logger.info(f"Data event trigger queued to Redis: {task_id}")
                return {"status": "queued", "task_id": task_id, "message": "Agent execution offloaded to background worker"}
            
        logger.warning("Task queue is disabled. Falling back to inline execution.")
    except Exception as e:
        logger.error(f"Redis dispatch failed for agent trigger: {e}. Falling back to inline execution.")
    
    # 2. Fallback to Inline Execution (Blocking)
    atom = AtomMetaAgent(workspace_id)
    result = await atom.execute(
        request=request,
        context={"event_type": event_type, "event_data": data},
        trigger_mode=AgentTriggerMode.DATA_EVENT
    )
    
    return result


async def handle_manual_trigger(request: str, user: User, 
                               workspace_id: str = "default",
                               additional_context: Dict = None,
                               execution_id: str = None) -> Dict[str, Any]:
    """
    Handler for manual/user-initiated agent triggers.
    Called from Chat or API.
    """
    atom = AtomMetaAgent(workspace_id, user=user)
    
    # Define streaming callback for UI feedback
    from core.websockets import manager as ws_manager
    async def streaming_callback(step_record):
        try:
            # 1. Broadcast to the specific workspace channel
            await ws_manager.broadcast(f"workspace:{workspace_id}", {
                "type": "agent_step_update",
                "agent_id": "atom_main",
                "step": step_record
            })
            
            # 2. Persist to DB for long-term visibility
            from core.reasoning_chain import get_reasoning_tracker, ReasoningStep
            tracker = get_reasoning_tracker()
            
            execution_id = step_record.get("execution_id")
            if execution_id:
                # Use standard ReasoningStepType if possible
                from core.reasoning_chain import ReasoningStepType
                # BUG FIX (W44): the map previously referenced
                # ReasoningStepType.FINAL_ANSWER which does NOT exist in the
                # enum (members: INTENT_ANALYSIS, MEMORY_QUERY, AGENT_SELECTION,
                # AGENT_SPAWN, INTEGRATION_CALL, WORKFLOW_TRIGGER, DECISION,
                # ACTION, CONCLUSION). The dict literal evaluates ALL values
                # eagerly, so AttributeError fired on EVERY step and the
                # reasoning-chain persistence silently never ran. CONCLUSION
                # is the closest semantic match for a final answer.
                stype_map = {
                    "action": ReasoningStepType.ACTION,
                    "final_answer": ReasoningStepType.CONCLUSION,
                    "planning": ReasoningStepType.INTENT_ANALYSIS,
                    "hitl_paused": ReasoningStepType.DECISION
                }
                
                step_obj = ReasoningStep(
                    id=str(uuid.uuid4()),
                    step_type=stype_map.get(step_record.get("step_type"), ReasoningStepType.ACTION),
                    description=step_record.get("thought", step_record.get("reason", "")),
                    inputs={"action": step_record.get("action")} if step_record.get("action") else {},
                    outputs={"observation": step_record.get("output")} if step_record.get("output") else {},
                    confidence=step_record.get("confidence", 0.9),
                    duration_ms=step_record.get("duration_ms", 0.0),
                    timestamp=datetime.now(timezone.utc),
                    metadata={"step_number": step_record.get("step")}
                )
                tracker.persist_step_to_db(step_obj, execution_id)
                
        except Exception as e:
            logger.warning(f"Failed to stream/persist agent step: {e}")

    # Merge contexts
    exec_context = {"user_id": user.id, "user_email": user.email}
    if additional_context:
        exec_context.update(additional_context)

    result = await atom.execute(
        request=request,
        context=exec_context,
        trigger_mode=AgentTriggerMode.MANUAL,
        step_callback=streaming_callback,
        execution_id=execution_id
    )
    
    return result


"""
Meta-Agent Routing Methods (Single-Tenant Version)

Ported from: rush869ark99/atom-saas@6c5f4e3d4
Changes: Replaced tenant_id with user_id, removed SaaS-specific features
"""

import logging
from typing import Dict, Any, Optional
from core.agent_governance_service import AgentGovernanceService
from core.intent_classifier import IntentCategory, IntentClassification

logger = logging.getLogger(__name__)


async def _check_governance(
    self,
    user_id: str,
    agent_id: str,
    route_category: str
) -> tuple[bool, str | None]:
    """
    Check if agent has permission for routing category.

    Args:
        user_id: User identifier (single-tenant architecture)
        agent_id: Agent UUID
        route_category: Route category (chat, workflow, task)

    Returns:
        (allowed, reason) - allowed=True if governance check passes
    """
    from core.database import SessionLocal
    
    with SessionLocal() as db:
        governance = AgentGovernanceService(db)
        decision = await governance.canPerformAction(
            user_id=user_id,
            agent_id=agent_id,
            action=f"route_to_{route_category}"
        )

        if not decision.allowed:
            # Log governance denial (simplified - no AuditLogger in upstream)
            logger.warning(
                f"[MetaAgent] Governance denied {route_category} routing: "
                f"{decision.reason}"
            )
            return False, decision.reason

        return True, None


async def _route_to_chat(
    self,
    request: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Route CHAT intent to LLMService for simple conversational response.

    Args:
        request: User's natural language request
        user_id: User identifier (single-tenant architecture)

    Returns:
        LLM response
    """
    logger.info(f"Routing CHAT intent to LLMService: {request[:50]}...")

    response = await self.llm.generate_response(
        prompt=request,
        system_prompt="You are a helpful AI assistant.",
        user_id=user_id
    )

    return {
        "route": "CHAT",
        "handler": "LLMService",
        "response": response,
        "status": "chat_complete"
    }


async def _route_to_workflow(
    self,
    request: str,
    user_id: str,
    execution_mode: str = "one-off"
) -> Dict[str, Any]:
    """
    Route WORKFLOW intent to QueenAgent for blueprint generation.

    Args:
        request: User's natural language request
        user_id: User identifier (single-tenant architecture)
        execution_mode: Execution mode (one-off or recurring_automation)

    Returns:
        Blueprint generation result
    """
    from core.database import SessionLocal
    
    logger.info(f"Routing WORKFLOW intent to QueenAgent: {request[:50]}...")

    with SessionLocal() as db:
        if not self.queen:
            from core.agents.queen_agent import QueenAgent
            self.queen = QueenAgent(db, self.llm, workspace_id=user_id)

        blueprint = await self.queen.generate_blueprint(
            goal=request,
            tenant_id=user_id,
            execution_mode=execution_mode
        )

        return {
            "route": "WORKFLOW",
            "handler": "QueenAgent",
            "blueprint_id": blueprint.get("blueprint_id"),
            "architecture_name": blueprint.get("architecture_name"),
            "node_count": len(blueprint.get("nodes", [])),
            "status": "blueprint_generated"
        }


async def _route_to_task(
    self,
    request: str,
    user_id: str,
    agent_id: str = "atom_main"
) -> Dict[str, Any]:
    """
    Route TASK intent to FleetAdmiral for dynamic agent recruitment.

    Args:
        request: User's natural language request
        user_id: User identifier (single-tenant architecture)
        agent_id: Agent UUID

    Returns:
        Fleet recruitment result
    """
    from core.database import SessionLocal
    from core.fleet_admiral import FleetAdmiral
    
    logger.info(f"Routing TASK intent to FleetAdmiral: {request[:50]}...")

    with SessionLocal() as db:
        fleet_admiral = FleetAdmiral(db, self.llm)
        
        result = await fleet_admiral.recruit_and_execute(
            task=request,
            user_id=user_id,
            root_agent_id=agent_id
        )

        return {
            "route": "TASK",
            "handler": "FleetAdmiral",
            "result": result,
            "status": "task_routed"
        }


async def _propose_chat_alternative(
    self,
    original_request: str,
    denied_route: str,
    denial_reason: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Auto-takeover proposal mode: When governance denies WORKFLOW/TASK,
    automatically propose CHAT-based alternative without human intervention.

    This generates a helpful response explaining:
    1. Why the original request was denied (governance reason)
    2. What CHAT can do instead (limited but safe alternative)
    3. How to upgrade agent maturity for future access

    Args:
        original_request: User's original request
        denied_route: Route category that was denied (workflow/task)
        denial_reason: Governance denial reason
        user_id: User identifier (single-tenant architecture)

    Returns:
        Dict with chat_response and proposal metadata
    """
    # Generate proposal explanation using LLM
    proposal_prompt = f"""
The user requested: "{original_request}"
This was routed to {denied_route} but denied by governance because: {denial_reason}

Generate a helpful response that:
1. Acknowledges the request
2. Explains why it cannot be executed as {denied_route} (agent maturity restriction)
3. Offers to answer via CHAT mode instead (informational response, no actions)
4. Suggests upgrading agent maturity level for future {denied_route} access

Keep it concise (2-3 sentences) and helpful. Do not be apologetic - be informative.
"""

    chat_response = await self.llm.generate_response(
        prompt=proposal_prompt,
        system_prompt="You are a helpful AI assistant explaining routing decisions.",
        user_id=user_id
    )

    return {
        "route": "CHAT",
        "handler": "LLMService",
        "auto_takeover": True,
        "original_route": denied_route,
        "denial_reason": denial_reason,
        "proposal": chat_response,
        "status": "auto_takeover_proposal"
    }


# Singleton for easy access
_atom_instance: Optional[AtomMetaAgent] = None

def get_atom_agent(workspace_id: str = "default") -> AtomMetaAgent:
    global _atom_instance
    if _atom_instance is None or _atom_instance.workspace_id != workspace_id:
        _atom_instance = AtomMetaAgent(workspace_id)
    return _atom_instance
