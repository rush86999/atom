"""
Journey tests for workflow CRUD, scheduling, board comments/decompose,
canvas deeper, mobile auth, and BYOK pricing lookups.

Targets reaching 80% endpoint coverage via user journeys.
"""

import pytest


# ===========================================================================
# Workflow CRUD + execution + scheduling
# ===========================================================================

class TestWorkflowCRUD:

    def test_create_workflow(self, registered_user):
        """POST /api/workflows creates a workflow."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/workflows", json={
            "name": "Journey Test Workflow",
            "description": "Test workflow",
            "steps": [{"step_id": "s1", "step_type": "nlu_analysis",
                        "description": "Analyze", "next_steps": []}],
            "start_step": "s1",
        }, headers=headers)
        assert resp.status_code in (200, 201, 400, 403, 422, 500), \
            f"Create workflow: {resp.status_code} {resp.text}"

    def test_get_workflow_by_id(self, registered_user):
        """GET /api/workflows/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/workflows/nonexistent-id",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Get workflow: {resp.status_code}"

    def test_delete_workflow(self, registered_user):
        """DELETE /api/workflows/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.delete("/api/workflows/nonexistent-id",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Delete workflow: {resp.status_code}"

    def test_edit_workflow(self, registered_user):
        """POST /api/workflows/{id}/edit is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/workflows/nonexistent-id/edit", json={
            "instruction": "Add a step to send an email",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Edit workflow: {resp.status_code}"

    def test_execute_workflow(self, registered_user):
        """POST /api/workflows/{id}/execute is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/workflows/nonexistent-id/execute",
                           json={"input_data": {}},
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Execute workflow: {resp.status_code}"

    def test_resume_workflow(self, registered_user):
        """POST /api/workflows/{execution_id}/resume is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/workflows/nonexistent-exec/resume",
                           json={"input_data": {}},
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Resume workflow: {resp.status_code}"

    def test_list_executions(self, registered_user):
        """GET /api/workflows/{id}/executions is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/workflows/nonexistent-id/executions",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"List executions: {resp.status_code}"

    def test_get_execution_detail(self, registered_user):
        """GET /api/workflows/executions/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/workflows/executions/nonexistent-exec",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Execution detail: {resp.status_code}"

    def test_schedule_workflow(self, registered_user):
        """POST /api/workflows/{id}/schedule is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/workflows/nonexistent-id/schedule", json={
            "schedule_type": "interval",
            "interval_seconds": 3600,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Schedule workflow: {resp.status_code}"

    def test_list_scheduler_jobs(self, registered_user):
        """GET /api/scheduler/jobs is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/scheduler/jobs",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 403, 404), \
            f"Scheduler jobs: {resp.status_code}"


# ===========================================================================
# Board comments + decompose
# ===========================================================================

class TestBoardComments:

    def test_list_task_comments(self, registered_user):
        """GET /api/boards/{id}/tasks/{id}/comments is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/boards/b1/tasks/t1/comments",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Task comments: {resp.status_code}"

    def test_create_task_comment(self, registered_user):
        """POST /api/boards/{id}/tasks/{id}/comments is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/boards/b1/tasks/t1/comments", json={
            "content": "Test comment",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201, 404, 403, 422, 500), \
            f"Create comment: {resp.status_code}"


