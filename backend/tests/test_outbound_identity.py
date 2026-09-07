"""Outbound identity gate — regression tests for the live 2026-09-02
confabulation: a draft replying to jschulz@blumetric.ca was signed
"Mark Kellam, Sales Representative, Brennan Machinery Inc." — another LEAD
from an earlier turn of the same conversation, upgraded into the sender.

The identity here is what chat_orchestrator._sender_identity resolves: the
account record (Rish Maniar / rish@brennan.ca) plus composer signature.
"""

from core.outbound_identity import (
    identity_rule_block,
    signature_identity_violation,
)

RISH = {"name": "Rish Maniar", "email": "rish@brennan.ca"}


def test_flags_the_live_kellam_confabulation():
    draft = (
        "Yes — I found the thread. Jacob Schulz submitted a quote request…\n\n"
        "To: jschulz@blumetric.ca\n"
        "Subject: Re: Quote Request\n\n"
        "Hi Jacob,\n\nThank you for your inquiry…\n\n"
        "Best regards,  \n"
        "Mark Kellam  \n"
        "Sales Representative  \n"
        "Brennan Machinery Inc.  \n"
        "www.brennan.ca"
    )
    assert signature_identity_violation(draft, RISH) == "Mark Kellam"


def test_flags_chandrakant_colleague_signature():
    # The supervisor's live correction on canvas 4c1986b1: a draft signed by
    # a cc'd COLLEAGUE is still the wrong sender.
    draft = (
        "Hi Jacob,\n\nChandrakant here from Brennan Machinery…\n\n"
        "Best,\nChandrakant Sharma\nBrennan Machinery Inc\n"
    )
    assert signature_identity_violation(draft, RISH) == "Chandrakant Sharma"


def test_accepts_full_name_variant():
    draft = "Hi Jacob,\n\nHere are the specs…\n\nBest regards,\nRish Maniar\nBrennan Machinery Inc."
    assert signature_identity_violation(draft, RISH) is None


def test_accepts_first_name_with_initial():
    draft = "Hi Jacob,\n\n…\n\nRegards,\n\nRish M.\nBrennan Machinery Inc."
    assert signature_identity_violation(draft, RISH) is None


def test_accepts_taught_html_signature_block():
    # The signature learned into the agent's training log (HTML, styled).
    draft = (
        "Hi Jacob,\n\n…<br><br>Regards,<br><br><strong><em>Rish M.</em></strong>"
        "<br><strong><em>Brennan Machinery Inc.</em></strong>"
        '<br><a href="https://www.brennan.ca">www.brennan.ca</a>'
    )
    assert signature_identity_violation(draft, RISH) is None


def test_placeholder_is_not_a_violation():
    draft = "Hi Mark,\n\n…\n\nBest regards,\n\n<b>Your Name</b>\n<b>Brennan Machinery</b>"
    assert signature_identity_violation(draft, RISH) is None


def test_no_signature_block_is_not_a_violation():
    assert signature_identity_violation("Hi Jacob,\n\nCould you share the specs?", RISH) is None


def test_quoted_signature_below_reply_does_not_fire():
    # Top-posted reply quoting the customer's own sign-off deeper in the
    # body — quoting Mark Kellam is fine; SIGNING as him is not.
    draft = (
        "Hi Mark,\n\nCould you confirm the material type?\n\nRegards,\n"
        "Rish M.\nBrennan Machinery Inc.\n\n"
        "--- original message ---\n"
        "Best regards,\nMark Kellam\nWFS Ltd."
    )
    assert signature_identity_violation(draft, RISH) is None


def test_unknown_identity_never_flags():
    assert signature_identity_violation("Regards,\nMark Kellam", None) is None
    assert signature_identity_violation("Regards,\nMark Kellam", {}) is None
    assert signature_identity_violation("Regards,\nMark Kellam", {"email": "x@y.z"}) is None


def test_rule_block_names_the_sender_and_bans_others():
    block = identity_rule_block(RISH)
    assert "Rish Maniar" in block and "rish@brennan.ca" in block
    assert "NEVER sign" in block
    assert identity_rule_block(None) == ""
    assert identity_rule_block({}) == ""


