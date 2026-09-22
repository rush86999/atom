# -*- coding: utf-8 -*-
"""Mail direction: "internal/external" and "sent/received" are DIFFERENT dimensions.

Audit directive 6. The previous logic collapsed them — a same-domain message was
labelled "internal — neither an inbound customer message nor a send to a
counterparty" and the sent-vs-received question was never answered, so an
acceptance case asking about the direction of a forwarded attachment got no
answer.

* INTERNAL/EXTERNAL is an organizational relationship: domain equality.
* SENT/RECEIVED is about THIS MAILBOX: is the sender (or a recipient) one of its
  own addresses?

Per-install identity is DATA (CLAUDE.md invariant #4), so mailbox membership is
derived from the store's own traffic — on this install the signed-in account is
an administrative address on a different domain from the shared team mailbox, so
keying on the account's domain found nothing and everything read "cannot
determine" (measured 2026-09-16).
"""
import pytest

import core.chat_tool_planner as planner


@pytest.fixture
def mailbox(monkeypatch):
    """A store whose mailbox is on one domain, plus a separate admin account."""
    monkeypatch.setattr(
        planner, "_own_addresses", lambda uid: ["admin@example.com"] if uid else []
    )
    monkeypatch.setattr(
        planner,
        "_mailbox_addresses",
        lambda *a: ["chandrakant@brennan.ca", "rish@brennan.ca", "vipul@brennan.ca"],
    )
    return "u1"


class TestTheTwoDimensions:
    def test_external_received(self, mailbox):
        out = planner._mail_direction("joel@seguinmach.com", "chandrakant@brennan.ca", mailbox)
        assert "external" in out and "RECEIVED by this mailbox" in out

    def test_external_sent_by_a_colleague(self, mailbox):
        """A colleague sending outward IS the mailbox sending."""
        out = planner._mail_direction(
            "chandrakant@brennan.ca", "kurt@neimanmachinery.com", mailbox
        )
        assert "external" in out and "SENT by this mailbox" in out

    def test_external_sent_from_the_account_address(self, mailbox):
        out = planner._mail_direction("admin@example.com", "joel@seguinmach.com", mailbox)
        assert "SENT by this mailbox" in out

    def test_member_to_member_is_not_called_sent_or_received(self, mailbox):
        """Both ends own: direction depends on WHICH member — say so.

        Reporting SENT here would mislabel a colleague's message that the
        operator merely received, which is the exact failure this dimension
        exists to prevent.
        """
        out = planner._mail_direction(
            "vipul@brennan.ca", "chandrakant@brennan.ca", mailbox
        )
        assert "internal" in out
        assert "SENT by this mailbox" not in out
        assert "RECEIVED by this mailbox" not in out
        assert "which member" in out.lower()

    def test_an_internal_message_is_still_attributed_to_its_sender(self, mailbox):
        out = planner._mail_direction("rish@brennan.ca", "vipul@brennan.ca", mailbox)
        assert "internal" in out

    def test_unknown_both_ends_asserts_nothing(self, mailbox):
        out = planner._mail_direction("a@other.com", "b@other.com", mailbox)
        assert "cannot be determined" in out
        assert "SENT" not in out and "RECEIVED" not in out

    def test_without_identity_it_reports_inability_rather_than_guessing(self, monkeypatch):
        monkeypatch.setattr(planner, "_own_addresses", lambda uid: [])
        monkeypatch.setattr(planner, "_mailbox_addresses", lambda *a: [])
        out = planner._mail_direction("a@brennan.ca", "b@brennan.ca", None)
        assert "internal relationship" in out
        assert "cannot be determined" in out


class TestDomainEqualityIsNotDirection:
    def test_same_domain_alone_never_yields_sent_or_received(self, monkeypatch):
        """The core confusion, pinned: internal != sent."""
        monkeypatch.setattr(planner, "_own_addresses", lambda uid: [])
        monkeypatch.setattr(planner, "_mailbox_addresses", lambda *a: [])
        out = planner._mail_direction("x@same.com", "y@same.com", None)
        assert "internal" in out
        assert "SENT by this mailbox" not in out
        assert "RECEIVED by this mailbox" not in out


class TestScopeOfANegativeClaim:
    """Negative claims are bounded — by a DETERMINISTIC GUARD, not by prompt prose.

    RCA 2026-09-17: "None that we sent" narrowed the user's own scope to external
    recipients, and "No file with that name exists in the system" exceeded the
    lookup that was actually run.

    Division of labour, deliberately split so the same policy is not stated twice
    (two overlapping mechanisms in one prompt is worse than one):

    * the EVIDENCE supplies the FACT that makes the wrong answer wrong — an
      internal member send is outgoing, so a scope-narrowed "none" is refuted by
      the data itself;
    * ``core.absence_guard`` supplies the ENFORCEMENT — it detects a universal
      absence claim the delivered evidence does not cover and forces a scoped
      regeneration. Prompt prose cannot enforce anything; that guard can.
    """

    def test_the_evidence_states_that_an_internal_send_is_outgoing(self, mailbox):
        """The fact the model needs, without a second policy paragraph."""
        out = planner._mail_direction(
            "rish@brennan.ca", "chandrakant@brennan.ca", mailbox
        )
        assert "internal" in out
        assert "still counts" in out and "outgoing" in out

    def test_the_grounding_rule_points_at_coverage_without_restating_policy(self):
        from core.chat_tool_planner import _GROUNDING_RULE

        assert "as wide as the search performed" in _GROUNDING_RULE
        # the policy itself lives in one place (the guard), not two
        assert "COMPLETE coverage" not in _GROUNDING_RULE
        # (these two pins are deliberately duplicated here from
        # test_planner_catalog_contracts.py to keep the division-of-labour
        # story in one file)

    def test_the_guard_enforces_what_the_prose_only_describes(self):
        """End-to-end: an uncovered universal claim is caught deterministically."""
        from core.absence_guard import uncovered_absence_claims

        evidence = (
            "LIVE TOOL RESULTS (deterministic mailbox scan):\n"
            "- [ingested mailbox] From: joel@seguinmach.com | FW: RFQ | $ 5,350.00"
        )
        over_claim = "None that we sent carried that price list."
        assert uncovered_absence_claims(over_claim, evidence), (
            "the guard must catch a universal claim the evidence does not cover"
        )
        scoped = "The scan found one message carrying that price list."
        assert not uncovered_absence_claims(scoped, evidence), (
            "a scoped statement must pass — the guard may not block honest answers"
        )
        # hedged honesty is likewise exempt: reporting what THIS search did
        # must never trip a regeneration
        assert not uncovered_absence_claims(
            "I did not find another one in the mailbox scan above.", evidence
        )

    def test_a_claim_the_evidence_covers_is_allowed(self):
        from core.absence_guard import uncovered_absence_claims

        evidence = (
            "LIVE TOOL RESULTS (memory.search):\n"
            "- [document: ingested] PRICE VIPUL (6).xlsx | WORKBOOK INDEX"
        )
        # the RCA sentence itself, verb-mediated ("contains no") — detected
        # since 2026-09-21; before that it was invisible to every detector
        # and this test passed with ANY evidence (vacuous)
        assert not uncovered_absence_claims(
            "PRICE VIPUL contains no scorecard sheet.", evidence
        ), "a claim about the subject the evidence names is covered"
