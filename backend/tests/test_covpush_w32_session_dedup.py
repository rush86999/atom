"""Coverage wave 32 — core/llm/compression/session_dedup.py (91% -> 95%+).

Completes the remaining branches (pure unit tests, no DB/network):
- _chunk empty-text early return
- _chunk buffer merge when a small part follows an existing buffer
- _chunk buffer flush when a large part arrives
- _chunk small part (just under the min) buffered for the tail
- deduplicate multi-chunk no-match -> original text returned unchanged
- deduplicate defensive empty-chunks guard (via _chunk mock)
"""
from unittest import mock

from core.llm.compression.session_dedup import DEDUP_MIN_CHUNK_CHARS, SessionDedupIndex


def test_chunk_empty_text_returns_empty_list():
    assert SessionDedupIndex._chunk("") == []
    assert SessionDedupIndex().index_text("") is None


def test_chunk_merges_small_parts_into_buffer():
    """Two small parts merge into one buffer chunk (never indexed)."""
    small = "A" * (DEDUP_MIN_CHUNK_CHARS // 4)
    idx = SessionDedupIndex()
    idx.index_text(small + "\n\n" + small)
    assert idx.size == 0


def test_chunk_flushes_buffer_when_large_part_arrives():
    """Small part buffered, then a large part flushes it as its own chunk."""
    small = "B" * (DEDUP_MIN_CHUNK_CHARS // 4)
    big = "C" * (DEDUP_MIN_CHUNK_CHARS + 100)
    idx = SessionDedupIndex()
    idx.index_text(small + "\n\n" + big)
    assert idx.size == 1  # only the big chunk qualifies


def test_chunk_buffers_just_under_min_part_for_tail():
    """A part of length min-1 (len+2 >= min, but < min itself) is buffered."""
    mid = "D" * (DEDUP_MIN_CHUNK_CHARS - 1)
    idx = SessionDedupIndex()
    idx.index_text("E" * (DEDUP_MIN_CHUNK_CHARS + 100) + "\n\n" + mid)
    assert idx.size == 1


def test_deduplicate_no_match_returns_original_text():
    """Multi-chunk text where nothing is in the index -> (text, 0)."""
    idx = SessionDedupIndex()
    text = "F" * (DEDUP_MIN_CHUNK_CHARS + 10) + "\n\n" + "G" * (DEDUP_MIN_CHUNK_CHARS + 10)
    assert idx.deduplicate(text) == (text, 0)


def test_deduplicate_defensive_empty_chunks_guard():
    """_chunk returns [] only for empty text (already short-circuited);
    guard is defensive — reach it by mocking the chunker."""
    idx = SessionDedupIndex()
    with mock.patch.object(SessionDedupIndex, "_chunk", staticmethod(lambda text: [])):
        text = "some non-empty text"
        assert idx.deduplicate(text) == (text, 0)
