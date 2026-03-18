# Phase 206: Coverage Push to 80% - Research

**Researched:** 2026-03-18
**Domain:** Backend Test Coverage Improvement
**Confidence:** HIGH

## Summary

Phase 206 aims to achieve 80% overall backend coverage, building on Phase 205's baseline of 74.69%. Research indicates this is a realistic but challenging target requiring a focused, wave-based approach. The 5.31 percentage point gap represents approximately 58 lines of coverage needed from the current baseline.

**Key findings from Phase 203/204/195/205 analysis:**

1. **Module-focused testing is most effective** - Phase 203 achieved 74.69% by testing individual modules comprehensively (workflow_analytics: 78.17%, workflow_debugger: 71.14%)

2. **Wave-based execution validated** - 4-wave structure (baseline → extend → new → verify) works well for coverage pushes

3. **File-level coverage doesn't always impact overall percentage** - Testing 9 files (~1,900 statements) had minimal impact on 74,000-statement codebase (Phase 204 lesson)

4. **Quality targets over percentage targets** - 88.07% on byok_cost_optimizer exceeded expectations; 47.69% on local_ocr_service accepted due to external dependencies

5. **Collection error stability is critical** - Phase 205 eliminated all collection errors (5 → 0), establishing pytest 7.4+ compliance

**Primary recommendation:** Use the proven 4-wave approach from Phase 204, but target larger modules (>500 statements) and extend partial coverage files (60-75%) to 80%+ for maximum impact.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.4+ | Test framework and collection | Industry standard, async support, fixtures |
| pytest-cov | 4.1+ | Coverage measurement | Built for pytest, branch coverage support |
| pytest-asyncio | 0.21+ | Async test support | Required for FastAPI, async services |
| coverage.py | 7.3+ | Coverage backend | Most accurate coverage measurement |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-mock | 3.10+ | Mocking with pytest | Simplified patch() syntax |
| factory_boy | 3.3+ | Test data generation | Complex model relationships |
| FastAPI TestClient | 0.100+ | API route testing | Built-in FastAPI testing |
| AsyncMock | 3.8+ | Async service mocking | Async method testing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-mock | unittest.mock | pytest-mock provides cleaner fixture-based patching |
| factory_boy | pytest-fixture factories | factory_boy better for complex relationships |
| coverage.py | pytest-cov only | coverage.py provides more detailed HTML reports |

**Installation:**
```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock factory_boy
```

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── tests/
│   ├── coverage/              # Coverage aggregation tests
│   │   └── test_coverage_aggregation.py
│   ├── api/                   # API route coverage tests
│   │   ├── test_*_routes_coverage.py
│   ├── core/                  # Core service coverage tests
│   │   ├── workflow/          # Workflow engine tests
│   │   ├── llm/              # LLM service tests
│   │   └── governance/       # Governance tests
│   ├── tools/                 # Tool coverage tests
│   └── unit/                  # Unit coverage tests
├── conftest.py                # Root fixtures (pytest_plugins)
└── pytest.ini                 # pytest configuration
```

### Pattern 1: 4-Wave Coverage Push
**What:** Organize testing into baseline, extend, new, and verify waves
**When to use:** Systematic coverage improvement phases (5-10% gains)
**Example:**
```python
# Wave 1: Baseline verification
def test_phase_206_baseline_coverage():
    """Verify 74.69% baseline from Phase 205"""
    coverage = get_coverage_report()
    assert coverage['totals']['percent_covered'] == 74.69

# Wave 2-3: Extend partial and test new files
# Wave 4: Verify aggregate coverage
def test_phase_206_final_coverage():
    """Verify 80% overall coverage target"""
    coverage = get_coverage_report()
    assert coverage['totals']['percent_covered'] >= 80.0
```

### Pattern 2: Module-Focused Coverage
**What:** Test individual modules to high coverage (75-80%)
**When to use:** High-impact modules (>200 statements)
**Example:**
```python
# Source: Phase 203 success (workflow_analytics: 78.17%)
def test_workflow_analytics_comprehensive():
    """Test all major paths in workflow_analytics_engine.py"""
    # Initialization
    # Analytics computation
    # Background thread handling
    # Error paths
    # Edge cases
```

### Pattern 3: AsyncMock for Async Services
**What:** Use AsyncMock for async method testing
**When to use:** Testing async service methods
**Example:**
```python
# Source: Phase 205 AsyncMock patterns
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_service_call():
    service = AsyncMock()
    service.process_message.return_value = {"status": "success"}
    result = await service.process_message("test")
    assert result["status"] == "success"
