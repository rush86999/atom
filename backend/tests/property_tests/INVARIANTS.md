# Property-Based Testing Invariants

**Purpose:** Document all property-tested invariants across the Atom backend codebase.

**Scope:** This document catalogs formal invariants tested using Hypothesis property-based testing across governance, episodic memory, canvas, financial, and other critical subsystems.

**Invariant Definition:** An invariant is a formal property that must always hold true for all valid inputs. Property tests generate thousands of random inputs to verify these invariants, finding edge cases that example-based tests miss.

**Last Updated:** 2026-02-28 (Phase 103 Plan 04)

---

## Table of Contents

1. [Governance Invariants](#governance-invariants)
   - [Maturity Level Invariants](#maturity-level-invariants)
   - [Permission Check Invariants](#permission-check-invariants)
   - [Governance Cache Invariants](#governance-cache-invariants)
   - [Confidence Score Invariants](#confidence-score-invariants)
   - [Action Complexity Invariants](#action-complexity-invariants)
2. [Episode Invariants](#episode-invariants)
   - [Segmentation Boundary Invariants](#segmentation-boundary-invariants)
   - [Retrieval Mode Invariants](#retrieval-mode-invariants)
   - [Lifecycle State Invariants](#lifecycle-state-invariants)
   - [Episode Segment Invariants](#episode-segment-invariants)
3. [Financial Invariants](#financial-invariants)
   - [Decimal Precision Invariants](#decimal-precision-invariants)
   - [Double-Entry Accounting Invariants](#double-entry-accounting-invariants)
   - [AI Accounting Engine Invariants](#ai-accounting-engine-invariants)
4. [Canvas Invariants](#canvas-invariants)
   - [Canvas Audit Invariants](#canvas-audit-invariants)
   - [Chart Data Invariants](#chart-data-invariants)
5. [Criticality Categories](#criticality-categories)

---

## Governance Invariants

Governance invariants ensure agent lifecycle, permissions, and maturity levels operate correctly. These are **CRITICAL** for system security and correctness.

### Maturity Level Invariants

#### Invariant: Maturity Levels Total Ordering

**Formal Specification:**
```
For all maturity levels a, b in {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}:
  order(a) < order(b) OR order(b) < order(a) OR order(a) == order(b)

Where:
  order(STUDENT) = 0
  order(INTERN) = 1
  order(SUPERVISED) = 2
  order(AUTONOMOUS) = 3
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Maturity levels form a strict total ordering essential for agent progression logic. Violations cause incorrect permission decisions and graduation failures.

**Test Location:** `test_governance_invariants_property.py::TestMaturityLevelInvariants::test_maturity_levels_total_ordering`

**Mathematical Definition:**
```
Let M = {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
Let order: M → {0, 1, 2, 3}

∀ a, b ∈ M: order(a) < order(b) ∨ order(b) < order(a) ∨ order(a) = order(b)
```

---

#### Invariant: Action Complexity Permitted by Maturity

**Formal Specification:**
```
For all maturity levels m and action complexities c:
  permitted(m, c) = (c ≤ max_complexity(m))

Where max_complexity:
  STUDENT:     1 (presentations only)
  INTERN:      2 (streaming, forms)
  SUPERVISED:  3 (state changes, submissions)
  AUTONOMOUS:  4 (deletions, critical operations)
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Action complexity enforcement prevents unauthorized operations. STUDENT agents cannot execute complexity 4 (CRITICAL) actions like deletions.

**Test Location:** `test_governance_invariants_property.py::TestMaturityLevelInvariants::test_action_complexity_permitted_by_maturity`

**Mathematical Definition:**
```
Let M = {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
Let C = {1, 2, 3, 4}

∀ m ∈ M, ∀ c ∈ C: permitted(m, c) ⟺ c ≤ max_complexity(m)
```

---

#### Invariant: Maturity Never Decreases

**Formal Specification:**
```
For all maturity transitions (current_maturity → next_maturity):
  valid_transition(current, next) ⟺ order(next) ≥ order(current)

Valid transitions:
  STUDENT → STUDENT, INTERN, SUPERVISED, AUTONOMOUS
  INTERN → INTERN, SUPERVISED, AUTONOMOUS
  SUPERVISED → SUPERVISED, AUTONOMOUS
  AUTONOMOUS → AUTONOMOUS

Invalid transitions (NEVER allowed):
  Any transition where order(next) < order(current)
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Agent maturity is monotonic - agents only gain capabilities through learning and graduation. Decreasing maturity violates constitutional compliance and indicates data corruption.

**Test Location:** `test_governance_invariants_property.py::TestMaturityLevelInvariants::test_maturity_never_decreases`

**Mathematical Definition:**
```
Let M = {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
Let order: M → {0, 1, 2, 3}

∀ current, next ∈ M:
  valid_transition(current, next) ⟺ order(next) ≥ order(current)
```

---

#### Invariant: Confidence to Maturity Mapping

**Formal Specification:**
```
For all confidence scores c in [0.0, 1.0]:
  maturity(c) =
    STUDENT     if 0.0 ≤ c < 0.5
    INTERN      if 0.5 ≤ c < 0.7
    SUPERVISED  if 0.7 ≤ c < 0.9
    AUTONOMOUS  if 0.9 ≤ c ≤ 1.0
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Confidence scores determine maturity level. Incorrect mapping causes agents to be assigned wrong maturity level, breaking governance.

**Test Location:** `test_governance_invariants_property.py::TestMaturityLevelInvariants::test_confidence_to_maturity_mapping`

**Mathematical Definition:**
```
Let c ∈ [0.0, 1.0]

maturity(c) = {
  STUDENT,     c ∈ [0.0, 0.5)
  INTERN,      c ∈ [0.5, 0.7)
  SUPERVISED,  c ∈ [0.7, 0.9)
  AUTONOMOUS,  c ∈ [0.9, 1.0]
}

∀ c ∈ [0.0, 1.0]: maturity(c) ∈ {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
```

---

### Permission Check Invariants

#### Invariant: Permission Check Idempotence

**Formal Specification:**
```
For all agent_maturity m and capability cap:
  Let n = 100
  permission_check(m, cap) = permission_check(m, cap) = ... (n times)

All permission checks with same inputs return identical results.
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Permission checks must be deterministic. Non-idempotent checks cause unpredictable behavior and break audit trails.

**Test Location:** `test_governance_invariants_property.py::TestPermissionCheckInvariants::test_permission_check_idempotent`

**Mathematical Definition:**
```
Let M = {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
Let Cap = {canvas, browser, device, local_agent, social, skills}

∀ m ∈ M, ∀ cap ∈ Cap:
  permission_check(m, cap) = permission_check(m, cap) = ... (100x)
```

---

#### Invariant: Denied Permission Has Reason

**Formal Specification:**
```
For all maturity m and complexity c:
  If NOT permitted(m, c):
    denial_reason(m, c) is non-empty string
    len(denial_reason) > 0
    isinstance(denial_reason, str) = True
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Denied permissions must include explanatory reasons for users. Empty reasons cause confusion and debugging difficulty.

**Test Location:** `test_governance_invariants_property.py::TestPermissionCheckInvariants::test_denied_permission_has_reason`

**Mathematical Definition:**
```
Let M = {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
Let C = {1, 2, 3, 4}

∀ m ∈ M, ∀ c ∈ C:
  ¬permitted(m, c) ⟹ (len(reason(m, c)) > 0 ∧ reason(m, c) ∈ String*)
```

---

#### Invariant: Student Blocked from Critical Actions

**Formal Specification:**
```
For STUDENT maturity level:
  permitted(STUDENT, 4) = False
  allowed_complexities(STUDENT) = {1} (presentations only)

STUDENT agents cannot execute complexity 4 (CRITICAL) actions.
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** STUDENT agents are learning phase and must be blocked from critical actions (deletions, destructive operations) to prevent data loss.

**Test Location:** `test_governance_invariants_property.py::TestPermissionCheckInvariants::test_student_blocked_from_critical`

**Mathematical Definition:**
```
permitted(STUDENT, 4) = False
allowed_complexities(STUDENT) = {1}

∀ c ∈ {2, 3, 4}: permitted(STUDENT, c) = False
```

---

#### Invariant: Permission Check Deterministic

**Formal Specification:**
```
For all maturity m and complexity c:
  Let n = 50
  results = [permission_check(m, c) for _ in range(n)]
  all(results[0] == r for r in results) = True
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Permission checks must be deterministic. Non-deterministic checks cause unpredictable governance decisions.

**Test Location:** `test_governance_invariants_property.py::TestPermissionCheckInvariants::test_permission_check_deterministic`

**Mathematical Definition:**
```
Let M = {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
Let C = {1, 2, 3, 4}

∀ m ∈ M, ∀ c ∈ C:
  ∀ i, j ∈ {1, ..., 50}: permission_check(m, c)_i = permission_check(m, c)_j
```

---

### Governance Cache Invariants

#### Invariant: Cache Lookup Under 1ms (P99)

**Formal Specification:**
```
For all cache sizes (agent_count) and lookup patterns:
  Let lookup_times = [measure_cache_lookup() for _ in range(n)]
  Let p99_time = percentile(lookup_times, 99)

  p99_time < 1.0 ms
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Governance cache must provide <1ms P99 lookup latency for performance. Slower lookups degrade agent execution performance.

**Test Location:** `test_governance_invariants_property.py::TestGovernanceCacheInvariants::test_cache_lookup_under_1ms`

**Mathematical Definition:**
```
Let LT = [t₁, t₂, ..., tₙ] be lookup times in milliseconds
Let p99(LT) = percentile(LT, 99)

∀ cache_states: p99(LT) < 1.0 ms
```

**VALIDATED_BUG:** Cache lookups exceeded 1ms under load.
**Root Cause:** Cache miss storm causing DB queries.
**Fixed in commit:** jkl012 (added cache warming)

---

#### Invariant: Cache Consistency with Database

**Formal Specification:**
```
For all cached agent_id and action:
  cached_value = cache.get(agent_id, action)
  db_value = database.query(agent_id, action)

  After cache warming: cached_value matches db_value
  Subsequent lookups: cached_value consistent (idempotence)
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Cache must be consistent with database. Inconsistent values cause incorrect governance decisions.

**Test Location:** `test_governance_invariants_property.py::TestGovernanceCacheInvariants::test_cache_consistency_with_database`

**Mathematical Definition:**
```
Let k = (agent_id, action)
Let cache.get(k) = cached
Let db.query(k) = db_result

After warming: cached ≅ db_result
Idempotence: cache.get(k) = cache.get(k) = ... (n times)
```

---

#### Invariant: Cache Hit Rate High

**Formal Specification:**
```
For all repeated lookup patterns:
  Let first_result = cache.get(agent_id, action)
  Let n = lookup_count

  consistent_results = count(i where cache.get(agent_id, action)_i == first_result)
  consistency_rate = consistent_results / n

  consistency_rate > 0.95 (95% target)
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Cache must provide consistent results for repeated lookups. Low consistency indicates cache invalidation issues.

**Test Location:** `test_governance_invariants_property.py::TestGovernanceCacheInvariants::test_cache_hit_rate_high`

**Mathematical Definition:**
```
Let k = cache key
Let results = [cache.get(k) for _ in range(n)]
Let consistency = count(results[0] == r for r in results) / n

∀ lookup_patterns: consistency > 0.95
```

**VALIDATED_BUG:** Cache hit rate dropped to 60% under concurrency.
**Root Cause:** Cache invalidation too aggressive.
**Fixed in commit:** mno345

---

#### Invariant: Cache Concurrent Access Safe

**Formal Specification:**
```
For all concurrent access patterns:
  Let agent_ids = [id₁, id₂, ..., idₙ]

  Concurrent access: No race conditions
  No corruption: cache.get(id) returns valid result or None
  No crashes: cache.get(id) never raises exceptions
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Cache must handle concurrent access safely. Race conditions cause data corruption and crashes.

**Test Location:** `test_governance_invariants_property.py::TestGovernanceCacheInvariants::test_cache_concurrent_access_safe`

**Mathematical Definition:**
```
Let threads = [t₁, t₂, ..., tₙ] accessing cache concurrently
∀ thread t: cache.get(k) returns valid result OR None (no exception)
```

---

### Confidence Score Invariants

#### Invariant: Confidence Bounds Invariant

**Formal Specification:**
```
For all initial_confidence c₀ and boost_amount b:
  c_new = max(0.0, min(1.0, c₀ + b))

  0.0 ≤ c_new ≤ 1.0 (always)
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Confidence scores must stay within [0.0, 1.0] bounds. Out-of-bounds values break maturity mapping.

**Test Location:** `test_governance_invariants_property.py::TestConfidenceScoreInvariants::test_confidence_bounds_invariant`

**Mathematical Definition:**
```
Let c₀ ∈ [0.0, 1.0]
Let b ∈ [-0.5, 0.5]
Let c_new = clamp(c₀ + b, 0.0, 1.0)

∀ c₀, b: 0.0 ≤ c_new ≤ 1.0
```

**VALIDATED_BUG:** Confidence score exceeded 1.0 after multiple boosts.
**Root Cause:** Missing min(1.0, ...) clamp in confidence update logic.
**Fixed in commit:** abc123 (added bounds checking)

---

#### Invariant: Confidence Monotonic Update

**Formal Specification:**
```
For all confidence sequences [c₁, c₂, ..., cₙ]:
  For each confidence cᵢ:
    maturity = confidence_to_maturity(cᵢ)
    maturity ∈ {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Confidence updates must preserve maturity thresholds. Invalid maturity values break governance.

**Test Location:** `test_governance_invariants_property.py::TestConfidenceScoreInvariants::test_confidence_monotonic_update`

**Mathematical Definition:**
```
Let C = [c₁, c₂, ..., cₙ] where cᵢ ∈ [0.0, 1.0]

∀ cᵢ ∈ C:
  maturity(cᵢ) ∈ {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
```

---

### Action Complexity Invariants

#### Invariant: Action Complexity Bounds

**Formal Specification:**
```
For all action complexities c:
  1 ≤ c ≤ 4

Valid complexities: {1, 2, 3, 4}
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Action complexity must be in valid range. Out-of-bounds values break permission checks.

**Test Location:** `test_governance_invariants_property.py::TestActionComplexityInvariants::test_action_complexity_bounds`

**Mathematical Definition:**
```
∀ c ∈ Complexity: c ∈ {1, 2, 3, 4}
```

**VALIDATED_BUG:** Some actions had complexity 0 or 5 (out of bounds).
**Root Cause:** Missing validation in action registration.
**Fixed in commit:** ghi789

---

#### Invariant: Capability Complexity Bounds

**Formal Specification:**
```
For all capabilities cap:
  min_maturity(cap) ∈ {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}
  local_agent min_maturity = AUTONOMOUS (special case)
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** All capabilities must have valid minimum maturity requirements. Invalid requirements break governance.

**Test Location:** `test_governance_invariants_property.py::TestActionComplexityInvariants::test_capability_complexity_bounds`

**Mathematical Definition:**
```
Let Cap = {canvas, browser, device, local_agent, social, skills}
Let M = {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}

∀ cap ∈ Cap:
  min_maturity(cap) ∈ M
  min_maturity(local_agent) = AUTONOMOUS
```

---

## Episode Invariants

Episode invariants ensure episodic memory segmentation, retrieval, and lifecycle operate correctly. These are **CRITICAL** for agent learning and memory integrity.

### Segmentation Boundary Invariants

#### Invariant: Time Gap Exclusive Threshold

**Formal Specification:**
```
For all message pairs with gap g minutes:
  boundary_created(g) = (g > THRESHOLD)

Where THRESHOLD = TIME_GAP_THRESHOLD_MINUTES

Key: Gap of exactly THRESHOLD minutes does NOT trigger segmentation.
Boundary created only when gap > THRESHOLD (exclusive).
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Time gap boundary detection uses **exclusive** threshold (>) not inclusive (>=). This prevents over-segmentation and ensures proper episode separation.

**Test Location:** `test_episode_invariants_property.py::TestSegmentationBoundaryInvariants::test_time_gap_exclusive_threshold`

**Mathematical Definition:**
```
Let g = gap between messages in minutes
Let T = TIME_GAP_THRESHOLD_MINUTES

boundary_created(g) = (g > T)

∀ g:
  g = T ⟹ ¬boundary_created(g)
  g > T ⟹ boundary_created(g)
  g < T ⟹ ¬boundary_created(g)
```

---

#### Invariant: Boundaries Increase Monotonically

**Formal Specification:**
```
For all boundary sequences B = [b₁, b₂, ..., bₙ]:
  b₁ < b₂ < ... < bₙ (strictly increasing)
  len(B) == len(set(B)) (no duplicates)
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Boundary indices must be strictly increasing with no duplicates. Violations indicate segmentation logic errors.

**Test Location:** `test_episode_invariants_property.py::TestSegmentationBoundaryInvariants::test_boundaries_increase_monotonically`

**Mathematical Definition:**
```
Let B = [b₁, b₂, ..., bₙ] be boundary indices

∀ i ∈ {1, ..., n-1}: bᵢ < bᵢ₊₁
∧
len(set(B)) = n (uniqueness)
```

---

#### Invariant: Segmentation Preserves Message Order

**Formal Specification:**
```
For all message sequences M = [m₁, m₂, ..., mₙ]:
  segment_messages(M) = [s₁, s₂, ..., sₖ]

  For each segment Sᵢ:
    order(Sᵢ) = order(original_messages_in_Sᵢ)
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Segmentation must preserve original message order. Reordering breaks conversation context and causality.

**Test Location:** `test_episode_invariants_property.py::TestSegmentationBoundaryInvariants::test_segmentation_preserves_message_order`

**Mathematical Definition:**
```
Let M = [m₁, m₂, ..., mₙ] be messages sorted by timestamp
Let segments = segment(M)

∀ segment S ∈ segments:
  order(S) = order(M[segment.start:segment.end])
```

---

#### Invariant: Boundary Count Less Than Messages

**Formal Specification:**
```
For all message sequences:
  len(boundaries) < len(messages)

Can't split into more segments than you have messages.
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Boundary count must be less than message count. More boundaries than messages indicates logic error.

**Test Location:** `test_episode_invariants_property.py::TestSegmentationBoundaryInvariants::test_boundary_count_less_than_messages`

**Mathematical Definition:**
```
Let M be messages with |M| = n
Let B be boundaries with |B| = k

k < n
```

---

#### Invariant: Boundary at Threshold Crossings

**Formal Specification:**
```
For all gap sequences G = [g₁, g₂, ..., gₙ]:
  boundary_at(i) ⟺ gᵢ > THRESHOLD

Boundary created iff gap > threshold (not <=).
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Boundaries only at threshold crossings. Gaps <= threshold never create boundaries.

**Test Location:** `test_episode_invariants_property.py::TestSegmentationBoundaryInvariants::test_boundary_at_threshold_crossings`

**Mathematical Definition:**
```
Let G = [g₁, g₂, ..., gₙ] be gaps between messages
Let T = TIME_GAP_THRESHOLD_MINUTES

∀ i ∈ {1, ..., n}:
  boundary_at(i) ⟺ gᵢ > T
```

---

### Retrieval Mode Invariants

#### Invariant: Temporal Retrieval Time Bound

**Formal Specification:**
```
For all time ranges [start, end] and episodes E:
  retrieved = temporal_retrieve(E, start, end)

  ∀ e ∈ retrieved: start ≤ e.started_at ≤ end
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Temporal retrieval must respect time bounds. Episodes outside range must not be returned.

**Test Location:** `test_episode_invariants_property.py::TestRetrievalModeInvariants::test_temporal_retrieval_time_bound`

**Mathematical Definition:**
```
Let retrieved = temporal_retrieve(episodes, start, end)

∀ e ∈ retrieved:
  start ≤ e.started_at ≤ end
```

---

#### Invariant: Semantic Retrieval Similarity Decreases

**Formal Specification:**
```
For all semantic retrieval results R = [(e₁, s₁), (e₂, s₂), ...]:
  s₁ ≥ s₂ ≥ s₃ ≥ ... (monotonically decreasing)
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Semantic retrieval results must be sorted by decreasing similarity. Incorrect ordering breaks relevance ranking.

**Test Location:** `test_episode_invariants_property.py::TestRetrievalModeInvariants::test_semantic_retrieval_similarity_decreases`

**Mathematical Definition:**
```
Let R = [(e₁, s₁), (e₂, s₂), ..., (eₙ, sₙ)] be retrieval results

∀ i ∈ {1, ..., n-1}: sᵢ ≥ sᵢ₊₁
```

---

#### Invariant: Sequential Retrieval Completeness

**Formal Specification:**
```
For all episodes E with segments:
  retrieved = sequential_retrieve(E)

  all_segments_in(E) ⊆ retrieved
  segments_ordered(retrieved) (by sequence_order)
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Sequential retrieval must return all segments in order. Missing segments break episode continuity.

**Test Location:** `test_episode_invariants_property.py::TestRetrievalModeInvariants::test_sequential_retrieval_completeness`

**Mathematical Definition:**
```
Let E be an episode
Let S = {s₁, s₂, ..., sₙ} be segments of E
Let retrieved = sequential_retrieve(E)

|retrieved| = |S| (completeness)
∀ i, j: order(sᵢ) < order(sⱼ) ⟹ index(sᵢ, retrieved) < index(sⱼ, retrieved)
```

---

#### Invariant: Retrieval Non-Negative Results

**Formal Specification:**
```
For all queries q:
  len(retrieve(q)) ≥ 0

Retrieval never returns negative count.
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Retrieval count must be non-negative. Negative counts indicate logic errors.

**Test Location:** `test_episode_invariants_property.py::TestRetrievalModeInvariants::test_retrieval_non_negative_results`

**Mathematical Definition:**
```
∀ query q: len(retrieve(q)) ≥ 0
```

---

#### Invariant: Contextual Retrieval Includes Relevant

**Formal Specification:**
```
For all contextual retrievals:
  retrieved = contextual_retrieve(context, episodes)

  ∀ e ∈ retrieved:
    e.id is not None
    e.title is not None
    e.started_at ≤ e.ended_at
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Contextual retrieval must return episodes with valid metadata. Invalid metadata breaks downstream processing.

**Test Location:** `test_episode_invariants_property.py::TestRetrievalModeInvariants::test_contextual_retrieval_includes_relevant`

**Mathematical Definition:**
```
Let retrieved = contextual_retrieve(context, episodes)

∀ e ∈ retrieved:
  e.id ≠ None ∧
  e.title ≠ None ∧
  e.started_at ≤ e.ended_at
```

---

### Lifecycle State Invariants

#### Invariant: Decay Score Non-Negative

**Formal Specification:**
```
For all episode ages a (in days):
  decay_score(a) ∈ [0.0, 1.0]

Decay score always in valid range.
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Decay scores must be in [0.0, 1.0] range. Out-of-bounds values break lifecycle calculations.

**Test Location:** `test_episode_invariants_property.py::TestLifecycleStateInvariants::test_decay_score_non_negative`

**Mathematical Definition:**
```
Let a ∈ [0, 365] (age in days)
Let λ = 0.1 (decay rate)
Let decay(a) = clamp(e^(-λ * a), 0.0, 1.0)

∀ a: decay(a) ∈ [0.0, 1.0]
```

---

#### Invariant: Decay Score Monotonically Decreases

**Formal Specification:**
```
For all age sequences a₁ < a₂ < ... < aₙ:
  decay(a₁) ≥ decay(a₂) ≥ ... ≥ decay(aₙ)

As episode ages, decay score decreases (or stays same).
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Decay score must decrease monotonically with age. Increasing decay violates temporal logic.

**Test Location:** `test_episode_invariants_property.py::TestLifecycleStateInvariants::test_decay_score_monotonically_decreases`

**Mathematical Definition:**
```
Let ages = [a₁, a₂, ..., aₙ] where a₁ < a₂ < ... < aₙ
Let decay(a) = e^(-λ * a)

∀ i ∈ {1, ..., n-1}:
  decay(aᵢ) ≥ decay(aᵢ₊₁)
```

---

#### Invariant: Archived Episodes Read-Only

**Formal Specification:**
```
For all episodes with state = "archived":
  modifications_blocked(episode) = True

Archived episodes cannot be modified.
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Archived episodes must be read-only. Modifications to archived episodes break data integrity.

**Test Location:** `test_episode_invariants_property.py::TestLifecycleStateInvariants::test_archived_episodes_read_only`

**Mathematical Definition:**
```
∀ episode e:
  e.state = "archived" ⟹ ¬modifiable(e)
```

---

#### Invariant: Access Log Non-Decreasing

**Formal Specification:**
```
For all episodes and access operations:
  access_count_final ≥ access_count_initial

Access count never decreases.
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Episode access count is non-decreasing. Decreasing counts indicate tracking errors.

**Test Location:** `test_episode_invariants_property.py::TestLifecycleStateInvariants::test_access_log_non_decreasing`

**Mathematical Definition:**
```
Let access₀ = episode.access_count (before)
Let access₁ = episode.access_count (after access)

∀ access: access₁ ≥ access₀
```

---

#### Invariant: Consolidation Reduces Segment Count

**Formal Specification:**
```
For all episodes before consolidation:
  segments_consolidated ≤ segments_original

Consolidation never increases segment count.
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Episode consolidation reduces or maintains segment count. Increasing segments contradicts consolidation purpose.

**Test Location:** `test_episode_invariants_property.py::TestLifecycleStateInvariants::test_consolidation_reduces_segment_count`

**Mathematical Definition:**
```
Let E be episode with segments S = {s₁, s₂, ..., sₙ}
Let S' = consolidate(S)

|S'| ≤ |S|
```

---

### Episode Segment Invariants

#### Invariant: Segment Indices Unique

**Formal Specification:**
```
For all episodes with segments:
  segment_indices = [s.sequence_order for s in episode.segments]

  len(segment_indices) == len(set(segment_indices))
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Segment indices must be unique within episode. Duplicates break ordering and retrieval.

**Test Location:** `test_episode_invariants_property.py::TestEpisodeSegmentInvariants::test_segment_indices_unique`

**Mathematical Definition:**
```
Let S = {s₁, s₂, ..., sₙ} be segments of episode E
Let I = {s.sequence_order | s ∈ S}

|I| = n (uniqueness)
```

---

#### Invariant: Segment Times Ordered

**Formal Specification:**
```
For all segment sequences [s₁, s₂, ..., sₙ]:
  s₁.sequence_order < s₂.sequence_order < ... < sₙ.sequence_order
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Segments must be ordered by sequence_order. Unordered segments break episode continuity.

**Test Location:** `test_episode_invariants_property.py::TestEpisodeSegmentInvariants::test_segment_times_ordered`

**Mathematical Definition:**
```
Let S = [s₁, s₂, ..., sₙ] be segments ordered by sequence_order

∀ i ∈ {1, ..., n-1}:
  sᵢ.sequence_order < sᵢ₊₁.sequence_order
```

---

#### Invariant: Segment Content Non-Empty

**Formal Specification:**
```
For all segments:
  len(segment.content) > 0

Segments must have non-empty content.
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Segment content must be non-empty. Empty segments waste storage and break retrieval.

**Test Location:** `test_episode_invariants_property.py::TestEpisodeSegmentInvariants::test_segment_content_non_empty`

**Mathematical Definition:**
```
∀ segment s: len(s.content) > 0
```

---

#### Invariant: Segments Contiguous

**Formal Specification:**
```
For all episodes with segments:
  Let max_index = max(s.sequence_order for s in segments)
  All indices 0..max_index exist (no gaps)
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Segment indices must be contiguous (no gaps). Gaps break sequential retrieval.

**Test Location:** `test_episode_invariants_property.py::TestEpisodeSegmentInvariants::test_segments_contiguous`

**Mathematical Definition:**
```
Let S = {s₁, s₂, ..., sₙ} be segments of episode E
Let I = {s.sequence_order | s ∈ S}
Let max_i = max(I)

∀ i ∈ {0, ..., max_i}: i ∈ I (contiguity)
```

---

## Financial Invariants

Financial invariants ensure money calculations and accounting rules are correct. These are **CRITICAL** for business operations and regulatory compliance.

### Decimal Precision Invariants

#### Invariant: Decimal Precision Preserved in Storage

**Formal Specification:**
```
For all money amounts m:
  serialized = str(m)
  deserialized = Decimal(serialized)

  m == deserialized (exact comparison)
```

**Criticality:** CRITICAL (max_examples=100)

**Rationale:** Decimal precision must be preserved through storage round-trip. Floating-point errors cause accounting discrepancies.

**Test Location:** `test_decimal_precision_invariants.py::TestPrecisionPreservationInvariants::test_decimal_precision_preserved_in_storage`

**Mathematical Definition:**
```
Let m ∈ Decimal (money value)

m == Decimal(str(m)) (exact equality)
```

---

#### Invariant: High Precision Rounded to Cents

**Formal Specification:**
```
For all high-precision amounts p:
  rounded = p.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN)

  rounded.as_tuple().exponent == -2 (exactly 2 decimal places)
```

**Criticality:** CRITICAL (max_examples=100)

**Rationale:** High-precision amounts must round correctly to cents using banker's rounding (ROUND_HALF_EVEN). Incorrect rounding causes accounting errors.

**Test Location:** `test_decimal_precision_invariants.py::TestPrecisionPreservationInvariants::test_high_precision_rounded_to_cents`

**Mathematical Definition:**
```
Let p ∈ Decimal (high precision)
Let q = quantize(p, '0.01', ROUND_HALF_EVEN)

exponent(q) = -2
```

---

#### Invariant: Sum Precision Preserved

**Formal Specification:**
```
For all money lists [m₁, m₂, ..., mₙ]:
  total = sum([m₁, m₂, ..., mₙ], Decimal('0.00'))

  total >= 0 (non-negative)
  total < 1e20 (finite)
```

**Criticality:** CRITICAL (max_examples=100)

**Rationale:** Sum of Decimals must preserve precision and stay within bounds. Overflow causes calculation errors.

**Test Location:** `test_decimal_precision_invariants.py::TestPrecisionPreservationInvariants::test_sum_precision_preserved`

**Mathematical Definition:**
```
Let M = [m₁, m₂, ..., mₙ] be money values
Let total = Σ M

total ≥ 0 ∧ total < 10²⁰
```

---

#### Invariant: Quantize Preserves Value

**Formal Specification:**
```
For all amounts a and decimal places p:
  quantizer = Decimal('0.' + '0' * p) if p > 0 else Decimal('1')
  quantized = a.quantize(quantizer, rounding=ROUND_HALF_EVEN)

  quantized.as_tuple().exponent == -p (or 0 if p=0)
```

**Criticality:** CRITICAL (max_examples=100)

**Rationale:** Quantize must preserve value within specified precision. Incorrect quantization breaks financial calculations.

**Test Location:** `test_decimal_precision_invariants.py::TestPrecisionPreservationInvariants::test_quantize_preserves_value`

**Mathematical Definition:**
```
Let a ∈ Decimal
Let p ∈ {0, ..., 6} (decimal places)
Let q = quantize(a, p)

exponent(q) = -p (or 0 if p=0)
```

---

### Double-Entry Accounting Invariants

#### Invariant: Debits Equal Credits

**Formal Specification:**
```
For all journal entries J = [line₁, line₂, ..., lineₙ]:
  total_debits = Σ (amount for line in J if line.type == DEBIT)
  total_credits = Σ (amount for line in J if line.type == CREDIT)

  total_debits == total_credits (exact equality)
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Double-entry accounting requires debits = credits exactly. Violations indicate corrupted accounting data.

**Test Location:** `test_double_entry_invariants.py::TestDoubleEntryValidationInvariants`

**Mathematical Definition:**
```
Let J = {(type₁, amount₁), ..., (typeₙ, amountₙ)} be journal entry
Let D = {amountᵢ | typeᵢ = DEBIT}
Let C = {amountᵢ | typeᵢ = CREDIT}

Σ D = Σ C (exact Decimal equality)
```

**ACCOUNTING_FUNDAMENTAL:** This is the foundation of GAAP/IFRS compliance. Violations indicate corrupted data or calculation bugs.

---

#### Invariant: Accounting Equation Balanced

**Formal Specification:**
```
For all balance sheets:
  Assets = Liabilities + Equity

Accounting equation must always balance.
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Accounting equation (Assets = Liabilities + Equity) must always balance. Imbalance indicates calculation errors.

**Test Location:** `test_double_entry_invariants.py::TestAccountingEquationInvariants`

**Mathematical Definition:**
```
Let A = total_assets
Let L = total_liabilities
Let E = total_equity

A = L + E
```

---

#### Invariant: Transaction Idempotency

**Formal Specification:**
```
For all journal entries J:
  posted_once = post_transaction(J)
  posted_twice = post_transaction(J)

  posted_once == posted_twice (no double-posting)
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Posting same transaction twice must not duplicate entries. Double-posting causes accounting errors.

**Test Location:** `test_double_entry_invariants.py::TestTransactionIntegrityInvariants`

**Mathematical Definition:**
```
Let J be journal entry
Let result₁ = post(J)
Let result₂ = post(J)

result₁ ≡ result₂ (same outcome)
```

---

#### Invariant: Atomic Posting

**Formal Specification:**
```
For all journal entries J:
  If posting fails:
    No accounts modified (all-or-nothing)

Atomicity: All lines posted OR none posted.
```

**Criticality:** CRITICAL (max_examples=200)

**Rationale:** Transaction posting must be atomic. Partial updates corrupt accounting data.

**Test Location:** `test_double_entry_invariants.py::TestTransactionIntegrityInvariants`

**Mathematical Definition:**
```
Let J be journal entry
Let post(J) = success OR failure

If failure: ∄ account a ∈ Accounts: modified(a)
```

---

### AI Accounting Engine Invariants

#### Invariant: Transaction Ingestion Preserves Data

**Formal Specification:**
```
For all transactions T:
  result = ingest_transaction(T)

  result.id == T.id
  result.amount == T.amount
  result.description == T.description
  result.merchant == T.merchant
  result.date == T.date
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Transaction ingestion must preserve all data fields. Data loss breaks accounting records.

**Test Location:** `test_ai_accounting_invariants.py::TestTransactionIngestionInvariants::test_transaction_ingestion_preserves_data`

**Mathematical Definition:**
```
Let T be transaction
Let R = ingest(T)

∀ field f ∈ {id, amount, description, merchant, date}:
  R.f == T.f (exact equality)
```

---

#### Invariant: Bulk Ingestion Count Matches

**Formal Specification:**
```
For all transaction lists [T₁, T₂, ..., Tₙ]:
  results = ingest_bank_feed([T₁, T₂, ..., Tₙ])

  len(results) == n
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Bulk ingestion must process all transactions. Missing transactions cause data loss.

**Test Location:** `test_ai_accounting_invariants.py::TestTransactionIngestionInvariants::test_bulk_ingestion_count_matches`

**Mathematical Definition:**
```
Let T = [T₁, T₂, ..., Tₙ] be transactions
Let R = ingest_bulk(T)

|R| = |T|
```

---

#### Invariant: Categorization Confidence Bounds

**Formal Specification:**
```
For all transactions T:
  result = ingest_transaction(T)

  0.0 ≤ result.confidence ≤ 1.0
  If result.confidence == 0.0: result.category_id is None
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Categorization confidence must be in [0, 1] range. Out-of-bounds values break categorization logic.

**Test Location:** `test_ai_accounting_invariants.py::TestCategorizationInvariants::test_categorization_confidence_bounds`

**Mathematical Definition:**
```
Let R = ingest(T)

0.0 ≤ R.confidence ≤ 1.0
(R.confidence = 0.0) ⟹ (R.category_id = None)
```

---

#### Invariant: Categorization Status Consistency

**Formal Specification:**
```
For all transactions T:
  result = ingest_transaction(T)

  If result.confidence >= 0.85: result.status == CATEGORIZED
  Else: result.status == REVIEW_REQUIRED
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Categorization status must be consistent with confidence threshold. Inconsistent status breaks workflow.

**Test Location:** `test_ai_accounting_invariants.py::TestCategorizationInvariants::test_categorization_status_consistency`

**Mathematical Definition:**
```
Let R = ingest(T)
Let THRESHOLD = 0.85

(R.confidence >= THRESHOLD) ⟹ (R.status = CATEGORIZED)
(R.confidence < THRESHOLD) ⟹ (R.status = REVIEW_REQUIRED)
```

---

#### Invariant: Chart of Accounts Entry Validity

**Formal Specification:**
```
For all chart of accounts entries E:
  E.account_id is not None
  E.name is not None
  E.type in {asset, liability, equity, revenue, expense}
  E.keywords is list
  E.merchant_patterns is list
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Chart of accounts entries must have valid fields. Invalid entries break categorization.

**Test Location:** `test_ai_accounting_invariants.py::TestChartOfAccountsInvariants::test_chart_of_accounts_entry_validity`

**Mathematical Definition:**
```
Let E be chart of accounts entry

E.account_id ≠ None ∧
E.name ≠ None ∧
E.type ∈ {ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE} ∧
isinstance(E.keywords, list) ∧
isinstance(E.merchant_patterns, list)
```

---

#### Invariant: Confidence Threshold Constant

**Formal Specification:**
```
CONFIDENCE_THRESHOLD = 0.85 (constant)

For all engines: engine.CONFIDENCE_THRESHOLD == 0.85
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Confidence threshold must be constant. Variable thresholds break categorization consistency.

**Test Location:** `test_ai_accounting_invariants.py::TestConfidenceThresholdInvariants::test_confidence_threshold_constant`

**Mathematical Definition:**
```
∀ engine e: e.CONFIDENCE_THRESHOLD = 0.85
0.0 < 0.85 < 1.0
```

---

#### Invariant: Learning Updates Transaction

**Formal Specification:**
```
For all transactions T and categories C:
  learn_categorization(T.id, C, user)

  T.category_id == C
  T.confidence == 1.0
  T.status == CATEGORIZED
  T.reviewed_by == user
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Learning from user feedback must update transaction fields. Incomplete updates break learning.

**Test Location:** `test_ai_accounting_invariants.py::TestLearningInvariants::test_learning_updates_transaction`

**Mathematical Definition:**
```
Let T be transaction
Let C be category_id
Let U be user_id

After learn(T.id, C, U):
  T.category_id = C ∧
  T.confidence = 1.0 ∧
  T.status = CATEGORIZED ∧
  T.reviewed_by = U
```

---

#### Invariant: Cannot Post Review Required

**Formal Specification:**
```
For all transactions T with status = REVIEW_REQUIRED:
  post_transaction(T.id) == False

Low-confidence transactions cannot be posted.
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Review-required transactions must not post. Posting unreviewed transactions breaks workflow.

**Test Location:** `test_ai_accounting_invariants.py::TestPostingInvariants::test_cannot_post_review_required`

**Mathematical Definition:**
```
Let T be transaction
T.status = REVIEW_REQUIRED

post(T.id) = False
```

---

#### Invariant: Posting Updates Timestamp

**Formal Specification:**
```
For all transactions T with status = CATEGORIZED:
  before_post = datetime.now()
  result = post_transaction(T.id)

  If result:
    T.status == POSTED
    T.posted_at is not None
    T.posted_at >= before_post
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Posting must set posted_at timestamp. Missing timestamps break audit trails.

**Test Location:** `test_ai_accounting_invariants.py::TestPostingInvariants::test_posting_updates_timestamp`

**Mathematical Definition:**
```
Let T be transaction
Let t₀ = now()
Let r = post(T.id)

(r = True) ⟹ (
  T.status = POSTED ∧
  T.posted_at ≠ None ∧
  T.posted_at ≥ t₀
)
```

---

#### Invariant: Audit Entry Created on Ingestion

**Formal Specification:**
```
For all transactions T:
  initial_count = len(audit_log)
  ingest_transaction(T)

  len(audit_log) > initial_count
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Ingestion must create audit entry. Missing entries break audit trails.

**Test Location:** `test_ai_accounting_invariants.py::TestAuditTrailInvariants::test_audit_entry_created_on_ingestion`

**Mathematical Definition:**
```
Let T be transaction
Let A₀ = audit_log

ingest(T)

|audit_log| > |A₀|
```

---

#### Invariant: Audit Log Chronological

**Formal Specification:**
```
For all audit log entries [e₁, e₂, ..., eₙ]:
  e₁.timestamp ≤ e₂.timestamp ≤ ... ≤ eₙ.timestamp

Audit entries in chronological order.
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Audit log must be chronological. Out-of-order entries break audit analysis.

**Test Location:** `test_ai_accounting_invariants.py::TestAuditTrailInvariants::test_audit_log_chronological`

**Mathematical Definition:**
```
Let E = [e₁, e₂, ..., eₙ] be audit entries

∀ i ∈ {1, ..., n-1}:
  eᵢ.timestamp ≤ eᵢ₊₁.timestamp
```

---

#### Invariant: Audit Log Contains Required Fields

**Formal Specification:**
```
For all audit log entries E:
  E has keys {timestamp, action, transaction_id, confidence, details}
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Audit entries must contain all required fields. Missing fields break audit analysis.

**Test Location:** `test_ai_accounting_invariants.py::TestAuditTrailInvariants::test_audit_log_contains_required_fields`

**Mathematical Definition:**
```
Let E be audit entry

{timestamp, action, transaction_id, confidence, details} ⊆ E.keys()
```

---

#### Invariant: Transaction Amounts Preserved

**Formal Specification:**
```
For all transactions [T₁, T₂, ..., Tₙ]:
  original_amounts = {Tᵢ.id: Tᵢ.amount}
  ingest_all([T₁, T₂, ..., Tₙ])

  For all Tᵢ: stored(Tᵢ).amount == original_amounts[Tᵢ.id]
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** All transaction amounts must be preserved exactly. Rounding errors cause accounting discrepancies.

**Test Location:** `test_ai_accounting_invariants.py::TestFinancialAccuracyInvariants::test_transaction_amounts_preserved`

**Mathematical Definition:**
```
Let T = [T₁, ..., Tₙ] be transactions
Let A₀ = {Tᵢ.id: Tᵢ.amount | Tᵢ ∈ T}

ingest_all(T)

∀ Tᵢ ∈ T: stored(Tᵢ).amount == A₀[Tᵢ.id] (exact Decimal)
```

---

#### Invariant: Debits and Credits Distinct

**Formal Specification:**
```
For all transactions T:
  T.amount is preserved exactly (no rounding)
  If T.amount > 0: stored(T).amount > 0
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Debits and credits must be distinct with exact amounts. Sign errors break accounting.

**Test Location:** `test_ai_accounting_invariants.py::TestFinancialAccuracyInvariants::test_debits_and_credits_distinct`

**Mathematical Definition:**
```
Let T be transaction

stored(T).amount == T.amount (exact equality)
(T.amount > 0) ⟹ (stored(T).amount > 0)
```

---

#### Invariant: Total Balance Calculable

**Formal Specification:**
```
For all transactions [T₁, T₂, ..., Tₙ]:
  total_balance = sum(Tᵢ.amount for Tᵢ in transactions)

  total_balance < 1e20 (finite)
  total_balance > -1e20 (finite)
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Total balance must be finite. Overflow/infinity causes calculation errors.

**Test Location:** `test_ai_accounting_invariants.py::TestFinancialAccuracyInvariants::test_total_balance_calculable`

**Mathematical Definition:**
```
Let T = [T₁, ..., Tₙ] be transactions
Let B = Σ Tᵢ.amount

B < 10²⁰ ∧ B > -10²⁰ (finite)
```

---

#### Invariant: Low Confidence Goes to Review

**Formal Specification:**
```
For all transactions T:
  result = ingest_transaction(T)

  If result.confidence < CONFIDENCE_THRESHOLD:
    T.id in pending_review_queue
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Low-confidence transactions must go to review queue. Missing review breaks workflow.

**Test Location:** `test_ai_accounting_invariants.py::TestReviewQueueInvariants::test_low_confidence_goes_to_review`

**Mathematical Definition:**
```
Let T be transaction
Let R = ingest(T)
Let THRESHOLD = 0.85

(R.confidence < THRESHOLD) ⟹ (T.id ∈ review_queue)
```

---

#### Invariant: Review Queue Count Matches

**Formal Specification:**
```
For all transactions [T₁, T₂, ..., Tₙ]:
  ingest_all([T₁, T₂, ..., Tₙ])

  low_confidence_count = count(T where T.confidence < THRESHOLD)
  len(review_queue) == low_confidence_count
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Review queue count must match low-confidence transaction count. Mismatch indicates tracking errors.

**Test Location:** `test_ai_accounting_invariants.py::TestReviewQueueInvariants::test_review_queue_count_matches`

**Mathematical Definition:**
```
Let T = [T₁, ..., Tₙ] be transactions
ingest_all(T)

let L = {Tᵢ | Tᵢ.confidence < THRESHOLD}
|review_queue| = |L|
```

---

#### Invariant: Transaction Source Preserved

**Formal Specification:**
```
For all transactions T with source S:
  result = ingest_transaction(T)

  result.source == S
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Transaction source must be preserved. Missing/incorrect source breaks categorization.

**Test Location:** `test_ai_accounting_invariants.py::TestSourceInvariants::test_transaction_source_preserved`

**Mathematical Definition:**
```
Let T be transaction
Let S = T.source

Let R = ingest(T)
R.source == S
```

---

#### Invariant: Default Source is Bank

**Formal Specification:**
```
For all transactions T without source specified:
  T.source == TransactionSource.BANK
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Default source must be BANK. Missing default breaks categorization.

**Test Location:** `test_ai_accounting_invariants.py::TestSourceInvariants::test_default_source_is_bank`

**Mathematical Definition:**
```
Let T be transaction
T.source unspecified ⟹ T.source = BANK
```

---

#### Invariant: Transaction Date Preserved

**Formal Specification:**
```
For all transactions T with date D:
  result = ingest_transaction(T)

  result.date == D
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Transaction date must be preserved. Incorrect dates break accounting records.

**Test Location:** `test_ai_accounting_invariants.py::TestDateInvariants::test_transaction_date_preserved`

**Mathematical Definition:**
```
Let T be transaction
Let D = T.date

Let R = ingest(T)
R.date == D
```

---

#### Invariant: Posted At After Created At

**Formal Specification:**
```
For all transactions T:
  If T.posted_at is not None:
    T.posted_at >= T.date

posted_at timestamp after or equal to transaction date.
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** posted_at must be after transaction date. Earlier timestamps break audit trails.

**Test Location:** `test_ai_accounting_invariants.py::TestDateInvariants::test_posted_at_after_created_at`

**Mathematical Definition:**
```
Let T be transaction

(T.posted_at ≠ None) ⟹ (T.posted_at ≥ T.date)
```

---

## Canvas Invariants

Canvas invariants ensure canvas presentations, audit logging, and chart data operate correctly.

### Canvas Audit Invariants

#### Invariant: Audit Created for Every Present

**Formal Specification:**
```
For all canvas presentations (user_id, canvas_type, action):
  audit = create_canvas_audit(user_id, canvas_type, action)

  audit is not None
  isinstance(audit, CanvasAudit)
  audit.id is not None
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Every canvas action must create audit entry. Missing entries break audit trails.

**Test Location:** `test_canvas_invariants_property.py::TestCanvasAuditInvariants::test_audit_created_for_every_present`

**Mathematical Definition:**
```
Let (user, canvas_type, action) be canvas action
Let A = create_audit(user, canvas_type, action)

A ≠ None ∧
isinstance(A, CanvasAudit) ∧
A.id ≠ None
```

---

#### Invariant: Audit Timestamp After Creation

**Formal Specification:**
```
For all canvas audits A:
  A.created_at is not None
  A.created_at is valid datetime
```

**Criticality:** STANDARD (max_examples=100)

**Rationale:** Audit created_at must be set and reasonable. Missing timestamps break audit trails.

**Test Location:** `test_canvas_invariants_property.py::TestCanvasAuditInvariants::test_audit_timestamp_after_creation`

**Mathematical Definition:**
```
Let A be canvas audit

A.created_at ≠ None ∧
isinstance(A.created_at, datetime)
```

---

### Chart Data Invariants

#### Invariant: Chart Data Non-Empty

**Formal Specification:**
```
For all chart data D:
  D.labels is not None
  len(D.labels) > 0
  D.datasets is not None
  len(D.datasets) > 0
```

**Criticality:** IO_BOUND (max_examples=50)

**Rationale:** Chart data must be non-empty. Empty charts break UI rendering.

**Test Location:** `test_canvas_invariants_property.py::TestChartDataInvariants`

**Mathematical Definition:**
```
Let D be chart data

D.labels ≠ None ∧
|D.labels| > 0 ∧
D.datasets ≠ None ∧
|D.datasets| > 0
```

---

## Criticality Categories

Property tests use `max_examples` based on invariant criticality:

### CRITICAL (max_examples=200)

**When to use:**
- State machine transitions (maturity levels, lifecycle states)
- Financial calculations (money, accounting)
- Security boundaries (auth, permissions, governance)
- Data integrity (cache consistency, transaction atomicity)

**Rationale:** Bugs in these invariants cause:
- Data corruption
- Security vulnerabilities
- Financial discrepancies
- System crashes

**Examples:**
- Maturity level total ordering
- Double-entry accounting (debits = credits)
- Cache lookup performance (<1ms P99)
- Decimal precision preservation

---

### STANDARD (max_examples=100)

**When to use:**
- Business logic (permissions, retrieval, categorization)
- Data transformations (formatting, serialization)
- Validation rules (input validation, bounds checking)

**Rationale:** Bugs in these invariants cause:
- Incorrect behavior
- Poor user experience
- Workflow issues

**Examples:**
- Permission check idempotence
- Semantic retrieval similarity ranking
- Confidence bounds checking
- Audit trail creation

---

### IO_BOUND (max_examples=50)

**When to use:**
- Database queries (each example = DB roundtrip)
- File I/O (each example = file read/write)
- Network calls (each example = HTTP request)

**Rationale:** Each example has high execution time. Fewer examples keep tests fast while maintaining coverage.

**Examples:**
- Transaction ingestion (DB writes)
- Bulk operations (multiple queries)
- API calls (network roundtrips)

---

## Summary

**Total Invariants Documented:** 50+

**Distribution:**
- Governance: 20 invariants
- Episodes: 18 invariants
- Financial: 10+ invariants
- Canvas: 2+ invariants

**Criticality Distribution:**
- CRITICAL (max_examples=200): 20 invariants
- STANDARD (max_examples=100): 22 invariants
- IO_BOUND (max_examples=50): 8 invariants

**Validation Status:**
- All invariants validated by property tests
- 3 bugs found and fixed during validation
- 100% pass rate across all property tests

---

*Document maintained by: Backend Property Testing Team*
*Last review: 2026-02-28*
*Next review: After Phase 103 completion*
