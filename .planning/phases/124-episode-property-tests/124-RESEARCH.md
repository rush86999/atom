# Phase 124: Episode Property Tests - Research

**Researched:** 2026-03-02
**Domain:** Python property-based testing with Hypothesis for episodic memory invariants
**Confidence:** HIGH

## Summary

Phase 124 aims to validate episodic memory system invariants using Hypothesis property-based testing, building on the successful test patterns from Phase 113. **Critical finding**: Phase 113 has already written extensive property tests for episode services with proven invariants and patterns that can be directly reused. The existing `test_episode_*_invariants.py` files provide a complete blueprint for episode segmentation, retrieval, and lifecycle property testing.

**Primary recommendation**: Reuse Phase 113's proven property test patterns (max_examples=50-200, @given decorators with hypothesis.strategies, boundary case testing with @example) and focus on expanding coverage for gaps identified during Phase 113. Use the existing invariant test structure from `backend/tests/property_tests/episodes/` as the template.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hypothesis | 6.0.0+ | Property-based testing framework | Industry standard for Python PBT, integrates with pytest |
| pytest | 7.4.4+ | Test runner | Phase 113 proven, already installed |
| hypothesis.strategies | 6.0.0+ | Data generation strategies | Built-in strategies (integers, floats, lists, datetimes) |
| pytest-asyncio | 0.21.0+ | Async test support | Required for async service methods |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-settings | stdlib | Test configuration | @settings decorator for max_examples |
| unittest.mock | stdlib | Mock dependencies | SQLAlchemy sessions, LanceDB handlers |
| datetime | stdlib | Time-based strategies | Episode timestamps, time gaps |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hypothesis | quickcheck | Less mature Python ecosystem |
| pytest.mark.parametrize | @given | PBT provides automated test case generation |
| Manual edge case testing | Hypothesis strategies | PBT finds edge cases humans miss |

**Installation:**
```bash
# All dependencies already installed from Phase 113
pip install hypothesis pytest pytest-asyncio
```

## Architecture Patterns

### Recommended Project Structure
```
backend/tests/property_tests/episodes/
├── test_episode_segmentation_invariants.py  # EXISTING: 827 lines
├── test_episode_retrieval_invariants.py    # EXISTING: 1070 lines
├── test_episode_lifecycle_invariants.py    # EXISTING: 456 lines
├── test_episode_service_contracts.py       # EXISTING: Service contract tests
├── test_episode_memory_consolidation_invariants.py  # EXISTING: Consolidation tests
└── test_episode_retrieval_advanced_invariants.py    # EXISTING: Advanced retrieval
```

### Pattern 1: Invariant Testing with @given
**What:** Property-based tests validate system invariants across generated inputs
**When to use:** Testing business rules, mathematical properties, state transitions
**Example:**
```python
# Source: backend/tests/property_tests/episodes/test_episode_segmentation_invariants.py
from hypothesis import given, settings, example
from hypothesis.strategies import integers, datetimes, timedeltas

@given(
    num_events=integers(min_value=2, max_value=50),
    gap_threshold_hours=integers(min_value=1, max_value=12)
)
@example(num_events=3, gap_threshold_hours=4)  # Boundary case
@settings(max_examples=200)  # Critical invariant - memory integrity
def test_time_gap_detection(self, num_events, gap_threshold_hours):
    """
    INVARIANT: Time gaps exceeding threshold must trigger new episode.
    Segmentation boundary is exclusive (> threshold, not >=).

    VALIDATED_BUG: Gap of exactly 4 hours did not trigger segmentation when threshold=4.
    Root cause was using >= instead of > in time gap comparison.
    Fixed in commit ghi789 by changing gap_hours >= THRESHOLD to gap_hours > THRESHOLD.
    """
    # Test implementation...
```

### Pattern 2: Boundary Case Testing with @example
**What:** Add specific edge cases alongside generated test cases
**When to use:** Critical boundary conditions that must always pass
**Example:**
```python
@given(gap_hours=integers(min_value=4, max_value=48))
@example(gap_hours=4)  # Exact boundary
@example(gap_hours=5)  # Just above boundary
@settings(max_examples=200)
def test_time_gap_threshold_enforcement(self, gap_hours):
    """
    INVARIANT: Time gap threshold is strictly enforced with exclusive boundary.
    Edge cases:
    - gap_hours=4 with threshold=4: should NOT segment (exclusive)
    - gap_hours=4.0001 with threshold=4: should segment (exclusive)
    """
```

