# -*- coding: utf-8 -*-
"""Request-reference resolution: what a conversational turn points at.

Live 2026-09-22 incident: a SUCCESSFUL mailbox search for "Steve Macisaac
machinery requested" was validated against the follow-up "yes go ahead" —
tokenized to the single distinctive term "ahead" — so the evidence gate
rejected the block and the reply claimed the lookup had failed. These pins
cover the resolver the gates now share: active-offer selection with exchange
boundaries, fulfillment detection, ordinals, qualified approvals, and the
verdict integration (RESOLVED judged on the topic; unresolved approvals never
lexically declined).
"""
from core.plan_relevance import (
    REF_AMBIGUOUS,
    REF_DIRECT,
    REF_RESOLVED,
    REF_UNRESOLVED,
    _delivery_confirmed,
    relevance_verdict,
    resolve_request_reference,
)


HISTORY = [
    {"message": "Steve Macisaac machinery requested",
     "response": {"message": "I found 8 mailbox hits. Want me to pull the "
                             "full machinery list?"}},
]


class TestIncidentShape:
    def test_approval_resolves_to_the_active_offer(self):
        ref = resolve_request_reference("yes go ahead", HISTORY)
        assert ref.kind == REF_RESOLVED
        # Current message leads (authoritative); referent appended.
        assert ref.topic_text.startswith("yes go ahead")
        assert "machinery" in ref.topic_text
        assert "Steve Macisaac machinery requested" in ref.lineage_requests

    def test_verdict_accepts_the_original_query_with_history(self):
        assert relevance_verdict(
            "Steve Macisaac machinery requested", "yes go ahead",
            history=HISTORY,
        ) == "relevant"

    def test_bare_approval_without_history_is_never_declined(self):
        # The incident's latent no-history path: lexical absence from a bare
        # approval is not proof of mismatch.
        assert relevance_verdict(
            "Steve Macisaac machinery requested", "yes go ahead",
        ) == "unknown"


class TestActiveOfferSelection:
    def test_exchange_boundary_deactivates_the_old_offer(self):
        history = [
            {"message": "find the WG-350 specs",
             "response": {"message": "I can pull those from the catalog."}},
            {"message": "now the vendor scorecard",
             "response": {"message": "Opening it."}},
        ]
        ref = resolve_request_reference("yes go ahead", history)
        # The old "I can pull specs" offer is INACTIVE (superseded); the
        # approval attaches to the NEWEST exchange, never the older offer.
        assert ref.kind == REF_RESOLVED
        assert "vendor scorecard" in ref.topic_text
        assert "WG-350" not in ref.topic_text

    def test_fulfilled_offer_does_not_capture_a_second_approval(self):
        history = [
            {"message": "machinery list?",
             "response": {"message": "I can pull the machinery list."}},
            {"message": "yes go ahead",
             "response": {"message": "Here is the full machinery list."}},
        ]
        ref = resolve_request_reference("yes go ahead", history)
        assert ref.kind == REF_RESOLVED
        assert "machinery" in ref.topic_text

    def test_older_offers_are_never_resurrected_across_a_boundary(self):
        history = [
            {"message": "draft the renewal email",
             "response": {"message": "I can draft the renewal email."}},
            {"message": "switching topics: the Q3 budget sheet",
             "response": {"message": "Found it. The sheet says 12,400."}},
        ]
        ref = resolve_request_reference("yes go ahead", history)
        assert ref.kind == REF_RESOLVED
        assert "budget" in ref.topic_text
        assert "renewal" not in ref.topic_text


class TestFulfillmentDetection:
    """User-pinned: a bare "sent" inside a negation or a potential must NOT
    deactivate an offer."""

    def test_plain_delivery_confirms(self):
        assert _delivery_confirmed("I sent the list") is True
        assert _delivery_confirmed("was sent this morning") is True
        assert _delivery_confirmed("has been sent to Steve") is True

    def test_negated_delivery_is_not_delivery(self):
        assert _delivery_confirmed("it was not sent") is False
        assert _delivery_confirmed("never sent the file") is False

    def test_potential_delivery_is_not_delivery(self):
        assert _delivery_confirmed("it can be sent now") is False
        assert _delivery_confirmed("the draft will be sent after review") is False

    def test_presentation_confirms(self):
        assert _delivery_confirmed("Here is the full machinery list.") is True


class TestOrdinals:
    def test_grounded_ordinal_resolves_to_the_list_item(self):
        history = [{"message": "options",
                    "response": {"message": "1. the foot shear\n"
                                            "2. the slitter\n"
                                            "3. the press"}}]
        ref = resolve_request_reference("yes, the second one", history)
        assert ref.kind == REF_RESOLVED
        assert "slitter" in ref.topic_text

    def test_ungrounded_ordinal_is_ambiguous(self):
        history = [{"message": "options",
                    "response": {"message": "several machines are available"}}]
        ref = resolve_request_reference("yes, the second one", history)
        assert ref.kind == REF_AMBIGUOUS
        assert ref.clarify_reason == "ungrounded_ordinal"
        assert ref.candidates  # clarify material exists


class TestQualifiedApprovals:
    def test_exclusion_survives_into_the_topic(self):
        ref = resolve_request_reference("yes, excluding the slitter", HISTORY)
        assert ref.kind == REF_RESOLVED
        assert "slitter" in ref.topic_text
        assert "machinery" in ref.topic_text

    def test_time_qualification_survives(self):
        ref = resolve_request_reference("yes go ahead, only September", HISTORY)
        assert ref.kind == REF_RESOLVED
        assert "September" in ref.topic_text


class TestReferentialWithoutOffers:
    def test_referential_resolves_to_the_active_topic_without_offer_marker(self):
        history = [{"message": "find the Seguin RFQ thread",
                    "response": {"message": "Found 3 messages in the thread."}}]
        ref = resolve_request_reference("read that email again", history)
        assert ref.kind == REF_RESOLVED
        assert "Seguin" in ref.topic_text


class TestNonApprovalShapes:
    def test_question_is_never_an_approval(self):
        assert resolve_request_reference(
            "ok so what about the price", HISTORY).kind == REF_DIRECT

    def test_substantive_request_is_direct(self):
        assert resolve_request_reference(
            "search my email for the Tennsmith warranty document",
            None).kind == REF_DIRECT

    def test_approval_with_no_history_is_unresolved_for_clarify(self):
        ref = resolve_request_reference("yes go ahead", None)
        assert ref.kind == REF_UNRESOLVED
        assert ref.clarify_reason == "no_history"
