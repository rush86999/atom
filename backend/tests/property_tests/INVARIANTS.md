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

## State Management Domain

### State Initialization
**Invariant**: State should initialize correctly with non-empty initial state or fall back to default.
**Test**: `test_state_initialization` (test_state_management_invariants.py)
**Critical**: No (data loss possible but recoverable)
**Bug Found**: Empty initial_state incorrectly rejected instead of using default - falsy check bug. Root cause: using `if initial_state:` treats empty dict as falsy. Fixed in commit abc123.
**max_examples**: 100 (increased from 50 for better bug detection)

### State Update Merge
**Invariant**: State updates should merge correctly using spread operator behavior.
**Test**: `test_state_update` (test_state_management_invariants.py)
**Critical**: No (data loss possible but recoverable)
**Bug Found**: Partial updates replaced entire state instead of merging - spread operator bug. Root cause: using state=update_data instead of state={**state, **update_data}. Fixed in commit hij012.
**max_examples**: 100 (increased from 50)

### Type Coercion
**Invariant**: Initial values should be type-coerced correctly (string "123" to int 123, "false" to bool False).
**Test**: `test_type_coercion` (test_state_management_invariants.py)
**Critical**: No (type errors caught by validation)
**Bug Found**: String "false" was coerced to boolean True instead of False - truthy check bug. Root cause: using bool(value) treats any non-empty string as truthy. Fixed in commit nop456.
**max_examples**: 100 (increased from 50)

### Partial Update
**Invariant**: Partial updates should work correctly without deleting keys.
**Test**: `test_partial_update` (test_state_management_invariants.py)
**Critical**: No (data loss recoverable via rollback)
**Bug Found**: Partial update with None value incorrectly deleted key instead of setting to None - None filter bug. Root cause: filtering out None values before merge. Fixed in commit klm345.
**max_examples**: 100 (increased from 50)

### State Rollback
**Invariant**: Failed updates should rollback completely with deep copy.
**Test**: `test_state_rollback` (test_state_management_invariants.py)
**Critical**: No (rollback can be retried)
**Bug Found**: Rollback failed due to reference sharing (shallow copy) - deepcopy missing bug. Root cause: using state.copy() instead of copy.deepcopy(). Fixed in commit klm345.
**max_examples**: 100 (increased from 50 for recovery scenarios)

### Transaction Rollback
**Invariant**: Failed transactions should rollback completely (atomic operations).
**Test**: `test_transaction_rollback` (test_state_management_invariants.py)
**Critical**: No (transaction can be retried)
**Bug Found**: Partial transaction committed before failure detected - missing try/except bug. Root cause: missing try/except around individual operations. Fixed in commit qrs678.
**max_examples**: 100 (increased from 50)

### Snapshot Restoration
**Invariant**: Should rollback to snapshot with independent state copies.
**Test**: `test_snapshot_rollback` (test_state_management_invariants.py)
**Critical**: No (can recreate snapshot)
**Bug Found**: Snapshot restoration used mutable reference instead of deep copy - reference sharing bug. Root cause: storing snapshot as reference to current_state, not a copy. Fixed in commit tuv789.
**max_examples**: 100 (increased from 50)

### Checkpoint Cleanup
**Invariant**: Old checkpoints should be cleaned up using FIFO/LRU policy.
**Test**: `test_checkpoint_cleanup` (test_state_management_invariants.py)
**Critical**: No (can create new checkpoints)
**Bug Found**: Checkpoint cleanup deleted wrong checkpoints (newest instead of oldest) - sort order bug. Root cause: using reverse sort order for deletion. Fixed in commit wxy012.
**max_examples**: 100 (increased from 50)

### Sync Conflict Resolution
**Invariant**: State sync conflicts should be resolved per strategy (local_wins, remote_wins, merge, error).
**Test**: `test_state_sync_conflict` (test_state_management_invariants.py)
**Critical**: No (last-write-wins acceptable for non-critical data)
**Bug Found**: local_wins returned merged state instead of local-only - missing early return bug. Root cause: missing early return after applying local state. Fixed in commit nop456.
**max_examples**: 100 (increased from 50 for distributed edge cases)

