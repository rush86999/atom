"""
Property-based and unit tests for proposal episode creation.

Tests the integration between ProposalService and EpisodeSegmentationService
to ensure proposal approvals/rejections are captured as learning episodes.
"""

import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy.orm import Session
from datetime import datetime

from core.models import (
    AgentProposal,
    AgentRegistry,
    AgentStatus,
    ProposalStatus,
    ProposalType,
    User,
    Workspace,
)
from core.proposal_service import ProposalService


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def user(db: Session):
    """Create test user."""
    user = User(
        id="test_proposal_user",
        email="proposal_test@example.com",
        first_name="Proposal",
        last_name="Test User",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def workspace(db: Session, user: User):
    """Create test workspace."""
    workspace = Workspace(
        id="test_proposal_workspace",
        name="Proposal Test Workspace",
        
    )
    db.add(workspace)
    db.commit()
    return workspace


@pytest.fixture
def intern_agent(db: Session, workspace: Workspace, user: User):
    """Create INTERN agent."""
    agent = AgentRegistry(
        id="test_intern_agent_proposal",
        name="Test Intern Agent Proposal",
        category="testing",
        module_path="agents.test_agent",
        class_name="TestAgent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        
        
    )
    db.add(agent)
    db.commit()
    return agent


@pytest.fixture
def proposal_factory(db: Session, intern_agent: AgentRegistry, user: User):
    """Factory to create proposals."""
    def _create_proposal(
        title: str = "Test Proposal",
        proposal_type: str = ProposalType.ACTION.value,
        reasoning: str = "Test reasoning",
    ) -> AgentProposal:
        proposal = AgentProposal(
            id=f"test_proposal_{datetime.now().timestamp()}",
            agent_id=intern_agent.id,
            agent_name=intern_agent.name,
            proposal_type=proposal_type,
            title=title,
            description="Test proposal description",
            proposed_action={
                "action_type": "canvas_present",
                "canvas_type": "chart",
            },
            reasoning=reasoning,
            status=ProposalStatus.PROPOSED.value,
            proposed_by=intern_agent.id,
            created_at=datetime.now(),
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        return proposal

    return _create_proposal


# ============================================================================
# Unit Tests
# ============================================================================

class TestProposalEpisodeCreation:
    """Test proposal episode creation functionality."""

    @pytest.mark.asyncio
    async def test_create_episode_from_approved_proposal(
        self,
        db: Session,
        proposal_factory,
        user: User,
    ):
        """Test creating episode from approved proposal."""
        proposal = proposal_factory(title="Test Approval Proposal")

        proposal_service = ProposalService(db)

        # Approve proposal
        result = await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
            modifications=None,
        )

        # Verify episode created
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
            Episode.proposal_outcome == "approved",
        ).first()

        assert episode is not None
        assert episode.agent_id == proposal.agent_id
        assert episode.user_id == user.id
        assert episode.proposal_id == proposal.id
        assert episode.proposal_outcome == "approved"
        assert episode.maturity_at_time == AgentStatus.INTERN.value

    @pytest.mark.asyncio
    async def test_create_episode_from_rejected_proposal(
        self,
        db: Session,
        proposal_factory,
        user: User,
    ):
        """Test creating episode from rejected proposal."""
        proposal = proposal_factory(title="Test Rejection Proposal")
        rejection_reason = "Insufficient justification"

        proposal_service = ProposalService(db)

        # Reject proposal
        await proposal_service.reject_proposal(
            proposal_id=proposal.id,
            
            reason=rejection_reason,
        )

        # Verify episode created
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
            Episode.proposal_outcome == "rejected",
        ).first()

        assert episode is not None
        assert episode.proposal_outcome == "rejected"
        assert episode.rejection_reason == rejection_reason

    @pytest.mark.asyncio
    async def test_episode_with_modifications(
        self,
        db: Session,
        proposal_factory,
        user: User,
    ):
        """Test episode captures proposal modifications."""
        proposal = proposal_factory()
        modifications = {"param1": "updated_value", "param2": "new_param"}

        proposal_service = ProposalService(db)

        # Approve with modifications
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
            modifications=modifications,
        )

        # Verify episode includes modifications
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        assert episode is not None
        assert episode.human_edits == modifications

    @pytest.mark.asyncio
    async def test_episode_importance_for_rejected_proposals(
        self,
        db: Session,
        proposal_factory,
        user: User,
    ):
        """Test rejected proposals have higher importance scores."""
        approved_proposal = proposal_factory(title="Approved Test")
        rejected_proposal = proposal_factory(title="Rejected Test")

        proposal_service = ProposalService(db)

        # Approve one
        await proposal_service.approve_proposal(
            proposal_id=approved_proposal.id,
            
        )

        # Reject one
        await proposal_service.reject_proposal(
            proposal_id=rejected_proposal.id,
            
            reason="Not good enough",
        )

        # Get episodes
        from core.models import Episode
        approved_episode = db.query(Episode).filter(
            Episode.proposal_id == approved_proposal.id,
        ).first()

        rejected_episode = db.query(Episode).filter(
            Episode.proposal_id == rejected_proposal.id,
        ).first()

        assert approved_episode is not None
        assert rejected_episode is not None

        # Rejected should have higher importance (learning opportunity)
        assert rejected_episode.importance_score > approved_episode.importance_score

    @pytest.mark.asyncio
    async def test_episode_segments_created(
        self,
        db: Session,
        proposal_factory,
        user: User,
    ):
        """Test episode includes proposal and outcome segments."""
        proposal = proposal_factory()

        proposal_service = ProposalService(db)
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
        )

        # Verify segments created
        from core.models import Episode, EpisodeSegment
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        segments = db.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id,
        ).all()

        assert len(segments) >= 2  # Proposal + outcome segments

        segment_types = {s.segment_type for s in segments}
        assert "proposal" in segment_types
        assert "reflection" in segment_types

    @pytest.mark.asyncio
    async def test_episode_topics_from_proposal(
        self,
        db: Session,
        proposal_factory,
        user: User,
    ):
        """Test topics extracted from proposal content."""
        proposal = proposal_factory(
            title="Financial Report Analysis Proposal",
            reasoning="This proposal analyzes financial data and generates insights",
        )

        proposal_service = ProposalService(db)
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
        )

        # Verify topics extracted
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        assert episode.topics is not None
        assert len(episode.topics) > 0
        # Should include action type and words from title/reasoning
        assert any("action" in t.lower() for t in episode.topics)

    @pytest.mark.asyncio
    async def test_human_intervention_count_set(
        self,
        db: Session,
        proposal_factory,
        user: User,
    ):
        """Test proposal episodes have intervention_count = 1."""
        proposal = proposal_factory()

        proposal_service = ProposalService(db)
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
        )

        # Verify human intervention counted
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        assert episode.human_intervention_count == 1  # Human approval/rejection


