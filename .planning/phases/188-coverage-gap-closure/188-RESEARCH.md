# Phase 188: Coverage Gap Closure (Final Push) - Research

**Researched:** 2026-03-14
**Domain:** Test Coverage Gap Analysis & Test Development
**Confidence:** HIGH

## Summary

Phase 188 is the final coverage push before achieving the 80% backend coverage target. Based on comprehensive analysis of Phase 187 (property-based testing) and Phase 186 (error handling coverage), the primary gaps are: (1) three agent lifecycle services below 50% coverage (evolution loop 18.8%, graduation service 12.1%, promotion service 22.7%), (2) missing unit tests for critical LLM services (cognitive tier system, cache aware router), and (3) overall backend coverage estimated at 74-76%. The phase should use a **hybrid approach**: critical paths (agent lifecycle, LLM routing) to 80%+, moderate-priority services to 50%+, focusing on production code paths over edge cases (already covered in Phase 186).

**Primary recommendation:** Use Phase 186 error path tests + Phase 187 property-based tests as foundation, add targeted unit/integration tests for uncovered happy paths in critical services, aiming for 76%+ overall coverage (3-4 percentage point increase) in 5-6 focused plans.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test runner | Industry standard for Python testing, extensive plugin ecosystem |
| pytest-cov | 7.0.0 | Coverage measurement | Official pytest coverage plugin, generates JSON/HTML reports |
| pytest-asyncio | 1.3.0 | Async test support | Required for testing FastAPI endpoints and async services |
| pytest-xdist | 3.8.0 | Parallel execution | Speeds up test suite with -n auto flag (2-4x speedup) |
| coverage.py | 7.13.4 | Coverage engine | Gold standard for Python coverage measurement, branch coverage support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hypothesis | 6.151.9 | Property-based testing | Already used in Phase 187 for invariant validation (176 tests) |
| httpx | 0.27+ | Async HTTP client | Testing FastAPI endpoints with TestClient replacement |
| faker | 20.0+ | Test data generation | Generating realistic test data for integration tests |
| pytest-mock | 3.12+ | Mocking fixture | Cleaner than unittest.mock, @patch.mock syntax |
| freezegun | 1.5+ | Time mocking | Testing time-dependent logic (episode segmentation, cache expiry) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | unittest is built-in but pytest has 10x better fixture system, parametrization, plugins |
| coverage.py | pytest-cov alone | coverage.py has more powerful CLI, combine both for best results |
| hypothesis | quickcheck | quickcheck is Haskell-only, hypothesis is Python-native with better strategies |
| httpx | requests | requests is synchronous, httpx is async-compatible for FastAPI testing |

**Installation:**
```bash
# All already installed (verified via pip list)
pip install pytest==9.0.2 pytest-cov==7.0.0 pytest-asyncio==1.3.0 pytest-xdist==3.8.0 hypothesis==6.151.9 coverage==7.13.4

# For new test development in Phase 188
pip install pytest-mock freezegun faker
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/
├── unit/
│   ├── agent_lifecycle/
│   │   ├── test_agent_evolution_loop_coverage.py      # Target: 80%+ (currently 18.8%)
│   │   ├── test_agent_graduation_service_coverage.py  # Target: 80%+ (currently 12.1%)
│   │   └── test_agent_promotion_service_coverage.py   # Target: 80%+ (currently 22.7%)
│   ├── llm/
│   │   ├── test_cognitive_tier_system_coverage.py     # New (no tests)
│   │   └── test_cache_aware_router_coverage.py        # New (no tests)
│   └── core_services/
│       └── test_*.py                                  # Fill remaining gaps to 50%+
├── integration/
│   ├── test_agent_lifecycle_integration.py            # End-to-end lifecycle flows
│   └── test_llm_routing_integration.py                # Multi-provider routing tests
└── property_tests/                                      # Phase 187 tests (176 tests, already complete)
    ├── governance/                                     # 38 tests
    ├── llm/                                           # 49 tests
    ├── episodes/                                      # 43 tests
    └── database/                                      # 49 tests
```