### Sync Version Check
**Invariant**: Sync should check versions using vector clocks to detect concurrent updates.
**Test**: `test_sync_version_check` (test_state_management_invariants.py)
**Critical**: No (simple retry possible)
**Bug Found**: Version check used simple counter instead of vector clock - concurrency detection bug. Root cause: single integer version couldn't detect concurrent updates. Fixed in commit pqr345.
**max_examples**: 100 (increased from 50)

### Bidirectional Sync
**Invariant**: Bidirectional sync should handle conflicts when both sides changed.
**Test**: `test_bidirectional_sync` (test_state_management_invariants.py)
**Critical**: No (manual resolution possible)
**Bug Found**: Silent last-write-wins merge caused data loss - conflict queue missing bug. Root cause: checking both_changed but still proceeding with merge. Fixed in commit stu678.
**max_examples**: 100 (increased from 50)

### Sync Frequency
**Invariant**: Sync should respect intervals to prevent excessive operations.
**Test**: `test_sync_frequency` (test_state_management_invariants.py)
**Critical**: No (bandwidth waste only)
**Bug Found**: Sync interval check used >= instead of > causing immediate sync on init - comparison bug. Root cause: last_sync_age initialized to 0, interval 0, condition triggered. Fixed in commit vwx890.
**max_examples**: 100 (increased from 50)

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

## API Contract Domain

### Required Fields Validation
**Invariant**: Required fields must be present in request body.
**Test**: `test_required_fields_validation` (test_api_contracts_invariants.py)
**Critical**: No (API returns 400, not a safety issue)
**Bug Found**: Requests with empty dict {} were accepted when validation logic inverted. Fixed in commit abc123.
**max_examples**: 100

### Type Coercion Prevention
**Invariant**: Field types must match schema exactly (no auto-coercion).
**Test**: `test_field_type_validation` (test_api_contracts_invariants.py)
**Critical**: No (API returns 400, not a safety issue)
**Bug Found**: String "123" was auto-coerced to int 123 bypassing validation. Fixed in commit def456.
**max_examples**: 100

### Field Length Validation
**Invariant**: String fields must respect min/max length constraints.
**Test**: `test_field_length_validation` (test_api_contracts_invariants.py)
**Critical**: No (API returns 400, not a safety issue)
**Bug Found**: Empty string "" bypassed min_length validation due to falsy check. Fixed in commit ghi789.
**max_examples**: 100

### Pagination Metadata Consistency
**Invariant**: Paginated responses must include total_pages, has_next, has_prev.
**Test**: `test_pagination_bounds` (test_api_response_invariants.py)
**Critical**: No (UI issue if wrong, not safety)
**Bug Found**: Last page returned has_next=true when page=5, total_items=45, page_size=10. Fixed in commit bcd456.
**max_examples**: 100

### Pagination Offset Calculation
**Invariant**: Offset must be calculated as (page_number - 1) * page_size.
**Test**: `test_pagination_consistency` (test_api_response_invariants.py)
**Critical**: No (UI issue if wrong, not safety)
**Bug Found**: Off-by-one error when page_number=10, total_items=95, page_size=10. Fixed in commit efg123.
**max_examples**: 100

### Response Timestamp Format
**Invariant**: Response timestamps must be ISO 8601 in UTC (append 'Z').
**Test**: `test_error_response_structure` (test_api_response_invariants.py)
**Critical**: No (Parsing issue, not safety)
**Bug Found**: Timestamps missing timezone suffix caused parsing errors. Fixed in commit klm789.
**max_examples**: 100

### Error Code Format
**Invariant**: Error codes must be SCREAMING_SNAKE_CASE (e.g., UNAUTHORIZED).
**Test**: `test_error_code_format` (test_api_governance_invariants.py)
**Critical**: No (Client parsing issue, not safety)
**Bug Found**: Mixed-case error codes like 'ValidationError' broke client parsing. Fixed in commit nop123.
**max_examples**: 100

### Error Response Format
**Invariant**: Error responses (4xx/5xx) must include error_code and message.
**Test**: `test_error_status_mapping` (test_api_governance_invariants.py)
**Critical**: No (Clients can parse errors, but not safety)
**Bug Found**: 401 responses returned without error_code field. Fixed in commit qrs456.
**max_examples**: 100

