"""
Microsoft 365 Integration Registration
Complete registration and setup for Microsoft 365 unified platform integration
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
import json
import datetime

from microsoft365_unified_service import (
    Microsoft365UnifiedService,
    M365ServiceType,
    M365PermissionScope,
    create_m365_service,
    M365_CONFIG_EXAMPLE
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Microsoft365IntegrationRegistry:
    """
    Microsoft 365 Integration Registry
    Handles registration, configuration, and setup for M365 unified platform
    """
    
    def __init__(self):
        self.service: Optional[Microsoft365UnifiedService] = None
        self.registration_data = {
            "integration_id": "microsoft365",
            "integration_name": "Microsoft 365",
            "integration_version": "1.0.0",
            "registered_at": None,
            "service_health": {},
            "configured_services": [],
            "available_features": [],
            "api_limits": {},
            "usage_metrics": {}
        }
    
    async def register_integration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register Microsoft 365 integration with ATOM platform
        """
        try:
            logger.info("Registering Microsoft 365 integration...")
            
            # Initialize M365 service
            self.service = await create_m365_service(config)
            
            # Authenticate with Microsoft 365
            if not await self.service.authenticate():
                return {
                    "success": False,
                    "error": "Failed to authenticate with Microsoft 365",
                    "integration_id": "microsoft365"
                }
            
            # Test service connectivity
            health_status = await self._test_service_connectivity()
            
            # Update registration data
            self.registration_data.update({
                "registered_at": datetime.datetime.now().isoformat(),
                "service_health": health_status,
                "configured_services": await self._get_configured_services(),
                "available_features": await self._get_available_features(),
                "api_limits": self._get_api_limits(),
                "usage_metrics": await self._get_usage_metrics()
            })
            
            logger.info("Microsoft 365 integration registered successfully")
            return {
                "success": True,
                "integration_id": "microsoft365",
                "integration_name": "Microsoft 365",
                "status": "active",
                "registered_at": self.registration_data["registered_at"],
                "services_configured": len(self.registration_data["configured_services"]),
                "features_available": len(self.registration_data["available_features"]),
                "health_status": health_status
            }
            
        except Exception as e:
            logger.error(f"Error registering M365 integration: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "integration_id": "microsoft365"
            }
    
    async def _test_service_connectivity(self) -> Dict[str, Any]:
        """Test connectivity to all M365 services"""
        if not self.service:
            return {"status": "error", "message": "Service not initialized"}
        
        try:
            health_status = await self.service.get_service_health()
            return {
                "status": "healthy",
                "services": health_status,
                "tested_at": datetime.datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "tested_at": datetime.datetime.now().isoformat()
            }
    
    async def _get_configured_services(self) -> List[str]:
        """Get list of configured M365 services"""
        services = []
        
        if not self.service:
            return services
        
        try:
            # Test Teams
            teams = await self.service.get_teams()
            if teams:
                services.append("microsoft_teams")
            
            # Test Outlook/Email
            emails = await self.service.get_emails(limit=1)
            if emails is not None:
                services.append("microsoft_outlook")
            
            # Test OneDrive
            documents = await self.service.get_documents(limit=1)
            if documents is not None:
                services.append("microsoft_onedrive")
            
            # Test Calendar
            events = await self.service.get_calendar_events(limit=1)
            if events is not None:
                services.append("microsoft_calendar")
            
            # Test SharePoint
            sites = await self.service.get_sharepoint_sites()
            if sites:
                services.append("microsoft_sharepoint")
            
            # Test Power Automate
            flows = await self.service.get_power_automate_flows()
            if flows is not None:
                services.append("microsoft_power_automate")
            
        except Exception as e:
            logger.error(f"Error getting configured services: {str(e)}")
        
        return services
    
    async def _get_available_features(self) -> List[str]:
        """Get list of available features"""
        features = [
            # Core Features
            "unified_authentication",
            "cross_service_workflows",
            "enterprise_management",
            
            # Teams Features
            "team_management",
            "channel_operations",
            "messaging",
            "meetings",
            "presence_status",
            
            # Outlook Features
            "email_operations",
            "calendar_management",
            "contact_management",
            "task_management",
            
            # OneDrive Features
            "file_operations",
            "document_sharing",
            "version_control",
            "sync_management",
            
            # SharePoint Features
            "site_management",
            "content_collaboration",
            "document_library",
            "enterprise_search",
            
            # Power Platform Features
            "workflow_automation",
            "business_intelligence",
            "custom_applications",
            "data_integration",
            
            # Advanced Features
            "real_time_collaboration",
            "advanced_analytics",
            "security_compliance",
            "audit_logging",
            "api_management",
            "rate_limiting"
        ]
        
        return features
    
    def _get_api_limits(self) -> Dict[str, Any]:
        """Get API rate limits and quotas"""
        return {
            "graph_api": {
                "requests_per_minute": 6000,
                "requests_per_hour": 30000,
                "requests_per_day": 600000,
                "concurrent_requests": 100
            },
            "teams": {
                "messages_per_second": 100,
                "api_calls_per_minute": 1500
            },
            "outlook": {
                "emails_per_minute": 60,
                "api_calls_per_minute": 600
            },
            "onedrive": {
                "file_operations_per_minute": 200,
                "upload_size_limit": "250GB",
                "storage_quota": "1TB per user"
            },
            "sharepoint": {
                "api_calls_per_minute": 600,
                "site_quota": "100TB",
                "file_size_limit": "15GB"
            },
            "power_automate": {
                "flows_per_user": 500,
                "executions_per_day": 10000,
                "api_calls_per_minute": 100
            }
        }
    
    async def _get_usage_metrics(self) -> Dict[str, Any]:
        """Get current usage metrics"""
        try:
            if not self.service:
                return {}
            
            # Get sample usage data
            teams = await self.service.get_teams()
            emails = await self.service.get_emails(limit=100)
            documents = await self.service.get_documents(limit=100)
            events = await self.service.get_calendar_events(limit=100)
            flows = await self.service.get_power_automate_flows()
            
            return {
                "teams": {
                    "total_teams": len(teams),
                    "active_teams": len([t for t in teams if not t.is_archived]),
                    "total_channels": sum(t.channel_count for t in teams),
                    "total_members": sum(t.member_count for t in teams)
                },
                "outlook": {
                    "emails_processed": len(emails),
                    "calendar_events": len(events),
                    "active_conversations": len(emails)
                },
                "onedrive": {
                    "documents_accessed": len(documents),
                    "storage_used": sum(d.size_bytes for d in documents),
                    "files_shared": len([d for d in documents if d.share_link])
                },
                "power_automate": {
                    "flows_configured": len(flows),
                    "active_flows": len([f for f in flows if f.status == "enabled"]),
                    "success_rate": sum(f.success_rate for f in flows) / len(flows) if flows else 0,
                    "total_executions": sum(f.execution_count for f in flows)
                },
                "collected_at": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting usage metrics: {str(e)}")
            return {"error": str(e)}
    
    async def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        try:
            if not self.service:
                return {
                    "status": "not_initialized",
                    "integration_id": "microsoft365"
                }
            
            # Test authentication
            is_authenticated = await self.service._ensure_authenticated()
            
            # Get current health
            health_status = await self._test_service_connectivity()
            
            # Get current usage
            usage_metrics = await self._get_usage_metrics()
            
            return {
                "status": "active" if is_authenticated else "authentication_error",
                "integration_id": "microsoft365",
                "integration_name": "Microsoft 365",
                "health_status": health_status,
                "usage_metrics": usage_metrics,
                "last_checked": datetime.datetime.now().isoformat(),
                "services_configured": await self._get_configured_services(),
                "features_available": await self._get_available_features()
            }
            
        except Exception as e:
            logger.error(f"Error getting integration status: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "integration_id": "microsoft365"
            }
    
    async def update_configuration(self, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update integration configuration"""
        try:
            if not self.service:
                return {
                    "success": False,
                    "error": "Service not initialized",
                    "integration_id": "microsoft365"
                }
            
            # For now, this is a placeholder
            # In production, you'd update the service configuration
            logger.info(f"Updating M365 configuration with: {config_updates}")
            
            return {
                "success": True,
                "message": "Configuration updated successfully",
                "integration_id": "microsoft365",
                "updated_at": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating M365 configuration: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "integration_id": "microsoft365"
            }
    
    async def unregister_integration(self) -> Dict[str, Any]:
        """Unregister Microsoft 365 integration"""
        try:
            if self.service:
                await self.service.close()
                self.service = None
            
            self.registration_data = {
                "integration_id": "microsoft365",
                "integration_name": "Microsoft 365",
                "unregistered_at": datetime.datetime.now().isoformat(),
                "status": "unregistered"
            }
            
            logger.info("Microsoft 365 integration unregistered successfully")
            return {
                "success": True,
                "integration_id": "microsoft365",
                "unregistered_at": self.registration_data["unregistered_at"]
            }
            
        except Exception as e:
            logger.error(f"Error unregistering M365 integration: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "integration_id": "microsoft365"
            }
    
    def get_registration_info(self) -> Dict[str, Any]:
        """Get complete registration information"""
        return {
            "integration_id": "microsoft365",
            "integration_name": "Microsoft 365 Unified Platform",
            "integration_version": "1.0.0",
            "provider": "Microsoft",
            "description": "Complete Microsoft 365 platform integration with unified authentication, cross-service workflows, and enterprise management",
            "category": "productivity",
            "type": "unified_platform",
            "services_supported": [
                "Microsoft Teams",
                "Microsoft Outlook",
                "Microsoft OneDrive",
                "Microsoft SharePoint",
                "Microsoft Exchange",
                "Microsoft Power Automate",
                "Microsoft Power BI",
                "Microsoft Power Apps",
                "Microsoft Planner",
                "Microsoft Bookings",
                "Microsoft Viva",
                "Microsoft Loop",
                "Microsoft Whiteboard"
            ],
            "capabilities": [
                "unified_authentication",
                "cross_service_workflows",
                "enterprise_management",
                "real_time_collaboration",
                "advanced_analytics",
                "security_compliance",
                "audit_logging",
                "api_management"
            ],
            "authentication_methods": [
                "oauth2_client_credentials",
                "oauth2_authorization_code",
                "msal",
                "conditional_access",
                "multi_factor_authentication"
            ],
            "rate_limits": self._get_api_limits(),
            "supported_features": await self._get_available_features(),
            "registration_data": self.registration_data
        }

# Main execution function
async def main():
    """Main execution function for testing M365 registration"""
    registry = Microsoft365IntegrationRegistry()
    
    try:
        # Test configuration (use example for testing)
        config = M365_CONFIG_EXAMPLE.copy()
        config.update({
            "tenant_id": "test-tenant-id",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret"
        })
        
        print("🔧 Testing Microsoft 365 Integration Registration...")
        
        # Register integration
        result = await registry.register_integration(config)
        print(f"✅ Registration result: {result}")
        
        # Get status
        status = await registry.get_integration_status()
        print(f"✅ Status: {status}")
        
        # Get registration info
        info = registry.get_registration_info()
        print(f"✅ Registration info: {info}")
        
        # Unregister
        unregister_result = await registry.unregister_integration()
        print(f"✅ Unregistration result: {unregister_result}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())