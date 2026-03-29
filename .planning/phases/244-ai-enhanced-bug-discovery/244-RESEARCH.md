# Phase 244: AI-Enhanced Bug Discovery - Research

**Researched:** 2026-03-25
**Domain:** Multi-agent fuzzing orchestration, AI-generated invariants, cross-platform bug correlation, semantic bug clustering
**Confidence:** HIGH

## Summary

Phase 244 focuses on using AI to enhance bug discovery across four dimensions: (1) **Multi-agent fuzzing orchestration** generates coverage-aware fuzzing strategies from coverage gap analysis, (2) **AI-generated invariants** analyze code to suggest property test opportunities using LLM code analysis, (3) **Cross-platform bug correlation** detects bugs manifesting across web/mobile/desktop platforms, and (4) **Semantic bug clustering** uses LLM embeddings to group similar bugs by error semantics. The research confirms that Atom has **comprehensive infrastructure** for AI-enhanced bug discovery: existing coverage gap analysis scripts (coverage_gap_analysis.py), DiscoveryCoordinator for unified orchestration (Phase 242), EmbeddingService with LanceDB for semantic search, GraphRAGEngine with LLM integration for code analysis, and 264+ property tests with documented invariants (INVARIANTS.md). The key gap is **no AI-driven strategy generation** for fuzzing campaigns, invariant suggestion, or semantic bug clustering.

**Primary recommendation:** Build AIEnhancedBugDiscovery service with four capabilities: (1) **FuzzingStrategyGenerator** uses LLM to analyze coverage gaps and generate targeted fuzzing strategies (e.g., "uncovered lines 45-67 in agent_governance_service.py → fuzz agent_id parameter with boundary values"), (2) **InvariantGenerator** uses LLM to analyze code patterns and suggest property test invariants (e.g., "for loop with dictionary access → suggest idempotence invariant"), (3) **CrossPlatformCorrelator** correlates bugs across web/mobile/desktop by error signatures and user flows (e.g., "auth fails on web + mobile → shared API bug"), (4) **SemanticBugClusterer** uses EmbeddingService + LanceDB to cluster bugs by semantic similarity (error messages, stack traces, code contexts). Reuse existing infrastructure (coverage_gap_analysis.py, DiscoveryCoordinator, EmbeddingService, LanceDB, GraphRAGEngine, LLMService) and integrate with weekly bug discovery pipeline.

**Key findings:**
1. **Coverage gap analysis infrastructure exists**: coverage_gap_analysis.py (370 lines) analyzes coverage.py data, calculates priority scores by business impact tier (Critical/High/Medium/Low), generates JSON + Markdown reports with top 50 files by priority_score
2. **DiscoveryCoordinator orchestrates all discovery methods**: Phase 242 delivered unified orchestration service (150+ lines) that runs fuzzing, chaos, property tests, browser discovery with aggregation, deduplication, severity classification, bug filing, weekly reporting
3. **Embedding infrastructure is production-ready**: EmbeddingService supports FastEmbed (10-20ms, local), OpenAI (100-300ms, cloud), Cohere (150-400ms, multilingual) with 384-1536 dimension vectors; LanceDBHandler provides vector storage and similarity search
4. **LLM code analysis infrastructure exists**: GraphRAGEngine uses LLMService for entity extraction from unstructured text, agent_world_model.py uses LLM for fact extraction, canvas_summary_service.py generates summaries
5. **Property test infrastructure is mature**: 264+ property tests across governance, LLM routing, episodic memory, security, with INVARIANTS.md documenting 66 formal invariants (mathematical specifications)
6. **Cross-platform testing infrastructure exists**: mobile_api/ tests (4 test files, 11K+ lines) for agent execution, auth, device features, workflows; e2e_ui/ tests with test_agent_cross_platform.py

## Standard Stack

### Core AI/LLM Integration
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **LLMService** | (unified) | LLM code analysis and strategy generation | Unified interface for OpenAI, Anthropic, DeepSeek, Gemini; already integrated across codebase |
| **EmbeddingService** | FastEmbed default | Semantic similarity for bug clustering | FastEmbed (10-20ms, local) for bug embeddings; LanceDB for vector search; existing infrastructure |
| **GraphRAGEngine** | V2 (PostgreSQL-backed) | Code structure analysis for invariant generation | LLM-based entity/relationship extraction from code; proven in agent_world_model.py |
| **coverage.py** | Latest | Coverage data collection | Industry standard for Python coverage; coverage_gap_analysis.py already parses coverage.json |
| **LanceDB** | Latest | Vector storage for bug embeddings | Existing LanceDBHandler with dual vector storage; semantic search for bug clustering |

### Supporting Tools
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-asyncio** | Latest | Async LLM calls in tests | LLM-based invariant generation is async |
| **numpy** | Latest | Vector similarity calculations | Cosine similarity for bug clustering |
| **scikit-learn** | Latest (optional) | Clustering algorithms | K-means, DBSCAN for bug grouping (if LanceDB insufficient) |
| **dataclasses** | (stdlib) | Strategy and invariant data models | Type-safe data structures for AI-generated artifacts |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **LLMService (unified)** | Direct OpenAI/Anthropic API | LLMService provides caching, retry logic, multi-provider support, BYOK compliance |
| **FastEmbed embeddings** | OpenAI text-embedding-3-small | FastEmbed is 10-20ms (local) vs OpenAI 100-300ms (cloud); sufficient for bug error messages |
| **LanceDB vector search** | scikit-learn NearestNeighbors | LanceDB provides persistent storage, indexing, proven in episodic memory; scikit-learn is in-memory only |
| **Coverage gap analysis (existing)** | pytest-cov JSON only | coverage_gap_analysis.py provides business impact scoring, priority ranking, gap-to-target calculation |
| **GraphRAGEngine for code analysis** | AST parsing alone | LLM understands code semantics, patterns, invariants better than AST alone |

**Installation:**
```bash
# Core AI/LLM (already installed)
pip install openai anthropic  # For LLMService providers

# Embeddings (already installed)
pip install fastembed lancedb  # FastEmbed for local embeddings, LanceDB for vector storage

# Optional clustering (if needed)
pip install scikit-learn  # K-means, DBSCAN for bug clustering

# Coverage analysis (already installed)
pip install coverage pytest-cov

# Vector operations (already installed)
pip install numpy
```

## Architecture Patterns

### Recommended Project Structure