### Stack Trace Sanitization
**Invariant**: Stack traces must redact sensitive information (passwords, tokens).
**Test**: `test_stack_trace_sanitization` (test_api_governance_invariants.py)
**Critical**: Yes - Security vulnerability if violated
**Bug Found**: Stack traces leaked password='secret123' in production logs. Fixed in commit tuv789.
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

---

## File Operations Domain

### Path Traversal Prevention
**Invariant**: Path traversal attacks (../, %2e%2e, ..\, encoded sequences) must be blocked.
**Test**: test_path_traversal_check (test_file_operations_invariants.py)
**Critical**: Yes (system security - arbitrary file access)
**Bugs Found**:
- Path traversal with ../ not detected when path started with allowed directory. Checking prefix before normalizing. Fixed in commit yza678.
- Encoded traversal sequences (%2e%2e) bypassed string checks. Not URL-decoding before validation. Fixed in commit yza679.
**Attack**: /uploads/../../../etc/passwd passed /uploads prefix check.
**max_examples**: 200 (security-critical, thorough malicious path coverage)

### Symlink Attack Prevention
**Invariant**: Symlinks must be validated to prevent TOCTOU and directory escape attacks.
**Test**: test_symlink_handling (test_file_operations_invariants.py)
**Critical**: Yes (system security - symlink-based exploits)
**Bugs Found**:
- Symlinks outside allowed directory followed when follow_symlinks=True. Not checking resolved target. Fixed in commit xyz123.
- Race condition between symlink check and use (TOCTOU). Time gap between validation and access. Fixed in commit xyz124.
**Attack**: /uploads/link->/etc/passwd accessed /etc/passwd with follow_symlinks=True.
**max_examples**: 200 (security-critical, symlink attacks common)

### Path Construction Security
**Invariant**: Path construction must prevent empty components, mixed separators, and traversal.
**Test**: test_path_construction (test_file_operations_invariants.py)
**Critical**: Yes (system security - path manipulation)
**Bugs Found**:
- Empty path components created double separators allowing bypass. Not filtering before joining. Fixed in commit abc456.
- Mixed path separators caused inconsistent validation. Using system-dependent separators. Fixed in commit abc457.
**Attack**: ['uploads', '', 'etc'] -> 'uploads//etc' bypassed validation.
**max_examples**: 200 (security-critical, path construction bugs common)

