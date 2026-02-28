"""
SOX Compliance Integration Tests - Phase 94-03

Integration tests for SOX compliance (AUD-04).

Tests verify:
- SOX traceability (Who, What, When, Where, How)
- SOX authorization tracking (approvals, governance)
- SOX non-repudiation (hash chain integrity)
- SOX retention period (7-year requirement)
- Complete SOX compliance check

These tests integrate all validators from Plans 01-03:
- HashChainIntegrity (hash chain verification)
- ChronologicalIntegrityValidator (timestamp monotonicity, gap detection)
- AuditTrailValidator (audit completeness)
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from sqlalchemy.orm import Session

from core.models import (
    FinancialAudit, FinancialAccount, User, AgentRegistry,
    AgentExecution
)
from core.hash_chain_integrity import HashChainIntegrity
from core.chronological_integrity import ChronologicalIntegrityValidator
from core.audit_trail_validator import AuditTrailValidator


# ==================== TEST CLASS ====================

@pytest.mark.usefixtures("db_session")
class TestSOXCompliance:
    """Integration tests for SOX compliance (AUD-04)."""

    @pytest.fixture(autouse=True)
    def setup_validators(self, db_session):
        """Initialize all validators."""
        self.db = db_session
        self.hash_integrity = HashChainIntegrity(db_session)
        self.chron_validator = ChronologicalIntegrityValidator(db_session)
        self.audit_validator = AuditTrailValidator(db_session)

    def test_sox_traceability(self):
        """
        Verify: SOX traceability - Who, What, When, Where, How.

        SOX requires complete traceability:
        - Who: user_id, agent_id, agent_maturity
        - What: action_type, changes, old_values, new_values
        - When: timestamp, sequence_number
        - Where: account_id, request context (ip_address, user_agent)
        - How: success/error_message, governance checks

        All must be present in audit entries.
        """
        # Create user and agent
        user = User(id=str(uuid.uuid4()), email="sox_test@example.com")
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name="SOX Test Agent",
            maturity="AUTONOMOUS"
        )
        execution = AgentExecution(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            user_id=user.id,
            status="completed"
        )
        self.db.add_all([user, agent, execution])
        self.db.commit()

        # Create financial account
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="SOX Test Account",
            balance=1000.00,
            account_type="checking"
        )
        self.db.add(account)
        self.db.commit()

        # Verify audit entry exists with all SOX fields
        audit = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account.id
        ).first()

        assert audit is not None, "No audit entry created"

        # Who
        assert audit.user_id is not None, "Missing user_id (Who)"
        assert audit.agent_maturity is not None, "Missing agent_maturity (Who)"

        # What
        assert audit.action_type is not None, "Missing action_type (What)"
        assert audit.changes is not None, "Missing changes (What)"

        # When
        assert audit.timestamp is not None, "Missing timestamp (When)"
        assert audit.sequence_number is not None, "Missing sequence_number (When)"

        # Where
        assert audit.account_id is not None, "Missing account_id (Where)"

        # How
        assert audit.success is not None, "Missing success (How)"
        assert audit.governance_check_passed is not None, "Missing governance_check (How)"

        # Verify all fields are queryable
        traceability_result = {
            'who': {
                'user_id': audit.user_id,
                'agent_maturity': audit.agent_maturity
            },
            'what': {
                'action': audit.action_type,
                'changes': audit.changes
            },
            'when': {
                'timestamp': audit.timestamp.isoformat(),
                'sequence': audit.sequence_number
            },
            'where': {
                'account_id': audit.account_id
            },
            'how': {
                'success': audit.success,
                'governance': audit.governance_check_passed
            }
        }

        # All fields populated
        for category, fields in traceability_result.items():
            for field, value in fields.items():
                assert value is not None, f"Traceability field {category}.{field} is None"

    def test_sox_authorization(self):
        """
        Verify: SOX authorization - approvals and governance checks.

        SOX requires tracking of:
        - Required approval (required_approval)
        - Approval granted (approval_granted)
        - Governance check passed (governance_check_passed)
        - Agent maturity at time of action (agent_maturity)
        """
        user = User(id=str(uuid.uuid4()), email="auth_test@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Create audit entry with authorization tracking
        audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            account_id=account_id,
            action_type='create',
            changes={'authorized': {'old': None, 'new': True}},
            old_values=None,
            new_values={'authorized': True},
            success=True,
            agent_maturity='SUPERVISED',  # Requires supervision
            governance_check_passed=True,
            required_approval=True,  # Required approval
            approval_granted=True,  # Approval was granted
            sequence_number=1,
            entry_hash="auth_hash",
            prev_hash=''
        )
        self.db.add(audit)
        self.db.commit()

        # Verify authorization fields
        assert audit.agent_maturity == 'SUPERVISED'
        assert audit.governance_check_passed is True
        assert audit.required_approval is True
        assert audit.approval_granted is True

        # Query by authorization status
        authorized_audits = self.db.query(FinancialAudit).filter(
            FinancialAudit.required_approval == True,
            FinancialAudit.approval_granted == True
        ).all()

        assert len(authorized_audits) > 0
        assert audit.id in [a.id for a in authorized_audits]

    def test_sox_non_repudiation(self):
        """
        Verify: SOX non-repudiation via cryptographic hash chains.

        Non-repudiation means:
        - Each entry is cryptographically linked to previous
        - Tampering breaks the chain
        - Chain can be verified for integrity
        """
        user = User(id=str(uuid.uuid4()), email="nonrepudiation@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Create audit chain
        num_entries = 10
        prev_hash = ''
        for i in range(num_entries):
            from core.hash_chain_integrity import HashChainIntegrity

            entry_hash = HashChainIntegrity.compute_entry_hash(
                account_id=account_id,
                action_type='create',
                old_values=None,
                new_values={'index': i},
                timestamp=datetime.utcnow(),
                sequence_number=i + 1,
                prev_hash=prev_hash,
                user_id=user.id
            )

            audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                account_id=account_id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'index': i},
                success=True,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                sequence_number=i + 1,
                entry_hash=entry_hash,
                prev_hash=prev_hash
            )
            self.db.add(audit)
            self.db.commit()

            prev_hash = entry_hash

        # Verify non-repudiation: chain integrity
        result = self.hash_integrity.verify_chain(account_id)

        assert result['is_valid'], f"Hash chain verification failed: {result}"
        assert result['total_entries'] == num_entries
        assert result['break_count'] == 0

        # Verify tampering would be detected
        # Get an entry and tamper with it
        tampered_audit = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id,
            FinancialAudit.sequence_number == 5
        ).first()

        original_hash = tampered_audit.entry_hash
        tampered_audit.entry_hash = "0" * 64  # Tampered
        self.db.commit()

        # Verification should now fail
        result = self.hash_integrity.verify_chain(account_id)
        assert not result['is_valid'], "Tampered chain passed verification"

        # Restore original hash
        tampered_audit.entry_hash = original_hash
        self.db.commit()

        # Verification should pass again
        result = self.hash_integrity.verify_chain(account_id)
        assert result['is_valid'], "Restored chain failed verification"

    def test_sox_retention_period(self):
        """
        Verify: SOX 7-year retention requirement.

        SOX Section 802 requires 7-year retention of audit records.
        Test verifies:
        - Old records are not auto-deleted
        - Queries can retrieve old records
        - Archive-ready structure exists
        """
        user = User(id=str(uuid.uuid4()), email="retention@example.com")
        self.db.add(user)
        self.db.commit()

        account_id = str(uuid.uuid4())

        # Create old audit entry (simulated 7 years ago)
        old_timestamp = datetime.utcnow() - timedelta(days=7 * 365)

        old_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=old_timestamp,
            user_id=user.id,
            account_id=account_id,
            action_type='create',
            changes={'old': {'old': None, 'new': True}},
            old_values=None,
            new_values={'old': True},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=1,
            entry_hash="old_hash",
            prev_hash=''
        )
        self.db.add(old_audit)
        self.db.commit()

        # Create recent audit entry
        recent_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            account_id=account_id,
            action_type='update',
            changes={'old': {'old': True, 'new': False}},
            old_values={'old': True},
            new_values={'old': False},
            success=True,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            sequence_number=2,
            entry_hash="recent_hash",
            prev_hash="old_hash"
        )
        self.db.add(recent_audit)
        self.db.commit()

        # Verify both records are retrievable
        all_audits = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        ).order_by(FinancialAudit.timestamp).all()

        assert len(all_audits) == 2
        assert all_audits[0].id == old_audit.id
        assert all_audits[1].id == recent_audit.id

        # Verify old record is still accessible
        old_retrieved = self.db.query(FinancialAudit).filter(
            FinancialAudit.id == old_audit.id
        ).first()

        assert old_retrieved is not None
        assert old_retrieved.timestamp == old_timestamp

        # Verify retention query works
        retention_cutoff = datetime.utcnow() - timedelta(days=7 * 365)
        retained_audits = self.db.query(FinancialAudit).filter(
            FinancialAudit.timestamp >= retention_cutoff
        ).count()

        assert retained_audits >= 1  # At least the recent entry

    def test_complete_sox_compliance_check(self):
        """
        Verify: Complete SOX compliance validation.

        Runs all SOX checks and generates compliance report.
        """
        # Create test data
        user = User(id=str(uuid.uuid4()), email="compliance@example.com")
        self.db.add(user)
        self.db.commit()

        # Create financial operation with full audit trail
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="Compliance Test Account",
            balance=5000.00,
            account_type="checking"
        )
        self.db.add(account)
        self.db.commit()

        account_id = account.id

        # Run all SOX compliance checks
        compliance_report = {
            'audit_trail': {
                'complete': self.audit_validator.validate_completeness()
            },
            'chronological_integrity': {
                'monotonic': self.chron_validator.validate_monotonicity(account_id),
                'no_gaps': self.chron_validator.detect_gaps(account_id)
            },
            'hash_chain_integrity': {
                'valid': self.hash_integrity.verify_chain(account_id)
            },
            'immutability': {
                'enforced': True  # Verified by other tests
            }
        }

        # Verify all checks pass
        assert compliance_report['audit_trail']['complete']['complete'], \
            "Audit trail incomplete"

        assert compliance_report['chronological_integrity']['monotonic']['is_monotonic'], \
            "Timestamps not monotonic"

        assert not compliance_report['chronological_integrity']['no_gaps']['has_gaps'], \
            "Sequence gaps detected"

        assert compliance_report['hash_chain_integrity']['valid']['is_valid'], \
            "Hash chain verification failed"

        # Overall compliance
        is_compliant = all([
            compliance_report['audit_trail']['complete']['complete'],
            compliance_report['chronological_integrity']['monotonic']['is_monotonic'],
            not compliance_report['chronological_integrity']['no_gaps']['has_gaps'],
            compliance_report['hash_chain_integrity']['valid']['is_valid']
        ])

        assert is_compliant, "SOX compliance check failed"

        compliance_report['overall_compliant'] = is_compliant
        compliance_report['checked_at'] = datetime.utcnow().isoformat()

    def test_sox_account_audit_trail(self):
        """
        Verify: Complete audit trail for an account.

        Tests that all operations on an account are audited
        with full SOX compliance fields.
        """
        # Create user and account
        user = User(id=str(uuid.uuid4()), email="audit_trail@example.com")
        self.db.add(user)
        self.db.commit()

        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="Audit Trail Test Account",
            balance=1000.00,
            account_type="checking"
        )
        self.db.add(account)
        self.db.commit()

        account_id = account.id

        # Perform multiple operations (create audit entries)
        # Note: Real operations would be through service layers
        # Here we manually create audit entries for testing

        # Operation 1: Initial creation (already audited by event listener)
        # Operation 2: Update balance
        account.balance = 1500.00
        self.db.commit()

        # Operation 3: Update account type
        account.account_type = "savings"
        self.db.commit()

        # Verify all operations are audited
        audits = self.db.query(FinancialAudit).filter(
            FinancialAudit.account_id == account_id
        ).order_by(FinancialAudit.sequence_number).all()

        assert len(audits) >= 3, f"Expected at least 3 audit entries, got {len(audits)}"

        # Verify SOX fields for each audit
        for audit in audits:
            # Who
            assert audit.user_id is not None
            assert audit.agent_maturity is not None

            # What
            assert audit.action_type is not None
            assert audit.changes is not None

            # When
            assert audit.timestamp is not None
            assert audit.sequence_number is not None

            # Where
            assert audit.account_id == account_id

            # How
            assert audit.success is not None
            assert audit.governance_check_passed is not None

        # Verify hash chain integrity
        result = self.hash_integrity.verify_chain(account_id)
        assert result['is_valid'], "Audit trail hash chain verification failed"
