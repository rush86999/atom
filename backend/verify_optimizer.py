
import sys
import os
import logging
from pprint import pprint

# Set up path to import backend modules
sys.path.append(os.getcwd())

from analytics.optimizer import WorkflowOptimizer

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_optimizer_logic():
    print("🧪 Testing WorkflowOptimizer Logic...")
    
    # Mock Workflow: Sequential but Independent
    # Step 1: Fetch Email
    # Step 2: Search Notion (No dependency on Step 1)
    mock_workflow = {
        "steps": [
            {
                "step_id": "step_1_email",
                "step_type": "generated",
                "description": "Fetch Email",
                "parameters": {"query": "important"},
                "next_steps": ["step_2_notion"]
            },
            {
                "step_id": "step_2_notion",
                "step_type": "generated",
                "description": "Search Notion",
                "parameters": {"query": "project docs"}, # No {{step_1_email}} reference
                "next_steps": []
            }
        ]
    }
    
    optimizer = WorkflowOptimizer()
    suggestions = optimizer.analyze(mock_workflow)
    
    print(f"📊 Found {len(suggestions)} suggestions:")
    for s in suggestions:
        pprint(s)
        
    if len(suggestions) == 1 and s.type == "parallelization":
        print("✅ SUCCESS: Optimizer correctly identified parallelization opportunity.")
    else:
        print("❌ FAILURE: Optimizer failed to identify obvious parallelization.")

def test_optimizer_dependency_logic():
    print("\n🧪 Testing Dependency Detection...")
    
    # Mock Workflow: Dependent
    # Step 1: Gen Text
    # Step 2: Use Text (Dependent)
    mock_workflow = {
        "steps": [
            {
                "step_id": "step_1_gen",
                "step_type": "llm",
                "description": "Generate Text",
                "next_steps": ["step_2_use"]
            },
            {
                "step_id": "step_2_use",
                "step_type": "email",
                "description": "Send Email",
                "parameters": {"body": "{{step_1_gen.output}}"}, # Dependency!
                "next_steps": []
            }
        ]
    }
    
    optimizer = WorkflowOptimizer()
    suggestions = optimizer.analyze(mock_workflow)
    
    if len(suggestions) == 0:
        print("✅ SUCCESS: Optimizer correctly respected data dependency (no suggestion).")
    else:
        print(f"❌ FAILURE: Optimizer suggested parallelizing dependent steps: {suggestions}")

if __name__ == "__main__":
    test_optimizer_logic()
    test_optimizer_dependency_logic()
