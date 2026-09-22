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

    def test_a_structured_block_is_not_auto_accepted(self):
        """A marker says what SHAPE the data is, never what question it answers.

        This test previously asserted the opposite — that any SQL/dataset/formula
        block is accepted regardless of the request. Review R3 found that exact
        bypass: an unrelated inventory SQL block was accepted for a
        vendor-scorecard ask. The marker is not provenance.
        """
        for block in (
            "SQL RESULT from inventory.xlsx: rows=42",
            "DATASET CATALOG — derivation inputs",
            "FORMULAS FOR THE MATCHED ROW(S) — some other row",
            "APP DB ANSWER (read-only NL→SQL over allowlisted tables)",
        ):
            assert not _evidence_addresses_request(
                block, "search the vendor scorecard for reliability 0.87"
            ), block

    def test_a_structured_block_that_shares_a_term_is_accepted(self):
        """Provenance is the shared subject, not the marker."""
        assert _evidence_addresses_request(
            "DATASET CATALOG — searched for 'PRICE VIPUL' (74 files)",
            "which emails carried the PRICE VIPUL price list",
        )

    def test_the_archived_wrong_topic_observation_is_rejected(self):
        """The block from execution 75cda6e1-f880-4f40-ac77-47002734d9bd.

        It answered a PRICE VIPUL query while the request was about a vendor
        scorecard. Its own header states the query, and the two share no
        distinctive term — which is what the gate must catch, rather than being
        satisfied by the `full:` marker it also carried.
        """
        block = (
            "LIVE TOOL RESULTS (outlook.search, query=\"PRICE VIPUL price list "
            "attachment\"):\n"
            "- [ingested mailbox] From: sales@x.com | September 16 RFQ PDFs | "
            "full: knowledge/conversations/AAA"
        )
        assert not _evidence_addresses_request(
            block, "search the vendor scorecard for reliability 0.87"
        )

    def test_a_request_with_no_distinctive_terms_is_never_rejected(self):
        # A contentless NON-conversational request ("hi") fail-opens: there is
        # no term to mismatch against and no approval to resolve.
        assert _evidence_addresses_request("some block", "hi")

    def test_an_unresolved_approval_does_not_validate_evidence(self):
        """2026-09-22 correction: a bare approval names no subject.

        Without a resolvable referent it must NOT fail-open arbitrary evidence
        — that would let an unrelated or stale search stand behind a "yes go
        ahead". The empty-terms fail-open is reserved for turns that are not
        unresolved conversational approvals."""
        assert not _evidence_addresses_request("unrelated block", "yes go ahead")
        assert _evidence_rejected("unrelated block", "yes go ahead") is True


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


class TestRegressionFromTheReview:
    """Defects the 2026-09-17 review reproduced, pinned so they stay fixed."""

    def test_the_archived_wrong_topic_block_is_rejected_despite_its_marker(self):
        """R3's bypass: ANY `full:` marker used to accept a block.

        The archived observation from execution 75cda6e1 answered a PRICE VIPUL
        query while the request was about a vendor scorecard. Its header states
        that query; the two share no distinctive term.
        """
        block = ('LIVE TOOL RESULTS (outlook.search, query="PRICE VIPUL price '
                 'list attachment"):\n- [ingested mailbox] From: a@b.com | '
                 'September 16 RFQ PDFs | full: knowledge/conversations/AAA')
        assert not _evidence_addresses_request(
            block, "search the vendor scorecard for reliability 0.87"
        )

    def test_an_unrelated_sql_block_is_rejected(self):
        """A marker says what SHAPE the data is, not what it answers."""
        assert not _evidence_addresses_request(
            "SQL RESULT from inventory.xlsx: rows=42",
            "search the vendor scorecard for reliability 0.87",
        )

    def test_a_block_whose_own_query_matches_is_accepted(self):
        """The declared query is provenance — when it matches, accept."""
        block = ('LIVE TOOL RESULTS (outlook.search, query="PRICE VIPUL price '
                 'list attachment"):\n- [ingested mailbox] | PRICE VIPUL.xlsx')
        assert _evidence_addresses_request(
            block, "which emails carried the PRICE VIPUL price list"
        )

    def test_evidence_with_no_declared_query_still_accepts_openable_sources(self):
        """Not every lane declares a query; the model can open and check."""
        assert _evidence_addresses_request(
            "LIVE TOOL RESULTS: full: knowledge/conversations/AAA | RFQ docs",
            "find the foot shear thread",
        )


MACHINERY_HISTORY = [
    {"message": "Steve Macisaac machinery requested",
     "response": {"message": "I found 8 mailbox hits. Want me to pull the "
                             "full machinery list?"}},
]
MACHINERY_BLOCK = (
    'LIVE TOOL RESULTS (outlook.search, query="Steve Macisaac machinery '
    'requested"):\n- [ingested mailbox] From: s@x.com | Fw: machinery '
    'listing | full: knowledge/conversations/BBB'
)


