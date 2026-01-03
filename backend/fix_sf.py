import sys
import os
import traceback

# Add backend to sys.path
sys.path.append(os.getcwd())

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    print("Attempting to import integrations.salesforce_routes...")
    from integrations import salesforce_routes
    print("Successfully imported integrations.salesforce_routes")
except Exception:
    print("Failed to import integrations.salesforce_routes:")
    traceback.print_exc()

try:
    print("Attempting to import integrations.auth_handler_salesforce...")
    from integrations import auth_handler_salesforce
    print("Successfully imported auth_handler_salesforce")
except Exception:
    print("Failed to import integrations.auth_handler_salesforce:")
    traceback.print_exc()
