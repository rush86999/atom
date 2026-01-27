
import sys
import os

# Setup path to root
sys.path.append(os.path.dirname(os.getcwd()))
sys.path.append(os.getcwd())

print("Attempting to import business_health_service...")
try:
    from backend.core.business_health_service import business_health_service
    print("SUCCESS: Import successful.")
except Exception as e:
    print(f"FAILURE: Import failed with error: {e}")
    import traceback
    traceback.print_exc()
