---
phase: 244-ai-enhanced-bug-discovery
plan: 01
subsystem: ai-enhanced-bug-discovery
tags: [ai-enhanced, fuzzing, coverage-aware, llm-integration, strategy-generation]

# Dependency graph
requires:
  - phase: 242-unified-bug-discovery-pipeline
    plan: 03
    provides: DiscoveryCoordinator, FuzzingOrchestrator, bug_discovery infrastructure
provides:
  - FuzzingStrategyGenerator service with LLM integration
  - Coverage-aware fuzzing strategy generation
  - Automated fuzzing campaign optimization
affects: [fuzzing-orchestrator, coverage-analysis, bug-discovery-pipeline]

# Tech tracking
tech-stack:
  added:
    - "FuzzingStrategyGenerator: AI-driven fuzzing strategy generation"
    - "FuzzingStrategy: Pydantic model for strategy validation"
    - "BusinessImpact: Enum for priority-based iteration allocation"
  patterns:
    - "LLM integration for intelligent fuzzing strategy generation"
    - "Graceful degradation with fallback strategies on LLM failure"
    - "Coverage gap analysis integration with coverage_gap_analysis.py"
    - "Strategy validation against codebase (endpoint, test file existence)"
    - "JSON persistence for generated strategies"

key-files:
  created:
    - backend/tests/bug_discovery/ai_enhanced/models/fuzzing_strategy.py (46 lines, FuzzingStrategy Pydantic model)
    - backend/tests/bug_discovery/ai_enhanced/fuzzing_strategy_generator.py (306 lines, FuzzingStrategyGenerator service)
    - backend/tests/bug_discovery/ai_enhanced/tests/test_fuzzing_strategy_generator.py (197 lines, 9 unit tests)
    - backend/tests/bug_discovery/storage/strategies/.gitkeep (README with usage documentation)
  modified:
    - backend/tests/bug_discovery/ai_enhanced/__init__.py (import path for FuzzingStrategyGenerator)
    - backend/tests/bug_discovery/ai_enhanced/models/__init__.py (import path for FuzzingStrategy, BusinessImpact)
    - backend/tests/bug_discovery/ai_enhanced/tests/__init__.py (test package initialization)

key-decisions:
  - "LLMService integration using tenant_id parameter (not workspace_id)"
  - "Fallback strategy generation with 50% confidence when LLM fails"
  - "Iteration allocation by business impact: Critical=10000, High=5000, Medium=2000, Low=1000"
  - "Strategy validation checks test file existence (resolved from backend_dir)"
  - "Code snippet extraction with +/- 3 lines context around uncovered lines"
  - "Endpoint inference from file path patterns (agent_governance_service -> /api/v1/agents)"
  - "JSON persistence with MD5 hash-based naming for strategy files"
  - "Pydantic model_dump() instead of deprecated dict() method"

patterns-established:
  - "Pattern: Coverage-aware fuzzing with priority-based strategy generation"
  - "Pattern: LLM integration with graceful degradation fallback"
  - "Pattern: Strategy validation against codebase before FuzzingOrchestrator execution"
  - "Pattern: Business impact-based resource allocation (iterations)"
  - "Pattern: JSON persistence for AI-generated artifacts"

# Metrics
duration: ~6 minutes
completed: 2026-03-25
---

# Phase 244: AI-Enhanced Bug Discovery - Plan 01 Summary

**FuzzingStrategyGenerator: AI-Driven Coverage-Aware Fuzzing with LLM Integration**

## Performance

- **Duration:** ~6 minutes
- **Started:** 2026-03-25T15:05:49Z
- **Completed:** 2026-03-25T15:12:47Z
- **Tasks:** 3
- **Files created:** 4
- **Total lines:** 696 lines (46 + 306 + 197 + 147 README)

## Accomplishments

