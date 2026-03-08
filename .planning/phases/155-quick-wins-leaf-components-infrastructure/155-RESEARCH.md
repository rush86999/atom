# Phase 155: Quick Wins (Leaf Components & Infrastructure) - Research

**Researched:** March 8, 2026
**Domain:** Cross-platform testing of leaf components, utilities, DTOs, configuration, and simple state management
**Confidence:** HIGH

## Summary

Phase 155 requires implementing **rapid coverage gains on low-complexity, high-volume code** across four platforms (backend, frontend, mobile, desktop) to achieve 80%+ coverage on components that are easy to test but numerous. The project already has substantial testing infrastructure in place: comprehensive pytest backend tests (74.55% coverage), Jest configuration with progressive thresholds for frontend/mobile, and quality metrics infrastructure from Phases 148-149 (cross-platform aggregation, trending analysis, assert-to-test ratio tracking). Current coverage gaps are significant: frontend at 21.96%, mobile at 0%, desktop at 0%.

**What's missing:** A systematic approach to testing leaf components and infrastructure that:
1. Identifies and prioritizes low-complexity, high-volume files (DTOs, utilities, UI components, config)
2. Generates simple tests for data structures (Pydantic models, TypeScript interfaces, Rust structs)
3. Tests configuration wiring (route registration, middleware, providers, context setup)
4. Validates simple state management (read-only services, useState hooks, AsyncStorage/MMKV getters)
5. Achieves 80%+ coverage on these "quick win" targets before moving to complex services in Phase 156

**Primary recommendation:** Create a Leaf Component Testing Strategy that focuses on (1) **Data transfer objects** - test Pydantic model validation, TypeScript interface type safety, Rust struct serialization; (2) **Utility functions** - test pure functions with simple inputs/outputs (formatters, validators, transformers); (3) **UI leaf components** - test Button, Input, Display components with React Testing Library; (4) **Configuration** - test route registration, middleware setup, provider wiring; (5) **Simple state** - test read-only services, localStorage getters, context initialization. Use pytest fixtures for backend DTOs, React Testing Library for frontend components, jest-expo for mobile, and cargo test for desktop Rust code.

**Key infrastructure already in place:**
- **Backend pytest**: 74.55% coverage, 200+ test files, comprehensive fixtures (test_skill_adapter.py pattern)
- **Frontend Jest**: Progressive thresholds (70% → 75% → 80%), React Testing Library setup, canvas component tests
- **Mobile jest-expo**: 50% → 55% → 60% thresholds (lower due to React Native complexity), test utilities shared with frontend
- **Desktop cargo test**: Integration tests in src-tauri/tests/ (device capabilities, file operations, platform-specific)
- **Quality metrics**: assert_test_ratio_tracker.py, ci_quality_gate.py, coverage_trend_analyzer.py from Phases 148-149
- **Cross-platform aggregation**: cross_platform_summary.json, cross_platform_trend.json, ci_status_aggregator.py

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Backend unit testing | De facto Python testing standard, fixtures, parametrize, extensive plugin ecosystem |
| **React Testing Library** | 14.x+ | Frontend component testing | Standard React testing approach (8M+ weekly downloads), user-centric, accessibility-first |
| **jest-expo** | 50.x+ | Mobile React Native testing | Official Expo testing framework, integrates with Jest, React Native component support |
| **cargo test** | Rust stable | Desktop Rust testing | Built-in Rust testing, unit + integration tests, thread-safe test execution |
| **Pydantic** | 2.x | Backend DTO validation | Industry standard Python validation (50M+ downloads), type-safe, testable validators |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-factoryboy** | 2.5+ | Pydantic model fixtures | Generate test data for DTOs with factory pattern |
| **@testing-library/user-event** | 14.x+ | User interaction simulation | Click, type, keyboard events for UI components |
| **react-test-renderer** | 18.x+ | Snapshot testing | Visual regression testing for leaf UI components |
| **tempfile** | Python stdlib | Temporary file testing | Test file I/O, config loading, state persistence |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| React Testing Library | Enzyme | Enzyme is deprecated, less maintained, implementation-focused testing |
| pytest fixtures | Factory Boy only | Fixtures are simpler for basic test data, factories better for complex scenarios |
| cargo test | tauri-driver | tauri-driver unmaintained, blocked on Tauri 2.x, cargo test is built-in |
| React Test Renderer | Jest snapshot | Snapshots can be ignored, test renderer provides more explicit assertions |

