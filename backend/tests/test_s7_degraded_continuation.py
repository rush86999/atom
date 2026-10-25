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


def test_sole_identity_noun_is_never_stripped_to_a_bare_adjective():
    """`approved record` must not fall through to `approved` and bind an
    unrelated approved_quotation.pdf. The sole source noun is identity."""
    _decision, composed, _session_ = _compose(
        observed_files=("approved_quotation.pdf",))
    marker = composed["references"]["continuation_evidence"]
    assert marker["state"] == "unresolved", marker
    assert "approved_quotation.pdf" not in str(marker)
    assert composed["references"].get("file") is None


def test_generic_floor_kind_is_refined_only_by_the_named_reference(
        monkeypatch):
    """A generic `document` capture is a nomination, not an identity. A
    named reference that does not match must not leave kind_only and let
    an unrelated purchase_order.pdf complete the date comparison."""
    message = ("Does the Valid until date on the draft still match the "
               "approved record document?")
    session = _session(("purchase_order.pdf",))
    decision = build_turn_decision(message, session, [])
    composed = apply_degraded_continuation_references(
        decision, _degraded(), session, message)
    marker = composed["references"]["continuation_evidence"]
    assert marker["state"] == "unresolved", marker
    assert composed["references"].get("file") is None
    req = _requirement(composed, message=message, monkeypatch=monkeypatch)
    assert req["identity"]["state"] == "unresolved", req
    assert req["identity"].get("names") == ["approved record"], req


def test_mixed_source_family_is_not_certified_from_one_family(monkeypatch):
    """The turn names the approved record and `my email`: the receipt must
    preserve the unaccounted family rather than bind kind_only to either."""
    message = ("Also check my email. Does the Valid until date still match "
               "the approved record?")
    session = _session(("approved_records_q2026_114.txt",))
    session["_retrieval_source_observations_prior"].append({
        "observation_id": "email-1",
        "source": "communication",
        "file_name": "thread-42.eml",
        "title": "thread-42",
        "workspace_id": "ws-1",
        "content_hash": "",
    })
    decision = build_turn_decision(message, session, [])
    assert "email" in (decision["references"]["sources"] or [])
    composed = apply_degraded_continuation_references(
        decision, _degraded(), session, message)
    marker = composed["references"]["continuation_evidence"]
    assert marker["state"] == "unresolved", marker
    assert composed["references"].get("file") is None
    req = _requirement(composed, message=message, monkeypatch=monkeypatch)
    assert req["identity"]["state"] == "unresolved", req
    assert req["identity"].get("names") == ["approved record"], req


def test_resolved_empty_source_record_is_filled_from_the_named_reference(
        monkeypatch):
    """A schema-valid model record with sources=[] made NO source
    decision. It must not erase the request's named reference into
    kind_only; the deterministic fill supplies the same binding the
    degraded path would."""
    session = _session((PRIOR_FILE,))
    decision = build_turn_decision(S7_ASK, session, [])
    empty = dict(_degraded())
    empty.update({
        "origin": "llm:test-model",
        "scope_change": "continue",
        "sources": [],
    })
    composed = apply_degraded_continuation_references(
        decision, empty, session, S7_ASK, fill_missing_source=True)
    marker = composed["references"]["continuation_evidence"]
    assert marker["state"] == "resolved", marker
    assert composed["references"]["file"] == {"file_name": PRIOR_FILE}
    req = _requirement(composed, accepted=empty, monkeypatch=monkeypatch)
    assert req["required"] is True, req
    assert req["identity"]["state"] == "resolved", req
    assert req["identity"]["file_name"] == PRIOR_FILE, req


def test_floor_file_plus_named_record_is_an_unresolved_mixed_obligation(
        monkeypatch):
    message = ("Does the Valid until date in catalog_2019.xlsx match the "
               "draft and the approved record?")
    session = _session((PRIOR_FILE,))
    decision = build_turn_decision(message, session, [])
    assert decision["references"].get("file")
    composed = apply_degraded_continuation_references(
        decision, _degraded(), session, message)
    marker = composed["references"]["continuation_evidence"]
    assert marker["state"] == "unresolved", marker
    assert marker.get("mixed_source_families") == (
        "floor_file_and_named_reference"), marker
    req = _requirement(composed, message=message, monkeypatch=monkeypatch)
    assert req["identity"]["state"] == "unresolved", req
    assert req["identity"]["names"] == ["approved record"], req
    _floor_file = req.get("file") or {}
    assert "catalog_2019.xlsx" in str(
        _floor_file.get("name") or _floor_file.get("file_name") or ""), req


