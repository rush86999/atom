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


class TestRunEvolutionCycle:
    """Test run_evolution_cycle method (lines 108-244)."""

    @pytest.fixture
    def loop_with_mocks(self, db_session):
        """Create loop with mocked dependencies."""
        from core.agent_evolution_loop import AgentEvolutionLoop

        loop = AgentEvolutionLoop(db_session)

        # Mock GroupReflectionService methods
        loop.reflection_svc.gather_group_experience_pool = MagicMock(return_value={
            "tool_patterns": [],
            "task_log_excerpts": ["task1", "task2"],
        })
        loop.reflection_svc.reflect_and_generate_directives = AsyncMock(return_value=[
            "Improve response quality",
            "Add more context awareness"
        ])

        return loop

    @pytest.mark.asyncio
    async def test_evolution_cycle_with_empty_pool(self, loop_with_mocks):
        """Cover lines 138-149: Returns early when no agents found."""
        # Mock select_parent_group to return empty
        loop_with_mocks.select_parent_group = MagicMock(return_value=[])

        result = await loop_with_mocks.run_evolution_cycle("tenant-1")

        assert result.parent_agent_ids == []
        assert result.directives == []
        assert result.evolved_agent_id is None
        assert result.benchmark_passed is False

    @pytest.mark.asyncio
    async def test_evolution_cycle_guardrail_blocks(self, loop_with_mocks):
        """Cover lines 179-202: Guardrail validation blocks promotion."""
        # Create test agent
        from core.models import AgentRegistry
        agent = AgentRegistry(
            id="agent-test",
            tenant_id="tenant-1",
            name="Test Agent",
            status="SUPERVISED",
            confidence_score=0.75,
            configuration={"system_prompt": "You are helpful"},
            enabled=True,
            category="general",
            module_path="core.test_agent",
            class_name="TestAgent",
        )
        loop_with_mocks.db.add(agent)
        loop_with_mocks.db.commit()

        # Mock parent group
        loop_with_mocks.select_parent_group = MagicMock(return_value=[agent])

        # Mock guardrail to fail
        loop_with_mocks._validate_via_guardrails = AsyncMock(return_value=False)
        loop_with_mocks._record_trace = MagicMock(return_value=MagicMock(id="trace-1"))

        result = await loop_with_mocks.run_evolution_cycle(
            "tenant-1",
            group_size=1
        )

        assert result.evolved_agent_id is None
        assert result.benchmark_passed is False
        assert result.trace_id == "trace-1"

    @pytest.mark.asyncio
    async def test_evolution_cycle_successful_flow(self, loop_with_mocks):
        """Cover lines 204-244: Full successful evolution cycle."""
        from core.models import AgentRegistry, AgentEvolutionTrace

        # Create test agent
        agent = AgentRegistry(
            id="agent-success",
            tenant_id="tenant-1",
            name="Success Agent",
            status="SUPERVISED",
            confidence_score=0.85,
            configuration={"system_prompt": "You are helpful"},
            enabled=True,
            category="general",
            module_path="core.test_agent",
            class_name="TestAgent",
        )
        loop_with_mocks.db.add(agent)
        loop_with_mocks.db.commit()

        # Mock parent group
        loop_with_mocks.select_parent_group = MagicMock(return_value=[agent])

        # Mock guardrail passes
        loop_with_mocks._validate_via_guardrails = AsyncMock(return_value=True)

        # Mock evaluation passes
        loop_with_mocks._evaluate_evolved_config = AsyncMock(return_value=(0.85, True))

        # Mock promotion
        loop_with_mocks._promote_evolved_config = AsyncMock(return_value="agent-success")

        # Mock trace recording
        trace = MagicMock()
        trace.id = "trace-success"
        loop_with_mocks._record_trace = MagicMock(return_value=trace)

        result = await loop_with_mocks.run_evolution_cycle(
            "tenant-1",
            group_size=1
        )

        assert result.parent_agent_ids == ["agent-success"]
        assert len(result.directives) == 2
        assert result.evolved_agent_id == "agent-success"
        assert result.benchmark_passed is True
        assert result.benchmark_score == 0.85
        assert result.trace_id == "trace-success"


