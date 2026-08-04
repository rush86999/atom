"""RED tests — Round 70 / Plan 315-01: tool registry wiring & metadata.

Expected to FAIL against the current code; go green in Plan 315-07.

Findings under test (B10):
  - `analyze_data` is auto-discovered at INTERN/complexity 2 instead of the
    intended SUPERVISED/complexity 3 (`tools/registry.py:292-303` inference
    downgrades it; `data_analysis_tool.py:268-286` explicit metadata is
    never used in production).
  - `forecast` / `run_model` (`tools/predictive_tools.py`) are never
    registered — the file doesn't match the `*_tool.py` auto-discovery glob
    and `register_predictive_tools()` is only called from tests.
"""
import pytest


@pytest.fixture(autouse=True)
def fresh_registry():
    """Reset the registry singleton so tests always see a fresh auto-discovery
    (the global singleton retains state across tests → order-dependent)."""
    import tools.registry as reg_mod

    reg_mod._global_registry = None
    yield


def test_analyze_data_registry_metadata():
    """B10: production registry must expose analyze_data at SUPERVISED/3,
    matching its explicit registration and its arbitrary-code-exec risk."""
    from tools.registry import get_tool_registry

    r = get_tool_registry()
    t = r._tools.get("analyze_data")
    assert t is not None, "analyze_data must be registered"
    assert t.maturity_required == "SUPERVISED", (
        f"B10 regression: analyze_data effective maturity is "
        f"{t.maturity_required!r}, expected 'SUPERVISED'."
    )
    assert t.complexity == 3, (
        f"B10 regression: analyze_data effective complexity is "
        f"{t.complexity!r}, expected 3."
    )


def test_forecast_and_run_model_registered():
    """B10: forecast / run_model must be registered in production (they are
    currently dead code — absent from the registry)."""
    from tools.registry import get_tool_registry

    r = get_tool_registry()
    for name in ("forecast", "run_model"):
        assert name in r._tools, (
            f"B10 regression: {name} is not registered in the production "
            f"tool registry (predictive_tools.py is never wired)."
        )


def test_predictive_tools_not_reachable_at_intern():
    """B13: the SUPERVISED gate must not be bypassable — forecast / run_model
    and their analyze_data primitive must all be absent from INTERN maturity.
    A SUPERVISED-only capability must never decompose into an INTERN primitive."""
    from tools.registry import get_tool_registry

    r = get_tool_registry()
    intern_tools = set(r.list_by_maturity("INTERN"))
    for name in ("forecast", "run_model", "analyze_data"):
        assert name not in intern_tools, (
            f"B13 regression: {name} is reachable at INTERN maturity — "
            f"the SUPERVISED gate decomposes into a lower-tier primitive."
        )


def test_predictive_tools_require_supervised():
    """B13: forecast / run_model / analyze_data are SUPERVISED-gated in the
    production registry (not a governance notice string — an enforced tier)."""
    from tools.registry import get_tool_registry

    r = get_tool_registry()
    for name in ("forecast", "run_model", "analyze_data"):
        t = r._tools.get(name)
        assert t is not None, f"{name} must be registered"
        assert t.maturity_required == "SUPERVISED", (
            f"B13 regression: {name} is {t.maturity_required!r}, expected "
            f"'SUPERVISED'."
        )


def test_startup_tool_inventory_data_and_predictive():
    """B10: the production registry (as initialized at startup / first access
    via get_tool_registry) exposes the full data + predictive tool set with
    the *explicit* metadata — no dead tools (forecast/run_model), no silent
    maturity downgrades from auto-discovery inference (analyze_data INTERN/2
    must not win over its explicit SUPERVISED/3)."""
    from tools.registry import get_tool_registry

    r = get_tool_registry()

    expected = {
        "load_dataset": ("data", 2, "INTERN"),
        "analyze_data": ("data", 3, "SUPERVISED"),
        "query_data": ("data", 2, "INTERN"),
        "describe_data": ("data", 1, "INTERN"),
        "list_datasets": ("data", 1, "INTERN"),
        "forecast": ("data", 4, "SUPERVISED"),
        "run_model": ("data", 4, "SUPERVISED"),
    }
    for name, (category, complexity, maturity) in expected.items():
        t = r._tools.get(name)
        assert t is not None, (
            f"B10 regression: {name} missing from startup inventory — the "
            f"data/predictive tools are not wired into production."
        )
        assert t.category == category, (
            f"B10 regression: {name} category is {t.category!r}, expected "
            f"{category!r}."
        )
        assert t.complexity == complexity, (
            f"B10 regression: {name} complexity is {t.complexity!r}, expected "
            f"{complexity!r}."
        )
        assert t.maturity_required == maturity, (
            f"B10 regression: {name} maturity is {t.maturity_required!r}, "
            f"expected {maturity!r}."
        )
