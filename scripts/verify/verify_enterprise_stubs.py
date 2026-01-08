import os
import sys

def verify_integrations(names):
    print(f"Checking integrations: {names}")
    sys.path.append(os.path.join(os.getcwd(), 'backend'))
    from main_api_app import app
    from core.lazy_integration_registry import load_integration
    
    for name in names:
        print(f"\n--- Testing {name} ---")
        router = load_integration(name)
        if router:
            app.include_router(router)
            print(f"✓ {name} router loaded manually")
            
            # Find routes
            routes = [r.path for r in app.routes if hasattr(r, 'path') and f'/api/{name}' in r.path]
            if routes:
                print(f"✓ Found Routes: {routes}")
            else:
                print(f"✗ No routes found for /api/{name}")
        else:
            print(f"✗ {name} failed to load")

if __name__ == "__main__":
    verify_integrations(["workday", "okta", "webex"])
