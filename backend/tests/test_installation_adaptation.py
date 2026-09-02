"""Installation Adaptation Plan — Phases 1-5 unit tests.

Anchored on the live incident (canvas da27bb76…, 2026-09-02): the
"Chandrakant" signature, the unverified "480V 3-phase available" claim,
the template-questions rewrites, and the no-op "nothing changed" turn are
the canonical cases the taxonomy, eval properties, and send gate must
handle. SQLite-per-test; no LLM, no provider keys.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.failure_taxonomy import classify_correction, property_for
from core.installation_profile_service import InstallationProfileService
from core.incident_eval_service import evaluate_property, generate_from_correction
from core.playbook_service import PlaybookService, playbook_mode
from core.correction_reflection_service import reflect_on_correction
from core.send_grounding import (
    check_grounding,
    extract_assertions,
    gate_send,
)

CANVAS_ID = "da27bb76-3f37-4f15-9f40-16c61b37b595"


@pytest.fixture()
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    from core.models import Base
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)
    session = Sess()
    try:
        yield session
    finally:
        session.close()
        eng.dispose()
        os.unlink(path)


# ───────────── Phase 2: failure taxonomy ─────────────

def test_taxonomy_identity_signature_name_changed():
    before = {"body": "Regards,\nChandrakant\nBrennan Machinery"}
    after = {"body": "Regards,\nRish M.\nBrennan Machinery"}
    label, signals = classify_correction(before, after)
    assert label == "identity"
    assert "signature_or_name_changed" in signals


def test_taxonomy_grounding_assertion_softened():
    before = "Yes, the machines we discussed are available in 480V 3-phase configuration."
    after = "We are confirming 480V 3-phase availability and will follow up with specs."
    label, _ = classify_correction(before, after)
    assert label == "grounding"


def test_taxonomy_process_template_questions_added():
    before = "Hi Mark, we will help you choose a machine. Best regards, Rish"
    after = ("Hi Mark, could you confirm:\n"
             "- The material type and grade?\n"
             "- The cross-sectional dimensions?\n"
             "Best regards, Rish")
    label, _ = classify_correction(before, after)
    assert label == "process"


def test_taxonomy_tone_small_wording():
    before = "We can help you pick the right machine"
    after = "We can help you select the right machine"
    label, _ = classify_correction(before, after)
    assert label == "tone"


def test_taxonomy_persistence_identical():
    label, _ = classify_correction("same text", "same text")
    assert label == "persistence"


def test_properties_match_classes():
    before = {"body": "Regards,\nChandrakant"}
    after = {"body": "Regards,\nRish M."}
    prop = property_for("identity", before, after)
    assert prop["kind"] == "excludes" and prop["value"] == "Chandrakant"

    before_g = "The machines are available in 480V 3-phase configuration."
    after_g = "We are confirming 480V 3-phase availability."
    prop = property_for("grounding", before_g, after_g)
    assert prop["kind"] == "no_unverified"
    assert "available" in prop["value"].lower()


# ───────────── Phase 2: incident evals ─────────────

def test_generate_dedups_by_fingerprint(db):
    before = {"body": "Regards,\nChandrakant"}
    after = {"body": "Regards,\nRish M."}
    first = generate_from_correction(
        db, "default", CANVAS_ID, "email",
        snapshot={"canvas_type": "email", "title": "T", "content": before},
        original=before, corrected=after, instruction="sign it correctly",
    )
    second = generate_from_correction(
        db, "default", CANVAS_ID, "email",
        snapshot={"canvas_type": "email", "title": "T", "content": before},
        original=before, corrected=after, instruction="sign it correctly",
    )
    assert first.id == second.id
    assert second.occurrences == 2


def test_evaluate_property_excludes_and_includes():
    verdict = evaluate_property(
        {"kind": "excludes", "value": "Chandrakant"},
        {"body": "Regards,\nRish M."}, {"body": "Regards,\nChandrakant"})
    assert verdict["status"] == "pass"

    verdict_fail = evaluate_property(
        {"kind": "excludes", "value": "Chandrakant"},
        {"body": "Regards,\nChandrakant"}, {"body": "Regards,\nRish M."})
    assert verdict_fail["status"] == "fail"

    verdict_inc = evaluate_property(
        {"kind": "includes", "value": "The material type and grade"},
        {"body": "please confirm:\nThe material type and grade?"},
        {"body": "hi"})
    assert verdict_inc["status"] == "pass"


def test_evaluate_no_unverified_blocks_assertive_claim():
    prop = {"kind": "no_unverified", "value": "available"}
    bad = {"body": "the machines are available in 480V 3-phase configuration."}
    good = {"body": "we are confirming 480V 3-phase availability."}
    assert evaluate_property(prop, bad, {}).get("status") == "fail"
    assert evaluate_property(prop, good, {}).get("status") == "pass"


# ───────────── Phase 1: installation profile ─────────────

def test_profile_get_or_create_and_merge_write(db):
    svc = InstallationProfileService(db)
    payload = svc.get_payload("default")
    assert payload["identity"] == {}

    svc.update_payload("default", {
        "identity": {"company_name": "Brennan Machinery Inc."},
        "facts": [{"claim": "480V 3-phase available", "source": "spec sheet",
                   "verified": True}],
    })
    fresh = InstallationProfileService(db).get_payload("default")
    assert fresh["identity"]["company_name"] == "Brennan Machinery Inc."
    assert len(fresh["facts"]) == 1
    # merge-write: updating people must not wipe facts
    svc.update_payload("default", {"people": [{"name": "Mark Kellam", "role": "dealer"}]})
    after = svc.get_payload("default")
    assert after["facts"] and after["people"][0]["role"] == "dealer"


def test_profile_fact_allows_normalization(db):
    svc = InstallationProfileService(db)
    svc.update_payload("default", {
        "facts": [{"claim": "480V 3-phase configuration available", "verified": True}],
    })
    assert svc.fact_allows("default", "available in 480V 3 phase configuration") is not None
    assert svc.fact_allows("default", "220V single phase available") is None


# ───────────── Phase 3: playbooks ─────────────

def test_playbook_states_and_retrieval(db):
    svc = PlaybookService(db, tenant_id="default")
    row = svc.create(
        "Bandsaw selection",
        trigger_canvas_type="email",
        trigger_keywords=["bandsaw", "machine"],
        template_questions=["The material type and grade?"],
        approval_state="approved",
    )
    hit = svc.get_relevant("choosing a bandsaw for a customer",
                           canvas_type="email")
    assert hit and hit[0]["name"] == "Bandsaw selection"
    assert "material type" in str(hit[0]["template_questions"])

    miss = svc.get_relevant("quarterly tax filing", canvas_type="document")
    assert miss == []

    # draft playbooks never enter prompts
    svc.create("Unapproved", source="learned", approval_state="draft")
    assert svc.get_relevant("unapproved", canvas_type="email") == []
    assert len(svc.list(include_drafts=True)) == 2


def test_playbook_mode_flag_gates_retrieval(db, monkeypatch):
    svc = PlaybookService(db, tenant_id="default")
    svc.create("P", trigger_keywords=["anything"], approval_state="approved")
    import core.playbook_service as pbs

    monkeypatch.setattr(pbs, "playbook_mode", lambda: "off")
    assert svc.get_relevant("anything") == []
    monkeypatch.setattr(pbs, "playbook_mode", lambda: "shadow")
    assert svc.get_relevant("anything")


def test_playbook_from_teach_and_pattern_draft_dedup(db):
    svc = PlaybookService(db, tenant_id="default")
    row = svc.create_from_teach(
        "Before quoting voltage, always ask: what material? what dimensions?",
        trigger_canvas_type="email",
    )
    assert row.approval_state == "draft" and row.source == "taught"
    assert row.template_questions

    first = svc.draft_from_pattern("always ask material first", origin_id="x1")
    assert first.approval_state == "draft"
    same = svc.find_by_pattern("always ask material first")
    assert same.id == first.id
    bumped = svc.draft_from_pattern("always ask material first", origin_id="x2")
    assert bumped.id == first.id and bumped.version == 2


# ───────────── Phase 4: reflection + grounded send ─────────────

def test_reflection_creates_and_bumps_draft(db):
    before = {"body": "Regards,\nChandrakant"}
    after = {"body": "Regards,\nRish M."}
    row = reflect_on_correction(db, "default", CANVAS_ID, "email",
                                before, after, "identity",
                                instruction="mark is dealer")
    assert row.approval_state == "draft" and row.source == "learned"
    again = reflect_on_correction(db, "default", CANVAS_ID, "email",
                                  before, after, "identity")
    assert again.id == row.id and again.version == 2
    # a different class on the same canvas is a DIFFERENT lesson
    other = reflect_on_correction(db, "default", CANVAS_ID, "email",
                                  before, after, "grounding")
    assert other.id != row.id


def test_send_grounding_extracts_and_blocks_the_480v_case(db):
    # The live incident body: assertive availability claim, no registry entry.
    body = ("Hi Mark,<br><br>Yes, the machines we discussed are available "
            "in 480V 3-phase configuration.")
    findings = extract_assertions(body)
    assert findings and "available" in findings[0]

    verdict = check_grounding(body, facts=[], playbook_covered=False)
    assert verdict.outcome == "block"

    # Hedged wording passes.
    hedged = "We are confirming 480V 3-phase availability and will follow up."
    assert check_grounding(hedged, facts=[]).outcome == "pass"

    # A verified facts-registry entry passes.
    assert check_grounding(
        body,
        facts=[{"claim": "480V 3-phase configuration available",
                "verified": True}]).outcome == "pass"

    # Signature boilerplate is not an assertion.
    assert check_grounding(
        "Regards,<br>All quotes are valid for 15 days only, thank you.",
        facts=[]).outcome == "pass"


def test_send_grounding_gate_modes(db, monkeypatch):
    import core.send_grounding as sg

    body = "The machines are available in 480V 3-phase configuration."
    monkeypatch.setattr(sg, "grounding_mode", lambda: "off")
    assert gate_send(db, "default", body)["mode"] == "off"
    assert gate_send(db, "default", body)["blocked"] is False

    monkeypatch.setattr(sg, "grounding_mode", lambda: "shadow")
    shadow = gate_send(db, "default", body)
    assert shadow["mode"] == "shadow" and shadow["outcome"] == "block"
    assert shadow["blocked"] is False  # shadow never blocks

    monkeypatch.setattr(sg, "grounding_mode", lambda: "enforce")
    enforced = gate_send(db, "default", body)
    assert enforced["blocked"] is True
    overridden = gate_send(db, "default", body, override=True)
    assert overridden["blocked"] is False and overridden["override"] is True


# ───────────── Phase 5: metrics ─────────────

def test_installation_metrics_report(db):
    from core.installation_metrics import report
    from core.models import CanvasContext, ChatMessage

    svc = PlaybookService(db, tenant_id="default")
    svc.create("PB", approval_state="approved")
    before = {"body": "Regards,\nChandrakant"}
    after = {"body": "Regards,\nRish M."}
    generate_from_correction(db, "default", CANVAS_ID, "email", {},
                             before, after, instruction="fix signature")
    db.add(CanvasContext(canvas_id=CANVAS_ID, tenant_id="default",
                         canvas_type="email", user_id="u1",
                         user_corrections=[{"original": {}, "corrected": {}}]))
    for i, text in enumerate(("mark is the dealer", "mark is the dealer")):
        db.add(ChatMessage(conversation_id="c1", tenant_id="default",
                           role="user", content=text))
    db.commit()

    out = report(db, tenant_id="default", window_days=30)
    assert out["corrections"]["total_all_time"] >= 1
    assert out["corrections"]["taxonomy_distribution_window"].get("identity", 0) >= 1
    assert out["repeated_feedback"]["repeats"] >= 1
    assert out["playbooks"]["total"] == 1
    assert out["evals"]["total_cases"] >= 1


# ───────────── wiring: capture path → evals + reflection ─────────────

def test_correction_capture_files_eval_and_reflection(db):
    """PUT /api/canvas/{id} → record_user_correction must ALSO file the
    regression case and the draft lesson — that is the loop that makes
    per-install learning automatic."""
    from core.models import CanvasContext, IncidentEval, Playbook
    from services.canvas_context_service import CanvasContextService

    db.add(CanvasContext(canvas_id=CANVAS_ID, tenant_id="default",
                         canvas_type="email", user_id="u1"))
    db.commit()

    ok = CanvasContextService(db, tenant_id="default").record_user_correction(
        canvas_id=CANVAS_ID,
        user_id="u1",
        original_action={"type": "canvas_edit",
                         "content": {"body": "Regards,\nChandrakant"},
                         "author": "agent"},
        corrected_action={"type": "canvas_edit",
                          "content": {"body": "Regards,\nRish M."},
                          "author": "supervisor"},
        context_info="mark is the dealer",
    )
    assert ok
    evals = db.query(IncidentEval).filter(
        IncidentEval.canvas_id == CANVAS_ID).all()
    assert evals and evals[0].taxonomy == "identity"
    drafts = db.query(Playbook).filter(
        Playbook.source == "learned").all()
    assert drafts and drafts[0].approval_state == "draft"


# ───────────── wiring: the runner replays against a fake planner ─────────────

def _fake_llm_returning(plan):
    from unittest.mock import AsyncMock, MagicMock
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(return_value=plan)
    return llm


@pytest.mark.asyncio
async def test_runner_replays_and_checks_property(db):
    from core.models import IncidentEval
    from core.incident_eval_runner import run_evals
    from core.chat_canvas_editor import CanvasEditPlan

    snapshot = {"canvas_type": "email", "title": "T",
                "content": {"body": "Regards,\nChandrakant"}}
    row = IncidentEval(
        tenant_id="default", canvas_id=CANVAS_ID, canvas_type="email",
        taxonomy="identity", instruction="fix the signature",
        context_snapshot=snapshot,
        expected_property={"kind": "excludes", "value": "Chandrakant"},
        source="correction", fingerprint="fp-test-1",
    )
    db.add(row)
    db.commit()

    # The planner replays the bug: it signs "Chandrakant" again → fail.
    bad_plan = CanvasEditPlan(
        wants_edit=True, edit_mode="replace",
        updated_content_json='{"body": "Regards,\\nChandrakant"}')
    summary = await run_evals(db, tenant_id="default",
                              llm_service=_fake_llm_returning(bad_plan))
    assert summary["failed"] == 1 and summary["passed"] == 0

    # The fixed planner leaves the wrong name out → pass.
    good_plan = CanvasEditPlan(
        wants_edit=True, edit_mode="replace",
        updated_content_json='{"body": "Regards,\\nRish M."}')
    summary = await run_evals(db, tenant_id="default",
                              llm_service=_fake_llm_returning(good_plan))
    assert summary["failed"] == 0 and summary["passed"] == 1


# ───────────── wiring: playbooks reach the editor prompt ─────────────

@pytest.mark.asyncio
async def test_editor_prompt_carries_playbook_steps_and_questions():
    from unittest.mock import AsyncMock, MagicMock

    from core.chat_canvas_editor import CanvasEditPlan, plan_canvas_edit

    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(
        return_value=CanvasEditPlan(wants_edit=False))
    canvas = {"canvas_id": "c-1", "canvas_type": "email", "title": "T",
              "content": {"body": "draft"}}
    plan = await plan_canvas_edit(
        "draft a reply to the bandsaw inquiry", [], canvas, llm,
        playbooks=[{"name": "Bandsaw selection", "steps": ["ask before quoting"],
                    "template_questions": ["The material type and grade?"]}],
    )
    assert plan is not None
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "COMPANY PLAYBOOKS" in prompt
    assert "Bandsaw selection" in prompt
    assert "The material type and grade?" in prompt
