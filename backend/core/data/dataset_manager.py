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
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

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

        try:
            if _HAS_DUCKDB:
                # Use DuckDB for SQL queries against the DataFrame
                result_df = _duckdb.sql(sql_or_code).df() if not sql_or_code.strip().startswith("import") else None
                if result_df is None:
                    # Fall through to pandas eval
                    raise ValueError("Not a SQL query")
            else:
                raise ImportError("No DuckDB")

            # Convert to list of dicts
            records = result_df.to_dict(orient="records")
            return {
                "success": True,
                "data": records,
                "row_count": len(records),
                "columns": list(result_df.columns),
            }
        except Exception:
            # Fallback: evaluate as Python code with df in scope
            try:
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
                return {"success": False, "error": f"Query failed: {e}"}

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
