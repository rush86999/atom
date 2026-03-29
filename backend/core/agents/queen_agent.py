"""
Queen Agent — Goal-Driven Architecture Generation

Inspired by the Aden Hive "Queen" agent, this module implements a high-level
orchestrator that translates natural language goals into a structured "Agent Blueprint".

The blueprint includes:
1. Required Skills (existing or to-be-created)
2. Dependency Graph (execution order)
3. Guardrails & Metadata
"""

import logging
import json
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from core.llm_service import LLMService
from core.agents.skill_creation_agent import SkillCreationAgent

logger = logging.getLogger(__name__)

class QueenAgent:
    """
    The Queen Agent is responsible for high-level "outcome-driven" design.
    It does not execute tasks itself; it architectures the agents and skills
    needed to achieve the user's objective.
    """

    def __init__(self, db: Session, llm: LLMService, workspace_id: str = "default", tenant_id: str = "default"):
        self.db = db
        self.llm = llm
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        # SkillCreationAgent should also be modernized in a future step if needed
        from core.agents.skill_creation_agent import SkillCreationAgent
        self.skill_creator = SkillCreationAgent(db, llm)

    async def generate_blueprint(self, goal: str, tenant_id: str = "default", execution_mode: str = "one-off") -> Dict[str, Any]:
        """
        Generate a structured blueprint from a natural language goal.
        """
        logger.info(f"Queen: Designing architecture for goal: {goal} (Mode: {execution_mode})")

        mode_instruction = ""
        if execution_mode == "recurring_automation":
            mode_instruction = "\nIMPORTANT: This is a RECURRING AUTOMATION. Ensure the architecture starts with a TRIGGER node (Event, Schedule, or Condition) that kicks off the sequence."
        else:
            mode_instruction = "\nIMPORTANT: This is a ONE-OFF TASK. The architecture should focus on a linear or complex reasoning path to achieve the goal immediately."

        prompt = f"""You are the Queen Agent, a master software architect and agent orchestrator.
Analyze the following goal and design a high-level agent architecture (blueprint) to achieve it.
{mode_instruction}

GOAL: {goal}

Generate a JSON blueprint with the following structure:
{{
  "architecture_name": "string",
  "description": "string",
  "execution_mode": "{execution_mode}",
  "nodes": [
    {{
      "id": "node_id",
      "type": "trigger|skill|agent|entity",
      "name": "string",
      "capability_required": "string",
      "dependencies": ["node_id_1", "node_id_2"],
      "metadata": {{"trigger_event": "string", "schedule": "string", "condition": "string"}} (optional)
    }}
  ],
  "required_integrations": ["string"],
  "missing_capabilities": [
    {{
      "name": "string",
      "description": "string"
    }}
  ]
}}

Guidelines:
1. For AUTOMATION, node 0 MUST be a trigger (temporal or conditional).
2. Entity nodes represent data objects or persistent state in the Knowledge Graph.
3. Identify existing capabilities (e.g., Browser, Terminal, Email, CRM).
4. If a capability is missing, list it in 'missing_capabilities'.
5. Define the flow of data and dependencies between nodes.

Return ONLY the JSON object."""

        try:
            content = await self.llm.generate_response(
                prompt=prompt,
                system_prompt="You are a master AI architect. Output only valid JSON.",
                tenant_id=tenant_id
            )
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            blueprint = json.loads(content)
            blueprint["blueprint_id"] = str(uuid.uuid4())
            
            # Handle missing capabilities by suggesting skill creation
            if blueprint.get("missing_capabilities"):
                logger.info(f"Queen: Identified {len(blueprint['missing_capabilities'])} missing capabilities")
                # We can proactively link these to SkillCreationAgent in future steps
            
            return blueprint
        except Exception as e:
            logger.error(f"Queen: Failed to generate blueprint: {e}")
            return self._generate_fallback_blueprint(goal)

    def generate_mermaid(self, blueprint: Dict[str, Any], statuses: Optional[Dict[str, str]] = None) -> str:
        """
        Generate a Mermaid diagram string from a blueprint.
        Status colors: 
        - completed: green (#e8f5e9)
        - in_progress: orange (#fff3e0)
        - failed: red (#ffebee)
        - pending: white/default
        """
        statuses = statuses or {}
        lines = ["graph TD"]
        
        # Style definitions
        lines.append("    classDef completed fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;")
        lines.append("    classDef in_progress fill:#fff3e0,stroke:#e65100,stroke-width:2px,stroke-dasharray: 5 5;")
        lines.append("    classDef failed fill:#ffebee,stroke:#b71c1c,stroke-width:2px;")
        lines.append("    classDef pending fill:#fafafa,stroke:#9e9e9e,stroke-width:1px;")

        nodes = blueprint.get("nodes", [])
        for node in nodes:
            node_id = node["id"]
            node_name = node["name"]
            node_type = node.get("type", "agent").upper()
            
            # Label
            label = f"{node_name}\\n({node_type})"
            lines.append(f"    {node_id}[\"{label}\"]")
            
            # Apply class based on status
            status = statuses.get(node_id, "pending")
            lines.append(f"    class {node_id} {status}")
            
            # Dependencies
            for dep in node.get("dependencies", []):
                lines.append(f"    {dep} --> {node_id}")
                
        return "\n".join(lines)

    def _generate_fallback_blueprint(self, goal: str) -> Dict[str, Any]:
        """Simple fallback if LLM generation fails."""
        return {
            "architecture_name": "Basic Sequential Architecture",
            "description": f"Fallback architecture for: {goal}",
            "nodes": [
                {
                    "id": "step_1",
                    "type": "agent",
                    "name": "General Agent",
                    "capability_required": "general_reasoning",
                    "dependencies": []
                }
            ],
            "required_integrations": [],
            "missing_capabilities": [],
            "blueprint_id": str(uuid.uuid4()),
            "status": "fallback"
        }

    async def realize_blueprint(self, blueprint: Dict[str, Any], tenant_id: str = "default") -> str:
        """
        Realize a generated blueprint into the persistent Workflow Engine.
        Translates Queen node types back to executable WorkflowSteps.
        """
        try:
            from advanced_workflow_orchestrator import (
                get_orchestrator, WorkflowDefinition, WorkflowStep, WorkflowStepType
            )
        except ImportError:
            logger.error("AdvancedWorkflowOrchestrator not available for realization")
            return "orchestrator_not_available"

        orchestrator = get_orchestrator()
        
        # 1. Generate IDs and Metadata
        workflow_id = f"ai_wf_{uuid.uuid4().hex[:8]}"
        name = blueprint.get("architecture_name", "AI Generated Workflow")
        description = blueprint.get("description", "Automatically generated by Queen Agent")
        
        # 2. Map Nodes to WorkflowSteps
        steps = []
        
        # Build Next Steps Adjacency List from Dependencies
        next_steps_map = {} # node_id -> list of next_node_id
        for node in blueprint.get("nodes", []):
            node_id = node["id"]
            if node_id not in next_steps_map:
                next_steps_map[node_id] = []
            
            for dep in node.get("dependencies", []):
                if dep not in next_steps_map:
                    next_steps_map[dep] = []
                next_steps_map[dep].append(node_id)

        start_step = None
        triggers = []

        for node in blueprint.get("nodes", []):
            node_type = node["type"]
            node_id = node["id"]
            
            # Map type
            if node_type == "trigger":
                step_type = WorkflowStepType.NLU_ANALYSIS
                triggers.append(node.get("metadata", {}).get("trigger_event", "manual"))
                if not start_step:
                    start_step = node_id
            elif node_type == "agent":
                step_type = WorkflowStepType.BUSINESS_AGENT_EXECUTION
            elif node_type == "entity":
                step_type = WorkflowStepType.KNOWLEDGE_UPDATE
            else:
                step_type = WorkflowStepType.UNIVERSAL_INTEGRATION

            new_step = WorkflowStep(
                step_id=node_id,
                step_type=step_type,
                description=node.get("name", "Process step"),
                parameters=node.get("metadata", {}),
                next_steps=next_steps_map.get(node_id, [])
            )
            steps.append(new_step)
            
            # If no trigger is defined, the first non-trigger node with no dependencies is start
            if not start_step and not node.get("dependencies"):
                start_step = node_id

        if not start_step and steps:
            start_step = steps[0].step_id

        # 3. Create Definition
        wf_def = WorkflowDefinition(
            workflow_id=workflow_id,
            name=name,
            description=description,
            steps=steps,
            start_step=start_step,
            triggers=triggers
        )

        # 4. Register
        orchestrator.register_workflow(wf_def)
        logger.info(f"Queen: Realized blueprint into workflow {workflow_id}")
        
        return workflow_id
