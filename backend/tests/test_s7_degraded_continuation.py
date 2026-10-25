"""S7 degraded continuation — durable facts survive an unavailable model.

The captured attempt-14 failure was a date-only follow-up whose
interpretation timed out. The deterministic floor kept the request but
lost the named source, and the message-shaped fallback marked the narrow
ask broad. These tests pin the replacement contract:

* a source NAMED by the request and already OBSERVED resolves without a
  model;
* several candidates stay ambiguous (never insertion-order);
* a genuinely broad follow-up keeps its whole-document obligation;
* a narrow ask never inherits a prior turn's broader contract;
* no named source / no observation composes nothing;
* a resolved interpretation is untouched (its constraints win).
"""
from __future__ import annotations

from core.turn_decision import (
    apply_degraded_continuation_references,
    apply_interpretation_references,
    build_turn_decision,
    deterministic_continuation_ready,
    interpretation_deterministic_continuation,
    session_observed_sources,
    turn_evidence_required,
)

S7_ASK = ("What is the current Valid until date on the draft, and does it "
          "still match the approved record?")
BROAD_ASK = ("Compare the draft quotation with my uploaded Approved "
             "Records document. Does the Valid Until date match? Flag "
             "anything that differs.")
PRIOR_FILE = "approved_records_q2026_114.txt"
PRIOR_FILE_2 = "approved_records_q2026_115.txt"
OTHER_FILE = "Quote confirmation.pdf"


def _degraded():
    return {
        "schema": "turn-interpretation-1",
        "request_id": "req-degraded",
        "origin": "unresolved",
        "unresolved_reason": "stage_budget_exhausted",
        "message": S7_ASK,
        "actions": [],
        "subjects": [],
        "sources": [],
        "requested_fields": [],
        "output_format": "",
        "constraints": [],
        "scope_change": "unresolved",
        "confidence": 0.0,
        "deterministic_decision": None,
    }


def _session(observed_files=(), requested=None):
    session = {}
    if observed_files:
        session["_retrieval_source_observations_prior"] = [{
            "observation_id": f"obs-{i}",
            "source": "ingested",
            "file_name": name,
            "title": name,
            "workspace_id": "ws-1",
            "content_hash": "",
        } for i, name in enumerate(observed_files)]
    if requested is not None:
        session["_evidence_requirement_prior"] = requested
    return session


def _compose(message=S7_ASK, observed_files=(PRIOR_FILE,), requested=None,
             interpretation=None):
    session = _session(observed_files, requested)
    decision = build_turn_decision(message, session, [])
    composed = apply_degraded_continuation_references(
        decision, interpretation if interpretation is not None
        else _degraded(), session, message)
    return decision, composed, session


def _requirement(composed, message=S7_ASK, accepted=None, monkeypatch=None):
    import integrations.chat_orchestrator as co

    if monkeypatch is not None:
        monkeypatch.setattr(
            co, "_resolve_requirement_identity",
            lambda names, workspace_id: {
                "state": "resolved",
                "file_id": "doc-captured",
                "file_name": (names or [""])[0],
            })
    return co._build_evidence_requirement(
        composed, message, True, workspace_id="ws-1",
        canvas_attached=True,
        accepted_request=accepted if accepted is not None else _degraded())


def test_captured_date_only_turn_resolves_the_named_source(monkeypatch):
    decision, composed, session = _compose(
        observed_files=(PRIOR_FILE, OTHER_FILE))
    assert decision["references"]["sources"] == []
    marker = composed["references"]["continuation_evidence"]
    assert marker["state"] == "resolved", marker
    assert marker["resolved_file"] == PRIOR_FILE
    assert composed["references"]["file"] == {"file_name": PRIOR_FILE}
    assert composed["references"]["sources"] == ["document"]
    assert turn_evidence_required(composed) is True

    req = _requirement(composed, monkeypatch=monkeypatch)
    assert req["required"] is True, req
    assert req["sources"] == ["document"], req
    assert req["fields"] == ["expiration_date"], req
    assert req["broader_comparison"] is False, req
    assert req["identity"]["state"] == "resolved", req
    assert req["identity"]["file_name"] == PRIOR_FILE, req
    assert req["artifact_attached"] is True, req


def test_ambiguous_source_preserves_every_candidate(monkeypatch):
    _decision, composed, _session_ = _compose(
        observed_files=(PRIOR_FILE, PRIOR_FILE_2))
    marker = composed["references"]["continuation_evidence"]
    assert marker["state"] == "ambiguous", marker
    assert "file" not in composed["references"] or not (
        composed["references"].get("file"))
    names = sorted(str(c.get("file_name"))
                   for c in (marker.get("candidates") or []))
    assert names == [PRIOR_FILE, PRIOR_FILE_2], marker

    req = _requirement(composed, monkeypatch=monkeypatch)
    assert req["required"] is True, req
    assert req["identity"]["state"] == "ambiguous", req
    names = sorted(str(c.get("file_name"))
                   for c in (req["identity"].get("candidates") or []))
    assert names == [PRIOR_FILE, PRIOR_FILE_2], req


