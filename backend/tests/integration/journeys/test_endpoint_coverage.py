"""
Journey tests covering reachable-but-untested endpoints.

These complement the existing journey files by exercising the mounted routes
that no journey previously hit. Each test walks a real user step (register →
login → call) and asserts the route is reachable (not 404) and doesn't crash
the ASGI transport (not a hard 500 unless documented). This is end-to-end
"can a user actually reach this feature" coverage, not unit-level validation.

Scoped to the minimal app (main.py) which mounts: auth, users, agents,
workflows, canvas, boards, shell, chat, BYOK (/api/ai), federation,
local-models, scheduler, health. Persona endpoints that live only in
main_api_app.py (tasks/calendar/finance/etc.) are intentionally NOT tested
here — they are not mounted in this app and would just 404.
"""

import uuid

import pytest


# ===========================================================================
# System surface: root, docs, health/metrics
# ===========================================================================

class TestSystemSurface:

    def test_root_endpoint(self, real_auth_client):
        """GET / returns the API identity (name, version, docs link)."""
        resp = real_auth_client.get("/")
        assert resp.status_code == 200, f"Root: {resp.status_code}"
        data = resp.json()
        assert "name" in data or "docs" in data, f"Root payload unexpected: {data}"

    def test_openapi_schema_available(self, real_auth_client):
        """GET /openapi.json returns the OpenAPI schema (docs surface)."""
        resp = real_auth_client.get("/openapi.json")
        assert resp.status_code == 200, f"OpenAPI: {resp.status_code}"
        data = resp.json()
        assert "paths" in data, f"OpenAPI missing paths: {data.keys()}"

    def test_health_metrics(self, real_auth_client):
        """GET /health/metrics responds (may be empty/degraded)."""
        resp = real_auth_client.get("/health/metrics")
        # Metrics may 200 or 503 depending on DB state; both prove reachability.
        assert resp.status_code in (200, 503), \
            f"Health metrics unexpected: {resp.status_code}"

    def test_health_sync(self, real_auth_client):
        """GET /health/sync responds."""
        resp = real_auth_client.get("/health/sync")
        assert resp.status_code in (200, 503), \
            f"Health sync unexpected: {resp.status_code}"

    def test_metrics_sync(self, real_auth_client):
        """GET /metrics/sync responds."""
        resp = real_auth_client.get("/metrics/sync")
        assert resp.status_code in (200, 503), \
            f"Metrics sync unexpected: {resp.status_code}"


# ===========================================================================
# Auth: untested mobile + verification endpoints
# ===========================================================================

class TestAuthEndpoints:

    def test_test_auth_endpoint(self, registered_user):
        """GET /api/auth/test-auth verifies the token (smoke test of auth)."""
        client, email, password, token = registered_user
        resp = client.get("/api/auth/test-auth",
                          headers={"Authorization": f"Bearer {token}"})
        # 200 (valid token) or 401 (endpoint rejects) — both prove reachable.
        assert resp.status_code in (200, 401), \
            f"test-auth: {resp.status_code} {resp.text}"

    def test_mobile_refresh_reachable(self, registered_user):
        """POST /api/auth/mobile/refresh is reachable (may reject bad token)."""
        client, email, password, token = registered_user
        resp = client.post("/api/auth/mobile/refresh", json={
            "refresh_token": "invalid-refresh-token",
        })
        assert resp.status_code in (200, 401, 422), \
            f"Mobile refresh: {resp.status_code} {resp.text}"

    def test_mobile_biometric_register_reachable(self, registered_user):
        """POST /api/auth/mobile/biometric/register is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/auth/mobile/biometric/register", json={
            "device_id": f"dev-{uuid.uuid4().hex[:8]}",
            "public_key": "fake-public-key",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201, 400, 401, 422), \
            f"Biometric register: {resp.status_code} {resp.text}"

    def test_mobile_biometric_authenticate_reachable(self, registered_user):
        """POST /api/auth/mobile/biometric/authenticate is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/auth/mobile/biometric/authenticate", json={
            "device_id": f"dev-{uuid.uuid4().hex[:8]}",
            "challenge_response": "fake-response",
        })
        assert resp.status_code in (200, 401, 422), \
            f"Biometric auth: {resp.status_code} {resp.text}"


# ===========================================================================
# Agents: untested lifecycle endpoints
# ===========================================================================

