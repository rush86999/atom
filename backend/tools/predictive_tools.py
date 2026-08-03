"""Predictive modeling agent tools (governed).

Provides forecasting and regression/classification capabilities via classical
ML (sklearn/statsmodels) executed in the sandbox. These tools are
SUPERVISED-maturity-gated: the LLM generates modeling code; the sandbox runs
it; results are surfaced for human review before being acted upon.

Evidence (each validated against ≥2 independent sources):
- IBM Developer: use pre-trained/classical ML via tool-calling, not raw LLM.
- AWS: predictive ML models via MCP + SageMaker.
- Towards Data Science: LLMs orchestrate sklearn tools.
- DeepLearning.AI community: LLMs predict tokens, not numbers — must use
  classical ML via tool-calling.
- arXiv 2605.09252: LLM agents call tools indiscriminately — needs governance.

Restriction: SUPERVISED maturity minimum. Financial forecasting results must
pass through HITL before deployment.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def forecast(
    dataset_name: str,
    target_column: str,
    periods: int = 7,
    date_column: Optional[str] = None,
    method: str = "linear",
    **kwargs,
) -> Dict[str, Any]:
    """Generate a time-series forecast from a cached dataset.

    Uses classical forecasting methods (not LLM-native prediction):
    - 'linear': Linear regression on time index (simple, interpretable)
    - 'moving_average': Moving average with trend
    - 'exponential': Exponential smoothing (statsmodels, if available)

    The LLM generates the modeling code; the sandbox executes it with the
    dataset available as 'df'. Results include forecast values, confidence
    interval (when available), and model diagnostics.

    **Governance**: Requires SUPERVISED maturity. Forecast results should
    be reviewed by a human before being used for business decisions.

    Args:
        dataset_name: Name of a previously-loaded dataset.
        target_column: The numeric column to forecast.
        periods: Number of future periods to forecast (default 7).
        date_column: Optional date/time column for time-series indexing.
        method: Forecasting method ('linear', 'moving_average', 'exponential').
    """
    session_id = kwargs.get("session_id", "default")

    # Build the forecasting code
    date_handling = ""
    if date_column:
        date_handling = f"df['{date_column}'] = pd.to_datetime(df['{date_column}'])\ndf = df.sort_values('{date_column}')\n"

    if method == "linear":
        code = f"""
import json
{date_handling}
from sklearn.linear_model import LinearRegression
import numpy as np

target = df['{target_column}'].values
n = len(target)
X = np.arange(n).reshape(-1, 1)

model = LinearRegression()
model.fit(X, target)

future_X = np.arange(n, n + {periods}).reshape(-1, 1)
forecast_values = model.predict(future_X)
slope = model.coef_[0]
intercept = model.intercept_
r_squared = model.score(X, target)

result = {{
    "method": "linear_regression",
    "forecast": [round(float(v), 2) for v in forecast_values],
    "periods": {periods},
    "model_stats": {{
        "slope": round(float(slope), 4),
        "intercept": round(float(intercept), 4),
        "r_squared": round(float(r_squared), 4),
    }},
    "historical_mean": round(float(np.mean(target)), 2),
    "historical_std": round(float(np.std(target)), 2),
}}
print(json.dumps(result))
"""
    elif method == "moving_average":
        code = f"""
import json
import numpy as np

