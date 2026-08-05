"""
TDD regression test: WorkflowScheduler._execute_job fired scheduled workflows
through the legacy AutomationEngine (executions.json), so scheduled executions
never appeared in the durable DB WorkflowExecution table and were invisible in
the Executions tab. Scheduled runs must use the durable WorkflowEngine, matching
POST /workflows/{id}/execute.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from ai.workflow_scheduler import WorkflowScheduler


@pytest.mark.asyncio
async def test_scheduled_job_uses_durable_engine():
    """A scheduled fire must persist via the durable WorkflowEngine (DB row),
    not the legacy AutomationEngine (executions.json)."""
    benign_wf = {"id": "wf_1", "name": "Benign", "steps": [
        {"id": "s1", "service": "http", "action": "get", "parameters": {}},
    ]}

    durable_engine = AsyncMock()

    with (
        patch("core.workflow_engine.get_workflow_engine", return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[benign_wf]),
    ):
        await WorkflowScheduler._execute_job("wf_1", {"k": "v"}, authorized=True)

    assert durable_engine.start_workflow.await_count >= 1, (
        "scheduled execution did not run through the durable WorkflowEngine"
    )
