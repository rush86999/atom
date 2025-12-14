
import asyncio
import httpx
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:5059/api/agent"

async def verify_agent_endpoints():
    """
    Verify the Computer Use Agent API endpoints functionality.
    """
    async with httpx.AsyncClient() as client:
        try:
            # 1. Start a new task
            logger.info("1. Starting new agent task...")
            payload = {
                "goal": "Find the cheapest flight to Tokyo",
                "mode": "thinker"
            }
            response = await client.post(f"{BASE_URL}/run", json=payload)
            
            if response.status_code != 200:
                logger.error(f"Failed to start task: {response.text}")
                return False
                
            task_data = response.json()
            task_id = task_data.get("id")
            logger.info(f"   Task started successfully. ID: {task_id}")
            logger.info(f"   Initial Status: {task_data.get('status')}")
            
            # 2. Poll status (Mock execution takes ~3 seconds)
            logger.info("2. Polling task status...")
            for _ in range(5):
                await asyncio.sleep(1)
                status_response = await client.get(f"{BASE_URL}/status/{task_id}")
                if status_response.status_code != 200:
                    logger.error(f"Failed to get status: {status_response.text}")
                    continue
                    
                status_data = status_response.json()
                status = status_data.get("status")
                logger.info(f"   Current Status: {status}")
                
                # Print logs
                logs = status_data.get("logs", [])
                if logs:
                    logger.info(f"   Latest Log: {logs[-1]}")
                
                if status in ["completed", "failed", "stopped"]:
                    break
            
            # 3. Verify completion
            final_response = await client.get(f"{BASE_URL}/status/{task_id}")
            final_data = final_response.json()
            logger.info(f"3. Final Result: {final_data.get('result')}")
            
            if final_data.get("status") == "completed":
                logger.info("✅ Agent Service Verification Passed")
                return True
            else:
                logger.error("❌ Agent Service Verification Failed (Task did not complete)")
                return False
                
        except httpx.RequestError as e:
            logger.error(f"Connection error: {e}. Is the backend server running?")
            return False

if __name__ == "__main__":
    success = asyncio.run(verify_agent_endpoints())
    if not success:
        sys.exit(1)
