"""Context-aware teaching transfer controls.

Pure applicability/mapping functions plus real service-boundary persistence:
the lesson journal remains the only store, revisions preserve unrelated
teaching, and a different workspace/agent cannot inherit governing guidance.
"""
from __future__ import annotations

import uuid

from core.artifact_teaching import (
    apply_document_teaching,
    apply_email_teaching,
    apply_presentation_teaching,
    evaluate_lesson_context,
    resolve_artifact_teaching,
    resolve_field_mapping,
)
from core.models import AgentRegistry
from core.student_learning_service import (
    deliver_teacher_lesson,
    format_lessons_block,
    get_agent_lessons,
    journal_standing_lesson_entry,
    list_agent_lessons,
    update_teaching_point,
)


def _agent(db, workspace="ws-a", name="Context Learner"):
    agent = AgentRegistry(
        id=f"ctx-{uuid.uuid4().hex[:8]}", name=name, category="operations",
        description="t", module_path="core.generic_agent",
        class_name="GenericAgent", status="intern", confidence_score=0.5,
        configuration={}, capabilities=[], workspace_id=workspace,
        tenant_id="default",
    )
    db.add(agent)
    db.commit()
    return agent


def _document_lesson(db, agent, **overrides):
    lesson_text = overrides.pop("lesson", "Use the standard report format")
    payload = {
        "topic": "report standard",
        "applies_to": ["document"],
        "format_spec": {
            "font_name": "Arial",
            "font_size": 11,
            "line_spacing": 1.15,
            "heading_order": ["Summary", "Findings", "Sources"],
            "table_columns": ["Item", "Value"],
            "prohibited_terms": ["INTERNAL ONLY"],
        },
        "context": {
            "business_category": "pricing",
            "audience": "internal",
        },
    }
    payload.update(overrides)
    return deliver_teacher_lesson(
        db, agent.id, lesson_text,
        workspace_id=agent.workspace_id, **payload)


def test_equivalent_context_renamed_fields_transfer(db_session):
    agent = _agent(db_session)
    _document_lesson(db_session, agent)
    result = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing", "audience": "internal"},
        workspace_id="ws-a",
    )
    assert result["status"] == "applicable"
    assert result["spec"]["font_size"] == 11
    assert result["spec"]["heading_order"] == ["Summary", "Findings", "Sources"]
    assert "conditions match" in result["explanation"]


def test_similar_topic_wrong_location_does_not_spread(db_session):
    agent = _agent(db_session)
    _document_lesson(db_session, agent, context={
        "business_category": "pricing", "location": "Warehouse B",
    })
    result = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing", "location": "Warehouse A"},
        workspace_id="ws-a",
    )
    assert result["status"] == "not_applicable"
    assert result["spec"] == {}
    assert result["applicability"][0]["conflicts"][0]["key"] == "location"


def test_missing_qualification_needs_targeted_context(db_session):
    agent = _agent(db_session)
    _document_lesson(db_session, agent, context={
        "business_category": "pricing", "qualification": "manager approved",
    })
    result = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing"},
        workspace_id="ws-a",
    )
    assert result["status"] == "needs_context"
    assert result["clarifications"][0]["missing"] == ["qualification"]
    assert "qualification" in result["explanation"]


def test_scoped_exception_overrides_only_inside_scope(db_session):
    agent = _agent(db_session)
    _document_lesson(
        db_session, agent,
        context={"business_category": "pricing"},
    )
    _document_lesson(
        db_session, agent,
        lesson="Use the warehouse exception format",
        topic="warehouse exception",
        format_spec={"font_size": 14},
        context={"business_category": "pricing", "location": "Warehouse B"},
    )
    inside = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing", "location": "Warehouse B"},
        workspace_id="ws-a",
    )
    outside = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing", "location": "Warehouse A"},
        workspace_id="ws-a",
    )
    assert inside["status"] == "applicable"
    assert inside["spec"]["font_size"] == 14
    assert inside["sources"][0]["context"]["location"] == "Warehouse B"
    assert outside["status"] == "applicable"
    assert outside["spec"]["font_size"] == 11


