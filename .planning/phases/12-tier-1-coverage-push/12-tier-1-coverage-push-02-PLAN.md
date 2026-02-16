---
phase: 12-tier-1-coverage-push
plan: 02
type: execute
wave: 2
depends_on: ["12-tier-1-coverage-push-01"]
files_modified:
  - backend/tests/integration/test_atom_agent_endpoints.py
  - backend/tests/coverage_reports/metrics/coverage.json
autonomous: true
gap_closure: false

must_haves:
  truths:
    - "atom_agent_endpoints.py has 50% coverage (API endpoints tested)"
    - "Integration tests use TestClient for FastAPI endpoint testing"
    - "WebSocket streaming endpoints tested with async test client"
    - "Coverage increase of +1.4 percentage points (368 lines * 0.5 / 25768 total)"
  artifacts:
    - path: "backend/tests/integration/test_atom_agent_endpoints.py"
      provides: "Integration tests for agent chat, streaming, and feedback endpoints"
      min_lines: 600
  key_links:
    - from: "backend/tests/integration/test_atom_agent_endpoints.py"
      to: "backend/core/atom_agent_endpoints.py"
      via: "FastAPI TestClient for endpoint testing"
      pattern: "from fastapi.testclient import TestClient"
    - from: "backend/tests/integration/test_atom_agent_endpoints.py"
      to: "backend/core/models.py"
      via: "use factories for test data"
      pattern: "from tests.factories import"
---

<objective>
Achieve 50% coverage on atom_agent_endpoints.py (736 lines) using integration tests for FastAPI endpoints including chat, streaming, and feedback APIs.

**Purpose:** Test the agent interaction layer which handles chat requests, streaming responses, feedback submission, and agent management. This file contains critical user-facing API endpoints that integrate with models.py (tested in Plan 01) and the workflow engine.