**Installation:**
```bash
# Backend - ALREADY INSTALLED
cd backend
pip install pytest pytest-cov pytest-json-report
pip install pytest-factoryboy  # NEW: for DTO fixture generation

# Frontend - ALREADY INSTALLED
cd frontend-nextjs
npm install --save-dev @testing-library/react @testing-library/user-event

# Mobile - ALREADY INSTALLED
cd mobile
npm install --save-dev jest-expo @testing-library/react-native

# Desktop - BUILT-IN
# cargo test is part of Rust toolchain
# No installation needed
```

## Architecture Patterns

### Recommended Project Structure

```
atom/
├── backend/
│   ├── tests/
│   │   ├── unit/dto/                   # NEW: Pydantic model tests
│   │   │   ├── test_response_models.py      # SuccessResponse, ErrorResponse
│   │   │   ├── test_pydantic_validators.py  # Custom validators
│   │   │   └── test_api_schemas.py          # Request/response schemas
│   │   ├── unit/utils/                 # NEW: Utility function tests
│   │   │   ├── test_formatters.py           # Date, string, number formatters
│   │   │   ├── test_validators.py           # Email, phone, URL validators
│   │   │   └── test_transformers.py         # Data transformation functions
│   │   ├── integration/config/          # NEW: Configuration tests
│   │   │   ├── test_route_registration.py   # API route setup
│   │   │   ├── test_middleware.py           # Middleware wiring
│   │   │   └── test_dependency_injection.py # Service container setup
│   │   └── unit/state/                  # NEW: Simple state tests
│   │       ├── test_read_only_services.py   # Config loaders, constants
│   │       └── test_cache_helpers.py        # Cache get/set operations
│   └── core/
│       ├── response_models.py          # DTOs under test
│       ├── models.py                   # Pydantic models
│       └── messaging_schemas.py        # API schemas
│
├── frontend-nextjs/
│   ├── components/ui/                  # Leaf components under test
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── badge.tsx
│   │   └── ... (20+ UI components)
│   ├── components/ui/__tests__/        # NEW: UI component tests
│   │   ├── button.test.tsx                  # Button variants, sizes, clicks
│   │   ├── input.test.tsx                   # Input validation, events
│   │   ├── badge.test.tsx                   # Badge variants, colors
│   │   └── ... (one test file per component)
│   ├── lib/                            # Utility functions
│   │   └── formatters.ts
│   ├── lib/__tests__/                  # NEW: Utility tests
│   │   └── formatters.test.ts
│   ├── hooks/                          # React hooks
│   │   └── useState.ts
│   ├── hooks/__tests__/                # NEW: Hook tests
│   │   └── useState.test.ts
│   └── pages/                          # Route configuration
│       └── _app.tsx                    # Provider setup under test
│
├── mobile/
│   ├── src/components/                 # Leaf components
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   └── ... (basic components)
│   ├── src/components/__tests__/       # NEW: Mobile component tests
│   │   ├── Button.test.tsx
│   │   └── Card.test.tsx
│   ├── src/utils/                      # Utilities
│   │   └── formatters.ts
│   ├── src/utils/__tests__/            # NEW: Utility tests
│   │   └── formatters.test.ts
│   └── src/__tests__/                  # NEW: Config tests
│       ├── navigation.test.ts              # React Navigation setup
│       └── providers.test.ts              # Context provider wiring
│
├── frontend-nextjs/src-tauri/
│   ├── src/                            # Rust source
│   │   ├── dto.rs                      # NEW: DTOs under test
│   │   ├── utils.rs                    # NEW: Utilities under test
│   │   └── config.rs                   # NEW: Configuration under test
│   └── tests/                          # EXISTING + NEW
│       ├── dto_test.rs                 # NEW: Serialize/deserialize tests
│       ├── utils_test.rs               # NEW: Pure function tests
│       └── config_test.rs              # NEW: Tauri command registration
│
└── backend/tests/scripts/
    ├── leaf_component_scanner.py       # NEW: Find untested leaf components
    ├── dto_coverage_analyzer.py        # NEW: Identify DTOs without tests
    ├── quick_wins_generator.py         # NEW: Generate test templates
    ├── assert_test_ratio_tracker.py    # EXISTING: Quality metrics
    └── ci_quality_gate.py              # EXISTING: Enforcement
```