def test_workspace_context_does_not_leak(db_session):
    agent = _agent(db_session, workspace="ws-b")
    _document_lesson(db_session, agent, context={"business_category": "pricing"})
    result = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing"},
        workspace_id="ws-a",
    )
    assert result["status"] == "not_applicable"
    assert result["spec"] == {}


def test_changed_source_version_is_stale(db_session):
    agent = _agent(db_session)
    _document_lesson(
        db_session, agent,
        context={"business_category": "pricing", "source_version": "v1"},
    )
    result = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={
            "business_category": "pricing", "audience": "internal",
            "source_version": "v2",
        },
        workspace_id="ws-a",
    )
    assert result["status"] == "not_applicable"
    assert result["applicability"][0]["conflicts"][0]["key"] == "source_version"


def test_equal_specificity_conflict_is_surfaced(db_session):
    agent = _agent(db_session)
    _document_lesson(db_session, agent, lesson="Use format one", topic="one",
                     format_spec={"font_size": 11})
    _document_lesson(db_session, agent, lesson="Use format two", topic="two",
                     format_spec={"font_size": 12})
    result = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing", "audience": "internal"},
        workspace_id="ws-a",
    )
    assert result["status"] == "conflict"
    assert "font_size" not in result["spec"]
    assert "conflict" in result["explanation"].lower()


def test_explicit_replacement_removes_older_lesson(db_session):
    agent = _agent(db_session)
    first = _document_lesson(
        db_session, agent, lesson="Use the old format", topic="old",
        format_spec={"font_size": 10})
    _document_lesson(
        db_session, agent, lesson="Use the replacement format",
        topic="replacement",
        format_spec={"font_size": 12},
        context={
            "business_category": "pricing", "audience": "internal",
            "replaces": [first["entry"]["id"]],
        },
    )
    result = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing", "audience": "internal"},
        workspace_id="ws-a",
    )
    assert result["status"] == "applicable"
    assert result["spec"]["font_size"] == 12


def test_effective_period_excludes_outside_dates(db_session):
    agent = _agent(db_session)
    _document_lesson(
        db_session, agent,
        context={"business_category": "pricing", "effective_to": "2026-01-01"},
    )
    result = resolve_artifact_teaching(
        db_session, agent.id, "document",
        task_context={"business_category": "pricing"},
        workspace_id="ws-a", now="2026-10-28",
    )
    assert result["status"] == "not_applicable"


def test_field_mapping_exact_rename_and_sheet_ambiguity():
    schema = [
        {"sheet": "New", "column": "SKU", "unit": "each"},
        {"sheet": "Other", "column": "SKU", "unit": "each"},
    ]
    exact = resolve_field_mapping(
        [{"concept": "subject", "sheet": "New", "column": "SKU",
          "unit": "each", "source_version": "v1"}],
        schema, source_version="v1",
    )
    assert exact["status"] == "applicable"
    ambiguous = resolve_field_mapping(
        [{"concept": "subject", "column": "SKU", "unit": "each"}],
        schema,
    )
    assert ambiguous["status"] == "conflict"
    stale = resolve_field_mapping(
        [{"concept": "subject", "sheet": "New", "column": "SKU",
          "source_version": "v1"}],
        schema, source_version="v2",
    )
    assert stale["status"] == "not_applicable"
    unit_changed = resolve_field_mapping(
        [{"concept": "subject", "sheet": "New", "column": "SKU", "unit": "box"}],
        schema,
    )
    assert unit_changed["status"] == "needs_context"


def test_document_teaching_reorders_sections_and_columns():
    markdown = (
        "## Findings\n\nText\n\n"
        "## Summary\n\n| Value | Item |\n|---|---|\n| 1 | A |\n\n"
        "## Sources\n\n- one\n"
    )
    text, findings = apply_document_teaching(markdown, {
        "heading_order": ["Summary", "Findings", "Sources"],
        "table_columns": ["Item", "Value"],
        "prohibited_terms": ["INTERNAL ONLY"],
    })
    assert text.index("## Summary") < text.index("## Findings") < text.index("## Sources")
    assert "| Item | Value |" in text
    assert findings == []


