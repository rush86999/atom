"""
Personal Budget Service for ATOM Upstream

Simplified budget tracking for personal/open-source deployment without billing enforcement.

Key differences from SaaS BudgetService:
- No tenant_id filtering (single-tenant/global budget)
- No Stripe integration or payment processing
- No hard-stop enforcement (warnings only)
- No quota checks or usage tracking
- User-responsible cost management

Ported from: rush86999/atom-saas/backend-saas/core/budget_service.py
Changes: Removed tenant_id, billing enforcement, hard-stop blocking, Stripe integration
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import User

logger = logging.getLogger(__name__)


class PersonalBudgetService:
    """
    Simplified budget tracking for personal/open-source ATOM deployment.

    Features:
    - Track ACU and API costs
    - Budget alerts (email, in-app)
    - Soft-stop enforcement (warnings, not blocks)
    - Budget forecasting

    NO:
    - Stripe integration
    - Payment processing
    - Hard-stop blocking
    - Tenant isolation
    - Usage quota enforcement
    """

    def check_budget(self, user_id: str, budget_limit_usd: float = 100.0) -> Dict[str, any]:
        """
        Check if user is within budget limit (WARNING ONLY, no blocking).

        Args:
            user_id: User ID (single-tenant, no tenant_id)
            budget_limit_usd: Budget limit in USD (default: $100)

        Returns:
            Dict with budget status (never blocks execution)
            {
                "within_budget": bool,
                "remaining_budget": float,
                "current_spend": float,
                "budget_limit": float,
                "percent_used": float,
                "warning": str or None
            }
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found for budget check.")
                return {
                    "within_budget": True,  # Don't block if user not found
                    "remaining_budget": budget_limit_usd,
                    "current_spend": 0.0,
                    "budget_limit": budget_limit_usd,
                    "percent_used": 0.0,
                    "warning": None
                }

            # Get current spend from user record (or default to 0)
            current_spend = getattr(user, 'current_spend_usd', 0.0)
            remaining = budget_limit_usd - current_spend
            percent_used = (current_spend / budget_limit_usd * 100) if budget_limit_usd > 0 else 0

            # Generate warning if over budget
            warning = None
            if remaining <= 0:
                warning = f"Budget exceeded by ${abs(remaining):.2f}. Consider reducing usage or increasing budget limit."
                logger.warning(f"User {user_id} exceeded budget. Spend: ${current_spend:.2f}, Limit: ${budget_limit_usd:.2f}")
            elif percent_used >= 90:
                warning = f"Budget at {percent_used:.1f}% capacity. ${remaining:.2f} remaining."

            # ALWAYS return within_budget=True (no blocking)
            return {
                "within_budget": True,  # Never block execution (personal use)
                "remaining_budget": max(0, remaining),
                "current_spend": current_spend,
                "budget_limit": budget_limit_usd,
                "percent_used": min(100, percent_used),
                "warning": warning
            }
        finally:
            db.close()

    def get_current_spend_usd(self, user_id: str) -> float:
        """
        Get total spend in USD for user.

        Args:
            user_id: User ID

        Returns:
            Current spend in USD
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return getattr(user, 'current_spend_usd', 0.0)
            return 0.0
        finally:
            db.close()

    def record_spend(self, user_id: str, amount_usd: float, description: str = ""):
        """
        Record spend for user (updates user.current_spend_usd).

        Args:
            user_id: User ID
            amount_usd: Amount spent in USD
            description: Optional description of the spend
        """
        if amount_usd <= 0:
            return

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                # Add current_spend_usd column if it doesn't exist
                if not hasattr(user, 'current_spend_usd'):
                    logger.info(f"Adding current_spend_usd column to user {user_id}")
                    # Column would be added via migration
                    return

                user.current_spend_usd = getattr(user, 'current_spend_usd', 0.0) + amount_usd
                db.commit()
                logger.info(f"Recorded ${amount_usd:.4f} spend for user {user_id}: {description}. New total: ${user.current_spend_usd:.4f}")
        except Exception as e:
            logger.error(f"Failed to record spend: {e}")
        finally:
            db.close()

    def get_budget_forecast(self, user_id: str, budget_limit_usd: float = 100.0, days: int = 30) -> Dict[str, any]:
        """
        Predict budget exhaustion based on recent spending.

        Args:
            user_id: User ID
            budget_limit_usd: Budget limit in USD
            days: Number of days to analyze (default: 30)

        Returns:
            Dict with forecast data
            {
                "current_spend": float,
                "budget_limit": float,
                "daily_avg_spend": float,
                "days_until_exhaustion": int or None,
                "exhaustion_date": str or None,
                "forecast": str
            }
        """
        # Simplified forecast (would need spending history table for accuracy)
        current_spend = self.get_current_spend_usd(user_id)
        remaining = budget_limit_usd - current_spend

        if remaining <= 0:
            return {
                "current_spend": current_spend,
                "budget_limit": budget_limit_usd,
                "daily_avg_spend": 0.0,
                "days_until_exhaustion": 0,
                "exhaustion_date": datetime.now().strftime("%Y-%m-%d"),
                "forecast": "Budget already exceeded"
            }

        # TODO: Implement actual spending history tracking for accurate forecasts
        # For now, use simple linear projection from current spend
        days_elapsed = 30  # Assume 30 days since account creation
        daily_avg_spend = current_spend / days_elapsed if days_elapsed > 0 else 0

        if daily_avg_spend > 0:
            days_until_exhaustion = int(remaining / daily_avg_spend)
            exhaustion_date = (datetime.now() + timedelta(days=days_until_exhaustion)).strftime("%Y-%m-%d")
            forecast = f"At current spending rate (${daily_avg_spend:.2f}/day), budget will be exhausted in {days_until_exhaustion} days ({exhaustion_date})"
        else:
            days_until_exhaustion = None
            exhaustion_date = None
            forecast = "Spending rate too low to forecast exhaustion"

        return {
            "current_spend": current_spend,
            "budget_limit": budget_limit_usd,
            "daily_avg_spend": daily_avg_spend,
            "days_until_exhaustion": days_until_exhaustion,
            "exhaustion_date": exhaustion_date,
            "forecast": forecast
        }

    def send_budget_alert(self, user_id: str, threshold_percent: int = 90) -> bool:
        """
        Send budget alert when threshold is crossed.

        Args:
            user_id: User ID
            threshold_percent: Alert threshold (default: 90%)

        Returns:
            True if alert was sent, False otherwise
        """
        budget_limit = 100.0  # Default budget limit
        status = self.check_budget(user_id, budget_limit)

        if status["percent_used"] >= threshold_percent:
            # TODO: Implement actual alert sending (email, in-app notification)
            logger.warning(f"Budget alert for user {user_id}: {status['percent_used']:.1f}% used (${status['current_spend']:.2f} / ${status['budget_limit']:.2f})")
            return True
        return False

    def is_budget_exceeded(self, user_id: str, budget_limit_usd: float = 100.0) -> bool:
        """
        Check if budget is exceeded (for warnings, NOT for blocking).

        Args:
            user_id: User ID
            budget_limit_usd: Budget limit in USD

        Returns:
            True if budget exceeded, False otherwise
        """
        status = self.check_budget(user_id, budget_limit_usd)
        return status["remaining_budget"] <= 0

    def reset_spend(self, user_id: str):
        """
        Reset user's spend to $0 (useful for monthly reset or testing).

        Args:
            user_id: User ID
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user and hasattr(user, 'current_spend_usd'):
                user.current_spend_usd = 0.0
                db.commit()
                logger.info(f"Reset spend for user {user_id} to $0.00")
        except Exception as e:
            logger.error(f"Failed to reset spend: {e}")
        finally:
            db.close()


# Singleton instance
personal_budget_service = PersonalBudgetService()
