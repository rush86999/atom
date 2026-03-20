# Milestone v5.5: Backend 80% Coverage - Clean Slate

**Created:** 2026-03-20
**Status:** 🚧 **ACTIVE**
**Timeline:** 2-3 weeks (aggressive execution)
**Goal:** Achieve 80% actual line coverage across the entire backend codebase

---

## Executive Summary

Milestone v5.5 is a **fresh start** for achieving 80% backend coverage. After v5.4 (Phase 211) was partially completed with only 1 of 4 plans executed, we're taking a clean slate approach with:

- **Wave-based parallel execution** (not sequential plans)
- **Highest-impact first** (coverage gap × criticality × complexity)
- **Daily verification** (pytest --cov reports every day)
- **Property-based testing** (Hypothesis for critical invariants)
- **CI workflows disabled** (reduce noise until 80% achieved)

**Current Baseline:** ~5.75% overall backend coverage
**Target:** 80% actual line coverage (not service-level estimates)
**Gap:** ~74 percentage points

---

## Why Clean Slate?

### Lessons from v5.4 (Phase 211)

**What Went Wrong:**
1. ❌ Executor claimed completion but didn't execute (Plans 01, 03, 04)
2. ❌ Manual verification needed (test files not created despite "completion")
3. ❌ CI noise distracted from coverage goals (now disabled)
4. ❌ Sequential plans too slow (only 1 of 4 executed)

**What Went Right:**
1. ✅ Plan-based structure worked well (clear tasks, testable outcomes)
2. ✅ Plan 02 executed flawlessly (108 tests, 75-87% coverage)
3. ✅ Documentation comprehensive (STATUS.md, SUMMARY.md, FIXES-SUMMARY.md)
4. ✅ CI disabled successfully (27 workflows archived)

### New Approach for v5.5

1. **Wave-based execution**: Parallel independent tests, not sequential plans
2. **Highest-impact prioritization**: Rank by (coverage gap × criticality × complexity)
3. **Daily verification**: Measure coverage every day, adjust strategy
4. **Manual oversight**: Verify test files exist before marking complete
5. **Re-enable CI after 80%**: Reduce noise, focus on development

---

## Wave-Based Execution Strategy

### Wave 1: Highest-Impact Modules (Priority: CRITICAL)

**Target:** Governance, LLM, episodic memory, API routes

**Modules:**
- `core/agent_governance_service.py` (80% target)
- `core/llm/byok_handler.py` (80% target)
- `core/llm/cognitive_tier_system.py` (80% target)
- `core/episode_segmentation_service.py` (80% target)
- `core/episode_retrieval_service.py` (80% target)
- `core/episode_lifecycle_service.py` (80% target)
- `api/atom_agent_endpoints.py` (80% target)

**Estimated Effort:** 2-3 days (7 modules, ~3,500 lines of tests)

### Wave 2: Core Services (Priority: HIGH)

**Target:** Canvas, browser, device, skills, training

**Modules:**
- `tools/canvas_tool.py` (80% target)
- `tools/browser_tool.py` (80% target)
- `tools/device_tool.py` (80% target)
- `core/skill_adapter.py` (80% target)
- `core/skill_composition_engine.py` (80% target)
- `core/skill_dynamic_loader.py` (80% target)
- `core/student_training_service.py` (80% target)
- `core/supervision_service.py` (80% target)

**Estimated Effort:** 3-4 days (8 modules, ~4,000 lines of tests)

### Wave 3: Database & Integration (Priority: MEDIUM)

**Target:** Models, migrations, external services

**Modules:**
- `core/models.py` (80% target)
- `alembic/versions/*.py` (80% target for migrations)
- `core/agent_world_model.py` (80% target)
- `core/policy_fact_extractor.py` (80% target)
- `tools/atom_cli_skill_wrapper.py` (80% target)

**Estimated Effort:** 2-3 days (5 modules, ~2,500 lines of tests)

### Wave 4: Edge Cases & Property Tests (Priority: MEDIUM)