- **FuzzingStrategyGenerator service created** with LLM integration for intelligent strategy generation
- **FuzzingStrategy Pydantic model** with coverage gap context and validation metadata
- **9 comprehensive unit tests** covering generation, validation, fallback, and file operations
- **Graceful degradation** with fallback strategies when LLM fails (50% confidence)
- **Coverage-aware fuzzing** integrating with coverage_gap_analysis.py output
- **Strategy validation** against codebase (endpoint format, test file existence)
- **Business impact-based iteration allocation** (Critical: 10000, High: 5000, Medium: 2000, Low: 1000)

## Task Commits

Each task was committed atomically:

1. **Task 1: FuzzingStrategy data model** - `e89e5509e` (feat)
2. **Task 2: FuzzingStrategyGenerator service** - `c26605cbc` (feat)
3. **Task 3: Unit tests for FuzzingStrategyGenerator** - `06dfe6893` (feat)

**Plan metadata:** 3 tasks, 3 commits, ~6 minutes execution time

## Files Created

### Created (4 files, 696 lines)

**`backend/tests/bug_discovery/ai_enhanced/models/fuzzing_strategy.py`** (46 lines)

FuzzingStrategy Pydantic model:
- Coverage gap context: `file_path`, `missing_lines`, `business_impact`, `priority_score`
- Fuzzing strategy: `target_endpoint`, `test_file`, `fuzz_target`, `suggested_inputs`, `iterations`, `rationale`
- Validation metadata: `confidence_score` (0.0-1.0), `validated` (bool)
- BusinessImpact enum: CRITICAL, HIGH, MEDIUM, LOW
- Iteration constraints: `ge=1000, le=20000`

**`backend/tests/bug_discovery/ai_enhanced/fuzzing_strategy_generator.py`** (306 lines)

FuzzingStrategyGenerator service:
- `generate_strategies_from_coverage()`: Analyze coverage gap JSON, generate strategies for top N files
- `_generate_fuzzing_strategy()`: LLM-powered strategy generation with code snippet analysis
- `_generate_fallback_strategy()`: Graceful degradation with 50% confidence
- `_validate_strategy()`: Validate LLM-generated strategies against codebase
- `_extract_code_snippet()`: Extract +/- 3 lines context around uncovered lines
- `_infer_endpoint_from_file()`: Map file paths to API endpoints
- `_get_test_file_for_endpoint()`: Map endpoints to fuzzing test files
- `_validate_strategy_against_codebase()`: Check endpoint format and test file existence
- `save_strategies()`: Persist strategies as JSON with MD5 hash-based naming

**`backend/tests/bug_discovery/ai_enhanced/tests/test_fuzzing_strategy_generator.py`** (197 lines, 9 tests)

Unit tests for FuzzingStrategyGenerator:
- `test_generate_strategies_from_coverage`: Strategy generation from coverage gap JSON
- `test_strategy_validation`: Validation status verification
- `test_fallback_strategy_on_llm_failure`: Graceful degradation on LLM failure
- `test_infer_endpoint_from_file`: Endpoint inference from file paths
- `test_get_test_file_for_endpoint`: Test file mapping for endpoints
- `test_validate_strategy_against_codebase`: Strategy validation with valid/invalid endpoints
- `test_save_strategies`: JSON persistence and verification
- `test_extract_code_snippet`: Code snippet extraction with context
- `test_iterations_by_business_impact`: Iteration allocation by business impact

**`backend/tests/bug_discovery/storage/strategies/.gitkeep`** (147 lines README)

Storage directory with documentation:
- File format specification (JSON structure)
- Naming convention (strategy_{timestamp}_{index}.json)
- Usage examples with FuzzingStrategyGenerator
- Integration with FuzzingOrchestrator
- Cleanup guidelines

## Architecture Overview

### Coverage-Aware Fuzzing Pipeline

```
coverage_gap_analysis.py
    ↓ (JSON with priority scores)
FuzzingStrategyGenerator.generate_strategies_from_coverage()
    ↓ (for each top N gap)
LLMService.generate_completion()
    ↓ (JSON strategy or fallback)
FuzzingStrategy validation
    ↓ (endpoint + test file check)
save_strategies()
    ↓ (JSON persistence)
FuzzingOrchestrator.start_campaign()
```

