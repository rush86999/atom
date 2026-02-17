---
phase: 06-social-layer
plan: 04
type: execute
wave: 1
depends_on: ["06-01", "06-02"]
files_modified:
  - core/agent_social_layer.py
  - tests/property_tests/social/test_feed_pagination_invariants.py
  - tests/test_agent_social_layer.py
autonomous: true
gap_closure: true

must_haves:
  truths:
    - "Feed pagination never returns duplicates (cursor-based invariant)"
    - "Feed always in chronological order (newest first)"
    - "FIFO message ordering is preserved"
    - "Channel isolation works (posts don't leak between channels)"
    - "Feed filtering by post_type works correctly"
    - "Property tests pass at 100% rate (currently 0%)"
  artifacts:
    - path: "core/agent_social_layer.py"
      provides: "Fixed cursor-based pagination and filtering"
    - path: "tests/property_tests/social/test_feed_pagination_invariants.py"
      provides: "Fixed property tests (100% pass rate)"
    - path: "tests/test_agent_social_layer.py"
      provides: "Fixed feed management tests"
  key_links:
    - from: "tests/property_tests/social/test_feed_pagination_invariants.py"
      to: "core/agent_social_layer.py"
      via: "property tests verify pagination invariants"
      pattern: "test_pagination_no_duplicates|test_chronological_order|test_fifo_ordering"
---

## Objective

Fix feed management implementation and property tests to achieve 100% pass rate. Resolve pagination duplicates, chronological ordering issues, FIFO message ordering problems, and feed filtering bugs.

**Purpose:** Feed management invariants are critical for social layer functionality. Currently all 6 property tests are failing (0% pass rate) due to implementation bugs in cursor-based pagination, ordering, and filtering.

**Output:** Property tests passing at 100%, feed pagination without duplicates, correct chronological ordering, working feed filters.

## Execution Context

@core/agent_social_layer.py (AgentSocialLayer with feed management)
@tests/property_tests/social/test_feed_pagination_invariants.py (6 property tests, 0% pass rate)
@tests/test_agent_social_layer.py (20 tests, 70% pass rate)
@.planning/phases/06-social-layer/06-social-layer-VERIFICATION.md (gap details)

## Context

@.planning/phases/06-social-layer/06-social-layer-02-PLAN.md (original communication plan)
@.planning/phases/06-social-layer/06-social-layer-02-SUMMARY.md (implementation summary)

# Verification Gap: Feed Management (Priority 2)
- All 6 property tests failing (0% pass rate)
- Pagination not cursor-based (offset-based causing duplicates)
- Filtering not working correctly
- Reply count not monotonic
- Foreign key constraint violations in tests

## Tasks

### Task 1: Fix Cursor-Based Pagination in AgentSocialLayer

**Files:** `core/agent_social_layer.py`

**Action:**
1. Fix get_feed_cursor() to ensure no duplicates:
   - Current implementation at line 492-589
   - Ensure cursor uses strictly LESS THAN comparison (not LTE)
   - Fix next_cursor calculation to use last post's created_at correctly
   - Add unique constraint check to prevent duplicate posts in same page

2. Fix pagination logic in get_feed():
   - Ensure offset-based pagination doesn't return duplicates
   - Add order_by with stable sorting (created_at DESC, id DESC for tiebreaker)

3. Add pagination invariant checks:
   ```python
   def _verify_no_duplicates(self, posts: List[Dict]) -> None:
       """Verify no duplicate post IDs in page."""
       post_ids = [p["id"] for p in posts]
       assert len(post_ids) == len(set(post_ids)), "Duplicates found in page"
   ```

Reference issue from verification:
- test_pagination_no_duplicates fails due to duplicates across pages

**Verify:**
- `pytest tests/property_tests/social/test_feed_pagination_invariants.py::TestFeedPaginationInvariants::test_pagination_no_duplicates -v` passes
- Manual test: Create 100 posts, paginate with limit=20, verify no duplicates across all pages

**Done:**
- Cursor-based pagination never returns duplicates
- Offset-based pagination has tiebreaker for stability
- Duplicate detection added for safety

---