# ── per-install team semantics (fresh-install contract) ──────────────────────
# A fresh installation has a TEAM of members; each member owns and trains
# agents that sign as their OWNER. Allowed senders are tenant DATA (users +
# installation-profile people classified by role/email domain) — never
# hardcoded names.

from core.outbound_identity import (  # noqa: E402
    classify_person_role,
    collect_team_signers,
    signature_signer_status,
)


def test_role_classification_is_data_driven():
    assert classify_person_role("dealer", "mkellam@wfsltd.ca", "brennan.ca") == "external"
    assert classify_person_role("regional vendor", "x@y.z", "brennan.ca") == "external"
    assert classify_person_role("internal", "chandrakant@brennan.ca", "brennan.ca") == "team"
    # Unknown role falls back to the mailbox domain.
    assert classify_person_role("technician", "vipul@brennan.ca", "brennan.ca") == "team"
    assert classify_person_role("technician", "jacob@blumetric.ca", "brennan.ca") == "external"


def test_two_tier_gate_external_vs_teammate():
    primary = {"name": "Rish Maniar", "email": "rish@brennan.ca"}
    team = [primary, {"name": "Chandrakant Sharma", "email": "chandrakant@brennan.ca"}]

    # A teammate's signature is an attribution miss, not a confabulation.
    chandrakant_draft = "Hi Jacob,\n\n…\n\nBest,\nChandrakant Sharma\nBrennan Machinery Inc"
    assert signature_signer_status(chandrakant_draft, primary, team) == (
        "Chandrakant Sharma", "teammate",
    )
    # An off-team signer is the hard confabulation class.
    kellam_draft = "Hi Jacob,\n\n…\n\nBest regards,  \nMark Kellam  \nSales Representative"
    assert signature_signer_status(kellam_draft, primary, team) == ("Mark Kellam", "external")
    # The owner's own signature — primary or any variant — passes.
    assert signature_signer_status("Regards,\nRish M.\nBrennan", primary, team) is None


def test_rule_block_lists_team_and_bans_off_team():
    team = [
        {"name": "Rish Maniar", "email": "rish@brennan.ca"},
        {"name": "Chandrakant Sharma", "email": "chandrakant@brennan.ca"},
        {"name": "Vipul Chopra", "email": "vipul@brennan.ca"},
    ]
    block = identity_rule_block(team[0], team)
    assert "Chandrakant Sharma" in block and "Vipul Chopra" in block
    assert "not on this business's team" in block


def test_collect_team_signers_excludes_external_profile_people():
    """Integration (live dev DB): the installation profile lists a dealer in
    its people section — the team resolver must classify him OUT of the
    team set, purely from the profile's own role data."""
    signers = collect_team_signers(
        session_user_id="00000000-0000-0000-0000-000000000000",  # no such user
        tenant_id="default",
    )
    names = {m["name"].lower() for m in signers["team"]}
    assert "mark kellam" not in names
    if signers["primary"]:
        assert "kellam" not in str(signers["primary"].get("name", "")).lower()


def test_identity_block_includes_styled_signature_html():
    """The styled (raw HTML) signature must reach the drafting prompt so the
    agent reproduces the user's real signature markup in the canvas body —
    the plain-text variant alone is the style-losing shadow (Sept 2026)."""
    from core.outbound_identity import identity_rule_block

    block = identity_rule_block({
        "name": "Rish M.",
        "email": "rish@example.com",
        "signature": "Regards, Rish M.",
        "signature_html": '<div style="font-family:Aptos"><b><i>Rish M.</i></b></div>',
    })
    assert "Their default signature" in block
    assert 'signature_html' in block.lower() or "exact HTML block" in block
    assert "VERBATIM" in block
    assert 'style="font-family:Aptos"' in block


def test_identity_block_without_html_has_no_html_directive():
    from core.outbound_identity import identity_rule_block

    block = identity_rule_block({"name": "Rish M.", "signature": "Regards, Rish M."})
    assert "exact HTML block" not in block
