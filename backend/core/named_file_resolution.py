"""Named-file routing: file type and catalog capability take precedence.

This module answers one question before any reader runs:

    "What did the user name, and which catalog can actually resolve it?"

Rules:
- An explicit extension is a capability fact. ``price list.txt`` is a
  document even though the words look like a workbook; ``.xlsx``/``.csv``
  are datasets.
- An extensionless name is resolved against BOTH catalogs before choosing a
  reader. A dataset-catalog miss is not evidence that a document is absent.
- Workspace scope is mandatory for the document catalog. A missing
  workspace returns ``unresolved`` (fail closed), never an all-workspace
  scan.
- Multiple requested sources are returned together. Nothing here selects
  the first source for the caller.

The module is deliberately pure/sync so routing tests do not need a served
application. Database and dataset-catalog access are isolated behind
``_document_rows`` / ``_dataset_rows`` and can be monkeypatched.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from core.agent_file_context import (
    DOCUMENT_EXTENSIONS,
    MATCH_TIER_CONTAINMENT,
    MATCH_TIER_EXACT,
    MATCH_TIER_NORMALIZED,
    SPREADSHEET_EXTENSIONS,
    detect_file_mentions,
    explicit_file_kind,
    score_file_match,
)

logger = logging.getLogger(__name__)

_VERIFIED_TIERS = (MATCH_TIER_EXACT, MATCH_TIER_NORMALIZED)


def _tier_rank(tier: Optional[str]) -> int:
    return {
        MATCH_TIER_EXACT: 3,
        MATCH_TIER_NORMALIZED: 2,
        MATCH_TIER_CONTAINMENT: 1,
    }.get(str(tier or ""), 0)


def _document_rows(workspace_id: Optional[str]) -> List[Dict[str, Any]]:
    """Workspace-scoped uploaded-document catalog rows.

    ``workspace_id`` is required. Returning an empty list on a missing
    workspace is intentional: named-file resolution must not scan every
    workspace when the caller has no scope.
    """
    if not workspace_id:
        return []
    try:
        from core.database import get_db_session
        from core.models import IngestedDocument

        with get_db_session() as db:
            rows = (
                db.query(IngestedDocument)
                .filter(IngestedDocument.workspace_id == workspace_id)
                .all()
            )
        return [
            {
                "file_id": str(getattr(r, "id", "") or ""),
                "file_name": str(getattr(r, "file_name", "") or ""),
                "title": str(getattr(r, "title", "") or ""),
                "workspace_id": str(getattr(r, "workspace_id", "") or ""),
                "file_type": str(getattr(r, "file_type", "") or ""),
            }
            for r in rows
            if str(getattr(r, "id", "") or "")
        ]
    except Exception as exc:
        logger.warning("named-file document catalog lookup failed: %r", exc)
        raise


def _dataset_rows(
    user_id: Optional[str], workspace_id: Optional[str]
) -> List[Dict[str, Any]]:
    """Workspace-scoped dataset-catalog entries (materialized sheets)."""
    if not workspace_id:
        return []
    try:
        from core.sheet_dataset_service import (
            find_entries_sync,
            sheet_datasets_enabled,
        )

        if not sheet_datasets_enabled():
            return []
        return list(
            find_entries_sync("", user_id, workspace_id, 500) or []
        )
    except Exception as exc:
        logger.warning("named-file dataset catalog lookup failed: %r", exc)
        raise


def _match_rows(
    mention: str,
    rows: List[Dict[str, Any]],
    *,
    name_keys: tuple,
    id_key: str,
) -> Dict[str, Any]:
    """Resolve one mention against catalog rows, preserving ambiguity."""
    by_key: Dict[str, Dict[str, Any]] = {}
    name_by_key: Dict[str, str] = {}
    tier_by_key: Dict[str, str] = {}
    for row in rows:
        key = str(row.get(id_key) or "")
        name = ""
        for k in name_keys:
            value = str(row.get(k) or "").strip()
            if value:
                name = value
                break
        if not key or not name:
            continue
        tier = score_file_match(mention, name)
        if tier is None or tier == "token":
            # Token overlap is discovery, not identity. It must never
            # create a candidate or an ambiguity verdict for a named file.
            continue
        prev = tier_by_key.get(key)
        if prev is None or _tier_rank(tier) > _tier_rank(prev):
            tier_by_key[key] = tier
            name_by_key[key] = name
            by_key[key] = row

    verified = [
        key for key, tier in tier_by_key.items() if tier in _VERIFIED_TIERS
    ]
    if verified:
        keys = verified
        if len(keys) == 1:
            chosen_key = keys[0]
            chosen = {
                "file_id": chosen_key,
                "file_name": name_by_key.get(chosen_key),
                "match_tier": tier_by_key.get(chosen_key),
            }
            row = by_key.get(chosen_key) or {}
            return {
                "state": "resolved",
                "file_id": chosen["file_id"],
                "file_name": chosen["file_name"],
                "match_tier": chosen["match_tier"],
                "workspace_id": row.get("workspace_id"),
                "file_type": row.get("file_type"),
                "candidates": [chosen],
            }
        candidates = [
            {
                "file_id": key,
                "file_name": name_by_key.get(key),
                "match_tier": tier_by_key.get(key),
            }
            for key in sorted(keys)
        ]
        return {
            "state": "ambiguous",
            "file_id": None,
            "file_name": None,
            "match_tier": None,
            "candidates": candidates,
        }
    # Containment is discovery-only: a single containment hit still needs
    # confirmation, never a silent verified read.
    containment = [
        {
            "file_id": key,
            "file_name": name_by_key.get(key),
            "match_tier": tier_by_key.get(key),
        }
        for key, tier in tier_by_key.items()
        if tier == MATCH_TIER_CONTAINMENT
    ]
    if containment:
        return {
            "state": "ambiguous",
            "file_id": None,
            "file_name": None,
            "match_tier": MATCH_TIER_CONTAINMENT,
            "candidates": sorted(
                containment, key=lambda c: str(c.get("file_id") or "")
            ),
        }
    return {
        "state": "unresolved",
        "file_id": None,
        "file_name": None,
        "match_tier": None,
        "candidates": [],
    }


def resolve_document_mention(
    mention: str, workspace_id: Optional[str]
) -> Dict[str, Any]:
    try:
        rows = _document_rows(workspace_id)
    except Exception as exc:  # noqa: BLE001
        return {
            "state": "catalog_unavailable",
            "file_id": None,
            "file_name": None,
            "match_tier": None,
            "candidates": [],
            "note": f"document catalog unavailable: {type(exc).__name__}",
        }
    return _match_rows(
        mention,
        rows,
        name_keys=("file_name", "title"),
        id_key="file_id",
    )


def resolve_dataset_mention(
    mention: str, user_id: Optional[str], workspace_id: Optional[str]
) -> Dict[str, Any]:
    try:
        rows = _dataset_rows(user_id, workspace_id)
    except Exception as exc:  # noqa: BLE001
        return {
            "state": "catalog_unavailable",
            "file_id": None,
            "file_name": None,
            "match_tier": None,
            "candidates": [],
            "note": f"dataset catalog unavailable: {type(exc).__name__}",
        }
    # Dataset rows repeat per sheet; identity is (source, external_id).
    normalised: List[Dict[str, Any]] = []
    for row in rows:
        source = str(row.get("source") or "")
        external_id = str(
            row.get("external_id")
            or row.get("resource_id")
            or row.get("id")
            or ""
        )
        normalised.append(
            {
                "file_id": (
                    f"{source}|{external_id}" if source else external_id
                ),
                "file_name": str(row.get("file_name") or ""),
                "workspace_id": workspace_id,
            }
        )
    return _match_rows(
        mention,
        normalised,
        name_keys=("file_name",),
        id_key="file_id",
    )


def resolve_named_file_intent(
    message: str,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    *,
    pinned_mention: Optional[str] = None,
) -> Dict[str, Any]:
    """Classify every named source and decide which catalog can read it.

    Returns all sources; no first-source selection. ``reader`` is one of
    ``datasets`` / ``documents`` / ``mixed`` / ``unknown`` / ``None``.
    """
    mentions = detect_file_mentions(message or "")
    if pinned_mention:
        pinned = str(pinned_mention).strip().lower()

        def _canon_mention(value: str) -> str:
            return re.sub(r"[^a-z0-9]+", "", value.casefold())

        if pinned and _canon_mention(pinned) not in {
            _canon_mention(m) for m in mentions
        }:
            # A confirmed task's resolved file is an ADDITIONAL source, not
            # a replacement for other sources named in the message.
            # Resolution-level identity dedupe happens after catalog lookup.
            mentions.append(pinned)
    sources: List[Dict[str, Any]] = []
    readers: List[str] = []
    if mentions and not workspace_id:
        # Missing scope is a configuration answer, not "no document".
        for mention in mentions:
            kind = explicit_file_kind(mention)
            reader = (
                "documents" if kind == "document"
                else "datasets" if kind == "spreadsheet"
                else "unknown"
            )
            sources.append({
                "mention": mention,
                "kind": kind or "unknown",
                "reader": reader,
                "state": "workspace_required",
                "document": None,
                "dataset": None,
                "candidates": [],
            })
        return {
            "mentions": mentions,
            "sources": sources,
            "reader": (
                "documents" if all(s["reader"] == "documents" for s in sources)
                else "datasets" if all(s["reader"] == "datasets" for s in sources)
                else "mixed" if len({s["reader"] for s in sources}) > 1
                else "unknown"
            ),
            "state": "workspace_required",
            "document_mentions": [
                s["mention"] for s in sources if s["kind"] == "document"
            ],
            "dataset_mentions": [
                s["mention"] for s in sources if s["kind"] == "spreadsheet"
            ],
        }
    for mention in mentions:
        kind = explicit_file_kind(mention)
        doc_res = None
        data_res = None
        if kind == "document":
            doc_res = resolve_document_mention(mention, workspace_id)
            reader = "documents"
        elif kind == "spreadsheet":
            data_res = resolve_dataset_mention(
                mention, user_id, workspace_id
            )
            reader = "datasets"
        else:
            doc_res = resolve_document_mention(mention, workspace_id)
            data_res = resolve_dataset_mention(
                mention, user_id, workspace_id
            )
            doc_hit = doc_res.get("state") in ("resolved", "ambiguous")
            data_hit = data_res.get("state") in ("resolved", "ambiguous")
            if doc_hit and data_hit:
                # Uploaded spreadsheets are mirrored into BOTH catalogs.
                # That is ONE source, not a mixed document/workbook ask.
                doc_name = str(doc_res.get("file_name") or "")
                data_name = str(data_res.get("file_name") or "")
                doc_type = str(doc_res.get("file_type") or "").lower()
                doc_ext = (
                    doc_name.rsplit(".", 1)[-1].lower()
                    if "." in doc_name else ""
                )
                doc_is_tabular = (
                    doc_type in SPREADSHEET_EXTENSIONS
                    or doc_ext in SPREADSHEET_EXTENSIONS
                )
                doc_is_document = (
                    doc_type in DOCUMENT_EXTENSIONS
                    or doc_ext in DOCUMENT_EXTENSIONS
                )
                same_name = bool(
                    doc_name
                    and data_name
                    and doc_name.rsplit(".", 1)[0].casefold()
                    == data_name.rsplit(".", 1)[0].casefold()
                )
                reader = (
                    "datasets"
                    if doc_is_tabular
                    or (same_name and not doc_is_document)
                    else "mixed"
                )
            elif doc_hit:
                reader = "documents"
            elif data_hit:
                reader = "datasets"
            else:
                reader = "unknown"
        sources.append(
            {
                "mention": mention,
                "kind": kind or "unknown",
                "reader": reader,
                "state": (
                    (doc_res or {}).get("state")
                    if reader == "documents"
                    else (data_res or {}).get("state")
                    if reader == "datasets"
                    else "ambiguous"
                    if reader == "mixed"
                    else "catalog_unavailable"
                    if (
                        (doc_res or {}).get("state") == "catalog_unavailable"
                        or (data_res or {}).get("state")
                        == "catalog_unavailable"
                    )
                    else "unresolved"
                ),
                "document": doc_res,
                "dataset": data_res,
                "candidates": (
                    (doc_res or {}).get("candidates")
                    if reader in ("documents", "mixed")
                    else (data_res or {}).get("candidates")
                    if reader == "datasets"
                    else []
                ),
            }
        )
        readers.append(reader)

    # Catalog identity dedupe: a prose mention and a clean pinned filename
    # can resolve to the same file. Keep one source per resolved identity;
    # never merge distinct files that merely share a stem.
    deduped: List[Dict[str, Any]] = []
    seen_keys = set()
    for source in sources:
        key = None
        if (
            source.get("reader") == "documents"
            and source.get("state") == "resolved"
        ):
            key = ("doc", (source.get("document") or {}).get("file_id"))
        elif (
            source.get("reader") == "datasets"
            and source.get("state") == "resolved"
        ):
            key = ("data", (source.get("dataset") or {}).get("file_id"))
        if key is not None:
            if key in seen_keys:
                continue
            seen_keys.add(key)
        deduped.append(source)
    sources = deduped
    readers = [str(s.get("reader") or "") for s in sources]

    if not sources:
        return {
            "mentions": [],
            "sources": [],
            "reader": None,
            "state": "none",
            "document_mentions": [],
            "dataset_mentions": [],
        }

    unique_readers = set(readers)
    if len(unique_readers) > 1 or "mixed" in unique_readers:
        reader = "mixed"
    elif unique_readers == {"documents"}:
        reader = "documents"
    elif unique_readers == {"datasets"}:
        reader = "datasets"
    else:
        reader = "unknown"

    states = [str(s.get("state") or "") for s in sources]
    if "catalog_unavailable" in states:
        state = "catalog_unavailable"
    elif "ambiguous" in states or reader == "mixed":
        state = "ambiguous"
    elif all(s == "resolved" for s in states):
        state = "resolved"
    elif any(s == "resolved" for s in states):
        state = "partial"
    else:
        state = "unresolved"

    return {
        "mentions": mentions,
        "sources": sources,
        "reader": reader,
        "state": state,
        "document_mentions": [
            s["mention"] for s in sources if s["kind"] == "document"
        ],
        "dataset_mentions": [
            s["mention"] for s in sources if s["kind"] == "spreadsheet"
        ],
    }
