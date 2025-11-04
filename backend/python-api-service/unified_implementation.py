"""
ATOM Unified Implementation Management
Handles toggling between Mock and Real services
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger

class UnifiedImplementationManager:
    """Manages service implementation toggling"""
    
    def __init__(self):
        self.service_registry = {
            'Slack': {
                'mock': None,
                'real': None,
                'current': 'mock'
            },
            'MicrosoftTeams': {
                'mock': None,
                'real': None,
                'current': 'mock'
            }
        }
        
        # Load implementations based on environment
        self._load_implementations()
        
    def _load_implementations(self):
        """Load service implementations based on environment"""
        try:
            # Mock Services
            from .slack_service_mock import slack_service as mock_slack
            from .teams_service_mock import teams_service as mock_teams
            
            # Real Services
            from .slack_service_real import real_slack_service
            from .teams_service_real import teams_service
            
            # Register implementations
            self.service_registry['Slack']['mock'] = mock_slack
            self.service_registry['Slack']['real'] = real_slack_service
            self.service_registry['MicrosoftTeams']['mock'] = mock_teams
            self.service_registry['MicrosoftTeams']['real'] = teams_service
            
            # Determine active implementation
            environment = os.getenv('ATOM_SERVICE_ENV', 'mock')
            
            for service_name in self.service_registry:
                # Check environment-specific overrides
                env_key = f'{service_name.upper()}_USE_REAL'
                use_real = os.getenv(env_key, 'false').lower() == 'true'
                
                if use_real:
                    self.service_registry[service_name]['current'] = 'real'
                elif environment == 'real':
                    self.service_registry[service_name]['current'] = 'real'
                else:
                    self.service_registry[service_name]['current'] = 'mock'
            
            logger.info(f"Implementation Manager: Loaded services")
            for service_name, config in self.service_registry.items():
                logger.info(f"  {service_name}: {config['current']} implementation")
                
        except Exception as e:
            logger.error(f"Implementation Manager: Failed to load implementations: {e}")
            # Fallback to mock for all services
            for service_name in self.service_registry:
                self.service_registry[service_name]['current'] = 'mock'

    def get_service(self, service_name: str):
        """Get the currently active implementation for a service"""
        if service_name not in self.service_registry:
            logger.error(f"Implementation Manager: Unknown service {service_name}")
            return None
            
        config = self.service_registry[service_name]
        implementation_type = config['current']
        service = config[implementation_type]
        
        if not service:
            logger.error(f"Implementation Manager: {implementation_type} implementation not available for {service_name}")
            return None
            
        return service

    def switch_implementation(self, service_name: str, implementation_type: str) -> bool:
        """Switch implementation for a specific service"""
        if service_name not in self.service_registry:
            logger.error(f"Implementation Manager: Unknown service {service_name}")
            return False
            
        if implementation_type not in ['mock', 'real']:
            logger.error(f"Implementation Manager: Invalid implementation type {implementation_type}")
            return False
            
        # Check if implementation is available
        if not self.service_registry[service_name][implementation_type]:
            logger.error(f"Implementation Manager: {implementation_type} implementation not available for {service_name}")
            return False
        
        old_implementation = self.service_registry[service_name]['current']
        self.service_registry[service_name]['current'] = implementation_type
        
        logger.info(f"Implementation Manager: Switched {service_name} from {old_implementation} to {implementation_type}")
        return True

    def get_implementation_status(self) -> Dict[str, Any]:
        """Get current implementation status for all services"""
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": os.getenv('ATOM_SERVICE_ENV', 'mock'),
            "services": {}
        }
        
        for service_name, config in self.service_registry.items():
            status["services"][service_name] = {
                "current": config['current'],
                "mock_available": config['mock'] is not None,
                "real_available": config['real'] is not None
            }
        
        return status

    def validate_implementations(self) -> Dict[str, Any]:
        """Validate that all required services are available"""
        validation = {
            "timestamp": datetime.utcnow().isoformat(),
            "valid": True,
            "services": {},
            "errors": []
        }
        
        required_services = ['Slack', 'MicrosoftTeams']
        
        for service_name in required_services:
            if service_name not in self.service_registry:
                validation["services"][service_name] = {
                    "available": False,
                    "error": "Service not registered"
                }
                validation["valid"] = False
                validation["errors"].append(f"Service {service_name} not registered")
            else:
                config = self.service_registry[service_name]
                mock_available = config['mock'] is not None
                real_available = config['real'] is not None
                current_available = config[config['current']] is not None
                
                validation["services"][service_name] = {
                    "current": config['current'],
                    "mock_available": mock_available,
                    "real_available": real_available,
                    "current_available": current_available
                }
                
                if not current_available:
                    validation["valid"] = False
                    validation["errors"].append(f"Current implementation ({config['current']}) not available for {service_name}")
        
        return validation

# Initialize global implementation manager
implementation_manager = UnifiedImplementationManager()