### Strategy Generation Flow

1. **Load Coverage Gap Analysis**
   - Parse coverage_gap_analysis.py output (JSON)
   - Extract top N priority files (default: 10, min_priority_score: 50.0)
   - Get missing_lines, business_impact, priority_score

2. **Generate Strategy for Each Gap**
   - Extract code snippet (+/- 3 lines around uncovered lines)
   - Build LLM prompt with coverage context
   - Call LLMService.generate_completion() (temperature=0.3, max_tokens=500)
   - Parse JSON response (target_endpoint, test_file, fuzz_target, suggested_inputs, iterations, rationale, confidence_score)

3. **Validate Strategy**
   - Check endpoint format: `/api/v1/[\w/-]+`
   - Check test file exists (resolve from backend_dir)
   - Set `validated` flag

4. **Fallback on LLM Failure**
   - Infer endpoint from file path patterns
   - Map to test file using endpoint mapping
   - Use business impact for iterations (Critical: 10000, High: 5000, Medium: 2000, Low: 1000)
   - Set confidence_score=0.5, rationale="Generic fuzzing (LLM failed)"

5. **Persist Strategies**
   - Save as JSON with MD5 hash-based naming
   - Output to `backend/tests/bug_discovery/storage/strategies/`

## Integration Points

### Coverage Gap Analysis

**Source:** `backend/tests/scripts/coverage_gap_analysis.py`

**Input JSON Structure:**
```json
{
  "all_gaps": [
    {
      "file": "backend/core/agent_governance_service.py",
      "coverage_pct": 65.0,
      "uncovered_lines": 45,
      "missing_lines": [100, 101, 102, 150, 151, 200],
      "business_impact": "Critical",
      "priority_score": 85.5
    }
  ]
}
```

**Strategy Generator Usage:**
```python
generator = FuzzingStrategyGenerator()
strategies = await generator.generate_strategies_from_coverage(
    coverage_gap_json="tests/coverage_reports/metrics/backend_164_gap_analysis.json",
    top_n_files=10,
    min_priority_score=50.0
)
```

### FuzzingOrchestrator Integration

**Source:** `backend/tests/fuzzing/campaigns/fuzzing_orchestrator.py`

**Applying Generated Strategies:**
```python
from tests.fuzzing.campaigns.fuzzing_orchestrator import FuzzingOrchestrator

orchestrator = FuzzingOrchestrator(github_token="...", github_repository="owner/repo")

for strategy in strategies:
    result = orchestrator.start_campaign(
        target_endpoint=strategy.target_endpoint,
        test_file=strategy.test_file,
        iterations=strategy.iterations
    )
```

### LLMService Integration

**Source:** `backend/core/llm_service.py`

**LLM Prompt Template:**
```
Analyze this coverage gap and generate a fuzzing strategy.

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
{
    "target_endpoint": "/api/v1/agents/run",
    "test_file": "backend/tests/fuzzing/test_agent_api_fuzzing.py",
    "fuzz_target": "agent_id parameter",
    "suggested_inputs": ["null", "empty string", "sql injection"],
    "iterations": 10000,
    "rationale": "Uncovered lines handle agent_id validation",
    "confidence_score": 0.85
}

Respond ONLY with valid JSON, no explanation.
```

## Test Coverage

### Unit Tests (9 tests, 100% pass rate)

**Coverage by Category:**

1. **Strategy Generation** (2 tests)
   - `test_generate_strategies_from_coverage`: Generate strategies from coverage gap JSON
   - `test_strategy_validation`: Verify validation status on generated strategies

2. **Graceful Degradation** (1 test)
   - `test_fallback_strategy_on_llm_failure`: Fallback strategy with 50% confidence when LLM fails

3. **Endpoint Inference** (2 tests)
   - `test_infer_endpoint_from_file`: Map file paths to API endpoints
   - `test_get_test_file_for_endpoint`: Map endpoints to fuzzing test files

