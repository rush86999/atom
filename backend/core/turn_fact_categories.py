"""
Turn Fact Categories

The 5 durable-fact categories (Mem0 production taxonomy) extracted from agent
turns. These survive context compression because they change rarely and are
referenced across sessions.

Reference: https://mem0.ai/blog/how-hermes-and-claude-handle-context-compression-...
"""

from enum import Enum


class FactCategory(str, Enum):
    """
    The 5 canonical categories of durable facts worth extracting per turn.

    Order matters only for documentation; extraction prompt emits the literal
    string value as the discriminator.
    """
    EXACT_VALUE = "exact_value"          # "$50K MRR", "7-day SLA", "launch on Mar 14"
    HARD_CONSTRAINT = "hard_constraint"  # "must use Stripe", "no PII to OpenAI"
    DECISION_REASON = "decision_reason"  # "chose Postgres for X", "rejected Option B"
    CROSS_TASK_DEP = "cross_task_dep"    # "blocks onboarding v2", "depends on auth service"
    IMPLICIT_PREF = "implicit_pref"      # "prefers terse responses", "wants bullet points"


ALL_FACT_CATEGORIES = tuple(c.value for c in FactCategory)
