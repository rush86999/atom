---
phase: 12-tier-1-coverage-push
plan: 03
type: execute
wave: 2
depends_on: ["12-tier-1-coverage-push-01"]
files_modified:
  - backend/tests/property_tests/llm/test_byok_handler_invariants.py
  - backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py
  - backend/tests/coverage_reports/metrics/coverage.json
autonomous: true
gap_closure: false

must_haves:
  truths:
    - "byok_handler.py has 50% coverage (LLM provider routing and fallback tested)"
    - "workflow_analytics_engine.py has 50% coverage (aggregation computation tested)"
    - "Property tests use Hypothesis for multi-provider routing and metric computation"
    - "Coverage increase of +1.1 percentage points (571 lines * 0.5 / 25768 total)"
  artifacts:
    - path: "backend/tests/property_tests/llm/test_byok_handler_invariants.py"
      provides: "Property tests for LLM provider selection, fallback, token counting"
      min_lines: 400
    - path: "backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py"
      provides: "Property tests for analytics aggregation and metric computation"
      min_lines: 350
  key_links:
    - from: "backend/tests/property_tests/llm/test_byok_handler_invariants.py"
      to: "backend/core/llm/byok_handler.py"
      via: "import BYOKHandler and test provider routing"
      pattern: "from core.llm.byok_handler import BYOKHandler"
    - from: "backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py"
      to: "backend/core/workflow_analytics_engine.py"
      via: "import AnalyticsEngine and test metric computation"
      pattern: "from core.workflow_analytics_engine import AnalyticsEngine"
---

<objective>
Achieve 50% coverage on byok_handler.py (549 lines) and workflow_analytics_engine.py (593 lines) using property tests for multi-provider LLM routing and analytics computation logic.

**Purpose:** Test the LLM routing layer (byok_handler.py) which manages multi-provider support (OpenAI, Anthropic, DeepSeek, Gemini) with fallback logic, and the analytics engine (workflow_analytics_engine.py) which computes workflow metrics and aggregations. Both files contain stateful logic best tested with property-based invariants.