**Existing Structure (DO NOT CHANGE):**
```
backend/tests/
├── bug_discovery/              # ✅ EXISTS - Bug filing service
│   ├── bug_filing_service.py   # ✅ EXISTS - GitHub Issues API
│   ├── core/                   # ✅ EXISTS - Discovery orchestration (Phase 242)
│   │   ├── discovery_coordinator.py
│   │   ├── result_aggregator.py
│   │   ├── bug_deduplicator.py
│   │   ├── severity_classifier.py
│   │   └── dashboard_generator.py
│   └── models/                 # ✅ EXISTS - BugReport model
│       └── bug_report.py
├── fuzzing/                    # ✅ EXISTS - API fuzzing (Phase 239)
│   ├── campaigns/
│   │   ├── fuzzing_orchestrator.py
│   │   └── crash_deduplicator.py
│   └── test_agent_api_fuzzing.py
├── property_tests/             # ✅ EXISTS - 264+ property tests (Phase 238)
│   ├── INVARIANTS.md           # ✅ EXISTS - 66 documented invariants
│   ├── governance/
│   ├── llm_routing/
│   └── episodic_memory/
├── scripts/                    # ✅ EXISTS - Coverage analysis scripts
│   ├── coverage_gap_analysis.py
│   └── coverage_trend_tracker.py
└── mobile_api/                 # ✅ EXISTS - Cross-platform tests
    ├── test_mobile_agent_execution.py
    └── test_mobile_auth.py
```

**NEW Structure (Phase 244):**
```
backend/tests/bug_discovery/
├── ai_enhanced/                # ✅ NEW - AI-enhanced bug discovery
│   ├── __init__.py
│   ├── fuzzing_strategy_generator.py    # ✅ NEW - AI-driven fuzzing strategies
│   ├── invariant_generator.py            # ✅ NEW - AI-generated property test invariants
│   ├── cross_platform_correlator.py      # ✅ NEW - Web/mobile/desktop bug correlation
│   ├── semantic_bug_clusterer.py         # ✅ NEW - LLM embedding bug clustering
│   ├── models/                           # ✅ NEW - Data models
│   │   ├── fuzzing_strategy.py           # AI-generated fuzzing strategy
│   │   ├── invariant_suggestion.py       # AI-generated invariant
│   │   └── bug_cluster.py                # Semantic bug cluster
│   └── tests/                            # ✅ NEW - Unit tests
│       ├── test_fuzzing_strategy_generator.py
│       ├── test_invariant_generator.py
│       ├── test_cross_platform_correlator.py
│       └── test_semantic_bug_clusterer.py
├── core/                       # ✅ KEEP (Phase 242)
│   └── discovery_coordinator.py  # Enhance with AI strategy generation
└── storage/                    # ✅ NEW - Persistent storage
    ├── strategies/              # AI-generated fuzzing strategies (JSON)
    ├── invariants/              # AI-generated invariant suggestions (Markdown)
    └── clusters/                # Semantic bug clusters (JSON)
```

**Key Principle:** AIEnhancedBugDiscovery is a layer ON TOP of existing discovery infrastructure (FuzzingOrchestrator, DiscoveryCoordinator, coverage analysis), not a replacement. It generates STRATEGIES for existing tools, not new discovery methods.

### Pattern 1: FuzzingStrategyGenerator (AI-01)

**What:** Use LLM to analyze coverage gaps and generate targeted fuzzing strategies.

**When to use:** Weekly fuzzing campaigns, after coverage analysis runs, before FuzzingOrchestrator.start_campaign().

**Example:**
```python
# Source: backend/tests/bug_discovery/ai_enhanced/fuzzing_strategy_generator.py
from typing import List, Dict, Any, Optional
from pathlib import Path
from core.llm_service import LLMService

class FuzzingStrategyGenerator:
    """
    Generate AI-driven fuzzing strategies from coverage gap analysis.

    Analyzes coverage_gap_analysis.py output (JSON with priority scores),
    identifies uncovered code patterns, and generates targeted fuzzing
    strategies for FuzzingOrchestrator.

    Example:
        generator = FuzzingStrategyGenerator()
        strategies = generator.generate_strategies_from_coverage(
            coverage_gap_json="tests/coverage_reports/metrics/backend_164_gap_analysis.json",
            top_n_files=10  # Focus on top 10 priority files
        )

        for strategy in strategies:
            # Apply strategy via FuzzingOrchestrator
            orchestrator.start_campaign(
                target_endpoint=strategy["endpoint"],
                test_file=strategy["test_file"],
                iterations=strategy["iterations"]
            )
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize FuzzingStrategyGenerator.

        Args:
            llm_service: LLMService instance (default: create new instance)
        """
        self.llm_service = llm_service or LLMService(tenant_id="default")

    async def generate_strategies_from_coverage(
        self,
        coverage_gap_json: str,
        top_n_files: int = 10,
        min_priority_score: float = 50.0
    ) -> List[Dict[str, Any]]:
        """
        Generate fuzzing strategies from coverage gap analysis.

        Args:
            coverage_gap_json: Path to coverage gap analysis JSON (from coverage_gap_analysis.py)
            top_n_files: Number of top priority files to analyze (default: 10)
            min_priority_score: Minimum priority score to include (default: 50.0)

        Returns:
            List of fuzzing strategies with target_endpoint, test_file, iterations, rationale
        """
        import json

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
            missing_lines = gap["missing_lines"]  # List of uncovered line numbers
            business_impact = gap["business_impact"]

            # Extract code snippet for uncovered lines
            code_snippet = self._extract_code_snippet(file_path, missing_lines[:10])

            # Generate fuzzing strategy using LLM
            strategy = await self._generate_fuzzing_strategy(
                file_path=file_path,
                code_snippet=code_snippet,
                missing_lines=missing_lines,
                business_impact=business_impact
            )

            strategies.append(strategy)

        return strategies

    async def _generate_fuzzing_strategy(
        self,
        file_path: str,
        code_snippet: str,
        missing_lines: List[int],
        business_impact: str
    ) -> Dict[str, Any]:
        """
        Generate fuzzing strategy for specific code gap using LLM.

        Args:
            file_path: Path to file with coverage gap
            code_snippet: Source code for uncovered lines
            missing_lines: List of uncovered line numbers
            business_impact: Business impact tier (Critical/High/Medium/Low)

        Returns:
            Dict with target_endpoint, test_file, iterations, rationale, confidence_score
        """
        # Build LLM prompt
        prompt = f"""Analyze this coverage gap and generate a fuzzing strategy.

File: {file_path}
Business Impact: {business_impact}
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
4. How many iterations are needed (Critical: 10000, High: 5000, Medium: 2000)?

Output JSON format:
{{
    "target_endpoint": "/api/v1/agents/run",
    "test_file": "tests/fuzzing/test_agent_api_fuzzing.py",
    "fuzz_target": "agent_id parameter",
    "suggested_inputs": ["null", "empty string", "sql injection", "oversized string", "special chars"],
    "iterations": 10000,
    "rationale": "Uncovered lines handle agent_id validation, need to test edge cases",
    "confidence_score": 0.85
}}

Respond ONLY with valid JSON, no explanation."""

        # Call LLM
        response = await self.llm_service.generate_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Low temperature for deterministic JSON
            max_tokens=500
        )

        # Parse JSON response
        import json
        try:
            strategy = json.loads(response.strip())
            return strategy
        except json.JSONDecodeError:
            # Fallback strategy if LLM fails
            return {
                "target_endpoint": self._infer_endpoint_from_file(file_path),
                "test_file": "tests/fuzzing/test_generic_fuzzing.py",
                "fuzz_target": "all parameters",
                "suggested_inputs": ["null", "empty", "malformed"],
                "iterations": 5000,
                "rationale": f"Generic fuzzing for {file_path} (LLM failed)",
                "confidence_score": 0.5
            }

    def _extract_code_snippet(self, file_path: str, line_numbers: List[int]) -> str:
        """Extract code snippet for given line numbers."""
        try:
            with open(file_path) as f:
                lines = f.readlines()

            # Get lines around missing numbers (context window)
            min_line = max(0, min(line_numbers) - 3)
            max_line = min(len(lines), max(line_numbers) + 3)

            snippet_lines = []
            for i in range(min_line, max_line):
                prefix = ">>> " if i in line_numbers else "    "
                snippet_lines.append(f"{prefix}{i+1}: {lines[i]}")

            return "\n".join(snippet_lines)
        except Exception:
            return "# Could not read file"

    def _infer_endpoint_from_file(self, file_path: str) -> str:
        """Infer API endpoint from file path (fallback)."""
        if "agent_governance_service" in file_path:
            return "/api/v1/agents"
        elif "auth" in file_path:
            return "/api/v1/auth"
        elif "workflow" in file_path:
            return "/api/v1/workflows"
        else:
            return "/api/v1/generic"
```

