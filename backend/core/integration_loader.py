import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from functools import wraps
import importlib
import logging
import re
import sys
import time

from integrations.atom_ingestion_pipeline import atom_ingestion_pipeline

logger = logging.getLogger(__name__)

# Validate module paths to prevent directory traversal attacks
VALID_MODULE_PATTERN = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$')

class IntegrationLoader:
    def __init__(self, timeout: int = None):
        self.integrations = []
        # Use environment variable or provided timeout, default to 5 seconds
        import os
        default_timeout = int(os.getenv("INTEGRATION_LOAD_TIMEOUT", "5"))
        self.timeout_seconds = timeout if timeout is not None else default_timeout

    def _validate_module_path(self, module_path: str) -> bool:
        """Validate module path to prevent directory traversal attacks"""
        if not VALID_MODULE_PATTERN.match(module_path):
            raise ValueError(f"Invalid module path: {module_path}")

        # Block dangerous modules
        blocked_prefixes = ['os.', 'sys.', 'subprocess.', 'eval']
        if any(module_path.startswith(prefix) for prefix in blocked_prefixes):
            raise ValueError(f"Restricted module: {module_path}")

        return True

    def _load_module_with_timeout(self, module_path, router_name):
        """Load module in a separate thread with timeout"""
        # Validate module path before loading
        self._validate_module_path(module_path)

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

        # Log progress
        logger.debug(f"  Loading {module_path}...")
        start_time = time.time()

        try:
            # Use ThreadPoolExecutor for timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._load_module_with_timeout, module_path, router_name)
                try:
                    router = future.result(timeout=self.timeout_seconds)
                    elapsed = time.time() - start_time
                    logger.info(f"  ✓ {module_path} loaded ({elapsed:.1f}s)")
                    self.integrations.append({
                        "name": module_path,
                        "router": router,
                        "status": "loaded"
                    })
                    return router
                except FuturesTimeoutError:
                    logger.warning(f"  ✗ TIMEOUT {module_path} (>{self.timeout_seconds}s)")
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
            logger.warning(f"  ✗ Not available: {module_path} ({elapsed:.1f}s)")
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
            logger.warning(f"  ✗ Router not found: {module_path} ({elapsed:.1f}s)")
            logger.error(f"[ERR] {module_path} loaded but '{router_name}' not found: {e}")
            return None
        except Exception as e:
            elapsed = time.time() - start_time
            logger.warning(f"  ✗ Error: {module_path} ({elapsed:.1f}s)")
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
