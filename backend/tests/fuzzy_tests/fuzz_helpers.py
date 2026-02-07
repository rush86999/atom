"""
Fuzzy Test Helpers for Atom Testing Framework

Provides common utilities and helpers for writing fuzz tests using Atheris.
"""

import sys
import os
from typing import Callable, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

try:
    import atheris
    ATHERIS_AVAILABLE = True
except ImportError:
    ATHERIS_AVAILABLE = False
    print("Warning: Atheris not available. Fuzz tests will be skipped.")


def setup_fuzzer(test_func: Callable[[bytes], None], argv: list = None):
    """
    Set up Atheris fuzzer with the given test function.

    Args:
        test_func: Function that takes bytes and tests the code
        argv: Command-line arguments (defaults to sys.argv)
    """
    if not ATHERIS_AVAILABLE:
        print("Atheris not available. Skipping fuzzer setup.")
        return

    if argv is None:
        argv = sys.argv

    atheris.Setup(argv, test_func)


def run_fuzz():
    """Run the fuzzer (must be called after setup_fuzzer)."""
    if not ATHERIS_AVAILABLE:
        print("Atheris not available. Skipping fuzzing.")
        return

    atheris.Fuzz()


def with_expected_exceptions(*exceptions):
    """
    Decorator that catches expected exceptions during fuzzing.

    Usage:
        @with_expected_exceptions(ValueError, TypeError)
        def test_fuzz(data):
            ...
    """
    def decorator(func):
        def wrapper(data):
            try:
                func(data)
            except exceptions:
                pass  # Expected exceptions are OK
            except Exception as e:
                # Unexpected exceptions should crash
                raise
        return wrapper
    return decorator


def sanitize_bytes(data: bytes) -> str:
    """
    Safely convert bytes to string, ignoring errors.

    Args:
        data: Input bytes

    Returns:
        String representation (with invalid UTF-8 replaced)
    """
    return data.decode('utf-8', errors='ignore')


def truncate_string(s: str, max_length: int = 1000) -> str:
    """
    Truncate string to max length for safety.

    Args:
        s: Input string
        max_length: Maximum length

    Returns:
        Truncated string
    """
    return s[:max_length] if len(s) > max_length else s


class FuzzTestCase:
    """Base class for fuzz test cases."""

    def __init__(self, name: str):
        self.name = name
        self.crashes = 0
        self.executions = 0

    def run(self, data: bytes):
        """
        Run the fuzz test case.

        Args:
            data: Fuzz input data
        """
        self.executions += 1
        try:
            self.test_func(data)
        except Exception as e:
            self.crashes += 1
            print(f"Crash in {self.name}: {e}")
            raise

    def test_func(self, data: bytes):
        """Override this method in subclasses."""
        raise NotImplementedError

    def stats(self) -> dict:
        """Return test statistics."""
        return {
            'name': self.name,
            'executions': self.executions,
            'crashes': self.crashes,
            'crash_rate': self.crashes / self.executions if self.executions > 0 else 0
        }


if __name__ == "__main__":
    if ATHERIS_AVAILABLE:
        print("Atheris fuzzing helpers loaded successfully.")
    else:
        print("Warning: Atheris not available. Install with: pip install atheris")