**Integration with DiscoveryCoordinator:**
```python
# Enhance DiscoveryCoordinator.run_full_discovery()
class DiscoveryCoordinator:
    async def run_ai_enhanced_discovery(self):
        """Run AI-enhanced bug discovery with coverage-aware fuzzing."""

        # 1. Run coverage analysis
        subprocess.run(["python", "tests/scripts/coverage_gap_analysis.py"])

        # 2. Generate fuzzing strategies from coverage gaps
        from tests.bug_discovery.ai_enhanced.fuzzing_strategy_generator import FuzzingStrategyGenerator
        strategy_gen = FuzzingStrategyGenerator()
        strategies = await strategy_gen.generate_strategies_from_coverage(
            coverage_gap_json="tests/coverage_reports/metrics/backend_164_gap_analysis.json"
        )

        # 3. Run targeted fuzzing campaigns
        for strategy in strategies:
            fuzzing_reports = self._run_fuzzing_discovery(
                endpoints=[strategy["target_endpoint"]],
                iterations=strategy["iterations"]
            )
```

### Pattern 2: InvariantGenerator (AI-02)

**What:** Use LLM to analyze code patterns and suggest property test invariants.

**When to use:** Before writing property tests, when expanding coverage to new modules, during code review.

**Example:**
```python
# Source: backend/tests/bug_discovery/ai_enhanced/invariant_generator.py
from typing import List, Dict, Any, Optional
from pathlib import Path
from core.llm_service import LLMService

class InvariantGenerator:
    """
    Generate AI-suggested property test invariants from code analysis.

    Analyzes Python code to identify patterns that warrant property-based
    testing (e.g., functions with loops, dictionary access, state machines)
    and generates formal invariant suggestions following INVARIANTS.md format.

    Example:
        generator = InvariantGenerator()
        invariants = generator.generate_invariants_for_file(
            file_path="backend/core/agent_governance_service.py"
        )

        for invariant in invariants:
            # Write to property test file
            generator.write_property_test(invariant)
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize InvariantGenerator.

        Args:
            llm_service: LLMService instance (default: create new instance)
        """
        self.llm_service = llm_service or LLMService(tenant_id="default")

    async def generate_invariants_for_file(
        self,
        file_path: str,
        max_invariants: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate invariant suggestions for a Python file.

        Args:
            file_path: Path to Python file to analyze
            max_invariants: Maximum number of invariants to suggest (default: 5)

        Returns:
            List of invariant suggestions with name, hypothesis, rationale, test_skeleton
        """
        # Read source code
        with open(file_path) as f:
            source_code = f.read()

        # Build LLM prompt
        prompt = f"""Analyze this Python code and suggest property-based testing invariants.

File: {file_path}

Code:
```python
{source_code[:3000]}  # First 3000 chars (token limit)
```

Task: Identify functions/classes that would benefit from property-based testing.
Look for:
1. Functions with loops (suggest idempotence, termination invariants)
2. Dictionary/set operations (suggest commutativity, associativity)
3. State machines (suggest monotonicity, transition invariants)
4. Mathematical operations (suggest rounding, precision invariants)
5. Caching mechanisms (suggest cache consistency invariants)

For each invariant, provide:
- invariant_name: Short descriptive name
- function_name: Target function to test
- hypothesis: Formal invariant statement (e.g., "For all inputs x, f(f(x)) == f(x)")
- rationale: Why this invariant matters
- hypothesis_strategy: Hypothesis test data generation strategy (e.g., "st.text()", "st.integers()")
- test_skeleton: Code skeleton for property test

Output JSON format:
{{
    "invariants": [
        {{
            "invariant_name": "Governance Cache Idempotence",
            "function_name": "check_permission",
            "hypothesis": "For all agent_id, action, and maturity levels, permission checks are idempotent",
            "formal_specification": "∀ agent_id, action, maturity: check_permission(agent_id, action, maturity) == check_permission(agent_id, action, maturity)",
            "rationale": "Permission checks must not have side effects or non-deterministic behavior",
            "hypothesis_strategy": "st.text() for agent_id, st.sampled_from(list(ActionType)) for action",
            "criticality": "CRITICAL",
            "test_skeleton": "@given(st.text(), st.sampled_from(list(ActionType)), st.sampled_from(list(MaturityLevel)))\\n@settings(max_examples=200)\\ndef test_check_permission_idempotent(agent_id, action, maturity):\\n    # Test implementation..."
        }}
    ]
}}

Respond ONLY with valid JSON, no explanation."""

        # Call LLM
        response = await self.llm_service.generate_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,  # Medium temperature for creativity
            max_tokens=2000
        )

        # Parse JSON response
        import json
        try:
            result = json.loads(response.strip())
            return result.get("invariants", [])[:max_invariants]
        except json.JSONDecodeError:
            return []

    def write_property_test(
        self,
        invariant: Dict[str, Any],
        output_dir: Optional[Path] = None
    ) -> str:
        """
        Write property test file from invariant suggestion.

        Args:
            invariant: Invariant suggestion from generate_invariants_for_file()
            output_dir: Output directory (default: backend/tests/property_tests/)

        Returns:
            Path to generated test file
        """
        if output_dir is None:
            output_dir = Path("backend/tests/property_tests/generated")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from invariant name
        filename = f"test_{invariant['invariant_name'].lower().replace(' ', '_')}.py"
        output_path = output_dir / filename

        # Write test file
        with open(output_path, "w") as f:
            f.write(f'''"""
Property Test: {invariant['invariant_name']}

Auto-generated by InvariantGenerator (Phase 244)
Invariant: {invariant['hypothesis']}
Rationale: {invariant['rationale']}
Criticality: {invariant.get('criticality', 'STANDARD')}
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# TODO: Import target function
# from {invariant['function_name'].split('.')[0]} import {invariant['function_name']}

{invariant['test_skeleton']}
''')

        return str(output_path)
```

