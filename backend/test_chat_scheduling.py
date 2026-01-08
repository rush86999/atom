import asyncio
import aiohttp
import json
import uuid
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/atom-agent/chat"

async def send_message(session, message, conversation_history=[]):
    payload = {
        "message": message,
        "user_id": "test_user",
        "session_id": "test_session",
        "conversation_history": conversation_history
    }
    
    try:
        async with session.post(BASE_URL, json=payload) as response:
            if response.status != 200:
                logger.error(f"Error: {response.status}")
                text = await response.text()
                logger.error(text)
                return None
            return await response.json()
    except Exception as e:
        logger.error(f"Connection Error: {e}")
        return None

async def run_tests():
    print("\nTesting Chat Scheduling...\n")
    
    async with aiohttp.ClientSession() as session:
        # 1. Create a workflow first
        print("--- 1. Creating a workflow ---")
        create_response = await send_message(session, "Create a new workflow for server monitoring")
        
        if not create_response or not create_response.get("success"):
            print(f"❌ Failed to create workflow. Response: {create_response}")
            return
            
        if "workflow_name" not in create_response["response"]:
             print(f"❌ Unexpected response format: {create_response}")
             return

        workflow_name = create_response["response"]["workflow_name"]
        print(f"✅ Created workflow: {workflow_name}")
        
        # 2. Schedule the workflow
        print("\n--- 2. Scheduling the workflow ---")
        schedule_msg = f"Schedule the {workflow_name} to run every weekday at 9am"
        print(f"Sending: '{schedule_msg}'")
        
        schedule_response = await send_message(session, schedule_msg)
        
        if schedule_response and schedule_response.get("success"):
            resp_data = schedule_response["response"]
            print(f"✅ Success: {resp_data['message']}")
            
            schedule_id = resp_data.get("schedule_id")
            if schedule_id:
                print(f"   Schedule ID: {schedule_id}")
                
                # 3. Cancel the schedule
                print("\n--- 3. Cancelling the schedule ---")
                # We need to pass the schedule_id somehow. 
                # In a real chat, the user might click a button which sends an event, 
                # or say "Cancel schedule X". 
                # Let's try to simulate the intent classification extracting the ID if we provide it explicitly,
                # or we can try to rely on context if we had it.
                # For this test, we'll assume we can pass the ID in the message or entities if we were mocking NLU.
                # But since we are testing the full flow, let's try to say "Cancel schedule <id>" 
                # and hope the NLU picks it up. If not, we might need to adjust the test or the NLU.
                
                # Actually, the NLU might not be trained to pick up raw IDs easily without context.
                # Let's try a direct approach if the NLU supports it, or just verify the schedule exists via other means?
                # But wait, the plan said "Cancel the daily report schedule".
                # Let's try that first.
                
                cancel_msg = f"Cancel the schedule for {workflow_name}"
                print(f"Sending: '{cancel_msg}'")
                cancel_response = await send_message(session, cancel_msg)
                
                if cancel_response and cancel_response.get("success"):
                     print(f"Response: {cancel_response['response']['message']}")
                else:
                    print("❌ Failed to cancel")
                    
            else:
                print("❌ No schedule ID returned")
        else:
            print("❌ Failed to schedule")
            if schedule_response:
                print(f"Response: {schedule_response}")

        # 4. Test invalid schedule
        print("\n--- 4. Testing invalid schedule ---")
        invalid_msg = f"Schedule {workflow_name} tomorrow maybe"
        print(f"Sending: '{invalid_msg}'")
        invalid_response = await send_message(session, invalid_msg)
        
        if invalid_response and invalid_response.get("success"):
             print(f"Response: {invalid_response['response']['message']}")
             # Expecting a message about not understanding the schedule
        
if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        pass
