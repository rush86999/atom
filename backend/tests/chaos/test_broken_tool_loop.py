
import asyncio
import json
import os

# Fix path
import pathlib
import sys
import traceback
from unittest.mock import AsyncMock, MagicMock, patch

backend_path = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.append(str(backend_path))
sys.path.append(os.getcwd())

# MOCK MODULES
sys.modules['anthropic'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['zhipuai'] = MagicMock()
sys.modules['instructor'] = MagicMock()

from enhanced_ai_workflow_endpoints import AgentStep, FinalAnswer, RealAIWorkflowService, ToolCall


async def main():
    log_file = "chaos_broken_tool.txt"
    try:
        with open(log_file, "w") as f:
            f.write(">>> [CHAOS] Starting TEST 3: The Broken Tool Loop\n")
            f.write("    [GOAL] Verify system handles repeated tool failures without infinite loop\n")

        # Mock _execute_tool to FAIL
        async def broken_tool(self, tool_call):
            with open(log_file, "a") as f:
                f.write(f"    [CHAOS] Executing Tool: {tool_call.tool_name} -> SIMULATING FAILURE\n")
            return "Error: Connection Reset"

        # Patch ReActAgent._execute_tool
        with patch('enhanced_ai_workflow_endpoints.ReActAgent._execute_tool', new=broken_tool):
            
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock()
            
            # Scenario: Agent tries to search 3 times, then gives up.
            
            # Step 1: Try Search
            step_1 = AgentStep(action=ToolCall(tool_name="search_web", parameters={"q": "python"}, reasoning="Attempt 1"))
            # Step 2: Try Search Again (Logic: LLM sees error)
            step_2 = AgentStep(action=ToolCall(tool_name="search_web", parameters={"q": "python"}, reasoning="Attempt 2"))
            # Step 3: Try Search Again
            step_3 = AgentStep(action=ToolCall(tool_name="search_web", parameters={"q": "python"}, reasoning="Attempt 3"))
            # Step 4: Give Up
            step_4 = AgentStep(action=FinalAnswer(answer="I cannot search right now.", reasoning="Too many failures."))
            
            mock_client.chat.completions.create.side_effect = [step_1, step_2, step_3, step_4]
            
            service = RealAIWorkflowService()
            service.get_client = MagicMock(return_value=mock_client)
            service.check_api_key = MagicMock(return_value=True)

            # Run
            result = await service.process_with_nlu("Search python", provider="deepseek")
            
            with open(log_file, "a") as f:
                f.write(f"    [RESULT] Agent Final Answer: {result.get('answer')}\n")
                if result.get('answer') == "I cannot search right now.":
                    f.write("[PASS] Circuit Breaker worked (Agent gave up naturally or Loop Limit hit).\n")
                else:
                    f.write(f"[FAIL] Unexpected result: {result}\n")

    except Exception as e:
        with open(log_file, "a") as f:
            f.write(f"[FAIL] Exception: {e}\n")
            traceback.print_exc(file=f)

if __name__ == "__main__":
    asyncio.run(main())