### Pattern 3: Multi-Parameter Strategy Generation
**What:** Generate complex test data using strategy composition
**When to use:** Testing functions with multiple inputs
**Example:**
```python
from hypothesis.strategies import lists, tuples, text

@given(
    utterances=lists(
        tuples(
            text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz '),
            text(min_size=3, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz')
        ),
        min_size=2,
        max_size=30
    )
)
@settings(max_examples=50)
def test_topic_consistency_within_segments(self, utterances):
    """Test that segments maintain topic consistency"""
    # Group utterances by topic (second element of tuple)
    segments = {}
    for content, topic in utterances:
        if topic not in segments:
            segments[topic] = []
        segments[topic].append({"content": content, "topic": topic})

    # Verify each segment has consistent topic
    for topic, segment_utterances in segments.items():
        assert all(u["topic"] == topic for u in segment_utterances)
```

### Pattern 4: State Machine Invariant Testing
**What:** Test state transition invariants
**When to use:** Lifecycle operations, status changes, state machines
**Example:**
```python
@given(
    episode_count=integers(min_value=20, max_value=100)
)
@settings(max_examples=50)
def test_lifecycle_workflow_order(self, episode_count):
    """
    INVARIANT: Lifecycle operations run in correct order.

    Order: decay -> consolidation -> archival
    Episodes flow through lifecycle:
    1. New episodes with high importance
    2. Old episodes decay (importance decreases)
    3. Similar episodes consolidate (reduce count)
    4. Low-importance, old episodes archive (move to cold storage)
    """
    # Simulate lifecycle transitions
    # Verify state machine integrity
```

### Anti-Patterns to Avoid
- **max_examples too low**: Using max_examples=10 provides insufficient coverage
- **Over-filtering with assume()**: Better to use precise strategies than filter out 90% of cases
- **Testing implementation details**: Test invariants, not specific code paths
- **Missing @example decorators**: Boundary cases need explicit examples
- **Testing without @settings**: Always specify max_examples for reproducibility

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test data generation | Manual loops with random | hypothesis.strategies | Automated shrinking, better edge case coverage |
| Boundary testing | Manual edge case enumeration | @example decorator | Explicit documentation of critical cases |
| Strategy composition | Custom data builders | st.tuples(), st.lists() | Built-in composition, reproducible |
| Invariant validation | Manual assertion checking | Property-based assertions | Automated counterexample generation |

**Key insight:** Hypothesis automatically finds minimal counterexamples when invariants fail. Manual testing requires humans to think of edge cases - Hypothesis finds them algorithmically through shrinking.

## Common Pitfalls

### Pitfall 1: max_examples Set Too Low
**What goes wrong:** Tests pass with max_examples=10 but fail at 100
**Why it happens:** Low example count misses rare edge cases
**How to avoid:** Use max_examples=50 for basic invariants, 100 for retrieval tests, 200 for critical memory integrity
**Warning signs:** Flaky tests that fail intermittently

```python
# BAD
@settings(max_examples=10)  # Too low for confidence

# GOOD
@settings(max_examples=200)  # Critical invariant - memory integrity
```

### Pitfall 2: Over-Filtering with assume()
**What goes wrong:** Tests run slowly because 99% of generated cases are filtered
**Why it happens:** Using broad strategies with strict filters
**How to avoid:** Use precise strategies (min_value, max_value) instead of filtering
**Warning signs:** HealthCheck.filter_too_much warnings

```python
# BAD - filters out 50% of cases
@given(st.integers())
def test_positive_numbers(n):
    assume(n > 0)  # Filters out half

# GOOD - generates only positive numbers
@given(st.integers(min_value=1))
def test_positive_numbers(n):
    assert n > 0  # Always true, no filtering needed
```

### Pitfall 3: Testing Implementation Instead of Invariants
**What goes wrong:** Tests break when refactoring code
**Why it happens:** Tests check specific implementation paths, not invariants
**How to avoid:** Test what should be true, not how it's achieved
**Warning signs:** Tests need updating when code refactors

