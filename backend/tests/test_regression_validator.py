"""Tests for the behavioral regression validator.

Phase 2 of the harness evolution gap closure. Covers: exact-match comparison,
mismatch detection, child crash detection, parent crash (improvement, not
regression), no-test-inputs edge case, fuzzy match, and to_dict serialization.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.auto_dev.regression_validator import (
    RegressionResult,
    RegressionValidator,
    TestMismatch,
)


# --- Mock sandbox helpers --------------------------------------------------


class _MockSandbox:
    """Mock sandbox returning predetermined outputs per code string."""

    def __init__(self, outputs: dict):
        self._outputs = outputs

    async def execute_raw_python(self, tenant_id, code, input_params, **kwargs):
        key = code.strip()
        return self._outputs.get(key, {"status": "success", "output": "default"})


# --- Exact-match tests ----------------------------------------------------


@pytest.mark.asyncio
async def test_identical_outputs_pass():
    sb = _MockSandbox({"parent": {"status": "success", "output": "42"},
                        "child": {"status": "success", "output": "42"}})
    v = RegressionValidator()
    result = await v.validate_regression("parent", "child", [{"x": 1}], sb, "t1")
    assert result.passed is True
    assert len(result.mismatches) == 0
    assert result.passed_tests == 1


@pytest.mark.asyncio
async def test_different_outputs_detected():
    sb = _MockSandbox({"parent": {"status": "success", "output": "42"},
                        "child": {"status": "success", "output": "99"}})
    v = RegressionValidator()
    result = await v.validate_regression("parent", "child", [{"x": 1}], sb, "t1")
    assert result.passed is False
    assert len(result.mismatches) == 1
    assert result.mismatches[0].parent_output == "42"
    assert result.mismatches[0].child_output == "99"


@pytest.mark.asyncio
async def test_multiple_test_inputs():
    """Multiple test inputs — any single mismatch fails the whole validation."""
    sb = _MockSandbox({"parent": {"status": "success", "output": "same"},
                        "child": {"status": "success", "output": "same"}})
    v = RegressionValidator()
    result = await v.validate_regression(
        "parent", "child", [{"x": 1}, {"x": 2}, {"x": 3}], sb, "t1"
    )
    assert result.passed is True
    assert result.total_tests == 3
    assert result.passed_tests == 3


@pytest.mark.asyncio
async def test_partial_mismatch_detected():
    """One mismatch out of three tests → overall fails."""
    call_count = [0]

    class PartialSandbox:
        async def execute_raw_python(self, tenant_id, code, input_params, **kwargs):
            call_count[0] += 1
            # Child returns "wrong" on the 2nd test (3rd+4th calls = child's 2nd)
            if code.strip() == "child" and call_count[0] == 4:
                return {"status": "success", "output": "wrong"}
            return {"status": "success", "output": "same"}

    v = RegressionValidator()
    result = await v.validate_regression(
        "parent", "child", [{"x": 1}, {"x": 2}], PartialSandbox(), "t1"
    )
    assert result.passed is False
    assert len(result.mismatches) >= 1


# --- Child crash -----------------------------------------------------------


@pytest.mark.asyncio
async def test_child_crash_detected():
    class CrashSandbox:
        async def execute_raw_python(self, tenant_id, code, input_params, **kwargs):
            if code.strip() == "child":
                return {"status": "failed", "output": "ZeroDivisionError"}
            return {"status": "success", "output": "42"}

    v = RegressionValidator()
    result = await v.validate_regression("parent", "child", [{"x": 1}], CrashSandbox(), "t1")
    assert result.passed is False
    assert "CRASH" in result.mismatches[0].child_output


# --- Parent crash (improvement, not regression) ----------------------------


@pytest.mark.asyncio
async def test_parent_crash_child_success_is_improvement():
    """If parent crashed but child succeeds, that's an improvement — not a regression."""
    class ImproveSandbox:
        async def execute_raw_python(self, tenant_id, code, input_params, **kwargs):
            if code.strip() == "parent":
                return {"status": "failed", "output": "old bug"}
            return {"status": "success", "output": "42"}

    v = RegressionValidator()
    result = await v.validate_regression("parent", "child", [{"x": 1}], ImproveSandbox(), "t1")
    assert result.passed is True
    assert result.passed_tests == 1


# --- Edge cases ------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_test_inputs_passes():
    """No test inputs → can't detect regression → passes (backward compat)."""
    v = RegressionValidator()
    result = await v.validate_regression("parent", "child", [], _MockSandbox({}), "t1")
    assert result.passed is True
    assert result.total_tests == 0


@pytest.mark.asyncio
async def test_whitespace_only_difference_passes_exact():
    """Exact match strips trailing whitespace."""
    sb = _MockSandbox({"parent": {"status": "success", "output": "42\n"},
                        "child": {"status": "success", "output": "42"}})
    v = RegressionValidator()
    result = await v.validate_regression("parent", "child", [{"x": 1}], sb, "t1")
    assert result.passed is True


# --- Fuzzy match -----------------------------------------------------------


@pytest.mark.asyncio
async def test_fuzzy_match_minor_difference_passes():
    sb = _MockSandbox({"parent": {"status": "success", "output": "The answer is 42."},
                        "child": {"status": "success", "output": "The answer is 42!\n"}})
    v = RegressionValidator(fuzzy_match=True, fuzzy_tolerance=0.9)
    result = await v.validate_regression("parent", "child", [{"x": 1}], sb, "t1")
    assert result.passed is True


@pytest.mark.asyncio
async def test_fuzzy_match_major_difference_fails():
    sb = _MockSandbox({"parent": {"status": "success", "output": "The answer is 42."},
                        "child": {"status": "success", "output": "Completely different output here."}})
    v = RegressionValidator(fuzzy_match=True, fuzzy_tolerance=0.9)
    result = await v.validate_regression("parent", "child", [{"x": 1}], sb, "t1")
    assert result.passed is False


# --- Serialization ---------------------------------------------------------


def test_regression_result_to_dict():
    r = RegressionResult(
        passed=False,
        total_tests=3,
        passed_tests=2,
        mismatches=[TestMismatch({"x": 1}, "expected", "got")],
    )
    d = r.to_dict()
    assert d["passed"] is False
    assert d["total_tests"] == 3
    assert d["passed_tests"] == 2
    assert d["mismatch_count"] == 1
    assert d["mismatches"][0]["test_input"] == {"x": 1}


def test_regression_detected_property():
    r = RegressionResult(passed=False, mismatches=[TestMismatch({}, "a", "b")])
    assert r.regression_detected is True

    r2 = RegressionResult(passed=True)
    assert r2.regression_detected is False
