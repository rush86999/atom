"""
Hash Chain Integrity Service - Phase 94-03

Cryptographic hash chain management for audit trail non-repudiation.

Each audit entry contains:
- entry_hash: SHA-256 hash of this entry's content + prev_hash
- prev_hash: entry_hash of the previous entry in the chain

This creates a tamper-evident chain where any modification breaks the cryptographic link.

Key Features:
- Canonical JSON serialization for consistent hashing
- SHA-256 cryptographic hashing
- Chain verification across account audit trails
- Tampering detection across all accounts
- Chain status monitoring
- Admin recovery functions (with warnings)
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from core.models import FinancialAudit

logger = logging.getLogger(__name__)


class HashChainIntegrity:
    """
    Manages cryptographic hash chains for audit trail non-repudiation.

    Each audit entry contains:
    - entry_hash: SHA-256 hash of this entry's content + prev_hash
    - prev_hash: entry_hash of the previous entry in the chain

    This creates a tamper-evident chain where any modification
    breaks the cryptographic link.
    """

    def __init__(self, db: Session):
        """
        Initialize hash chain integrity checker.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    @staticmethod
    def _to_canonical_json(data: Dict[str, Any]) -> str:
        """
        Convert dict to canonical JSON for consistent hashing.

        Uses sorted keys and no extra whitespace to ensure
        the same data always produces the same hash.

        Args:
            data: Dictionary to serialize

        Returns:
            Canonical JSON string
        """
        # Filter out None values and entry_hash (avoid circular dependency)
        # Note: prev_hash MUST be included for hash chain integrity
        filtered = {k: v for k, v in data.items()
                    if v is not None and k not in ['entry_hash']}

        # Convert datetime to ISO format string
        for key, value in filtered.items():
            if isinstance(value, datetime):
                filtered[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                # Recursively handle nested structures
                filtered[key] = json.dumps(value, sort_keys=True)

        return json.dumps(filtered, sort_keys=True, separators=(',', ':'))

    @staticmethod
    def compute_entry_hash(
        account_id: str,
        action_type: str,
        old_values: Optional[Dict[str, Any]],
        new_values: Optional[Dict[str, Any]],
        timestamp: datetime,
        sequence_number: int,
        prev_hash: str,
        user_id: str
    ) -> str:
        """
        Compute SHA-256 hash for an audit entry.

        The hash includes all relevant audit data plus the previous
        entry's hash, creating a cryptographic chain.

        Args:
            account_id: Account being audited
            action_type: Action (create/update/delete)
            old_values: Values before change (for update/delete)
            new_values: Values after change (for create/update)
            timestamp: When the action occurred
            sequence_number: Sequential position in audit trail
            prev_hash: Hash of previous entry (empty for first entry)
            user_id: User who performed the action

        Returns:
            64-character hexadecimal SHA-256 hash
        """
        # Build canonical data structure
        data = {
            'account_id': account_id,
            'action_type': action_type,
            'old_values': old_values,
            'new_values': new_values,
            'timestamp': timestamp.isoformat(),
            'sequence_number': sequence_number,
            'prev_hash': prev_hash,
            'user_id': user_id
        }

        # Canonical JSON for consistent hashing
        canonical = HashChainIntegrity._to_canonical_json(data)

        # Compute SHA-256 hash
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify_chain(
        self,
        account_id: str,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Verify integrity of hash chain for an account.

        Recomputes each hash and verifies it matches the stored value.

        Args:
            account_id: Account to verify
            start_sequence: Starting sequence number (None = beginning)
            end_sequence: Ending sequence number (None = latest)

        Returns:
            Dict with:
            - is_valid: bool - True if all hashes match
            - total_entries: int - Number of entries checked
            - first_break: Optional[Dict] - First mismatch found
            - break_count: int - Number of broken links
        """
        query = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        )

        if start_sequence is not None:
            query = query.filter(FinancialAudit.sequence_number >= start_sequence)
        if end_sequence is not None:
            query = query.filter(FinancialAudit.sequence_number <= end_sequence)

        entries = query.order_by(FinancialAudit.sequence_number).all()

        if len(entries) == 0:
            return {
                'is_valid': True,
                'total_entries': 0,
                'first_break': None,
                'break_count': 0
            }

        break_count = 0
        first_break = None

        # Verify first entry (prev_hash should be empty)
        if entries[0].prev_hash != '':
            first_break = {
                'sequence_number': entries[0].sequence_number,
                'audit_id': entries[0].id,
                'issue': 'first_entry_has_prev_hash',
                'expected_prev_hash': '',
                'actual_prev_hash': entries[0].prev_hash
            }
            break_count += 1

        # Verify each subsequent entry
        for i in range(1, len(entries)):
            current = entries[i]
            previous = entries[i-1]

            # Recompute hash for current entry
            expected_hash = self.compute_entry_hash(
                account_id=current.account_id,
                action_type=current.action_type,
                old_values=current.old_values,
                new_values=current.new_values,
                timestamp=current.timestamp,
                sequence_number=current.sequence_number,
                prev_hash=current.prev_hash,
                user_id=current.user_id
            )

            # Check if stored hash matches computed hash
            if current.entry_hash != expected_hash:
                if first_break is None:
                    first_break = {
                        'sequence_number': current.sequence_number,
                        'audit_id': current.id,
                        'issue': 'hash_mismatch',
                        'expected_hash': expected_hash,
                        'actual_hash': current.entry_hash
                    }
                break_count += 1

            # Check if prev_hash matches previous entry's hash
            if current.prev_hash != previous.entry_hash:
                if first_break is None:
                    first_break = {
                        'sequence_number': current.sequence_number,
                        'audit_id': current.id,
                        'issue': 'prev_hash_mismatch',
                        'expected_prev_hash': previous.entry_hash,
                        'actual_prev_hash': current.prev_hash
                    }
                break_count += 1

        return {
            'is_valid': break_count == 0,
            'total_entries': len(entries),
            'first_break': first_break,
            'break_count': break_count,
            'verified_at': datetime.utcnow().isoformat()
        }

    def detect_tampering(
        self,
        limit_accounts: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scan all accounts for hash chain breaks indicating tampering.

        Args:
            limit_accounts: Limit number of accounts to check (None = all)

        Returns:
            Dict with:
            - accounts_checked: int
            - tampered_accounts: List[str] - Account IDs with broken chains
            - total_breaks: int
            - details: Dict[str, Dict] - Break details per account
        """
        # Get unique account IDs
        account_ids = self.db.query(
            FinancialAudit.account_id
        ).distinct().limit(limit_accounts).all()

        account_ids = [a[0] for a in account_ids]

        tampered_accounts = []
        total_breaks = 0
        details = {}

        for account_id in account_ids:
            result = self.verify_chain(account_id)

            if not result['is_valid']:
                tampered_accounts.append(account_id)
                total_breaks += result['break_count']
                details[account_id] = result

        return {
            'accounts_checked': len(account_ids),
            'tampered_accounts': tampered_accounts,
            'total_breaks': total_breaks,
            'details': details,
            'scanned_at': datetime.utcnow().isoformat()
        }

    def get_chain_status(
        self,
        account_id: str
    ) -> Dict[str, Any]:
        """
        Get hash chain status for an account.

        Returns statistics and health information.

        Args:
            account_id: Account ID to check

        Returns:
            Dict with chain status information
        """
        entries = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        ).order_by(FinancialAudit.sequence_number).all()

        if len(entries) == 0:
            return {
                'account_id': account_id,
                'chain_length': 0,
                'is_valid': True,
                'first_entry': None,
                'last_entry': None,
                'status': 'empty'
            }

        # Verify chain
        verification = self.verify_chain(account_id)

        # Compute chain health metrics
        first_hash = entries[0].entry_hash
        last_hash = entries[-1].entry_hash

        return {
            'account_id': account_id,
            'chain_length': len(entries),
            'is_valid': verification['is_valid'],
            'first_entry': {
                'sequence_number': entries[0].sequence_number,
                'timestamp': entries[0].timestamp.isoformat(),
                'hash': first_hash
            },
            'last_entry': {
                'sequence_number': entries[-1].sequence_number,
                'timestamp': entries[-1].timestamp.isoformat(),
                'hash': last_hash
            },
            'breaks': verification['break_count'],
            'status': 'valid' if verification['is_valid'] else 'tampered',
            'checked_at': datetime.utcnow().isoformat()
        }

    def recompute_hash(
        self,
        audit_id: str
    ) -> Dict[str, Any]:
        """
        Recompute hash for a single audit entry (admin recovery function).

        WARNING: Only use this if you're certain the stored hash is
        incorrect due to a bug, not due to tampering.

        Args:
            audit_id: ID of audit entry to recompute

        Returns:
            Dict with old and new hash values
        """
        audit = self.db.query(FinancialAudit).filter(
            FinancialAudit.id == audit_id
        ).first()

        if not audit:
            return {'error': 'Audit entry not found'}

        old_hash = audit.entry_hash

        # Get previous entry's hash
        prev_entry = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == audit.account_id,
            FinancialAudit.sequence_number == audit.sequence_number - 1
        ).first()

        prev_hash = prev_entry.entry_hash if prev_entry else ''

        # Compute new hash
        new_hash = self.compute_entry_hash(
            account_id=audit.account_id,
            action_type=audit.action_type,
            old_values=audit.old_values,
            new_values=audit.new_values,
            timestamp=audit.timestamp,
            sequence_number=audit.sequence_number,
            prev_hash=prev_hash,
            user_id=audit.user_id
        )

        # Update the hash (this would be logged separately)
        audit.entry_hash = new_hash
        self.db.commit()

        logger.warning(f"Recomputed hash for audit {audit_id}: {old_hash[:8]}... -> {new_hash[:8]}...")

        return {
            'audit_id': audit_id,
            'old_hash': old_hash,
            'new_hash': new_hash,
            'hash_changed': old_hash != new_hash,
            'recomputed_at': datetime.utcnow().isoformat()
        }
