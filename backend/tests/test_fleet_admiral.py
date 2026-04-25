"""
Tests for FleetAdmiral - dynamic agent recruitment orchestrator.

Tests cover:
- Task analysis with various complexities (low, medium, high)
- Fleet recruitment with specialist agents
- Fleet coordination and task distribution
- Blackboard state management
- Task execution with fleet orchestration
- Error handling (recruitment failures, task failures)
- LLM-based task analysis with mock responses
- Delegation chain creation and tracking

TDD Pattern: AsyncMock for async methods, patch at import location
"""

import os
import sys
os.environ["TESTING"] = "1"

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from sqlalchemy.orm import Session

# Mock the missing modules before importing
sys_modules = [
    'core.specialist_matcher',
    'core.recruitment_analytics_service',
    'analytics.fleet_optimization_service'
]

for mod in sys_modules:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from core.fleet_admiral import FleetAdmiral, TaskAnalysis
from core.models import DelegationChain, ChainLink, AgentRegistry


class TestTaskAnalysis:
    """Test task analysis functionality."""

    @pytest.mark.asyncio
    async def test_analyze_simple_task_low_complexity(self):
        """Test analysis of a simple task with low complexity."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        # Mock LLM response for simple task
        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="low",
                required_capabilities=["general"],
                estimated_duration="5 minutes",
                specialist_count=1,
                reasoning="Simple task requiring general assistance"
            )
        )

        admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

        result = await admiral.analyze_task_requirements(
            task="What is the weather today?",
            user_id="user-123"
        )

        assert result["complexity"] == "low"
        assert result["specialist_count"] == 1
        assert "general" in result["required_capabilities"]
        assert result["estimated_duration"] == "5 minutes"

    @pytest.mark.asyncio
    async def test_analyze_medium_complexity_task(self):
        """Test analysis of a medium complexity task."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="medium",
                required_capabilities=["data_analysis", "reporting"],
                estimated_duration="30 minutes",
                specialist_count=2,
                reasoning="Task requires data analysis and reporting"
            )
        )

        admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

        result = await admiral.analyze_task_requirements(
            task="Analyze last month's sales data and create a report",
            user_id="user-456"
        )

        assert result["complexity"] == "medium"
        assert result["specialist_count"] == 2
        assert "data_analysis" in result["required_capabilities"]
        assert "reporting" in result["required_capabilities"]

    @pytest.mark.asyncio
    async def test_analyze_complex_multistep_task(self):
        """Test analysis of a complex multi-step task."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="high",
                required_capabilities=["web_scraping", "data_analysis", "integration", "reporting"],
                estimated_duration="2-3 hours",
                specialist_count=5,
                reasoning="Complex task requiring multiple specialists and coordination"
            )
        )

        admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

        result = await admiral.analyze_task_requirements(
            task="Research competitors, scrape their websites, analyze pricing, and integrate with our CRM",
            user_id="user-789"
        )

        assert result["complexity"] == "high"
        assert result["specialist_count"] == 5
        assert len(result["required_capabilities"]) == 4
        assert "web_scraping" in result["required_capabilities"]
        assert "integration" in result["required_capabilities"]

    @pytest.mark.asyncio
    async def test_analyze_task_with_llm_failure_fallback(self):
        """Test fallback behavior when LLM analysis fails."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        # Mock LLM failure
        mock_llm.generate_structured_response = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )

        admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

        result = await admiral.analyze_task_requirements(
            task="Any task",
            user_id="user-000"
        )

        # Should return default fallback values
        assert result["complexity"] == "medium"
        assert result["specialist_count"] == 2
        assert result["estimated_duration"] == "30 minutes"
        assert "LLM analysis failed" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_analyze_task_passes_user_id_to_llm(self):
        """Test that user_id is correctly passed to LLM service."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="low",
                required_capabilities=["general"],
                estimated_duration="5 minutes",
                specialist_count=1,
                reasoning="Simple task"
            )
        )

        admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

        await admiral.analyze_task_requirements(
            task="Test task",
            user_id="test-user-abc"
        )

        # Verify user_id was passed to LLM
        mock_llm.generate_structured_response.assert_called_once()
        call_kwargs = mock_llm.generate_structured_response.call_args[1]
        assert call_kwargs["user_id"] == "test-user-abc"


class TestFleetRecruitment:
    """Test fleet recruitment functionality."""

    @pytest.mark.asyncio
    async def test_recruit_fleet_for_simple_task(self):
        """Test recruiting a small fleet for a simple task."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        # Mock task analysis
        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="low",
                required_capabilities=["general"],
                estimated_duration="5 minutes",
                specialist_count=1,
                reasoning="Simple task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            # Mock chain initialization
            mock_chain = Mock()
            mock_chain.id = "chain-001"
            mock_chain.status = "active"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                # Mock recruitment success
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": [
                            {
                                "agent_id": "specialist-001",
                                "agent_name": "General Assistant",
                                "domain": "general",
                                "capability_score": 0.95
                            }
                        ]
                    }
                )

                # Mock member recruitment
                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                result = await admiral.recruit_and_execute(
                    task="Simple task",
                    user_id="user-123"
                )

                assert result["chain_id"] == "chain-001"
                assert result["specialists_count"] == 1
                assert result["fleet_status"] == "active"
                assert len(result["specialists"]) == 1

    @pytest.mark.asyncio
    async def test_recruit_fleet_with_multiple_specialists(self):
        """Test recruiting multiple specialists for complex task."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="high",
                required_capabilities=["data_analysis", "integration", "reporting"],
                estimated_duration="2 hours",
                specialist_count=3,
                reasoning="Complex task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-002"
            mock_chain.status = "active"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": [
                            {
                                "agent_id": "specialist-001",
                                "agent_name": "Data Analyst",
                                "domain": "data_analysis",
                                "capability_score": 0.92
                            },
                            {
                                "agent_id": "specialist-002",
                                "agent_name": "Integration Specialist",
                                "domain": "integration",
                                "capability_score": 0.88
                            },
                            {
                                "agent_id": "specialist-003",
                                "agent_name": "Report Generator",
                                "domain": "reporting",
                                "capability_score": 0.90
                            }
                        ]
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                result = await admiral.recruit_and_execute(
                    task="Complex multi-step task",
                    user_id="user-456"
                )

                assert result["specialists_count"] == 3
                assert len(result["specialists"]) == 3
                assert result["fleet_status"] == "active"

    @pytest.mark.asyncio
    async def test_recruit_fleet_with_custom_root_agent(self):
        """Test recruiting fleet with custom root agent ID."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="medium",
                required_capabilities=["analysis"],
                estimated_duration="1 hour",
                specialist_count=2,
                reasoning="Medium task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-003"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": []
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                result = await admiral.recruit_and_execute(
                    task="Test task",
                    user_id="user-789",
                    root_agent_id="custom-root-agent"
                )

                # Verify custom root agent was used
                mock_fleet_service.initialize_fleet.assert_called_once()
                call_kwargs = mock_fleet_service.initialize_fleet.call_args[1]
                assert call_kwargs["root_agent_id"] == "custom-root-agent"

    @pytest.mark.asyncio
    async def test_recruit_fleet_handles_recruitment_failure(self):
        """Test handling of recruitment failures."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="medium",
                required_capabilities=["analysis"],
                estimated_duration="1 hour",
                specialist_count=2,
                reasoning="Medium task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-fail-001"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                # Mock recruitment failure
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": False,
                        "error": "No suitable specialists found"
                    }
                )

                mock_fleet_service.complete_chain = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                result = await admiral.recruit_and_execute(
                    task="Impossible task",
                    user_id="user-999"
                )

                assert result["fleet_status"] == "failed"
                assert result["specialists_count"] == 0
                assert "error" in result
                # Verify chain was marked as failed
                mock_fleet_service.complete_chain.assert_called_once_with("chain-fail-001", "failed")


class TestBlackboardManagement:
    """Test blackboard state management."""

    @pytest.mark.asyncio
    async def test_blackboard_updated_with_task_analysis(self):
        """Test that blackboard is updated with task analysis."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        task_analysis_result = {
            "complexity": "high",
            "required_capabilities": ["web_scraping", "analysis"],
            "estimated_duration": "2 hours",
            "specialist_count": 3,
            "reasoning": "Complex task"
        }

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(**task_analysis_result)
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-bb-001"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": [
                            {
                                "agent_id": "spec-001",
                                "agent_name": "Web Scraper",
                                "domain": "web_scraping"
                            }
                        ]
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                await admiral.recruit_and_execute(
                    task="Complex task",
                    user_id="user-bb-123"
                )

                # Verify blackboard was updated with task analysis
                mock_fleet_service.update_blackboard.assert_called_once()
                call_args = mock_fleet_service.update_blackboard.call_args
                updates = call_args[1]["updates"]

                assert "task_analysis" in updates
                assert updates["task_analysis"]["complexity"] == "high"
                assert updates["recruitment_phase"] == "complete"

    @pytest.mark.asyncio
    async def test_blackboard_tracks_recruitment_completion_time(self):
        """Test that blackboard tracks recruitment completion timestamp."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="medium",
                required_capabilities=["analysis"],
                estimated_duration="1 hour",
                specialist_count=2,
                reasoning="Medium task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-bb-002"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": []
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                before_recruitment = datetime.now(timezone.utc)

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                await admiral.recruit_and_execute(
                    task="Test task",
                    user_id="user-bb-456"
                )

                after_recruitment = datetime.now(timezone.utc)

                # Verify blackboard was updated with timestamp
                mock_fleet_service.update_blackboard.assert_called_once()
                call_args = mock_fleet_service.update_blackboard.call_args
                updates = call_args[1]["updates"]

                assert "recruitment_completed_at" in updates
                # Verify timestamp is valid ISO format
                completion_time = datetime.fromisoformat(updates["recruitment_completed_at"])
                assert before_recruitment <= completion_time <= after_recruitment

    @pytest.mark.asyncio
    async def test_blackboard_tracks_recruited_specialists(self):
        """Test that blackboard tracks all recruited specialists."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="high",
                required_capabilities=["analysis", "integration", "reporting"],
                estimated_duration="2 hours",
                specialist_count=3,
                reasoning="Complex task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-bb-003"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                specialists = [
                    {"agent_id": "spec-001", "agent_name": "Analyst", "domain": "analysis"},
                    {"agent_id": "spec-002", "agent_name": "Integrator", "domain": "integration"},
                    {"agent_id": "spec-003", "agent_name": "Reporter", "domain": "reporting"}
                ]

                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": specialists
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                await admiral.recruit_and_execute(
                    task="Complex task",
                    user_id="user-bb-789"
                )

                # Verify blackboard tracks all specialists
                mock_fleet_service.update_blackboard.assert_called_once()
                call_args = mock_fleet_service.update_blackboard.call_args
                updates = call_args[1]["updates"]

                assert "specialists_recruited" in updates
                assert len(updates["specialists_recruited"]) == 3

                # Verify each specialist is tracked
                for i, spec in enumerate(updates["specialists_recruited"]):
                    assert "agent_id" in spec
                    assert "agent_name" in spec
                    assert "domain" in spec


