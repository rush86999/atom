"""Verify that normal template and component writes preserve revision history."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import event, select

from api.user_templates_endpoints import UpdateTemplateRequest, update_template
from core.custom_components_service import CustomComponentsService
from core.models import ComponentVersion, CustomComponent, TemplateVersion, User, WorkflowTemplate


@pytest.fixture
def version_history(test_database):
    _, sessions = test_database
    with sessions.begin() as db:
        db.add(User(
            id="revision-owner", email="history@example.com", hashed_password="fixture",
            first_name="Revision", last_name="Owner", role="member", status="active",
        ))
        db.flush()
        db.add(CustomComponent(
            id="component", name="Example", display_name="Example",
            component_type="form", created_by="revision-owner",
        ))
        db.add(WorkflowTemplate(
            id="template", name="Example", author_id="revision-owner",
            category="test", icon="test", version="1.0.5", steps=[],
        ))
    return sessions


def test_concurrent_template_edits_record_distinct_legacy_revision_numbers(version_history):
    gate = Barrier(2)

    def edit(index):
        with version_history() as db:
            owner = db.get(User, "revision-owner")
            synchronized = False

            @event.listens_for(db, "do_orm_execute", retval=True)
            def synchronize_initial_reads(state):
                nonlocal synchronized
                result = state.invoke_statement()
                if state.is_select and not synchronized and f"FROM {WorkflowTemplate.__tablename__}" in str(state.statement):
                    synchronized = True
                    gate.wait(timeout=10)
                return result

            return asyncio.run(update_template(
                "template", UpdateTemplateRequest(change_description=f"Change {index}"),
                owner, db,
            ))

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(edit, (1, 2)))

    with version_history() as db:
        template = db.get(WorkflowTemplate, "template")
        versions = db.scalars(select(TemplateVersion.version_number).order_by(
            TemplateVersion.version_number)).all()
        assert template.version == "1.0.7"
        assert versions == [6, 7]


def test_component_history_write_failure_rolls_back_saved_edit(version_history):
    with version_history() as db:
        @event.listens_for(db, "before_flush")
        def fail_history_insert(session, *_):
            if any(isinstance(row, ComponentVersion) for row in session.new):
                raise RuntimeError("fixture history write failed")

        with pytest.raises(RuntimeError, match="fixture history write failed"):
            CustomComponentsService(db).update_component(
                "component", "revision-owner", description="Must roll back",
            )

    with version_history() as db:
        component = db.get(CustomComponent, "component")
        assert component.description is None
        assert component.current_version == 1
        assert db.scalars(select(ComponentVersion)).all() == []
