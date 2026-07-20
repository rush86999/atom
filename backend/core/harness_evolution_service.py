import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models import AgentReasoningStep, AgentRegistry
from core.sandbox_transaction import SandboxTransaction

logger = logging.getLogger(__name__)

class HarnessEvolutionService:
    """
    Offline Meta-Runtime Service that mines execution traces for failure patterns,
    proposes targeted harness mutations, validates them in isolated sandboxes,
    and deploys patches to agent configurations.
    """

    def __init__(self, db: Session):
        self.db = db

    async def mine_weaknesses(self, tenant_id: str, lookback_hours: int = 24) -> List[Dict[str, Any]]:
        """
        Scan AgentReasoningStep execution traces to identify repeating failure patterns
        grouped by model, step type, and action tool.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        # Query failed verifications or negative feedback
        failures = (
            self.db.query(AgentReasoningStep)
            .filter(
                AgentReasoningStep.tenant_id == tenant_id,
                AgentReasoningStep.timestamp >= cutoff,
                (AgentReasoningStep.verified == "failed_verification") | (AgentReasoningStep.feedback_score < 0)
            )
            .all()
        )

        patterns = {}
        for f in failures:
            # Safely extract tool name if action is JSON
            tool_name = "unknown"
            if f.action and isinstance(f.action, dict):
                tool_name = f.action.get("tool", "unknown")
            elif isinstance(f.action, str):
                try:
                    act_json = json.loads(f.action)
                    tool_name = act_json.get("tool", "unknown")
                except Exception:
                    pass

            # Group key by step type and tool
            key = (f.step_type, tool_name)
            if key not in patterns:
                patterns[key] = {
                    "step_type": f.step_type,
                    "tool": tool_name,
                    "failure_count": 0,
                    "examples": []
                }
            patterns[key]["failure_count"] += 1
            if len(patterns[key]["examples"]) < 3:
                patterns[key]["examples"].append({
                    "id": f.id,
                    "thought": f.thought,
                    "observation": f.observation,
                    "verification_evidence": f.verification_evidence
                })

        return list(patterns.values())

    async def propose_mutation(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        Propose a targeted micro-patch configuration to rectify a recurring failure pattern.
        """
        tool = pattern.get("tool", "unknown")
        step_type = pattern.get("step_type", "unknown")

        # Select patch strategy based on tool/step
        if tool == "shell" or tool == "run_command":
            target = "ast_tripwire"
            payload = {
                "blocked_patterns": ["rm -rf /", "mkfs", "dd if="],
                "max_depth": 10
            }
        elif step_type == "thought":
            target = "system_prompt"
            payload = {
                "instruction_append": "Always justify tool parameters before invoking them."
            }
        else:
            target = "context_compaction"
            payload = {
                "max_token_limit": 4096,
                "compaction_strategy": "boundary_protection"
            }

        return {
            "patch_id": f"patch_{step_type}_{tool}",
            "target_component": target,
            "mutation_payload": payload,
            "model_scope": "all"
        }

    async def validate_mutation_in_sandbox(
        self,
        patch: Dict[str, Any],
        workspace_dir: str,
        test_fn
    ) -> bool:
        """
        Validate a proposed harness patch inside a transactional rollback sandbox.
        """
        logger.info(f"Validating patch {patch['patch_id']} in workspace sandbox...")
        
        try:
            # Wrap verification in SandboxTransaction to ensure clean state
            with SandboxTransaction(target_dir=workspace_dir, timeout_seconds=10) as tx:
                # Apply temporary patch configuration mock
                logger.info(f"Applying patch configuration in sandbox: {patch['target_component']}")
                
                # Execute user-supplied test function to verify logic
                success = test_fn(patch)
                if not success:
                    raise ValueError("Regression tests failed in sandbox")
                
                return True
        except Exception as e:
            logger.warning(f"Patch validation failed or rolled back: {e}")
            return False

    async def deploy_harness_patch(self, patch: Dict[str, Any], agent_id: str) -> bool:
        """
        Commit the validated harness patch directly into the agent registry configuration.
        """
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            logger.error(f"Agent {agent_id} not found for patch deployment")
            return False

        if not agent.configuration:
            agent.configuration = {}
        
        if "harness_patches" not in agent.configuration:
            agent.configuration["harness_patches"] = []

        # Upsert patch configuration
        patches = agent.configuration["harness_patches"]
        patches = [p for p in patches if p["patch_id"] != patch["patch_id"]]
        patches.append(patch)
        agent.configuration["harness_patches"] = patches

        # Save to DB
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(agent, "configuration")
        self.db.commit()
        
        logger.info(f"Successfully deployed patch {patch['patch_id']} to agent {agent_id}")
        return True