4. **Validation** (1 test)
   - `test_validate_strategy_against_codebase`: Validate with valid/invalid endpoints and test files

5. **Persistence** (1 test)
   - `test_save_strategies`: Save strategies as JSON and verify content

6. **Code Extraction** (1 test)
   - `test_extract_code_snippet`: Extract code snippet with +/- 3 lines context

7. **Business Impact** (1 test)
   - `test_iterations_by_business_impact`: Iteration allocation by business impact tier

**Test Results:**
```
9 passed, 12 warnings in 32.12s
```

## Deviations from Plan

### Rule 1 - Bug: Fixed LLMService initialization

**Found during:** Task 2
**Issue:** LLMService.__init__() uses `tenant_id` parameter, not `workspace_id`
**Fix:** Updated FuzzingStrategyGenerator.__init__() to use `LLMService(tenant_id="default")`
**Files modified:** `backend/tests/bug_discovery/ai_enhanced/fuzzing_strategy_generator.py`
**Commit:** Part of `c26605cbc`

### Rule 3 - Blocking: Fixed test file path resolution

**Found during:** Task 3
**Issue:** `_validate_strategy_against_codebase()` failed because test_file path was relative, not resolved from backend_dir
**Fix:** Updated to resolve relative paths: `test_path = backend_dir / test_file if not Path(test_file).is_absolute() else Path(test_file)`
**Files modified:** `backend/tests/bug_discovery/ai_enhanced/fuzzing_strategy_generator.py`
**Commit:** Part of `06dfe6893`

### Rule 1 - Bug: Fixed Pydantic deprecation

**Found during:** Task 3
**Issue:** Pydantic V2 deprecation warning for `.dict()` method
**Fix:** Updated `strategy.dict()` to `strategy.model_dump()` in save_strategies()
**Files modified:** `backend/tests/bug_discovery/ai_enhanced/fuzzing_strategy_generator.py`
**Commit:** Part of `06dfe6893`

## Next Phase Readiness

✅ **FuzzingStrategyGenerator complete** - AI-driven coverage-aware fuzzing strategy generation

**Ready for:**
- Phase 244 Plan 02: Multi-agent fuzzing orchestration
- Phase 244 Plan 03: AI-generated property-based invariants
- Phase 244 Plan 04: Cross-platform bug correlation

**AI-Enhanced Bug Discovery Infrastructure Established:**
- FuzzingStrategyGenerator with LLM integration
- Coverage-aware strategy generation with business impact prioritization
- Graceful degradation with fallback strategies
- Strategy validation against codebase
- JSON persistence for generated strategies
- 9 comprehensive unit tests with 100% pass rate

## Self-Check: PASSED

All files created:
- ✅ backend/tests/bug_discovery/ai_enhanced/models/fuzzing_strategy.py (46 lines)
- ✅ backend/tests/bug_discovery/ai_enhanced/fuzzing_strategy_generator.py (306 lines)
- ✅ backend/tests/bug_discovery/ai_enhanced/tests/test_fuzzing_strategy_generator.py (197 lines, 9 tests)
- ✅ backend/tests/bug_discovery/storage/strategies/.gitkeep (147 lines README)

All commits exist:
- ✅ e89e5509e - Task 1: FuzzingStrategy data model
- ✅ c26605cbc - Task 2: FuzzingStrategyGenerator service
- ✅ 06dfe6893 - Task 3: Unit tests for FuzzingStrategyGenerator

All verification passed:
- ✅ FuzzingStrategy model with all required fields
- ✅ FuzzingStrategyGenerator with LLM integration
- ✅ 9 unit tests pass (100% pass rate)
- ✅ Strategy validation against codebase
- ✅ Fallback strategy generation on LLM failure
- ✅ Business impact-based iteration allocation
- ✅ JSON persistence for generated strategies

---

*Phase: 244-ai-enhanced-bug-discovery*
*Plan: 01*
*Completed: 2026-03-25*
