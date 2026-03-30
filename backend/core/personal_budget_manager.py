import logging
from typing import Optional, Dict
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)

class PersonalBudgetManager:
    """
    Manages local LLM token budgets and cost limits for personal an atom-upstream instance.
    This is a lightweight port of the SaaS QuotaManager, focusing on 'Personal Budgets'
    rather than multi-tenant tiered pricing.
    """

    # Default daily limits (in USD)
    DEFAULT_DAILY_BUDGET = 5.0
    DEFAULT_MONTHLY_BUDGET = 50.0

    def __init__(self, db_session=None):
        self.db = db_session
        # For upstream, we might store these in a local config or preferences table
        self.daily_limit = float(os.getenv("ATOM_DAILY_BUDGET", self.DEFAULT_DAILY_BUDGET))
        self.monthly_limit = float(os.getenv("ATOM_MONTHLY_BUDGET", self.DEFAULT_MONTHLY_BUDGET))

    def check_budget(self, estimated_cost: float = 0.0) -> bool:
        """
        Check if the current request is within the personal token budget.
        In Upstream, this typically checks a 'user_preferences' or 'local_usage' table.
        """
        # TODO: Implement database lookup for current_daily_spend
        # For now, we allow if within env limits
        logger.info(f"Checking personal budget for estimated cost: ${estimated_cost:.6f}")
        
        # High-water mark safety
        if estimated_cost > self.daily_limit:
            logger.warning(f"Single request cost ${estimated_cost} exceeds daily limit ${self.daily_limit}")
            return False
            
        return True

    def record_usage(self, model: str, input_tokens: int, output_tokens: int, cost: float):
        """
        Record token usage for the personal account.
        """
        logger.info(f"Usage recorded: {model} ({input_tokens} in, {output_tokens} out) - Cost: ${cost:.6f}")
        # In Upstream, we'd persist this to a 'token_usage' or similar table
        # to track toward daily/monthly limits.

    @staticmethod
    def get_tier_name() -> str:
        """Upstream is always 'Personal' tier."""
        return "personal"

budget_manager = PersonalBudgetManager()