def test_bare_back_reference_resolves_the_sole_observed_source():
    for message in (
            "Does the Valid until date still match the same document?",
            "Does the Valid until date still match the record?",
            "Does the Valid until date still match the file?"):
        _decision, composed, _session_ = _compose(
            message=message, observed_files=(PRIOR_FILE,))
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "resolved", (message, marker)
        assert marker["resolved_file"] == PRIOR_FILE, (message, marker)

    _decision, ambiguous, _session_ = _compose(
        message="Does the Valid until date still match the same document?",
        observed_files=(PRIOR_FILE, OTHER_FILE))
    marker = ambiguous["references"]["continuation_evidence"]
    assert marker["state"] == "ambiguous", marker


def test_casual_source_mention_is_not_an_evidence_request():
    message = "Thanks, the approved record was helpful."
    session = _session((PRIOR_FILE,))
    decision = build_turn_decision(message, session, [])
    composed = apply_degraded_continuation_references(
        decision, _degraded(), session, message)
    assert composed["references"] == decision["references"]
    assert turn_evidence_required(composed) is False


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


def test_concrete_date_difference_stays_narrow_and_fast_pathed(monkeypatch):
    """`any date difference` is a concrete field scope, not a
    whole-document obligation. It must stay narrow AND get the bounded
    refinement instead of the full interpretation wait."""
    message = ("Compare the valid until date and flag any date difference "
               "with the approved record.")
    session = _session((PRIOR_FILE,))
    decision = build_turn_decision(message, session, [])
    assert deterministic_continuation_ready(
        message, session, decision) is not None
    composed = apply_degraded_continuation_references(
        decision, _degraded(), session, message)
    req = _requirement(composed, message=message, monkeypatch=monkeypatch)
    assert req["broader_comparison"] is False, req


def test_compound_action_vetoes_cover_bare_objects_and_adjectives():
    one = _session((PRIOR_FILE,))
    for mixed in (
            "Check the valid until date matches the approved record and "
            "prepare summary for the client.",
            "Check the valid until date matches the approved record and "
            "compose reply for the client.",
            "Check the valid until date matches the approved record and "
            "rewrite the summary.",
            "Check the valid until date matches the approved record and "
            "revise the summary.",
            "Check the valid until date matches the approved record and "
            "adjust the terms.",
            "Check the valid until date matches the approved record and "
            "insert the client name."):
        decision = build_turn_decision(mixed, one, [])
        assert deterministic_continuation_ready(
            mixed, one, decision) is None, mixed
    for adjective in (
            "Does the valid until date on the updated draft match the "
            "approved record?",
            "Does the valid until date on the corrected draft match the "
            "approved record?",
            "Does the valid until date on the edited draft match the "
            "approved record?"):
        decision = build_turn_decision(adjective, one, [])
        assert deterministic_continuation_ready(
            adjective, one, decision) is not None, adjective


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
    for mixed in (
            "Update the payment terms to Net 30 and tell me whether the "
            "Valid until date still matches the approved record.",
            "Check that the valid until date matches the approved record "
            "and draft a short email to the client.",
            "Check the valid until date against the approved record and "
            "send it to the client.",
    ):
        decision = build_turn_decision(mixed, one, [])
        assert deterministic_continuation_ready(mixed, one, decision) is None


def test_specific_floor_file_is_not_replaced_by_a_named_record():
    """A workbook mention and a named record are two sources; the fast
    path must not bind the record while the floor owns the workbook."""
    message = ("Does the Valid until date in catalog_2019.xlsx match the "
               "draft and the approved record?")
    session = _session((PRIOR_FILE,))
    decision = build_turn_decision(message, session, [])
    assert decision["references"].get("file"), decision["references"]
    assert deterministic_continuation_ready(
        message, session, decision) is None


def test_broad_phrasings_are_not_fast_pathed_and_stay_broad(monkeypatch):
    messages = (
        "Compare every value on the draft with the approved record.",
        "Compare the price and everything else with the approved record.",
        "Compare the price and tell me about every difference with the "
        "approved record.",
        "Compare the price and don't miss any differences with the "
        "approved record.",
        "Does the price match, and is everything else consistent with the "
        "approved record?",
        "Compare the price and check everything on the draft against the "
        "approved record.",
        "Compare the price and all of it against the approved record.",
        "Compare the price and every part of the draft against the "
        "approved record.",
        "Compare the price and check the rest against the approved record.",
    )
    session = _session((PRIOR_FILE,))
    for message in messages:
        decision = build_turn_decision(message, session, [])
        assert deterministic_continuation_ready(
            message, session, decision) is None, message
        composed = apply_degraded_continuation_references(
            decision, _degraded(), session, message)
        req = _requirement(composed, message=message, monkeypatch=monkeypatch)
        assert req["broader_comparison"] is True, (message, req)


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
