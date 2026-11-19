"""Readiness endpoint: dependency→connection mapping over real token rows.

Covers ``GET /api/workflow-templates/{id}/readiness`` (the surface the
marketplace page calls). The SQLAlchemy chain is faked at the boundary —
the unit under test is the endpoint's assembly logic, not the ORM.
"""

from types import SimpleNamespace

import pytest

from api import workflow_template_routes as wtr


class _FakeQuery:
    def __init__(self, providers):
        self._providers = providers

    def filter(self, *args, **kwargs):
        return self

    def distinct(self):
        return self

    def all(self):
        return [(p,) for p in self._providers]


class _FakeDB:
    def __init__(self, providers):
        self._providers = providers

    def query(self, *_cols):
        return _FakeQuery(self._providers)


@pytest.fixture()
def template_manager_monkeypatch(monkeypatch):
    def _install(dependencies):
        manager = SimpleNamespace(
            get_template=lambda tid: (
                SimpleNamespace(template_id=tid, dependencies=dependencies)
                if tid == "template_personal_invoice_chase"
                else None
            )
        )
        monkeypatch.setattr(wtr, "get_template_manager", lambda: manager)

    return _install


async def test_readiness_missing_and_ready_paths(template_manager_monkeypatch):
    template_manager_monkeypatch(["gmail", "slack"])
    user = SimpleNamespace(id="u1", tenant_id=None)

    missing = await wtr.get_template_readiness(
        "template_personal_invoice_chase",
        current_user=user,
        db=_FakeDB(providers=[]),
    )
    assert missing["ready"] is False
    assert missing["missing"] == ["gmail", "slack"]
    assert "/integrations?connect=gmail" in missing["connect_urls"]

    ready = await wtr.get_template_readiness(
        "template_personal_invoice_chase",
        current_user=user,
        db=_FakeDB(providers=["google"]),  # gmail alias
    )
    assert ready["ready"] is False
    assert ready["connected"] == ["gmail"]
    assert ready["missing"] == ["slack"]


async def test_readiness_no_dependencies_is_ready(template_manager_monkeypatch):
    template_manager_monkeypatch([])
    result = await wtr.get_template_readiness(
        "template_personal_invoice_chase",
        current_user=SimpleNamespace(id="u1", tenant_id="t1"),
        db=_FakeDB(providers=[]),
    )
    assert result["ready"] is True


async def test_readiness_404_for_unknown_template(template_manager_monkeypatch):
    from fastapi import HTTPException

    template_manager_monkeypatch(["gmail"])
    with pytest.raises(HTTPException) as exc:
        await wtr.get_template_readiness(
            "template_does_not_exist",
            current_user=SimpleNamespace(id="u1", tenant_id=None),
            db=_FakeDB(providers=[]),
        )
    assert exc.value.status_code == 404


# --- Execution status (post-run loop closure) ---


class _FakeExecQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._row


class _FakeExecDB:
    def __init__(self, row):
        self._row = row

    def query(self, *_model):
        return _FakeExecQuery(self._row)


def _row(status="completed", error=None):
    from datetime import datetime

    return SimpleNamespace(
        execution_id="exe-1",
        workflow_id="workflow_abc123",
        status=status,
        error=error,
        created_at=datetime(2026, 8, 23, 12, 0, 0),
        completed_at=datetime(2026, 8, 23, 12, 0, 5) if status == "completed" else None,
    )


async def test_execution_status_found_by_workflow_id():
    from core.models import WorkflowExecution

    result = await wtr.get_execution_status(
        "workflow_abc123",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(_row()),
    )
    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["error"] is None


async def test_execution_status_includes_error_on_failure():
    result = await wtr.get_execution_status(
        "whatever",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(_row(status="failed", error="step s2 exploded")),
    )
    assert result["status"] == "failed"
    assert result["error"] == "step s2 exploded"


async def test_execution_status_404_when_unknown():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await wtr.get_execution_status(
            "nope",
            current_user=SimpleNamespace(id="u1"),
            db=_FakeExecDB(None),
        )
    assert exc.value.status_code == 404


# --- Step-level results ---


def _row_with_context(context_json, status="completed"):
    import json
    from datetime import datetime

    return SimpleNamespace(
        execution_id="exe-1",
        workflow_id="workflow_abc123",
        status=status,
        error=None,
        created_at=datetime(2026, 8, 23, 12, 0, 0),
        completed_at=datetime(2026, 8, 23, 12, 0, 5),
        context=context_json if isinstance(context_json, str) else (
            json.dumps(context_json) if context_json is not None else None
        ),
    )


async def test_results_parses_execution_history():
    row = _row_with_context({
        "variables": {"x": 1},
        "results": {"s1": {"status": "completed"}},
        "execution_history": [
            {"step_id": "scan_inbox", "step_type": "action", "status": "completed"},
            {"step_id": "approval_gate", "step_type": "approval", "status": "awaiting_approval",
             "notes": "waiting for human OK"},
        ],
    })
    result = await wtr.get_execution_results(
        "workflow_abc123",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(row),
    )
    assert [s["step_id"] for s in result["steps"]] == ["scan_inbox", "approval_gate"]
    assert result["steps"][1]["notes"] == "waiting for human OK"
    assert result["outputs"] == {"s1": {"status": "completed"}}


