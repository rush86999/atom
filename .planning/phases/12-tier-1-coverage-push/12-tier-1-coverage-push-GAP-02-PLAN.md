---
phase: 12-tier-1-coverage-push
plan: GAP-02
type: execute
wave: 2
depends_on: ["12-tier-1-coverage-push-GAP-01"]
files_modified:
  - backend/tests/integration/test_workflow_engine_integration.py
  - backend/tests/integration/test_byok_handler_integration.py
  - backend/tests/integration/test_workflow_analytics_integration.py
  - backend/tests/coverage_reports/metrics/coverage.json
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "workflow_engine.py coverage increases from 9.17% to 40%+ (integration tests for async paths)"
    - "byok_handler.py coverage increases from 11.27% to 40%+ (integration tests with mocked LLMs)"
    - "workflow_analytics_engine.py coverage increases from 27.77% to 50%+ (integration tests with DB)"
    - "Integration tests use pytest fixtures with mocked external dependencies"
    - "Tests call actual implementation methods (not just validate invariants)"
  artifacts:
    - path: "backend/tests/integration/test_workflow_engine_integration.py"
      provides: "Integration tests for workflow async execution paths"
      min_lines: 500
    - path: "backend/tests/integration/test_byok_handler_integration.py"
      provides: "Integration tests for LLM provider routing with mocked clients"
      min_lines: 400
    - path: "backend/tests/integration/test_workflow_analytics_integration.py"
      provides: "Integration tests for analytics with database interactions"
      min_lines: 350
  key_links:
    - from: "backend/tests/integration/test_workflow_engine_integration.py"
      to: "backend/core/workflow_engine.py"
      via: "from core.workflow_engine import WorkflowEngine"
      pattern: "WorkflowEngine\\(\\), engine\\.execute_workflow\\(\\)"
    - from: "backend/tests/integration/test_byok_handler_integration.py"
      to: "backend/core/llm/byok_handler.py"
      via: "from core.llm.byok_handler import BYOKHandler"
      pattern: "BYOKHandler\\(\\), handler\\.stream_completion\\(\\)"
    - from: "backend/tests/integration/test_workflow_analytics_integration.py"
      to: "backend/core/workflow_analytics_engine.py"
      via: "from core.workflow_analytics_engine import AnalyticsEngine"
      pattern: "AnalyticsEngine\\(\\), engine\\.compute_workflow_metrics\\(\\)"
---

<objective>
Add integration tests for stateful systems (workflow_engine.py, byok_handler.py, workflow_analytics_engine.py) to increase coverage from current levels (9.17%, 11.27%, 27.77%) toward 50% targets. Property tests validate invariants but don't call actual implementation methods - integration tests with mocked dependencies will execute real code paths.

**Purpose:** Close "Gap 2: Per-File Coverage Targets Not Met" and "Gap 3: Test Quality Issues" from VERIFICATION.md. Property tests are valuable for invariant validation but achieve low coverage because they don't execute actual handler methods. Integration tests with mocked external dependencies will call real implementation code.

**Root Causes (from VERIFICATION.md):**
1. Property tests validate invariants without calling actual handler methods (test_workflow_status_invariant should execute workflow_engine methods, not just validate state transitions)
2. workflow_engine.py async execution paths not tested (9.17% coverage - needs integration tests with mocked state_manager, ws_manager, analytics)
3. byok_handler.py provider routing not tested (11.27% coverage - needs integration tests with mocked LLM clients)
4. workflow_analytics_engine.py database interactions not tested (27.77% coverage - needs integration tests with DB operations)

**Gap Closed:** "Per-File Coverage Targets Not Met" and "Test Quality Issues" - 3 files move toward 50% target

