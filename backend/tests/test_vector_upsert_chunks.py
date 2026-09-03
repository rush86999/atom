"""Chunked upsert contract: long documents store as {doc_id}::c{i} rows so
each region gets its own embedding; identity, hash-skip, and family cleanup
stay per-file. (2026-09-03 — single-row-per-document made mid-file recall
depend on whatever the document's head looked like.)"""

import asyncio
import hashlib

import pytest

from core.vector_upsert import _split_into_chunks, upsert_document_chunks


class FakeHandler:
    """In-proc stand-in for LanceDBHandler covering the upsert surface."""

    def __init__(self):
        self.rows = {}

    def add_document(self, table_name, text, source, metadata, user_id, doc_id,
                     workspace_id=None, skip_ai_triggers=False, extra_columns=None):
        self.rows[doc_id] = {
            "id": doc_id,
            "text": text,
            "metadata": dict(metadata or {}),
            "extra_columns": dict(extra_columns or {}),
        }
        return True

    def get_document_by_id(self, table_name, doc_id):
        return self.rows.get(doc_id)

    def delete_documents_by_id(self, table_name, doc_id):
        return self.rows.pop(doc_id, None) is not None

    def get_document_ids_by_prefix(self, table_name, prefix):
        return [i for i in self.rows if i.startswith(prefix)]


def _doc_hash(text):
    from core.doc_freshness_service import hash_text

    return hash_text(text)


def _long_text(marker, n_paragraphs=40):
    return "\n\n".join(
        f"{marker} paragraph {i}: " + ("detail " * 30) for i in range(n_paragraphs)
    )


def _run(handler, **kwargs):
    return asyncio.get_event_loop().run_until_complete(
        upsert_document_chunks(handler, table_name="documents", **kwargs)
    )


def test_long_document_writes_chunk_family():
    h = FakeHandler()
    text = _long_text("alpha")
    status = _run(h, text=text, doc_id="doc1", source="s", metadata={})
    assert status == "written"
    chunk_ids = [i for i in h.rows if i.startswith("doc1::c")]
    assert len(chunk_ids) > 3
    full_hash = _doc_hash(text)
    for cid in chunk_ids:
        assert h.rows[cid]["metadata"]["chunk_total"] == len(chunk_ids)
        assert h.rows[cid]["metadata"]["parent_doc_id"] == "doc1"
        assert h.rows[cid]["metadata"]["source_content_hash"] == full_hash
    # ordered indices, no gaps
    idxs = sorted(h.rows[cid]["metadata"]["chunk_index"] for cid in chunk_ids)
    assert idxs == list(range(len(chunk_ids)))


def test_same_content_skips_unchanged():
    h = FakeHandler()
    text = _long_text("alpha")
    assert _run(h, text=text, doc_id="doc1", source="s", metadata={}) == "written"
    before = dict(h.rows)
    assert _run(h, text=text, doc_id="doc1", source="s", metadata={}) == "skipped_unchanged"
    assert h.rows.keys() == before.keys()


def test_changed_content_replaces_family():
    h = FakeHandler()
    assert _run(h, text=_long_text("alpha"), doc_id="doc1", source="s", metadata={}) == "written"
    old_hash = _doc_hash(_long_text("alpha"))
    new_text = _long_text("beta", n_paragraphs=20)
    assert _run(h, text=new_text, doc_id="doc1", source="s", metadata={}) == "written"
    # ids are stable by design ({doc_id}::c0…) — the CONTENT is what's replaced
    new_hash = _doc_hash(new_text)
    assert all(
        m["source_content_hash"] == new_hash
        for m in (r["metadata"] for r in h.rows.values())
    )
    assert not any(
        m["source_content_hash"] == old_hash
        for m in (r["metadata"] for r in h.rows.values())
    ), "no row may keep the old version's hash"


def test_short_document_delegates_to_single_row():
    h = FakeHandler()
    status = _run(h, text="tiny doc", doc_id="doc1", source="s", metadata={})
    assert status == "written"
    assert set(h.rows) == {"doc1"}


def test_shrunk_document_leaves_no_orphan_chunks():
    h = FakeHandler()
    assert _run(h, text=_long_text("alpha"), doc_id="doc1", source="s", metadata={}) == "written"
    family_before = {i for i in h.rows if i.startswith("doc1::c")}
    assert family_before
    assert _run(h, text="now tiny", doc_id="doc1", source="s", metadata={}) == "written"
    assert set(h.rows) == {"doc1"}, "chunk family must be cleaned up"


def test_split_chunks_overlap_and_boundaries():
    text = "\n\n".join(f"line {i} " + "x " * 60 for i in range(30))
    chunks = _split_into_chunks(text, size=800, overlap=120)
    assert len(chunks) > 2
    assert all(len(c) <= 900 for c in chunks), "chunks stay near the window size"
    assert "".join(chunks[0].split()) [:-40] in "".join(text.split())  # content preserved (modulo overlap)