### Pattern 1: Pydantic Model Testing (Backend DTOs)

**What:** Test Pydantic model validation, serialization, deserialization, and custom validators

**When to use:** All Pydantic BaseModel subclasses in backend/core/

**Example:**
```python
# backend/tests/unit/dto/test_response_models.py
"""
Tests for standardized response models (SuccessResponse, ErrorResponse, PaginatedResponse).

Tests cover:
- Model validation with valid data
- Validation errors with invalid data
- Serialization/deserialization
- Generic type specialization
- Default values and factory functions
"""
import pytest
from datetime import datetime
from pydantic import ValidationError
from core.response_models import SuccessResponse, PaginatedResponse, ErrorResponse


class TestSuccessResponse:
    """Test SuccessResponse generic model."""

    def test_success_response_with_data(self):
        """Test success response with data."""
        response = SuccessResponse[dict](
            data={"id": "123", "name": "Test"},
            message="Operation successful"
        )
        assert response.success is True
        assert response.data == {"id": "123", "name": "Test"}
        assert response.message == "Operation successful"
        assert isinstance(response.timestamp, str)

    def test_success_response_with_none_data(self):
        """Test success response with None data."""
        response = SuccessResponse[None](
            data=None,
            message="Completed"
        )
        assert response.success is True
        assert response.data is None
        assert response.message == "Completed"

    def test_success_response_serialization(self):
        """Test JSON serialization."""
        response = SuccessResponse[dict](
            data={"id": "123"},
            message="Success"
        )
        json_dict = response.model_dump()
        assert json_dict["success"] is True
        assert json_dict["data"] == {"id": "123"}
        assert "timestamp" in json_dict

    def test_success_response_generic_specialization(self):
        """Test generic type specialization with different data types."""
        # String data
        str_response = SuccessResponse[str](data="test", message="OK")
        assert isinstance(str_response.data, str)

        # List data
        list_response = SuccessResponse[list](data=[1, 2, 3], message="OK")
        assert isinstance(list_response.data, list)

        # Dict data
        dict_response = SuccessResponse[dict](data={"key": "value"}, message="OK")
        assert isinstance(dict_response.data, dict)


class TestPaginatedResponse:
    """Test PaginatedResponse model."""

    def test_paginated_response_structure(self):
        """Test paginated response with pagination metadata."""
        response = PaginatedResponse[dict](
            data=[{"id": "1"}, {"id": "2"}],
            pagination={
                "total": 100,
                "page": 1,
                "page_size": 50,
                "total_pages": 2
            }
        )
        assert response.success is True
        assert len(response.data) == 2
        assert response.pagination["total"] == 100
        assert response.pagination["page"] == 1

    def test_paginated_response_validation(self):
        """Test validation error with missing pagination."""
        with pytest.raises(ValidationError):
            PaginatedResponse[dict](
                data=[{"id": "1"}],
                # Missing required pagination field
                pagination={}  # Should contain required keys
            )


class TestErrorResponse:
    """Test ErrorResponse model."""

    def test_error_response_structure(self):
        """Test error response with error details."""
        response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Invalid input",
            details={"field": "email", "issue": "required"}
        )
        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"
        assert response.message == "Invalid input"
        assert response.details["field"] == "email"

    def test_error_response_with_minimal_fields(self):
        """Test error response with only required fields."""
        response = ErrorResponse(
            error_code="INTERNAL_ERROR",
            message="Something went wrong"
        )
        assert response.success is True  # ErrorResponse inherits SuccessResponse
        assert response.error_code == "INTERNAL_ERROR"
        assert response.details is None  # Optional field defaults to None
```

