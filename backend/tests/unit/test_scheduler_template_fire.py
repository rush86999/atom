"""
TDD regression test: WorkflowScheduler._execute_job only resolved scheduled
workflows via load_workflows() (workflows.json). DB templates (WorkflowTemplate)
are schedulable via POST /workflows/{id}/schedule but, when the job fired, the
scheduler logged "Scheduled workflow ... not found" and never started them.
A scheduled template fire must fall back to _load_template_definition, matching
POST /workflows/{id}/execute.
"""

import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, "/Users/rushiparikh/projects/atom/backend")

import pytest

from ai.workflow_scheduler import WorkflowScheduler


@pytest.mark.asyncio
async def test_scheduled_template_fire_uses_template_fallback():
    """A scheduled DB template (absent from workflows.json) must be resolved via
    the template fallback and started on the durable WorkflowEngine."""
    template_def = {"id": "tpl_1", "name": "Template", "steps": [
        {"id": "s1", "service": "http", "action": "get", "parameters": {}},
    ]}

    durable_engine = AsyncMock()

    with (
        patch("core.workflow_engine.get_workflow_engine", return_value=durable_engine),
        patch("core.workflow_endpoints.load_workflows", return_value=[]),
        patch("core.workflow_endpoints._load_template_definition", return_value=template_def),
    ):
        await WorkflowScheduler._execute_job("tpl_1", {"k": "v"}, authorized=True)

    assert durable_engine.start_workflow.await_count >= 1, (
        "scheduled template fire did not start the durable WorkflowEngine"
    )
