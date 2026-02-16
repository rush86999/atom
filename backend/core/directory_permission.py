"""
Directory Permission Service - Maturity-based directory access control.

Enforces "earned trust" model where agents gain directory access as they mature:
- STUDENT: Can only suggest commands in safe directories (/tmp, ~/Downloads)
- INTERN: Can access ~/Documents but requires approval
- SUPERVISED: Can access ~/Desktop but requires approval
- AUTONOMOUS: Auto-execute in /tmp, ~/Downloads, ~/Documents

Uses GovernanceCache for sub-millisecond lookups.
Uses pathlib for cross-platform path resolution.
"""

import logging
from pathlib import Path
from typing import Dict, Any

from core.governance_cache import get_governance_cache
from core.models import AgentStatus

logger = logging.getLogger(__name__)


# Directory permissions by maturity level (from FEATURE_ROADMAP.md)
DIRECTORY_PERMISSIONS = {
    AgentStatus.STUDENT: {
        "allowed": ["/tmp", "~/Downloads"],
        "suggest_only": True  # Can suggest, not execute
    },
    AgentStatus.INTERN: {
        "allowed": ["/tmp", "~/Downloads", "~/Documents"],
        "suggest_only": True  # Requires approval
    },
    AgentStatus.SUPERVISED: {
        "allowed": ["~/Documents", "~/Desktop"],
        "suggest_only": True  # Requires approval
    },
    AgentStatus.AUTONOMOUS: {
        "allowed": ["/tmp", "~/Downloads", "~/Documents"],
        "suggest_only": False  # Auto-execute
    }
}

# Blocked directories for all agents (critical system paths)
BLOCKED_DIRECTORIES = [
    "/etc",
    "/root",
    "/sys",
    "/System",
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)"
]


