"""
Chronological Integrity Validator for Financial Audit Trails (AUD-02)

This module provides validation for SOX compliance requirement AUD-02:
"Chronological Integrity: Audit timestamps are monotonically increasing,
with no gaps in sequence numbers."

Key Features:
- Monotonic timestamp validation (no backward jumps)
- Sequence gap detection (no missing sequence numbers)
- Out-of-order detection (timestamp order matches sequence order)
- Time gap detection (unusual delays between entries)
- Comprehensive integrity check combining all validators

Usage:
    from core.chronological_integrity import ChronologicalIntegrityValidator
    from sqlalchemy.orm import Session

    validator = ChronologicalIntegrityValidator(db_session)
    result = validator.validate_integrity(account_id="acct-123")

    if not result['is_valid']:
        print(f"Violations: {result['monotonicity']['violations']}")
        print(f"Gaps: {result['sequence_gaps']['gaps']}")
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from core.models import FinancialAudit

logger = logging.getLogger(__name__)


class ChronologicalIntegrityValidator:
    """
    Validates chronological integrity of audit trails (AUD-02).

    SOX compliance requires that audit records maintain chronological integrity:
    1. Timestamps are monotonically increasing (no backward jumps)
    2. Sequence numbers have no gaps (sequence_number[i+1] = sequence_number[i] + 1)
    3. Timestamp order matches sequence order (no clock skew)
    4. Database constraints prevent timestamp manipulation

    This validator provides methods to check all these invariants.
    """

    def __init__(self, db: Session):
        """
        Initialize validator with database session.

        Args:
            db: SQLAlchemy session for database queries
        """
        self.db = db

    def validate_monotonicity(
        self,
        account_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Validate that audit timestamps are monotonically increasing.

        For each account, timestamps should be in ascending order.
        Equal timestamps are allowed (same microsecond), but backward
        jumps indicate clock skew or manual manipulation.

        Args:
            account_id: Filter to specific account (None = all accounts)
            start_time: Start of validation window
            end_time: End of validation window

        Returns:
            Dict with:
            - is_monotonic: bool - True if all timestamps are monotonic
            - violations: List[Dict] - Timestamp violations found
            - total_entries: int - Total entries checked
            - accounts_checked: int - Number of accounts validated
            - validated_at: str - ISO timestamp of validation

        Example:
            >>> result = validator.validate_monotonicity(account_id="acct-123")
            >>> if not result['is_monotonic']:
            ...     for v in result['violations']:
            ...         print(f"Backward jump at sequence {v['sequence_number']}")
        """
        query = self.db.query(FinancialAudit)

        if account_id:
            query = query.filter(FinancialAudit.account_id == account_id)
        if start_time:
            query = query.filter(FinancialAudit.timestamp >= start_time)
        if end_time:
            query = query.filter(FinancialAudit.timestamp <= end_time)

        # Group by account_id for per-account monotonicity
        audits = query.order_by(FinancialAudit.account_id, FinancialAudit.timestamp).all()

        violations = []
        current_account = None
        prev_timestamp = None

        for audit in audits:
            if audit.account_id != current_account:
                # New account - reset tracking
                current_account = audit.account_id
                prev_timestamp = audit.timestamp
                continue

            # Check monotonicity (equal is OK for same microsecond, but not backward)
            if audit.timestamp < prev_timestamp:
                violations.append({
                    'account_id': audit.account_id,
                    'audit_id': audit.id,
                    'current_timestamp': audit.timestamp.isoformat(),
                    'previous_timestamp': prev_timestamp.isoformat(),
                    'sequence_number': getattr(audit, 'sequence_number', 'N/A'),
                    'violation_type': 'backward_timestamp'
                })
                logger.warning(
                    f"Backward timestamp jump detected: "
                    f"account={audit.account_id}, "
                    f"current={audit.timestamp.isoformat()}, "
                    f"previous={prev_timestamp.isoformat()}"
                )

            prev_timestamp = audit.timestamp

        accounts_checked = len(set(a.account_id for a in audits))

        return {
            'is_monotonic': len(violations) == 0,
            'violations': violations,
            'total_entries': len(audits),
            'accounts_checked': accounts_checked,
            'validated_at': datetime.utcnow().isoformat()
        }

    def detect_gaps(
        self,
        account_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Detect gaps in sequence numbers.

        A gap occurs when sequence_number[i+1] != sequence_number[i] + 1
        This can indicate missing audit entries due to:
        - Application errors (failed to create audit entry)
        - Database transaction rollbacks
        - Manual deletion of audit records
        - Import/export errors

        Args:
            account_id: Filter to specific account (None = all accounts)
            start_time: Start of validation window
            end_time: End of validation window

        Returns:
            Dict with:
            - has_gaps: bool - True if gaps found
            - gaps: List[Dict] - Gap details
            - total_gaps: int - Number of gaps
            - accounts_with_gaps: List[str] - Account IDs with gaps
            - checked_at: str - ISO timestamp of check

        Example:
            >>> result = validator.detect_gaps(account_id="acct-123")
            >>> if result['has_gaps']:
            ...     for gap in result['gaps']:
            ...         print(f"Missing sequences {gap['after_sequence']}-{gap['actual_sequence']}")
        """
        query = self.db.query(FinancialAudit)

        if account_id:
            query = query.filter(FinancialAudit.account_id == account_id)
        if start_time:
            query = query.filter(FinancialAudit.timestamp >= start_time)
        if end_time:
            query = query.filter(FinancialAudit.timestamp <= end_time)

        # Order by account then sequence for gap detection
        audits = query.order_by(
            FinancialAudit.account_id,
            FinancialAudit.sequence_number
        ).all()

        gaps = []
        current_account = None
        prev_sequence = None
        accounts_with_gaps = set()

        for audit in audits:
            if audit.account_id != current_account:
                # New account - reset tracking
                current_account = audit.account_id
                prev_sequence = getattr(audit, 'sequence_number', None)
                continue

            current_sequence = getattr(audit, 'sequence_number', None)

            # Skip if sequence_number not available (Plan 01 not run yet)
            if prev_sequence is None or current_sequence is None:
                prev_sequence = current_sequence
                continue

            # Check for gap
            expected_sequence = prev_sequence + 1
            if current_sequence != expected_sequence:
                gap_info = {
                    'account_id': audit.account_id,
                    'expected_sequence': expected_sequence,
                    'actual_sequence': current_sequence,
                    'gap_size': current_sequence - prev_sequence - 1,
                    'after_sequence': prev_sequence,
                    'before_timestamp': audit.timestamp.isoformat()
                }
                gaps.append(gap_info)
                accounts_with_gaps.add(audit.account_id)
                logger.warning(
                    f"Sequence gap detected: "
                    f"account={audit.account_id}, "
                    f"expected={expected_sequence}, "
                    f"actual={current_sequence}, "
                    f"gap_size={gap_info['gap_size']}"
                )

            prev_sequence = current_sequence

        return {
            'has_gaps': len(gaps) > 0,
            'gaps': gaps,
            'total_gaps': len(gaps),
            'accounts_with_gaps': list(accounts_with_gaps),
            'checked_at': datetime.utcnow().isoformat()
        }

    def detect_out_of_order(
        self,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Detect entries where timestamp order doesn't match sequence order.

        This can happen if:
        - Application time used instead of server time
        - Clock skew across servers
        - Manual timestamp manipulation

        In a properly ordered audit trail, sorting by timestamp should
        give the same order as sorting by sequence_number.

        Args:
            account_id: Filter to specific account (None = all accounts)

        Returns:
            Dict with out-of-order entries

        Example:
            >>> result = validator.detect_out_of_order(account_id="acct-123")
            >>> if result['has_out_of_order']:
            ...     print(f"Found {len(result['entries'])} out-of-order entries")
        """
        query = self.db.query(FinancialAudit)

        if account_id:
            query = query.filter(FinancialAudit.account_id == account_id)

        audits = query.order_by(
            FinancialAudit.account_id,
            FinancialAudit.timestamp
        ).all()

        out_of_order = []
        current_account = None
        sequence_by_timestamp = {}

        # Build sequence-by-timestamp map
        for audit in audits:
            if audit.account_id != current_account:
                # Process previous account
                if current_account is not None:
                    out_of_order.extend(self._check_sequence_timestamp_order(
                                                current_account, sequence_by_timestamp))
                # Start new account
                current_account = audit.account_id
                sequence_by_timestamp = {}

            seq_num = getattr(audit, 'sequence_number', None)
            if seq_num is not None:
                sequence_by_timestamp[seq_num] = audit.timestamp

        # Process last account
        if current_account is not None:
            out_of_order.extend(self._check_sequence_timestamp_order(
                                            current_account, sequence_by_timestamp))

        return {
            'has_out_of_order': len(out_of_order) > 0,
            'entries': out_of_order,
            'total_checked': len(audits),
            'checked_at': datetime.utcnow().isoformat()
        }

    def _check_sequence_timestamp_order(
        self,
        account_id: str,
        sequence_by_timestamp: Dict[int, datetime]
    ) -> List[Dict[str, Any]]:
        """
        Check if timestamp order matches sequence order for an account.

        Args:
            account_id: Account to check
            sequence_by_timestamp: Dict mapping sequence_number -> timestamp

        Returns:
            List of out-of-order violations
        """
        sorted_sequences = sorted(sequence_by_timestamp.keys())
        out_of_order = []

        for i in range(1, len(sorted_sequences)):
            seq = sorted_sequences[i]
            prev_seq = sorted_sequences[i-1]

            timestamp = sequence_by_timestamp[seq]
            prev_timestamp = sequence_by_timestamp[prev_seq]

            # Timestamp should be >= previous timestamp
            if timestamp < prev_timestamp:
                out_of_order.append({
                    'account_id': account_id,
                    'sequence_number': seq,
                    'timestamp': timestamp.isoformat(),
                    'previous_sequence': prev_seq,
                    'previous_timestamp': prev_timestamp.isoformat(),
                    'violation': 'timestamp_before_previous_sequence'
                })
                logger.warning(
                    f"Out-of-order entry detected: "
                    f"account={account_id}, "
                    f"sequence={seq}, "
                    f"timestamp={timestamp.isoformat()}, "
                    f"previous_timestamp={prev_timestamp.isoformat()}"
                )

        return out_of_order

    def detect_time_gaps(
        self,
        account_id: Optional[str] = None,
        threshold_seconds: int = 3600  # 1 hour default
    ) -> Dict[str, Any]:
        """
        Detect unusual time gaps between consecutive audit entries.

        Large gaps might indicate:
        - Missing audit entries (system downtime)
        - Data import from backup
        - Application deployment gaps
        - Testing/development in production

        Args:
            account_id: Filter to specific account (None = all accounts)
            threshold_seconds: Minimum gap size to flag (default: 3600 = 1 hour)

        Returns:
            Dict with time gap information

        Example:
            >>> # Flag gaps > 10 minutes
            >>> result = validator.detect_time_gaps(
            ...     account_id="acct-123",
            ...     threshold_seconds=600
            ... )
            >>> if result['has_time_gaps']:
            ...     for gap in result['time_gaps']:
            ...         print(f"Gap of {gap['gap_hours']:.1f} hours")
        """
        query = self.db.query(FinancialAudit)

        if account_id:
            query = query.filter(FinancialAudit.account_id == account_id)

        audits = query.order_by(
            FinancialAudit.account_id,
            FinancialAudit.timestamp
        ).all()

        time_gaps = []
        current_account = None
        prev_timestamp = None

        for audit in audits:
            if audit.account_id != current_account:
                current_account = audit.account_id
                prev_timestamp = audit.timestamp
                continue

            time_diff = (audit.timestamp - prev_timestamp).total_seconds()

            if time_diff > threshold_seconds:
                time_gaps.append({
                    'account_id': audit.account_id,
                    'sequence_number': getattr(audit, 'sequence_number', 'N/A'),
                    'gap_seconds': time_diff,
                    'gap_hours': time_diff / 3600,
                    'gap_days': time_diff / 86400,
                    'from_timestamp': prev_timestamp.isoformat(),
                    'to_timestamp': audit.timestamp.isoformat()
                })
                logger.info(
                    f"Time gap detected: "
                    f"account={audit.account_id}, "
                    f"gap_seconds={time_diff:.0f}, "
                    f"from={prev_timestamp.isoformat()}, "
                    f"to={audit.timestamp.isoformat()}"
                )

            prev_timestamp = audit.timestamp

        return {
            'has_time_gaps': len(time_gaps) > 0,
            'time_gaps': time_gaps,
            'threshold_seconds': threshold_seconds,
            'total_gaps': len(time_gaps),
            'checked_at': datetime.utcnow().isoformat()
        }

    def validate_integrity(
        self,
        account_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        time_gap_threshold: int = 3600
    ) -> Dict[str, Any]:
        """
        Run comprehensive chronological integrity validation.

        This is the main entry point for AUD-02 validation. It combines
        all individual checks into a single comprehensive report.

        Args:
            account_id: Filter to specific account (None = all accounts)
            start_time: Start of validation window
            end_time: End of validation window
            time_gap_threshold: Threshold for time gap detection (seconds)

        Returns:
            Dict with results from all integrity checks:
            - is_valid: bool - Overall validity (all checks pass)
            - monotonicity: Dict - Monotonic timestamp validation
            - sequence_gaps: Dict - Sequence gap detection
            - out_of_order: Dict - Out-of-order detection
            - time_gaps: Dict - Time gap detection
            - validated_at: str - ISO timestamp of validation

        Example:
            >>> result = validator.validate_integrity(account_id="acct-123")
            >>> if result['is_valid']:
            ...     print("Audit trail is chronologically sound")
            >>> else:
            ...     if not result['monotonicity']['is_monotonic']:
            ...         print("Timestamp violations found")
            ...     if result['sequence_gaps']['has_gaps']:
            ...         print("Sequence gaps found")
        """
        monotonicity = self.validate_monotonicity(account_id, start_time, end_time)
        gaps = self.detect_gaps(account_id, start_time, end_time)
        out_of_order = self.detect_out_of_order(account_id)
        time_gaps = self.detect_time_gaps(account_id, time_gap_threshold)

        # Overall validity: monotonic + no gaps + no out-of-order
        # Time gaps are informational, not a validity violation
        is_valid = (
            monotonicity['is_monotonic'] and
            not gaps['has_gaps'] and
            not out_of_order['has_out_of_order']
        )

        return {
            'is_valid': is_valid,
            'monotonicity': monotonicity,
            'sequence_gaps': gaps,
            'out_of_order': out_of_order,
            'time_gaps': time_gaps,
            'validated_at': datetime.utcnow().isoformat()
        }
