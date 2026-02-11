# Property Test Invariants

This document catalogs all invariants tested by property-based tests across all domains.

**Purpose**: Document system invariants, their criticality, and bug-finding history for quality assurance.

**Last Updated**: 2026-02-11

---

## Event Handling Domain

### Chronological Ordering
**Invariant**: Events must be processed in timestamp order.
**Test**: `test_chronological_ordering` (test_event_handling_invariants.py)
**Critical**: Yes (workflow correctness depends on ordering)
**Bug Found**: Out-of-order events processed in arrival order (missing sort step)
**max_examples**: 100

### Sequence Ordering
**Invariant**: Sequence numbers must be monotonically increasing with gap detection.
**Test**: `test_sequence_ordering`
**Critical**: Yes (missing events indicate data loss)
**Bug Found**: Sequence gaps not detected, causing missed events
**max_examples**: 100

### Partition Ordering Determinism
**Invariant**: Same partition key must always map to same partition.
**Test**: `test_partition_ordering`
**Critical**: Yes (non-deterministic breaks ordering guarantees)
**Bug Found**: Partition mapping changed during hot-reload (non-deterministic hash seed)
**max_examples**: 100

### Causal Dependency Ordering
**Invariant**: Events must be processed after dependencies satisfied.
**Test**: `test_causal_ordering`
**Critical**: Yes (violates causal constraints)
**Bug Found**: Dependencies not topologically sorted before processing
**max_examples**: 100

### Event Batch Size Calculation
**Invariant**: Events batched by size, last batch may be partial but not empty.
**Test**: `test_batch_size`
**Critical**: No (performance optimization)
**Bug Found**: Empty last batch when event_count exact multiple of batch_size (off-by-one)
**max_examples**: 100

### Batch Timeout Boundary
**Invariant**: Batches must flush when timeout expires.
**Test**: `test_batch_timeout`
**Critical**: No (latency optimization)
**Bug Found**: Boundary condition used >= instead of >, causing early flush
**max_examples**: 100

### Batch Memory Limit
**Invariant**: Batches must respect memory limits.
**Test**: `test_batch_memory_limit`
**Critical**: Yes (OOM errors cause crashes)
**Bug Found**: Integer division overflow before comparison, silent OOM
**max_examples**: 100

### Priority Event Batching
**Invariant**: Priority events must bypass normal batching.
**Test**: `test_priority_batching`
**Critical**: No (latency optimization)
**Bug Found**: Priority events added to normal batch, causing delay
**max_examples**: 100

### DLQ Retry Limit
**Invariant**: Events exceeding max_retries move to DLQ permanently.
**Test**: `test_dlq_retry`
**Critical**: No (manual intervention available)
**Bug Found**: retry_count=3 retried when max_retries=3 (off-by-one, used >= instead of >)
**max_examples**: 100

### DLQ Retention Policy
**Invariant**: DLQ events older than max_age must be deleted.
**Test**: `test_dlq_retention`
**Critical**: No (disk space recovery)
**Bug Found**: Retention used >= instead of >, deleting events at exact boundary
**max_examples**: 100

### DLQ Size Limit
**Invariant**: DLQ must enforce maximum size limits.
**Test**: `test_dlq_size_limit`
**Critical**: Yes (unbounded growth causes memory pressure)
**Bug Found**: Size check used > instead of >=, allowing overflow by 1
**max_examples**: 100

### DLQ Categorization
**Invariant**: DLQ events must be categorized by failure type.
**Test**: `test_dlq_categorization`
**Critical**: No (monitoring and retry strategy)
**Bug Found**: Categorization was case-sensitive, treating "Transient" != "transient"
**max_examples**: 100

---

## Episodic Memory Domain

### Time Gap Segmentation
**Invariant**: Time gaps > threshold (exclusive) trigger new episode.
**Test**: `test_time_gap_detection` (test_episode_segmentation_invariants.py)
**Critical**: Yes (memory integrity depends on correct segmentation)
**Bug Found**: Gap of exactly 4 hours did not trigger segmentation when threshold=4 (boundary bug). Root cause: using >= instead of >. Fixed in commit ghi789.
**max_examples**: 200 (critical - memory integrity)

### Time Gap Threshold Enforcement
**Invariant**: Segmentation boundary is exclusive (> not >=).
**Test**: `test_time_gap_threshold_enforcement` (test_episode_segmentation_invariants.py)
**Critical**: Yes (prevents incorrect episode boundaries)
**Bug Found**: Gaps exactly equal to threshold incorrectly triggered new episodes. Fixed in commit jkl012.
**max_examples**: 200 (critical - boundary enforcement)