### Pattern 1: Coverage-Driven Test Development
**What:** Write tests to specifically cover missing lines identified by coverage.py report, not just "test functionality"

**When to use:** When file has <50% coverage and coverage.json shows specific missing lines

**Example:**
```python
# Source: Phase 186 error path testing pattern
# File: tests/unit/agent_lifecycle/test_agent_evolution_loop_coverage.py

import pytest
from core.agent_evolution_loop import AgentEvolutionLoop

class TestAgentEvolutionLoopCoverage:
    """Coverage-driven tests for agent_evolution_loop.py (currently 18.8%)"""

    def test_run_evolution_cycle_success(self, db_session):
        """Cover lines 129-235: Main evolution cycle execution"""
        # Test happy path through evolution cycle
        # Target: Cover select_parent_group, get_ancestor_lineage, _apply_directives
        loop = AgentEvolutionLoop(db_session)
        result = loop.run_evolution_cycle(agent_id="test-agent")
        assert result.success
        assert result.evolved_config is not None

    def test_select_parent_group_novelty(self, db_session):
        """Cover lines 268-299: Parent selection with novelty scoring"""
        loop = AgentEvolutionLoop(db_session)
        # Test novelty calculation (line 291 - currently uncovered)
        parents = loop.select_parent_group(agent_id="test-agent", group_size=5)
        assert len(parents) == 5
        assert all(p.novelty_score > 0 for p in parents)

    # Add more tests for each uncovered function in coverage report
```

### Pattern 2: Parametrized Tests for Matrix Coverage
**What:** Use pytest.mark.parametrize to test all combinations of parameters

**When to use:** Testing maturity matrix (4 levels × 4 complexities), graduation criteria, cognitive tiers

**Example:**
```python
# Source: Phase 187 property-based testing pattern
# File: tests/unit/llm/test_cognitive_tier_system_coverage.py

import pytest
from core.llm.cognitive_tier_system import CognitiveClassifier

class TestCognitiveTierCoverage:
    """Coverage-driven tests for cognitive_tier_system.py (currently 0%)"""

    @pytest.mark.parametrize("prompt,expected_tier", [
        ("hello", "micro"),
        ("summarize this document", "standard"),
        ("write a complex analysis", "versatile"),
        ("generate a full report with data", "heavy"),
    ])
    def test_classify_prompt_coverage(self, prompt, expected_tier):
        """Cover all tier classification branches (lines 50-150)"""
        classifier = CognitiveClassifier()
        tier = classifier.classify(prompt)
        assert tier.name == expected_tier

    @pytest.mark.parametrize("tokens,semantic_score,task_type,expected_tier", [
        (100, 0.3, "chat", "micro"),
        (1000, 0.5, "generation", "standard"),
        (5000, 0.7, "analysis", "versatile"),
        (10000, 0.9, "complex", "heavy"),
    ])
    def test_classify_with_cache_coverage(self, tokens, semantic_score, task_type, expected_tier):
        """Cover cache-aware classification logic (lines 151-250)"""
        classifier = CognitiveClassifier()
        tier = classifier.classify_with_cache(tokens, semantic_score, task_type)
        assert tier.name == expected_tier
```

### Anti-Patterns to Avoid
- **Test duplication**: Don't write tests that Phase 186/187 already covered (error paths, invariants)
- **Coverage gaming**: Don't write useless tests just to hit lines - test real functionality
- **Mock overuse**: Don't mock everything - use real DB for integration tests (see Phase 182-183 patterns)
- **Ignoring branch coverage**: Line coverage isn't enough - use --cov-branch to catch if/else branches
- **Test order dependence**: Don't assume tests run in order - each test must be independent

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage measurement | Custom coverage script | `pytest --cov=core --cov-report=json` | coverage.py is industry standard, handles branches, exclusion markers, parallel execution |
| Test data generation | Manual fixture creation | `faker` library | faker provides realistic test data (names, emails, dates) without manual work |
| Test isolation | Custom cleanup code | pytest fixtures (autouse=True) | pytest fixtures handle setup/teardown automatically, even on test failure |
| Missing line identification | Grep through source code | `coverage report --skip-covered --omit="tests/*"` | coverage.py shows exactly which lines are missing, no manual analysis needed |
| Mock management | Manual Mock patching | `pytest-mock` fixture | mocker.fixture is cleaner than unittest.mock.patch, auto-undoes patches after test |

