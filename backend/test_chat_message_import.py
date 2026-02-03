import os
import sys

sys.path.append(os.getcwd())

try:
    from core.models import ChatMessage
    print("SUCCESS: Imported ChatMessage")
except ImportError as e:
    print(f"FAILURE: ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAILURE: Exception: {e}")
    sys.exit(1)
