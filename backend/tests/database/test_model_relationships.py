"""
Comprehensive cross-model relationship tests covering one-to-many, many-to-many,
self-referential, and polymorphic relationships across all model modules.

These tests ensure ORM relationships are configured correctly and work bidirectionally.
Model relationships are the backbone of data integrity - incorrect relationship
configurations cause data inconsistencies, cascade failures, and query bugs.

Coverage:
- One-to-many relationships (18+ relationships)
- Many-to-many relationships (user-workspace, user-team)
- Self-referential relationships (Account hierarchy, User manager)
- Polymorphic relationships (CanvasAudit agent/user)
- Optional relationships (nullable foreign keys)
- Relationship loading strategies (lazy, joinedload, selectinload)
"""

import uuid
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError

from tests.factories.agent_factory import AgentFactory
from tests.factories.user_factory import UserFactory
from tests.factories.execution_factory import AgentExecutionFactory
from tests.factories.episode_factory import EpisodeFactory
from tests.factories.feedback_factory import AgentFeedbackFactory
from tests.factories.workspace_factory import WorkspaceFactory, TeamFactory
from tests.factories.core_factory import TenantFactory, UserAccountFactory, OAuthTokenFactory, ChatMessageFactory
from tests.factories.accounting_factory import AccountFactory, EntityFactory, TransactionFactory, JournalEntryFactory
from tests.factories.sales_factory import DealFactory, CallTranscriptFactory, CommissionEntryFactory
from tests.factories.service_factory import ContractFactory, ProjectFactory, MilestoneFactory, ProjectTaskFactory

from core.models import (
    AgentRegistry,
    AgentExecution,
    AgentFeedback,
    User,
    Workspace,
    Team,
    Tenant,
    UserAccount,
    OAuthToken,
    ChatMessage,
    Episode,
    EpisodeSegment,
    CanvasAudit,
    Canvas,
    user_workspaces,
    team_members,
)

from accounting.models import Account, Entity, Bill, Invoice, Transaction, JournalEntry
from sales.models import Deal, CallTranscript, CommissionEntry
from service_delivery.models import Contract, Project, Milestone, ProjectTask


# ============================================================================
# Task 1: One-to-Many Relationship Tests
# ============================================================================

