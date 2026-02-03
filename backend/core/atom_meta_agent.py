"""
Atom Meta-Agent - Central Orchestrator for ATOM Platform
The main intelligent agent that can spawn specialty agents and access all platform features.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
from ai.nlp_engine import CommandType, NaturalLanguageEngine

from core.agent_governance_service import AgentGovernanceService
from core.agent_world_model import AgentExperience, WorldModelService
from core.database import get_db_session
from core.models import (
    AgentExecution,
    AgentRegistry,
    AgentStatus,
    HITLActionStatus,
    User,
    Workspace,
)
from integrations.mcp_service import mcp_service

logger = logging.getLogger(__name__)


class AgentTriggerMode(Enum):
    """How an agent can be triggered"""
    MANUAL = "manual"           # User-initiated via API/Chat
    DATA_EVENT = "data_event"   # Triggered by new data (webhook, ingestion, etc.)
    SCHEDULED = "scheduled"     # Triggered by cron/scheduler
    WORKFLOW = "workflow"       # Triggered as part of a workflow step


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
        }
    }



import json

from core.llm.byok_handler import BYOKHandler
from core.react_models import ReActObservation, ReActStep, ToolCall

# Try to import instructor and AsyncOpenAI
try:
    import instructor
    from openai import AsyncOpenAI
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False
    instructor = None
    AsyncOpenAI = None

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
        "delegate_task",
        "request_human_intervention",
        "get_system_health",
        "list_integrations",
        "list_integrations",
        "call_integration",  # Fallback
        "canvas_tool"
    ]

    def __init__(self, workspace_id: str = "default", user: Optional[User] = None):
        self.workspace_id = workspace_id
        self.user = user
        self.world_model = WorldModelService(workspace_id)
        self.orchestrator = AdvancedWorkflowOrchestrator()
        self._spawned_agents: Dict[str, AgentRegistry] = {}
        self.mcp = mcp_service  # MCP access for tools
        self.llm = BYOKHandler(workspace_id=workspace_id)
        self.session_tools: List[Dict[str, Any]] = [] # Usage: Dynamically added tools

        
    async def execute(self, request: str, context: Dict[str, Any] = None, 
                      trigger_mode: AgentTriggerMode = AgentTriggerMode.MANUAL,
                      step_callback: Optional[callable] = None,
                      execution_id: str = None) -> Dict[str, Any]:
        """
        Main entry point for Atom. Uses Robust ReAct Loop with Pydantic validation.
        Based on 2025 Architecture: PydanticAI wraps each step in a validation layer.
        """
        context = context or {}
        if "original_request" not in context:
            context["original_request"] = request
            
        logger.info(f"Atom executing request: {request[:50]}... (mode: {trigger_mode.value})")
        
        start_time = datetime.utcnow()
        execution_id = execution_id or str(uuid.uuid4())
        
        # 0. Get Tenant ID and Create Execution Record
        with get_db_session() as db:
        with get_db_session() as db:
        try:
            workspace = db.query(Workspace).filter(Workspace.id == self.workspace_id).first()
            if workspace:
                tenant_id = workspace.tenant_id
            
            # Create persistent execution record
            execution = AgentExecution(
                id=execution_id,
                agent_id="atom_main",
                tenant_id=tenant_id or "default",
                status="running",
                input_summary=request[:200],
                triggered_by=trigger_mode.value,
                started_at=start_time
            )
            db.add(execution)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to create AgentExecution: {e}")
        finally:
            db.close()
        
        # 1. Access Memory for relevant context
        memory_context = await self.world_model.recall_experiences(
            agent=self._get_atom_registry(),
            current_task_description=request
        )
        
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

        
        # 3. Planning & Specialty Delegation Phase (NEW)
        # If the task is complex, we use a high-reasoning turn to plan subtasks
        is_complex = len(request) > 100 or any(kw in request.lower() for kw in ["analyze", "create", "sync", "report", "manage"])
        
        if is_complex and trigger_mode == AgentTriggerMode.MANUAL:
            plan_record = {
                "execution_id": execution_id,
                "step": 0,
                "step_type": "planning",
                "thought": "Decomposing complex request into specialized subtasks...",
                "action": {"tool": "planner", "params": {"query": request}},
                "timestamp": datetime.utcnow().isoformat()
            }
            if step_callback: await step_callback(plan_record)
            
            try:
                # Use orchestrator to identify specialized workflow or subtasks
                plan = await self.orchestrator.generate_dynamic_workflow(request)
                if plan and plan.get("nodes"):
                    # Record the plan as an observation
                    plan_summary = f"Identified plan with {len(plan['nodes'])} steps. Delegating to specialized components."
                    plan_record["output"] = plan_summary
                    execution_history += f"System Plan: {plan_summary}\n"
                    if step_callback: await step_callback(plan_record)
            except Exception as plan_error:
                logger.warning(f"Planning phase failed: {plan_error}")

        # 4. ReAct Loop with Pydantic Validation
        max_steps = 10
        steps = []
        final_answer = None
        status = "success"
        execution_history = ""
        
        for current_step in range(1, max_steps + 1):
            step_start = datetime.utcnow()
            # Generate next step using instructor for structured output
            react_step = await self._react_step(
                request=request,
                memory_context=memory_context,
                tool_descriptions=tool_descriptions,
                execution_history=execution_history,
                context=context
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
                "timestamp": datetime.utcnow().isoformat()
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
                step_record["duration_ms"] = (datetime.utcnow() - step_start).total_seconds() * 1000
                if step_callback: await step_callback(step_record)
            
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
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        with get_db_session() as db:
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
                          context: Dict) -> ReActStep:
        """
        Generate a single ReAct step with Pydantic validation.
        Uses instructor to ensure structured output.
        """
        system_prompt = f"""You are Atom, an intelligent business assistant.

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
- You can QUERY your Knowledge Graph for complex relationships.
- **IMPORTANT**: Use `save_business_fact` to store "Truths" (policies, rules). If you see a Fact in memory, VERIFY its citations (`verify_citation`) if it's critical.
- **IMPORTANT**: You have a large toolkit. If you don't see a tool you need, use `mcp_tool_search` to find it.

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

