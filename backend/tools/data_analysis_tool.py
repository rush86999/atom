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

import ast
import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _validate_data_code(code: str) -> Optional[str]:
    """Validate agent-supplied code with the sandbox AST policy.

    Reuses the same tripwire scanner the sandbox uses (blocks os/subprocess/
    socket/pty imports; eval/exec/open/compile/__import__/globals/vars/locals/
    dir calls) and additionally rejects dunder attribute access (the classic
    pyjail escape) and runtime reflection (B11). Returns an error message,
    or None if the code is allowed.
    """
    from core.sandbox_tripwire import check_python_ast

    violation = check_python_ast(code)
    if violation:
        return str(violation)
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return f"Attribute access on dunder names is not allowed: .{node.attr}"
        # B11: getattr(obj, '__cl' + 'ass__') defeats the literal-Attribute
        # dunder scan above, and __getattribute__ is reachable as a literal
        # attribute name. Data analysis never needs runtime reflection, so
        # block getattr/__getattribute__ outright — there is no legitimate use
        # for them in agent-supplied pandas/sklearn code.
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "getattr":
                return "Reflection via getattr() is not allowed"
            if isinstance(fn, ast.Attribute) and fn.attr in (
                "getattr",
                "__getattribute__",
            ):
                return f"Reflection via {fn.attr}() is not allowed"
    return None


def _validate_identifier(value: str, field: str) -> Optional[str]:
    # B13: reject non-string input cleanly instead of letting re.fullmatch
    # raise TypeError (which surfaces as a 500 to the caller).
    if not isinstance(value, str):
        return f"{field} must be a valid Python identifier (got {value!r})"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        return f"{field} must be a valid Python identifier (got {value!r})"
    return None


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
        return {"success": False, "error": "Failed to load dataset"}


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

        # Validate the submitted code FIRST — the same AST policy the sandbox
        # uses. Blocks os/subprocess/socket imports, eval/exec/open/compile/
        # __import__, and dunder/object-model escapes, on every path.
        violation = _validate_data_code(code)
        if violation:
            return {"success": False, "error": f"Code blocked by sandbox policy: {violation}"}

        # Serialize the dataset once as structured data — never as source text.
        df_json = df.to_json(orient="records")

        # Sandbox execution (production path). Data travels via the runtime's
        # `inputs` channel so dataset contents can never become executable text.
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

            full_code = (
                "import json, pandas as pd\n"
                "df = pd.read_json(__inputs__['df'])\n"
                f"{code}\n"
            )
            result = await runtime.execute_python(
                full_code, policy=policy, inputs={"df": df_json}
            )
            if result.success:
                output = result.stdout.strip()
                try:
                    parsed = json.loads(output)
                    return {"success": True, "results": parsed}
                except json.JSONDecodeError:
                    return {"success": True, "output": output[:5000]}
            if result.exit_code == -1:
                # Sandbox-level failure (no runtime / Docker down / OOM).
                logger.warning("Sandbox unavailable; refusing to exec code in-process")
                return {
                    "success": False,
                    "error": "Sandbox execution unavailable. analyze_data requires the sandbox runtime.",
                }
            return {
                "success": False,
                "error": result.stderr[:2000] if result.stderr else "Execution failed",
                "stdout": result.stdout[:1000] if result.stdout else "",
            }
        except Exception as sandbox_err:
            # Fail closed (B1): NEVER exec agent-supplied code in the server
            # process. The in-process `exec(code)` fallback was a P0 RCE — the
            # sandbox is a hard requirement for analyze_data.
            logger.warning(
                "Sandbox unavailable (%s); refusing to exec code in-process", sandbox_err
            )
            return {
                "success": False,
                "error": "Sandbox execution unavailable. analyze_data requires the sandbox runtime.",
            }

    except Exception as e:
        logger.error(f"analyze_data failed: {e}")
        return {"success": False, "error": "Failed to run data analysis"}


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
        logger.error(f"query_data failed: {e}")
        return {"success": False, "error": "Failed to run query"}


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
        logger.error(f"describe_data failed: {e}")
        return {"success": False, "error": "Failed to describe dataset"}


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
        logger.error(f"list_datasets failed: {e}")
        return {"success": False, "error": "Failed to list datasets"}


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
        # SUPERVISED: analyze_data runs arbitrary (sandboxed) Python against a
        # dataset — the highest-risk data tool. INTERN maturity must not be
        # able to invoke it autonomously (B10).
        maturity_required="SUPERVISED",
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
