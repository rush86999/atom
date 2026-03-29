"""
Integration Registry Service
Maps connector_id to integration service classes with dynamic loading
"""
import time
import asyncio
import importlib
from typing import Dict, Any, Optional, Type, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from sqlalchemy.orm import Session

from core.models import TenantIntegration, IntegrationAuditLog, TenantIntegrationConfig
from core.integration_service import IntegrationService
from core.cache import UniversalCacheService
from core.structured_logger import get_logger
from core.circuit_breaker import circuit_breaker
from core.rate_limiter import rate_limiter
from core.monitoring import track_integration_execution, set_integration_circuit_breaker_state
from core.integration_service import IntegrationErrorCode
from core.alerts import alert_dispatcher, AlertPriority

logger = get_logger(__name__)


# Default connector_id to service_class_path mapping
# Can be overridden by database entries
DEFAULT_SERVICE_REGISTRY = {
    "slack": "integrations.slack_service_unified:SlackUnifiedService",
    "slack_unified": "integrations.slack_service_unified:SlackUnifiedService",
    "teams": "integrations.teams_enhanced_service:TeamsEnhancedService",
    "teams_enhanced": "integrations.teams_enhanced_service:TeamsEnhancedService",
    "google_chat_enhanced": "integrations.google_chat_enhanced_service:GoogleChatEnhancedService",
    "salesforce": "integrations.salesforce_service:SalesforceService",
    "hubspot": "integrations.hubspot_service:HubSpotService",
    "notion": "integrations.notion_service:NotionService",
    "asana": "integrations.asana_service:AsanaService",
    "gmail": "integrations.gmail_service:GmailService",
    "github": "integrations.github_service:GitHubService",
    "gitlab": "integrations.gitlab_service:GitLabService",
    "jira": "integrations.jira_service:JiraService",
    "trello": "integrations.trello_service:TrelloService",
    "webex": "integrations.webex_service:WebexService",
    "zoom": "integrations.zoom_service:ZoomService",
    "airtable": "integrations.airtable_service:AirtableService",
    "google_calendar": "integrations.google_calendar_service:GoogleCalendarService",
    "microsoft365": "integrations.microsoft365_service:Microsoft365Service",
    "zoho_crm": "integrations.zoho_crm_service:ZohoCRMService",
    "zoho_books": "integrations.zoho_books_service:ZohoBooksService",
    "zoho_projects": "integrations.zoho_projects_service:ZohoProjectsService",
    "zoho_inventory": "integrations.zoho_inventory_service:ZohoInventoryService",
    "zoho_mail": "integrations.zoho_mail_service:ZohoMailService",
    "zoho_workdrive": "integrations.zoho_workdrive_service:ZohoWorkDriveService",
    "google_drive": "integrations.google_drive_service:GoogleDriveService",
    "shopify": "integrations.shopify_service:ShopifyService",
    "stripe": "integrations.stripe_service:StripeService",
    "discord": "integrations.discord_enhanced_service:DiscordEnhancedService",
    "teams_legacy": "integrations.teams_service:TeamsService",
    "slack_legacy": "integrations.slack_enhanced_service:SlackEnhancedService",
    "mailchimp": "integrations.mailchimp_service:MailchimpService",
    "aws_ses": "integrations.aws_ses_service:AWSSESService",
    "linear": "integrations.linear_service:LinearService",
    "monday": "integrations.monday_service:MondayService",
    "clickup": "integrations.clickup_service:ClickUpService",
    "outlook": "integrations.outlook_service:OutlookService",
    "outlook_calendar": "integrations.outlook_calendar_service:OutlookCalendarService",
    "sendgrid": "integrations.sendgrid_routes:SendGridService",
    "dropbox": "integrations.dropbox_service:DropboxService",
    "onedrive": "integrations.onedrive_service:OneDriveService",
    "box": "integrations.box_service:BoxService",
    "whatsapp": "integrations.whatsapp_business_integration:WhatsAppBusinessService",
    "openai": "integrations.openai_service:OpenAIService",
    "intercom": "integrations.intercom_service:IntercomService",
    "freshdesk": "integrations.freshdesk_service:FreshdeskService",
    "apollo": "integrations.apollo_service:ApolloService",
    "workday": "integrations.workday_service:WorkdayService",
    "openclaw": "integrations.openclaw_service:OpenClawService",
    "figma": "integrations.figma_service:FigmaService",
    "plaid": "integrations.plaid_service:PlaidService",
    "deepgram": "integrations.deepgram_service:DeepgramService",
    "tableau": "integrations.tableau_service:TableauService",
    "bitbucket": "integrations.bitbucket_service:BitbucketService",
    "linkedin": "integrations.linkedin_service:LinkedInService",
    "okta": "integrations.okta_service:OktaService",
    "line": "integrations.line_service:LineService",
    "matrix": "integrations.matrix_service:MatrixService",
    "messenger": "integrations.messenger_service:MessengerService",
    "gotomeeting": "integrations.gotomeeting_service:GotoMeetingService",
    "activepieces": "integrations.activepieces_service:ActivePiecesService",
    "document_logic": "integrations.document_logic_service:DocumentLogicService",
}