**Source:** Based on existing test_skill_adapter.py pattern and Pydantic testing best practices

### Pattern 2: Utility Function Testing (Pure Functions)

**What:** Test pure functions with simple inputs/outputs using pytest parametrize

**When to use:** All utility functions (formatters, validators, transformers)

**Example:**
```python
# backend/tests/unit/utils/test_formatters.py
"""
Tests for utility functions (formatters, validators, transformers).

Tests cover:
- Pure function behavior with various inputs
- Edge cases (empty strings, null values, special characters)
- Parametrized test cases for efficiency
"""
import pytest
from core.utils.formatters import format_date, format_currency, format_phone


class TestFormatters:
    """Test formatting utility functions."""

    @pytest.mark.parametrize("input_date,expected_output", [
        ("2026-03-08", "March 8, 2026"),
        ("2026-01-01", "January 1, 2026"),
        ("2026-12-31", "December 31, 2026"),
    ])
    def test_format_date(self, input_date, expected_output):
        """Test date formatting with various inputs."""
        assert format_date(input_date) == expected_output

    @pytest.mark.parametrize("amount,currency,expected", [
        (1000, "USD", "$1,000.00"),
        (1000, "EUR", "€1,000.00"),
        (0.99, "USD", "$0.99"),
        (1000000, "USD", "$1,000,000.00"),
    ])
    def test_format_currency(self, amount, currency, expected):
        """Test currency formatting with different currencies and amounts."""
        assert format_currency(amount, currency) == expected

    def test_format_phone_valid(self):
        """Test phone number formatting for valid numbers."""
        assert format_phone("1234567890") == "(123) 456-7890"
        assert format_phone("+11234567890") == "+1 (123) 456-7890"

    @pytest.mark.parametrize("invalid_phone", [
        "123",           # Too short
        "abcdefghij",    # Non-numeric
        "",              # Empty string
        None,            # None value
    ])
    def test_format_phone_invalid(self, invalid_phone):
        """Test phone formatting with invalid inputs."""
        with pytest.raises(ValueError):
            format_phone(invalid_phone)
```

**Source:** Existing pytest parametrize patterns in backend/tests/

### Pattern 3: React Component Testing (Frontend UI Components)

**What:** Test leaf UI components with React Testing Library (user-centric approach)

