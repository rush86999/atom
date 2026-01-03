import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
import time

# Fix path
sys.path.append(os.getcwd())

from enhanced_ai_workflow_endpoints import RealAIWorkflowService

async def main():
    try:
        print(">>> [CHAOS] Starting TEST 1: The Slowpoke Simulation", flush=True)
        
        # We want to patch a tool to take a LONG time.
        # The agent calls `service.execute_tool`.
        
        with patch('core.byok_endpoints.get_byok_manager') as mock_byok_get:
            mock_byok_manager = MagicMock()
            mock_byok_manager.get_api_key.return_value = "sk-mock-key"
            mock_byok_get.return_value = mock_byok_manager

            print("    [DEBUG] Initializing Service...", flush=True)
            service = RealAIWorkflowService()
            await service.initialize_sessions()
            print("    [DEBUG] Service Initialized.", flush=True)
            
            # Inject keys
            service.deepseek_api_key = "sk-mock-deepseek"
            service.google_api_key = None 

            # Mock LLM to ASK for a tool
            mock_llm_response_tool = {
                'content': json.dumps({
                    "intent": "Read file",
                    "workflow_suggestion": {},
                    "answer": "I will read the file.", 
                    "tool_calls": [{"name": "read_file", "arguments": {"path": "test.txt"}}],
                    "confidence": 0.99
                }),
                'provider': 'deepseek'
            }
            
            # Mock LLM to give Final Answer after tool
            mock_llm_response_final = {
                'content': json.dumps({
                    "intent": "Answer",
                    "answer": "The file says hello.",
                    "confidence": 1.0
                }),
                'provider': 'deepseek'
            }
            
            # State to toggle messages
            call_count = 0
            async def mock_deepseek_call(*args, **kwargs):
                nonlocal call_count
                print(f"    [DEBUG] Mock DeepSeek hit! Call #{call_count}", flush=True)
                call_count += 1
                if call_count == 1:
                    return mock_llm_response_tool
                else:
                    return mock_llm_response_final

            # Mock the tool execution to SLEEP
            async def slow_read_file(*args, **kwargs):
                print("    [SLOWPOKE] Tool invoked. Sleeping for 45 seconds...", flush=True)
                await asyncio.sleep(45) 
                print("    [SLOWPOKE] Awake! Returning result.", flush=True)
                return "File Content: Hello World"

            # Patch tool
            service._tools["read_file"] = slow_read_file
            
            # Patch LLM Call
            service.call_deepseek_api = mock_deepseek_call
            
            # Execute
            print("    [NOTE] This test should take ~45 seconds. If it hangs forever, we failed.", flush=True)
            start_time = time.time()
            
            try:
                # Increase timeout slightly to allow for overhead
                print("    [DEBUG] Calling process_with_nlu...", flush=True)
                result = await asyncio.wait_for(service.process_with_nlu("Read test.txt", provider="deepseek"), timeout=60)
                
                duration = time.time() - start_time
                print(f"    [RESULT] Finished in {duration:.2f} seconds.", flush=True)
                print(f"    [RESULT] Intent: {result.get('intent')}", flush=True)
                
                if duration >= 45:
                    print("[PASS] System handled long-running tool without crashing.", flush=True)
                else:
                    print("[WARN] Finished too fast? Did sleep work?", flush=True)
                    
            except asyncio.TimeoutError:
                print("[FAIL] The process timed out externally (Test limit 60s).", flush=True)
            except Exception as e:
                print(f"[FAIL] Exception occurred in NLU: {e}", flush=True)
                import traceback
                traceback.print_exc()
            finally:
                await service.cleanup_sessions()
    except Exception as e:
        print(f"[CRITICAL] Script crashed: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