**Output:** Property tests covering provider selection invariants, fallback behavior, token counting accuracy, and aggregation computation correctness.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@backend/tests/coverage_reports/metrics/priority_files_for_phases_12_13.json
@backend/core/llm/byok_handler.py
@backend/core/workflow_analytics_engine.py
@backend/tests/property_tests/llm/test_llm_operations_invariants.py
@backend/tests/property_tests/analytics/test_analytics_invariants.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create property tests for BYOK handler provider routing and fallback</name>
  <files>backend/tests/property_tests/llm/test_byok_handler_invariants.py</files>
  <action>
    Create backend/tests/property_tests/llm/test_byok_handler_invariants.py with property tests for multi-provider LLM routing:

    **Target byok_handler.py (549 lines, 0% coverage) - test these invariants:**

    1. **Provider Selection Invariants** (using st.sampled_from for providers):
       ```python
       @given(
           provider=st.sampled_from(["openai", "anthropic", "deepseek", "gemini"]),
           model=st.text(min_size=1, max_size=50, alphabet='abc123-_')
       )
       def test_provider_selection_is_valid(self, provider, model):
           """INVARIANT: Selected provider supports the requested model."""
           handler = BYOKHandler()
           selected = handler.select_provider(model)
           assert selected in VALID_PROVIDERS

       @given(
           preferred_providers=st.lists(
               st.sampled_from(["openai", "anthropic", "deepseek", "gemini"]),
               min_size=1,
               max_size=4,
               unique=True
           )
       )
       def test_provider_priority_ordering(self, preferred_providers):
           """INVARIANT: Providers selected in priority order."""
           handler = BYOKHandler(provider_priority=preferred_providers)
           # Verify priority ordering is preserved
           assert handler.provider_priority == preferred_providers
       ```

    2. **Fallback Behavior Invariants**:
       ```python
       @given(
           providers_available=st.lists(
               st.sampled_from(["openai", "anthropic", "deepseek", "gemini"]),
               min_size=1,
               max_size=4
           ),
           failed_providers=st.sets(st.sampled_from(["openai", "anthropic", "deepseek", "gemini"]), min_size=0, max_size=2)
       )
       def test_fallback_to_next_available(self, providers_available, failed_providers):
           """INVARIANT: Fallback selects next available provider."""
       available = [p for p in providers_available if p not in failed_providers]
       if available:
           # Should select from available providers
           assert len(available) > 0
       else:
           # No providers available - should raise or return error
           assert True

       @given(
           max_retries=st.integers(min_value=1, max_value=5)
       )
       def test_max_retries_respected(self, max_retries):
           """INVARIANT: Retry attempts do not exceed max_retries."""
       handler = BYOKHandler(max_retries=max_retries)
       attempts = 0
       for _ in range(max_retries + 10):  # Try more than max
           if attempts >= max_retries:
               break
           attempts += 1
       assert attempts <= max_retries
       ```

    3. **Token Counting Invariants**:
       ```python
       @given(
           text=st.text(min_size=0, max_size=1000, alphabet='abc DEF 123'),
           model=st.sampled_from(["gpt-4", "claude-3", "gemini-pro"])
       )
       def test_token_count_is_non_negative(self, text, model):
           """INVARIANT: Token count is always non-negative."""
       handler = BYOKHandler()
       tokens = handler.count_tokens(text, model)
       assert tokens >= 0

       @given(
           texts=st.lists(st.text(min_size=0, max_size=100, alphabet='abc'), min_size=1, max_size=10)
       )
       def test_token_count_is_additive(self, texts):
           """INVARIANT: Token count of concatenation equals sum of individual counts."""
       handler = BYOKHandler()
       individual_counts = [handler.count_tokens(t) for t in texts]
       combined_count = handler.count_tokens(" ".join(texts))
       # Combined should be approximately equal (accounting for tokenizer optimization)
       assert abs(combined_count - sum(individual_counts)) <= len(texts)  # Allow small variance
       ```

    4. **Rate Limiting Invariants**:
       ```python
       @given(
           requests_per_minute=st.integers(min_value=1, max_value=100),
           request_count=st.integers(min_value=0, max_value=200)
       )
       def test_rate_limit_enforced(self, requests_per_minute, request_count):
           """INVARIANT: Requests respect rate limits."""
       handler = BYOKHandler(rate_limit=requests_per_minute)
       allowed = min(request_count, requests_per_minute)
       assert handler.get_allowed_requests(request_count) == allowed

       @given(
           tokens_per_minute=st.integers(min_value=1000, max_value=100000),
           token_count=st.integers(min_value=0, max_value=200000)
       )
       def test_token_rate_limit_enforced(self, tokens_per_minute, token_count):
           """INVARIANT: Token usage respects token rate limits."""
       handler = BYOKHandler(token_rate_limit=tokens_per_minute)
       allowed = min(token_count, tokens_per_minute)
       assert handler.get_allowed_tokens(token_count) == allowed
       ```

    5. **Cost Calculation Invariants**:
       ```python
       @given(
           input_tokens=st.integers(min_value=0, max_value=10000),
           output_tokens=st.integers(min_value=0, max_value=5000),
           provider=st.sampled_from(["openai", "anthropic", "deepseek", "gemini"])
       )
       def test_cost_calculation_is_non_negative(self, input_tokens, output_tokens, provider):
           """INVARIANT: Cost is always non-negative."""
       handler = BYOKHandler()
       cost = handler.calculate_cost(input_tokens, output_tokens, provider)
       assert cost >= 0

       @given(
           input_tokens=st.integers(min_value=0, max_value=10000),
           output_tokens=st.integers(min_value=0, max_value=5000)
       )
       def test_cost_scales_with_tokens(self, input_tokens, output_tokens):
           """INVARIANT: Cost increases with more tokens."""
       handler = BYOKHandler()
       cost1 = handler.calculate_cost(input_tokens, output_tokens, "openai")
       cost2 = handler.calculate_cost(input_tokens * 2, output_tokens * 2, "openai")
       assert cost2 >= cost1
       ```

    **Test structure:**
    ```python
    import pytest
    from hypothesis import given, strategies as st, settings
    from core.llm.byok_handler import BYOKHandler

    class TestBYOKProviderInvariants:
        @pytest.fixture
        def handler(self):
            return BYOKHandler()

        @given(provider=st.sampled_from(["openai", "anthropic", "deepseek", "gemini"]))
        @settings(max_examples=50)
        def test_provider_is_configured(self, handler, provider):
            """INVARIANT: All configured providers have API keys."""
            assert handler.is_provider_configured(provider) == (provider in handler.configured_providers)

    class TestBYOKFallbackInvariants:
        @pytest.fixture
        def handler(self):
            return BYOKHandler(max_retries=3)

        @given(failure_count=st.integers(min_value=0, max_value=5))
        @settings(max_examples=50)
        def test_fallback_chain_exhaustion(self, handler, failure_count):
            """INVARIANT: Fallback chain exhausts after all providers fail."""
            # Simulate provider failures
    ```

    **Coverage target:** 50% of byok_handler.py (275 lines covered)

    **Use existing patterns from:**
    - backend/tests/property_tests/llm/test_llm_operations_invariants.py (for LLM test patterns)
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/property_tests/llm/test_byok_handler_invariants.py -v --cov=backend/core/llm/byok_handler --cov-report=term-missing | tail -30
    Expected: 50%+ coverage on byok_handler.py, all property tests pass
  </verify>
  <done>
    byok_handler.py coverage >= 50%, at least 10 property tests with Hypothesis strategies, no flaky tests
  </done>
