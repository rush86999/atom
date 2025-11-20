import sys
import os

# Add project root to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

try:
    from backend.integrations.hubspot_routes import router
    print(f"Successfully imported hubspot_routes. Router prefix: {router.prefix}")
except ImportError as e:
    print(f"Failed to import hubspot_routes: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
