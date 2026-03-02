"""
Property-Based Tests for Async Governance Invariants

Tests async AgentContextResolver methods using Hypothesis:
- resolve_agent_for_request() always returns (agent, context) tuple
- Resolution path is always non-empty
- Invalid agent IDs return None agent but valid context

Uses @pytest.mark.asyncio BEFORE @given to avoid Hypothesis async errors.
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import sampled_from, uuids, text, optional
from sqlalchemy.orm import Session
from typing import Optional

from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry, AgentStatus, ChatSession

HYPOTHESIS_SETTINGS_CRITICAL = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200
}

HYPOTHESIS_SETTINGS_IO = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 50
}


class TestAsyncContextResolverInvariants:
    """Property-based tests for async agent context resolution (CRITICAL)."""

    # Tests will be added in next task
