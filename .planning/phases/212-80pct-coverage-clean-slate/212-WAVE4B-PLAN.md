---
phase: 212-80pct-coverage-clean-slate
plan: WAVE4B
type: execute
wave: 4
depends_on: ["212-WAVE3A", "212-WAVE3B", "212-WAVE3C"]
files_modified:
  - backend/tests/test_edge_cases.py
  - mobile/src/navigation/__tests__/DeepLinks.test.tsx
  - desktop-app/src-tauri/tests/file_operations_test.rs
  - backend/tests/test_integration_gaps.py
autonomous: true

must_haves:
  truths:
    - "Edge cases covered (timeouts, retries, errors, empty inputs, concurrent access)"
    - "Mobile deep links tested"
    - "Desktop file operations tested"
    - "Integration gaps covered (WebSocket, LanceDB, Redis, S3/R2)"
    - "Overall coverage: 60%+ weighted average"
  artifacts:
    - path: "backend/tests/test_edge_cases.py"
      provides: "Tests for edge cases and error paths"
      min_lines: 300
      exports: ["TestTimeouts", "TestRetries", "TestEmptyInputs", "TestConcurrentAccess"]
    - path: "mobile/src/navigation/__tests__/DeepLinks.test.tsx"
      provides: "React Native tests for deep linking"
      min_lines: 150
      exports: ["test_agent_deep_link", "test_workflow_deep_link"]
    - path: "desktop-app/src-tauri/tests/file_operations_test.rs"
      provides: "Rust tests for file operations"
      min_lines: 200
      exports: ["test_file_read", "test_file_write"]
    - path: "backend/tests/test_integration_gaps.py"
      provides: "Tests for integration gaps"
      min_lines: 250
      exports: ["TestWebSocketIntegration", "TestLanceDBIntegration"]
  key_links:
    - from: "backend/tests/test_edge_cases.py"
      to: "backend/core/**/*.py"
      via: "Edge case coverage for all services"
    - from: "backend/tests/test_integration_gaps.py"
      to: "backend/integrations/**/*.py"
      via: "Integration testing for external services"
---

<objective>
Finalize coverage with edge case testing, platform gap closure, and integration validation.

Purpose: Edge cases expose hidden failures. Platform gaps ensure mobile/desktop completeness. Integration gaps validate external service connections.

Output: 4 test files with 900+ total lines, achieving 60%+ overall coverage (realistic weighted average).
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md

# Edge Cases to Cover
- Timeouts (all async operations)
- Retries (transient failures)
- Empty inputs (all APIs)
- Null/None handling
- Concurrent access
- Resource exhaustion
- Network failures
- Malformed inputs

# Integration Gaps
- WebSocket integration
- LanceDB integration
- Redis integration
- S3/R2 integration

