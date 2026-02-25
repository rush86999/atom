"""
E2E Scenario Factories for Financial Audit Trail Testing - Phase 94-04

Provides factory functions for creating comprehensive end-to-end financial scenarios
that span multiple models (accounts, payments, budgets, subscriptions, invoices).

These factories enable complete audit trail walkthrough testing, ensuring all financial
operations from phases 91-93 are properly logged and traceable.

Features:
- PaymentScenarioFactory: Account -> Payment Transaction -> Invoice flows
- BudgetScenarioFactory: Budget Limit -> Spend Attempt -> (Approval/Denial) flows
- SubscriptionScenarioFactory: Create -> Monthly Charges -> Cancel lifecycle
- ReconciliationScenarioFactory: Initial -> Operations -> Final balance validation
- ComplexMultiModelScenarioFactory: Cross-model linking (Project -> Budget -> Subscription -> Invoice)
"""

import uuid
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from core.models import FinancialAccount, FinancialAudit, User
from core.decimal_utils import to_decimal, round_money

# Type alias for Session to support older Python versions
DatabaseSession = Session


# ==================== PAYMENT SCENARIO FACTORY ====================

class PaymentScenarioFactory:
    """Factory for creating complete payment audit scenarios."""

    @staticmethod
    def create_payment_scenario(
        db_session,  # DatabaseSession
        amount: Decimal,
        currency: str = "USD"
    ) -> Dict[str, Any]:
        """
        Create a complete payment scenario with full audit trail.

        Scenario: Account -> Payment Transaction -> Invoice

        Args:
            db_session: Database session
            amount: Payment amount
            currency: Currency code (default: USD)

        Returns:
            Dict with all created entities and audit entries
        """
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=f"payment_{uuid.uuid4()}@example.com",
            first_name="Payment",
            last_name="Test",
            role="MEMBER",
            status="ACTIVE",
            email_verified=True
        )
        db_session.add(user)
        db_session.flush()

        # Create financial account
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="Payment Test Account",
            balance=float(amount),
            currency=currency,
            account_type="checking",
            provider="Test Bank",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(account)
        db_session.flush()

        # Simulate payment transaction (dataclass - not persisted to DB)
        # In real scenario, this would be persisted via Transaction model from Phase 91
        transaction_id = str(uuid.uuid4())
        transaction = {
            'id': transaction_id,
            'amount': float(amount),
            'currency': currency,
            'status': 'completed',
            'source': 'stripe',
            'account_id': account.id,
            'user_id': user.id,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Simulate invoice (dataclass - not persisted to DB)
        # In real scenario, this would be persisted via Invoice model from Phase 92
        invoice_id = str(uuid.uuid4())
        invoice = {
            'id': invoice_id,
            'amount': float(amount),
            'currency': currency,
            'status': 'paid',
            'user_id': user.id,
            'account_id': account.id,
            'transaction_id': transaction_id,
            'created_at': datetime.utcnow().isoformat()
        }

        # Create audit entries manually for testing
        # In production, FinancialAuditService event listener would create these
        audit_entries = []

        # Account creation audit
        account_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            agent_id='test-agent',
            agent_execution_id=None,
            account_id=account.id,
            action_type='create',
            changes={},
            old_values=None,
            new_values={'balance': float(amount), 'currency': currency},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='E2E Test Scenario',
            sequence_number=1,
            entry_hash=hashlib.sha256(f"create{account.id}1".encode()).hexdigest(),
            prev_hash=''
        )
        db_session.add(account_audit)
        audit_entries.append(account_audit)

        # Payment transaction audit
        payment_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            agent_id='test-agent',
            agent_execution_id=None,
            account_id=account.id,
            action_type='update',
            changes={'balance': {'old': float(amount), 'new': float(amount)}},
            old_values={'balance': float(amount)},
            new_values={'transaction_id': transaction_id, 'amount': float(amount)},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='E2E Test Scenario',
            sequence_number=2,
            entry_hash=hashlib.sha256(f"update{account.id}2".encode()).hexdigest(),
            prev_hash=account_audit.entry_hash
        )
        db_session.add(payment_audit)
        audit_entries.append(payment_audit)

        db_session.commit()

        return {
            'user': user,
            'account': account,
            'transaction': transaction,
            'invoice': invoice,
            'audit_entries': audit_entries,
            'scenario_type': 'payment'
        }


