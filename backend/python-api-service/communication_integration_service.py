"""
Communication Apps Integration Service for ATOM Agent Memory System

This service provides integration between communication apps (Slack, Gmail, Outlook, MS Teams)
and ATOM agent memory through LanceDB ingestion pipeline.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional

# Import communication services
try:
    from slack_service_real import real_slack_service
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

try:
    from teams_service_real import teams_service
    TEAMS_AVAILABLE = True
except ImportError:
    TEAMS_AVAILABLE = False

# Import OAuth handlers
try:
    from db_oauth_slack import get_user_slack_tokens
    SLACK_OAUTH_AVAILABLE = True
except ImportError:
    SLACK_OAUTH_AVAILABLE = False

try:
    from db_oauth_teams import get_user_teams_tokens
    TEAMS_OAUTH_AVAILABLE = True
except ImportError:
    TEAMS_OAUTH_AVAILABLE = False

# Import ATOM services
try:
    from sync.orchestration_service import OrchestrationService
    from sync.source_change_detector import SourceConfig, SourceType
    from text_processing_service import process_text_for_embeddings, generate_embeddings
    ATOM_SERVICES_AVAILABLE = True
except ImportError as e:
    ATOM_SERVICES_AVAILABLE = False
    logging.warning(f"ATOM services not available: {e}")

logger = logging.getLogger(__name__)


class CommunicationIntegrationService:
    """
    Service for communication apps integration with ATOM agent memory system
    """
    
    def __init__(self):
        self.processors: Dict[str, Dict[str, Any]] = {}
        self.orchestration_service: Optional[OrchestrationService] = None
        self.running = False
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Initialize service availability
        self.services = {
            'slack': {
                'available': SLACK_AVAILABLE and SLACK_OAUTH_AVAILABLE,
                'service': real_slack_service if SLACK_AVAILABLE else None,
                'get_tokens': get_user_slack_tokens if SLACK_OAUTH_AVAILABLE else None,
            },
            'teams': {
                'available': TEAMS_AVAILABLE and TEAMS_OAUTH_AVAILABLE,
                'service': teams_service if TEAMS_AVAILABLE else None,
                'get_tokens': get_user_teams_tokens if TEAMS_OAUTH_AVAILABLE else None,
            },
            'gmail': {
                'available': False,  # Gmail service not implemented yet
                'service': None,
                'get_tokens': None,
            },
            'outlook': {
                'available': False,  # Outlook service not implemented yet
                'service': None,
                'get_tokens': None,
            },
        }
        
        logger.info("Initialized CommunicationIntegrationService")
    
    async def initialize(
        self, 
        orchestration_service: Optional[OrchestrationService] = None
    ) -> bool:
        """Initialize communication integration service"""
        try:
            self.orchestration_service = orchestration_service
            self.running = True
            self.health_check_task = asyncio.create_task(self._health_monitoring_loop())
            
            logger.info("CommunicationIntegrationService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize CommunicationIntegrationService: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown communication integration service gracefully"""
        try:
            self.running = False
            
            # Stop health monitoring
            if self.health_check_task:
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("CommunicationIntegrationService shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during communication service shutdown: {e}")
    
    async def add_user_communication_integration(
        self, 
        user_id: str, 
        platform: str, 
        config_overrides: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Add communication integration for a user"""
        try:
            platform = platform.lower()
            
            if platform not in self.services:
                return {
                    "status": "unsupported",
                    "message": f"Platform '{platform}' not supported",
                    "supported_platforms": list(self.services.keys()),
                }
            
            service_info = self.services[platform]
            
            if not service_info['available']:
                return {
                    "status": "unavailable",
                    "message": f"Platform '{platform}' is not available",
                    "platform": platform,
                }
            
            # Check if user already has integration
            user_key = f"{user_id}_{platform}"
            if user_key in self.processors:
                return {
                    "status": "exists",
                    "message": f"User already has {platform} integration",
                    "user_id": user_id,
                    "platform": platform,
                }
            
            # Get user tokens
            if not service_info['get_tokens']:
                return {
                    "status": "no_oauth",
                    "message": f"OAuth handler not available for {platform}",
                    "platform": platform,
                }
            
            tokens = await service_info['get_tokens'](user_id)
            if not tokens or "access_token" not in tokens:
                return {
                    "status": "not_connected",
                    "message": f"User has not connected {platform} account",
                    "user_id": user_id,
                    "platform": platform,
                }
            
            # Test service connection
            if not service_info['service']:
                return {
                    "status": "no_service",
                    "message": f"{platform} service not available",
                    "platform": platform,
                }
            
            connection_test = await self._test_service_connection(
                platform, service_info['service'], tokens
            )
            
            if not connection_test:
                return {
                    "status": "connection_failed",
                    "message": f"Failed to connect to {platform}",
                    "user_id": user_id,
                    "platform": platform,
                }
            
            # Store user integration
            self.processors[user_key] = {
                "user_id": user_id,
                "platform": platform,
                "tokens": tokens,
                "service": service_info['service'],
                "config": config_overrides or {},
                "last_sync": None,
                "message_count": 0,
            }
            
            logger.info(f"Successfully added {platform} integration for user: {user_id}")
            
            return {
                "status": "success",
                "message": f"{platform.title()} integration added successfully",
                "user_id": user_id,
                "platform": platform,
                "features": await self._get_platform_features(platform),
            }
            
        except Exception as e:
            logger.error(f"Error adding {platform} integration for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error adding integration: {str(e)}",
                "user_id": user_id,
                "platform": platform,
            }
    
    async def remove_user_communication_integration(
        self, user_id: str, platform: str
    ) -> Dict[str, Any]:
        """Remove communication integration for a user"""
        try:
            platform = platform.lower()
            user_key = f"{user_id}_{platform}"
            
            # Check if user has integration
            if user_key not in self.processors:
                return {
                    "status": "not_found",
                    "message": f"User does not have {platform} integration",
                    "user_id": user_id,
                    "platform": platform,
                }
            
            # Remove integration
            del self.processors[user_key]
            
            logger.info(f"Successfully removed {platform} integration for user: {user_id}")
            
            return {
                "status": "success",
                "message": f"{platform.title()} integration removed successfully",
                "user_id": user_id,
                "platform": platform,
            }
            
        except Exception as e:
            logger.error(f"Error removing {platform} integration for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error removing integration: {str(e)}",
                "user_id": user_id,
                "platform": platform,
            }
    
    async def get_user_communication_status(
        self, user_id: str, platform: str = None
    ) -> Dict[str, Any]:
        """Get communication integration status for a user"""
        try:
            if platform:
                # Get status for specific platform
                platform = platform.lower()
                user_key = f"{user_id}_{platform}"
                
                if user_key not in self.processors:
                    return {
                        "status": "not_integrated",
                        "message": f"User does not have {platform} integration",
                        "user_id": user_id,
                        "platform": platform,
                    }
                
                integration = self.processors[user_key]
                
                # Test connection
                service_info = self.services[platform]
                connection_test = False
                if service_info['available'] and service_info['get_tokens']:
                    tokens = await service_info['get_tokens'](user_id)
                    if tokens and service_info['service']:
                        connection_test = await self._test_service_connection(
                            platform, service_info['service'], tokens
                        )
                
                return {
                    "status": "active" if connection_test else "disconnected",
                    "message": f"{platform.title()} integration is {'active' if connection_test else 'disconnected'}",
                    "user_id": user_id,
                    "platform": platform,
                    "connected": connection_test,
                    "last_sync": integration.get("last_sync"),
                    "message_count": integration.get("message_count", 0),
                }
            
            else:
                # Get status for all platforms
                platform_status = {}
                total_integrations = 0
                active_integrations = 0
                
                for platform_name in self.services.keys():
                    user_key = f"{user_id}_{platform_name}"
                    
                    if user_key in self.processors:
                        integration = self.processors[user_key]
                        total_integrations += 1
                        
                        # Test connection
                        service_info = self.services[platform_name]
                        connection_test = False
                        
                        if service_info['available'] and service_info['get_tokens']:
                            tokens = await service_info['get_tokens'](user_id)
                            if tokens and service_info['service']:
                                connection_test = await self._test_service_connection(
                                    platform_name, service_info['service'], tokens
                                )
                        
                        if connection_test:
                            active_integrations += 1
                        
                        platform_status[platform_name] = {
                            "integrated": True,
                            "connected": connection_test,
                            "last_sync": integration.get("last_sync"),
                            "message_count": integration.get("message_count", 0),
                        }
                    else:
                        platform_status[platform_name] = {
                            "integrated": False,
                            "connected": False,
                        }
                
                return {
                    "status": "complete",
                    "message": f"Communication integration status",
                    "user_id": user_id,
                    "total_integrations": total_integrations,
                    "active_integrations": active_integrations,
                    "platforms": platform_status,
                }
            
        except Exception as e:
            logger.error(f"Error getting communication status for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Error getting status: {str(e)}",
                "user_id": user_id,
            }
    
    async def get_integration_statistics(self) -> Dict[str, Any]:
        """Get overall communication integration statistics"""
        try:
            # Count integrations by platform
            platform_counts = {}
            total_integrations = 0
            total_messages = 0
            
            for user_key, integration in self.processors.items():
                platform = integration.get("platform", "unknown")
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
                total_integrations += 1
                total_messages += integration.get("message_count", 0)
            
            # Count active connections
            active_connections = 0
            for user_key, integration in self.processors.items():
                platform = integration.get("platform")
                service_info = self.services.get(platform, {})
                
                if service_info.get("available"):
                    # Test a sample connection
                    try:
                        tokens = await service_info.get("get_tokens", lambda _: None)(integration["user_id"])
                        if tokens and service_info.get("service"):
                            test_result = await self._test_service_connection(
                                platform, service_info["service"], tokens
                            )
                            if test_result:
                                active_connections += 1
                    except:
                        pass
            
            statistics = {
                "status": "active" if self.running else "inactive",
                "total_integrations": total_integrations,
                "active_connections": active_connections,
                "total_messages_processed": total_messages,
                "platform_counts": platform_counts,
                "supported_platforms": [
                    platform for platform, info in self.services.items()
                    if info["available"]
                ],
                "services_status": {
                    platform: info["available"]
                    for platform, info in self.services.items()
                },
                "atom_services_available": ATOM_SERVICES_AVAILABLE,
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"Error getting communication integration statistics: {e}")
            return {
                "status": "error",
                "message": f"Error getting statistics: {str(e)}",
            }
    
    async def _test_service_connection(
        self, platform: str, service: Any, tokens: Dict[str, Any]
    ) -> bool:
        """Test connection to service"""
        try:
            if platform == "slack":
                # Test Slack connection
                return await self._test_slack_connection(service, tokens)
            elif platform == "teams":
                # Test Teams connection
                return await self._test_teams_connection(service, tokens)
            else:
                logger.warning(f"No connection test implemented for {platform}")
                return False
                
        except Exception as e:
            logger.error(f"Error testing {platform} connection: {e}")
            return False
    
    async def _test_slack_connection(
        self, slack_service: Any, tokens: Dict[str, Any]
    ) -> bool:
        """Test Slack connection"""
        try:
            # Use slack service to test connection
            if hasattr(slack_service, 'get_client'):
                client = slack_service.get_client(tokens["access_token"])
                if client:
                    # Test API call
                    response = await client.auth_test()
                    return response.get("ok", False)
            return False
            
        except Exception as e:
            logger.error(f"Error testing Slack connection: {e}")
            return False
    
    async def _test_teams_connection(
        self, teams_service: Any, tokens: Dict[str, Any]
    ) -> bool:
        """Test Teams connection"""
        try:
            # Use teams service to test connection
            if hasattr(teams_service, 'get_client'):
                client = teams_service.get_client(tokens["access_token"])
                if client:
                    # Test Graph API call
                    response = client.get('https://graph.microsoft.com/v1.0/me')
                    return response.status_code == 200
            return False
            
        except Exception as e:
            logger.error(f"Error testing Teams connection: {e}")
            return False
    
    async def _get_platform_features(self, platform: str) -> List[str]:
        """Get available features for a platform"""
        features = {
            "slack": [
                "Message history retrieval",
                "Channel listing",
                "User information",
                "Real-time message streaming",
                "File access",
                "Search functionality",
            ],
            "teams": [
                "Message history retrieval",
                "Channel listing",
                "User information",
                "File access",
                "Search functionality",
            ],
            "gmail": [
                "Email retrieval",
                "Message processing",
                "Attachment handling",
                "Search functionality",
            ],
            "outlook": [
                "Email retrieval",
                "Message processing",
                "Attachment handling",
                "Search functionality",
            ],
        }
        
        return features.get(platform.lower(), [])
    
    async def _health_monitoring_loop(self) -> None:
        """Health monitoring loop for integration service"""
        while self.running:
            try:
                # Check health of all integrations
                unhealthy_integrations = []
                
                for user_key, integration in self.processors.items():
                    platform = integration.get("platform")
                    service_info = self.services.get(platform, {})
                    
                    if service_info.get("available"):
                        # Test connection
                        tokens = await service_info.get("get_tokens", lambda _: None)(integration["user_id"])
                        if tokens and service_info.get("service"):
                            connection_test = await self._test_service_connection(
                                platform, service_info["service"], tokens
                            )
                            if not connection_test:
                                unhealthy_integrations.append(user_key)
                    else:
                        unhealthy_integrations.append(user_key)
                
                # Log health status
                total_integrations = len(self.processors)
                healthy_integrations = total_integrations - len(unhealthy_integrations)
                
                logger.info(
                    f"Communication integration health: {healthy_integrations}/{total_integrations} integrations healthy"
                )
                
                # Wait for next health check
                await asyncio.sleep(300)  # 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in communication health monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retry


# Global service instance
_communication_integration_service: Optional[CommunicationIntegrationService] = None


def get_communication_integration_service() -> CommunicationIntegrationService:
    """Get global communication integration service instance"""
    global _communication_integration_service
    
    if _communication_integration_service is None:
        _communication_integration_service = CommunicationIntegrationService()
    
    return _communication_integration_service


async def initialize_communication_integration_service(
    orchestration_service: Optional[OrchestrationService] = None
) -> bool:
    """Initialize global communication integration service"""
    service = get_communication_integration_service()
    return await service.initialize(orchestration_service)


async def shutdown_communication_integration_service() -> None:
    """Shutdown global communication integration service"""
    service = get_communication_integration_service()
    await service.shutdown()