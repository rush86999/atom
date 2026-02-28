"""
Audit Immutable Guard - Phase 94-03

Application-level enforcement of FinancialAudit immutability.

This provides application-level enforcement as a fallback
when database triggers aren't available (e.g., SQLite in dev).

For production PostgreSQL environments, database triggers
provide the primary enforcement layer.

Key Features:
- SQLAlchemy before_flush event listener
- Prevents UPDATE and DELETE on FinancialAudit
- SOX immutability requirement enforcement
"""

import logging
from sqlalchemy import event
from sqlalchemy.orm import Session

from core.models import FinancialAudit

logger = logging.getLogger(__name__)


@event.listens_for(Session, 'before_flush')
def prevent_audit_modification(session, context):
    """
    Prevent modification or deletion of FinancialAudit records.

    This provides application-level enforcement as a fallback
    when database triggers aren't available (e.g., SQLite in dev).

    For production PostgreSQL environments, database triggers
    (see: alembic/versions/20260225_audit_immutable_trigger.py)
    provide the primary enforcement layer.

    Args:
        session: SQLAlchemy session
        context: Flush context

    Raises:
        AssertionError: If attempting to modify or delete FinancialAudit

    SOX Requirement:
        Section 802 requires audit records be immutable and tamper-evident
        for 7 years. This function enforces immutability at the application layer.
    """
    # Check for DELETE operations
    for instance in session.deleted:
        if isinstance(instance, FinancialAudit):
            audit_id = getattr(instance, 'id', 'unknown')
            raise AssertionError(
                f"Cannot delete FinancialAudit entry (SOX immutability requirement): {audit_id}"
            )

    # Check for UPDATE operations
    for instance in session.dirty:
        if isinstance(instance, FinancialAudit):
            audit_id = getattr(instance, 'id', 'unknown')
            raise AssertionError(
                f"Cannot modify FinancialAudit entry (SOX immutability requirement): {audit_id}"
            )

    logger.debug("Audit immutability guard: no violations detected")