async def test_results_handles_garbage_context():
    row = _row_with_context("not-json{")
    result = await wtr.get_execution_results(
        "whatever",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(row),
    )
    assert result["steps"] == []
    assert result["outputs"] is None


async def test_results_caps_history_and_outputs():
    big = {
        "execution_history": [{"step_id": f"s{i}", "status": "completed"} for i in range(250)],
        "results": {f"k{i}": i for i in range(80)},
    }
    result = await wtr.get_execution_results(
        "big",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(_row_with_context(big)),
    )
    assert len(result["steps"]) == 100
    assert len(result["outputs"]) == 50


# --- Normal (WorkflowEngine) result projection ---


def _row_with_engine_state(outputs=None, steps=None, context=None, *,
                           status="completed", error=None):
    import json
    from datetime import datetime

    def _dump(value):
        if value is None:
            return None
        return value if isinstance(value, str) else json.dumps(value)

    return SimpleNamespace(
        execution_id="exe-engine-1",
        workflow_id="workflow_engine_1",
        status=status,
        error=error,
        created_at=datetime(2026, 8, 23, 12, 0, 0),
        completed_at=datetime(2026, 8, 23, 12, 0, 5),
        user_id="u1",
        owner_id="u1",
        tenant_id=None,
        outputs=_dump(outputs),
        steps=_dump(steps),
        context=_dump(context),
    )


_SYNTHETIC_ENGINE_OUTPUTS = {
    "summarize": {
        "service": "main_agent",
        "action": "generate_content",
        "status": "success",
        "result": {
            "success": True,
            "result": {
                "agent_response": "Synthetic total 42",
                "model": "test-local",
                "provider": "ollama",
            },
            "input_processed": {"private_input": "omit"},
        },
        "raw_error": "private error",
        "context": {"context_secret": "omit"},
        "tool_metadata": {"tool_name": "private-tool"},
    },
}


async def test_results_projects_safe_scoped_finished_engine_step():
    row = _row_with_engine_state(
        steps={"summarize": {"status": "COMPLETED", "step_type": "ai_task"}},
        outputs=_SYNTHETIC_ENGINE_OUTPUTS,
    )
    result = await wtr.get_execution_results(
        "exe-engine-1",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(row),
    )

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["steps"] == [{
        "step_id": "summarize",
        "step_type": "ai_task",
        "status": "COMPLETED",
        "notes": None,
    }]
    projected = result["outputs"]["summarize"]
    assert projected["status"] == "success"
    assert projected["result"] == {
        "agent_response": "Synthetic total 42",
        "model": "test-local",
        "provider": "ollama",
    }
    # Only the projected business result is exposed; outer main-agent
    # service/action metadata, raw input, context, errors and tool metadata
    # stay out of the response.
    assert "main_agent" not in str(result)
    assert "generate_content" not in str(result)
    assert "private_input" not in str(result)
    assert "input_processed" not in str(result)
    assert "tool_metadata" not in str(result)
    assert "raw_error" not in str(result)
    assert "context_secret" not in str(result)


_SYNTHETIC_GENERIC_AI_OUTPUT = {
    "service": "ai",
    "action": "summarize",
    "status": "success",
    "result": {
        "status": "success",
        "result": "text",
        "agent_response": "text",
        "provider": "ollama",
        "model": "test-model",
    },
}


async def test_results_projects_generic_ai_wrapper_envelope():
    row = _row_with_engine_state(
        steps={"summarize": {"status": "success", "step_type": "ai_task"}},
        outputs={"summarize": _SYNTHETIC_GENERIC_AI_OUTPUT},
    )
    result = await wtr.get_execution_results(
        "exe-engine-1",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(row),
    )

    assert result["steps"] == [{
        "step_id": "summarize",
        "step_type": "ai_task",
        "status": "success",
        "notes": None,
    }]
    assert result["outputs"]["summarize"] == {
        "status": "success",
        "result": {
            "agent_response": "text",
            "provider": "ollama",
            "model": "test-model",
        },
    }
    # Wrapper metadata, arbitrary keys and the legacy string result stay out.
    projected_result = result["outputs"]["summarize"]["result"]
    assert set(projected_result) == {"agent_response", "provider", "model"}


async def test_results_engine_no_result_is_empty_not_failure():
    row = _row_with_engine_state(outputs=None, steps=None)
    result = await wtr.get_execution_results(
        "exe-engine-1",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(row),
    )
    assert result["steps"] == []
    assert result["outputs"] is None


def _assert_public_projection_error(exc):
    detail = exc.value.detail
    assert exc.value.status_code == 409
    assert detail == {
        "error": "execution_result_unavailable",
        "message": "the persisted execution result could not be projected safely",
    }
    rendered = str(detail)
    for private in (
        "fields", "outputs", "agent_response", "input_processed",
        "private_input", "api_key",
    ):
        assert private not in rendered


