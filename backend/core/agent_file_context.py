"""Agent file-context: let a chat mention a specific file and ground the
conversation in what was actually ingested from it.

Three pieces, shared by the memory assembler (context injection) and the chat
orchestrator (mini-canvas creation):

- ``detect_file_mentions(message)`` — filenames the user referred to
  ("check the acme_invoices.xlsx data"), including names WITH SPACES
  ("Consolidated Price List 2019.xlsx" — the spaceless regex truncated it
  to "2019.xlsx" and the truncated token then matched unrelated files;
  live 2026-09-23).
- ``lookup_file_records(workspace_id, filename)`` — is data from that file
  available in the workspace's ingested stores, and is the file's IDENTITY
  verified (vs a fuzzy, discovery-only candidate)?
- ``build_file_block(...)`` / ``build_file_canvas_content(...)`` — formatted
  output for the LLM context and for the mini canvas.

Matching is tiered, not binary. Exact and normalized names can establish a
source-name match; containment and shared-token matches are discovery-only;
overlap carried solely by a year or number ("2019.xlsx" vs "Sales 2019
final.xlsx") is not a match. A resource ID/version is still required before
that source can support an authoritative preview.
"""
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# A filename-ish token with a known data/document extension. No spaces in
# the name segments — spaces made the match swallow surrounding words
# ("hey check the acme_thread.txt" matched the whole phrase). Spaced names
# are recovered separately by _SPACED_FILE_NAME_RE below, which bounds the
# damage with a leading-noise strip plus substring de-duplication.
FILE_NAME_RE = re.compile(
    r"\b([A-Za-z0-9][A-Za-z0-9_\-]*(?:\.[A-Za-z0-9_\-]+)*\."
    r"(xlsx|xls|csv|tsv|pdf|docx|doc|pptx|txt|md|json))\b",
    re.IGNORECASE,
)

# Filenames WITH spaces ("Consolidated Price List 2019.xlsx"). Segments are
# single words (no punctuation) joined by one or two spaces/tabs, ending in
# a known extension, so the match cannot run past a comma, period or
# newline. Leading conversational words are stripped afterwards.
_SPACED_FILE_NAME_RE = re.compile(
    r"\b([A-Za-z0-9][A-Za-z0-9_\-()]*(?:[ \t]{1,2}[A-Za-z0-9][A-Za-z0-9_\-()]*){1,8}"
    r"\.(?:xlsx|xls|csv|tsv|pdf|docx|doc|pptx|txt|md|json))\b",
    re.IGNORECASE,
)

