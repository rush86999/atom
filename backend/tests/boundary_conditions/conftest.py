"""
Boundary Conditions Test Configuration

This conftest.py provides fixtures and helpers for testing boundary conditions
where bugs commonly occur:
- Exact threshold values (min, max, threshold)
- Empty inputs (empty strings, empty lists, None values)
- Unicode and special character inputs
- Malicious input (SQL injection, XSS)
- Extreme values (maximums, negatives)

These tests complement property-based tests by targeting EXACT boundaries
that random testing rarely hits.
"""

import pytest
from typing import Any, List


# ============================================================================
# Boundary Value Test Data Fixtures
# ============================================================================

@pytest.fixture
def empty_inputs() -> List[str]:
    """
    Empty inputs that should be handled gracefully.

    Common bug: Functions crash on empty strings or None values.
    """
    return [
        "",               # Empty string
        "   ",            # Whitespace only
        "  \t  \n  ",     # Tabs and newlines only
        "\x00",           # Null byte
    ]


@pytest.fixture
def unicode_strings() -> List[str]:
    """
    Unicode strings covering international languages and emojis.

    Common bug: UnicodeEncodeError when processing non-ASCII text.
    """
    return [
        "正常文本",                            # Chinese (CJK)
        "עברית",                               # Hebrew (RTL)
        "العربية",                             # Arabic (RTL)
        "🎉🚀🔥",                              # Emojis (multi-byte)
        "مرحبا بالعالم",                       # Arabic + English
        "Привет мир",                          # Cyrillic
        "Γειά σου Κόσμε",                      # Greek
        "🎯✨💡🚀",                             # Multiple emojis
        "Test with embedded emoji 🚀 in text",  # Mixed ASCII + emoji
        "ãéîôû",                               # Accented Latin
    ]


@pytest.fixture
def special_characters() -> List[str]:
    """
    Special characters and malicious inputs that must be rejected safely.

    Common bug: SQL injection or XSS vulnerabilities.
    """
    return [
        "'; DROP TABLE users; --",            # SQL injection
        "1' OR '1'='1'",                       # SQL injection variant
        "<script>alert('xss')</script>",      # XSS attempt
        "<img src=x onerror=alert(1)>",        # XSS variant
        "../../../etc/passwd",                 # Path traversal
        "../../etc/passwd",                    # Path traversal variant
        "$(whoami)",                           # Command substitution
        "`whoami`",                            # Backtick command
        "| cat /etc/passwd",                   # Pipe injection
        "; rm -rf /",                          # Command injection
        "&& rm -rf /",                         # Command chaining
        "\x00\x01\x02\x03",                   # Control characters
        "\n\r\t",                              # Newline, carriage return, tab
        "\\\"\\`\\'",                          # Escaped quotes
    ]


@pytest.fixture
def extreme_values() -> dict:
    """
    Extreme values at system limits.

    Common bug: Integer overflow, excessive memory usage.
    """
    return {
        "max_int": 2**63 - 1,                  # Maximum 64-bit signed int
        "min_int": -2**63,                     # Minimum 64-bit signed int
        "max_int_32": 2**31 - 1,               # Maximum 32-bit signed int
        "min_int_32": -2**31,                  # Minimum 32-bit signed int
        "zero": 0,
        "negative": -1,
        "large_string_1k": "x" * 1000,         # 1KB string
        "large_string_10k": "x" * 10000,       # 10KB string
        "large_string_100k": "x" * 100000,     # 100KB string
        "very_long_string": "x" * 1000000,     # 1MB string
    }


@pytest.fixture
def boundary_integers() -> List[tuple]:
    """
    Boundary integers for testing min/max thresholds.

    Tests: min-1, min, min+1, max-1, max, max+1
    Common bug: Off-by-one errors at boundaries.

    Usage:
        @pytest.mark.parametrize("value,expected", boundary_integers())
        def test_boundaries(value, expected):
            assert is_valid(value) == expected
    """
    return [
        # (value, min, max, description)
        (-1, 0, 100, "min-1"),
        (0, 0, 100, "min (exact)"),
        (1, 0, 100, "min+1"),
        (99, 0, 100, "max-1"),
        (100, 0, 100, "max (exact)"),
        (101, 0, 100, "max+1"),
    ]


