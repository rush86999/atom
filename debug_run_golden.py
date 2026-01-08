
import asyncio
import sys
import os
import traceback

import sys
import os
import traceback
import pathlib

# Fix path
# Assuming this script is in /atom (root), backend is ./backend
# But if it moved, we want robust logic.
backend_path = pathlib.Path(__file__).resolve().parent / 'backend'
if not backend_path.exists():
    backend_path = pathlib.Path(__file__).resolve().parent 

sys.path.append(str(backend_path))
sys.path.append(os.getcwd())

from unittest.mock import MagicMock
sys.modules['anthropic'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['zhipuai'] = MagicMock()
sys.modules['instructor'] = MagicMock()

# Import the test file logic (we might need to duplicate it or import it if structure allows)
# To be safe, I'll copy the logic here to guarantee execution.

from enhanced_ai_workflow_endpoints import RealAIWorkflowService, AgentStep, FinalAnswer
from unittest.mock import patch, AsyncMock
import json

async def run_test():
    dataset_dir = os.path.join(os.getcwd(), 'backend', 'tests', 'golden_dataset')
    cases = []
    if os.path.exists(dataset_dir):
        for f in os.listdir(dataset_dir):
            if f.endswith('.json'):
                path = os.path.join(dataset_dir, f)
                with open(path, 'r') as json_file:
                    cases.append(json.load(json_file))
    
    print(f"Found {len(cases)} cases.")
    
    for case in cases:
        print(f"\n>>> Running Case: {case['id']}")
        try:
            service = RealAIWorkflowService()
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock()
            
            mock_action = FinalAnswer(answer=case['full_expected_output'], reasoning="Golden Path Replay")
            mock_step = AgentStep(action=mock_action)
            mock_client.chat.completions.create.return_value = mock_step
            
            service.get_client = MagicMock(return_value=mock_client)
            service.check_api_key = MagicMock(return_value=True)
            
            result = await service.process_with_nlu(case['input'], provider="deepseek")
            
            print(f"    Result: {result.get('answer')}")
            if result['answer'] == case['full_expected_output']:
                print("    [PASS]")
            else:
                print(f"    [FAIL] Expected '{case['full_expected_output']}', got '{result['answer']}'")
                
        except Exception:
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
