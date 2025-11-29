import asyncio
import os
import json
import logging
from fastapi.testclient import TestClient
from main_api_app import app
from core.workflow_engine import get_workflow_engine
from core.analytics_engine import get_analytics_engine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use test database
os.environ["DATABASE_URL"] = "sqlite:///test_atom_data.db"

async def verify_analytics():
    logger.info("Starting Analytics Verification...")
    
    # 1. Setup
    client = TestClient(app)
    engine = get_workflow_engine()
    analytics = get_analytics_engine()
    
    # Clear existing analytics for clean test
    analytics.workflow_metrics = {}
    analytics._save_data()
    
    # 2. Create and Execute Workflow
    workflow = {
        "id": "test_analytics_wf",
        "title": "Test Analytics Workflow",
        "created_by": "tester",
        "estimated_time_saved": 120,
        "business_value": 50,
        "steps": [
            {
                "id": "step1",
                "name": "Step 1",
                "service": "default",
                "action": "log",
                "parameters": {"message": "Hello Analytics"},
                "sequence_order": 1
            }
        ]
    }
    
    logger.info("Executing workflow...")
    # We use start_workflow but wait for completion manually since it runs in background
    # For this test, we'll call _run_execution directly to await it
    execution_id = await engine.state_manager.create_execution(workflow["id"], {})
    await engine._run_execution(execution_id, workflow)
    
    logger.info("Workflow execution completed.")
    
    # 3. Verify JSON Persistence
    logger.info("Verifying JSON persistence...")
    json_path = os.path.join(analytics.data_dir, "workflow_metrics.json")
    if not os.path.exists(json_path):
        logger.error("❌ workflow_metrics.json not found!")
        return
        
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    if "test_analytics_wf" not in data:
        logger.error("❌ Workflow ID not found in metrics JSON!")
        return
        
    metric = data["test_analytics_wf"]
    if metric["execution_count"] != 1:
        logger.error(f"❌ Expected 1 execution, got {metric['execution_count']}")
        return
        
    if metric["total_business_value"] != 50:
        logger.error(f"❌ Expected 50 business value, got {metric['total_business_value']}")
        return
        
    logger.info("✅ JSON persistence verified.")
    
    # 4. Verify API Endpoint
    logger.info("Verifying API endpoint...")
    response = client.get("/api/analytics/dashboard")
    if response.status_code != 200:
        logger.error(f"❌ API failed with {response.status_code}")
        return
        
    api_data = response.json()
    wf_analytics = api_data.get("workflows", {})
    
    if wf_analytics.get("total_executions") != 1:
        logger.error(f"❌ API reported {wf_analytics.get('total_executions')} executions, expected 1")
        return
        
    if wf_analytics.get("total_business_value") != 50:
        logger.error(f"❌ API reported {wf_analytics.get('total_business_value')} value, expected 50")
        return
        
    logger.info("✅ API endpoint verified.")
    logger.info("🎉 Analytics Integration Verification Successful!")

if __name__ == "__main__":
    asyncio.run(verify_analytics())
