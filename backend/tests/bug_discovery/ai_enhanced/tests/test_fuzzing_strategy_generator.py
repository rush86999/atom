"""Unit tests for FuzzingStrategyGenerator."""
import pytest
import json
import tempfile
from pathlib import Path
import sys

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.ai_enhanced.fuzzing_strategy_generator import FuzzingStrategyGenerator
from tests.bug_discovery.ai_enhanced.models.fuzzing_strategy import FuzzingStrategy, BusinessImpact


@pytest.fixture
def sample_coverage_gap_json(tmp_path):
    """Create sample coverage gap JSON for testing."""
    gap_data = {
        "all_gaps": [
            {
                "file": "backend/core/agent_governance_service.py",
                "coverage_pct": 65.0,
                "uncovered_lines": 45,
                "missing_lines": [100, 101, 102, 150, 151, 200],
                "business_impact": "Critical",
                "priority_score": 85.5
            },
            {
                "file": "backend/api/auth_routes.py",
                "coverage_pct": 70.0,
                "uncovered_lines": 30,
                "missing_lines": [50, 51, 52],
                "business_impact": "High",
                "priority_score": 60.0
            }
        ],
        "tier_breakdown": {
            "Critical": {"file_count": 1, "missing_lines": 45}
        }
    }

    gap_file = tmp_path / "gap_analysis.json"
    with open(gap_file, "w") as f:
        json.dump(gap_data, f)

    return str(gap_file)


@pytest.mark.asyncio
class TestFuzzingStrategyGenerator:
    """Test FuzzingStrategyGenerator functionality."""

    async def test_generate_strategies_from_coverage(self, sample_coverage_gap_json):
        """Test strategy generation from coverage gap JSON."""
        generator = FuzzingStrategyGenerator()

        strategies = await generator.generate_strategies_from_coverage(
            coverage_gap_json=sample_coverage_gap_json,
            top_n_files=2,
            min_priority_score=50.0
        )

        assert len(strategies) >= 1  # At least one strategy generated

        strategy = strategies[0]
        assert isinstance(strategy, FuzzingStrategy)
        assert strategy.file_path == "backend/core/agent_governance_service.py"
        assert strategy.business_impact == BusinessImpact.CRITICAL
        assert strategy.priority_score == 85.5
        assert strategy.missing_lines == [100, 101, 102, 150, 151, 200]

    async def test_strategy_validation(self, sample_coverage_gap_json):
        """Test that strategies are validated against codebase."""
        generator = FuzzingStrategyGenerator()

        strategies = await generator.generate_strategies_from_coverage(
            coverage_gap_json=sample_coverage_gap_json
        )

        # All strategies should have validation status
        for strategy in strategies:
            assert hasattr(strategy, "validated")
            assert isinstance(strategy.validated, bool)

    async def test_fallback_strategy_on_llm_failure(self, sample_coverage_gap_json, monkeypatch):
        """Test fallback strategy when LLM fails."""
        generator = FuzzingStrategyGenerator()

        # Mock LLM to fail
        async def failing_generate(*args, **kwargs):
            raise Exception("LLM failed")

        monkeypatch.setattr(generator.llm_service, "generate_completion", failing_generate)

        strategies = await generator.generate_strategies_from_coverage(
            coverage_gap_json=sample_coverage_gap_json
        )

        assert len(strategies) >= 1  # Fallback strategy generated

        strategy = strategies[0]
        assert strategy.confidence_score == 0.5  # Low confidence for fallback
        assert "Generic fuzzing" in strategy.rationale

    def test_infer_endpoint_from_file(self):
        """Test endpoint inference from file paths."""
        generator = FuzzingStrategyGenerator()

        assert generator._infer_endpoint_from_file("backend/core/agent_governance_service.py") == "/api/v1/agents"
        assert generator._infer_endpoint_from_file("backend/api/auth_routes.py") == "/api/v1/auth"
        assert generator._infer_endpoint_from_file("backend/tools/canvas_tool.py") == "/api/v1/canvas"
        assert generator._infer_endpoint_from_file("backend/unknown.py") == "/api/v1/generic"

    def test_get_test_file_for_endpoint(self):
        """Test test file mapping for endpoints."""
        generator = FuzzingStrategyGenerator()

        assert "test_auth_api_fuzzing.py" in generator._get_test_file_for_endpoint("/api/v1/auth")
        assert "test_agent_api_fuzzing.py" in generator._get_test_file_for_endpoint("/api/v1/agents")
        assert "test_canvas_presentation_fuzzing.py" in generator._get_test_file_for_endpoint("/api/v1/canvas")

    def test_validate_strategy_against_codebase(self):
        """Test strategy validation against codebase."""
        generator = FuzzingStrategyGenerator()

        # Valid test file
        assert generator._validate_strategy_against_codebase(
            "/api/v1/agents",
            "backend/tests/fuzzing/test_agent_api_fuzzing.py"
        )

        # Invalid endpoint format
        assert not generator._validate_strategy_against_codebase(
            "invalid-endpoint",
            "backend/tests/fuzzing/test_agent_api_fuzzing.py"
        )

    @pytest.mark.asyncio
    async def test_save_strategies(self, tmp_path):
        """Test saving strategies to JSON files."""
        generator = FuzzingStrategyGenerator()

        strategies = [
            FuzzingStrategy(
                file_path="backend/test.py",
                missing_lines=[1, 2, 3],
                business_impact=BusinessImpact.HIGH,
                priority_score=75.0,
                target_endpoint="/api/v1/test",
                test_file="backend/tests/fuzzing/test_test.py",
                fuzz_target="param",
                suggested_inputs=["null"],
                iterations=5000,
                rationale="Test",
                confidence_score=0.8
            )
        ]

        saved_paths = await generator.save_strategies(strategies, output_dir=str(tmp_path))

        assert len(saved_paths) == 1
        assert Path(saved_paths[0]).exists()

        # Verify JSON content
        with open(saved_paths[0]) as f:
            data = json.load(f)
            assert data["target_endpoint"] == "/api/v1/test"

    def test_extract_code_snippet(self):
        """Test code snippet extraction."""
        generator = FuzzingStrategyGenerator()

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as f:
            f.write("line 1\nline 2\nline 3\nline 4\nline 5\n")
            temp_path = f.name

        try:
            snippet = generator._extract_code_snippet(temp_path, [2, 3])
            assert "line 1" in snippet or "line 4" in snippet  # Context around missing lines
        finally:
            Path(temp_path).unlink()

    async def test_iterations_by_business_impact(self, sample_coverage_gap_json):
        """Test iterations assigned based on business impact."""
        generator = FuzzingStrategyGenerator()

        strategies = await generator.generate_strategies_from_coverage(
            coverage_gap_json=sample_coverage_gap_json
        )

        # Critical impact should have more iterations
        critical_strategies = [s for s in strategies if s.business_impact == BusinessImpact.CRITICAL]
        if critical_strategies:
            assert critical_strategies[0].iterations >= 5000  # High for critical
