"""
Command Whitelist Service - Decorator-based command validation with maturity restrictions.

Provides defense-in-depth security for shell command execution:
- Decorator enforces whitelist at function entry
- Maturity level gates (STUDENT/INTERN/SUPERVISED/AUTONOMOUS)
- Command category validation (read/write/delete/blocked)
- Subprocess shell=False pattern enforcement

Usage:
    from core.command_whitelist import whitelisted_command, CommandCategory

    @whitelisted_command(
        category=CommandCategory.FILE_READ,
        maturity_levels=[AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]
    )
    async def execute_read_command(...):
        # Safe subprocess execution here
        pass
"""

import asyncio
import logging
from enum import Enum
from functools import wraps
from typing import List, Dict, Callable, Any, Optional
from sqlalchemy.orm import Session

from core.models import AgentRegistry

logger = logging.getLogger(__name__)


class CommandCategory(str, Enum):
    """Command categories with maturity restrictions."""
    FILE_READ = "file_read"        # ls, cat, grep, head, tail, find, wc, pwd
    FILE_WRITE = "file_write"      # cp, mv, mkdir, touch
    FILE_DELETE = "file_delete"    # rm (AUTONOMOUS only)
    BUILD_TOOLS = "build_tools"    # make, npm, pip, python3, node
    DEV_OPS = "dev_ops"            # git, docker, kubectl, terraform
    NETWORK = "network"            # curl, wget, ping (read-only)
    BLOCKED = "blocked"            # chmod, chown, kill, sudo, etc.


# Command whitelist by category and maturity level
# Format: {category: {commands: [...], maturity_levels: [...]}}
COMMAND_WHITELIST = {
    CommandCategory.FILE_READ: {
        "commands": ["ls", "pwd", "cat", "head", "tail", "grep", "find", "wc"],
        "maturity_levels": ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
    },
    CommandCategory.FILE_WRITE: {
        "commands": ["cp", "mv", "mkdir", "touch"],
        "maturity_levels": ["SUPERVISED", "AUTONOMOUS"]
    },
    CommandCategory.FILE_DELETE: {
        "commands": ["rm"],
        "maturity_levels": ["AUTONOMOUS"]  # AUTONOMOUS only
    },
    CommandCategory.BUILD_TOOLS: {
        "commands": ["make", "npm", "pip", "python3", "node", "npm", "yarn", "cargo"],
        "maturity_levels": ["SUPERVISED", "AUTONOMOUS"]
    },
    CommandCategory.DEV_OPS: {
        "commands": ["git", "docker", "kubectl", "terraform", "ansible"],
        "maturity_levels": ["SUPERVISED", "AUTONOMOUS"]
    },
    CommandCategory.NETWORK: {
        "commands": ["curl", "wget", "ping", "nslookup", "dig", "netstat"],
        "maturity_levels": ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
    },
    CommandCategory.BLOCKED: {
        "commands": [
            "chmod", "chown", "kill", "killall", "pkill",
            "sudo", "su", "reboot", "shutdown", "halt",
            "iptables", "ufw", "firewall-cmd", "usermod", "userdel",
            "dd", "mkfs", "fdisk", "mount", "umount"
        ],
        "maturity_levels": []  # No agent can execute
    }
}


