"""
Chaos engineering fixtures.

Exports:
    - Memory pressure injection fixtures for heap exhaustion testing
    - Service crash simulation fixtures for LLM provider and Redis failures
    - Database connection drop fixtures for connection pool exhaustion testing
"""

from tests.chaos.fixtures.memory_chaos_fixtures import (
    MemoryPressureInjector,
    memory_pressure_injector,
    system_memory_monitor,
    heap_snapshot,
    memory_pressure_thresholds,
)
from tests.chaos.fixtures.database_chaos_fixtures import (
    database_connection_dropper,
    connection_pool_exhaustion,
    database_recovery_validator,
)

__all__ = [
    "MemoryPressureInjector",
    "memory_pressure_injector",
    "system_memory_monitor",
    "heap_snapshot",
    "memory_pressure_thresholds",
    "ServiceCrashSimulator",
    "llm_provider_crash_simulator",
    "redis_crash_simulator",
    "external_api_crash_simulator",
    "service_unavailable_response",
    "database_connection_dropper",
    "connection_pool_exhaustion",
    "database_recovery_validator",
]
