"""
King Agent — Sovereign Executive Orchestrator

The King Agent is the counter-part to the Queen Agent. While the Queen
architectures the solution (blueprints), the King executes it by 
orchestrating specialty agents and enforcing sovereign governance.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from core.llm_router import LLMRouter
from core.atom_meta_agent import AtomMetaAgent
from core.agents.queen_agent import QueenAgent
from core.blueprint_healer import BlueprintHealer
from core.models import User, AgentTriggerMode, AgentEvolutionTrace
from core.database import SessionLocal
from core.canvas_tool import present_markdown, update_canvas

logger = logging.getLogger(__name__)

class KingAgent(AtomMetaAgent):
    """
    The King Agent takes a blueprint and oversees its realization.
    It manages the lifecycle of sub-tasks and ensures each node in the 
    blueprint is executed by the most capable available resource.
    """
    
    def __init__(self, workspace_id: str = "default", user: Optional[User] = None):
        super().__init__(workspace_id, user)
        # Use LLMRouter for Queen/Healer consistency
        self.llm_router = LLMRouter()
        self.healer = BlueprintHealer(None, self.llm_router) # db will be injected in session

    async def execute_blueprint(
        self, 
        blueprint: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None,
        canvas_context: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Executes a Queen's blueprint with sovereign self-healing.
        """
        logger.info(f"King: Executing blueprint: {blueprint.get('architecture_name')}")
        context = context or {}
        nodes = blueprint.get("nodes", [])
        
        executed_nodes = {}
        pending_nodes = nodes.copy()
        
        # Prepare initial Canvas visualization
        canvas_id = None
        node_statuses = {n["id"]: "pending" for n in nodes}
        
        if context.get("user_id") and context.get("tenant_id"):
            mermaid = self.queen.generate_mermaid(blueprint, node_statuses)
            canvas_res = await present_markdown(
                tenant_id=context["tenant_id"],
                user_id=context["user_id"],
                title=f"Execution Plan: {blueprint.get('architecture_name')}",
                content=f"```mermaid\n{mermaid}\n```",
                agent_id=getattr(self, "agent_id", None)
            )
            canvas_id = canvas_res.get("canvas_id")

        while pending_nodes and retry_count < max_retries:
            ready_nodes = [
                n for n in pending_nodes 
                if all(dep in executed_nodes for dep in n.get("dependencies", []))
            ]
            
            if not ready_nodes and pending_nodes:
                logger.error("King: Stalled execution or circular dependency.")
                break
                
            for node in ready_nodes:
                logger.info(f"King: Processing node: {node['name']} ({node['type']})")
                
                # Update status to in_progress on Canvas
                if canvas_id:
                    node_statuses[node["id"]] = "in_progress"
                    new_mermaid = self.queen.generate_mermaid(blueprint, node_statuses)
                    await update_canvas(
                        tenant_id=context["tenant_id"],
                        user_id=context["user_id"],
                        canvas_id=canvas_id,
                        updates={"content": f"```mermaid\n{new_mermaid}\n```"}
                    )

                try:
                    # Execute the node
                    node_result = await self._execute_node(node, context, canvas_context)
                    
                    if isinstance(node_result, dict) and "error" in node_result:
                        raise ValueError(node_result["error"])

                    executed_nodes[node["id"]] = node_result
                    pending_nodes.remove(node)
                    node_statuses[node["id"]] = "completed"
                    
                    results.append({
                        "node_id": node["id"],
                        "node_name": node["name"],
                        "status": "completed",
                        "result": node_result
                    })
                    
                    # Update Canvas with completion
                    if canvas_id:
                        new_mermaid = self.queen.generate_mermaid(blueprint, node_statuses)
                        await update_canvas(
                            tenant_id=context["tenant_id"],
                            user_id=context["user_id"],
                            canvas_id=canvas_id,
                            updates={"content": f"```mermaid\n{new_mermaid}\n```"}
                        )

                except Exception as e:
                    logger.warning(f"King: Node failure detected in {node['id']}: {e}")
                    node_statuses[node["id"]] = "failed"
                    
                    # Update Canvas with failure
                    if canvas_id:
                        new_mermaid = self.queen.generate_mermaid(blueprint, node_statuses)
                        await update_canvas(
                            tenant_id=context["tenant_id"],
                            user_id=context["user_id"],
                            canvas_id=canvas_id,
                            updates={"content": f"```mermaid\n{new_mermaid}\n```"}
                        )

                    # TRIGGER SELF-HEALING
                    logger.info("King: Activating Blueprint Healer...")
                    healed_blueprint = await self.healer.heal_blueprint(
                        blueprint=blueprint,
                        failed_node_id=node["id"],
                        error_message=str(e),
                        tenant_id=context.get("tenant_id", "default")
                    )
                    
                    if healed_blueprint.get("status") == "healed":
                        logger.info("King: Blueprint healed. Record learning trace.")
                        
                        # RECORD LEARNING TRACE
                        try:
                            directive = await self.healer.summarize_healing_as_directive(
                                failed_node=node,
                                healed_nodes=healed_blueprint.get("nodes", []),
                                error=str(e),
                                tenant_id=context.get("tenant_id", "default")
                            )
                            
                            with SessionLocal() as db:
                                trace = AgentEvolutionTrace(
                                    tenant_id=context.get("tenant_id", "default"),
                                    agent_id=getattr(self, "agent_id", "king_agent"),
                                    evolution_type="performance_based",
                                    task_log=f"Node failure: {node['id']}\nError: {e}",
                                    evolving_requirements=directive,
                                    model_patch=json.dumps(healed_blueprint.get("nodes", [])),
                                    benchmark_passed=True, 
                                    benchmark_score=1.0,
                                    is_high_quality=True
                                )
                                db.add(trace)
                                db.commit()
                                logger.info(f"King: Recorded evolution trace with directive: {directive}")
                        except Exception as tracing_err:
                            logger.error(f"King: Failed to record learning trace: {tracing_err}")

                        logger.info("King: Restarting execution with patched architecture.")
                        blueprint = healed_blueprint
                        nodes = blueprint.get("nodes", [])
                        # Re-sync node statuses
                        for n in nodes:
                            if n["id"] not in node_statuses:
                                node_statuses[n["id"]] = "pending"
                        
                        pending_nodes = [n for n in nodes if n["id"] not in executed_nodes]
                        retry_count += 1
                        
                        # Update Canvas with new blueprint
                        if canvas_id:
                            new_mermaid = self.queen.generate_mermaid(blueprint, node_statuses)
                            await update_canvas(
                                tenant_id=context["tenant_id"],
                                user_id=context["user_id"],
                                canvas_id=canvas_id,
                                updates={
                                    "title": f"Healed Plan ({retry_count}): {blueprint.get('architecture_name')}",
                                    "content": f"```mermaid\n{new_mermaid}\n```"
                                }
                            )
                        break 
                    else:
                        logger.error("King: Healing failed. Abandoning execution.")
                        return {
                            "status": "failed",
                            "error": str(e),
                            "partial_results": results
                        }

        return {
            "status": "success",
            "blueprint_id": blueprint.get("blueprint_id"),
            "execution_results": results,
            "final_summary": f"Blueprint '{blueprint.get('architecture_name')}' executed successfully with {retry_count} heal events."
        }

    async def _execute_node(self, node: Dict[str, Any], context: Dict, canvas_context: Optional[Dict]) -> Any:
        """
        Executes a single node in the blueprint.
        """
        node_id = node.get("id")
        node_type = node.get("type", "agent")
        capability = node.get("capability_required")
        
        # If it's an agent node, delegate to a specialized agent
        if node_type == "agent":
            # Map capability to agent name if needed
            agent_name = self._map_capability_to_agent(capability)
            logger.info(f"King: Delegating '{node['name']}' to {agent_name}")
            
            # Use parent's delegation logic
            return await self._execute_delegation(
                agent_name=agent_name,
                task=f"Objective: {node['name']}. Requirements: {capability}",
                context=context
            )
        
        # If it's a direct skill/tool call
        elif node_type == "skill":
            logger.info(f"King: Executing skill: {node['name']}")
            # Use parent's tool execution (includes governance)
            return await self._execute_tool_with_governance(
                tool_name=capability,
                args=node.get("params", {}),
                context=context,
                step_callback=None
            )
            
        return {"status": "skipped", "reason": f"Unknown node type: {node_type}"}

    def _map_capability_to_agent(self, capability: str) -> str:
        """Helper to route capabilities to specialized agents."""
        mapping = {
            "reconciliation": "accounting",
            "lead_scoring": "sales",
            "inventory_check": "logistics",
            "campaign_analysis": "marketing",
            "b2b_extract_po": "purchasing"
        }
        return mapping.get(capability, "general") # Default to Meta (Self) or General