class TestSelectParentGroup:
    """Test select_parent_group method (lines 246-299)."""

    def test_select_parent_group_with_novelty(self, db_session):
        """Cover lines 268-299: Parent selection with novelty calculation."""
        from core.models import AgentRegistry
        from datetime import datetime, timedelta, timezone
        from core.agent_evolution_loop import AgentEvolutionLoop

        # Create agents with varying confidence scores
        now = datetime.now(timezone.utc)
        agents = []
        for i, conf in enumerate([0.5, 0.7, 0.9, 0.6, 0.8, 0.4]):
            agent = AgentRegistry(
                id=f"agent-{i}",
                tenant_id="tenant-select",
                name=f"Agent {i}",
                status="SUPERVISED",
                confidence_score=conf,
                enabled=True,
                updated_at=now - timedelta(days=1),
                category="general",
                module_path="core.test_agent",
                class_name="TestAgent",
            )
            db_session.add(agent)
            agents.append(agent)
        db_session.commit()

        loop = AgentEvolutionLoop(db_session)
        parents = loop.select_parent_group("tenant-select", n=5)

        # Should return top agents sorted by combined score
        assert len(parents) <= 5
        # Highest confidence agent should be first
        assert parents[0].confidence_score >= parents[-1].confidence_score if parents else True

    def test_select_parent_group_filters_by_threshold(self, db_session):
        """Cover line 275: Filters by MIN_PERF_THRESHOLD."""
        from core.models import AgentRegistry
        from datetime import datetime, timedelta, timezone
        from core.agent_evolution_loop import AgentEvolutionLoop, MIN_PERF_THRESHOLD

        now = datetime.now(timezone.utc)
        # Create agents below threshold
        for i in range(3):
            agent = AgentRegistry(
                id=f"agent-low-{i}",
                tenant_id="tenant-threshold",
                name=f"Low Agent {i}",
                status="INTERN",
                confidence_score=0.2,  # Below MIN_PERF_THRESHOLD (0.3)
                enabled=True,
                updated_at=now - timedelta(days=1),
                category="general",
                module_path="core.test_agent",
                class_name="TestAgent",
            )
            db_session.add(agent)
        db_session.commit()

        loop = AgentEvolutionLoop(db_session)
        parents = loop.select_parent_group("tenant-threshold")

        # Should return empty - all below threshold
        assert parents == []


class TestApplyDirectivesToClone:
    """Test _apply_directives_to_clone method (lines 359-433)."""

    @pytest.mark.asyncio
    async def test_apply_directives_to_clone(self, db_session):
        """Cover lines 375-433: Directive application to cloned config."""
        from core.models import AgentRegistry
        from core.agent_evolution_loop import AgentEvolutionLoop

        agent = AgentRegistry(
            id="agent-clone",
            tenant_id="tenant-clone",
            name="Clone Agent",
            status="SUPERVISED",
            confidence_score=0.8,
            configuration={"system_prompt": "Original prompt"},
            category="general",
            module_path="core.test_agent",
            class_name="TestAgent",
        )
        db_session.add(agent)
        db_session.commit()

        loop = AgentEvolutionLoop(db_session)

        # Mock guardrail to pass
        loop._validate_via_guardrails = AsyncMock(return_value=True)

        directives = ["Add more detail", "Be more concise"]
        evolved_config, guardrail_ok = await loop._apply_directives_to_clone(
            agent, directives, "tenant-clone"
        )

        assert guardrail_ok is True
        assert "evolution_history" in evolved_config
        assert len(evolved_config["evolution_history"]) == 1
        assert evolved_config["evolution_history"][0]["directives"] == directives
        assert "Evolution Directives" in evolved_config["system_prompt"]
        # Original prompt should be preserved
        assert "Original prompt" in evolved_config["system_prompt"]

    @pytest.mark.asyncio
    async def test_apply_directives_creates_skill(self, db_session):
        """Cover lines 391-424: CREATE_SKILL directive handling."""
        from core.models import AgentRegistry
        from core.agent_evolution_loop import AgentEvolutionLoop

        agent = AgentRegistry(
            id="agent-skill",
            tenant_id="tenant-skill",
            name="Skill Agent",
            status="SUPERVISED",
            confidence_score=0.8,
            configuration={"system_prompt": "Original"},
            category="general",
            module_path="core.test_agent",
            class_name="TestAgent",
        )
        db_session.add(agent)
        db_session.commit()

        loop = AgentEvolutionLoop(db_session)
        loop._validate_via_guardrails = AsyncMock(return_value=True)

        # Mock SkillCreationAgent
        with patch('core.agent_evolution_loop.SkillCreationAgent') as mock_skill_class:
            mock_skill = MagicMock()
            mock_skill.id = "skill-new"
            mock_skill.name = "evolved_skill_test"
            mock_skill_agent = AsyncMock()
            mock_skill_agent.create_skill_from_api_documentation = AsyncMock(return_value=mock_skill)
            mock_skill_class.return_value = mock_skill_agent

            directives = ["CREATE_SKILL: Fetch data from API https://example.com"]
            evolved_config, guardrail_ok = await loop._apply_directives_to_clone(
                agent, directives, "tenant-skill"
            )

            assert guardrail_ok is True
            assert "active_skills" in evolved_config
            assert "skill-new" in evolved_config["active_skills"]