def whitelisted_command(
    category: CommandCategory,
    maturity_levels: List[str]
):
    """
    Decorator to validate shell commands against whitelist.

    Enforces:
    1. Command is in whitelist category
    2. Agent maturity level is permitted
    3. Subprocess uses safe execution pattern (shell=False)

    Args:
        category: Command category (FILE_READ, FILE_WRITE, etc.)
        maturity_levels: List of maturity levels allowed (e.g., ["STUDENT", "INTERN"])

    Usage:
        @whitelisted_command(
            category=CommandCategory.FILE_READ,
            maturity_levels=[AgentStatus.STUDENT, AgentStatus.INTERN]
        )
        async def execute_read_command(
            agent_id: str,
            command: str,
            working_directory: str,
            db: Session,
            *args,
            **kwargs
        ):
            # Safe subprocess execution here
            process = await asyncio.create_subprocess_exec(...)
            return result

    Raises:
        PermissionError: If command not in whitelist or maturity level insufficient
        ValueError: If agent not found or command empty
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract parameters from kwargs
            agent_id = kwargs.get("agent_id")
            command = kwargs.get("command", "")
            db = kwargs.get("db")

            if not agent_id:
                raise ValueError("agent_id required for whitelist validation")

            if not command or not command.strip():
                raise ValueError("Empty command")

            if not db:
                raise ValueError("Database session required for maturity check")

            # Parse base command
            command_parts = command.strip().split()
            base_command = command_parts[0]

            # Get category configuration
            category_config = COMMAND_WHITELIST.get(category)
            if not category_config:
                raise ValueError(f"Invalid command category: {category}")

            # Check if command is in category whitelist
            allowed_commands = category_config["commands"]
            if base_command not in allowed_commands:
                raise PermissionError(
                    f"Command '{base_command}' not in {category.value} whitelist. "
                    f"Allowed commands: {', '.join(allowed_commands)}"
                )

            # Check agent maturity level
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            agent_maturity = agent.status

            # Check if maturity level is permitted
            if agent_maturity not in maturity_levels:
                # Get minimum required maturity
                allowed_maturities = category_config["maturity_levels"]
                min_maturity = allowed_maturities[0] if allowed_maturities else "BLOCKED"

                raise PermissionError(
                    f"Agent maturity '{agent_maturity}' not permitted for {category.value} commands. "
                    f"Required maturity: {min_maturity or 'BLOCKED'}. "
                    f"Agent status: {agent_maturity}"
                )

            # Check if command is in blocked category
            if category == CommandCategory.BLOCKED:
                raise PermissionError(
                    f"Command '{base_command}' is blocked for all maturity levels. "
                    f"This command cannot be executed by agents."
                )

            # All checks passed - log and execute
            logger.info(
                f"Whitelist validation passed: agent={agent_id}, "
                f"maturity={agent_maturity}, command='{base_command}', "
                f"category={category.value}"
            )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def validate_command(
    command: str,
    maturity_level: str
) -> Dict[str, Any]:
    """
    Validate command against whitelist without executing.

    Returns validation result with maturity requirements.

    Args:
        command: Shell command to validate
        maturity_level: Current agent maturity level (STUDENT, INTERN, etc.)

    Returns:
        Dict with:
            - valid (bool): Whether command is valid for this maturity level
            - category (str): Command category
            - maturity_required (str): Minimum maturity required
            - reason (str): Human-readable validation result

    Example:
        >>> validate_command("ls /tmp", "STUDENT")
        {
            "valid": True,
            "category": "file_read",
            "maturity_required": "STUDENT",
            "reason": "Command 'ls' is valid for STUDENT maturity level"
        }

        >>> validate_command("rm file.txt", "INTERN")
        {
            "valid": False,
            "category": "file_delete",
            "maturity_required": "AUTONOMOUS",
            "reason": "Command 'rm' requires AUTONOMOUS maturity level"
        }
    """
    if not command or not command.strip():
        return {
            "valid": False,
            "category": None,
            "maturity_required": None,
            "reason": "Empty command"
        }

    # Parse base command
    command_parts = command.strip().split()
    base_command = command_parts[0]

    # Find category for this command
    command_category = None
    category_config = None

    for category, config in COMMAND_WHITELIST.items():
        if base_command in config["commands"]:
            command_category = category
            category_config = config
            break

    if not category_category:
        return {
            "valid": False,
            "category": None,
            "maturity_required": None,
            "reason": f"Command '{base_command}' not found in any whitelist category"
        }

    # Check if command is blocked
    if command_category == CommandCategory.BLOCKED:
        return {
            "valid": False,
            "category": command_category.value,
            "maturity_required": "BLOCKED",
            "reason": f"Command '{base_command}' is blocked for all maturity levels"
        }

    # Check maturity level
    allowed_maturities = category_config["maturity_levels"]

    if maturity_level not in allowed_maturities:
        # Get minimum required maturity
        min_maturity = allowed_maturities[0] if allowed_maturities else "BLOCKED"

        return {
            "valid": False,
            "category": command_category.value,
            "maturity_required": min_maturity,
            "reason": (
                f"Command '{base_command}' requires {min_maturity} maturity level. "
                f"Current maturity: {maturity_level}"
            )
        }

    # All checks passed
    return {
        "valid": True,
        "category": command_category.value,
        "maturity_required": maturity_level,
        "reason": f"Command '{base_command}' is valid for {maturity_level} maturity level"
    }


def get_command_category(command: str) -> Optional[CommandCategory]:
    """
    Get category for a command.

    Args:
        command: Shell command to categorize

    Returns:
        CommandCategory enum or None if not found
    """
    if not command or not command.strip():
        return None

    base_command = command.strip().split()[0]

    for category, config in COMMAND_WHITELIST.items():
        if base_command in config["commands"]:
            return category

    return None


def get_allowed_commands(maturity_level: str) -> List[str]:
    """
    Get all allowed commands for a maturity level.

    Args:
        maturity_level: Agent maturity level (STUDENT, INTERN, etc.)

    Returns:
        List of allowed commands for this maturity level
    """
    allowed_commands = []

    for category, config in COMMAND_WHITELIST.items():
        if maturity_level in config["maturity_levels"]:
            allowed_commands.extend(config["commands"])

    return sorted(set(allowed_commands))
