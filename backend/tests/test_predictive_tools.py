"""Tests for predictive modeling tools (forecast + run_model).

Covers: linear regression forecast, moving average forecast, regression
model training (R², coefficients), classification model training (accuracy,
feature importance), governance notice presence, and error handling.
"""
import asyncio
import contextlib
import io
import os
import tempfile
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _mock_sandbox_runtime(monkeypatch):
    """analyze_data fails closed in production when the sandbox is unavailable
    (B1 — the in-process exec fallback was removed as a P0 RCE). For unit tests
    of the tool logic, substitute a test-only runtime that executes the
    (test-controlled) code in-process and returns captured stdout."""
    import core.sandbox_runtime as srt

    class _ExecutingFakeRuntime:
        async def execute_python(self, code, *, policy, inputs=None, cwd=None):
            ns = {"__inputs__": inputs or {}}
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exec(code, ns, ns)
            return SimpleNamespace(
                success=True, stdout=buf.getvalue(), stderr="", exit_code=0
            )

    monkeypatch.setattr(srt, "get_runtime", lambda: _ExecutingFakeRuntime())


@pytest.fixture
def timeseries_csv():
    """Create a CSV with time-series data (sales by day)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("date,sales\n")
        for i in range(1, 21):
            f.write(f"2026-01-{i:02d},{100 + i * 5}\n")
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def regression_csv():
    """Create a CSV for regression (house prices)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("sqft,bedrooms,price\n")
        f.write("1500,3,300000\n")
        f.write("2000,4,400000\n")
        f.write("1200,2,250000\n")
        f.write("1800,3,350000\n")
        f.write("2500,4,500000\n")
        f.write("3000,5,600000\n")
        f.write("2200,4,440000\n")
        f.write("1600,3,320000\n")
        path = f.name
    yield path
    os.unlink(path)


# --- Forecast tool ---------------------------------------------------------


@pytest.mark.asyncio
async def test_forecast_linear(timeseries_csv):
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import forecast

    await load_dataset(source=timeseries_csv, name="sales", session_id="fc-test")
    result = await forecast(
        dataset_name="sales",
        target_column="sales",
        periods=5,
        date_column="date",
        method="linear",
        session_id="fc-test",
    )
    assert result["success"]
    forecast_data = result["forecast"]
    assert isinstance(forecast_data, dict)
    assert "forecast" in forecast_data
    assert len(forecast_data["forecast"]) == 5
    assert "r_squared" in forecast_data["model_stats"]
    assert "governance_notice" in result


@pytest.mark.asyncio
async def test_forecast_moving_average(timeseries_csv):
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import forecast

    await load_dataset(source=timeseries_csv, name="sales", session_id="fc-test2")
    result = await forecast(
        dataset_name="sales",
        target_column="sales",
        periods=3,
        method="moving_average",
        session_id="fc-test2",
    )
    assert result["success"]
    assert "forecast" in result["forecast"]
    assert len(result["forecast"]["forecast"]) == 3