**Integration with DiscoveryCoordinator:**
```python
# Enhance DiscoveryCoordinator to generate invariants
class DiscoveryCoordinator:
    async def suggest_invariants_for_gaps(
        self,
        coverage_gap_json: str,
        max_invariants_per_file: int = 3
    ):
        """Suggest property test invariants for low-coverage files."""
        from tests.bug_discovery.ai_enhanced.invariant_generator import InvariantGenerator

        invariant_gen = InvariantGenerator()

        # Load coverage gaps
        import json
        with open(coverage_gap_json) as f:
            gap_data = json.load(f)

        # Generate invariants for top gaps
        for gap in gap_data["all_gaps"][:10]:
            invariants = await invariant_gen.generate_invariants_for_file(
                file_path=gap["file"],
                max_invariants=max_invariants_per_file
            )

            # Write property tests
            for invariant in invariants:
                test_path = invariant_gen.write_property_test(invariant)
                print(f"Generated property test: {test_path}")
```

### Pattern 3: CrossPlatformCorrelator (AI-03)

**What:** Detect bugs manifesting across web/mobile/desktop platforms by correlating error signatures and user flows.

**When to use:** After cross-platform tests run, during bug triage, for platform-specific issue analysis.

**Example:**
```python
# Source: backend/tests/bug_discovery/ai_enhanced/cross_platform_correlator.py
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from tests.bug_discovery.models.bug_report import BugReport
from tests.bug_discovery.core.bug_deduplicator import BugDeduplicator

class CrossPlatformCorrelator:
    """
    Correlate bugs across web/mobile/desktop platforms.

    Detects when the same bug manifests on multiple platforms (e.g., auth
    fails on web + mobile → shared API bug) by analyzing error signatures,
    API endpoints, user flows, and temporal patterns.

    Example:
        correlator = CrossPlatformCorrelator()

        # Collect bugs from all platforms
        web_bugs = load_bugs_from_web_tests()
        mobile_bugs = load_bugs_from_mobile_tests()
        desktop_bugs = load_bugs_from_desktop_tests()

        # Correlate across platforms
        correlated = correlator.correlate_cross_platform_bugs(
            web_bugs=web_bugs,
            mobile_bugs=mobile_bugs,
            desktop_bugs=desktop_bugs
        )

        for correlation in correlated:
            print(f"Same bug on {correlation['platforms']}: {correlation['error_signature']}")
    """

    PLATFORM_WEB = "web"
    PLATFORM_MOBILE = "mobile"
    PLATFORM_DESKTOP = "desktop"

    def __init__(self):
        """Initialize CrossPlatformCorrelator."""
        self.bug_deduplicator = BugDeduplicator()

    def correlate_cross_platform_bugs(
        self,
        web_bugs: List[BugReport],
        mobile_bugs: List[BugReport],
        desktop_bugs: List[BugReport],
        similarity_threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Correlate bugs across platforms by error signature and context.

        Args:
            web_bugs: Bugs from web tests (e2e_ui/)
            mobile_bugs: Bugs from mobile tests (mobile_api/)
            desktop_bugs: Bugs from desktop tests (if available)
            similarity_threshold: Minimum similarity score for correlation (0.0-1.0)

        Returns:
            List of correlated bug groups with platform coverage
        """
        # Group all bugs by platform
        all_bugs = {
            self.PLATFORM_WEB: web_bugs,
            self.PLATFORM_MOBILE: mobile_bugs,
            self.PLATFORM_DESKTOP: desktop_bugs
        }

        # Generate cross-platform error signatures
        cross_platform_signatures = self._generate_cross_platform_signatures(all_bugs)

        # Group bugs by cross-platform signature
        signature_groups = defaultdict(list)
        for bug, signature in cross_platform_signatures:
            signature_groups[signature].append(bug)

        # Filter to multi-platform groups
        correlated = []
        for signature, bugs in signature_groups.items():
            platforms = set(bug.metadata.get("platform", "unknown") for bug in bugs)

            if len(platforms) > 1:  # Multi-platform bug
                # Calculate similarity score
                similarity = self._calculate_cross_platform_similarity(bugs)

                if similarity >= similarity_threshold:
                    correlated.append({
                        "error_signature": signature,
                        "platforms": list(platforms),
                        "bugs": bugs,
                        "similarity_score": similarity,
                        "suggested_action": self._suggest_action(bugs, platforms)
                    })

        # Sort by number of platforms (descending)
        correlated.sort(key=lambda x: len(x["platforms"]), reverse=True)

        return correlated

    def _generate_cross_platform_signatures(
        self,
        all_bugs: Dict[str, List[BugReport]]
    ) -> List[Tuple[BugReport, str]]:
        """
        Generate cross-platform error signatures (platform-agnostic).

        Strips platform-specific details (file paths, line numbers) to focus
        on semantic error patterns.
        """
        signatures = []

        for platform, bugs in all_bugs.items():
            for bug in bugs:
                # Normalize error message for cross-platform comparison
                normalized_error = self._normalize_error_for_cross_platform(
                    bug.error_message,
                    platform
                )

                # Generate signature from normalized error + API endpoint
                import hashlib
                signature_content = f"{normalized_error}|{bug.metadata.get('api_endpoint', 'unknown')}"
                signature = hashlib.sha256(signature_content.encode()).hexdigest()

                signatures.append((bug, signature))

        return signatures

    def _normalize_error_for_cross_platform(
        self,
        error_message: str,
        platform: str
    ) -> str:
        """
        Normalize error message by removing platform-specific details.

        Examples:
        - "/backend/core/agent_governance_service.py:456" → "agent_governance_service.py"
        - "HTTP 500: Internal Server Error" → "HTTP 500"
        - "File not found: /var/www/html/index.html" → "File not found"
        """
        import re

        normalized = error_message

        # Remove file paths (platform-specific)
        normalized = re.sub(r'/[a-zA-Z0-9_/\-\.]+/', '/', normalized)
        normalized = re.sub(r'C:\\[a-zA-Z0-9_\\\-\.]+\\', '\\\\', normalized)

        # Remove line numbers
        normalized = re.sub(r':\d+', ':LINE', normalized)

        # Normalize error codes
        normalized = normalized.replace("Internal Server Error", "HTTP 500")
        normalized = normalized.replace("Not Found", "HTTP 404")
        normalized = normalized.replace("Unauthorized", "HTTP 401")

        return normalized.strip()

    def _calculate_cross_platform_similarity(self, bugs: List[BugReport]) -> float:
        """
        Calculate similarity score for cross-platform bug group.

        Args:
            bugs: List of bugs from different platforms

        Returns:
            Similarity score (0.0-1.0)
        """
        if len(bugs) < 2:
            return 0.0

        # Calculate similarity based on:
        # 1. Error message similarity (Jaccard similarity)
        # 2. API endpoint match (exact match required)
        # 3. Temporal proximity (bugs found within 1 hour)

        # Check API endpoint match
        endpoints = set(bug.metadata.get("api_endpoint", "") for bug in bugs)
        endpoint_match = 1.0 if len(endpoints) == 1 else 0.5

        # Calculate error message similarity
        error_messages = [bug.error_message.lower().split() for bug in bugs]
        word_sets = [set(msg) for msg in error_messages]

        # Jaccard similarity: |A ∩ B| / |A ∪ B|
        intersections = []
        unions = []

        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                intersection = word_sets[i] & word_sets[j]
                union = word_sets[i] | word_sets[j]
                intersections.append(len(intersection))
                unions.append(len(union))

        avg_jaccard = sum(intersections) / max(sum(unions), 1)

        # Combine scores
        similarity = (endpoint_match * 0.6) + (avg_jaccard * 0.4)

        return round(similarity, 3)

    def _suggest_action(
        self,
        bugs: List[BugReport],
        platforms: List[str]
    ) -> str:
        """Suggest remediation action for cross-platform bug."""
        # Check if bug is in shared API (common cause)
        api_endpoints = set(bug.metadata.get("api_endpoint", "") for bug in bugs)

        if len(api_endpoints) == 1 and list(api_endpoints)[0].startswith("/api/"):
            return f"Fix shared API endpoint {list(api_endpoints)[0]} (affects {', '.join(platforms)})"
        else:
            return f"Investigate shared backend logic (affects {', '.join(platforms)})"
```