**Target:** Invariants, error paths, security validation

**Property Tests:**
- Governance invariants (maturity routing, permission checks)
- LLM invariants (cognitive tier classification, cache awareness)
- Episode invariants (segmentation, retrieval, lifecycle)
- Financial invariants (decimal precision, double-entry validation)
- Security invariants (JWT validation, auth checks)

**Estimated Effort:** 2-3 days (100+ property tests, ~2,000 lines)

---

## Daily Verification Process

### Morning Coverage Check

```bash
# Run coverage with HTML report
cd backend
pytest --cov=core --cov=api --cov=tools --cov-report=html --cov-report=term

# Open coverage report
open htmlcov/index.html

# Check overall percentage
# Target: +3-5 percentage points per day
```

### Daily Standup Questions

1. **Coverage achieved yesterday?** (e.g., "5.75% → 10.2%, +4.45pp")
2. **Coverage planned today?** (e.g., "Wave 1: agent_governance_service.py")
3. **Blockers?** (e.g., "Need to mock external API for LLM tests")
4. **Estimated completion?** (e.g., "On track for 80% in 12 days")

### Weekly Progress Review

**Week 1 Target:** 5.75% → 25% (+19.25pp)
- Wave 1: Highest-Impact Modules (7 modules)

**Week 2 Target:** 25% → 55% (+30pp)
- Wave 2: Core Services (8 modules)

**Week 3 Target:** 55% → 80% (+25pp)
- Wave 3: Database & Integration (5 modules)
- Wave 4: Edge Cases & Property Tests

---

## Property-Based Testing Strategy

### Critical Invariants to Test

#### Governance Invariants
1. **Maturity Routing**: STUDENT agents cannot execute automated triggers
2. **Permission Checks**: AUTONOMOUS agents have all permissions, STUDENT have read-only
3. **Cache Consistency**: Governance cache returns same results as DB
4. **Action Complexity**: Higher complexity requires higher maturity

#### LLM Invariants
1. **Cognitive Tier Classification**: Same prompt always classifies to same tier
2. **Cache Awareness**: Cached prompts don't incur LLM costs
3. **Escalation**: Quality threshold breach triggers tier escalation
4. **Provider Fallback**: Primary provider failure falls back to secondary

#### Episode Invariants
1. **Segmentation**: Time gaps always create new episodes
2. **Retrieval**: Semantic search returns relevant episodes
3. **Lifecycle**: Old episodes decay and consolidate
4. **Graduation**: Intervention rate affects graduation eligibility

#### Financial Invariants
1. **Decimal Precision**: All calculations use Decimal, not float
2. **Double-Entry**: Every debit has equal credit
3. **Audit Trail**: All transactions logged immutably
4. **Budget Enforcement**: Costs never exceed approved budgets

### Hypothesis Test Configuration

```python
# Critical invariants (financial, security, data loss)
@given(st.builds(Transaction))
@settings(max_examples=1000)  # High coverage for critical paths
def test_financial_invariants(transaction):
    assert transaction.debit + transaction.credit == Decimal('0')

# Standard invariants (business logic, validation)
@given(st.builds(Agent))
@settings(max_examples=200)  # Moderate coverage
def test_agent_invariants(agent):
    assert agent.maturity in ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']

# IO-bound tests (API, database)
@given(st.from_regex(regex))
@settings(max_examples=50)  # Lower for IO-bound
def test_api_validation(input_data):
    response = client.post("/api/validate", json=input_data)
    assert response.status_code in [200, 400, 422]
```

---

## Success Criteria

### Milestone Complete When:

1. ✅ **80% actual line coverage** (measured by `pytest --cov`)
2. ✅ **All critical paths tested** (governance, security, data integrity)
3. ✅ **Property tests passing** (100+ Hypothesis tests, 1000+ examples)
4. ✅ **Integration tests passing** (external services, browser, device)
5. ✅ **CI workflows re-enabled** (all tests passing, no failures)
6. ✅ **Documentation complete** (SUMMARY.md for each wave)

