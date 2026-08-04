"""RED tests — Round 70 / Plan 315-01: RCE surfaces in data analysis tools.

These tests assert the *secure* behavior and are expected to FAIL against the
current code (they document confirmed bugs). They go green in Plan 315-02.

Findings under test:
  B1 — analyze_data falls back to in-process exec(code) when the sandbox is
       unavailable (`backend/tools/data_analysis_tool.py:148-169`).
  B2 — forecast/run_model interpolate unsanitized target_column / date_column /
       periods / test_size / feature_columns into exec'd code
       (`backend/tools/predictive_tools.py:70,103,144,252-265`).
  B3 — dataset data is f-string interpolated into sandbox source
       (`backend/tools/data_analysis_tool.py:122-126`), so data becomes code.

TDD: red first, then fix in 315-02.
"""
import json

import pytest
from types import SimpleNamespace


@pytest.fixture
def sales_src():
    return '[{"date": "2026-01-01", "amount": 10}, {"date": "2026-01-02", "amount": 20}]'


@pytest.mark.asyncio
async def test_analyze_data_exec_fallback_runs_arbitrary_code(monkeypatch, sales_src):
    """B1: with the sandbox unavailable, analyze_data MUST NOT exec arbitrary
    code in the server process. The payload passes the AST policy (harmless
    on its face), so only a fail-closed sandbox path can stop it. Currently
    the in-process exec fallback runs it (success=True)."""
    from tools.data_analysis_tool import load_dataset, analyze_data
    import core.sandbox_runtime as srt

    async def _boom(*args, **kwargs):
        raise RuntimeError("docker not running")

    monkeypatch.setattr(srt, "get_runtime", _boom)

    await load_dataset(source=sales_src, name="sales", session_id="rce-b1")
    result = await analyze_data(
        dataset_name="sales",
        code="print(df.shape)",
        session_id="rce-b1",
    )

    # SECURE behavior: execution must fail closed — never run the code.
    assert result["success"] is False, (
        f"B1 regression: sandbox-unavailable exec fallback executed code. got: {result}"
    )


class FakeRuntime:
    """Fake sandbox runtime that records the code it receives."""

    def __init__(self):
        self.captured_code = None

    async def execute_python(self, code, *, policy, inputs=None, cwd=None):
        self.captured_code = code
        return SimpleNamespace(success=True, stdout="[]", stderr="", exit_code=0)


@pytest.mark.asyncio
async def test_analyze_data_does_not_interpolate_data_into_code(monkeypatch, sales_src):
    """B3: dataset contents must NEVER be interpolated into the code sent to
    the sandbox. Currently df.to_json() is f-string embedded into
    `pd.read_json('{df_json}')`, so a cell containing `'); <code>` becomes
    source code. The injected payload text must not appear in the code."""
    from tools.data_analysis_tool import load_dataset, analyze_data
    import core.sandbox_runtime as srt

    # Dataset cell that would break out of a single-quoted Python string.
    # Build via json.dumps so the newlines are escaped as valid JSON control
    # characters (raw newlines in a JSON string are a parse error).
    malicious_cell = "x')\nimport os\nprint('PWNED')"
    source = json.dumps([{"date": "2026-01-01", "note": malicious_cell}])

    fake = FakeRuntime()
    monkeypatch.setattr(srt, "get_runtime", lambda: fake)

    await load_dataset(source=source, name="sales_b3", session_id="rce-b3")
    result = await analyze_data(
        dataset_name="sales_b3",
        code="print(df.shape)",
        session_id="rce-b3",
    )

    # The sandbox path must have run and the injected payload must NOT appear
    # in the code we handed to the runtime (data goes via structured inputs).
    assert fake.captured_code is not None
    assert "PWNED" not in fake.captured_code, (
        f"B3 regression: dataset data was interpolated into executable source.\n"
        f"code={fake.captured_code}"
    )
    assert result.get("success") is True


# --- B2: predictive-tool parameter injection ---------------------------------


@pytest.mark.asyncio
async def test_forecast_target_column_injection_blocked(monkeypatch, sales_src):
    """B2: target_column / date_column / periods must be validated BEFORE they
    are f-string interpolated into exec'd code. A payload column name must be
    rejected without any codegen reaching the runtime."""
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import forecast
    import core.sandbox_runtime as srt

    called = []

    class _SpyRuntime:
        async def execute_python(self, code, *, policy, inputs=None, cwd=None):
            called.append(code)
            return SimpleNamespace(success=True, stdout="{}", stderr="", exit_code=0)

    monkeypatch.setattr(srt, "get_runtime", lambda: _SpyRuntime())

    await load_dataset(source=sales_src, name="sales_b2", session_id="rce-b2")

    evil = "sales'); print('PWNED'); ('"
    result = await forecast(
        dataset_name="sales_b2",
        target_column=evil,
        periods=5,
        session_id="rce-b2",
    )
    assert result["success"] is False, (
        f"B2 regression: malicious target_column reached codegen. got: {result}"
    )
    assert called == [], f"B2 regression: codegen happened: {called}"

    # Non-integer periods must also be rejected before codegen.
    result = await forecast(
        dataset_name="sales_b2",
        target_column="sales",
        periods="7; print('PWNED')",
        session_id="rce-b2",
    )
    assert result["success"] is False
    assert called == []


