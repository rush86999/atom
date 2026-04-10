# Phase 290: Comprehensive Test Suite for Auto-Dev Module

## Objective
Create comprehensive unit and integration tests for all auto_dev components achieving 80%+ coverage.

## Scope
- **12 test files** covering all auto_dev components (2,407 lines of code)
- **Target**: 80%+ coverage measured by pytest-cov
- **Performance**: All tests complete in <60 seconds
- **Isolation**: No external dependencies (all mocked)

## Test Files to Create

### 1. conftest.py (100+ lines)
**Shared fixtures for auto_dev tests**
- `mock_auto_dev_llm`: Deterministic LLM responses
- `mock_sandbox`: Simulated ContainerSandbox execution
- `auto_dev_db_session`: Test database with auto_dev models
- `sample_task_event`, `sample_skill_event`, `sample_episode`

### 2. test_event_bus.py (200+ lines)
**EventBus unit tests**
- Publish-subscribe functionality
- Multiple subscribers receive events
- Subscriber exceptions don't crash bus
- TaskEvent and SkillExecutionEvent payloads
- Event filtering by agent_id and tenant_id

### 3. test_base_learning_engine.py (150+ lines)
**BaseLearningEngine abstract interface tests**
- Cannot instantiate abstract class
- Concrete implementation requirements
- LLM service fallback
- Sandbox fallback
- Markdown fence stripping

### 4. test_memento_engine.py (250+ lines)
**MementoEngine skill generation tests**
- analyze_episode() extracts failure patterns
- propose_code_change() generates skill code
- validate_change() executes in sandbox
- promote_skill() creates CommunitySkill
- Event subscription and triggering

### 5. test_reflection_engine.py (200+ lines)
**ReflectionEngine pattern detection tests**
- Listens to task_fail and skill_execution events
- Detects repeated failure patterns
- Triggers MementoEngine after threshold
- Tracks pattern frequency
- Resets patterns after promotion

### 6. test_alpha_evolver_engine.py (300+ lines)
**AlphaEvolverEngine mutation tests**
- analyze_episode() identifies optimization opportunities
- propose_code_change() generates mutations
- validate_change() tests mutations in sandbox
- spawn_variant() creates WorkflowVariant
- Lineage tracking (parent_tool_id)

### 7. test_evolution_engine.py (200+ lines)
**EvolutionEngine monitoring tests**
- Monitors variant performance
- Detects trigger conditions
- Triggers background optimization
- Prunes low-fitness variants
- Publishes evolution events

### 8. test_fitness_service.py (150+ lines)
**FitnessService scoring tests**
- evaluate_initial_proxy(): syntax/compilation/semantic (30%/40%/30%)
- evaluate_delayed_webhook(): success/speed/cost (50%/30%/20%)
- get_top_variants(): stable sorted top N
- Scores normalized to [0.0, 1.0]
- Scoring math verification

### 9. test_advisor_service.py (150+ lines)
**AdvisorService guidance tests**
- generate_guidance() creates human-readable advice
- analyze_variant_performance() provides detailed analysis
- Uses LLMService for guidance
- Handles missing data gracefully
- Caches guidance for performance

### 10. test_container_sandbox.py (200+ lines)
**ContainerSandbox execution tests**
- Executes Python code in Docker
- Falls back to subprocess if Docker unavailable
- Enforces security constraints (timeout, memory)
- Returns execution results
- Handles execution errors gracefully

### 11. test_capability_gate.py (150+ lines)
**AutoDevCapabilityService maturity gate tests**
- can_use_auto_dev() checks agent maturity
- STUDENT and INTERN blocked
- SUPERVISED and AUTONOMOUS allowed
- Tenant opt-in verification
- Capability checks for specific operations

### 12. test_auto_dev_integration.py (200+ lines)
**End-to-end integration tests**
- EpisodeService → EventBus → LearningEngine flow
- MementoEngine full lifecycle (episode → skill)
- AlphaEvolverEngine full lifecycle (episode → variant)
- EvolutionEngine monitoring and optimization
- FitnessService + AdvisorService integration

## Success Criteria
1. ✅ 12 test files created with 2,000+ lines of test code
2. ✅ All tests pass with pytest (0 failures, 0 errors)
3. ✅ Coverage >= 80% for all auto_dev modules
4. ✅ Tests complete in <60 seconds
5. ✅ No external dependencies required (all mocked)
6. ✅ Integration tests verify end-to-end flows
7. ✅ Code follows pytest best practices

## Verification Commands
```bash
# Run all tests
cd atom-upstream
python -m pytest tests/test_auto_dev/ -v

# Check coverage
python -m pytest tests/test_auto_dev/ --cov=core.auto_dev --cov-report=term-missing --cov-report=html

# Performance check
time python -m pytest tests/test_auto_dev/ -v
```

## Next Steps
Execute: `/gsd-execute-phase 290`