class TestLineageResolution:
    """2026-09-22: a follow-up legitimately consumes evidence originating in
    the request it approves. Lineage establishes RELEVANCE ONLY."""

    def test_the_incident_block_is_accepted_via_resolved_history(self):
        # Zero lexical overlap between "yes go ahead" and the block — the
        # resolved topic (message + the offer's exchange) carries it.
        assert _evidence_addresses_request(
            MACHINERY_BLOCK, "yes go ahead", MACHINERY_HISTORY)

    def test_lineage_acceptance_keeps_marker_and_outcome_honesty(self):
        # Guardrail: lineage establishes relevance, not completeness — the
        # block still says what it is; the gate does not rewrite provenance.
        from integrations.chat_orchestrator import _evidence_relevance

        assert _evidence_relevance(
            MACHINERY_BLOCK.replace("full: knowledge/conversations/BBB",
                                    "preview only — not read"),
            "yes go ahead", MACHINERY_HISTORY,
        ) == "addresses"

    def test_stale_out_of_lineage_block_is_still_rejected(self):
        # The RCA 2026-09-17 protection survives: an OLD request's block,
        # outside the resolved lineage, must not stand behind this turn.
        stale_history = [
            {"message": "search the PRICE VIPUL price list attachment",
             "response": {"message": "Here are the price list hits."}},
            {"message": "search the vendor scorecard for reliability 0.87",
             "response": {"message": "Working on the scorecard."}},
        ]
        stale_block = (
            'LIVE TOOL RESULTS (outlook.search, query="PRICE VIPUL price '
            'list attachment"):\n- [ingested mailbox] From: sales@x.com | '
            'September 16 RFQ PDFs | full: knowledge/conversations/AAA'
        )
        assert not _evidence_addresses_request(
            stale_block, "search the vendor scorecard for reliability 0.87",
            stale_history)
        assert _evidence_rejected(
            stale_block, "search the vendor scorecard for reliability 0.87",
            stale_history) is True

    def test_zero_overlap_with_an_older_request_is_unproven_not_mismatch(self):
        """A query that merely BEST-matches an older request is not proof of
        incompatibility — MISMATCH needs the byte-identical provenance
        conflict, everything else lexical is UNPROVEN."""
        from integrations.chat_orchestrator import _evidence_relevance

        history = [
            {"message": "check the consolidated price list for WG-350",
             "response": {"message": "Here is the price list row."}},
        ]
        block = (
            'LIVE TOOL RESULTS (outlook.search, query="consolidated price '
            'list for WG-350 details"):\n- [ingested mailbox] excerpts only'
        )
        # Shares WG-350 with the current ask → declared check passes on the
        # shared code; but with a current ask naming NOTHING from it, the
        # verdict must be unproven, never mismatch.
        verdict = _evidence_relevance(
            block, "what about the press brake availability", history)
        assert verdict == "unproven"

    def test_explicit_provenance_conflict_is_mismatch(self):
        from integrations.chat_orchestrator import _evidence_relevance

        history = [
            {"message": "PRICE VIPUL price list attachment",
             "response": {"message": "Here are the price list hits."}},
            {"message": "now search the vendor scorecard for reliability 0.87",
             "response": {"message": "Working on the scorecard."}},
        ]
        stale_block = (
            'LIVE TOOL RESULTS (outlook.search, query="PRICE VIPUL price '
            'list attachment"):\n- [ingested mailbox] From: sales@x.com | '
            'September 16 RFQ PDFs'
        )
        # Declared query byte-identical to the recorded OUT-OF-LINEAGE
        # request, zero overlap with the current topic → explicit conflict.
        assert _evidence_relevance(
            stale_block, "search the vendor scorecard for reliability 0.87",
            history) == "mismatch"

    def test_multi_id_read_header_is_accepted_regardless_of_length(self):
        """A three-id read header exceeds the declared-query capture cap; the
        id-directed rule reads the header line, so the block still stands."""
        from integrations.chat_orchestrator import _evidence_relevance

        ids = "A" * 60 + " message_id: " + "B" * 59 + "=1 message_id: " + "C" * 60
        block = (
            f"LIVE TOOL RESULTS (outlook.read_emails, query='message_id: {ids}')\n"
            "- READ OK (FULL BODY) | message_id: " + "A" * 60 + "\nbody text"
        )
        assert _evidence_relevance(
            block, "yes go ahead", MACHINERY_HISTORY) == "addresses"

    def test_resolved_topic_overrides_the_bare_message_for_lexical_checks(self):
        # "yes, excluding the slitter" — the qualification rides in the topic
        # and a block matching the machinery subject passes.
        block = (
            'LIVE TOOL RESULTS (outlook.search, query="Steve Macisaac '
            'machinery requested"):\n- preview line, not read in full'
        )
        assert _evidence_addresses_request(
            block, "yes go ahead, only September", MACHINERY_HISTORY)
