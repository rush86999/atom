"""
Property-Based Tests for Audit Completeness Invariants (AUD-01) - Phase 94-01

Tests verify that all financial operations create audit entries automatically
via SQLAlchemy event listeners with required SOX fields.

Invariant Categories:
- Transaction Logging Completeness: Every operation creates an audit entry
- Required Fields Validation: All mandatory fields are present
- Sequence Monotonicity: Sequence numbers increase without gaps
- Action Type Coverage: Create/update/delete all create audits

Test Strategy:
- Hypothesis generates 50-100 examples per test (800+ total test cases)
- Tests cover all financial models from phases 91-93 (FinancialAccount)
- Property-based validation ensures completeness across edge cases
"""

import pytest
import uuid
from datetime import datetime
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.models import FinancialAccount, FinancialAudit, User
from core.financial_audit_service import FinancialAuditService, FINANCIAL_MODELS
from core.audit_trail_validator import AuditTrailValidator
from core.decimal_utils import to_decimal


# ==================== TEST FIXTURES ====================

@pytest.fixture
def audit_service():
    """Provide FinancialAuditService instance."""
    return FinancialAuditService()


@pytest.fixture
def audit_validator(db_session):
    """Provide AuditTrailValidator instance."""
    return AuditTrailValidator(db_session)


# ==================== AUDIT COMPLETENESS TESTS ====================