### Anti-Criteria (What Prevents Completion):

1. ❌ Service-level estimates (must be actual line coverage)
2. ❌ Unverified test files (must exist and pass)
3. ❌ Failing tests (must fix before marking complete)
4. ❌ CI failures (must pass before re-enabling)

---

## Estimated Timeline

| Wave | Duration | Coverage Target | Modules |
|------|----------|-----------------|---------|
| Wave 1 | 2-3 days | 5.75% → 25% (+19.25pp) | 7 modules |
| Wave 2 | 3-4 days | 25% → 55% (+30pp) | 8 modules |
| Wave 3 | 2-3 days | 55% → 70% (+15pp) | 5 modules |
| Wave 4 | 2-3 days | 70% → 80% (+10pp) | Property tests |
| **Total** | **9-13 days** | **5.75% → 80% (+74.25pp)** | **20+ modules** |

**Aggressive Timeline:** 9 days (parallel execution, no blockers)
**Realistic Timeline:** 13 days (some blockers, rework)
**Conservative Timeline:** 15 days (external dependencies, complex fixes)

---

## Next Steps

### Immediate Actions (Day 0)

1. ✅ Create milestone directory (`.planning/phases/212-80pct-coverage-clean-slate/`)
2. ✅ Create MILESTONE.md (this file)
3. ✅ Update PROJECT.md (v5.5 active milestone)
4. 🔲 Run baseline coverage measurement
5. 🔲 Create Wave 1 test files
6. 🔲 Execute Wave 1 tests

### Day 1-3: Wave 1 Execution

1. Create test files for 7 highest-impact modules
2. Run tests and verify 80% coverage per module
3. Measure overall coverage (target: 25%)
4. Create Wave 1 SUMMARY.md

### Day 4-7: Wave 2 Execution

1. Create test files for 8 core service modules
2. Run tests and verify 80% coverage per module
3. Measure overall coverage (target: 55%)
4. Create Wave 2 SUMMARY.md

### Day 8-10: Wave 3 Execution

1. Create test files for 5 database/integration modules
2. Run tests and verify 80% coverage per module
3. Measure overall coverage (target: 70%)
4. Create Wave 3 SUMMARY.md

### Day 11-13: Wave 4 Execution

1. Create 100+ property-based tests
2. Run all Hypothesis tests with max_examples=1000
3. Measure overall coverage (target: 80%)
4. Create Wave 4 SUMMARY.md
5. Re-enable CI workflows
6. Verify all tests passing

---

## Files Created This Milestone

**Milestone Documentation:**
- `.planning/phases/212-80pct-coverage-clean-slate/212-MILESTONE.md` (this file)

**To Be Created:**
- `212-WAVE1-PLAN.md` - Highest-impact modules
- `212-WAVE1-SUMMARY.md` - Wave 1 results
- `212-WAVE2-PLAN.md` - Core services
- `212-WAVE2-SUMMARY.md` - Wave 2 results
- `212-WAVE3-PLAN.md` - Database & integration
- `212-WAVE3-SUMMARY.md` - Wave 3 results
- `212-WAVE4-PLAN.md` - Property tests
- `212-WAVE4-SUMMARY.md` - Wave 4 results
- `212-COMPLETE.md` - Final milestone summary

---

## Commands Reference

```bash
# Baseline coverage measurement
cd backend
pytest --cov=core --cov=api --cov=tools --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_agent_governance_service.py -v

# Run with coverage for specific module
pytest --cov=core.agent_governance_service tests/test_agent_governance_service.py

# Property-based tests with Hypothesis
pytest tests/test_governance_invariants.py -v

# Open coverage report
open htmlcov/index.html

# Check coverage percentage
pytest --cov=core --cov-report=term | grep "TOTAL"
```

---

*Milestone v5.5 created 2026-03-20. Target: 80% backend coverage in 9-13 days.*