```python
# BAD - tests implementation
def test_segmentation_creates_episodes(self):
    # Verifies specific function call order

# GOOD - tests invariant
def test_all_events_in_some_episode(self):
    # Verifies no events are lost, regardless of implementation
```

### Pitfall 4: Missing Boundary Case Examples
**What goes wrong:** Edge cases at exact boundaries not tested
**Why it happens:** Relying only on generated test cases
**How to avoid:** Always add @example decorators for boundary values
**Warning signs:** Bugs found at exact threshold values (e.g., exactly 30 minutes)

```python
# BAD - only relies on generated cases
@given(st.integers(min_value=1, max_value=100))
def test_threshold(self, value):
    ...

# GOOD - explicit boundary cases
@given(st.integers(min_value=1, max_value=100))
@example(value=30)  # Exact threshold
@example(value=31)  # Just above
@example(value=29)  # Just below
@settings(max_examples=100)
def test_threshold(self, value):
    ...
```

### Pitfall 5: Floating Point Precision Issues
**What goes wrong:** Similarity scores fail bounds checks due to floating point errors
**Why it happens:** Uncorrected floating point arithmetic
**How to avoid:** Use allow_nan=False, allow_infinity=False, clamp results
**Warning signs:** Similarity scores of -0.01 or 1.0001

```python
# BAD - allows invalid scores
@given(st.floats())
def test_similarity_bounds(self, score):
    assert 0.0 <= score <= 1.0  # May fail due to NaN/Infinity

# GOOD - clamps and validates
@given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_similarity_bounds(self, score):
    similarity = max(0.0, min(1.0, calculated_score))  # Clamp to [0, 1]
    assert 0.0 <= similarity <= 1.0
```

## Code Examples

Verified patterns from Phase 113 property tests:

### Segmentation Invariants (827 lines, proven)
```python
# Source: backend/tests/property_tests/episodes/test_episode_segmentation_invariants.py

class TestTimeGapSegmentationInvariants:
    """Tests for time-based segmentation invariants"""

    @given(
        num_events=st.integers(min_value=2, max_value=50),
        gap_threshold_hours=st.integers(min_value=1, max_value=12)
    )
    @example(num_events=3, gap_threshold_hours=4)  # Boundary case
    @settings(max_examples=200)
    def test_time_gap_detection(self, num_events, gap_threshold_hours):
        """
        INVARIANT: Time gaps exceeding threshold must trigger new episode.
        VALIDATED_BUG: Gap of exactly 4 hours did not trigger segmentation.
        Fixed in commit ghi789 by using > instead of >=.
        """
        # Test implementation...
```

### Retrieval Invariants (1070 lines, proven)
```python
# Source: backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py

class TestTemporalRetrievalInvariants:
    """Tests for temporal retrieval invariants"""

    @given(
        episode_count=st.integers(min_value=1, max_value=100),
        days_ago=st.integers(min_value=1, max_value=90),
        limit=st.integers(min_value=10, max_value=100)
    )
    @example(episode_count=10, days_ago=30, limit=20)
    @settings(max_examples=100)
    def test_temporal_retrieval_time_filtering(self, episode_count, days_ago, limit):
        """
        INVARIANT: Temporal retrieval filters by time range correctly.
        VALIDATED_BUG: Episodes exactly at boundary were excluded.
        Fixed in commit stu123 by including boundary timestamps.
        """
        # Test implementation...
```

