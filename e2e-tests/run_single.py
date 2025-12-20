import sys
import json
sys.path.insert(0, '.')

from config.test_config import TestConfig
from tests.test_error_handling import run_tests as run_error_handling
from tests.test_complex_workflows import run_tests as run_complex_workflows

config = TestConfig()
print("Running error handling tests...")
results = run_error_handling(config)
print(json.dumps(results, indent=2))

print("\nRunning complex workflows tests...")
results2 = run_complex_workflows(config)
print(json.dumps(results2, indent=2))