class DirectoryPermissionService:
    """
    Service for checking directory access permissions based on agent maturity.

    Uses GovernanceCache for <1ms cached lookups.
    Uses pathlib.Path for cross-platform path resolution.
    """

    def __init__(self):
        """Initialize directory permission service."""
        self.cache = get_governance_cache()
        self.logger = logger

    def check_directory_permission(
        self,
        agent_id: str,
        directory: str,
        maturity_level: AgentStatus
    ) -> Dict[str, Any]:
        """
        Check if agent can access directory based on maturity level.

        Args:
            agent_id: Agent requesting access
            directory: Directory path to check
            maturity_level: Agent maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)

        Returns:
            Dict with:
                {
                    "allowed": bool,
                    "suggest_only": bool,
                    "reason": str,
                    "maturity_level": str,
                    "resolved_path": str
                }

        Example:
            >>> service = DirectoryPermissionService()
            >>> result = service.check_directory_permission(
            ...     agent_id="agent-123",
            ...     directory="/tmp/work",
            ...     maturity_level=AgentStatus.STUDENT
            ... )
            >>> print(result["allowed"], result["suggest_only"])
            True, True
        """
        # Check cache first (sub-millisecond lookup)
        cache_key = f"{agent_id}:dir:{directory}"
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            self.logger.debug(f"Cache HIT for directory permission: {cache_key}")
            return cached_result

        self.logger.debug(f"Cache MISS for directory permission: {cache_key}")

        # Resolve path (handle ~, .., symlinks)
        resolved_path = self._expand_path(directory)

        # Check blocked directories first (security check)
        if self._is_blocked(resolved_path):
            result = {
                "allowed": False,
                "suggest_only": False,
                "reason": f"Directory '{directory}' is in blocked list (system-critical)",
                "maturity_level": maturity_level.value,
                "resolved_path": str(resolved_path)
            }
            self._cache_result(cache_key, result)
            return result

        # Check maturity-based permissions
        permissions = DIRECTORY_PERMISSIONS.get(
            maturity_level,
            {"allowed": [], "suggest_only": True}
        )

        # Expand allowed directories (handle ~)
        allowed_dirs = [self._expand_path(d) for d in permissions["allowed"]]

        # Check if directory is within allowed paths
        is_allowed = self._is_within_allowed(resolved_path, allowed_dirs)

        result = {
            "allowed": is_allowed,
            "suggest_only": permissions["suggest_only"],
            "reason": self._get_reason(maturity_level, permissions["suggest_only"]),
            "maturity_level": maturity_level.value,
            "resolved_path": str(resolved_path)
        }

        # Cache result for 60 seconds
        self._cache_result(cache_key, result)

        return result

    def _expand_path(self, directory: str) -> Path:
        """
        Resolve directory path (cross-platform).

        Handles:
        - ~ expansion to home directory
        - Path canonicalization (.., symlinks)
        - Cross-platform separators

        Args:
            directory: Directory path string

        Returns:
            Resolved Path object
        """
        try:
            # Expand ~ to home directory
            expanded = Path(directory).expanduser()

            # Resolve to absolute path (handles .., symlinks)
            resolved = expanded.resolve()

            return resolved
        except Exception as e:
            self.logger.error(f"Error resolving path '{directory}': {e}")
            # Return original as Path object on error
            return Path(directory)

    def _is_blocked(self, directory: Path) -> bool:
        """
        Check if directory is in blocked list.

        Args:
            directory: Resolved Path object

        Returns:
            True if directory is blocked
        """
        directory_str = str(directory)

        for blocked in BLOCKED_DIRECTORIES:
            # Check if directory starts with blocked path
            if directory_str.startswith(blocked):
                self.logger.warning(f"Blocked directory access attempt: {directory_str}")
                return True

        return False

    def _is_within_allowed(self, directory: Path, allowed_dirs: list) -> bool:
        """
        Check if directory is within allowed paths.

        Args:
            directory: Resolved Path object to check
            allowed_dirs: List of resolved allowed Path objects

        Returns:
            True if directory is within allowed paths
        """
        directory_str = str(directory)

        for allowed_dir in allowed_dirs:
            allowed_str = str(allowed_dir)

            # Check if directory is within allowed path
            # Use startswith for prefix matching (cross-platform compatible)
            if directory_str.startswith(allowed_str):
                return True

        return False

    def _get_reason(self, maturity_level: AgentStatus, suggest_only: bool) -> str:
        """
        Get human-readable reason for permission decision.

        Args:
            maturity_level: Agent maturity level
            suggest_only: Whether access is suggest-only

        Returns:
            Reason string
        """
        if suggest_only:
            return f"{maturity_level.value} agents can suggest commands in this directory (requires approval)"
        else:
            return f"{maturity_level.value} agents can auto-execute in this directory"

    def _get_from_cache(self, cache_key: str) -> Dict[str, Any]:
        """
        Get directory permission from cache.

        Uses generic cache.get() with special "dir:" action type.

        Args:
            cache_key: Cache key (format: "{agent_id}:dir:{directory}")

        Returns:
            Cached permission dict or None
        """
        # Parse cache key to extract agent_id and action_type
        # Format: "{agent_id}:dir:{directory}" -> agent_id, action_type="dir:{directory}"
        parts = cache_key.split(":", 2)
        if len(parts) >= 2:
            agent_id = parts[0]
            action_type = f"dir:{parts[2] if len(parts) > 2 else ''}"

            cached = self.cache.get(agent_id, action_type)
            return cached

        return None

    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """
        Cache directory permission result.

        Args:
            cache_key: Cache key (format: "{agent_id}:dir:{directory}")
            result: Permission result dict to cache
        """
        parts = cache_key.split(":", 2)
        if len(parts) >= 2:
            agent_id = parts[0]
            action_type = f"dir:{parts[2] if len(parts) > 2 else ''}"

            self.cache.set(agent_id, action_type, result)


# Global service instance
_directory_permission_service: DirectoryPermissionService = None


def get_directory_permission_service() -> DirectoryPermissionService:
    """Get global directory permission service instance."""
    global _directory_permission_service
    if _directory_permission_service is None:
        _directory_permission_service = DirectoryPermissionService()
        logger.info("Initialized directory permission service")
    return _directory_permission_service


# Convenience function for direct usage
def check_directory_permission(
    agent_id: str,
    directory: str,
    maturity_level: AgentStatus
) -> Dict[str, Any]:
    """
    Check directory permission (convenience function).

    Args:
        agent_id: Agent requesting access
        directory: Directory path to check
        maturity_level: Agent maturity level

    Returns:
        Permission result dict
    """
    service = get_directory_permission_service()
    return service.check_directory_permission(agent_id, directory, maturity_level)