### Pattern 4: SemanticBugClusterer (AI-04)

**What:** Use LLM embeddings to cluster semantically similar bugs for grouping and triage.

**When to use:** After bug discovery runs, for weekly bug reports, to identify systemic issues.

**Example:**
```python
# Source: backend/tests/bug_discovery/ai_enhanced/semantic_bug_clusterer.py
from typing import List, Dict, Any, Optional
from core.embedding_service import EmbeddingService
from core.lancedb_handler import LanceDBHandler
from tests.bug_discovery.models.bug_report import BugReport

class SemanticBugClusterer:
    """
    Cluster bugs by semantic similarity using LLM embeddings.

    Generates embeddings for bug error messages, stack traces, and code
    contexts, then clusters similar bugs using LanceDB vector search.

    Example:
        clusterer = SemanticBugClusterer()

        # Cluster bugs from discovery run
        clusters = clusterer.cluster_bugs(
            bugs=bug_reports,
            similarity_threshold=0.75,
            min_cluster_size=2
        )

        for cluster in clusters:
            print(f"Cluster {cluster['cluster_id']}: {len(cluster['bugs'])} similar bugs")
            print(f"Theme: {cluster['theme']}")
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        lancedb_handler: Optional[LanceDBHandler] = None
    ):
        """
        Initialize SemanticBugClusterer.

        Args:
            embedding_service: EmbeddingService for generating embeddings (default: create new)
            lancedb_handler: LanceDBHandler for vector storage (default: create new)
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.lancedb_handler = lancedb_handler or LanceDBHandler(
            db_path="./data/bug_clusters"
        )

        # Create bug embeddings table
        self._ensure_embeddings_table()

    def _ensure_embeddings_table(self):
        """Create LanceDB table for bug embeddings if not exists."""
        try:
            # Check if table exists
            existing_tables = self.lancedb_handler.list_tables()
            if "bug_embeddings" not in existing_tables:
                # Create table
                self.lancedb_handler.create_table(
                    table_name="bug_embeddings",
                    schema={
                        "bug_id": str,
                        "error_message": str,
                        "stack_trace": str,
                        "embedding": list,  # Vector
                        "metadata": dict,
                        "timestamp": str
                    }
                )
        except Exception as e:
            print(f"Warning: Could not create bug_embeddings table: {e}")

    async def cluster_bugs(
        self,
        bugs: List[BugReport],
        similarity_threshold: float = 0.75,
        min_cluster_size: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Cluster bugs by semantic similarity.

        Args:
            bugs: List of BugReport objects from discovery methods
            similarity_threshold: Minimum similarity for clustering (cosine similarity, 0.0-1.0)
            min_cluster_size: Minimum bugs per cluster (default: 2)

        Returns:
            List of clusters with cluster_id, bugs, theme, similarity_scores
        """
        # Generate embeddings for all bugs
        embeddings = await self._generate_bug_embeddings(bugs)

        # Store embeddings in LanceDB
        await self._store_embeddings(embeddings)

        # Cluster using vector similarity search
        clusters = await self._cluster_by_similarity(
            bugs=bugs,
            embeddings=embeddings,
            similarity_threshold=similarity_threshold,
            min_cluster_size=min_cluster_size
        )

        # Generate cluster themes using LLM
        for cluster in clusters:
            cluster["theme"] = await self._generate_cluster_theme(cluster["bugs"])

        return clusters

    async def _generate_bug_embeddings(
        self,
        bugs: List[BugReport]
    ) -> List[Dict[str, Any]]:
        """Generate embeddings for bug error messages."""
        embeddings = []

        for bug in bugs:
            # Combine error message + stack trace for embedding
            text_to_embed = f"{bug.error_message}\n{bug.stack_trace or ''}"

            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(text_to_embed)

            embeddings.append({
                "bug_id": bug.test_name,  # Use test_name as ID
                "error_message": bug.error_message,
                "stack_trace": bug.stack_trace,
                "embedding": embedding,
                "metadata": bug.metadata,
                "bug": bug  # Store reference
            })

        return embeddings

    async def _store_embeddings(self, embeddings: List[Dict[str, Any]]):
        """Store embeddings in LanceDB."""
        try:
            # Convert to list of dicts for LanceDB
            data = []
            for emb in embeddings:
                data.append({
                    "bug_id": emb["bug_id"],
                    "error_message": emb["error_message"],
                    "stack_trace": emb["stack_trace"],
                    "vector": emb["embedding"],  # LanceDB uses "vector" column
                    "metadata": emb["metadata"],
                    "timestamp": str(bug.timestamp) if hasattr(emb["bug"], 'timestamp') else ""
                })

            # Insert into LanceDB
            self.lancedb_handler.add_data(
                table_name="bug_embeddings",
                data=data
            )
        except Exception as e:
            print(f"Warning: Could not store embeddings: {e}")

    async def _cluster_by_similarity(
        self,
        bugs: List[BugReport],
        embeddings: List[Dict[str, Any]],
        similarity_threshold: float,
        min_cluster_size: int
    ) -> List[Dict[str, Any]]:
        """Cluster bugs using vector similarity search."""
        clusters = []
        assigned_bugs = set()

        # For each bug, find similar bugs via vector search
        for i, bug_embedding in enumerate(embeddings):
            if i in assigned_bugs:
                continue

            # Vector search for similar bugs
            similar_bugs = self.lancedb_handler.vector_search(
                table_name="bug_embeddings",
                query_vector=bug_embedding["embedding"],
                limit=len(bugs),
                metric="cosine"
            )

            # Filter by similarity threshold
            similar_bug_ids = []
            similarity_scores = []

            for result in similar_bugs:
                similarity = 1.0 - result.get("distance", 1.0)  # Convert distance to similarity

                if similarity >= similarity_threshold:
                    similar_bug_ids.append(result["bug_id"])
                    similarity_scores.append(similarity)

            # Check if cluster meets minimum size
            if len(similar_bug_ids) >= min_cluster_size:
                # Get bug objects
                cluster_bugs = []
                for bug_id in similar_bug_ids:
                    for emb in embeddings:
                        if emb["bug_id"] == bug_id:
                            cluster_bugs.append(emb["bug"])
                            assigned_bugs.add(embeddings.index(emb))
                            break

                clusters.append({
                    "cluster_id": f"cluster_{len(clusters)}",
                    "bugs": cluster_bugs,
                    "similarity_scores": similarity_scores,
                    "theme": ""  # Generated later
                })

        return clusters

    async def _generate_cluster_theme(self, bugs: List[BugReport]) -> str:
        """Generate semantic theme for bug cluster using LLM."""
        if not bugs:
            return "Empty cluster"

        # Build prompt with bug error messages
        error_messages = "\n".join([
            f"- {bug.error_message[:200]}" for bug in bugs[:5]
        ])

        prompt = f"""Analyze these bug error messages and generate a short theme label (3-5 words).

Error messages:
{error_messages}

Task: What is the common theme or root cause across these bugs?

Examples:
- "SQL injection in agent_id parameter"
- "Memory leaks in LLM streaming"
- "Race conditions in cache updates"

Respond ONLY with the theme label, no explanation."""

        # Call LLM
        from core.llm_service import LLMService
        llm_service = LLMService(tenant_id="default")

        response = await llm_service.generate_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=50
        )

        return response.strip()
```

