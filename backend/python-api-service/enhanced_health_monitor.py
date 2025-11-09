#!/usr/bin/env python3
"""
Enhanced Health Monitoring System for ATOM Integrations
Provides comprehensive health checks for all integration services
"""

import os
import json
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from asyncpg import Pool

logger = logging.getLogger(__name__)

@dataclass
class ServiceHealth:
    """Service health status data structure"""
    name: str
    status: str  # 'healthy', 'unhealthy', 'degraded', 'unknown'
    connected: bool
    response_time: Optional[float] = None
    last_check: str = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class IntegrationHealthReport:
    """Complete integration health report"""
    integration_name: str
    overall_status: str  # 'healthy', 'unhealthy', 'degraded', 'unknown'
    services: List[ServiceHealth]
    connected_count: int
    total_services: int
    timestamp: str
    backend_connected: bool = True

class IntegrationHealthMonitor:
    """Enhanced health monitoring for all integrations"""
    
    def __init__(self):
        self.health_cache = {}
        self.cache_timeout = 60  # seconds
        
    async def check_hubspot_health(self, user_id: str = None) -> IntegrationHealthReport:
        """Check HubSpot integration health"""
        services = []
        
        # API Health Check
        api_health = await self._check_api_health(
            "HubSpot API", 
            "https://api.hubapi.com/crm/v3/objects/contacts?limit=1"
        )
        services.append(api_health)
        
        # Auth Health Check
        if user_id:
            auth_health = await self._check_hubspot_auth_health(user_id)
            services.append(auth_health)
        else:
            services.append(ServiceHealth(
                name="HubSpot Auth",
                status="degraded",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error="No user ID provided for auth check"
            ))
        
        # Webhooks Health Check
        webhook_health = await self._check_hubspot_webhooks_health()
        services.append(webhook_health)
        
        # Overall status calculation
        connected_count = sum(1 for s in services if s.connected)
        total_services = len(services)
        
        if connected_count == total_services:
            overall_status = "healthy"
        elif connected_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return IntegrationHealthReport(
            integration_name="HubSpot",
            overall_status=overall_status,
            services=services,
            connected_count=connected_count,
            total_services=total_services,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    async def check_slack_health(self, user_id: str = None) -> IntegrationHealthReport:
        """Check Slack integration health"""
        services = []
        
        # API Health Check
        api_health = await self._check_api_health(
            "Slack API", 
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN', '')}"}
        )
        services.append(api_health)
        
        # Auth Health Check
        if user_id:
            auth_health = await self._check_slack_auth_health(user_id)
            services.append(auth_health)
        else:
            services.append(ServiceHealth(
                name="Slack Auth",
                status="degraded",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error="No user ID provided for auth check"
            ))
        
        # Events API Health Check
        events_health = await self._check_slack_events_health()
        services.append(events_health)
        
        # Webhooks Health Check
        webhook_health = await self._check_slack_webhooks_health()
        services.append(webhook_health)
        
        # Overall status calculation
        connected_count = sum(1 for s in services if s.connected)
        total_services = len(services)
        
        if connected_count == total_services:
            overall_status = "healthy"
        elif connected_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return IntegrationHealthReport(
            integration_name="Slack",
            overall_status=overall_status,
            services=services,
            connected_count=connected_count,
            total_services=total_services,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    async def check_jira_health(self, user_id: str = None) -> IntegrationHealthReport:
        """Check Jira integration health"""
        services = []
        
        # API Health Check
        api_health = await self._check_api_health(
            "Jira API", 
            "https://api.atlassian.com/ex/jira/rest/api/3/myself"
        )
        services.append(api_health)
        
        # Auth Health Check
        if user_id:
            auth_health = await self._check_jira_auth_health(user_id)
            services.append(auth_health)
        else:
            services.append(ServiceHealth(
                name="Jira Auth",
                status="degraded",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error="No user ID provided for auth check"
            ))
        
        # Issues Service Health Check
        issues_health = await self._check_jira_issues_health()
        services.append(issues_health)
        
        # Projects Service Health Check
        projects_health = await self._check_jira_projects_health()
        services.append(projects_health)
        
        # Overall status calculation
        connected_count = sum(1 for s in services if s.connected)
        total_services = len(services)
        
        if connected_count == total_services:
            overall_status = "healthy"
        elif connected_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return IntegrationHealthReport(
            integration_name="Jira",
            overall_status=overall_status,
            services=services,
            connected_count=connected_count,
            total_services=total_services,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    async def check_linear_health(self, user_id: str = None) -> IntegrationHealthReport:
        """Check Linear integration health"""
        services = []
        
        # API Health Check
        api_health = await self._check_api_health(
            "Linear API", 
            "https://api.linear.app/query",
            method="POST",
            data={"query": "{ viewer { id } }"}
        )
        services.append(api_health)
        
        # Auth Health Check
        if user_id:
            auth_health = await self._check_linear_auth_health(user_id)
            services.append(auth_health)
        else:
            services.append(ServiceHealth(
                name="Linear Auth",
                status="degraded",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error="No user ID provided for auth check"
            ))
        
        # Issues Service Health Check
        issues_health = await self._check_linear_issues_health()
        services.append(issues_health)
        
        # Teams Service Health Check
        teams_health = await self._check_linear_teams_health()
        services.append(teams_health)
        
        # Overall status calculation
        connected_count = sum(1 for s in services if s.connected)
        total_services = len(services)
        
        if connected_count == total_services:
            overall_status = "healthy"
        elif connected_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return IntegrationHealthReport(
            integration_name="Linear",
            overall_status=overall_status,
            services=services,
            connected_count=connected_count,
            total_services=total_services,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    async def check_salesforce_health(self, user_id: str = None) -> IntegrationHealthReport:
        """Check Salesforce integration health"""
        services = []
        
        # API Health Check
        api_health = await self._check_api_health(
            "Salesforce API", 
            "https://login.salesforce.com/services/oauth2/token"
        )
        services.append(api_health)
        
        # Auth Health Check
        if user_id:
            auth_health = await self._check_salesforce_auth_health(user_id)
            services.append(auth_health)
        else:
            services.append(ServiceHealth(
                name="Salesforce Auth",
                status="degraded",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error="No user ID provided for auth check"
            ))
        
        # SObjects Service Health Check
        sobjects_health = await self._check_salesforce_sobjects_health()
        services.append(sobjects_health)
        
        # SOQL Service Health Check
        soql_health = await self._check_salesforce_soql_health()
        services.append(soql_health)
        
        # Overall status calculation
        connected_count = sum(1 for s in services if s.connected)
        total_services = len(services)
        
        if connected_count == total_services:
            overall_status = "healthy"
        elif connected_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return IntegrationHealthReport(
            integration_name="Salesforce",
            overall_status=overall_status,
            services=services,
            connected_count=connected_count,
            total_services=total_services,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    async def check_xero_health(self, user_id: str = None) -> IntegrationHealthReport:
        """Check Xero integration health"""
        services = []
        
        # API Health Check
        api_health = await self._check_api_health(
            "Xero API", 
            "https://api.xero.com/connections"
        )
        services.append(api_health)
        
        # Auth Health Check
        if user_id:
            auth_health = await self._check_xero_auth_health(user_id)
            services.append(auth_health)
        else:
            services.append(ServiceHealth(
                name="Xero Auth",
                status="degraded",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error="No user ID provided for auth check"
            ))
        
        # Accounting API Health Check
        accounting_health = await self._check_xero_accounting_health()
        services.append(accounting_health)
        
        # Payroll Service Health Check
        payroll_health = await self._check_xero_payroll_health()
        services.append(payroll_health)
        
        # Overall status calculation
        connected_count = sum(1 for s in services if s.connected)
        total_services = len(services)
        
        if connected_count == total_services:
            overall_status = "healthy"
        elif connected_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"
        
        return IntegrationHealthReport(
            integration_name="Xero",
            overall_status=overall_status,
            services=services,
            connected_count=connected_count,
            total_services=total_services,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    # Helper methods for specific health checks
    async def _check_api_health(self, name: str, url: str, method: str = "GET", 
                               headers: Dict[str, str] = None, 
                               data: Dict[str, Any] = None) -> ServiceHealth:
        """Generic API health check"""
        start_time = time.time()
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data)
                else:
                    response = await client.request(method, url, headers=headers, json=data)
                
                response_time = (time.time() - start_time) * 1000  # milliseconds
                
                if response.status_code < 400:
                    return ServiceHealth(
                        name=name,
                        status="healthy",
                        connected=True,
                        response_time=response_time,
                        last_check=datetime.now(timezone.utc).isoformat(),
                        metadata={"status_code": response.status_code}
                    )
                else:
                    return ServiceHealth(
                        name=name,
                        status="unhealthy",
                        connected=False,
                        response_time=response_time,
                        last_check=datetime.now(timezone.utc).isoformat(),
                        error=f"HTTP {response.status_code}: {response.text[:200]}",
                        metadata={"status_code": response.status_code}
                    )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ServiceHealth(
                name=name,
                status="unhealthy",
                connected=False,
                response_time=response_time,
                last_check=datetime.now(timezone.utc).isoformat(),
                error=str(e)
            )
    
    async def _check_hubspot_auth_health(self, user_id: str) -> ServiceHealth:
        """Check HubSpot authentication health"""
        try:
            from db_oauth_hubspot import get_user_hubspot_tokens
            from main_api_app import get_db_pool
            
            db_pool = await get_db_pool()
            tokens = await get_user_hubspot_tokens(db_pool, user_id)
            
            if tokens and tokens.get("access_token"):
                return ServiceHealth(
                    name="HubSpot Auth",
                    status="healthy",
                    connected=True,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    metadata={"has_refresh_token": bool(tokens.get("refresh_token"))}
                )
            else:
                return ServiceHealth(
                    name="HubSpot Auth",
                    status="unhealthy",
                    connected=False,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error="No valid tokens found"
                )
        except Exception as e:
            return ServiceHealth(
                name="HubSpot Auth",
                status="unhealthy",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error=str(e)
            )
    
    async def _check_hubspot_webhooks_health(self) -> ServiceHealth:
        """Check HubSpot webhooks health"""
        return ServiceHealth(
            name="HubSpot Webhooks",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Webhook health check not implemented"
        )
    
    async def _check_slack_auth_health(self, user_id: str) -> ServiceHealth:
        """Check Slack authentication health"""
        try:
            from db_oauth_slack import get_user_slack_tokens
            from main_api_app import get_db_pool
            
            db_pool = await get_db_pool()
            tokens = await get_user_slack_tokens(db_pool, user_id)
            
            if tokens and tokens.get("access_token"):
                return ServiceHealth(
                    name="Slack Auth",
                    status="healthy",
                    connected=True,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    metadata={"has_bot_token": bool(tokens.get("bot_token"))}
                )
            else:
                return ServiceHealth(
                    name="Slack Auth",
                    status="unhealthy",
                    connected=False,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error="No valid tokens found"
                )
        except Exception as e:
            return ServiceHealth(
                name="Slack Auth",
                status="unhealthy",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error=str(e)
            )
    
    async def _check_slack_events_health(self) -> ServiceHealth:
        """Check Slack events API health"""
        return ServiceHealth(
            name="Slack Events",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Events API health check not implemented"
        )
    
    async def _check_slack_webhooks_health(self) -> ServiceHealth:
        """Check Slack webhooks health"""
        return ServiceHealth(
            name="Slack Webhooks",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Webhooks health check not implemented"
        )
    
    async def _check_jira_auth_health(self, user_id: str) -> ServiceHealth:
        """Check Jira authentication health"""
        try:
            from db_oauth_jira import get_user_jira_tokens
            from main_api_app import get_db_pool
            
            db_pool = await get_db_pool()
            tokens = await get_user_jira_tokens(db_pool, user_id)
            
            if tokens and tokens.get("access_token"):
                return ServiceHealth(
                    name="Jira Auth",
                    status="healthy",
                    connected=True,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    metadata={"has_refresh_token": bool(tokens.get("refresh_token"))}
                )
            else:
                return ServiceHealth(
                    name="Jira Auth",
                    status="unhealthy",
                    connected=False,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error="No valid tokens found"
                )
        except Exception as e:
            return ServiceHealth(
                name="Jira Auth",
                status="unhealthy",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error=str(e)
            )
    
    async def _check_jira_issues_health(self) -> ServiceHealth:
        """Check Jira issues service health"""
        return ServiceHealth(
            name="Jira Issues",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Issues service health check not implemented"
        )
    
    async def _check_jira_projects_health(self) -> ServiceHealth:
        """Check Jira projects service health"""
        return ServiceHealth(
            name="Jira Projects",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Projects service health check not implemented"
        )
    
    async def _check_linear_auth_health(self, user_id: str) -> ServiceHealth:
        """Check Linear authentication health"""
        try:
            from db_oauth_linear import get_user_linear_tokens
            from main_api_app import get_db_pool
            
            db_pool = await get_db_pool()
            tokens = await get_user_linear_tokens(db_pool, user_id)
            
            if tokens and tokens.get("access_token"):
                return ServiceHealth(
                    name="Linear Auth",
                    status="healthy",
                    connected=True,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    metadata={"has_refresh_token": bool(tokens.get("refresh_token"))}
                )
            else:
                return ServiceHealth(
                    name="Linear Auth",
                    status="unhealthy",
                    connected=False,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error="No valid tokens found"
                )
        except Exception as e:
            return ServiceHealth(
                name="Linear Auth",
                status="unhealthy",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error=str(e)
            )
    
    async def _check_linear_issues_health(self) -> ServiceHealth:
        """Check Linear issues service health"""
        return ServiceHealth(
            name="Linear Issues",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Issues service health check not implemented"
        )
    
    async def _check_linear_teams_health(self) -> ServiceHealth:
        """Check Linear teams service health"""
        return ServiceHealth(
            name="Linear Teams",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Teams service health check not implemented"
        )
    
    async def _check_salesforce_auth_health(self, user_id: str) -> ServiceHealth:
        """Check Salesforce authentication health"""
        try:
            from db_oauth_salesforce import get_user_salesforce_tokens
            from main_api_app import get_db_pool
            
            db_pool = await get_db_pool()
            tokens = await get_user_salesforce_tokens(db_pool, user_id)
            
            if tokens and tokens.get("access_token"):
                return ServiceHealth(
                    name="Salesforce Auth",
                    status="healthy",
                    connected=True,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    metadata={"has_refresh_token": bool(tokens.get("refresh_token"))}
                )
            else:
                return ServiceHealth(
                    name="Salesforce Auth",
                    status="unhealthy",
                    connected=False,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error="No valid tokens found"
                )
        except Exception as e:
            return ServiceHealth(
                name="Salesforce Auth",
                status="unhealthy",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error=str(e)
            )
    
    async def _check_salesforce_sobjects_health(self) -> ServiceHealth:
        """Check Salesforce SObjects service health"""
        return ServiceHealth(
            name="Salesforce SObjects",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="SObjects service health check not implemented"
        )
    
    async def _check_salesforce_soql_health(self) -> ServiceHealth:
        """Check Salesforce SOQL service health"""
        return ServiceHealth(
            name="Salesforce SOQL",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="SOQL service health check not implemented"
        )
    
    async def _check_xero_auth_health(self, user_id: str) -> ServiceHealth:
        """Check Xero authentication health"""
        try:
            from db_oauth_xero import get_user_xero_tokens
            from main_api_app import get_db_pool
            
            db_pool = await get_db_pool()
            tokens = await get_user_xero_tokens(db_pool, user_id)
            
            if tokens and tokens.get("access_token"):
                return ServiceHealth(
                    name="Xero Auth",
                    status="healthy",
                    connected=True,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    metadata={"has_refresh_token": bool(tokens.get("refresh_token"))}
                )
            else:
                return ServiceHealth(
                    name="Xero Auth",
                    status="unhealthy",
                    connected=False,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    error="No valid tokens found"
                )
        except Exception as e:
            return ServiceHealth(
                name="Xero Auth",
                status="unhealthy",
                connected=False,
                last_check=datetime.now(timezone.utc).isoformat(),
                error=str(e)
            )
    
    async def _check_xero_accounting_health(self) -> ServiceHealth:
        """Check Xero accounting API health"""
        return ServiceHealth(
            name="Xero Accounting",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Accounting API health check not implemented"
        )
    
    async def _check_xero_payroll_health(self) -> ServiceHealth:
        """Check Xero payroll service health"""
        return ServiceHealth(
            name="Xero Payroll",
            status="degraded",
            connected=False,
            last_check=datetime.now(timezone.utc).isoformat(),
            error="Payroll service health check not implemented"
        )
    
    async def check_all_integrations_health(self, user_id: str = None) -> Dict[str, IntegrationHealthReport]:
        """Check health of all integrations"""
        integrations = ["hubspot", "slack", "jira", "linear", "salesforce", "xero"]
        results = {}
        
        for integration in integrations:
            try:
                if integration == "hubspot":
                    results[integration] = await self.check_hubspot_health(user_id)
                elif integration == "slack":
                    results[integration] = await self.check_slack_health(user_id)
                elif integration == "jira":
                    results[integration] = await self.check_jira_health(user_id)
                elif integration == "linear":
                    results[integration] = await self.check_linear_health(user_id)
                elif integration == "salesforce":
                    results[integration] = await self.check_salesforce_health(user_id)
                elif integration == "xero":
                    results[integration] = await self.check_xero_health(user_id)
            except Exception as e:
                logger.error(f"Failed to check {integration} health: {e}")
                results[integration] = IntegrationHealthReport(
                    integration_name=integration.capitalize(),
                    overall_status="unhealthy",
                    services=[],
                    connected_count=0,
                    total_services=0,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    backend_connected=False
                )
        
        return results

# Global health monitor instance
health_monitor = IntegrationHealthMonitor()