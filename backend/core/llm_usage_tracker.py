"""
LLM Usage Tracker for monitoring API calls, costs, and budget enforcement.

Tracks LLM usage across providers, models, and workspaces with budget management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from threading import Lock

@dataclass
class UsageRecord:
    """Single LLM usage record"""
    workspace_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    savings_usd: float = 0.0
    agent_id: Optional[str] = None
    complexity: str = "moderate"
    is_managed_service: bool = True
    timestamp: datetime = field(default_factory=datetime.now)


class LLMUsageTracker:
    """
    Thread-safe tracker for LLM usage with budget enforcement.
    """

    def __init__(self):
        self._records: list[UsageRecord] = []
        self._budgets: dict[str, float] = {}  # workspace_id -> budget_limit
        self._usage: dict[str, float] = {}  # workspace_id -> total_usage
        self._lock = Lock()

    def record(
        self,
        workspace_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        savings_usd: float = 0.0,
        agent_id: Optional[str] = None,
        complexity: str = "moderate",
        is_managed_service: bool = True,
    ) -> None:
        """
        Record an LLM usage event.

        Args:
            workspace_id: Workspace identifier
            provider: LLM provider (e.g., "openai", "anthropic")
            model: Model name (e.g., "gpt-4o", "claude-3-5-sonnet")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_usd: Cost in USD
            savings_usd: Savings compared to reference model (e.g., gpt-4o)
            agent_id: Optional agent identifier
            complexity: Query complexity level
            is_managed_service: Whether this was managed AI or BYOK
        """
        record = UsageRecord(
            workspace_id=workspace_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            savings_usd=savings_usd,
            agent_id=agent_id,
            complexity=complexity,
            is_managed_service=is_managed_service,
        )

        with self._lock:
            self._records.append(record)
            if workspace_id not in self._usage:
                self._usage[workspace_id] = 0.0
            self._usage[workspace_id] += cost_usd

    def set_budget(self, workspace_id: str, budget_limit: float) -> None:
        """
        Set a budget limit for a workspace.

        Args:
            workspace_id: Workspace identifier
            budget_limit: Budget limit in USD
        """
        with self._lock:
            self._budgets[workspace_id] = budget_limit

    def is_budget_exceeded(self, workspace_id: str) -> bool:
        """
        Check if a workspace has exceeded its budget.

        Args:
            workspace_id: Workspace identifier

        Returns:
            True if budget is exceeded, False otherwise
        """
        with self._lock:
            if workspace_id not in self._budgets:
                return False  # No budget set

            budget_limit = self._budgets[workspace_id]
            current_usage = self._usage.get(workspace_id, 0.0)

            return current_usage >= budget_limit

    def get_usage(self, workspace_id: str) -> float:
        """
        Get total usage for a workspace.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Total usage in USD
        """
        with self._lock:
            return self._usage.get(workspace_id, 0.0)

    def get_budget(self, workspace_id: str) -> Optional[float]:
        """
        Get budget limit for a workspace.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Budget limit in USD, or None if not set
        """
        with self._lock:
            return self._budgets.get(workspace_id)

    def get_records(self, workspace_id: str, limit: int = 100) -> list[UsageRecord]:
        """
        Get usage records for a workspace.

        Args:
            workspace_id: Workspace identifier
            limit: Maximum number of records to return

        Returns:
            List of usage records (most recent first)
        """
        with self._lock:
            workspace_records = [
                r for r in self._records if r.workspace_id == workspace_id
            ]
            # Return most recent first
            return list(reversed(workspace_records[-limit:]))

    def reset_usage(self, workspace_id: str) -> None:
        """
        Reset usage for a workspace.

        Args:
            workspace_id: Workspace identifier
        """
        with self._lock:
            self._usage[workspace_id] = 0.0


# Global singleton instance
_llm_usage_tracker: Optional[LLMUsageTracker] = None


def get_llm_usage_tracker() -> LLMUsageTracker:
    """
    Get the global LLM usage tracker instance.

    Returns:
        LLMUsageTracker singleton instance
    """
    global _llm_usage_tracker
    if _llm_usage_tracker is None:
        _llm_usage_tracker = LLMUsageTracker()
    return _llm_usage_tracker


# Export singleton for convenience
llm_usage_tracker = get_llm_usage_tracker()