### Lifecycle Invariants (456 lines, proven)
```python
# Source: backend/tests/property_tests/episodes/test_episode_lifecycle_invariants.py

class TestEpisodeDecayInvariants:
    """Property-based tests for episode importance decay invariants."""

    @given(
        initial_importance=st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False),
        access_count=st.integers(min_value=0, max_value=100),
        days_since_access=st.integers(min_value=0, max_value=365)
    )
    @example(initial_importance=0.8, access_count=10, days_since_access=90)
    @example(initial_importance=1.0, access_count=0, days_since_access=180)
    @settings(max_examples=200)
    def test_importance_decay_formula(self, initial_importance, access_count, days_since_access):
        """
        INVARIANT: Episode importance decays over time without access.
        VALIDATED_BUG: Episodes accessed 90+ days ago still had full importance.
        Fixed in commit stu234 by applying decay to all episodes >90 days old.
        """
        # Test implementation...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual edge case testing | Hypothesis PBT | Phase 113 | Automated edge case discovery |
| Example-based testing | Property-based invariants | Phase 113 | Tests what matters, not implementation |
| Fixed test data | Strategy-based generation | Phase 113 | Better coverage, shrinking |

**Deprecated/outdated:**
- **Manual edge case enumeration**: Hypothesis finds edge cases algorithmically
- **Testing implementation details**: Test invariants instead for maintainability
- **Low max_examples (<50)**: Modern CI/CD can handle 100-200 examples per test

## Key Invariants Identified

### Segmentation Invariants (from Phase 113)
1. **Time Gap Detection**: Gaps > threshold trigger new episodes (exclusive boundary)
2. **Topic Change Detection**: Semantic similarity < 0.75 triggers segmentation
3. **Task Completion**: task_complete=True marks segment boundaries
4. **Segment Boundaries**: Disjoint, chronological, no overlaps
5. **Information Preservation**: No events lost during segmentation
6. **Metadata Integrity**: All episodes have required fields (id, start_time, end_time, agent_id)
7. **Context Preservation**: Context window maintained across boundaries
8. **Entity Extraction**: Entities extracted and deduplicated correctly
9. **Importance Scoring**: Scores in valid range [0. 1]
10. **Consolidation Eligibility**: Based on threshold, prevents circular references

### Retrieval Invariants (from Phase 113)
1. **Temporal Filtering**: Episodes filtered by time range correctly (>= boundary)
2. **Similarity Bounds**: Scores in [0, 1], no NaN/Infinity
3. **Ranking Order**: Results sorted by relevance (descending)
4. **Limit Enforcement**: Result count <= specified limit
5. **Segment Completeness**: Sequential retrieval includes all segments
6. **Hybrid Scoring**: Contextual retrieval combines temporal + semantic scores
7. **Feedback Boosting**: Positive feedback +0.2, negative feedback -0.3, clamped to [0, 1]
8. **Canvas Type Filtering**: Correctly filters by canvas type (sheets, charts, etc.)
9. **Status Filtering**: Archived episodes excluded from active queries
10. **Access Logging**: All accesses logged with required fields

### Lifecycle Invariants (from Phase 113)
1. **Decay Formula**: importance = (initial * max(0.1, 1 - days/365)) + access_boost
2. **Decay Thresholds**: 90-day initial, 180-day significant, 365-day maximum decay
3. **Consolidation Similarity**: Only merges episodes >0.85 similarity
4. **Consolidation No Circles**: A.consolidated_into = B implies B.consolidated_into != A
5. **Archival Status**: Archived episodes have status="archived" and archived_at set
6. **Archival Searchability**: Archived episodes remain searchable via LanceDB
7. **Segment Preservation**: Archival preserves episode segments (no cascade delete)
8. **Lifecycle Order**: decay -> consolidation -> archival (state machine)

## Open Questions

1. **Should Phase 124 write new property tests or expand existing Phase 113 tests?**
   - What we know: Phase 113 already has 2358+ lines of property tests covering all major invariants
   - What's unclear: Are there gaps in Phase 113 coverage that Phase 124 should address?
   - Recommendation: Review Phase 113 test coverage reports first, identify gaps, then expand existing test files

2. **What max_examples values are appropriate for new property tests?**
   - What we know: Phase 113 uses max_examples=50 (basic), 100 (retrieval), 200 (critical)
   - What's unclear: Should Phase 124 use higher values for more confidence?
   - Recommendation: Follow Phase 113 pattern (50 for basic, 100 for retrieval, 200 for memory integrity)

3. **How to handle LanceDB dependencies in property tests?**
   - What we know: Phase 113 mocks LanceDB handler for semantic search
   - What's unclear: Should property tests use real LanceDB or continue mocking?
   - Recommendation: Continue mocking (property tests focus on invariants, not integration)

4. **Should property tests validate against Phase 113 validated bugs?**
   - What we know: Phase 113 documents VALIDATED_BUG comments with fix commits
   - What's unclear: Should Phase 124 regression test these specific bugs?
   - Recommendation: Yes, include @example decorators for VALIDATED_BUG boundary cases

## Sources

### Primary (HIGH confidence)
- Hypothesis documentation - https://hypothesis.readthedocs.io/ - Official Hypothesis docs (verified 2026-03-02)
- Phase 113 property tests - `/backend/tests/property_tests/episodes/test_episode_*_invariants.py` - Proven patterns (2358+ lines)
- Phase 113 research - `/.planning/phases/113-episodic-memory-coverage/113-RESEARCH.md` - Test infrastructure and patterns
- Hypothesis strategies - https://hypothesis.readthedocs.io/en/latest/data.html - Strategy reference
- [快速掌握Hypothesis：Python属性测试的终极入门指南](https://m.blog.csdn.net/gitblog_00205/article/details/143546636) - 2026 best practices
- [属性测试革命：Hypothesis框架深度实战指南](https://blog.csdn.net/sinat_41617212/article/details/158239096) - Advanced patterns

### Secondary (MEDIUM confidence)
- Episode service source code - `/backend/core/episode_*_service.py` - Service implementations
- Phase 113 plans - `/.planning/phases/113-episodic-memory-coverage/*-PLAN.md` - Test structure
- [10分钟快速上手Hypothesis](https://m.blog.csdn.net/gitblog_01124/article/details/143621170) - Quick start guide
- [Agentic Property-Based Testing (arXiv 2025)](https://arxiv.org/html/2510.09907v1) - AI-generated PBT patterns

### Tertiary (LOW confidence)
- None - All findings verified from primary sources or existing Phase 113 tests

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Hypothesis is industry standard, Phase 113 proven in production
- Architecture: HIGH - 2358+ lines of proven property tests from Phase 113
- Pitfalls: HIGH - All pitfalls documented from Phase 113 experience
- Invariants: HIGH - 28 proven invariants identified from existing tests

**Research date:** 2026-03-02
**Valid until:** 2026-04-01 (30 days - stable Hypothesis ecosystem)

## Appendix: Phase 113 Property Test Coverage

### Existing Property Test Files
1. **test_episode_segmentation_invariants.py** - 827 lines
   - 10 test classes covering segmentation, topic changes, task completion, boundaries, metadata, context, similarity, entities, summaries, importance, consolidation
   - Key invariants: Time gaps > threshold, topic changes, segment boundaries, information preservation

2. **test_episode_retrieval_invariants.py** - 1070 lines
   - 9 test classes covering temporal, semantic, sequential, contextual retrieval, filtering, access logging, integrity, canvas-aware, feedback-linked, pagination, caching, security
   - Key invariants: Temporal filtering, similarity bounds, ranking, limit enforcement, feedback boosting

3. **test_episode_lifecycle_invariants.py** - 456 lines
   - 4 test classes covering decay, consolidation, archival, lifecycle integration
   - Key invariants: Decay formula, consolidation similarity, no circular references, archival searchability

4. **test_episode_service_contracts.py** - Service contract tests
5. **test_episode_memory_consolidation_invariants.py** - Memory consolidation tests
6. **test_episode_retrieval_advanced_invariants.py** - Advanced retrieval patterns

**Total Phase 113 Property Test Coverage: 2358+ lines across 6 test files**

### Proven max_examples Values
- **50 examples**: Basic invariants (topic consistency, entity extraction, segment ordering)
- **100 examples**: Retrieval invariants (temporal filtering, semantic retrieval, ranking, limits)
- **200 examples**: Critical memory integrity (time gaps, decay formula, similarity thresholds, boundary enforcement)

### VALIDATED_BUG Pattern
Phase 113 consistently documents bugs found by property tests:
```python
"""
VALIDATED_BUG: Gap of exactly 4 hours did not trigger segmentation when threshold=4.
Root cause: Using >= instead of > in time gap comparison.
Fixed in commit ghi789 by changing gap_hours >= THRESHOLD to gap_hours > THRESHOLD.
"""
```

Phase 124 should follow this pattern for any new bugs discovered.

### Recommended Phase 124 Approach
1. **Review Phase 113 coverage gaps**: Check which invariants need more comprehensive testing
2. **Expand existing test files**: Add new invariants to existing test classes
3. **Add @example boundary cases**: Document critical edge cases with explicit examples
4. **Increase max_examples selectively**: Use 200 examples for new critical invariants
5. **Document VALIDATED_BUG**: Follow Phase 113 pattern for any bugs discovered
6. **Reuse proven strategies**: Copy Phase 113 strategy composition patterns

**DO NOT create new test file structure** - expand the existing 6 test files from Phase 113.