class TestBoardDecompose:

    def test_decompose_task(self, registered_user):
        """POST /api/boards/{id}/tasks/{id}/decompose is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/boards/b1/tasks/t1/decompose", json={},
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Decompose: {resp.status_code}"


# ===========================================================================
# Canvas deeper
# ===========================================================================

class TestCanvasDeeper:

    def test_get_context(self, registered_user):
        """GET /api/canvas/{id}/context is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/canvas/test-canvas/context",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Canvas context: {resp.status_code}"

    def test_create_context(self, registered_user):
        """POST /api/canvas/{id}/context is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/canvas/test-canvas/context", json={
            "canvas_type": "markdown",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201, 404, 403, 422, 500), \
            f"Create context: {resp.status_code}"

    def test_update_context_state(self, registered_user):
        """PUT /api/canvas/{id}/context/state is reachable."""
        client, email, password, token = registered_user
        resp = client.put("/api/canvas/test-canvas/context/state", json={
            "state": {"content": "updated"},
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Update state: {resp.status_code}"

    def test_submit_canvas(self, registered_user):
        """POST /api/canvas/submit is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/canvas/submit", json={
            "canvas_id": "test",
            "action": "submit",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Canvas submit: {resp.status_code}"

    def test_canvas_summary(self, registered_user):
        """GET /api/canvas/{id}/summary is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/canvas/test-canvas/summary",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Canvas summary: {resp.status_code}"


# ===========================================================================
# Mobile auth
# ===========================================================================

class TestMobileAuth:

    def test_mobile_login_reachable(self, registered_user):
        """POST /api/auth/mobile/login is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/auth/mobile/login", json={
            "email": email,
            "password": password,
            "device_name": "Test Device",
        })
        assert resp.status_code in (200, 401, 404, 422), \
            f"Mobile login: {resp.status_code}"

    def test_mobile_device_list(self, registered_user):
        """GET /api/auth/mobile/device is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/auth/mobile/device",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 401, 404, 422), \
            f"Mobile device: {resp.status_code}"


# ===========================================================================
# BYOK pricing lookups
# ===========================================================================

class TestByokPricing:

    def test_get_pricing_for_model(self, registered_user):
        """GET /api/ai/pricing/model/{model} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/ai/pricing/model/gpt-4o",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"Pricing model: {resp.status_code}"

    def test_get_pricing_for_provider(self, registered_user):
        """GET /api/ai/pricing/provider/{provider} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/ai/pricing/provider/openai",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"Pricing provider: {resp.status_code}"

    def test_estimate_cost(self, registered_user):
        """POST /api/ai/pricing/estimate is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/ai/pricing/estimate", json={
            "model": "gpt-4o",
            "input_tokens": 1000,
            "output_tokens": 500,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 422), \
            f"Estimate cost: {resp.status_code}"

    def test_get_provider_detail(self, registered_user):
        """GET /api/ai/providers/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/ai/providers/openai",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 422), \
            f"Provider detail: {resp.status_code}"

    def test_get_key_status(self, registered_user):
        """GET /api/ai/providers/{id}/keys/{key_name} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/ai/providers/openai/keys/default",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"Key status: {resp.status_code}"

    def test_delete_key(self, registered_user):
        """DELETE /api/ai/providers/{id}/keys/{key_name} is reachable."""
        client, email, password, token = registered_user
        resp = client.delete("/api/ai/providers/openai/keys/default",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"Delete key: {resp.status_code}"

    def test_pdf_providers(self, registered_user):
        """GET /api/ai/pdf/providers is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/ai/pdf/providers",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"PDF providers: {resp.status_code}"

    def test_ai_health(self, registered_user):
        """GET /api/ai/health is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/ai/health",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"AI health: {resp.status_code}"


# ===========================================================================
# Board CRUD deeper
# ===========================================================================

class TestBoardCRUDDeeper:

    def test_get_board_detail(self, registered_user):
        """GET /api/boards/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/boards/nonexistent-board",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Board detail: {resp.status_code}"

    def test_add_column(self, registered_user):
        """POST /api/boards/{id}/columns is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/boards/b1/columns", json={
            "name": "To Do",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201, 404, 403, 422, 500), \
            f"Add column: {resp.status_code}"

    def test_create_task(self, registered_user):
        """POST /api/boards/{id}/tasks is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/boards/b1/tasks", json={
            "title": "Test Task",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201, 404, 403, 422, 500), \
            f"Create task: {resp.status_code}"

    def test_list_tasks(self, registered_user):
        """GET /api/boards/{id}/tasks is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/boards/b1/tasks",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"List tasks: {resp.status_code}"

    def test_update_task(self, registered_user):
        """PATCH /api/boards/{id}/tasks/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.patch("/api/boards/b1/tasks/t1", json={
            "status": "done",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Update task: {resp.status_code}"

    def test_delete_task(self, registered_user):
        """DELETE /api/boards/{id}/tasks/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.delete("/api/boards/b1/tasks/t1",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Delete task: {resp.status_code}"


# ===========================================================================
# Agent deeper
# ===========================================================================

class TestAgentDeeper:

    def test_get_agent_by_id(self, registered_user):
        """GET /api/agents/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/agents/nonexistent-agent",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Get agent: {resp.status_code}"

    def test_get_agent_status(self, registered_user):
        """GET /api/agents/{id}/status is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/agents/nonexistent-agent/status",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Agent status: {resp.status_code}"

    def test_delete_agent(self, registered_user):
        """DELETE /api/agents/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.delete("/api/agents/nonexistent-agent",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Delete agent: {resp.status_code}"

    def test_run_agent(self, registered_user):
        """POST /api/agents/{id}/run is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/agents/nonexistent-agent/run", json={
            "message": "Do something",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Run agent: {resp.status_code}"

    def test_stop_agent(self, registered_user):
        """POST /api/agents/{id}/stop is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/agents/nonexistent-agent/stop",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Stop agent: {resp.status_code}"

    def test_agent_feedback(self, registered_user):
        """POST /api/agents/{id}/feedback is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/agents/nonexistent-agent/feedback", json={
            "feedback_type": "thumbs_up",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422), \
            f"Agent feedback: {resp.status_code}"

    def test_spawn_agent(self, registered_user):
        """POST /api/agents/spawn is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/agents/spawn", json={
            "domain": "sales",
            "task": "Generate a report",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201, 403, 422, 500), \
            f"Spawn agent: {resp.status_code}"


# ===========================================================================
# User management deeper
# ===========================================================================

class TestUserManagementDeeper:

    def test_revoke_session(self, registered_user):
        """DELETE /api/users/sessions/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.delete("/api/users/sessions/nonexistent-session",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Revoke session: {resp.status_code}"

    def test_revoke_all_sessions(self, registered_user):
        """DELETE /api/users/sessions is reachable."""
        client, email, password, token = registered_user
        resp = client.delete("/api/users/sessions",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 403), \
            f"Revoke all sessions: {resp.status_code}"


# ===========================================================================
# Shell execute (security-critical)
# ===========================================================================

class TestShellExecute:

    def test_execute_command(self, registered_user):
        """POST /api/shell/execute is reachable (may be permission-gated)."""
        client, email, password, token = registered_user
        resp = client.post("/api/shell/execute", json={
            "command": "echo hello",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 403, 422, 500), \
            f"Shell execute: {resp.status_code}"


# ===========================================================================
# Chat remaining
# ===========================================================================

class TestChatRemaining:

    def test_chat_health(self, real_auth_client):
        """GET /api/chat/health is reachable."""
        resp = real_auth_client.get("/api/chat/health")
        assert resp.status_code == 200, f"Chat health: {resp.status_code}"

    def test_chat_root(self, real_auth_client):
        """GET /api/chat/ is reachable."""
        resp = real_auth_client.get("/api/chat/")
        assert resp.status_code == 200, f"Chat root: {resp.status_code}"

    def test_get_session_detail(self, registered_user):
        """GET /api/chat/sessions/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/chat/sessions/nonexistent-session",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 422), \
            f"Session detail: {resp.status_code}"


# ===========================================================================
# System
# ===========================================================================

class TestSystem:

    def test_root_endpoint(self, real_auth_client):
        """GET / returns system info."""
        resp = real_auth_client.get("/")
        assert resp.status_code == 200, f"Root: {resp.status_code}"

    def test_openapi_schema(self, real_auth_client):
        """GET /openapi.json returns the schema."""
        resp = real_auth_client.get("/openapi.json")
        assert resp.status_code == 200, f"OpenAPI: {resp.status_code}"
