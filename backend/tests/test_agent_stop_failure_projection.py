"""Safe projection tests for agent decision 503 error envelopes."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.agent_routes import _raise_agent_decision


def _detail(result):
    with pytest.raises(HTTPException) as excinfo:
        _raise_agent_decision(result)
    return excinfo.value


def test_unknown_projection_keeps_only_allowlisted_observation():
    result = {
        "status": "effect_unknown",
        "message": "The stop outcome is uncertain.",
        "operation_id": "agent:stop:projection",
        "target_id": "a1",
        "verification": {
            "status": "unavailable",
            "effect": "unknown",
            "replay": "do_not_repeat",
        },
        "data": {
            "agent_id": "a1",
            "cancelled_tasks": 2,
            "configuration": {"secret": "must-not-escape"},
            "schedule_config": {"cron": "must-not-escape"},
            "job_parameters": {"token": "must-not-escape"},
            "exception": "must-not-escape",
        },
    }
    exc = _detail(result)
    assert exc.status_code == 503
    assert exc.detail["data"] == {"agent_id": "a1", "cancelled_tasks": 2}
    assert "configuration" not in exc.detail["data"]
    assert "schedule_config" not in exc.detail["data"]
    assert "job_parameters" not in exc.detail["data"]
    assert "exception" not in exc.detail["data"]


def test_unknown_projection_omits_wrong_typed_or_private_observation():
    result = {
        "status": "committed_unverified",
        "message": "The decision committed but readback did not verify.",
        "operation_id": "agent:stop:projection-types",
        "target_id": "a1",
        "verification": {
            "status": "refuted",
            "effect": "committed",
            "replay": "do_not_repeat",
        },
        "data": {
            "agent_id": "",
            "cancelled_tasks": True,
            "configuration": {"secret": "must-not-escape"},
        },
    }
    exc = _detail(result)
    assert exc.status_code == 503
    assert "data" not in exc.detail


def test_unknown_projection_without_data_does_not_conjure_observation():
    result = {
        "status": "effect_unknown",
        "message": "The decision outcome is uncertain.",
        "operation_id": "agent:run:no-data",
        "target_id": "a1",
        "verification": {
            "status": "unavailable",
            "effect": "unknown",
            "replay": "do_not_repeat",
        },
        "data": None,
    }
    exc = _detail(result)
    assert exc.status_code == 503
    assert "data" not in exc.detail


def test_state_unavailable_projects_typed_error_without_private_data():
    result = {
        "status": "state_unavailable",
        "error": "The agent task state is unavailable; no cancellation was attempted.",
        "error_code": "AGENT_TASK_STATE_UNAVAILABLE",
        "http_status": 503,
        "operation_id": "agent:stop:unreadable",
        "target_id": "a1",
        "verification": {
            "status": "unavailable",
            "effect": "none",
            "replay": "safe_after_refresh",
        },
        "data": {"configuration": {"secret": "must-not-escape"}},
    }
    exc = _detail(result)
    assert exc.status_code == 503
    assert exc.detail["error"]["code"] == "AGENT_TASK_STATE_UNAVAILABLE"
    assert exc.detail["verification"]["effect"] == "none"
    assert "data" not in exc.detail