### Anti-Patterns to Avoid

- **Manual strategy generation**: Don't manually design fuzzing strategies — use LLM to analyze coverage gaps and generate targeted strategies
- **Generic invariant suggestions**: Don't suggest generic invariants — analyze code patterns, context, and business impact for specific invariants
- **Platform-specific bug triage**: Don't treat web/mobile/desktop bugs separately — correlate across platforms to identify shared root causes
- **Manual bug clustering**: Don't manually group bugs by error message — use semantic embeddings for intelligent clustering
- **LLM without validation**: Don't trust LLM outputs blindly — validate strategies, invariants, clusters with automated checks

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Coverage gap analysis** | Custom coverage parsing scripts | coverage_gap_analysis.py (370 lines) | Business impact scoring, priority ranking, JSON + Markdown output |
| **Vector embeddings** | Custom embedding generation | EmbeddingService (FastEmbed, OpenAI, Cohere) | FastEmbed (10-20ms local), multi-provider support, proven in episodic memory |
| **Vector storage** | Custom vector database | LanceDBHandler (existing infrastructure) | Persistent storage, indexing, semantic search, integrated with codebase |
| **LLM code analysis** | Custom AST parsing | GraphRAGEngine + LLMService | LLM understands code semantics, patterns, invariants better than AST alone |
| **Discovery orchestration** | Custom subprocess management | DiscoveryCoordinator (Phase 242) | Unified orchestration, aggregation, deduplication, bug filing, reporting |
| **Bug deduplication** | Custom deduplication logic | BugDeduplicator (Phase 242) | SHA256 error signature hashing, cross-method deduplication |

**Key insight:** Phase 244 is an AI enhancement layer ON TOP of existing infrastructure, not new discovery methods. Reuse coverage_gap_analysis.py, DiscoveryCoordinator, EmbeddingService, LanceDB, GraphRAGEngine, LLMService. The only new code is strategy/invariant/cluster generation logic.

## Common Pitfalls

### Pitfall 1: LLM Hallucination in Strategy Generation

**What goes wrong:** LLM generates invalid fuzzing strategies (non-existent endpoints, wrong file paths), causing fuzzing campaigns to fail.

**Why it happens:** LLM lacks context about project structure, API routes, test file organization.

**How to avoid:**
1. Validate LLM-generated strategies against actual codebase:
```python
def validate_fuzzing_strategy(strategy: Dict[str, Any]) -> bool:
    """Validate LLM-generated fuzzing strategy."""
    # Check if endpoint exists
    endpoint = strategy["target_endpoint"]
    if not endpoint_exists_in_codebase(endpoint):
        return False

    # Check if test file exists
    test_file = strategy["test_file"]
    if not Path(test_file).exists():
        return False

    # Check iterations is reasonable
    iterations = strategy["iterations"]
    if not (1000 <= iterations <= 20000):
        return False

    return True
```
2. Provide LLM with context: API routes, test file locations, coverage gap data
3. Use low temperature (0.3) for deterministic JSON output
4. Implement fallback strategies if LLM fails

**Warning signs:** Fuzzing campaigns fail immediately, strategies reference non-existent files, iteration counts are unrealistic.

### Pitfall 2: Over-Generated Invariants

**What goes wrong:** InvariantGenerator suggests 50+ invariants for a single file, overwhelming developers with low-quality suggestions.

**Why it happens:** LLM suggests invariants for every function without filtering by importance, testability, or business impact.