# Platform Gaps
- Mobile deep links (atom:// protocol)
- Desktop file operations
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create edge case tests</name>
  <files>backend/tests/test_edge_cases.py</files>
  <action>
Create backend/tests/test_edge_cases.py for edge case coverage:

1. Imports: pytest, asyncio

2. Class TestTimeouts:
   - test_llm_timeout(): LLM request times out
   - test_db_query_timeout(): DB query times out
   - test_external_api_timeout(): External API times out
   - test_timeout_handling(): Timeout handled gracefully
   - test_timeout_does_not_crash(): Service continues after timeout

3. Class TestRetries:
   - test_retry_on_transient_error(): Retries on 5xx
   - test_retry_on_network_error(): Retries on network error
   - test_no_retry_on_auth_error(): No retry on 401
   - test_retry_exhaustion(): Fails after max retries
   - test_retry_with_backoff(): Exponential backoff works

4. Class TestEmptyInputs:
   - test_empty_prompt(): Handles empty LLM prompt
   - test_empty_query(): Handles empty search query
   - test_empty_list(): Handles empty list inputs
   - test_none_handling(): Handles None values
   - test_empty_string(): Handles empty string

5. Class TestConcurrentAccess:
   - test_concurrent_writes(): Handles concurrent writes
   - test_concurrent_reads(): Handles concurrent reads
   - test_race_condition(): No race conditions
   - test_lock_contention(): Handles lock contention

6. Class TestResourceExhaustion:
   - test_memory_limit(): Handles memory limit
   - test_rate_limit(): Handles rate limiting
   - test_connection_pool_exhausted(): Handles pool exhaustion
   - test_disk_full(): Handles disk full

7. Class TestNetworkFailures:
   - test_connection_refused(): Handles connection refused
   - test_dns_failure(): Handles DNS failure
   - test_timeout(): Handles timeout
   - test_partial_response(): Handles partial response

8. Class TestMalformedInputs:
   - test_invalid_json(): Handles invalid JSON
   - test_invalid_xml(): Handles invalid XML
   - test_invalid_utf8(): Handles invalid UTF-8
   - test_truncated_data(): Handles truncated data

9. Mock time, network, resources
  </action>
  <verify>
pytest backend/tests/test_edge_cases.py -v
# All edge case tests should pass
  </verify>
  <done>
All edge case tests passing
  </done>
</task>

<task type="auto">
  <name>Task 2: Create mobile deep link tests</name>
  <files>mobile/src/navigation/__tests__/DeepLinks.test.tsx</files>
  <action>
Create mobile/src/navigation/__tests__/DeepLinks.test.tsx:

1. Test deep link handling:
   - test_agent_deep_link(): Handles atom://agent/{id}
   - test_workflow_deep_link(): Handles atom://workflow/{id}
   - test_canvas_deep_link(): Handles atom://canvas/{id}
   - test_tool_deep_link(): Handles atom://tool/{name}
   - test_invalid_deep_link(): Handles invalid links
   - test_deep_link_with_params(): Parses query params
   - test_deep_link_navigation(): Navigates to correct screen

2. Use @testing-library/react-native

3. Mock React Navigation deep linking
  </action>
  <verify>
cd mobile && npm test -- DeepLinks.test.tsx --coverage
# Mobile deep link coverage should improve
  </verify>
  <done>
All mobile deep link tests passing
  </done>
</task>

<task type="auto">
  <name>Task 3: Create desktop file operation tests</name>
  <files>desktop-app/src-tauri/tests/file_operations_test.rs</files>
  <action>
Create desktop-app/src-tauri/tests/file_operations_test.rs:

1. Test file operations:
   #[test]
   fn test_file_read() {
       // Test file reading
   }

   #[test]
   fn test_file_write() {
       // Test file writing
   }

   #[test]
   fn test_file_exists() {
       // Test file existence check
   }

   #[test]
   fn test_directory_operations() {
       // Test directory create/list/delete
   }

   #[test]
   fn test_file_permissions() {
       // Test permission checks
   }

   #[test]
   fn test_error_handling() {
       // Test error cases (not found, permission denied)
   }

   #[test]
   fn test_file_paths() {
       // Test path handling (relative, absolute)
   }

2. Use cargo test, tarpaulin for coverage
  </action>
  <verify>
cd desktop-app/src-tauri && cargo test
cd desktop-app/src-tauri && cargo tarpaulin --out Html
# Rust file operations coverage should improve
  </verify>
  <done>
All desktop file operation tests passing
  </done>
</task>

<task type="auto">
  <name>Task 4: Create integration gap closure tests</name>
  <files>backend/tests/test_integration_gaps.py</files>
  <action>
Create backend/tests/test_integration_gaps.py for remaining integration gaps:

1. Test WebSocket integration:
   - test_websocket_connection(): WebSocket connects
   - test_websocket_reconnect(): WebSocket reconnects
   - test_websocket_message(): WebSocket sends/receives messages
   - test_websocket_error(): WebSocket error handling
   - test_websocket_auth(): WebSocket authentication

2. Test LanceDB integration:
   - test_lancedb_connection(): LanceDB connects
   - test_lancedb_insert(): LanceDB inserts vectors
   - test_lancedb_search(): LanceDB vector search
   - test_lancedb_delete(): LanceDB deletes vectors
   - test_lancedb_batch(): LanceDB batch operations

3. Test Redis integration:
   - test_redis_connection(): Redis connects
   - test_redis_set(): Redis sets value
   - test_redis_get(): Redis gets value
   - test_redis_expire(): Redis expires keys
   - test_redis_pubsub(): Redis pub/sub

4. Test S3/R2 integration:
   - test_storage_upload(): Uploads file
   - test_storage_download(): Downloads file
   - test_storage_exists(): Checks existence
   - test_storage_delete(): Deletes file
   - test_storage_presigned_url(): Generates presigned URL

5. Mock external services where not available
  </action>
  <verify>
pytest backend/tests/test_integration_gaps.py -v
# All integration gap tests should pass
  </verify>
  <done>
All integration gap tests passing
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all edge case tests:
   pytest backend/tests/test_edge_cases.py -v

2. Run mobile deep link tests:
   cd mobile && npm test -- DeepLinks.test.tsx --coverage

3. Run desktop file operation tests:
   cd desktop-app/src-tauri && cargo test

4. Run integration gap tests:
   pytest backend/tests/test_integration_gaps.py -v

5. Verify overall coverage:
   pytest backend/tests/ --cov=core --cov=api --cov=tools --cov-report=json
   # Backend should be 80%+

6. Verify overall coverage weighted average:
   # Backend 80%+ x Frontend 45%+ x Mobile 40%+ x Desktop 40%+ = 60%+ weighted
</verification>

<success_criteria>
1. All edge case tests pass
2. All mobile deep link tests pass
3. All desktop file operation tests pass
4. All integration gap tests pass
5. Backend coverage >= 80%
6. Frontend coverage >= 45%
7. Mobile coverage >= 40%
8. Desktop coverage >= 40%
9. Overall coverage >= 60% (weighted average)
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE4B-SUMMARY.md` and `212-COMPLETE.md`
</output>