{self._get_communication_instruction(context)}
"""
        
        # Build rich memory context for the prompt
        experiences = memory_context.get('experiences', [])
        knowledge = memory_context.get('knowledge', [])
        formulas = memory_context.get('formulas', [])
        facts = memory_context.get('business_facts', [])
        
        memory_sections = []
        if experiences:
            exp_summaries = [f"- {getattr(e, 'input_summary', 'Task')[:80]}... → {getattr(e, 'outcome', 'completed')}" for e in experiences[:3]]
            memory_sections.append(f"PAST EXPERIENCES:\n" + "\n".join(exp_summaries))
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

        # Use BYOK's tenant-aware structured generation (respects BYOK vs Managed subscription)
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
        
        # Fallback: Use BYOK handler for raw response
        raw_response = await self.llm.generate_response(
            prompt=user_prompt,
            system_instruction=system_prompt,
            model_type="fast",
            temperature=0.2
        )
        
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
            with get_db_session() as db:
            try:
                gov = AgentGovernanceService(db)
                auth_check = gov.can_perform_action("atom_main", tool_name)
                
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
            
            # 2. Execute via MCP with governance check
            result = await self.mcp.call_tool(tool_name, args, context=context)
            return str(result)
            
        except Exception as e:
            return f"Tool error: {str(e)}"

    
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
            with get_db_session() as db:
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
            with get_db_session() as db:
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
            timestamp=datetime.utcnow()
        )
        await self.world_model.record_experience(experience)

        # 2. Update Governance Outcome
        success = result.get("status") == "success" or (result.get("final_output") is not None and "error" not in result.get("final_output").lower())
        with get_db_session() as db:
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
            with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.metadata_json:
                c_style = user.metadata_json.get("communication_style", {})
                if c_style.get("enable_personalization"):
                    guide = c_style.get("style_guide", "")
                    if guide:
                        return f"\nCOMMUNICATION STYLE:\n{guide}\nPlease carefully mimic this style in your final answer."
            return ""
        except Exception:
            return ""
        finally:
            db.close()


# ==================== TRIGGER HANDLERS ====================

async def handle_data_event_trigger(event_type: str, data: Dict[str, Any], 
                                    workspace_id: str = "default") -> Dict[str, Any]:
    """
    Handler for data-driven agent triggers.
    Called when new data arrives (webhook, ingestion, integration event, etc.)
    """
    # Build request from event
    request = f"Process {event_type} event with data: {str(data)[:100]}"
    
    # 1. Try SQS Dispatch (Async/Scalable)
    import os
    if os.getenv("SQS_QUEUE_URL"):
        try:
            from sqs_worker import dispatch_task
            task_id = dispatch_task(
                task_name="execute_agent",
                payload={
                    "request": request,
                    "context": {"event_type": event_type, "event_data": data},
                    "trigger_mode": AgentTriggerMode.DATA_EVENT.value,
                    "tenant_id": workspace_id
                }
            )
            logger.info(f"Data event trigger queued to SQS: {task_id}")
            return {"status": "queued", "task_id": task_id, "message": "Agent execution offloaded to background worker"}
        except Exception as e:
            logger.error(f"SQS dispatch failed for agent trigger: {e}. Falling back to inline execution.")
    
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
            from core.reasoning_chain import ReasoningStep, get_reasoning_tracker
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
                    timestamp=datetime.utcnow(),
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


# Singleton for easy access
_atom_instance: Optional[AtomMetaAgent] = None

def get_atom_agent(workspace_id: str = "default") -> AtomMetaAgent:
    global _atom_instance
    if _atom_instance is None or _atom_instance.workspace_id != workspace_id:
        _atom_instance = AtomMetaAgent(workspace_id)
    return _atom_instance
