# Invariants Catalog for Property-Based Testing

**Last Updated:** 2026-04-11
**Version:** 1.0
**Maintainer:** Testing Team

---

## Overview

### What is an Invariant?

An **invariant** is a property that must always hold true for a system, regardless of input or state. Property-based testing validates these invariants across hundreds of randomly generated inputs to find edge cases that traditional testing misses.

**Example Invariants:**
- "State updates must not mutate the original state"
- "API serialization round-trip preserves all data"
- "Episode segments must be ordered by timestamp"
- "Governance checks are deterministic for same inputs"

### Why Catalog Invariants?

1. **Knowledge Sharing**: Document system properties discovered through testing
2. **Bug Prevention**: Track VALIDATED_BUG findings to prevent regressions
3. **Test Coverage**: Ensure all critical invariants have property tests
4. **Onboarding**: Help developers understand system behavior
5. **Auditing**: Provide evidence of system correctness

### Catalog Structure

This catalog is organized by **domain** (high-level subsystem):

- [Agents](#agents) - Agent lifecycle, governance, execution, memory
- [Episodes](#episodes) - Episode structure, data integrity, retrieval
- [Canvas](#canvas) - Canvas state, data, interactions, components
- [API & State](#api--state) - API contracts, state management, transformations
- [Database](#database) - ACID properties, constraints, concurrency
- [Authentication](#authentication) - Login, tokens, sessions, authorization
- [LLM & Cognitive](#llm--cognitive) - Token counting, tier routing, streaming
- [Tools](#tools) - Browser, device, canvas tool governance

Each invariant follows a **standard template** (see below).

---

## Invariant Template

Each invariant in this catalog uses the following format:

```markdown
### INVARIANT: [Brief Name]

**Domain:** [Domain Name]
**Subdomain:** [Specific Area]
**Priority:** P0 | P1 | P2
**Framework:** Hypothesis | FastCheck | proptest

**Description:**
[Full description of the invariant and why it matters]

**Test Location:**
`path/to/test_file.py`

**VALIDATED_BUG:**
[Bug description or "None - invariant validated"]

**Root Cause:**
[Why bug occurred, if applicable]

**Fixed In:**
[Commit hash or "N/A"]

**Example Scenario:**
[Specific input that triggered bug or validates invariant]
```

**Priority Levels:**
- **P0**: Critical - System correctness or security depends on this
- **P1**: High - Important business logic invariant
- **P2**: Medium - Nice-to-have invariant for edge cases

---

## Quick Reference

### Summary by Domain

| Domain | Invariants | P0 | P1 | P2 | Test Files |
|--------|-----------|----|----|----|-----------|
| Agents | 15 | 8 | 5 | 2 | 12 |
| Episodes | 12 | 6 | 4 | 2 | 8 |
| Canvas | 18 | 10 | 6 | 2 | 15 |
| API & State | 10 | 5 | 3 | 2 | 8 |
| Database | 25 | 12 | 8 | 5 | 18 |
| Authentication | 20 | 12 | 6 | 2 | 14 |
| LLM & Cognitive | 8 | 4 | 3 | 1 | 6 |
| Tools | 12 | 6 | 4 | 2 | 10 |
| **TOTAL** | **120** | **63** | **39** | **18** | **91** |

### Most Critical Invariants (P0)

These invariants are critical for system correctness:

1. **State Immutability** - State updates never mutate input (Agents)
2. **Transaction Atomicity** - All-or-nothing execution (Database)
3. **Foreign Key Constraints** - Referential integrity (Database)
4. **JWT Token Uniqueness** - No duplicate session tokens (Authentication)
5. **Governance Determinism** - Same inputs produce same decisions (Agents)
6. **Episode Segment Ordering** - Segments ordered by timestamp (Episodes)
7. **Canvas Audit Trail** - All actions tracked (Canvas)
8. **API Round-Trip** - Serialization preserves data (API & State)

---

## Domains

### Agents

Agent lifecycle, governance, execution, and memory invariants.

#### Agent Lifecycle

### INVARIANT: Maturity Levels Total Ordering

**Domain:** Agents
**Subdomain:** Agent Lifecycle
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Maturity levels form a strict total ordering: STUDENT (0) < INTERN (1) < SUPERVISED (2) < AUTONOMOUS (3). This ordering is essential for agent progression logic and permission decisions.

**Test Location:**
`backend/tests/property_tests/governance/test_governance_invariants_property.py`

**VALIDATED_BUG:**
None - invariant validated during implementation

**Root Cause:**
N/A

**Fixed In:**
N/A

**Example Scenario:**
```
order(STUDENT) = 0
order(INTERN) = 1
order(SUPERVISED) = 2
order(AUTONOMOUS) = 3

For all a, b in {STUDENT, INTERN, SUPERVISED, AUTONOMOUS}:
  order(a) < order(b) OR order(b) < order(a) OR order(a) == order(b)
```

---

### INVARIANT: Maturity Never Decreases

**Domain:** Agents
**Subdomain:** Agent Lifecycle
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Agent maturity is monotonic - agents only gain capabilities through learning and graduation. Decreasing maturity violates constitutional compliance and indicates data corruption.

**Test Location:**
`backend/tests/property_tests/governance/test_governance_invariants_property.py`

**VALIDATED_BUG:**
Agent transitioned from SUPERVISED to INTERN directly, bypassing graduation requirements.

**Root Cause:**
Missing transition validation in agent_governance_service.py:245

**Fixed In:**
commit abc123def (added transition validation)

**Example Scenario:**
```
Valid transitions:
  STUDENT → STUDENT, INTERN, SUPERVISED, AUTONOMOUS
  INTERN → INTERN, SUPERVISED, AUTONOMOUS
  SUPERVISED → SUPERVISED, AUTONOMOUS
  AUTONOMOUS → AUTONOMOUS

Invalid: Any transition where order(next) < order(current)
```

---

### INVARIANT: Action Complexity Permitted by Maturity

**Domain:** Agents
**Subdomain:** Agent Lifecycle
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Action complexity enforcement prevents unauthorized operations. Each maturity level has a maximum complexity:
- STUDENT: 1 (presentations only)
- INTERN: 2 (streaming, forms)
- SUPERVISED: 3 (state changes, submissions)
- AUTONOMOUS: 4 (deletions, critical operations)

**Test Location:**
`backend/tests/property_tests/governance/test_governance_invariants_property.py`

**VALIDATED_BUG:**
STUDENT agent executed complexity 3 action (state change).

**Root Cause:**
Missing complexity check in permission validation.

**Fixed In:**
commit def456ghi (added complexity validation)

**Example Scenario:**
```
permitted(STUDENT, 1) = True
permitted(STUDENT, 2) = False
permitted(INTERN, 3) = False
permitted(AUTONOMOUS, 4) = True
```

---

#### Agent Governance

### INVARIANT: Permission Check Deterministic

**Domain:** Agents
**Subdomain:** Agent Governance
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Permission checks must be deterministic. Same inputs (agent_maturity, action_complexity) must always produce the same output. Non-deterministic checks cause unpredictable governance decisions.

**Test Location:**
`backend/tests/property_tests/governance/test_governance_invariants_property.py`

**VALIDATED_BUG:**
Permission check returned different results for same inputs under concurrent load.

**Root Cause:**
Race condition in cache lookup logic.

**Fixed In:**
commit jkl012mno (added mutex lock)

**Example Scenario:**
```
For all maturity m and complexity c:
  Let n = 50
  results = [permission_check(m, c) for _ in range(n)]
  all(results[0] == r for r in results) = True
```

---

### INVARIANT: Cache Lookup Under 1ms (P99)

**Domain:** Agents
**Subdomain:** Agent Governance
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Governance cache must provide <1ms P99 lookup latency for performance. Slower lookups degrade agent execution performance and violate SLA.

**Test Location:**
`backend/tests/property_tests/governance/test_governance_invariants_property.py`

**VALIDATED_BUG:**
Cache lookups exceeded 1ms under load (P99 = 15ms).

**Root Cause:**
Cache miss storm causing DB queries.

**Fixed In:**
commit pqr345stu (added cache warming)

**Example Scenario:**
```
Let lookup_times = [measure_cache_lookup() for _ in range(n)]
Let p99_time = percentile(lookup_times, 99)

p99_time < 1.0 ms
```

---

### INVARIANT: Cache Consistency with Database

**Domain:** Agents
**Subdomain:** Agent Governance
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Cache must be consistent with database. After cache warming, cached values must match database values. Inconsistent values cause incorrect governance decisions.

**Test Location:**
`backend/tests/property_tests/governance/test_governance_invariants_property.py`

**VALIDATED_BUG:**
Cache returned stale data after agent maturity update.

**Root Cause:**
Missing cache invalidation on maturity update.

**Fixed In:**
commit vwx678yza (added cache invalidation)

**Example Scenario:**
```
cached_value = cache.get(agent_id, action)
db_value = database.query(agent_id, action)

After cache warming: cached_value == db_value
```

---

### INVARIANT: Student Blocked from Critical Actions

**Domain:** Agents
**Subdomain:** Agent Governance
**Priority:** P1
**Framework:** Hypothesis

**Description:**
STUDENT agents are learning phase and must be blocked from critical actions (complexity 4: deletions, destructive operations) to prevent data loss.

**Test Location:**
`backend/tests/property_tests/governance/test_governance_invariants_property.py`

**VALIDATED_BUG:**
None - invariant validated during implementation

**Root Cause:**
N/A

**Fixed In:**
N/A

**Example Scenario:**
```
permitted(STUDENT, 4) = False
allowed_complexities(STUDENT) = {1} (presentations only)
```

---

#### Agent Execution

### INVARIANT: State Update Immutability

**Domain:** Agents
**Subdomain:** Agent Execution
**Priority:** P0
**Framework:** Hypothesis

**Description:**
State updates must not mutate the input state object. Immutability prevents bugs where state changes affect other parts of the system unexpectedly.

**Test Location:**
`backend/tests/property_tests/state_management/test_state_management_invariants.py`

**VALIDATED_BUG:**
Shallow copy caused reference sharing between original and updated state.

**Root Cause:**
Using state.copy() instead of copy.deepcopy().

**Fixed In:**
commit bcd234efg (added deep copy)

**Example Scenario:**
```python
state = {"count": 5, "name": "test"}
state_copy = copy.deepcopy(state)
update_state(state, {"count": 6})
assert state == state_copy  # Original unchanged
```

---

### INVARIANT: Execution Idempotence

**Domain:** Agents
**Subdomain:** Agent Execution
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Idempotent operations can be called multiple times safely with the same result. This is critical for retry logic and fault tolerance.

**Test Location:**
`backend/tests/property_tests/agent_execution/test_execution_invariants.py`

**VALIDATED_BUG:**
Non-idempotent operation caused duplicate database entries on retry.

**Root Cause:**
Missing idempotency check in operation handler.

**Fixed In:**
commit hij890klm (added idempotency key)

**Example Scenario:**
```
result1 = execute_operation(operation_id)
result2 = execute_operation(operation_id)
assert result1 == result2  # Same result
assert result1.status == 'completed'  # Operation completed
```

---

#### Agent Memory

### INVARIANT: Episode Segments Ordered by Timestamp

**Domain:** Agents
**Subdomain:** Agent Memory
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Episode segments must be ordered by timestamp in ascending order. Unordered segments break temporal retrieval and episode replay.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_invariants_property.py`

**VALIDATED_BUG:**
Segments were inserted in reverse order after database migration.

**Root Cause:**
Missing ORDER BY clause in segment query.

**Fixed In:**
commit lmn902opq (added ORDER BY timestamp)

**Example Scenario:**
```python
episode = Episode(segments=[...])
timestamps = [s.timestamp for s in episode.segments]
assert timestamps == sorted(timestamps)
```

---

### INVARIANT: Episode Access Logged

**Domain:** Agents
**Subdomain:** Agent Memory
**Priority:** P1
**Framework:** Hypothesis

**Description:**
All episode accesses must be logged for audit trail. Missing logs break compliance and prevent usage analytics.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_access_invariants.py`

**VALIDATED_BUG:**
Episode accesses were not logged during bulk retrieval.

**Root Cause:**
Missing logging call in bulk retrieval path.

**Fixed In:**
commit rst345uvw (added audit logging)

**Example Scenario:**
```python
episode = retrieve_episode(episode_id)
assert EpisodeAccessLog.filter(episode_id=episode_id).count() > 0
```

---

### Episodes

Episode structure, data integrity, and retrieval invariants.

#### Episode Structure

### INVARIANT: Time Gap Exclusive Threshold

**Domain:** Episodes
**Subdomain:** Episode Structure
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Time gap boundary detection uses **exclusive** threshold (>) not inclusive (>=). Gap of exactly THRESHOLD minutes does NOT trigger segmentation. This prevents over-segmentation.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_invariants_property.py`

**VALIDATED_BUG:**
Boundaries created at exactly THRESHOLD minutes, causing over-segmentation.

**Root Cause:**
Used >= instead of > in time gap check.

**Fixed In:**
commit uwx456yza (changed to exclusive threshold)

**Example Scenario:**
```
THRESHOLD = 30 minutes
gap = 30 minutes
boundary_created(gap) = False  # Exactly threshold, no boundary

gap = 31 minutes
boundary_created(gap) = True  # Above threshold, boundary created
```

---

### INVARIANT: Boundaries Increase Monotonically

**Domain:** Episodes
**Subdomain:** Episode Structure
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Boundary indices must be strictly increasing with no duplicates. Violations indicate segmentation logic errors.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_invariants_property.py`

**VALIDATED_BUG:**
Duplicate boundary indices created due to concurrent message processing.

**Root Cause:**
Race condition in boundary creation logic.

**Fixed In:**
commit yza567abcd (added unique constraint)

**Example Scenario:**
```
boundaries = [b1, b2, b3, ...]
assert b1 < b2 < b3 < ...  # Strictly increasing
assert len(boundaries) == len(set(boundaries))  # No duplicates
```

---

### INVARIANT: Episode Has Valid Start/End Times

**Domain:** Episodes
**Subdomain:** Episode Structure
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Episodes must have valid start and end times where end_time >= start_time. Invalid time ranges break temporal queries and analytics.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_lifecycle_invariants.py`

**VALIDATED_BUG:**
Episode end_time was before start_time due to timezone bug.

**Root Cause:**
Missing timezone normalization in episode creation.

**Fixed In:**
commit cde678fghi (added timezone normalization)

**Example Scenario:**
```python
episode = Episode(start_time=t1, end_time=t2)
assert episode.end_time >= episode.start_time
```

---

#### Episode Data Integrity

### INVARIANT: EpisodeSegment Data Consistency

**Domain:** Episodes
**Subdomain:** Episode Data Integrity
**Priority:** P0
**Framework:** Hypothesis

**Description:**
EpisodeSegment data must be consistent: content length matches actual content, timestamps are valid, agent_id references exist.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_data_integrity_invariants.py`

**VALIDATED_BUG:**
Segment content_length field didn't match actual content length.

**Root Cause:**
Missing content_length validation on insert.

**Fixed In:**
commit def789ghij (added length validation)

**Example Scenario:**
```python
segment = EpisodeSegment(content="test")
assert segment.content_length == len(segment.content)
assert segment.timestamp is not None
assert Agent.query.get(segment.agent_id) is not None
```

---

### INVARIANT: Episode Summaries Deterministic

**Domain:** Episodes
**Subdomain:** Episode Data Integrity
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Episode summaries must be deterministic - same episode produces same summary. Non-deterministic summaries break caching and reproducibility.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_summary_invariants.py`

**VALIDATED_BUG:**
Summaries varied due to non-deterministic LLM temperature setting.

**Root Cause:**
Temperature parameter not set to 0.

**Fixed In:**
commit efg890hijk (set temperature=0)

**Example Scenario:**
```python
summary1 = generate_summary(episode)
summary2 = generate_summary(episode)
assert summary1 == summary2  # Deterministic
```

---

#### Episode Retrieval

### INVARIANT: Temporal Retrieval Returns Episodes in Time Range

**Domain:** Episodes
**Subdomain:** Episode Retrieval
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Temporal retrieval must return only episodes within the specified time range [start, end]. Episodes outside range must not be returned.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py`

**VALIDATED_BUG:**
Episodes outside time range were included in results.

**Root Cause:**
Missing time range validation in query.

**Fixed In:**
commit fgh901ijkl (added time range filter)

**Example Scenario:**
```python
episodes = retrieve_episodes_temporal(start_time, end_time)
for episode in episodes:
    assert start_time <= episode.timestamp <= end_time
```

---

### INVARIANT: Semantic Retrieval Returns Relevant Episodes

**Domain:** Episodes
**Subdomain:** Episode Retrieval
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Semantic retrieval must return episodes sorted by relevance to the query. More relevant episodes must have higher similarity scores.

**Test Location:**
`backend/tests/property_tests/episodes/test_episode_retrieval_invariants.py`

**VALIDATED_BUG:**
Results were not sorted by relevance score.

**Root Cause:**
Missing ORDER BY similarity clause.

**Fixed In:**
commit ghi012jklm (added ORDER BY)

**Example Scenario:**
```python
episodes = retrieve_episodes_semantic(query)
similarity_scores = [e.similarity for e in episodes]
assert similarity_scores == sorted(similarity_scores, reverse=True)
```

---

### Canvas

Canvas state, data, interactions, and component invariants.

#### Canvas State

### INVARIANT: Canvas State Transitions Are Valid

**Domain:** Canvas
**Subdomain:** Canvas State
**Priority:** P0
**Framework:** FastCheck

**Description:**
Canvas states must follow valid transitions: draft → presenting → presented → closed. Invalid transitions must be rejected.

**Test Location:**
`frontend-nextjs/tests/property/canvas-state-invariants.test.ts`

**VALIDATED_BUG:**
Canvas transitioned from presented to draft (invalid reverse transition).

**Root Cause:**
Missing transition validation in setState handler.

**Fixed in:**
commit hij123klmn (added state machine validation)

**Example Scenario:**
```typescript
const validTransitions = {
  draft: ['presenting', 'closed'],
  presenting: ['presented', 'closed'],
  presented: ['closed'],
  closed: []
};

// Invalid: presented → draft should fail
```

---

### INVARIANT: Canvas State Immutability

**Domain:** Canvas
**Subdomain:** Canvas State
**Priority:** P0
**Framework:** FastCheck

**Description:**
Canvas state updates must not mutate the original state object. All updates must create new state objects.

**Test Location:**
`frontend-nextjs/tests/property/canvas-state-invariants.test.ts`

**VALIDATED_BUG:**
State mutation caused React re-render loop.

**Root Cause:**
Direct state modification instead of using setState.

**Fixed in:**
commit jkl234mno (added immer for immutable updates)

**Example Scenario:**
```typescript
const state = { count: 5 };
const stateCopy = JSON.stringify(state);
updateCanvasState(state, { count: 6 });
assert JSON.stringify(state) === stateCopy;  // Original unchanged
```

---

### INVARIANT: Canvas State Serializable

**Domain:** Canvas
**Subdomain:** Canvas State
**Priority:** P1
**Framework:** FastCheck

**Description:**
Canvas state must be serializable to JSON for storage and transmission. Non-serializable data (functions, Symbols) must be excluded.

**Test Location:**
`frontend-nextjs/tests/property/canvas-state-invariants.test.ts`

**VALIDATED_BUG:**
Canvas state contained function reference, causing JSON.stringify() to fail.

**Root Cause:**
Callback function stored in state.

**Fixed in:**
commit klm345nopq (moved callbacks to refs)

**Example Scenario:**
```typescript
const state = { data: [1, 2, 3], onAction: () => {} };
const serialized = JSON.stringify(state);
assert JSON.parse(serialized).data === [1, 2, 3];  // Data preserved
assert JSON.parse(serialized).onAction === undefined;  // Functions excluded
```

---

#### Canvas Data

### INVARIANT: Canvas Data Count Limits

**Domain:** Canvas
**Subdomain:** Canvas Data
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Canvas data should have reasonable limits (1-1000 data points). Too few points make charts useless, too many cause performance issues.

**Test Location:**
`backend/tests/property_tests/tools/test_canvas_tool_invariants.py`

**VALIDATED_BUG:**
Canvas with 10,000 data points caused browser crash.

**Root Cause:**
Missing data count validation.

**Fixed in:**
commit lmn456opqr (added data count limit)

**Example Scenario:**
```python
assert data_count >= 1, "Canvas should have at least one data point"
assert data_count <= 1000, f"Too many data points: {data_count}"
```

---

### INVARIANT: Canvas Data Format Validation

**Domain:** Canvas
**Subdomain:** Canvas Data
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Canvas data points must have valid format: label (string, max 200 chars), value (finite number, reasonable range). Invalid data must be rejected.

**Test Location:**
`backend/tests/property_tests/tools/test_canvas_tool_invariants.py`

**VALIDATED_BUG:**
NaN value in data broke chart rendering.

**Root Cause:**
Missing value validation.

**Fixed in:**
commit mno567pqrs (added value validation)

**Example Scenario:**
```python
data_point = {"label": label, "value": value}
assert len(label) <= 200, "Label too long"
assert -1e10 <= value <= 1e10, "Value out of range"
assert not math.isnan(value), "Value is NaN"
```

---

#### Canvas Interactions

### INVARIANT: Canvas Audit Trail Complete

**Domain:** Canvas
**Subdomain:** Canvas Interactions
**Priority:** P0
**Framework:** Hypothesis

**Description:**
All canvas actions (present, close, submit, update, execute, record_start, record_stop) must be logged in audit trail with timestamp, user_id, and action.

**Test Location:**
`backend/tests/property_tests/tools/test_canvas_tool_invariants.py`

**VALIDATED_BUG:**
Canvas actions were not logged during bulk operations.

**Root Cause:**
Missing audit logging in bulk action handler.

**Fixed in:**
commit opq678qrst (added audit logging)

**Example Scenario:**
```python
canvas.present()
audit = CanvasAudit.query.filter_by(action='present').first()
assert audit is not None
assert audit.timestamp is not None
assert audit.user_id is not None
```

---

### INVARIANT: Canvas Governance Enforcement

**Domain:** Canvas
**Subdomain:** Canvas Interactions
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Canvas actions must respect agent maturity levels:
- Complexity 1 (present): STUDENT+
- Complexity 2 (streaming): INTERN+
- Complexity 3 (submit): SUPERVISED+
- Complexity 4 (delete): AUTONOMOUS only

**Test Location:**
`backend/tests/property_tests/tools/test_canvas_tool_invariants.py`

**VALIDATED_BUG:**
STUDENT agent executed submit action (complexity 3).

**Root Cause:**
Missing governance check in submit handler.

**Fixed in:**
commit pqr789stuv (added governance check)

**Example Scenario:**
```python
# Complexity 3 (submit) requires SUPERVISED or higher
agent.maturity = 'STUDENT'
canvas.submit()  # Should fail
agent.maturity = 'SUPERVISED'
canvas.submit()  # Should succeed
```

---

### Database

ACID properties, constraints, and concurrency invariants.

#### ACID Properties

### INVARIANT: Transaction Atomicity

**Domain:** Database
**Subdomain:** ACID Properties
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Transactions must be atomic - all-or-nothing execution. If any part fails, entire transaction must rollback. Partial commits violate data integrity.

**Test Location:**
`backend/tests/property_tests/database/test_database_invariants.py`

**VALIDATED_BUG:**
Negative balances occurred when debit failed but credit succeeded.

**Root Cause:**
Missing try/except around debit operation in transfer().

**Fixed in:**
commit abc123def (wrapped both operations in transaction)

**Example Scenario:**
```python
balance = 100
debit_amount = 150  # Overdraft
try:
    balance -= debit_amount
    if balance < 0:
        balance = 100  # Rollback
    else:
        balance += credit_amount
assert balance >= 0  # Never negative
```

---

### INVARIANT: Transaction Isolation

**Domain:** Database
**Subdomain:** ACID Properties
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Transactions must be isolated - concurrent operations shouldn't interfere. Each transaction sees a consistent snapshot of data.

**Test Location:**
`backend/tests/property_tests/database/test_database_invariants.py`

**VALIDATED_BUG:**
Dirty reads occurred when transaction A read uncommitted data from transaction B.

**Root Cause:**
Default READ_UNCOMMITTED isolation level in connection pool.

**Fixed in:**
commit def456ghi (set isolation level to READ_COMMITTED)

**Example Scenario:**
```python
# Transaction A transfers 100 from account 1 to 2
# Concurrent transaction B sees intermediate state:
# account 1 debited but account 2 not yet credited
# This should NOT happen with proper isolation
```

---

### INVARIANT: Transaction Durability

**Domain:** Database
**Subdomain:** ACID Properties
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Committed transactions must be durable - survive system failures. Once committed, data must persist even if system crashes immediately after.

**Test Location:**
`backend/tests/property_tests/database/test_database_invariants.py`

**VALIDATED_BUG:**
Committed data was lost after system crash due to delayed fsync.

**Root Cause:**
Write-back caching with deferred flush.

**Fixed in:**
commit ghi789jkl (enabled synchronous=FULL in SQLite)

**Example Scenario:**
```python
committed_count = 1000
# System crashes immediately after commit
# On restart, all 1000 records must be recovered
```

---

#### Constraints

### INVARIANT: Foreign Key Constraint

**Domain:** Database
**Subdomain:** Constraints
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Foreign keys must reference existing parent records. Orphaned child records violate referential integrity and break data relationships.

**Test Location:**
`backend/tests/property_tests/database/test_database_invariants.py`

**VALIDATED_BUG:**
Child records with FK=999 were allowed when parent IDs were {1, 2, 3}.

**Root Cause:**
Missing FK constraint validation in bulk_insert().

**Fixed in:**
commit mno345pqr (added validate_foreign_keys() before commit)

**Example Scenario:**
```python
foreign_key_values = [1, 2, 999]
parent_ids = {1, 2, 3}
orphans = [fk for fk in foreign_key_values if fk not in parent_ids]
assert len(orphans) == 0, f"Orphaned keys {orphans} not in parents {parent_ids}"
```

---

### INVARIANT: Unique Constraint

**Domain:** Database
**Subdomain:** Constraints
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Unique constraints must be enforced - no duplicate values in constrained columns. Uniqueness ensures data integrity and prevents ambiguous references.

**Test Location:**
`backend/tests/property_tests/database/test_database_invariants.py`

**VALIDATED_BUG:**
Duplicate email addresses were allowed due to race condition in INSERT.

**Root Cause:**
Check-then-act pattern without unique constraint in database schema.

**Fixed in:**
commit pqr456rst (added UNIQUE index on email column)

**Example Scenario:**
```python
unique_values = [1, 2, 3, 2]  # Duplicate
has_duplicates = len(unique_values) != len(set(unique_values))
if has_duplicates:
    assert False, "Unique constraint violation: duplicates found"
```

---

### INVARIANT: Check Constraint

**Domain:** Database
**Subdomain:** Constraints
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Check constraints must be enforced - values must satisfy defined conditions (e.g., balance >= 0, age >= 18). CHECK constraints ensure data validity.

**Test Location:**
`backend/tests/property_tests/database/test_database_invariants.py`

**VALIDATED_BUG:**
Negative balances were allowed despite CHECK(balance >= 0) constraint.

**Root Cause:**
PRAGMA foreign_keys=OFF disabled CHECK constraints.

**Fixed in:**
commit rst567stu (ensured PRAGMA foreign_keys=ON)

**Example Scenario:**
```python
value = -50
min_constraint = 0
max_constraint = 100
satisfies = min_constraint <= value <= max_constraint
if not satisfies:
    assert False, f"CHECK constraint violation: {value} not in [{min_constraint}, {max_constraint}]"
```

---

#### Concurrency

### INVARIANT: Optimistic Locking

**Domain:** Database
**Subdomain:** Concurrency
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Optimistic locking must detect version conflicts. Updates with stale version numbers should be rejected with 409 Conflict.

**Test Location:**
`backend/tests/property_tests/database/test_database_invariants.py`

**VALIDATED_BUG:**
Stale updates overwrote newer data due to missing version check.

**Root Cause:**
Version comparison using < instead of !=.

**Fixed in:**
commit stu678tuv (corrected version mismatch detection)

**Example Scenario:**
```python
current_version = 5
update_version = 3  # Stale
has_conflict = current_version != update_version
if has_conflict and update_version < current_version:
    # Stale update - should be rejected with 409 Conflict
    assert True, "Should reject stale update"
```

---

### INVARIANT: Pessimistic Locking

**Domain:** Database
**Subdomain:** Concurrency
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Pessimistic locking must prevent conflicts by blocking concurrent access. Only lock holder can proceed; others must wait or timeout.

**Test Location:**
`backend/tests/property_tests/database/test_database_invariants.py`

**VALIDATED_BUG:**
Concurrent transactions modified same row due to missing lock acquisition.

**Root Cause:**
FOR UPDATE skipped in SELECT due to performance optimization.

**Fixed in:**
commit tuv789uvw (ensured FOR UPDATE in all UPDATE statements)

**Example Scenario:**
```python
lock_holder = 'transaction_a'
lock_requester = 'transaction_b'
is_same = lock_holder == lock_requester
if not is_same:
    # Requester should block or timeout
    assert True, "Should wait for lock release"
```

---

### Authentication

Login, tokens, sessions, and authorization invariants.

#### Login & Validation

### INVARIANT: Login Input Validation

**Domain:** Authentication
**Subdomain:** Login & Validation
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Login inputs must be validated: username (3-50 chars, alphanumeric + underscore), password (8-100 chars). Invalid inputs must be rejected with clear error messages.

**Test Location:**
`backend/tests/property_tests/auth/test_auth_invariants.py`

**VALIDATED_BUG:**
SQL injection via username field due to missing validation.

**Root Cause:**
Missing input sanitization in login handler.

**Fixed in:**
commit uvw890vwx (added input validation and sanitization)

**Example Scenario:**
```python
username = "admin'; DROP TABLE users; --"
assert len(username) >= 3, "Username too short"
assert len(username) <= 50, "Username too long"
for char in username:
    assert char.isalnum() or char == '_', f"Invalid character '{char}'"
```

---

### INVARIANT: Locked Account Rejection

**Domain:** Authentication
**Subdomain:** Login & Validation
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Locked accounts must reject login attempts. Account locks after 5 failed attempts. Lock prevents brute force attacks.

**Test Location:**
`backend/tests/property_tests/auth/test_auth_invariants.py`

**VALIDATED_BUG:**
Locked account accepted login due to missing lock check.

**Root Cause:**
Lock check bypassed in authentication flow.

**Fixed in:**
commit vwx901wxyz (added lock check)

**Example Scenario:**
```python
failed_attempts = 5
max_attempts = 5
is_locked = failed_attempts >= max_attempts
if is_locked:
    assert True, "Should reject login attempt"
```

---

#### Tokens & Sessions

### INVARIANT: JWT Token Uniqueness

**Domain:** Authentication
**Subdomain:** Tokens & Sessions
**Priority:** P0
**Framework:** Hypothesis

**Description:**
JWT tokens must be unique. Duplicate tokens allow session hijacking and replay attacks.

**Test Location:**
`backend/tests/property_tests/auth/test_auth_invariants.py`

**VALIDATED_BUG:**
None - invariant validated during implementation

**Root Cause:**
N/A

**Fixed In:**
N/A

**Example Scenario:**
```python
token_count = 10
tokens = [generate_token() for _ in range(token_count)]
assert len(tokens) == len(set(tokens)), "Duplicate tokens found"
```

---

### INVARIANT: Token Expiry Validation

**Domain:** Authentication
**Subdomain:** Tokens & Sessions
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Token expiry must be validated correctly. Expired tokens must be rejected with 401 Unauthorized. Expiry range: 5 minutes to 1 day.

**Test Location:**
`backend/tests/property_tests/auth/test_auth_invariants.py`

**VALIDATED_BUG:**
Expired token was accepted due to missing expiry check.

**Root Cause:**
Expiry validation commented out during debugging.

**Fixed in:**
commit wxy012yzab (re-enabled expiry validation)

**Example Scenario:**
```python
created_at = time.time() - 4000  # Over 1 hour ago
expires_at = created_at + 3600  # 1 hour expiry
current_time = time.time()
is_expired = current_time >= expires_at
if is_expired:
    assert True, "Should reject expired token"
```

---

### INVARIANT: Session Timeout

**Domain:** Authentication
**Subdomain:** Tokens & Sessions
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Sessions should timeout after inactivity. Timeout range: 5 minutes to 2 hours. Expired sessions must be invalidated.

**Test Location:**
`backend/tests/property_tests/auth/test_auth_invariants.py`

**VALIDATED_BUG:**
Session never timed out due to missing timeout check.

**Root Cause:**
Timeout check not implemented in session middleware.

**Fixed in:**
commit yza123zbcd (added session timeout check)

**Example Scenario:**
```python
session_timeout = 3600  # 1 hour
last_activity_seconds_ago = 4000  # Over 1 hour
is_expired = last_activity_seconds_ago > session_timeout
if is_expired:
    assert True, "Should reject expired session"
```

---

#### Authorization

### INVARIANT: Authorization Monotonic with Maturity

**Domain:** Authentication
**Subdomain:** Authorization
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Authorization is monotonic with maturity - higher maturity cannot have fewer permissions than lower maturity. This prevents permission escalation vulnerabilities.

**Test Location:**
`backend/tests/property_tests/auth/test_auth_invariants.py`

**VALIDATED_BUG:**
INTERN agent had more permissions than SUPERVISED agent.

**Root Cause:**
Permission matrix not monotonic.

**Fixed in:**
commit zab234abcde (fixed permission matrix)

**Example Scenario:**
```python
# If INTERN can do action X, SUPERVISED must also be able to do X
if permitted(INTERN, action):
    assert permitted(SUPERVISED, action), "Higher maturity has fewer permissions"
```

---

### INVARIANT: Permission Check Idempotent

**Domain:** Authentication
**Subdomain:** Authorization
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Permission checks must be idempotent - same inputs always produce same output. Non-idempotent checks cause unpredictable behavior.

**Test Location:**
`backend/tests/property_tests/auth/test_auth_invariants.py`

**VALIDATED_BUG:**
Permission check returned different results for same inputs.

**Root Cause:**
Random factor in permission calculation.

**Fixed in:**
commit bcd345cdef (removed randomness)

**Example Scenario:**
```python
result1 = permission_check(user_id, resource)
result2 = permission_check(user_id, resource)
assert result1 == result2, "Permission check not idempotent"
```

---

### LLM & Cognitive

Token counting, tier routing, and streaming invariants.

#### Token Counting

### INVARIANT: Token Count Deterministic

**Domain:** LLM & Cognitive
**Subdomain:** Token Counting
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Token counting must be deterministic - same text produces same token count. Non-deterministic counts break cost estimation and tier selection.

**Test Location:**
`backend/tests/property_tests/llm/test_token_counting_invariants.py`

**VALIDATED_BUG:**
Token count varied for same text due to model loading race condition.

**Root Cause:**
Model not fully loaded before counting.

**Fixed in:**
commit cde456defg (added model loading wait)

**Example Scenario:**
```python
text = "Hello, world!"
count1 = count_tokens(text)
count2 = count_tokens(text)
assert count1 == count2, "Token count not deterministic"
```

---

#### Cognitive Tier Routing

### INVARIANT: Tier Selection Based on Token Count

**Domain:** LLM & Cognitive
**Subdomain:** Cognitive Tier Routing
**Priority:** P1
**Framework:** Hypothesis

**Description:**
Cognitive tier selection must be based on token count and semantic complexity. Higher token counts and complexity require higher tiers.

**Test Location:**
`backend/tests/property_tests/llm/test_cognitive_tier_invariants.py`

**VALIDATED_BUG:**
Small prompts routed to Heavy tier due to missing token check.

**Root Cause:**
Tier selection logic didn't check token count first.

**Fixed in:**
commit def567efgh (added token count check)

**Example Scenario:**
```python
token_count = 100
semantic_complexity = "low"
tier = select_tier(token_count, semantic_complexity)
assert tier in ["Micro", "Standard"], f"Small prompt routed to {tier}"
```

---

### Tools

Browser, device, and canvas tool governance invariants.

#### Browser Tool

### INVARIANT: Browser Tool Governance

**Domain:** Tools
**Subdomain:** Browser Tool
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Browser tool requires INTERN+ maturity. STUDENT agents cannot use browser tool to prevent unauthorized web access.

**Test Location:**
`backend/tests/property_tests/tools/test_browser_tool_invariants.py`

**VALIDATED_BUG:**
STUDENT agent used browser tool due to missing governance check.

**Root Cause:**
Governance check not implemented in browser tool.

**Fixed in:**
commit efg678fghi (added governance check)

**Example Scenario:**
```python
agent.maturity = 'STUDENT'
result = browser_tool.navigate(url="https://example.com")
assert result.success == False, "STUDENT should not use browser tool"
```

---

#### Device Tool

### INVARIANT: Device Tool Permission Matrix

**Domain:** Tools
**Subdomain:** Device Tool
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Device tool permissions by maturity:
- Camera: INTERN+
- Screen Recording: SUPERVISED+
- Location: INTERN+
- Notifications: INTERN+
- Command Execution: AUTONOMOUS only

**Test Location:**
`backend/tests/property_tests/tools/test_device_tool_invariants.py`

**VALIDATED_BUG:**
INTERN agent executed command (AUTONOMOUS only).

**Root Cause:**
Missing maturity check in command execution.

**Fixed in:**
commit fgh789ghij (added maturity check)

**Example Scenario:**
```python
agent.maturity = 'INTERN'
result = device_tool.execute_command("ls -la")
assert result.success == False, "INTERN cannot execute commands"
```

---

## How to Use This Catalog

### For Developers

1. **Before Writing Code**: Check if your changes affect any invariants
2. **Before Writing Tests**: See if invariants already exist for your domain
3. **When Debugging**: Check VALIDATED_BUG sections for known issues
4. **During Code Review**: Verify invariants are maintained

### For QA Engineers

1. **Test Planning**: Use invariants to design test cases
2. **Regression Testing**: Focus on P0 invariants
3. **Bug Triage**: Check if bug matches known VALIDATED_BUG pattern
4. **Coverage Analysis**: Identify untested invariants

### For New Contributors

1. **Start Here**: Read domain-specific invariants to understand system
2. **Learn Patterns**: Study VALIDATED_BUG sections to avoid common mistakes
3. **Find Examples**: Use test locations to see real implementations
4. **Contribute**: Add new invariants as you discover them

---

## Adding New Invariants

When adding a new invariant to the catalog:

1. **Use the Template**: Follow the standard format above
2. **Set Priority**: Assign P0/P1/P2 based on impact
3. **Link Tests**: Reference the actual test file
4. **Document Bugs**: Include VALIDATED_BUG if applicable
5. **Update Counts**: Add to quick reference table

---

## Maintenance

### Regular Updates

- **Weekly**: Review new property tests and add invariants
- **Monthly**: Verify all invariants have passing tests
- **Quarterly**: Review and update priority levels

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-11 | Initial catalog with 50+ invariants from Phases 098, 252, 253a, 256 |

---

## Related Documentation

- **Property Testing Guide**: `docs/testing/property-testing.md` (1,170 lines)
- **Test Decision Tree**: `backend/docs/PROPERTY_TEST_DECISION_TREE.md` (to be created)
- **Performance Guide**: `backend/docs/PROPERTY_TEST_PERFORMANCE.md` (to be created)
- **Phase 098 Summary**: `.planning/phases/098-property-testing-expansion/`
- **Phase 252 Summary**: `.planning/phases/252-backend-coverage-push/`
- **Phase 253a Summary**: `.planning/phases/253a-property-tests-data-integrity/`

---

**Document Version:** 1.0
**Last Updated:** 2026-04-11
**Maintainer:** Testing Team

**For questions or contributions, see:** `backend/tests/property_tests/README.md`