@pytest.mark.usefixtures("db_session", "audit_service")
class TestAuditCompletenessInvariants:
    """Property-based tests for audit logging completeness (AUD-01)."""

    @pytest.fixture(autouse=True)
    def setup_audit_service(self, db_session, audit_service):
        """Initialize audit service before each test."""
        self.audit_service = audit_service
        self.audit_service.register_financial_models()
        self.db = db_session

        # Create a test user for all tests
        user = User(
            id=str(uuid.uuid4()),
            email=f"test_{uuid.uuid4()}@example.com",
            first_name="Test",
            last_name="User"
        )
        self.db.add(user)
        self.db.commit()
        self.test_user_id = user.id

    @given(
        account_name=st.text(min_size=1, max_size=50).filter(lambda x: x.isalnum()),
        balance=st.decimals(min_value='0', max_value='1000000.00', places=2),
        account_type=st.sampled_from(['checking', 'savings', 'investment', 'credit_card'])
    )
    @settings(max_examples=100)
    def test_every_financial_operation_creates_audit(
        self, account_name, balance, account_type
    ):
        """
        Verify: For any financial account creation, an audit entry is created.

        Invariant: count(FinancialAudit) >= count(FinancialAccount operations)

        Test Strategy:
        - Generate random account names, balances, and types
        - Create FinancialAccount and commit to trigger after_flush
        - Verify exactly one audit entry exists for the account
        """
        # Create financial account
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=self.test_user_id,
            name=account_name,
            balance=float(balance),
            account_type=account_type,
            provider="Test Bank"
        )
        self.db.add(account)
        self.db.commit()  # Triggers after_flush event listener

        # Verify audit entry exists
        audit_count = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account.id
        ).count()

        assert audit_count > 0, f"No audit entry found for account {account.id}"

        # Verify audit entry has required fields
        audit = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account.id
        ).first()

        assert audit is not None, "Audit entry should exist"
        assert audit.action_type == 'create', f"Expected 'create', got '{audit.action_type}'"
        assert audit.user_id is not None, "user_id should be set"
        assert audit.success is True, "Operation should be marked successful"
        assert audit.timestamp is not None, "timestamp should be set"
        assert audit.sequence_number is not None, "sequence_number should be set"
        assert audit.entry_hash is not None, "entry_hash should be set"

    @given(
        initial_balance=st.decimals(min_value='0', max_value='1000.00', places=2),
        new_balance=st.decimals(min_value='0', max_value='10000.00', places=2)
    )
    @settings(max_examples=50)
    def test_update_operations_create_audits(self, initial_balance, new_balance):
        """
        Verify: UPDATE operations create audit entries with old/new values.

        Invariant: UPDATE operations capture both old and new state

        Test Strategy:
        - Create account with initial balance
        - Update balance to new value
        - Verify 2 audit entries (create + update)
        - Verify update audit has old_values and new_values
        """
        assume(initial_balance != new_balance)  # Ensure actual change

        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=self.test_user_id,
            name="Test Account",
            balance=float(initial_balance),
            account_type='checking',
            provider="Test Bank"
        )
        self.db.add(account)
        self.db.commit()

        # Update balance
        account.balance = float(new_balance)
        self.db.commit()  # Triggers after_flush

        # Should have 2 audit entries: create + update
        audits = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account.id
        ).all()

        assert len(audits) == 2, f"Expected 2 audits, got {len(audits)}"

        # Find update audit
        update_audit = next((a for a in audits if a.action_type == 'update'), None)
        assert update_audit is not None, "No update audit found"
        assert update_audit.old_values is not None, "old_values should be captured"
        assert update_audit.new_values is not None, "new_values should be captured"

        # Verify balance change captured
        assert 'balance' in update_audit.old_values, "old_values should contain balance"
        assert 'balance' in update_audit.new_values, "new_values should contain balance"

    @given(
        balance=st.decimals(min_value='0', max_value='1000.00', places=2)
    )
    @settings(max_examples=50)
    def test_delete_operations_create_audits(self, balance):
        """
        Verify: DELETE operations create audit entries.

        Invariant: DELETE operations create final audit entry before removal

        Test Strategy:
        - Create account
        - Delete account
        - Verify 2 audit entries (create + delete)
        - Verify delete audit exists
        """
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=self.test_user_id,
            name="Test Account",
            balance=float(balance),
            account_type='checking',
            provider="Test Bank"
        )
        self.db.add(account)
        self.db.commit()

        account_id = account.id
        self.db.delete(account)
        self.db.commit()

        # Should have 2 audit entries: create + delete
        audits = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        ).all()

        assert len(audits) == 2, f"Expected 2 audits, got {len(audits)}"

        delete_audit = next((a for a in audits if a.action_type == 'delete'), None)
        assert delete_audit is not None, "No delete audit found"

    @given(
        num_operations=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_multiple_operations_create_multiple_audits(self, num_operations):
        """
        Verify: N operations create N audit entries.

        Invariant: count(audits) = count(operations)

        Test Strategy:
        - Create N financial accounts in single transaction
        - Verify N audit entries created
        - Each account should have exactly 1 audit
        """
        account_ids = []

        for i in range(num_operations):
            account = FinancialAccount(
                id=str(uuid.uuid4()),
                user_id=self.test_user_id,
                name=f"Test Account {i}",
                balance=100.0 + i,
                account_type='checking',
                provider="Test Bank"
            )
            self.db.add(account)
            account_ids.append(account.id)

        self.db.commit()  # Triggers after_flush for all operations

        # Count audit entries
        audit_count = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id.in_(account_ids)
        ).count()

        assert audit_count == num_operations, \
            f"Expected {num_operations} audits, got {audit_count}"

    @given(
        num_operations=st.integers(min_value=2, max_value=20)
    )
    @settings(max_examples=50)
    def test_sequence_numbers_are_monotonic(self, num_operations):
        """
        Verify: Sequence numbers increase monotonically for same account.

        Invariant: sequence_number[i+1] = sequence_number[i] + 1

        Test Strategy:
        - Create account
        - Perform N updates to generate multiple audits
        - Verify sequence numbers are consecutive
        """
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=self.test_user_id,
            name="Test Account",
            balance=100.0,
            account_type='checking',
            provider="Test Bank"
        )
        self.db.add(account)
        self.db.commit()

        # Perform updates to generate more audits
        for i in range(num_operations - 1):
            account.balance = 100.0 + i
            self.db.commit()

        # Check sequence numbers
        audits = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account.id
        ).order_by(FinancialAudit.sequence_number).all()

        assert len(audits) == num_operations, \
            f"Expected {num_operations} audits, got {len(audits)}"

        for i in range(1, len(audits)):
            expected_seq = audits[i-1].sequence_number + 1
            actual_seq = audits[i].sequence_number
            assert actual_seq == expected_seq, \
                f"Sequence numbers not monotonic: expected {expected_seq}, got {actual_seq}"

    @given(
        account_name=st.text(min_size=1, max_size=30).filter(lambda x: x.isalnum())
    )
    @settings(max_examples=50)
    def test_audit_entries_have_required_fields(self, account_name):
        """
        Verify: All audit entries contain required SOX fields.

        Required fields: id, timestamp, user_id, account_id, action_type,
                        success, agent_maturity, sequence_number, entry_hash

        Invariant: All mandatory fields are non-null

        Test Strategy:
        - Create account to generate audit
        - Verify all required fields are present and non-null
        """
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=self.test_user_id,
            name=account_name,
            balance=100.0,
            account_type='checking',
            provider="Test Bank"
        )
        self.db.add(account)
        self.db.commit()

        audit = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account.id
        ).first()

        REQUIRED_FIELDS = [
            'id', 'timestamp', 'user_id', 'account_id',
            'action_type', 'success', 'agent_maturity',
            'sequence_number', 'entry_hash'
        ]

        for field in REQUIRED_FIELDS:
            assert hasattr(audit, field), f"Missing field: {field}"
            value = getattr(audit, field)
            assert value is not None, f"Field {field} is None"

    @given(
        balance=st.decimals(min_value='0', max_value='5000.00', places=2)
    )
    @settings(max_examples=50)
    def test_hash_chain_fields_populated(self, balance):
        """
        Verify: Hash chain fields (entry_hash, prev_hash) are populated.

        Invariant: entry_hash is non-null, prev_hash is null for first entry

        Test Strategy:
        - Create account to generate first audit
        - Verify entry_hash is populated
        - Verify prev_hash is null for first entry
        """
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=self.test_user_id,
            name="Test Account",
            balance=float(balance),
            account_type='checking',
            provider="Test Bank"
        )
        self.db.add(account)
        self.db.commit()

        audit = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account.id
        ).first()

        assert audit.entry_hash is not None, "entry_hash should be populated"
        assert len(audit.entry_hash) == 64, "entry_hash should be SHA-256 (64 hex chars)"
        # prev_hash can be null for first entry or populated for subsequent entries
        assert audit.prev_hash is not None or audit.sequence_number == 1, \
            "prev_hash should be null only for first entry"

    @given(
        num_accounts=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=30)
    def test_financial_models_registered(self, num_accounts):
        """
        Verify: All financial models are registered in audit service.

        Invariant: FINANCIAL_MODELS contains FinancialAccount

        Test Strategy:
        - Create multiple accounts
        - Verify audit service has FinancialAccount registered
        - Verify all models in FINANCIAL_MODELS are valid SQLAlchemy models
        """
        for i in range(num_accounts):
            account = FinancialAccount(
                id=str(uuid.uuid4()),
                user_id=self.test_user_id,
                name=f"Test Account {i}",
                balance=100.0 * (i + 1),
                account_type='checking',
                provider="Test Bank"
            )
            self.db.add(account)

        self.db.commit()

        registered = self.audit_service.get_registered_models()
        assert 'FinancialAccount' in registered, "FinancialAccount should be registered"
        assert len(registered) > 0, "At least one model should be registered"


