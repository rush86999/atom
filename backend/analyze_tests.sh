#!/bin/bash
# Analyze all failing property tests

echo "=== Phase 306-01: Test Failure Analysis ===" > /tmp/test_analysis.txt
echo "" >> /tmp/test_analysis.txt

tests=(
  "test_post_agents_returns_422_on_invalid_input"
  "test_delete_agents_id_returns_204_on_success"
  "test_post_agents_rejects_empty_name"
  "test_post_agents_rejects_invalid_maturity"
  "test_post_agents_requires_non_empty_capabilities"
  "test_get_agents_id_rejects_invalid_uuid"
  "test_post_workflows_requires_name_field"
  "test_post_canvas_requires_type_field"
  "test_post_workflows_returns_workflow_with_status_field"
  "test_get_canvas_id_returns_canvas_data_structure"
  "test_get_agents_id_returns_403_for_non_owned_agents"
  "test_post_agents_handles_extra_fields_gracefully"
  "test_get_agents_handles_pagination"
  "test_post_agents_handles_large_payloads"
)

for test in "${tests[@]}"; do
  echo "## Test: $test" >> /tmp/test_analysis.txt
  PYTHONPATH=. pytest "tests/property_tests/test_api_invariants.py" -k "$test" -v --tb=line 2>&1 | grep -E "AssertionError|Expected|got|Error:" | head -10 >> /tmp/test_analysis.txt
  echo "" >> /tmp/test_analysis.txt
done

cat /tmp/test_analysis.txt
