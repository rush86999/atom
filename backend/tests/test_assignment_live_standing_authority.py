"""Real-transport bounded authority is opt-in and double-gated.

No live send is performed here: this pins the configuration predicate that the
executor uses before it would ever dispatch the Outlook adapter.
"""
from __future__ import annotations

from types import SimpleNamespace

from core.assignment_executor import AssignmentExecutor
from core.assignment_plan import (
    new_assignment, new_step, new_teaching_snapshot,
    normalize_standing_authority,
)


def _assignment():
    grant = normalize_standing_authority(
        {"actions": ["outbound"], "max_effects": 1,
         "recipients": ["bounded@example.invalid"]},
        granted_by="owner-1")
    step = new_step(
        step_id="send", title="Send", operation_type="outbound",
        adapter="email.send_outlook",
        inputs={"to": ["bounded@example.invalid"], "subject": "S",
                "body": "B"},
        effect="external", approval_required=True,
        standing_authorization=f"grant:{grant['grant_id']}")
    return new_assignment(
        objective="Live bounded authority probe",
        employee_id="owner-1", workspace_id="ws-1", tenant_id="tenant-1",
        teaching_snapshot=new_teaching_snapshot(revision="live-probe"),
        steps=[step], authorized_actions=["outbound"],
        standing_authority=grant), step


def test_live_standing_authority_requires_both_flags(monkeypatch):
    executor = AssignmentExecutor.__new__(AssignmentExecutor)
    executor.adapters = __import__(
        "core.assignment_executor", fromlist=["default_adapter_registry"]
    ).default_adapter_registry
    assignment, step = _assignment()
    adapter = executor.adapters.get("email.send_outlook")
    assert adapter is not None

    monkeypatch.delenv("ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", raising=False)
    monkeypatch.delenv(
        "ATOM_ASSIGNMENT_ALLOW_STANDING_LIVE_SEND", raising=False)
    assert executor._adapter_allows_standing(adapter) is False
    assert executor._standing_grant_covers(assignment, step) is None

    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", "1")
    assert executor._adapter_allows_standing(adapter) is False
    assert executor._standing_grant_covers(assignment, step) is None

    monkeypatch.setenv(
        "ATOM_ASSIGNMENT_ALLOW_STANDING_LIVE_SEND", "1")
    assert executor._adapter_allows_standing(adapter) is True
    covered = executor._standing_grant_covers(assignment, step)
    assert covered is not None
    assert covered["grant_id"] == assignment["standing_authority"]["grant_id"]


def test_recipient_outside_the_live_grant_is_not_covered(monkeypatch):
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_LIVE_SEND", "1")
    monkeypatch.setenv("ATOM_ASSIGNMENT_ALLOW_STANDING_LIVE_SEND", "1")
    executor = AssignmentExecutor.__new__(AssignmentExecutor)
    executor.adapters = __import__(
        "core.assignment_executor", fromlist=["default_adapter_registry"]
    ).default_adapter_registry
    assignment, step = _assignment()
    step["inputs"]["to"] = ["other@example.invalid"]
    assert executor._standing_grant_covers(assignment, step) is None