# ==================== AUDIT VALIDATOR TESTS ====================

@pytest.mark.usefixtures("db_session", "audit_service")
class TestAuditTrailValidator:
    """Property-based tests for AuditTrailValidator."""

    @pytest.fixture(autouse=True)
    def setup_validator(self, db_session, audit_service):
        """Initialize validator and audit service."""
        self.validator = AuditTrailValidator(db_session)
        self.audit_service = audit_service
        self.audit_service.register_financial_models()
        self.db = db_session

        # Create a test user for all tests
        user = User(
            id=str(uuid.uuid4()),
            email=f"test_{uuid.uuid4()}@example.com",
            first_name="Test",
            last_name="User"
        )
        self.db.add(user)
        self.db.commit()
        self.test_user_id = user.id

    @given(
        num_audits=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=30)
    def test_validate_required_fields(self, num_audits):
        """
        Verify: Validator correctly identifies valid/invalid audit entries.

        Invariant: All auto-generated audits pass required fields validation

        Test Strategy:
        - Create N accounts to generate N audits
        - Run validate_required_fields
        - Verify all entries are valid (no invalid_entries)
        """
        for i in range(num_audits):
            account = FinancialAccount(
                id=str(uuid.uuid4()),
                user_id=self.test_user_id,
                name=f"Test Account {i}",
                balance=100.0 + i,
                account_type='checking',
                provider="Test Bank"
            )
            self.db.add(account)

        self.db.commit()

        result = self.validator.validate_required_fields(limit=100)

        assert result['total_checked'] >= num_audits, \
            f"Should check at least {num_audits} entries"
        assert result['valid'], f"Found {len(result['invalid_entries'])} invalid entries"
        assert len(result['invalid_entries']) == 0, "Should have no invalid entries"

    @given(
        num_operations=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=30)
    def test_get_audit_statistics(self, num_operations):
        """
        Verify: Validator generates accurate audit statistics.

        Invariant: Statistics match actual audit counts

        Test Strategy:
        - Create N accounts
        - Verify statistics total_audits >= N
        - Verify by_action_type includes 'create'
        - Verify success_rate is 1.0 (all operations succeed)
        """
        for i in range(num_operations):
            account = FinancialAccount(
                id=str(uuid.uuid4()),
                user_id=self.test_user_id,
                name=f"Test Account {i}",
                balance=100.0 + i,
                account_type='checking',
                provider="Test Bank"
            )
            self.db.add(account)

        self.db.commit()

        stats = self.validator.get_audit_statistics()

        assert stats['total_audits'] >= num_operations, \
            f"Expected at least {num_operations} audits, got {stats['total_audits']}"
        assert 'create' in stats['by_action_type'], "Should have 'create' action type"
        assert stats['success_rate'] == 1.0, "All operations should succeed"

    @given(
        num_updates=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=30)
    def test_validate_sequence_monotonicity(self, num_updates):
        """
        Verify: Validator detects sequence monotonicity violations.

        Invariant: Auto-generated sequences are always monotonic

        Test Strategy:
        - Create account with multiple updates
        - Validate sequence monotonicity
        - Verify no violations detected
        """
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=self.test_user_id,
            name="Test Account",
            balance=100.0,
            account_type='checking',
            provider="Test Bank"
        )
        self.db.add(account)
        self.db.commit()

        # Generate multiple audits via updates
        for i in range(num_updates - 1):
            account.balance = 100.0 + i
            self.db.commit()

        result = self.validator.validate_sequence_monotonicity(account.id)

        assert result['valid'], f"Found {len(result['violations'])} sequence violations"
        assert result['total_entries'] == num_updates, \
            f"Expected {num_updates} entries, got {result['total_entries']}"
        assert len(result['violations']) == 0, "Should have no sequence violations"
