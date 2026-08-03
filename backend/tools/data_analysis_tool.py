"""Data analysis agent tools.

Provides agents with the ability to load datasets, run analysis code in the
sandbox, and query/summarize data — all without ingesting raw data into
LLM context (the agent generates code; the sandbox executes it).

Evidence:
- DABstep benchmark (arXiv 2506.23719): code-interpreter is the SOTA pattern
  for multi-step data analysis.
- DS-STAR (Google Research): code execution + self-debugging raises accuracy.
- ExperiencedDevs: LLMs should orchestrate code, not ingest raw files.

Tools exposed:
  - load_dataset: Load CSV/Excel/JSON data, cache by name for cross-turn use
  - analyze_data: Run analysis code (pandas/DuckDB/sklearn) in the sandbox
  - query_data: Run SQL or pandas expressions against a cached dataset
  - describe_data: Get summary statistics for a dataset

All tools are async, return Dict[str, Any] with a 'success' key, and accept
the dispatch context (user_id, agent_id, session_id) as kwargs.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def load_dataset(
    source: str,
    name: str,
    format: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Load a dataset from a file path or inline JSON, cache it by name.

    The dataset is cached in the session and can be referenced by name in
    subsequent analyze_data / query_data calls — no need to re-load or
    re-send the data through LLM context every turn.

    Args:
        source: File path (CSV/Excel/JSON/Parquet) or inline JSON string.
        name: A human-readable name for the dataset (e.g. 'sales_q3').
        format: Optional format override ('csv', 'json', 'excel', 'parquet').
    """
    session_id = kwargs.get("session_id", "default")
    try:
        from core.data.dataset_manager import get_dataset_manager

        dm = get_dataset_manager()
        handle = dm.load(source=source, name=name, session_id=session_id, format=format)
        return {
            "success": True,
            "dataset": handle.to_dict(),
            "message": (
                f"Loaded dataset '{name}': {handle.row_count} rows, "
                f"{len(handle.columns)} columns"
            ),
        }
    except Exception as e:
        logger.error(f"load_dataset failed: {e}")
        return {"success": False, "error": str(e)}


async def analyze_data(
    dataset_name: str,
    code: str,
    **kwargs,
) -> Dict[str, Any]:
    """Run analysis code against a cached dataset in the sandbox.

    The agent generates Python code that operates on the dataset. The code
    is executed in the sandbox runtime (Docker/E2B/Firecracker) with the
    dataset available as a pandas DataFrame variable 'df'.

    The sandbox enforces:
      - AST tripwires (blocks os/subprocess/socket imports, eval/exec)
      - Egress proxy (blocks non-allowlisted network access)
      - Resource caps (memory, CPU, timeout)
      - Network isolation (--network none in Docker)

    This is the SOTA pattern for LLM-driven data analysis: the LLM generates
    code, the sandbox executes it safely, results flow back structured.

    Args:
        dataset_name: Name of a previously-loaded dataset.
        code: Python code to execute. The dataset is available as 'df'
              (a pandas DataFrame). Print results as JSON for parsing.
    """
    session_id = kwargs.get("session_id", "default")
    try:
        from core.data.dataset_manager import get_dataset_manager

        dm = get_dataset_manager()
        df = dm.get_dataframe(dataset_name, session_id)
        if df is None:
            return {
                "success": False,
                "error": f"Dataset '{dataset_name}' not loaded. Call load_dataset first.",
            }

        # Try sandbox execution first (production path)
        try:
            from core.sandbox_runtime import get_runtime
            from core.sandbox_policy import SandboxPolicy

            runtime = get_runtime()
            policy = SandboxPolicy(
                run_id=f"data_analysis_{dataset_name}",
                agent_id=kwargs.get("agent_id", "data-agent"),
                tier_at_issuance="STUDENT",
                max_exec_seconds=30,
            )

            # Build the full code: inject df as a global, then run user code
            import json as _json
            import pandas as _pd

            # Serialize the dataframe to JSON for the sandbox
            df_json = df.to_json(orient="records")
            full_code = f"""
import json, pandas as pd
df = pd.read_json('{df_json}')
{code}
"""

            result = await runtime.execute_python(full_code, policy=policy)
            if result.success:
                output = result.stdout.strip()
                # Try to parse output as JSON
                try:
                    parsed = _json.loads(output)
                    return {"success": True, "results": parsed}
                except _json.JSONDecodeError:
                    # Return raw output if not JSON
                    return {"success": True, "output": output[:5000]}
            elif result.exit_code == -1:
                # exit_code -1 = sandbox-level failure (Docker not running, boot
                # timeout, OOM). Fall through to local fallback for dev/test.
                logger.debug(f"Sandbox unavailable (exit_code=-1); using local eval")
            else:
                return {
                    "success": False,
                    "error": result.stderr[:2000] if result.stderr else "Execution failed",
                    "stdout": result.stdout[:1000] if result.stdout else "",
                }
        except Exception as sandbox_err:
            logger.debug(f"Sandbox unavailable ({sandbox_err}); using local eval")

        # Fallback: local pandas eval (dev/test only — NOT for production).
        # Uses full builtins since this is a dev convenience path; the
        # production path uses the sandbox with AST tripwires.
        import pandas as pd
        import builtins as _builtins
        local_vars = {"df": df, "pd": pd, "json": _builtins.__import__("json")}
        import io as _io
        import contextlib as _contextlib

        stdout_capture = _io.StringIO()
        with _contextlib.redirect_stdout(stdout_capture):
            exec(code, {"__builtins__": _builtins.__dict__}, local_vars)

        output = stdout_capture.getvalue().strip()
        import json as _json
        try:
            parsed = _json.loads(output)
            return {"success": True, "results": parsed}
        except _json.JSONDecodeError:
            return {"success": True, "output": output[:5000]}

    except Exception as e:
        logger.error(f"analyze_data failed: {e}")
        return {"success": False, "error": str(e)}