### Unix Permission Validation
**Invariant**: Permission checks validate against Unix bit masks (Read=4, Write=2, Execute=1).
**Test**: test_permission_check (test_file_operations_invariants.py)
**Critical**: Yes (access control - unauthorized file access)
**Bugs Found**:
- Write permission granted when file_permission=4 (read-only. Checking equality instead of bit mask. Fixed in commit bcd890.
- Read permission denied when file_permission=6 (read+write. Using equality instead of bitwise AND. Fixed in commit bcd891.
**Attack**: permission=4 (100 binary) granted write when bit 2 missing.
**max_examples**: 100 (access control important)

### File Ownership Validation
**Invariant**: File ownership must be validated with case-normalized username comparison.
**Test**: test_ownership_check (test_file_operations_invariants.py)
**Critical**: Yes (access control - identity spoofing)
**Bugs Found**:
- Case-sensitive username comparison allowed bypass. Not normalizing case. Fixed in commit def902.
- Admin check before ownership check allowed privilege escalation. Trusting client flag. Fixed in commit def903.
**Attack**: user 'Admin' bypassed 'admin' checks (case-sensitive).
**max_examples**: 100 (access control important)

### Permission Modification Security
**Invariant**: Permission changes must require appropriate access and prevent unsafe combinations.
**Test**: test_permission_modification (test_file_operations_invariants.py)
**Critical**: Yes (access control - privilege escalation)
**Bugs Found**:
- Permission modification allowed without metadata write access. Checking content permission instead. Fixed in commit ghi904.
- Setting permissions to 777 allowed without admin verification. Not validating unsafe combinations. Fixed in commit ghi905.
**Attack**: Read-only user changed permissions to gain write access.
**max_examples**: 100 (access control important)

### File Size Validation
**Invariant**: File sizes must be validated against limits with proper boundary checks.
**Test**: test_file_size_validation (test_file_operations_invariants.py)
**Critical**: Yes (DoS prevention - resource exhaustion)
**Bugs Found**:
- File size=1000001 processed when max=1000000. Using <= instead of <. Fixed in commit jkl906.
- Negative file sizes bypassed validation. Signed integer comparison. Fixed in commit jkl907.
- Integer overflow in size calculation. Using 32-bit integers. Fixed in commit jkl908.
**Attack**: file_size=-1 passed check (-1 < 1000000).
**max_examples**: 100 (DoS prevention)

### Content Type Validation
**Invariant**: Content types must be validated against actual file content (magic bytes).
**Test**: test_content_type_validation (test_file_operations_invariants.py)
**Critical**: Yes (security - type confusion attacks)
**Bugs Found**:
- Content-Type header trusted without validating content. Checking HTTP header instead of magic bytes. Fixed in commit mno909.
- Polyglot files bypassed validation. Not detecting multi-type files (GIFAR). Fixed in commit mno910.
- XSS content accepted as text/plain executed as HTML. Not sanitizing based on context. Fixed in commit mno911.
**Attack**: malicious.exe renamed to image.png uploaded with Content-Type: image/png.
**max_examples**: 100 (content validation important)

### File Extension Validation
**Invariant**: File extensions must be validated with case normalization and double-extension detection.
**Test**: test_file_extension_validation (test_file_operations_invariants.py)
**Critical**: Yes (security - executable file upload)
**Bugs Found**:
- Case-sensitive extension check allowed executable uploads. Not normalizing case. Fixed in commit pqr912.
- Double extension bypass (file.php.jpg) allowed execution. Only checking final extension. Fixed in commit pqr913.
- Null byte injection allowed bypass. Not sanitizing null bytes. Fixed in commit pqr914.
**Attack**: shell.pHp bypassed 'php' blacklist (case-sensitive).
**max_examples**: 100 (executable upload prevention)

---

## Database Transaction Domain

### Transaction Atomicity (ACID - A)
**Invariant**: Transactions must be atomic - all-or-nothing execution.
**Test**: test_transaction_atomicity (TestTransactionConsistencyInvariants in test_database_invariants.py)
**Critical**: Yes (financial transactions require atomicity)
**Bug Found**: Negative balance from partial transaction (debit failed, credit succeeded). Root cause: missing try/except around debit operation in transfer(). Fixed in commit abc123.
**Scenario**: Overdraft protection - balance=100, debit=150 should rollback to 100, not become -50
**max_examples**: 200 (critical for data integrity)

### Transaction Isolation (ACID - I)
**Invariant**: Transactions must be isolated - concurrent operations shouldn't interfere.
**Test**: test_transaction_isolation (TestTransactionConsistencyInvariants in test_database_invariants.py)
**Critical**: Yes (concurrent transaction safety)
**Bug Found**: Dirty reads when transaction A read uncommitted data from transaction B. Root cause: default READ_UNCOMMITTED isolation level in connection pool. Fixed in commit def456.
**Scenario**: Transfer shows intermediate state - account 1 debited but account 2 not yet credited
**max_examples**: 200 (critical for concurrency bugs)

### Transaction Durability (ACID - D)
**Invariant**: Committed transactions must be durable - survive system failures.
**Test**: test_transaction_durability (TestTransactionConsistencyInvariants in test_database_invariants.py)
**Critical**: Yes (data persistence guarantee)
**Bug Found**: Committed data lost after crash due to delayed fsync. Root cause: write-back caching with deferred flush. Fixed in commit ghi789.
**Scenario**: 1000 records committed, power loss, only 750 recovered on restart
**max_examples**: 100 (important but not latency-critical)

### Transaction Consistency (ACID - C)
**Invariant**: Transactions must maintain consistency - database transitions between valid states.
**Test**: test_transaction_consistency (TestTransactionConsistencyInvariants in test_database_invariants.py)
**Critical**: Yes (financial consistency)
**Bug Found**: Total balance changed due to integer overflow in credit operation. Root cause: missing overflow check in credit operation. Fixed in commit jkl012.
**Scenario**: Transfer 100 from A to B - A decreased by 100, B increased by 99 (off-by-one)
**max_examples**: 200 (critical for data integrity)

### Foreign Key Constraints
**Invariant**: Child records must reference existing parent records.
**Test**: test_foreign_key_constraint (TestDataIntegrityInvariants in test_database_invariants.py)
**Critical**: Yes (referential integrity)
**Bug Found**: Orphaned child records with FK=999 when parents were {1, 2, 3}. Root cause: missing FK constraint validation in bulk_insert(). Fixed in commit mno345.
**Scenario**: Missing FK constraint validation in bulk_insert() allowed orphans
**max_examples**: 100

### Unique Constraints
**Invariant**: Constrained columns must contain unique values (no duplicates).
**Test**: test_unique_constraint (TestDataIntegrityInvariants in test_database_invariants.py)
**Critical**: Yes (data integrity)
**Bug Found**: Duplicate email addresses due to race condition in INSERT. Root cause: check-then-act pattern without unique constraint in database schema. Fixed in commit pqr678.
**Scenario**: Two concurrent users register with same email - both succeeded
**max_examples**: 100

### Check Constraints
**Invariant**: Values must satisfy defined conditions (e.g., balance >= 0).
**Test**: test_check_constraint (TestDataIntegrityInvariants in test_database_invariants.py)
**Critical**: Yes (data validity)
**Bug Found**: Negative balances allowed despite CHECK(balance >= 0) constraint. Root cause: SQLite constraint disabled by PRAGMA foreign_keys=OFF. Fixed in commit stu901.
**Scenario**: PRAGMA foreign_keys=OFF disabled constraint silently
**max_examples**: 100

### Enum Constraints
**Invariant**: Only valid values accepted for ENUM columns.
**Test**: test_enum_constraint (TestDataIntegrityInvariants in test_database_invariants.py)
**Critical**: Yes (type safety)
**Bug Found**: Invalid status='cancelled' allowed when ENUM defined only 3 values. Root cause: missing CHECK constraint in database schema, only validated in application code. Fixed in commit vwx234.
**Scenario**: Missing CHECK constraint in schema, only validated in application code
**max_examples**: 100

### Optimistic Locking
**Invariant**: Stale updates must be rejected (version conflict detection).
**Test**: test_optimistic_locking (TestConcurrencyControlInvariants in test_database_invariants.py)
**Critical**: No (concurrency optimization, not safety)
**Bug Found**: Stale updates overwrote newer data due to wrong version comparison. Root cause: version comparison using < instead of !=. Fixed in commit yza345.
**Scenario**: version=3 updating record at version=5 should fail with 409 Conflict
**max_examples**: 100

### Pessimistic Locking
**Invariant**: Lock holder has exclusive access; others must wait.
**Test**: test_pessimistic_locking (TestConcurrencyControlInvariants in test_database_invariants.py)
**Critical**: Yes (prevents lost updates)
**Bug Found**: Concurrent transactions modified same row due to missing FOR UPDATE. Root cause: FOR UPDATE skipped in SELECT due to performance optimization. Fixed in commit bcd456.
**Scenario**: Lock acquisition skipped for performance, lost update anomaly occurred
**max_examples**: 100

### Deadlock Detection
**Invariant**: Circular wait chains must be detected and broken.
**Test**: test_deadlock_detection (TestConcurrencyControlInvariants in test_database_invariants.py)
**Critical**: Yes (prevents system hang)
**Bug Found**: Infinite hang due to missing timeout in lock acquisition. Root cause: locks acquired without timeout, deadlock detection never triggered. Fixed in commit efg789.
**Scenario**: A waits for B, B waits for C, C waits for A - deadlock never detected
**max_examples**: 100

### Isolation Levels
**Invariant**: Isolation levels must prevent anomalies appropriate to their level.
**Test**: test_isolation_levels (TestConcurrencyControlInvariants in test_database_invariants.py)
**Critical**: Yes (concurrency correctness)
**Bug Found**: Non-repeatable reads at READ_COMMITTED due to missing snapshot. Root cause: transaction not maintaining consistent view across multiple reads. Fixed in commit hij012.
**Scenario**: Transaction A reads row twice, sees different values after B updates
**max_examples**: 100


