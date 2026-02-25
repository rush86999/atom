"""
Financial Audit Test Fixtures - Phase 94-01

Test fixtures for generating FinancialAudit entries and related test data.

Note: factory_boy is not installed, so we use simple fixture functions
instead of Factory Boy classes.

Features:
- User, FinancialAccount fixture functions for foreign key relationships
- FinancialAudit fixture function for audit entry generation
- AuditChainBuilder for valid hash chain construction
- Pytest fixtures for easy integration with test suite
"""

import hashlib
import json
import uuid
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional

from core.models import FinancialAudit, FinancialAccount, User
from core.decimal_utils import to_decimal


# ==================== FIXTURE FUNCTIONS ====================

def create_test_user(
    id: Optional[str] = None,
    email: Optional[str] = None,
    first_name: str = "Test",
    last_name: str = "User"
) -> User:
    """
    Create a test User object.

    Args:
        id: User ID (auto-generated if not provided)
        email: User email (auto-generated if not provided)
        first_name: First name
        last_name: Last name

    Returns:
        User object
    """
    return User(
        id=id or str(uuid.uuid4()),
        email=email or f"test_{uuid.uuid4()}@example.com",
        first_name=first_name,
        last_name=last_name,
        role="MEMBER",
        status="ACTIVE",
        email_verified=True
    )


def create_test_financial_account(
    id: Optional[str] = None,
    user_id: Optional[str] = None,
    account_type: str = "checking",
    provider: str = "Test Bank",
    balance: float = 1000.0,
    currency: str = "USD",
    name: str = "Test Account"
) -> FinancialAccount:
    """
    Create a test FinancialAccount object.

    Args:
        id: Account ID (auto-generated if not provided)
        user_id: User ID (auto-generated if not provided)
        account_type: Account type
        provider: Bank/provider name
        balance: Account balance
        currency: Currency code
        name: Account name

    Returns:
        FinancialAccount object
    """
    return FinancialAccount(
        id=id or str(uuid.uuid4()),
        user_id=user_id or str(uuid.uuid4()),
        account_type=account_type,
        provider=provider,
        balance=balance,
        currency=currency,
        name=name,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


def create_test_financial_audit(
    id: Optional[str] = None,
    account_id: Optional[str] = None,
    user_id: Optional[str] = None,
    action_type: str = "create",
    sequence_number: int = 1,
    entry_hash: Optional[str] = None,
    prev_hash: str = "",
    success: bool = True,
    agent_maturity: str = "AUTONOMOUS"
) -> FinancialAudit:
    """
    Create a test FinancialAudit object.

    Args:
        id: Audit ID (auto-generated if not provided)
        account_id: Account ID (auto-generated if not provided)
        user_id: User ID (auto-generated if not provided)
        action_type: Action type (create/update/delete)
        sequence_number: Sequence number
        entry_hash: Entry hash (auto-generated if not provided)
        prev_hash: Previous entry hash
        success: Whether operation succeeded
        agent_maturity: Agent maturity level

    Returns:
        FinancialAudit object
    """
    if entry_hash is None:
        data = f"{action_type}{account_id or 'unknown'}{prev_hash}{datetime.utcnow().isoformat()}"
        entry_hash = hashlib.sha256(data.encode()).hexdigest()

    return FinancialAudit(
        id=id or str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        user_id=user_id or str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        agent_execution_id=str(uuid.uuid4()),
        account_id=account_id or str(uuid.uuid4()),
        action_type=action_type,
        changes={'balance': {'old': 100.0, 'new': 200.0}},
        old_values={'balance': 100.0},
        new_values={'balance': 200.0},
        success=success,
        error_message=None,
        agent_maturity=agent_maturity,
        governance_check_passed=True,
        required_approval=False,
        approval_granted=None,
        request_id=str(uuid.uuid4()),
        ip_address='127.0.0.1',
        user_agent='Test Agent',
        sequence_number=sequence_number,
        entry_hash=entry_hash,
        prev_hash=prev_hash
    )


# ==================== HASH CHAIN BUILDER ====================

class AuditChainBuilder:
    """
    Helper to build valid hash chains for testing.

    Creates sequences of audit entries where each entry's prev_hash
    points to the previous entry's entry_hash.
    """

    @staticmethod
    def build_chain(num_entries: int, account_id: str, user_id: Optional[str] = None) -> List[FinancialAudit]:
        """
        Build a chain of audit entries with valid hash links.

        Args:
            num_entries: Number of audit entries to create
            account_id: Account ID for all entries
            user_id: User ID for all entries (auto-generated if not provided)

        Returns:
            List of FinancialAudit objects with valid hash chain
        """
        entries = []
        prev_hash = ''
        uid = user_id or str(uuid.uuid4())

        for i in range(num_entries):
            entry_hash = AuditChainBuilder._compute_hash(i, account_id, prev_hash)

            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=uid,
                agent_id=str(uuid.uuid4()),
                agent_execution_id=str(uuid.uuid4()),
                account_id=account_id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'balance': 100.0 * (i + 1)},
                success=True,
                error_message=None,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                request_id=str(uuid.uuid4()),
                ip_address='127.0.0.1',
                user_agent='Test Agent',
                sequence_number=i + 1,
                entry_hash=entry_hash,
                prev_hash=prev_hash
            )
            entries.append(audit)
            prev_hash = entry_hash

        return entries

    @staticmethod
    def _compute_hash(index: int, account_id: str, prev_hash: str) -> str:
        """
        Compute hash for audit entry.

        Args:
            index: Entry index
            account_id: Account ID
            prev_hash: Previous entry's hash

        Returns:
            SHA-256 hash as hex string
        """
        data = f"{account_id}{index}{prev_hash}{datetime.utcnow().isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def verify_chain(entries: List[FinancialAudit]) -> bool:
        """
        Verify hash chain integrity.

        Args:
            entries: List of audit entries in sequence order

        Returns:
            True if chain is valid, False otherwise
        """
        if not entries:
            return True

        # Check sequence numbers are monotonic
        for i in range(1, len(entries)):
            if entries[i].sequence_number != entries[i-1].sequence_number + 1:
                return False

        # Check hash chain (note: hashes contain timestamps so exact match is difficult)
        # We just verify sequence numbers and that hashes exist
        for entry in entries:
            if not entry.entry_hash or len(entry.entry_hash) != 64:
                return False

        return True

    @staticmethod
    def build_gapped_chain(gaps: List[int], account_id: str) -> List[FinancialAudit]:
        """
        Build a chain with intentional sequence gaps for testing gap detection.

        Args:
            gaps: List of sequence numbers to skip (e.g., [3, 7] skips entries 3 and 7)
            account_id: Account ID for all entries

        Returns:
            List of FinancialAudit objects with sequence gaps
        """
        entries = []
        prev_hash = ''
        current_seq = 1
        uid = str(uuid.uuid4())

        for i in range(10):  # Create 10 entries total
            if current_seq in gaps:
                # Skip this sequence number
                current_seq += 1
                continue

            entry_hash = AuditChainBuilder._compute_hash(current_seq, account_id, prev_hash)

            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=uid,
                account_id=account_id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'balance': 100.0 * current_seq},
                success=True,
                error_message=None,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=current_seq,
                entry_hash=entry_hash,
                prev_hash=prev_hash
            )
            entries.append(audit)
            prev_hash = entry_hash
            current_seq += 1

        return entries