@pytest.fixture
def maturity_boundaries() -> List[tuple]:
    """
    Maturity level transition boundaries.

    Tests exact threshold values where agent status changes.
    Common bug: Using < instead of <= or >= instead of >.

    Thresholds:
    - STUDENT: < 0.5
    - INTERN: 0.5 - 0.7
    - SUPERVISED: 0.7 - 0.9
    - AUTONOMOUS: >= 0.9
    """
    from core.models import AgentStatus

    return [
        # (confidence_score, expected_status, description)
        (-0.1, AgentStatus.STUDENT, "below minimum (clamped)"),
        (0.0, AgentStatus.STUDENT, "minimum"),
        (0.49, AgentStatus.STUDENT, "just below INTERN"),
        (0.5, AgentStatus.INTERN, "INTERN threshold (exact)"),
        (0.51, AgentStatus.INTERN, "just above INTERN"),
        (0.69, AgentStatus.INTERN, "just below SUPERVISED"),
        (0.7, AgentStatus.SUPERVISED, "SUPERVISED threshold (exact)"),
        (0.71, AgentStatus.SUPERVISED, "just above SUPERVISED"),
        (0.89, AgentStatus.SUPERVISED, "just below AUTONOMOUS"),
        (0.9, AgentStatus.AUTONOMOUS, "AUTONOMOUS threshold (exact)"),
        (0.91, AgentStatus.AUTONOMOUS, "just above AUTONOMOUS"),
        (1.0, AgentStatus.AUTONOMOUS, "maximum"),
        (1.1, AgentStatus.AUTONOMOUS, "above maximum (clamped)"),
    ]


@pytest.fixture
def confidence_scores() -> List[float]:
    """
    Confidence score boundary values.

    Used for testing maturity transitions and confidence-based decisions.
    """
    return [
        -0.1,    # Below minimum
        0.0,     # Minimum
        0.1,     # Low confidence
        0.25,    # Quarter confidence
        0.49,    # Just below INTERN threshold
        0.5,     # INTERN threshold (exact)
        0.51,    # Just above INTERN threshold
        0.6,     # Mid-INTERN
        0.69,    # Just below SUPERVISED threshold
        0.7,     # SUPERVISED threshold (exact)
        0.71,    # Just above SUPERVISED threshold
        0.8,     # Mid-SUPERVISED
        0.89,    # Just below AUTONOMOUS threshold
        0.9,     # AUTONOMOUS threshold (exact)
        0.91,    # Just above AUTONOMOUS threshold
        0.95,    # High confidence
        1.0,     # Maximum
        1.1,     # Above maximum (should clamp)
    ]


# ============================================================================
# Boundary Test Helper Functions
# ============================================================================

def assert_exclusive_boundary(value: float, threshold: float, expected: bool, operation: str = ">"):
    """
    Assert that boundary comparisons use EXCLUSIVE operators (>, <) not INCLUSIVE (>=, <=).

    This is critical for time gap detection and other thresholds where exact equality
    should NOT trigger the boundary condition.

    Args:
        value: The test value
        threshold: The boundary threshold
        expected: Expected result (True if condition met, False otherwise)
        operation: The comparison operator (">" or "<")

    Example:
        # Time gap of exactly 30 minutes should NOT trigger segmentation
        assert_exclusive_boundary(30.0, 30.0, False, ">")  # 30.0 > 30.0 is False

    Common bug: Using >= instead of > causes off-by-one errors.
    """
    if operation == ">":
        result = value > threshold
    elif operation == "<":
        result = value < threshold
    elif operation == ">=":
        result = value >= threshold
    elif operation == "<=":
        result = value <= threshold
    else:
        raise ValueError(f"Unknown operation: {operation}")

    assert result == expected, (
        f"Boundary check failed: {value} {operation} {threshold} = {result}, "
        f"expected {expected}. This may be an off-by-one error."
    )


