import sys
import os

sys.path.append(os.getcwd())
# Also backend
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from backend.ai.nlp_engine import NaturalLanguageEngine, CommandType
    print("Import successful.")
except ImportError as e:
    print(f"Import Failed: {e}")
    sys.exit(1)

def debug_nlp():
    print("Initializing Engine...")
    engine = NaturalLanguageEngine()
    
    print("Parsing 'Hello'...")
    try:
        intent = engine.parse_command("Hello")
        print(f"Intent Type: {intent.command_type}")
        print(f"Confidence: {intent.confidence}")
    except Exception as e:
        print(f"Parse Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_nlp()