**Key insight:** Phase 164 already built coverage gap analysis tooling. Reuse those scripts instead of hand-writing analysis code. The `generate_test_stubs.py` from Phase 164 creates test file skeletons based on missing lines.

## Common Pitfalls

### Pitfall 1: Focusing on Wrong Files
**What goes wrong:** Writing tests for low-value files (e.g., __init__.py, deprecated code) instead of critical business logic

**Why it happens:** Coverage reports show all files equally, doesn't prioritize by business impact

**How to avoid:** Use Phase 164's business impact scoring to prioritize:
- **Critical**: agent lifecycle (evolution, graduation, promotion), LLM routing (cognitive tier, cache router)
- **High**: episode services, governance services
- **Moderate**: API routes, utilities
- **Low**: deprecated code, __init__.py files

**Warning signs:** Spending time on files with no production usage or marked as deprecated

### Pitfall 2: Re-testing Phase 186/187 Coverage
**What goes wrong:** Writing unit tests for error paths that Phase 186 already tested with 814 error path tests

**Why it happens:** Not checking what tests already exist before writing new ones

**How to avoid:** Run `pytest --co -q` to see existing tests, grep for test files matching your target service. Phase 186 covered error paths, Phase 187 covered invariants. Phase 188 should cover **happy paths and missing branches**.

**Warning signs:** Test names like `test_error_handling_` when Phase 186 already has `test_*_error_paths.py`

### Pitfall 3: Ignoring Branch Coverage
**What goes wrong:** Achieving 80% line coverage but only 40% branch coverage (missing if/else branches)

**Why it happens:** pytest-cov defaults to line coverage, branch coverage requires --cov-branch flag

**How to avoid:** Always run `pytest --cov=core --cov-branch --cov-report=term-missing` to see which branches are missing. A single `if` statement requires 2 tests (true/false) for full branch coverage.

**Warning signs:** Coverage report shows 75% but code has many `if` statements without false branch tests

### Pitfall 4: Test Slowness from DB Operations
**What goes wrong:** Unit tests become slow (10+ seconds) due to real DB operations in every test

**Why it happens:** Overusing db_session fixture instead of mocking for pure unit tests

**How to avoid:** Use layered testing approach:
- **Unit tests**: Mock DB, test pure logic (fast, <1s per test)
- **Integration tests**: Real DB, test multi-service flows (slower, but fewer tests)
- **Phase 183-184 patterns**: Use factory_boy for test data, not raw DB inserts

**Warning signs:** Test file takes >30 seconds to run with <20 tests

### Pitfall 5: SQLite vs PostgreSQL Differences
**What goes wrong:** Tests pass with SQLite but fail in production (PostgreSQL) due to DB differences

**Why it happens:** SQLite doesn't enforce foreign keys by default, has different JSON behavior

**How to avoid:** Phase 187 documented this - use PostgreSQL-like settings in SQLite:
```python
# conftest.py
@pytest.fixture(scope="session")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    connection = engine.connect()
    connection.execute(text("PRAGMA foreign_keys=ON"))
    # ... rest of setup
```

**Warning signs:** Tests pass locally but CI fails, or foreign key tests don't catch issues

## Code Examples

Verified patterns from Phase 186-187:

### Coverage-Driven Test Development
```python
# Source: Phase 186 error path testing pattern
# File: tests/unit/agent_lifecycle/test_agent_evolution_loop_coverage.py

import pytest
from core.agent_evolution_loop import AgentEvolutionLoop, EvolutionCycleResult

class TestAgentEvolutionLoopCoverage:
    """Coverage-driven tests to raise agent_evolution_loop.py from 18.8% to 80%+"""

    def test_evolution_cycle_result_to_dict(self):
        """Cover EvolutionCycleResult.to_dict (line 82) - currently uncovered"""
        result = EvolutionCycleResult(
            success=True,
            evolved_config={"model": "gpt-4"},
            parent_configs=[],
            directives_applied=["directive1"],
            validation_passed=True,
            evaluation_score=0.9
        )
        data = result.to_dict()
        assert data["success"] == True
        assert data["evolved_config"] == {"model": "gpt-4"}

    def test_run_evolution_cycle_full_flow(self, db_session):
        """Cover run_evolution_cycle (lines 129-235) - main loop logic"""
        loop = AgentEvolutionLoop(db_session)

        # Setup: Create test agent with config
        agent_id = "test-agent-evolution"
        # ... create agent in DB

        # Execute: Run evolution cycle
        result = loop.run_evolution_cycle(agent_id=agent_id, num_generations=5)

        # Assert: Verify cycle completed
        assert result.success
        assert len(result.evolved_config) > 0
        assert result.evaluation_score > 0.0
```

### Parametrized Coverage for Cognitive Tiers
```python
# Source: Phase 187 parametrized test pattern
# File: tests/unit/llm/test_cognitive_tier_system_coverage.py

import pytest
from core.llm.cognitive_tier_system import CognitiveClassifier, CognitiveTier

class TestCognitiveTierCoverage:
    """Coverage-driven tests for cognitive_tier_system.py (currently 0% coverage)"""

    @pytest.mark.parametrize("prompt,expected_tier,min_tokens,max_tokens", [
        ("hi", CognitiveTier.MICRO, 0, 100),
        ("summarize this", CognitiveTier.STANDARD, 100, 1000),
        ("analyze this data", CognitiveTier.VERSATILE, 1000, 5000),
        ("generate complex report", CognitiveTier.HEAVY, 5000, 10000),
    ])
    def test_classify_by_token_count(self, prompt, expected_tier, min_tokens, max_tokens):
        """Cover token-based classification (lines 50-100)"""
        classifier = CognitiveClassifier()
        tier = classifier.classify(prompt)
        assert tier == expected_tier
        assert min_tokens <= tier.token_range[0] <= tier.token_range[1] <= max_tokens

    @pytest.mark.parametrize("tokens,complexity,expected_tier", [
        (50, 0.2, CognitiveTier.MICRO),
        (500, 0.5, CognitiveTier.STANDARD),
        (2000, 0.7, CognitiveTier.VERSATILE),
        (8000, 0.9, CognitiveTier.HEAVY),
    ])
    def test_classify_with_semantic_complexity(self, tokens, complexity, expected_tier):
        """Cover semantic complexity classification (lines 101-150)"""
        classifier = CognitiveClassifier()
        tier = classifier.classify_with_complexity(tokens, complexity)
        assert tier == expected_tier
```