**How to avoid:**
1. Limit invariants per file (max 5-10)
2. Prioritize CRITICAL/HIGH business impact tiers
3. Require invariant to pass testability checks:
```python
def is_invariant_testable(invariant: Dict[str, Any]) -> bool:
    """Check if invariant is testable with Hypothesis."""
    # Check if hypothesis_strategy is valid
    strategy = invariant.get("hypothesis_strategy", "")
    if "st." not in strategy:
        return False  # No Hypothesis strategy

    # Check if function is importable
    function_name = invariant.get("function_name", "")
    if not function_exists(function_name):
        return False

    # Check if criticality is valid
    criticality = invariant.get("criticality", "STANDARD")
    if criticality not in ["CRITICAL", "HIGH", "STANDARD", "LOW"]:
        return False

    return True
```
4. Use coverage gap data to prioritize uncovered functions

**Warning signs:** Hundreds of invariant suggestions, most are untestable, developers ignore all suggestions.

### Pitfall 3: Cross-Platform False Correlations

**What goes wrong:** CrossPlatformCorrelator groups unrelated bugs (e.g., "auth fails on web" + "payment fails on mobile") because of generic error messages.

**Why it happens:** Error normalization is too aggressive, removing important context. Jaccard similarity on generic words ("error", "failed", "500") produces false matches.

**How to avoid:**
1. Require API endpoint match for cross-platform correlation (exact match)
2. Use semantic embeddings (not just word overlap) for error similarity
3. Set high similarity threshold (0.8+ for cross-platform)
4. Require temporal proximity (bugs found within 1 hour):
```python
def is_temporally_proximal(bug1: BugReport, bug2: BugReport, max_hours: int = 1) -> bool:
    """Check if bugs were found within max_hours of each other."""
    from datetime import timedelta

    time_diff = abs(bug1.timestamp - bug2.timestamp)
    return time_diff <= timedelta(hours=max_hours)
```

**Warning signs:** Cross-platform bug groups have no common theme, suggested actions are generic, correlation rate is <5%.

### Pitfall 4: Semantic Clustering with Poor Embeddings

**What goes wrong:** SemanticBugClusterer groups unrelated bugs because embeddings capture wrong signal (e.g., file paths instead of error semantics).

**Why it happens:** Embedding text includes too much metadata (file paths, line numbers) instead of error semantics.

**How to avoid:**
1. Clean text before embedding:
```python
def clean_text_for_embedding(text: str) -> str:
    """Remove non-semantic content from error messages."""
    import re

    # Remove file paths
    text = re.sub(r'/[a-zA-Z0-9_/\-\.]+', '', text)

    # Remove line numbers
    text = re.sub(r':\d+', '', text)

    # Remove timestamps
    text = re.sub(r'\d{4}-\d{2}-\d{2}.*?\d{2}:\d{2}:\d{2}', '', text)

    # Keep error keywords, function names, error types
    return text.strip()
```
2. Use FastEmbed (384-dim) for speed, not OpenAI (1536-dim) for bug clustering
3. Set appropriate similarity threshold (0.75-0.85 for cosine similarity)

**Warning signs:** Clusters have no coherent theme, cluster size is 1 (no grouping), or all bugs in one cluster (threshold too low).

### Pitfall 5: Ignoring Existing Discovery Infrastructure

**What goes wrong:** Phase 244 builds new fuzzing/invariant/cluster services from scratch, duplicating DiscoveryCoordinator, FuzzingOrchestrator, coverage_gap_analysis.py.

**Why it happens:** Team doesn't review existing infrastructure (Phases 237-243) before implementing AI enhancements.

**How to avoid:**
1. Review Phase 242 DiscoveryCoordinator before building AI orchestration
2. Integrate with FuzzingOrchestrator, not replace it
3. Use coverage_gap_analysis.py output as input to strategy generation
4. Extend BugDeduplicator, not build new deduplication logic

**Warning signs:** New services duplicate existing functionality, no integration with DiscoveryCoordinator, parallel CI pipelines.

## Code Examples

Verified patterns from official sources:

### Pattern 1: Coverage-Driven Fuzzing Strategy Generation (This Phase)

```python
# Source: backend/tests/bug_discovery/ai_enhanced/fuzzing_strategy_generator.py
from tests.scripts.coverage_gap_analysis import analyze_gaps

async def generate_targeted_strategies():
    """Generate fuzzing strategies from coverage gaps."""
    # Run coverage analysis
    gaps = analyze_gaps(coverage_data, impact_lookup)

    # Top 10 priority gaps
    top_gaps = gaps[:10]

    # Generate strategies using LLM
    generator = FuzzingStrategyGenerator()
    strategies = await generator.generate_strategies_from_coverage(
        coverage_gap_json="tests/coverage_reports/metrics/backend_164_gap_analysis.json",
        top_n_files=10
    )

    # Apply strategies via FuzzingOrchestrator
    for strategy in strategies:
        orchestrator.start_campaign(
            target_endpoint=strategy["target_endpoint"],
            test_file=strategy["test_file"],
            iterations=strategy["iterations"]
        )
```

### Pattern 2: Invariant Generation with Validation (This Phase)

```python
# Source: backend/tests/bug_discovery/ai_enhanced/invariant_generator.py
async def generate_and_validate_invariants():
    """Generate invariants with validation checks."""
    generator = InvariantGenerator()

    # Generate invariants for low-coverage file
    invariants = await generator.generate_invariants_for_file(
        file_path="backend/core/agent_governance_service.py",
        max_invariants=5
    )

    # Validate each invariant
    for invariant in invariants:
        if is_invariant_testable(invariant):
            # Write property test
            test_path = generator.write_property_test(invariant)
            print(f"Generated: {test_path}")
        else:
            print(f"Skipping untestable invariant: {invariant['invariant_name']}")
```

### Pattern 3: Cross-Platform Bug Correlation (This Phase)

```python
# Source: backend/tests/bug_discovery/ai_enhanced/cross_platform_correlator.py
def correlate_platform_bugs():
    """Correlate bugs across web/mobile/desktop."""
    correlator = CrossPlatformCorrelator()

    # Load bugs from all platforms
    web_bugs = load_bugs_from_json("web_bugs.json")
    mobile_bugs = load_bugs_from_json("mobile_bugs.json")
    desktop_bugs = load_bugs_from_json("desktop_bugs.json")

    # Correlate across platforms
    correlated = correlator.correlate_cross_platform_bugs(
        web_bugs=web_bugs,
        mobile_bugs=mobile_bugs,
        desktop_bugs=desktop_bugs,
        similarity_threshold=0.8
    )

    # Report cross-platform bugs
    for correlation in correlated:
        print(f"Cross-platform bug: {correlation['platforms']}")
        print(f"  Similarity: {correlation['similarity_score']}")
        print(f"  Action: {correlation['suggested_action']}")
```

### Pattern 4: Semantic Bug Clustering (This Phase)

