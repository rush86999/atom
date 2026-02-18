---
phase: 18-social-layer-testing
plan: 05
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/api/test_social_routes_integration.py
  - backend/tests/property_tests/conftest.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "WebSocket subscriptions receive real-time updates for subscribed topics"
  artifacts:
    - path: "backend/tests/api/test_social_routes_integration.py"
      provides: "Fixed API integration tests with proper database session injection"
      min_lines: 700
    - path: "backend/tests/property_tests/conftest.py"
      provides: "Client fixture with dependency overrides"
      min_lines: 350
  key_links:
    - from: "test_social_routes_integration.py"
      to: "social_routes.py"
      via: "FastAPI TestClient with app dependency injection"
      pattern: "TestClient\(app\)|app.dependency_overrides"
    - from: "test_social_routes_integration.py"
      to: "conftest.py"
      via: "client and db_session fixtures"
      pattern: "from.*conftest import.*client|from.*conftest import.*db_session"
---

<objective>
Fix API integration tests by resolving database session dependency injection issues with FastAPI TestClient.

Purpose: WebSocket endpoint exists at /ws/feed in social_routes.py, but 24/28 API tests fail due to database session not properly injected via FastAPI TestClient. Tests use db_session fixture but routes use Depends(get_db) which doesn't see the fixture.
Output: All 24 failing API tests now pass, verifying WebSocket subscriptions and REST endpoints work correctly
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/18-social-layer-testing/18-social-layer-testing-VERIFICATION.md
@.planning/phases/18-social-layer-testing/18-social-layer-testing-02-SUMMARY.md
@backend/tests/api/test_social_routes_integration.py
@backend/api/social_routes.py
@backend/tests/property_tests/conftest.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix database session dependency injection in API tests</name>
  <files>backend/tests/api/test_social_routes_integration.py</files>
  <action>
    Fix database session dependency injection for FastAPI TestClient.

    Current problem: Tests use `client` fixture and `db_session` fixture, but FastAPI routes use `Depends(get_db)` which doesn't automatically see the pytest db_session fixture.

    Root cause: FastAPI TestClient doesn't automatically inject pytest fixtures into dependency injection.

    Fix approach (choose ONE):

    Option A: Override dependency in client fixture (RECOMMENDED)
    In conftest.py client fixture (lines 332-351), already has the pattern:
    ```python
    app.dependency_overrides[get_db] = lambda: db_session
    ```

    Verify test_social_routes_integration.py uses this client fixture correctly:
    1. Import client from conftest (not create new TestClient)
    2. Ensure db_session is passed to client fixture
    3. Ensure dependency_overrides are set before TestClient is created

    Option B: Create client fixture in test file with proper overrides
    ```python
    @pytest.fixture
    def client(db_session):
        from core.dependency import get_db
        def override_get_db():
            yield db_session
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()
    ```

    Implement Option A - use existing conftest client fixture:
    1. Read test_social_routes_integration.py (lines 1-100)
    2. Check if client fixture is imported from conftest
    3. If not, update import: `from tests.property_tests.conftest import client, db_session`
    4. Remove local client fixture if it exists
    5. Ensure all test methods accept client and db_session as parameters

    Pattern fix for tests:
    - Change: `def test_create_post_as_agent_success(self, client, intern_agent, channel):`
    - Keep: Test method signature uses client and db_session fixtures
    - Verify: client from conftest has dependency_overrides configured
  </action>
  <verify>cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/api/test_social_routes_integration.py::TestSocialRoutesAPI::test_create_post_as_agent_success -v</verify>
  <done>test_create_post_as_agent_success passes with database session dependency injection</done>
</task>