def test_email_teaching_sets_protocol_and_rejects_internal_term():
    content, findings = apply_email_teaching(
        {"subject": "Status", "body": "Hello team"},
        {"subject_prefix": "[Review]", "greeting": "Hello",
         "signature": "Rish", "prohibited_terms": ["INTERNAL ONLY"]},
    )
    assert content["subject"] == "[Review] Status"
    assert content["body"].startswith("Hello")
    assert "Rish" in content["body"]
    assert content["draft_only"] is True
    assert content["send_performed"] is False
    assert findings == []


def test_presentation_teaching_reorders_slides():
    markdown = (
        "Slide 1: Findings\n- one\n\n"
        "Slide 2: Overview\n- two\n\n"
        "Slide 3: Sources\n- three\n"
    )
    text, findings = apply_presentation_teaching(
        markdown, {"slide_order": ["Overview", "Findings", "Sources"]})
    assert text.index("Slide 1: Overview") < text.index("Slide 2: Findings")
    assert findings == []


def test_long_instruction_keeps_trailing_exception():
    lesson = ("Use the standard report format. " + "Detail " * 80
              + "Do not apply to archived accounts.")
    block = format_lessons_block([{
        "id": "long", "topic": "standard", "lesson": lesson,
    }])
    assert "Do not apply to archived accounts." in block


def test_update_revision_preserves_unrelated_agent(db_session):
    agent_a = _agent(db_session, workspace="ws-a", name="A")
    agent_b = _agent(db_session, workspace="ws-b", name="B")
    first = _document_lesson(db_session, agent_a)
    deliver_teacher_lesson(
        db_session, agent_b.id, "Decision rule for B",
        decision_options=["APPROVE", "DENY"], topic="decision",
    )
    point_id = first["entry"]["id"]
    updated = update_teaching_point(
        db_session, agent_a.id, point_id,
        format_spec={"font_size": 12},
    )
    assert updated["status"] == "ok"
    assert updated["entry"]["revision"] == 2
    listed = list_agent_lessons(db_session, agent_a.id)
    assert listed[0]["revision"] == 2
    b_lessons = get_agent_lessons(db_session, agent_b.id)
    assert [item.get("lesson") for item in b_lessons] == ["Decision rule for B"]
    assert b_lessons[0].get("format_spec") is None


def test_mapping_only_lesson_resolves_and_confirmation_updates_it(db_session):
    agent = _agent(db_session)
    entry = journal_standing_lesson_entry(
        db_session, agent.id,
        "Price means the monetary value per unit.",
        source="teacher", topic="price mapping",
        applies_to=["document"],
        context={"field_mappings": [{
            "concept": "Price", "sheet": "Sheet1", "column": "Price",
            "unit": "USD", "source_version": "v1", "revision": 1,
        }]},
        workspace_id="ws-a",
    )
    assert entry is not None
    resolved = resolve_artifact_teaching(
        db_session, agent.id, "document", workspace_id="ws-a")
    assert resolved["status"] == "applicable"
    assert resolved["field_mappings"][0]["concept"] == "Price"
    assert resolved["field_mappings"][0]["lesson_id"] == entry["id"]

    updated = update_teaching_point(
        db_session, agent.id, entry["id"],
        context={"field_mappings": [{
            "concept": "Price", "sheet": "Sheet1", "column": "Amount",
            "unit": "USD", "source_version": "v2", "revision": 2,
        }]})
    assert updated["status"] == "ok"
    assert updated["entry"]["revision"] == 2
    resolved = resolve_artifact_teaching(
        db_session, agent.id, "document", workspace_id="ws-a")
    assert resolved["field_mappings"][0]["column"] == "Amount"
