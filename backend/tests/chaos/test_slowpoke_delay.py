
import asyncio
import os
import sys
import time
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

# Fix path
sys.path.append(os.getcwd())

# Mock missing modules BEFORE importing service
sys.modules['anthropic'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['zhipuai'] = MagicMock()
sys.modules['instructor'] = MagicMock()

from enhanced_ai_workflow_endpoints import RealAIWorkflowService


async def main():
    print(f"\n>>> [CHAOS] Starting TEST 1: The Slowpoke Simulation", flush=True)
    print("    [GOAL] Verify system handles 45s tool delay without crashing", flush=True)
    
    try:
        # Mock the ReActAgent._execute_tool method
        # This is where the delay should happen.
        
        async def slow_execute_tool(self, tool_call):
            print(f"    [CHAOS] Intercepted Tool Call: {tool_call.tool_name}", flush=True)
            if tool_call.tool_name == "slow_tool":
                print("    [CHAOS] Sleeping for 45 seconds...", flush=True)
                await asyncio.sleep(45)
                return "Done waiting."
            return "Unknown tool"

        # Patch the class method
        with patch('enhanced_ai_workflow_endpoints.ReActAgent._execute_tool', new=slow_execute_tool):
            
            # Setup Service with Mocked LLM to FORCE the tool call
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock()
            
            from enhanced_ai_workflow_endpoints import AgentStep, FinalAnswer, ToolCall

            # Step 1: LLM calls 'slow_tool'
            step_1 = AgentStep(action=ToolCall(tool_name="slow_tool", parameters={}, reasoning="Testing delay"))
            # Step 2: LLM finishes
            step_2 = AgentStep(action=FinalAnswer(answer="Finished", reasoning="Done"))
            
            # Use side_effect to return different steps on sequential calls
            mock_client.chat.completions.create.side_effect = [step_1, step_2]
            
            service = RealAIWorkflowService()
            # Force our mock client
            service.get_client = MagicMock(return_value=mock_client)
            # Bypass key check
            service.check_api_key = MagicMock(return_value=True)

            print("    [DEBUG] Starting Agent Execution...", flush=True)
            start_time = time.time()
            
            # Run
            result = await service.process_with_nlu("Run slow test", provider="deepseek")
            
            duration = time.time() - start_time
            print(f"    [DEBUG] Execution finished in {duration:.2f}s", flush=True)
            
            # We add a 2 second buffer for execution overhead
            if duration >= 45:
                print("    [PASS] System handled 45s delay without timeout.", flush=True)
            else:
                print(f"    [FAIL] Execution was too fast ({duration:.2f}s). Delay not triggered?", flush=True)

    except Exception as e:
        print(f"[FAIL] Exception: {e}", flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
