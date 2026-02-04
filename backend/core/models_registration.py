
"""
Central registration point for all SQLAlchemy models to prevent circular dependencies.
"""
import accounting.models
import service_delivery.models

# 2. Import all models to ensure they are registered with the Base
import core.models

# 1. Base should be imported first
from core.database import Base

# Add other model modules as they are created

# 3. Export Base for convenience
__all__ = ["Base"]
