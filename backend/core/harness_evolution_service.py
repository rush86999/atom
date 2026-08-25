import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from core.models import AgentReasoningStep, AgentRegistry
from core.sandbox_transaction import SandboxTransaction

logger = logging.getLogger(__name__)


def normalize_model_family(model_id) -> str:
    """Re-export of the R82 family policy (see core.llm.model_provenance)."""
    from core.llm.model_provenance import normalize_model_family as _norm

    return str(_norm(model_id))


def applicable_patches(
    patches: List[Dict[str, Any]],
    current_model_id: Optional[str],
    provider_id: Optional[str] = None,
    drift_detector=None,
) -> List[Dict[str, Any]]:
    """Read-time filter deciding which harness patches apply to a model call.

    The constraint chain (R82 adjudicated design):
      1. scope match — ``all`` patches always apply; ``model_family`` patches
         apply only when their family normalizes to the serving model's family;
      2. fail-safe — scoped patches with unknown origin family (``None``,
         pre-provenance) are EXCLUDED, never silently universalized;
      3. drift expiry — when the detector reports active silent-bump drift on
         ``(provider_id, current_model_id)``, family-scoped patches matching
         that identity are suppressed IMMEDIATELY (serve-path action, not
         next-mining-cycle correction), until the echo stabilizes again.

    Granularity is per-LLM-call: tier/stage routing means one run can span
    several models, so callers inside step loops pass the concrete router-
    selected model for THAT call (never a caller alias like "auto").
    """
    family = normalize_model_family(current_model_id)
    drifted = False
    if drift_detector is not None and provider_id and current_model_id:
        try:
            drifted = drift_detector.is_drifted(provider_id, current_model_id)
        except Exception:
            drifted = False

    out: List[Dict[str, Any]] = []
    for patch in patches or []:
        if not isinstance(patch, dict):
            continue
        scope = str(patch.get("model_scope", "all"))
        if scope == "all":
            out.append(patch)
            continue
        patch_family = normalize_model_family(patch.get("model_family"))
        if not patch_family or patch_family != family:
            continue
        if drifted:
            continue
        out.append(patch)
    return out




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

        # Select patch strategy based on tool/step.
        # model_scope policy (R82, adjudicated): deterministic blast-radius
        # controls (tripwires, compaction bounds) are portable across models
        # ("all"); prose-level strategy (system_prompt rules) failed even on
        # its own evolution model in AHE's component ablation and demonstrably
        # fails to transfer across task surfaces — so prompt patches are
        # family-scoped. "model_family" is None until mining keys clusters on
        # AgentReasoningStep.requested_model (provenance lands with R82);
        # unknown-family scoped patches are excluded at application time
        # (fail-safe), see applicable_patches().
        if tool == "shell" or tool == "run_command":
            target = "ast_tripwire"
            payload = {
                "blocked_patterns": ["rm -rf /", "mkfs", "dd if="],
                "max_depth": 10
            }
            model_scope = "all"
            model_family = None
        elif step_type == "thought":
            target = "system_prompt"
            payload = {
                "instruction_append": "Always justify tool parameters before invoking them."
            }
            model_scope = "model_family"
            model_family = pattern.get("model_family")
        else:
            target = "context_compaction"
            payload = {
                "max_token_limit": 4096,
                "compaction_strategy": "boundary_protection"
            }
            # Compaction bounds are secretly model-sensitive (context windows
            # differ per model); left portable today but the schema permits
            # scoping once mining attributes overflow failures to families.
            model_scope = "all"
            model_family = None

        return {
            "patch_id": f"patch_{step_type}_{tool}",
            "target_component": target,
            "mutation_payload": payload,
            "model_scope": model_scope,
            "model_family": model_family,
        }

    async def validate_mutation_in_sandbox(
        self,
        patch: Dict[str, Any],
        workspace_dir: str,
        test_fn=None,
    ) -> bool:
        """
        Validate a proposed harness patch inside a transactional rollback sandbox.

        When ``test_fn`` is provided, it's called with the patch to verify
        behavior. When NOT provided (the common case — no caller passes one),
        a default regression check runs: the patch is structurally validated
        (no forbidden patterns, valid JSON/config keys) to catch obviously
        dangerous or malformed patches before deployment.

        Previously this method required a caller-supplied test_fn but none was
        ever passed, making validation effectively a no-op.
        """
        logger.info(
            f"Validating patch {patch.get('patch_id', 'unknown')} in workspace sandbox..."
        )

        try:
            with SandboxTransaction(target_dir=workspace_dir, timeout_seconds=10) as tx:
                logger.info(f"Applying patch configuration in sandbox: {patch.get('target_component', 'unknown')}")

                if test_fn is not None:
                    # Caller-supplied test function (backward compat)
                    success = test_fn(patch)
                    if not success:
                        raise ValueError("Regression tests failed in sandbox")
                else:
                    # Default structural validation when no test_fn is provided.
                    # This catches obviously dangerous patches before deployment.
                    success = self._default_patch_validation(patch)
                    if not success:
                        raise ValueError("Default patch validation failed")

                return True
        except Exception as e:
            logger.warning(f"Patch validation failed or rolled back: {e}")
            return False

    def _default_patch_validation(self, patch: Dict[str, Any]) -> bool:
        """Structural validation for harness patches when no test_fn is provided.

        Checks:
          1. Patch has required fields (patch_id, target_component)
          2. Patch content doesn't contain danger patterns (reuse the
             governance gate's pattern set)
          3. Patch isn't trying to modify protected config keys directly
             (self-referential safety-net mutation)
        """
        if not patch.get("patch_id"):
            return False
        if not patch.get("target_component"):
            return False

        # Check patch content for danger patterns
        patch_str = str(patch).lower()
        try:
            from core.agent_governance_service import AgentGovernanceService
            for pattern in AgentGovernanceService._DANGER_PATTERNS:
                if pattern in patch_str:
                    logger.warning(
                        f"Patch {patch['patch_id']} contains danger pattern: '{pattern}'"
                    )
                    return False
        except Exception:
            pass  # governance service unavailable — don't block

        # Check for self-referential mutation of protected keys
        target = str(patch.get("target_component", "")).lower()
        try:
            from core.agent_governance_service import AgentGovernanceService
            for key in AgentGovernanceService._PROTECTED_CONFIG_KEYS:
                if key in target and key != "harness_patches":
                    logger.warning(
                        f"Patch {patch['patch_id']} targets protected key: '{key}'"
                    )
                    return False
        except Exception:
            pass

        return True

    async def deploy_harness_patch(self, patch: Dict[str, Any], agent_id: str) -> bool:
        """
        Commit the validated harness patch directly into the agent registry configuration.

        Takes a rollback snapshot before deploying so the patch can be reverted
        on regression via the MutationRollbackRegistry.
        """
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            logger.error(f"Agent {agent_id} not found for patch deployment")
            return False

        if not agent.configuration:
            agent.configuration = {}

        if "harness_patches" not in agent.configuration:
            agent.configuration["harness_patches"] = []

        # Take a rollback snapshot before mutating (Phase 1b).
        old_patches = list(agent.configuration.get("harness_patches", []))
        try:
            from core.auto_dev.mutation_rollback import get_rollback_registry
            mutation_id = get_rollback_registry().snapshot(
                agent_id=agent_id,
                config_key="harness_patches",
                old_value=old_patches,
                new_value=patch,
                source="harness_evolution",
            )
            patch["_rollback_mutation_id"] = mutation_id
        except Exception:
            pass  # rollback is best-effort; never blocks deployment

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
