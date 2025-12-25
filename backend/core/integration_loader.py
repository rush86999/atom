import importlib
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import asyncio
from functools import wraps
from integrations.atom_ingestion_pipeline import atom_ingestion_pipeline

logger = logging.getLogger(__name__)

class IntegrationLoader:
    def __init__(self):
        self.integrations = []
        self.timeout_seconds = 5  # Timeout for each integration load

    def _load_module_with_timeout(self, module_path, router_name):
        """Load module in a separate thread with timeout"""
        try:
            module = importlib.import_module(module_path)
            router = getattr(module, router_name)
            return router
        except Exception as e:
            raise e

    def load_integration(self, module_path, router_name="router", condition=True):
        """
        Attempts to import a router from a module with timeout protection.
        
        Args:
            module_path (str): Dot-notation path to the module (e.g., 'integrations.asana_routes').
            router_name (str): Name of the router object in the module. Defaults to 'router'.
            condition (bool): Optional condition that must be true to attempt loading.
            
        Returns:
            APIRouter or None: The imported router if successful, else None.
        """
        if not condition:
            return None

        # Print progress
        print(f"  Loading {module_path}...", end="", flush=True)
        start_time = time.time()

        try:
            # Use ThreadPoolExecutor for timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._load_module_with_timeout, module_path, router_name)
                try:
                    router = future.result(timeout=self.timeout_seconds)
                    elapsed = time.time() - start_time
                    print(f" ✓ ({elapsed:.1f}s)")
                    self.integrations.append({
                        "name": module_path,
                        "router": router,
                        "status": "loaded"
                    })
                    logger.info(f"[OK] {module_path} loaded")
                    return router
                except FuturesTimeoutError:
                    print(f" ✗ TIMEOUT (>{self.timeout_seconds}s)")
                    logger.warning(f"[TIMEOUT] {module_path} took too long to load")
                    self.integrations.append({
                        "name": module_path,
                        "router": None,
                        "status": "timeout",
                        "error": f"Timeout after {self.timeout_seconds}s"
                    })
                    return None
        except ImportError as e:
            elapsed = time.time() - start_time
            print(f" ✗ Not available ({elapsed:.1f}s)")
            logger.warning(f"[WARN] {module_path} not available: {e}")
            self.integrations.append({
                "name": module_path,
                "router": None,
                "status": "failed",
                "error": str(e)
            })
            return None
        except AttributeError as e:
            elapsed = time.time() - start_time
            print(f" ✗ Router not found ({elapsed:.1f}s)")
            logger.error(f"[ERR] {module_path} loaded but '{router_name}' not found: {e}")
            return None
        except Exception as e:
            elapsed = time.time() - start_time
            print(f" ✗ Error ({elapsed:.1f}s)")
            logger.error(f"[ERR] {module_path} failed: {e}")
            self.integrations.append({
                "name": module_path,
                "router": None,
                "status": "error",
                "error": str(e)
            })
            return None

    def get_loaded_integrations(self):
        return [i for i in self.integrations if i["status"] == "loaded"]

def auto_ingest(app_type: str, record_type: str):
    """
    Decorator to automatically ingest API response data into the ATOM Ingestion Pipeline.
    Expects the decorated function to return a dict or a list of dicts.
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            if result:
                # Ingest safely in background
                try:
                    if isinstance(result, list):
                        for item in result:
                            atom_ingestion_pipeline.ingest_record(app_type, record_type, item)
                    elif isinstance(result, dict):
                        atom_ingestion_pipeline.ingest_record(app_type, record_type, result)
                except Exception as e:
                    logger.error(f"AutoIngest failed for {app_type}: {e}")
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if result:
                try:
                    if isinstance(result, list):
                        for item in result:
                            atom_ingestion_pipeline.ingest_record(app_type, record_type, item)
                    elif isinstance(result, dict):
                        atom_ingestion_pipeline.ingest_record(app_type, record_type, result)
                except Exception as e:
                    logger.error(f"AutoIngest failed for {app_type}: {e}")
            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