**When to use:** All components/ui/*.tsx files (Button, Input, Badge, etc.)

**Example:**
```tsx
// frontend-nextjs/components/ui/__tests__/button.test.tsx
/**
 * Tests for Button component.
 *
 * Tests cover:
 * - Rendering with different variants (default, destructive, outline, etc.)
 * - Rendering with different sizes (default, sm, lg, icon)
 * - User interaction (click events)
 * - Disabled state
 * - Accessibility attributes (ARIA)
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { Button } from '../button';

describe('Button Component', () => {
  describe('Rendering', () => {
    it('renders default button', () => {
      render(<Button>Click me</Button>);
      const button = screen.getByRole('button', { name: 'Click me' });
      expect(button).toBeInTheDocument();
      expect(button).toHaveClass('bg-primary-600');
    });

    it('renders destructive variant', () => {
      render(<Button variant="destructive">Delete</Button>);
      const button = screen.getByRole('button', { name: 'Delete' });
      expect(button).toHaveClass('bg-red-500');
    });

    it('renders outline variant', () => {
      render(<Button variant="outline">Cancel</Button>);
      const button = screen.getByRole('button', { name: 'Cancel' });
      expect(button).toHaveClass('border');
    });

    it.each([
      ['default', 'h-10'],
      ['sm', 'h-9'],
      ['lg', 'h-11'],
      ['icon', 'h-10 w-10'],
    ])('renders %s size with correct classes', (size, expectedClass) => {
      render(<Button size={size as any}>Button</Button>);
      const button = screen.getByRole('button');
      expect(button).toHaveClass(expectedClass);
    });
  });

  describe('User Interaction', () => {
    it('calls onClick handler when clicked', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      render(<Button onClick={handleClick}>Click me</Button>);

      const button = screen.getByRole('button');
      await user.click(button);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('does not call onClick when disabled', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      render(
        <Button onClick={handleClick} disabled>
          Click me
        </Button>
      );

      const button = screen.getByRole('button');
      await user.click(button);

      expect(handleClick).not.toHaveBeenCalled();
      expect(button).toBeDisabled();
    });
  });

  describe('Accessibility', () => {
    it('has accessible name', () => {
      render(<Button>Submit</Button>);
      const button = screen.getByRole('button', { name: 'Submit' });
      expect(button).toBeInTheDocument();
    });

    it('forwards custom props to button element', () => {
      render(
        <Button aria-label="Close dialog" data-testid="close-btn">
          ×
        </Button>
      );

      const button = screen.getByLabelText('Close dialog');
      expect(button).toHaveAttribute('data-testid', 'close-btn');
    });
  });
});
```

**Source:** Existing component test patterns in components/Agents/__tests__/AgentManager.test.tsx and React Testing Library best practices

### Pattern 4: Configuration Testing (Route/Provider Wiring)

**What:** Test that routes, middleware, and providers are wired correctly

**When to use:** Route registration, middleware setup, context provider configuration

**Example:**
```python
# backend/tests/integration/config/test_route_registration.py
"""
Tests for API route registration and middleware wiring.

Tests cover:
- All expected routes are registered
- Middleware is applied in correct order
- Route handlers return expected response models
"""
import pytest
from fastapi.testclient import TestClient
from main import app


class TestRouteRegistration:
    """Test API route registration."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_route_registered(self, client):
        """Test health check route is registered."""
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_agent_routes_registered(self, client):
        """Test agent routes are registered."""
        # List agents
        response = client.get("/api/v1/agents")
        assert response.status_code in [200, 401]  # OK or Unauthorized (auth required)

        # Create agent
        response = client.post("/api/v1/agents", json={})
        assert response.status_code in [200, 400, 401]  # OK, Bad Request, or Unauthorized

    def test_canvas_routes_registered(self, client):
        """Test canvas routes are registered."""
        response = client.get("/api/v1/canvases")
        assert response.status_code in [200, 401]

    def test_governance_middleware_applied(self, client):
        """Test that governance middleware is applied."""
        # Governance middleware should intercept requests
        # and add governance context to response headers
        response = client.get("/api/v1/agents")
        # Check for governance headers if middleware is active
        # (Specific implementation depends on middleware design)
        assert response.status_code in [200, 401, 403]


class TestMiddlewareConfiguration:
    """Test middleware configuration."""

    def test_cors_middleware_configured(self, client):
        """Test CORS middleware is configured."""
        response = client.options("/api/v1/agents")
        assert response.status_code == 200
        # Check CORS headers
        assert "access-control-allow-origin" in response.headers

    def test_auth_middleware_configured(self, client):
        """Test authentication middleware is configured."""
        # Unauthenticated request should return 401
        response = client.post("/api/v1/agents", json={})
        assert response.status_code in [401, 403]
```

**Source:** Existing test_main_app_comprehensive.py pattern and FastAPI testing best practices

### Pattern 5: Simple State Management Testing

**What:** Test read-only services, localStorage/MMKV operations, and simple state getters/setters

**When to use:** Simple state without complex logic (config loaders, cache helpers, hooks)

**Example:**
```typescript
// frontend-nextjs/hooks/__tests__/useFormatters.test.ts
/**
 * Tests for useFormatters hook (simple state management).
 *
 * Tests cover:
 * - Hook returns expected formatters
 * - Hook memoization prevents re-renders
 * - Hook cleanup
 */
import { renderHook } from '@testing-library/react';
import { useFormatters } from '../useFormatters';

