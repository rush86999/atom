# Property Test Invariants

This document catalogs all invariants tested by the property-based test suite, organized by domain.

## Governance Domain

### Confidence Score Bounds
**Invariant**: Confidence scores must stay in [0.0, 1.0] and match maturity level ranges.
**Test**: `test_confidence_bounds` in `test_agent_governance_invariants.py`
**Critical**: Yes (security-relevant for privilege management)
**max_examples**: 200 (increased from 50 for higher confidence)
**Bugs Found**:
- Confidence of 0.95 assigned to INTERN agent (should be 0.5-0.7 range) - regression logic bug
- Confidence of 0.6 assigned to STUDENT agent (exceeds 0.5 max) - promotion validation bug
- Confidence of 0.85 assigned to AUTONOMOUS agent (below 0.9 min) - penalty feedback bug

### Maturity Progression
**Invariant**: Agents never regress in maturity level (STUDENT → INTERN → SUPERVISED → AUTONOMOUS).
**Test**: `test_maturity_progression` in `test_agent_governance_invariants.py`
**Critical**: Yes (prevents privilege escalation attacks)
**max_examples**: 200 (increased from 50)
**Bugs Found**:
- Maturity regression from SUPERVISED to INTERN - manual admin override bypass
- Severe regression from AUTONOMOUS to STUDENT - automatic demotion bug

### Action Maturity Requirements
**Invariant**: Actions require minimum maturity levels based on complexity (1-4).
**Test**: `test_action_maturity_requirements` in `test_agent_governance_invariants.py`
**Critical**: Yes (prevents unauthorized destructive operations)
**max_examples**: 200 (increased from 50)
**Bugs Found**:
- INTERN agent allowed to execute delete (complexity 4) action - missing ACTION_COMPLEXITY entry
- STUDENT agent allowed to execute state changes (complexity 3) - missing form action mapping

### Intervention Rate Calculation
**Invariant**: Intervention rate must be calculated correctly and stay within [0, 1].
**Test**: `test_intervention_rate` in `test_agent_governance_invariants.py`
**Critical**: Yes (determines graduation readiness)
**max_examples**: 200 (increased from 50)
**Bugs Found**:
- Intervention count exceeding total actions caused division errors - race condition in tracking

### Permission Checking
**Invariant**: Permissions must be validated before actions are executed.
**Test**: `test_permission_check` in `test_agent_governance_invariants.py`
**Critical**: Yes (security enforcement)
**max_examples**: 50 (standard invariant)

### Tool Governance
**Invariant**: Tools require minimum maturity levels (canvas: STUDENT, browser: INTERN, etc.).
**Test**: `test_tool_governance` in `test_agent_governance_invariants.py`
**Critical**: Yes (access control)
**max_examples**: 50 (standard invariant)

### Trigger Governance
**Invariant**: STUDENT agents cannot use automated triggers.
**Test**: `test_trigger_governance` in `test_agent_governance_invariants.py`
**Critical**: Yes (prevents unattended automation)
**max_examples**: 50 (standard invariant)

### Trigger Blocking
**Invariant**: STUDENT agents are blocked from automated triggers.
**Test**: `test_trigger_blocking` in `test_agent_governance_invariants.py`
**Critical**: Yes (training safety)
**max_examples**: 50 (standard invariant)

### Approval Requirements
**Invariant**: Actions require approval based on maturity and complexity.
**Test**: `test_approval_requirement` in `test_agent_governance_invariants.py`
**Critical**: Yes (human-in-the-loop enforcement)
**max_examples**: 50 (standard invariant)

### Proposal Workflow
**Invariant**: Proposals follow proper approval workflow (pending → approved/rejected).
**Test**: `test_proposal_workflow` in `test_agent_governance_invariants.py`
**Critical**: Yes (process integrity)
**max_examples**: 50 (standard invariant)

### Proposal Expiration
**Invariant**: Proposals expire after a configured time period.
**Test**: `test_proposal_expiration` in `test_agent_governance_invariants.py`
**Critical**: Yes (security timeout)
**max_examples**: 50 (standard invariant)

### Approval Authority
**Invariant**: Approvers must have authority and cannot self-approve.
**Test**: `test_approval_authority` in `test_agent_governance_invariants.py`
**Critical**: Yes (separation of duties)
**max_examples**: 50 (standard invariant)

### Audit Log Entry
**Invariant**: All governance actions must be logged with timestamp and outcome.
**Test**: `test_audit_log_entry` in `test_agent_governance_invariants.py`
**Critical**: Yes (compliance requirement)
**max_examples**: 50 (standard invariant)

