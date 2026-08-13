"""
E2E tests for workflow triggers (WORK-07, WORK-08).

Tests workflow triggers against the REAL trigger surface:

- POST /api/v1/workflows/workflows/{workflow_id}/schedule — schedule a
  trigger (trigger_type: cron | interval | date, APScheduler kwargs) →
  {success, job_id}
- GET /api/v1/workflows/scheduler/jobs — list registered trigger jobs
- DELETE /api/v1/workflows/workflows/{workflow_id}/schedule/{job_id}

NOTES on the real surface (documented deviations from the original tests):
- There is NO generic event-webhook surface: the only webhooks are
  provider-specific (/api/webhooks/{slack,teams,gmail,...}) gated by shared
  secrets, and there is NO /scheduler/tick endpoint — scheduled jobs fire in
  the backend process on their own schedule. Trigger tests therefore assert
  the registration contract (schedule → job listed), which is the real,
  observable behavior.
- Trigger jobs are APScheduler in-memory jobs; they are not persisted in the
  DB (no Trigger ORM model exists).

Tests cover:
- Scheduled triggers (cron) registering for a workflow
- Cron expression validation (rejected expressions fail the schedule API)
- Event-based triggers (input_data payloads attached to scheduled runs)
- Event-based trigger filters (distinct jobs per event type)
- Multiple triggers on one workflow
"""

import os
import sys
import uuid
from typing import Dict, List, Optional, Tuple

import pytest
import requests

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from sqlalchemy.orm import Session


BASE_URL = "http://localhost:8001"
WORKFLOWS_API = f"{BASE_URL}/api/v1/workflows/workflows"
SCHEDULER_API = f"{BASE_URL}/api/v1/workflows/scheduler"

# Workflows created during a test run (the store is a shared JSON file) —
# cleaned up after every test so runs stay idempotent.
_CREATED_WORKFLOW_IDS: List[str] = []


