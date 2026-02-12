
import sys
import os
import logging
from uuid import uuid4

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from core.models import AgentRegistry, AgentStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_inventory_agent():
    db = SessionLocal()
    try:
        agent_id = "inventory_reconcile"
        existing = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        
        if existing:
            logger.info(f"Agent {agent_id} already exists. Updating status...")
            existing.status = "active" # Ensure it's active
            db.commit()
            return

        logger.info(f"Creating agent {agent_id}...")
        new_agent = AgentRegistry(
            id=agent_id,
            name="Inventory Reconciliation Manager",
            description="Agent responsible for reconciling inventory differences between Shopify and WMS.",
            category="Operations",
            status="active",
            confidence_score=0.9,
            module_path="core.generic_agent",
            class_name="GenericAgent",
            configuration={
                "tools": ["reconcile_inventory"],
                "system_prompt": "You are an expert Inventory Manager. Your goal is to reconcile inventory counts. Use the 'reconcile_inventory' tool to check SKUs."
            },
            created_at=None, # Auto
            updated_at=None
        )
        
        db.add(new_agent)
        db.commit()
        logger.info(f"Successfully seeded agent: {agent_id}")
        
    except Exception as e:
        logger.error(f"Failed to seed agent: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_inventory_agent()
