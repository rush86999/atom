
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

async def verify_computer_use_integration():
    """Verify Lux Computer Use integration via BYOK"""
    print("🧪 Verifying Lux Computer Use Integration...")
    
    # 1. Set the Lux API key in environment (simulating loading from credentials/env)
    # Using the key we found in credentials.md
    os.environ["LUX_MODEL_API_KEY"] = "sk-Iow_oheGtqjqq7FkTrjWlzHWhESIgam3Yyv-TCz_e5g"
    
    try:
        from core.byok_endpoints import get_byok_manager
        from services.agent_service import agent_service
        
        # 2. Verify BYOK can see the provider and key
        byok = get_byok_manager()
        
        print("   Checking Lux provider configuration...")
        provider = byok.providers.get("lux")
        if not provider:
            print("   ❌ Lux provider not found in BYOK configuration")
            return
            
        print(f"   ✅ Found provider: {provider.name}")
        
        # 3. Retrieve key using BYOK logic
        print("   Testing key retrieval...")
        api_key = byok.get_api_key("lux")
        
        if api_key == "sk-Iow_oheGtqjqq7FkTrjWlzHWhESIgam3Yyv-TCz_e5g":
            print("   ✅ Key retrieval successful via BYOK")
        else:
            print(f"   ❌ Key retrieval failed. Got: {api_key}")
            
        # 4. Test Agent Service Execution
        print("   Testing Agent execution...")
        
        # Start a task
        start_result = await agent_service.execute_task("Open calculator and calculate 2+2")
        task_id = start_result.get("id")
        print(f"   Task started: {task_id}")
        
        # Wait for completion (poll status)
        for _ in range(5):
             await asyncio.sleep(1)
             status_data = agent_service.get_task_status(task_id)
             status = status_data.get("status")
             print(f"   Status: {status}")
             if status == "completed":
                 print(f"   ✅ Task completed successfully")
                 print(f"   Result: {status_data.get('result')}")
                 print(f"   Logs: {status_data.get('logs')}")
                 return
                 
        print("   ⚠️ Task timed out or did not complete expectedly.")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_computer_use_integration())
