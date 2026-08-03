"""Tests for predictive modeling tools (forecast + run_model).

Covers: linear regression forecast, moving average forecast, regression
model training (R², coefficients), classification model training (accuracy,
feature importance), governance notice presence, and error handling.
"""
import asyncio
import os
import tempfile

import pytest


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