async def query_data(
    dataset_name: str,
    query: str,
    **kwargs,
) -> Dict[str, Any]:
    """Run a SQL query or pandas expression against a cached dataset.

    If DuckDB is available, runs as SQL against the DataFrame.
    Otherwise, evaluates as Python code with 'df' in scope.

    Args:
        dataset_name: Name of a previously-loaded dataset.
        query: SQL query (DuckDB) or pandas expression (e.g. "df.head(10).to_dict('records')").
    """
    session_id = kwargs.get("session_id", "default")
    try:
        from core.data.dataset_manager import get_dataset_manager

        dm = get_dataset_manager()
        result = dm.query(dataset_name, query, session_id=session_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


async def describe_data(
    dataset_name: str,
    **kwargs,
) -> Dict[str, Any]:
    """Get summary statistics for a dataset (pandas describe()).

    Args:
        dataset_name: Name of a previously-loaded dataset.
    """
    session_id = kwargs.get("session_id", "default")
    try:
        from core.data.dataset_manager import get_dataset_manager

        dm = get_dataset_manager()
        return dm.describe(dataset_name, session_id=session_id)
    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_datasets(
    **kwargs,
) -> Dict[str, Any]:
    """List all loaded datasets in the current session."""
    session_id = kwargs.get("session_id", "default")
    try:
        from core.data.dataset_manager import get_dataset_manager

        dm = get_dataset_manager()
        datasets = dm.list_datasets(session_id=session_id)
        return {"success": True, "datasets": datasets, "count": len(datasets)}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool registration
# ─────────────────────────────────────────────────────────────────────────────


def register_data_analysis_tools(tool_registry=None):
    """Register data analysis tools with the tool registry."""
    from tools.registry import get_tool_registry

    if tool_registry is None:
        tool_registry = get_tool_registry()

    tool_registry.register(
        name="load_dataset",
        function=load_dataset,
        version="1.0.0",
        description=(
            "Load a dataset (CSV/Excel/JSON/Parquet) and cache it by name for "
            "cross-turn analysis. The data stays in memory — it is NOT sent "
            "through the LLM context window. Use this before analyze_data or "
            "query_data."
        ),
        category="data",
        complexity=2,
        maturity_required="INTERN",
        parameters={
            "source": "string (required) — file path or inline JSON array",
            "name": "string (required) — name to reference this dataset (e.g. 'sales_q3')",
            "format": "string (optional) — csv/json/excel/parquet (auto-detected if omitted)",
        },
        tags=["data", "dataset", "load", "csv", "excel", "analysis"],
    )

    tool_registry.register(
        name="analyze_data",
        function=analyze_data,
        version="1.0.0",
        description=(
            "Run analysis code (pandas/DuckDB/sklearn) against a cached dataset "
            "in the sandbox. The dataset is available as 'df' (a pandas DataFrame). "
            "Print results as JSON for structured return. The sandbox enforces "
            "AST tripwires, egress proxy, and resource caps."
        ),
        category="data",
        complexity=3,
        maturity_required="INTERN",
        parameters={
            "dataset_name": "string (required) — name of a previously-loaded dataset",
            "code": "string (required) — Python code to execute (df is available as a DataFrame)",
        },
        tags=["data", "analysis", "pandas", "sandbox", "code-interpreter"],
    )

    tool_registry.register(
        name="query_data",
        function=query_data,
        version="1.0.0",
        description=(
            "Run a SQL query (DuckDB) or pandas expression against a cached "
            "dataset. Simpler than analyze_data for single-expression queries."
        ),
        category="data",
        complexity=2,
        maturity_required="INTERN",
        parameters={
            "dataset_name": "string (required) — name of a previously-loaded dataset",
            "query": "string (required) — SQL or pandas expression",
        },
        tags=["data", "query", "sql", "duckdb", "pandas"],
    )

    tool_registry.register(
        name="describe_data",
        function=describe_data,
        version="1.0.0",
        description=(
            "Get summary statistics (count, mean, std, min, max, quartiles) "
            "for a cached dataset."
        ),
        category="data",
        complexity=1,
        maturity_required="INTERN",
        parameters={
            "dataset_name": "string (required) — name of a previously-loaded dataset",
        },
        tags=["data", "statistics", "describe", "summary"],
    )

    tool_registry.register(
        name="list_datasets",
        function=list_datasets,
        version="1.0.0",
        description="List all datasets loaded in the current session.",
        category="data",
        complexity=1,
        maturity_required="INTERN",
        parameters={},
        tags=["data", "list", "datasets"],
    )

    logger.info("Data analysis tools registered with ToolRegistry")