# ==================== BUDGET SCENARIO FACTORY ====================

class BudgetScenarioFactory:
    """Factory for creating budget enforcement audit scenarios."""

    @staticmethod
    def create_budget_scenario(
        db_session,  # DatabaseSession
        budget_amount: Decimal,
        spend_amount: Decimal
    ) -> Dict[str, Any]:
        """
        Create a complete budget scenario with full audit trail.

        Scenario: Budget Limit -> Spend Attempt -> (Approval/Denial) -> Transaction

        Args:
            db_session: Database session
            budget_amount: Monthly budget limit
            spend_amount: Attempted spend amount

        Returns:
            Dict with all created entities and audit entries
        """
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=f"budget_{uuid.uuid4()}@example.com",
            first_name="Budget",
            last_name="Test",
            role="MEMBER",
            status="ACTIVE",
            email_verified=True
        )
        db_session.add(user)
        db_session.flush()

        # Create project account (simulating project model)
        project_id = str(uuid.uuid4())

        # Create budget account
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name=f"Budget Test Account {project_id[:8]}",
            balance=float(budget_amount),
            currency="USD",
            account_type="checking",
            provider="Budget Provider",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(account)
        db_session.flush()

        # Determine if spend is approved
        is_approved = spend_amount <= budget_amount

        transaction = None
        if is_approved:
            # Simulate approved transaction
            transaction_id = str(uuid.uuid4())
            transaction = {
                'id': transaction_id,
                'amount': float(spend_amount),
                'currency': 'USD',
                'status': 'completed',
                'source': 'budget_enforcement',
                'project_id': project_id,
                'user_id': user.id,
                'timestamp': datetime.utcnow().isoformat()
            }

            # Update account balance
            new_balance = float(budget_amount) - float(spend_amount)
            account.balance = new_balance

        # Create audit entries
        audit_entries = []

        # Budget setup audit
        budget_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            agent_id='test-agent',
            agent_execution_id=None,
            account_id=account.id,
            action_type='create',
            changes={},
            old_values=None,
            new_values={'balance': float(budget_amount)},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='E2E Test Scenario',
            sequence_number=1,
            entry_hash=hashlib.sha256(f"create{account.id}1".encode()).hexdigest(),
            prev_hash=''
        )
        db_session.add(budget_audit)
        audit_entries.append(budget_audit)

        if is_approved and transaction:
            # Spend approval audit
            spend_audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                agent_id='test-agent',
                agent_execution_id=None,
                account_id=account.id,
                action_type='update',
                changes={'balance': {'old': float(budget_amount), 'new': new_balance}},
                old_values={'balance': float(budget_amount)},
                new_values={'balance': new_balance, 'transaction_id': transaction['id']},
                success=True,
                error_message=None,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                request_id=str(uuid.uuid4()),
                ip_address='127.0.0.1',
                user_agent='E2E Test Scenario',
                sequence_number=2,
                entry_hash=hashlib.sha256(f"update{account.id}2".encode()).hexdigest(),
                prev_hash=budget_audit.entry_hash
            )
            db_session.add(spend_audit)
            audit_entries.append(spend_audit)
        else:
            # Spend denial audit
            denial_audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                agent_id='test-agent',
                agent_execution_id=None,
                account_id=account.id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'spend_denied': True, 'requested_amount': float(spend_amount)},
                success=False,
                error_message='Budget limit exceeded',
                agent_maturity='AUTONOMOUS',
                governance_check_passed=False,
                required_approval=True,
                approval_granted=False,
                request_id=str(uuid.uuid4()),
                ip_address='127.0.0.1',
                user_agent='E2E Test Scenario',
                sequence_number=2,
                entry_hash=hashlib.sha256(f"create{account.id}2".encode()).hexdigest(),
                prev_hash=budget_audit.entry_hash
            )
            db_session.add(denial_audit)
            audit_entries.append(denial_audit)

        db_session.commit()

        return {
            'user': user,
            'project_id': project_id,
            'account': account,
            'transaction': transaction,
            'spend_approved': is_approved,
            'spend_amount': spend_amount,
            'budget_amount': budget_amount,
            'audit_entries': audit_entries,
            'scenario_type': 'budget'
        }