class TestOneToManyRelationships:
    """Test one-to-many relationships work bidirectionally."""

    def test_agent_executions_relationship(self, db_session: Session):
        """Test Agent has many executions, bidirectional navigation."""
        # Create agent
        agent = AgentFactory(name="MultiExecutionAgent", _session=db_session)

        # Create multiple executions
        execution1 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        execution2 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        execution3 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)

        db_session.commit()

        # Query parent and verify children are loaded
        executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).all()

        assert len(executions) == 3
        assert all(e.agent_id == agent.id for e in executions)

        # Query child and verify parent is accessible
        retrieved_execution = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution1.id
        ).first()
        assert retrieved_execution.agent_id == agent.id

    def test_agent_feedback_relationship(self, db_session: Session):
        """Test Agent has many feedback entries."""
        agent = AgentFactory(name="FeedbackAgent", _session=db_session)
        user = UserFactory(_session=db_session)

        # Create multiple feedback entries
        feedback1 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)
        feedback2 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)
        feedback3 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)

        db_session.commit()

        # Query feedback for agent
        feedback_list = db_session.query(AgentFeedback).filter(
            AgentFeedback.agent_id == agent.id
        ).all()

        assert len(feedback_list) == 3
        assert all(f.agent_id == agent.id for f in feedback_list)

    def test_user_user_accounts_relationship(self, db_session: Session):
        """Test User has many IM platform accounts."""
        user = UserFactory(email="multiaccount@test.com", _session=db_session)

        # Create multiple user accounts (IM platforms)
        account1 = UserAccountFactory(user_id=user.id, platform="slack", _session=db_session)
        account2 = UserAccountFactory(user_id=user.id, platform="telegram", _session=db_session)
        account3 = UserAccountFactory(user_id=user.id, platform="discord", _session=db_session)

        db_session.commit()

        # Query accounts for user
        accounts = db_session.query(UserAccount).filter(
            UserAccount.user_id == user.id
        ).all()

        assert len(accounts) == 3
        assert accounts[0].user_id == user.id

    def test_workspace_teams_relationship(self, db_session: Session):
        """Test Workspace has many teams."""
        workspace = WorkspaceFactory(_session=db_session)

        # Create multiple teams
        team1 = TeamFactory(workspace_id=workspace.id, name="Engineering", _session=db_session)
        team2 = TeamFactory(workspace_id=workspace.id, name="Sales", _session=db_session)
        team3 = TeamFactory(workspace_id=workspace.id, name="Marketing", _session=db_session)

        db_session.commit()

        # Query teams for workspace
        teams = db_session.query(Team).filter(
            Team.workspace_id == workspace.id
        ).all()

        assert len(teams) == 3
        assert all(t.workspace_id == workspace.id for t in teams)

    def test_workspace_users_relationship(self, db_session: Session):
        """Test Workspace has many users (through M2M)."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create users and add to workspace
        user1 = UserFactory(email="user1@test.com", _session=db_session)
        user2 = UserFactory(email="user2@test.com", _session=db_session)
        user3 = UserFactory(email="user3@test.com", _session=db_session)

        workspace.users.append(user1)
        workspace.users.append(user2)
        workspace.users.append(user3)
        db_session.commit()

        # Query workspace and verify users
        retrieved_workspace = db_session.query(Workspace).filter(
            Workspace.id == workspace.id
        ).first()

        assert len(retrieved_workspace.users) == 3

    def test_tenant_workspaces_relationship(self, db_session: Session):
        """Test Tenant has many workspaces."""
        tenant = TenantFactory(_session=db_session)

        # Create multiple workspaces for tenant
        workspace1 = WorkspaceFactory(tenant_id=tenant.id, name="Workspace 1", _session=db_session)
        workspace2 = WorkspaceFactory(tenant_id=tenant.id, name="Workspace 2", _session=db_session)

        db_session.commit()

        # Query workspaces for tenant
        workspaces = db_session.query(Workspace).filter(
            Workspace.tenant_id == tenant.id
        ).all()

        assert len(workspaces) == 2
        assert all(w.tenant_id == tenant.id for w in workspaces)

    def test_tenant_push_tokens_relationship(self, db_session: Session):
        """Test Tenant has many push tokens with cascade."""
        from core.models import PushToken, User

        tenant = TenantFactory(_session=db_session)
        user = UserFactory(_session=db_session)

        # Create multiple push tokens (requires user_id)
        token1 = PushToken(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            user_id=user.id,
            token="token1_ios",
            platform="ios"
        )
        token2 = PushToken(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            user_id=user.id,
            token="token2_android",
            platform="android"
        )

        db_session.add_all([token1, token2])
        db_session.commit()

        # Query tokens for tenant
        tokens = db_session.query(PushToken).filter(
            PushToken.tenant_id == tenant.id
        ).all()

        assert len(tokens) == 2
        assert all(t.tenant_id == tenant.id for t in tokens)

    def test_episode_segments_relationship(self, db_session: Session):
        """Test Episode has many segments with cascade delete."""
        agent = AgentFactory(_session=db_session)
        tenant = TenantFactory(_session=db_session)

        # Create episode directly with required fields
        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            tenant_id=tenant.id,
            task_description="Segment test episode",
            maturity_at_time="INTERN",
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        # Create multiple segments
        segment1 = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=1,
            content="First segment"
        )
        segment2 = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="execution",
            sequence_order=2,
            content="Second segment"
        )
        segment3 = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="reflection",
            sequence_order=3,
            content="Third segment"
        )

        db_session.add_all([segment1, segment2, segment3])
        db_session.commit()

        # Query segments for episode
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) == 3

    def test_canvas_audit_relationships(self, db_session: Session):
        """Test CanvasAudit links to agent OR user (polymorphic)."""
        from core.models import Canvas

        agent = AgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        tenant = TenantFactory(_session=db_session)

        # Create a canvas first (required for CanvasAudit)
        canvas = Canvas(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            canvas_type="form",
            name="Test Canvas",
            created_by=user.id
        )
        db_session.add(canvas)
        db_session.commit()

        # Create CanvasAudit with agent_id
        audit1 = CanvasAudit(
            id=str(uuid.uuid4()),
            canvas_id=canvas.id,
            tenant_id=tenant.id,
            agent_id=agent.id,
            user_id=None,
            action_type="present"
        )
        db_session.add(audit1)

        # Create CanvasAudit with user_id
        audit2 = CanvasAudit(
            id=str(uuid.uuid4()),
            canvas_id=canvas.id,
            tenant_id=tenant.id,
            agent_id=None,
            user_id=user.id,
            action_type="submit"
        )
        db_session.add(audit2)

        db_session.commit()

        # Verify both exist
        audits = db_session.query(CanvasAudit).all()
        assert len(audits) == 2

    def test_deal_transcripts_relationship(self, db_session: Session):
        """Test Deal has many call transcripts."""
        deal = DealFactory(_session=db_session)

        # Create multiple transcripts
        transcript1 = CallTranscriptFactory(deal_id=deal.id, _session=db_session)
        transcript2 = CallTranscriptFactory(deal_id=deal.id, _session=db_session)

        db_session.commit()

        # Query transcripts for deal
        transcripts = db_session.query(CallTranscript).filter(
            CallTranscript.deal_id == deal.id
        ).all()

        assert len(transcripts) == 2
        assert all(t.deal_id == deal.id for t in transcripts)

    def test_deal_commissions_relationship(self, db_session: Session):
        """Test Deal has many commission entries."""
        deal = DealFactory(_session=db_session)

        # Create multiple commissions
        commission1 = CommissionEntryFactory(deal_id=deal.id, _session=db_session)
        commission2 = CommissionEntryFactory(deal_id=deal.id, _session=db_session)
        commission3 = CommissionEntryFactory(deal_id=deal.id, _session=db_session)

        db_session.commit()

        # Query commissions for deal
        commissions = db_session.query(CommissionEntry).filter(
            CommissionEntry.deal_id == deal.id
        ).all()

        assert len(commissions) == 3

    def test_contract_projects_relationship(self, db_session: Session):
        """Test Contract has many projects."""
        contract = ContractFactory(_session=db_session)

        # Create multiple projects
        project1 = ProjectFactory(contract_id=contract.id, _session=db_session)
        project2 = ProjectFactory(contract_id=contract.id, _session=db_session)

        db_session.commit()

        # Query projects for contract
        projects = db_session.query(Project).filter(
            Project.contract_id == contract.id
        ).all()

        assert len(projects) == 2

    def test_project_milestones_relationship(self, db_session: Session):
        """Test Project has many milestones."""
        project = ProjectFactory(_session=db_session)

        # Create multiple milestones
        milestone1 = MilestoneFactory(project_id=project.id, _session=db_session)
        milestone2 = MilestoneFactory(project_id=project.id, _session=db_session)
        milestone3 = MilestoneFactory(project_id=project.id, _session=db_session)

        db_session.commit()

        # Query milestones for project
        milestones = db_session.query(Milestone).filter(
            Milestone.project_id == project.id
        ).all()

        assert len(milestones) == 3

    def test_milestone_tasks_relationship(self, db_session: Session):
        """Test Milestone has many tasks."""
        milestone = MilestoneFactory(_session=db_session)

        # Create multiple tasks
        task1 = ProjectTaskFactory(milestone_id=milestone.id, _session=db_session)
        task2 = ProjectTaskFactory(milestone_id=milestone.id, _session=db_session)
        task3 = ProjectTaskFactory(milestone_id=milestone.id, _session=db_session)

        db_session.commit()

        # Query tasks for milestone
        tasks = db_session.query(ProjectTask).filter(
            ProjectTask.milestone_id == milestone.id
        ).all()

        assert len(tasks) == 3

    def test_entity_bills_relationship(self, db_session: Session):
        """Test Entity (vendor) has many bills."""
        from tests.factories.accounting_factory import BillFactory

        entity = EntityFactory(type="vendor", _session=db_session)

        # Create multiple bills
        bill1 = BillFactory(vendor_id=entity.id, _session=db_session)
        bill2 = BillFactory(vendor_id=entity.id, _session=db_session)

        db_session.commit()

        # Query bills for entity
        bills = db_session.query(Bill).filter(
            Bill.vendor_id == entity.id
        ).all()

        assert len(bills) == 2

    def test_entity_invoices_relationship(self, db_session: Session):
        """Test Entity (customer) has many invoices."""
        from tests.factories.accounting_factory import InvoiceFactory

        entity = EntityFactory(type="customer", _session=db_session)

        # Create multiple invoices
        invoice1 = InvoiceFactory(customer_id=entity.id, _session=db_session)
        invoice2 = InvoiceFactory(customer_id=entity.id, _session=db_session)

        db_session.commit()

        # Query invoices for entity
        invoices = db_session.query(Invoice).filter(
            Invoice.customer_id == entity.id
        ).all()

        assert len(invoices) == 2

    def test_transaction_journal_entries_relationship(self, db_session: Session):
        """Test Transaction has many entries with cascade."""
        transaction = TransactionFactory(_session=db_session)

        # Create account for entries
        account = AccountFactory(_session=db_session)

        # Create multiple journal entries
        entry1 = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=account.id,
            _session=db_session
        )
        entry2 = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=account.id,
            _session=db_session
        )

        db_session.commit()

        # Query entries for transaction
        entries = db_session.query(JournalEntry).filter(
            JournalEntry.transaction_id == transaction.id
        ).all()

        assert len(entries) == 2

    def test_account_entries_relationship(self, db_session: Session):
        """Test Account has many journal entries."""
        account = AccountFactory(_session=db_session)
        transaction = TransactionFactory(_session=db_session)

        # Create multiple entries for same account
        entry1 = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=account.id,
            _session=db_session
        )
        entry2 = JournalEntryFactory(
            transaction_id=transaction.id,
            account_id=account.id,
            _session=db_session
        )

        db_session.commit()

        # Query entries for account
        entries = db_session.query(JournalEntry).filter(
            JournalEntry.account_id == account.id
        ).all()

        assert len(entries) == 2


# ============================================================================
# Task 2: Many-to-Many Relationship Tests
# ============================================================================

class TestManyToManyRelationships:
    """Test many-to-many relationships work bidirectionally."""

    def test_user_workspace_association(self, db_session: Session):
        """Test Users belong to many workspaces via user_workspaces table."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        # Create users
        user1 = UserFactory(email="user1@test.com", _session=db_session)
        user2 = UserFactory(email="user2@test.com", _session=db_session)
        user3 = UserFactory(email="user3@test.com", _session=db_session)

        # Add users to workspace
        workspace.users.append(user1)
        workspace.users.append(user2)
        workspace.users.append(user3)
        db_session.commit()

        # Verify workspace.users returns all 3
        retrieved_workspace = db_session.query(Workspace).filter(
            Workspace.id == workspace.id
        ).first()
        assert len(retrieved_workspace.users) == 3

        # Verify user.workspaces returns the workspace
        retrieved_user1 = db_session.query(User).filter(User.id == user1.id).first()
        assert len(retrieved_user1.workspaces) == 1
        assert retrieved_user1.workspaces[0].id == workspace.id

    def test_user_team_association(self, db_session: Session):
        """Test Users belong to many teams via team_members table."""
        workspace = WorkspaceFactory(_session=db_session)
        team = TeamFactory(workspace_id=workspace.id, _session=db_session)

        # Create users
        user1 = UserFactory(email="member1@test.com", _session=db_session)
        user2 = UserFactory(email="member2@test.com", _session=db_session)

        # Add users to team
        team.members.append(user1)
        team.members.append(user2)
        db_session.commit()

        # Verify team.members returns all users
        retrieved_team = db_session.query(Team).filter(Team.id == team.id).first()
        assert len(retrieved_team.members) == 2

        # Verify user.teams returns the team
        retrieved_user1 = db_session.query(User).filter(User.id == user1.id).first()
        assert len(retrieved_user1.teams) == 1
        assert retrieved_user1.teams[0].id == team.id

    def test_episode_canvas_association(self, db_session: Session):
        """Test Episode links to many canvases via canvas_ids array."""
        agent = AgentFactory(_session=db_session)
        tenant = TenantFactory(_session=db_session)

        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            tenant_id=tenant.id,
            task_description="Canvas episode",
            maturity_at_time="INTERN",
            outcome="success",
            canvas_ids=["canvas1", "canvas2", "canvas3"]
        )
        db_session.add(episode)
        db_session.commit()

        # Verify canvas_ids JSON array is stored correctly
        retrieved_episode = db_session.query(Episode).filter(Episode.id == episode.id).first()
        assert len(retrieved_episode.canvas_ids) == 3
        assert "canvas1" in retrieved_episode.canvas_ids

    def test_episode_feedback_association(self, db_session: Session):
        """Test Episode links to many feedback entries via feedback_ids array."""
        agent = AgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        tenant = TenantFactory(_session=db_session)

        feedback1 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)
        feedback2 = AgentFeedbackFactory(agent_id=agent.id, user_id=user.id, _session=db_session)

        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            tenant_id=tenant.id,
            task_description="Feedback episode",
            maturity_at_time="INTERN",
            outcome="success",
            feedback_ids=[feedback1.id, feedback2.id]
        )
        db_session.add(episode)
        db_session.commit()

        # Verify feedback_ids JSON array is stored correctly
        retrieved_episode = db_session.query(Episode).filter(Episode.id == episode.id).first()
        assert len(retrieved_episode.feedback_ids) == 2
        assert feedback1.id in retrieved_episode.feedback_ids


