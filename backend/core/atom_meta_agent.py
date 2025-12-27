"""
Atom Meta-Agent - Central Orchestrator for ATOM Platform
The main intelligent agent that can spawn specialty agents and access all platform features.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from core.models import AgentRegistry, AgentStatus, User
from core.database import SessionLocal
from core.agent_world_model import WorldModelService, AgentExperience
from core.agent_governance_service import AgentGovernanceService
from advanced_workflow_orchestrator import AdvancedWorkflowOrchestrator
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
            "capabilities": ["reconciliation", "expense_analysis", "budget_tracking"],
            "default_params": {"focus": "cost_optimization"}
        },
        "sales_assistant": {
            "name": "Sales Assistant", 
            "category": "Sales",
            "description": "Manages leads, tracks opportunities, generates outreach",
            "capabilities": ["lead_scoring", "crm_sync", "email_outreach"],
            "default_params": {"pipeline": "default"}
        },
        "ops_coordinator": {
            "name": "Operations Coordinator",
            "category": "Operations",
            "description": "Manages inventory, logistics, vendor relationships",
            "capabilities": ["inventory_check", "order_tracking", "vendor_management"],
            "default_params": {"region": "all"}
        },
        "hr_assistant": {
            "name": "HR Assistant",
            "category": "HR",
            "description": "Handles onboarding, policy queries, leave management",
            "capabilities": ["onboarding", "policy_lookup", "leave_tracking"],
            "default_params": {}
        },
        "marketing_analyst": {
            "name": "Marketing Analyst",
            "category": "Marketing",
            "description": "Analyzes campaigns, tracks metrics, generates insights",
            "capabilities": ["campaign_analysis", "audience_insights", "content_suggestions"],
            "default_params": {"channels": ["email", "social"]}
        }
    }



from core.llm.byok_handler import BYOKHandler
from core.agent_utils import parse_react_response
import json

class AtomMetaAgent:
    """
    The central Atom agent that orchestrates all platform capabilities.
    Can spawn specialty agents, access memory, trigger workflows, and call integrations.
    """
    
    def __init__(self, workspace_id: str = "default", user: Optional[User] = None):
        self.workspace_id = workspace_id
        self.user = user
        self.world_model = WorldModelService(workspace_id)
        self.orchestrator = AdvancedWorkflowOrchestrator()
        self._spawned_agents: Dict[str, AgentRegistry] = {}
        self.mcp = mcp_service  # MCP access for web search and web access
        self.llm = BYOKHandler(workspace_id=workspace_id)
        
    async def execute(self, request: str, context: Dict[str, Any] = None, 
                     trigger_mode: AgentTriggerMode = AgentTriggerMode.MANUAL) -> Dict[str, Any]:
        """
        Main entry point for Atom. Uses ReAct loop to solve the request.
        """
        context = context or {}
        if "original_request" not in context:
            context["original_request"] = request
            
        logger.info(f"Atom executing request: {request[:50]}... (mode: {trigger_mode.value})")
        
        # 1. Access Memory for relevant context
        memory_context = await self.world_model.recall_experiences(
            agent=self._get_atom_registry(),
            current_task_description=request
        )
        
        # 2. ReAct Loop
        max_steps = 10 # Meta agent is complex, give it more steps
        steps = []
        final_answer = None
        status = "success"
        
        current_step = 0
        execution_history = ""
        
        try:
            while current_step < max_steps:
                current_step += 1
                
                # Plan/Think
                llm_response = await self._step_think(request, memory_context, execution_history, context)
                
                # Parse
                thought, action, answer = parse_react_response(llm_response)
                
                step_record = {
                    "step": current_step,
                    "thought": thought,
                    "action": action,
                    "output": None,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                if thought:
                    execution_history += f"Thought: {thought}\n"
                
                if answer:
                    step_record["final_answer"] = answer
                    final_answer = answer
                    steps.append(step_record)
                    execution_history += f"Final Answer: {answer}\n"
                    
                    # Update status for record_outcome
                    status = "success"
                    break
                
                if action:
                    execution_history += f"Action: {json.dumps(action)}\n"
                    
                    tool_name = action.get("tool")
                    tool_args = action.get("params", {})
                    
                    observation = await self._step_act(tool_name, tool_args, context)
                    
                    step_record["output"] = observation
                    execution_history += f"Observation: {str(observation)}\n"
                    
                else:
                    if current_step == max_steps:
                        final_answer = llm_response # Forced answer
                        status = "timeout_forced_answer"
                        
                steps.append(step_record)
                
            if not final_answer:
                final_answer = "Maximum steps reached without final answer."
                status = "max_steps_exceeded"
                
        except Exception as e:
            logger.error(f"Atom execution failed: {e}")
            final_answer = f"Error during execution: {str(e)}"
            status = "failed"
            
        # 3. Record Execution
        result_payload = {
            "final_output": final_answer,
            "actions_executed": steps,
            "trigger_mode": trigger_mode.value
        }
        
        await self._record_execution(request, result_payload, trigger_mode)
        
        return result_payload

    async def _step_think(self, request: str, memory: Dict, history: str, context: Dict) -> str:
        """Generating the next thought/action plan for Meta Agent"""
        
        system_prompt = f"""
You are Atom, the Advanced Central Orchestrator for this platform.
Your goal is to solve the user's request by orchestrating Specialty Agents, Workflows, and Integrations.

CORE ORCHESTRATION TOOLS:
1. spawn_agent
   - Description: Spawn a specialty agent to handle a domain-specific task.
   - Params: {{"template": "finance_analyst" | "sales_assistant" | "ops_coordinator" | "hr_assistant" | "marketing_analyst", "task": "specific instructions"}}
   
