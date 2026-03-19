import logging
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from core.models import CoordinatedStrategy, StrategyContribution, AgentRegistry

logger = logging.getLogger(__name__)

class CoordinatedStrategyService:
    """Manages collaboration among diverse specialty agents for coordinated strategies."""

    def __init__(self, db: Session):
        self.db = db

    def initiate_strategy(
        self, 
        tenant_id: str, 
        title: str, 
        objective: str, 
        initiator_agent_id: str
    ) -> CoordinatedStrategy:
        """Create a new strategic plan and add the first contribution."""
        strategy_id = str(uuid.uuid4())
        strategy = CoordinatedStrategy(
            id=strategy_id,
            tenant_id=tenant_id,
            title=title,
            objective=objective,
            status="negotiating"
        )
        self.db.add(strategy)
        
        # Add initiator's contribution
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == initiator_agent_id).first()
        if agent:
            contribution = StrategyContribution(
                id=str(uuid.uuid4()),
                strategy_id=strategy_id,
                agent_id=initiator_agent_id,
                specialty=agent.category or "general",
                content={"proposal": f"Initial strategy for {objective}"},
                status="proposed"
            )
            self.db.add(contribution)
        
        self.db.commit()
        self.db.refresh(strategy)
        logger.info(f"Initiated coordinated strategy {strategy_id} by agent {initiator_agent_id}")
        return strategy

    def recruit_diverse_partner(
        self, 
        strategy_id: str, 
        target_specialty: str,
        complementary_trait: str = "risk_profile"
    ) -> Optional[AgentRegistry]:
        """Recruit an agent with a specific specialty and a DIFFERENT diversity profile."""
        strategy = self.db.query(CoordinatedStrategy).filter(CoordinatedStrategy.id == strategy_id).first()
        if not strategy:
            return None

        # Get existing contributors' traits
        existing_traits = []
        for c in strategy.contributions:
            if c.agent and c.agent.diversity_profile:
                val = c.agent.diversity_profile.get(complementary_trait)
                if val:
                    existing_traits.append(val)

        # Search for an agent with target specialty who has a NEW trait value
        query = self.db.query(AgentRegistry).filter(AgentRegistry.category == target_specialty)
        
        potential_agents = query.all()
        for agent in potential_agents:
            if agent.diversity_profile:
                trait_val = agent.diversity_profile.get(complementary_trait)
                if trait_val and trait_val not in existing_traits:
                    # Found a diverse partner!
                    logger.info(f"Recruited diverse partner {agent.id} for strategy {strategy_id}")
                    return agent
        
        # Fallback to any agent in that specialty
        return query.first()

    def add_contribution(
        self, 
        strategy_id: str, 
        agent_id: str, 
        content: Dict
    ) -> StrategyContribution:
        """Add a specialty contribution or critique to the strategy."""
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if not agent:
            raise ValueError("Agent not found")

        contribution = StrategyContribution(
            id=str(uuid.uuid4()),
            strategy_id=strategy_id,
            agent_id=agent_id,
            specialty=agent.category or "general",
            content=content,
            status="proposed"
        )
        self.db.add(contribution)
        self.db.commit()
        return contribution

    def finalize_strategy(self, strategy_id: str) -> bool:
        """Move strategy to approved status."""
        strategy = self.db.query(CoordinatedStrategy).filter(CoordinatedStrategy.id == strategy_id).first()
        if strategy:
            strategy.status = "approved"
            strategy.approved_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        return False