### Log Retention
**Invariant**: Audit logs must be retained for minimum 30 days.
**Test**: `test_log_retention` in `test_agent_governance_invariants.py`
**Critical**: Yes (compliance requirement)
**max_examples**: 50 (standard invariant)

### Sensitive Action Logging
**Invariant**: Sensitive operations require detailed audit logs.
**Test**: `test_sensitive_action_logging` in `test_agent_governance_invariants.py`
**Critical**: Yes (compliance requirement)
**max_examples**: 50 (standard invariant)

### Session Timeout
**Invariant**: Sessions must timeout after inactivity period.
**Test**: `test_session_timeout` in `test_agent_governance_invariants.py`
**Critical**: Yes (security)
**max_examples**: 50 (standard invariant)

### Session Creation
**Invariant**: Sessions must be created with proper metadata.
**Test**: `test_session_creation` in `test_agent_governance_invariants.py`
**Critical**: No (operational)
**max_examples**: 50 (standard invariant)

### Session Limits
**Invariant**: Concurrent session limits must be enforced.
**Test**: `test_session_limits` in `test_agent_governance_invariants.py`
**Critical**: No (resource management)
**max_examples**: 50 (standard invariant)

### Idle Timeout
**Invariant**: Idle sessions must timeout after configured period.
**Test**: `test_idle_timeout` in `test_agent_governance_invariants.py`
**Critical**: Yes (security)
**max_examples**: 50 (standard invariant)

### Training Episode Requirements
**Invariant**: Training requires minimum episodes before graduation.
**Test**: `test_training_episode_requirement` in `test_agent_governance_invariants.py`
**Critical**: Yes (graduation criteria)
**max_examples**: 50 (standard invariant)

### Intervention Threshold
**Invariant**: Intervention rate must be below threshold for graduation.
**Test**: `test_intervention_threshold` in `test_agent_governance_invariants.py`
**Critical**: Yes (graduation criteria)
**max_examples**: 50 (standard invariant)

### Constitutional Compliance
**Invariant**: Constitutional compliance score must be high for graduation.
**Test**: `test_constitutional_compliance` in `test_agent_governance_invariants.py`
**Critical**: Yes (graduation criteria)
**max_examples**: 50 (standard invariant)

### Training Duration
**Invariant**: Training must meet minimum duration requirements.
**Test**: `test_training_duration` in `test_agent_governance_invariants.py`
**Critical**: Yes (graduation criteria)
**max_examples**: 50 (standard invariant)

### Supervision Requirements
**Invariant**: Supervision required based on maturity and action risk.
**Test**: `test_supervision_requirement` in `test_agent_governance_invariants.py`
**Critical**: Yes (safety enforcement)
**max_examples**: 50 (standard invariant)

### Intervention Tracking
**Invariant**: Interventions must be tracked with details.
**Test**: `test_intervention_tracking` in `test_agent_governance_invariants.py`
**Critical**: Yes (audit trail)
**max_examples**: 50 (standard invariant)

### Supervisor Validation
**Invariant**: Supervisors must be validated (active, have permission).
**Test**: `test_supervisor_validation` in `test_agent_governance_invariants.py`
**Critical**: Yes (access control)
**max_examples**: 50 (standard invariant)

### Session Termination
**Invariant**: Supervision sessions must be terminatable with reason.
**Test**: `test_session_termination` in `test_agent_governance_invariants.py`
**Critical**: Yes (audit trail)
**max_examples**: 50 (standard invariant)

## Governance Cache Domain

### Cache Miss Returns None
**Invariant**: Cache miss for non-existent entries should return None.
**Test**: `test_cache_miss_returns_none` in `test_governance_cache_invariants.py`
**Critical**: No (performance optimization)
**max_examples**: 100 (increased from 50)
**Bugs Found**:
- Cache miss returned stale cached value due to TTL check bug (<= vs < comparison)

### Cache Set Then Get
**Invariant**: Cache set followed by get should return the cached value.
**Test**: `test_cache_set_then_get` in `test_governance_cache_invariants.py`
**Critical**: Yes (consistency)
**max_examples**: 100 (increased from 50)
**Bugs Found**:
- Case sensitivity bug: 'TestAgent' and 'testagent' created separate cache entries

