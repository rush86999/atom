"""
Integration Registry Service
Maps connector_id to integration service classes with dynamic loading

Simplified single-tenant version for open-source distribution.
Removes all SaaS-specific patterns (tenant_id, billing, quota, multi-tenancy).
"""
import time
import asyncio
import importlib
from typing import Dict, Any, Optional, Type, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from core.structured_logger import get_logger

logger = get_logger(__name__)


# Default connector_id to service_class_path mapping
# Static registry for single-tenant open-source deployment
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

    Single-tenant open-source version. Simplified from SaaS version:
    - No tenant_id filtering (single-tenant deployment)
    - No database-driven service mapping (static DEFAULT_SERVICE_REGISTRY only)
    - No per-tenant caching (global service class cache)
    - No SaaS-specific model dependencies
    - No billing/quota checks
    - No multi-tenancy patterns

    Features:
    - Dynamic service loading using importlib with timeout protection
    - Global service class caching for performance
    - Static service registry via DEFAULT_SERVICE_REGISTRY
    - Graceful degradation for unknown connectors
    """

    def __init__(self, use_cache: bool = True):
        """
        Initialize IntegrationRegistry.

        Args:
            use_cache: Enable in-memory class caching (default True)
        """
        self.use_cache = use_cache
        self._service_cache: Dict[str, Type] = {}

    def get_service_class(
        self,
        connector_id: str
    ) -> Optional[Type]:
        """
        Get service class for connector_id.

        Loads service class dynamically using importlib with timeout protection.
        Caches loaded classes in memory to avoid repeated imports.

        Args:
            connector_id: Integration identifier (e.g., "slack", "salesforce")

        Returns:
            Service class or None if not found
        """
        # Check in-memory cache first
        cache_key = f"service_class:{connector_id}"
        if self.use_cache and cache_key in self._service_cache:
            return self._service_cache[cache_key]

        # Get service_class_path from static registry
        service_class_path = self._get_service_class_path(connector_id)
        if not service_class_path:
            logger.warning(f"No service class path found for {connector_id}")
            return None

        # Load service class dynamically with timeout
        service_class = self._load_service_class_with_timeout(
            service_class_path,
            timeout=5
        )

        if service_class:
            # Cache in memory
            if self.use_cache:
                self._service_cache[cache_key] = service_class
            logger.info(f"Loaded service class for {connector_id}: {service_class_path}")

        return service_class

    def _get_service_class_path(
        self,
        connector_id: str
    ) -> Optional[str]:
        """
        Get service_class_path from static registry.

        Args:
            connector_id: Integration identifier

        Returns:
            Service class path string or None
        """
        # Static registry only (no database in single-tenant upstream)
        return DEFAULT_SERVICE_REGISTRY.get(connector_id)

    def _load_service_class_with_timeout(
        self,
        service_class_path: str,
        timeout: int = 5
    ) -> Optional[Type]:
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

    # =========================================================================
    # Integration Catalog Methods
    # =========================================================================

    def get_all_integrations(self) -> List[Dict[str, Any]]:
        """Get all available integrations from the static registry.

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
        """Get a single integration by ID from the static registry.

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

    def list_available_connectors(self) -> Dict[str, str]:
        """
        List all available connector_id mappings.

        Returns:
            Dict mapping connector_id to service_class_path
        """
        return DEFAULT_SERVICE_REGISTRY.copy()


# Global registry instance for convenient access
integration_registry = IntegrationRegistry()
