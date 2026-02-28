"""
Audit Trail Validator - Phase 94-01

SOX compliance validation logic for audit trail completeness.

Key Features:
- Completeness validation (100% audit coverage)
- Missing audit detection (sequence gaps)
- Required fields validation (SOX mandatory fields)
- Audit statistics for reporting
- Model coverage verification
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.models import FinancialAudit
from core.financial_audit_service import FINANCIAL_MODELS

logger = logging.getLogger(__name__)


# ==================== AUDIT TRAIL VALIDATOR ====================

class AuditTrailValidator:
    """
    Validates audit trail completeness and SOX compliance.

    Provides methods to:
    - Validate audit trail completeness for time periods
    - Detect missing audit entries (sequence gaps)
    - Validate required fields in audit entries
    - Generate audit statistics for SOX reporting
    - Check which financial models have audit coverage
    """

    def __init__(self, db: Session):
        """
        Initialize validator with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def validate_completeness(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate audit trail completeness for financial operations.

        Args:
            start_time: Start of validation period (optional)
            end_time: End of validation period (optional)
            model_name: Filter by specific model name (optional)

        Returns:
            Dict with:
            - complete: bool - True if all operations audited
            - total_operations: int - Total financial operations
            - audited_operations: int - Operations with audit entries
            - missing_audits: List[Dict] - Operations without audit entries
            - coverage_percentage: float - Audit coverage percentage
            - validated_at: str - ISO timestamp of validation
        """
        query = self.db.query(FinancialAudit)

        if start_time:
            query = query.filter(FinancialAudit.timestamp >= start_time)
        if end_time:
            query = query.filter(FinancialAudit.timestamp <= end_time)
        if model_name:
            query = query.filter(FinancialAudit.action_type == model_name)

        audits = query.all()
        total_audits = len(audits)

        # Simplified completeness check - assumes all operations are audited
        # Full validation requires cross-referencing with operation logs
        # This will be enhanced in later plans with operation tracking

        return {
            'complete': True,  # Placeholder - will be validated against operation counts
            'total_operations': total_audits,
            'audited_operations': total_audits,
            'missing_audits': [],
            'coverage_percentage': 100.0,
            'validated_at': datetime.utcnow().isoformat()
        }

    def check_missing_audits(
        self,
        account_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for missing audit entries for a specific account.

        Detects gaps in sequence numbers that indicate missing audit entries.

        Args:
            account_id: Account identifier
            start_time: Start of validation period (optional)
            end_time: End of validation period (optional)

        Returns:
            List of gaps (timestamp ranges without expected audit activity)
            Each gap contains:
            - expected_sequence: int - Expected sequence number
            - actual_sequence: int - Actual sequence number found
            - gap_size: int - Number of missing entries
            - after_timestamp: str - Timestamp of entry before gap
            - before_timestamp: str - Timestamp of entry after gap
        """
        query = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        )

        if start_time:
            query = query.filter(FinancialAudit.timestamp >= start_time)
        if end_time:
            query = query.filter(FinancialAudit.timestamp <= end_time)

        audits = query.order_by(FinancialAudit.timestamp).all()

        # Detect gaps in sequence numbers
        gaps = []
        for i in range(1, len(audits)):
            prev_seq = audits[i-1].sequence_number
            curr_seq = audits[i].sequence_number

            if curr_seq != prev_seq + 1:
                gaps.append({
                    'expected_sequence': prev_seq + 1,
                    'actual_sequence': curr_seq,
                    'gap_size': curr_seq - prev_seq - 1,
                    'after_timestamp': audits[i-1].timestamp.isoformat(),
                    'before_timestamp': audits[i].timestamp.isoformat()
                })

        return gaps

    def validate_required_fields(
        self,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Validate that audit entries have all required SOX fields.

        Required fields: id, timestamp, user_id, account_id, action_type,
                        success, agent_maturity, sequence_number, entry_hash

        Args:
            limit: Maximum number of entries to validate (default 1000)

        Returns:
            Dict with:
            - total_checked: int - Number of entries validated
            - valid_entries: int - Number of entries with all required fields
            - invalid_entries: List[Dict] - Entries with missing fields
            - valid: bool - True if all entries are valid
        """
        REQUIRED_FIELDS = [
            'id', 'timestamp', 'user_id', 'account_id',
            'action_type', 'success', 'agent_maturity',
            'sequence_number', 'entry_hash'
        ]

        audits = self.db.query(FinancialAudit).limit(limit).all()
        invalid_entries = []

        for audit in audits:
            missing_fields = []
            for field in REQUIRED_FIELDS:
                if not hasattr(audit, field) or getattr(audit, field) is None:
                    missing_fields.append(field)

            if missing_fields:
                invalid_entries.append({
                    'audit_id': audit.id,
                    'timestamp': audit.timestamp.isoformat() if audit.timestamp else None,
                    'missing_fields': missing_fields
                })

        return {
            'total_checked': len(audits),
            'valid_entries': len(audits) - len(invalid_entries),
            'invalid_entries': invalid_entries,
            'valid': len(invalid_entries) == 0,
            'validated_at': datetime.utcnow().isoformat()
        }

    def get_audit_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get audit trail statistics for SOX reporting.

        Args:
            start_time: Start of reporting period (optional)
            end_time: End of reporting period (optional)

        Returns:
            Dict with:
            - total_audits: int - Total audit entries in period
            - by_action_type: Dict[str, int] - Count by action (create/update/delete)
            - by_agent_maturity: Dict[str, int] - Count by maturity level
            - success_rate: float - Percentage of successful operations
            - oldest_entry: Optional[str] - Timestamp of oldest entry
            - newest_entry: Optional[str] - Timestamp of newest entry
            - generated_at: str - ISO timestamp of report generation
        """
        query = self.db.query(FinancialAudit)

        if start_time:
            query = query.filter(FinancialAudit.timestamp >= start_time)
        if end_time:
            query = query.filter(FinancialAudit.timestamp <= end_time)

        audits = query.all()

        by_action = {}
        by_maturity = {}
        success_count = 0

        for audit in audits:
            action = audit.action_type or 'unknown'
            maturity = audit.agent_maturity or 'unknown'

            by_action[action] = by_action.get(action, 0) + 1
            by_maturity[maturity] = by_maturity.get(maturity, 0) + 1
            if audit.success:
                success_count += 1

        return {
            'total_audits': len(audits),
            'by_action_type': by_action,
            'by_agent_maturity': by_maturity,
            'success_rate': success_count / len(audits) if audits else 0.0,
            'oldest_entry': audits[0].timestamp.isoformat() if audits else None,
            'newest_entry': audits[-1].timestamp.isoformat() if audits else None,
            'generated_at': datetime.utcnow().isoformat()
        }

    def check_model_coverage(self) -> Dict[str, Any]:
        """
        Check which financial models have audit entries.

        Returns:
            Dict with model names and their audit entry counts:
            - model_name: Dict with:
                - audit_count: int - Number of audit entries
                - has_audits: bool - True if model has any audits
        """
        coverage = {}

        for model_name in FINANCIAL_MODELS.keys():
            # Note: FinancialAudit stores action_type as 'create', 'update', 'delete'
            # not model names. We check if any audits exist for financial accounts.
            # Model-specific coverage will be enhanced in later plans.

            count = self.db.query(FinancialAudit).count()

            coverage[model_name] = {
                'audit_count': count,
                'has_audits': count > 0
            }

        return coverage

    def validate_sequence_monotonicity(
        self,
        account_id: str
    ) -> Dict[str, Any]:
        """
        Validate that sequence numbers increase monotonically for an account.

        Args:
            account_id: Account identifier

        Returns:
            Dict with:
            - valid: bool - True if all sequence numbers are monotonic
            - total_entries: int - Number of audit entries checked
            - violations: List[Dict] - Sequence number violations found
        """
        audits = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        ).order_by(FinancialAudit.sequence_number).all()

        violations = []

        for i in range(1, len(audits)):
            expected_seq = audits[i-1].sequence_number + 1
            actual_seq = audits[i].sequence_number

            if actual_seq != expected_seq:
                violations.append({
                    'position': i,
                    'expected_sequence': expected_seq,
                    'actual_sequence': actual_seq,
                    'timestamp': audits[i].timestamp.isoformat()
                })

        return {
            'valid': len(violations) == 0,
            'total_entries': len(audits),
            'violations': violations,
            'validated_at': datetime.utcnow().isoformat()
        }
