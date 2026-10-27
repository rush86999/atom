from core.source_requirements import (
    attach_source_requirements,
    derive_required_research_sources,
)


def test_workbook_only_assessment_requires_only_datasets():
    diag = derive_required_research_sources(
        message=(
            "Using the uploaded orders.xlsx, review O-1001 against policy. "
            "Do not send, approve, or modify anything."),
        lessons=[],
    )

    assert diag["sources"] == ["datasets"]
    assert diag["message_sources"] == ["datasets"]


def test_unrelated_lesson_mentioning_correspondence_adds_nothing():
    diag = derive_required_research_sources(
        message="Review the uploaded orders.xlsx for O-1001.",
        lessons=[{
            "id": "lesson-unrelated",
            "topic": "closing",
            "scope": "global",
            "lesson": "Email the manager when the review is done.",
        }],
    )

    assert diag["sources"] == ["datasets"]
    assert diag["lesson_candidates"] == [{
        "lesson_id": "lesson-unrelated",
        "topic": "closing",
        "scope": "global",
        "goal_id": None,
        "source_agent_id": None,
        "source": "outlook",
        "accepted": False,
        "reason": "source mention without an affirmative research instruction",
    }]


def test_applicable_own_lesson_with_explicit_requirement_retains_both():
    lesson = {
        "id": "lesson-cross-source",
        "topic": "order review",
        "scope": "goal",
        "goal_id": "goal-7",
        "lesson": (
            "Always check email attachments for unmatched workbook rows "
            "before deciding the order."),
    }
    diag = derive_required_research_sources(
        message="Review the order record.",
        lessons=[lesson],
    )

    assert diag["sources"] == ["datasets", "outlook"]
    assert len(diag["evidence"]) == 2
    assert {e["lesson_id"] for e in diag["evidence"]} == {
        "lesson-cross-source"}
    assert {e["scope"] for e in diag["evidence"]} == {"goal"}
    assert all(e["goal_id"] == "goal-7" for e in diag["evidence"])


def test_explicit_cross_source_request_retains_both():
    diag = derive_required_research_sources(
        message=(
            "Review the workbook and check the email thread for the "
            "approval history."),
        lessons=[],
    )

    assert diag["sources"] == ["datasets", "outlook"]


def test_sibling_lesson_is_not_source_authority():
    diag = derive_required_research_sources(
        message="Review the uploaded orders.xlsx for O-1001.",
        lessons=[{
            "id": "lesson-sibling",
            "scope": "global",
            "lesson": "Always check email attachments for unmatched rows.",
            "_source_agent_id": "other-agent",
        }],
    )

    assert diag["sources"] == ["datasets"]
    assert diag["lesson_candidates"] == [{
        "lesson_id": "lesson-sibling",
        "topic": None,
        "scope": "global",
        "goal_id": None,
        "source_agent_id": "other-agent",
        "source": "outlook",
        "accepted": False,
        "reason": "sibling lesson is not source authority for this task",
    }]


def test_accepted_task_source_requirement_is_authoritative():
    diag = derive_required_research_sources(
        message="Review the order record.",
        lessons=[],
        accepted_task={
            "source_requirements": {
                "datasets": True,
                "outlook": True,
            }
        },
    )

    assert diag["sources"] == ["datasets", "outlook"]
    assert [e["kind"] for e in diag["evidence"]] == [
        "accepted_task", "accepted_task"]


def test_accepted_task_records_source_authority_with_lesson_identity():
    lesson = {
        "id": "lesson-cross-source",
        "topic": "order review",
        "scope": "goal",
        "goal_id": "goal-7",
        "lesson": "Always check email attachments for unmatched workbook rows.",
    }
    diag = derive_required_research_sources(
        message="Review the workbook.", lessons=[lesson])
    task = {"task_id": "task-1", "status": "pending"}

    attached = attach_source_requirements(task, diag)

    assert attached is task
    assert task["source_requirements"] == ["datasets", "outlook"]
    assert {
        (e["lesson_id"], e["scope"], e["reason"])
        for e in task["source_requirement_evidence"]
        if e["kind"] == "lesson"
    } == {
        ("lesson-cross-source", "goal",
         "applicable own lesson explicitly requires the source"),
    }


def test_explicitly_excluded_workbook_does_not_add_datasets():
    diag = derive_required_research_sources(
        message=(
            "Check the email thread for the approval; do not use the "
            "workbook for this decision."),
        lessons=[],
    )

    assert diag["sources"] == ["outlook"]


def test_named_document_source_is_derived_from_the_request():
    diag = derive_required_research_sources(
        message="Read the attached policy PDF and summarize it.",
        lessons=[],
    )

    assert diag["sources"] == ["documents"]


def test_attach_preserves_existing_requirements_on_empty_derivation():
    task = {
        "task_id": "task-keep",
        "source_requirements": ["datasets", "outlook"],
    }

    attached = attach_source_requirements(task, {"sources": []})

    assert attached["source_requirements"] == ["datasets", "outlook"]