```

### Anti-Patterns to Avoid
- **Testing small files for overall percentage gain** - File-level coverage doesn't impact overall percentage (Phase 204 lesson)
- **Chasing impossible percentages** - External dependencies limit achievable coverage (local_ocr_service: 47.69% accepted)
- **Fixing collection errors last** - Phase 205 fixed errors first, enabling accurate measurement
- **Ignoring schema alignment** - Test code must match actual schema from models.py

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage measurement | Custom coverage scripts | pytest --cov with --cov-branch | Handles branch coverage, HTML reports, JSON export |
| Test data generation | Manual fixture creation | factory_boy | Handles complex relationships, reduces boilerplate |
| Mock management | Manual patch() decorators | pytest-mock fixture | Cleaner syntax, automatic cleanup |
| API testing | Manual request construction | FastAPI TestClient | Built for FastAPI, handles dependencies |
| Async testing | Custom async wrappers | pytest-asyncio | Industry standard, handles event loops |

**Key insight:** Custom coverage scripts are fragile and miss edge cases. pytest-cov handles branch coverage, partial line coverage, and comprehensive reporting out of the box.

## Common Pitfalls

### Pitfall 1: Overall Coverage Not Increasing (Rule 4 - Architectural)
**What goes wrong:** Testing 9 files (~1,900 statements) shows 0% overall improvement
**Why it happens:** Overall percentage dominated by large, already-covered modules
**How to avoid:** Target larger modules (>500 statements) or many medium files
**Warning signs:** File-level coverage improvements but overall percentage unchanged
**Phase 204 example:** 200-250 tests created, 74.69% maintained (not increased)

### Pitfall 2: Collection Errors Blocking Measurement (Rule 3 - Infrastructure)
**What goes wrong:** Cannot run full test suite due to import/syntax errors
**Why it happens:** New test files have import errors, schema drift, Pydantic v2 issues
**How to avoid:** Fix collection errors before coverage measurement (pytest --collect-only)
**Warning signs:** pytest shows "error" during collection, not just "failed"
**Phase 205 achievement:** 5 → 0 collection errors, pytest 7.4+ compliance

### Pitfall 3: Schema Drift Blocking Tests (Rule 4 - Architectural)
**What goes wrong:** Tests fail due to model schema changes in source code
**Why it happens:** Code evolves, tests lag behind (node_id → step_id, trace_id → workflow_execution_id)
**How to avoid:** Verify actual schema from models.py before writing tests
**Warning signs:** Attribute errors, validation errors in tests
**Phase 205 example:** 8 locations in workflow_debugger.py documented, 33 tests passing after alignment

### Pitfall 4: External Dependencies Limiting Coverage (Rule 4 - Reality)
**What goes wrong:** Cannot achieve 75%+ on files with external dependencies
**Why it happens:** PDF converters, OCR engines, WebSocket connections require complex mocking
**How to avoid:** Accept realistic targets (40-50%) for external dependency-heavy files
**Warning signs:** Coverage plateaus at 40-50% despite comprehensive tests
**Phase 204 example:** local_ocr_service 47.69% accepted as realistic

### Pitfall 5: Unreachable Code in Production (Rule 2 - Best Effort)
**What goes wrong:** Tests fail for code paths never executed in production
**Why it happens:** Dead code, defensive programming, legacy paths
**How to avoid:** Use pragma: no cover with explanation, document why unreachable
**Warning signs:** Tests require complex setup for unlikely scenarios
**Best practice:** Document excluded lines with reason

## Code Examples

Verified patterns from Phase 203/204/205 execution:

### Coverage Measurement with pytest-cov
```bash
# Measure coverage with branch measurement
pytest --cov=core --cov=api --cov=tools --cov-branch --cov-report=json --cov-report=html

# Verify collection errors
pytest --collect-only -q | grep error
```

### AsyncMock Pattern (3 variations)
```python
# Source: Phase 205 AsyncMock fixes
from unittest.mock import AsyncMock, patch

# Pattern 1: Function-based service
async def test_productivity_route_with_async_service():
    with patch('api.productivity_routes.get_productivity_service') as mock_get:
        mock_service = AsyncMock()
        mock_service.analyze.return_value = {"score": 85}
        mock_get.return_value = mock_service
        # Test route...

# Pattern 2: Class method
async def test_creative_route_with_class_method():
    with patch('api.creative_routes.CreativeService') as mock_class:
        mock_instance = AsyncMock()
        mock_instance.generate_idea.return_value = {"idea": "test"}
        mock_class.return_value = mock_instance
        # Test route...

# Pattern 3: Instance method (already AsyncMock)
service = AsyncMock()
service.process_message.return_value = {"status": "success"}
```

### Schema Alignment Pattern
```python
# Source: Phase 205 schema fixes
# WRONG (old schema):
WorkflowBreakpoint(node_id="node-1", is_active=True)

# RIGHT (actual schema from models.py):
WorkflowBreakpoint(step_id="step-1", enabled=True)

