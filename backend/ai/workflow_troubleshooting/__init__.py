"""
Workflow Automation Troubleshooting AI System

A comprehensive AI-powered system for diagnosing and resolving workflow automation issues.
Provides intelligent troubleshooting, monitoring, and alerting capabilities.
"""

from .diagnostic_analyzer import (
    AIDiagnosticAnalyzer,
    DiagnosticFinding,
    DiagnosticPattern,
)
from .monitoring_system import (
    MonitoringRule,
    WorkflowAlert,
    WorkflowMetric,
    WorkflowMonitoringSystem,
)
from .troubleshooting_api import router as troubleshooting_router
from .troubleshooting_engine import (
    IssueCategory,
    IssueSeverity,
    TroubleshootingSession,
    TroubleshootingStep,
    WorkflowIssue,
    WorkflowTroubleshootingEngine,
)

__all__ = [
    # Core troubleshooting engine
    "WorkflowTroubleshootingEngine",
    "TroubleshootingSession",
    "WorkflowIssue",
    "IssueCategory",
    "IssueSeverity",
    "TroubleshootingStep",
    # API components
    "troubleshooting_router",
    # AI diagnostic components
    "AIDiagnosticAnalyzer",
    "DiagnosticFinding",
    "DiagnosticPattern",
    # Monitoring and alerting
    "WorkflowMonitoringSystem",
    "WorkflowAlert",
    "WorkflowMetric",
    "MonitoringRule",
]

__version__ = "1.0.0"
__author__ = "ATOM Platform Team"
__description__ = "AI-Powered Workflow Automation Troubleshooting System"