async def test_results_engine_malformed_output_fails_safely():
    from fastapi import HTTPException

    row = _row_with_engine_state(outputs="not-json{secret", steps=None)
    with pytest.raises(HTTPException) as exc:
        await wtr.get_execution_results(
            "exe-engine-1",
            current_user=SimpleNamespace(id="u1"),
            db=_FakeExecDB(row),
        )
    _assert_public_projection_error(exc)
    assert "not-json" not in str(exc.value.detail)
    assert "secret" not in str(exc.value.detail)


async def test_results_engine_unsupported_shape_is_refused_not_faked():
    from fastapi import HTTPException

    row = _row_with_engine_state(
        steps={"summarize": {"status": "completed"}},
        outputs={
            "summarize": {
                "status": "completed",
                "result": {
                    "success": True,
                    "result": {"content": "Synthetic total 42"},
                },
            },
        },
    )
    with pytest.raises(HTTPException) as exc:
        await wtr.get_execution_results(
            "exe-engine-1",
            current_user=SimpleNamespace(id="u1"),
            db=_FakeExecDB(row),
        )
    _assert_public_projection_error(exc)


async def test_results_engine_oversize_business_result_refused():
    from fastapi import HTTPException

    row = _row_with_engine_state(
        steps={"summarize": {"status": "completed"}},
        outputs={
            "summarize": {
                "status": "completed",
                "result": {
                    "success": True,
                    "result": {
                        "agent_response": "x" * (wtr._RESULT_MAX_TEXT + 1),
                        "model": "test-local",
                        "provider": "ollama",
                    },
                },
            },
        },
    )
    with pytest.raises(HTTPException) as exc:
        await wtr.get_execution_results(
            "exe-engine-1",
            current_user=SimpleNamespace(id="u1"),
            db=_FakeExecDB(row),
        )
    _assert_public_projection_error(exc)


async def test_results_engine_overlong_step_id_refused():
    from fastapi import HTTPException

    long_id = "s" * (wtr._RESULT_MAX_STEP_ID + 1)
    row = _row_with_engine_state(
        steps={long_id: {"status": "completed"}},
        outputs={long_id: _SYNTHETIC_ENGINE_OUTPUTS["summarize"]},
    )
    with pytest.raises(HTTPException) as exc:
        await wtr.get_execution_results(
            "exe-engine-1",
            current_user=SimpleNamespace(id="u1"),
            db=_FakeExecDB(row),
        )
    _assert_public_projection_error(exc)


async def test_results_engine_sensitive_output_refused():
    from fastapi import HTTPException

    row = _row_with_engine_state(
        steps={"summarize": {"status": "completed"}},
        outputs={
            "summarize": {
                "status": "completed",
                "result": {
                    "success": True,
                    "result": {
                        "agent_response": (
                            "read /Users/alice/private/report.txt"),
                        "model": "test-local",
                        "provider": "ollama",
                    },
                    "input_processed": {"private_input": "omit"},
                },
                "tool_metadata": {"api_key": "sk-abcdefgh12345678"},
            },
        },
    )
    with pytest.raises(HTTPException) as exc:
        await wtr.get_execution_results(
            "exe-engine-1",
            current_user=SimpleNamespace(id="u1"),
            db=_FakeExecDB(row),
        )
    _assert_public_projection_error(exc)
    assert "Users" not in str(exc.value.detail)
    assert "alice" not in str(exc.value.detail)
    assert "sk-abcdefgh12345678" not in str(exc.value.detail)


async def test_results_generated_shape_unchanged_when_engine_fields_exist():
    row = _row_with_engine_state(
        steps={"summarize": {"status": "completed"}},
        outputs=_SYNTHETIC_ENGINE_OUTPUTS,
        context={
            "variables": {"x": 1},
            "results": {"s1": {"status": "completed"}},
            "execution_history": [{
                "step_id": "s1",
                "step_type": "action",
                "status": "completed",
            }],
        },
    )
    result = await wtr.get_execution_results(
        "exe-engine-1",
        current_user=SimpleNamespace(id="u1"),
        db=_FakeExecDB(row),
    )
    assert result == {
        "success": True,
        "execution_id": "exe-engine-1",
        "status": "completed",
        "error": None,
        "steps": [{
            "step_id": "s1",
            "step_type": "action",
            "status": "completed",
            "notes": None,
        }],
        "outputs": {"s1": {"status": "completed"}},
    }


async def test_results_legacy_owner_bounds_use_existing_access_filter(monkeypatch):
    seen = {}
    marker = object()

    def _fake_access_filter(user):
        seen["user"] = user
        return marker

    monkeypatch.setattr(wtr, "_execution_access_filter", _fake_access_filter)
    user = SimpleNamespace(id="u1")
    row = _row_with_engine_state(
        steps={"summarize": {"status": "completed"}},
        outputs=_SYNTHETIC_ENGINE_OUTPUTS,
    )
    result = await wtr.get_execution_results(
        "exe-engine-1",
        current_user=user,
        db=_FakeExecDB(row),
    )
    assert seen["user"] is user
    assert result["outputs"]["summarize"]["result"]["agent_response"] == (
        "Synthetic total 42")
