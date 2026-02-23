# Autonomous Coding Agents: TDD Patterns

**Autonomous Coding Orchestrator** enables full SDLC automation from natural language requirements to deployed code. This guide covers Test-Driven Development (TDD) patterns specifically for AI-assisted coding workflows.

## Overview

The Autonomous Coding Orchestrator coordinates 7 specialized agents through the complete software development lifecycle:

1. **RequirementParserService**: Parse natural language into structured requirements
2. **CodebaseResearchService**: Research existing codebase and conflicts
3. **PlanningAgent**: Create implementation plan
4. **CodeGeneratorOrchestrator**: Generate source code
5. **TestGeneratorService**: Generate comprehensive tests
6. **TestRunnerService**: Run tests and fix failures
7. **DocumenterAgent**: Generate documentation
8. **CommitterAgent**: Create commits and PRs

**Governance**: AUTONOMOUS maturity required

---

## Red/Green TDD for Autonomous Coding

### What is Red/Green TDD?

TDD (Test-Driven Development) is a programming practice where every piece of code is accompanied by automated tests that demonstrate it works. The most disciplined form is **test-first development**:

1. **Red Phase**: Write tests first, confirm they fail
2. **Green Phase**: Implement code until tests pass
3. **Refactor Phase**: Improve code while keeping tests green

### Why TDD for AI Coding Agents?

AI coding agents face specific risks that TDD mitigates:

- **Non-working code**: Agents may write code that doesn't actually work
- **Unnecessary code**: Agents build features that are never used
- **Regression risk**: Changes break existing functionality
- **Lack of verification**: Without tests, correctness is unproven

**Red/green TDD protects against all these risks** by:
- Ensuring tests fail first (validates they actually test something)
- Building robust test suites that prevent regressions
- Confirming code works before considering it complete
- Providing executable specifications

### How to Use Red/Green TDD with Coding Agents

#### Basic Pattern

When requesting code from an AI agent, explicitly specify TDD:

```
Build a Python function to extract headers from a markdown string. Use red/green TDD.
```

**Expected agent behavior:**
1. Write failing test first (red phase)
2. Implement minimal code to pass (green phase)
3. Run tests to confirm
4. Document the implementation

#### Advanced Pattern

For complex features, be more explicit:

```
Implement user authentication with JWT tokens. Use red/green TDD:

1. Write tests for:
   - Token generation with valid credentials
   - Token rejection with invalid credentials
   - Token expiration handling
   - Refresh token flow

2. Confirm all tests fail before implementing

3. Implement authentication service

4. Run tests and fix until all pass
```

---

## TDD Workflow Integration

### Phase 1: Test Generation (Red)

The **TestGeneratorService** creates comprehensive tests before any code is written:

```python
# TestGeneratorService generates tests like this:

def test_extract_headers_from_markdown():
    """Test that headers are extracted correctly."""
    markdown = "# Header 1\n\n## Header 2"
    expected = ["Header 1", "Header 2"]

    result = extract_headers(markdown)
    assert result == expected, f"Expected {expected}, got {result}"

def test_extract_headers_empty_string():
    """Test that empty markdown returns empty list."""
    markdown = ""
    expected = []

    result = extract_headers(markdown)
    assert result == expected
```

**Critical validation**: The TestRunnerService confirms tests fail before implementation.

### Phase 2: Implementation (Green)

The **CodeGeneratorOrchestrator** writes code to make tests pass:

```python
def extract_headers(markdown: str) -> List[str]:
    """Extract headers from markdown string."""
    import re

    # Match ATX-style headers (# ## ###)
    pattern = r'^#{1,6}\s+(.+)$'
    headers = []

    for line in markdown.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            headers.append(match.group(1).strip())

    return headers
```

**Quality gate**: Tests must pass before code is committed.

### Phase 3: Fix Failures

The **TestRunnerService** executes tests and fixes failures:

1. Run test suite
2. Collect failures
3. Analyze error messages
4. Generate fixes
5. Re-run until all pass

**Example failure cycle**:
```
FAILED test_extract_headers_nested_format:
AssertionError: Expected ['Header', 'Subheader'], got ['Header']

→ Fix: Add Setext-style header pattern support
→ Re-run: PASSED
```

### Phase 4: Verification

After implementation, the **TestRunnerService** validates:

- ✅ All new tests pass
- ✅ No regressions in existing tests
- ✅ Coverage threshold met (80%+)
- ✅ Property tests pass (if applicable)

---

## Best Practices

### 1. Always Specify TDD in Prompts

**Good:**
```
Create a REST API endpoint for user management. Use red/green TDD.
```

**Bad:**
```
Create a REST API endpoint for user management.
```

### 2. Require Test Failure Confirmation

When using autonomous coding orchestrator, the workflow enforces:

```python
# TestGeneratorService creates tests
tests = generate_tests(requirements)

# TestRunnerService confirms they FAIL before implementation
test_results = run_tests(tests)
assert test_results.failed_count > 0, "Tests must fail first (red phase)"

# Only then generate implementation
code = generate_code(tests)

# Verify tests now PASS
test_results = run_tests(tests)
assert test_results.passed, "Tests must pass after implementation (green phase)"
```

### 3. Test-First for All Code

Apply TDD to:
- ✅ Business logic functions
- ✅ API endpoints
- ✅ Database models
- ✅ Service classes
- ✅ Utility functions

**Exception**: Pure data classes (Pydantic models) can skip TDD since validation is built-in.

### 4. Maintain Test Independence

Each test should be:
- **Independent**: Doesn't rely on other tests
- **Deterministic**: Same input = same output
- **Fast**: Executes in milliseconds
- **Isolated**: Uses fixtures/mocks, not external services

### 5. Use Property-Based Tests for Complex Invariants

For critical systems, combine TDD with property-based tests:

```python
from hypothesis import given, settings, strategies as st

@given(st.lists(st.text(min_size=1), max_size=10))
@settings(max_examples=100)
def test_extract_headers_preserves_order(markdown_lines):
    """Property: Header extraction preserves original order."""
    markdown = "\n".join([f"# {line}" for line in markdown_lines])
    headers = extract_headers(markdown)

    # Order must match appearance in markdown
    assert headers == markdown_lines
```

See: `docs/property_tests/README.md` for property testing patterns.

---

## TDD Anti-Patterns to Avoid

### ❌ Skipping Test Failure Check

```python
# BAD: Tests pass immediately (no red phase)
test_results = run_tests(tests)
# Skip failure check
code = generate_code(tests)
```

### ❌ Writing Code Before Tests

```python
# BAD: Implementation first
code = generate_code(requirements)
tests = generate_tests(code)
```

### ❌ Using Tests as Documentation Only

Tests must be **executable specifications**, not just documentation.

### ❌ Ignoring Test Failures

All tests must pass before committing. Use `continue-on-error` only for coverage reports.

---

## Quality Gates

The Autonomous Coding Orchestrator enforces:

1. **Test-First Enforcement**: Tests generated before implementation
2. **Red Phase Validation**: Tests must fail before coding
3. **Green Phase Validation**: Tests must pass after coding
4. **Coverage Threshold**: 80%+ code coverage required
5. **Regression Protection**: No existing tests may break
6. **Property Test Validation**: Invariants must hold

---

## References

- **Simon Willison's TDD Guide**: [Red/green TDD - Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/)
- **Property-Based Testing**: See `backend/tests/property_tests/README.md`
- **Autonomous Coding Orchestrator**: `backend/core/autonomous_coding_orchestrator.py`
- **Test Coverage Standards**: `docs/CODE_QUALITY_STANDARDS.md`

---

## Example: Complete TDD Workflow

### User Request

```
Create a function to validate email addresses using red/green TDD.
```

### Agent Execution (Autonomous)

#### Phase 1: Test Generation (Red)

```python
# tests/unit/test_email_validator.py

import pytest

def test_validate_email_valid_format():
    """Test that valid email addresses pass validation."""
    assert validate_email("user@example.com") == True
    assert validate_email("user.name@example.com") == True
    assert validate_email("user+tag@example.co.uk") == True

def test_validate_email_invalid_format():
    """Test that invalid email addresses fail validation."""
    assert validate_email("invalid") == False
    assert validate_email("@example.com") == False
    assert validate_email("user@") == False

def test_validate_email_empty_string():
    """Test that empty string fails validation."""
    assert validate_email("") == False
```

**Validation**: All tests fail ✅ (red phase confirmed)

#### Phase 2: Implementation (Green)

```python
# core/email_validator.py

import re

def validate_email(email: str) -> bool:
    """
    Validate email address format.

    Returns True if email matches standard pattern, False otherwise.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

**Validation**: All tests pass ✅ (green phase confirmed)

#### Phase 3: Property Test Enhancement

```python
# tests/property_tests/test_email_invariants.py

from hypothesis import given, settings, strategies as st

@given(st.emails())
@settings(max_examples=100)
def test_validate_email_hypothesis_format(email):
    """Property: Valid emails per RFC 5322 pass validation."""
    # Hypothesis generates valid RFC 5322 emails
    assert validate_email(email) == True
```

**Validation**: Property tests pass ✅

#### Phase 4: Coverage Verification

```bash
pytest tests/unit/test_email_validator.py --cov=core/email_validator --cov-report=term-missing

Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
core/email_validator.py       8      0   100%
```

**Quality gate**: 100% coverage ✅

---

## Summary

**Red/Green TDD** is essential for autonomous coding agents:

1. **Protects against non-working code**
2. **Ensures tests actually test something**
3. **Builds regression protection**
4. **Provides executable specifications**

**Usage**: Simply append "Use red/green TDD" to any coding request.

**Enforcement**: Autonomous Coding Orchestrator validates red/green phases automatically.

---

*Last Updated: 2026-02-23*
*Phase: v3.0 Production Readiness*