2. call_integration
   - Description: Call an external service integration directly.
   - Params: {{"service": "salesforce" | "slack" | "hubspot", "action": "action_name", "params": {{...}}}}
   
3. trigger_workflow
   - Description: Trigger a predefined workflow.
   - Params: {{"workflow_id": "id", "input": {{...}}}}

4. query_memory
   - Description: Search the World Model for information.
   - Params: {{"query": "search query"}}

FORMAT INSTRUCTIONS:
Thought: Describe your reasoning.
Action: {{"tool": "tool_name", "params": {{...}}}}
Observation: [Result provided by system]
...
Final Answer: The final response to the user.

AVAILABLE PLATFORM TOOLS (via call_integration or direct actions):
{json.dumps(await self.mcp.get_all_tools(), indent=2)}

Context:
"""
        context_str = f"User Context: {context.get('user_id', 'unknown')}\n"
        
        # Enriched Hybrid Memory Display
        memory_display = f"""
- Past Experiences: {json.dumps(memory.get('experiences', [])[:2], indent=2)}
- Knowledge Graph: {memory.get('knowledge_graph', 'N/A')}
- Documents: {json.dumps([k.get('text', '')[:200] for k in memory.get('knowledge', [])], indent=2)}
- Formulas: {json.dumps(memory.get('formulas', []), indent=2)}
"""

        user_prompt = f"""
{context_str}
Memory Context:
{memory_display}

Current Request: {request}

History:
{history}

Next Step:
"""
        return await self.llm.generate_response(
            prompt=user_prompt,
            system_instruction=system_prompt,
            model_type="fast",
            temperature=0.2
        )

    async def _step_act(self, tool_name: str, args: Dict, context: Dict) -> Any:
        """Execute Meta Tools with Governance Check"""
        try:
            # 1. Governance Maturity Check
            db = SessionLocal()
            try:
                gov = AgentGovernanceService(db)
                # Atom Agent check
                auth_check = gov.can_perform_action("atom_main", tool_name)
                if not auth_check["allowed"]:
                    return f"Governance Error: {auth_check['reason']}"
            finally:
                db.close()

            # 2. Tool Execution
            if tool_name == "spawn_agent":
                template = args.get("template")
                task = args.get("task", context.get("original_request"))
                
                agent = await self.spawn_agent(template, persist=False)
                
                # Execute the spawned agent immediately on the sub-task
                from core.generic_agent import GenericAgent
                runner = GenericAgent(agent, self.workspace_id)
                result = await runner.execute(task, context)
                
                return f"Agent {agent.name} Result: {result.get('output')}"
                
            elif tool_name == "call_integration":
                return await self.call_integration(args.get("service"), args.get("action"), args.get("params", {}))
                
            elif tool_name == "trigger_workflow":
                return await self.trigger_workflow(args.get("workflow_id"), args.get("input", {}))
                
            elif tool_name == "query_memory":
                return await self.query_memory(args.get("query"))
                
            else:
                return f"Error: Tool '{tool_name}' not found."
                
        except Exception as e:
            return f"Tool Execution Error: {str(e)}"

    
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
    
    async def trigger_workflow(self, workflow_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a workflow through the orchestrator"""
        context = await self.orchestrator.execute_workflow(
            workflow_id, 
            input_data,
            execution_context={"user_id": self.user.id if self.user else "atom_system"}
        )
        return {
            "workflow_id": workflow_id,
            "execution_id": context.workflow_id,
            "status": context.status.value,
            "results": context.results
        }
    
    async def call_integration(self, service: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call any integration service through Atom.
        Leverages the UniversalIntegrationService.
        """
        try:
            from integrations.universal_integration_service import UniversalIntegrationService
            
            integration = UniversalIntegrationService(self.workspace_id)
            result = await integration.execute(service, action, params)
            return {"status": "success", "service": service, "result": result}
        except Exception as e:
            logger.error(f"Integration call failed: {e}")
            return {"status": "failed", "service": service, "error": str(e)}
    
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
        db = SessionLocal()
        try:
            gov = AgentGovernanceService(db)
            await gov.record_outcome("atom_main", success=success)
        except Exception as ge:
            logger.error(f"Failed to record Atom governance outcome: {ge}")
        finally:
            db.close()


# ==================== TRIGGER HANDLERS ====================

async def handle_data_event_trigger(event_type: str, data: Dict[str, Any], 
                                    workspace_id: str = "default") -> Dict[str, Any]:
    """
    Handler for data-driven agent triggers.
    Called when new data arrives (webhook, ingestion, integration event, etc.)
    """
    atom = AtomMetaAgent(workspace_id)
    
    # Build request from event
    request = f"Process {event_type} event with data: {str(data)[:100]}"
    
    result = await atom.execute(
        request=request,
        context={"event_type": event_type, "event_data": data},
        trigger_mode=AgentTriggerMode.DATA_EVENT
    )
    
    return result


async def handle_manual_trigger(request: str, user: User, 
                               workspace_id: str = "default") -> Dict[str, Any]:
    """
    Handler for manual/user-initiated agent triggers.
    Called from Chat or API.
    """
    atom = AtomMetaAgent(workspace_id, user)
    
    result = await atom.execute(
        request=request,
        context={"user_id": user.id, "user_email": user.email},
        trigger_mode=AgentTriggerMode.MANUAL
    )
    
    return result


# Singleton for easy access
_atom_instance: Optional[AtomMetaAgent] = None

def get_atom_agent(workspace_id: str = "default") -> AtomMetaAgent:
    global _atom_instance
    if _atom_instance is None or _atom_instance.workspace_id != workspace_id:
        _atom_instance = AtomMetaAgent(workspace_id)
    return _atom_instance
