"""Dataset manager for agent-driven data analysis.

Loads, caches, and queries datasets across agent turns. Uses DuckDB when
available (out-of-core, handles larger-than-RAM datasets) with a pandas
fallback for environments without DuckDB.

Datasets are session-scoped: loaded within a session, cleared on session
end. Each session gets its own dataset namespace, preventing cross-session
data leakage.

Evidence:
- DuckDB vs Pandas (codecentric): DuckDB outperforms on large analytical
  workloads, handles larger-than-RAM datasets.
- DuckDB official benchmarks: 3-25× faster, 10× larger datasets.
- ExperiencedDevs: LLMs should orchestrate code, not ingest raw files.
- DuckDB Lab: dataset referenced by name across turns.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# System directories that dataset file sources may never resolve into.
_SYSTEM_ROOTS = (
    "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/dev", "/boot",
    "/proc", "/sys", "/System", "/Library", "/private/etc", "/var/root",
)


def _validate_dataset_source(source: str) -> None:
    """Reject dataset sources that would read arbitrary server files (B5).

    Allows paths under the temp dir (tests/fixtures) or the configured data
    dir; rejects URL sources (must be downloaded first) and any path that
    resolves into system directories.
    """
    import tempfile as _tempfile

    if source.startswith(("http://", "https://")):
        raise ValueError("URL sources are not allowed; download the file first")
    p = os.path.realpath(source)
    if p.startswith(_SYSTEM_ROOTS):
        raise ValueError(f"Path outside allowed dataset directories: {source}")
    tmp = os.path.realpath(_tempfile.gettempdir())
    data_root = os.path.realpath(os.environ.get("ATOM_DATA_DIR", "./data"))
    if p != tmp and not p.startswith(tmp + os.sep):
        if p != data_root and not p.startswith(data_root + os.sep):
            raise ValueError(f"Path outside allowed dataset directories: {source}")


# DuckDB functions that read from the server filesystem or fetch remote URLs.
# Allowing any of these in agent-supplied SQL would let a query exfiltrate
# /etc/passwd, list directories, or pull attacker-controlled content (B6).
_DUCKDB_FILE_READ_FUNCTIONS = (
    "read_csv", "read_csv_auto", "read_json", "read_json_auto",
    "read_parquet", "read_blob", "glob", "read_text",
    "read_ndjson", "read_xlsx", "read_spreadsheet", "read_pandas",
    "read_json_objects", "read_json_struct_auto",
    "parquet_scan", "json_scan",
    "sqlite_scan", "postgres_scan", "mysql_scan",
    "load_extension", "ls",
)
# httpfs-style URL schemes (SSRF). Scanned on SQL-looking queries only, on the
# RAW text (the URL lives inside a string literal that the fn scan strips).
_DUCKDB_URL_SCHEME_RE = re.compile(r"\b(?:https?|s3|gcs|gs|azure|abfss|r2)://", re.IGNORECASE)


def _validate_dataset_sql(sql: str) -> Optional[str]:
    """Reject DuckDB SQL that would read server files or fetch URLs (B6).

    DuckDB exposes several functions (`read_csv`, `read_blob`, `glob`, ...)
    that bypass the dataset-source allowlist by reading directly from the
    filesystem or a URL at query time. A token-based scan is sufficient here
    because these are not valid column/table names anyone would reasonably
    call, and false positives only ever block a query (fail-closed).
    """
    if not sql:
        return None
    # Strip string literals and comments so a benign string containing
    # "read_csv" doesn't trip the scan, while still catching call sites.
    # B17: DuckDB also supports dollar-quoted strings ($$...$$ and
    # $tag$...$tag$); without stripping them, a string that merely mentions a
    # restricted function name is wrongly blocked.
    stripped = re.sub(r"'(?:[^'\\]|\\.)*'", " ", sql)
    stripped = re.sub(r"\$\$.*?\$\$", " ", stripped, flags=re.DOTALL)
    stripped = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)\$.*?\$\1\$",
                      lambda m: " " * len(m.group(0)), stripped, flags=re.DOTALL)
    stripped = re.sub(r"--[^\n]*", " ", stripped)
    stripped = re.sub(r"/\*.*?\*/", " ", stripped, flags=re.DOTALL)
    lowered = stripped.lower()
    for fn in _DUCKDB_FILE_READ_FUNCTIONS:
        if fn in lowered:
            return (
                f"SQL contains a restricted filesystem/URL function ('{fn}'); "
                f"server file reads are not allowed."
            )
    # Direct URL references (e.g. `SELECT * FROM 'https://…'` via httpfs) put
    # the URL in a string literal, so scan the RAW query. Only applied to
    # SQL-looking text so pandas expressions containing URL data aren't blocked.
    if _looks_like_sql(sql) and _DUCKDB_URL_SCHEME_RE.search(sql):
        return "SQL contains a URL reference; remote URL reads (httpfs) are not allowed."
    return None


def _looks_like_sql(text: str) -> bool:
    """Heuristic: does this query string look like SQL rather than a pandas
    expression? Used only to pick the right execution path — a wrong guess
    just falls through to the (AST-guarded) pandas eval."""
    stripped = text.lstrip().lower()
    return stripped.startswith(("select ", "with ", "insert ", "update ", "delete ", "create ", "drop ", "alter ", "pragma "))

# B18: hard cap on inline JSON source size. Inline datasets are meant for
# small, agent-constructed payloads (a few thousand rows at most). File-based
# sources (CSV/Parquet/etc.) are the path for large data. Without a cap, a
# pathological inline string is parsed unbounded → server memory exhaustion.
# 5 MiB is comfortably above any legitimate inline dataset while rejecting
# DoS-sized input. Override via env for unusual deployments.
_MAX_INLINE_JSON_BYTES = int(os.environ.get("ATOM_MAX_INLINE_JSON_BYTES", 5 * 1024 * 1024))


# Check if DuckDB is available (graceful fallback to pandas).
try:
    import duckdb as _duckdb
    _HAS_DUCKDB = True
except ImportError:
    _HAS_DUCKDB = False
    logger.info("DuckDB not available; dataset manager using pandas fallback")

try:
    import pandas as _pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False


@dataclass
class DatasetHandle:
    """A reference to a loaded dataset."""

    name: str
    source: str  # file path, URL, or "inline"
    row_count: int
    columns: List[str]
    dtypes: Dict[str, str] = field(default_factory=dict)
    backend: str = "duckdb" if _HAS_DUCKDB else "pandas"
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "row_count": self.row_count,
            "columns": self.columns,
            "dtypes": self.dtypes,
            "backend": self.backend,
        }


class DatasetManager:
    """Manages loaded datasets across agent turns within a session.

    Thread-safe (datasets may be accessed from concurrent tool calls).
    Session-scoped (datasets are isolated per session_id).
    """

    def __init__(self) -> None:
        # session_id → {dataset_name → DatasetHandle + data}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def load(
        self,
        source: str,
        name: str,
        session_id: str = "default",
        format: Optional[str] = None,
    ) -> DatasetHandle:
        """Load a dataset from a file path, URL, or inline JSON.

        Args:
            source: File path (CSV/Excel/JSON/Parquet), or inline JSON string.
            name: A human-readable name for the dataset (used to reference it later).
            session_id: Session scope for isolation.
            format: Optional format override ('csv', 'json', 'excel', 'parquet').
                    If None, inferred from file extension.

        Returns:
            DatasetHandle with metadata about the loaded dataset.

        Raises:
            FileNotFoundError if the file doesn't exist.
            ValueError if the format is unsupported or data is empty.
        """
        if not _HAS_PANDAS:
            raise RuntimeError("pandas is required for dataset loading")

        # Determine format
        if format is None:
            if source.endswith(".csv"):
                format = "csv"
            elif source.endswith(".json"):
                format = "json"
            elif source.endswith((".xlsx", ".xls")):
                format = "excel"
            elif source.endswith(".parquet"):
                format = "parquet"
            elif source.strip().startswith(("[", "{")):
                format = "inline_json"
            else:
                format = "csv"  # default

        # Reject arbitrary server file reads (B5) before touching disk.
        if format != "inline_json":
            _validate_dataset_source(source)

        # Load the data
        if format == "csv":
            df = _pd.read_csv(source)
        elif format == "json":
            df = _pd.read_json(source)
        elif format == "excel":
            df = _pd.read_excel(source)
        elif format == "parquet":
            df = _pd.read_parquet(source)
        elif format == "inline_json":
            # B18: cap size before parsing to prevent unbounded memory use.
            if len(source) > _MAX_INLINE_JSON_BYTES:
                raise ValueError(
                    f"Inline JSON too large ({len(source)} bytes; limit "
                    f"{_MAX_INLINE_JSON_BYTES}). Use a file-based source "
                    f"(CSV/Parquet) for large datasets."
                )
            data = json.loads(source)
            df = _pd.DataFrame(data if isinstance(data, list) else [data])
        else:
            raise ValueError(f"Unsupported format: {format}")

        if df.empty:
            raise ValueError(f"Dataset '{name}' loaded empty from '{source}'")

        # Build handle
        handle = DatasetHandle(
            name=name,
            source=source,
            row_count=len(df),
            columns=list(df.columns),
            dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
            session_id=session_id,
        )

        # Cache the dataframe
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {}
            self._sessions[session_id][name] = {"handle": handle, "df": df}

        logger.info(
            f"[DatasetManager] loaded '{name}': {len(df)} rows, "
            f"{len(df.columns)} cols, backend={handle.backend}"
        )
        return handle

    def get_dataframe(self, name: str, session_id: str = "default") -> Optional[Any]:
        """Get the cached pandas DataFrame for a dataset."""
        with self._lock:
            session = self._sessions.get(session_id, {})
            entry = session.get(name)
            if entry:
                return entry["df"]
        return None

    def get_handle(self, name: str, session_id: str = "default") -> Optional[DatasetHandle]:
        """Get the metadata handle for a dataset."""
        with self._lock:
            session = self._sessions.get(session_id, {})
            entry = session.get(name)
            if entry:
                return entry["handle"]
        return None

    def list_datasets(self, session_id: str = "default") -> List[Dict[str, Any]]:
        """List all loaded datasets in a session."""
        with self._lock:
            session = self._sessions.get(session_id, {})
            return [entry["handle"].to_dict() for entry in session.values()]

    def query(
        self,
        name: str,
        sql_or_code: str,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """Run a query against a cached dataset.

        Args:
            name: Dataset name (must be loaded).
            sql_or_code: SQL query (if DuckDB available) or Python code
                referencing the dataset as a pandas DataFrame variable ``df``.
            session_id: Session scope.

        Returns:
            Dict with 'success', 'data' (list of row dicts), 'row_count'.
        """
        df = self.get_dataframe(name, session_id)
        if df is None:
            return {"success": False, "error": f"Dataset '{name}' not loaded"}

        # B6: block DuckDB filesystem/URL functions (read_csv, read_blob, glob,
        # ...) before the SQL ever reaches DuckDB. Agent-supplied queries must
        # never read arbitrary server files or fetch remote URLs.
        sql_violation = _validate_dataset_sql(sql_or_code)
        if sql_violation:
            return {"success": False, "error": f"Query blocked by sandbox policy: {sql_violation}"}

        # If it doesn't look like SQL, skip straight to the pandas path rather
        # than letting DuckDB raise a confusing parser error.
        looks_like_sql = _looks_like_sql(sql_or_code)

        try:
            if _HAS_DUCKDB and looks_like_sql:
                # Use DuckDB for SQL queries against the DataFrame
                result_df = _duckdb.sql(sql_or_code).df()
            else:
                raise ImportError("Not a SQL query — use pandas path")

            # Convert to list of dicts
            records = result_df.to_dict(orient="records")
            return {
                "success": True,
                "data": records,
                "row_count": len(records),
                "columns": list(result_df.columns),
            }
        except Exception:
            # Fallback: evaluate as a pandas expression with df in scope.
            # Guarded by the same AST policy used for analyze_data (B4): blocks
            # os/subprocess/open/eval/exec and dunder/object-model escapes.
            try:
                from tools.data_analysis_tool import _validate_data_code

                violation = _validate_data_code(sql_or_code)
                if violation:
                    return {
                        "success": False,
                        "error": f"Query blocked by sandbox policy: {violation}",
                    }
                import pandas as pd
                local_vars = {"df": df, "pd": pd}
                result = eval(sql_or_code, {"__builtins__": {}}, local_vars)
                if isinstance(result, pd.DataFrame):
                    records = result.to_dict(orient="records")
                    return {
                        "success": True,
                        "data": records,
                        "row_count": len(records),
                        "columns": list(result.columns),
                    }
                elif isinstance(result, (dict, list)):
                    return {"success": True, "data": result, "row_count": len(result) if isinstance(result, list) else 1}
                else:
                    return {"success": True, "data": str(result), "row_count": 1}
            except Exception as e:
                logger.error(f"Dataset query failed: {e}")
                return {"success": False, "error": "Query failed"}

    def head(self, name: str, n: int = 5, session_id: str = "default") -> Dict[str, Any]:
        """Get the first N rows of a dataset."""
        df = self.get_dataframe(name, session_id)
        if df is None:
            return {"success": False, "error": f"Dataset '{name}' not loaded"}
        records = df.head(n).to_dict(orient="records")
        return {"success": True, "data": records, "row_count": len(records)}

    def describe(self, name: str, session_id: str = "default") -> Dict[str, Any]:
        """Get summary statistics for a dataset."""
        df = self.get_dataframe(name, session_id)
        if df is None:
            return {"success": False, "error": f"Dataset '{name}' not loaded"}
        stats = df.describe(include="all").to_dict()
        # Clean up NaN values for JSON serialization
        cleaned = {}
        for col, values in stats.items():
            cleaned[col] = {
                k: (None if (isinstance(v, float) and v != v) else v)
                for k, v in values.items()
            }
        return {"success": True, "statistics": cleaned}

    def clear_session(self, session_id: str) -> int:
        """Clear all datasets for a session. Returns count cleared."""
        with self._lock:
            session = self._sessions.pop(session_id, {})
            return len(session)

    def clear_all(self) -> int:
        """Clear all datasets across all sessions."""
        with self._lock:
            count = sum(len(s) for s in self._sessions.values())
            self._sessions.clear()
            return count


# Module-level singleton.
_default_manager: Optional[DatasetManager] = None


def get_dataset_manager() -> DatasetManager:
    """Return the process-wide default DatasetManager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = DatasetManager()
    return _default_manager
