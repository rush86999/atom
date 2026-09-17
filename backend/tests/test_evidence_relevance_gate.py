# -*- coding: utf-8 -*-
"""A block from an OLDER request must not stand as this turn's evidence.

RCA 2026-09-17 findings 2 and 4. The canvas-edit leg's plan was reused by the
reply leg with no relevance check, so the turn answered from an unrelated search:
the persisted plan was `outlook.search 'PRICE VIPUL price list attachment'` for a
request about a vendor scorecard, its observation led with unrelated RFQ PDFs, and
the reply then claimed a value from a document no store contained — while denying
evidence the system had held one turn earlier.

There was no relevance gate and no corrective retrieval. This is the gate. It is
deliberately CONSERVATIVE, because rejecting a good block is worse than accepting
a poor one — it would throw away the turn's evidence.
"""
import pytest

from integrations.chat_orchestrator import (
    _evidence_addresses_request,
    _evidence_rejected,
)


class TestGateRejectsMismatchedEvidence:
    def test_the_rca_case_is_rejected(self):
        block = ("- [ingested mailbox] From: sales@x.com | RE: RFQ PDF | "
                 "received: 2026-09-16 | September 16 RFQ attachments")
        assert not _evidence_addresses_request(
            block, "search the vendor scorecard for reliability 0.87"
        )

    def test_excerpts_with_no_shared_term_are_rejected(self):
        block = "- [ingested mailbox] From: a@b.com | hello | received: 2026-01-01"
        assert not _evidence_addresses_request(
            block, "find the Tennsmith warranty document"
        )

    def test_an_empty_block_addresses_nothing(self):
        assert not _evidence_addresses_request("", "any request")
        assert not _evidence_addresses_request("   ", "any request")


class TestGateAcceptsWhatShouldStand:
    def test_a_shared_distinctive_term_is_accepted(self):
        block = "- [ingested mailbox] From: s@x.com | PRICE VIPUL | received: 2026-09-16"
        assert _evidence_addresses_request(
            block, "which emails carried the PRICE VIPUL price list"
        )

    def test_a_quoted_figure_matches(self):
        block = ("- [ingested mailbox] From: joel@seguinmach.com | FW: RFQ | "
                 "$ 5,350.00 - 10 % in stock")
        assert _evidence_addresses_request(
            block, "search for this one: $ 5,350.00 - 10 % in stock"
        )

    def test_openable_full_evidence_is_accepted(self):
        """The model can open it and check; a literal term match is not required."""
        block = ("- [ingested mailbox] From: a@b.com | quote | full: "
                 "knowledge/conversations/XYZ | FULL BODY: ...")
        assert _evidence_addresses_request(block, "a differently phrased request")

    def test_structured_answers_are_accepted(self):
        """Dataset/SQL/formula blocks carry their own provenance."""
        for block in (
            "SQL RESULT from 'wb.xlsx' sheet 'Sheet1' (query-verified copy)",
            "DATASET CATALOG — derivation inputs",
            "FORMULAS FOR THE MATCHED ROW(S) — the derivation",
            "APP DB ANSWER (read-only NL→SQL over allowlisted tables",
        ):
            assert _evidence_addresses_request(block, "an unrelated sounding ask"), block

    def test_a_request_with_no_distinctive_terms_is_never_rejected(self):
        assert _evidence_addresses_request("some block", "do it again")


class TestRejectionIsLogged:
    def test_rejection_is_reported_not_silent(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            rejected = _evidence_rejected(
                "- [ingested mailbox] From: a@b.com | hello | received: 2026-01-01",
                "find the Tennsmith warranty document",
            )
        assert rejected
        assert any("evidence-gate" in r.message for r in caplog.records), (
            "the reason must be visible in the trace"
        )

    def test_an_empty_block_is_not_a_rejection(self):
        """No evidence is the caller's own case; only MISMATCHED evidence is ours."""
        assert _evidence_rejected("", "any request") is False
