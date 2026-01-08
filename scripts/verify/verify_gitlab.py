import os
import sys

def verify_gitlab_routes():
    print("Checking if GitLab routes are registered in FastAPI app...")
    sys.path.append(os.path.join(os.getcwd(), 'backend'))
    from main_api_app import app
    from core.lazy_integration_registry import load_integration
    
    print("Manually loading GitLab integration...")
    router = load_integration("gitlab")
    if router:
        app.include_router(router)
        print("✓ Router loaded manually")
    else:
        print("✗ Router failed to load")

    found = False
    for route in app.routes:
        if hasattr(route, 'path') and '/api/gitlab' in route.path:
            print(f"Found Route: {route.path}")
            found = True
    
    if found:
        print("SUCCESS: GitLab routes are registered.")
    else:
        print("FAILURE: GitLab routes not found.")

if __name__ == "__main__":
    verify_gitlab_routes()