```python
# Source: backend/tests/bug_discovery/ai_enhanced/semantic_bug_clusterer.py
async def cluster_bugs_semantically():
    """Cluster bugs by semantic similarity."""
    clusterer = SemanticBugClusterer()

    # Load bugs from discovery run
    bugs = load_bug_reports_from_discovery()

    # Cluster by semantic similarity
    clusters = await clusterer.cluster_bugs(
        bugs=bugs,
        similarity_threshold=0.75,
        min_cluster_size=2
    )

    # Report clusters
    for cluster in clusters:
        print(f"Cluster {cluster['cluster_id']}: {len(cluster['bugs'])} bugs")
        print(f"  Theme: {cluster['theme']}")
        print(f"  Avg similarity: {sum(cluster['similarity_scores']) / len(cluster['similarity_scores']):.2f}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Manual fuzzing targets** | **AI-generated strategies from coverage gaps** | Phase 244 (this phase) | 10x more targeted fuzzing, focuses on business impact priority |
| **Manual invariant identification** | **AI-generated invariants from code analysis** | Phase 244 (this phase) | 5x more property tests, systematic coverage expansion |
| **Separate platform bug tracking** | **Cross-platform bug correlation** | Phase 244 (this phase) | Detect shared root causes across web/mobile/desktop |
| **Manual bug grouping** | **Semantic clustering with embeddings** | Phase 244 (this phase) | Identify systemic issues, reduce duplicate bug filing |

**Deprecated/outdated:**
- **Manual fuzzing target selection**: Replaced by AI-generated strategies from coverage gap analysis
- **Manual invariant discovery**: Replaced by LLM code analysis for property test suggestions
- **Platform-specific bug triage**: Replaced by cross-platform correlation for shared root causes
- **Manual bug clustering**: Replaced by semantic embeddings for intelligent grouping

## Open Questions

1. **LLM provider selection for strategy generation**
   - What we know: LLMService supports OpenAI, Anthropic, DeepSeek, Gemini
   - What's unclear: Which provider is best for code analysis (strategy generation, invariant suggestions)?
   - Recommendation: Use GPT-4o or Claude 3.5 Sonnet for code analysis (best performance), fallback to MiniMax M2.5 for cost savings

2. **Semantic clustering similarity threshold**
   - What we know: Need to balance precision (few clusters, high quality) vs recall (more clusters, potential false positives)
   - What's unclear: What threshold works best for bug error messages (0.75? 0.80? 0.85?)
   - Recommendation: Start with 0.75, validate with manual review of first 100 clusters, adjust based on precision/recall

3. **Cross-platform correlation rate expectations**
   - What we know: Cross-platform bugs are less common than platform-specific bugs
   - What's unclear: What percentage of bugs should be cross-platform (5%? 10%? 20%)?
   - Recommendation: Expect 5-10% cross-platform correlation rate, validate against historical bug data

4. **AI-generated invariant acceptance rate**
   - What we know: LLM may suggest untestable or low-value invariants
   - What's unclear: What percentage of AI-generated invariants should developers accept (30%? 50%? 70%)?
   - Recommendation: Target 50% acceptance rate, improve validation logic if below 30%

5. **Fuzzing strategy validation overhead**
   - What we know: LLM-generated strategies need validation (endpoint exists, test file exists, iterations reasonable)
   - What's unclear: How much validation overhead is acceptable (<10%? <20%? <30%)?
   - Recommendation: Keep validation overhead <20%, if higher, improve LLM prompt with more context

## Sources

### Primary (HIGH confidence)
- **backend/tests/scripts/coverage_gap_analysis.py** - Coverage gap analysis with business impact scoring (370 lines)
- **backend/tests/bug_discovery/core/discovery_coordinator.py** - Unified discovery orchestration (150+ lines)
- **backend/core/embedding_service.py** - FastEmbed, OpenAI, Cohere embeddings (10-20ms local, 100-300ms cloud)
- **backend/core/lancedb_handler.py** - Vector storage and similarity search (dual vector support)
- **backend/core/graphrag_engine.py** - LLM-based entity/relationship extraction for code analysis
- **backend/core/llm_service.py** - Unified LLM interface (OpenAI, Anthropic, DeepSeek, Gemini)
- **backend/tests/property_tests/INVARIANTS.md** - 66 documented property test invariants with formal specifications
- **backend/tests/fuzzing/campaigns/fuzzing_orchestrator.py** - Fuzzing campaign lifecycle management (508 lines)
- **backend/tests/mobile_api/** - Cross-platform testing infrastructure (4 test files, 11K+ lines)

### Secondary (MEDIUM confidence)
- **Phase 238 Research (Property-Based Testing)** - 264+ property tests, Hypothesis 6.92.x, invariant patterns
- **Phase 239 Research (API Fuzzing)** - FuzzingOrchestrator, CrashDeduplicator, Atheris integration
- **Phase 242 Research (Unified Pipeline)** - DiscoveryCoordinator, ResultAggregator, BugDeduplicator
- **coverage.py documentation** - Coverage data collection, coverage.json format, missing lines tracking
- **FastEmbed documentation** - FastEmbed BAAI/bge-small-en-v1.5 model (384 dimensions, 10-20ms)
- **LanceDB documentation** - Vector database, similarity search, cosine distance metrics

### Tertiary (LOW confidence)
- **Web search unavailable** (rate limit exhausted) - Unable to verify AI fuzzing research papers, LLM invariant generation benchmarks
- **Cross-platform bug correlation patterns** (not verified) - Need to validate against historical bug data
- **Semantic clustering thresholds** (not verified) - Need to experiment with actual bug error messages

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All infrastructure verified in codebase (coverage_gap_analysis.py, EmbeddingService, LanceDB, DiscoveryCoordinator, LLMService)
- Architecture: HIGH - Patterns established in Phases 238-243, clear integration points
- Pitfalls: MEDIUM - Identified from LLM limitations and vector search challenges, need validation
- Cross-platform correlation: MEDIUM - Pattern is straightforward, correlation rate needs validation
- Semantic clustering: MEDIUM - Embedding infrastructure exists, threshold tuning needed

**Research date:** 2026-03-25
**Valid until:** 2026-04-24 (30 days - stable AI/LLM infrastructure, proven patterns from Phases 238-243)

**Next steps for planner:**
1. Design FuzzingStrategyGenerator service with LLM integration and validation logic
2. Design InvariantGenerator service with code analysis and testability checks
3. Design CrossPlatformCorrelator with error normalization and similarity scoring
4. Design SemanticBugClusterer with EmbeddingService + LanceDB integration
5. Plan integration with DiscoveryCoordinator (enhance run_full_discovery with AI strategies)
6. Define validation checks for LLM-generated artifacts (strategies, invariants, clusters)
7. Plan cross-platform test data collection (web, mobile, desktop bug reports)
8. Define success metrics (strategy validation rate >80%, invariant acceptance >50%, cross-platform correlation 5-10%, clustering precision >70%)