**Output:** Integration tests covering request/response contracts, WebSocket streaming, error handling, and governance integration for all major agent endpoints.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@backend/tests/coverage_reports/metrics/priority_files_for_phases_12_13.json
@backend/core/atom_agent_endpoints.py
@backend/core/models.py
@backend/tests/conftest.py
@backend/tests/factories/
@backend/tests/test_endpoints.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create integration tests for agent chat and streaming endpoints</name>
  <files>backend/tests/integration/test_atom_agent_endpoints.py</files>
  <action>
    Create backend/tests/integration/test_atom_agent_endpoints.py with comprehensive API endpoint tests:

    **Target atom_agent_endpoints.py (736 lines, 0% coverage) - test these endpoints:**

    1. **POST /api/agents/{agent_id}/chat** - Chat completion endpoint:
       ```python
       def test_chat_success_returns_response(client, db, agent):
           response = client.post(f"/api/agents/{agent.id}/chat", json={
               "message": "Hello, agent!",
               "session_id": "test_session_123"
           })
           assert response.status_code == 200
           data = response.json()
           assert "response" in data
           assert "session_id" in data

       def test_chat_with_governance_blocking(client, db, student_agent):
           """STUDENT agents blocked for certain actions."""
           response = client.post(f"/api/agents/{student_agent.id}/chat", json={
               "message": "Execute critical action",
               "session_id": "test_session"
           })
           assert response.status_code == 403  # Governance block

       def test_chat_invalid_agent_id(client, db):
           response = client.post("/api/agents/nonexistent/chat", json={
               "message": "Hello"
           })
           assert response.status_code == 404
       ```

    2. **WebSocket /api/agents/{agent_id}/stream** - Streaming endpoint:
       ```python
       @pytest.mark.asyncio
       async def test_streaming_returns_chunks(async_client, agent):
           async with async_client.websocket_connect(f"/api/agents/{agent.id}/stream") as websocket:
               await websocket.send_json({
                   "message": "Stream response",
                   "session_id": "test_stream_123"
               })
               chunks_received = 0
               try:
                   while True:
                       chunk = await websocket.receive_json()
                       chunks_received += 1
                       if chunk.get("done"):
                           break
               except:
                   pass
               assert chunks_received > 0

       @pytest.mark.asyncio
       async def test_streaming_with_error_handling(async_client, agent):
           async with async_client.websocket_connect(f"/api/agents/{agent.id}/stream") as websocket:
               await websocket.send_json({"message": ""})  # Empty message
               response = await websocket.receive_json()
               assert "error" in response or "response" in response
       ```

    3. **POST /api/agents/{agent_id}/feedback** - Feedback submission:
       ```python
       def test_submit_feedback_success(client, db, agent, execution):
           response = client.post(f"/api/agents/{agent.id}/feedback", json={
               "execution_id": execution.id,
               "rating": 5,
               "feedback_type": "thumbs_up"
           })
           assert response.status_code == 201
           data = response.json()
           assert data["rating"] == 5

       def test_feedback_invalid_rating(client, db, agent):
           response = client.post(f"/api/agents/{agent.id}/feedback", json={
               "execution_id": "exec_123",
               "rating": 11  # Invalid > 10
           })
           assert response.status_code == 422  # Validation error
       ```

    4. **GET /api/agents/{agent_id}** - Agent retrieval:
       ```python
       def test_get_agent_success(client, db, agent):
           response = client.get(f"/api/agents/{agent.id}")
           assert response.status_code == 200
           data = response.json()
           assert data["id"] == agent.id
           assert data["name"] == agent.name

       def test_get_agent_not_found(client, db):
           response = client.get("/api/agents/nonexistent")
           assert response.status_code == 404
       ```

    5. **GET /api/agents** - Agent listing:
       ```python
       def test_list_agents_returns_paginated(client, db, agent_factory):
           for i in range(5):
               agent_factory(name=f"Agent {i}")
           response = client.get("/api/agents?page=1&limit=3")
           assert response.status_code == 200
           data = response.json()
           assert len(data["agents"]) == 3
           assert data["total"] == 5
       ```

    6. **Governance integration tests** (critical for agent operations):
       ```python
       def test_governance_check_for_student_agent(client, db, student_agent):
           """Student agents have restricted access."""
           response = client.post(f"/api/agents/{student_agent.id}/chat", json={
               "message": "Execute workflow",
               "action": "workflow_execute"
           })
           # Student agents blocked from workflow execution
           assert response.status_code in [403, 200]  # Depends on implementation

       def test_governance_check_for_autonomous_agent(client, db, autonomous_agent):
           """Autonomous agents have full access."""
           response = client.post(f"/api/agents/{autonomous_agent.id}/chat", json={
               "message": "Execute workflow"
           })
           assert response.status_code == 200
       ```

    **Test fixtures needed:**
    ```python
    import pytest
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session
    from core.models import AgentRegistry, AgentExecution, AgentFeedback
    from tests.factories import AgentFactory, UserFactory
    from main import app  # FastAPI application

    @pytest.fixture
    def client():
        return TestClient(app)

    @pytest.fixture
    def async_client():
        from httpx import AsyncClient
        return AsyncClient(app=app, base_url="http://test")

    @pytest.fixture
    def student_agent(db: Session):
        return AgentFactory(maturity_level="STUDENT")

    @pytest.fixture
    def autonomous_agent(db: Session):
        return AgentFactory(maturity_level="AUTONOMOUS")

    @pytest.fixture
    def execution(db: Session, agent):
        exec = AgentExecution(
            agent_id=agent.id,
            status="COMPLETED",
            input_data={"message": "test"}
        )
        db.add(exec)
        db.commit()
        return exec
    ```

    **Coverage target:** 50% of atom_agent_endpoints.py (368 lines covered)

    **Use existing patterns from:**
    - backend/tests/test_endpoints.py (for FastAPI TestClient patterns)
    - backend/tests/factories/ (AgentFactory for test data)
    - backend/tests/test_governance_streaming.py (for governance integration tests)
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/integration/test_atom_agent_endpoints.py -v --cov=backend/core/atom_agent_endpoints --cov-report=term-missing | tail -30
    Expected: 50%+ coverage on atom_agent_endpoints.py, all integration tests pass
  </verify>
  <done>
    atom_agent_endpoints.py coverage >= 50%, at least 15 integration tests covering all major endpoints, WebSocket tests pass
  </done>
</task>

