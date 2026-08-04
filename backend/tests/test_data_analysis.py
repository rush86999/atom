"""Tests for the dataset manager + data analysis tools.

Covers: dataset loading (CSV/JSON/inline), caching, session isolation,
query execution (pandas fallback), summary statistics, list/clear,
and the agent tool dispatch (load_dataset, analyze_data, query_data,
describe_data, list_datasets).
"""
import asyncio
import contextlib
import io
import json
import os
import tempfile
from types import SimpleNamespace

import pytest

from core.data.dataset_manager import DatasetManager, DatasetHandle, get_dataset_manager


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
def manager() -> DatasetManager:
    return DatasetManager()


@pytest.fixture
def csv_file():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("product,price,quantity\n")
        f.write("Widget A,29.99,150\n")
        f.write("Widget B,49.99,80\n")
        f.write("Widget C,9.99,500\n")
        path = f.name
    yield path
    os.unlink(path)


# --- Dataset loading -------------------------------------------------------


def test_load_csv(manager, csv_file):
    handle = manager.load(csv_file, "inventory", session_id="s1")
    assert handle.name == "inventory"
    assert handle.row_count == 3
    assert "product" in handle.columns
    assert "price" in handle.columns
    assert "quantity" in handle.columns


def test_load_inline_json(manager):
    handle = manager.load(
        source='[{"name": "Alice", "score": 95}, {"name": "Bob", "score": 87}]',
        name="scores",
        session_id="s1",
    )
    assert handle.row_count == 2
    assert "name" in handle.columns
    assert "score" in handle.columns


def test_load_empty_raises(manager):
    with pytest.raises(ValueError):
        manager.load(
            source='[]',
            name="empty",
            session_id="s1",
        )


def test_load_missing_file_raises(manager):
    with pytest.raises(Exception):
        manager.load("/nonexistent/file.csv", "missing", session_id="s1")


# --- Caching + retrieval ---------------------------------------------------


def test_get_dataframe(manager, csv_file):
    manager.load(csv_file, "inventory", session_id="s1")
    df = manager.get_dataframe("inventory", session_id="s1")
    assert df is not None
    assert len(df) == 3


def test_get_dataframe_not_loaded(manager):
    assert manager.get_dataframe("nonexistent", session_id="s1") is None


def test_get_handle(manager, csv_file):
    manager.load(csv_file, "inventory", session_id="s1")
    handle = manager.get_handle("inventory", session_id="s1")
    assert handle is not None
    assert handle.name == "inventory"


# --- Session isolation -----------------------------------------------------


def test_session_isolation(manager, csv_file):
    manager.load(csv_file, "inventory", session_id="s1")
    # s2 should NOT see s1's datasets
    assert manager.get_dataframe("inventory", session_id="s2") is None
    assert len(manager.list_datasets(session_id="s2")) == 0


def test_same_name_different_sessions(manager, csv_file):
    """Same dataset name in different sessions should be isolated."""
    manager.load(csv_file, "data", session_id="s1")
    manager.load(
        source='[{"x": 1}]',
        name="data",
        session_id="s2",
    )
    df1 = manager.get_dataframe("data", session_id="s1")
    df2 = manager.get_dataframe("data", session_id="s2")
    assert len(df1) == 3  # CSV with 3 rows
    assert len(df2) == 1  # JSON with 1 row


# --- Query -----------------------------------------------------------------


def test_query_pandas_expr(manager, csv_file):
    manager.load(csv_file, "inventory", session_id="s1")
    result = manager.query(
        "inventory",
        "df[df['price'] > 20].to_dict(orient='records')",
        session_id="s1",
    )
    assert result["success"]
    assert result["row_count"] == 2  # Widget A (29.99) + Widget B (49.99)


def test_query_not_loaded(manager):
    result = manager.query("nonexistent", "SELECT * FROM df", session_id="s1")
    assert result["success"] is False


# --- Head + Describe -------------------------------------------------------


def test_head(manager, csv_file):
    manager.load(csv_file, "inventory", session_id="s1")
    result = manager.head("inventory", n=2, session_id="s1")
    assert result["success"]
    assert result["row_count"] == 2


