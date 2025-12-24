
import os
import json
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class AutomationSettingsManager:
    """
    Manages global automation settings, providing toggles for 
    non-workflow-governed automations.
    """
    
    SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "automation_settings.json")
    
    DEFAULT_SETTINGS = {
        "enable_automatic_knowledge_extraction": True,
        "enable_out_of_workflow_automations": True,
        "document_processing_auto_trigger": True,
        "enable_accounting_automations": True,
        "enable_sales_automations": True,
        "response_control_mode": "suggest", # suggest, draft, auto_send
        "enable_integration_enrichment": True
    }
    
    def __init__(self):
        self._settings = self._load_settings()
        
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON file or return defaults"""
        try:
            # Ensure data directory exists
            Path(self.SETTINGS_FILE).parent.mkdir(parents=True, exist_ok=True)
            
            if os.path.exists(self.SETTINGS_FILE):
                with open(self.SETTINGS_FILE, 'r') as f:
                    return {**self.DEFAULT_SETTINGS, **json.load(f)}
            else:
                self._save_settings(self.DEFAULT_SETTINGS)
                return self.DEFAULT_SETTINGS.copy()
        except Exception as e:
            logger.error(f"Failed to load automation settings: {e}")
            return self.DEFAULT_SETTINGS.copy()
            
    def _save_settings(self, settings: Dict[str, Any]):
        """Persist settings to disk"""
        try:
            with open(self.SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save automation settings: {e}")

    def get_settings(self) -> Dict[str, Any]:
        """Get copy of current settings"""
        return self._settings.copy()

    def update_settings(self, new_settings: Dict[str, Any]):
        """Update settings and persist them"""
        self._settings.update(new_settings)
        self._save_settings(self._settings)
        return self._settings

    def is_extraction_enabled(self) -> bool:
        """Check if automatic KG extraction is enabled"""
        return self._settings.get("enable_automatic_knowledge_extraction", True)

    def is_automations_enabled(self) -> bool:
        """Check if general out-of-workflow automations are enabled"""
        return self._settings.get("enable_out_of_workflow_automations", True)

    def is_accounting_enabled(self) -> bool:
        """Check if accounting automations are enabled"""
        return self._settings.get("enable_accounting_automations", True)

    def is_sales_enabled(self) -> bool:
        """Check if sales automations are enabled"""
        return self._settings.get("enable_sales_automations", True)

# Global Manager Instance
automation_settings_manager = AutomationSettingsManager()

def get_automation_settings():
    return automation_settings_manager
