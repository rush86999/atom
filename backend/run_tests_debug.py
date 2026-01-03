import sys
import os
import pytest

# Add current directory to path
sys.path.append(os.getcwd())
print(f"Added {os.getcwd()} to sys.path")

# Run pytest
try:
    ret = pytest.main(["tests/grey_box/test_schema_contracts.py", "-v"])
    print(f"Pytest return code: {ret}")
except Exception as e:
    print(f"Error running pytest: {e}")
