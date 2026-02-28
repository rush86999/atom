
import sys
import os
from main_api_app import app

print("Registered Routes:")
for route in app.routes:
    if hasattr(route, "path"):
        methods = getattr(route, "methods", [])
        print(f"Path: {route.path} | Methods: {methods}")