**Output:** Integration test files for workflow_engine, byok_handler, and analytics with mocked dependencies, achieving 40%+ coverage on workflow_engine/byok_handler and 50%+ on analytics
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-VERIFICATION.md
@.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-01-SUMMARY.md
@.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-03-SUMMARY.md
@backend/core/workflow_engine.py
@backend/core/llm/byok_handler.py
@backend/core/workflow_analytics_engine.py
@backend/tests/integration/test_atom_agent_endpoints.py
@backend/tests/property_tests/conftest.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create integration tests for workflow_engine.py async execution paths</name>
  <files>backend/tests/integration/test_workflow_engine_integration.py</files>
  <action>
    Create backend/tests/integration/test_workflow_engine_integration.py with integration tests that call actual WorkflowEngine methods:

    **Target workflow_engine.py (1163 lines, 9.17% coverage) - test these actual methods:**

    1. **Async Workflow Execution** (mock state_manager, ws_manager, analytics):
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from core.workflow_engine import WorkflowEngine, WorkflowExecutionStatus

       @pytest.mark.asyncio
       async def test_execute_simple_workflow(db_session):
           """Test actual workflow execution with mocked dependencies."""
           # Mock state manager
           mock_state_manager = AsyncMock()
           mock_state_manager.get_state.return_value = {}

           # Mock WebSocket manager
           mock_ws_manager = MagicMock()
           mock_ws_manager.broadcast = AsyncMock()

           # Mock analytics
           mock_analytics = AsyncMock()

           # Create engine with mocked dependencies
           engine = WorkflowEngine(
               state_manager=mock_state_manager,
               ws_manager=mock_ws_manager,
               analytics=mock_analytics
           )

           # Create actual workflow definition
           workflow_def = {
               "id": "test_workflow",
               "steps": [
                   {"id": "step1", "action": "test", "inputs": {}}
               ]
           }

           # Execute workflow (calls real _execute_workflow_graph method)
           result = await engine.execute_workflow(workflow_def, db_session)

           # Verify real execution happened
           assert result["status"] == "completed"
           mock_state_manager.get_state.assert_called_once()
           mock_ws_manager.broadcast.assert_called()
       ```

    2. **Step Execution with Concurrency Control**:
       ```python
       @pytest.mark.asyncio
       async def test_concurrent_step_execution(db_session):
           """Test actual step execution logic with concurrency limits."""
           engine = WorkflowEngine(max_concurrent_steps=2)

           workflow_def = {
               "id": "concurrent_test",
               "steps": [
                   {"id": "step1", "action": "wait", "inputs": {"duration": 0.1}},
                   {"id": "step2", "action": "wait", "inputs": {"duration": 0.1}},
                   {"id": "step3", "action": "wait", "inputs": {"duration": 0.1}},
               ]
           }

           result = await engine.execute_workflow(workflow_def, db_session)
           assert result["status"] == "completed"
           # Verify concurrency limit was respected
       ```

    3. **Error Recovery and Retry Logic**:
       ```python
       @pytest.mark.asyncio
       async def test_workflow_retry_on_failure(db_session):
           """Test actual retry logic when steps fail."""
           engine = WorkflowEngine(max_retries=2)

           workflow_def = {
               "id": "retry_test",
               "steps": [
                   {
                       "id": "failing_step",
                       "action": "failing_action",
                       "retries": 2
                   }
               ]
           }

           # Mock step executor that fails then succeeds
           call_count = 0
           async def mock_executor(step, context):
               nonlocal call_count
               call_count += 1
               if call_count < 2:
                   raise Exception("Simulated failure")
               return {"status": "success"}

           with patch.object(engine, '_execute_step', side_effect=mock_executor):
               result = await engine.execute_workflow(workflow_def, db_session)

           assert result["status"] == "completed"
           assert call_count == 2  # Failed once, succeeded on retry
       ```

    4. **Conditional Branching Evaluation**:
       ```python
       @pytest.mark.asyncio
       async def test_conditional_branch_execution(db_session):
           """Test actual conditional branch evaluation."""
           engine = WorkflowEngine()

           workflow_def = {
               "id": "conditional_test",
               "steps": [
                   {"id": "step1", "action": "set_value", "outputs": {"result": True}},
                   {
                       "id": "step2",
                       "action": "branch",
                       "condition": "${step1.result} == true",
                       "then": {"action": "true_branch"},
                       "else": {"action": "false_branch"}
                   }
               ]
           }

           result = await engine.execute_workflow(workflow_def, db_session)
           assert result["status"] == "completed"
           # Verify true_branch was executed, not false_branch
       ```

    5. **DAG Topological Sort Execution Order**:
       ```python
       @pytest.mark.asyncio
       async def test_dag_execution_order(db_session):
           """Test actual DAG execution preserves dependency order."""
           engine = WorkflowEngine()

           workflow_def = {
               "id": "dag_test",
               "steps": [
                   {"id": "step3", "depends_on": ["step1", "step2"], "action": "final"},
                   {"id": "step1", "action": "first"},
                   {"id": "step2", "action": "second"},
               ]
           }

           execution_order = []
           async def tracking_executor(step, context):
               execution_order.append(step["id"])
               return {"status": "success"}

           with patch.object(engine, '_execute_step', side_effect=tracking_executor):
               result = await engine.execute_workflow(workflow_def, db_session)

           # Verify step1 and step2 executed before step3
           assert execution_order.index("step1") < execution_order.index("step3")
           assert execution_order.index("step2") < execution_order.index("step3")
       ```

    **Coverage target:** 40% of workflow_engine.py (465+ lines covered, up from 123)

    **Use existing patterns from:**
    - backend/tests/integration/test_atom_agent_endpoints.py (for integration test structure)
    - backend/tests/property_tests/conftest.py (for db_session fixture)

    **Key difference from property tests:** These tests CALL actual methods (execute_workflow, _execute_step) rather than just validating state transitions
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/integration/test_workflow_engine_integration.py -v --cov=backend/core/workflow_engine --cov-report=term-missing | tail -30
    Expected: workflow_engine.py coverage >= 40%, all integration tests pass
  </verify>
  <done>
    workflow_engine.py coverage >= 40%, at least 5 integration tests calling actual execution methods
  </done>
</task>

<task type="auto">
  <name>Task 2: Create integration tests for byok_handler.py with mocked LLM clients</name>
  <files>backend/tests/integration/test_byok_handler_integration.py</files>
  <action>
    Create backend/tests/integration/test_byok_handler_integration.py with integration tests that call actual BYOKHandler methods:

    **Target byok_handler.py (549 lines, 11.27% coverage) - test these actual methods:**

    1. **Provider Selection and Routing** (mock LLM clients):
       ```python
       import pytest
       from unittest.mock import AsyncMock, MagicMock, patch
       from core.llm.byok_handler import BYOKHandler

       @pytest.mark.asyncio
       async def test_provider_selection_openai():
           """Test actual provider selection logic."""
           handler = BYOKHandler()

           # Mock OpenAI client
           mock_openai = AsyncMock()
           mock_openai.chat.completions.create = AsyncMock(
               return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="Test response"))])
           )

           with patch('core.llm.byok_handler.openai', mock_openai):
               result = await handler.stream_completion(
                   model="gpt-4",
                   messages=[{"role": "user", "content": "Test"}],
                   provider="openai"
               )

           # Verify actual provider logic was called
           assert "Test response" in result
           mock_openai.chat.completions.create.assert_called_once()
       ```

    2. **Fallback Behavior**:
       ```python
       @pytest.mark.asyncio
       async def test_fallback_to_secondary_provider():
           """Test actual fallback logic when primary provider fails."""
           handler = BYOKHandler(
               provider_priority=["openai", "anthropic"],
               max_retries=2
           )

           # Mock OpenAI to fail, Anthropic to succeed
           mock_openai = AsyncMock()
           mock_openai.chat.completions.create = AsyncMock(
               side_effect=Exception("OpenAI unavailable")
           )

           mock_anthropic = AsyncMock()
           mock_anthropic.messages.create = AsyncMock(
               return_value=MagicMock(content=[MagicMock(text="Fallback response")])
           )

           with patch('core.llm.byok_handler.openai', mock_openai), \
                patch('core.llm.byok_handler.anthropic', mock_anthropic):
               result = await handler.stream_completion(
                   model="claude-3",
                   messages=[{"role": "user", "content": "Test"}],
                   provider="auto"  # Should fallback to anthropic
               )

           # Verify fallback occurred
           assert "Fallback response" in result
           mock_anthropic.messages.create.assert_called_once()
       ```

    3. **Token Counting**:
       ```python
       @pytest.mark.asyncio
       async def test_token_counting_accuracy():
           """Test actual token counting for different providers."""
           handler = BYOKHandler()

           # Test OpenAI tokenization
           openai_tokens = handler.count_tokens("Hello, world!", "gpt-4")
           assert openai_tokens > 0

           # Test Anthropic tokenization
           anthropic_tokens = handler.count_tokens("Hello, world!", "claude-3")
           assert anthropic_tokens > 0

           # Verify tokens are counted (not estimated)
           assert isinstance(openai_tokens, int)
           assert isinstance(anthropic_tokens, int)
       ```

    4. **Rate Limiting**:
       ```python
       @pytest.mark.asyncio
       async def test_rate_limit_enforcement():
           """Test actual rate limiting logic."""
           handler = BYOKHandler(rate_limit=10)  # 10 requests per minute

           # Mock successful responses
           mock_client = AsyncMock()
           mock_client.chat.completions.create = AsyncMock(
               return_value=MagicMock(choices=[MagicMock(message=MagicMock(content="OK"))])
           )

           # Make 15 requests (should hit rate limit after 10)
           results = []
           for i in range(15):
               try:
                   result = await handler.stream_completion(
                       model="gpt-4",
                       messages=[{"role": "user", "content": f"Request {i}"}],
                       provider="openai"
                   )
                   results.append(result)
               except Exception as e:
                   if "rate limit" in str(e).lower():
                       results.append(f"Rate limited at request {i}")

           # Verify rate limit was enforced
           assert len([r for r in results if "Rate limited" not in str(r)]) <= 10
       ```

    5. **Streaming Response**:
       ```python
       @pytest.mark.asyncio
       async def test_streaming_response():
           """Test actual streaming response handling."""
           handler = BYOKHandler()

           # Mock streaming response
           async def mock_stream():
               chunks = ["Hello", ", ", "world", "!"]
               for chunk in chunks:
                   yield MagicMock(delta=MagicMock(content=chunk))

           mock_client = AsyncMock()
           mock_client.chat.completions.create = AsyncMock(
               return_value=MagicMock(choices=[MagicMock(message=MagicMock())])
           )
           mock_client.chat.completions.create.return_value.choices[0].message.content = None
           mock_client.chat.completions.create.return_value.choices[0].message.stream = mock_stream()

           with patch('core.llm.byok_handler.openai', mock_client):
               result = ""
               async for chunk in handler.stream_completion(
                   model="gpt-4",
                   messages=[{"role": "user", "content": "Test"}],
                   provider="openai",
                   stream=True
               ):
                   result += chunk

           assert result == "Hello, world!"
       ```

    **Coverage target:** 40% of byok_handler.py (220+ lines covered, up from 62)

    **Use existing patterns from:**
    - backend/tests/integration/test_atom_agent_endpoints.py (for integration test structure)
    - backend/tests/property_tests/llm/test_llm_operations_invariants.py (for LLM test patterns)

    **Key difference from property tests:** These tests CALL actual handler methods (stream_completion, count_tokens) with mocked LLM clients, rather than just validating provider selection invariants
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/integration/test_byok_handler_integration.py -v --cov=backend/core/llm/byok_handler --cov-report=term-missing | tail -30
    Expected: byok_handler.py coverage >= 40%, all integration tests pass
  </verify>
  <done>
    byok_handler.py coverage >= 40%, at least 5 integration tests calling actual handler methods
  </done>
</task>

<task type="auto">
  <name>Task 3: Create integration tests for workflow_analytics_engine.py with database</name>
  <files>backend/tests/integration/test_workflow_analytics_integration.py</files>
  <action>
    Create backend/tests/integration/test_workflow_analytics_integration.py with integration tests that call actual AnalyticsEngine methods:

    **Target workflow_analytics_engine.py (593 lines, 27.77% coverage) - test these actual methods:**

    1. **Database Query Aggregation** (use real db_session):
       ```python
       import pytest
       from datetime import datetime, timedelta
       from core.workflow_analytics_engine import AnalyticsEngine
       from core.models import WorkflowExecution, WorkflowExecutionStatus

       @pytest.mark.asyncio
       async def test_aggregate_execution_metrics(db_session):
           """Test actual metric aggregation from database."""
           engine = AnalyticsEngine()

           # Create test workflow executions in database
           for i in range(10):
               exec = WorkflowExecution(
                   workflow_id=f"test_workflow_{i % 3}",
                   status=WorkflowExecutionStatus.COMPLETED,
                   started_at=datetime.utcnow() - timedelta(hours=i),
                   completed_at=datetime.utcnow() - timedelta(hours=i) + timedelta(minutes=5),
                   execution_time_ms=5000 + i * 100
               )
               db_session.add(exec)
           db_session.commit()

           # Call actual aggregation method
           metrics = await engine.compute_workflow_metrics(
               workflow_id="test_workflow_0",
               db_session=db_session
           )

           # Verify actual aggregation occurred
           assert metrics["total_executions"] > 0
           assert metrics["average_execution_time"] > 0
           assert "success_rate" in metrics
       ```

    2. **Time Series Aggregation**:
       ```python
       @pytest.mark.asyncio
       async def test_time_series_aggregation(db_session):
           """Test actual time series computation."""
           engine = AnalyticsEngine()

           # Create executions across time range
           base_time = datetime.utcnow() - timedelta(days=7)
           for i in range(20):
               exec = WorkflowExecution(
                   workflow_id="time_series_test",
                   status=WorkflowExecutionStatus.COMPLETED,
                   started_at=base_time + timedelta(hours=i),
                   completed_at=base_time + timedelta(hours=i) + timedelta(minutes=3),
                   execution_time_ms=3000
               )
               db_session.add(exec)
           db_session.commit()

           # Call actual time series method
           series = await engine.compute_execution_time_series(
               workflow_id="time_series_test",
               start_time=base_time,
               end_time=datetime.utcnow(),
               granularity="hour",
               db_session=db_session
           )

           # Verify time series was computed
           assert len(series) > 0
           assert all("timestamp" in point and "value" in point for point in series)
       ```

    3. **Percentile Computation**:
       ```python
       @pytest.mark.asyncio
       async def test_percentile_computation(db_session):
           """Test actual percentile computation from data."""
           engine = AnalyticsEngine()

           # Create executions with varying times
           execution_times = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
           for i, time_ms in enumerate(execution_times):
               exec = WorkflowExecution(
                   workflow_id="percentile_test",
                   status=WorkflowExecutionStatus.COMPLETED,
                   started_at=datetime.utcnow(),
                   completed_at=datetime.utcnow() + timedelta(milliseconds=time_ms),
                   execution_time_ms=time_ms
               )
               db_session.add(exec)
           db_session.commit()

           # Call actual percentile method
           p50 = await engine.compute_percentile(
               workflow_id="percentile_test",
               percentile=50,
               db_session=db_session
           )

           p95 = await engine.compute_percentile(
               workflow_id="percentile_test",
               percentile=95,
               db_session=db_session
           )

           # Verify percentiles
           assert 400 <= p50 <= 600  # Around median
           assert p95 > p50  # 95th percentile higher than median
       ```

    4. **Success Rate Calculation**:
       ```python
       @pytest.mark.asyncio
       async def test_success_rate_calculation(db_session):
           """Test actual success rate computation."""
           engine = AnalyticsEngine()

           # Create mix of successful and failed executions
           for i in range(10):
               status = (
                   WorkflowExecutionStatus.COMPLETED if i < 7
                   else WorkflowExecutionStatus.FAILED
               )
               exec = WorkflowExecution(
                   workflow_id="success_rate_test",
                   status=status,
                   started_at=datetime.utcnow(),
                   completed_at=datetime.utcnow() + timedelta(minutes=1),
                   execution_time_ms=60000
               )
               db_session.add(exec)
           db_session.commit()

           # Call actual success rate method
           success_rate = await engine.compute_success_rate(
               workflow_id="success_rate_test",
               db_session=db_session
           )

           # Verify 70% success rate (7/10)
           assert 0.65 <= success_rate <= 0.75  # Allow small variance
       ```

    5. **Trend Analysis**:
       ```python
       @pytest.mark.asyncio
       async def test_trend_analysis(db_session):
           """Test actual trend computation."""
           engine = AnalyticsEngine()

           # Create executions with increasing execution times
           base_time = datetime.utcnow() - timedelta(days=1)
           for i in range(10):
               exec = WorkflowExecution(
                   workflow_id="trend_test",
                   status=WorkflowExecutionStatus.COMPLETED,
                   started_at=base_time + timedelta(hours=i),
                   completed_at=base_time + timedelta(hours=i) + timedelta(minutes=i),
                   execution_time_ms=i * 60000  # Increasing trend
               )
               db_session.add(exec)
           db_session.commit()

           # Call actual trend method
           trend = await engine.compute_execution_trend(
               workflow_id="trend_test",
               db_session=db_session
           )

           # Verify increasing trend detected
           assert trend["direction"] == "increasing"
           assert trend["confidence"] > 0.5
       ```

    **Coverage target:** 50% of workflow_analytics_engine.py (297+ lines covered, up from 165)

    **Use existing patterns from:**
    - backend/tests/integration/test_atom_agent_endpoints.py (for integration test structure)
    - backend/tests/property_tests/conftest.py (for db_session fixture)
    - backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py (for analytics patterns)

    **Key difference from property tests:** These tests CALL actual analytics methods (compute_workflow_metrics, compute_percentile) with real database operations, rather than just validating aggregation invariants
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/integration/test_workflow_analytics_integration.py -v --cov=backend/core/workflow_analytics_engine --cov-report=term-missing | tail -30
    Expected: workflow_analytics_engine.py coverage >= 50%, all integration tests pass
  </verify>
  <done>
    workflow_analytics_engine.py coverage >= 50%, at least 5 integration tests with database operations
  </done>
</task>

</tasks>

<verification>
1. Run all three integration test files: `pytest backend/tests/integration/test_workflow_engine_integration.py backend/tests/integration/test_byok_handler_integration.py backend/tests/integration/test_workflow_analytics_integration.py -v`
2. Check coverage for each file:
   - `pytest --cov=backend/core/workflow_engine --cov-report=term-missing`
   - `pytest --cov=backend/core/llm/byok_handler --cov-report=term-missing`
   - `pytest --cov=backend/core/workflow_analytics_engine --cov-report=term-missing`
3. Verify all tests use mocked dependencies (AsyncMock, patch)
4. Confirm tests call actual implementation methods (not just validate invariants)
5. Check coverage.json for updated percentages
</verification>

<success_criteria>
- workflow_engine.py coverage >= 40% (up from 9.17%)
- byok_handler.py coverage >= 40% (up from 11.27%)
- workflow_analytics_engine.py coverage >= 50% (up from 27.77%)
- At least 15 integration tests total (5 per file)
- All tests use mocked external dependencies (state_manager, LLM clients)
- Tests call actual implementation methods, not just validate invariants
- Gap 2 (Per-File Coverage Targets) partially closed (analytics at 50%, others at 40%)
- Gap 3 (Test Quality Issues) closed - integration tests complement property tests
</success_criteria>

<output>
After completion, create `.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-GAP-02-SUMMARY.md` with:
- Coverage achieved for each file (workflow_engine, byok_handler, analytics)
- Number of integration tests created
- Before/after coverage percentages
- Gap 2 progress: 1/3 files at 50%+ (analytics), 2/3 files at 40%+ (need more in GAP-03 or Phase 13)
- Gap 3 closed: Integration tests now complement property tests
</output>
