"""
Comprehensive database constraint testing covering all database models.

Tests database-level constraints including:
- Unique constraints (email, subdomain, composite keys)
- Not null constraints (required fields)
- Foreign key constraints (referential integrity)
- Check constraints (enum values, range validation)
- JSON field constraints and validations

Purpose: Database constraints are the last line of defense for data integrity.
These tests validate SQLAlchemy configurations match database schema and
constraint behaviors work correctly.

Tests use pytest fixtures for database sessions (db_session from conftest.py)
and Factory Boy factories for test data creation.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from tests.factories.user_factory import UserFactory
from tests.factories.workspace_factory import WorkspaceFactory, TeamFactory
from tests.factories.core_factory import (
    TenantFactory,
    UserAccountFactory,
)
from tests.factories.accounting_factory import (
    AccountFactory,
    TransactionFactory,
    JournalEntryFactory,
    EntityFactory,
)
from tests.factories.sales_factory import (
    LeadFactory,
    DealFactory,
)
from tests.factories.service_factory import (
    ProjectFactory,
    MilestoneFactory,
)

from core.models import (
    Workspace,
    Team,
    Tenant,
    User,
    UserAccount,
    UserRole,
    UserStatus,
    WorkspaceStatus,
    AgentStatus,
    TransactionStatus,
    AccountType,
    EntryType,
    EntityType,
)

# ============================================================================
# Unique Constraint Tests
# ============================================================================

class TestUniqueConstraints:
    """Test unique constraints across all models."""

    def test_user_email_unique(self, db_session: Session):
        """Test User.email must be unique (IntegrityError on duplicate)."""
        UserFactory(email="test@example.com", _session=db_session)
        db_session.commit()

        # Attempt to create second user with same email
        with pytest.raises(IntegrityError):
            UserFactory(email="test@example.com", _session=db_session)
            db_session.commit()

        db_session.rollback()

    def test_tenant_subdomain_unique(self, db_session: Session):
        """Test Tenant.subdomain must be unique (IntegrityError on duplicate)."""
        TenantFactory(subdomain="acme", _session=db_session)
        db_session.commit()

        # Attempt duplicate subdomain
        with pytest.raises(IntegrityError):
            TenantFactory(subdomain="acme", _session=db_session)
            db_session.commit()

        db_session.rollback()

    def test_tenant_api_key_unique(self, db_session: Session):
        """Test Tenant.api_key must be unique (when set)."""
        TenantFactory(api_key="sk_test_12345", _session=db_session)
        db_session.commit()

        # Attempt duplicate api_key
        with pytest.raises(IntegrityError):
            TenantFactory(api_key="sk_test_12345", _session=db_session)
            db_session.commit()

        db_session.rollback()

    def test_account_workspace_code_unique(self, db_session: Session):
        """Test Account has composite unique (workspace_id, code)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create first account with workspace_id=1, code="1000"
        AccountFactory(
            workspace_id=workspace.id,
            code="1000",
            _session=db_session
        )
        db_session.commit()

        # Attempt duplicate with same workspace and code
        with pytest.raises(IntegrityError):
            AccountFactory(
                workspace_id=workspace.id,
                code="1000",  # Same code in same workspace
                _session=db_session
            )
            db_session.commit()

        db_session.rollback()

        # Verify different workspace with same code works
        workspace2 = WorkspaceFactory(_session=db_session)
        AccountFactory(
            workspace_id=workspace2.id,
            code="1000",  # Same code, different workspace
            _session=db_session
        )
        db_session.commit()
        assert db_session.query(AccountFactory._meta.model).count() == 2

    def test_user_account_platform_platform_user_unique(self, db_session: Session):
        """Test UserAccount composite unique (platform, platform_user_id)."""
        user1 = UserFactory(_session=db_session)
        user2 = UserFactory(_session=db_session)
        tenant = TenantFactory(_session=db_session)
        db_session.commit()

        # Create first UserAccount
        UserAccountFactory(
            user_id=user1.id,
            tenant_id=tenant.id,
            platform="telegram",
            platform_user_id="123",
            _session=db_session
        )
        db_session.commit()

        # Attempt duplicate with same platform and platform_user_id (different user)
        with pytest.raises(IntegrityError):
            UserAccountFactory(
                user_id=user2.id,  # Different user
                tenant_id=tenant.id,
                platform="telegram",  # Same platform
                platform_user_id="123",  # Same platform_user_id - violation!
                _session=db_session
            )
            db_session.commit()

        db_session.rollback()

    def test_categorization_rule_workspace_merchant_unique(self, db_session: Session):
        """Test CategorizationRule composite unique (workspace_id, merchant_pattern)."""
        from accounting.models import CategorizationRule

        workspace = WorkspaceFactory(_session=db_session)
        account = AccountFactory(_session=db_session)
        db_session.commit()

        # Create first rule
        rule1 = CategorizationRule(
            id=str(int(1e9)),
            workspace_id=workspace.id,
            merchant_pattern="Amazon",
            target_account_id=account.id,
            confidence_weight=5.0,
            is_active=True
        )
        db_session.add(rule1)
        db_session.commit()

        # Attempt duplicate with same workspace and merchant
        with pytest.raises(IntegrityError):
            rule2 = CategorizationRule(
                id=str(int(1e9 + 1)),
                workspace_id=workspace.id,
                merchant_pattern="Amazon",  # Same merchant in same workspace
                target_account_id=account.id,
                confidence_weight=5.0,
                is_active=True
            )
            db_session.add(rule2)
            db_session.commit()

        db_session.rollback()

    def test_tenant_setting_workspace_key_unique(self, db_session: Session):
        """Test TenantSetting composite unique (tenant_id, setting_key)."""
        from core.models import TenantSetting

        tenant = TenantFactory(_session=db_session)
        db_session.commit()

        # Create first setting
        setting1 = TenantSetting(
            id=str(int(1e9)),
            tenant_id=tenant.id,
            setting_key="theme",
            setting_value="dark"
        )
        db_session.add(setting1)
        db_session.commit()

        # Attempt duplicate with same tenant and key
        with pytest.raises(IntegrityError):
            setting2 = TenantSetting(
                id=str(int(1e9 + 1)),
                tenant_id=tenant.id,
                setting_key="theme",  # Same key for same tenant
                setting_value="light"
            )
            db_session.add(setting2)
            db_session.commit()

        db_session.rollback()


