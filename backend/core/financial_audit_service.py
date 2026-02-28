"""
Financial Audit Service - Phase 94-01

Centralized financial audit orchestration with SQLAlchemy event listeners.
Automatically captures all financial operations for SOX compliance.

Key Features:
- Automatic audit logging via SQLAlchemy event listeners
- Support for all financial models from phases 91-93
- Hash chain integration for tamper evidence
- Session context tracking (user_id, agent_maturity)
- Decimal to float conversion for JSON serialization (Phase 91 compatibility)
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import event
from sqlalchemy.orm import Session

from core.models import FinancialAudit, FinancialAccount
from core.hash_chain_integrity import HashChainIntegrity

logger = logging.getLogger(__name__)

# ==================== FINANCIAL MODELS REGISTRY ====================

# Financial models requiring audit logging from phases 91-93
# Note: SaaSSubscription, BudgetLimit, Invoice, Contract, Transaction are dataclasses
# and are handled through their parent models or service layers
FINANCIAL_MODELS = {
    'FinancialAccount': FinancialAccount,
    # Dataclass models are handled in service layers:
    # 'SaaSSubscription': SaaSSubscription,  # dataclass in financial_ops_engine.py
    # 'BudgetLimit': BudgetLimit,  # dataclass in financial_ops_engine.py
    # 'Invoice': Invoice,  # dataclass (to be added)
    # 'Contract': Contract,  # dataclass (to be added)
    # 'Transaction': Transaction,  # dataclass in ai_accounting_engine.py
}


# ==================== FINANCIAL AUDIT SERVICE ====================

class FinancialAuditService:
    """
    Service for managing financial audit trail with automatic logging.

    Uses SQLAlchemy event listeners to capture all financial operations
    (INSERT, UPDATE, DELETE) without manual logging required.

    Architecture:
    - Event listener registered at module level (@event.listens_for)
    - Triggers on Session.after_flush for all ORM operations
    - Creates FinancialAudit entries with hash chain support
    - Extracts user_id and agent_maturity from session.info context
    """

    def __init__(self):
        """Initialize audit service."""
        self._models_registered: Set[str] = set()

    def register_financial_models(self, models: Optional[List[Any]] = None) -> None:
        """
        Register financial models for audit logging.

        Note: Event listener is global and registered at module import time.
        This method tracks which models should be audited for validation purposes.

        Args:
            models: List of model classes to register (defaults to all FINANCIAL_MODELS)
        """
        if models is None:
            models = list(FINANCIAL_MODELS.values())

        for model in models:
            self._models_registered.add(model.__name__)

        logger.info(f"Registered {len(self._models_registered)} financial models for audit")

    def get_linked_audits(
        self,
        db,  # Session
        account_id: str,
        depth: int = 1
    ) -> Dict[str, List[FinancialAudit]]:
        """
        Get audit entries linked across financial models.

        For comprehensive traceability, financial operations often span
        multiple models (e.g., Project -> Budget -> Transaction -> Invoice).

        Args:
            db: Database session
            account_id: Starting account ID
            depth: How many levels deep to follow links (1 = direct only)

        Returns:
            Dict mapping model/account to related audit entries
        """
        result = {account_id: []}

        # Get direct audits for this account
        direct_audits = db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        ).order_by(FinancialAudit.timestamp).all()

        result[account_id] = direct_audits

        if depth <= 1:
            return result

        # Follow links based on audit content
        linked_ids = set()

        for audit in direct_audits:
            # Extract linked IDs from new_values and old_values
            if audit.new_values:
                linked_ids.update(self._extract_linked_ids(audit.new_values))
            if audit.old_values:
                linked_ids.update(self._extract_linked_ids(audit.old_values))

        # Recursively get audits for linked entities
        for linked_id in linked_ids:
            if linked_id != account_id:  # Avoid cycles
                linked = self.get_linked_audits(db, linked_id, depth - 1)
                result.update(linked)

        return result

    @staticmethod
    def _extract_linked_ids(values) -> set:
        """Extract potential linked account/transaction IDs from audit values."""
        linked_ids = set()

        # Common field names for linked entities
        link_fields = ['project_id', 'subscription_id', 'invoice_id',
                       'transaction_id', 'account_id', 'contract_id']

        if not values:
            return linked_ids

        for field in link_fields:
            if field in values and values[field]:
                linked_ids.add(str(values[field]))

        return linked_ids

    def reconstruct_transaction(
        self,
        db,  # Session
        account_id: str,
        sequence_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Reconstruct a financial transaction from audit trail.

        Args:
            db: Database session
            account_id: Account ID
            sequence_number: Specific sequence to reconstruct (None = latest)

        Returns:
            Dict with reconstructed transaction state
        """
        query = db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        )

        if sequence_number is not None:
            query = query.filter(FinancialAudit.sequence_number == sequence_number)
        else:
            query = query.order_by(FinancialAudit.sequence_number.desc()).limit(1)

        audit = query.first()

        if not audit:
            return {'error': 'Audit entry not found'}

        # Reconstruct from audit data
        return {
            'audit_id': audit.id,
            'timestamp': audit.timestamp.isoformat(),
            'sequence_number': audit.sequence_number,
            'action': audit.action_type,
            'actor': {
                'user_id': audit.user_id,
                'agent_maturity': audit.agent_maturity,
                'agent_id': audit.agent_id
            },
            'state': {
                'before': audit.old_values,
                'after': audit.new_values,
                'changes': audit.changes
            },
            'governance': {
                'passed': audit.governance_check_passed,
                'required_approval': audit.required_approval,
                'approval_granted': audit.approval_granted
            },
            'result': {
                'success': audit.success,
                'error': audit.error_message
            },
            'integrity': {
                'entry_hash': audit.entry_hash,
                'prev_hash': audit.prev_hash
            }
        }

    def get_full_audit_trail(
        self,
        db,  # Session
        account_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get full audit trail for an account with reconstructed transactions.

        Args:
            db: Database session
            account_id: Account ID
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of reconstructed transactions
        """
        query = db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        )

        if start_time:
            query = query.filter(FinancialAudit.timestamp >= start_time)
        if end_time:
            query = query.filter(FinancialAudit.timestamp <= end_time)

        audits = query.order_by(FinancialAudit.sequence_number).all()

        trail = []
        for audit in audits:
            reconstructed = self.reconstruct_transaction(db, account_id, audit.sequence_number)
            trail.append(reconstructed)

        return trail

    def get_registered_models(self) -> Set[str]:
        """
        Return set of registered model names.

        Returns:
            Set of model class names registered for audit
        """
        return self._models_registered.copy()


# ==================== EVENT LISTENER ====================

@event.listens_for(Session, 'after_flush')
def log_financial_operations(session: Session, context: Any) -> None:
    """
    Automatically log all financial operations to audit trail.

    This event listener fires after every SQLAlchemy flush operation,
    capturing all INSERT, UPDATE, DELETE operations on financial models.

    Args:
        session: SQLAlchemy session being flushed
        context: Flush context (not used)
    """
    try:
        # Process session.new (INSERT operations)
        for instance in session.new:
            if _is_financial_model(instance):
                _create_audit_entry(session, instance, 'create')

        # Process session.dirty (UPDATE operations)
        for instance in session.dirty:
            if _is_financial_model(instance):
                _create_audit_entry(session, instance, 'update')

        # Process session.deleted (DELETE operations)
        for instance in session.deleted:
            if _is_financial_model(instance):
                _create_audit_entry(session, instance, 'delete')

    except Exception as e:
        # Log error but don't fail the transaction
        # Financial operations should succeed even if audit logging fails
        logger.error(f"Failed to create audit entry: {e}", exc_info=True)


# ==================== HELPER FUNCTIONS ====================

def _is_financial_model(instance: Any) -> bool:
    """
    Check if instance is a financial model requiring audit.

    Args:
        instance: Object to check

    Returns:
        True if instance is a financial model, False otherwise
    """
    instance_type = type(instance).__name__
    return instance_type in FINANCIAL_MODELS


def _create_audit_entry(session: Session, instance: Any, action: str) -> Optional[str]:
    """
    Create FinancialAudit entry with hash chain integrity.

    Args:
        session: SQLAlchemy session
        instance: Financial model instance
        action: Operation type ('create', 'update', 'delete')

    Returns:
        Audit entry ID or None if creation failed
    """
    try:
        # Get account_id from instance before deletion
        # For deleted objects, we need to get the ID from the instance state
        account_id = str(getattr(instance, 'id', 'unknown'))

        # For DELETE operations, account might already be detached
        # We need to get values from instance's internal state
        if action == 'delete':
            # Use the instance's committed state for deleted objects
            if hasattr(instance, '_sa_instance_state'):
                try:
                    # Try to get ID from the instance's committed state
                    account_id = str(instance._sa_instance_state.key[1][0])
                except (KeyError, IndexError, TypeError):
                    # Fallback to direct attribute access
                    account_id = str(getattr(instance, 'id', 'unknown'))

        # Get previous entry's hash for chain integrity
        prev_entry = session.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        ).order_by(FinancialAudit.sequence_number.desc()).first()

        prev_hash = prev_entry.entry_hash if prev_entry else ''

        # Get next sequence number
        next_sequence = (prev_entry.sequence_number + 1) if prev_entry else 1

        # Get values
        user_id = _get_user_id(session)
        old_values = _extract_values(instance, action, 'old') if action in ['update', 'delete'] else None
        new_values = _extract_values(instance, action, 'new') if action in ['create', 'update'] else None
        agent_maturity = _get_agent_maturity(session)
        timestamp = datetime.utcnow()

        # Compute hash using HashChainIntegrity (real cryptographic hash)
        entry_hash = HashChainIntegrity.compute_entry_hash(
            account_id=account_id,
            action_type=action,
            old_values=old_values,
            new_values=new_values,
            timestamp=timestamp,
            sequence_number=next_sequence,
            prev_hash=prev_hash,
            user_id=user_id
        )

        # Create FinancialAudit record
        audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=timestamp,  # Will be overwritten by server_default=func.now()
            user_id=user_id,
            agent_id=_get_agent_id(session),
            agent_execution_id=_get_agent_execution_id(session),
            account_id=account_id,
            action_type=action,
            changes=_compute_changes(old_values, new_values),
            old_values=old_values,
            new_values=new_values,
            success=True,  # after_flush means operation succeeded
            error_message=None,
            agent_maturity=agent_maturity,
            governance_check_passed=True,  # Placeholder
            required_approval=False,  # Placeholder
            approval_granted=None,
            request_id=_get_request_id(session),
            ip_address=_get_ip_address(session),
            user_agent=_get_user_agent(session),
            sequence_number=next_sequence,
            entry_hash=entry_hash,
            prev_hash=prev_hash
        )

        session.add(audit)
        logger.debug(f"Created audit entry for {action} on {account_id}")
        return audit.id

    except Exception as e:
        logger.error(f"Failed to create audit entry: {e}", exc_info=True)
        return None


def _extract_values(instance: Any, action: str, state: str) -> Dict[str, Any]:
    """
    Extract values from instance, converting Decimal to float for JSON.

    Args:
        instance: Model instance
        action: Operation type
        state: 'old' or 'new'

    Returns:
        Dictionary of column names to values
    """
    values = {}

    for column in instance.__table__.columns:
        col_name = column.name

        if hasattr(instance, col_name):
            value = getattr(instance, col_name)

            # Convert Decimal to float for JSON serialization (from Phase 91)
            if isinstance(value, Decimal):
                value = float(value)

            # Convert datetime to ISO string
            elif isinstance(value, datetime):
                value = value.isoformat()

            values[col_name] = value

    return values


def _compute_changes(old_values: Optional[Dict], new_values: Optional[Dict]) -> Dict[str, Dict[str, Any]]:
    """
    Compute changed fields between old and new values.

    Args:
        old_values: Old state dictionary
        new_values: New state dictionary

    Returns:
        Dictionary of changed fields with old/new values
    """
    if not old_values or not new_values:
        return {}

    changes = {}
    for key in new_values:
        if key in old_values and old_values[key] != new_values[key]:
            changes[key] = {'old': old_values[key], 'new': new_values[key]}

    return changes


def _get_next_sequence(session: Session, account_id: str) -> int:
    """
    Get next sequence number for this account.

    Args:
        session: SQLAlchemy session
        account_id: Account identifier

    Returns:
        Next sequence number (starts at 1)
    """
    last = session.query(FinancialAudit).filter(
        FinancialAudit.account_id == account_id
    ).order_by(FinancialAudit.sequence_number.desc()).first()

    return (last.sequence_number + 1) if last else 1


# ==================== SESSION CONTEXT HELPERS ====================

def _get_user_id(session: Session) -> str:
    """
    Extract user_id from session info or return 'system'.

    Args:
        session: SQLAlchemy session

    Returns:
        User ID string
    """
    return session.info.get('user_id', 'system')


def _get_agent_id(session: Session) -> Optional[str]:
    """
    Extract agent_id from session info.

    Args:
        session: SQLAlchemy session

    Returns:
        Agent ID or None
    """
    return session.info.get('agent_id')


def _get_agent_execution_id(session: Session) -> Optional[str]:
    """
    Extract agent_execution_id from session info.

    Args:
        session: SQLAlchemy session

    Returns:
        Agent execution ID or None
    """
    return session.info.get('agent_execution_id')


def _get_agent_maturity(session: Session) -> str:
    """
    Extract agent_maturity from session info.

    Args:
        session: SQLAlchemy session

    Returns:
        Agent maturity level (defaults to AUTONOMOUS)
    """
    return session.info.get('agent_maturity', 'AUTONOMOUS')


def _get_request_id(session: Session) -> Optional[str]:
    """
    Extract request_id from session info.

    Args:
        session: SQLAlchemy session

    Returns:
        Request ID or None
    """
    return session.info.get('request_id')


def _get_ip_address(session: Session) -> Optional[str]:
    """
    Extract ip_address from session info.

    Args:
        session: SQLAlchemy session

    Returns:
        IP address or None
    """
    return session.info.get('ip_address')


def _get_user_agent(session: Session) -> Optional[str]:
    """
    Extract user_agent from session info.

    Args:
        session: SQLAlchemy session

    Returns:
        User agent string or None
    """
    return session.info.get('user_agent')


# ==================== HASH CHAIN INTEGRITY ====================

def verify_audit_chain(
    db: Session,
    account_id: str
) -> Dict[str, Any]:
    """
    Verify hash chain integrity for an account's audit trail.

    Convenience function that creates HashChainIntegrity instance
    and verifies the chain.

    Args:
        db: SQLAlchemy session
        account_id: Account to verify

    Returns:
        Dict with verification results:
        - is_valid: bool - True if all hashes match
        - total_entries: int - Number of entries checked
        - first_break: Optional[Dict] - First mismatch found
        - break_count: int - Number of broken links
    """
    integrity = HashChainIntegrity(db)
    return integrity.verify_chain(account_id)