# ==================== SUBSCRIPTION SCENARIO FACTORY ====================

class SubscriptionScenarioFactory:
    """Factory for creating SaaS subscription audit scenarios."""

    @staticmethod
    def create_subscription_lifecycle(
        db_session,  # DatabaseSession
        monthly_cost: Decimal,
        num_months: int = 3
    ) -> Dict[str, Any]:
        """
        Create a complete subscription lifecycle scenario.

        Scenario: Create Subscription -> Monthly Charges -> Cancel

        Args:
            db_session: Database session
            monthly_cost: Monthly subscription cost
            num_months: Number of months to charge

        Returns:
            Dict with all created entities and audit entries
        """
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=f"sub_{uuid.uuid4()}@example.com",
            first_name="Subscription",
            last_name="Test",
            role="MEMBER",
            status="ACTIVE",
            email_verified=True
        )
        db_session.add(user)
        db_session.flush()

        # Create subscription account
        subscription_id = str(uuid.uuid4())
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name=f"Test Subscription {subscription_id[:8]}",
            balance=float(monthly_cost * num_months),
            currency="USD",
            account_type="credit_card",
            provider="Subscription Provider",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(account)
        db_session.flush()

        # Create invoices for each month
        invoices = []
        audit_entries = []

        for month in range(num_months):
            invoice_id = str(uuid.uuid4())
            invoice = {
                'id': invoice_id,
                'amount': float(monthly_cost),
                'currency': 'USD',
                'status': 'paid',
                'user_id': user.id,
                'account_id': account.id,
                'subscription_id': subscription_id,
                'month': month + 1,
                'created_at': (datetime.utcnow() - timedelta(days=30 * (num_months - month))).isoformat()
            }
            invoices.append(invoice)

            # Create invoice audit entry
            invoice_audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow() - timedelta(days=30 * (num_months - month)),
                user_id=user.id,
                agent_id='test-agent',
                agent_execution_id=None,
                account_id=account.id,
                action_type='create',
                changes={},
                old_values=None,
                new_values={'invoice_id': invoice_id, 'amount': float(monthly_cost), 'month': month + 1},
                success=True,
                error_message=None,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                request_id=str(uuid.uuid4()),
                ip_address='127.0.0.1',
                user_agent='E2E Test Scenario',
                sequence_number=month + 1,
                entry_hash=hashlib.sha256(f"create{account.id}{month + 1}".encode()).hexdigest(),
                prev_hash=audit_entries[-1].entry_hash if audit_entries else ''
            )
            db_session.add(invoice_audit)
            audit_entries.append(invoice_audit)

        # Cancel subscription audit
        cancel_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            agent_id='test-agent',
            agent_execution_id=None,
            account_id=account.id,
            action_type='update',
            changes={'status': {'old': 'active', 'new': 'cancelled'}},
            old_values={'status': 'active'},
            new_values={'status': 'cancelled', 'cancelled_at': datetime.utcnow().isoformat()},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='E2E Test Scenario',
            sequence_number=num_months + 1,
            entry_hash=hashlib.sha256(f"update{account.id}{num_months + 1}".encode()).hexdigest(),
            prev_hash=audit_entries[-1].entry_hash if audit_entries else ''
        )
        db_session.add(cancel_audit)
        audit_entries.append(cancel_audit)

        db_session.commit()

        return {
            'user': user,
            'subscription_id': subscription_id,
            'account': account,
            'invoices': invoices,
            'audit_entries': audit_entries,
            'scenario_type': 'subscription_lifecycle',
            'total_charged': float(monthly_cost * num_months),
            'num_months': num_months
        }


