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
