"""
Obsidian Service for ATUM SaaS Platform
Provides interaction with Obsidian Local REST API

Ported from upstream: rush86999/atom@c853e138f
Changes: Added tenant_id context for multi-tenancy, inherits from IntegrationService
"""

import logging
import requests
from typing import Any, Dict, List, Optional
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)


class ObsidianService(IntegrationService):
    """
    Obsidian Local REST API integration service for multi-tenant SaaS.

    Provides interaction with Obsidian vaults through the Local REST API plugin.
    All operations are tenant-isolated through tenant_id context.
    """

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        """
        Initialize Obsidian service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with:
                - api_token: Obsidian API token (optional)
                - plugin_url: Obsidian plugin URL (default: http://localhost:27123)
        """
        super().__init__(tenant_id=tenant_id, config=config)

        self.api_token = config.get("api_token")
        self.plugin_url = config.get("plugin_url", "http://localhost:27123").rstrip('/')
        self.session = requests.Session()

        if self.api_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'ATUM-SaaS-Platform/1.0'
            })

        logger.info(f"Initialized Obsidian service for tenant {self.tenant_id[:8]}")

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return Obsidian integration capabilities.

        Returns:
            Dict with operations, parameters, rate limits, webhook support
        """
        return {
            "operations": [
                {
                    "id": "test_connection",
                    "name": "Test Connection",
                    "description": "Test connection to Obsidian Local REST API",
                    "category": "connectivity"
                },
                {
                    "id": "list_notes",
                    "name": "List Notes",
                    "description": "List all notes in the vault",
                    "category": "read"
                },
                {
                    "id": "get_note",
                    "name": "Get Note",
                    "description": "Get note content by path",
                    "category": "read",
                    "required_params": ["path"]
                },
                {
                    "id": "create_note",
                    "name": "Create Note",
                    "description": "Create or overwrite a note",
                    "category": "write",
                    "required_params": ["path", "content"]
                },
                {
                    "id": "append_note",
                    "name": "Append Note",
                    "description": "Append content to a note",
                    "category": "write",
                    "required_params": ["path", "content"]
                },
                {
                    "id": "search",
                    "name": "Search Notes",
                    "description": "Search notes by query",
                    "category": "read",
                    "required_params": ["query"]
                }
            ],
            "required_params": ["plugin_url"],
            "optional_params": ["api_token"],
            "rate_limits": {
                "requests_per_minute": 60,  # Local REST API has no strict limit
                "concurrent_requests": 5
            },
            "supports_webhooks": False,
            "auth_type": "api_token"
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Check if Obsidian service is healthy.

        Returns:
            Dict with health status
        """
        result = self.test_connection()
        return {
            "healthy": result.get("status") == "success",
            "message": result.get("message", "Unknown status"),
            "last_check": result.get("timestamp")
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Obsidian operation with tenant context.

        Args:
            operation: Operation name
            parameters: Operation parameters
            context: Tenant context dict (must contain tenant_id)

        Returns:
            Dict with success, result, error, details

        Raises:
            NotImplementedError: If operation not supported
        """
        # Validate tenant context to prevent cross-tenant access
        if context and context.get("tenant_id") != self.tenant_id:
            logger.error(
                f"Tenant ID mismatch in Obsidian operation: "
                f"expected {self.tenant_id[:8]}, got {context.get('tenant_id', 'None')[:8] if context.get('tenant_id') else 'None'}"
            )
            return {
                "success": False,
                "error": "Tenant context validation failed",
                "details": {"operation": operation}
            }

        try:
            if operation == "test_connection":
                result = self.test_connection()
                return {"success": result.get("status") == "success", "result": result}

            elif operation == "list_notes":
                notes = self.list_notes()
                return {"success": True, "result": {"notes": notes}, "details": {"count": len(notes)}}

            elif operation == "get_note":
                path = parameters.get("path")
                if not path:
                    return {"success": False, "error": "Missing required parameter: path"}
                content = self.get_note(path)
                if content is None:
                    return {"success": False, "error": f"Failed to get note: {path}"}
                return {"success": True, "result": {"content": content, "path": path}}

            elif operation == "create_note":
                path = parameters.get("path")
                content = parameters.get("content")
                if not path or content is None:
                    return {"success": False, "error": "Missing required parameters: path, content"}
                success = self.create_note(path, content)
                return {"success": success, "result": {"path": path}}

            elif operation == "append_note":
                path = parameters.get("path")
                content = parameters.get("content")
                if not path or content is None:
                    return {"success": False, "error": "Missing required parameters: path, content"}
                success = self.append_note(path, content)
                return {"success": success, "result": {"path": path}}

            elif operation == "search":
                query = parameters.get("query")
                if not query:
                    return {"success": False, "error": "Missing required parameter: query"}
                results = self.search(query)
                return {"success": True, "result": {"results": results}, "details": {"count": len(results)}}

            else:
                raise NotImplementedError(f"Operation not supported: {operation}")

        except Exception as e:
            logger.error(f"Obsidian operation failed for tenant {self.tenant_id[:8]}: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"operation": operation}
            }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Obsidian Local REST API.

        Returns:
            Dict with connection status
        """
        try:
            response = self.session.get(f"{self.plugin_url}/")
            if response.status_code == 200:
                logger.info(f"Obsidian connection test successful for tenant {self.tenant_id[:8]}")
                return {
                    "status": "success",
                    "message": "Obsidian connection successful",
                    "authenticated": True,
                    "timestamp": self.plugin_url
                }
            else:
                logger.warning(f"Obsidian connection test failed for tenant {self.tenant_id[:8]}: {response.status_code}")
                return {
                    "status": "error",
                    "message": f"Connection failed: {response.status_code}",
                    "authenticated": False
                }
        except Exception as e:
            logger.error(f"Obsidian connection test failed for tenant {self.tenant_id[:8]}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }

    def list_notes(self) -> List[str]:
        """
        List all notes in the vault.

        Returns:
            List of note paths
        """
        try:
            response = self.session.get(f"{self.plugin_url}/active/")
            response.raise_for_status()
            notes = response.json().get('files', [])
            logger.debug(f"Listed {len(notes)} notes for tenant {self.tenant_id[:8]}")
            return notes
        except Exception as e:
            logger.error(f"Failed to list Obsidian notes for tenant {self.tenant_id[:8]}: {e}")
            return []

    def get_note(self, path: str) -> Optional[str]:
        """
        Get note content by path.

        Args:
            path: Note path in vault

        Returns:
            Note content or None if failed
        """
        try:
            response = self.session.get(f"{self.plugin_url}/vault/{path.lstrip('/')}")
            response.raise_for_status()
            content = response.text
            logger.debug(f"Retrieved note {path} for tenant {self.tenant_id[:8]}")
            return content
        except Exception as e:
            logger.error(f"Failed to get Obsidian note {path} for tenant {self.tenant_id[:8]}: {e}")
            return None

    def create_note(self, path: str, content: str) -> bool:
        """
        Create or overwrite a note.

        Args:
            path: Note path in vault
            content: Note content (markdown)

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.put(
                f"{self.plugin_url}/vault/{path.lstrip('/')}",
                data=content,
                headers={'Content-Type': 'text/markdown'}
            )
            response.raise_for_status()
            logger.info(f"Created note {path} for tenant {self.tenant_id[:8]}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Obsidian note {path} for tenant {self.tenant_id[:8]}: {e}")
            return False

    def append_note(self, path: str, content: str) -> bool:
        """
        Append content to a note.

        Args:
            path: Note path in vault
            content: Content to append (markdown)

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.post(
                f"{self.plugin_url}/vault/{path.lstrip('/')}",
                data=content,
                headers={'Content-Type': 'text/markdown'}
            )
            response.raise_for_status()
            logger.info(f"Appended to note {path} for tenant {self.tenant_id[:8]}")
            return True
        except Exception as e:
            logger.error(f"Failed to append to Obsidian note {path} for tenant {self.tenant_id[:8]}: {e}")
            return False

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search notes by query.

        Args:
            query: Search query string

        Returns:
            List of search results
        """
        try:
            response = self.session.post(
                f"{self.plugin_url}/search/",
                json={"query": query}
            )
            response.raise_for_status()
            results = response.json()
            logger.debug(f"Obsidian search '{query}' returned {len(results)} results for tenant {self.tenant_id[:8]}")
            return results
        except Exception as e:
            logger.error(f"Obsidian search failed for tenant {self.tenant_id[:8]}: {e}")
            return []