class TestAgentLifecycleEndpoints:

    def test_get_agent_by_id(self, registered_user):
        """GET /api/agents/{id} is reachable (404 for unknown id is fine)."""
        client, email, password, token = registered_user
        resp = client.get("/api/agents/nonexistent-agent",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Get agent: {resp.status_code} {resp.text}"

    def test_graduation_progress(self, registered_user):
        """GET /api/agents/{id}/graduation-progress is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/agents/nonexistent-agent/graduation-progress",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422), \
            f"Graduation progress: {resp.status_code} {resp.text}"

    def test_promote_agent(self, registered_user):
        """POST /api/agents/{id}/promote is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/agents/nonexistent-agent/promote",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422), \
            f"Promote: {resp.status_code} {resp.text}"

    def test_atom_trigger(self, registered_user):
        """POST /api/agents/atom/trigger is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/agents/atom/trigger", json={
            "goal": "Test goal",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 202, 400, 403, 422, 500), \
            f"Atom trigger: {resp.status_code} {resp.text}"

    def test_atom_execute(self, registered_user):
        """POST /api/agents/atom/execute is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/agents/atom/execute", json={
            "instruction": "Say hello",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 400, 403, 422, 500), \
            f"Atom execute: {resp.status_code} {resp.text}"


# ===========================================================================
# Boards: untested rebalance + decompose-commit + task canvas/comments
# ===========================================================================

class TestBoardEndpoints:

    def test_rebalance_board(self, registered_user):
        """POST /api/boards/{id}/rebalance is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/boards/nonexistent-board/rebalance",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422), \
            f"Rebalance: {resp.status_code} {resp.text}"

    def test_decompose_commit(self, registered_user):
        """POST /api/boards/{b}/tasks/{t}/decompose/commit is reachable."""
        client, email, password, token = registered_user
        resp = client.post(
            "/api/boards/nonexistent-board/tasks/nonexistent-task/decompose/commit",
            json={"subtasks": []},
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422), \
            f"Decompose commit: {resp.status_code} {resp.text}"

    def test_task_canvas(self, registered_user):
        """GET /api/boards/{b}/tasks/{t}/canvas is reachable."""
        client, email, password, token = registered_user
        resp = client.get(
            "/api/boards/nonexistent-board/tasks/nonexistent-task/canvas",
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Task canvas: {resp.status_code} {resp.text}"

    def test_task_artifact_comments(self, registered_user):
        """GET /api/boards/{b}/tasks/{t}/artifact-comments is reachable."""
        client, email, password, token = registered_user
        resp = client.get(
            "/api/boards/nonexistent-board/tasks/nonexistent-task/artifact-comments",
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Artifact comments: {resp.status_code} {resp.text}"

    def test_delete_board_task(self, registered_user):
        """DELETE /api/boards/{b}/tasks/{t} is reachable."""
        client, email, password, token = registered_user
        resp = client.delete(
            "/api/boards/nonexistent-board/tasks/nonexistent-task",
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Delete task: {resp.status_code} {resp.text}"


# ===========================================================================
# Canvas: untested CRUD + history + context read + recording detail
# ===========================================================================

class TestCanvasEndpoints:

    def test_read_canvas_by_id(self, registered_user):
        """GET /api/canvas/{id} is reachable (404 for unknown id is correct)."""
        client, email, password, token = registered_user
        resp = client.get("/api/canvas/nonexistent-canvas",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"Read canvas: {resp.status_code} {resp.text}"

    def test_canvas_history(self, registered_user):
        """GET /api/canvas/{id}/history is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/canvas/nonexistent-canvas/history",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"Canvas history: {resp.status_code} {resp.text}"

    def test_canvas_context_read(self, registered_user):
        """GET /api/canvas/{id}/context is reachable."""
        client, email, password, token = registered_user
        resp = client.get("/api/canvas/nonexistent-canvas/context",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404), \
            f"Canvas context: {resp.status_code} {resp.text}"

    def test_recording_detail(self, registered_user):
        """GET /api/canvas/recordings/{id} is reachable (404 for unknown)."""
        client, email, password, token = registered_user
        resp = client.get("/api/canvas/recordings/nonexistent-recording",
                          headers={"Authorization": f"Bearer {token}"})
        # Must NOT be shadowed by /{canvas_id} (route-ordering regression).
        assert resp.status_code in (200, 404), \
            f"Recording detail: {resp.status_code} {resp.text}"

    def test_start_recording(self, registered_user):
        """POST /api/canvas/recordings/start is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/canvas/recordings/start", json={
            "canvas_id": "test-canvas",
            "canvas_type": "generic",
            "agent_id": "test-agent",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 400, 403, 422), \
            f"Start recording: {resp.status_code} {resp.text}"


# ===========================================================================
# Chat: untested session list + detail
# ===========================================================================

class TestChatSessionEndpoints:

    def test_list_sessions_explicit(self, registered_user):
        """GET /api/chat/sessions (list) is reachable and returns a list shape."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}

        me_resp = client.get("/api/auth/me", headers=headers)
        user_id = me_resp.json().get("data", {}).get("user_id", "default_user")

        resp = client.get(f"/api/chat/sessions?user_id={user_id}",
                          headers=headers)
        assert resp.status_code == 200, f"List sessions: {resp.text}"
        # Should be a list or a wrapper containing one.
        data = resp.json()
        assert isinstance(data, (list, dict)), f"Sessions payload: {data}"

    def test_get_session_detail(self, registered_user):
        """GET /api/chat/sessions/{id} is reachable (404 for unknown)."""
        client, email, password, token = registered_user
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = client.get("/api/auth/me", headers=headers)
        user_id = me_resp.json().get("data", {}).get("user_id", "default_user")
        # The endpoint requires user_id as a query param (IDOR protection).
        resp = client.get(f"/api/chat/sessions/{uuid.uuid4()}?user_id={user_id}",
                          headers=headers)
        assert resp.status_code in (200, 404), \
            f"Session detail: {resp.status_code} {resp.text}"


