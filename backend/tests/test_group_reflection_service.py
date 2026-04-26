"""
Test suite for group_reflection_service.py

Group reflection service for collective learning and evolution directives.
Target file: backend/core/group_reflection_service.py (709 lines)
Target tests: 20-25 tests
Coverage target: 25-30%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass, field

# Import target module classes
from core.group_reflection_service import (
    DomainProfile,
    DomainProfileRegistry,
    GroupReflectionService,
    MIN_QUALITY_SCORE,
    PERF_WEIGHT,
    NOVELTY_WEIGHT,
    DOMAIN_PROFILES,
)


class TestDomainProfile:
    """Test DomainProfile dataclass."""

    def test_domain_profile_creation(self):
        """DomainProfile can be created with valid parameters."""
        profile = DomainProfile(
            name="Engineering",
            success_label="Tests pass",
            failure_label="Tests fail",
            patch_label="Code diff",
            prompt_preamble="These are coding agents"
        )
        assert profile.name == "Engineering"
        assert profile.success_label == "Tests pass"
        assert profile.failure_label == "Tests fail"

    def test_domain_profile_defaults(self):
        """DomainProfile uses correct default values."""
        profile = DomainProfile(
            name="Test",
            success_label="Success",
            failure_label="Failure",
            patch_label="Patch",
            prompt_preamble="Preamble"
        )
        assert profile.experience_fieldname == "task_log"
        assert profile.tool_vocab == []
        assert profile.quality_weight == 1.0

    def test_domain_profile_with_optional_fields(self):
        """DomainProfile handles optional extract_signal function."""
        def custom_extractor(log: str) -> Optional[str]:
            return "extracted"

        profile = DomainProfile(
            name="Custom",
            success_label="Success",
            failure_label="Failure",
            patch_label="Patch",
            prompt_preamble="Preamble",
            extract_signal=custom_extractor,
            tool_vocab=["tool1", "tool2"],
            quality_weight=1.5
        )
        assert profile.extract_signal is not None
        assert profile.tool_vocab == ["tool1", "tool2"]
        assert profile.quality_weight == 1.5


class TestDomainProfileRegistry:
    """Test DomainProfileRegistry class."""

    def test_resolve_engineering_profile(self):
        """DomainProfileRegistry resolves engineering domain profile."""
        profile = DomainProfileRegistry.resolve("engineering")
        assert profile.name == "Software Engineering"
        assert "code" in profile.patch_label.lower()

    def test_resolve_crm_profile(self):
        """DomainProfileRegistry resolves CRM domain profile."""
        profile = DomainProfileRegistry.resolve("crm")
        assert profile.name == "CRM & Sales Outreach"
        assert "email" in profile.success_label.lower() or "deal" in profile.success_label.lower()

    def test_resolve_finance_profile(self):
        """DomainProfileRegistry resolves finance domain profile."""
        profile = DomainProfileRegistry.resolve("finance")
        assert profile.name == "Financial Operations"
        assert "reconcil" in profile.success_label.lower() or "account" in profile.success_label.lower()

    def test_resolve_case_insensitive(self):
        """DomainProfileRegistry.resolve is case-insensitive."""
        profile1 = DomainProfileRegistry.resolve("Engineering")
        profile2 = DomainProfileRegistry.resolve("ENGINEERING")
        profile3 = DomainProfileRegistry.resolve("EnGiNeErInG")
        assert profile1.name == profile2.name == profile3.name

    def test_resolve_unknown_domain_returns_generic(self):
        """DomainProfileRegistry returns generic profile for unknown domains."""
        profile = DomainProfileRegistry.resolve("unknown_domain_xyz")
        assert profile.name == "General Purpose"

    def test_resolve_none_returns_generic(self):
        """DomainProfileRegistry returns generic profile for None."""
        profile = DomainProfileRegistry.resolve(None)
        assert profile.name == "General Purpose"

    def test_list_domains(self):
        """DomainProfileRegistry lists all registered domains."""
        domains = DomainProfileRegistry.list_domains()
        assert isinstance(domains, list)
        assert len(domains) > 0
        assert "engineering" in domains
        assert "crm" in domains


class TestGroupReflectionService:
    """Test GroupReflectionService class."""

    def test_service_initialization(self):
        """GroupReflectionService initializes with database session."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)
            assert service.db is mock_db

    def test_list_supported_domains(self):
        """GroupReflectionService lists all supported domains."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)
            domains = service.list_supported_domains()
            assert isinstance(domains, list)
            assert len(domains) > 0

    def test_register_domain(self):
        """GroupReflectionService can register new domain at runtime."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            # Create custom profile
            custom_profile = DomainProfile(
                name="Legal",
                success_label="Clause extracted",
                failure_label="Clause missed",
                patch_label="Rule change",
                prompt_preamble="Legal document review agents"
            )

            GroupReflectionService.register_domain("legal", custom_profile)

            # Verify it's registered
            profile = DomainProfileRegistry.resolve("legal")
            assert profile.name == "Legal"


