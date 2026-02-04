import sys
import os
import logging
from dotenv import load_dotenv

# Force load .env to pick up manual user changes
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.append(os.getcwd())

def test_llm_connection():
    print("--- Testing LLM Connection ---")
    
    # 1. Initialize Engine
    try:
        from ai.nlp_engine import NaturalLanguageEngine
        print("Initializing NLP Engine...")
        engine = NaturalLanguageEngine()
        
        if not engine._is_llm_available():
            print("❌ LLM Client is NOT available after initialization.")
            return
            
        print(f"✅ LLM Client Initialized using provider: {type(engine._llm_client).__name__}")
        print(f"API Key present: {bool(engine._llm_client.api_key)}")
        if hasattr(engine._llm_client, "base_url"):
             print(f"Base URL: {engine._llm_client.base_url}")

    except Exception as e:
        print(f"❌ Failed to initialize engine: {e}")
        return

    # 2. Test Query
    print("\n--- Sending Test Query ---")
    try:
        messages = [{"role": "user", "content": "Say 'Connection Successful' if you can read this."}]
        response = engine.query_llm(messages)
        
        if response:
            print(f"✅ Response Received:\n{response}")
        else:
            print("❌ Response was Empty/None.")
            
    except Exception as e:
        print(f"❌ Query Failed with Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_llm_connection()
