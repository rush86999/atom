# Phase 303 Quality Standards: Stub Test Detection and Prevention

**Phase**: 303 - Quality-Focused Stub Test Fixes
**Document**: 303-QUALITY-STANDARDS.md
**Date**: 2026-04-25
**Purpose**: Establish quality standards and stub test detection checklist to prevent future stub test creation

---

## Section 1: Stub Test Detection Checklist

### What Are Stub Tests?

**Stub tests** are placeholder tests that validate Python syntax but don't test actual production code. They contribute 0% to coverage goals despite existing in the test suite.

**Example Stub Test**:
```python
class TestVersionCreation:
    def test_create_version(self):
        version = {"id": "v1", "workflow_id": "wf-001"}
        assert version["id"] == "v1"  # Tests dict, not WorkflowVersion!
```

**Problem**: Test validates `dict` operations but never imports `WorkflowVersion` from target module.

### 4 Critical Criteria for Stub Tests

**A test is a STUB if ALL of the following are true**:

1. ❌ **No Import of Target Module**
   - Test file does NOT import from target module (e.g., `from core.advanced_workflow_system import`)
   - Or imports are generic (e.g., `from core.models import *` without specific classes)

2. ❌ **Tests Assert on Generic Python Operations**
   - Tests assert on `dict`, `list`, `eval`, `for` loops, `if` statements
   - Tests don't assert on production code behavior (model validation, business logic)

3. ❌ **No AsyncMock/Mock Patches of Target Module**
   - No `patch('core.module_name.ClassName')` or `patch('core.module_name.function')`
   - No mocking of database operations, LLM calls, or external dependencies

4. ❌ **0% Coverage Despite Having Test Code**
   - Coverage report shows 0% for target module
   - Tests pass but contribute nothing to coverage goals

### Auto-Detection Script

```bash
#!/bin/bash
# detect_stub_tests.sh - Detect stub tests in test suite

for test_file in tests/test_*.py; do
    module_name=$(basename "$test_file" .py | sed 's/test_//')
    target_module="core.${module_name}"

    echo "=== Checking $test_file ==="

    # Check 1: Import target module
    if grep -q "^from ${target_module} import" "$test_file"; then
        echo "✅ Import found: from ${target_module} import"
    else
        echo "❌ NO IMPORT: Does not import from ${target_module}"
    fi

    # Check 2: Generic assertions
    if grep -q "assert.*\[" "$test_file" || grep -q "assert eval" "$test_file"; then
        echo "⚠️  Generic assertions detected (dict/list/eval)"
    fi

    # Check 3: Coverage
    coverage=$(pytest "$test_file" --cov="${target_module}" --cov-report=json -q 2>/dev/null | grep -oP '\d+(?=%)' || echo "0")
    if [ "$coverage" -eq "0" ]; then
        echo "❌ ZERO COVERAGE: ${coverage}% for ${target_module}"
    else
        echo "✅ Coverage: ${coverage}%"
    fi

    echo ""
done
```

### Manual Review Checklist

Before committing new tests, verify:

- [ ] Test file imports from target module (e.g., `from core.module_name import ClassName`)
- [ ] Tests assert on production code behavior (not generic Python operations)
- [ ] Tests use AsyncMock/Mock for external dependencies (database, LLM, API calls)
- [ ] Coverage report shows >0% for target module
- [ ] Test count is reasonable (15-30 tests for comprehensive coverage)
- [ ] Test file size is 400+ lines (for 15-30 tests)
- [ ] Tests follow Phase 297-298 patterns (see Section 2)

---

## Section 2: Phase 297-298 AsyncMock Patterns (Reference)

### Proper Import Pattern

**Import specific classes from target module**:

```python
# ✅ CORRECT: Import specific classes
from core.advanced_workflow_system import (
    ParameterType,
    WorkflowState,
    InputParameter,
    WorkflowStep,
    MultiOutputConfig,
    AdvancedWorkflowDefinition,
)

# ❌ WRONG: No imports
# (stub tests don't import anything)

# ❌ WRONG: Generic imports
from core.advanced_workflow_system import *
```

### AsyncMock Fixture Pattern

**Use AsyncMock for external dependencies**:

```python
from unittest.mock import AsyncMock, patch
import pytest

class TestAtomMetaAgentInit:
    """Test AtomMetaAgent initialization."""

    def test_initialization_with_default_workspace(self):
        """Agent initializes with default workspace."""
        with patch('core.atom_meta_agent.WorldModelService'):
            with patch('core.atom_meta_agent.AgentGovernanceService'):
                with patch('core.atom_meta_agent.AgentFleetService'):
                    agent = AtomMetaAgent()
                    assert agent.workspace_id == "default"
```

