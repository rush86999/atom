import importlib
import logging

logger = logging.getLogger(__name__)

class IntegrationLoader:
    def __init__(self):
        self.integrations = []

    def load_integration(self, module_path, router_name="router", condition=True):
        """
        Attempts to import a router from a module.
        
        Args:
            module_path (str): Dot-notation path to the module (e.g., 'integrations.asana_routes').
            router_name (str): Name of the router object in the module. Defaults to 'router'.
            condition (bool): Optional condition that must be true to attempt loading.
            
        Returns:
            APIRouter or None: The imported router if successful, else None.
        """
        if not condition:
            return None

        try:
            module = importlib.import_module(module_path)
            router = getattr(module, router_name)
            self.integrations.append({
                "name": module_path,
                "router": router,
                "status": "loaded"
            })
            logger.info(f"[OK] {module_path} loaded")
            return router
        except ImportError as e:
            logger.warning(f"[WARN] {module_path} not available: {e}")
            self.integrations.append({
                "name": module_path,
                "router": None,
                "status": "failed",
                "error": str(e)
            })
            return None
        except AttributeError as e:
            logger.error(f"[ERR] {module_path} loaded but '{router_name}' not found: {e}")
            return None

    def get_loaded_integrations(self):
        return [i for i in self.integrations if i["status"] == "loaded"]
