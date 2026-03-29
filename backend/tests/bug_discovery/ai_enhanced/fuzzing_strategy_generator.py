"""FuzzingStrategyGenerator: AI-driven coverage-aware fuzzing strategy generation."""
import json
import hashlib
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.llm_service import LLMService
from tests.bug_discovery.ai_enhanced.models.fuzzing_strategy import FuzzingStrategy, BusinessImpact


class FuzzingStrategyGenerator:
    """
    Generate AI-driven fuzzing strategies from coverage gap analysis.

    Analyzes coverage_gap_analysis.py output (JSON with priority scores),
    identifies uncovered code patterns, and generates targeted fuzzing
    strategies for FuzzingOrchestrator.

    Example:
        generator = FuzzingStrategyGenerator()
        strategies = await generator.generate_strategies_from_coverage(
            coverage_gap_json="backend/tests/coverage_reports/metrics/backend_164_gap_analysis.json",
            top_n_files=10
        )
        for strategy in strategies:
            orchestrator.start_campaign(
                target_endpoint=strategy.target_endpoint,
                test_file=strategy.test_file,
                iterations=strategy.iterations
            )
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        """Initialize FuzzingStrategyGenerator."""
        self.llm_service = llm_service or LLMService(tenant_id="default")

    async def generate_strategies_from_coverage(
        self,
        coverage_gap_json: str,
        top_n_files: int = 10,
        min_priority_score: float = 50.0
    ) -> List[FuzzingStrategy]:
        """
        Generate fuzzing strategies from coverage gap analysis.

        Args:
            coverage_gap_json: Path to coverage gap analysis JSON
            top_n_files: Number of top priority files to analyze
            min_priority_score: Minimum priority score to include

        Returns:
            List of FuzzingStrategy objects
        """
        # Load coverage gap analysis
        with open(coverage_gap_json) as f:
            gap_data = json.load(f)

        # Extract top N priority files
        all_gaps = gap_data.get("all_gaps", [])
        top_gaps = [g for g in all_gaps if g["priority_score"] >= min_priority_score][:top_n_files]

        strategies = []

        # Generate strategy for each gap
        for gap in top_gaps:
            file_path = gap["file"]
            missing_lines = gap.get("missing_lines", [])
            business_impact = gap["business_impact"]

            # Extract code snippet for uncovered lines
            code_snippet = self._extract_code_snippet(file_path, missing_lines[:10])

            # Generate fuzzing strategy using LLM
            strategy = await self._generate_fuzzing_strategy(
                file_path=file_path,
                code_snippet=code_snippet,
                missing_lines=missing_lines,
                business_impact=business_impact,
                priority_score=gap["priority_score"]
            )

            if strategy:
                strategies.append(strategy)

        return strategies

    async def _generate_fuzzing_strategy(
        self,
        file_path: str,
        code_snippet: str,
        missing_lines: List[int],
        business_impact: str,
        priority_score: float
    ) -> Optional[FuzzingStrategy]:
        """Generate fuzzing strategy using LLM."""
        # Build LLM prompt
        prompt = f"""Analyze this coverage gap and generate a fuzzing strategy.

File: {file_path}
Business Impact: {business_impact}
Priority Score: {priority_score}
Uncovered Lines: {missing_lines}

Code Snippet:
```python
{code_snippet}
```

Task: Generate a fuzzing strategy to cover these lines.

Consider:
1. What API endpoint or function does this code serve?
2. What input parameters should we fuzz?
3. What boundary values, edge cases, or malformed inputs should we test?
4. How many iterations (Critical: 10000, High: 5000, Medium: 2000)?

Output JSON format:
{{
    "target_endpoint": "/api/v1/agents/run",
    "test_file": "backend/tests/fuzzing/test_agent_api_fuzzing.py",
    "fuzz_target": "agent_id parameter",
    "suggested_inputs": ["null", "empty string", "sql injection", "oversized string", "special chars"],
    "iterations": 10000,
    "rationale": "Uncovered lines handle agent_id validation, need to test edge cases",
    "confidence_score": 0.85
}}

