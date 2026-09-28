from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def database(monkeypatch):
    from core import database as database_module
    from core.models_registration import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def get_db_session():
        db = session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(database_module, "get_db_session", get_db_session)
    yield session_factory
    engine.dispose()


def _add_canvas(session_factory, canvas_id, content):
    from core.models import Canvas

    with session_factory() as db:
        db.add(
            Canvas(
                id=canvas_id,
                tenant_id="default",
                created_by="user-1",
                name="Shared draft",
                canvas_type="document",
                content=content,
            )
        )
        db.commit()


def _add_audit(
    session_factory,
    canvas_id,
    operation_id,
    content,
    created_at,
    postconditions=None,
):
    from core.models import CanvasAudit

    details = {
        "operation_id": operation_id,
        "content": content,
        "review_status": "accepted",
    }
    if postconditions is not None:
        details["postconditions"] = postconditions
    with session_factory() as db:
        db.add(
            CanvasAudit(
                id=f"audit-{uuid4().hex[:12]}",
                canvas_id=canvas_id,
                tenant_id="default",
                session_id="session-1",
                action_type="update",
                user_id="user-1",
                created_at=created_at,
                details_json=details,
            )
        )
        db.commit()


def _add_continuation(session_factory, continuation_id, origin_id):
    from core.models import AgentExecution

    with session_factory() as db:
        db.add(
            AgentExecution(
                id=continuation_id,
                status="running",
                triggered_by="continuation",
                started_at=datetime.now(timezone.utc),
                metadata_json={
                    "session_id": "session-1",
                    "originating_execution_id": origin_id,
                },
            )
        )
        db.commit()


@pytest.mark.asyncio
async def test_overlapping_turns_receive_independent_verdicts(database):
    from integrations.chat_orchestrator import ChatOrchestrator

    canvas_id = f"canvas-{uuid4().hex[:8]}"
    first_id = f"execution-{uuid4().hex[:8]}"
    second_id = f"execution-{uuid4().hex[:8]}"
    served = {"body": "second"}
    postconditions = [
        {
            "entity_id": "body",
            "field": "value",
            "expected": {"raw_value": "second"},
        }
    ]
    _add_canvas(database, canvas_id, served)
    _add_audit(
        database,
        canvas_id,
        first_id,
        {"body": "first"},
        datetime.now(timezone.utc),
    )
    _add_audit(
        database,
        canvas_id,
        second_id,
        served,
        datetime.now(timezone.utc),
        postconditions,
    )

    with (
        patch(
            "tools.canvas_crud_tool.read_canvas",
            new=AsyncMock(return_value={"success": True, "content": served}),
        ),
        patch(
            "core.chat_canvas_editor._evidence_action_applied",
            side_effect=lambda content, _action: content == served,
        ),
    ):
        first = await ChatOrchestrator._canvas_write_for_operation(canvas_id, "session-1", "user-1", first_id)
        second = await ChatOrchestrator._canvas_write_for_operation(canvas_id, "session-1", "user-1", second_id)
        unknown = await ChatOrchestrator._canvas_write_for_operation(
            canvas_id, "session-1", "user-1", f"{first_id}-suffix"
        )

    assert first["verdict"] == "write_recorded"
    assert second["verdict"] == "result_verified"
    assert unknown["verdict"] == "unverified"


@pytest.mark.asyncio
async def test_overlapping_turn_claim_does_not_use_another_turn_write(database):
    from integrations.chat_orchestrator import ChatOrchestrator

    canvas_id = f"canvas-{uuid4().hex[:8]}"
    first_id = f"execution-{uuid4().hex[:8]}"
    second_id = f"execution-{uuid4().hex[:8]}"
    _add_canvas(database, canvas_id, {"body": "second"})
    _add_audit(
        database,
        canvas_id,
        second_id,
        {"body": "second"},
        datetime.now(timezone.utc),
    )

    corrected = await ChatOrchestrator._canvas_claim_correction(
        "I've updated the draft.",
        {"canvas_id": canvas_id},
        "session-1",
        "user-1",
        False,
        execution_id=first_id,
    )

    assert "I've updated the draft" not in corrected
    assert "Unverified" in corrected


@pytest.mark.asyncio
async def test_overlapping_continuations_bind_only_to_their_origin(database):
    from integrations.chat_orchestrator import ChatOrchestrator

    canvas_id = f"canvas-{uuid4().hex[:8]}"
    first_id = f"execution-{uuid4().hex[:8]}"
    second_id = f"execution-{uuid4().hex[:8]}"
    first_continuation = f"continuation-{uuid4().hex[:8]}"
    second_continuation = f"continuation-{uuid4().hex[:8]}"
    served = {"body": "second"}
    postconditions = [
        {
            "entity_id": "body",
            "field": "value",
            "expected": {"raw_value": "second"},
        }
    ]
    _add_canvas(database, canvas_id, served)
    _add_continuation(database, first_continuation, first_id)
    _add_continuation(database, second_continuation, second_id)
    _add_audit(
        database,
        canvas_id,
        first_continuation,
        {"body": "first"},
        datetime.now(timezone.utc),
    )
    _add_audit(
        database,
        canvas_id,
        second_continuation,
        served,
        datetime.now(timezone.utc),
        postconditions,
    )

    with (
        patch(
            "tools.canvas_crud_tool.read_canvas",
            new=AsyncMock(return_value={"success": True, "content": served}),
        ),
        patch(
            "core.chat_canvas_editor._evidence_action_applied",
            side_effect=lambda content, _action: content == served,
        ),
    ):
        first = await ChatOrchestrator._canvas_write_for_operation(canvas_id, "session-1", "user-1", first_id)
        second = await ChatOrchestrator._canvas_write_for_operation(canvas_id, "session-1", "user-1", second_id)

    assert first["verdict"] == "write_recorded"
    assert second["verdict"] == "result_verified"