### Topic Change Detection
**Invariant**: Topic changes trigger new segments for semantic coherence.
**Test**: `test_topic_change_detection` (test_episode_segmentation_invariants.py)
**Critical**: No (usability)
**Bug Found**: Case-sensitive comparison split same-topic utterances. Fixed in commit mno345.
**max_examples**: 100

### Task Completion Detection
**Invariant**: Task completion markers trigger segment boundaries.
**Test**: `test_task_completion_detection` (test_episode_segmentation_invariants.py)
**Critical**: No (workflow optimization)
**Bug Found**: Segments without task_complete=True incorrectly included. Fixed in commit pqr456.
**max_examples**: 100

### Temporal Retrieval Time Filtering
**Invariant**: Temporal retrieval filters by time range correctly.
**Test**: `test_temporal_retrieval_time_filtering` (test_episode_retrieval_invariants.py)
**Critical**: No (retrieval accuracy)
**Bug Found**: Episodes at exact boundary excluded. Fixed in commit stu123.
**max_examples**: 100

### Semantic Similarity Bounds
**Invariant**: Semantic retrieval similarity scores are in [0, 1].
**Test**: `test_semantic_retrieval_similarity_bounds` (test_episode_retrieval_invariants.py)
**Critical**: No (ranking quality)
**Bug Found**: Scores of -0.01 from floating point rounding. Fixed in commit vwx456.
**max_examples**: 100

### Semantic Retrieval Ranking
**Invariant**: Episodes ranked by similarity (descending).
**Test**: `test_semantic_retrieval_ranking_order` (test_episode_retrieval_invariants.py)
**Critical**: No (determinism)
**Bug Found**: Non-deterministic ordering for identical scores. Fixed in commit yza789.
**max_examples**: 100

### Sequential Retrieval Segment Inclusion
**Invariant**: Sequential retrieval includes all episode segments.
**Test**: `test_sequential_retrieval_includes_segments` (test_episode_retrieval_invariants.py)
**Critical**: No (completeness)
**Bug Found**: Segments with null episode_id excluded by INNER JOIN. Fixed in commit bcd234.
**max_examples**: 100

### Readiness Score Bounds
**Invariant**: Graduation readiness score must be in [0, 100].
**Test**: `test_readiness_score_bounds` (test_agent_graduation_invariants.py)
**Critical**: Yes (promotion decisions are security-relevant)
**Bug Found**: Score of 105 from negative intervention rate. Fixed in commit mno345.
**Boundary**: STUDENT->INTERN: 10 episodes, 50% intervention, 0.70 constitutional = 40.0 readiness
**max_examples**: 200 (critical - security)

### Readiness Score Monotonicity
**Invariant**: Readiness score increases with better metrics.
**Test**: `test_readiness_score_monotonic` (test_agent_graduation_invariants.py)
**Critical**: Yes (prevents unfair evaluation)
**Bug Found**: Integer division caused score decrease. Fixed in commit def456.
**max_examples**: 200 (critical - fair evaluation)

### Intervention Rate Threshold
**Invariant**: Intervention rate must be below threshold for promotion.
**Test**: `test_intervention_rate_threshold` (test_agent_graduation_invariants.py)
**Critical**: Yes (prevents premature promotion)
**Bug Found**: Rate of 0.5 accepted when threshold was 0.5. Fixed in commit ghi789.
**Requirement**: STUDENT->INTERN requires <50% intervention
**max_examples**: 200 (critical - security)

### Constitutional Score Threshold
**Invariant**: Constitutional score meets minimum threshold for promotion.
**Test**: `test_constitutional_score_threshold` (test_agent_graduation_invariants.py)
**Critical**: Yes (constitutional compliance is non-negotiable)
**Bug Found**: Score of 0.6999 rounded to 0.70 and accepted. Fixed in commit jkl012.
**Thresholds**: INTERN>=0.70, SUPERVISED>=0.85, AUTONOMOUS>=0.95
**max_examples**: 200 (critical - governance)

---

## Maintenance Notes

**Adding New Invariants**:
1. Create property test in appropriate domain file
2. Add entry to this document
3. Set appropriate max_examples (100 for critical/complex, 50 for standard, 20 for performance-heavy)
4. Document bugs found with commit hashes
5. Mark criticality (Yes = data loss/corruption/security, No = performance/optimization)

**Review Schedule**:
- Monthly: Review bug findings and update criticality
- Quarterly: Expand test coverage with new invariants
- On Incident: Add invariant for any production issue

**Quality Gates**:
- All invariants must pass before deployment
- New bugs must be documented with VALIDATED_BUG sections
- max_examples must be justified based on criticality