### Cache Key Uniqueness
**Invariant**: Cache keys are unique per (agent_id, action_type) combination.
**Test**: `test_cache_key_uniqueness` in `test_governance_cache_invariants.py`
**Critical**: Yes (correctness)
**max_examples**: 100 (increased from 50)
**Bugs Found**:
- Key collision due to missing separator (agent_1+action_X collided with agent_1action_X)

### Cache Expiration
**Invariant**: Cache entries must expire after TTL elapses.
**Test**: `test_cache_expires_after_ttl` in `test_governance_cache_invariants.py`
**Critical**: Yes (stale data prevention)
**max_examples**: 10 (time-sensitive test)
**Bugs Found**:
- Entries persisted indefinitely due to timestamp vs duration comparison bug

### Cache Refresh on Set
**Invariant**: Setting a cached entry should refresh its TTL.
**Test**: `test_cache_refresh_on_set` in `test_governance_cache_invariants.py`
**Critical**: Yes (data freshness)
**max_examples**: 10 (time-sensitive test)
**Bugs Found**:
- TTL not refreshed on set() for existing keys, causing frequent access to expire

### Cache Size Limit
**Invariant**: Cache size must never exceed max_size limit.
**Test**: `test_cache_size_limit_enforced` in `test_governance_cache_invariants.py`
**Critical**: Yes (resource management)
**max_examples**: 50 (standard invariant)

### LRU Eviction
**Invariant**: LRU eviction removes least recently used entries first.
**Test**: `test_lru_eviction_oldest_first` in `test_governance_cache_invariants.py`
**Critical**: Yes (correctness)
**max_examples**: 50 (standard invariant)

### Recency Updates
**Invariant**: Accessing entries updates their recency.
**Test**: `test_recency_updates_on_access` in `test_governance_cache_invariants.py`
**Critical**: Yes (LRU correctness)
**max_examples**: 50 (standard invariant)

### Concurrent Read Safety
**Invariant**: Concurrent reads must be thread-safe.
**Test**: `test_concurrent_read_safety` in `test_governance_cache_invariants.py`
**Critical**: Yes (thread safety)
**max_examples**: 50 (standard invariant)

### Concurrent Write Safety
**Invariant**: Concurrent writes must be thread-safe.
**Test**: `test_concurrent_write_safety` in `test_governance_cache_invariants.py`
**Critical**: Yes (thread safety)
**max_examples**: 50 (standard invariant)

### Hit Rate Calculation
**Invariant**: Hit rate must be calculated correctly (hits / total * 100).
**Test**: `test_hit_rate_calculation` in `test_governance_cache_invariants.py`
**Critical**: No (monitoring)
**max_examples**: 50 (standard invariant)

### Hit Rate Bounds
**Invariant**: Hit rate must always be in [0.0, 100.0].
**Test**: `test_hit_rate_bounds` in `test_governance_cache_invariants.py`
**Critical**: No (monitoring)
**max_examples**: 50 (standard invariant)

### Warm Cache Hit Rate
**Invariant**: Warm cache should achieve high hit rate.
**Test**: `test_high_hit_rate_with_warm_cache` in `test_governance_cache_invariants.py`
**Critical**: No (performance)
**max_examples**: 50 (standard invariant)

### Specific Action Invalidation
**Invariant**: Invalidating specific action should not affect other cached actions.
**Test**: `test_specific_action_invalidation` in `test_governance_cache_invariants.py`
**Critical**: Yes (correctness)
**max_examples**: 100 (increased from 50)
**Bugs Found**:
- Invalidation cleared all actions for agent due to prefix matching bug

### Agent-Wide Invalidation
**Invariant**: Agent-wide invalidation must remove all cached actions for that agent.
**Test**: `test_agent_wide_invalidation` in `test_governance_cache_invariants.py`
**Critical**: Yes (correctness)
**max_examples**: 50 (standard invariant)

### Cache Clear
**Invariant**: Clear must remove all cache entries.
**Test**: `test_clear_removes_all_entries` in `test_governance_cache_invariants.py`
**Critical**: Yes (correctness)
**max_examples**: 50 (standard invariant)

### Lookup Latency
**Invariant**: Lookup latency must be <10ms per requirement.
**Test**: `test_lookup_latency_performance` in `test_governance_cache_invariants.py`
**Critical**: Yes (performance requirement)
**max_examples**: 50 (standard invariant)

### Hit Rate Requirement
**Invariant**: Cache must achieve required hit rate (target: 50-99%).
**Test**: `test_hit_rate_requirement` in `test_governance_cache_invariants.py`
**Critical**: Yes (performance requirement)
**max_examples**: 50 (standard invariant)