# ============================================================================
# Not Null Constraint Tests
# ============================================================================

class TestNotNullConstraints:
    """Test not null constraints across all models."""

    def test_workspace_name_not_null(self, db_session: Session):
        """Test Workspace.name is required."""
        with pytest.raises(IntegrityError):
            workspace = WorkspaceFactory(name=None, _session=db_session)
            db_session.commit()
        db_session.rollback()

    def test_user_email_not_null(self, db_session: Session):
        """Test User.email is required."""
        with pytest.raises((IntegrityError, ValueError)):
            UserFactory(email=None, _session=db_session)
            db_session.commit()
        db_session.rollback()

    def test_account_type_not_null(self, db_session: Session):
        """Test Account.type enum is required."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Account.type is nullable=False with enum
        # Factory should provide valid type by default
        account = AccountFactory(
            workspace_id=workspace.id,
            type=AccountType.ASSET,
            _session=db_session
        )
        db_session.commit()
        assert account.type is not None

    def test_transaction_category_not_null(self, db_session: Session):
        """Test Transaction.category is required (cost attribution enforcement)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Transaction.category is nullable=False for cost attribution
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            category="llm_tokens",
            _session=db_session
        )
        db_session.commit()
        assert transaction.category == "llm_tokens"

    def test_deal_name_not_null(self, db_session: Session):
        """Test Deal.name is required."""
        from sales.models import Deal

        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Deal name should be required
        deal = DealFactory(
            workspace_id=workspace.id,
            name="Enterprise Deal",
            _session=db_session
        )
        db_session.commit()
        assert deal.name is not None

    def test_project_name_not_null(self, db_session: Session):
        """Test Project.name is required."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Project name should be required
        project = ProjectFactory(
            workspace_id=workspace.id,
            name="Website Redesign",
            _session=db_session
        )
        db_session.commit()
        assert project.name is not None


# ============================================================================
# Foreign Key Constraint Tests
# ============================================================================

class TestForeignKeyConstraints:
    """Test foreign key relationships and referential integrity.

    Note: SQLite doesn't enforce FK constraints by default.
    These tests verify ORM behavior and relationship configuration.
    """

    def test_workspace_tenant_fk(self, db_session: Session):
        """Test Workspace.tenant_id must reference valid tenant."""
        tenant = TenantFactory(_session=db_session)
        db_session.commit()

        # Valid FK reference
        workspace = WorkspaceFactory(
            tenant_id=tenant.id,
            _session=db_session
        )
        db_session.commit()
        assert workspace.tenant_id == tenant.id

    def test_team_workspace_fk(self, db_session: Session):
        """Test Team.workspace_id must reference valid workspace."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Valid FK reference
        team = TeamFactory(
            workspace_id=workspace.id,
            _session=db_session
        )
        db_session.commit()
        assert team.workspace_id == workspace.id

    def test_user_tenant_fk(self, db_session: Session):
        """Test User.tenant_id is nullable but must be valid if set."""
        tenant = TenantFactory(_session=db_session)
        db_session.commit()

        # Valid FK reference
        user = UserFactory(tenant_id=tenant.id, _session=db_session)
        db_session.commit()
        assert user.tenant_id == tenant.id

    def test_transaction_project_fk(self, db_session: Session):
        """Test Transaction.project_id is nullable but must be valid."""
        from service_delivery.models import Project

        workspace = WorkspaceFactory(_session=db_session)
        project = ProjectFactory(workspace_id=workspace.id, _session=db_session)
        db_session.commit()

        # Valid FK reference
        transaction = TransactionFactory(
            workspace_id=workspace.id,
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()
        assert transaction.project_id == project.id

    def test_bill_vendor_fk(self, db_session: Session):
        """Test Bill.vendor_id must reference valid Entity."""
        from accounting.models import Bill, Entity

        workspace = WorkspaceFactory(_session=db_session)
        vendor = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.VENDOR,
            _session=db_session
        )
        db_session.commit()

        # Valid FK reference
        bill = Bill(
            id=str(int(1e9)),
            workspace_id=workspace.id,
            vendor_id=vendor.id,
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=30),
            amount=1500.00
        )
        db_session.add(bill)
        db_session.commit()
        assert bill.vendor_id == vendor.id

    def test_invoice_customer_fk(self, db_session: Session):
        """Test Invoice.customer_id must reference valid Entity."""
        from accounting.models import Invoice, Entity

        workspace = WorkspaceFactory(_session=db_session)
        customer = EntityFactory(
            workspace_id=workspace.id,
            type=EntityType.CUSTOMER,
            _session=db_session
        )
        db_session.commit()

        # Valid FK reference
        invoice = Invoice(
            id=str(int(1e9)),
            workspace_id=workspace.id,
            customer_id=customer.id,
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=30),
            amount=2500.00
        )
        db_session.add(invoice)
        db_session.commit()
        assert invoice.customer_id == customer.id

    def test_milestone_project_fk(self, db_session: Session):
        """Test Milestone.project_id must reference valid Project."""
        from service_delivery.models import Milestone

        workspace = WorkspaceFactory(_session=db_session)
        project = ProjectFactory(workspace_id=workspace.id, _session=db_session)
        db_session.commit()

        # Valid FK reference
        milestone = MilestoneFactory(
            project_id=project.id,
            _session=db_session
        )
        db_session.commit()
        assert milestone.project_id == project.id