**Key Points**:
- Patch at import level (e.g., `patch('core.module_name.ClassName')`)
- Use context managers for patches
- Assert on actual behavior (not generic operations)

### Database Session Pattern

**Mock database sessions**:

```python
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

class TestAgentGovernance:
    """Test agent governance with database mocking."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock(spec=Session)
        return db

    def test_create_agent_with_mock_db(self, mock_db):
        """Test agent creation with mocked database."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        agent = AgentRegistry(
            agent_id="test-agent",
            name="Test Agent",
            agent_type="assistant"
        )

        mock_db.add(agent)
        mock_db.commit()

        assert agent.agent_id == "test-agent"
        mock_db.add.assert_called_once()
```

### LLM Service Mocking Pattern

**Mock LLM service calls**:

```python
from unittest.mock import AsyncMock, patch

class TestLLMIntegration:
    """Test LLM integration with AsyncMock."""

    @pytest.mark.asyncio
    async def test_streaming_response(self):
        """Test streaming LLM response."""
        with patch('core.llm.LLMService') as mock_llm:
            mock_llm.return_value.stream_response = AsyncMock(
                return_value=["token1", "token2", "token3"]
            )

            llm_service = LLMService()
            tokens = []
            async for token in llm_service.stream_response("test prompt"):
                tokens.append(token)

            assert tokens == ["token1", "token2", "token3"]
```

### Success + Error Path Testing

**Test both success and error cases**:

```python
from pydantic import ValidationError
import pytest

class TestModelValidation:
    """Test Pydantic model validation."""

    def test_valid_input(self):
        """Test model accepts valid input."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-001",
            name="Test Workflow",
            description="A test workflow"
        )
        assert workflow.workflow_id == "wf-001"

    def test_invalid_input(self):
        """Test model rejects invalid input."""
        with pytest.raises(ValidationError):
            AdvancedWorkflowDefinition(
                name="Invalid Workflow"
                # Missing required workflow_id
            )
```

---

## Section 3: Test Creation Standards

### Test Structure Requirements

1. **Class-Based Organization**:
   ```python
   class TestAdvancedWorkflowDefinition:
       """Test AdvancedWorkflowDefinition workflow creation and validation."""

       def test_workflow_creation(self):
           """AdvancedWorkflowDefinition can be created with valid parameters."""
           # Test implementation
   ```

2. **Descriptive Test Names**:
   - Use `test_` prefix
   - Name should describe what is being tested
   - Example: `test_workflow_creation_with_valid_steps`

3. **Docstrings for Tests**:
   - Every test should have a docstring
   - Docstring should explain what behavior is being tested
   - Example: `"""AdvancedWorkflowDefinition can be created with valid parameters."""`

### Import Requirements

1. **Import Target Module**:
   ```python
   from core.module_name import ClassName, FunctionName
   ```

2. **Import Test Dependencies**:
   ```python
   import pytest
   from unittest.mock import AsyncMock, patch
   from pydantic import ValidationError
   from datetime import datetime, timezone
   ```

3. **Import Production Models** (if testing relationships):
   ```python
   from core.models import AgentRegistry, AgentStatus, User
   ```

### Assertion Requirements

1. **Assert on Actual Behavior**:
   ```python
   # ✅ CORRECT: Assert on production code behavior
   assert workflow.workflow_id == "wf-001"
   assert workflow.state == WorkflowState.DRAFT

   # ❌ WRONG: Assert on generic Python operations
   assert version["id"] == "v1"
   assert len(steps) > 0
   ```

2. **Specific Assertions**:
   ```python
   # ✅ CORRECT: Specific assertion
   assert agent.maturity_level == MaturityLevel.AUTONOMOUS

   # ❌ WRONG: Generic assertion
   assert agent is not None
   ```

### Fixture Requirements

1. **Use AsyncMock for Async Operations**:
   ```python
   from unittest.mock import AsyncMock

   mock_service = AsyncMock()
   mock_service.execute.return_value = "result"
   ```

2. **Patch at Import Level**:
   ```python
   # ✅ CORRECT: Patch at import level
   with patch('core.atom_meta_agent.WorldModelService'):
       agent = AtomMetaAgent()

   # ❌ WRONG: Patch at class level (doesn't work)
   with patch.object(WorldModelService, '__init__', return_value=None):
       agent = AtomMetaAgent()
   ```

3. **Mock Database Sessions**:
   ```python
   @pytest.fixture
   def mock_db(self):
       """Mock database session."""
       db = Mock(spec=Session)
       db.query.return_value.filter.return_value.first.return_value = None
       return db
   ```