@pytest.mark.asyncio
async def test_run_model_feature_columns_injection_blocked(monkeypatch, sales_src):
    """B2: run_model's target_column / feature_columns / test_size must be
    validated before codegen — no injected payload may reach the runtime."""
    from tools.data_analysis_tool import load_dataset
    from tools.predictive_tools import run_model
    import core.sandbox_runtime as srt

    called = []

    class _SpyRuntime:
        async def execute_python(self, code, *, policy, inputs=None, cwd=None):
            called.append(code)
            return SimpleNamespace(success=True, stdout="{}", stderr="", exit_code=0)

    monkeypatch.setattr(srt, "get_runtime", lambda: _SpyRuntime())

    await load_dataset(source=sales_src, name="sales_b2b", session_id="rce-b2b")

    evil = "price'); print('PWNED'); ('"
    result = await run_model(
        dataset_name="sales_b2b",
        target_column=evil,
        model_type="regression",
        session_id="rce-b2b",
    )
    assert result["success"] is False
    assert called == []

    # A malicious feature_columns entry must be rejected too.
    result = await run_model(
        dataset_name="sales_b2b",
        target_column="sales",
        feature_columns=[evil],
        model_type="regression",
        session_id="rce-b2b",
    )
    assert result["success"] is False
    assert called == []

    # Non-numeric test_size must be rejected before codegen.
    result = await run_model(
        dataset_name="sales_b2b",
        target_column="sales",
        test_size="0.2; print('PWNED')",
        model_type="regression",
        session_id="rce-b2b",
    )
    assert result["success"] is False
    assert called == []


# --- B9: str(e) leak containment ---------------------------------------------


@pytest.mark.asyncio
async def test_data_tools_do_not_leak_internal_exception_text(monkeypatch):
    """B9: a forced internal error in any data tool must return a generic
    message — never raw exception text (which can contain file paths, SQL, or
    server internals). Currently every tool returns `str(e)` to the caller."""
    from tools.data_analysis_tool import (
        load_dataset,
        analyze_data,
        query_data,
        describe_data,
        list_datasets,
    )
    from core.data import dataset_manager as dm_mod

    class _Boom:
        def __getattr__(self, _name):
            raise RuntimeError("SECRET_INTERNAL_DETAILS_123")

    monkeypatch.setattr(dm_mod, "get_dataset_manager", _Boom)

    cases = [
        ("load_dataset", load_dataset, dict(source="x", name="x", session_id="b9")),
        ("analyze_data", analyze_data, dict(dataset_name="x", code="print(1)", session_id="b9")),
        ("query_data", query_data, dict(dataset_name="x", query="df", session_id="b9")),
        ("describe_data", describe_data, dict(dataset_name="x", session_id="b9")),
        ("list_datasets", list_datasets, dict(session_id="b9")),
    ]
    for label, fn, kw in cases:
        result = await fn(**kw)
        assert result.get("success") is False, (
            f"{label}: expected failure, got {result}"
        )
        err = result.get("error", "")
        assert "SECRET_INTERNAL_DETAILS_123" not in err, (
            f"B9 regression: {label} leaked raw exception text: {err!r}"
        )


def test_dataset_query_does_not_leak_exception_text(monkeypatch):
    """B9: dataset_manager.query must not surface raw exception text either
    (currently `f\"Query failed: {e}\"` echoes the internal exception)."""
    from core.data import dataset_manager as dm_mod
    from tools import data_analysis_tool as dat_mod

    mgr = dm_mod.get_dataset_manager()
    session = "b9-query"
    mgr.load(source='[{"a": 1}]', name="t", session_id=session)

    def _boom(_code):
        raise RuntimeError("SECRET_INTERNAL_DETAILS_123")

    monkeypatch.setattr(dat_mod, "_validate_data_code", _boom)

    result = mgr.query("t", "df.head()", session_id=session)
    assert result.get("success") is False
    err = result.get("error", "")
    assert "SECRET_INTERNAL_DETAILS_123" not in err, (
        f"B9 regression: dataset_manager.query leaked exception text: {err!r}"
    )