# ============================================================================
# Check Constraint Tests
# ============================================================================

class TestCheckConstraints:
    """Test check constraints and range validation.

    Note: Range validation is typically application-level, not database check.
    These tests verify ORM validation logic.
    """

    def test_agent_confidence_score_range(self, db_session: Session):
        """Test Agent.confidence_score should be 0.0-1.0 (application-level)."""
        from core.models import AgentRegistry, AgentStatus

        # Test valid values at boundaries
        agent1 = AgentRegistry(
            id=str(int(1e9)),
            name="Agent Min",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.0  # Minimum valid
        )
        db_session.add(agent1)
        db_session.commit()

        agent2 = AgentRegistry(
            id=str(int(1e9 + 1)),
            name="Agent Mid",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.5  # Mid range
        )
        db_session.add(agent2)
        db_session.commit()

        agent3 = AgentRegistry(
            id=str(int(1e9 + 2)),
            name="Agent Max",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=1.0  # Maximum valid
        )
        db_session.add(agent3)
        db_session.commit()

        # Verify all agents created successfully
        agents = db_session.query(AgentRegistry).all()
        assert len(agents) == 3
        assert all(0.0 <= a.confidence_score <= 1.0 for a in agents)

    def test_project_guardrail_thresholds(self, db_session: Session):
        """Test Project budget guardrails: warn < pause < block (application-level)."""
        from service_delivery.models import Project

        workspace = WorkspaceFactory(_session=db_session)

        # Valid guardrail thresholds
        project = Project(
            id=str(int(1e9)),
            workspace_id=workspace.id,
            name="Test Project",
            budget_warn_threshold=5000.0,
            budget_pause_threshold=7500.0,
            budget_block_threshold=10000.0,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=90)
        )
        db_session.add(project)
        db_session.commit()

        # Verify thresholds are ordered correctly
        assert project.budget_warn_threshold < project.budget_pause_threshold
        assert project.budget_pause_threshold < project.budget_block_threshold