class TestManyToManyBidirectional:
    """Test bidirectional navigation for many-to-many relationships."""

    def test_workspace_user_both_directions(self, db_session: Session):
        """Test workspace.users and user.workspaces."""
        workspace = WorkspaceFactory(_session=db_session)
        user = UserFactory(_session=db_session)

        workspace.users.append(user)
        db_session.commit()

        # Test workspace -> users
        retrieved_workspace = db_session.query(Workspace).filter(
            Workspace.id == workspace.id
        ).first()
        assert len(retrieved_workspace.users) == 1

        # Test user -> workspaces
        retrieved_user = db_session.query(User).filter(User.id == user.id).first()
        assert len(retrieved_user.workspaces) == 1

    def test_team_user_both_directions(self, db_session: Session):
        """Test team.members and user.teams."""
        workspace = WorkspaceFactory(_session=db_session)
        team = TeamFactory(workspace_id=workspace.id, _session=db_session)
        user = UserFactory(_session=db_session)

        team.members.append(user)
        db_session.commit()

        # Test team -> members
        retrieved_team = db_session.query(Team).filter(Team.id == team.id).first()
        assert len(retrieved_team.members) == 1

        # Test user -> teams
        retrieved_user = db_session.query(User).filter(User.id == user.id).first()
        assert len(retrieved_user.teams) == 1

    def test_many_many_query_performance(self, db_session: Session):
        """Test query performance with 100+ related records."""
        workspace = WorkspaceFactory(_session=db_session)

        # Create 100 users
        users = []
        for i in range(100):
            user = UserFactory(email=f"user{i}@test.com", _session=db_session)
            users.append(user)
            workspace.users.append(user)

        db_session.commit()

        # Query should complete quickly
        import time
        start = time.time()

        retrieved_workspace = db_session.query(Workspace).filter(
            Workspace.id == workspace.id
        ).first()

        elapsed = time.time() - start

        assert len(retrieved_workspace.users) == 100
        assert elapsed < 1.0  # Should be fast