class TestGatherGroupExperiencePool:
    """Test gather_group_experience_pool method."""

    def test_gather_pool_with_no_traces(self):
        """GroupReflectionService handles empty trace pool."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            pool = service.gather_group_experience_pool(["agent-001", "agent-002"])

            assert pool["agent_count"] == 2
            assert pool["trace_count"] == 0

    def test_gather_pool_with_traces(self):
        """GroupReflectionService gathers experience from traces."""
        # Create mock trace
        mock_trace = MagicMock()
        mock_trace.is_high_quality = True
        mock_trace.benchmark_score = 0.8
        mock_trace.tool_use_log = [
            {"tool_name": "bash", "success": True},
            {"tool_name": "search", "success": False}
        ]
        mock_trace.task_log = "Test log content"
        mock_trace.benchmark_passed = True
        mock_trace.model_patch = "def fixed_function():\n    return True"
        mock_trace.evolving_requirements = "Previous directive"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_trace]

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            pool = service.gather_group_experience_pool(["agent-001"])

            assert pool["trace_count"] == 1
            assert len(pool["tool_patterns"]) == 2
            assert len(pool["task_log_excerpts"]) > 0

    def test_gather_pool_filters_low_quality_traces(self):
        """GroupReflectionService filters out low-quality traces."""
        # Create low-quality trace
        mock_trace_low = MagicMock()
        mock_trace_low.is_high_quality = False
        mock_trace_low.benchmark_score = 0.2

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_trace_low]

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            pool = service.gather_group_experience_pool(["agent-001"])

            # Should be filtered out
            assert pool["trace_count"] == 0
            assert pool["filtered_count"] == 1

    def test_gather_pool_dedupes_patches(self):
        """GroupReflectionService deduplicates successful patches."""
        # Create traces with identical patches
        patch_text = "def fixed():\n    pass"

        mock_trace1 = MagicMock()
        mock_trace1.is_high_quality = True
        mock_trace1.benchmark_score = 0.8
        mock_trace1.tool_use_log = None
        mock_trace1.task_log = None
        mock_trace1.benchmark_passed = True
        mock_trace1.model_patch = patch_text
        mock_trace1.evolving_requirements = None

        mock_trace2 = MagicMock()
        mock_trace2.is_high_quality = True
        mock_trace2.benchmark_score = 0.8
        mock_trace2.tool_use_log = None
        mock_trace2.task_log = None
        mock_trace2.benchmark_passed = True
        mock_trace2.model_patch = patch_text  # Same patch
        mock_trace2.evolving_requirements = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_trace1, mock_trace2]

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            pool = service.gather_group_experience_pool(["agent-001"])

            # Should have only 1 unique patch
            assert len(pool["successful_patches"]) == 1


class TestReflectAndGenerateDirectives:
    """Test reflect_and_generate_directives method."""

    @pytest.mark.asyncio
    async def test_reflect_with_empty_pool(self):
        """GroupReflectionService handles empty pool gracefully."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service') as mock_llm:
            mock_llm_service = AsyncMock()
            mock_llm.return_value = mock_llm_service
            service = GroupReflectionService(mock_db)

            empty_pool = {
                "agent_count": 0,
                "trace_count": 0,
                "tool_patterns": [],
                "task_log_excerpts": [],
                "successful_patches": [],
                "evolving_requirements": [],
                "filtered_count": 0,
                "_domain_profile": DomainProfileRegistry.resolve("engineering"),
                "_category": "engineering"
            }

            directives = await service.reflect_and_generate_directives(empty_pool)

            # Should return bootstrap directive
            assert isinstance(directives, list)
            assert len(directives) > 0

    @pytest.mark.asyncio
    async def test_reflect_generates_directives(self):
        """GroupReflectionService generates evolution directives."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service') as mock_llm:
            mock_llm_service = AsyncMock()
            mock_llm_service.generate_response.return_value = "1. Add error handling\n2. Improve caching\n3. Fix race condition"
            mock_llm.return_value = mock_llm_service

            service = GroupReflectionService(mock_db)

            pool = {
                "agent_count": 2,
                "trace_count": 5,
                "tool_patterns": [
                    {"tool_name": "bash", "success": True, "agent_id": "agent-001"}
                ],
                "task_log_excerpts": ["Error: file not found"],
                "successful_patches": ["def fix(): pass"],
                "evolving_requirements": [],
                "filtered_count": 0,
                "_domain_profile": DomainProfileRegistry.resolve("engineering"),
                "_category": "engineering"
            }

            directives = await service.reflect_and_generate_directives(pool)

            assert isinstance(directives, list)
            assert len(directives) > 0
            # Should parse numbered list
            assert any("error handling" in d.lower() for d in directives)

    @pytest.mark.asyncio
    async def test_reflect_handles_llm_failure(self):
        """GroupReflectionService handles LLM call failure gracefully."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service') as mock_llm:
            mock_llm_service = AsyncMock()
            mock_llm_service.generate_response.side_effect = Exception("LLM error")
            mock_llm.return_value = mock_llm_service

            service = GroupReflectionService(mock_db)

            pool = {
                "agent_count": 1,
                "trace_count": 1,
                "tool_patterns": [],
                "task_log_excerpts": [],
                "successful_patches": [],
                "evolving_requirements": [],
                "filtered_count": 0,
                "_domain_profile": DomainProfileRegistry.resolve("engineering"),
                "_category": "engineering"
            }

            directives = await service.reflect_and_generate_directives(pool)

            # Should return fallback directive
            assert isinstance(directives, list)
            assert len(directives) > 0