@pytest.mark.asyncio
async def test_forecast_unknown_method(timeseries_csv):
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import forecast

    await load_dataset(source=timeseries_csv, name="sales", session_id="fc-test3")
    result = await forecast(
        dataset_name="sales",
        target_column="sales",
        method="bogus",
        session_id="fc-test3",
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_forecast_not_loaded():
    from tools.predictive_tools import forecast
    result = await forecast(
        dataset_name="nonexistent",
        target_column="x",
        session_id="fc-test4",
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_forecast_governance_notice(timeseries_csv):
    """Forecast results must include a governance notice for human review."""
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import forecast

    await load_dataset(source=timeseries_csv, name="sales", session_id="fc-gov")
    result = await forecast(
        dataset_name="sales",
        target_column="sales",
        periods=3,
        method="linear",
        session_id="fc-gov",
    )
    assert result["success"]
    assert "governance_notice" in result
    assert "review" in result["governance_notice"].lower()


# --- run_model tool --------------------------------------------------------


@pytest.mark.asyncio
async def test_run_model_regression(regression_csv):
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import run_model

    await load_dataset(source=regression_csv, name="houses", session_id="rm-test")
    result = await run_model(
        dataset_name="houses",
        target_column="price",
        model_type="regression",
        session_id="rm-test",
    )
    assert result["success"]
    model_data = result["model"]
    assert isinstance(model_data, dict)
    assert "test_r2" in model_data
    assert "coefficients" in model_data
    assert "governance_notice" in result


@pytest.mark.asyncio
async def test_run_model_classification(regression_csv):
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import run_model

    await load_dataset(source=regression_csv, name="houses", session_id="rm-test2")
    result = await run_model(
        dataset_name="houses",
        target_column="bedrooms",  # classify into bedroom counts
        model_type="classification",
        session_id="rm-test2",
    )
    assert result["success"]
    model_data = result["model"]
    assert "test_accuracy" in model_data
    assert "feature_importance" in model_data


@pytest.mark.asyncio
async def test_run_model_unknown_type(regression_csv):
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import run_model

    await load_dataset(source=regression_csv, name="houses", session_id="rm-test3")
    result = await run_model(
        dataset_name="houses",
        target_column="price",
        model_type="bogus",
        session_id="rm-test3",
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_run_model_governance_notice(regression_csv):
    """Model results must include a governance notice for human review."""
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import run_model

    await load_dataset(source=regression_csv, name="houses", session_id="rm-gov")
    result = await run_model(
        dataset_name="houses",
        target_column="price",
        model_type="regression",
        session_id="rm-gov",
    )
    assert result["success"]
    assert "governance_notice" in result
    assert "review" in result["governance_notice"].lower()


# --- B11: exponential-smoothing robustness -----------------------------------


@pytest.fixture
def tiny_series_csv():
    """2-row time series — too short for statsmodels trend='add' (needs >2)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("date,sales\n")
        f.write("2026-01-01,10\n")
        f.write("2026-01-02,20\n")
        path = f.name
    yield path
    os.unlink(path)


def _install_fake_statsmodels_valueerror(monkeypatch):
    """Install a fake statsmodels whose ExponentialSmoothing raises ValueError
    on construction (simulates a short series). statsmodels is not installed in
    this env, so the ImportError branch is the only path today — the fake
    forces the ValueError branch that currently escapes the try/except."""
    import sys
    import types

    sm = types.ModuleType("statsmodels")
    tsa = types.ModuleType("statsmodels.tsa")
    hw = types.ModuleType("statsmodels.tsa.holtwinters")

    def _raise(*args, **kwargs):
        raise ValueError("ExponentialSmoothing requires at least 3 datapoints")

    hw.ExponentialSmoothing = _raise
    tsa.holtwinters = hw
    sm.tsa = tsa
    monkeypatch.setitem(sys.modules, "statsmodels", sm)
    monkeypatch.setitem(sys.modules, "statsmodels.tsa", tsa)
    monkeypatch.setitem(sys.modules, "statsmodels.tsa.holtwinters", hw)


@pytest.mark.asyncio
async def test_forecast_exponential_short_series_falls_back(monkeypatch, tiny_series_csv):
    """B11: forecast(method='exponential') must fall back to simple exponential
    smoothing when statsmodels raises ValueError on a short series — not fail.
    Currently only ImportError is caught, so the ValueError escapes to a tool
    error."""
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import forecast

    _install_fake_statsmodels_valueerror(monkeypatch)

    await load_dataset(source=tiny_series_csv, name="tiny", session_id="b11")
    result = await forecast(
        dataset_name="tiny",
        target_column="sales",
        periods=3,
        method="exponential",
        session_id="b11",
    )
    assert result["success"] is True, (
        f"B11 regression: exponential forecast failed instead of falling "
        f"back to simple EMA. got: {result}"
    )
    forecast_data = result["forecast"]
    assert isinstance(forecast_data, dict)
    assert len(forecast_data["forecast"]) == 3


@pytest.mark.asyncio
async def test_forecast_results_held_for_review(timeseries_csv):
    """B13: forecast results must carry a structured governance block marking
    them PENDING human review — a machine-readable HITL surface, not just an
    advisory notice string."""
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import forecast

    await load_dataset(source=timeseries_csv, name="sales", session_id="b13-gov")
    result = await forecast(
        dataset_name="sales",
        target_column="sales",
        periods=3,
        method="linear",
        session_id="b13-gov",
    )
    assert result["success"]
    gov = result.get("governance")
    assert gov is not None, (
        f"B13 regression: forecast result has no structured governance block "
        f"(HITL not surfaced). got: {result}"
    )
    assert gov.get("requires_review") is True
    assert gov.get("review_status") == "PENDING"


@pytest.mark.asyncio
async def test_run_model_results_held_for_review(regression_csv):
    """B13: run_model results must carry a structured governance block marking
    them PENDING human review."""
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import run_model

    await load_dataset(source=regression_csv, name="houses", session_id="b13-gov2")
    result = await run_model(
        dataset_name="houses",
        target_column="price",
        model_type="regression",
        session_id="b13-gov2",
    )
    assert result["success"]
    gov = result.get("governance")
    assert gov is not None, (
        f"B13 regression: run_model result has no structured governance block "
        f"(HITL not surfaced). got: {result}"
    )
    assert gov.get("requires_review") is True
    assert gov.get("review_status") == "PENDING"


@pytest.mark.asyncio
async def test_forecast_rejects_invalid_periods(timeseries_csv):
    """B11/315-02D: periods outside 1..365 (or non-int) return a clean error
    before any codegen — no huge/negative/zero forecasts."""
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import forecast

    await load_dataset(source=timeseries_csv, name="sales", session_id="b11p")
    for bad in (0, -3, 366, 1000, "7", 3.5, True):
        result = await forecast(
            dataset_name="sales",
            target_column="sales",
            periods=bad,
            method="linear",
            session_id="b11p",
        )
        assert result["success"] is False, (
            f"periods={bad!r} should be rejected, got {result}"
        )
