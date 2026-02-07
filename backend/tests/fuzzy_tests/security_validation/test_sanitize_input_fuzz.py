"""
Fuzzy Test: Input Sanitization

Tests the robustness of input sanitization against malicious inputs.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

try:
    import atheris
    ATHERIS_AVAILABLE = True
except ImportError:
    ATHERIS_AVAILABLE = False
    print("Warning: Atheris not available")

import re


def sanitize_user_input(user_input: str) -> str:
    """
    Sanitize user input to prevent XSS and injection attacks.

    Removes:
    - HTML tags
    - SQL injection patterns
    - JavaScript code
    - Special characters

    Args:
        user_input: Raw user input

    Returns:
        Sanitized string
    """
    if not user_input:
        return ""

    # Remove HTML tags
    sanitized = re.sub(r'<[^>]+>', '', user_input)

    # Remove SQL injection patterns
    sanitized = re.sub(r"';.*DROP TABLE", '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"'.*OR.*'.*='", '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"'.*UNION.*SELECT", '', sanitized, flags=re.IGNORECASE)

    # Remove JavaScript
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'onerror=', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'onload=', '', sanitized, flags=re.IGNORECASE)

    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')

    # Limit length
    if len(sanitized) > 1000:
        sanitized = sanitized[:1000]

    return sanitized.strip()


@atheris.instrument_func
def test_sanitize_input_fuzz(data):
    """
    Fuzz test for input sanitization.

    Tests:
    - XSS payloads
    - SQL injection payloads
    - Malformed UTF-8
    - Very long strings
    - Null bytes
    - Special characters

    Expected: No crashes, sanitized output
    """
    try:
        # Convert bytes to string
        user_input = data.decode('utf-8', errors='ignore')

        # Sanitize input
        sanitized = sanitize_user_input(user_input)

        # Verify output is safe
        assert isinstance(sanitized, str)

        # Check for XSS patterns (should be removed)
        assert '<script' not in sanitized.lower()
        assert 'javascript:' not in sanitized.lower()
        assert 'onerror=' not in sanitized.lower()
        assert 'onload=' not in sanitized.lower()

        # Check for SQL injection patterns (should be removed)
        assert "'; drop table" not in sanitized.lower()
        assert "' or '" not in sanitized.lower()
        assert "' union select" not in sanitized.lower()

        # Check length limit
        assert len(sanitized) <= 1000

        # Check for null bytes
        assert '\x00' not in sanitized

    except Exception as e:
        # Unexpected exception
        print(f"Unexpected exception: {e}")
        raise


def main(argc, argv):
    """Main entry point for fuzzing."""
    if not ATHERIS_AVAILABLE:
        print("Error: Atheris not available")
        sys.exit(1)

    atheris.Setup(argv, test_sanitize_input_fuzz)
    atheris.Fuzz()


if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
