#!/bin/bash
# Phase 207 Coverage Aggregation Script
# Run tests individually to avoid SQLAlchemy import conflicts

echo "=== Phase 207 Coverage Aggregation ===" > /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
echo "Date: $(date)" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
echo "" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt

cd /Users/rushiparikh/projects/atom/backend

# Clear previous coverage data
rm -f .coverage
rm -f coverage.json

# Array of test files with their coverage targets
declare -a tests=(
  "tests/unit/api/test_reports.py:api.reports"
  "tests/unit/api/test_websocket_routes.py:api.websocket_routes"
  "tests/unit/api/test_workflow_analytics_routes.py:api.workflow_analytics_routes"
  "tests/unit/api/test_time_travel_routes.py:api.time_travel_routes"
  "tests/unit/api/test_onboarding_routes.py:api.onboarding_routes"
  "tests/unit/api/test_sales_routes.py:api.sales_routes"
  "tests/unit/core/test_lux_config.py:core.lux_config"
  "tests/unit/core/test_messaging_schemas.py:core.messaging_schemas"
  "tests/core/test_billing.py:core.billing"
  "tests/core/test_llm_service.py:core.llm_service"
  "tests/core/test_historical_learner.py:core.historical_learner"
  "tests/core/test_external_integration_service.py:core.external_integration_service"
  "tests/unit/tools/test_device_tool.py:tools.device_tool"
  "tests/unit/tools/test_browser_tool.py:tools.browser_tool"
  "tests/unit/tools/test_canvas_tool.py:tools.canvas_tool"
  "tests/unit/agent/test_agent_graduation_service_incremental.py:core.agent_graduation_service"
  "tests/unit/llm/test_byok_handler_incremental.py:core.llm.byok_handler"
)

echo "Running coverage for all Phase 207 tests..."
echo "" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt

# Run each test individually
total_passed=0
total_failed=0
for test_entry in "${tests[@]}"; do
  IFS=':' read -r test_file coverage_target <<< "$test_entry"
  echo "Running: $test_file (coverage: $coverage_target)"

  # Run test with coverage
  PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest "$test_file" \
    --cov="$coverage_target" \
    --cov-branch \
    --cov-report=term-missing \
    --cov-report=json:coverage_${test_file//\//_}.json \
    -v 2>&1 | tee -a /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_run_individual.log

  # Check pass/fail
  result=${PIPESTATUS[0]}
  if [ $result -eq 0 ]; then
    ((total_passed++))
  else
    ((total_failed++))
  fi

  # Append coverage data to main JSON
  if [ -f "coverage_${test_file//\//_}.json" ]; then
    # Merge coverage data (simplified approach)
    cat "coverage_${test_file//\//_}.json" >> coverage_all.json.tmp
  fi

  echo "" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
done

# Generate combined coverage report
echo "" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
echo "=== Coverage Summary ===" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt

# Count tests
echo "" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
echo "=== Test Summary ===" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
echo "Test files passed: $total_passed" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
echo "Test files failed: $total_failed" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt

echo "" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
echo "=== Coverage Complete ===" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt

# Extract individual coverage percentages
echo "" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
echo "=== Individual Module Coverage ===" >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt
grep -A 5 "coverage:" /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_run_individual.log | grep -E "^[a-z_]+\." | awk '{print $1, $NF}' >> /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt

echo "Coverage aggregation complete!"
echo "Results saved to: /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_aggregation.txt"
echo "Detailed log: /Users/rushiparikh/projects/atom/.planning/phases/207-coverage-quality-push/coverage_run_individual.log"
