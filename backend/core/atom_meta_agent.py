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
        
    async def execute(self, request: str, context: Dict[str, Any] = None, 
                     trigger_mode: AgentTriggerMode = AgentTriggerMode.MANUAL) -> Dict[str, Any]:
        """
        Main entry point for Atom. Analyzes request and decides best course of action.
        
        Args:
            request: Natural language request from user or event description
            context: Additional context (data payload, event metadata, etc.)
            trigger_mode: How this execution was triggered
        """
        context = context or {}
        logger.info(f"Atom executing request: {request[:50]}... (mode: {trigger_mode.value})")
        
        # 1. Access Memory for relevant context
        memory_context = await self.world_model.recall_experiences(
            agent=self._get_atom_registry(),
            current_task_description=request
        )
        
        # 2. Analyze request and determine action
        action_plan = await self._analyze_and_plan(request, context, memory_context)
        
        # 3. Execute the plan
        result = await self._execute_plan(action_plan, context, trigger_mode)
        
        # 4. Record experience
        await self._record_execution(request, result, trigger_mode)
        
        return result
    
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
            class_name="GenericAgent"
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
    
    async def _analyze_and_plan(self, request: str, context: Dict, 
                                memory_context: Dict) -> Dict[str, Any]:
        """
        Analyze the request and create an action plan.
        Uses AI reasoning to determine best approach.
        """
        # Simple heuristic planning for now
        # In production, this would use AI to reason about the best approach
        
        plan = {
            "actions": [],
            "requires_agent": False,
            "agent_template": None,
            "workflow_id": None
        }
        
        request_lower = request.lower()
        
        # Detect if we need a specialty agent
        if any(kw in request_lower for kw in ["finance", "expense", "budget", "reconcile", "payroll"]):
            plan["requires_agent"] = True
            plan["agent_template"] = "finance_analyst"
            plan["actions"].append({"type": "spawn_agent", "template": "finance_analyst"})
            
        elif any(kw in request_lower for kw in ["sales", "lead", "crm", "opportunity", "pipeline"]):
            plan["requires_agent"] = True
            plan["agent_template"] = "sales_assistant"
            plan["actions"].append({"type": "spawn_agent", "template": "sales_assistant"})
            
        elif any(kw in request_lower for kw in ["inventory", "order", "shipping", "vendor"]):
            plan["requires_agent"] = True
            plan["agent_template"] = "ops_coordinator"
            plan["actions"].append({"type": "spawn_agent", "template": "ops_coordinator"})
            
        elif any(kw in request_lower for kw in ["hr", "onboarding", "leave", "policy"]):
            plan["requires_agent"] = True
            plan["agent_template"] = "hr_assistant"
            plan["actions"].append({"type": "spawn_agent", "template": "hr_assistant"})
            
        elif any(kw in request_lower for kw in ["campaign", "marketing", "audience", "content"]):
            plan["requires_agent"] = True
            plan["agent_template"] = "marketing_analyst"
            plan["actions"].append({"type": "spawn_agent", "template": "marketing_analyst"})
        
        # Check for workflow triggers
        if "workflow" in request_lower or "automation" in request_lower:
            plan["actions"].append({"type": "check_workflows"})
        
        # Always add memory context injection
        if memory_context.get("experiences") or memory_context.get("knowledge"):
            plan["memory_augmented"] = True
        
        return plan
    
    async def _execute_plan(self, plan: Dict[str, Any], context: Dict, 
                           trigger_mode: AgentTriggerMode) -> Dict[str, Any]:
        """Execute the action plan"""
        results = {
            "trigger_mode": trigger_mode.value,
            "actions_executed": [],
            "final_output": None
        }
        
        for action in plan.get("actions", []):
            action_type = action.get("type")
            
            if action_type == "spawn_agent":
                template = action.get("template")
                agent = await self.spawn_agent(template, persist=False)
                results["actions_executed"].append({
                    "action": "spawn_agent",
                    "agent_id": agent.id,
                    "agent_name": agent.name
                })
                results["spawned_agent"] = agent.id
                
            elif action_type == "trigger_workflow":
                wf_id = action.get("workflow_id")
                wf_result = await self.trigger_workflow(wf_id, context)
                results["actions_executed"].append({
                    "action": "trigger_workflow",
                    "workflow_id": wf_id,
                    "result": wf_result
                })
        
        # If we spawned an agent, execute it
        if results.get("spawned_agent"):
            agent_id = results["spawned_agent"]
            # Execute the agent's logic
            results["final_output"] = f"Agent {agent_id} executed task. (Simulated output)"
        else:
            results["final_output"] = "Atom processed request directly."
        
        return results
    
    async def _record_execution(self, request: str, result: Dict, 
                               trigger_mode: AgentTriggerMode):
        """Record execution to World Model for future learning"""
        experience = AgentExperience(
            id=str(uuid.uuid4()),
            agent_id="atom_main",
            task_type="meta_orchestration",
            input_summary=request[:200],
            outcome="Success" if result.get("final_output") else "Partial",
            learnings=f"Trigger: {trigger_mode.value}. Actions: {len(result.get('actions_executed', []))}",
            agent_role="Meta",
            specialty=None,
            timestamp=datetime.utcnow()
        )
        await self.world_model.record_experience(experience)


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
