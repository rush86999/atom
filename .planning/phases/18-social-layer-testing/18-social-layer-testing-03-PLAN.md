---
phase: 18-social-layer-testing
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_social_feed_integration.py
  - backend/tests/property_tests/conftest.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Cursor pagination never returns duplicate posts even when new posts arrive during pagination"
    - "Property tests verify: no duplicates, FIFO ordering, no lost messages, feed stability"
  artifacts:
    - path: "backend/tests/test_social_feed_integration.py"
      provides: "Fixed cursor pagination and property-based tests"
      min_lines: 1300
    - path: "backend/tests/property_tests/conftest.py"
      provides: "Hypothesis-compatible database fixtures"
  key_links:
    - from: "test_social_feed_integration.py"
      to: "agent_social_layer.py"
      via: "get_feed_cursor method call"
      pattern: "get_feed_cursor.*db_session"
    - from: "test_social_feed_integration.py"
      to: "conftest.py"
      via: "db_session fixture import"
      pattern: "from.*conftest import db_session"
---

<objective>
Fix cursor pagination tests and Hypothesis+pytest fixture incompatibility in property-based tests.

Purpose: Cursor pagination implementation is correct (compound cursor timestamp:id), but tests fail due to fixture issues and test data problems. Property-based tests written correctly but 7/12 fail because Hypothesis @given decorator runs before pytest fixtures are available.
Output: All 9 previously failing tests now pass, property-based tests execute correctly with Hypothesis strategies
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
@backend/tests/test_social_feed_integration.py
@backend/tests/property_tests/conftest.py
@backend/core/agent_social_layer.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix Hypothesis+pytest fixture incompatibility in property-based tests</name>
  <files>backend/tests/test_social_feed_integration.py</files>
  <action>
    Fix the 7 property-based tests in TestFeedInvariants class that fail with "fixture not found" errors.

    Root cause: Hypothesis @given decorator generates test parameters BEFORE pytest fixtures are available. Tests like:
    - test_cursor_pagination_never_returns_duplicates(post_count, page_size, db_session)
    - test_chronological_order_invariant(post_count, db_session)
    - test_cursor_stability_invariant(post_count, page_size, db_session)
    - test_feed_filtering_invariant(post_count, post_type, sender_id, db_session)
    - test_channel_isolation_invariant(channel_count, post_count, db_session)
    - test_feed_pagination_invariant(post_count, page_size, db_session)
    - test_no_duplicates_in_feed(post_count, page_size, db_session)

    Solution approach (choose ONE):
    A) Refactor property tests to use Hypothesis strategies with fixture injection pattern:
       - Create test data INSIDE the test using strategies.st.integers()
       - Use db_session fixture as function parameter (not Hypothesis strategy)
       - Example: @given(st.integers(10, 200), st.integers(5, 50))
               async def test_cursor_pagination_never_returns_duplicates(post_count, page_size):
                   # Setup db_session inside test via fixtures

    B) Use pytest's @pytest.mark.parametrize with example values instead of Hypothesis

    C) Create a fixture that returns Hypothesis-drawn values

    Implement approach A (most compatible with existing code):
    1. Keep db_session as pytest fixture (last parameter)
    2. Use @given decorator only for Hypothesis-generated integers
    3. Import db_session from conftest
    4. Ensure db_session is NOT a Hypothesis strategy parameter

    Pattern to fix:
    BEFORE: @given(st.integers(10, 200), st.integers(5, 50), ...db_session fixture...)
    AFTER:  @given(st.integers(10, 200), st.integers(5, 50))
            async def test_cursor_pagination_never_returns_duplicates(post_count, page_size, db_session):
                # Hypothesis generates post_count, page_size
                # pytest injects db_session fixture
  </action>
  <verify>cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_social_feed_integration.py::TestFeedInvariants -v</verify>
  <done>7 property-based tests in TestFeedInvariants class pass without fixture errors</done>
</task>