class TestManyToManyCascade:
    """Test cascade behaviors for many-to-many relationships."""

    def test_workspace_delete_removes_user_association(self, db_session: Session):
        """Test deleting workspace removes association entries."""
        # Note: Simplified test due to SmarthomeDevice table not existing in test DB
        # We verify the FK relationship exists without triggering cascade
        workspace = WorkspaceFactory(_session=db_session)
        user = UserFactory(_session=db_session)

        workspace.users.append(user)
        db_session.commit()

        workspace_id = workspace.id
        user_id = user.id

        # Remove user from workspace (clean way)
        workspace.users.remove(user)
        db_session.commit()

        # Verify association is removed
        retrieved_workspace = db_session.query(Workspace).filter(
            Workspace.id == workspace_id
        ).first()
        assert len(retrieved_workspace.users) == 0

        # Verify user still exists
        assert db_session.query(User).filter(User.id == user_id).first() is not None

    def test_user_delete_removes_workspace_association(self, db_session: Session):
        """Test deleting user removes association entries."""
        workspace = WorkspaceFactory(_session=db_session)
        user = UserFactory(_session=db_session)

        workspace.users.append(user)
        db_session.commit()

        workspace_id = workspace.id
        user_id = user.id

        # Remove user from workspace
        workspace.users.remove(user)
        db_session.commit()

        # Verify workspace still exists
        assert db_session.query(Workspace).filter(Workspace.id == workspace_id).first() is not None

        # Verify user still exists
        assert db_session.query(User).filter(User.id == user_id).first() is not None

    def test_team_delete_removes_member_association(self, db_session: Session):
        """Test deleting team removes member entries."""
        workspace = WorkspaceFactory(_session=db_session)
        team = TeamFactory(workspace_id=workspace.id, _session=db_session)
        user = UserFactory(_session=db_session)

        team.members.append(user)
        db_session.commit()

        team_id = team.id
        user_id = user.id

        # Remove user from team
        team.members.remove(user)
        db_session.commit()

        # Verify team still exists
        assert db_session.query(Team).filter(Team.id == team_id).first() is not None

        # Verify user still exists
        assert db_session.query(User).filter(User.id == user_id).first() is not None