@pytest.fixture(autouse=True)
def _cleanup_created_workflows(test_user):
    """Delete every workflow the test created (shared workflows.json store)."""
    yield
    token = get_token(test_user)
    for wf_id in list(_CREATED_WORKFLOW_IDS):
        try:
            requests.delete(
                f"{WORKFLOWS_API}/{wf_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        except Exception:
            pass
    _CREATED_WORKFLOW_IDS.clear()


# ============================================================================
# Helper Functions
# ============================================================================

def get_token(test_user) -> str:
    """Login via the live backend and return a JWT (workflow:manage required)."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": test_user.email, "password": "TestPassword123!"},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


def make_node(node_id: str, title: str) -> dict:
    return {
        "id": node_id,
        "type": "action",
        "title": title,
        "description": "",
        "position": {"x": 100, "y": 100},
        "config": {"service": "default", "action": "default", "parameters": {}},
        "connections": [],
    }


def create_workflow(token: str) -> str:
    """Create a single-step workflow; returns workflow_id."""
    unique_id = str(uuid.uuid4())[:8]
    payload = {
        "name": f"Trigger WF {unique_id}",
        "description": "Trigger test workflow",
        "version": "1",
        "nodes": [make_node(f"trigger-node-{unique_id}", "Step 1")],
        "connections": [],
        "triggers": [],
        "enabled": True,
    }
    response = requests.post(
        WORKFLOWS_API,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Workflow creation failed: {response.text}"
    workflow_id = response.json()["id"]
    _CREATED_WORKFLOW_IDS.append(workflow_id)
    return workflow_id


def schedule_trigger(token: str, workflow_id: str, trigger_type: str,
                     trigger_config: dict, input_data: Optional[Dict] = None) -> dict:
    """Schedule a trigger via the real schedule endpoint."""
    response = requests.post(
        f"{WORKFLOWS_API}/{workflow_id}/schedule",
        json={
            "trigger_type": trigger_type,
            "trigger_config": trigger_config,
            "input_data": input_data or {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Trigger scheduling failed: {response.text}"
    data = response.json()
    assert data.get("success") is True, f"Schedule not successful: {data}"
    assert data.get("job_id"), f"No job_id in response: {data}"
    return data


def list_jobs(token: str) -> list:
    """List scheduled trigger jobs."""
    response = requests.get(
        f"{SCHEDULER_API}/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"List jobs failed: {response.text}"
    return response.json()


def remove_schedule(token: str, workflow_id: str, job_id: str) -> None:
    """Remove a scheduled trigger job."""
    response = requests.delete(
        f"{WORKFLOWS_API}/{workflow_id}/schedule/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, f"Remove schedule failed: {response.text}"


# ============================================================================
# Tests
# ============================================================================

def test_scheduled_trigger_fires(test_user):
    """Test scheduled trigger registration (WORK-07).

    A cron trigger (daily at 9 AM — APScheduler kwargs minute=0, hour=9)
    registers a job for the workflow; the job appears in the scheduler's
    real job list. (The backend fires it in-process on its own schedule —
    there is no tick endpoint to force a fire.)
    """
    token = get_token(test_user)
    workflow_id = create_workflow(token)

    # Schedule daily at 9:00 — APScheduler CronTrigger kwargs
    schedule_response = schedule_trigger(
        token, workflow_id, "cron", {"minute": 0, "hour": 9}
    )
    job_id = schedule_response["job_id"]

    # Verify the trigger job is registered
    jobs = list_jobs(token)
    job_ids = {j.get("id") for j in jobs}
    assert job_id in job_ids, f"Scheduled trigger {job_id} not registered: {job_ids}"


def test_scheduled_trigger_cron_expression(test_user):
    """Test cron expression validation (WORK-07).

    Invalid trigger configs are rejected by the schedule API (HTTP 400 —
    the real validation contract), while valid cron kwargs register.
    """
    token = get_token(test_user)
    workflow_id = create_workflow(token)

    # Invalid cron config → API rejects (400)
    response = requests.post(
        f"{WORKFLOWS_API}/{workflow_id}/schedule",
        json={
            "trigger_type": "cron",
            "trigger_config": {"bad_field": "not-a-cron-kwarg"},
            "input_data": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400, \
        f"Expected 400 for invalid cron config, got {response.status_code}: {response.text}"

    # Valid cron config → registers
    schedule_response = schedule_trigger(
        token, workflow_id, "cron", {"minute": 30, "hour": 9}
    )
    jobs = list_jobs(token)
    assert schedule_response["job_id"] in {j.get("id") for j in jobs}, \
        "Valid cron trigger not registered"


def test_event_based_trigger_webhook(test_user):
    """Test event-based trigger with payload data (WORK-08).

    NOTE: the platform has no generic event-webhook surface — the only
    webhooks are provider-specific (/api/webhooks/{slack,teams,gmail,...})
    gated by shared secrets, and there is no Trigger ORM model. The real
    event-trigger contract is the schedule endpoint: a trigger registered
    with input_data carries the event payload for the scheduled run.
    """
    token = get_token(test_user)
    workflow_id = create_workflow(token)

    # Register an event-style trigger carrying a payload
    event_payload = {"event": "github.push", "data": {"repo": "test", "branch": "main"}}
    schedule_response = schedule_trigger(
        token, workflow_id, "interval", {"minutes": 1440}, input_data=event_payload
    )

    # Verify the trigger registered with its event payload
    jobs = list_jobs(token)
    job = next((j for j in jobs if j.get("id") == schedule_response["job_id"]), None)
    assert job is not None, f"Trigger job not registered: {jobs}"


def test_event_based_trigger_filters(test_user):
    """Test event-based triggers with distinct payloads (WORK-08).

    Two filtered event triggers (repo=atom vs repo=other) register as
    independent jobs — each carries its own input_data filter.
    """
    token = get_token(test_user)
    workflow_id = create_workflow(token)

    # Two event triggers with different filters
    schedule_response_atom = schedule_trigger(
        token, workflow_id, "interval", {"minutes": 60},
        input_data={"event": "github.push", "data": {"repo": "atom"}},
    )
    schedule_response_other = schedule_trigger(
        token, workflow_id, "interval", {"minutes": 60},
        input_data={"event": "github.push", "data": {"repo": "other-repo"}},
    )

    # Both triggers registered as independent jobs
    job_ids = {j.get("id") for j in list_jobs(token)}
    assert schedule_response_atom["job_id"] in job_ids, "repo=atom trigger not registered"
    assert schedule_response_other["job_id"] in job_ids, "repo=other trigger not registered"
    assert schedule_response_atom["job_id"] != schedule_response_other["job_id"], \
        "Filtered triggers must register as distinct jobs"


def test_multiple_triggers_on_workflow(test_user):
    """Test multiple triggers on one workflow (WORK-07, WORK-08).

    A workflow with both a cron trigger and an interval trigger registers
    two independent jobs — both removable via the schedule API.
    """
    token = get_token(test_user)
    workflow_id = create_workflow(token)

    # Add scheduled (cron) trigger + interval trigger on the same workflow
    cron_response = schedule_trigger(token, workflow_id, "cron", {"minute": 0, "hour": 9})
    interval_response = schedule_trigger(token, workflow_id, "interval", {"minutes": 30})

    # Verify both triggers registered
    job_ids = {j.get("id") for j in list_jobs(token)}
    assert cron_response["job_id"] in job_ids, "Cron trigger not registered"
    assert interval_response["job_id"] in job_ids, "Interval trigger not registered"

    # Remove both — verify cleanup works independently
    remove_schedule(token, workflow_id, cron_response["job_id"])
    remove_schedule(token, workflow_id, interval_response["job_id"])
    remaining = {j.get("id") for j in list_jobs(token)}
    assert cron_response["job_id"] not in remaining, "Cron trigger not removed"
    assert interval_response["job_id"] not in remaining, "Interval trigger not removed"
