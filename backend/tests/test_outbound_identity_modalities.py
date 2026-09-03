"""Cross-modality outbound-attribution eval — the user's question was
"these fixes seem email specific; what about other communication or task
contexts?" This suite is the regression answer: adversarial fixtures per
artifact type (IM send, task assignment, calendar event, CRM ownership)
plus the false-positive guards (mentions are not attributions).

The gate under test keys on (a) outbound action verbs and (b) attribution
param keys — so a search mentioning a person, or a message BODY mentioning
a person, can never fire it by construction. Each case here is that
construction, pinned.
"""

import pytest

from core.outbound_identity import (
    check_tool_call_attribution,
    tool_call_identity_status,
)

PRIMARY = {"name": "Rish Maniar", "email": "rish@brennan.ca"}
TEAM = [
    PRIMARY,
    {"name": "Chandrakant Sharma", "email": "chandrakant@brennan.ca"},
    {"name": "Vipul Chopra", "email": "vipul@brennan.ca"},
]


def verdict(service, action, params):
    return tool_call_identity_status(service, action, params, PRIMARY, TEAM)


# ── IM / chat sends ──────────────────────────────────────────────────────────

def test_slack_post_without_attribution_never_fires():
    assert verdict("slack", "post_message", {"channel": "C123", "text": "Hi"}) is None


def test_slack_message_body_mention_is_not_attribution():
    # Mentioning the lead in the BODY is fine — attribution lives in params.
    assert verdict("slack", "post_message", {
        "channel": "C123",
        "text": "Mark Kellam asked about the bandsaw",
    }) is None


def test_slack_send_as_external_user_is_caught():
    v = verdict("slack", "post_message", {"as_user": "Mark Kellam", "text": "Hi"})
    assert v and v["status"] == "external" and v["field"] == "as_user"


def test_slack_send_as_teammate_flags_teammate():
    v = verdict("slack", "post_message", {"as_user": "Vipul Chopra", "text": "Hi"})
    assert v and v["status"] == "teammate"


def test_handle_form_of_owner_passes():
    assert verdict("slack", "post_message", {"as_user": "@rish", "text": "Hi"}) is None


# ── task assignment ──────────────────────────────────────────────────────────

def test_task_assigned_to_external_lead_is_caught():
    v = verdict("asana", "create_task", {
        "assignee": "Mark Kellam", "title": "Follow up on bandsaw",
    })
    assert v and v["status"] == "external" and v["field"] == "assignee"


def test_task_assigned_to_owner_passes():
    assert verdict("asana", "create_task", {
        "assignee": "Rish M.", "title": "Follow up on bandsaw",
    }) is None


def test_task_assigned_to_teammate_flags_teammate():
    v = verdict("trello", "assign_task", {"assigned_to": "Chandrakant Sharma"})
    assert v and v["status"] == "teammate"


# ── calendar ─────────────────────────────────────────────────────────────────

def test_calendar_organizer_external_email_is_caught():
    v = verdict("outlook", "create_event", {
        "organizer": "jschulz@blumetric.ca", "subject": "Bandsaw call",
    })
    assert v and v["status"] == "external" and v["field"] == "organizer"


def test_calendar_organizer_owner_email_passes():
    assert verdict("outlook", "create_event", {
        "organizer": "rish@brennan.ca", "subject": "Bandsaw call",
    }) is None


# ── CRM ownership ────────────────────────────────────────────────────────────

def test_crm_deal_owner_external_is_caught():
    v = verdict("zoho", "update_deal", {"owner": "Mark Kellam", "amount": 1000})
    assert v and v["status"] == "external"


# ── searches and reads must never fire ───────────────────────────────────────

def test_search_mentioning_person_never_fires():
    assert verdict("outlook", "search_emails", {"query": "Mark Kellam bandsaw"}) is None
    assert verdict("slack", "search_history", {"query": "Mark Kellam"}) is None
    assert verdict("asana", "search_tasks", {"query": "assignee: Mark Kellam"}) is None


def test_non_outbound_action_with_attribution_key_still_does_not_fire():
    # Reading a profile that happens to carry an "owner" field is a read,
    # not an outbound attribution.
    assert verdict("zoho", "get_record", {"owner": "Mark Kellam", "id": "x"}) is None


# ── value shapes ─────────────────────────────────────────────────────────────

def test_dict_valued_attribution_param_is_unwrapped():
    v = verdict("smtp", "send_email", {"from": {"name": "Mark Kellam"}})
    assert v and v["status"] == "external"


def test_non_person_values_are_ignored():
    assert verdict("slack", "post_message", {"as_user": True, "text": "Hi"}) is None
    assert verdict("asana", "create_task", {"assignee": "team-42"}) is None


# ── chokepoint wiring (fault isolation + mode) ──────────────────────────────

@pytest.mark.asyncio
async def test_chokepoint_returns_none_when_gate_off(monkeypatch):
    import core.outbound_identity as oi

    monkeypatch.setattr(oi, "outbound_identity_mode", lambda: "off")
    result = await check_tool_call_attribution(
        "slack", "post_message", {"as_user": "Mark Kellam"}, {"user_id": "u"},
    )
    assert result is None


@pytest.mark.asyncio
async def test_chokepoint_carries_mode_and_survives_resolution_failure(monkeypatch):
    import core.outbound_identity as oi

    monkeypatch.setattr(oi, "outbound_identity_mode", lambda: "enforce")
    monkeypatch.setattr(
        oi, "collect_team_signers_cached",
        lambda *a, **k: {"primary": PRIMARY, "team": TEAM},
    )
    result = await oi.check_tool_call_attribution(
        "asana", "create_task", {"assignee": "Mark Kellam"},
        {"user_id": "u", "tenant_id": "default"},
    )
    assert result["status"] == "external" and result["mode"] == "enforce"

    # Resolution failure must never break the send path.
    def _boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(oi, "collect_team_signers_cached", _boom)
    assert await oi.check_tool_call_attribution(
        "asana", "create_task", {"assignee": "Mark Kellam"}, {"user_id": "u"},
    ) is None