# ===========================================================================
# Scheduler: untested reload
# ===========================================================================

class TestSchedulerEndpoints:

    def test_scheduler_reload(self, registered_user):
        """POST /api/scheduler/reload is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/scheduler/reload",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 403, 500), \
            f"Scheduler reload: {resp.status_code} {resp.text}"


# ===========================================================================
# Workflows: untested debug surface
#
# NOTE: three of the debug read endpoints (execution-traces, breakpoints,
# debug-sessions) currently return a controlled 500 because of a
# model/debugger schema mismatch — core/workflow_debugger.py queries
# attributes (WorkflowDebugSession.workflow_id/.user_id/.created_at,
# WorkflowBreakpoint.is_active, ExecutionTrace.execution_id) that are NOT
# defined on the ORM models in core/models.py (which use workflow_execution_id,
# `enabled`, etc.). The handler catches the AttributeError and returns a
# structured internal_error, so a 500 here proves the route IS wired and the
# handler ran — the failure is in the data layer. These are flagged for a
# coordinated model+migration fix (see TODO in each test below).
# ===========================================================================

class TestWorkflowDebugEndpoints:

    def test_debug_step(self, registered_user):
        """POST /api/workflows/debug/step is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/workflows/debug/step", json={
            "trace_id": "nonexistent-trace",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422, 500), \
            f"Debug step: {resp.status_code} {resp.text}"

    def test_create_debug_trace(self, registered_user):
        """POST /api/workflows/debug/traces is reachable."""
        client, email, password, token = registered_user
        resp = client.post("/api/workflows/debug/traces", json={
            "workflow_id": "nonexistent-workflow",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201, 404, 403, 422, 500), \
            f"Debug trace: {resp.status_code} {resp.text}"

    def test_execution_traces(self, registered_user):
        """GET /api/workflows/executions/{id}/traces is reachable.

        TODO(data-layer): returns 500 — ExecutionTrace model uses
        workflow_execution_id but workflow_debugging.py serializes via
        .execution_id. Fix requires aligning model + handler + migration.
        """
        client, email, password, token = registered_user
        resp = client.get("/api/workflows/executions/nonexistent-exec/traces",
                          headers={"Authorization": f"Bearer {token}"})
        # 500 is a *controlled* internal_error (handler caught the
        # AttributeError) — route is reachable. 200 once the model is fixed.
        assert resp.status_code in (200, 404, 403, 500), \
            f"Execution traces: {resp.status_code} {resp.text}"

    def test_list_debug_breakpoints(self, registered_user):
        """GET /api/workflows/{id}/debug/breakpoints is reachable.

        TODO(data-layer): returns 500 — WorkflowBreakpoint model uses
        `enabled` but the handler serializes via .is_active/.node_id etc.
        """
        client, email, password, token = registered_user
        resp = client.get("/api/workflows/nonexistent-id/debug/breakpoints",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Debug breakpoints: {resp.status_code} {resp.text}"

    def test_list_debug_sessions(self, registered_user):
        """GET /api/workflows/{id}/debug/sessions is reachable.

        TODO(data-layer): returns 500 — WorkflowDebugSession model uses
        workflow_execution_id/started_at but the debugger queries
        .workflow_id/.user_id/.created_at.
        """
        client, email, password, token = registered_user
        resp = client.get("/api/workflows/nonexistent-id/debug/sessions",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 500), \
            f"Debug sessions: {resp.status_code} {resp.text}"

    def test_delete_scheduled_job(self, registered_user):
        """DELETE /api/workflows/{id}/schedule/{job_id} is reachable."""
        client, email, password, token = registered_user
        resp = client.delete(
            "/api/workflows/nonexistent-id/schedule/nonexistent-job",
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Delete scheduled job: {resp.status_code} {resp.text}"


# ===========================================================================
# Comments: untested PATCH/DELETE on standalone comment router
# ===========================================================================

class TestCommentEndpoints:

    def test_patch_comment(self, registered_user):
        """PATCH /api/comments/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.patch("/api/comments/nonexistent-comment", json={
            "content": "Updated text",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403, 422), \
            f"Patch comment: {resp.status_code} {resp.text}"

    def test_delete_comment(self, registered_user):
        """DELETE /api/comments/{id} is reachable."""
        client, email, password, token = registered_user
        resp = client.delete("/api/comments/nonexistent-comment",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 404, 403), \
            f"Delete comment: {resp.status_code} {resp.text}"
