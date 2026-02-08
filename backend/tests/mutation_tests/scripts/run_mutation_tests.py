#!/usr/bin/env python3
"""
Mutation Testing Runner

This script runs mutation testing using mutmut and generates reports.

Usage:
    python run_mutation_tests.py --target priority_p0_financial
    python run_mutation_tests.py --all
    python run_mutation_tests.py --quick

Options:
    --target: Run mutation tests for specific target
    --all: Run all mutation tests (all targets)
    --quick: Quick smoke test (fewer mutations)
    --report: Generate HTML report
    --threshold: Override score threshold
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
import configparser
from datetime import datetime


def load_targets_config():
    """Load mutation testing targets configuration."""
    config_path = Path(__file__).parent / "targets" / "TARGETS.ini"
    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def run_mutmut_for_target(target_name, config, quick=False, threshold=None):
    """Run mutmut for a specific target."""
    if target_name not in config:
        print(f"Error: Target '{target_name}' not found in configuration")
        return False

    target_config = config[target_name]
    modules = target_config.get('modules', '').split('\n')
    modules = [m.strip() for m in modules if m.strip()]

    if not modules:
        print(f"Warning: No modules defined for target '{target_name}'")
        return False

    # Get threshold
    score_threshold = float(target_config.get('mutation_score_threshold', 80.0))
    if threshold is not None:
        score_threshold = float(threshold)

    print(f"\n{'='*60}")
    print(f"Running mutation tests for: {target_name}")
    print(f"Modules: {', '.join(modules)}")
    print(f"Score threshold: {score_threshold}%")
    print(f"{'='*60}\n")

    # Build mutmut command
    cmd = [
        "mutmut", "run",
        "--paths-to-mutate", ",".join(modules),
        "--runner", "pytest tests/ -x -q --tb=line"
    ]

    if quick:
        cmd.extend(["--max-examples", "10"])

    # Run mutmut
    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)

        # Generate HTML report
        subprocess.run(
            ["mutmut", "html"],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=False
        )

        # Check results
        score = parse_mutation_score(result.stdout)

        if score is not None:
            print(f"\n{'='*60}")
            print(f"Mutation Score: {score:.2f}%")
            print(f"Threshold: {score_threshold}%")
            print(f"{'='*60}\n")

            if score >= score_threshold:
                print(f"✅ PASSED: Score {score:.2f}% >= {score_threshold}%")
                return True
            else:
                print(f"❌ FAILED: Score {score:.2f}% < {score_threshold}%")
                return False
        else:
            print("Warning: Could not parse mutation score")
            return False

    except subprocess.TimeoutExpired:
        print(f"Error: Mutation testing timed out for target '{target_name}'")
        return False
    except Exception as e:
        print(f"Error running mutation tests: {e}")
        return False


def parse_mutation_score(output):
    """Parse mutation score from mutmut output."""
    import re

    # Look for "Mutation score: XX.XX%" pattern
    match = re.search(r'Mutation score:\s+(\d+\.\d+)%', output)
    if match:
        return float(match.group(1))
    return None


def run_all_targets(config, quick=False, threshold=None):
    """Run mutation tests for all targets."""
    targets = [s for s in config.sections() if s.startswith('priority_')]

    results = {}
    for target in targets:
        results[target] = run_mutmut_for_target(
            target,
            config,
            quick=quick,
            threshold=threshold
        )

    # Summary
    print(f"\n{'='*60}")
    print("MUTATION TESTING SUMMARY")
    print(f"{'='*60}\n")

    for target, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{target}: {status}")

    total = len(results)
    passed = sum(1 for r in results.values() if r)

    print(f"\nTotal: {passed}/{total} targets passed")

    return passed == total


def main():
    parser = argparse.ArgumentParser(
        description="Run mutation testing for Atom platform"
    )
    parser.add_argument(
        "--target",
        help="Specific target to test (e.g., priority_p0_financial)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all mutation tests"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick smoke test (fewer mutations)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        help="Override score threshold"
    )

    args = parser.parse_args()

    # Load configuration
    config = load_targets_config()

    # Run tests
    if args.target:
        success = run_mutmut_for_target(
            args.target,
            config,
            quick=args.quick,
            threshold=args.threshold
        )
        sys.exit(0 if success else 1)
    elif args.all:
        success = run_all_targets(
            config,
            quick=args.quick,
            threshold=args.threshold
        )
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
