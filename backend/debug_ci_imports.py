# -*- coding: utf-8 -*-
import sys
import os
import time
import signal
import importlib

print("=" * 60)
print("🔍 DEBUG CI IMPORTS: START")
print("=" * 60)

# Environment Diagnostics
print(f"ENV: ATOM_MOCK_DATABASE = {os.getenv('ATOM_MOCK_DATABASE')}")
print(f"ENV: ATOM_DISABLE_LANCEDB = {os.getenv('ATOM_DISABLE_LANCEDB')}")
print(f"ENV: DATABASE_URL = {os.getenv('DATABASE_URL')}")
print(f"ENV: ENVIRONMENT = {os.getenv('ENVIRONMENT')}")

def timeout_handler(signum, frame):
    raise TimeoutError("Import timed out!")

# Set a safety timeout for each import block (e.g. 30 seconds)
# If an import takes longer than this, we fail fast instead of hanging for 4m
SIGNAL_TIMEOUT = 30 

def debug_import(module_name):
    print(f"\n⏳ Importing: {module_name} ...")
    start_time = time.time()
    
    # Set alarm
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(SIGNAL_TIMEOUT)
    
    try:
        module = importlib.import_module(module_name)
        elapsed = time.time() - start_time
        signal.alarm(0) # Disable alarm
        print(f"✅ Import OK: {module_name} ({elapsed:.4f}s)")
        return module
    except TimeoutError:
        print(f"❌ TIMEOUT: {module_name} took longer than {SIGNAL_TIMEOUT}s")
        sys.exit(1)
    except Exception as e:
        signal.alarm(0) # Disable alarm
        print(f"❌ ERROR importing {module_name}: {e}")
        # We don't exit immediately, we might want to see other failures? 
        # Actually for CI, failing fast is usually better.
        sys.exit(1)

# 1. Test Database Mocking explicitly
print("\n--- TEST: Core Database ---")
try:
    db_module = debug_import("core.database")
    # Verify the Engine URL
    from core.database import engine, DATABASE_URL
    print(f"   -> core.database.DATABASE_URL = {DATABASE_URL}")
    print(f"   -> engine.url = {engine.url}")
    
    if "sqlite" in str(engine.url) and ":memory:" in str(engine.url):
         print("   -> 🛡️ MOCK CONFIRMED: Using in-memory SQLite")
    elif "sqlite" in str(engine.url) and "dev.db" in str(engine.url):
         print("   -> ⚠️ WARNING: Using dev.db file (Safe fallback, but slower than memory)")
    else:
         print(f"   -> 🚨 DANGER: Using REAL DATABASE connection: {engine.url}")
         
except SystemExit:
    raise
except Exception as e:
    print(f"   -> Critical DB Check Failed: {e}")

# 2. Main API App (Heaviest import, initializes generic Agents?)
print("\n--- TEST: Main API App ---")
debug_import("main_api_app")

# 3. Core Agents
print("\n--- TEST: Core Agents ---")
debug_import("core.generic_agent")
debug_import("core.atom_meta_agent")
debug_import("core.agent_governance_service")
debug_import("integrations.mcp_service")

# 4. Advanced Orchestrator (Suspected culprit)
print("\n--- TEST: Advanced Orchestrator ---")
debug_import("advanced_workflow_orchestrator")

print("\n" + "=" * 60)
print("✅ DEBUG CI IMPORTS: FINISHED SUCCESS")
print("=" * 60)