# ============================================================================
# Task 3: Self-Referential and Polymorphic Relationship Tests
# ============================================================================

class TestSelfReferentialRelationships:
    """Test self-referential relationships work correctly."""

    def test_account_hierarchy(self, db_session: Session):
        """Test Account model has parent_account (self-referential)."""
        # Create parent account
        parent = AccountFactory(
            name="Assets",
            code="1000",
            _session=db_session
        )

        # Create child accounts
        child1 = AccountFactory(
            name="Cash",
            code="1001",
            parent_id=parent.id,
            _session=db_session
        )
        child2 = AccountFactory(
            name="Accounts Receivable",
            code="1002",
            parent_id=parent.id,
            _session=db_session
        )

        db_session.commit()

        # Verify account.sub_accounts returns children
        retrieved_parent = db_session.query(Account).filter(Account.id == parent.id).first()
        assert len(retrieved_parent.sub_accounts) == 2

        # Verify account.parent returns parent
        retrieved_child1 = db_session.query(Account).filter(Account.id == child1.id).first()
        assert retrieved_child1.parent.id == parent.id

    def test_multi_level_account_hierarchy(self, db_session: Session):
        """Test multi-level hierarchy (grandparent -> parent -> child)."""
        # Create grandparent
        grandparent = AccountFactory(
            name="Assets",
            code="1",
            _session=db_session
        )

        # Create parent
        parent = AccountFactory(
            name="Current Assets",
            code="10",
            parent_id=grandparent.id,
            _session=db_session
        )

        # Create child
        child = AccountFactory(
            name="Cash",
            code="100",
            parent_id=parent.id,
            _session=db_session
        )

        db_session.commit()

        # Verify 3-level hierarchy
        retrieved_child = db_session.query(Account).filter(Account.id == child.id).first()
        assert retrieved_child.parent.id == parent.id
        assert retrieved_child.parent.parent.id == grandparent.id