class TestHelperMethods:
    """Test internal helper methods."""

    def test_detect_category_from_agent(self):
        """GroupReflectionService detects agent category from database."""
        mock_agent = MagicMock()
        mock_agent.category = "crm"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_agent

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            category = service._detect_category(["agent-001"])

            assert category == "crm"

    def test_detect_category_no_agents(self):
        """GroupReflectionService handles empty agent list."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            category = service._detect_category([])

            assert category is None

    def test_passes_quality_gate_high_quality(self):
        """GroupReflectionService passes high-quality traces."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            mock_trace = MagicMock()
            mock_trace.is_high_quality = True
            mock_trace.benchmark_score = 0.8

            passes = service._passes_quality_gate(mock_trace, 0.3)

            assert passes is True

    def test_passes_quality_gate_low_quality(self):
        """GroupReflectionService fails low-quality traces."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            mock_trace = MagicMock()
            mock_trace.is_high_quality = False
            mock_trace.benchmark_score = 0.2

            passes = service._passes_quality_gate(mock_trace, 0.3)

            assert passes is False

    def test_summarize_tool_patterns(self):
        """GroupReflectionService summarizes tool usage patterns."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            profile = DomainProfileRegistry.resolve("engineering")

            patterns = [
                {"tool_name": "bash", "success": True, "agent_id": "agent-001"},
                {"tool_name": "bash", "success": True, "agent_id": "agent-001"},
                {"tool_name": "bash", "success": False, "agent_id": "agent-002"},
                {"tool_name": "search", "success": True, "agent_id": "agent-001"}
            ]

            summary = service._summarize_tool_patterns(patterns, profile)

            assert "bash" in summary
            assert "search" in summary
            assert "66%" in summary or "67%" in summary  # 2/3 success rate

    def test_parse_directives(self):
        """GroupReflectionService parses directives from LLM response."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            response = """1. Add error handling to API calls
