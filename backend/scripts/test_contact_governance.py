import sys
import os
import asyncio
import logging

# Set up path and logging
sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Robust mock for integration dependencies
from unittest.mock import MagicMock
sys.modules['integrations.atom_whatsapp_integration'] = MagicMock()
sys.modules['integrations.meta_business_service'] = MagicMock()
sys.modules['integrations.ecommerce_unified_service'] = MagicMock()
sys.modules['integrations.marketing_unified_service'] = MagicMock()
sys.modules['integrations.document_logic_service'] = MagicMock()
sys.modules['integrations.atom_ingestion_pipeline'] = MagicMock()

# MOCK DB for verification
from core.database import SessionLocal, engine
from core.models import Base, Workspace, HITLAction, HITLActionStatus
from core.agent_integration_gateway import AgentIntegrationGateway, ActionType

# Re-initialize gateway in the script to use the mocks
agent_integration_gateway = AgentIntegrationGateway()

# ISOLATED DB FOR TESTING
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
TEST_DB_URL = "sqlite:///governance_test.db"
test_engine = create_engine(TEST_DB_URL)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

async def verify_governance_flow():
    logger.info("Starting External Governance Verification...")
    
    # Create tables in isolated DB
    Base.metadata.create_all(bind=test_engine)
    
    db = TestSessionLocal()
    workspace_id = "gov-test-ws-123"

    # Inject DB into governance engine
    from core.governance_engine import contact_governance
    contact_governance.db = db
    
    try:
        # 1. Setup Test Workspace in Learning Phase
        ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not ws:
            ws = Workspace(id=workspace_id, name="Governance Test", learning_phase_completed=False)
            db.add(ws)
            db.commit()
        else:
            ws.learning_phase_completed = False
            db.commit()

        # 2. Attempt External Contact (Should Pause)
        params = {
            "recipient_id": "+1234567890",
            "content": "Hello Customer! This is an automated message.",
            "workspace_id": workspace_id,
            "agent_id": "test-agent"
        }
        
        logger.info("Attempting external contact in Learning Phase...")
        response = await agent_integration_gateway.execute_action(
            ActionType.SEND_MESSAGE, "whatsapp", params
        )
        
        if response.get("status") == "waiting_approval":
            logger.info(f"SUCCESS: Action correctly paused. HITL ID: {response.get('hitl_id')}")
        else:
            logger.error(f"FAILURE: Action not paused. Response: {response}")
            return

        # 3. Simulate Graduation (Learning Phase Completed)
        logger.info("Completing Learning Phase...")
        ws.learning_phase_completed = True
        db.commit()
        
        # 4. Attempt External Contact Again (Should Proceed)
        # We'll mock the internal handler to see if it reaches it
        # Actually, if it doesn't return "waiting_approval", it tried to execute_message.
        logger.info("Attempting external contact after graduation...")
        response = await agent_integration_gateway.execute_action(
            ActionType.SEND_MESSAGE, "whatsapp", params
        )
        
        if response.get("status") != "waiting_approval":
            logger.info("SUCCESS: Action proceeded immediately after graduation")
        else:
            logger.error("FAILURE: Action still paused after graduation")
            return

        # 5. Test Confidence Threshold
        # Set learning phase back to false but check if confidence score works
        # Actually, get_confidence_score will look at the 1 existing pending/rejected action.
        # Let's approve the first action to see if confidence increases.
        hitl_id = response.get("hitl_id") # Note: previous response didn't have hitl_id, use the one from step 2
        # Use a real hitl_id from DB
        hitl_rec = db.query(HITLAction).filter(HITLAction.workspace_id == workspace_id).first()
        if hitl_rec:
            hitl_rec.status = HITLActionStatus.APPROVED.value
            db.commit()
            logger.info(f"Approved HITL action {hitl_rec.id}")
        
        logger.info("Stakeholder Governance Verification Complete.")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_governance_flow())
