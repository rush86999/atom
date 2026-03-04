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

from core.llm_router import LLMRouter
from core.agents.skill_creation_agent import SkillCreationAgent

logger = logging.getLogger(__name__)

class QueenAgent:
    """
    The Queen Agent is responsible for high-level "outcome-driven" design.
    It does not execute tasks itself; it architectures the agents and skills
    needed to achieve the user's objective.
    """

    def __init__(self, db: Session, llm_router: LLMRouter):
        self.db = db
        self.llm = llm_router
        self.skill_creator = SkillCreationAgent(db, llm_router)

    async def generate_blueprint(self, goal: str, tenant_id: str = "default") -> Dict[str, Any]:
        """
        Generate a structured blueprint from a natural language goal.
        """
        logger.info(f"Queen: Designing architecture for goal: {goal}")

        prompt = f"""You are the Queen Agent, a master software architect and agent orchestrator.
Analyze the following goal and design a high-level agent architecture (blueprint) to achieve it.

GOAL: {goal}

Generate a JSON blueprint with the following structure:
{{
  "architecture_name": "string",
  "description": "string",
  "nodes": [
    {{
      "id": "node_id",
      "type": "skill|agent",
      "name": "string",
      "capability_required": "string",
      "dependencies": ["node_id_1", "node_id_2"]
    }}
  ],
  "required_integrations": ["string"],
  "missing_capabilities": [
    {{
      "name": "string",
      "description": "string",
      "suggested_api_docs_url": "string (optional)"
    }}
  ]
}}

Guidelines:
1. Identify existing capabilities (e.g., Browser, Terminal, Email, CRM).
2. If a capability is missing, list it in 'missing_capabilities'.
3. Define the flow of data and dependencies between nodes.

Return ONLY the JSON object."""

        try:
            response = await self.llm.call(
                tenant_id=tenant_id,
                messages=[
                    {"role": "system", "content": "You are a master AI architect. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.get("content", "")
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

    async def realize_blueprint(self, blueprint: Dict[str, Any], tenant_id: str, user_id: str):
        """
        Take a blueprint and actually create/configure the agents and skills.
        (Future implementation: wiring everything up in the DB)
        """
        logger.info(f"Queen: Realizing blueprint {blueprint.get('blueprint_id')}")
        # This will involve calling SkillCreationAgent for each missing capability
        pass
