"""Dataset catalog tools for agents (autonomous-hire / function-calling paths).

The CHAT surface does not need these: there, the harness itself consults the
dataset catalog inside the read leg (universal_integration_service.
_read_storage_file's dataset fast path) and the reply model is under a strict
no-tool-calling contract. These tools exist for agent runtimes that DO issue
tool calls (ToolRegistry-driven hires, MCP exposure via core/mcp_service
export_all) so they can discover and load SQL-queryable sheet datasets and
then query them with the existing query_data / describe_data / analyze_data
data tools — no new query mechanism.

Flow: find_datasets("price list") → load_registered_dataset("zoho_workdrive_
consolidated_price_list__linmac") → query_data(dataset_name, 'SELECT * FROM
df WHERE "Item Number" ILIKE ''%WG350DSAV%''').
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def find_datasets(
    file_hint: str = "",
    **kwargs,
) -> Dict[str, Any]:
    """Find SQL-queryable datasets registered from ingested files.

    Args:
        file_hint: File/sheet name tokens, e.g. "price list", "invoices 2026".
                  Empty hint lists the most recent datasets in scope.
    """
    try:
        from core.sheet_dataset_service import find_entries_sync

        entries = await __import__("asyncio").to_thread(
            find_entries_sync,
            file_hint or "",
            kwargs.get("user_id"),
            kwargs.get("workspace_id"),
            20,
        )
        return {
            "success": True,
            "count": len(entries),
            "datasets": [
                {
                    "dataset_name": e["dataset_name"],
                    "sheet": e["entity_name"],
                    "file_name": e.get("file_name"),
                    "source": e.get("source"),
                    "rows": e.get("row_count"),
                    "columns": e.get("columns"),
                    "source_modified_at": e.get("source_modified_at"),
                }
                for e in entries
            ],
            "how_to_use": (
                "Pick a dataset_name, call load_registered_dataset(dataset_name=...), "
                "then query_data(dataset_name=<same name>, query='SELECT * FROM df "
                "WHERE ...'). The table name in SQL is df; the __sheet_row column "
                "holds the original spreadsheet row number."
            ),
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"find_datasets failed: {e}")
        return {"success": False, "error": "Failed to search dataset catalog"}


async def load_registered_dataset(
    dataset_name: str,
    **kwargs,
) -> Dict[str, Any]:
    """Load a catalog dataset (Parquet) into this session for SQL querying.

    After this call, query_data / describe_data / analyze_data work on it by
    the same dataset_name (SQL references the data as `df`).

    Args:
        dataset_name: Exact name from find_datasets.
    """
    session_id = kwargs.get("session_id", "default")
    try:
        from core.data.dataset_manager import get_dataset_manager, _validate_dataset_source
        from core.sheet_dataset_service import (
            get_entry_by_name_sync,
            load_formulas_for_parquet,
            sheet_datasets_enabled,
        )

        if not sheet_datasets_enabled():
            return {"success": False, "error": "Dataset catalog is disabled"}
        if not isinstance(dataset_name, str) or not dataset_name.strip():
            return {"success": False, "error": "dataset_name is required"}

        entry = await __import__("asyncio").to_thread(get_entry_by_name_sync, dataset_name.strip())
        if not entry:
            return {
                "success": False,
                "error": f"No active dataset named '{dataset_name}'. Call find_datasets first.",
            }

        path = entry.get("parquet_path") or ""
        # Defense in depth: only catalog-registered paths under the data root.
        _validate_dataset_source(path)

        formulas = await __import__("asyncio").to_thread(load_formulas_for_parquet, path)

        handle = get_dataset_manager().load(
            source=path,
            name=entry["dataset_name"],
            session_id=session_id,
            format="parquet",
        )
        return {
            "success": True,
            "dataset": handle.to_dict(),
            # Cell->formula map from the ORIGINAL ingested workbook (Parquet
            # itself carries only computed values).
            "formulas": formulas,
            "freshness": {
                "source_file": entry.get("file_name"),
                "content_hash": entry.get("content_hash"),
                "source_modified_at": entry.get("source_modified_at"),
                "ingested_at": entry.get("ingested_at"),
            },
            "message": (
                f"Loaded '{entry['dataset_name']}' ({handle.row_count} rows, sheet "
                f"'{entry['entity_name']}' of '{entry.get('file_name')}'). Query it with "
                f"query_data(dataset_name='{entry['dataset_name']}', query='SELECT * FROM df ...')."
                + (
                    f" The formulas field maps original spreadsheet cells to their"
                    f" formulas ({len(formulas)} formula cells)."
                    if formulas
                    else ""
                )
            ),
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"load_registered_dataset failed: {e}")
        return {"success": False, "error": "Failed to load dataset"}


def register_dataset_tools(tool_registry=None):
    """Register dataset-catalog tools with the ToolRegistry."""
    from tools.registry import get_tool_registry

    if tool_registry is None:
        tool_registry = get_tool_registry()

    tool_registry.register(
        name="find_datasets",
        function=find_datasets,
        version="1.0.0",
        description=(
            "Search the dataset catalog for SQL-queryable copies of ingested "
            "spreadsheet files (Excel/CSV). Use when a question needs an exact "
            "value, row, price, or figure from a named tabular file — querying "
            "the dataset beats reading file text. Returns dataset names, sheets, "
            "row counts, and columns."
        ),
        category="data",
        complexity=1,
        maturity_required="INTERN",
        parameters={
            "file_hint": "string (optional) — file/sheet name tokens, e.g. 'price list'",
        },
        tags=["data", "dataset", "catalog", "excel", "spreadsheet", "sql"],
    )

    tool_registry.register(
        name="load_registered_dataset",
        function=load_registered_dataset,
        version="1.0.0",
        description=(
            "Load a catalog dataset into this session so query_data / describe_data "
            "can run SQL against it. Pair with find_datasets; SQL references the "
            "data as table `df`."
        ),
        category="data",
        complexity=2,
        maturity_required="INTERN",
        parameters={
            "dataset_name": "string (required) — exact name from find_datasets",
        },
        tags=["data", "dataset", "load", "parquet", "sql"],
    )

    logger.info("Dataset catalog tools registered with ToolRegistry")
