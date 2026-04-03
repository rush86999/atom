"""
Atom Meta-Agent - Central Orchestrator for ATOM Platform
The main intelligent agent that can spawn specialty agents and access all platform features.
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from fastapi import HTTPException

from core.models import (
    AgentRegistry, AgentStatus, User, HITLActionStatus, AgentExecution,
    Workspace, AgentReasoningStep, ExecutionStatus, AgentTriggerMode,
    MetaAgentDecision  # For routing decision logging
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


# LLM Integration:
# Uses LLMService for unified LLM interactions (BYOK key resolution, cost tracking, observability).
# Initialized via get_llm_service() singleton factory for workspace-aware service.
# All LLM calls (generate_response, generate_structured_response) go through self.llm.

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    tool: str = Field(..., description="Name of the tool to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool")

class ReActStep(BaseModel):
    thought: str = Field(..., description="The reasoning behind the current action or final answer")
    action: Optional[ToolCall] = Field(None, description="The tool to call if further action is needed")
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
        self.world_model = WorldModelService(workspace_id=workspace_id, tenant_id=self.tenant_id)
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

        
    async def execute(self, request: str, context: Dict[str, Any] = None, 
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
        
        start_time = datetime.now(timezone.utc)
        execution_id = execution_id or str(uuid.uuid4())

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
                execution = AgentExecution(
                    id=execution_id,
                    agent_id="atom_main",
                    tenant_id=tenant_id,
                    status=ExecutionStatus.RUNNING.value,
                    input_summary=request[:200],
                    triggered_by=trigger_mode.value,
                    started_at=start_time
                )
                db.add(execution)
                db.commit()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create AgentExecution: {e}")
        
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
        if "mcp_tool_search" not in [t["name"] for t in unique_active_tools]:
             unique_active_tools.append({
                 "name": "mcp_tool_search",
                 "description": "Search for more capabilities/tools if you can't find what you need in the current list. Returns list of tools that you can then use in the NEXT step.",
                 "parameters": {"query": "string"}
             })

        tool_descriptions = json.dumps([{"name": t["name"], "description": t["description"]} for t in unique_active_tools], indent=2)


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

        for current_step in range(1, max_steps + 1):
            step_start = datetime.now(timezone.utc)
            # Generate next step using instructor for structured output
            react_step = await self._react_step(
                request=request,
                memory_context=memory_context,
                tool_descriptions=tool_descriptions,
                execution_history=execution_history,
                context=context,
                canvas_text=canvas_text  # NEW: Canvas context
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
            
            # Safety: If no action and no final answer, we are stuck - convert thought to final answer
            if not react_step.action:
                final_answer = react_step.thought or "I'm sorry, I'm unable to proceed with that request."
                step_record["final_answer"] = final_answer
                step_record["step_type"] = "final_answer"
                # Record it one last time to satisfy visibility
                if step_callback: await step_callback(step_record)
                steps.append(step_record)
                break
            
            # Execute action if provided
            if react_step.action:
                tool_name = react_step.action.tool
                tool_args = react_step.action.params
                
                execution_history += f"Action: {tool_name}({json.dumps(tool_args)})\n"
                
                if tool_name == "mcp_tool_search":
                    found_tools = await self.mcp.search_tools(tool_args.get("query", ""), limit=5)
                    self.session_tools.extend(found_tools)
                    observation = f"Found {len(found_tools)} tools. They have been added to your toolkit for the next step: {[t['name'] for t in found_tools]}"
                    
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
                    execution_history += f"Observation: {observation}\n"

                # Update duration after tool execution
                step_record["duration_ms"] = (datetime.now(timezone.utc) - step_start).total_seconds() * 1000
                if step_callback: await step_callback(step_record)
            
            # Persist Step to DB (Phase 6: Learning Loop)
            try:
                with SessionLocal() as db:
                    db_step = AgentReasoningStep(
                        id=str(uuid.uuid4()),
                        execution_id=execution_id,
                        step_number=current_step,
                        step_type=step_record["step_type"],
                        thought=react_step.thought,
                        action=react_step.action.model_dump() if react_step.action else None,
                        observation=step_record.get("output"),
                        confidence=step_record["confidence"],
                        duration_ms=step_record["duration_ms"]
                    )
                    db.add(db_step)
                    db.commit()
                    # Add DB ID to record for UI feedback binding
                    step_record["id"] = db_step.id 
            except Exception as e:
                logger.error(f"Failed to persist reasoning step: {e}")
                # traceback.print_exc()

            steps.append(step_record)
        
        # Handle max steps exceeded
        if not final_answer:
            final_answer = "Maximum reasoning steps reached. Please refine your request."
            status = "max_steps_exceeded"
        
        # 4. Record Execution
        result_payload = {
            "final_output": final_answer,
            "actions_executed": steps,
            "trigger_mode": trigger_mode.value,
            "status": status
        }
        
        await self._record_execution(request, result_payload, trigger_mode)
        
        # Update Execution Record with duration
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        db = SessionLocal()
        try:
            execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
            if execution:
                execution.status = "completed" if status == "success" else status
                execution.result_summary = str(final_answer)[:500]
                execution.duration_seconds = duration
                execution.completed_at = end_time
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update AgentExecution: {e}")
            db.rollback()
        finally:
            db.close()

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
            return f"Delegation failed: {str(e)}"



    async def _react_step(self, request: str, memory_context: Dict, 
                          tool_descriptions: str, execution_history: str, 
                          context: Dict, canvas_text: str = "") -> ReActStep:
        """
        Generate a single ReAct step with Pydantic validation.
        Uses instructor to ensure structured output.
        """
        canvas_segment = f"\nCURRENT CANVAS STATE:\n{canvas_text}" if canvas_text else ""
        
        system_prompt = """You are Atom, an intelligent business assistant.

