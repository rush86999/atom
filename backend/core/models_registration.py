
"""
Central registration point for all SQLAlchemy models to prevent circular dependencies.

IMPORTANT: Optional model modules (accounting, service_delivery, saas, ecommerce)
are conditionally imported to prevent recursion during test setup. They are only
imported when NOT in a testing environment to avoid heavy initialization.
"""
import os
import sys

# 1. Base should be imported first
from core.database import Base

# 2. Import all models to ensure they are registered with the Base
import core.models

# 3. Optional model modules - only import in production (NOT during tests)
# This prevents recursion during test initialization
# Check multiple indicators for test environment
def _is_testing():
    """Check if we're in a testing environment."""
    return (
        os.environ.get("PYTEST_CURRENT_TEST") is not None or
        os.environ.get("TESTING") is not None or
        "pytest" in sys.argv or
        "unittest" in sys.argv or
        sys.modules.get("pytest") is not None
    )

TESTING = _is_testing()

if not TESTING:
    try:
        import accounting.models
        import service_delivery.models
        import saas.models
        import ecommerce.models
    except ImportError:
        # Optional modules may not exist in all environments
        pass

# 4. Export Base for convenience
__all__ = ["Base"]
