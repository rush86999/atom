"""
Billing module wrapper for backward compatibility.

This module provides a compatibility layer for imports from core.billing.
The actual implementation is in core.billing_orchestrator.
"""

from core.billing_orchestrator import billing_orchestrator

# Export billing_orchestrator as billing_service for backward compatibility
billing_service = billing_orchestrator

__all__ = ['billing_service']
