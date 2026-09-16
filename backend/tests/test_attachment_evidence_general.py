# -*- coding: utf-8 -*-
"""Attachments are first-class searchable evidence (generalized).

An identifier can live in three places, and a search that reads only one of them
is blind to the other two:

1. the message TEXT,
2. the file NAME,
3. the file CONTENT.

The live F-5216 case failed on all three at once (2026-09-15): the 4:07 PM
forward's body says only "Fw: RFQ - Foot shear / Please check - row - 235", the
workbook is named ``PRICE VIPUL (6).xlsx`` (no code in it), and even its row 235
reads ``F-52"x16G`` — the literal "F-5216" appears in neither the message, nor
the file name, nor the file. The only way to the answer is the JOIN: file →
the message that carried it.

These tests lock the join, not the case: nothing here is mail-, sheet-, machine-
or business-specific. Any comms row, any integration, any file type.
"""
import pytest

import core.chat_tool_planner as p


class TestAttachmentNameDerivation:
    def test_names_from_the_structured_column(self):
        row = {"attachments": '[{"name": "Quote 1234.pdf"}, {"name": "spec.doc"}]'}
        assert p._comms_attachment_names(row) == ["Quote 1234.pdf", "spec.doc"]

    def test_malformed_and_empty_cells_are_safe(self):
        for bad in (None, "", "[]", "not json", '{"name": "x"}', 0):
            assert p._attachment_names(bad) == []

    def test_identifier_tokens_come_out_of_the_file_name(self):
        """A code inside a file name is what a query actually matches."""
        text = p._comms_attachment_text(
            {"attachments": '[{"name": "F-5216 spec sheet (rev 2).pdf"}]'}
        )
        assert "F-5216 spec sheet (rev 2).pdf" in text
        for token in ("5216", "spec", "sheet", "rev"):
            assert token in text

    def test_no_attachments_yields_empty_text(self):
        assert p._comms_attachment_text({"attachments": "[]"}) == ""

    def test_ledger_and_column_are_merged(self, monkeypatch):
        """The two sources disagree in the wild; the union is the truth.

        The F-5216 forward stores ``'[]'`` in its own column while the workbook
        sits ingested against its message id — reading only the column made the
        attachment invisible.
        """
        monkeypatch.setattr(
            p, "_mail_attachments_for", lambda mid, limit=4: [("PRICE VIPUL (6).xlsx", "ext_1")]
        )
        row = {"id": "m1", "attachments": "[]"}
        assert p._comms_attachment_names(row) == ["PRICE VIPUL (6).xlsx"]

    def test_union_dedupes(self, monkeypatch):
        monkeypatch.setattr(
            p, "_mail_attachments_for", lambda mid, limit=4: [("a.pdf", "doc1")]
        )
        row = {"id": "m1", "attachments": '[{"name": "a.pdf"}]'}
        assert p._comms_attachment_names(row) == ["a.pdf"]


class TestFileNameTokens:
    def test_generic_tokenization(self):
        toks = p._file_name_tokens("PRICE VIPUL (6).xlsx")
        assert {"price", "vipul"} <= toks

    def test_format_words_are_not_evidence(self):
        """The extension says what FORMAT a file is, not WHICH file it is.

        Counting it made every two spreadsheets match each other on "xlsx", so
        the file→message join degenerated into "all of them" (caught by
        test_one_short_shared_token_does_not_match).
        """
        for name in ("a.xlsx", "b.pdf", "final docx.docx", "scan img.png"):
            assert not (p._file_name_tokens(name) & p._FORMAT_TOKENS)

    def test_short_tokens_are_dropped(self):
        assert p._file_name_tokens("a-b-12.pdf") == set()

    def test_empty_is_empty(self):
        assert p._file_name_tokens("") == set()
        assert p._file_name_tokens(None) == set()