### Integration Test for Agent Promotion
```python
# Source: Phase 184 integration testing pattern
# File: tests/integration/test_agent_promotion_integration.py

import pytest
from core.agent_promotion_service import AgentPromotionService
from core.agent_graduation_service import AgentGraduationService

class TestAgentPromotionIntegration:
    """Integration tests for agent promotion service (currently 22.7% coverage)"""

    def test_promotion_readiness_full_flow(self, db_session):
        """Cover is_agent_ready_for_promotion (lines 136-158) + evaluation logic (178-355)"""
        service = AgentPromotionService(db_session)

        # Setup: Create agent with episodes, interventions, scores
        agent_id = "test-promotion-agent"
        # ... create agent, episodes, interventions in DB

        # Execute: Check promotion readiness
        readiness = service.is_agent_ready_for_promotion(
            agent_id=agent_id,
            target_maturity="SUPERVISED"
        )

        # Assert: Verify readiness calculation
        assert readiness["ready"] == True
        assert readiness["episode_count"] >= 25
        assert readiness["intervention_rate"] <= 0.20
        assert readiness["constitutional_score"] >= 0.85

    def test_promotion_path_generation(self, db_session):
        """Cover get_promotion_path (lines 367-448)"""
        service = AgentPromotionService(db_session)
        agent_id = "test-promotion-path"

        # Execute: Generate promotion path
        path = service.get_promotion_path(agent_id=agent_id)

        # Assert: Verify path structure
        assert "current_level" in path
        assert "target_level" in path
        assert "requirements" in path
        assert len(path["steps"]) > 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service-level coverage estimates (e.g., "80% governance") | Actual line coverage via coverage.py JSON | Phase 163 (2026-03-11) | Eliminated false confidence from estimates, now measure exact lines |
| Manual gap analysis | Automated gap analysis via Phase 164 tooling | Phase 164 (2026-03-11) | Generates test stubs automatically, prioritizes by business impact |
| Error path testing only | Error paths (Phase 186) + Invariants (Phase 187) + Happy paths (Phase 188) | Phase 186-187 (2026-03-13) | Comprehensive coverage: error handling, mathematical correctness, normal operation |
| Single-tier coverage (line only) | Multi-tier coverage (line + branch) | Phase 163 (2026-03-11) | --cov-branch catches missing if/else branches |

**Deprecated/outdated:**
- **Service-level coverage estimates**: Phase 163 eliminated these - now use actual line coverage from coverage.py
- **Manual gap identification**: Phase 164 built automated tooling - use `scripts/analyze_coverage_gaps.py` instead of manual grep
- **Ignoring branch coverage**: Phase 163 added --cov-branch to all test runs - branch coverage is now mandatory

## Open Questions

1. **What is the ACTUAL current backend coverage?**
   - What we know: Phase 187 shows 74.55% in limited coverage.json (only 3 files), Phase 186 reports 75%+ on error paths
   - What's unclear: True overall backend coverage across all 6,118 source files
   - Recommendation: Run `pytest --cov=core --cov=api --cov=tools --cov-report=json --cov-branch` at start of Phase 188 to establish accurate baseline

2. **Should we focus on quality (critical paths) or quantity (all files)?**
   - What we know: 3 critical files <50% (evolution, graduation, promotion), LLM services have zero unit tests
   - What's unclear: Whether to achieve 80% on critical files or 50% across all files
   - Recommendation: **Hybrid approach** - Critical files to 80%+ (agent lifecycle, LLM routing), moderate files to 50%+, skip low-value deprecated code

3. **How many tests needed to reach 76%+ coverage?**
   - What we know: Phase 186 added 375 tests for ~13.7% improvement, Phase 187 added 176 property-based tests
   - What's unclear: Diminishing returns - each percent harder to achieve
   - Recommendation: Estimate 150-200 focused tests for 3-4 percentage point increase (74% → 76-78%), using coverage-driven development

4. **Are there test infrastructure blockers?**
   - What we know: Phase 187 found SQLite JSONB compatibility issues, pytest-rerunfailures plugin missing
   - What's unclear: Other infrastructure issues that might block Phase 188
   - Recommendation: Verify test infrastructure works before starting (pytest --version, pip list, test run with --co)

## Sources

### Primary (HIGH confidence)
- **Phase 187 Verification Report** - .planning/phases/187-property-based-testing/187-VERIFICATION.md (582 lines, comprehensive)
  - 176 property-based tests across 4 domains
  - 99.4% pass rate (175/176 passing)
  - 0 production bugs found (all invariants verified)
- **Phase 186 Aggregate Summary** - .planning/phases/186-edge-cases-error-handling/186-AGGREGATE-SUMMARY.md (880 lines)
  - 814 total tests (375 new in Phase 186)
  - 75%+ coverage on error handling paths
  - 347 VALIDATED_BUG findings documented
- **coverage.json** - backend/coverage.json (limited sample: 3 files, 16.82% average)
  - agent_evolution_loop.py: 18.8% (36/191 lines)
  - agent_graduation_service.py: 12.1% (29/240 lines)
  - agent_promotion_service.py: 22.7% (29/128 lines)
- **ROADMAP.md** - .planning/ROADMAP.md (Phase 188 specification)
  - Goal: Close remaining coverage gaps to approach 80% target
  - Success criteria: All zero-coverage files tested, below-50% files raised above 50%, overall 76%+ coverage

### Secondary (MEDIUM confidence)
- **Phase 164-183 Plans** - Gap analysis, test stub generation, integration testing patterns
  - Coverage gap analysis tooling with business impact scoring
  - Test prioritization service with phased roadmap generation
  - Integration testing patterns from Phases 182-184 (skill execution, package governance, database layer)
- **pytest documentation** - https://docs.pytest.org/ (verified 2026-03-14)
  - Parametrization patterns, fixture usage, coverage integration
- **coverage.py documentation** - https://coverage.readthedocs.io/ (verified 2026-03-14)
  - Branch coverage (--cov-branch), JSON report format, missing line reporting

### Tertiary (LOW confidence)
- **Test file enumeration** - Found 1,343 test files in backend/tests/ (needs verification of quality/completeness)
- **Source file analysis** - 6,118 total Python files, 203 with tests, 5,711 without tests (needs filtering for production code)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest/coverage.py are industry standards, versions verified via pip list
- Architecture: HIGH - Phase 186-187 established patterns, verified in aggregate summaries
- Pitfalls: HIGH - Phase 186 documented 347 bugs, Phase 187 infrastructure issues well-documented
- Coverage gaps: MEDIUM - Limited coverage.json sample (3 files only), need full baseline at Phase 188 start
- Test count estimates: MEDIUM - Based on Phase 186 ratio (375 tests for 13.7% improvement), diminishing returns expected

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (30 days - testing infrastructure and coverage goals stable)

---

## Appendix: File-by-File Gap Analysis

### Critical Priority (<50% coverage, high business impact)

1. **core/agent_evolution_loop.py** (18.8%, 36/191 lines, 155 missing)
   - Missing: run_evolution_cycle (27 lines), select_parent_group (11 lines), get_ancestor_lineage (16 lines), _apply_directives_to_clone (25 lines)
   - Estimated tests needed: 30-40 tests for 80%+ coverage
   - Priority: HIGH - Agent evolution is core to autonomous agent improvement

2. **core/agent_graduation_service.py** (12.1%, 29/240 lines, 211 missing)
   - Missing: calculate_readiness_score (24 lines), run_graduation_exam (13 lines), validate_constitutional_compliance (11 lines), promote_agent (17 lines)
   - Estimated tests needed: 40-50 tests for 80%+ coverage
   - Priority: HIGH - Agent graduation controls maturity progression (critical governance)

3. **core/agent_promotion_service.py** (22.7%, 29/128 lines, 99 missing)
   - Missing: is_agent_ready_for_promotion (10 lines), _evaluate_agent_for_promotion (67 lines), get_promotion_path (14 lines)
   - Estimated tests needed: 20-30 tests for 80%+ coverage
   - Priority: HIGH - Promotion service determines when agents can advance

### Zero Coverage (no dedicated tests, critical services)

4. **core/llm/cognitive_tier_system.py** (0% estimated, no test files found)
   - Missing: All tier classification logic, cache-aware routing, cost estimation
   - Estimated tests needed: 30-40 tests for 80%+ coverage
   - Priority: HIGH - Cognitive tier controls LLM routing and cost management

5. **core/llm/cache_aware_router.py** (0% estimated, no test files found)
   - Missing: Cache key generation, lookup logic, TTL handling, miss handling
   - Estimated tests needed: 20-30 tests for 80%+ coverage
   - Priority: HIGH - Cache router reduces LLM costs by 90% (Phase 68 achievement)

**Total estimated tests for critical gaps:** 140-190 focused tests to raise 5 critical files from <25% to 80%+ coverage

### Estimated Coverage Impact

Assuming current overall coverage is 74-75% (based on Phase 186-187 reports):
- 5 critical files: ~500 lines of production code
- 140-190 new tests: ~2,000-3,000 lines of test code
- Expected coverage increase: 3-4 percentage points (74% → 77-78%)
- Realistic target: 76%+ overall backend coverage (Phase 188 success criteria)
