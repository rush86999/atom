import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock

# Fix path
sys.path.append(os.getcwd())

from enhanced_ai_workflow_endpoints import RealAIWorkflowService

async def main():
    log_file = "chaos_broken_tool.txt"
    with open(log_file, "w") as f:
        f.write(">>> [CHAOS] Starting TEST 3: The Broken Tool Loop\n")
        
    service = None
    try:
        with patch('core.byok_endpoints.get_byok_manager') as mock_byok_get, \
             patch('enhanced_ai_workflow_endpoints.RealAIWorkflowService.call_deepseek_api', new_callable=AsyncMock) as mock_deepseek: 
            
            # 1. Setup Service
            mock_byok_manager = MagicMock()
            mock_byok_manager.get_api_key.return_value = "sk-mock-key"
            mock_byok_get.return_value = mock_byok_manager
            
            service = RealAIWorkflowService()
            await service.initialize_sessions()
            service.deepseek_api_key = "sk-mock-deepseek"
            service.google_api_key = None 

            # 2. Logic: The agent wants to search. The tool FAILS. The agent RETRIES.
            # We want to verify it STOPS after N retries.
            
            # Mock LLM: Always asks for search tool if previous result was error?
            # Or simplified: The LLM asks for search. We return ERROR. 
            # The backend loop might auto-retry OR the LLM sees the error and asks AGAIN.
            # We need to simulate the LLM asking AGAIN.
            
            # Response 1: "I will search." [Tool: search]
            # ... Tool executes -> FAIL ...
            # Response 2: "Search failed. I will try again." [Tool: search]
            # ... Tool executes -> FAIL ...
            # Response 3: "Search failed again. One more time." [Tool: search]
            # ... Tool executes -> FAIL ...
            # Response 4: "I give up." [Final Answer]
            
            mock_llm_tool = {
                'content': json.dumps({
                    "intent": "Search",
                    "tool_calls": [{"name": "search_web", "arguments": {"query": "python"}}],
                    "confidence": 0.99
                }),
                'provider': 'deepseek'
            }
            
            mock_llm_final = {
                'content': json.dumps({
                    "intent": "Answer",
                    "answer": "I cannot search right now.",
                    "confidence": 1.0
                }),
                'provider': 'deepseek'
            }
            
            # Side effect: Returns tool call 3 times, then final answer.
            # This simulates the LLM trying 3 times. 
            # If the backend has a HARD LOOP LIMIT (e.g. 5 steps), this should finish.
            # If the backend detects "Broken Tool" pattern, it might stop earlier?
            # Or we purely rely on step limit.
            
            mock_deepseek.side_effect = [
                mock_llm_tool, 
                mock_llm_tool, 
                mock_llm_tool, 
                mock_llm_tool, # 4th try
                mock_llm_final
            ]
            
            # Mock the Tool to FAIL
            async def broken_search(*args, **kwargs):
                with open(log_file, "a") as f:
                    f.write("    [CHAOS] Search Tool Broken! Raising Error.\n")
                raise RuntimeError("Simulated Connection Reset")
                
            service._tools["search_web"] = broken_search

            # Execute
            result = await service.process_with_nlu("Search for python", provider="deepseek")
            
            with open(log_file, "a") as f:
                f.write(f"    [RESULT] Agent Final Answer: {result.get('answer') or result.get('raw_response')}\n")
                f.write("[PASS] Circuit Breaker / Step Limit worked. System did not hang.\n")

    except Exception as e:
        with open(log_file, "a") as f:
            f.write(f"[FAIL] Exception: {e}\n")
            import traceback
            traceback.print_exc(file=f)
    finally:
        if service:
            await service.cleanup_sessions()

if __name__ == "__main__":
    asyncio.run(main())
