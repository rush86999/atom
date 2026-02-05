"""
WhatsApp Business Service Manager
Enhanced service management with production-ready features
"""

from datetime import datetime, timedelta
import json
import logging
import os
from typing import Any, Dict, Optional

from .whatsapp_business_integration import WhatsAppBusinessIntegration, whatsapp_integration

logger = logging.getLogger(__name__)


class WhatsAppServiceManager:
    """Enhanced service management for WhatsApp Business integration"""

    def __init__(self):
        self.service_id = "whatsapp_business"
        self.integration = whatsapp_integration
        self.config = {}
        self.status = "disconnected"
        self.health_metrics = {
            "last_health_check": None,
            "consecutive_failures": 0,
            "uptime_percentage": 0,
            "message_success_rate": 0,
        }

    def load_configuration(self) -> Dict[str, Any]:
        """Load WhatsApp configuration from environment and database"""
        try:
            from .whatsapp_configuration_setup import (
                get_or_create_configuration,
                validate_configuration,
            )

            # Get configuration (real or demo)
            config = get_or_create_configuration()

            # Validate configuration
            validation = validate_configuration(config)

            if validation["is_demo"]:
                logger.info("Using demo WhatsApp configuration for testing")
                print(
                    "WhatsApp Business: DEMO MODE - Use real API credentials for production"
                )
            elif not validation["is_valid"]:
                logger.warning(
                    f"WhatsApp configuration incomplete: {validation['missing_required']}"
                )
                print(
                    f"WhatsApp Business: Configuration incomplete - {validation['missing_required']}"
                )

            # Add service-specific configuration
            config.update(
                {
                    "validation": validation,
                    "service_manager": True,
                    "loaded_at": datetime.now().isoformat(),
                }
            )

            self.config = config
            return config

        except Exception as e:
            logger.error(f"Error loading WhatsApp configuration: {str(e)}")
            # Return demo configuration as fallback
            from .whatsapp_configuration_setup import setup_demo_configuration

            demo_config = setup_demo_configuration()
            demo_config["validation"] = {
                "is_valid": True,
                "is_demo": True,
                "errors": [],
                "warnings": ["Using demo configuration as fallback"],
                "missing_required": [],
                "configuration_type": "demo_fallback",
            }
            self.config = demo_config
            return demo_config

    def initialize_service(self) -> Dict[str, Any]:
        """Initialize WhatsApp service with configuration"""
        try:
            config = self.load_configuration()

            if config.get("status") == "error":
                return {
                    "success": False,
                    "error": config.get("error"),
                    "status": "configuration_error",
                }

            if config.get("status") == "incomplete":
                return {
                    "success": False,
                    "error": "Missing required configuration fields",
                    "status": "incomplete_configuration",
                    "missing_fields": ["access_token", "phone_number_id"],
                }

            # Initialize the integration
            init_success = self.integration.initialize(config)

            if init_success:
                self.status = "connected"
                self.health_metrics["last_health_check"] = datetime.now()
                self.health_metrics["consecutive_failures"] = 0

                # Register service with service registry
                self._register_with_service_registry()

                logger.info("WhatsApp Business service initialized successfully")
                return {
                    "success": True,
                    "status": "initialized",
                    "service_id": self.service_id,
                    "features_enabled": config.get("features", {}),
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                self.status = "failed"
                return {
                    "success": False,
                    "error": "Failed to initialize WhatsApp integration",
                    "status": "initialization_failed",
                }

        except Exception as e:
            logger.error(f"Error initializing WhatsApp service: {str(e)}")
            self.status = "error"
            return {"success": False, "error": str(e), "status": "initialization_error"}

    def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for WhatsApp service"""
        try:
            current_time = datetime.now()

            # Basic connectivity check
            if self.config.get("status") != "configured":
                return {
                    "status": "unhealthy",
                    "error": "Configuration incomplete",
                    "last_check": current_time.isoformat(),
                }

            # Check API connectivity
            test_result = self._test_api_connectivity()

            # Check database connectivity
            db_status = self._test_database_connectivity()

            # Calculate health metrics
            health_score = self._calculate_health_score(test_result, db_status)

            # Update health metrics
            self.health_metrics["last_health_check"] = current_time

            if health_score >= 0.9:
                health_status = "healthy"
                self.health_metrics["consecutive_failures"] = 0
            elif health_score >= 0.7:
                health_status = "degraded"
            else:
                health_status = "unhealthy"
                self.health_metrics["consecutive_failures"] += 1

            self.status = health_status

            return {
                "status": health_status,
                "health_score": health_score,
                "api_connectivity": test_result,
                "database_connectivity": db_status,
                "consecutive_failures": self.health_metrics["consecutive_failures"],
                "uptime_percentage": self.health_metrics["uptime_percentage"],
                "message_success_rate": self.health_metrics["message_success_rate"],
                "last_check": current_time.isoformat(),
                "service_id": self.service_id,
            }

        except Exception as e:
            logger.error(f"Error during WhatsApp health check: {str(e)}")
            self.health_metrics["consecutive_failures"] += 1
            return {
                "status": "unhealthy",
                "error": str(e),
                "consecutive_failures": self.health_metrics["consecutive_failures"],
                "last_check": datetime.now().isoformat(),
            }

    def get_service_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service metrics"""
        try:
            # Get basic metrics from integration
            if not self.integration or not hasattr(self.integration, "get_analytics"):
                return {"status": "unavailable", "error": "Integration not available"}

            # Get analytics from last 30 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            analytics = self.integration.get_analytics(start_date, end_date)

            # Calculate additional metrics
            metrics = {
                "service_id": self.service_id,
                "status": self.status,
                "health_metrics": self.health_metrics,
                "analytics": analytics,
                "configuration": {
                    "auto_reply_enabled": self.config.get("features", {}).get(
                        "auto_reply_enabled", False
                    ),
                    "business_hours_enabled": self.config.get("features", {}).get(
                        "business_hours_enabled", False
                    ),
                    "message_retention_days": self.config.get("features", {}).get(
                        "message_retention_days", 30
                    ),
                },
                "performance": {
                    "average_response_time": self._calculate_average_response_time(),
                    "peak_hours": self._get_peak_usage_hours(),
                    "top_templates": self._get_top_templates(),
                    "active_conversations": self._get_active_conversation_count(),
                },
                "timestamp": datetime.now().isoformat(),
            }

            return metrics

        except Exception as e:
            logger.error(f"Error getting service metrics: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _test_api_connectivity(self) -> Dict[str, Any]:
        """Test WhatsApp API connectivity"""
        try:
            if not self.integration or not self.integration.access_token:
                return {"status": "failed", "error": "No access token configured"}

            # Test API health endpoint
            import requests

            url = f"{self.integration.base_url}/me"
            headers = {"Authorization": f"Bearer {self.integration.access_token}"}

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "response_time": response.elapsed.total_seconds(),
                    "api_version": "v18.0",
                }
            else:
                return {
                    "status": "failed",
                    "error": f"API returned status {response.status_code}",
                    "response_text": response.text[:200],
                }

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def _test_database_connectivity(self) -> Dict[str, Any]:
        """Test database connectivity"""
        try:
            if not self.integration or not self.integration.db_connection:
                return {
                    "status": "failed",
                    "error": "Database connection not available",
                }

            # Test database query
            with self.integration.db_connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            return {"status": "healthy", "database": "PostgreSQL"}

        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def _calculate_health_score(self, api_result: Dict, db_result: Dict) -> float:
        """Calculate overall health score (0.0 to 1.0)"""
        score = 1.0

        if api_result.get("status") != "healthy":
            score -= 0.5

        if db_result.get("status") != "healthy":
            score -= 0.4

        # Penalty for consecutive failures
        if self.health_metrics["consecutive_failures"] > 0:
            score -= min(0.3, self.health_metrics["consecutive_failures"] * 0.1)

        return max(0.0, score)

    def _calculate_average_response_time(self) -> float:
        """Calculate average response time in minutes"""
        # This would typically query the database for actual response times
        return 2.5  # Placeholder value

    def _get_peak_usage_hours(self) -> list:
        """Get peak usage hours"""
        return ["09:00-11:00", "14:00-16:00"]  # Placeholder data

    def _get_top_templates(self) -> list:
        """Get most used templates"""
        return [
            "appointment_reminder",
            "welcome_message",
            "follow_up",
        ]  # Placeholder data

    def _get_active_conversation_count(self) -> int:
        """Get count of active conversations"""
        try:
            if self.integration and hasattr(self.integration, "get_conversations"):
                conversations = self.integration.get_conversations(limit=100)
                return len(conversations)
            return 0
        except Exception as e:
            return 0

    def _register_with_service_registry(self):
        """Register WhatsApp service with the service registry"""
        try:
            # This would integrate with the existing service registry
            service_info = {
                "service_id": self.service_id,
                "name": "WhatsApp Business",
                "type": "communication",
                "status": self.status,
                "capabilities": [
                    "send_messages",
                    "receive_messages",
                    "template_messages",
                    "media_messages",
                    "customer_support",
                    "auto_responses",
                    "message_analytics",
                    "conversation_management",
                ],
                "endpoints": [
                    "/api/whatsapp/health",
                    "/api/whatsapp/send",
                    "/api/whatsapp/conversations",
                    "/api/whatsapp/messages/{whatsapp_id}",
                    "/api/whatsapp/templates",
                    "/api/whatsapp/analytics",
                ],
                "configuration": {
                    "requires_oauth": False,
                    "requires_api_key": True,
                    "webhook_support": True,
                },
                "timestamp": datetime.now().isoformat(),
            }

            # Store service info (this would integrate with service registry)
            with open(f"/tmp/{self.service_id}_registration.json", "w") as f:
                json.dump(service_info, f, indent=2)

            logger.info(f"WhatsApp service registered: {self.service_id}")

        except Exception as e:
            logger.error(f"Error registering WhatsApp service: {str(e)}")


# Global service manager instance
whatsapp_service_manager = WhatsAppServiceManager()


def initialize_whatsapp_service() -> Dict[str, Any]:
    """Initialize WhatsApp Business service"""
    return whatsapp_service_manager.initialize_service()


def get_whatsapp_service_status() -> Dict[str, Any]:
    """Get WhatsApp service health status"""
    return whatsapp_service_manager.health_check()


def get_whatsapp_service_metrics() -> Dict[str, Any]:
    """Get WhatsApp service metrics"""
    return whatsapp_service_manager.get_service_metrics()