2. Implement caching for frequently accessed data
3. Optimize database queries with indexes"""

            directives = service._parse_directives(response, 5)

            assert len(directives) == 3
            assert "error handling" in directives[0].lower()
            assert "caching" in directives[1].lower()

    def test_parse_directives_with_bullet_points(self):
        """GroupReflectionService parses bullet point directives."""
        mock_db = MagicMock()

        with patch('core.group_reflection_service.ServiceFactory.get_llm_service'):
            service = GroupReflectionService(mock_db)

            response = """- Improve error handling
- Add retry logic
- Optimize performance"""

            directives = service._parse_directives(response, 5)

            assert len(directives) == 3


class TestQualityConstants:
    """Test quality gate constants."""

    def test_min_quality_score(self):
        """MIN_QUALITY_SCORE is set appropriately."""
        assert 0 < MIN_QUALITY_SCORE < 1.0

    def test_performance_weight(self):
        """PERF_WEIGHT is set appropriately."""
        assert 0 < PERF_WEIGHT < 1.0

    def test_novelty_weight(self):
        """NOVELTY_WEIGHT is set appropriately."""
        assert 0 < NOVELTY_WEIGHT < 1.0

    def test_weights_sum_to_one(self):
        """Performance and novelty weights sum to 1.0."""
        assert abs((PERF_WEIGHT + NOVELTY_WEIGHT) - 1.0) < 0.01


class TestBuiltInDomainProfiles:
    """Test built-in domain profile registry."""

    def test_engineering_profile_exists(self):
        """Engineering profile is registered."""
        assert "engineering" in DOMAIN_PROFILES

    def test_crm_profile_exists(self):
        """CRM profile is registered."""
        assert "crm" in DOMAIN_PROFILES

    def test_finance_profile_exists(self):
        """Finance profile is registered."""
        assert "finance" in DOMAIN_PROFILES

    def test_support_profile_exists(self):
        """Support profile is registered."""
        assert "support" in DOMAIN_PROFILES

    def test_marketing_profile_exists(self):
        """Marketing profile is registered."""
        assert "marketing" in DOMAIN_PROFILES

    def test_scheduling_profile_exists(self):
        """Scheduling profile is registered."""
        assert "scheduling" in DOMAIN_PROFILES

    def test_domain_aliases_exist(self):
        """Domain aliases are registered."""
        assert "software" in DOMAIN_PROFILES  # Alias for engineering
        assert "dev" in DOMAIN_PROFILES  # Alias for engineering
        assert "calendar" in DOMAIN_PROFILES  # Alias for scheduling


class TestSignalExtractionHelpers:
    """Test domain-specific signal extraction helpers."""

    def test_extract_error_lines_finds_error(self):
        """extract_error_lines finds lines containing error keyword."""
        from core.group_reflection_service import _extract_error_lines

        log = "Starting process\nProcessing data\nError: file not found\nContinuing"
        result = _extract_error_lines(log, "error")

        assert result is not None
        assert "Error: file not found" in result

    def test_extract_error_lines_returns_tail(self):
        """extract_error_lines returns tail of log if keyword not found."""
        from core.group_reflection_service import _extract_error_lines

        log = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        result = _extract_error_lines(log, "error")

        # Should return last characters
        assert result is not None

    def test_extract_traceback_finds_traceback(self):
        """extract_traceback finds Python traceback."""
        from core.group_reflection_service import _extract_traceback

        log = "Processing data\nTraceback (most recent call last):\n  File 'test.py', line 10\nValueError"
        result = _extract_traceback(log)

        assert result is not None
        assert "Traceback" in result

    def test_extract_email_signal_finds_email_signals(self):
        """extract_email_signal finds email-related signals."""
        from core.group_reflection_service import _extract_email_signal

        log = "Email sent\nBounced: user@example.com\nOpened: click tracking"
        result = _extract_email_signal(log)

        assert result is not None
        assert "bounce" in result.lower() or "open" in result.lower()
