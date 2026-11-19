"""Issue #618 — "Use Template → Execute" never started.

The Workflows page lists templates from the FILE-BACKED template system
(``GET /api/workflow-templates``, ids like
``template_personal_candidate_pipeline``) and posts that id straight to
``/api/v1/workflows/workflows/{id}/execute``. The execute endpoint only
resolved durable workflows plus DB-UUID ``WorkflowTemplate`` rows, so every
template execution 404'd ("Workflow not found").

``_load_template_definition`` now falls through to the file-backed system.
These tests pin: resolution works, steps carry the engine's execution
contract (service/action/parameters), and declared (list-shaped) step
parameters bind through the engine's ``${input.<name>}`` convention with
declared defaults preferred.

They also pin the DB-template visibility policy shared with
``GET /api/user/templates``: the author and any user reading a public row
resolve it, while another user's private row resolves to ``None`` (404 at
the execute/schedule routes).
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import WorkflowTemplate
from core.workflow_endpoints import _load_template_definition
from core.workflow_template_system import WorkflowTemplateManager

TEMPLATE_ID = "template_exec_resolution_test"


def _write_template(tmp_path) -> WorkflowTemplateManager:
    manager = WorkflowTemplateManager(template_dir=str(tmp_path))
    manager.create_template({
        "template_id": TEMPLATE_ID,
        "name": "Exec Resolution Test",
        "description": "template executed straight from the catalog",
        "category": "automation",
        "complexity": "beginner",
        "tags": [],
        "author": "test",
        "is_public": True,
        "steps": [
            {
                "id": "s1",
                "name": "Fan out",
                "service": "workflow",
                "action": "noop",
                "parameters": {"sources": ["email", "form"]},
            },
            {
                "id": "s2",
                "name": "Notify",
                "service": "email",
                "action": "send",
                "parameters": [
                    {"name": "to_address", "type": "string", "label": "To",
                     "required": True, "default_value": None},
                    {"name": "subject", "type": "string", "label": "Subject",
                     "required": False, "default_value": "Weekly digest"},
                ],
            },
        ],
        "inputs": [],
    })
    return manager


@pytest.fixture
def template_dir(tmp_path, monkeypatch):
    """Point the resolver's WorkflowTemplateManager at the scratch store —
    the same patching seam the endpoint's function-level import provides."""
    real_cls = WorkflowTemplateManager

    def _factory():
        return real_cls(template_dir=str(tmp_path))

    monkeypatch.setattr(
        "core.workflow_template_system.WorkflowTemplateManager", _factory)
    return tmp_path


@pytest.fixture
def template_db():
    """Minimal real DB for the WorkflowTemplate visibility policy."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Base.metadata.tables["workflow_templates"]],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _db_user(user_id: str):
    return SimpleNamespace(id=user_id)


def _add_db_template(
    db, template_id: str, *, author_id: str = "author-1",
    is_public: bool = False, steps=None,
):
    db.add(WorkflowTemplate(
        id=template_id,
        name="DB Template",
        description="stored template",
        category="automation",
        icon="default",
        author_id=author_id,
        steps=steps if steps is not None else [],
        is_public=is_public,
    ))
    db.commit()


def test_file_backed_template_id_resolves_to_executable_definition(
    template_dir, template_db,
):
    _write_template(template_dir)

    definition = _load_template_definition(
        TEMPLATE_ID, _db_user("user-1"), template_db)

    assert definition is not None
    assert definition["id"] == TEMPLATE_ID
    assert definition["name"] == "Exec Resolution Test"
    assert len(definition["steps"]) == 2


def test_resolved_steps_carry_engine_contract(template_dir, template_db):
    """WorkflowEngine._execute_step reads step["service"], step["action"] and
    resolves step["parameters"] as a plain {name: value} dict — the resolved
    definition must satisfy that for both parameter shapes."""
    _write_template(template_dir)

    steps = _load_template_definition(
        TEMPLATE_ID, _db_user("user-1"), template_db)["steps"]
    by_id = {s["id"]: s for s in steps}

    assert by_id["s1"]["service"] == "workflow"
    assert by_id["s1"]["action"] == "noop"
    assert by_id["s1"]["parameters"] == {"sources": ["email", "form"]}

    assert by_id["s2"]["service"] == "email"
    assert by_id["s2"]["action"] == "send"
    # Declared parameter list → {name: value}: default preferred, otherwise
    # bind to the execution input the modal collected.
    assert by_id["s2"]["parameters"]["subject"] == "Weekly digest"
    assert by_id["s2"]["parameters"]["to_address"] == "${input.to_address}"


def test_unknown_id_still_returns_none(template_dir, template_db):
    assert _load_template_definition(
        "template_does_not_exist", _db_user("user-1"), template_db) is None


def test_db_private_template_resolves_for_its_author(template_db):
    _add_db_template(
        template_db, "template_private_author", author_id="author-1",
        steps=[{"id": "s1", "service": "email", "action": "send"}],
    )

    definition = _load_template_definition(
        "template_private_author", _db_user("author-1"), template_db)

    assert definition is not None
    assert definition["id"] == "template_private_author"
    assert definition["steps"] == [
        {"id": "s1", "service": "email", "action": "send"}]
    assert definition["_template_catalog"] is True


def test_db_private_template_is_not_found_for_another_user(template_db):
    _add_db_template(
        template_db, "template_private_other", author_id="author-1")

    assert _load_template_definition(
        "template_private_other", _db_user("unrelated-user"), template_db
    ) is None


def test_hidden_db_template_does_not_fall_through_to_file_catalog(
    template_dir, template_db,
):
    _write_template(template_dir)
    _add_db_template(
        template_db, TEMPLATE_ID, author_id="author-1", is_public=False)

    assert _load_template_definition(
        TEMPLATE_ID, _db_user("unrelated-user"), template_db) is None

    definition = _load_template_definition(
        TEMPLATE_ID, _db_user("author-1"), template_db)
    assert definition is not None
    assert definition["name"] == "DB Template"
    assert definition["_template_catalog"] is True


def test_db_public_template_resolves_for_another_user(template_db):
    _add_db_template(
        template_db, "template_public_other", author_id="author-1",
        is_public=True,
    )

    definition = _load_template_definition(
        "template_public_other", _db_user("unrelated-user"), template_db)

    assert definition is not None
    assert definition["id"] == "template_public_other"


def test_db_public_resolves_without_actor_but_private_stays_missing(
    template_db,
):
    """Legacy jobs carry no frozen actor. With a request DB but ``user=None``
    the public catalog must still resolve, while another user's private row
    stays absent — same policy the visibility predicate already encodes."""
    _add_db_template(
        template_db, "template_public_no_actor", author_id="author-1",
        is_public=True,
    )
    _add_db_template(
        template_db, "template_private_no_actor", author_id="author-1",
    )

    public = _load_template_definition(
        "template_public_no_actor", None, template_db)
    private = _load_template_definition(
        "template_private_no_actor", None, template_db)

    assert public is not None
    assert public["id"] == "template_public_no_actor"
    assert private is None


def test_db_resolution_uses_request_db_not_a_new_session(
    template_db, monkeypatch,
):
    _add_db_template(
        template_db, "template_request_db", author_id="author-1")

    def _unexpected_session():
        raise AssertionError(
            "the resolver must use the request DB, not open its own session")

    monkeypatch.setattr(
        "core.workflow_endpoints.get_db", _unexpected_session)

    definition = _load_template_definition(
        "template_request_db", _db_user("author-1"), template_db)

    assert definition is not None
    assert definition["id"] == "template_request_db"