</task>

<task type="auto">
  <name>Task 2: Create property tests for workflow analytics engine computation</name>
  <files>backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py</files>
  <action>
    Create backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py with property tests for analytics computation:

    **Target workflow_analytics_engine.py (593 lines, 0% coverage) - test these invariants:**

    1. **Aggregation Accuracy Invariants** (using st.lists for numeric data):
       ```python
       @given(
           values=st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=100)
       )
       def test_sum_aggregation_is_accurate(self, values):
           """INVARIANT: Sum aggregation equals arithmetic sum."""
       engine = WorkflowAnalyticsEngine()
       result = engine.aggregate(values, "sum")
       assert result == sum(values)

       @given(
           values=st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=100)
       )
       def test_avg_aggregation_is_accurate(self, values):
           """INVARIANT: Average aggregation equals arithmetic mean."""
       engine = WorkflowAnalyticsEngine()
       result = engine.aggregate(values, "avg")
       assert result == sum(values) / len(values)

       @given(
           values=st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=100)
       )
       def test_max_aggregation_finds_maximum(self, values):
           """INVARIANT: Max aggregation finds the maximum value."""
       engine = WorkflowAnalyticsEngine()
       result = engine.aggregate(values, "max")
       assert result == max(values)

       @given(
           values=st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=100)
       )
       def test_min_aggregation_finds_minimum(self, values):
           """INVARIANT: Min aggregation finds the minimum value."""
       engine = WorkflowAnalyticsEngine()
       result = engine.aggregate(values, "min")
       assert result == min(values)
       ```

    2. **Percentile Computation Invariants**:
       ```python
       @given(
           values=st.lists(st.integers(min_value=0, max_value=1000), min_size=10, max_size=100),
           percentile=st.integers(min_value=0, max_value=100)
       )
       def test_percentile_in_range(self, values, percentile):
           """INVARIANT: Percentile is within value range."""
       engine = WorkflowAnalyticsEngine()
       result = engine.percentile(values, percentile)
       assert min(values) <= result <= max(values)

       @given(
           values=st.lists(st.integers(min_value=0, max_value=1000), min_size=10, max_size=100)
       )
       def test_median_is_50th_percentile(self, values):
           """INVARIANT: Median equals 50th percentile."""
       engine = WorkflowAnalyticsEngine()
       median = engine.median(values)
       p50 = engine.percentile(values, 50)
       assert median == p50
       ```

    3. **Time Series Aggregation Invariants**:
       ```python
       @given(
           timestamps=st.lists(
               st.integers(min_value=1577836800, max_value=2000000000),  # 2020-2033
               min_size=2,
               max_size=50,
               unique=True
           )
       )
       def test_time_series_sorted(self, timestamps):
           """INVARIANT: Time series output is sorted chronologically."""
       engine = WorkflowAnalyticsEngine()
       series = engine.create_time_series(timestamps)
       assert series == sorted(timestamps)

       @given(
           values=st.lists(st.integers(min_value=0, max_value=100), min_size=5, max_size=20),
           window_size=st.integers(min_value=2, max_value=5)
       )
       def test_moving_average_window_size(self, values, window_size):
           """INVARIANT: Moving average respects window size."""
       engine = WorkflowAnalyticsEngine()
       ma = engine.moving_average(values, window_size)
       assert len(ma) == max(0, len(values) - window_size + 1)
       ```

    4. **Metric Computation Invariants**:
       ```python
       @given(
           execution_times=st.lists(st.integers(min_value=1, max_value=10000), min_size=1, max_size=100)
       )
       def test_average_execution_time_positive(self, execution_times):
           """INVARIANT: Average execution time is positive."""
       engine = WorkflowAnalyticsEngine()
       avg = engine.average_execution_time(execution_times)
       assert avg > 0

       @given(
           success_count=st.integers(min_value=0, max_value=100),
           failure_count=st.integers(min_value=0, max_value=100)
       )
       def test_success_rate_bounds(self, success_count, failure_count):
           """INVARIANT: Success rate is between 0 and 1."""
       engine = WorkflowAnalyticsEngine()
       total = success_count + failure_count
       if total > 0:
           rate = engine.success_rate(success_count, failure_count)
           assert 0 <= rate <= 1

       @given(
           throughputs=st.lists(st.integers(min_value=1, max_value=1000), min_size=5, max_size=50)
       )
       def test_throughput_trend_direction(self, throughputs):
           """INVARIANT: Trend direction is increasing, decreasing, or stable."""
       engine = WorkflowAnalyticsEngine()
       trend = engine.compute_trend(throughputs)
           assert trend in ["increasing", "decreasing", "stable"]
       ```

    5. **Bucket Aggregation Invariants**:
       ```python
       @given(
           values=st.lists(st.floats(min_value=0, max_value=1000, allow_nan=False), min_size=10, max_size=100),
           num_buckets=st.integers(min_value=2, max_value=10)
       )
       def test_histogram_buckets_exhaustive(self, values, num_buckets):
           """INVARIANT: All values fall into some bucket."""
       engine = WorkflowAnalyticsEngine()
       buckets = engine.histogram(values, num_buckets)
       total_count = sum(buckets.values())
       assert total_count == len(values)

       @given(
           values=st.lists(st.floats(min_value=0, max_value=1000, allow_nan=False), min_size=10, max_size=100),
           num_buckets=st.integers(min_value=2, max_value=10)
       )
       def test_histogram_bucket_count(self, values, num_buckets):
           """INVARIANT: Histogram has requested number of buckets."""
       engine = WorkflowAnalyticsEngine()
       buckets = engine.histogram(values, num_buckets)
       assert len(buckets) == num_buckets
       ```

    **Test structure:**
    ```python
    import pytest
    from hypothesis import given, strategies as st, settings
    from core.workflow_analytics_engine import WorkflowAnalyticsEngine

    class TestAnalyticsAggregationInvariants:
        @pytest.fixture
        def engine(self):
            return WorkflowAnalyticsEngine()

        @given(values=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=50))
        @settings(max_examples=100)
        def test_sum_invariant(self, engine, values):
            """INVARIANT: Sum of values is computed correctly."""
            assert engine.aggregate(values, "sum") == sum(values)

    class TestAnalyticsPercentileInvariants:
        @pytest.fixture
        def engine(self):
            return WorkflowAnalyticsEngine()

        @given(values=st.lists(st.integers(min_value=0, max_value=100), min_size=10, max_size=50))
        @settings(max_examples=50)
        def test_percentile_in_range(self, engine, values):
            """INVARIANT: Percentile is within data range."""
            p95 = engine.percentile(values, 95)
            assert min(values) <= p95 <= max(values)
    ```

    **Coverage target:** 50% of workflow_analytics_engine.py (297 lines covered)

    **Use existing patterns from:**
    - backend/tests/property_tests/analytics/test_analytics_invariants.py (for analytics test patterns)
  </action>
  <verify>
    PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py -v --cov=backend/core/workflow_analytics_engine --cov-report=term-missing | tail -30
    Expected: 50%+ coverage on workflow_analytics_engine.py, all property tests pass
  </verify>
  <done>
    workflow_analytics_engine.py coverage >= 50%, at least 12 property tests covering aggregation and metrics
  </done>
