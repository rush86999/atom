#!/usr/bin/env python3
import re

with open('tests/integration/test_workflow_execution_integration.py', 'r') as f:
    content = f.read()

# Fix input_data to use JSON strings
content = re.sub(
    r'input_data=\{[^}]+\}',
    lambda m: m.group(0).replace('{', 'json.dumps({').replace('}', '})'),
    content
)

# Fix output_data to outputs
content = content.replace('.output_data =', '.outputs =')
content = content.replace('retrieved.output_data', 'json.loads(retrieved.outputs)')

# Fix input_data assertions
content = re.sub(
    r'retrieved\.input_data == (\{[^}]+\})',
    r'json.loads(retrieved.input_data) == \1',
    content
)

# Add json import if not present
if 'import json' not in content:
    content = content.replace('import pytest', 'import pytest\nimport json')

with open('tests/integration/test_workflow_execution_integration.py', 'w') as f:
    f.write(content)

print('Fixed JSON serialization in test file')
