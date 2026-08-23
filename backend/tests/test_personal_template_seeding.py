"""Personal-wedge seeding: file-based starters must reach the DB template UI.

The UI reads templates from the ORM ``WorkflowTemplate`` table while starters
ship as JSON files — these tests lock the bridge:

1. Seeding inserts all personal_*.json starters with author attribution.
2. Idempotent: second run inserts nothing (no duplicates).
3. User edits survive: existing rows are never overwritten by re-seeding.
4. Readiness mapping: dependency→connection status incl. provider aliases
   ("Gmail" connected as "google" counts), powering the one-CTA onboarding fix.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Base, IntegrationToken, Tenant, User, WorkflowTemplate
from core.personal_template_seeder import seed_personal_templates
from core.workflow_ui_endpoints import _compute_readiness


EXPECTED_STARTER_IDS = {
    "template_personal_invoice_chase",
    "template_personal_candidate_pipeline",
    "template_personal_support_triage",
}


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Minimal table subset: only what the seeder and models touch.
    # SQLite defaults to lazy FK enforcement, so omitted FK targets are fine.
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Tenant.__table__,
            User.__table__,
            WorkflowTemplate.__table__,
            IntegrationToken.__table__,
        ],
    )
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def session_with_user(db_session):
    user = User(
        id="user-bootstrap",
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        role="admin",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    return db_session


def test_seed_inserts_all_starters(session_with_user):
    inserted = seed_personal_templates(session_with_user)

    assert inserted == len(EXPECTED_STARTER_IDS)
    rows = {r.id: r for r in session_with_user.query(WorkflowTemplate).all()}
    assert EXPECTED_STARTER_IDS <= set(rows)

    invoice = rows["template_personal_invoice_chase"]
    assert invoice.is_public is True
    assert invoice.author_id == "user-bootstrap"
    assert invoice.steps, "starter steps must be present for the editor"
    schema = invoice.input_schema or {}
    assert "gmail" in schema.get("dependencies", [])
    assert schema.get("complexity") == "beginner"


def test_seed_is_idempotent(session_with_user):
    assert seed_personal_templates(session_with_user) == len(EXPECTED_STARTER_IDS)
    assert seed_personal_templates(session_with_user) == 0
    assert (
        session_with_user.query(WorkflowTemplate).count() == len(EXPECTED_STARTER_IDS)
    )


def test_seed_never_overwrites_user_edits(session_with_user):
    seed_personal_templates(session_with_user)
    row = session_with_user.query(WorkflowTemplate).filter_by(
        id="template_personal_invoice_chase"
    ).first()
    row.name = "My customized chase"
    session_with_user.commit()

    assert seed_personal_templates(session_with_user) == 0

    session_with_user.expire_all()
    row = session_with_user.query(WorkflowTemplate).filter_by(
        id="template_personal_invoice_chase"
    ).first()
    assert row.name == "My customized chase"


def test_seed_fails_soft_without_users(db_session):
    """No users → nothing to attribute authorship to → skip cleanly."""
    assert seed_personal_templates(db_session) == 0
    assert db_session.query(WorkflowTemplate).count() == 0


# --- Readiness mapping (the Gmail-OAuth friction killer) ---


def test_readiness_reports_missing_dependencies():
    result = _compute_readiness(["gmail", "slack"], connected_providers=set())
    assert result["ready"] is False
    assert result["connected"] == []
    assert result["missing"] == ["gmail", "slack"]
    assert result["connect_urls"] == [
        "/integrations?connect=gmail",
        "/integrations?connect=slack",
    ]


def test_readiness_accepts_provider_aliases():
    """Users connect 'Google' — templates ask for 'gmail'. Same thing."""
    result = _compute_readiness(["gmail", "slack"], connected_providers={"google"})
    assert result["ready"] is False
    assert result["connected"] == ["gmail"]
    assert result["missing"] == ["slack"]


def test_readiness_ready_when_all_connected():
    result = _compute_readiness(["gmail"], connected_providers={"google"})
    assert result["ready"] is True
    assert result["missing"] == []


def test_readiness_empty_dependencies_is_ready():
    result = _compute_readiness([], connected_providers=set())
    assert result["ready"] is True