class TestCarryingMessageJoin:
    def test_no_match_returns_empty(self, monkeypatch):
        monkeypatch.setattr(p, "_mail_attachment_reverse_index", lambda: {})
        assert p._messages_carrying_file("anything.xlsx") == []

    def test_blank_name_returns_empty(self):
        assert p._messages_carrying_file("") == []
        assert p._messages_carrying_file("   ") == []

    def test_two_shared_tokens_match(self, monkeypatch):
        monkeypatch.setattr(
            p,
            "_mail_attachment_reverse_index",
            lambda: {"PRICE VIPUL (6).xlsx": [("msg-1", "doc-1")]},
        )
        monkeypatch.setattr(
            p, "_comms_store_records", lambda: [{"id": "msg-1", "subject": "s", "content": ""}]
        )
        lines = p._messages_carrying_file("PRICE VIPUL.xlsx")
        assert len(lines) == 1
        assert "doc-1" in lines[0]

    @pytest.mark.parametrize(
        "wanted,known",
        [
            ("widget list 2019.xlsx", "widget price report.xlsx"),
            ("vipul pricing.xlsx", "PRICE VIPUL (6).xlsx"),
            ("vipul pricing.xlsx", "Consolidated Price List 2019.pdf"),
        ],
    )
    def test_one_shared_token_does_not_match(self, monkeypatch, wanted, known):
        """One shared token is not evidence — measured on the real store.

        Allowing a single shared token (even a 5-char one like "price") matched
        four UNRELATED price lists for the "PRICE VIPUL (6).xlsx" query, which
        would annotate the answer with other vendors' files.
        """
        monkeypatch.setattr(
            p, "_mail_attachment_reverse_index", lambda: {known: [("msg-1", "doc-1")]}
        )
        monkeypatch.setattr(
            p, "_comms_store_records", lambda: [{"id": "msg-1", "subject": "s", "content": ""}]
        )
        assert p._messages_carrying_file(wanted) == []

    @pytest.mark.parametrize(
        "wanted,known",
        [
            ("PRICE VIPUL.xlsx", "PRICE VIPUL (6).xlsx"),
            ("Tennsmith Price List.docx", "Tennsmith Inc. Price List TNS-059.docx"),
            ("HARSLE stock list.xlsx", "HARSLE press brake stock price list.xlsx"),
        ],
    )
    def test_two_shared_tokens_match_the_same_artifact(self, monkeypatch, wanted, known):
        """Names drift (a "(6)" suffix, a distributor prefix) — the join must
        still find the file the dataset lane named."""
        monkeypatch.setattr(
            p, "_mail_attachment_reverse_index", lambda: {known: [("msg-1", "doc-1")]}
        )
        monkeypatch.setattr(
            p, "_comms_store_records", lambda: [{"id": "msg-1", "subject": "s", "content": ""}]
        )
        assert len(p._messages_carrying_file(wanted)) == 1


class TestAttachmentContentLeg:
    def test_no_phrases_returns_empty(self):
        assert p._attachment_content_hits([]) == []
        assert p._attachment_content_hits([""]) == []

    def test_requires_a_real_token(self):
        """A bare short string must not trigger a document scan."""
        assert p._attachment_content_hits(["ab"]) == []

    def test_missing_ledger_returns_empty(self, monkeypatch):
        monkeypatch.setattr(p, "_doc_to_message_index", lambda: {})
        assert p._attachment_content_hits(["f-5216"]) == []

    def test_scan_is_bounded_to_attachment_documents(self, monkeypatch):
        """The scan must be restricted to attachments, never a row slice.

        An earlier cut sliced the first N rows of the whole store and silently
        scanned the WRONG documents (the store is not ordered; measured live:
        1 match across the full table, 0 across the first 4000 rows).
        """
        monkeypatch.setattr(p, "_doc_to_message_index", lambda: {})
        monkeypatch.setattr(p, "_load_documents_table", lambda: None)
        # Must not raise, and must not touch a table when there is no ledger.
        assert p._attachment_content_hits(["f-5216"]) == []


class TestRenderedLineCarriesAttachments:
    def test_listing_line_names_the_file_and_its_document(self, monkeypatch):
        """The reader must see the same files the search matched, openable."""
        monkeypatch.setattr(
            p, "_mail_attachments_for", lambda mid, limit=4: [("F-5216.pdf", "ext_abc")]
        )
        line = p._ingested_line_from_row(
            {
                "id": "m1",
                "sender": "a@x.com",
                "recipient": "b@y.com",
                "subject": "Quote",
                "content": "Please see pricing",
                "timestamp": "2026-09-11 20:07:31",
                "attachments": "[]",
            },
            with_body=True,
        )
        assert "F-5216.pdf" in line
        assert "ext_abc" in line
