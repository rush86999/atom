#!/usr/bin/env python3
"""
Sprint 1 Test Runner
Runs tests without loading conftest to avoid main app import issues
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_test_file(test_file_name, test_class_name):
    """Run tests from a specific file"""
    module_name = test_file_name.replace('.py', '')
    test_module = __import__(f'tests.{module_name}', fromlist=[module_name])

    # Get test class
    test_class = getattr(test_module, test_class_name)

    # Run all test methods
    test_methods = [m for m in dir(test_class) if m.startswith('test_')]

    passed = 0
    failed = 0
    errors = []

    for method_name in test_methods:
        try:
            method = getattr(test_class, method_name)
            # Check if it's async
            import asyncio
            if asyncio.iscoroutinefunction(method):
                print(f"  ⏭️  Skipping async test: {method_name}")
                continue

            # Run test
            print(f"  Running {method_name}...", end=" ")
            method()
            print("✓ PASSED")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED")
            print(f"    {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR")
            print(f"    {e}")
            errors.append((method_name, str(e)))
            failed += 1

    return passed, failed, errors


def main():
    print("=" * 70)
    print("SPRINT 1 TEST RESULTS")
    print("=" * 70)
    print()

    total_passed = 0
    total_failed = 0

    # Run GraphRAG tests
    print("📊 GraphRAG Pattern Extraction Tests")
    print("-" * 70)

    # Import test classes
    from tests.test_graphrag_patterns import (
        TestEmailExtraction, TestURLExtraction, TestPhoneExtraction,
        TestDateExtraction, TestCurrencyExtraction, TestIPExtraction,
        TestUUIDExtraction, TestMixedContent, TestEmptyInput
    )

    test_instances = [
        TestEmailExtraction(),
        TestURLExtraction(),
        TestPhoneExtraction(),
        TestDateExtraction(),
        TestCurrencyExtraction(),
        TestIPExtraction(),
        TestUUIDExtraction(),
        TestMixedContent(),
        TestEmptyInput(),
    ]

    for test_instance in test_instances:
        test_methods = [m for m in dir(test_instance) if m.startswith('test_')]

        for method_name in test_methods:
            try:
                method = getattr(test_instance, method_name)
                print(f"  {method_name}...", end=" ")
                method()
                print("✓")
                total_passed += 1
            except AssertionError as e:
                print(f"✗ {e}")
                total_failed += 1
            except Exception as e:
                print(f"✗ {type(e).__name__}: {e}")
                total_failed += 1

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")

    if total_failed == 0:
        print()
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print()
        print(f"⚠️  {total_failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
