"""Session-level cross-turn exact-match deduplication.

Replaces byte-identical repeated text chunks across turns with lightweight
reference markers, so unchanged context (system prompts, tool definitions,
prior outputs that repeat) isn't re-sent verbatim every turn.

CRITICAL: this is EXACT-MATCH ONLY (SHA-256 hash comparison). It performs
NO semantic rewriting, NO prose compression, NO summarization. If two chunks
differ by even one character, they are treated as different. This is the
safety boundary that makes it safe for business automation — financial
figures, CRM records, and contract terms are never altered.

Evidence basis: lossy/semantic compression degrades agentic accuracy and
changes failure modes (ICML 2025 arXiv:2505.19433, arXiv:2510.22963, ACM
LLMLingua-2 eval). Exact-match dedup has zero information loss — if the
text is byte-identical, replacing it with a reference loses nothing.
"""
from __future__ import annotations

import hashlib
import logging
import os
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Minimum chunk size (chars) to bother deduplicating. Smaller chunks are
# not worth the reference-marker overhead.
DEDUP_MIN_CHUNK_CHARS: int = int(os.getenv("COMPRESS_DEDUP_MIN_CHUNK", "200"))

# Max entries in the per-session hash index (LRU eviction beyond this).
DEDUP_MAX_INDEX_SIZE: int = int(os.getenv("COMPRESS_DEDUP_MAX_INDEX", "500"))


class SessionDedupIndex:
    """Per-session LRU index of content hashes seen in prior turns.

    Thread-safe within a single asyncio event loop (mutations happen in the
    orchestrator's request path, which is sequential per session).
    """

    def __init__(self, max_size: int = DEDUP_MAX_INDEX_SIZE) -> None:
        self._max_size = max_size
        # OrderedDict for LRU: hash → first-seen chunk preview (for logging)
        self._seen: "OrderedDict[str, str]" = OrderedDict()

    def index_text(self, text: str) -> None:
        """Add all qualifying chunks from ``text`` to the index."""
        for chunk in self._chunk(text):
            if len(chunk) < DEDUP_MIN_CHUNK_CHARS:
                continue  # too short to be worth indexing
            h = self._hash(chunk)
            if h not in self._seen:
                self._seen[h] = chunk[:60]
                # LRU eviction
                while len(self._seen) > self._max_size:
                    self._seen.popitem(last=False)

    def deduplicate(self, text: str) -> Tuple[str, int]:
        """Replace byte-identical repeated chunks with reference markers.

        Returns (deduplicated_text, replacements_made).
        """
        replacements = 0
        if not text or not text.strip():
            return text, 0

        chunks = self._chunk(text)
        if not chunks:
            return text, 0

        # Special case: single chunk that exactly matches a previously-indexed
        # chunk → replace the whole text with a reference.
        if len(chunks) == 1:
            h = self._hash(chunks[0])
            if h in self._seen:
                return f"[previously sent: {h[:8]}]", 1
            return text, 0

        result_parts: List[str] = []
        for chunk in chunks:
            h = self._hash(chunk)
            if h in self._seen:
                result_parts.append(f"[previously sent: {h[:8]}]")
                replacements += 1
            else:
                result_parts.append(chunk)

        if replacements == 0:
            return text, 0

        # Rejoin with the paragraph separator that _chunk split on. Using ""
        # here would drop the "\n\n" between paragraphs, merging adjacent
        # reference markers and corrupting the text (BUG-010).
        return "\n\n".join(result_parts), replacements

    def clear(self) -> None:
        self._seen.clear()

    @property
    def size(self) -> int:
        return len(self._seen)

    # --- Internal helpers ---------------------------------------------------

    @staticmethod
    def _hash(chunk: str) -> str:
        """SHA-256 of the chunk (exact-match key)."""
        return hashlib.sha256(chunk.encode("utf-8")).hexdigest()

    @staticmethod
    def _chunk(text: str) -> List[str]:
        """Split text into chunks of ≥ DEDUP_MIN_CHUNK_CHARS.

        Splits on paragraph boundaries (double newlines) to avoid cutting
        mid-sentence. Chunks smaller than the minimum are merged with the
        following chunk.
        """
        if not text:
            return []

        raw_parts = text.split("\n\n")
        chunks: List[str] = []
        buffer = ""

        for part in raw_parts:
            if len(buffer) + len(part) + 2 < DEDUP_MIN_CHUNK_CHARS:
                # Merge with buffer
                if buffer:
                    buffer += "\n\n" + part
                else:
                    buffer = part
            else:
                if buffer:
                    chunks.append(buffer)
                    buffer = ""
                if len(part) >= DEDUP_MIN_CHUNK_CHARS:
                    chunks.append(part)
                else:
                    buffer = part

        if buffer:
            chunks.append(buffer)

        return chunks


def get_or_create_dedup_index(session: Dict[str, Any]) -> SessionDedupIndex:
    """Get or create the dedup index on a session dict.

    The index is stored as ``session["_dedup_index"]``. Created lazily on
    first access. Callers should call ``index_text`` after each turn to
    populate, and ``deduplicate`` before building messages from history.
    """
    idx = session.get("_dedup_index")
    if idx is None:
        idx = SessionDedupIndex()
        session["_dedup_index"] = idx
    return idx