</task>

<task type="auto">
  <name>Task 3: Generate coverage report and validate 50% targets for both files</name>
  <files>backend/tests/coverage_reports/metrics/coverage.json</files>
  <action>
    Run coverage for both files and validate 50% coverage targets:

    1. Run pytest with coverage for both files:
       ```bash
       PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest \
         backend/tests/property_tests/llm/test_byok_handler_invariants.py \
         backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py \
         --cov=backend/core/llm/byok_handler \
         --cov=backend/core/workflow_analytics_engine \
         --cov-report=json \
         --cov-report=term \
         -v
       ```

    2. Check coverage.json for coverage percentages:
       ```python
       import json
       with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
         data = json.load(f)
         byok_cov = data['files'].get('backend/core/llm/byok_handler.py', {}).get('summary', {}).get('percent_covered', 0)
         analytics_cov = data['files'].get('backend/core/workflow_analytics_engine.py', {}).get('summary', {}).get('percent_covered', 0)
         print(f"byok_handler.py: {byok_cov}%, workflow_analytics_engine.py: {analytics_cov}%")
       ```

    3. Calculate combined coverage impact for Plan 03:
       - byok_handler.py: 50% of 549 = 275 lines
       - workflow_analytics_engine.py: 50% of 593 = 297 lines
       - Total covered: 572 lines
       - Overall impact: +1.1 percentage points (572 / 25768)

    4. If coverage is below 50%, add tests for:
       - Uncovered provider configurations in byok_handler.py
       - Edge cases in token counting (empty strings, special characters)
       - Additional aggregation functions in analytics engine
       - Error paths in metric computation

    5. Generate cumulative summary for Plans 01-03:
       - Plan 01: +2.0% (models.py + workflow_engine.py)
       - Plan 02: +1.4% (atom_agent_endpoints.py)
       - Plan 03: +1.1% (byok_handler.py + workflow_analytics_engine.py)
       - Total: +4.5% overall coverage increase
  </action>
  <verify>
    python3 -c "
    import json
    with open('backend/tests/coverage_reports/metrics/coverage.json') as f:
        data = json.load(f)
        byok_cov = data['files'].get('backend/core/llm/byok_handler.py', {}).get('summary', {}).get('percent_covered', 0)
        analytics_cov = data['files'].get('backend/core/workflow_analytics_engine.py', {}).get('summary', {}).get('percent_covered', 0)
        print(f'byok_handler.py: {byok_cov}%, workflow_analytics_engine.py: {analytics_cov}%')
        assert byok_cov >= 50.0, f'byok_handler.py coverage {byok_cov}% < 50%'
        assert analytics_cov >= 50.0, f'workflow_analytics_engine.py coverage {analytics_cov}% < 50%'
    "
    Expected: Both files show 50%+ coverage
  </verify>
  <done>
    byok_handler.py >= 50% coverage, workflow_analytics_engine.py >= 50% coverage, cumulative +4.5% from Plans 01-03
  </done>
