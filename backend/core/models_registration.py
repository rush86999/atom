
"""
Central registration point for all SQLAlchemy models to prevent circular dependencies.

IMPORTANT: Optional model modules (accounting, service_delivery, saas, ecommerce)
are conditionally imported to prevent recursion during test setup. They are only
imported when NOT in a testing environment to avoid heavy initialization.
"""
import os

# 1. Base should be imported first
from core.database import Base

# 2. Import all models to ensure they are registered with the Base
import core.models

# 3. Optional model modules - only import in production (NOT during tests)
# This prevents recursion during test initialization
TESTING = os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING")

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
