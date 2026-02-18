#!/bin/bash
cd /Users/rushiparikh/projects/atom/backend
PYTHONPATH=. pytest tests/property_tests/workflows/test_workflow_engine_async_execution.py tests/integration/test_workflow_analytics_integration.py tests/integration/test_atom_agent_endpoints_expanded.py tests/unit/test_byok_handler_expanded.py tests/unit/test_canvas_tool_expanded.py tests/property_tests/governance/test_agent_governance_invariants.py --cov=. --cov-report=term --cov-report=json:tests/coverage_reports/metrics/coverage_full.json -v 2>&1 | tail -100