Respond ONLY with valid JSON, no explanation."""

        try:
            # Call LLM
            response = await self.llm_service.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Low temperature for deterministic JSON
                max_tokens=500
            )

            # Parse JSON response
            response_text = response.get("content", response.get("text", ""))
            strategy_data = json.loads(response_text.strip())

            # Validate strategy
            strategy = FuzzingStrategy(
                file_path=file_path,
                missing_lines=missing_lines,
                business_impact=business_impact,
                priority_score=priority_score,
                **strategy_data
            )

            # Validate against codebase
            strategy.validated = self._validate_strategy(strategy)

            return strategy

        except (json.JSONDecodeError, Exception) as e:
            # Fallback strategy if LLM fails
            return self._generate_fallback_strategy(
                file_path, missing_lines, business_impact, priority_score
            )

    def _generate_fallback_strategy(
        self,
        file_path: str,
        missing_lines: List[int],
        business_impact: str,
        priority_score: float
    ) -> Optional[FuzzingStrategy]:
        """Generate fallback strategy when LLM fails."""
        # Infer endpoint from file path
        target_endpoint = self._infer_endpoint_from_file(file_path)
        test_file = self._get_test_file_for_endpoint(target_endpoint)

        # Determine iterations based on business impact
        impact_iterations = {
            BusinessImpact.CRITICAL: 10000,
            BusinessImpact.HIGH: 5000,
            BusinessImpact.MEDIUM: 2000,
            BusinessImpact.LOW: 1000
        }
        iterations = impact_iterations.get(business_impact, 2000)

        return FuzzingStrategy(
            file_path=file_path,
            missing_lines=missing_lines,
            business_impact=business_impact,
            priority_score=priority_score,
            target_endpoint=target_endpoint,
            test_file=test_file,
            fuzz_target="all parameters",
            suggested_inputs=["null", "empty", "malformed"],
            iterations=iterations,
            rationale=f"Generic fuzzing for {file_path} (LLM failed)",
            confidence_score=0.5,
            validated=self._validate_strategy_against_codebase(target_endpoint, test_file)
        )

    def _extract_code_snippet(self, file_path: str, line_numbers: List[int]) -> str:
        """Extract code snippet for given line numbers."""
        try:
            with open(file_path) as f:
                lines = f.readlines()

            min_line = max(0, min(line_numbers) - 3)
            max_line = min(len(lines), max(line_numbers) + 3)

            snippet_lines = []
            for i in range(min_line, max_line):
                prefix = ">>> " if (i + 1) in line_numbers else "    "
                snippet_lines.append(f"{prefix}{i+1}: {lines[i]}")

            return "\n".join(snippet_lines)
        except Exception:
            return "# Could not read file"

    def _infer_endpoint_from_file(self, file_path: str) -> str:
        """Infer API endpoint from file path."""
        if "agent_governance_service" in file_path or "agent_execution" in file_path:
            return "/api/v1/agents"
        elif "auth" in file_path:
            return "/api/v1/auth"
        elif "canvas" in file_path:
            return "/api/v1/canvas"
        elif "workflow" in file_path:
            return "/api/v1/workflows"
        else:
            return "/api/v1/generic"

    def _get_test_file_for_endpoint(self, endpoint: str) -> str:
        """Get fuzzing test file for endpoint."""
        test_file_map = {
            "/api/v1/auth/login": "backend/tests/fuzzing/test_auth_api_fuzzing.py",
            "/api/v1/auth": "backend/tests/fuzzing/test_auth_api_fuzzing.py",
            "/api/v1/agents": "backend/tests/fuzzing/test_agent_api_fuzzing.py",
            "/api/v1/canvas": "backend/tests/fuzzing/test_canvas_presentation_fuzzing.py",
            "/api/v1/workflows": "backend/tests/fuzzing/test_workflow_fuzzing.py",
        }
        return test_file_map.get(endpoint, "backend/tests/fuzzing/test_agent_api_fuzzing.py")

    def _validate_strategy(self, strategy: FuzzingStrategy) -> bool:
        """Validate LLM-generated strategy against codebase."""
        return self._validate_strategy_against_codebase(
            strategy.target_endpoint,
            strategy.test_file
        )

    def _validate_strategy_against_codebase(
        self,
        target_endpoint: str,
        test_file: str
    ) -> bool:
        """Validate endpoint exists and test file exists."""
        # Check if test file exists (resolve relative to backend dir)
        test_path = backend_dir / test_file if not Path(test_file).is_absolute() else Path(test_file)
        if not test_path.exists():
            return False

        # Validate endpoint is reasonable format
        if not re.match(r"^/api/v1/[\w/-]+$", target_endpoint):
            return False

        return True

    async def save_strategies(
        self,
        strategies: List[FuzzingStrategy],
        output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Save generated strategies to JSON files.

        Args:
            strategies: List of FuzzingStrategy objects
            output_dir: Output directory (default: backend/tests/bug_discovery/storage/strategies)

        Returns:
            List of saved file paths
        """
        if output_dir is None:
            output_dir = backend_dir / "tests" / "bug_discovery" / "storage" / "strategies"

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        saved_paths = []
        for i, strategy in enumerate(strategies):
            timestamp = hashlib.md5(strategy.file_path.encode()).hexdigest()[:8]
            filename = f"strategy_{timestamp}_{i}.json"
            filepath = Path(output_dir) / filename

            with open(filepath, "w") as f:
                json.dump(strategy.model_dump(), f, indent=2)

            saved_paths.append(str(filepath))

        return saved_paths
