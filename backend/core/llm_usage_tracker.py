"""
LLM Usage Tracker for monitoring API calls, costs, and budget enforcement.

Tracks LLM usage across providers, models, and workspaces with budget management.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
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
    chain_id: Optional[str] = None # NEW Phase 11
    complexity: str = "moderate"
    is_managed_service: bool = True
    timestamp: datetime = field(default_factory=datetime.now)


class LLMUsageTracker:
    """
    Thread-safe tracker for LLM usage with budget enforcement.

    Budgets are enforced on a **rolling daily window**: spend is tracked per
    ``(workspace, calendar date)`` so a budget breach today doesn't permanently
    block generation (the old monotonic counter never reset, locking workspaces
    out until process restart). ``_records`` is also bounded to avoid unbounded
    memory growth in the process-wide singleton.
    """

    # Bound on retained per-workspace records (most recent kept). Limits memory
    # in the singleton; get_records already returns only the tail anyway.
    _MAX_RECORDS = 50_000

    def __init__(self):
        self._records: list[UsageRecord] = []
        self._budgets: dict[str, float] = {}  # workspace_id -> daily budget limit (USD)
        # workspace_id -> {date -> spend_usd}. Lazy-pruned to recent dates.
        self._usage: dict[str, dict[date, float]] = {}
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
        chain_id: Optional[str] = None, # NEW Phase 11
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
            chain_id=chain_id, # Phase 11
            complexity=complexity,
            is_managed_service=is_managed_service,
        )

        with self._lock:
            self._records.append(record)
            # Bound the record list (keep most recent). Without this the
            # singleton leaked memory proportional to total LLM call volume.
            if len(self._records) > self._MAX_RECORDS:
                overflow = len(self._records) - self._MAX_RECORDS
                del self._records[:overflow]
            # Track spend per calendar date so budgets are a DAILY window
            # (previously a single monotonic counter never reset, so a workspace
            # that hit its budget once was locked out until process restart).
            today = record.timestamp.date()
            ws_usage = self._usage.setdefault(workspace_id, {})
            ws_usage[today] = ws_usage.get(today, 0.0) + cost_usd
            # Lazy-prune dates older than 2 days (keeps the dict small; only
            # today's spend is consulted for budget enforcement).
            if len(ws_usage) > 2:
                cutoff = today
                for d in list(ws_usage.keys()):
                    if d < cutoff:
                        del ws_usage[d]

    def set_budget(self, workspace_id: str, budget_limit: float) -> None:
        """
        Set a budget limit for a workspace.

        Args:
            workspace_id: Workspace identifier
            budget_limit: Budget limit in USD
        """
        with self._lock:
            self._budgets[workspace_id] = budget_limit

    def _today_usage_locked(self, workspace_id: str) -> float:
        """Spend for the current calendar date (caller holds _lock)."""
        ws_usage = self._usage.get(workspace_id, {})
        return ws_usage.get(date.today(), 0.0)

    def is_budget_exceeded(self, workspace_id: str) -> bool:
        """
        Check if a workspace has exceeded its **daily** budget.

        Budgets reset at the start of each calendar day (local server date), so
        a breach today does not block generation tomorrow.

        Args:
            workspace_id: Workspace identifier

        Returns:
            True if today's spend meets/exceeds the daily budget, else False.
        """
        with self._lock:
            if workspace_id not in self._budgets:
                return False  # No budget set

            budget_limit = self._budgets[workspace_id]
            return self._today_usage_locked(workspace_id) >= budget_limit

    def get_usage(self, workspace_id: str) -> float:
        """
        Get usage for a workspace for the **current day**.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Today's spend in USD.
        """
        with self._lock:
            return self._today_usage_locked(workspace_id)

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
        Reset usage for a workspace for the current day.

        Args:
            workspace_id: Workspace identifier
        """
        with self._lock:
            today = date.today()
            ws_usage = self._usage.setdefault(workspace_id, {})
            ws_usage[today] = 0.0


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
