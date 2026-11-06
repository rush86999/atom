"""
Queen Agent — Goal-Driven Architecture Generation

Inspired by the Aden Hive "Queen" agent, this module implements a high-level
orchestrator that translates natural language goals into a structured "Agent Blueprint".

The blueprint includes:
1. Required Skills (existing or to-be-created)
2. Dependency Graph (execution order)
3. Guardrails & Metadata
"""

import asyncio
import logging
import json
import os
import uuid
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, ValidationError
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

    async def generate_blueprint(self, goal: str, tenant_id: str = "default", execution_mode: str = "one-off", user_id: Optional[str] = None) -> Dict[str, Any]:
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
            content = await self.llm.generate(
                prompt=prompt,
                system_instruction="You are a master AI architect. Output only valid JSON.",
                tenant_id=tenant_id,
                user_id=user_id
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

    def _workflow_blueprint_prompt(
        self, goal: str, execution_mode: str,
    ) -> str:
        mode_rules = (
            "This is a recurring automation. It MUST start with exactly one "
            "trigger node whose metadata declares trigger_event, schedule or "
            "condition."
            if execution_mode == "recurring_automation" else
            "This is a one-off workflow. It must have exactly one start node; "
            "a trigger is optional and, if present, must be the start."
        )
        return f"""You are the workflow architect. Design a reusable workflow
blueprint for the user's plain-language request. You design only; you never
execute the workflow, activate a trigger, grant authority or author executable
plumbing.

REQUEST:
{goal}

MODE RULES:
{mode_rules}

Return ONLY a JSON object with this shape:
{{
  "architecture_name": "short name",
  "description": "what the workflow does",
  "execution_mode": "{execution_mode}",
  "nodes": [
    {{
      "id": "stable_snake_or_kebab_id",
      "type": "trigger|skill|agent|entity",
      "name": "human-readable step name",
      "capability_required": "capability or null",
      "dependencies": ["other_node_id"],
      "metadata": {{"trigger_event": "...", "schedule": "...", "condition": "..."}},
      "action": {{"kind": "read|compute|notify|write|approval", "service": "optional", "action": "optional"}}
    }}
  ],
  "required_integrations": ["..."],
  "missing_capabilities": [{{"name": "...", "description": "..."}}]
}}

Rules:
- Node ids are unique and stable. Dependencies must reference existing nodes.
- The graph must be acyclic and connected from one start node.
- Mark every step that mutates governed state or sends an external effect with
  action.kind "write" or "notify". The server inserts the required human
  approval checkpoint before it; do not omit the action intent.
- Use "read" or "compute" for analysis-only steps. Entity nodes represent
  persistent state; use "read" for a lookup and "write" for a change.
- Do not invent capabilities. If a capability is unavailable, list it in
  missing_capabilities instead of mapping it to an integration.
- Do not include expected outputs, credentials, executable code, SQL, tool
  arguments or provider names.
"""

    async def generate_workflow_blueprint(
        self,
        goal: str,
        *,
        execution_mode: str = "one_off",
        workspace_id: str = "default",
        tenant_id: str = "default",
        deadline_seconds: float = 120.0,
    ) -> Dict[str, Any]:
        """Generate a validated-shape blueprint, never a fallback workflow.

        The model owns the business design. This method only asks for the
        structured draft; validation, HITL insertion, persistence and route
        scope are server-owned. Any model/protocol failure is a typed
        ``BlueprintGenerationError`` and creates no workflow.
        """
        from core.agents.workflow_blueprint import (
            BlueprintGenerationError,
            WorkflowBlueprintDraft,
        )

        if not str(goal or "").strip():
            raise BlueprintGenerationError(
                "workflow_request_empty",
                "a workflow request is required", 422)
        prompt = self._workflow_blueprint_prompt(goal, execution_mode)
        try:
            result = await asyncio.wait_for(
                self.llm.generate_structured_response(
                    prompt=prompt,
                    response_model=WorkflowBlueprintDraft,
                    system_instruction=(
                        "You are a workflow architect. Design only. "
                        "Return JSON only."),
                    task_type="planning",
                    capability_profile="workflow_blueprint",
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    temperature=0.0,
                    max_tokens=4096,
                    # The blueprint schema is a large nested object. The
                    # existing structured transport supports an explicit JSON
                    # mode; it is a protocol choice, not a provider branch.
                    output_mode="json",
                ),
                timeout=max(1.0, float(deadline_seconds or 120.0)),
            )
        except asyncio.TimeoutError as exc:
            raise BlueprintGenerationError(
                "workflow_blueprint_timeout",
                "the workflow designer timed out; no workflow was created",
                504) from exc
        except ValidationError as exc:
            raise BlueprintGenerationError(
                "workflow_blueprint_invalid",
                "the workflow designer returned an invalid blueprint",
                422, details=[str(exc)]) from exc
        except Exception as exc:  # noqa: BLE001 — typed safe boundary
            try:
                from core.llm.byok_handler import (
                    NoSuitableConfiguredModelError,
                )
            except Exception:  # noqa: BLE001
                NoSuitableConfiguredModelError = ()  # type: ignore
            if NoSuitableConfiguredModelError and isinstance(
                    exc, NoSuitableConfiguredModelError):
                raise BlueprintGenerationError(
                    "workflow_blueprint_no_suitable_route",
                    "no configured route can carry the workflow designer "
                    "workload; no workflow was created",
                    503) from exc
            try:
                from core.llm_service import LLMScopeUnresolvedError
            except Exception:  # noqa: BLE001
                LLMScopeUnresolvedError = ()  # type: ignore
            if LLMScopeUnresolvedError and isinstance(
                    exc, LLMScopeUnresolvedError):
                raise BlueprintGenerationError(
                    "workflow_blueprint_scope_unresolved",
                    "the workflow designer could not resolve the authorized "
                    "scope; no workflow was created",
                    403) from exc
            logger.warning(
                "Queen: structured workflow blueprint generation failed: %s",
                exc)
            raise BlueprintGenerationError(
                "workflow_blueprint_unavailable",
                "the workflow designer is unavailable; no workflow was "
                "created",
                503) from exc
        if result is None:
            raise BlueprintGenerationError(
                "workflow_blueprint_no_result",
                "the workflow designer returned no blueprint; no workflow "
                "was created",
                503)
        try:
            if isinstance(result, BaseModel):
                draft = WorkflowBlueprintDraft.model_validate(
                    result.model_dump())
            else:
                draft = WorkflowBlueprintDraft.model_validate(result)
        except ValidationError as exc:
            raise BlueprintGenerationError(
                "workflow_blueprint_invalid",
                "the workflow designer returned an invalid blueprint",
                422, details=[str(exc)]) from exc
        return draft.model_dump()

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
            node_id = node.get("id")
            node_name = node.get("name")
            if not node_id or not node_name:
                continue
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
            node_id = node.get("id")
            if not node_id:
                continue
            if node_id not in next_steps_map:
                next_steps_map[node_id] = []

            for dep in node.get("dependencies", []):
                if dep not in next_steps_map:
                    next_steps_map[dep] = []
                next_steps_map[dep].append(node_id)

        start_step = None
        triggers = []

        for node in blueprint.get("nodes", []):
            node_id = node.get("id")
            if not node_id:
                continue
            node_type = node.get("type", "agent")
            
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
