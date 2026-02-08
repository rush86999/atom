"""
Fuzzy Test: Currency String Parser

Tests the robustness of currency parsing against malformed and unexpected inputs.
This helps prevent crashes and security vulnerabilities from edge cases.

Uses Atheris for coverage-guided fuzzing.
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
    print("Warning: Atheris not available. Install with: pip install atheris")

import re
from decimal import Decimal, InvalidOperation


def parse_currency(currency_str: str) -> float:
    """
    Parse currency string to float.

    Supports formats:
    - $123.45
    - 123.45
    - USD 123.45
    - €123,45
    - 1,234.56

    Args:
        currency_str: Currency string

    Returns:
        Float value

    Raises:
        ValueError: If invalid format
    """
    if not currency_str or not isinstance(currency_str, str):
        raise ValueError("Invalid currency string")

    # Remove currency symbols and whitespace
    cleaned = re.sub(r'[\$€£¥₹₽]', '', currency_str)
    cleaned = cleaned.strip()

    # Remove thousands separators (commas)
    cleaned = cleaned.replace(',', '')

    # Remove currency codes (USD, EUR, etc.)
    cleaned = re.sub(r'\b[A-Z]{3}\b', '', cleaned).strip()

    if not cleaned:
        raise ValueError("Empty currency string")

    try:
        return float(cleaned)
    except ValueError as e:
        raise ValueError(f"Cannot parse currency: {currency_str}") from e


@atheris.instrument_func
def test_currency_parser_fuzz(data):
    """
    Fuzz test for currency parsing.

    Tests:
    - Random bytes as currency strings
    - Malformed UTF-8
    - Empty strings
    - Special characters
    - Very long strings

    Expected exceptions: ValueError (for invalid input)
    Unexpected: Crashes, segmentation faults
    """
    try:
        # Convert bytes to string (ignore invalid UTF-8)
        currency_str = data.decode('utf-8', errors='ignore')

        # Truncate to reasonable length for safety
        if len(currency_str) > 1000:
            currency_str = currency_str[:1000]

        # Attempt to parse
        result = parse_currency(currency_str)

        # If we got here, parse succeeded
        # Verify result is a finite number
        assert isinstance(result, (int, float))
        assert not (result != result)  # Check for NaN
        assert abs(result) < 1e15  # Sanity check for reasonable values

    except (ValueError, InvalidOperation):
        # Expected exceptions for invalid input
        pass
    except Exception as e:
        # Unexpected exception - possible crash
        print(f"Unexpected exception: {e}")
        raise


def main(argc, argv):
    """Main entry point for fuzzing."""
    if not ATHERIS_AVAILABLE:
        print("Error: Atheris not available")
        sys.exit(1)

    # Set up fuzzer
    atheris.Setup(argv, test_currency_parser_fuzz)

    # Run fuzzer
    atheris.Fuzz()


if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