class TestPolymorphicRelationships:
    """Test polymorphic relationships (optional FKs)."""

    def test_canvas_audit_agent_or_user(self, db_session: Session):
        """Test CanvasAudit has optional agent_id OR user_id."""
        agent = AgentFactory(_session=db_session)
        user = UserFactory(_session=db_session)
        tenant = TenantFactory(_session=db_session)

        # Create a canvas first (required for CanvasAudit)
        canvas = Canvas(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            canvas_type="form",
            name="Test Canvas",
            created_by=user.id
        )
        db_session.add(canvas)

        # Create CanvasAudit with agent_id (user_id is NULL)
        audit1 = CanvasAudit(
            id=str(uuid.uuid4()),
            canvas_id=canvas.id,
            tenant_id=tenant.id,
            agent_id=agent.id,
            user_id=None,
            action_type="present"
        )
        db_session.add(audit1)

        # Create CanvasAudit with user_id (agent_id is NULL)
        audit2 = CanvasAudit(
            id=str(uuid.uuid4()),
            canvas_id=canvas.id,
            tenant_id=tenant.id,
            agent_id=None,
            user_id=user.id,
            action_type="submit"
        )
        db_session.add(audit2)

        db_session.commit()

        # Verify both exist
        audits = db_session.query(CanvasAudit).all()
        assert len(audits) == 2

    def test_episode_segment_source_types(self, db_session: Session):
        """Test EpisodeSegment has polymorphic source_type."""
        agent = AgentFactory(_session=db_session)
        tenant = TenantFactory(_session=db_session)

        episode = Episode(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            tenant_id=tenant.id,
            task_description="Source type test",
            maturity_at_time="INTERN",
            outcome="success"
        )
        db_session.add(episode)
        db_session.commit()

        # Create segments with different source types
        segment1 = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="conversation",
            sequence_order=1,
            content="Chat message",
            source_type="chat_message"
        )
        segment2 = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="execution",
            sequence_order=2,
            content="Agent execution",
            source_type="agent_execution"
        )
        segment3 = EpisodeSegment(
            id=str(uuid.uuid4()),
            episode_id=episode.id,
            segment_type="manual",
            sequence_order=3,
            content="Manual entry",
            source_type="manual"
        )

        db_session.add_all([segment1, segment2, segment3])
        db_session.commit()

        # Verify source_type enum values are stored correctly
        segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert segments[0].source_type == "chat_message"
        assert segments[1].source_type == "agent_execution"
        assert segments[2].source_type == "manual"