def assert_inclusive_boundary(value: float, threshold: float, expected: bool, operation: str = ">="):
    """
    Assert that boundary comparisons use INCLUSIVE operators (>=, <=).

    This is appropriate for thresholds where exact equality SHOULD trigger
    the boundary condition.

    Args:
        value: The test value
        threshold: The boundary threshold
        expected: Expected result (True if condition met, False otherwise)
        operation: The comparison operator (">=" or "<=")

    Example:
        # Confidence of exactly 0.5 SHOULD map to INTERN
        assert_inclusive_boundary(0.5, 0.5, True, ">=")  # 0.5 >= 0.5 is True

    Common bug: Using > instead of >= causes off-by-one errors.
    """
    if operation == ">":
        result = value > threshold
    elif operation == "<":
        result = value < threshold
    elif operation == ">=":
        result = value >= threshold
    elif operation == "<=":
        result = value <= threshold
    else:
        raise ValueError(f"Unknown operation: {operation}")

    assert result == expected, (
        f"Boundary check failed: {value} {operation} {threshold} = {result}, "
        f"expected {expected}. This may be an off-by-one error."
    )


def assert_clamped_value(value: Any, min_val: Any, max_val: Any, expected: Any):
    """
    Assert that values are properly clamped to [min_val, max_val] range.

    Common bug: Values outside range cause crashes instead of clamping.

    Args:
        value: Input value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        expected: Expected clamped result

    Example:
        # Values below 0 should clamp to 0
        assert_clamped_value(-10, 0, 100, 0)
        assert_clamped_value(150, 0, 100, 100)
    """
    # Simple clamping logic
    if value < min_val:
        clamped = min_val
    elif value > max_val:
        clamped = max_val
    else:
        clamped = value

    assert clamped == expected, (
        f"Clamping failed: clamp({value}, {min_val}, {max_val}) = {clamped}, "
        f"expected {expected}"
    )


# ============================================================================
# Common Test Patterns
# ============================================================================

@pytest.fixture
def time_gap_boundaries() -> List[tuple]:
    """
    Time gap threshold boundaries for episode segmentation.

    CRITICAL: Time gap uses EXCLUSIVE boundary (> not >=).
    Gap of exactly threshold minutes does NOT trigger new segment.

    Threshold: 30 minutes
    """
    return [
        # (gap_minutes, should_segment, description)
        (0, False, "no gap"),
        (15.0, False, "half threshold"),
        (29.9, False, "just below threshold"),
        (29.999, False, "just below threshold (precise)"),
        (30.0, False, "EXACT threshold (should NOT segment - exclusive >)"),
        (30.001, True, "just above threshold (precise)"),
        (30.1, True, "just above threshold"),
        (31.0, True, "above threshold"),
        (60.0, True, "double threshold"),
        (1440.0, True, "24 hours"),
    ]


@pytest.fixture
def cache_size_boundaries() -> List[tuple]:
    """
    Cache size boundaries for LRU eviction testing.

    Tests: 0 entries, exactly at capacity, one over capacity, double capacity.
    """
    return [
        # (max_size, entries, expected_evictions, description)
        (1, 0, 0, "empty cache"),
        (1, 1, 0, "exactly at capacity"),
        (1, 2, 1, "one over capacity"),
        (10, 10, 0, "at capacity (10)"),
        (10, 11, 1, "one over capacity (10)"),
        (100, 100, 0, "at capacity (100)"),
        (100, 101, 1, "one over capacity (100)"),
        (100, 200, 100, "double capacity"),
        (1000, 2000, 1000, "double capacity (large)"),
    ]


@pytest.fixture
def semantic_similarity_boundaries() -> List[tuple]:
    """
    Semantic similarity threshold boundaries for topic change detection.

    Threshold: 0.75 (below this = topic change)
    """
    return [
        # (similarity, should_detect_change, description)
        (0.0, True, "completely different"),
        (0.5, True, "low similarity"),
        (0.74, True, "just below threshold"),
        (0.749, True, "just below threshold (precise)"),
        (0.75, False, "EXACT threshold (inclusive >=, no change)"),
        (0.751, False, "just above threshold"),
        (0.8, False, "high similarity"),
        (0.9, False, "very similar"),
        (1.0, False, "identical"),
    ]


# ============================================================================
# Pytest Configuration for Boundary Tests
# ============================================================================

def pytest_configure(config):
    """
    Configure pytest for boundary condition testing.
    """
    # Add custom markers
    config.addinivalue_line(
        "markers", "boundary: mark test as boundary condition test"
    )
    config.addinivalue_line(
        "markers", "unicode: mark test as unicode handling test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security boundary test"
    )
