"""Sentence-aware chunking for document ingestion (gap A3).

Research finding (arXiv 2511.05991): grounding graph nodes/edges in source
text chunks was the single decisive factor for answer accuracy (15–20% →
90%). This chunker is deterministic and dependency-free — fixed-size windows
with overlap, snapped to sentence boundaries so extracted entities keep
readable supporting text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


@dataclass
class Chunk:
    index: int
    text: str
    char_start: int
    char_end: int

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[Chunk]:
    """Split ``text`` into overlapping, sentence-aligned chunks.

    Args:
        text: raw document text.
        chunk_size: target character count per chunk.
        overlap: character overlap between consecutive chunks.
    """
    if not text or not text.strip():
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    overlap = max(0, min(overlap, chunk_size // 2))

    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]
    if not sentences:  # single unbroken blob
        sentences = [text]

    chunks: List[Chunk] = []
    current = ""
    start = 0
    cursor = 0  # absolute offset of the current scan position

    for sentence in sentences:
        # Re-locate the sentence's absolute offset (split drops whitespace).
        idx = text.find(sentence, cursor)
        if idx == -1:
            idx = cursor
        if current == "":
            start = idx
        if len(current) + len(sentence) <= chunk_size or not current:
            current += (" " if current and not current.endswith((" ", "\n")) else "") + sentence
            cursor = idx + len(sentence)
        else:
            chunks.append(Chunk(len(chunks), current.strip(), start, start + len(current)))
            # Start the next chunk with trailing context for continuity.
            tail = current[-overlap:] if overlap else ""
            current = tail + sentence
            start = max(0, start + len(current) - len(sentence) - len(tail))
            cursor = idx + len(sentence)
    if current.strip():
        chunks.append(Chunk(len(chunks), current.strip(), start, start + len(current)))

    return chunks


def locate_name_chunks(name: str, chunks: List[Chunk], limit: int = 10) -> List[int]:
    """Chunk indices whose text mentions ``name`` (case-insensitive substring).

    Used at ingest time to attach provenance (supporting chunk references)
    to extracted entities — the relational equivalent of RDF 1.2
    ``rdf:reifies`` statement-level provenance.
    """
    if not name:
        return []
    needle = name.lower()
    hits = [c.index for c in chunks if needle in c.text.lower()]
    return hits[:limit]