# Always verify schema from core/models.py before writing tests
```

### Wave Execution Pattern
```python
# Source: Phase 204 4-wave structure
# Wave 1: Baseline verification (Plan 01)
def test_baseline_coverage():
    coverage = get_coverage_report()
    assert coverage['totals']['percent_covered'] == 74.69

# Wave 2-3: Extend partial and test new (Plans 02-06)
# Target specific files with 75%+ coverage

# Wave 4: Verification (Plan 07)
def test_final_coverage():
    coverage = get_coverage_report()
    assert coverage['totals']['percent_covered'] >= 80.0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service-level coverage estimates | Actual line coverage measurement | Phase 163 | Prevents false confidence |
| pytest 6.x | pytest 7.4+ with root conftest | Phase 205 | Eliminates collection errors |
| Test code schema assumptions | Verify actual schema from models.py | Phase 205 | Prevents schema drift failures |
| Percentage-chasing targets | Quality-focused realistic targets | Phase 204 | Higher file-level coverage achieved |
| Manual patch() decorators | pytest-mock fixture | Phase 194+ | Cleaner mock management |

**Deprecated/outdated:**
- **pytest 6.x**: pytest_plugins must be in root conftest in 7.4+ (Phase 205)
- **Service-level estimates**: Actual line coverage required since Phase 163
- **Chasing 100% coverage**: External dependencies make 100% unrealistic (Phase 204 lesson)

## Open Questions

1. **Which files to target for maximum impact?**
   - What we know: Phase 204 showed small files don't impact overall percentage
   - What's unclear: Exact list of files with 60-75% coverage and >200 statements
   - Recommendation: Generate coverage gap analysis from Phase 205 baseline, prioritize large files

2. **Should workflow_debugger.py schema drift be fixed first?**
   - What we know: 8 locations with incorrect attribute names blocking 10 tests
   - What's unclear: Risk level of production code changes, migration requirements
   - Recommendation: Fix test code to match actual schema (lower risk), document source bugs separately

3. **What is realistic test count for 5.31pp improvement?**
   - What we know: Phase 203 created 770+ tests for 9.69pp improvement, Phase 204 created 200-250 tests for 0pp
   - What's unclear: Linear scaling doesn't apply (diminishing returns)
   - Recommendation: Target 300-500 tests across 10-15 files, focusing on high-impact modules

4. **How many waves are optimal?**
   - What we know: 4 waves validated in Phase 204, 3 waves in Phase 203
   - What's unclear: Optimal wave count for 5.31pp improvement
   - Recommendation: Use 4 waves (baseline → extend partial → new → verify) for consistency

## Sources

### Primary (HIGH confidence)
- Phase 205 final summary (.planning/phases/205-coverage-quality-push/205-04-SUMMARY.md) - Coverage quality improvements, test fixes, collection error elimination
- Phase 204 final summary (.planning/phases/204-coverage-push-75-80/204-07-SUMMARY.md) - Wave-based execution, file-level vs overall coverage
- Phase 203 final summary (.planning/phases/203-coverage-push-65/203-11-SUMMARY.md) - Module-focused testing, 770+ tests created
- Phase 195 final summary - API route coverage, integration test suite
- pytest official docs (https://docs.pytest.org) - pytest 7.4+ requirements, pytest_plugins configuration
- pytest-cov documentation (https://pytest-cov.readthedocs.io) - Coverage measurement, branch coverage

### Secondary (MEDIUM confidence)
- pytest-asyncio documentation (https://pytest-asyncio.readthedocs.io) - Async test support
- factory_boy documentation (https://factoryboy.readthedocs.io) - Test data generation
- FastAPI TestClient docs (https://fastapi.tiangolo.com/tutorial/testing/) - API route testing

### Tertiary (LOW confidence)
- None - All findings verified from phase summaries or official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, pytest-cov, pytest-asyncio industry standard
- Architecture: HIGH - 4-wave pattern validated in Phases 203/204/195
- Pitfalls: HIGH - Documented from actual phase deviations
- Realistic targets: HIGH - Based on Phase 203/204/205 execution data

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (30 days - stable testing domain)

**Phase context:**
- Baseline: 74.69% (Phase 205 final)
- Gap to 75%: 0.31pp (8 lines)
- Gap to 80%: 5.31pp (58 lines)
- Collection errors: 0 (pytest 7.4+ compliant)
- Test infrastructure: Production-ready
- Previous phases: 203 (+9.69pp), 204 (0pp, quality focus), 205 (0pp, quality focus)

**Key lessons from previous phases:**
1. Module-focused testing works best (Phase 203: workflow_analytics 78.17%)
2. Small file testing doesn't impact overall percentage (Phase 204: 9 files, 0pp gain)
3. Fix collection errors before measurement (Phase 205: 5 → 0 errors)
4. Accept realistic targets for external dependencies (Phase 204: local_ocr_service 47.69%)
5. Quality over percentage (Phase 204: 5 of 8 files met 75%+ target)
