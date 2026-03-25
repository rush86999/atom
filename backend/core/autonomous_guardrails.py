import logging
import time
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone

from core.models import TokenUsage, AgentRegistry, AgentStatus
from core.database import SessionLocal

logger = logging.getLogger(__name__)

class AutonomousGuardrailService:
    """
    Enforces safety boundaries for Autonomous agents in Upstream.
    If a guardrail is tripped, the agent's autonomy is paused or restricted.
    """

    # Enforcement modes
    ALERT_ONLY = "alert_only"
    SOFT_STOP = "soft_stop"
    HARD_STOP = "hard_stop"

    # --- SAFETY CONFIGURATION ---
    
    # Models deemed safe for complex/high-risk tasks
    ADVANCED_MODELS = [
        "gpt-4", "gpt-4-turbo", "gpt-4o", 
        "claude-3-opus", "claude-3-sonnet", "claude-3-5-sonnet",
        "gemini-1.5-pro", "gemini-2.0-flash-exp"
    ]

    # Actions that are NEVER allowed autonomously regardless of agent status
    DANGER_ZONE_ACTIONS = {
        "pii_access": ["get_ssn", "read_passwords", "export_customer_data"],
        "system_config": ["update_env_vars", "modify_db_schema", "purge_logs"],
        "mass_comm": ["send_bulk_email", "broadcast_slack_all"],
        "terminal_danger": ["rm -rf", "format", "chmod 777"]
    }

    def __init__(self, db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None):
        self.db = db
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id

    def check_guardrails(
        self, 
        agent_id: str, 
        action_type: str, 
        action_params: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main check for autonomous actions.
        """
        effective_tenant = tenant_id or self.tenant_id
        query = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        )
        if effective_tenant:
            query = query.filter(AgentRegistry.tenant_id == effective_tenant)
        
        agent = query.first()
        if not agent:
            return {"proceed": False, "reason": "Agent not found", "requires_downgrade": False}

        # 0. Model Capability Check
        # Ensure high-complexity tasks use advanced models
        model_name = action_params.get("model_name", "unknown")
        capability_check = self._check_model_capability(action_type, model_name)
        if not capability_check["allowed"]:
            return {
                "proceed": False,
                "reason": capability_check["reason"],
                "violation_type": "model_mismatch",
                "requires_downgrade": False # Just block this specific task
            }

        # 0.1 Danger Zone Check
        if self._is_in_danger_zone(action_type, action_params):
            return {
                "proceed": False,
                "reason": f"Action '{action_type}' is in the platform's 'Danger Zone' and requires manual oversight.",
                "violation_type": "danger_zone",
                "requires_downgrade": False
            }

        # 1. Rate Limiting (Actions per Hour)
        # Default 60 actions/hour unless specified in agent config
        config = agent.configuration if hasattr(agent, 'configuration') and agent.configuration else {}
        rate_limit = config.get("guardrails", {}).get("max_actions_per_hour", 60)
        recent_actions_count = self._get_recent_action_count(agent_id, tenant_id=effective_tenant, hours=1)
        
        if recent_actions_count >= rate_limit:
            return {
                "proceed": False,
                "reason": f"Rate limit exceeded: {recent_actions_count}/{rate_limit} actions in the last hour.",
                "violation_type": "rate_limit",
                "requires_downgrade": True
            }

        # 2. Daily Cost Gating
        # Default $10/day unless specified in agent config
        cost_limit = config.get("guardrails", {}).get("max_daily_spend_usd", 10.0)
        daily_spend = self._get_daily_spend(agent_id, tenant_id=effective_tenant)
        
        if daily_spend >= cost_limit:
            # Check enforcement mode
            enforcement_mode = config.get("guardrails", {}).get("enforcement_mode", self.ALERT_ONLY)
            
            if enforcement_mode == self.ALERT_ONLY:
                logger.info(f"Daily cost gate hit (Alert Only): ${daily_spend:.2f}/${cost_limit:.2f}.")
                return {"proceed": True, "reason": "Daily cost gate hit (Alert Only)", "requires_downgrade": False}
            
            elif enforcement_mode == self.SOFT_STOP:
                # Prevent new episodes, allow active to complete
                from core.models import AgentExecution
                has_active = self.db.query(AgentExecution).filter(
                    AgentExecution.agent_id == agent_id,
                    AgentExecution.status == "running"
                ).first() is not None
                
                if has_active:
                    return {
                        "proceed": True,
                        "reason": "Daily cost gate hit. Active episode allowed to complete (Soft Stop).",
                        "violation_type": "cost_gate_soft",
                        "requires_downgrade": False
                    }
                else:
                    return {
                        "proceed": False,
                        "reason": f"Daily cost gate hit: ${daily_spend:.2f}/${cost_limit:.2f}. New episodes blocked (Soft Stop).",
                        "violation_type": "cost_gate",
                        "requires_downgrade": True
                    }
            
            elif enforcement_mode == self.HARD_STOP:
                # Halt all operations immediately
                self._cancel_active_episodes(agent_id)
                return {
                    "proceed": False,
                    "reason": f"Daily cost gate hit: ${daily_spend:.2f}/${cost_limit:.2f}. All operations halted (Hard Stop).",
                    "violation_type": "cost_gate_hard",
                    "requires_downgrade": True
                }

            # Default to block if unknown mode
            return {
                "proceed": False,
                "reason": f"Daily cost gate hit: ${daily_spend:.2f}/${cost_limit:.2f}.",
                "violation_type": "cost_gate",
                "requires_downgrade": True
            }

        # 3. Sensitivity Interlock (High-value actions)
        if self._is_sensitive_action(action_type, action_params):
            return {
                "proceed": False,
                "reason": f"Action '{action_type}' exceeds safety sensitivity thresholds for autonomous execution.",
                "violation_type": "sensitivity_interlock",
                "requires_downgrade": False 
            }

        return {"proceed": True, "reason": "All guardrails passed.", "requires_downgrade": False}

    def _check_model_capability(self, action_type: str, model_name: str) -> Dict[str, Any]:
        """
        Ensure high-complexity tasks use advanced models.
        """
        high_complexity_prefixes = ["delete", "execute", "deploy", "transfer", "payment", "approve", "modify", "update"]
        is_high_complexity = any(p in action_type.lower() for p in high_complexity_prefixes)
        
        if is_high_complexity:
            is_advanced = any(m in model_name.lower() for m in self.ADVANCED_MODELS)
            if not is_advanced:
                return {
                    "allowed": False,
                    "reason": f"Model '{model_name}' is insufficient for high-risk action '{action_type}'. Advanced model required."
                }
        
        return {"allowed": True, "reason": "Model capability verified."}

    def _is_in_danger_zone(self, action_type: str, params: Dict[str, Any]) -> bool:
        """Check if action matches any danger zone categories"""
        action_lower = action_type.lower()
        for category, actions in self.DANGER_ZONE_ACTIONS.items():
            if action_lower in actions:
                logger.warning(f"Danger Zone Triggered: {action_type} (Category: {category})")
                return True
        
        # Check for terminal command patterns
        if "terminal" in action_lower:
            cmd = params.get("command", "").lower()
            for danger_cmd in self.DANGER_ZONE_ACTIONS["terminal_danger"]:
                if danger_cmd in cmd:
                    logger.warning(f"Danger Zone Triggered: Terminal command '{cmd}' contains '{danger_cmd}'")
                    return True
                    
        return False

    def _get_recent_action_count(self, agent_id: str, tenant_id: Optional[str] = None, hours: int = 1) -> int:
        """Count actions in the database for this agent (using TokenUsage as proxy for actions)"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = self.db.query(TokenUsage).filter(
            TokenUsage.agent_id == agent_id,
            TokenUsage.timestamp >= since,
            TokenUsage.workspace_id == self.workspace_id
        )
        if tenant_id:
            query = query.filter(TokenUsage.tenant_id == tenant_id)
            
        return query.count()

    def _get_daily_spend(self, agent_id: str, tenant_id: Optional[str] = None) -> float:
        """Get total cost of agent actions in the last 24 hours"""
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        query = self.db.query(func.sum(TokenUsage.cost_usd)).filter(
            TokenUsage.agent_id == agent_id,
            TokenUsage.timestamp >= since,
            TokenUsage.workspace_id == self.workspace_id
        )
        if tenant_id:
            query = query.filter(TokenUsage.tenant_id == tenant_id)
            
        total_cost = query.scalar() or 0.0
        return float(total_cost)

    def _is_sensitive_action(self, action_type: str, params: Dict[str, Any]) -> bool:
        """
        Check if action parameters exceed safety thresholds.
        Example: Transferring > $500 or deleting a critical resource.
        """
        action_lower = action_type.lower()
        
        # 1. Financial Transfers
        if "transfer" in action_lower or "payment" in action_lower:
            amount = params.get("amount", 0)
            if amount > 500:
                logger.warning(f"Sensitive Action Blocked: Transfer amount {amount} > 500")
                return True
        
        # 2. Mass Deletions
        if "delete" in action_lower:
            if params.get("batch_count", 1) > 10:
                return True
            if params.get("resource_type") in ["database", "deployment", "user"]:
                return True
                
        return False

    def handle_violation(self, agent_id: str, violation_type: str, reason: str, tenant_id: Optional[str] = None):
        """Log violation and potentially downgrade agent status"""
        query = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id,
            AgentRegistry.workspace_id == self.workspace_id
        )
        if tenant_id or self.tenant_id:
            query = query.filter(AgentRegistry.tenant_id == (tenant_id or self.tenant_id))
            
        agent = query.first()
        if not agent:
            return

        logger.warning(f"Guardrail Violation for Agent {agent.name} (Tenant: {tenant_id}): {violation_type} - {reason}")
        
        # If it's a serious violation, drop them back to SUPERVISED
        if violation_type in ["rate_limit", "cost_gate", "cost_gate_hard"]:
            agent.status = AgentStatus.SUPERVISED.value
            logger.info(f"Agent {agent.name} downgraded to SUPERVISED due to {violation_type}")
            self.db.commit()

    def _cancel_active_episodes(self, agent_id: str) -> int:
        """Mark all running episodes as cancelled (Hard Stop)."""
        from core.models import AgentExecution
        try:
            running = self.db.query(AgentExecution).filter(
                AgentExecution.agent_id == agent_id,
                AgentExecution.status == "running"
            ).all()
            
            count = 0
            for ep in running:
                ep.status = "cancelled"
                count += 1
            
            self.db.commit()
            logger.info(f"Hard Stop: Cancelled {count} active episodes for agent {agent_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to cancel episodes: {e}")
            self.db.rollback()
            return 0
