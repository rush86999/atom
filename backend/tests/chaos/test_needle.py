import asyncio
import json
import os

# Fix path
import pathlib
import random
import sys
from unittest.mock import AsyncMock, MagicMock, patch

backend_path = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.append(str(backend_path))
sys.path.append(os.getcwd())

# MOCK MODULES
sys.modules['anthropic'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['zhipuai'] = MagicMock()
sys.modules['instructor'] = MagicMock()

from enhanced_ai_workflow_endpoints import RealAIWorkflowService


async def main():
    log_file = "chaos_needle_result.txt"
    with open(log_file, "w") as f:
        f.write(">>> [CHAOS] Starting TEST 2: Needle in a Haystack\n")

    service = None
    try:
        with patch('core.byok_endpoints.get_byok_manager') as mock_byok_get, \
             patch('core.memory.MemoryManager.get_chat_history') as mock_get_history, \
             patch('enhanced_ai_workflow_endpoints.RealAIWorkflowService.call_deepseek_api', new_callable=AsyncMock) as mock_deepseek: # Patch deepseek call directly
            
            # 1. Setup Service
            mock_byok_manager = MagicMock()
            mock_byok_manager.get_api_key.return_value = "sk-mock-key"
            mock_byok_get.return_value = mock_byok_manager
            
            service = RealAIWorkflowService()
            await service.initialize_sessions()
            service.deepseek_api_key = "sk-mock-deepseek"
            service.google_api_key = None 

            # 2. Generate NOISE (The Haystack)
            noise_messages = []
            for i in range(50):
                noise_messages.append({"role": "user", "content": f"Noise message {i}: The sky is generally blue."})
                noise_messages.append({"role": "assistant", "content": f"Noise response {i}: Indeed."})
            
            # The Needle is NOT in history, it is the CURRENT Query? 
            # Or the Needle is a fact buried in history?
            # User requirement: "Inject 50 random, irrelevant messages... before asking."
            # "Goal: Test if the agent loses focus."
            # So if I ask "What is my name?" and I told it 50 messages ago, that's retrieval.
            # If I ask "What is 2+2?" and it has 50 stupid messages, it shouldn't get confused.
            
            # Let's try: Buried Fact.
            # Message 0: "My secret code is 1234."
            # Message 1-50: Noise.
            # Query: "What is my secret code?"
            
            history_payload = [
                {"role": "user", "content": "IMPORTANT: My secret code is 1234."},
                {"role": "assistant", "content": "I will remember that."},
            ] + noise_messages
            
            mock_get_history.return_value = history_payload
            
            # 3. Mock LLM Response (The Agent finding the needle)
            # If the prompt is constructed correctly, the LLM SHOULD see the history.
            # We are testing the SYSTEM's ability to handle this context size and the LLM (Mocked) logic?
            # Wait. If I Mock the LLM, I am testing... what?
            # I am testing that the BACKEND correctly fetches and passes the history to the LLM.
            # I cannot test the LLM's "Focus" with a Mock LLM.
            # But the user Requirement says: "Test if the agent loses focus."
            # This implies using a REAL LLM?
            # But I don't have real keys.
            
            # Grey-Box compromise:
            # I will verifying that the `call_deepseek_api` receives the FULL context (52 messages + query).
            # If the backend truncates it or fails to include it, the test fails.
            
            async def verify_context(*args, **kwargs):
                # args[0] is `messages` list usually?
                # or check kwargs
                messages = kwargs.get('messages') or args[0]
                
                with open(log_file, "a") as f:
                    f.write(f"    [DEBUG] LLM called with {len(messages)} messages.\n")
                    f.write(f"    [DEBUG] First message: {messages[0]}\n")
                    # f.write(f"    [DEBUG] noise sample: {messages[10]}\n") # Avoid out of range if len < 10
                
                # Verify size
                if len(messages) < 50:
                     raise Exception(f"Context truncated! Only {len(messages)} messages.")
                
                # Verify Needle presence
                is_needle_there = any("1234" in str(m) for m in messages)
                if not is_needle_there:
                     raise Exception("The Needle (secret code) was lost from context!")
                
                return {
                    'content': json.dumps({
                        "intent": "Answer",
                        "answer": "Your secret code is 1234.",
                        "confidence": 1.0
                    }),
                    'provider': 'deepseek'
                }

            mock_deepseek.side_effect = verify_context
            
            # 4. Execute
            with open(log_file, "a") as f:
                f.write(f"    [NOTE] Injecting {len(history_payload)} messages of history.\n")
            
            result = await service.process_with_nlu("What is my secret code?", conversation_id="chaos-test-session", provider="deepseek")
            
            with open(log_file, "a") as f:
                f.write(f"    [RESULT] Agent Answer: {result.get('answer') or result.get('raw_response')}\n")
                if "1234" in str(result):
                    f.write("[PASS] Needle Found. Context pipeline intact.\n")
                else:
                    f.write("[FAIL] Needle missing from answer.\n")

    except Exception as e:
        with open(log_file, "a") as f:
            f.write(f"[CRITICAL FAIL] {e}\n")
            import traceback
            traceback.print_exc(file=f)
    finally:
        if service:
            await service.cleanup_sessions()

if __name__ == "__main__":
    asyncio.run(main())
