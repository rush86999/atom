"""
Performance Regression Tests - Track performance over time.

This module contains tests that detect performance regressions by comparing
current benchmark results against historical baselines.

Tests use pytest-benchmark for historical tracking and the check_regression
fixture to fail when performance degrades beyond the threshold (20% by default).

Baselines are stored in performance_baseline.json and can be auto-updated
when performance improves by >10% using --benchmark-autosave.

Reference: Phase 243 Plan 02 - Performance Regression Detection
"""
