"""
Bug Discovery Core Services

This module provides unified access to all bug discovery core services:
- DiscoveryCoordinator: Orchestrates all discovery methods
- ResultAggregator: Normalizes results from all methods
- BugDeduplicator: Deduplicates bugs by error signature
- SeverityClassifier: Classifies bug severity
- DashboardGenerator: Generates weekly reports
"""

from tests.bug_discovery.core.discovery_coordinator import (
    DiscoveryCoordinator,
    run_discovery
)
from tests.bug_discovery.core.result_aggregator import ResultAggregator
from tests.bug_discovery.core.bug_deduplicator import BugDeduplicator
from tests.bug_discovery.core.severity_classifier import SeverityClassifier
from tests.bug_discovery.core.dashboard_generator import DashboardGenerator

__all__ = [
    "DiscoveryCoordinator",
    "run_discovery",
    "ResultAggregator",
    "BugDeduplicator",
    "SeverityClassifier",
    "DashboardGenerator",
]