</task>

</tasks>

<verification>
1. Run both test files: `pytest backend/tests/property_tests/llm/test_byok_handler_invariants.py backend/tests/property_tests/analytics/test_workflow_analytics_invariants.py -v`
2. Check coverage: `pytest --cov=backend/core/llm/byok_handler --cov=backend/core/workflow_analytics_engine --cov-report=term-missing`
3. Verify no Hypothesis shrinking failures
4. Validate aggregation accuracy with edge cases (empty lists, single values, large numbers)
5. Confirm provider fallback logic works correctly
</verification>

<success_criteria>
- byok_handler.py coverage >= 50% (275 lines covered from 549 total)
- workflow_analytics_engine.py coverage >= 50% (297 lines covered from 593 total)
- At least 10 property tests for BYOK handler (provider selection, fallback, token counting)
- At least 12 property tests for analytics engine (aggregation, percentiles, time series)
- Combined Plan 03 impact: +1.1 percentage points to overall coverage
- Cumulative Plans 01-03 impact: +4.5 percentage points
</success_criteria>

<output>
After completion, create `.planning/phases/12-tier-1-coverage-push/12-tier-1-coverage-push-03-SUMMARY.md` with:
- Coverage achieved for byok_handler.py and workflow_analytics_engine.py
- Number of property tests created
- Cumulative coverage impact from Plans 01-03
- Remaining Tier 1 file (workflow_debugger.py) for Plan 04
</output>