class TestDelegationChain:
    """Test delegation chain creation and tracking."""

    @pytest.mark.asyncio
    async def test_chain_initialized_with_task_analysis_metadata(self):
        """Test that delegation chain is initialized with task analysis metadata."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="high",
                required_capabilities=["analysis"],
                estimated_duration="2 hours",
                specialist_count=3,
                reasoning="Complex task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-dc-001"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": []
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                await admiral.recruit_and_execute(
                    task="Complex task",
                    user_id="user-dc-123"
                )

                # Verify chain was initialized with task analysis metadata
                mock_fleet_service.initialize_fleet.assert_called_once()
                call_kwargs = mock_fleet_service.initialize_fleet.call_args[1]

                assert "initial_metadata" in call_kwargs
                metadata = call_kwargs["initial_metadata"]
                assert "task_analysis" in metadata
                assert metadata["recruitment_phase"] == "in_progress"

    @pytest.mark.asyncio
    async def test_chain_links_created_for_each_specialist(self):
        """Test that chain links are created for each recruited specialist."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="medium",
                required_capabilities=["analysis", "reporting"],
                estimated_duration="1 hour",
                specialist_count=2,
                reasoning="Medium task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-dc-002"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": [
                            {
                                "agent_id": "spec-001",
                                "agent_name": "Analyst",
                                "domain": "analysis",
                                "capability_score": 0.95
                            },
                            {
                                "agent_id": "spec-002",
                                "agent_name": "Reporter",
                                "domain": "reporting",
                                "capability_score": 0.90
                            }
                        ]
                    }
                )

                # Track recruit_member calls
                recruit_calls = []
                def capture_recruit(*args, **kwargs):
                    recruit_calls.append((args, kwargs))
                    return Mock()
                mock_fleet_service.recruit_member = Mock(side_effect=capture_recruit)
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                await admiral.recruit_and_execute(
                    task="Medium task",
                    user_id="user-dc-456"
                )

                # Verify 2 chain links were created
                assert len(recruit_calls) == 2

                # Verify each link has correct parameters
                for i, call in enumerate(recruit_calls):
                    args, kwargs = call
                    # recruit_member is called with keyword arguments only
                    assert kwargs["chain_id"] == "chain-dc-002"
                    assert kwargs["parent_agent_id"] == "atom_main"
                    assert "link_order" in kwargs
                    assert kwargs["link_order"] == i

    @pytest.mark.asyncio
    async def test_chain_id_returned_in_result(self):
        """Test that chain ID is returned in recruitment result."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="low",
                required_capabilities=["general"],
                estimated_duration="5 minutes",
                specialist_count=1,
                reasoning="Simple task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "expected-chain-id"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": []
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                result = await admiral.recruit_and_execute(
                    task="Simple task",
                    user_id="user-dc-789"
                )

                assert result["chain_id"] == "expected-chain-id"


class TestRecruitmentIntelligence:
    """Test recruitment intelligence integration."""

    @pytest.mark.asyncio
    async def test_recruitment_intelligence_lazy_initialized(self):
        """Test that recruitment intelligence is lazily initialized."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            # Create admiral - recruitment intelligence should not be initialized yet
            admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

            assert admiral.recruitment_intelligence is None

            # Now trigger recruitment
            mock_llm.generate_structured_response = AsyncMock(
                return_value=TaskAnalysis(
                    complexity="low",
                    required_capabilities=["general"],
                    estimated_duration="5 minutes",
                    specialist_count=1,
                    reasoning="Simple task"
                )
            )

            mock_chain = Mock()
            mock_chain.id = "chain-ri-001"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_instance = Mock()
                mock_recruit_class.return_value = mock_recruit_instance

                mock_recruit_instance.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": []
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                await admiral.recruit_and_execute(
                    task="Test task",
                    user_id="user-ri-123"
                )

                # After recruitment, intelligence should be initialized
                assert admiral.recruitment_intelligence is not None

    @pytest.mark.asyncio
    async def test_recruitment_passes_chain_context(self):
        """Test that recruitment is called with chain context."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="medium",
                required_capabilities=["analysis"],
                estimated_duration="1 hour",
                specialist_count=2,
                reasoning="Medium task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-ctx-001"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_instance = Mock()
                mock_recruit_class.return_value = mock_recruit_instance

                # Track orchestrate_recruitment call
                recruitment_call = None
                async def mock_orchestrate(**kwargs):
                    nonlocal recruitment_call
                    recruitment_call = kwargs
                    return {"success": True, "recruitment_roster": []}

                mock_recruit_instance.orchestrate_recruitment = mock_orchestrate

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                await admiral.recruit_and_execute(
                    task="Test task",
                    user_id="user-ctx-456"
                )

                # Verify recruitment was called with chain context
                assert recruitment_call is not None
                assert recruitment_call["context"]["chain_id"] == "chain-ctx-001"
                assert recruitment_call["chain_id"] == "chain-ctx-001"

    @pytest.mark.asyncio
    async def test_recruitment_respects_max_specialists_from_analysis(self):
        """Test that max_specialists parameter is set from task analysis."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="high",
                required_capabilities=["analysis", "integration", "reporting"],
                estimated_duration="3 hours",
                specialist_count=5,
                reasoning="Complex task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-ms-001"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_instance = Mock()
                mock_recruit_class.return_value = mock_recruit_instance

                # Track orchestrate_recruitment call
                recruitment_call = None
                async def mock_orchestrate(**kwargs):
                    nonlocal recruitment_call
                    recruitment_call = kwargs
                    return {"success": True, "recruitment_roster": []}

                mock_recruit_instance.orchestrate_recruitment = mock_orchestrate

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                await admiral.recruit_and_execute(
                    task="Complex task",
                    user_id="user-ms-789"
                )

                # Verify max_specialists matches task analysis
                assert recruitment_call["max_specialists"] == 5


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_handles_empty_recruitment_roster(self):
        """Test handling of empty recruitment roster."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="low",
                required_capabilities=["general"],
                estimated_duration="5 minutes",
                specialist_count=1,  # Must be >= 1 per TaskAnalysis validation
                reasoning="No specialists needed but minimum is 1"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-er-001"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": []
                    }
                )

                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                result = await admiral.recruit_and_execute(
                    task="Simple task",
                    user_id="user-er-123"
                )

                assert result["specialists_count"] == 0
                assert len(result["specialists"]) == 0

    @pytest.mark.asyncio
    async def test_handles_task_analysis_timeout(self):
        """Test handling of LLM timeout during task analysis."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        # Mock LLM timeout
        import asyncio
        mock_llm.generate_structured_response = AsyncMock(
            side_effect=asyncio.TimeoutError("LLM request timed out")
        )

        admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

        result = await admiral.analyze_task_requirements(
            task="Timeout task",
            user_id="user-er-456"
        )

        # Should return fallback values
        assert result["complexity"] == "medium"
        assert "LLM analysis failed" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_specialist_domain_tracked_in_results(self):
        """Test that specialist domains are properly tracked in results."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="high",
                required_capabilities=["analysis", "integration"],
                estimated_duration="2 hours",
                specialist_count=2,
                reasoning="Complex task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-er-002"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": [
                            {
                                "agent_id": "spec-001",
                                "agent_name": "Data Analyst",
                                "domain": "data_analysis",
                                "capability_score": 0.95
                            },
                            {
                                "agent_id": "spec-002",
                                "agent_name": "API Integrator",
                                "domain": "api_integration",
                                "capability_score": 0.88
                            }
                        ]
                    }
                )

                mock_fleet_service.recruit_member = Mock(return_value=Mock())
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                result = await admiral.recruit_and_execute(
                    task="Complex task",
                    user_id="user-er-789"
                )

                # Verify domains are tracked in results
                specialists = result["specialists"]
                assert len(specialists) == 2
                assert specialists[0]["domain"] == "data_analysis"
                assert specialists[1]["domain"] == "api_integration"

    @pytest.mark.asyncio
    async def test_optimization_metadata_passed_to_specialists(self):
        """Test that optimization metadata is passed when recruiting specialists."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.generate_structured_response = AsyncMock(
            return_value=TaskAnalysis(
                complexity="medium",
                required_capabilities=["analysis"],
                estimated_duration="1 hour",
                specialist_count=1,
                reasoning="Medium task"
            )
        )

        with patch('core.fleet_admiral.AgentFleetService') as mock_fleet_service_class:
            mock_fleet_service = Mock()
            mock_fleet_service_class.return_value = mock_fleet_service

            mock_chain = Mock()
            mock_chain.id = "chain-er-003"
            mock_fleet_service.initialize_fleet = Mock(return_value=mock_chain)

            with patch('core.fleet_admiral.RecruitmentIntelligenceService') as mock_recruit_class:
                optimization_metadata = {
                    "priority": "high",
                    "estimated_cost": 0.05,
                    "confidence": 0.92
                }

                mock_recruit_class.return_value.orchestrate_recruitment = AsyncMock(
                    return_value={
                        "success": True,
                        "recruitment_roster": [
                            {
                                "agent_id": "spec-001",
                                "agent_name": "Optimized Analyst",
                                "domain": "analysis",
                                "optimization": optimization_metadata
                            }
                        ]
                    }
                )

                # Track recruit_member calls
                recruit_calls = []
                def mock_recruit(*args, **kwargs):
                    recruit_calls.append((args, kwargs))
                    return Mock()

                mock_fleet_service.recruit_member = mock_recruit
                mock_fleet_service.update_blackboard = Mock()

                admiral = FleetAdmiral(db=mock_db, llm=mock_llm)

                await admiral.recruit_and_execute(
                    task="Optimized task",
                    user_id="user-er-999"
                )

                # Verify optimization metadata was passed
                assert len(recruit_calls) == 1
                args, kwargs = recruit_calls[0]
                assert "context_json" in kwargs
                assert kwargs["context_json"]["optimization"] == optimization_metadata
