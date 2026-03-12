"""
Test runner for episode service tests with accounting module workaround.

Patches core.models to remove duplicate accounting classes before running tests.
This avoids SQLAlchemy metadata conflicts.
"""

import sys
import os

# Set environment before any imports
os.environ["TESTING"] = "1"

# CRITICAL: Patch core.models BEFORE importing anything
# This prevents duplicate Transaction/JournalEntry/Account classes
import core.models as models_module

# Store references to original classes
original_classes = {}

# Find and temporarily remove accounting-related classes
accounting_classes = ['Account', 'Transaction', 'JournalEntry', 'CategorizationProposal']
for cls_name in accounting_classes:
    if hasattr(models_module, cls_name):
        original_classes[cls_name] = getattr(models_module, cls_name)
        delattr(models_module, cls_name)
        print(f"Temporarily removed {cls_name} from core.models")

# Now run pytest
import pytest

if __name__ == "__main__":
    sys.exit(pytest.main([
        "tests/integration/services/test_episode_services_coverage.py::TestEpisodeBoundaryDetection",
        "-v",
        "--tb=short",
        "--cov=core.episode_segmentation_service",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=json:tests/coverage_reports/metrics/backend_phase_166_segmentation.json"
    ]))
