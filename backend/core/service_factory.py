"""
Service Factory for Atom Platform

Provides centralized service instantiation to eliminate code duplication.
Ensures efficient resource management and consistent service configuration.
"""

import logging
import threading
from typing import Dict, Optional
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.agent_context_resolver import AgentContextResolver
from core.governance_cache import GovernanceCache

logger = logging.getLogger(__name__)


class ServiceFactory:
    """
    Centralized factory for creating and managing service instances.

    Uses thread-local storage to ensure thread safety while allowing
    service instance reuse within a single thread/request context.

    Example:
        # In API routes
        @router.post("/agent/{agent_id}/execute")
        async def execute_agent(agent_id: str, db: Session = Depends(get_db)):
            governance = ServiceFactory.get_governance_service(db)
            can_execute = governance.can_execute_action(agent_id, 3)

        # In core services
        def process_agent_request(agent_id: str, db: Session):
            resolver = ServiceFactory.get_context_resolver(db)
            context = resolver.resolve_context(agent_id)
    """

    # Thread-local storage for service instances
    _thread_local = threading.local()

    # Global singletons (thread-safe services)
    _governance_cache: Optional[GovernanceCache] = None
    _cache_lock = threading.Lock()

    @classmethod
    def get_governance_service(cls, db: Session) -> AgentGovernanceService:
        """
        Get or create an AgentGovernanceService instance.

        Args:
            db: Database session

        Returns:
            AgentGovernanceService instance
        """
        if not hasattr(cls._thread_local, 'governance_service'):
            cls._thread_local.governance_service = AgentGovernanceService(db)
        return cls._thread_local.governance_service

    @classmethod
    def get_context_resolver(cls, db: Session) -> AgentContextResolver:
        """
        Get or create an AgentContextResolver instance.

        Args:
            db: Database session

        Returns:
            AgentContextResolver instance
        """
        if not hasattr(cls._thread_local, 'context_resolver'):
            cls._thread_local.context_resolver = AgentContextResolver(db)
        return cls._thread_local.context_resolver

    @classmethod
    def get_governance_cache(cls) -> GovernanceCache:
        """
        Get or create the global GovernanceCache instance.

        The cache is a singleton since it's thread-safe and shared
        across all requests.

        Returns:
            GovernanceCache instance
        """
        if cls._governance_cache is None:
            with cls._cache_lock:
                # Double-check locking pattern
                if cls._governance_cache is None:
                    cls._governance_cache = GovernanceCache()
                    logger.info("Initialized global GovernanceCache")
        return cls._governance_cache

    @classmethod
    def clear_thread_local(cls):
        """
        Clear thread-local service instances.

        Should be called at the end of each request to prevent memory leaks.
        This is particularly important for long-running server processes.

        Example:
            # In FastAPI middleware
            @app.middleware("http")
            async def clear_services(request: Request, call_next):
                response = await call_next(request)
                ServiceFactory.clear_thread_local()
                return response
        """
        if hasattr(cls._thread_local, 'governance_service'):
            delattr(cls._thread_local, 'governance_service')
        if hasattr(cls._thread_local, 'context_resolver'):
            delattr(cls._thread_local, 'context_resolver')


class GovernanceServiceFactory:
    """
    Legacy factory for governance services.

    DEPRECATED: Use ServiceFactory.get_governance_service() instead.
    This class is maintained for backward compatibility.

    Example:
        # Old way (deprecated)
        governance = GovernanceServiceFactory.create(db)

        # New way (recommended)
        governance = ServiceFactory.get_governance_service(db)
    """

    _instances: Dict[int, AgentGovernanceService] = {}
    _lock = threading.Lock()

    @staticmethod
    def create(db: Session) -> AgentGovernanceService:
        """
        Create or reuse governance service instance for current thread.

        DEPRECATED: Use ServiceFactory.get_governance_service() instead.

        Args:
            db: Database session

        Returns:
            AgentGovernanceService instance
        """
        thread_id = threading.current_thread().ident
        if thread_id not in GovernanceServiceFactory._instances:
            with GovernanceServiceFactory._lock:
                # Double-check locking
                if thread_id not in GovernanceServiceFactory._instances:
                    GovernanceServiceFactory._instances[thread_id] = AgentGovernanceService(db)
                    logger.debug(f"Created AgentGovernanceService for thread {thread_id}")

        return GovernanceServiceFactory._instances[thread_id]

    @staticmethod
    def clear_all():
        """
        Clear all cached governance service instances.

        DEPRECATED: Use ServiceFactory.clear_thread_local() instead.
        """
        GovernanceServiceFactory._instances.clear()
        logger.warning("Cleared all governance service instances (legacy factory)")


# Convenience functions for common service access patterns

def get_governance_service(db: Session) -> AgentGovernanceService:
    """
    Convenience function to get governance service.

    Args:
        db: Database session

    Returns:
        AgentGovernanceService instance

    Example:
        governance = get_governance_service(db)
        can_execute = governance.can_execute_action(agent_id, 2)
    """
    return ServiceFactory.get_governance_service(db)


def get_context_resolver(db: Session) -> AgentContextResolver:
    """
    Convenience function to get context resolver.

    Args:
        db: Database session

    Returns:
        AgentContextResolver instance

    Example:
        resolver = get_context_resolver(db)
        context = resolver.resolve_context(agent_id)
    """
    return ServiceFactory.get_context_resolver(db)


def get_governance_cache() -> GovernanceCache:
    """
    Convenience function to get governance cache.

    Returns:
        GovernanceCache instance (singleton)

    Example:
        cache = get_governance_cache()
        cached_result = cache.get_cached_result(agent_id, action)
    """
    return ServiceFactory.get_governance_cache()