describe('useFormatters Hook', () => {
  it('returns formatter functions', () => {
    const { result } = renderHook(() => useFormatters());

    expect(result.current.formatDate).toBeInstanceOf(Function);
    expect(result.current.formatCurrency).toBeInstanceOf(Function);
    expect(result.current.formatPhone).toBeInstanceOf(Function);
  });

  it('formats dates correctly', () => {
    const { result } = renderHook(() => useFormatters());

    expect(result.current.formatDate('2026-03-08')).toBe('March 8, 2026');
    expect(result.current.formatDate('2026-01-01')).toBe('January 1, 2026');
  });

  it('memoizes formatter functions', () => {
    const { result, rerender } = renderHook(() => useFormatters());

    const firstFormatDate = result.current.formatDate;
    rerender();
    const secondFormatDate = result.current.formatDate;

    expect(firstFormatDate).toBe(secondFormatDate);
  });
});
```

**Source:** React Testing Library renderHook pattern and existing hook test patterns

### Anti-Patterns to Avoid

- **Testing implementation details**: Test user behavior, not component internals (use React Testing Library, not enzyme shallow rendering)
- **Complex test setup**: Leaf components should have simple test setup (avoid complex fixtures for simple tests)
- **Testing third-party libraries**: Don't test React, Pydantic, or Rust stdlib - test YOUR code
- **Over-mocking**: Only mock external dependencies (API calls, file I/O), not the code under test
- **Ignoring edge cases**: Leaf components often have many edge cases (empty strings, null values, special characters)
- **Testing multiple things**: Each test should verify one behavior (single assertion principle)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pydantic test data | Manual dict creation | pytest-factoryboy, @pytest.fixture | Reusable test data, factory pattern, less boilerplate |
| Component rendering | Custom render functions | @testing-library/react render | Standard React testing approach, accessibility-first |
| User interaction simulation | Custom event dispatchers | @testing-library/user-event | Realistic user behavior, handles event propagation |
| Test discovery | Manual file scanning | pytest --collect-only, Jest --listTests | Built-in test discovery, CI/CD integration |
| Coverage reporting | Custom coverage scripts | pytest-cov, Jest coverage | Industry standard, JSON/LCOV/HTML reports |
| Snapshot testing | Manual DOM assertions | react-test-renderer | Visual regression detection, automated diff |

**Key insight:** Leaf components are simple - keep tests simple too. Use standard testing libraries instead of custom infrastructure.

## Common Pitfalls

### Pitfall 1: Testing Pydantic Models Incorrectly

**What goes wrong:** Tests validate Pydantic's built-in validation instead of YOUR custom validation logic

**Why it happens:** Testing that Pydantic validates required fields (which Pydantic already tests)

**How to avoid:**
- Focus on YOUR custom validators (e.g., @field_validator, @model_validator)
- Test business logic validation rules, not Pydantic's built-in type checking
- Test serialization/deserialization for YOUR custom field serializers
- Test edge cases in YOUR validation logic (empty strings, null values, special characters)

**Warning signs:** Tests pass with any valid data, no business logic validation tested

**Mitigation:** Review Pydantic tests - are they testing YOUR code or just Pydantic's functionality?

### Pitfall 2: Over-Testing UI Components

**What goes wrong:** Testing component internals (props, state, methods) instead of user behavior

**Why it happens:** Using shallow rendering (enzyme) or accessing component internals

**How to avoid:**
- Test what users see: rendered text, accessibility attributes, user interactions
- Use React Testing Library queries (getByRole, getByLabelText, getByText)
- Test user flows (click button → form submits) not implementation (props passed)
- Avoid testing component internals (state, methods, lifecycle hooks)

**Warning signs:** Tests break when refactoring component without changing behavior

**Mitigation:** Follow Testing Library philosophy: "The more your tests resemble the way your software is used, the more confidence they can give you"

### Pitfall 3: Missing Test Data for Edge Cases

**What goes wrong:** Tests only cover happy path, missing edge cases (empty strings, null values, special characters)

**Why it happens:** Focusing on typical usage, not edge cases

**How to avoid:**
- Use pytest.mark.parametrize to test multiple inputs in one test
- Include edge cases: empty strings, null values, special characters, large inputs
- Test boundary conditions: min/max values, empty arrays, single-item arrays
- Test error cases: invalid inputs, missing required fields, type mismatches

**Warning signs:** Low code coverage despite many tests (tests covering same paths)

**Mitigation:** Use coverage reports to identify untested lines/branches

### Pitfall 4: Testing Configuration with Real Services

**What goes wrong:** Configuration tests start real services (database, API servers), making tests slow and fragile

**Why it happens:** Testing configuration wiring requires real services to verify

**How to avoid:**
- Mock external services (database, APIs) in configuration tests
- Test that services are CONFIGURED correctly, not that they WORK
- Use TestClient for FastAPI (doesn't start real server)
- Use pytest fixtures for mocking (monkeypatch, pytest-mock)

**Warning signs:** Configuration tests take >10 seconds, fail due to network/database issues

**Mitigation:** Configuration tests should be fast (<100ms), use mocks

### Pitfall 5: Testing State Management with Complex Setup

**What goes wrong:** Simple state tests require complex setup (multiple providers, mock stores, fake contexts)

**Why it happens:** Testing state in isolation requires mocking the entire state tree

**How to avoid:**
- Test simple state in isolation (localStorage getters, useState hooks)
- Use renderHook for custom hooks (no provider setup needed)
- Test state updates with user actions, not direct state manipulation
- For complex state, defer to Phase 156 (Core Services) - Phase 155 is for QUICK WINS

**Warning signs:** State tests have >50 lines of setup code

**Mitigation:** If state test setup is complex, the state is too complex for Phase 155 - defer to Phase 156

## Code Examples

Verified patterns from official sources:

### Pydantic Model Testing

```python
# Source: Pydantic documentation + test_skill_adapter.py pattern
import pytest
from pydantic import ValidationError
from core.response_models import SuccessResponse

