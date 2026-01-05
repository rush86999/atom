
import sys
import os
from unittest.mock import MagicMock

# Fix path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
sys.path.append(os.getcwd())

# Mock
sys.modules['anthropic'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['zhipuai'] = MagicMock()
sys.modules['instructor'] = MagicMock()

def test_debug():
    try:
        from enhanced_ai_workflow_endpoints import RealAIWorkflowService
        print("Class imported successfully.")
        print("Attributes in RealAIWorkflowService:")
        found = False
        for x in dir(RealAIWorkflowService):
            if "get_" in x:
                print(f" - {x}")
                if "get_session" in x: found = True
        
        if not found:
            print("CRITICAL: get_session NOT found in dir()")
                
        service = RealAIWorkflowService()
        print("Instance created.")
        try:
            service.get_session("test")
            print("get_session called successfully.")
        except Exception as e:
            print(f"get_session failed: {e}")

    except ImportError as e:
        print(f"ImportError: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_debug()