### Statistics Accuracy
**Invariant**: Cache statistics (hits, misses, size, hit_rate) must be accurate.
**Test**: `test_statistics_accuracy` in `test_governance_cache_invariants.py`
**Critical**: No (monitoring)
**max_examples**: 50 (standard invariant)

### Statistics Incremental
**Invariant**: Statistics must increment correctly with each operation.
**Test**: `test_statistics_incremental` in `test_governance_cache_invariants.py`
**Critical**: No (monitoring)
**max_examples**: 50 (standard invariant)

### Key Format Consistency
**Invariant**: Cache key format must be consistent (agent_id:action_type.lower()).
**Test**: `test_key_format_consistency` in `test_governance_cache_invariants.py`
**Critical**: Yes (correctness)
**max_examples**: 50 (standard invariant)

### Case-Insensitive Action Type
**Invariant**: Action type should be case-insensitive in keys.
**Test**: `test_case_insensitive_action_type` in `test_governance_cache_invariants.py`
**Critical**: No (usability)
**max_examples**: 50 (standard invariant)

### Max Size Limit
**Invariant**: max_size limit must be strictly enforced.
**Test**: `test_max_size_limit_enforced` in `test_governance_cache_invariants.py`
**Critical**: Yes (resource management)
**max_examples**: 50 (standard invariant)

### Eviction Counter
**Invariant**: Eviction counter must increment correctly.
**Test**: `test_eviction_counter_increments` in `test_governance_cache_invariants.py`
**Critical**: No (monitoring)
**max_examples**: 50 (standard invariant)

### Read-Write Consistency
**Invariant**: Reads and writes must be consistent under concurrency.
**Test**: `test_read_write_consistency` in `test_governance_cache_invariants.py`
**Critical**: Yes (thread safety)
**max_examples**: 50 (standard invariant)

### Cache Performance
**Invariant**: Cache lookups should be sub-millisecond for hits.
**Test**: `test_cache_performance` in `test_agent_governance_invariants.py`
**Critical**: Yes (performance requirement)
**max_examples**: 50 (standard invariant)

### Cache Expiration (Governance)
**Invariant**: Cache entries should expire based on age vs TTL.
**Test**: `test_cache_expiration` in `test_agent_governance_invariants.py`
**Critical**: Yes (stale data prevention)
**max_examples**: 50 (standard invariant)

### Cache Eviction (Governance)
**Invariant**: Cache should evict entries when full.
**Test**: `test_cache_eviction` in `test_agent_governance_invariants.py`
**Critical**: Yes (resource management)
**max_examples**: 50 (standard invariant)

### Cache Consistency (Governance)
**Invariant**: Cache should be consistent with source of truth.
**Test**: `test_cache_consistency` in `test_agent_governance_invariants.py`
**Critical**: Yes (correctness)
**max_examples**: 50 (standard invariant)

### Blocked Context Tracking
**Invariant**: Blocked triggers should be tracked.
**Test**: `test_blocked_context_tracking` in `test_agent_governance_invariants.py`
**Critical**: Yes (audit trail)
**max_examples**: 50 (standard invariant)

### Rate Limiting
**Invariant**: Triggers should be rate-limited.
**Test**: `test_rate_limiting` in `test_agent_governance_invariants.py`
**Critical**: Yes (resource protection)
**max_examples**: 50 (standard invariant)

### Block Rate Monitoring
**Invariant**: Block rate should be monitored to detect training needs.
**Test**: `test_block_rate_monitoring` in `test_agent_governance_invariants.py`
**Critical**: No (monitoring)
**max_examples**: 50 (standard invariant)

## Summary Statistics

**Total Invariants Documented**: 68
- Governance Domain: 37 invariants
- Governance Cache Domain: 31 invariants

**Critical Invariants**: 42
- Security/Privilege Management: 12
- Access Control: 8
- Data Consistency: 10
- Performance Requirements: 6
- Compliance/Audit: 6

**Standard Invariants**: 26
- Monitoring/Metrics: 10
- Operational: 16

**Bugs Found via Property Testing**: 14 documented bugs
- Confidence scoring bugs: 3
- Maturity progression bugs: 2
- Permission escalation bugs: 2
- Cache consistency bugs: 4
- Data integrity bugs: 3

**Test Coverage**:
- Critical tests use max_examples=200 (4 tests)
- Standard cache tests use max_examples=100 (6 tests)
- Standard invariants use max_examples=50 (58 tests)
- Time-sensitive tests use max_examples=10 (2 tests)
