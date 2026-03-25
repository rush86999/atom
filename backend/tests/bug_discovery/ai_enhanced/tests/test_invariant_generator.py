"""Unit tests for InvariantGenerator."""
import pytest
import tempfile
from pathlib import Path
import sys

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.ai_enhanced.invariant_generator import InvariantGenerator
from tests.bug_discovery.ai_enhanced.models.invariant_suggestion import InvariantSuggestion, Criticality


@pytest.fixture
def sample_python_file(tmp_path):
    """Create sample Python file for testing."""
    code = '''
"""Sample module for invariant generation."""

from typing import Dict, Any

cache: Dict[str, Any] = {}

def get_from_cache(key: str) -> Any:
    """Get value from cache."""
    return cache.get(key)

def calculate_total(items: list[int]) -> int:
    """Calculate total of items."""
    total = 0
    for item in items:
        total += item
    return total

def set_status(status: str) -> None:
    """Set status."""
    global cache
    cache["status"] = status

def double_value(x: int) -> int:
    """Double a value."""
    return x * 2
'''

    test_file = tmp_path / "sample_module.py"
    test_file.write_text(code)
    return str(test_file)


@pytest.mark.asyncio
class TestInvariantGenerator:
    """Test InvariantGenerator functionality."""

    async def test_generate_invariants_for_file(self, sample_python_file):
        """Test invariant generation from Python file."""
        generator = InvariantGenerator()

        invariants = await generator.generate_invariants_for_file(
            file_path=sample_python_file,
            max_invariants=3
        )

        assert len(invariants) >= 1  # At least one invariant generated
        assert len(invariants) <= 3  # Respects max_invariants

        invariant = invariants[0]
        assert isinstance(invariant, InvariantSuggestion)
        assert invariant.file_path == sample_python_file
        assert invariant.invariant_name
        assert invariant.hypothesis
        assert invariant.formal_specification

    async def test_invariant_validation(self, sample_python_file):
        """Test that invariants are validated."""
        generator = InvariantGenerator()

        invariants = await generator.generate_invariants_for_file(
            file_path=sample_python_file
        )

        # All invariants should have validation status
        for invariant in invariants:
            assert hasattr(invariant, "is_testable")
            assert isinstance(invariant.is_testable, bool)
            assert hasattr(invariant, "validation_errors")

    def test_is_valid_hypothesis_strategy(self):
        """Test Hypothesis strategy validation."""
        generator = InvariantGenerator()

        # Valid strategies
        assert generator._is_valid_hypothesis_strategy("st.text()")
        assert generator._is_valid_hypothesis_strategy("st.integers(min_value=0, max_value=100)")
        assert generator._is_valid_hypothesis_strategy("st.sampled_from([1, 2, 3])")

        # Invalid strategies
        assert not generator._is_valid_hypothesis_strategy("invalid.strategy")
        assert not generator._is_valid_hypothesis_strategy("")

    def test_infer_strategy_from_args(self):
        """Test strategy inference from function arguments."""
        generator = InvariantGenerator()

        # ID arguments -> text strategy
        assert "st.text()" in generator._infer_strategy_from_args(["user_id"])

        # Count arguments -> integers strategy
        assert "st.integers" in generator._infer_strategy_from_args(["count"])

        # Boolean arguments -> booleans strategy
        assert "st.booleans" in generator._infer_strategy_from_args(["is_enabled"])

    def test_get_examples_for_criticality(self):
        """Test examples count by criticality."""
        generator = InvariantGenerator()

        assert generator._get_examples_for_criticality(Criticality.CRITICAL) == 200
        assert generator._get_examples_for_criticality(Criticality.HIGH) == 150
        assert generator._get_examples_for_criticality(Criticality.STANDARD) == 100
        assert generator._get_examples_for_criticality(Criticality.LOW) == 50

    def test_criticality_score_sorting(self):
        """Test criticality scores for sorting."""
        generator = InvariantGenerator()

        assert generator._criticality_score(Criticality.CRITICAL) == 4
        assert generator._criticality_score(Criticality.HIGH) == 3
        assert generator._criticality_score(Criticality.STANDARD) == 2
        assert generator._criticality_score(Criticality.LOW) == 1

    def test_extract_functions_from_ast(self, sample_python_file):
        """Test function extraction from AST."""
        generator = InvariantGenerator()

        with open(sample_python_file) as f:
            import ast
            tree = ast.parse(f.read())

        functions = generator._extract_functions(tree)

        assert len(functions) == 4  # 4 functions in sample file

        func_names = {f["name"] for f in functions}
        assert "get_from_cache" in func_names
        assert "calculate_total" in func_names
        assert "set_status" in func_names
        assert "double_value" in func_names

    def test_write_property_test(self, tmp_path):
        """Test writing property test file."""
        generator = InvariantGenerator()

        invariant = InvariantSuggestion(
            file_path="test.py",
            invariant_name="Test Invariant",
            function_name="test_func",
            hypothesis="Test hypothesis",
            formal_specification="∀ x: P(x)",
            rationale="Test rationale",
            hypothesis_strategy="st.text()",
            criticality=Criticality.HIGH,
            test_skeleton="@given(st.text())\ndef test_func(x):\n    pass",
            suggested_examples=100,
            is_testable=True,
            validation_errors=[]
        )

        test_path = generator.write_property_test(invariant, output_dir=tmp_path)

        assert Path(test_path).exists()
        assert "test_test_invariant.py" in test_path

        # Verify content
        content = Path(test_path).read_text()
        assert "Test Invariant" in content
        assert "@given" in content
        assert "def test_" in content

    @pytest.mark.asyncio
    async def test_save_invariants(self, tmp_path):
        """Test saving invariants to Markdown files."""
        generator = InvariantGenerator()

        invariants = [
            InvariantSuggestion(
                file_path="test.py",
                invariant_name="Invariant 1",
                function_name="func1",
                hypothesis="Hypothesis 1",
                formal_specification="∀ x: P1(x)",
                rationale="Rationale 1",
                hypothesis_strategy="st.text()",
                criticality=Criticality.HIGH,
                test_skeleton="@given(st.text())\ndef test_func1(x): pass",
                suggested_examples=100,
                is_testable=True,
                validation_errors=[]
            ),
            InvariantSuggestion(
                file_path="test.py",
                invariant_name="Invariant 2",
                function_name="func2",
                hypothesis="Hypothesis 2",
                formal_specification="∀ x: P2(x)",
                rationale="Rationale 2",
                hypothesis_strategy="st.integers()",
                criticality=Criticality.STANDARD,
                test_skeleton="@given(st.integers())\ndef test_func2(x): pass",
                suggested_examples=50,
                is_testable=True,
                validation_errors=[]
            )
        ]

        saved_paths = await generator.save_invariants(invariants, output_dir=str(tmp_path))

        assert len(saved_paths) == 2

        for path in saved_paths:
            assert Path(path).exists()
            assert Path(path).suffix == ".md"
            content = Path(path).read_text()
            assert "# " in content  # Markdown heading

    async def test_fallback_invariants_on_llm_failure(self, sample_python_file, monkeypatch):
        """Test fallback invariants when LLM fails."""
        generator = InvariantGenerator()

        # Mock LLM to fail
        async def failing_generate(*args, **kwargs):
            raise Exception("LLM failed")

        monkeypatch.setattr(generator.llm_service, "generate_completion", failing_generate)

        invariants = await generator.generate_invariants_for_file(
            file_path=sample_python_file
        )

        assert len(invariants) >= 1  # Fallback invariants generated

        # Check for fallback indicator
        for inv in invariants:
            if "LLM failed" in inv.rationale:
                assert inv.criticality == Criticality.STANDARD  # Default for fallback

    def test_validate_invariant_errors(self):
        """Test invariant validation produces errors for invalid invariants."""
        generator = InvariantGenerator()

        # Create invalid invariant with model_validate to bypass Pydantic validation
        from pydantic import ValidationError
        try:
            invalid_invariant = InvariantSuggestion.model_validate({
                "file_path": "test.py",
                "invariant_name": "Invalid",
                "function_name": "func",
                "hypothesis": "Test",
                "formal_specification": "Test",
                "rationale": "Test",
                "hypothesis_strategy": "invalid.strategy()",
                "criticality": Criticality.STANDARD,
                "test_skeleton": "no decorator here",
                "suggested_examples": 5,  # Too low
                "is_testable": False,
                "validation_errors": []
            })
        except ValidationError:
            # Expected to fail Pydantic validation, create valid but testable=False
            invalid_invariant = InvariantSuggestion(
                file_path="test.py",
                invariant_name="Invalid",
                function_name="func",
                hypothesis="Test",
                formal_specification="Test",
                rationale="Test",
                hypothesis_strategy="invalid.strategy()",
                criticality=Criticality.STANDARD,
                test_skeleton="no decorator here",
                suggested_examples=10,  # Valid but still has other errors
                is_testable=False,
                validation_errors=[]
            )

        is_testable, errors = generator._validate_invariant(invalid_invariant)

        assert not is_testable
        assert len(errors) > 0
        assert any("Invalid Hypothesis strategy" in e for e in errors)