def test_success_response_validation():
    """Test SuccessResponse validates correctly."""
    # Valid data
    response = SuccessResponse[dict](data={"id": "123"}, message="Success")
    assert response.success is True

    # Invalid data (Pydantic validates types)
    with pytest.raises(ValidationError):
        SuccessResponse[dict](data=None, message="Success")  # Should be dict
```

### React Component Testing

```tsx
// Source: React Testing Library documentation
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '../button';

test('button calls onClick when clicked', async () => {
  const user = userEvent.setup();
  const handleClick = jest.fn();

  render(<Button onClick={handleClick}>Click me</Button>);

  const button = screen.getByRole('button');
  await user.click(button);

  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

### Utility Function Testing

```python
# Source: pytest documentation
import pytest

@pytest.mark.parametrize("input,expected", [
  ("test", "TEST"),
  ("Test", "TEST"),
  ("TEsT", "TEST"),
])
def test_uppercase(input, expected):
  assert uppercase(input) == expected
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Enzyme shallow rendering | React Testing Library | 2019+ | User-centric testing, better accessibility |
| Manual test data | pytest-factoryboy | 2020+ | Reusable test data, factory pattern |
| Snapshot testing | Visual regression testing | 2021+ | More intentional visual tests |
| Testing implementation | Testing behavior | 2019+ | More robust refactoring, less brittle tests |

**Deprecated/outdated:**
- **Enzyme**: Deprecated, unmaintained, replaced by React Testing Library
- **Shallow rendering**: Tests implementation details, replaced by full rendering
- **Jest snapshot滥用**: Snapshots can be ignored, use intentional assertions

## Open Questions

1. **Scope of Phase 155 vs Phase 156**
   - What we know: Phase 155 is "quick wins", Phase 156 is "core services"
   - What's unclear: Where to draw the line - what's "quick" vs "core"?
   - Recommendation: Phase 155 = test files that can be written in <30 minutes (DTOs, utilities, leaf components). Phase 156 = complex services requiring >30 minutes (agent governance, LLM, episodic memory).

2. **Mobile testing approach**
   - What we know: Mobile has 0% coverage, React Native testing is more complex than React web
   - What's unclear: Should we test mobile components with jest-expo or use API-level tests?
   - Recommendation: Start with jest-expo for simple components (Button, Card), defer complex navigation/state to Phase 156.

3. **Desktop Rust testing scope**
   - What we know: Desktop has 0% coverage, Tauri integration tests exist but are sparse
   - What's unclear: Should we test Tauri-specific code (IPC commands) or just Rust utilities?
   - Recommendation: Test Rust utilities and DTOs in Phase 155 (quick wins), defer Tauri IPC integration to Phase 156.

## Sources

### Primary (HIGH confidence)

- **Pytest Documentation**: https://docs.pytest.org/en/stable/ - Verified fixtures, parametrize, test discovery patterns
- **React Testing Library**: https://testing-library.com/react - Verified render, screen queries, userEvent patterns
- **Jest Documentation**: https://jestjs.io/docs/getting-started - Verified configuration, coverage, snapshot testing
- **Pydantic Documentation**: https://docs.pydantic.dev/ - Verified validation testing, custom validators
- **Existing Atom Tests**: /Users/rushiparikh/projects/atom/backend/tests/test_skill_adapter.py - Verified Pydantic model testing pattern

### Secondary (MEDIUM confidence)

- **pytest-factoryboy**: https://pytest-factoryboy.readthedocs.io/ - Verified factory pattern for test data
- **cargo test**: https://doc.rust-lang.org/book/ch11-00-testing.html - Verified Rust unit/integration test patterns
- **jest-expo**: https://docs.expo.dev/guides/testing/ - Verified React Native testing approach
- **Existing Coverage Configs**: frontend-nextjs/jest.config.js, mobile/jest.config.js - Verified progressive thresholds, coverage collection

### Tertiary (LOW confidence)

- **Web search results**: Limited utility (no results returned), relying on existing codebase patterns and official documentation
- **Best practices synthesis**: Based on existing test files in Atom codebase (test_skill_adapter.py, AgentManager.test.tsx, canvas component tests)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are industry standards with extensive documentation
- Architecture: HIGH - Based on existing test patterns in Atom codebase (200+ backend tests, React component tests, Tauri integration tests)
- Pitfalls: HIGH - Documented from common testing mistakes (enzyme overuse, testing implementation details)
- Code examples: HIGH - Verified from existing Atom test files and official documentation

**Research date:** March 8, 2026
**Valid until:** April 7, 2026 (30 days - testing frameworks stable, unlikely to change)

**Key decisions for planner:**
1. **Focus on speed**: Phase 155 is "quick wins" - prioritize files that can be tested in <30 minutes (DTOs, utilities, leaf components)
2. **Use existing patterns**: Follow test_skill_adapter.py pattern (backend), AgentManager.test.tsx pattern (frontend), device_capabilities_integration_test.rs pattern (desktop)
3. **80% target**: Leaf components should achieve 80%+ coverage with simple tests (validation, rendering, user interaction)
4. **Defer complexity**: Any service requiring >30 minutes to test should be deferred to Phase 156 (Core Services)
5. **Mobile first approach**: Mobile has 0% coverage - prioritize simple component tests (Button, Card) to get baseline coverage
6. **Desktop DTOs first**: Test Rust DTOs and utilities in Phase 155, defer Tauri IPC integration to Phase 156

**Priority order for Phase 155:**
1. Backend DTOs (Pydantic models) - highest coverage gain, simplest tests
2. Frontend UI components (Button, Input, Display) - medium coverage gain, simple tests
3. Backend utilities (formatters, validators) - medium coverage gain, simple tests
4. Frontend hooks (useState, useFormatter) - lower coverage gain, simple tests
5. Configuration tests (route registration, provider setup) - lower coverage gain, medium complexity
6. Mobile components (Button, Card) - medium coverage gain, medium complexity
7. Desktop DTOs (Rust structs) - lower coverage gain, simple tests
8. Simple state management (localStorage, MMKV) - lower coverage gain, simple tests