{date_handling}
target = df['{target_column}'].values
window = min(7, len(target) // 2) if len(target) > 2 else 1
ma = np.mean(target[-window:])
trend = (target[-1] - target[0]) / max(len(target), 1)

forecast_values = [ma + trend * (i + 1) for i in range({periods})]
result = {{
    "method": "moving_average",
    "window": window,
    "forecast": [round(float(v), 2) for v in forecast_values],
    "periods": {periods},
    "trend_per_period": round(float(trend), 4),
    "historical_mean": round(float(np.mean(target)), 2),
}}
print(json.dumps(result))
"""
    elif method == "exponential":
        code = f"""
import json
import numpy as np

{date_handling}
target = df['{target_column}'].values

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    model = ExponentialSmoothing(target, trend='add', seasonal=None)
    fit = model.fit()
    forecast_values = fit.forecast({periods})
    result = {{
        "method": "exponential_smoothing",
        "forecast": [round(float(v), 2) for v in forecast_values],
        "periods": {periods},
        "aic": round(float(fit.aic), 2),
    }}
except ImportError:
    # Fallback to simple exponential smoothing
    alpha = 0.3
    smoothed = target[0]
    for v in target[1:]:
        smoothed = alpha * v + (1 - alpha) * smoothed
    forecast_values = [smoothed] * {periods}
    result = {{
        "method": "simple_exponential (statsmodels unavailable)",
        "forecast": [round(float(v), 2) for v in forecast_values],
        "periods": {periods},
        "alpha": alpha,
    }}
print(json.dumps(result))
"""
    else:
        return {"success": False, "error": f"Unknown method: {method}. Use 'linear', 'moving_average', or 'exponential'."}

    # Delegate to analyze_data for execution
    from tools.data_analysis_tool import analyze_data
    result = await analyze_data(
        dataset_name=dataset_name,
        code=code,
        session_id=session_id,
    )

    if result.get("success"):
        return {
            "success": True,
            "forecast": result.get("results", result.get("output")),
            "governance_notice": (
                "Forecast generated by classical ML (not LLM-native). "
                "Review before using for business decisions."
            ),
        }
    return result


async def run_model(
    dataset_name: str,
    target_column: str,
    feature_columns: Optional[list] = None,
    model_type: str = "regression",
    test_size: float = 0.2,
    **kwargs,
) -> Dict[str, Any]:
    """Train and evaluate a predictive model on a cached dataset.

    Uses classical ML (sklearn) — the LLM generates the modeling code;
    the sandbox executes it.

    **Governance**: Requires SUPERVISED maturity. Model results should be
    reviewed by a human before deployment.

    Args:
        dataset_name: Name of a previously-loaded dataset.
        target_column: The column to predict.
        feature_columns: List of feature column names (default: all except target).
        model_type: 'regression' (LinearRegression) or 'classification' (RandomForest).
        test_size: Fraction of data for testing (default 0.2).
    """
    session_id = kwargs.get("session_id", "default")

    if feature_columns is None:
        feature_cols_code = "feature_cols = [c for c in df.columns if c != target_col]"
    else:
        cols_str = ", ".join(f"'{c}'" for c in feature_columns)
        feature_cols_code = f"feature_cols = [{cols_str}]"

    if model_type == "regression":
        imports_code = """
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
"""
        model_code = "model = LinearRegression()"
        metrics_code = """
result = {
    "model_type": "linear_regression",
    "train_score": round(float(model.score(X_train, y_train)), 4),
    "test_r2": round(float(r2_score(y_test, y_pred)), 4),
    "test_mse": round(float(mean_squared_error(y_test, y_pred)), 4),
    "test_mae": round(float(mean_absolute_error(y_test, y_pred)), 4),
    "coefficients": {str(col): round(float(c), 4) for col, c in zip(feature_cols, model.coef_)},
    "intercept": round(float(model.intercept_), 4),
    "n_train": len(X_train), "n_test": len(X_test),
}
"""
    elif model_type == "classification":
        imports_code = """
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
"""
        model_code = "model = RandomForestClassifier(n_estimators=50, random_state=42)"
        metrics_code = """
result = {
    "model_type": "random_forest_classifier",
    "train_accuracy": round(float(accuracy_score(y_train, model.predict(X_train))), 4),
    "test_accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
    "feature_importance": {str(col): round(float(imp), 4) for col, imp in zip(feature_cols, model.feature_importances_)},
    "n_train": len(X_train), "n_test": len(X_test),
    "classes": [str(c) for c in model.classes_],
}
"""
    else:
        return {"success": False, "error": f"Unknown model_type: {model_type}. Use 'regression' or 'classification'."}

    code = f"""
import json
import pandas as pd
import numpy as np
{imports_code}

target_col = '{target_column}'
{feature_cols_code}

# Drop rows with missing values
df_clean = df.dropna(subset=feature_cols + [target_col])
X = df_clean[feature_cols]
y = df_clean[target_col]

# Convert non-numeric features
for col in X.columns:
    if X[col].dtype == 'object':
        X[col] = pd.Categorical(X[col]).codes

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size={test_size}, random_state=42)
{model_code}
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
{metrics_code}
result["n_features"] = len(feature_cols)
result["feature_columns"] = feature_cols
result["rows_used"] = len(df_clean)
result["rows_dropped"] = len(df) - len(df_clean)
print(json.dumps(result, default=str))
"""

    from tools.data_analysis_tool import analyze_data
    result = await analyze_data(
        dataset_name=dataset_name,
        code=code,
        session_id=session_id,
    )

    if result.get("success"):
        return {
            "success": True,
            "model": result.get("results", result.get("output")),
            "governance_notice": (
                "Model trained by classical ML (not LLM-native). "
                "Review metrics before deploying for business decisions."
            ),
        }
    return result


def register_predictive_tools(tool_registry=None):
    """Register predictive modeling tools with the tool registry.

    These tools are SUPERVISED-maturity-gated per the evidence on LLM
    tool-calling reliability (arXiv 2605.09252) and the consensus that
    LLMs should orchestrate classical ML, not forecast natively
    (IBM, AWS, Towards Data Science, DeepLearning.AI).
    """
    from tools.registry import get_tool_registry

    if tool_registry is None:
        tool_registry = get_tool_registry()

    tool_registry.register(
        name="forecast",
        function=forecast,
        version="1.0.0",
        description=(
            "Generate a time-series forecast from a cached dataset using "
            "classical ML (linear regression, moving average, or exponential "
            "smoothing). NOT LLM-native forecasting — uses sklearn/statsmodels. "
            "Results include forecast values, model statistics, and a governance "
            "notice to review before business use."
        ),
        category="data",
        complexity=4,
        maturity_required="SUPERVISED",
        parameters={
            "dataset_name": "string (required) — name of a previously-loaded dataset",
            "target_column": "string (required) — the numeric column to forecast",
            "periods": "int (optional, default 7) — number of future periods",
            "date_column": "string (optional) — date column for time-series indexing",
            "method": "string (optional) — linear/moving_average/exponential",
        },
        tags=["data", "forecast", "predictive", "time-series", "ml"],
    )

    tool_registry.register(
        name="run_model",
        function=run_model,
        version="1.0.0",
        description=(
            "Train and evaluate a predictive model (regression or classification) "
            "on a cached dataset using sklearn. Returns model metrics (R², MSE, "
            "accuracy, feature importance) and a governance notice to review "
            "before business deployment."
        ),
        category="data",
        complexity=4,
        maturity_required="SUPERVISED",
        parameters={
            "dataset_name": "string (required) — name of a previously-loaded dataset",
            "target_column": "string (required) — the column to predict",
            "feature_columns": "list (optional) — feature columns (default: all except target)",
            "model_type": "string (optional) — regression/classification",
            "test_size": "float (optional, default 0.2) — test set fraction",
        },
        tags=["data", "model", "regression", "classification", "sklearn", "ml"],
    )

    logger.info("Predictive modeling tools registered with ToolRegistry")