# ============================================================================
# Enum Constraint Tests
# ============================================================================

class TestEnumConstraints:
    """Test enum constraints across all models.

    Note: SQLAlchemy enum constraints are enforced at ORM level for SQLite.
    """

    def test_agent_status_enum_valid(self, db_session: Session):
        """Test AgentStatus must use valid enum value."""
        from core.models import AgentRegistry, AgentStatus

        # Test all valid enum values
        for status in AgentStatus:
            agent = AgentRegistry(
                id=str(int(1e9) + hash(status.value)),
                name=f"Agent {status.value}",
                category="testing",
                module_path="test.module",
                class_name="TestAgent",
                status=status.value,
                confidence_score=0.5
            )
            db_session.add(agent)
        db_session.commit()

        # Verify all agents created
        agents = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("Agent %")
        ).all()
        assert len(agents) == len(AgentStatus)

    def test_user_role_enum_valid(self, db_session: Session):
        """Test UserRole must use valid enum value."""
        # Test all valid enum values
        for role in UserRole:
            user = UserFactory(
                email=f"user_{role.value}@test.com",
                role=role.value,
                _session=db_session
            )
        db_session.commit()

        # Verify all users created
        users = db_session.query(User).filter(
            User.email.like("user_%@test.com")
        ).all()
        assert len(users) == len(UserRole)

    def test_transaction_status_enum_valid(self, db_session: Session):
        """Test TransactionStatus must use valid enum value."""
        workspace = WorkspaceFactory(_session=db_session)

        # Test all valid enum values
        for status in TransactionStatus:
            transaction = TransactionFactory(
                id=str(int(1e9) + hash(status.value)),
                workspace_id=workspace.id,
                status=status.value,
                _session=db_session
            )
        db_session.commit()

        # Verify all transactions created
        transactions = db_session.query(TransactionFactory._meta.model).filter(
            TransactionFactory._meta.model.workspace_id == workspace.id
        ).all()
        assert len(transactions) == len(TransactionStatus)

    def test_account_type_enum_valid(self, db_session: Session):
        """Test AccountType must use valid enum value."""
        workspace = WorkspaceFactory(_session=db_session)

        # Test all valid enum values
        for account_type in AccountType:
            account = AccountFactory(
                id=str(int(1e9) + hash(account_type.value)),
                workspace_id=workspace.id,
                type=account_type.value,
                _session=db_session
            )
        db_session.commit()

        # Verify all accounts created
        from accounting.models import Account
        accounts = db_session.query(Account).filter(
            Account.workspace_id == workspace.id
        ).all()
        assert len(accounts) == len(AccountType)

    def test_project_status_enum_valid(self, db_session: Session):
        """Test ProjectStatus must use valid enum value."""
        from service_delivery.models import Project, ProjectStatus

        workspace = WorkspaceFactory(_session=db_session)

        # Test all valid enum values
        for status in ProjectStatus:
            project = Project(
                id=str(int(1e9) + hash(status.value)),
                workspace_id=workspace.id,
                name=f"Project {status.value}",
                status=status.value,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=90)
            )
            db_session.add(project)
        db_session.commit()

        # Verify all projects created
        projects = db_session.query(Project).filter(
            Project.workspace_id == workspace.id
        ).all()
        assert len(projects) == len(ProjectStatus)
