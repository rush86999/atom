# -*- coding: utf-8 -*-
"""Value-provenance tracing (2026-10-01, owner policy).

The policy (owner directive, stated after the price-verification
conversation): a value that a workbook/read cannot derive is NOT
immediately 'unsourced' — manual calculations typically live in
ATTACHMENTS (emailed spreadsheets, worksheets, letters) that are
cataloged alongside the main file. Tier 1 is therefore a trace across
every OTHER cataloged document; only when no other document carries the
item is the value 'body-only', and the decision becomes a typed
two-option choice for the user:

  1. use the value as-is (user confirms), or
  2. rebuild it from components (the user supplies the base inputs; the
     agent gathers the modifier inputs per the taught business rules —
     who to ask and which components is KNOWLEDGE, never code).

Domain-neutral by construction: items are tokens, documents are catalog
entries, and the option labels carry no business vocabulary.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional, Sequence

__all__ = [
    "trace_items_across_catalog",
    "provenance_lines",
    "decision_options",
]

#: Bounded work: at most this many items traced, each across at most
#: this many other files — the trace is evidence-gathering, not a scan.
MAX_ITEMS = 8
MAX_FILES = 12


def _default_probe(entries: Sequence[Dict[str, Any]], item: str) -> bool:
    """Does this file (its entries) carry the item? Reuses the cached,
    word-boundary-aware content probe."""
    from core.sheet_dataset_service import _probe_cached

    try:
        return _probe_cached(list(entries or []), item, 3) is not None
    except Exception:  # noqa: BLE001 — a file that won't probe is a 'no'
        return False


def _default_catalog(user_id: Optional[str],
                     workspace_id: Optional[str]) -> List[Dict[str, Any]]:
    from core.sheet_dataset_service import find_entries_sync

    return find_entries_sync("", user_id, workspace_id, 1000) or []


def trace_items_across_catalog(
    items: Sequence[str],
    *,
    exclude_file: Optional[str] = None,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    probe: Optional[Callable[[Sequence[Dict[str, Any]], str], bool]] = None,
    catalog: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, List[str]]:
    """Per item: the OTHER cataloged documents that carry it.

    Pure aggregation when ``catalog``/``probe`` are injected (tests);
    the default catalog read happens on the caller's thread — the
    orchestrator wraps this in ``asyncio.to_thread``.
    """
    probe = probe or _default_probe
    clean = [str(i).strip() for i in items or [] if str(i).strip()]
    if not clean:
        return {}
    if catalog is None:
        catalog = _default_catalog(user_id, workspace_id)
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for entry in catalog or []:
        name = str(entry.get("file_name") or "").strip()
        if not name or (exclude_file
                        and name.lower() == str(exclude_file).lower()):
            continue
        by_file.setdefault(name, []).append(entry)
    out: Dict[str, List[str]] = {}
    for item in clean[:MAX_ITEMS]:
        holders: List[str] = []
        for name, entries in list(by_file.items())[:MAX_FILES]:
            if probe(entries, item):
                holders.append(name)
        out[item] = holders
    return out


def provenance_lines(trace: Dict[str, List[str]]) -> List[str]:
    """Human lines for the trace: which other documents carry each item,
    and which are body-only (the tier-1 result the decision rests on)."""
    if not trace:
        return []
    lines = ["Derivation check across other cataloged documents:"]
    body_only: List[str] = []
    for item, files in trace.items():
        if files:
            shown = ", ".join(files[:3]) + (
                f" +{len(files) - 3} more" if len(files) > 3 else "")
            lines.append(f"- {item}: found in {shown}")
        else:
            body_only.append(str(item))
    if body_only:
        lines.append(
            "- no other cataloged document carries: "
            + ", ".join(body_only)
            + " (body-only values — the quoted figure is the only "
              "source found)")
    return lines


def decision_options() -> List[Dict[str, str]]:
    """The typed two-option decision for body-only values.

    Labels are the user's own reply when clicked (the UI fills the
    input with the label), so they read as messages. Business specifics
    — who to ask for which components, the margin rule — live in taught
    knowledge and are applied at execution, never here.
    """
    return [
        {"type": "confirm",
         "label": "Use these values as-is"},
        {"type": "execute",
         "label": "Rebuild instead: I'll give the base inputs — gather "
                  "the remaining components and recalculate"},
    ]
