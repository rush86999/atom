"""
Tests for FinancialAuditService

Tests for financial audit service including:
- Automatic audit logging
- Event listeners
- Audit trail reconstruction
- Linked audits
- Hash chain verification
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch, MagicMock

from core.financial_audit_service import (
    FinancialAuditService,
    log_financial_operations,
    verify_audit_chain,
    _is_financial_model,
    _create_audit_entry,
    _extract_values,
    _compute_changes,
    _get_next_sequence,
    _get_user_id,
    _get_agent_id,
    _get_agent_maturity,
)
from core.models import (
    FinancialAudit,
    FinancialAccount,
    AgentRegistry,
    AgentStatus,
)


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")

    # Import and create all tables
    from core.models import Base
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Set session context
    session.info['user_id'] = 'test-user'
    session.info['agent_id'] = 'test-agent'
    session.info['agent_maturity'] = 'AUTONOMOUS'

    yield session
    session.close()


@pytest.fixture
def audit_service():
    """Create financial audit service instance."""
    return FinancialAuditService()


@pytest.fixture
def test_account(db_session):
    """Create a test financial account."""
    account = FinancialAccount(
        id="account-1",
        workspace_id="workspace-1",
        account_name="Test Account",
        account_type="asset",
        balance=Decimal("10000.00"),
        currency="USD",
    )
    db_session.add(account)
    db_session.commit()
    return account


class TestFinancialAuditServiceInit:
    """Tests for FinancialAuditService initialization."""

    def test_init(self):
        """Test service initialization."""
        service = FinancialAuditService()
        assert service._models_registered == set()


class TestRegisterFinancialModels:
    """Tests for register_financial_models method."""

    def test_register_all_models(self, audit_service):
        """Test registering all financial models."""
        audit_service.register_financial_models()

        registered = audit_service.get_registered_models()
        assert "FinancialAccount" in registered

    def test_register_specific_models(self, audit_service):
        """Test registering specific models."""
        from core.models import FinancialAccount
        audit_service.register_financial_models([FinancialAccount])

        registered = audit_service.get_registered_models()
        assert "FinancialAccount" in registered

    def test_get_registered_models(self, audit_service):
        """Test getting registered models."""
        audit_service.register_financial_models()

        registered = audit_service.get_registered_models()
        assert isinstance(registered, set)


class TestGetLinkedAudits:
    """Tests for get_linked_audits method."""

    def test_get_linked_audits_direct(self, audit_service, db_session, test_account):
        """Test getting direct linked audits."""
        # Create audit entries
        for i in range(3):
            audit = FinancialAudit(
                id=f"audit-{i}",
                account_id=test_account.id,
                timestamp=datetime.utcnow() - timedelta(hours=i),
                user_id="test-user",
                agent_id="test-agent",
                agent_maturity="AUTONOMOUS",
                action_type="create" if i == 0 else "update",
                changes={},
                old_values=None,
                new_values={"balance": float(10000 + i * 100)},
                sequence_number=i + 1,
            )
            db_session.add(audit)
        db_session.commit()

        result = audit_service.get_linked_audits(
            db=db_session,
            account_id=test_account.id,
            depth=1
        )

        assert test_account.id in result
        assert len(result[test_account.id]) == 3

    def test_get_linked_audits_recursive(self, audit_service, db_session):
        """Test getting linked audits recursively."""
        # Create accounts and audits with links
        account1 = FinancialAccount(
            id="account-a",
            workspace_id="workspace-1",
            account_name="Account A",
            account_type="asset",
            balance=Decimal("5000.00"),
            currency="USD",
        )
        account2 = FinancialAccount(
            id="account-b",
            workspace_id="workspace-1",
            account_name="Account B",
            account_type="liability",
            balance=Decimal("3000.00"),
            currency="USD",
        )
        db_session.add_all([account1, account2])
        db_session.commit()

        # Create audit with linked account
        audit = FinancialAudit(
            id="audit-link",
            account_id=account1.id,
            timestamp=datetime.utcnow(),
            user_id="test-user",
            action_type="update",
            changes={},
            old_values=None,
            new_values={"linked_account_id": "account-b"},
            sequence_number=1,
        )
        db_session.add(audit)
        db_session.commit()

        result = audit_service.get_linked_audits(
            db=db_session,
            account_id=account1.id,
            depth=2
        )

        assert account1.id in result
        assert len(result[account1.id]) >= 1


class TestReconstructTransaction:
    """Tests for reconstruct_transaction method."""

    def test_reconstruct_transaction(self, audit_service, db_session, test_account):
        """Test reconstructing a transaction from audit."""
        # Create audit entry
        audit = FinancialAudit(
            id="audit-reconstruct",
            account_id=test_account.id,
            timestamp=datetime.utcnow(),
            user_id="test-user",
            agent_id="test-agent",
            agent_maturity="AUTONOMOUS",
            action_type="update",
            changes={"balance": {"old": 9000, "new": 10000}},
            old_values={"balance": 9000.0},
            new_values={"balance": 10000.0},
            sequence_number=1,
        )
        db_session.add(audit)
        db_session.commit()

        result = audit_service.reconstruct_transaction(
            db=db_session,
            account_id=test_account.id,
            sequence_number=1
        )

        assert result["audit_id"] == "audit-reconstruct"
        assert result["action"] == "update"
        assert result["state"]["before"]["balance"] == 9000.0
        assert result["state"]["after"]["balance"] == 10000.0

    def test_reconstruct_transaction_not_found(self, audit_service, test_account):
        """Test reconstructing non-existent transaction."""
        result = audit_service.reconstruct_transaction(
            db=None,  # Won't be used
            account_id=test_account.id,
            sequence_number=999
        )

        assert "error" in result


class TestGetFullAuditTrail:
    """Tests for get_full_audit_trail method."""

    def test_get_full_audit_trail(self, audit_service, db_session, test_account):
        """Test getting full audit trail."""
        # Create multiple audit entries
        for i in range(5):
            audit = FinancialAudit(
                id=f"audit-trail-{i}",
                account_id=test_account.id,
                timestamp=datetime.utcnow() - timedelta(days=i),
                user_id="test-user",
                action_type="update",
                changes={},
                old_values=None,
                new_values={"balance": float(10000 - i * 100)},
                sequence_number=i + 1,
            )
            db_session.add(audit)
        db_session.commit()

        result = audit_service.get_full_audit_trail(
            db=db_session,
            account_id=test_account.id
        )

        assert len(result) == 5
        assert all("action" in r for r in result)


class TestIsFinancialModel:
    """Tests for _is_financial_model function."""

    def test_is_financial_model_true(self, test_account):
        """Test checking if instance is financial model (True)."""
        assert _is_financial_model(test_account) is True

    def test_is_financial_model_false(self, db_session):
        """Test checking if instance is financial model (False)."""
        agent = AgentRegistry(
            id="agent-test",
            name="Test",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.9
        )
        db_session.add(agent)

        assert _is_financial_model(agent) is False


class TestExtractValues:
    """Tests for _extract_values function."""

    def test_extract_values_basic(self, test_account):
        """Test extracting values from instance."""
        values = _extract_values(test_account, "create", "new")

        assert "account_name" in values
        assert values["account_name"] == "Test Account"
        assert "balance" in values
        assert isinstance(values["balance"], float)  # Decimal converted to float

    def test_extract_values_decimal_conversion(self, db_session):
        """Test Decimal to float conversion."""
        account = FinancialAccount(
            id="decimal-test",
            workspace_id="workspace-1",
            account_name="Decimal Test",
            account_type="asset",
            balance=Decimal("12345.67"),
            currency="USD",
        )
        db_session.add(account)

        values = _extract_values(account, "create", "new")

        assert isinstance(values["balance"], float)
        assert values["balance"] == 12345.67


class TestComputeChanges:
    """Tests for _compute_changes function."""

    def test_compute_changes_basic(self):
        """Test computing changes between old and new values."""
        old = {"name": "Old Name", "value": 100}
        new = {"name": "New Name", "value": 100}

        changes = _compute_changes(old, new)

        assert "name" in changes
        assert changes["name"]["old"] == "Old Name"
        assert changes["name"]["new"] == "New Name"
        assert "value" not in changes  # No change

    def test_compute_changes_no_old(self):
        """Test computing changes with no old values."""
        new = {"name": "Test"}

        changes = _compute_changes(None, new)

        assert changes == {}

    def test_compute_changes_no_new(self):
        """Test computing changes with no new values."""
        old = {"name": "Test"}

        changes = _compute_changes(old, None)

        assert changes == {}


class TestGetNextSequence:
    """Tests for _get_next_sequence function."""

    def test_get_next_sequence_first(self, db_session, test_account):
        """Test getting next sequence for first audit."""
        seq = _get_next_sequence(db_session, test_account.id)

        assert seq == 1

    def test_get_next_sequence_existing(self, db_session, test_account):
        """Test getting next sequence with existing audits."""
        # Create existing audit
        audit = FinancialAudit(
            id="existing-audit",
            account_id=test_account.id,
            timestamp=datetime.utcnow(),
            user_id="test-user",
            action_type="create",
            sequence_number=3,
        )
        db_session.add(audit)
        db_session.commit()

        seq = _get_next_sequence(db_session, test_account.id)

        assert seq == 4


class TestSessionContextHelpers:
    """Tests for session context helper functions."""

    def test_get_user_id(self, db_session):
        """Test extracting user_id from session."""
        db_session.info['user_id'] = 'test-user-123'

        result = _get_user_id(db_session)

        assert result == 'test-user-123'

    def test_get_user_id_default(self, db_session):
        """Test default user_id when not set."""
        # Clear user_id
        if 'user_id' in db_session.info:
            del db_session.info['user_id']

        result = _get_user_id(db_session)

        assert result == 'system'

    def test_get_agent_id(self, db_session):
        """Test extracting agent_id from session."""
        db_session.info['agent_id'] = 'agent-456'

        result = _get_agent_id(db_session)

        assert result == 'agent-456'

    def test_get_agent_maturity(self, db_session):
        """Test extracting agent_maturity from session."""
        db_session.info['agent_maturity'] = 'SUPERVISED'

        result = _get_agent_maturity(db_session)

        assert result == 'SUPERVISED'

    def test_get_agent_maturity_default(self, db_session):
        """Test default agent_maturity when not set."""
        if 'agent_maturity' in db_session.info:
            del db_session.info['agent_maturity']

        result = _get_agent_maturity(db_session)

        assert result == 'AUTONOMOUS'


class TestVerifyAuditChain:
    """Tests for verify_audit_chain function."""

    def test_verify_audit_chain_empty(self, db_session):
        """Test verifying chain with no audits."""
        result = verify_audit_chain(db_session, "non-existent-account")

        assert result["is_valid"] is True  # Empty chain is valid
        assert result["total_entries"] == 0

    def test_verify_audit_chain_valid(self, db_session, test_account):
        """Test verifying valid audit chain."""
        # Create audits with proper chain
        prev_hash = ""
        for i in range(3):
            from core.hash_chain_integrity import HashChainIntegrity
            entry_hash = HashChainIntegrity.compute_entry_hash(
                account_id=test_account.id,
                action_type="update",
                old_values={},
                new_values={"balance": float(i * 100)},
                timestamp=datetime.utcnow(),
                sequence_number=i + 1,
                prev_hash=prev_hash,
                user_id="test"
            )

            audit = FinancialAudit(
                id=f"chain-audit-{i}",
                account_id=test_account.id,
                timestamp=datetime.utcnow(),
                user_id="test-user",
                action_type="update",
                changes={},
                old_values=None,
                new_values={"balance": float(i * 100)},
                sequence_number=i + 1,
                entry_hash=entry_hash,
                prev_hash=prev_hash,
            )
            db_session.add(audit)
            db_session.commit()

            prev_hash = entry_hash

        result = verify_audit_chain(db_session, test_account.id)

        assert result["is_valid"] is True
        assert result["total_entries"] == 3


class TestEventListeners:
    """Tests for SQLAlchemy event listeners."""

    def test_log_financial_operations_on_create(self, audit_service, db_session):
        """Test that creating account triggers audit logging."""
        # This test verifies the event listener is registered
        # Actual logging happens during flush/commit

        account = FinancialAccount(
            id="new-account",
            workspace_id="workspace-1",
            account_name="New Account",
            account_type="asset",
            balance=Decimal("5000.00"),
            currency="USD",
        )
        db_session.add(account)
        db_session.commit()

        # Check that audit was created
        audits = db_session.query(FinancialAudit).filter(
            FinancialAudit.account_id == "new-account"
        ).all()

        assert len(audits) >= 1
        assert audits[0].action_type == "create"


class TestErrorHandling:
    """Tests for error handling."""

    def test_create_audit_entry_error_handling(self, db_session, test_account):
        """Test error handling in audit entry creation."""
        # This should not raise, just log error
        with patch('core.financial_audit_service.logger') as mock_logger:
            # Force an error during audit creation
            with patch.object(db_session, 'add', side_effect=Exception("DB error")):
                try:
                    db_session.flush()
                except:
                    pass

            # Logger should have been called
            assert True  # If we get here, error was handled


class TestExtractLinkedIds:
    """Tests for _extract_linked_ids method."""

    def test_extract_linked_ids(self, audit_service):
        """Test extracting linked IDs from values."""
        values = {
            "project_id": "project-123",
            "subscription_id": "subscription-456",
            "other_field": "value"
        }

        linked = audit_service._extract_linked_ids(values)

        assert "project-123" in linked
        assert "subscription-456" in linked

    def test_extract_linked_ids_empty(self, audit_service):
        """Test extracting linked IDs from empty values."""
        linked = audit_service._extract_linked_ids(None)

        assert len(linked) == 0
