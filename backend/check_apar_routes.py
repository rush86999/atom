from api.apar_routes import router

prefix = "/api" # This is what main_api_app.py uses
router_prefix = router.prefix

print(f"Router Prefix: {router_prefix}")
print("Effective Routes:")
for route in router.routes:
    if hasattr(route, "path"):
        full_path = prefix + router_prefix + route.path
        methods = getattr(route, "methods", [])
        print(f"Path: {full_path} | Methods: {methods}")