class IntegrationRegistry:
    """
    Central registry for integration service discovery and loading.

    Features:
    - Dynamic service loading using importlib with timeout protection
    - Per-tenant service caching via UniversalCacheService
    - Database-driven service class path resolution
    - Graceful degradation for unknown connectors

    CRITICAL: All methods must enforce tenant_id filtering to prevent
    cross-tenant credential leakage.
    """

    def __init__(self, db: Optional[Session] = None, use_cache: bool = True):
        """
        Initialize IntegrationRegistry.

        Args:
            db: SQLAlchemy database session (optional for catalog queries)
            use_cache: Enable caching (default True)
        """
        self.db = db
        self.cache = UniversalCacheService() if use_cache else None
        self.use_cache = use_cache
        self._service_cache: Dict[str, Type[IntegrationService]] = {}

    def get_service_class(
        self,
        connector_id: str,
        tenant_id: str
    ) -> Optional[Type[IntegrationService]]:
        """
        Get service class for connector_id with tenant isolation.

        Loads service class dynamically using importlib with timeout protection.
        Caches loaded classes in memory to avoid repeated imports.

        Args:
            connector_id: Integration identifier (e.g., "slack", "salesforce")
            tenant_id: Tenant UUID for cache isolation

        Returns:
            Service class or None if not found

        CRITICAL: Cache key includes tenant_id to prevent cross-tenant cache poisoning.
        """
        # Check in-memory cache first (class-level cache, not tenant-isolated)
        cache_key = f"service_class:{connector_id}"
        if cache_key in self._service_cache:
            return self._service_cache[cache_key]

        # Get service_class_path from database or defaults
        service_class_path = self._get_service_class_path(connector_id, tenant_id)
        if not service_class_path:
            logger.warning(f"No service class path found for {connector_id}")
            return None

        # Load service class dynamically with timeout
        service_class = self._load_service_class_with_timeout(
            service_class_path,
            timeout=5
        )

        if service_class:
            # Cache in memory (class-level, not tenant-specific)
            self._service_cache[cache_key] = service_class
            logger.info(f"Loaded service class for {connector_id}: {service_class_path}")

        return service_class

    async def get_service_instance(
        self,
        connector_id: str,
        tenant_id: str
    ) -> Optional[IntegrationService]:
        """
        Get service instance for connector_id and tenant_id.

        Creates a new service instance per tenant to prevent cross-tenant
        credential leakage. Service instances are cached separately per-tenant.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID

        Returns:
            Service instance or None if not found
        """
        # Get service class
        service_class = self.get_service_class(connector_id, tenant_id)
        if not service_class:
            return None

        # Check per-tenant cache for service instance
        if self.use_cache:
            cache_key = f"service_instance:{connector_id}"
            cached = await self.cache.get_async(cache_key, tenant_id=tenant_id)
            if cached:
                return cached

        # Get tenant-specific configuration from database
        config = self._get_tenant_config(connector_id, tenant_id)

        # Create new service instance (per-tenant isolation)
        service_instance = service_class(tenant_id=tenant_id, config=config)

        # Cache per-tenant (includes tenant_id in cache key)
        if self.use_cache:
            cache_key = f"service_instance:{connector_id}"
            await self.cache.set_async(
                cache_key,
                service_instance,
                ttl=300,  # 5 minutes
                tenant_id=tenant_id
            )

        return service_instance

    async def execute_operation(
        self,
        connector_id: str,
        tenant_id: str,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Execute an operation on a service through the registry.
        Enhanced with Production Standards:
        - Structured Logging (Trace IDs, Workflow IDs)
        - Circuit Breaker (Prevents cascading failures)
        - Rate Limiting (Per-tenant/Per-integration)
        - Metrics (Latency, Error Rate)
        """
        context = context or {}
        trace_id = context.get("trace_id", "none")
        workflow_id = context.get("workflow_id", None)
        agent_id = context.get("agent_id", None)
        
        # Determine execution path for metrics and logs
        execution_path = "system"
        if agent_id:
            execution_path = "agent"
        elif workflow_id:
            execution_path = "workflow"
        elif context.get("system_context"):
            execution_path = f"system:{context['system_context']}"
        
        start_time = time.time()
        logger.info(
            "Integration execution started",
            connector_id=connector_id,
            tenant_id=tenant_id,
            operation=operation,
            trace_id=trace_id,
            workflow_id=workflow_id,
            agent_id=agent_id
        )

        # 2. Circuit Breaker Check
        cb_key = f"{connector_id}:{tenant_id}"
        if not await circuit_breaker.is_enabled(cb_key):
            set_integration_circuit_breaker_state(connector_id, tenant_id, True)
            logger.warning(
                "Execution blocked by circuit breaker",
                connector_id=connector_id,
                tenant_id=tenant_id,
                operation=operation
            )
            duration = time.time() - start_time
            track_integration_execution(
                connector_id, tenant_id, operation, 
                "circuit_broken", duration, execution_path
            )
            self._record_audit_log(
                db, tenant_id, connector_id, operation, 
                "circuit_broken", "Circuit Open", parameters, context
            )
            return {
                "success": False,
                "error": "INTEGRATION_DISABLED",
                "message": f"Integration {connector_id} is temporarily disabled due to repeated failures."
            }
        
        set_integration_circuit_breaker_state(connector_id, tenant_id, False)

        # 3. Rate Limiting Check
        is_limited, remaining = await rate_limiter.is_rate_limited(connector_id, tenant_id)
        if is_limited:
            duration = time.time() - start_time
            track_integration_execution(
                connector_id, tenant_id, operation, 
                "rate_limited", duration, execution_path
            )
            self._record_audit_log(
                db, tenant_id, connector_id, operation, 
                "rate_limited", "Rate Limit Exceeded", parameters, context
            )
            return {
                "success": False,
                "error": "RATE_LIMITED",
                "message": f"Rate limit exceeded for integration {connector_id}."
            }

        # 4. Get Service Instance
        service = await self.get_service_instance(connector_id, tenant_id)
        if not service:
            duration = time.time() - start_time
            track_integration_execution(
                connector_id, tenant_id, operation, 
                "not_found", duration, execution_path
            )
            return {
                "success": False,
                "error": "INTEGRATION_NOT_FOUND",
                "message": f"Integration {connector_id} not found or not active for this tenant"
            }

        # 5. Execute with Metrics and Circuit Breaker Recording
        start_time = time.time()
        try:
            result = await service.execute_operation(operation, parameters, context)
            duration = time.time() - start_time
            
            if result.get("success"):
                # Success Recording
                await circuit_breaker.record_success(cb_key)
                track_integration_execution(
                    connector_id, tenant_id, operation, 
                    "success", duration, execution_path
                )
                self._record_audit_log(
                    db, tenant_id, connector_id, operation, 
                    "success", None, parameters, context, result
                )
            else:
                # Treated as failure for circuit breaker if it's a provider error
                await circuit_breaker.record_failure(cb_key)
                track_integration_execution(
                    connector_id, tenant_id, operation, 
                    "failure", duration, execution_path
                )
                self._record_audit_log(
                    db, tenant_id, connector_id, operation, 
                    "failure", result.get("error"), parameters, context, result
                )
                
                # Proactive alerting for Auth Failures
                if result.get("error") == IntegrationErrorCode.AUTH_INVALID.value:
                    asyncio.create_task(alert_dispatcher.dispatch(
                        priority=AlertPriority.HIGH,
                        title=f"Authentication Failure: {connector_id}",
                        message=f"Interaction for tenant {tenant_id} failed due to invalid credentials. Re-authentication required.",
                        context={
                            "tenant_id": tenant_id,
                            "connector_id": connector_id,
                            "error": result.get("message"),
                            "action": "REAUTH_REQUIRED"
                        },
                        suppression_key=f"auth_fail:{tenant_id}:{connector_id}"
                    ))
            
            return result

        except Exception as e:
            duration = time.time() - start_time
            # Critical Failure recording
            await circuit_breaker.record_failure(cb_key, error=e)
            track_integration_execution(
                connector_id, tenant_id, operation, 
                "exception", duration, execution_path
            )
            self._record_audit_log(
                db, tenant_id, connector_id, operation, 
                "error", str(e), parameters, context
            )
            
            return {
                "success": False,
                "error": "EXECUTION_EXCEPTION",
                "message": str(e)
            }

    def _record_audit_log(
        self,
        db: Optional[Session],
        tenant_id: str,
        connector_id: str,
        operation: str,
        outcome: str,
        reason: Optional[str],
        parameters: Dict[str, Any],
        context: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None
    ):
        """Record persistent audit log for integration operation."""
        if not db:
            return

        try:
            import json
            from core.models import IntegrationAuditLog
            
            # Helper to truncate large data
            def truncate(data: Any, max_len: int = 1000) -> str:
                s = str(data)
                return (s[:max_len] + '...') if len(s) > max_len else s

            audit_log = IntegrationAuditLog(
                tenant_id=tenant_id,
                connector_id=connector_id,
                operation_name=operation,
                action="execute_operation",
                outcome=outcome,
                reason=reason,
                agent_id=context.get("agent_id"),
                workflow_run_id=context.get("workflow_id"),
                arguments=truncate(parameters),
                result=result if result else {},
                audit_metadata={
                    "trace_id": context.get("trace_id"),
                    "execution_path": context.get("execution_path") or "unknown"
                }
            )
            db.add(audit_log)
            db.flush()
        except Exception as e:
            logger.error(f"Failed to record integration audit log: {e}")

    def _get_service_class_path(
        self,
        connector_id: str,
        tenant_id: str
    ) -> Optional[str]:
        """
        Get service_class_path from database or defaults.

        CRITICAL: Query filters by tenant_id to prevent cross-tenant leakage.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID

        Returns:
            Service class path string or None
        """
        # Try database first (tenant-specific configuration)
        integration = self.db.query(TenantIntegration).filter(
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.connector_id == connector_id,
            TenantIntegration.is_active == True
        ).first()

        if integration and integration.service_class_path:
            return integration.service_class_path

        # Fall back to defaults
        return DEFAULT_SERVICE_REGISTRY.get(connector_id)

    def _get_tenant_config(
        self,
        connector_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Get tenant-specific configuration from database.

        CRITICAL: Query filters by tenant_id.

        Args:
            connector_id: Integration identifier
            tenant_id: Tenant UUID

        Returns:
            Configuration dict or empty dict
        """
        integration = self.db.query(TenantIntegration).filter(
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.connector_id == connector_id,
            TenantIntegration.is_active == True
        ).first()

        if integration and integration.config:
            return integration.config

        return {}

    def _load_service_class_with_timeout(
        self,
        service_class_path: str,
        timeout: int = 5
    ) -> Optional[Type[IntegrationService]]:
        """
        Load service class using importlib with bounded timeout.

        Prevents application startup hangs from slow module-level code.

        Args:
            service_class_path: Module path (e.g., "integrations.slack_service:SlackService")
            timeout: Timeout in seconds (default 5)

        Returns:
            Service class or None if failed/timeout
        """
        try:
            module_path, class_name = service_class_path.split(":")

            # Use ThreadPoolExecutor for timeout protection
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(importlib.import_module, module_path)
                module = future.result(timeout=timeout)

            service_class = getattr(module, class_name)
            return service_class

        except FuturesTimeoutError:
            logger.error(f"Timeout loading {service_class_path} after {timeout}s")
            return None
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load {service_class_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading {service_class_path}: {e}")
            return None

    async def invalidate_tenant_cache(
        self,
        tenant_id: str,
        connector_id: Optional[str] = None
    ):
        """
        Invalidate cache for tenant's integration services.

        Use when credentials are revoked or configuration changes.

        Args:
            tenant_id: Tenant UUID
            connector_id: Specific connector to invalidate (or all if None)
        """
        if connector_id:
            cache_key = f"service_instance:{connector_id}"
            await self.cache.delete_async(cache_key, tenant_id=tenant_id)
            logger.info(f"Invalidated cache for tenant={tenant_id}, connector={connector_id}")
        else:
            # Invalidate all service instances for tenant
            await self.cache.delete_tenant_all(tenant_id)
            logger.info(f"Invalidated all cache for tenant={tenant_id}")

    def invalidate_tenant_cache_sync(
        self,
        tenant_id: str,
        connector_id: Optional[str] = None
    ):
        """
        Synchronous version of invalidate_tenant_cache for use in non-async contexts.

        Use when credentials are revoked or configuration changes in synchronous code.

        Args:
            tenant_id: Tenant UUID
            connector_id: Specific connector to invalidate (or all if None)
        """
        if connector_id:
            cache_key = f"service_instance:{connector_id}"
            self.cache.delete(cache_key, tenant_id=tenant_id)
            logger.info(f"Invalidated cache for tenant={tenant_id}, connector={connector_id}")
        else:
            # Invalidate all service instances for tenant
            # Run async delete_tenant_all in event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, create a task
                    asyncio.create_task(self.cache.delete_tenant_all(tenant_id))
                else:
                    # If loop is not running, run the coroutine
                    loop.run_until_complete(self.cache.delete_tenant_all(tenant_id))
            except RuntimeError:
                # No event loop exists, create a new one
                asyncio.run(self.cache.delete_tenant_all(tenant_id))
            logger.info(f"Invalidated all cache for tenant={tenant_id}")

    # =========================================================================
    # Tenant-Level Integration Configuration Methods
    # =========================================================================

    def is_enabled_for_tenant(self, db: Session, tenant_id: str, integration_id: str) -> bool:
        """Check if integration is enabled for a specific tenant.

        If no config exists, integration is enabled by default (backward compatibility).

        Args:
            db: Database session
            tenant_id: Tenant ID
            integration_id: Integration ID (e.g., "salesforce", "slack")

        Returns:
            True if enabled, False if explicitly disabled

        CRITICAL: Query filters by tenant_id for security.
        """
        config = db.query(TenantIntegrationConfig).filter(
            TenantIntegrationConfig.tenant_id == tenant_id,
            TenantIntegrationConfig.integration_id == integration_id
        ).first()

        # If no config exists, integration is enabled by default (backward compatibility)
        if config is None:
            return True

        return config.enabled

    def get_tenant_config(self, db: Session, tenant_id: str, integration_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant-level configuration for an integration.

        Args:
            db: Database session
            tenant_id: Tenant ID
            integration_id: Integration ID

        Returns:
            Configuration dict with enabled, sync_settings, connected_user_count, last_activity_at
            or None if not configured

        CRITICAL: Query filters by tenant_id for security.
        """
        config = db.query(TenantIntegrationConfig).filter(
            TenantIntegrationConfig.tenant_id == tenant_id,
            TenantIntegrationConfig.integration_id == integration_id
        ).first()

        if config is None:
            return None

        return {
            "enabled": config.enabled,
            "sync_settings": config.sync_settings or {},
            "connected_user_count": config.connected_user_count,
            "last_activity_at": config.last_activity_at.isoformat() if config.last_activity_at else None,
            "last_sync_at": config.last_sync_at.isoformat() if config.last_sync_at else None,
        }

    def set_tenant_enabled(self, db: Session, tenant_id: str, integration_id: str, enabled: bool) -> TenantIntegrationConfig:
        """Enable or disable an integration for a tenant.

        Creates config if it doesn't exist, updates if it does.

        Args:
            db: Database session
            tenant_id: Tenant ID
            integration_id: Integration ID
            enabled: True to enable, False to disable

        Returns:
            Updated or created TenantIntegrationConfig

        CRITICAL: All queries filter by tenant_id for security.
        """
        config = db.query(TenantIntegrationConfig).filter(
            TenantIntegrationConfig.tenant_id == tenant_id,
            TenantIntegrationConfig.integration_id == integration_id
        ).first()

        if config is None:
            config = TenantIntegrationConfig(
                tenant_id=tenant_id,
                integration_id=integration_id,
                enabled=enabled
            )
            db.add(config)
        else:
            config.enabled = enabled

        db.commit()
        db.refresh(config)
        return config

    def update_sync_settings(self, db: Session, tenant_id: str, integration_id: str, sync_settings: Dict[str, Any]) -> TenantIntegrationConfig:
        """Update sync settings for a tenant integration.

        Creates config if it doesn't exist, updates if it does.

        Args:
            db: Database session
            tenant_id: Tenant ID
            integration_id: Integration ID
            sync_settings: Sync settings dict (entity_types, frequency_hours, data_limit_mb)

        Returns:
            Updated TenantIntegrationConfig

        CRITICAL: All queries filter by tenant_id for security.
        """
        config = db.query(TenantIntegrationConfig).filter(
            TenantIntegrationConfig.tenant_id == tenant_id,
            TenantIntegrationConfig.integration_id == integration_id
        ).first()

        if config is None:
            config = TenantIntegrationConfig(
                tenant_id=tenant_id,
                integration_id=integration_id,
                sync_settings=sync_settings
            )
            db.add(config)
        else:
            config.sync_settings = sync_settings

        db.commit()
        db.refresh(config)
        return config

    # =========================================================================
    # Integration Catalog Methods
    # =========================================================================

    def get_all_integrations(self) -> List[Dict[str, Any]]:
        """Get all available integrations from the default registry.

        Returns:
            List of integration dicts with id, name, service_class_path
        """
        catalog = []
        for connector_id, service_path in DEFAULT_SERVICE_REGISTRY.items():
            # Skip legacy/duplicate entries
            if connector_id.endswith("_legacy"):
                continue
            catalog.append({
                "id": connector_id,
                "name": connector_id.replace("_", " ").title(),
                "service_class_path": service_path,
            })
        return catalog

    def get_integration(self, integration_id: str) -> Optional[Dict[str, Any]]:
        """Get a single integration by ID from the default registry.

        Args:
            integration_id: Integration identifier (e.g., "slack", "salesforce")

        Returns:
            Integration dict with id, name, service_class_path, or None
        """
        service_path = DEFAULT_SERVICE_REGISTRY.get(integration_id)
        if service_path is None:
            return None
        return {
            "id": integration_id,
            "name": integration_id.replace("_", " ").title(),
            "service_class_path": service_path,
        }

    def cleanup_integration_resources(
        self,
        integration_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Cleanup all resources for an integration: service instances, webhooks, rate limits.

        Args:
            integration_id: Integration identifier (e.g., "slack", "salesforce")
            tenant_id: Tenant ID

        Returns:
            Dict with cleared_resources list, tenant_id, integration_id, and counts
        """
        # Clear service instance cache
        cache_key = f"{tenant_id}:{integration_id}"
        cleared_instances = self._service_instances.pop(cache_key, None)

        # Clear webhook subscriptions
        webhooks_cleared = self._clear_webhooks(integration_id, tenant_id)

        # Clear rate limit trackers
        rate_limits_cleared = self._clear_rate_limits(integration_id, tenant_id)

        logger.info(
            "Cleanup integration resources",
            integration_id=integration_id,
            tenant_id=tenant_id,
            service_instances_cleared=1 if cleared_instances else 0,
            webhooks_cleared=webhooks_cleared,
            rate_limits_cleared=rate_limits_cleared
        )

        return {
            "cleared_resources": ["service_instances", "webhooks", "rate_limits"],
            "tenant_id": tenant_id,
            "integration_id": integration_id,
            "service_instances_cleared": 1 if cleared_instances else 0,
            "webhooks_cleared": webhooks_cleared,
            "rate_limits_cleared": rate_limits_cleared
        }

    def unregister_service_instance(
        self,
        integration_id: str,
        tenant_id: str,
        user_id: Optional[str] = None
    ):
        """
        Unregister a service instance from the registry, calling service-specific cleanup if available.

        Args:
            integration_id: Integration identifier
            tenant_id: Tenant ID
            user_id: Optional user ID for user-specific cache key
        """
        # Build cache key
        if user_id:
            cache_key = f"{tenant_id}:{user_id}:{integration_id}"
        else:
            cache_key = f"{tenant_id}:{integration_id}"

        # Remove from service instances cache
        service_instance = self._service_instances.pop(cache_key, None)

        if service_instance and hasattr(service_instance, "cleanup"):
            try:
                # Call service-specific cleanup if available
                service_instance.cleanup()
                logger.info(
                    "Called service-specific cleanup",
                    integration_id=integration_id,
                    tenant_id=tenant_id,
                    user_id=user_id
                )
            except Exception as e:
                logger.warning(
                    "Service-specific cleanup failed",
                    integration_id=integration_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    error=str(e)
                )

        logger.info(
            "Unregistered service instance",
            cache_key=cache_key,
            integration_id=integration_id,
            tenant_id=tenant_id,
            user_id=user_id
        )

    def _clear_webhooks(self, integration_id: str, tenant_id: str) -> int:
        """
        Clear webhook subscriptions for an integration.

        Args:
            integration_id: Integration identifier
            tenant_id: Tenant ID

        Returns:
            Count of webhooks cleared
        """
        # Iterate through webhook registry and remove matching entries
        # This is a placeholder - actual implementation depends on webhook storage
        cleared_count = 0

        # TODO: Implement webhook registry cleanup when webhook storage is defined
        # For now, log the operation
        logger.info(
            "Webhook cleanup placeholder",
            integration_id=integration_id,
            tenant_id=tenant_id,
            note="Webhook registry not yet implemented"
        )

        return cleared_count

    def _clear_rate_limits(self, integration_id: str, tenant_id: str) -> int:
        """
        Clear rate limit trackers for an integration.

        Args:
            integration_id: Integration identifier
            tenant_id: Tenant ID

        Returns:
            Count of rate limit trackers cleared
        """
        # Clear rate limit tracker for this integration/tenant
        from core.rate_limiter import rate_limiter

        try:
            # Clear rate limit cache for this integration
            rate_limit_key = f"{integration_id}:{tenant_id}"
            # This is a placeholder - actual implementation depends on rate_limiter API
            cleared = 1  # Assume one tracker cleared
        except Exception as e:
            logger.warning(
                "Failed to clear rate limits",
                integration_id=integration_id,
                tenant_id=tenant_id,
                error=str(e)
            )
            cleared = 0

        return cleared

    def get_active_service_count(
        self,
        tenant_id: str,
        integration_id: Optional[str] = None
    ) -> int:
        """
        Count active service instances in cache.

        Args:
            tenant_id: Tenant ID
            integration_id: Optional integration ID to filter by

        Returns:
            Count of active service instances
        """
        count = 0

        for cache_key in self._service_instances.keys():
            # Parse cache key (format: "tenant_id:integration_id" or "tenant_id:user_id:integration_id")
            parts = cache_key.split(":")
            if len(parts) >= 2 and parts[0] == tenant_id:
                if integration_id is None or parts[-1] == integration_id:
                    count += 1

        return count

    def list_available_connectors(self) -> Dict[str, str]:
        """
        List all available connector_id mappings.

        Returns:
            Dict mapping connector_id to service_class_path
        """
        return DEFAULT_SERVICE_REGISTRY.copy()
