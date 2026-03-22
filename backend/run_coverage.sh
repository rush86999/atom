#!/bin/bash
PYTHONPATH=/Users/rushiparikh/projects/atom/backend python3 -m pytest \
  tests/core/test_workflow_engine_coverage.py \
  tests/core/test_workflow_engine_path_coverage.py \
  tests/core/test_atom_agent_endpoints_core.py \
  --cov=core.workflow_engine \
  --cov=core.atom_agent_endpoints \
  --cov-report=json \
  --cov-report=term \
  -q

echo ""
echo "=== COVERAGE SUMMARY ==="
python3 << 'EOF'
import json
try:
    with open('coverage.json') as f:
        data = json.load(f)
        
        if 'core/workflow_engine.py' in data['files']:
            we = data['files']['core/workflow_engine.py']
            print(f"\nworkflow_engine.py: {we['summary']['percent_covered']:.2f}%")
            print(f"  Lines: {we['summary']['covered_lines']}/{we['summary']['num_statements']}")
        
        if 'core/atom_agent_endpoints.py' in data['files']:
            ae = data['files']['core/atom_agent_endpoints.py']
            print(f"\natom_agent_endpoints.py: {ae['summary']['percent_covered']:.2f}%")
            print(f"  Lines: {ae['summary']['covered_lines']}/{ae['summary']['num_statements']}")
except Exception as e:
    print(f"Error reading coverage: {e}")
EOF