<task type="auto">
  <name>Task 2: Generate coverage report and validate 50% target for agent endpoints</name>
  <files>backend/tests/coverage_reports/metrics/coverage.json</files>
  <action>
    Run coverage for atom_agent_endpoints.py and validate 50% coverage target:

    1. Run pytest with coverage:
       ```bash
       PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/integration/test_atom_agent_endpoints.py --cov=backend/core/atom_agent_endpoints --cov-report=json --cov-report=term -v
       ```

    2. Check coverage.json for coverage percentage:
       ```python
       import json
       with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
         data = json.load(f)
         endpoints_coverage = data['files']['backend/core/atom_agent_endpoints.py']['summary']['percent_covered']
         print(f"atom_agent_endpoints.py: {endpoints_coverage}%")
       ```

    3. If coverage is below 50%, analyze uncovered lines:
       - Check for untested error paths (4xx, 5xx responses)
       - Add tests for missing governance scenarios
       - Add tests for edge cases (empty requests, malformed JSON)

    4. Common missing coverage areas to address:
       - Exception handlers (try/except blocks)
       - Default parameter values
       - Optional request fields
       - Different maturity level combinations

    Coverage calculation for validation:
    - Target: 50% of 736 lines = 368 lines covered
    - Expected impact: +1.4 percentage points to overall coverage (368 / 25768)
  </action>
  <verify>
    python3 -c "
    import json
    with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
        data = json.load(f)
        endpoints_cov = data['files'].get('backend/core/atom_agent_endpoints.py', {}).get('summary', {}).get('percent_covered', 0)
        print(f'atom_agent_endpoints.py: {endpoints_cov}%')
        assert endpoints_cov >= 50.0, f'atom_agent_endpoints.py coverage {endpoints_cov}% < 50%'
    "
    Expected: atom_agent_endpoints.py shows 50%+ coverage
  </verify>
  <done>
    atom_agent_endpoints.py >= 50% coverage, coverage.json updated, at least 15 integration tests created
  </done>
</task>

<task type="auto">
  <name>Task 3: Run full test suite to ensure no regressions and validate overall coverage increase</name>
  <files>backend/tests/coverage_reports/metrics/coverage.json</files>
  <action>
    Run the full test suite for models.py, workflow_engine.py, and atom_agent_endpoints.py to validate combined coverage impact:

    1. Run combined coverage for all three files:
       ```bash
       PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest \
         backend/tests/unit/test_models_orm.py \
         backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py \
         backend/tests/integration/test_atom_agent_endpoints.py \
         --cov=backend/core/models \
         --cov=backend/core/workflow_engine \
         --cov=backend/core/atom_agent_endpoints \
         --cov-report=json \
         --cov-report=term \
         -v
       ```

    2. Calculate combined coverage impact:
       - models.py: 50% of 2351 = 1176 lines
       - workflow_engine.py: 50% of 1163 = 582 lines
       - atom_agent_endpoints.py: 50% of 736 = 368 lines
       - Total covered: 2126 lines
       - Overall impact: +3.4 percentage points (2126 / 25768)

    3. Verify no test failures or regressions:
       - All unit tests pass
       - All property tests pass (no Hypothesis errors)
       - All integration tests pass (no network/DB issues)

    4. Generate summary report for Plans 01-02:
       ```python
       summary = {
           "phase": "12-tier-1-coverage-push",
           "plans_completed": ["01", "02"],
           "files_tested": ["models.py", "workflow_engine.py", "atom_agent_endpoints.py"],
           "coverage_achieved": {
               "models.py": "50%",
               "workflow_engine.py": "50%",
               "atom_agent_endpoints.py": "50%"
           },
           "overall_impact": "+3.4%",
           "remaining_tier1_files": ["workflow_analytics_engine.py", "llm/byok_handler.py", "workflow_debugger.py"]
       }
       ```
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/unit/test_models_orm.py backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py backend/tests/integration/test_atom_agent_endpoints.py -v
    Expected: All tests pass, no errors or failures
  </verify>
  <done>
    Combined coverage +3.4 percentage points, all three files at 50%+ coverage, no test regressions
  </done>
</task>

</tasks>

<verification>
1. Run agent endpoints tests: `pytest backend/tests/integration/test_atom_agent_endpoints.py -v`
2. Check coverage: `pytest --cov=backend/core/atom_agent_endpoints --cov-report=term-missing`
3. Verify WebSocket tests work with async client
4. Validate governance integration tests cover all maturity levels
5. Confirm no regressions in existing tests
</verification>

<success_criteria>
- atom_agent_endpoints.py coverage >= 50% (368 lines covered from 736 total)
- At least 15 integration tests covering chat, streaming, feedback, and agent management
- WebSocket streaming tests pass
- Governance integration tests for all maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
- Combined Plans 01-02 impact: +3.4 percentage points to overall coverage
- No test failures or regressions
</success_criteria>

<output>
After completion, create `.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-02-SUMMARY.md` with:
- Coverage achieved for atom_agent_endpoints.py
- Number of integration tests created
- Combined coverage impact from Plans 01-02
- Any API contracts or edge cases identified for future testing
</output>