<task type="auto">
  <name>Task 2: Fix cursor pagination second page test (test_cursor_second_page_returns_older_posts)</name>
  <files>backend/tests/test_social_feed_integration.py</files>
  <action>
    Fix test_cursor_second_page_returns_older_posts which expects 10 posts but returns 0.

    Current issue: The test creates posts and then requests the second page (after getting cursor from first page), but gets 0 posts instead of 10.

    Root cause analysis needed:
    1. Check if first page cursor is correctly generated
    2. Verify posts have different timestamps (compound cursor: timestamp:id)
    3. Ensure query uses correct WHERE clause (timestamp < cursor_timestamp OR (timestamp = cursor_timestamp AND id < cursor_id))

    Fix approach:
    1. Read the existing test implementation around line 530-560
    2. Add debug logging to see what cursor is generated
    3. Verify get_feed_cursor() in agent_social_layer.py uses correct comparison
    4. Fix test data setup to ensure posts are properly ordered with different timestamps

    Expected cursor format: "timestamp:id" (base64 encoded)
    Expected query: WHERE (created_at < ?) OR (created_at = ? AND id < ?) ORDER BY created_at DESC, id DESC LIMIT ?

    If the implementation is correct, the test data setup may be the issue:
    - Ensure all posts have unique timestamps (add timedelta microseconds)
    - Verify commit() is called before pagination
  </action>
  <verify>cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_social_feed_integration.py::TestCursorPagination::test_cursor_second_page_returns_older_posts -v</verify>
  <done>test_cursor_second_page_returns_older_posts passes: second page returns 10 posts</done>
</task>

<task type="auto">
  <name>Task 3: Fix test_feed_with_multiple_filters test</name>
  <files>backend/tests/test_social_feed_integration.py</files>
  <action>
    Fix test_feed_with_multiple_filters which expects 1 post but gets 2.

    Current issue: Test applies multiple filters (sender_id, post_type, is_public) and expects only posts matching ALL filters, but gets 2 instead of 1.

    Root cause analysis:
    1. Check if test creates multiple posts with different attributes
    2. Verify filters should be AND combined (all must match) not OR
    3. Ensure filter logic in get_feed() correctly applies all conditions

    Fix approach:
    1. Find the test around line 130-160
    2. Review what posts are created in test setup
    3. Review what filters are applied
    4. Either fix test expectation OR fix filter implementation

    Likely issue: Test creates posts that match all filters when it shouldn't, OR filter logic is incorrect.

    Verify agent_social_layer.py get_feed() method applies filters correctly:
    - query = query.filter(AgentPost.sender_id == sender_id)
    - query = query.filter(AgentPost.post_type == post_type)
    - query = query.filter(AgentPost.is_public == True)
  </action>
  <verify>cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_social_feed_integration.py::TestFeedGeneration::test_feed_with_multiple_filters -v</verify>
  <done>test_feed_with_multiple_filters passes: returns exactly 1 post matching all filters</done>
</task>

</tasks>

<verification>
After completing all tasks, run the full test suite for social feed integration:

```bash
cd backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_social_feed_integration.py -v --tb=short
```

Expected results:
- 38 total tests
- 36-38 tests passing (previously 29)
- 0-2 tests failing (property tests may need additional tuning)
- No "fixture not found" errors

Gap closure verification:
- [ ] Property-based tests no longer have Hypothesis+pytest fixture incompatibility errors
- [ ] Cursor pagination second page test returns 10 posts (not 0)
- [ ] Multiple filters test returns correct count (1 not 2)
</verification>

<success_criteria>
1. All 7 property-based tests in TestFeedInvariants execute without fixture errors
2. test_cursor_second_page_returns_older_posts passes (returns 10 posts)
3. test_feed_with_multiple_filters passes (returns 1 post)
4. Overall pass rate for test_social_feed_integration.py improves from 76% to 95%+
</success_criteria>

<output>
After completion, create `.planning/phases/18-social-layer-testing/18-social-layer-testing-03-SUMMARY.md`
</output>
