"""
E2E UI Page Objects module.

This module exports all Page Object classes for use in tests.
"""

from .page_objects import (
    BasePage,
    LoginPage,
    DashboardPage,
    ProjectsPage,
    ChatPage,
    ExecutionHistoryPage,
    SkillsMarketplacePage,
    SkillInstallationPage,
    SkillConfigPage,
    SkillExecutionPage,
)

# Cross-platform page objects
from .cross_platform_objects import (
    SharedWorkflowPage,
    FeatureParityPage,
)

__all__ = [
    # Base page objects
    "BasePage",
    "LoginPage",
    "DashboardPage",
    "ProjectsPage",
    "ChatPage",
    "ExecutionHistoryPage",
    "SkillsMarketplacePage",
    "SkillInstallationPage",
    "SkillConfigPage",
    "SkillExecutionPage",
    # Cross-platform page objects
    "SharedWorkflowPage",
    "FeatureParityPage",
]
