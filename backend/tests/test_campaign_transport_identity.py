"""Transport -> intake regression: only a provider response echo is identity.

``model_provenance.accepted_transport_call`` used to synthesize
``response_identity`` from the served route. These focused cases drive the real
transport writers (BYOK response-echo capture, route attribution, campaign
journal sink), the durable route-decision adapter and the intake gate. No
network, provider or live database is touched.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("TESTING", "1")

from core.employee_benchmark_evidence import (
    REASON_IDENTITY_MISSING,
    activate_campaign_journal,
    deactivate_campaign_journal,
    open_campaign_transport_journal,
)
from core.employee_campaign_intake import (
    accepted_calls_missing_identity,
    accepted_transport_calls,
    record_campaign_evidence,
)
from core.llm.byok_handler import BYOKHandler
from core.llm.model_provenance import (
    clear_route_attribution,
    get_route_attribution,
    set_echoed_response_model,
    set_requested_route,
    set_resolved_model,
    set_served_route,
)

REQUESTED = {"provider": "ollama", "model": "llama3.1:8b"}
SERVED = {"provider": "ollama", "model": "llama3.1:8b-instruct-q4_K_M"}


@pytest.fixture(autouse=True)
def _clean_attribution():
    clear_route_attribution()
    yield
    clear_route_attribution()


def _transport():
    return get_route_attribution()["transport"]


def test_accepted_call_without_response_echo_has_no_identity():
    set_requested_route(REQUESTED["provider"], REQUESTED["model"])
    set_served_route(SERVED["provider"], SERVED["model"])

    attribution = get_route_attribution()
    transport = attribution["transport"]

    # The call is still recorded as accepted — it did serve a response — but it
    # carries no identity because the response metadata echoed no model.
    assert transport["accepted"] is True
    assert transport["response_identity"] is None
    # Normal route telemetry is preserved unchanged.
    assert transport["served_route"] == SERVED
    assert transport["requested_route"] == REQUESTED
    assert attribution["served_route"] == SERVED
    assert attribution["requested_route"] == REQUESTED
    assert attribution["error"] is None


def test_response_identity_comes_from_provider_echo_not_served_route():
    echoed = "llama3.1:8b-instruct-q4_K_M-2026-11"
    set_requested_route(REQUESTED["provider"], REQUESTED["model"])
    set_echoed_response_model(echoed)
    set_resolved_model(echoed)
    set_served_route(SERVED["provider"], SERVED["model"])

    transport = _transport()

    # Identity is the model in the provider's response metadata; the served
    # route keeps the route actually accepted for normal telemetry.
    assert transport["response_identity"] == {
        "provider": SERVED["provider"], "model": echoed}
    assert transport["served_route"] == SERVED
    assert transport["resolved_model"] == echoed


def test_echo_is_consumed_once_and_never_leaks_into_a_retry():
    set_echoed_response_model("first-echo")
    set_served_route("alpha", "first-model")
    assert _transport()["response_identity"] == {
        "provider": "alpha", "model": "first-echo"}

    # A later accepted call in the same context had no fresh echo: it must be
    # reported as identity-less, not inherit the previous attempt's model.
    set_served_route("beta", "second-model")
    transport = _transport()
    assert transport["served_route"] == {
        "provider": "beta", "model": "second-model"}
    assert transport["response_identity"] is None


def test_new_attempt_discards_the_previous_pending_echo():
    set_echoed_response_model("stale-echo")
    set_requested_route("alpha", "next-attempt")
    set_served_route("alpha", "next-attempt")

    assert _transport()["response_identity"] is None


def test_response_without_a_model_clears_the_previous_pending_echo():
    BYOKHandler._capture_echoed_model(SimpleNamespace(model="old-echo"))
    BYOKHandler._capture_echoed_model(SimpleNamespace(choices=[]))

    set_served_route("alpha", "next-attempt")

    assert _transport()["response_identity"] is None


def test_byok_capture_supplies_identity_from_raw_response_metadata():
    response = SimpleNamespace(model="raw-response-echo", choices=[])

    BYOKHandler._capture_echoed_model(response)
    set_served_route("alpha", "requested-model")

    transport = _transport()
    assert transport["response_identity"] == {
        "provider": "alpha", "model": "raw-response-echo"}
    assert transport["resolved_model"] == "raw-response-echo"


def test_legacy_served_route_is_audit_only_not_response_identity():
    from api.assignment_routes import _routing_history_entry

    entry = _routing_history_entry(
        {
            "mode": "pinned",
            "requested_route": dict(REQUESTED),
            "served_route": dict(SERVED),
        },
        stage="employee_proposal",
        attempt_id="legacy-transport",
    )

    assert entry["accepted"] is True
    assert entry["served_route"] == SERVED
    assert entry["response_identity"] is None


def test_route_decision_without_echo_reaches_intake_as_missing_identity(
        tmp_path):
    from api.assignment_routes import _routing_history_entry

    set_requested_route(REQUESTED["provider"], REQUESTED["model"])
    set_served_route(SERVED["provider"], SERVED["model"])
    decision = _routing_history_entry(
        get_route_attribution(),
        stage="employee_proposal",
        attempt_id="attempt-no-echo",
    )

    assert decision["accepted"] is True
    assert decision["response_identity"] is None
    assert accepted_transport_calls([decision]) == []
    assert [
        item["call_id"]
        for item in accepted_calls_missing_identity([decision])
    ] == ["attempt-no-echo"]

    result = record_campaign_evidence(
        db_path=tmp_path / "absent.db",
        execution_id="exec-no-echo",
        campaign="employee-heldout-two-domain",
        observation={},
        completed_at=None,
        decisions=[decision],
    )
    assert result["status"] == "rejected"
    assert REASON_IDENTITY_MISSING in result["reasons"]


def test_campaign_sink_records_missing_echo_as_accepted_without_identity():
    journal = open_campaign_transport_journal(
        campaign_id="employee-heldout-two-domain",
        execution_id="exec-no-echo",
    )
    activate_campaign_journal(journal)
    try:
        set_requested_route(REQUESTED["provider"], REQUESTED["model"])
        set_served_route(SERVED["provider"], SERVED["model"])
    finally:
        deactivate_campaign_journal()

    entry = journal.entries[0]
    assert entry["accepted"] is True
    assert entry["requested_route"] == REQUESTED
    assert entry["served_route"] == SERVED
    assert entry["response_identity"] is None


def test_campaign_sink_records_the_provider_echo_not_the_served_route():
    journal = open_campaign_transport_journal(
        campaign_id="employee-heldout-two-domain",
        execution_id="exec-echo",
    )
    activate_campaign_journal(journal)
    try:
        set_requested_route(REQUESTED["provider"], REQUESTED["model"])
        set_echoed_response_model("provider-echo-model")
        set_served_route(SERVED["provider"], SERVED["model"])
    finally:
        deactivate_campaign_journal()

    entry = journal.entries[0]
    assert entry["served_route"] == SERVED
    assert entry["response_identity"] == {
        "provider": SERVED["provider"], "model": "provider-echo-model"}