### Coverage Requirements

1. **Target 25-30% Coverage** (for model/dataclass testing):
   - Enum definitions: 100% covered
   - Model/dataclass fields: 80% covered
   - Validation logic: 60% covered
   - Business logic methods: 40% covered

2. **Minimum Coverage**:
   - Must achieve >0% coverage (not stub tests)
   - Should achieve 15%+ coverage for meaningful testing
   - Ideal: 25-30% coverage for comprehensive testing

3. **Measure Coverage**:
   ```bash
   pytest tests/test_module.py --cov=core.module --cov-report=term-missing --cov-report=json
   ```

### Pass Rate Requirements

1. **Target 95%+ Pass Rate**:
   - 95%+ tests passing is acceptable
   - 100% pass rate is ideal
   - <90% pass rate needs investigation

2. **Handle Expected Failures**:
   - Use `pytest.mark.xfail` for known issues
   - Use `pytest.mark.skip` for incomplete tests
   - Document why test is skipped/expected to fail

---

## Section 4: Bulk Test Creation Anti-Patterns

### ❌ Anti-Pattern 1: Don't Create Placeholder Tests

**Wrong**:
```python
class TestDynamicGeneration:
    def test_generate_workflow_from_template(self):
        template = {"name": "test_template", "steps": [{"action": "test"}]}
        assert template is not None  # Placeholder!
```

**Correct**:
```python
class TestAdvancedWorkflowDefinition:
    def test_workflow_creation(self):
        """AdvancedWorkflowDefinition can be created with valid parameters."""
        workflow = AdvancedWorkflowDefinition(
            workflow_id="wf-001",
            name="Test Workflow",
            description="A test workflow"
        )
        assert workflow.workflow_id == "wf-001"
```

### ❌ Anti-Pattern 2: Don't Test Generic Python Operations

**Wrong**:
```python
def test_for_loop_execution(self):
    items = ["a", "b", "c"]
    results = []
    for item in items:
        results.append(item.upper())
    assert len(results) == 3  # Tests Python for loop!
```

**Correct**:
```python
def test_workflow_step_execution(self):
    """WorkflowStep can execute with valid inputs."""
    step = WorkflowStep(
        step_id="step-1",
        name="First Step",
        description="Execute first step",
        step_type="processing"
    )
    assert step.step_id == "step-1"
    assert step.can_pause is True
```

### ❌ Anti-Pattern 3: Don't Skip Imports of Target Modules

**Wrong**:
```python
# No imports from target module
class TestVersionCreation:
    def test_create_version(self):
        version = {"id": "v1", "workflow_id": "wf-001"}
        assert version["id"] == "v1"
```

**Correct**:
```python
from core.workflow_versioning_system import WorkflowVersion, VersionType

class TestWorkflowVersion:
    def test_version_creation(self):
        """WorkflowVersion can be created with valid parameters."""
        version = WorkflowVersion(
            workflow_id="wf-001",
            version="1.0.0",
            version_type=VersionType.MAJOR,
            # ... other required fields
        )
        assert version.workflow_id == "wf-001"
```

### ❌ Anti-Pattern 4: Don't Use eval() for Condition Testing

**Wrong**:
```python
def test_evaluate_condition(self):
    condition = "value > 5"
    context = {"value": 10}
    result = eval(condition, {}, context)  # Unsafe!
    assert result is True
```

**Correct**:
```python
def test_workflow_conditional_execution(self):
    """Workflow executes steps conditionally based on state."""
    workflow = AdvancedWorkflowDefinition(
        workflow_id="wf-001",
        name="Conditional Workflow",
        steps=[
            WorkflowStep(
                step_id="step-1",
                name="First Step",
                condition={"state": "running"},
                step_type="processing"
            )
        ]
    )
    assert workflow.steps[0].condition == {"state": "running"}
```

### ❌ Anti-Pattern 5: Don't Assert on Dict Operations for Model Testing

**Wrong**:
```python
def test_create_version(self):
    version = {"id": "v1", "workflow_id": "wf-001"}
    assert version["id"] == "v1"  # Tests dict, not model!
```

**Correct**:
```python
def test_version_creation(self):
    """WorkflowVersion can be created with valid parameters."""
    version = WorkflowVersion(
        workflow_id="wf-001",
        version="1.0.0",
        version_type=VersionType.MAJOR,
        # ... other required fields
    )
    assert version.workflow_id == "wf-001"
    assert version.version == "1.0.0"
```

---

## Section 5: Quality Gate for Phase 304+