_TASK_FILE_PHRASE_RE = re.compile(
    r"\b(?P<name>(?:[A-Za-z0-9][A-Za-z0-9_'’()\-]*[ \t]+){0,4}"
    r"(?:price[ \t]+list|workbooks?|spreadsheets?|excel[ \t]+files?|"
    r"file[ \t]+names?)"
    r"(?:[ \t]+[A-Za-z0-9][A-Za-z0-9_'’()\-]*){0,3}"
    r"[ \t]+(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_TASK_FILE_QUOTED_RE = re.compile(r"[\"']([^\"'\n]{2,100})[\"']")
_TASK_BOUNDARY_WORDS = {
    "from", "in", "of", "at", "on", "for", "to", "the", "a", "an",
    "this", "that", "these", "those", "find", "search", "check", "get",
    "read", "open", "show", "list", "use", "using", "all", "any", "some",
}
_TASK_ANCHOR_WORDS = {"price", "list", "workbook", "workbooks", "spreadsheet", "excel", "file", "filename"}

# Conversational words a spaced match may pick up in front of the real
# name ("hey check the price list.xlsx"). Split in two: function words and
# read-verbs are stripped ALWAYS (they are never plausible filename
# words); domain words are stripped only while the remainder keeps a
# strong stem token, so "Sheet 1.xlsx" never loses "Sheet" (its remainder
# "1.xlsx" carries no identity) while "the workbook <name>.xlsx" does lose
# "workbook". "list" is deliberately in neither: it is a common real
# filename word ("Price List.xlsx").
_LEADING_STRIP_ALWAYS = {
    "a", "an", "the", "this", "that", "these", "those", "my", "our", "your",
    "hey", "hi", "hello", "please", "check", "see", "look", "open", "find",
    "get", "read", "pull", "grab", "fetch", "search", "use", "using",
    "compare", "show", "tell", "want", "need", "give", "at", "in", "on",
    "of", "for", "from", "to", "into", "with", "about", "is", "are", "was",
    "and", "or", "it", "its", "called", "named", "you", "me", "i", "can",
    "could", "would", "should", "do", "does", "did", "what", "whats",
    "which", "where", "how", "much",
}
_LEADING_DOMAIN_WORDS = {
    "file", "workbook", "workbooks", "spreadsheet", "sheet", "excel",
    "doc", "docs", "machine", "machines", "model", "models", "item", "items",
}

#: Extensions that mark a tabular/data file (workbook answer contracts and
#: read-only routing key off these).
SPREADSHEET_EXTENSIONS = ("xlsx", "xls", "xlsm", "csv", "tsv")

_EXTENSION_WORDS = {
    "xlsx", "xls", "xlsm", "csv", "tsv", "pdf", "docx", "doc", "pptx",
    "txt", "md", "json",
}

# LanceDB tables that carry per-record ``source`` fields worth searching.
_SCANNABLE_PREFIXES = ("integration_",)
_SCANNABLE_TABLES = ("documents",)

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")

# Match tiers, strongest first. Exact/normalized names can establish a
# source-name match; containment and token overlap only discover candidates.
MATCH_TIER_EXACT = "exact"
MATCH_TIER_NORMALIZED = "normalized"
MATCH_TIER_CONTAINMENT = "containment"
MATCH_TIER_TOKEN = "token"
VERIFIED_MATCH_TIERS = (MATCH_TIER_EXACT, MATCH_TIER_NORMALIZED)
_TIER_RANK = {
    MATCH_TIER_EXACT: 3, MATCH_TIER_NORMALIZED: 2,
    MATCH_TIER_CONTAINMENT: 1, MATCH_TIER_TOKEN: 0,
}


def _strip_leading_noise(name: str) -> str:
    tokens = name.split()
    while len(tokens) > 1:
        first = tokens[0].lower().strip(".?!,'\"")
        remainder = " ".join(tokens[1:])
        if first.isdigit():
            tokens.pop(0)
            continue
        if first in _LEADING_STRIP_ALWAYS:
            tokens.pop(0)
            continue
        if first in _LEADING_DOMAIN_WORDS and _strong_tokens(remainder):
            tokens.pop(0)
            continue
        break
    return " ".join(tokens)


def _normalize_task_phrase(raw: str) -> str:
    tokens = re.split(r"[ \t]+", (raw or "").strip())
    if not tokens:
        return ""
    anchor = None
    for idx, token in enumerate(tokens):
        clean = token.lower().strip(".,;:!?()[]{}'\"")
        if clean in _TASK_ANCHOR_WORDS:
            anchor = idx
    if anchor is not None:
        start = max(0, anchor - 3)
        for idx in range(anchor - 1, start - 1, -1):
            clean = tokens[idx].lower().strip(".,;:!?()[]{}'\"")
            if clean in _TASK_BOUNDARY_WORDS:
                start = idx + 1
                break
        tokens = tokens[start:]
    while tokens and tokens[0].lower().strip(".,;:!?()[]{}'\"") in _TASK_BOUNDARY_WORDS:
        tokens.pop(0)
    return " ".join(tokens).strip(".,;:!?()[]{}'\"").lower()


def detect_file_task_mentions(message: str) -> List[str]:
    """Conservative file targets for pending reads without a known suffix."""
    if not message:
        return []
    found: List[str] = []
    for match in _TASK_FILE_PHRASE_RE.finditer(message):
        value = _normalize_task_phrase(match.group("name"))
        if value and value not in found:
            found.append(value)
    for match in _TASK_FILE_QUOTED_RE.finditer(message):
        value = (match.group(1) or "").strip().lower()
        if (
            value
            and re.search(r"\b(?:price\s+list|workbook|spreadsheet|excel|file\s+name)\b", value)
            and re.search(r"[A-Za-z]{3,}", value)
            and value not in found
        ):
            found.append(value)
    for value in detect_file_mentions(message):
        if value not in found:
            found.append(value)
    kept = []
    for value in found:
        superseded = any(
            other != value
            and "." in other.rsplit("/", 1)[-1]
            and _canon(value) in _canon(other)
            for other in found
        )
        if not superseded:
            kept.append(value)
    kept.sort(key=lambda value: (-len(value), value))
    return kept


def detect_file_mentions(message: str) -> List[str]:
    """Filenames (lowercased, deduped, most specific first) mentioned in a
    chat message. Spaced names are detected whole — never truncated to
    their last segment — and a bare single-segment name that is part of a
    longer mention in the same message is dropped ("2019.xlsx" inside
    "Consolidated Price List 2019.xlsx")."""
    if not message:
        return []
    raw: List[str] = []
    for m in FILE_NAME_RE.finditer(message):
        raw.append(m.group(1))
    for m in _SPACED_FILE_NAME_RE.finditer(message):
        name = _strip_leading_noise(m.group(1))
        if name:
            raw.append(name)
    ordered: List[str] = []
    seen = set()
    for name in raw:
        n = name.strip().lower()
        if n and n not in seen:
            seen.add(n)
            ordered.append(n)
    canons = {n: _canon(n) for n in ordered}
    kept = [
        n for n in ordered
        if not any(
            canons[n] != canons[other] and canons[n] in canons[other]
            for other in ordered
        )
    ]
    kept.sort(key=lambda n: (-len(n), n))
    return kept


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _canon(value: str) -> str:
    """Identity-comparison form: lowercase with separators collapsed away,
    so "Consolidated_Price-List 2019.xlsx" == "consolidated price list
    2019.xlsx"."""
    return re.sub(r"[\s_\-]+", "", (value or "").strip().lower())


def _tokens(value: str) -> set:
    stem = value.rsplit(".", 1)[0]
    return {t for t in _TOKEN_SPLIT_RE.split(stem.lower()) if len(t) >= 3}


def _strong_tokens(value: str) -> set:
    """Stem tokens that can CARRY a filename identity: alphabetic (or
    alphanumeric with a letter), length >= 3, not a bare number, not a
    generic extension word. A year ("2019") or the extension itself
    ("xlsx") may corroborate but never carries a match on its own."""
    return {
        t for t in _tokens(value)
        if any(c.isalpha() for c in t) and t not in _EXTENSION_WORDS
    }


def score_file_match(mention: str, source: str) -> Optional[str]:
    """Tiered filename identity between a user mention and an ingested
    ``source`` name. Returns the match tier or ``None``.

    - exact / normalized — a name-level match, subject to a strong stem;
      containment and shared-token matches remain discovery-only.
    - containment / token — candidates only; neither can prove file identity.
    - None — no identity claim at all (numeric/year-only or extension-only
      overlap).
    """
    a, b = _norm(mention), _norm(source or "")
    if not a or not b:
        return None
    strong_a, strong_b = _strong_tokens(a), _strong_tokens(b)
    if a == b and strong_a and strong_b:
        return MATCH_TIER_EXACT
    ca, cb = _canon(a), _canon(b)
    if ca == cb and strong_a and strong_b:
        return MATCH_TIER_NORMALIZED
    # Containment: one STEM inside the other ("price list.xlsx" vs
    # "Consolidated Price List 2019.xlsx" — the extension position breaks
    # full-name contiguity, but the stem is a strict subset). The SHORTER
    # side must carry a strong token, so "2019.xlsx" inside "Sales 2019
    # final.xlsx" does not verify. Equal stems with different extensions
    # ("a.csv" vs "a.xlsx") are different files — not containment.
    sa, sb = _canon(a.rsplit(".", 1)[0]), _canon(b.rsplit(".", 1)[0])
    contained = (
        ca in cb or cb in ca
        or (sa and sb and sa != sb and (sa in sb or sb in sa))
    )
    if contained:
        shorter = a if len(ca) <= len(cb) else b
        if _strong_tokens(shorter):
            return MATCH_TIER_CONTAINMENT
        return None
    if _strong_tokens(a) & _strong_tokens(b):
        return MATCH_TIER_TOKEN
    return None


def spreadsheet_mentions(message: str) -> List[str]:
    """Mentions that name a tabular/data file (workbook, sheet, csv)."""
    return [
        m for m in detect_file_mentions(message)
        if m.rsplit(".", 1)[-1] in SPREADSHEET_EXTENSIONS
    ]


def is_spreadsheet_task_mention(mention: str) -> bool:
    value = (mention or "").strip().lower()
    if not value:
        return False
    if value.rsplit(".", 1)[-1] in SPREADSHEET_EXTENSIONS:
        return True
    return bool(re.search(
        r"\b(?:price\s+list|workbook|spreadsheet|excel)\b",
        value,
    ))


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
    """Find ingested records and keep name matches separate from candidates."""
    empty: Dict[str, Any] = {
        "found": False,
        "verified": False,
        "identity_verified": False,
        "ambiguous": False,
        "match_tier": None,
        "matched_source": None,
        "provider": None,
        "resource_id": None,
        "source_metadata": None,
        "tables": [],
        "total": 0,
        "candidates": [],
    }
    db = _resolve_workspace_db(workspace_id)
    if db is None:
        return empty

    try:
        table_names = [
            name for name in sorted(db.table_names())
            if name in _SCANNABLE_TABLES
            or str(name).startswith(_SCANNABLE_PREFIXES)
        ]
    except Exception as e:
        logger.debug(f"file context: table listing failed: {e}")
        return empty

    result: Dict[str, Any] = dict(empty)
    candidates: List[str] = []
    verified: Dict[str, Dict[str, Any]] = {}
    verified_tables: Dict[str, Dict[str, Any]] = {}

    def _identity(row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            try:
                import json as _json
                metadata = _json.loads(metadata)
            except Exception:
                metadata = None
        if not isinstance(metadata, dict):
            metadata = {}
        source_meta = row.get("source_metadata")
        if isinstance(source_meta, dict):
            metadata = {**metadata, **source_meta}
        resource_id = (
            row.get("resource_id") or row.get("external_id")
            or row.get("file_id") or metadata.get("resource_id")
            or metadata.get("external_id") or metadata.get("id")
        )
        provider = row.get("provider") or metadata.get("provider")
        return {
            "provider": str(provider) if provider else None,
            "resource_id": str(resource_id) if resource_id else None,
            "source_metadata": metadata or None,
        }

    for table_name in table_names:
        try:
            tbl = db.open_table(table_name)
            arrow = tbl.to_arrow()
            if "source" not in arrow.column_names:
                continue
            tier_by_source: Dict[str, Optional[str]] = {}
            table_count = 0
            table_samples: List[str] = []
            for row in arrow.to_pylist():
                source = str(row.get("source") or "")
                if source not in tier_by_source:
                    tier_by_source[source] = score_file_match(filename, source)
                tier = tier_by_source[source]
                if tier is None:
                    continue
                table_count += 1
                if tier in VERIFIED_MATCH_TIERS:
                    identity = _identity(row)
                    entry = verified.setdefault(source, {
                        "source": source,
                        "match_tier": tier,
                        **identity,
                        "resource_ids": set(),
                    })
                    # Same NAME in different folders arrives as the same
                    # source string with DIFFERENT resource ids — a name
                    # alone is not identity then either (2026-09-23
                    # review: exact names can exist in multiple folders).
                    if identity.get("resource_id"):
                        entry["resource_ids"].add(identity["resource_id"])
                    if identity.get("resource_id") and not entry.get(
                            "resource_id"):
                        entry["resource_id"] = identity["resource_id"]
                        entry["provider"] = identity.get("provider")
                        entry["source_metadata"] = identity.get(
                            "source_metadata")
                    table = verified_tables.setdefault(table_name, {
                        "table": table_name,
                        "count": 0,
                        "samples": [],
                    })
                    table["count"] += 1
                    if len(table["samples"]) < sample_cap:
                        text = str(row.get("text") or "").strip().replace("\n", " ")
                        if text:
                            table["samples"].append(text[:160])
                    if len(table_samples) < sample_cap:
                        text = str(row.get("text") or "").strip().replace("\n", " ")
                        if text:
                            table_samples.append(text[:160])
                elif source not in candidates:
                    candidates.append(source)
            if not table_count:
                continue
            result["found"] = True
            result["total"] += table_count
            if table_name not in verified_tables:
                result["tables"].append({
                    "table": table_name,
                    "count": table_count,
                    "samples": table_samples[:sample_cap],
                })
        except Exception as e:
            logger.debug(f"file context: scan {table_name} failed: {e}")
            continue

    if len(verified) == 1:
        entry = next(iter(verified.values()))
        if len(entry.get("resource_ids") or ()) > 1:
            # One name, several distinct provider resources behind it.
            result["ambiguous"] = True
            result["match_tier"] = entry.get("match_tier")
        else:
            result.update({
                "verified": True,
                "identity_verified": bool(entry.get("resource_id")),
                "match_tier": entry.get("match_tier"),
                "matched_source": entry.get("source"),
                "provider": entry.get("provider"),
                "resource_id": entry.get("resource_id"),
                "source_metadata": entry.get("source_metadata"),
            })
            result["tables"] = list(verified_tables.values())
    elif len(verified) > 1:
        result["ambiguous"] = True
        candidates = list(verified) + candidates
        result["tables"] = []

    result["candidates"] = candidates[:5]
    if not result["found"]:
        result["candidates"] = []
    return result


def build_file_block(filename: str, lookup: Optional[Dict[str, Any]]) -> str:
    """LLM-facing context block for one mentioned file."""
    lookup = lookup or {}
    if lookup.get("identity_verified") is False:
        candidates = ", ".join(
            f"'{c}'" for c in (lookup.get("candidates") or [])[:3]
        )
        return (
            f"FILE CHECK — '{filename}': source identity is not verified. "
            f"Similarly-named sources ({candidates}) may exist, but no "
            "provider resource ID/version was confirmed. Do not present "
            "their rows as this file's contents."
        )
    if not lookup.get("found"):
        base = (
            f"FILE CHECK — '{filename}': NOT found in the ingested data. "
            "Tell the user honestly that no data from this file is available "
            "yet, and that they can ingest it (data ingestion) before you can "
            "discuss its contents. Do not invent its contents."
        )
        if lookup.get("candidates"):
            sims = ", ".join(f"'{c}'" for c in lookup["candidates"][:3])
            base += (
                f" Similarly-named ingested sources exist ({sims}) but none "
                "confirms this file's identity — do not present their rows "
                "as this file's contents."
            )
        return base
    matched = lookup.get("matched_source") or filename
    if not lookup.get("verified"):
        sims = ", ".join(f"'{c}'" for c in (lookup.get("candidates") or [])[:3])
        return (
            f"FILE CHECK — '{filename}': identity NOT confirmed. Data from "
            f"similarly-named source(s) ({sims}) is ingested, but nothing "
            "verifies which (if any) IS the file the user named. Do not "
            "present those rows as this file's contents; confirm the exact "
            "file or read the file itself first."
        )
    tier = lookup.get("match_tier") or "match"
    parts = [
        f"FILE CHECK — '{filename}': VERIFIED ({tier} match) against ingested "
        f"source '{matched}'. Data IS available from ingestion."
    ]
    for t in lookup.get("tables", []):
        parts.append(f"- source table {t['table']}: {t['count']} record(s)")
        for s in t.get("samples", []):
            parts.append(f"  sample: {s}")
    parts.append(
        "These are cached ingestion EXCERPTS, not the file's full contents: "
        "discuss them as samples, and verify specific values (prices, "
        "quantities) against a fresh read of the file before quoting them "
        "as authoritative. Do not invent rows that are not shown."
    )
    return "\n".join(parts)


def build_file_canvas_content(
    filename: str, lookup: Dict[str, Any], mention: Optional[str] = None,
    live_identity: Optional[Dict[str, Any]] = None,
    differs_from_live: Optional[Dict[str, Any]] = None,
) -> str:
    """Readable preview for the mini canvas (doc-type canvas content).
    ``filename`` is the VERIFIED ingested source name; ``mention`` is what
    the user typed (kept visible when it differs). ``live_identity`` ties
    the preview to the conversation's live read of the SAME file (shared
    evidence, not an independent source); ``differs_from_live`` explicitly
    flags that a DIFFERENT file was read live."""
    lookup = lookup or {}
    if lookup.get("identity_verified") is False:
        return (
            f"Data source identity is not verified for '{filename}'. "
            "No preview was created because the source resource/version "
            "could not be confirmed."
        )
    lines = [f"Data ingested from: {filename}", ""]
    if mention and _canon(mention) != _canon(filename):
        lines.append(f"(matched your mention '{mention}' — "
                     f"{lookup.get('match_tier') or 'fuzzy'} match)")
        lines.append("")
    lines.append(
        "NOTE: cached ingestion samples — NOT a fresh read of the file."
    )
    if isinstance(live_identity, dict) and live_identity.get("file_name"):
        _svc = live_identity.get("service") or "storage"
        _fid = live_identity.get("file_id") or live_identity.get("resource_id") or "?"
        _hash = live_identity.get("content_sha256") or "unavailable"
        lines.append(
            f"SAME FILE AS THIS CONVERSATION'S LIVE READ / VERIFIED RESOURCE "
            f"({_svc}, id {_fid}, sha256 {_hash}): this preview is bound to "
            "the resource used by the answer."
        )
        _workbook = live_identity.get("workbook_read")
        if isinstance(_workbook, dict):
            for _outcome in (_workbook.get("coverage", {}).get("outcomes", [])):
                _refs = ", ".join(
                    f"{_item.get('sheet')}!{_item.get('cell')}"
                    for _item in (_outcome.get("evidence") or [])[:3]
                )
                lines.append(
                    f"TARGET {_outcome.get('target')}: "
                    f"{str(_outcome.get('status') or '').upper()}"
                    + (f" | {_refs}" if _refs else "")
                )
    elif isinstance(differs_from_live, dict) and differs_from_live.get(
            "file_name"):
        lines.append(
            "DIFFERENT FILE than the one read earlier in this conversation "
            f"('{differs_from_live['file_name']}') — do not mix their values."
        )
    lines.append("")
    for t in lookup.get("tables", []):
        lines.append(f"{t['table']} — {t['count']} record(s)")
        for s in t.get("samples", []):
            lines.append(f"  • {s}")
        lines.append("")
    lines.append("Edited here, this canvas is a shared reference for training, instruction and discussion.")
    return "\n".join(lines)
