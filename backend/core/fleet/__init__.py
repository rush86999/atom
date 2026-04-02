"""
Fleet package for multi-agent fleet coordination.

This package provides data types and utilities for fleet task management.
"""

from .fleet_task_types import (
    FailurePolicy,
    FleetTaskType,
    DEFAULT_FAILURE_POLICIES
)

__all__ = [
    "FailurePolicy",
    "FleetTaskType",
    "DEFAULT_FAILURE_POLICIES",
]