### PRE-CHECK Requirements

**Before executing any phase, run this checklist**:

1. **Verify Imports**:
   ```bash
   grep -h "^from core\." tests/test_<module>.py | head -5
   ```
   - ✅ Import from target module found
   - ❌ NO IMPORTS FOUND → Fix before proceeding

2. **Run Coverage**:
   ```bash
   pytest tests/test_<module>.py --cov=core.<module> --cov-report=term
   ```
   - ✅ Coverage >0% → Proceed
   - ❌ Coverage 0% → Stub test detected, fix before proceeding

3. **Count Tests**:
   ```bash
   grep -c "def test_" tests/test_<module>.py
   ```
   - ✅ 15-30 tests → Good
   - ⚠️ <15 tests → Consider expanding
   - ⚠️ >30 tests → Review for redundancy

4. **Check File Size**:
   ```bash
   wc -l tests/test_<module>.py
   ```
   - ✅ 400+ lines → Good
   - ⚠️ <400 lines → May be incomplete

### Stub Test Auto-Detection

**Automated detection before committing**:

```bash
#!/bin/bash
# pre_commit_check.sh - Run before committing test files

# Check for stub tests
if grep -q "^def test_" tests/test_*.py; then
    echo "Checking for stub tests..."

    for test_file in tests/test_*.py; do
        module_name=$(basename "$test_file" .py | sed 's/test_//')

        # Check 1: Import target module
        if ! grep -q "^from core.${module_name} import" "$test_file"; then
            echo "❌ STUB TEST DETECTED: $test_file (no import from core.${module_name})"
            exit 1
        fi

        # Check 2: Coverage >0%
        coverage=$(pytest "$test_file" --cov="core.${module_name}" --cov-report=json -q 2>/dev/null | jq -r '.totals.percent_covered' || echo "0")
        if [ "$coverage" = "0" ] || [ "$coverage" = "0.0" ]; then
            echo "❌ STUB TEST DETECTED: $test_file (0% coverage for core.${module_name})"
            exit 1
        fi
    done

    echo "✅ No stub tests detected"
else
    echo "No test files to check"
fi
```

### Coverage Thresholds

**Minimum requirements for new test files**:

| Metric | Minimum | Target | Ideal |
|--------|---------|--------|-------|
| Coverage | >0% | 15%+ | 25-30% |
| Test Count | 10 | 15-30 | 20-25 |
| Test Lines | 200 | 400+ | 500-600 |
| Pass Rate | 90% | 95%+ | 100% |

**Quality gate rules**:
- Coverage must be >0% (not stub tests)
- Pass rate must be 95%+ (high quality)
- Test count should be 15-30 (comprehensive)
- Test file size should be 400+ lines (thorough)

---

## Section 6: Remediation Patterns

### How to Rewrite Stub Tests

**Follow Plan 303-01/303-02 patterns**:

1. **Import Actual Classes**:
   ```python
   from core.module_name import ClassName, AnotherClass
   ```

2. **Delete Stub Tests**:
   ```python
   # DELETE: def test_generate_workflow_from_template(self):
   # DELETE:     template = {"name": "test_template"}
   # DELETE:     assert template is not None
   ```

3. **Write Proper Tests**:
   ```python
   class TestClassName:
       def test_model_creation(self):
           """ClassName can be created with valid parameters."""
           instance = ClassName(
               field1="value1",
               field2="value2"
           )
           assert instance.field1 == "value1"

       def test_model_validation(self):
           """ClassName validates required fields."""
           with pytest.raises(ValidationError):
               ClassName(field1="value1")  # Missing field2
   ```

4. **Run Coverage**:
   ```bash
   pytest tests/test_module.py --cov=core.module --cov-report=term
   ```

5. **Verify >0% Coverage**:
   - If 0% → Still stub test, fix imports
   - If >0% → Success, commit

### How to Fix Fixture Issues

**Common fixture issues from Phases 300-301**:

1. **Incorrect Patching**:
   ```python
   # ❌ WRONG: Patching non-existent function
   with patch('core.byok_handler.load_config'):
       handler = BYOKHandler()

   # ✅ CORRECT: Patching actual dependency
   with patch('core.byok_handler.SessionLocal'):
       handler = BYOKHandler()
   ```

2. **Missing db Argument**:
   ```python
   # ❌ WRONG: Missing db argument
   def test_segment_episode(self):
       service = EpisodeSegmentationService()
       service.segment_episode("episode_id")

   # ✅ CORRECT: Include db argument
   def test_segment_episode(self, mock_db):
       service = EpisodeSegmentationService(mock_db)
       service.segment_episode("episode_id")
   ```