AVAILABLE TOOLS:
{tool_descriptions}

FORMAT: You must respond with structured output containing:
- thought: Your reasoning about what to do next
- action: If you need to use a tool, provide {{"tool": "tool_name", "params": {{...}}}}
- final_answer: If you have enough information to answer, provide the response

Only provide EITHER action OR final_answer, not both.

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

{canvas_segment}
""".format(
            tool_descriptions=tool_descriptions,
            comm_instruction=self._get_communication_instruction(context),
            canvas_segment=canvas_segment
        )
        
        # Build rich memory context for the prompt
        experiences = memory_context.get('experiences', [])
        knowledge = memory_context.get('knowledge', [])
        formulas = memory_context.get('formulas', [])
        facts = memory_context.get('business_facts', [])
        canvas_episodes = memory_context.get('canvas_episodes', [])  # NEW: Canvas-aware episodes

        memory_sections = []
        if experiences:
            exp_summaries = [f"- {getattr(e, 'input_summary', 'Task')[:80]}... → {getattr(e, 'outcome', 'completed')}" for e in experiences[:3]]
            memory_sections.append(f"PAST EXPERIENCES:\n" + "\n".join(exp_summaries))
        if canvas_episodes:  # NEW: Canvas-aware episodic memory
            canvas_ep_summaries = [
                f"- [{e.get('canvas_id', 'unknown')[:8]}] {e.get('task_description', 'Task')[:60]}... → {e.get('outcome', 'completed')} (boost: +{e.get('canvas_boost', 0):.2f})"
                for e in canvas_episodes[:3]
            ]
            memory_sections.append(f"CANVAS EPISODES (same workspace):\n" + "\n".join(canvas_ep_summaries))
        if knowledge:
            doc_summaries = [f"- {k.get('text', '')[:100]}..." for k in knowledge[:3]]
            memory_sections.append(f"RELEVANT KNOWLEDGE:\n" + "\n".join(doc_summaries))
        if formulas:
            formula_summaries = [f"- {f.get('name', 'Formula')}: {f.get('description', '')[:60]}" for f in formulas[:3]]
            memory_sections.append(f"AVAILABLE FORMULAS:\n" + "\n".join(formula_summaries))
        if facts:
            fact_summaries = [f"- [Status: {f.verification_status}] {f.fact} (Source: {f.metadata.get('source', 'unknown')})" for f in facts[:3]]
            memory_sections.append(f"TRUSTED BUSINESS FACTS:\n" + "\n".join(fact_summaries))
        
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
            task_type="reasoning",
            agent_id="atom_main"
        )
        
        if structured_result:
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

    async def _execute_tool_with_governance(self, tool_name: str, args: Dict, 
                                            context: Dict, step_callback: Optional[callable]) -> str:
        """Execute a tool via MCP with governance checks"""
        try:
            # 1. Governance Check
            db = SessionLocal()
            try:
                gov = AgentGovernanceService(db)
                # 1. Governance Check
                auth_check = gov.can_perform_action("atom_main", tool_name)
                
                # META AGENT CONSTRAINT: Enforce Propose-Only for all non-read actions (Complexity > 1)
                # The user must accept or modify any state-changing task.
                complexity = auth_check.get("action_complexity", 2)
                if complexity > 1:
                    auth_check["requires_human_approval"] = True
                    auth_check["reason"] = f"Meta-Agent is in Propose-Only mode. Action '{tool_name}' requires confirmation."

                if auth_check.get("requires_human_approval"):
                    action_id = gov.request_approval(
                        agent_id="atom_main",
                        action_type=tool_name,
                        params=args,
                        reason=auth_check["reason"],
                        workspace_id=self.workspace_id
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
                maturity = self.graduation_service.get_maturity(self.tenant_id, "atom_main", capability_name)

                logger.info(f"Invoking capability '{capability_name}' at maturity level: {maturity}")

                # Enforce gating (Student level requires HITL)
                if maturity == "student":
                    return f"Action 'invoke_capability({capability_name})' blocked. Capability is at STUDENT level and requires explicit governance authorization or HITL approval."

                # Execute logic...
                result = await self.mcp.call_tool(capability_name, args.get("params", {}), context=context)

                # Record usage for graduation
                self.graduation_service.record_usage(self.tenant_id, "atom_main", capability_name, success=True)
                return str(result)

            # 2. Execute via MCP with governance check
            result = await self.mcp.call_tool(tool_name, args, context=context)
            return str(result)

        except Exception as e:
            return f"Tool error: {str(e)}"

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

                    # 2. Recruit the specialist
                    agent = get_specialized_agent(domain, self.workspace_id)
                    
                    # 3. Create the Link
                    link = fleet_service.recruit_member(
                        chain_id=chain.id,
                        parent_agent_id="atom_main",
                        child_agent_id=agent.id if agent else f"specialist_{domain}",
                        task_description=task_desc,
                        context_json={"fleet_goal": goal, "domain": domain},
                        link_order=i,
                        optimization_metadata=optimization_metadata
                    )
                    
                    fleet_members.append({
                        "agent": agent.name if agent else domain,
                        "task": task_desc,
                        "status": "recruited"
                    })

                if step_callback:
                    await step_callback({
                        "type": "fleet_recruited",
                        "chain_id": chain.id,
                        "members": fleet_members
                    })
                
                member_summary = "\n".join([f"- {m['agent']}: {m['task']}" for m in fleet_members])
                return f"Fleet Successfully Recruited in Upstream (Chain: {chain.id}).\nMembers:\n{member_summary}\n\nAll members are now synchronized via the Fleet Blackboard."

        except Exception as e:
            logger.error(f"Fleet recruitment failed in Upstream: {e}")
            return f"Fleet recruitment error: {str(e)}"

    
    async def spawn_agent(self, template_name: str, custom_params: Dict[str, Any] = None,
                         persist: bool = False) -> AgentRegistry:
        """
        Spawn a specialty agent from template or custom definition.
        
        Args:
            template_name: Name of predefined template OR "custom"
            custom_params: Custom agent configuration
            persist: If True, register in database; else ephemeral
        """
        if template_name in SpecialtyAgentTemplate.TEMPLATES:
            template = SpecialtyAgentTemplate.TEMPLATES[template_name]
            
            # Extract capabilities for graduation registration
            initial_capabilities = template.get("capabilities", [])
            
            with SessionLocal() as db:
                # Register capabilities at STUDENT level if they don't exist
                for capability in initial_capabilities:
                    self.graduation_service.reset_maturity(
                        self.tenant_id, 
                        # Use a deterministic ID placeholder if agent is not yet persisted
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
            confidence_score=0.5,  # Default starting confidence
            module_path="core.generic_agent",
            class_name="GenericAgent",
            configuration=custom_params or template.get("default_params", {})
        )
        
        if persist:
            # Register in database
            with SessionLocal() as db:
                governance = AgentGovernanceService(db)
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
            self._spawned_agents[agent_id] = agent
            logger.info(f"Created ephemeral agent: {agent_id}")
        
        return agent
    
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
                return "General", 1 # Default to assuming supervisor exists to be safe, or 0? 
                                    # Safe fallback: assume 0 to force Meta Agent help? 
                                    # Actually, if DB fails, maybe we WANT Meta Agent help.
                                    # Let's return 0 on error to be safe (Meta Agent steps in).
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

    async def _record_execution(self, request: str, result: Dict, 
                                trigger_mode: AgentTriggerMode):
        """Record execution to World Model for future learning"""
        experience = AgentExperience(
            id=str(uuid.uuid4()),
            agent_id="atom_main",
            task_type="meta_orchestration",
            input_summary=request[:200],
            outcome=result.get("status", "Success") if result.get("final_output") else "Partial",
            learnings=f"Trigger: {trigger_mode.value}. Steps: {len(result.get('actions_executed', []))}",
            agent_role="Meta",
            specialty=None,
            timestamp=datetime.now(timezone.utc)
        )
        await self.world_model.record_experience(experience)

        # 2. Update Governance Outcome
        success = result.get("status") == "success" or (result.get("final_output") is not None and "error" not in result.get("final_output").lower())
        db = SessionLocal()
        try:
            gov = AgentGovernanceService(db)
            await gov.record_outcome("atom_main", success=success)
        except Exception as ge:
            logger.error(f"Failed to record Atom governance outcome: {ge}")
        finally:
            db.close()
            
    def _get_communication_instruction(self, context: Dict) -> str:
        """Helper to fetch user communication style"""
        user_id = context.get("user_id") or (self.user.id if self.user else None)
        if not user_id: return ""
        
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
                # Log governance denial
                from core.audit_logger import AuditLogger
                AuditLogger.log_decision(
                    db=db,
                    user_id=user_id,  # Changed from tenant_id
                    decision_type="governance_denial",
                    decision_id=str(uuid.uuid4()),
                    trigger_source="meta_agent_routing",
                    reasoning_summary=f"Governance denied {route_category} routing",
                    explanation=decision.reason
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
                self.queen = QueenAgent(db, self.llm, user_id=user_id)  # Changed from tenant_id

            blueprint = await self.queen.generate_blueprint(
                goal=request,
                user_id=user_id,  # Changed from tenant_id
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
    atom = AtomMetaAgent(workspace_id, user)
    
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
                stype_map = {
                    "action": ReasoningStepType.ACTION,
                    "final_answer": ReasoningStepType.FINAL_ANSWER,
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


async def route_with_governance(
    self,
    request: str,
    intent: IntentClassification,
    user_id: str,
    agent_id: str = "atom_main"
) -> Dict[str, Any]:
    """
    Route request with governance checks.

    CHAT bypasses governance (simple conversational queries).
    WORKFLOW/TASK require governance checks.

    Args:
        request: User's natural language request
        intent: Classified intent from IntentClassifier
        user_id: User identifier (single-tenant architecture)
        agent_id: Agent UUID (default: atom_main)

    Returns:
        Routing result with handler and status
    """
    # CHAT bypasses governance
    if intent.category == IntentCategory.CHAT:
        return await self._route_to_chat(request, user_id)

    # WORKFLOW/TASK require governance
    allowed, reason = await self._check_governance(
        user_id, agent_id, intent.category.value
    )

    if not allowed:
        # Auto-takeover proposal mode: propose CHAT alternative
        return await self._propose_chat_alternative(
            original_request=request,
            denied_route=intent.category.value,
            denial_reason=reason,
            user_id=user_id
        )

    # Proceed with routing
    if intent.category == IntentCategory.WORKFLOW:
        return await self._route_to_workflow(request, user_id)
    else:  # TASK
        return await self._route_to_task(request, user_id, agent_id)


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
            user_id=user_id,
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
