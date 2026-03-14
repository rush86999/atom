"""
Coverage-driven tests for AgentEvolutionLoop (currently 49% -> target 70%+)

Focus areas from coverage report:
- EvolutionCycleResult.__init__ and to_dict (lines 60-92)
- run_evolution_cycle main loop (lines 129-235)
- select_parent_group with novelty (lines 246-299)
- get_ancestor_lineage (lines 301-353)
- _apply_directives_to_clone (lines 359-433)
- _evaluate_evolved_config (lines 464-502)
- _promote_evolved_config (lines 508-526)
- _record_trace (lines 528-591)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.agent_evolution_loop import (
    AgentEvolutionLoop,
    EvolutionCycleResult,
    PERF_WEIGHT,
    NOVELTY_WEIGHT,
)


class TestEvolutionCycleResult:
    """Test EvolutionCycleResult data class (lines 60-92)."""

    def test_init_creates_result_with_all_fields(self):
        """Cover lines 71-79: EvolutionCycleResult.__init__"""
        result = EvolutionCycleResult(
            cycle_id=str(uuid4()),
            tenant_id="tenant-123",
            parent_agent_ids=["agent-1", "agent-2"],
            directives=["improve performance"],
            evolved_agent_id="agent-3",
            benchmark_passed=True,
            benchmark_score=0.85,
            trace_id="trace-456",
        )

        assert result.cycle_id
        assert result.tenant_id == "tenant-123"
        assert result.parent_agent_ids == ["agent-1", "agent-2"]
        assert result.directives == ["improve performance"]
        assert result.evolved_agent_id == "agent-3"
        assert result.benchmark_passed is True
        assert result.benchmark_score == 0.85
        assert result.trace_id == "trace-456"
        assert result.timestamp  # Should be set by __init__

    def test_to_dict_serializes_all_fields(self):
        """Cover line 82: EvolutionCycleResult.to_dict"""
        result = EvolutionCycleResult(
            cycle_id="cycle-1",
            tenant_id="tenant-1",
            parent_agent_ids=["a1"],
            directives=["d1"],
            evolved_agent_id="a2",
            benchmark_passed=True,
            benchmark_score=0.9,
            trace_id="t1",
        )

        data = result.to_dict()

        assert data["cycle_id"] == "cycle-1"
        assert data["tenant_id"] == "tenant-1"
        assert data["parent_agent_ids"] == ["a1"]
        assert data["directives"] == ["d1"]
        assert data["evolved_agent_id"] == "a2"
        assert data["benchmark_passed"] is True
        assert data["benchmark_score"] == 0.9
        assert data["trace_id"] == "t1"
        assert "timestamp" in data


class TestAgentEvolutionLoopInit:
    """Test AgentEvolutionLoop initialization."""

    def test_init_creates_reflection_service(self):
        """Cover lines 100-102: AgentEvolutionLoop.__init__"""
        db = MagicMock()
        loop = AgentEvolutionLoop(db)

        assert loop.db is db
        assert loop.reflection_svc is not None