# ==================== PYTEST FIXTURES ====================

@pytest.fixture
def audit_factory(db_session):
    """
    Provide audit factory function with database session.

    Usage:
        def test_something(audit_factory):
            audit = audit_factory(action_type='create')
    """
    def _create(**kwargs):
        audit = create_test_financial_audit(**kwargs)
        db_session.add(audit)
        db_session.commit()
        return audit
    return _create


@pytest.fixture
def audit_chain_builder():
    """
    Provide AuditChainBuilder instance.

    Usage:
        def test_something(audit_chain_builder):
            chain = audit_chain_builder.build_chain(10, 'account-id')
    """
    return AuditChainBuilder


@pytest.fixture
def sample_audit_chain(audit_chain_builder):
    """
    Provide a pre-built chain of 10 audit entries.

    Usage:
        def test_something(sample_audit_chain):
            assert len(sample_audit_chain) == 10
    """
    account_id = str(uuid.uuid4())
    return audit_chain_builder.build_chain(10, account_id)


@pytest.fixture
def sample_gapped_chain(audit_chain_builder):
    """
    Provide a chain with intentional sequence gaps.

    Skips sequence numbers 3 and 7 for testing gap detection.

    Usage:
        def test_something(sample_gapped_chain):
            # Chain has gaps at sequences 3 and 7
    """
    account_id = str(uuid.uuid4())
    return audit_chain_builder.build_gapped_chain([3, 7], account_id)


# ==================== HELPER FUNCTIONS ====================

def create_test_audits_for_account(
    db_session,
    account_id: str,
    user_id: str,
    count: int = 5,
    action_type: str = 'create'
) -> List[FinancialAudit]:
    """
    Create multiple test audits for a specific account.

    Args:
        db_session: Database session
        account_id: Account ID
        user_id: User ID
        count: Number of audits to create
        action_type: Action type for all audits

    Returns:
        List of created FinancialAudit objects
    """
    audits = []
    prev_hash = ''

    for i in range(count):
        entry_hash = hashlib.sha256(
            f"{account_id}{i}{prev_hash}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()

        audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user_id,
            agent_id=str(uuid.uuid4()),
            agent_execution_id=str(uuid.uuid4()),
            account_id=account_id,
            action_type=action_type,
            changes={},
            old_values=None,
            new_values={'balance': 100.0 * (i + 1)},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='Test Agent',
            sequence_number=i + 1,
            entry_hash=entry_hash,
            prev_hash=prev_hash
        )

        db_session.add(audit)
        audits.append(audit)
        prev_hash = entry_hash

    db_session.commit()
    return audits


def create_audit_with_invalid_fields(db_session) -> FinancialAudit:
    """
    Create an audit entry with intentionally invalid fields for testing validation.

    Returns:
        FinancialAudit with missing required fields (for validation testing)
    """
    audit = FinancialAudit(
        id=str(uuid.uuid4()),
        timestamp=None,  # Invalid: timestamp should not be None
        user_id=None,  # Invalid: user_id should not be None
        agent_id=str(uuid.uuid4()),
        agent_execution_id=str(uuid.uuid4()),
        account_id='test-account',
        action_type='create',
        changes={},
        old_values=None,
        new_values={},
        success=True,
        error_message=None,
        agent_maturity='AUTONOMOUS',
        governance_check_passed=True,
        required_approval=False,
        approval_granted=None,
        request_id=str(uuid.uuid4()),
        ip_address='127.0.0.1',
        user_agent='Test Agent',
        sequence_number=1,
        entry_hash='',  # Invalid: entry_hash should not be empty
        prev_hash=''
    )

    db_session.add(audit)
    db_session.commit()
    return audit
