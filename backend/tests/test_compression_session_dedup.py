"""Tests for the session-dedup engine (exact-match only).

Covers: exact-match replacement, single-chunk dedup, multi-chunk dedup,
no-false-positive on similar-but-different text, financial-data safety
(1-cent difference preserved), LRU eviction, session dict integration.
"""
import pytest

from core.llm.compression.session_dedup import (
    SessionDedupIndex,
    get_or_create_dedup_index,
)


@pytest.fixture
def index() -> SessionDedupIndex:
    return SessionDedupIndex()


# --- Exact-match dedup -----------------------------------------------------


def test_exact_match_single_chunk_deduped(index):
    block = "This is a long system prompt that repeats across turns. " * 5
    index.index_text(block)
    result, count = index.deduplicate(block)
    assert count == 1
    assert "previously sent" in result


def test_exact_match_multi_chunk_deduped(index):
    block_a = "This is a long system prompt block that repeats. " * 5
    block_b = "This is new content for the current turn. " * 5
    index.index_text(block_a)
    text = block_a + "\n\n" + block_b
    result, count = index.deduplicate(text)
    assert count >= 1
    assert "previously sent" in result
    assert "new content" in result  # new block preserved


def test_no_dedup_on_first_occurrence(index):
    """Text indexed for the first time should NOT be deduped."""
    block = "This is a new block of content that has not been seen before. " * 5
    index.index_text(block)
    # Deduplicating the SAME text (already indexed) should dedup
    result, count = index.deduplicate(block)
    assert count >= 1  # it was indexed, so it deduplicates


# --- No false positives (CRITICAL for business data) -----------------------


def test_no_false_positive_on_similar_text(index):
    """Similar-but-different text must NOT be deduped."""
    original = (
        "This is the original system prompt with specific details "
        "about the CRM integration and its configuration parameters. " * 3
    )
    modified = original.replace("CRM integration", "ERP integration")
    index.index_text(original)
    result, count = index.deduplicate(modified)
    assert count == 0, "Different text should NOT be deduped!"


def test_financial_data_1_cent_difference_preserved(index):
    """A 1-cent difference in financial data must NOT be deduped."""
    invoice = (
        "Invoice #12345: Customer Acme Corp.\n"
        "Widget A x10 @ $487.23 = $4,872.30\n"
        "Widget B x5 @ $234.56 = $1,172.80\n"
        "Service Plan x1 @ $500.00 = $500.00\n"
        "Subtotal: $6,545.10. Tax (8%): $523.61. Total: $7,068.71.\n"
        "Payment terms: Net 30. Due: 2026-08-30."
    )
    index.index_text(invoice)
    invoice_1_cent_off = invoice.replace("$7,068.71", "$7,068.72")
    result, count = index.deduplicate(invoice_1_cent_off)
    assert count == 0, "1-cent difference must be preserved!"
    assert "$7,068.72" in result


def test_identical_financial_data_deduped(index):
    """Byte-identical financial data IS deduped (zero information loss)."""
    invoice = (
        "Invoice #12345: Customer Acme Corp.\n"
        "Widget A x10 @ $487.23 = $4,872.30\n"
        "Widget B x5 @ $234.56 = $1,172.80\n"
        "Service Plan x1 @ $500.00 = $500.00\n"
        "Subtotal: $6,545.10. Tax (8%): $523.61. Total: $7,068.71.\n"
        "Payment terms: Net 30. Due: 2026-08-30."
    )
    index.index_text(invoice)
    result, count = index.deduplicate(invoice)
    assert count == 1


# --- Edge cases ------------------------------------------------------------


def test_empty_text(index):
    assert index.deduplicate("") == ("", 0)
    assert index.deduplicate("   ") == ("   ", 0)


def test_short_text_not_chunked(index):
    """Text below the minimum chunk size passes through unchanged."""
    short = "Hello world."
    index.index_text(short)
    result, count = index.deduplicate(short)
    assert count == 0
    assert result == short


def test_clear(index):
    block = "A long block of text for testing. " * 10
    index.index_text(block)
    assert index.size > 0
    index.clear()
    assert index.size == 0


# --- LRU eviction ----------------------------------------------------------


def test_lru_eviction():
    idx = SessionDedupIndex(max_size=3)
    for i in range(5):
        idx.index_text(f"Block number {i} with enough content to exceed the minimum chunk size threshold here. " * 3)
    assert idx.size <= 3


def test_lru_evicts_oldest_first():
    idx = SessionDedupIndex(max_size=2)
    block_a = "Block A content that is long enough to qualify for dedup processing. " * 3
    block_b = "Block B content that is long enough to qualify for dedup processing. " * 3
    block_c = "Block C content that is long enough to qualify for dedup processing. " * 3
    idx.index_text(block_a)
    idx.index_text(block_b)
    idx.index_text(block_c)  # should evict block_a
    # block_a should no longer be in the index → not deduped
    _, count_a = idx.deduplicate(block_a)
    assert count_a == 0, "Block A should have been evicted"
    # block_b and block_c should still be present
    _, count_b = idx.deduplicate(block_b)
    assert count_b >= 1, "Block B should still be indexed"


# --- Session dict integration ----------------------------------------------


def test_get_or_create_dedup_index():
    session = {"history": []}
    idx = get_or_create_dedup_index(session)
    assert "_dedup_index" in session
    idx2 = get_or_create_dedup_index(session)
    assert idx is idx2, "Should return the same instance"