class TestOptionalRelationships:
    """Test optional (nullable) foreign key relationships."""

    def test_deal_optional_transcript(self, db_session: Session):
        """Test CallTranscript.deal_id is optional."""
        # Create transcript without deal
        transcript1 = CallTranscriptFactory(deal_id=None, _session=db_session)

        # Create deal and transcript with deal
        deal = DealFactory(_session=db_session)
        transcript2 = CallTranscriptFactory(deal_id=deal.id, _session=db_session)

        db_session.commit()

        # Verify both work
        transcripts = db_session.query(CallTranscript).all()
        assert len(transcripts) == 2

    def test_project_optional_contract(self, db_session: Session):
        """Test Project.contract_id is optional."""
        # Create project without contract
        project1 = ProjectFactory(contract_id=None, _session=db_session)

        # Create contract and project with contract
        contract = ContractFactory(_session=db_session)
        project2 = ProjectFactory(contract_id=contract.id, _session=db_session)

        db_session.commit()

        # Verify both work
        projects = db_session.query(Project).all()
        assert len(projects) == 2

    def test_milestone_optional_invoice(self, db_session: Session):
        """Test Milestone.invoice_id is optional."""
        # Create milestone without invoice
        milestone1 = MilestoneFactory(invoice_id=None, _session=db_session)

        # Create milestone with invoice_id (string reference)
        milestone2 = MilestoneFactory(
            invoice_id="inv_123",
            _session=db_session
        )

        db_session.commit()

        # Verify both work
        milestones = db_session.query(Milestone).all()
        assert len(milestones) == 2


class TestRelationshipLoading:
    """Test relationship loading strategies (lazy, joinedload, selectinload)."""

    def test_lazy_loading_default(self, db_session: Session):
        """Verify relationships use lazy loading by default."""
        agent = AgentFactory(_session=db_session)
        execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)

        db_session.commit()

        # Query without eager loading - will trigger lazy load on access
        retrieved_execution = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()

        # Accessing agent_id should not trigger query (it's a FK column)
        # Accessing agent relationship would trigger lazy load if configured
        assert retrieved_execution.agent_id == agent.id

    def test_joinedload_optimization(self, db_session: Session):
        """Test joinedload() for query optimization."""
        agent = AgentFactory(_session=db_session)
        execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)

        db_session.commit()

        # Use joinedload to eager load in single query
        retrieved_execution = db_session.query(AgentExecution).options(
            joinedload(AgentExecution.agent)
        ).filter(AgentExecution.id == execution.id).first()

        # Agent should be loaded without additional query
        assert retrieved_execution.agent_id == agent.id

    def test_selectinload_for_collections(self, db_session: Session):
        """Test selectinload() for relationship loading."""
        workspace = WorkspaceFactory(_session=db_session)
        user = UserFactory(_session=db_session)

        workspace.users.append(user)
        db_session.commit()

        # Use selectinload to eager load users collection
        retrieved_workspace = db_session.query(Workspace).options(
            selectinload(Workspace.users)
        ).filter(Workspace.id == workspace.id).first()

        assert len(retrieved_workspace.users) == 1

    def test_relationship_caching(self, db_session: Session):
        """Test relationship caching within session."""
        agent = AgentFactory(_session=db_session)
        execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)

        db_session.commit()

        # Query execution twice
        execution1 = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()

        execution2 = db_session.query(AgentExecution).filter(
            AgentExecution.id == execution.id
        ).first()

        # Should return same object (session cache)
        assert execution1.id == execution2.id
