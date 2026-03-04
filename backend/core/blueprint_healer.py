"""
Blueprint Healer — Reactive Self-Healing for Agent Architectures

Inspired by Hive's self-healing, this module captures failures during
blueprint execution and uses the Queen's architectural logic to 
correct and retry paths.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from core.llm_router import LLMRouter
from core.agents.queen_agent import QueenAgent

logger = logging.getLogger(__name__)

class BlueprintHealer:
    """
    Analyzes execution failures and patches blueprints.
    """

    def __init__(self, db, llm_router: LLMRouter):
        self.db = db
        self.llm = llm_router
        self.queen = QueenAgent(db, llm_router)

    async def heal_blueprint(self, blueprint: Dict[str, Any], failed_node_id: str, error_message: str, tenant_id: str = "default") -> Dict[str, Any]:
        """
        Analyzes a failure and returns a 'healed' version of the blueprint.
        """
        logger.info(f"Healer: Analyzing failure in node {failed_node_id}: {error_message}")

        prompt = f"""You are the Blueprint Healer. An agent architecture failed during execution.
        
BLUEPRINT: {json.dumps(blueprint, indent=2)}
FAILED NODE: {failed_node_id}
ERROR: {error_message}

Your task is to:
1. Identify WHY the node failed.
2. Propose a FIX: 
   - Add a new prerequisite node (e.g., 'Search for documentation').
   - Modify the parameters of the failed node.
   - Replace the node with a different capability.
3. Output the updated nodes list for the blueprint.

Return ONLY the updated 'nodes' array in JSON format."""

        try:
            response = await self.llm.call(
                tenant_id=tenant_id,
                messages=[
                    {"role": "system", "content": "You are a self-healing AI architect. Output only valid JSON nodes array."},
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.get("content", "")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            updated_nodes = json.loads(content)
            
            # Patch the blueprint
            healed_blueprint = blueprint.copy()
            healed_blueprint["nodes"] = updated_nodes
            healed_blueprint["status"] = "healed"
            healed_blueprint["healing_notes"] = f"Healed failure in {failed_node_id}: {error_message[:100]}"
            
            return healed_blueprint

        except Exception as e:
            logger.error(f"Healer: Failed to heal blueprint: {e}")
            return blueprint # Return original if healing fails

    async def summarize_healing_as_directive(self, failed_node: Dict[str, Any], healed_nodes: List[Dict[str, Any]], error: str, tenant_id: str = "default") -> str:
        """
        Synthesizes a concrete evolution directive from a failure and its fix.
        This directive will be fed into the GEA evolution loop.
        """
        prompt = f"""You are the GEA Learning Module. Analyze a blueprint failure and its architectural fix to extract a permanent 'lesson learned'.

FAILURE: Node '{failed_node.get('name')}' ({failed_node.get('type')}) failed.
ERROR: {error}
FIX APPLIED: {json.dumps(healed_nodes, indent=2)}

Create ONE concrete, actionable evolution directive (one sentence) that would prevent this architectural mistake in future generations.
Examples:
- "Always add a search node before attempting to use a tool with unknown schema."
- "Increase timeout for nodes involving high-latency CSV exports."
- "Verify data availability via an authentication-check node before attempting sensitive API calls."

DIRECTIVE:"""

        try:
            response = await self.llm.call(
                tenant_id=tenant_id,
                messages=[
                    {"role": "system", "content": "You are a professional AI evolution scientist. Output ONLY the directive string."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.get("content", "Improve architectural robustness for the failing node type.").strip()
        except:
            return "Refine dependencies for failed node types."
