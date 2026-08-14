"""
Tests for proposal episode creation via ProposalService.

Wave 116 (2026-08-13): rewritten against the current async API and current
Episode schema. The previous version used a phantom AgentProposal surface
(proposed_action= / reasoning= / proposed_by= constructor kwargs,
Episode.proposal_outcome / Episode.rejection_reason / Episode.human_edits
columns) and called approve/reject without user_id — it failed 13/13.

Now aligned: proposals carry proposal_data, episodes expose outcome/reason/
edits via metadata_json, and executors are mocked so no real canvas/browser
side effects run. Uses a fresh in-memory DB per test.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, strategies as st
from hypothesis import HealthCheck
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    Episode,
    EpisodeSegment,
    ProposalStatus,
    ProposalType,
    User,
    Workspace,
)
from core.proposal_service import ProposalService
from core.models_registration import Base


@pytest.fixture
def db():
    """Fresh in-memory database session with full schema (per test)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def user(db: Session):
    """Create test user."""
    user = User(
        id=f"test_proposal_user_{uuid.uuid4()}",
        email=f"proposal_test-{uuid.uuid4()}@example.com",
        first_name="Proposal",
        last_name="Test User",
        role="member",
        status="active",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def workspace(db: Session, user: User):
    """Create test workspace."""
    workspace = Workspace(
        id=f"test_ws_{uuid.uuid4()}",
        name="Proposal Test Workspace",
    )
    db.add(workspace)
    db.commit()
    return workspace


@pytest.fixture
def intern_agent(db: Session, workspace: Workspace, user: User):
    """Create INTERN agent."""
    agent = AgentRegistry(
        id=f"test_intern_agent_{uuid.uuid4()}",
        name="Test Intern Agent Proposal",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        user_id=user.id,
        tenant_id="default",
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture
def proposal_factory(db: Session, intern_agent: AgentRegistry, user: User):
    """Factory to create proposals against the current schema."""

    def _create_proposal(
        title: str = "Test Proposal",
        reasoning: str = "Test reasoning",
        proposal_data: dict = None,
    ) -> AgentProposal:
        proposal = AgentProposal(
            id=f"test_proposal_{uuid.uuid4().hex[:8]}",
            tenant_id="default",
            user_id=user.id,
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=ProposalType.ACTION.value,
            title=title,
            description=f"Proposal with reasoning: {reasoning}",
            proposal_data=proposal_data or {
                "action_type": "canvas_present",
                "canvas_type": "chart",
                "reasoning": reasoning,
            },
            status=ProposalStatus.PENDING_APPROVAL.value,
            created_at=datetime(2026, 8, 1, 12, 0, 0),
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        return proposal

    return _create_proposal


def _service(db, *, execute_result=None):
    """ProposalService with a mocked action executor (no real side effects)."""
    service = ProposalService(db)
    service._execute_proposed_action_with = AsyncMock(
        return_value=execute_result if execute_result is not None
        else {"success": True, "result": "ok"}
    )
    return service


def _learning_patch():
    """Patch AgentLearningEnhanced so its record_* calls are awaitable."""
    learning_cls = MagicMock()
    learning_cls.return_value.record_user_correction = AsyncMock()
    learning_cls.return_value.record_rejection = AsyncMock()
    return patch("core.proposal_service.AgentLearningEnhanced", learning_cls)


def _find_episode(db, proposal):
    return db.query(Episode).filter(
        Episode.proposal_id == proposal.id
    ).first()


class TestProposalEpisodeCreation:
    """Test proposal episode creation functionality."""

    @pytest.mark.asyncio
    async def test_create_episode_from_approved_proposal(
        self, db: Session, proposal_factory, user: User
    ):
        """Test creating episode from approved proposal."""
        proposal = proposal_factory(title="Test Approval Proposal")

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(proposal.id, user.id)

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert episode.agent_id == proposal.agent_id
        assert episode.proposal_id == proposal.id
        assert episode.metadata_json["proposal_outcome"] == "approved"
        assert episode.maturity_at_time == AgentStatus.INTERN.value
        assert episode.outcome == "success"

    @pytest.mark.asyncio
    async def test_create_episode_from_rejected_proposal(
        self, db: Session, proposal_factory, user: User
    ):
        """Test creating episode from rejected proposal."""
        proposal = proposal_factory(title="Test Rejection Proposal")
        rejection_reason = "Insufficient justification"

        service = _service(db)
        with _learning_patch():
            await service.reject_proposal(proposal.id, user.id, rejection_reason)

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert episode.metadata_json["proposal_outcome"] == "rejected"
        assert episode.metadata_json["rejection_reason"] == rejection_reason
        assert episode.outcome == "failure"
        assert episode.supervision_decision == "rejected"

    @pytest.mark.asyncio
    async def test_episode_with_modifications(
        self, db: Session, proposal_factory, user: User
    ):
        """Test episode captures proposal modifications."""
        proposal = proposal_factory()
        modifications = {"param1": "updated_value", "param2": "new_param"}

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(
                proposal.id, user.id, modifications=modifications
            )

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert episode.metadata_json["human_edits"] == [
            {"param1": "updated_value"}, {"param2": "new_param"}
        ]
        assert episode.importance_score >= 0.6  # modifications boost

    @pytest.mark.asyncio
    async def test_episode_importance_for_rejected_proposals(
        self, db: Session, proposal_factory, user: User
    ):
        """Test rejected proposals have higher importance scores."""
        approved_proposal = proposal_factory(title="Approved Test")
        rejected_proposal = proposal_factory(title="Rejected Test")

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(approved_proposal.id, user.id)
            await service.reject_proposal(
                rejected_proposal.id, user.id, "Not good enough"
            )

        approved_episode = _find_episode(db, approved_proposal)
        rejected_episode = _find_episode(db, rejected_proposal)

        assert approved_episode is not None
        assert rejected_episode is not None
        # Rejected should have higher importance (learning opportunity)
        assert rejected_episode.importance_score > approved_episode.importance_score

    @pytest.mark.asyncio
    async def test_episode_segments_created(
        self, db: Session, proposal_factory, user: User
    ):
        """Test episode includes proposal and outcome segments."""
        proposal = proposal_factory()

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(proposal.id, user.id)

        episode = _find_episode(db, proposal)
        segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()

        assert len(segments) >= 2  # Proposal + outcome segments
        segment_types = {s.segment_type for s in segments}
        assert "proposal" in segment_types
        assert "reflection" in segment_types

    @pytest.mark.asyncio
    async def test_episode_topics_from_proposal(
        self, db: Session, proposal_factory, user: User
    ):
        """Test topics extracted from proposal content."""
        proposal = proposal_factory(
            title="Financial Report Analysis Proposal",
            reasoning="This proposal analyzes financial data and generates insights",
        )

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(proposal.id, user.id)

        episode = _find_episode(db, proposal)
        assert episode.topics is not None
        assert len(episode.topics) > 0
        # action type is always included
        assert any("canvas" in t.lower() for t in episode.topics)

    @pytest.mark.asyncio
    async def test_human_intervention_count_set(
        self, db: Session, proposal_factory, user: User
    ):
        """Test proposal episodes have intervention_count = 1."""
        proposal = proposal_factory()

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(proposal.id, user.id)

        episode = _find_episode(db, proposal)
        assert episode.human_intervention_count == 1  # Human approval/rejection

    @pytest.mark.asyncio
    async def test_execution_failure_still_creates_episode(
        self, db: Session, proposal_factory, user: User
    ):
        """Failed executions record a failure episode."""
        proposal = proposal_factory()

        service = _service(db, execute_result={"success": False, "error": "boom"})
        with _learning_patch():
            result = await service.approve_proposal(proposal.id, user.id)

        assert result["success"] is False
        episode = _find_episode(db, proposal)
        assert episode is not None
        assert episode.metadata_json["proposal_outcome"] == "failed"
        assert episode.outcome == "failure"


# ============================================================================
# Property-Based Tests
# ============================================================================

class TestProposalEpisodeProperties:
    """Property-based tests for proposal episode creation."""

    @given(
        title=st.text(min_size=5, max_size=50).filter(lambda x: len(x.strip()) > 0),
        reasoning=st.text(min_size=10, max_size=200).filter(lambda x: len(x.strip()) > 0),
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_episode_content_preservation(
        self,
        db: Session,
        proposal_factory,
        user: User,
        title,
        reasoning,
    ):
        """Test proposal content is preserved in episode."""
        proposal = proposal_factory(
            title=title.strip(),
            reasoning=reasoning.strip(),
        )

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(proposal.id, user.id)

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert title.strip() in episode.task_description
        assert len(episode.topics) > 0

    @given(
        modifications_dict=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.text(min_size=1, max_size=50),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_modifications_preserved_in_episode(
        self,
        db: Session,
        proposal_factory,
        user: User,
        modifications_dict,
    ):
        """Test modifications are preserved in episode."""
        if not modifications_dict:
            return  # Skip empty modifications

        proposal = proposal_factory()

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(
                proposal.id, user.id, modifications=modifications_dict
            )

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert len(episode.metadata_json["human_edits"]) == len(modifications_dict)

    @given(
        rejection_reason=st.text(min_size=10, max_size=200).filter(
            lambda x: len(x.strip()) > 0
        ),
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_rejection_reason_preserved(
        self,
        db: Session,
        proposal_factory,
        user: User,
        rejection_reason,
    ):
        """Test rejection reason is preserved in episode."""
        proposal = proposal_factory()

        service = _service(db)
        with _learning_patch():
            await service.reject_proposal(
                proposal.id, user.id, rejection_reason.strip()
            )

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert episode.metadata_json["rejection_reason"] == rejection_reason.strip()
        assert episode.metadata_json["proposal_outcome"] == "rejected"

    @given(
        outcome=st.sampled_from(["approved", "rejected"]),
    )
    @settings(max_examples=2, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_outcome_recorded_correctly(
        self,
        db: Session,
        proposal_factory,
        user: User,
        outcome,
    ):
        """Test proposal outcome is recorded correctly."""
        proposal = proposal_factory()

        service = _service(db)
        with _learning_patch():
            if outcome == "approved":
                await service.approve_proposal(proposal.id, user.id)
            else:
                await service.reject_proposal(
                    proposal.id, user.id, "Test rejection"
                )

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert episode.metadata_json["proposal_outcome"] == outcome

    @given(
        st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_importance_score_bounds(
        self,
        db: Session,
        proposal_factory,
        user: User,
        modification_count,
    ):
        """Test importance score within valid bounds."""
        proposal = proposal_factory()

        modifications = {f"key_{i}": f"value_{i}" for i in range(modification_count)}

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(
                proposal.id,
                user.id,
                modifications=modifications if modifications else None,
            )

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert 0.0 <= episode.importance_score <= 1.0

    @given(
        st.lists(
            st.text(min_size=1, max_size=20),
            min_size=1,
            max_size=10,
            unique=True,
        )
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.asyncio
    async def test_entities_extracted_from_proposal(
        self,
        db: Session,
        proposal_factory,
        user: User,
        entity_list,
    ):
        """Test entities are extracted from proposal."""
        proposal = proposal_factory(
            proposal_data={
                "action_type": "test_action",
                "entities": entity_list[:5],  # Use first 5 as entities
            }
        )

        service = _service(db)
        with _learning_patch():
            await service.approve_proposal(proposal.id, user.id)

        episode = _find_episode(db, proposal)
        assert episode is not None
        assert len(episode.entities) > 0
        # Should include proposal ID and agent ID
        assert f"proposal:{proposal.id}" in episode.entities
        assert f"agent:{proposal.agent_id}" in episode.entities
