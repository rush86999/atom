# API Contract Testing Guide

## Overview

API contract testing validates that the Atom backend API conforms to its OpenAPI specification. We use Schemathesis for property-based contract testing and openapi-diff for breaking change detection.

## Tools

- **Schemathesis**: Property-based API contract testing (built on Hypothesis)
- **openapi-diff**: Breaking change detection for OpenAPI specs
- **FastAPI**: Auto-generates OpenAPI spec at `/openapi.json`

## Project Structure

```
backend/
├── tests/
│   ├── contract/              # Contract test directory
│   │   ├── __init__.py
│   │   ├── conftest.py        # Schemathesis fixtures
│   │   ├── test_core_api.py   # Health, agent endpoints
│   │   ├── test_canvas_api.py # Canvas endpoints
│   │   └── test_governance_api.py # Governance endpoints
│   └── scripts/
│       ├── generate_openapi_spec.py     # Generate OpenAPI spec
│       └── detect_breaking_changes.py   # Breaking change detection
├── openapi.json             # Baseline OpenAPI spec (committed)
└── docs/
    └── API_CONTRACT_TESTING.md  # This file
```

## Running Contract Tests Locally

### Run all contract tests

```bash
cd backend
pytest tests/contract/ -v -m contract
```

### Run specific test file

```bash
cd backend
pytest tests/contract/test_core_api.py -v
```

### Generate OpenAPI spec

```bash
cd backend
python tests/scripts/generate_openapi_spec.py -o openapi.json
```

### Detect breaking changes

```bash
cd backend
python tests/scripts/detect_breaking_changes.py
```

## Writing Contract Tests

### Basic pattern

```python
import pytest
from conftest import schema
from hypothesis import settings

class TestMyEndpoint:
    @schema.parametrize(endpoint="/api/v1/my-endpoint")
    @settings(max_examples=20, deadline=None)
    def test_my_endpoint_contracts(self, case):
        response = case.call_and_validate()
        # Schemathesis validates:
        # - Response status code matches spec
        # - Response body matches schema
        # - Required headers present
```

### Authenticated endpoints

For protected endpoints, use the `schema_with_auth` fixture:

```python
from conftest import schema_with_auth

@schema_with_auth.parametrize(endpoint="/api/v1/protected")
def test_protected_endpoint(self, case):
    response = case.call_and_validate()
```

## CI Integration

The contract tests run automatically on every PR via `.github/workflows/contract-tests.yml`:

1. **Schemathesis Tests**: Validates all API contracts
2. **Breaking Change Detection**: Compares OpenAPI spec against baseline
3. **PR Comments**: Reports breaking changes on PR

## Success Criteria Verification

### 1. OpenAPI spec auto-generated from FastAPI endpoints

```bash
curl http://localhost:8000/openapi.json | python -c "import json, sys; d=json.load(sys.stdin); print(f'{len(d[\"paths\"])} endpoints')"
```

### 2. Schemathesis validates all API contracts

```bash
cd backend && pytest tests/contract/ -v -m contract --collect-only | grep "test_" | wc -l
```

### 3. Breaking changes detected during validation

```bash
cd backend && python tests/scripts/detect_breaking_changes.py --help
```

### 4. CI workflow runs on every PR

Check `.github/workflows/contract-tests.yml` for `pull_request` trigger.

### 5. Contract violations block merge

The workflow sets `continue-on-error: false` for contract tests.

## Common Mistakes to Avoid

### ❌ Manual TestClient Calls

```python
# WRONG: Manual HTTP calls bypass Schemathesis validation
def test_health_endpoint(self):
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code in [200, 400, 401, 403, 404]  # Too loose!
```

### ✅ Schemathesis Property-Based Testing

```python
# CORRECT: Schemathesis validates schema automatically
@schema.parametrize(endpoint="/health")
@settings(max_examples=10, deadline=None)
def test_health_endpoint_contracts(self, case):
    response = case.call_and_validate()  # Validates schema!
    assert response.status_code in [200, 503]  # Business logic only
```

**Key differences:**
1. Use `@schema.parametrize()` decorator - generates diverse test cases
2. Use `case.call_and_validate()` - automatic schema validation
3. Remove loose status code assertions - Schemathesis handles it
4. Hypothesis generates edge cases you wouldn't think of

## Running Contract Tests (Updated)

```bash
# Run all contract tests
pytest tests/contract/ -v -m contract

# Run specific test file
pytest tests/contract/test_core_api.py -v

# Run with more examples (slower but more thorough)
pytest tests/contract/ -v -m contract --hypothesis-max-examples=100
```

## Troubleshooting

### Schemathesis fails with import error

Ensure you're in the backend directory and dependencies are installed:

```bash
cd backend
pip install -r requirements.txt
```

### Breaking change detection fails

Install openapi-diff via npx (auto-installed on first run):

```bash
npx openapi-diff --version
```

### Tests pass locally but fail in CI

Check for:
- Database differences (SQLite vs PostgreSQL)
- Environment variables
- FastAPI lifespan context issues

## Pre-commit Hook (Recommended)

To catch breaking changes before pushing, add a pre-commit hook:

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run contract tests before committing
cd backend
pytest tests/contract/ -v -m contract --maxfail=5
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Contract tests failed. Commit aborted."
    echo "   Fix the issues or skip with: git commit --no-verify"
    exit 1
fi

# Detect breaking changes
python3 tests/scripts/detect_breaking_changes.py
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Breaking changes detected. Commit aborted."
    echo "   To update baseline: python3 tests/scripts/generate_openapi_spec.py -o openapi.json"
    echo "   To skip: git commit --no-verify"
    exit 1
fi
```

Make it executable:

```bash
chmod +x .git/hooks/pre-commit
```

This ensures contract violations never leave your development machine.

## References

- [Schemathesis Documentation](https://schemathesis.readthedocs.io/)
- [openapi-diff GitHub](https://github.com/OpenAPITools/openapi-diff)
- [FastAPI OpenAPI Customization](https://fastapi.tiangolo.com/tutorial/extending-openapi/)
- [Phase 128 Research](.planning/phases/128-backend-api-contract-testing/128-RESEARCH.md)