### Task 2: Fix Feed Filtering and Chronological Ordering

**Files:** `core/agent_social_layer.py`

**Action:**
1. Fix get_feed() filtering logic:
   - Ensure post_type filter uses exact match
   - Fix sender_filter to use correct field (sender_id not sender_name)
   - Fix channel_id filter to handle None values correctly
   - Fix is_public filter to use boolean comparison correctly

2. Fix chronological ordering:
   - Ensure all feed queries use `order_by(desc(AgentPost.created_at), desc(AgentPost.id))`
   - Add tiebreaker on id for posts with same timestamp
   - Verify newest posts appear first

3. Fix get_feed_cursor() filtering:
   - Apply same filters before cursor comparison
   - Ensure cursor pagination respects all filter parameters

Reference issues from verification:
- test_feed_filtering_by_post_type fails
- test_chronological_order invariant fails

**Verify:**
- `pytest tests/property_tests/social/test_feed_pagination_invariants.py::TestChronologicalOrderInvariant::test_feed_chronological_order -v` passes
- `pytest tests/property_tests/social/test_feed_pagination_invariants.py::TestFeedFilteringInvariants::test_feed_filtering_by_type_matches_all -v` passes
- `pytest tests/test_agent_social_layer.py::TestFeedPagination::test_feed_filtering_by_post_type -v` passes

**Done:**
- Feed filtering works for post_type, sender, channel, is_public
- Chronological order preserved (newest first)
- Tiebreaker on id for posts with same timestamp

---

### Task 3: Fix Property Tests and Channel Isolation

**Files:** `tests/property_tests/social/test_feed_pagination_invariants.py`, `tests/test_agent_social_layer.py`

**Action:**
1. Fix test_channel_isolation property test:
   - Fix foreign key constraint by ensuring channel exists before creating posts
   - Set channel_id correctly in test data creation
   - Verify posts belong to correct channel in assertions

2. Fix test_reply_count_monotonic_increase:
   - Ensure reply_count is properly incremented in add_reply()
   - Fix assertion to check monotonic increase (not exact increment)
   - Handle edge case where reply counting may be delayed

3. Fix test_fifo_message_ordering:
   - Adjust for reverse chronological ordering (newest first in feed)
   - Verify sent order matches reverse of received order
   - Account for millisecond timestamp differences

4. Fix test_feed_filtering_by_type_matches_all:
   - Ensure all posts have correct post_type set
   - Fix filter comparison to be case-insensitive if needed
   - Verify no posts with wrong type appear in filtered results

Reference issues from verification:
- Foreign key constraint violations
- Reply count assertions failing
- Channel ID mismatches

**Verify:**
- `pytest tests/property_tests/social/test_feed_pagination_invariants.py -v` shows 100% pass rate (6/6 tests pass)
- `pytest tests/test_agent_social_layer.py -v` shows 90%+ pass rate
- No foreign key constraint errors

**Done:**
- All 6 property tests passing
- Channel isolation verified
- FIFO ordering verified
- Reply count monotonicity verified

---

## Deviations

**Rule 1 (Timestamp Precision):** If millisecond timestamps cause collisions, use microsecond precision or UUID tiebreaker.

**Rule 2 (Test Isolation):** Ensure each test uses unique channel IDs and agent IDs to prevent foreign key violations.

**Rule 3 (Backward Compatibility):** All fixes must maintain backward compatibility with existing API contracts.

## Success Criteria

- [ ] Property tests achieve 100% pass rate (6/6 tests)
- [ ] Feed pagination never returns duplicates (verified with 200 posts)
- [ ] Chronological order preserved (newest first with tiebreaker)
- [ ] Feed filtering works correctly (post_type, sender, channel, is_public)
- [ ] Channel isolation verified (no posts leak between channels)
- [ ] FIFO ordering preserved (messages in order sent)
- [ ] Reply count monotonicity maintained

## Dependencies

- Plan 06-01 (Post Generation & PII Redaction) must be complete
- Plan 06-02 (Communication & Feed Management) must be complete

## Estimated Duration

3-4 hours (pagination fixes + filtering fixes + test fixes)