def test_describe(manager, csv_file):
    manager.load(csv_file, "inventory", session_id="s1")
    result = manager.describe("inventory", session_id="s1")
    assert result["success"]
    assert "price" in result["statistics"]
    assert "quantity" in result["statistics"]


def test_describe_not_loaded(manager):
    result = manager.describe("nonexistent", session_id="s1")
    assert result["success"] is False


# --- List + Clear ----------------------------------------------------------


def test_list_datasets(manager, csv_file):
    manager.load(csv_file, "inventory", session_id="s1")
    datasets = manager.list_datasets(session_id="s1")
    assert len(datasets) == 1
    assert datasets[0]["name"] == "inventory"
    assert datasets[0]["row_count"] == 3


def test_clear_session(manager, csv_file):
    manager.load(csv_file, "inventory", session_id="s1")
    cleared = manager.clear_session("s1")
    assert cleared == 1
    assert len(manager.list_datasets(session_id="s1")) == 0


def test_clear_all(manager, csv_file):
    manager.load(csv_file, "d1", session_id="s1")
    manager.load(csv_file, "d2", session_id="s2")
    cleared = manager.clear_all()
    assert cleared == 2
    assert len(manager.list_datasets(session_id="s1")) == 0
    assert len(manager.list_datasets(session_id="s2")) == 0


def test_singleton():
    a = get_dataset_manager()
    b = get_dataset_manager()
    assert a is b


# --- Agent tool dispatch ---------------------------------------------------


@pytest.mark.asyncio
async def test_tool_load_dataset(csv_file):
    from tools.data_analysis_tool import load_dataset
    result = await load_dataset(source=csv_file, name="test_data", session_id="tool-test")
    assert result["success"]
    assert result["dataset"]["row_count"] == 3


@pytest.mark.asyncio
async def test_tool_load_dataset_inline():
    from tools.data_analysis_tool import load_dataset
    result = await load_dataset(
        source='[{"a": 1}, {"a": 2}]',
        name="inline_test",
        session_id="tool-test",
    )
    assert result["success"]
    assert result["dataset"]["row_count"] == 2


@pytest.mark.asyncio
async def test_tool_query_data(csv_file):
    from tools.data_analysis_tool import load_dataset, query_data
    await load_dataset(source=csv_file, name="inv", session_id="tool-test")
    result = await query_data(
        dataset_name="inv",
        query="df['price'].mean()",
        session_id="tool-test",
    )
    assert result["success"]


@pytest.mark.asyncio
async def test_tool_describe_data(csv_file):
    from tools.data_analysis_tool import load_dataset, describe_data
    await load_dataset(source=csv_file, name="inv", session_id="tool-test")
    result = await describe_data(dataset_name="inv", session_id="tool-test")
    assert result["success"]
    assert "price" in result["statistics"]


@pytest.mark.asyncio
async def test_tool_list_datasets(csv_file):
    from tools.data_analysis_tool import load_dataset, list_datasets
    # Use a fresh session to avoid pollution from prior tests
    sid = "list-test-fresh"
    await load_dataset(source=csv_file, name="inv", session_id=sid)
    result = await list_datasets(session_id=sid)
    assert result["success"]
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_tool_analyze_data_not_loaded():
    from tools.data_analysis_tool import analyze_data
    result = await analyze_data(
        dataset_name="nonexistent",
        code="print(df.head())",
        session_id="tool-test",
    )
    assert result["success"] is False
    assert "not loaded" in result["error"]


@pytest.mark.asyncio
async def test_tool_analyze_data_basic(csv_file):
    """analyze_data via the (test-mocked) sandbox runtime."""
    from tools.data_analysis_tool import load_dataset, analyze_data
    await load_dataset(source=csv_file, name="inv", session_id="tool-test")
    result = await analyze_data(
        dataset_name="inv",
        code="import json; print(json.dumps({'rows': len(df), 'cols': list(df.columns)}))",
        session_id="tool-test",
    )
    assert result["success"]
    # Result should contain the analysis output
    assert "rows" in str(result.get("results", result.get("output", "")))


@pytest.mark.asyncio
async def test_tool_load_failure():
    from tools.data_analysis_tool import load_dataset
    result = await load_dataset(
        source="/nonexistent/file.csv",
        name="fail",
        session_id="tool-test",
    )
    assert result["success"] is False
