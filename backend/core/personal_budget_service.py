"""
Personal Budget Service for ATOM (Single-Tenant Open-Source Version)

This service provides simplified budget management for personal use without
billing enforcement, payment processing, or multi-tenancy patterns.

Ported from atom-saas
Changes: Removed Stripe, billing enforcement, tenant isolation, hard-stop blocking
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from core.database import SessionLocal
from core.models import User

logger = logging.getLogger(__name__)


class PersonalBudgetService:
    """
    Simplified budget tracking service for personal/open-source deployment.
    
    Key differences from SaaS version:
    - No Stripe integration (personal use = user's responsibility)
    - No billing enforcement (warnings only, no blocking)
    - No tenant-scoped budget (global budget for entire instance)
    - No hard-stop enforcement (user can exceed budget with warnings)
    - No payment processing (cost management is user's responsibility)
    
    Purpose: Help users track AI/LLM costs for personal automation without
    enforcing hard limits. Budget warnings only.
    """
    
    def __init__(self):
        self.budget_limit_usd = 0.0
        self.current_spend_usd = 0.0
        
    def check_budget(self, budget_limit_usd: float, estimated_cost: float = 0.0) -> bool:
        """
        Check if budget is available (warning only, does not block execution).
        
        Args:
            budget_limit_usd: Monthly budget limit in USD
            estimated_cost: Estimated cost for upcoming operation
            
        Returns:
            True if under budget, False if exceeded (but does NOT block execution)
            
        Note:
            This is a soft check only. Even if False is returned, execution
            continues because this is personal use (user's responsibility).
        """
        current_spend = self.get_current_spend_usd()
        remaining = budget_limit_usd - current_spend
        
        if remaining <= estimated_cost:
            logger.warning(
                f"Budget exceeded or will be exceeded. "
                f"Limit: ${budget_limit_usd:.2f}, "
                f"Spent: ${current_spend:.2f}, "
                f"Remaining: ${remaining:.2f}, "
                f"Estimated: ${estimated_cost:.2f}. "
                f"Continuing anyway (personal use = user responsibility)."
            )
            return False
            
        return True
    
    def get_current_spend_usd(self) -> float:
        """
        Get total spend for current month.
        
        Returns:
            Total spend in USD for current month
        """
        db = SessionLocal()
        try:
            # For single-tenant, aggregate across all agent executions
            from core.models import AgentExecution
            
            # Get current month's start
            now = datetime.utcnow()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Query total spend from agent executions
            executions = db.query(AgentExecution).filter(
                AgentExecution.created_at >= month_start,
                AgentExecution.status == 'completed'
            ).all()
            
            # Sum up all costs (ACU + API costs)
            total_spend = sum(
                (e.acu_cost_usd or 0.0) + (e.api_cost_usd or 0.0)
                for e in executions
            )
            
            return total_spend
        except Exception as e:
            logger.error(f"Error getting current spend: {e}")
            return 0.0
        finally:
            db.close()
    
    def get_budget_forecast(self, budget_limit_usd: float) -> Dict[str, Any]:
        """
        Predict when budget will be exhausted based on current spending rate.
        
        Args:
            budget_limit_usd: Monthly budget limit in USD
            
        Returns:
            Dictionary with forecast data:
            - current_spend_usd: Total spent this month
            - daily_spend_usd: Average daily spend
            - days_until_exhaustion: Days until budget exhausted (or None)
            - projected_exhaustion_date: Date when budget will be exhausted (or None)
            - budget_status: 'on_track', 'at_risk', 'exceeded'
        """
        current_spend = self.get_current_spend_usd()
        
        # Calculate daily spend rate
        now = datetime.utcnow()
        days_in_month = now.day  # Current day of month (1-31)
        daily_spend = current_spend / max(days_in_month, 1)  # Avoid division by zero
        
        remaining_budget = budget_limit_usd - current_spend
        days_remaining = (budget_limit_usd - current_spend) / max(daily_spend, 0.0001)
        
        # Determine status
        if current_spend >= budget_limit_usd:
            status = 'exceeded'
            days_until_exhaustion = 0
            projected_exhaustion_date = now
        elif days_remaining < 7:
            status = 'at_risk'
            days_until_exhaustion = max(0, int(days_remaining))
            projected_exhaustion_date = now + timedelta(days=days_until_exhaustion)
        else:
            status = 'on_track'
            days_until_exhaustion = int(days_remaining) if days_remaining < 100 else None
            projected_exhaustion_date = now + timedelta(days=days_until_exhaustion) if days_remaining < 100 else None
        
        return {
            'current_spend_usd': current_spend,
            'daily_spend_usd': daily_spend,
            'days_until_exhaustion': days_until_exhaustion,
            'projected_exhaustion_date': projected_exhaustion_date.isoformat() if projected_exhaustion_date else None,
            'budget_status': status,
            'budget_limit_usd': budget_limit_usd,
            'remaining_budget_usd': max(0, remaining_budget)
        }
    
    def send_budget_alert(self, threshold_percent: float) -> bool:
        """
        Send budget alert when threshold is crossed.
        
        Args:
            threshold_percent: Alert threshold (e.g., 80.0 for 80%)
            
        Returns:
            True if alert sent, False otherwise
            
        Note:
            In personal deployment, this logs to console/warnings.
            In production, integrate with email/notification systems.
        """
        # Get budget limit from user settings or default
        budget_limit_usd = self._get_budget_limit()
        current_spend = self.get_current_spend_usd()
        
        usage_percent = (current_spend / budget_limit_usd) * 100 if budget_limit_usd > 0 else 0
        
        if usage_percent >= threshold_percent:
            logger.warning(
                f"🚨 BUDGET ALERT: {usage_percent:.1f}% of monthly budget used. "
                f"Spent: ${current_spend:.2f} of ${budget_limit_usd:.2f}. "
                f"Remaining: ${budget_limit_usd - current_spend:.2f}."
            )
            return True
        
        return False
    
    def is_budget_exceeded(self) -> bool:
        """
        Check if budget has been exceeded.
        
        Returns:
            True if budget exceeded, False otherwise
            
        Note:
            This is for warning/logging only. Does NOT block execution
            because personal use = user's choice.
        """
        budget_limit_usd = self._get_budget_limit()
        current_spend = self.get_current_spend_usd()
        
        return current_spend >= budget_limit_usd
    
    def _get_budget_limit(self) -> float:
        """
        Get budget limit from user settings or default.
        
        Returns:
            Budget limit in USD (default: $100/month)
        """
        db = SessionLocal()
        try:
            # For single-tenant, use first admin user's settings or default
            user = db.query(User).filter(User.is_admin == True).first()
            
            if user and hasattr(user, 'budget_limit_usd') and user.budget_limit_usd:
                return user.budget_limit_usd
            
            # Default budget limit for personal use
            return 100.0
        except Exception as e:
            logger.error(f"Error getting budget limit: {e}")
            return 100.0  # Default fallback
        finally:
            db.close()
    
    def record_spend(self, amount: float, execution_id: Optional[str] = None):
        """
        Record spend after agent execution (for tracking/forecasting).
        
        Args:
            amount: Amount spent in USD
            execution_id: Optional agent execution ID for attribution
            
        Note:
            This is for tracking/forecasting only. Actual spend is recorded
            in AgentExecution table during execution.
        """
        logger.info(
            f"Recorded ${amount:.4f} spend"
            + (f" for execution {execution_id}" if execution_id else "")
            + f". Total this month: ${self.get_current_spend_usd():.2f}"
        )


# Singleton instance for easy import
personal_budget_service = PersonalBudgetService()
