"""Datasets VFS provider — the dataset catalog as an agent-native directory.

Exposes every SQL-queryable dataset (ingested spreadsheets AND synced app
records) under ``datasets/``:

    datasets/
      zoho_workdrive_consolidated_price_list_2019/     ← one source file
        machine_pricing/content.lines                  ← R#-citable rows
      app_zoho_books_invoices/content.lines            ← app-record dataset

Agents navigate with the SAME ``documents.ls/cat/grep`` actions they already
know (path prefix resolves the provider). Line format is the repo-wide
``R# | col=value`` convention, so a grep citation
``datasets/<group>/<sheet>/content.lines:L2`` IS the answer with provenance —
the user never has to say where a value lives.

Read-only over the catalog (core/sheet_dataset_service); query_data remains
the analytic surface, the VFS is the navigable one.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from core.vfs_base import VFSCitation, VFSNode, VFSProvider, VFSResource

logger = logging.getLogger(__name__)

#: Rows rendered per sheet before truncation (bounded cat/grep cost).
_MAX_LINES_PER_SHEET = 400

_LEAF = "content.lines"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", (text or "").lower()).strip("_")


def _group_of(entry: Dict[str, Any]) -> str:
    """File datasets share a group per source file (dataset_name is
    '{source}_{stem}__{sheet}'); app-record datasets are their own group."""
    name = entry.get("dataset_name") or ""
    return name.rsplit("__", 1)[0] if "__" in name else name


class DatasetsVFSProvider(VFSProvider):
    """VFS view over the dataset catalog (file + app-record datasets)."""

    prefix = "datasets"

    def __init__(self, workspace_id: Optional[str] = None):
        self._workspace_id = workspace_id

    def _entries(self) -> List[Dict[str, Any]]:
        from core.sheet_dataset_service import find_entries_sync

        return find_entries_sync("", None, self._workspace_id, 500)

    @staticmethod
    def _entities_of(group: str, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [e for e in entries if _group_of(e) == group]

    @staticmethod
    def _entity_slug(entry: Dict[str, Any]) -> str:
        return _slug(entry.get("entity_name") or entry.get("dataset_name") or "dataset")

    async def ls(self, path: str, ctx: Optional[Dict[str, Any]] = None) -> List[VFSNode]:
        entries = self._entries()
        parts = [p for p in (path or "").lstrip("/").rstrip("/").split("/") if p and p != "datasets"]

        if not parts:
            groups: Dict[str, Dict[str, Any]] = {}
            for e in entries:
                groups.setdefault(_group_of(e), e)
            return [
                VFSNode(
                    name=group,
                    type="dir",
                    path=f"datasets/{group}",
                    modified=(first.get("source_modified_at") or first.get("ingested_at")),
                )
                for group, first in sorted(groups.items())
            ]
        group = parts[0]
        group_entries = self._entities_of(group, entries)
        if not group_entries:
            return []
        if len(parts) == 1:
            return [
                VFSNode(
                    name=self._entity_slug(e),
                    type="file",
                    path=f"datasets/{group}/{self._entity_slug(e)}",
                    size=e.get("row_count"),
                    modified=e.get("source_modified_at") or e.get("ingested_at"),
                )
                for e in group_entries
            ]
        # leaf: datasets/<group>/<entity>
        return [VFSNode(name=_LEAF, type="file", path=f"datasets/{group}/{parts[1]}/{_LEAF}")]

    async def cat(self, path: str, ctx: Optional[Dict[str, Any]] = None) -> VFSResource:
        import pandas as pd

        from core.sheet_dataset_service import SHEET_ROW_COL

        cleaned = (path or "").lstrip("/").rstrip("/")
        if cleaned.endswith(f"/{_LEAF}"):
            cleaned = cleaned[: -len(f"/{_LEAF}")]
        parts = [p for p in cleaned.split("/") if p and p != "datasets"]
        if len(parts) < 2:
            raise FileNotFoundError(f"'{path}' is not a dataset leaf")
        group, entity_slug = parts[0], parts[1]

        entries = self._entries()
        group_entries = self._entities_of(group, entries)
        entry = next(
            (e for e in group_entries if self._entity_slug(e) == entity_slug),
            None,
        )
        if entry is None:
            raise FileNotFoundError(f"No dataset '{entity_slug}' under '{group}'")

        df = pd.read_parquet(entry["parquet_path"])
        lines: List[str] = [
            f"# {entry.get('file_name')} — sheet '{entry.get('entity_name')}' "
            f"({entry.get('row_count')} rows; source modified "
            f"{entry.get('source_modified_at') or 'unknown'})"
        ]
        cols = [c for c in df.columns if c != SHEET_ROW_COL]
        shown = df.head(_MAX_LINES_PER_SHEET)
        for _, row in shown.iterrows():
            rnum = row.get(SHEET_ROW_COL)
            cells = " | ".join(
                f"{c}={' '.join(str(row[c]).split())[:48]}"
                for c in cols
                if row.get(c) is not None and str(row.get(c)).strip()
            )
            lines.append(f"R{rnum} | {cells}")
        if len(df) > _MAX_LINES_PER_SHEET:
            lines.append(f"... {len(df) - _MAX_LINES_PER_SHEET} more rows — query via datasets.search/query_data")
        return VFSResource(
            path=f"datasets/{group}/{entity_slug}/{_LEAF}",
            meta={
                "file_name": entry.get("file_name"),
                "source": entry.get("source"),
                "source_kind": entry.get("source_kind"),
                "content_hash": entry.get("content_hash"),
                "row_count": entry.get("row_count"),
                "columns": entry.get("columns"),
                "source_modified_at": entry.get("source_modified_at"),
                "dataset_name": entry.get("dataset_name"),
            },
            lines=lines,
        )

    async def grep(
        self, pattern: str, path_prefix: str, ctx: Optional[Dict[str, Any]] = None
    ) -> List[VFSCitation]:
        """Content search across ALL datasets — the VFS face of the value
        probe. Leaves sit two levels deep, so the default one-level walk is
        overridden; each sheet is scanned for the pattern, citations carry
        precise line numbers."""
        import re as _re

        try:
            regex = _re.compile(pattern, _re.IGNORECASE)
        except _re.error:
            return []
        entries = self._entries()
        parts = [p for p in (path_prefix or "").lstrip("/").rstrip("/").split("/") if p and p != "datasets"]
        candidates = entries
        if parts:
            candidates = self._entities_of(parts[0], entries)
        citations: List[VFSCitation] = []
        for entry in candidates:
            try:
                res = await self.cat(f"datasets/{_group_of(entry)}/{self._entity_slug(entry)}", ctx)
            except Exception:  # noqa: BLE001 — one bad sheet never blocks grep
                continue
            for i, line in enumerate(res.lines):
                if regex.search(line):
                    citations.append(VFSCitation(
                        path=res.path, line=i + 1, snippet=line[:200],
                    ))
        return citations
