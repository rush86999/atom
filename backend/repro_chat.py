
import sys
import os
import asyncio
import traceback

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    print("Attempting to import ChatOrchestrator...")
    from integrations.chat_orchestrator import ChatOrchestrator
    print("Import successful.")

    print("Attempting to instantiate ChatOrchestrator...")
    # Mocking dependencies if needed, but let's see if __init__ crashes
    orchestrator = ChatOrchestrator()
    print("Instantiation successful.")

except Exception:
    traceback.print_exc()