3. **Integration Test Assumptions**:
   ```python
   # ❌ WRONG: Integration test in unit test
   def test_llm_call(self):
       llm = LLMService()
       response = llm.call("prompt")  # Requires API key!

   # ✅ CORRECT: Mock external dependency
   def test_llm_call(self):
       with patch('core.llm.LLMService') as mock_llm:
           mock_llm.return_value.call.return_value = "response"
           llm = LLMService()
           response = llm.call("prompt")
           assert response == "response"
   ```

### How to Improve Failing Tests

**Steps to fix failing tests**:

1. **Identify Failure Pattern**:
   - AssertionError → Fix assertion or test data
   - ImportError → Fix import paths
   - AttributeError → Fix patch paths or mock setup
   - ValidationError → Fix test data (missing required fields)

2. **Fix Patch Paths**:
   ```python
   # Patch where module is IMPORTED, not where it's defined
   # ❌ WRONG
   with patch('core.llm.llm_service.OpenAI'):
       ...

   # ✅ CORRECT
   with patch('core.byok_handler.OpenAI'):  # Patch where used
       ...
   ```

3. **Add Missing Dependencies**:
   ```python
   # Add fixtures for database, LLM, external services
   @pytest.fixture
   def mock_db(self):
       db = Mock(spec=Session)
       db.query.return_value.filter.return_value.first.return_value = None
       return db
   ```

4. **Update Assertions**:
   ```python
   # Make assertions specific and meaningful
   # ❌ WRONG
   assert result is not None

   # ✅ CORRECT
   assert result.status == "success"
   assert result.data["key"] == "expected_value"
   ```

---

## Section 7: Reference Examples

### Example 1: Plan 303-01 Test Structure

**File**: `tests/test_advanced_workflow_system.py` (24 tests, 451 lines, 27% coverage)

**Structure**:
- TestParameterTypeEnum (3 tests)
- TestWorkflowStateEnum (3 tests)
- TestInputParameter (4 tests)
- TestWorkflowStep (3 tests)
- TestMultiOutputConfig (1 test)
- TestAdvancedWorkflowDefinition (10 tests)

**Key Features**:
- ✅ Imports from target module (6 classes)
- ✅ Tests Pydantic model validation
- ✅ Tests business logic (state transitions, missing inputs)
- ✅ 100% pass rate (24/24 passing)
- ✅ 27% coverage (exceeds 25-30% target)

### Example 2: Plan 303-02 Test Structure

**File**: `tests/test_workflow_versioning_system.py` (17 tests, 289 lines, 15% coverage)

**Structure**:
- TestVersionTypeEnum (3 tests)
- TestChangeTypeEnum (3 tests)
- TestWorkflowVersion (4 tests)
- TestVersionDiff (3 tests)
- TestBranchAndConflict (4 tests)

**Key Features**:
- ✅ Imports from target module (6 classes)
- ✅ Tests dataclass validation
- ✅ Tests version metadata and diffs
- ✅ 100% pass rate (17/17 passing)
- ✅ 15% coverage (acceptable for dataclass testing)

### Example 3: Phase 297 Test Structure

**File**: `tests/test_atom_meta_agent.py` (33 tests, 627 lines)

**Structure**:
- TestSpecialtyAgentTemplate (8 tests)
- TestAtomMetaAgentInit (5 tests)
- TestIntentClassification (7 tests)
- TestAgentRouting (6 tests)
- TestAgentLifecycle (7 tests)

**Key Features**:
- ✅ Imports from target module (4 classes)
- ✅ Uses AsyncMock for external dependencies
- ✅ Tests business logic (domain creation, agent routing)
- ✅ Patches at import level
- ✅ 100% pass rate

---

## Conclusion

This quality standards document establishes:

1. **Stub Test Detection**: 4 critical criteria for identifying stub tests
2. **Auto-Detection Script**: Bash script to detect stub tests before committing
3. **Quality Patterns**: Phase 297-298 AsyncMock patterns as gold standard
4. **Test Creation Standards**: Import, assertion, fixture, coverage, pass rate requirements
5. **Anti-Patterns**: 5 common anti-patterns to avoid
6. **Quality Gate**: PRE-CHECK requirements for Phase 304+
7. **Remediation Patterns**: How to fix stub tests, fixture issues, failing tests

**Next Steps**: Apply these standards to all future test creation in Phase 304+ to prevent stub test recurrence.

---

**Document Status**: ✅ COMPLETE
**Total Lines**: 580 lines
**Purpose**: Prevent stub test creation in Phase 304+