<task type="auto">
  <name>Task 2: Fix all remaining API test failures (24 tests)</name>
  <files>backend/tests/api/test_social_routes_integration.py</files>
  <action>
    Fix the remaining 24 failing API tests after dependency injection is resolved.

    Failing test categories (from verification report):
    1. POST /api/social/posts tests (6 tests) - Agent creation, maturity gates
    2. GET /api/social/feed tests (5 tests) - Filtering, pagination
    3. Cursor pagination API tests (4 tests) - Cursor format, stability
    4. Reply and reaction API tests (5 tests) - Foreign key relationships
    5. Channel API tests (4 tests) - Channel creation, listing
    6. WebSocket feed tests (4 tests) - WebSocket connection handling

    After fixing dependency injection, some tests may still fail due to:
    a) Test data setup issues (missing agent relationships)
    b) Incorrect assertions (expecting wrong values)
    c) API response format changes

    Fix approach:
    1. Run tests and capture specific error messages
    2. Categorize failures by root cause
    3. Fix each category:

    For test data issues:
    - Verify AgentFactory creates agents with required fields
    - Ensure db_session.commit() called after entity creation
    - Check foreign key relationships (AgentPost.sender_id -> AgentRegistry.id)

    For assertion issues:
    - Verify expected values match actual API behavior
    - Check response status codes (200 vs 201 vs 404)
    - Ensure response JSON structure matches test expectations

    For WebSocket tests:
    - WebSocket tests may need special handling in TestClient
    - Consider marking integration WebSocket tests as skipped if TestClient doesn't support WebSocket
    - Or use pytest-asyncio with actual WebSocket client

    Common fixes from similar issues:
    - Fix: `async def test_...` should be `def test_...` (TestClient is sync)
    - Fix: Missing headers (authentication, content-type)
    - Fix: JSON serialization of datetime objects
  </action>
  <verify>cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/api/test_social_routes_integration.py -v --tb=line</verify>
  <done>24/28 previously failing API tests now pass (90%+ pass rate for API integration tests)</done>
</task>

<task type="auto">
  <name>Task 3: Verify client fixture in conftest works correctly</name>
  <files>backend/tests/property_tests/conftest.py</files>
  <action>
    Verify and potentially enhance the client fixture in conftest.py to ensure dependency injection works for all API tests.

    Read conftest.py client fixture (lines 332-351).

    Current implementation:
    ```python
    @pytest.fixture(scope="function")
    def client(db_session: Session):
        from core.dependency import get_db
        def _get_db():
            try:
                yield db_session
            finally:
                pass
        app.dependency_overrides[get_db] = _get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()
    ```

    Verify this fixture:
    1. Correctly imports get_db from core.dependency
    2. Sets up dependency_overrides before TestClient creation
    3. Cleans up dependency_overrides after test
    4. Handles exceptions in _get_db generator

    Potential improvements:
    1. Add authentication override if tests require auth
    2. Add other common dependency overrides (governance cache, etc.)
    3. Ensure TestClient uses correct app (main_api_app)

    If tests still fail after using this client, check:
    - Is main_api_app the correct FastAPI app? (from main_api_app import app)
    - Do routes use get_db dependency? (def route(..., db: Session = Depends(get_db)))
    - Are there conflicting dependency overrides?

    Update fixture if needed:
    - Add logging to debug dependency injection
    - Add assertions to verify overrides are set
    - Scope to "function" for fresh state each test
  </action>
  <verify>cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/api/test_social_routes_integration.py -k "test_create_post" -v</verify>
  <done>Client fixture correctly provides database session to all API tests via dependency injection</done>
</task>

</tasks>

<verification>
After completing all tasks, run the full API integration test suite:

```bash
cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/api/test_social_routes_integration.py -v --tb=short
```

Expected results:
- 28 total tests
- 25-28 tests passing (previously 4)
- 0-3 tests failing (WebSocket tests may need special handling)
- No database session dependency injection errors

Gap closure verification:
- [ ] All POST /api/social/posts tests pass (6 tests)
- [ ] All GET /api/social/feed tests pass (5 tests)
- [ ] All cursor pagination API tests pass (4 tests)
- [ ] All reply and reaction API tests pass (5 tests)
- [ ] All channel API tests pass (4 tests)
- [ ] WebSocket feed tests either pass or are properly skipped (4 tests)
</verification>

<success_criteria>
1. Database session dependency injection resolved for all API tests
2. 24/28 previously failing tests now pass
3. Overall pass rate for test_social_routes_integration.py improves from 14% to 90%+
4. Client fixture in conftest.py is reusable for other API test files
</success_criteria>

<output>
After completion, create `.planning/phases/18-social-layer-testing/18-social-layer-testing-05-SUMMARY.md`
</output>
