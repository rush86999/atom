"""Agent file-context: let a chat mention a specific file and ground the
conversation in what was actually ingested from it.

Three pieces, shared by the memory assembler (context injection) and the chat
orchestrator (mini-canvas creation):

- ``detect_file_mentions(message)`` — filenames the user referred to
  ("check the acme_invoices.xlsx data").
- ``lookup_file_records(workspace_id, filename)`` — is data from that file
  available in the workspace's ingested stores, and what does it look like?
- ``build_file_block(...)`` / ``build_file_canvas_content(...)`` — formatted
  output for the LLM context and for the mini canvas.

Matching is intentionally fuzzy: "acme xlsx" matches ``acme_thread.xlsx`` via
shared tokens, because users rarely type exact filenames.
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# A filename-ish token with a known data/document extension. No spaces in
# the name segments — spaces made the match swallow surrounding words
# ("hey check the acme_thread.txt" matched the whole phrase).
FILE_NAME_RE = re.compile(
    r"\b([A-Za-z0-9][A-Za-z0-9_\-]*(?:\.[A-Za-z0-9_\-]+)*\."
    r"(xlsx|xls|csv|tsv|pdf|docx|doc|pptx|txt|md|json))\b",
    re.IGNORECASE,
)

# LanceDB tables that carry per-record ``source`` fields worth searching.
_SCANNABLE_PREFIXES = ("integration_",)
_SCANNABLE_TABLES = ("documents",)

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def detect_file_mentions(message: str) -> List[str]:
    """Filenames (lowercased, deduped) mentioned in a chat message."""
    if not message:
        return []
    seen: List[str] = []
    for m in FILE_NAME_RE.finditer(message):
        name = m.group(1).strip().lower()
        if name and name not in seen:
            seen.append(name)
    return seen


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _tokens(value: str) -> set:
    stem = value.rsplit(".", 1)[0]
    return {t for t in _TOKEN_SPLIT_RE.split(stem.lower()) if len(t) >= 3}


def _matches(mention: str, source: str) -> bool:
    """Fuzzy filename match: exact, containment, or shared stem tokens."""
    a, b = _norm(mention), _norm(source or "")
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta & tb)


def _resolve_workspace_db(workspace_id: str):
    """The LanceDB handle the ingestion pipeline writes to — same resolution
    order as the inventory leg (hybrid service handler, then raw handler)."""
    try:
        from core.hybrid_data_ingestion import get_hybrid_ingestion_service

        handler = get_hybrid_ingestion_service(workspace_id).memory_handler
        if handler is not None and getattr(handler, "db", None) is not None:
            return handler.db
    except Exception:
        pass
    try:
        from core.lancedb_handler import get_lancedb_handler

        handler = get_lancedb_handler(workspace_id)
        db = getattr(handler, "db", None)
        if db is None:
            init = getattr(handler, "_ensure_db", None) or getattr(handler, "initialize", None)
            if callable(init):
                init()
            db = getattr(handler, "db", None)
        if db is not None:
            return db
    except Exception as e:
        logger.debug(f"file context: handler unavailable: {e}")
    # Last resort: open the per-workspace store directly (same path rule as
    # LanceDBHandler: LANCEDB_URI_BASE/<workspace_id>).
    try:
        import os

        import lancedb

        # Anchor relative base paths to backend/ — same rule as
        # LanceDBHandler._resolve_local_db_path. A raw CWD-relative connect
        # forked the store on root-vs-backend launches (2026-09-02).
        from core.lancedb_handler import _resolve_local_db_path

        base_uri = _resolve_local_db_path(
            os.getenv("LANCEDB_URI_BASE", "./data/atom_memory")
        )
        return lancedb.connect(os.path.join(base_uri, workspace_id))
    except Exception as e:
        logger.debug(f"file context: workspace db unavailable: {e}")
        return None


def lookup_file_records(workspace_id: str, filename: str, sample_cap: int = 4) -> Optional[Dict[str, Any]]:
    """Find ingested records originating from ``filename``.

    Returns ``{"found": bool, "tables": [{table, count, samples: [str]}],
    "total": int}`` or ``{"found": False}`` when nothing in the workspace's
    ingested stores originates from that file.
    """
    db = _resolve_workspace_db(workspace_id)
    if db is None:
        return {"found": False}

    tables: List[str] = []
    try:
        for name in sorted(db.table_names()):
            if name in _SCANNABLE_TABLES or str(name).startswith(_SCANNABLE_PREFIXES):
                tables.append(name)
    except Exception as e:
        logger.debug(f"file context: table listing failed: {e}")
        return {"found": False}

    result: Dict[str, Any] = {"found": False, "tables": [], "total": 0}
    for table_name in tables:
        try:
            tbl = db.open_table(table_name)
            arrow = tbl.to_arrow()
            if "source" not in arrow.column_names:
                continue
            rows = arrow.to_pylist()
            matched_texts: List[str] = []
            for row in rows:
                if not _matches(filename, str(row.get("source") or "")):
                    continue
                if len(matched_texts) < sample_cap:
                    text = str(row.get("text") or "").strip().replace("\n", " ")
                    if text:
                        matched_texts.append(text[:160])
            if not matched_texts and not any(
                _matches(filename, str(r.get("source") or "")) for r in rows[:500]
            ):
                continue
            count = sum(
                1 for r in rows if _matches(filename, str(r.get("source") or ""))
            )
            if not count:
                continue
            result["found"] = True
            result["total"] += count
            result["tables"].append(
                {"table": table_name, "count": count, "samples": matched_texts}
            )
        except Exception as e:
            logger.debug(f"file context: scan {table_name} failed: {e}")
            continue

    return result


def build_file_block(filename: str, lookup: Optional[Dict[str, Any]]) -> str:
    """LLM-facing context block for one mentioned file."""
    if lookup is None or not lookup.get("found"):
        return (
            f"FILE CHECK — '{filename}': NOT found in the ingested data. "
            "Tell the user honestly that no data from this file is available "
            "yet, and that they can ingest it (data ingestion) before you can "
            "discuss its contents. Do not invent its contents."
        )
    parts = [f"FILE CHECK — '{filename}': data IS available from ingestion."]
    for t in lookup.get("tables", []):
        parts.append(f"- source table {t['table']}: {t['count']} record(s)")
        for s in t.get("samples", []):
            parts.append(f"  sample: {s}")
    parts.append(
        "Discuss these actual records with the user; do not invent rows that "
        "are not shown."
    )
    return "\n".join(parts)


def build_file_canvas_content(filename: str, lookup: Dict[str, Any]) -> str:
    """Readable preview for the mini canvas (doc-type canvas content)."""
    lines = [f"Data ingested from: {filename}", ""]
    for t in lookup.get("tables", []):
        lines.append(f"{t['table']} — {t['count']} record(s)")
        for s in t.get("samples", []):
            lines.append(f"  • {s}")
        lines.append("")
    lines.append("Edited here, this canvas is a shared reference for training, instruction and discussion.")
    return "\n".join(lines)
