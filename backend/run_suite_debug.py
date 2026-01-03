import sys
import os
import pytest

# Add current directory to path
sys.path.append(os.getcwd())
print(f"Added {os.getcwd()} to sys.path")

results_file = "suite_results.txt"

with open(results_file, "w", encoding="utf-8") as f:
    # Redirect stdout/stderr to file
    sys.stdout = f
    sys.stderr = f
    
    print("Running Grey-Box Test Suite...")
    ret = pytest.main(["tests/grey_box", "-v"])
    print(f"\nFinal Exit Code: {ret}")

# Restore stdout to print confirmation
sys.stdout = sys.__stdout__
print("DONE")