# ==================== RECONCILIATION SCENARIO FACTORY ====================

class ReconciliationScenarioFactory:
    """Factory for creating reconciliation test scenarios."""

    @staticmethod
    def create_reconciliation_scenario(
        db_session,  # DatabaseSession
        initial_balance: Decimal,
        operations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a scenario for reconciliation testing.

        Operations format:
        [
            {'type': 'credit', 'amount': Decimal('100.00')},
            {'type': 'debit', 'amount': Decimal('50.00')},
            ...
        ]

        Args:
            db_session: Database session
            initial_balance: Starting account balance
            operations: List of credit/debit operations

        Returns:
            Dict with expected vs actual state for reconciliation
        """
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=f"reconcile_{uuid.uuid4()}@example.com",
            first_name="Reconciliation",
            last_name="Test",
            role="MEMBER",
            status="ACTIVE",
            email_verified=True
        )
        db_session.add(user)
        db_session.flush()

        # Create account
        account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="Reconciliation Test Account",
            balance=float(initial_balance),
            currency="USD",
            account_type="checking",
            provider="Test Bank",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(account)
        db_session.flush()

        # Track expected balance and transaction IDs
        expected_balance = initial_balance
        transaction_ids = []
        audit_entries = []

        # Create initial balance audit
        initial_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            agent_id='test-agent',
            agent_execution_id=None,
            account_id=account.id,
            action_type='create',
            changes={},
            old_values=None,
            new_values={'balance': float(initial_balance)},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='E2E Test Scenario',
            sequence_number=1,
            entry_hash=hashlib.sha256(f"create{account.id}1".encode()).hexdigest(),
            prev_hash=''
        )
        db_session.add(initial_audit)
        audit_entries.append(initial_audit)

        # Process operations
        seq_num = 2
        for op in operations:
            amount = to_decimal(op['amount'])

            if op['type'] == 'credit':
                expected_balance += amount
            elif op['type'] == 'debit':
                expected_balance -= amount

            # Create transaction record
            transaction_id = str(uuid.uuid4())
            transaction_ids.append(transaction_id)

            # Create audit entry for operation
            op_audit = FinancialAudit(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                user_id=user.id,
                agent_id='test-agent',
                agent_execution_id=None,
                account_id=account.id,
                action_type='update',
                changes={'transaction_id': transaction_id, 'type': op['type']},
                old_values=None,
                new_values={'amount': float(amount), 'type': op['type']},
                success=True,
                error_message=None,
                agent_maturity='AUTONOMOUS',
                governance_check_passed=True,
                required_approval=False,
                approval_granted=None,
                request_id=str(uuid.uuid4()),
                ip_address='127.0.0.1',
                user_agent='E2E Test Scenario',
                sequence_number=seq_num,
                entry_hash=hashlib.sha256(f"update{account.id}{seq_num}".encode()).hexdigest(),
                prev_hash=audit_entries[-1].entry_hash if audit_entries else ''
            )
            db_session.add(op_audit)
            audit_entries.append(op_audit)
            seq_num += 1

        # Update final balance
        account.balance = float(expected_balance)
        db_session.commit()

        return {
            'user': user,
            'account': account,
            'transactions': transaction_ids,
            'initial_balance': float(initial_balance),
            'expected_final_balance': float(expected_balance),
            'actual_final_balance': account.balance,
            'audit_entries': audit_entries,
            'scenario_type': 'reconciliation'
        }


# ==================== COMPLEX MULTI-MODEL SCENARIO FACTORY ====================

class ComplexMultiModelScenarioFactory:
    """Factory for creating complex cross-model audit scenarios."""

    @staticmethod
    def create_cross_model_scenario(
        db_session,  # DatabaseSession
    ) -> Dict[str, Any]:
        """
        Create a scenario involving multiple linked financial models.

        Scenario: Project -> Budget -> Subscription Payment -> Invoice -> Reconciliation

        Args:
            db_session: Database session

        Returns:
            Dict with all entities and cross-linked audit entries
        """
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=f"complex_{uuid.uuid4()}@example.com",
            first_name="Complex",
            last_name="Test",
            role="MEMBER",
            status="ACTIVE",
            email_verified=True
        )
        db_session.add(user)
        db_session.flush()

        # Create project account
        project_id = str(uuid.uuid4())
        project_account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name=f"Complex Test Project {project_id[:8]}",
            balance=10000.00,
            currency="USD",
            account_type="checking",
            provider="Project Bank",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(project_account)
        db_session.flush()

        # Create subscription account
        subscription_id = str(uuid.uuid4())
        subscription_account = FinancialAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            name="Project Tool Subscription",
            balance=299.00,
            currency="USD",
            account_type="credit_card",
            provider="Subscription Provider",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(subscription_account)
        db_session.flush()

        # Create invoice data
        invoice_id = str(uuid.uuid4())
        invoice = {
            'id': invoice_id,
            'amount': 299.00,
            'currency': 'USD',
            'status': 'paid',
            'user_id': user.id,
            'project_id': project_id,
            'subscription_id': subscription_id,
            'created_at': datetime.utcnow().isoformat()
        }

        # Create audit entries for project
        audit_entries = []

        # Project account creation audit
        project_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            agent_id='test-agent',
            agent_execution_id=None,
            account_id=project_account.id,
            action_type='create',
            changes={},
            old_values=None,
            new_values={'balance': 10000.00, 'project_id': project_id},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='E2E Test Scenario',
            sequence_number=1,
            entry_hash=hashlib.sha256(f"create{project_account.id}1".encode()).hexdigest(),
            prev_hash=''
        )
        db_session.add(project_audit)
        audit_entries.append(project_audit)

        # Subscription account creation audit
        subscription_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            agent_id='test-agent',
            agent_execution_id=None,
            account_id=subscription_account.id,
            action_type='create',
            changes={},
            old_values=None,
            new_values={'balance': 299.00, 'subscription_id': subscription_id},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='E2E Test Scenario',
            sequence_number=1,
            entry_hash=hashlib.sha256(f"create{subscription_account.id}1".encode()).hexdigest(),
            prev_hash=''
        )
        db_session.add(subscription_audit)
        audit_entries.append(subscription_audit)

        # Invoice payment audit (linked to project)
        invoice_audit = FinancialAudit(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user.id,
            agent_id='test-agent',
            agent_execution_id=None,
            account_id=project_account.id,
            action_type='update',
            changes={'balance': {'old': 10000.00, 'new': 9701.00}},
            old_values={'balance': 10000.00},
            new_values={'balance': 9701.00, 'invoice_id': invoice_id, 'subscription_id': subscription_id},
            success=True,
            error_message=None,
            agent_maturity='AUTONOMOUS',
            governance_check_passed=True,
            required_approval=False,
            approval_granted=None,
            request_id=str(uuid.uuid4()),
            ip_address='127.0.0.1',
            user_agent='E2E Test Scenario',
            sequence_number=2,
            entry_hash=hashlib.sha256(f"update{project_account.id}2".encode()).hexdigest(),
            prev_hash=project_audit.entry_hash
        )
        db_session.add(invoice_audit)
        audit_entries.append(invoice_audit)

        db_session.commit()

        # Group audits by model (account_id)
        audits_by_model = {}
        for audit in audit_entries:
            if audit.account_id not in audits_by_model:
                audits_by_model[audit.account_id] = []
            audits_by_model[audit.account_id].append(audit)

        return {
            'user': user,
            'project_id': project_id,
            'subscription_id': subscription_id,
            'project_account': project_account,
            'subscription_account': subscription_account,
            'invoice': invoice,
            'audit_entries': audit_entries,
            'audits_by_model': audits_by_model,
            'scenario_type': 'cross_model',
            'total_flow': 299.00
        }
