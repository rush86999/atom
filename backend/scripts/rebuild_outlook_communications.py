#!/usr/bin/env python3
"""Rebuild atom_communications from a healthy Lance version, repaired.

Why (Aug 2026): the Outlook poller kept an in-memory-only fetch cursor, so
every backend restart re-fetched the newest mailbox page and re-added it —
749 distinct messages had grown into 21k duplicate rows with EMPTY
sender/recipient/content (a normalizer key mismatch dropped them), 21k Lance
version manifests (~20GB) and a 100%-full disk. Merge-insert repair on that
fragmented table multiplied the damage, so this script REBUILDS instead:

  1. checkout() the last healthy version (pre-duplication-collapse)
  2. dedup rows by message id (keep one copy)
  3. repair outlook fields from the preserved raw Graph payload
     (metadata.email_metadata.outlook_metadata): sender / recipient /
     html-stripped content / received timestamp — same logic as the fixed
     pipeline normalizer
  4. re-embed content (FastEmbed bge-small, same embedder as the pipeline)
  5. swap in a fresh table, recreate the content FTS index
  6. seed poll_fetch_state.json so the poller resumes without re-adding

Usage (from repo root):
  PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python \
      -m scripts.rebuild_outlook_communications [--source-version 21380] [--apply]

Without --apply it only reports what it would do.
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("rebuild_outlook_communications")

_CHUNK = 2000

_HTML_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.DOTALL | re.IGNORECASE)
_HTML_WS_RE = re.compile(r"[ \t]*\n[ \t\n]*")


def _html_to_text(html_body: str) -> str:
    if not html_body:
        return ""
    try:
        import html as _html

        text = _HTML_TAG_RE.sub("\n", html_body)
        return _HTML_WS_RE.sub("\n", _html.unescape(text)).strip()
    except Exception:
        return html_body


def _parse_meta(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            try:
                return ast.literal_eval(raw)
            except Exception:
                return {}
    return {}


def _outlook_payload(meta: Dict[str, Any]) -> Dict[str, Any]:
    om = (meta.get("email_metadata") or {}).get("outlook_metadata")
    if isinstance(om, dict):
        return om
    if isinstance(om, str):
        try:
            return json.loads(om)
        except Exception:
            try:
                return ast.literal_eval(om)
            except Exception:
                return {}
    return {}


def _addr(entry: Any) -> str:
    if isinstance(entry, dict):
        return str((entry.get("emailAddress") or {}).get("address") or "")
    return ""


def _recipients(msg: Dict[str, Any]) -> str:
    addrs = []
    for key in ("toRecipients", "ccRecipients", "bccRecipients"):
        for entry in msg.get(key) or []:
            a = _addr(entry)
            if a:
                addrs.append(a)
    return ", ".join(addrs)


def _received_at(msg: Dict[str, Any]) -> Optional[datetime]:
    raw = msg.get("receivedDateTime") or msg.get("createdDateTime")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def repair_fields(row: dict) -> dict:
    """Same field repairs the fixed pipeline normalizer applies at ingest."""
    updates: dict = {}
    om = _outlook_payload(_parse_meta(row.get("metadata")))
    if not om:
        return updates

    body = om.get("body") or {}
    if str(body.get("contentType", "")).lower() == "html":
        content = _html_to_text(str(body.get("content") or ""))
    else:
        content = str(body.get("content") or "").strip()
    content = content or str(om.get("bodyPreview") or "").strip()

    if content:
        updates["content"] = content
    sender = _addr(om.get("from") or om.get("sender"))
    if sender:
        updates["sender"] = sender
    recipient = _recipients(om)
    if recipient:
        updates["recipient"] = recipient
    ts = _received_at(om)
    if ts is not None:
        updates["timestamp"] = ts
    return updates


class Embedder:
    def __init__(self):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        self.dim = 384

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [e.tolist() for e in self._model.embed(texts)]


def dedup_and_repair(rows: List[dict]) -> Tuple[List[dict], Dict[str, int]]:
    """Keep one row per id; repair outlook fields; report what was done."""
    stats = {"total": len(rows), "dup_removed": 0, "repaired": 0, "unrepaired": 0}
    by_id: Dict[str, dict] = {}
    for row in rows:
        rid = str(row.get("id") or "")
        if rid in by_id:
            stats["dup_removed"] += 1
            continue
        by_id[rid] = dict(row)

    result = []
    for rid, row in by_id.items():
        if row.get("app_type") == "outlook":
            updates = repair_fields(row)
            if updates:
                row.update(updates)
                stats["repaired"] += 1
            elif not str(row.get("content") or "").strip():
                stats["unrepaired"] += 1
        result.append(row)
    return result, stats


def embed_rows(rows: List[dict], schema) -> List[dict]:
    import pyarrow as pa

    embedder = Embedder()
    for start in range(0, len(rows), _CHUNK):
        chunk = rows[start:start + _CHUNK]
        texts = [str(r.get("content") or "") for r in chunk]
        vectors = embedder.embed_batch(texts)
        for row, vec in zip(chunk, vectors):
            row["vector"] = vec
            row["search_vector"] = vec
        logger.info("embedded %d/%d", min(start + _CHUNK, len(rows)), len(rows))
    _ = pa  # schema import guard
    return rows


def seed_poll_state(db, ids: List[str], memory_dir: str) -> None:
    """Resume the poller from 'now' with the rebuilt ids marked as seen."""
    state_path = os.path.join(memory_dir, "poll_fetch_state.json")
    state: Dict[str, Any] = {}
    if os.path.exists(state_path):
        try:
            state = json.loads(open(state_path).read() or "{}")
        except Exception:
            state = {}
    known = set(state.get("seen_message_ids") or [])
    known.update(ids)
    cursors = state.get("fetch_timestamps") or {}
    cursors.setdefault("last_fetch_outlook", datetime.now().isoformat())
    state["seen_message_ids"] = list(known)[-20000:]
    state["fetch_timestamps"] = cursors
    tmp = state_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, state_path)
    logger.info("seeded %s (%d known ids)", state_path, len(known))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-version", type=int, required=True,
                        help="healthy Lance version to recover from")
    parser.add_argument("--workspace", default="default")
    parser.add_argument("--apply", action="store_true", help="write the rebuilt table")
    args = parser.parse_args()

    import lancedb

    memory_dir = os.path.join("data", "atom_memory", args.workspace)
    db = lancedb.connect(memory_dir)
    table = db.open_table("atom_communications")

    table.checkout(args.source_version)
    snapshot = table.to_arrow().to_pylist()
    logger.info("snapshot v%d: %d rows", args.source_version, len(snapshot))
    table.checkout_latest()

    rebuilt, stats = dedup_and_repair(snapshot)
    logger.info("dedup/repair: %s", stats)

    distinct = len({r["id"] for r in rebuilt})
    kellam = [r for r in rebuilt if "kellam" in (str(r.get("content")) + str(r.get("subject"))).lower()]
    logger.info("rebuilt: %d rows (%d distinct ids), %d mention Kellam", len(rebuilt), distinct, len(kellam))

    if not args.apply:
        for r in kellam[:3]:
            logger.info("sample: from=%s | %s | %.90s", r.get("sender"), r.get("timestamp"), r.get("content"))
        logger.info("dry-run only — pass --apply to write")
        return 0

    schema = table.schema
    embed_rows(rebuilt, schema)

    import pyarrow as pa

    arrow = pa.Table.from_pylist(rebuilt, schema=schema)
    db.drop_table("atom_communications")
    new_table = db.create_table("atom_communications", schema=schema)
    for start in range(0, len(rebuilt), _CHUNK):
        new_table.add(arrow.slice(start, _CHUNK))
        logger.info("added %d/%d rows", min(start + _CHUNK, len(rebuilt)), len(rebuilt))

    try:
        new_table.create_index(
            metric="bm25", index_type="FTS", column="content",
            name="content_idx", replace=True,
        )
        logger.info("content FTS index created")
    except Exception as e:
        logger.warning("FTS index creation skipped (%s)", e)

    seed_poll_state(db, [str(r["id"]) for r in rebuilt], memory_dir)

    logger.info("DONE: live table now has %d rows", new_table.count_rows())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