def test_genuinely_broad_followup_keeps_the_whole_document_obligation(
        monkeypatch):
    _decision, composed, _session_ = _compose(message=BROAD_ASK)
    req = _requirement(composed, message=BROAD_ASK, monkeypatch=monkeypatch)
    assert req["fields"] == ["expiration_date"], req
    assert req["broader_comparison"] is True, req


def test_date_only_followup_does_not_inherit_a_prior_broad_contract(
        monkeypatch):
    prior = {
        "required": True,
        "sources": ["document"],
        "fields": ["expiration_date"],
        "broader_comparison": True,
        "identity": {"state": "kind_only", "candidates": []},
        "artifact_attached": True,
    }
    _decision, composed, _session_ = _compose(requested=prior)
    req = _requirement(composed, monkeypatch=monkeypatch)
    assert req["broader_comparison"] is False, req


def test_named_source_identifier_is_preserved(monkeypatch):
    message = ("Does the Valid until date still match the approved "
               "record A?")
    _decision, composed, _session_ = _compose(
        message=message,
        observed_files=("approved_records_A.txt",
                        "approved_records_B.txt"))
    marker = composed["references"]["continuation_evidence"]
    assert marker["state"] == "resolved", marker
    assert marker["resolved_file"] == "approved_records_A.txt", marker

    _decision, unresolved, _session_ = _compose(
        message=message, observed_files=("approved_records_B.txt",))
    marker = unresolved["references"]["continuation_evidence"]
    assert marker["state"] == "unresolved", marker
    assert "approved_records_B.txt" not in str(marker)
    assert unresolved["references"].get("file") is None


def test_no_named_source_changes_nothing():
    decision, composed, _session_ = _compose(message="What is the status?")
    assert composed["references"] == decision["references"]
    assert turn_evidence_required(composed) is False


def test_no_observed_evidence_changes_nothing():
    decision, composed, _session_ = _compose(observed_files=())
    assert composed["references"] == decision["references"]
    assert turn_evidence_required(composed) is False


def test_prior_requirement_carrier_is_never_evidence():
    prior = {
        "required": True,
        "sources": ["document"],
        "fields": ["expiration_date"],
        "identity": {"state": "resolved",
                     "file_name": PRIOR_FILE},
        "artifact_attached": True,
    }
    decision, composed, session = _compose(
        observed_files=(), requested=prior)
    assert session_observed_sources(session) == []
    assert composed["references"] == decision["references"]


def test_bounded_date_only_turn_is_ready_without_a_model():
    session = _session((PRIOR_FILE, OTHER_FILE))
    decision = build_turn_decision(S7_ASK, session, [])
    ready = deterministic_continuation_ready(S7_ASK, session, decision)
    assert ready is not None, (
        "a named, uniquely observed source plus one canonical field is "
        "the bounded shape that needs no interpretation")
    assert ready["fields"] == ["expiration_date"], ready
    assert ready["reference"]["resolved_file"] == PRIOR_FILE, ready
    record = interpretation_deterministic_continuation(
        S7_ASK, "req-det", decision, ready["reference"])
    assert record["origin"] == "deterministic:continuation", record
    assert record["sources"] == [PRIOR_FILE], record
    assert record["scope_change"] == "continue", record


def test_broad_turn_is_not_fast_pathed():
    session = _session((PRIOR_FILE,))
    decision = build_turn_decision(BROAD_ASK, session, [])
    assert deterministic_continuation_ready(
        BROAD_ASK, session, decision) is None, (
        "a whole-document obligation stays on the interpretation path")


def test_ambiguous_or_mutating_turn_is_not_fast_pathed():
    session = _session((PRIOR_FILE, PRIOR_FILE_2))
    decision = build_turn_decision(S7_ASK, session, [])
    assert deterministic_continuation_ready(
        S7_ASK, session, decision) is None
    one = _session((PRIOR_FILE,))
    mixed = ("Update the payment terms to Net 30 and tell me whether the "
             "Valid until date still matches the approved record.")
    decision = build_turn_decision(mixed, one, [])
    assert deterministic_continuation_ready(mixed, one, decision) is None


def test_resolved_interpretation_is_untouched():
    session = _session((PRIOR_FILE,))
    decision = build_turn_decision(S7_ASK, session, [])
    resolved = dict(_degraded())
    resolved.update({"origin": "llm:test-model",
                     "scope_change": "continue",
                     "sources": ["approved record A"]})
    composed = apply_degraded_continuation_references(
        decision, resolved, session, S7_ASK)
    assert composed["references"] == decision["references"], (
        "a resolved interpretation's own constraints must stay "
        "authoritative; the degraded fallback must not preempt it")
    # And the existing unresolved-interpretation composer still composes
    # nothing on its own.
    assert apply_interpretation_references(
        decision, _degraded(), session)["references"] == (
            decision["references"])
