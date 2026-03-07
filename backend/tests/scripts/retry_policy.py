#!/usr/bin/env python3
"""
Centralized retry policy configuration for flaky test detection.

Provides platform-specific retry policies with environment variable override support.
Used by flaky test detectors across all platforms (backend pytest, frontend Jest, mobile jest-expo, desktop cargo).

Usage:
    python backend/tests/scripts/retry_policy.py --platform backend
    FLAKY_THRESHOLD=0.5 python backend/tests/scripts/retry_policy.py --platform frontend
"""

import os
import sys
import json
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class RetryPolicy:
    """
    Retry policy configuration for flaky tests.

    Attributes:
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        test_timeout: Timeout for single test run in seconds
        flaky_threshold: Flaky rate threshold for quarantine (0.0 to 1.0)
        detection_runs: Number of runs for flaky detection
        min_stable_runs: Minimum runs before considering test stable
        auto_quarantine: Automatically skip quarantined tests
        warn_quarantine: Warn on quarantined tests
        platform_overrides: Platform-specific override policies
    """

    # Maximum number of retry attempts
    max_retries: int = 3

    # Delay between retries (seconds)
    retry_delay: float = 1.0

    # Timeout for single test run (seconds)
    test_timeout: float = 30.0

    # Flaky rate threshold for quarantine (0.0 to 1.0)
    flaky_threshold: float = 0.3  # 30% failure rate

    # Number of runs for flaky detection
    detection_runs: int = 10

    # Minimum runs before considering test stable
    min_stable_runs: int = 20

    # Quarantine: Automatically skip quarantined tests
    auto_quarantine: bool = True

    # Quarantine: Warn on quarantined tests
    warn_quarantine: bool = True

    # Platform-specific overrides
    platform_overrides: Optional[Dict[str, Dict[str, Any]]] = None

    def get_policy_for_platform(self, platform: str) -> 'RetryPolicy':
        """
        Get retry policy for specific platform.

        Merges platform-specific overrides with base policy.

        Args:
            platform: Platform name (backend, frontend, mobile, desktop)

        Returns:
            RetryPolicy with platform-specific overrides applied
        """
        if self.platform_overrides and platform in self.platform_overrides:
            overrides = self.platform_overrides[platform]
            # Merge overrides with base policy
            return RetryPolicy(**{**asdict(self), **overrides, 'platform_overrides': None})
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary, excluding platform_overrides."""
        return {k: v for k, v in asdict(self).items() if k != 'platform_overrides'}


# Default retry policies
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    retry_delay=1.0,
    test_timeout=30.0,
    flaky_threshold=0.3,
    detection_runs=10,
    min_stable_runs=20,
    auto_quarantine=True,
    warn_quarantine=True,
    platform_overrides={
        # Backend: Longer timeout for async tests
        "backend": {
            "test_timeout": 60.0,
            "max_retries": 2,
        },
        # Frontend: Lower flaky threshold (MSW/axios issues)
        "frontend": {
            "flaky_threshold": 0.2,
            "detection_runs": 15,
        },
        # Mobile: More retries (network flakiness)
        "mobile": {
            "max_retries": 5,
            "retry_delay": 2.0,
        },
        # Desktop: Faster retries (Rust tests are fast)
        "desktop": {
            "max_retries": 2,
            "retry_delay": 0.5,
            "test_timeout": 15.0,
        }
    }
)


def get_policy(platform: Optional[str] = None) -> RetryPolicy:
    """
    Load retry policy with environment variable overrides.

    Environment variables:
        FLAKY_THRESHOLD: Override flaky_threshold (e.g., "0.5")
        MAX_RETRIES: Override max_retries (e.g., "5")
        RETRY_DELAY: Override retry_delay (e.g., "2.0")
        TEST_TIMEOUT: Override test_timeout (e.g., "60.0")
        DETECTION_RUNS: Override detection_runs (e.g., "15")

    Args:
        platform: Platform name (backend, frontend, mobile, desktop)

    Returns:
        RetryPolicy with environment variable overrides applied
    """
    policy = DEFAULT_RETRY_POLICY

    # Apply platform-specific overrides
    if platform:
        policy = policy.get_policy_for_platform(platform)

    # Apply environment variable overrides
    if "FLAKY_THRESHOLD" in os.environ:
        try:
            policy.flaky_threshold = float(os.environ["FLAKY_THRESHOLD"])
        except ValueError:
            print(f"Warning: Invalid FLAKY_THRESHOLD '{os.environ['FLAKY_THRESHOLD']}', using default", file=sys.stderr)

    if "MAX_RETRIES" in os.environ:
        try:
            policy.max_retries = int(os.environ["MAX_RETRIES"])
        except ValueError:
            print(f"Warning: Invalid MAX_RETRIES '{os.environ['MAX_RETRIES']}', using default", file=sys.stderr)

    if "RETRY_DELAY" in os.environ:
        try:
            policy.retry_delay = float(os.environ["RETRY_DELAY"])
        except ValueError:
            print(f"Warning: Invalid RETRY_DELAY '{os.environ['RETRY_DELAY']}', using default", file=sys.stderr)

    if "TEST_TIMEOUT" in os.environ:
        try:
            policy.test_timeout = float(os.environ["TEST_TIMEOUT"])
        except ValueError:
            print(f"Warning: Invalid TEST_TIMEOUT '{os.environ['TEST_TIMEOUT']}', using default", file=sys.stderr)

    if "DETECTION_RUNS" in os.environ:
        try:
            policy.detection_runs = int(os.environ["DETECTION_RUNS"])
        except ValueError:
            print(f"Warning: Invalid DETECTION_RUNS '{os.environ['DETECTION_RUNS']}', using default", file=sys.stderr)

    return policy


def main():
    """CLI for testing retry policy configuration."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Display retry policy configuration for a platform"
    )
    parser.add_argument(
        "--platform",
        choices=["backend", "frontend", "mobile", "desktop"],
        help="Platform to get policy for"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output policy as JSON"
    )

    args = parser.parse_args()

    policy = get_policy(args.platform)

    if args.json:
        print(json.dumps(policy.to_dict(), indent=2))
    else:
        platform_name = args.platform or "default"
        print(f"Retry Policy for {platform_name}:")
        print(f"  max_retries: {policy.max_retries}")
        print(f"  retry_delay: {policy.retry_delay}s")
        print(f"  test_timeout: {policy.test_timeout}s")
        print(f"  flaky_threshold: {policy.flaky_threshold}")
        print(f"  detection_runs: {policy.detection_runs}")
        print(f"  min_stable_runs: {policy.min_stable_runs}")
        print(f"  auto_quarantine: {policy.auto_quarantine}")
        print(f"  warn_quarantine: {policy.warn_quarantine}")


if __name__ == "__main__":
    main()