# ============================================================================
# Property-Based Tests
# ============================================================================

class TestProposalEpisodeProperties:
    """Property-based tests for proposal episode creation."""

    @given(
        title=st.text(min_size=5, max_size=50).filter(lambda x: len(x.strip()) > 0),
        reasoning=st.text(min_size=10, max_size=200).filter(lambda x: len(x.strip()) > 0),
    )
    @settings(max_examples=15)
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

        proposal_service = ProposalService(db)
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
        )

        # Verify content in episode
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        assert episode is not None
        assert proposal.title in episode.title
        assert len(episode.topics) > 0

    @given(
        modifications_dict=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.text(min_size=1, max_size=50),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=15)
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

        proposal_service = ProposalService(db)
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
            modifications=modifications_dict,
        )

        # Verify modifications in episode
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        assert episode is not None
        assert episode.human_edits == modifications_dict

    @given(
        rejection_reason=st.text(min_size=10, max_size=200).filter(
            lambda x: len(x.strip()) > 0
        ),
    )
    @settings(max_examples=15)
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

        proposal_service = ProposalService(db)
        await proposal_service.reject_proposal(
            proposal_id=proposal.id,
            
            reason=rejection_reason.strip(),
        )

        # Verify rejection reason in episode
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        assert episode is not None
        assert episode.rejection_reason == rejection_reason.strip()
        assert episode.proposal_outcome == "rejected"

    @given(
        outcome=st.sampled_from(["approved", "rejected"]),
    )
    @settings(max_examples=2)
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

        proposal_service = ProposalService(db)

        if outcome == "approved":
            await proposal_service.approve_proposal(
                proposal_id=proposal.id,
                
            )
        else:
            await proposal_service.reject_proposal(
                proposal_id=proposal.id,
                
                reason="Test rejection",
            )

        # Verify outcome
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        assert episode is not None
        assert episode.proposal_outcome == outcome

    @given(
        st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=10)
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

        proposal_service = ProposalService(db)
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
            modifications=modifications if modifications else None,
        )

        # Verify importance score
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

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
    @settings(max_examples=10)
    @pytest.mark.asyncio
    async def test_entities_extracted_from_proposal(
        self,
        db: Session,
        proposal_factory,
        user: User,
        entity_list,
    ):
        """Test entities are extracted from proposal."""
        # Create proposal with specific entities in action
        proposal = proposal_factory()
        proposal.proposed_action = {
            "action_type": "test_action",
            "entities": entity_list[:5],  # Use first 5 as entities
        }
        db.commit()

        proposal_service = ProposalService(db)
        await proposal_service.approve_proposal(
            proposal_id=proposal.id,
            
        )

        # Verify entities extracted
        from core.models import Episode
        episode = db.query(Episode).filter(
            Episode.proposal_id == proposal.id,
        ).first()

        assert episode is not None
        assert len(episode.entities) > 0
        # Should include proposal ID, agent ID, reviewer ID
        assert any("proposal:" in e for e in episode.entities)
        assert any("agent:" in e for e in episode.entities)
