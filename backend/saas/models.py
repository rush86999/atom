# Consolidated to core.models to prevent SQLAlchemy registry conflicts
try:
    from core.models import SaaSTier, UsageEvent
except ImportError:
    # Models not yet implemented
    SaaSTier = None
    UsageEvent = None
