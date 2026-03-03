"""
Audit Immutability Invariants Tests - Phase 94-03

Property-based tests for audit trail immutability (AUD-03).

Tests verify:
- FinancialAudit entries cannot be modified
- FinancialAudit entries cannot be deleted
- Hash chain verification detects tampering
- prev_hash linking works correctly
- First entry has empty prev_hash

Uses Hypothesis to generate 400+ test cases for comprehensive coverage.
"""

import hashlib
import pytest
from datetime import datetime
from decimal import Decimal
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session
import uuid

from core.models import FinancialAudit, FinancialAccount, User
from core.hash_chain_integrity import HashChainIntegrity
from tests.fixtures.financial_audit_fixtures import AuditChainBuilder


# ==================== TEST CLASS ====================

@pytest.mark.usefixtures("db_session")
class TestAuditImmutabilityInvariants:
    """Property-based tests for audit immutability (AUD-03)."""

    @pytest.fixture(autouse=True)
    def setup_integrity(self, db_session):
        """Initialize hash chain integrity checker."""
        from core.audit_immutable_guard import prevent_audit_modification
        self.integrity = HashChainIntegrity(db_session)
        self.db = db_session

    @given(
        initial_balance=st.decimals(min_value='0', max_value='1000.00', places=2),
        new_balance=st.decimals(min_value='0', max_value='10000.00', places=2)
    )
    @settings(max_examples=200)
    def test_audits_cannot_be_modified(self, initial_balance, new_balance):
        """
        Verify: FinancialAudit entries cannot be modified.

        Invariant: UPDATE on FinancialAudit raises exception

        Property: For any initial_balance and new_balance,
        attempting to modify an audit entry raises an exception.
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        # Create audit entry
        audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            account_id=str(uuid.uuid4()),
            action_type='create',
            changes={'balance': {'old': None, 'new': float(initial_balance)}},
            old_values=None,
            new_values={'balance': float(initial_balance)},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=1,
            entry_hash=hashlib.sha256(b"initial_hash").hexdigest(),
            prev_hash=''
        )
        self.db.add(audit)
        self.db.commit()

        # Try to modify the audit entry
        audit.success = False
        audit.error_message = "Attempting modification"

        # Should raise exception (database trigger or application guard)
        with pytest.raises((AssertionError, IntegrityError, OperationalError, ProgrammingError)):
            self.db.commit()

        # Rollback to clean up
        self.db.rollback()

    @given(
        balance=st.decimals(min_value='0', max_value='1000.00', places=2)
    )
    @settings(max_examples=200)
    def test_audits_cannot_be_deleted(self, balance):
        """
        Verify: FinancialAudit entries cannot be deleted.

        Invariant: DELETE on FinancialAudit raises exception

        Property: For any balance value,
        attempting to delete an audit entry raises an exception.
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        # Create audit entry
        audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            account_id=str(uuid.uuid4()),
            action_type='create',
            changes={'balance': {'old': None, 'new': float(balance)}},
            old_values=None,
            new_values={'balance': float(balance)},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=1,
            entry_hash=hashlib.sha256(b"initial_hash").hexdigest(),
            prev_hash=''
        )
        self.db.add(audit)
        self.db.commit()

        # Try to delete the audit entry
        self.db.delete(audit)

        # Should raise exception (database trigger or application guard)
        with pytest.raises((AssertionError, IntegrityError, OperationalError, ProgrammingError)):
            self.db.commit()

        # Rollback to clean up
        self.db.rollback()

    @given(
        num_entries=st.integers(min_value=5, max_value=50)
    )
    @settings(max_examples=200)
    def test_hash_chain_verifies_integrity(self, num_entries):
        """
        Verify: Hash chain correctly validates integrity.

        Invariant: Valid chain passes verification

        Property: For any chain of 5-50 entries with valid hash links,
        chain verification returns is_valid=True.
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Build valid chain using AuditChainBuilder
        chain_builder = AuditChainBuilder()
        entries = chain_builder.build_chain(num_entries, account_id)

        # Add to database
        for entry in entries:
            self.db.add(entry)
        self.db.commit()

        # Verify chain is valid
        result = self.integrity.verify_chain(account_id)

        assert result['is_valid'], f"Valid chain failed verification: {result}"
        assert result['total_entries'] == num_entries
        assert result['break_count'] == 0

    @given(
        tamper_position=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=200)
    def test_tampered_chain_is_detected(self, tamper_position):
        """
        Verify: Tampered hash chain is detected.

        Invariant: Modified hash breaks chain verification

        Property: For any chain with tampered hash at position 1-20,
        verification returns is_valid=False and identifies the break.
        """
        assume(tamper_position < 25)  # Keep test bounded

        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Build valid chain
        chain_builder = AuditChainBuilder()
        num_entries = tamper_position + 5
        entries = chain_builder.build_chain(num_entries, account_id)

        # Tamper with an entry's hash
        tampered_entry = entries[tamper_position]
        tampered_entry.entry_hash = "0" * 64  # Invalid hash

        # Add to database
        for entry in entries:
            self.db.add(entry)
        self.db.commit()

        # Verify chain detects tampering
        result = self.integrity.verify_chain(account_id)

        assert not result['is_valid'], "Tampered chain passed verification"
        assert result['break_count'] > 0
        assert result['first_break'] is not None

    @given(
        num_entries=st.integers(min_value=3, max_value=30)
    )
    @settings(max_examples=200)
    def test_prev_hash_linking_works(self, num_entries):
        """
        Verify: Each entry's prev_hash correctly links to previous entry.

        Invariant: entry[i].prev_hash == entry[i-1].entry_hash

        Property: For any chain of 3-30 entries,
        prev_hash correctly points to previous entry's hash.
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Build chain
        chain_builder = AuditChainBuilder()
        entries = chain_builder.build_chain(num_entries, account_id)

        # Verify prev_hash linking in memory
        for i in range(1, len(entries)):
            current = entries[i]
            previous = entries[i-1]

            assert current.prev_hash == previous.entry_hash, \
                f"prev_hash mismatch at position {i}: {current.prev_hash} != {previous.entry_hash}"

        # Add to database and verify
        for entry in entries:
            self.db.add(entry)
        self.db.commit()

        # Query back and verify
        queried = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        ).order_by(FinancialAudit.sequence_number).all()

        for i in range(1, len(queried)):
            assert queried[i].prev_hash == queried[i-1].entry_hash, \
                f"Database: prev_hash mismatch at position {i}"

    @given()
    @settings(max_examples=200)
    def test_first_entry_has_empty_prev_hash(self):
        """
        Verify: First audit entry in chain has empty prev_hash.

        Invariant: entry[0].prev_hash == ''

        Property: The first entry in any chain must have empty prev_hash.
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Create single entry
        audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            account_id=account_id,
            action_type='create',
            changes={'first': {'old': None, 'new': True}},
            old_values=None,
            new_values={'first': True},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=1,
            entry_hash=hashlib.sha256(b"first").hexdigest(),
            prev_hash=''  # First entry has empty prev_hash
        )
        self.db.add(audit)
        self.db.commit()

        # Verify
        result = self.integrity.verify_chain(account_id)

        assert result['is_valid'], f"Single entry chain failed: {result}"
        assert audit.prev_hash == ''
        assert result['total_entries'] == 1

    @given(
        num_accounts=st.integers(min_value=1, max_value=10),
        entries_per_account=st.integers(min_value=2, max_value=20)
    )
    @settings(max_examples=200)
    def test_detect_tampering_across_accounts(self, num_accounts, entries_per_account):
        """
        Verify: Tampering detection works across multiple accounts.

        Invariant: detect_tampering finds all broken chains

        Property: For any set of accounts with valid chains,
        detect_tampering returns zero breaks.
        """
        assume(num_accounts <= 10 and entries_per_account <= 20)

        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        chain_builder = AuditChainBuilder()

        # Create multiple accounts with valid chains
        account_ids = [str(uuid.uuid4()) for _ in range(num_accounts)]

        for account_id in account_ids:
            entries = chain_builder.build_chain(entries_per_account, account_id, user.id)
            for entry in entries:
                self.db.add(entry)
        self.db.commit()

        # Detect tampering across all accounts
        result = self.integrity.detect_tampering()

        assert result['accounts_checked'] >= num_accounts
        assert len(result['tampered_accounts']) == 0
        assert result['total_breaks'] == 0

    @given(
        account_id=st.uuids().map(lambda u: str(u))
    )
    @settings(max_examples=200)
    def test_get_chain_status(self, account_id):
        """
        Verify: Chain status provides accurate health information.

        Invariant: get_chain_status returns correct statistics

        Property: For any account_id, status reflects actual chain state.
        """
        user = User(id=str(uuid.uuid4()), email=f"test_{uuid.uuid4()}@example.com")
        self.db.add(user)
        self.db.commit()

        # Empty chain should return empty status
        status = self.integrity.get_chain_status(str(account_id))
        assert status['chain_length'] == 0
        assert status['status'] == 'empty'
        assert status['is_valid'] is True

        # Create chain
        chain_builder = AuditChainBuilder()
        num_entries = 10
        entries = chain_builder.build_chain(num_entries, str(account_id), user.id)

        for entry in entries:
            self.db.add(entry)
        self.db.commit()

        # Check status again
        status = self.integrity.get_chain_status(str(account_id))

        assert status['chain_length'] == num_entries
        assert status['status'] == 'valid'
        assert status['is_valid'] is True
        assert status['first_entry'] is not None
        assert status['last_entry'] is not None
        assert status['breaks'] == 0
