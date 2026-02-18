"""
Skill Adapter for OpenClaw community skills.

Wraps parsed SKILL.md files as LangChain BaseTool subclasses
with Pydantic validation for seamless integration with Atom agents.

Reference: Phase 14 Plan 01 - Skill Adapter
Reference: Phase 25 Plan 02 - CLI Skill Integration
"""

import logging
import re
from typing import Any, Dict, Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict

# Import CLI command wrapper for atom-* skills
from tools.atom_cli_skill_wrapper import execute_atom_cli_command

logger = logging.getLogger(__name__)


class CommunitySkillInput(BaseModel):
    """
    Pydantic schema for community skill input validation.

    Uses flexible input pattern with extra='allow' to handle
    varying skill input requirements (per RESEARCH.md pitfall 5).
    """
    query: str = Field(description="User's request or question for the skill")

    model_config = ConfigDict(
        extra='allow'  # Allow additional fields not in schema
    )


class CommunitySkillTool(BaseTool):
    """
    LangChain BaseTool wrapper for imported OpenClaw community skills.

    Supports two skill types:
    - prompt_only: Natural language instructions with template interpolation
    - python_code: Python code requiring sandbox execution (Plan 02)

    Instance attributes:
        name: Tool name (overridden per instance)
        description: Tool description from skill metadata
        args_schema: Pydantic schema for input validation
        skill_id: Unique identifier for this skill
        skill_type: "prompt_only" or "python_code"
        skill_content: Prompt template or Python code
        sandbox_enabled: Whether sandbox is enabled for Python skills
    """

    name: str = "community_skill"
    description: str = "Execute a community skill from ClawHub"
    args_schema: Type[BaseModel] = CommunitySkillInput

    skill_id: str = ""
    skill_type: str = "prompt_only"  # "prompt_only" or "python_code"
    skill_content: str = ""  # Prompt template or Python code
    sandbox_enabled: bool = False

    def _run(self, query: str) -> str:
        """
        Execute the skill synchronously.

        Args:
            query: User's request or question

        Returns:
            Formatted prompt or execution result

        Raises:
            NotImplementedError: For python_code skills without sandbox
        """
        # Check if this is a CLI skill (atom-* prefix)
        if self.skill_id.startswith("atom-"):
            return self._execute_cli_skill(query)

        if self.skill_type == "prompt_only":
            return self._execute_prompt_skill(query)
        elif self.skill_type == "python_code":
            return self._execute_python_skill(query)
        else:
            raise ValueError(f"Unknown skill type: {self.skill_type}")

    def _execute_cli_skill(self, query: str) -> str:
        """
        Execute Atom CLI skill via subprocess wrapper.

        For skills with atom-* prefix, executes CLI commands instead of
        prompt interpolation. Parses query for command arguments.

        Args:
            query: User's request (may contain arguments like "port 3000")

        Returns:
            Formatted result with stdout/stderr

        Examples:
            query="Start daemon on port 3000" -> atom-os daemon --port 3000
            query="Check status" -> atom-os status
        """
        try:
            # Extract command name from skill_id
            # e.g., "atom-daemon" -> "daemon"
            command = self.skill_id.replace("atom-", "")

            # Parse arguments from query (simple space-based splitting)
            # More sophisticated parsing could use LLM in future
            args = self._parse_cli_args(query, command)

            logger.info(f"Executing CLI skill: {command} with args: {args}")

            # Execute command via subprocess wrapper
            result = execute_atom_cli_command(command, args)

            # Format output for LLM
            if result["success"]:
                output = f"Command executed successfully:\n{result['stdout']}"
                if result["stderr"]:
                    output += f"\nWarnings:\n{result['stderr']}"
                return output
            else:
                return f"Command failed:\n{result['stderr']}"

        except Exception as e:
            logger.error(f"CLI skill execution failed for {self.skill_id}: {e}")
            return f"ERROR: Failed to execute CLI skill - {str(e)}"

    def _parse_cli_args(self, query: str, command: str) -> Optional[list]:
        """
        Parse CLI arguments from user query.

        Simple argument extraction for common flags. Could be enhanced
        with LLM-based parsing for complex scenarios.

        Args:
            query: User's query text
            command: CLI command name

        Returns:
            List of command arguments or None

        Examples:
            "port 3000" -> ["--port", "3000"]
            "start with host mount" -> ["--host-mount"]
        """
        args = []
        query_lower = query.lower()

        # Handle --port flag
        # Pattern: "port 3000" or "port=3000" or "--port 3000"
        port_match = re.search(r'port\s*=?\s*(\d+)', query_lower)
        if port_match:
            args.extend(["--port", port_match.group(1)])

        # Handle --host flag
        host_match = re.search(r'host\s+(\S+)', query_lower)
        if host_match:
            args.extend(["--host", host_match.group(1)])

        # Handle --workers flag
        workers_match = re.search(r'workers?\s+(\d+)', query_lower)
        if workers_match:
            args.extend(["--workers", workers_match.group(1)])

        # Handle boolean flags
        if "host mount" in query_lower or "host-mount" in query_lower:
            args.append("--host-mount")

        if "dev" in query_lower or "development" in query_lower:
            args.append("--dev")

        if "foreground" in query_lower:
            args.append("--foreground")

        # Special case: atom-config --show-daemon
        if command == "config" and ("show daemon" in query_lower or "show-daemon" in query_lower):
            args.append("--show-daemon")

        return args if args else None

    async def _arun(self, query: str) -> str:
        """
        Execute the skill asynchronously.

        Args:
            query: User's request or question

        Returns:
            Formatted prompt or execution result
        """
        # Delegate to synchronous implementation
        return self._run(query)

    def _execute_prompt_skill(self, query: str) -> str:
        """
        Execute prompt-only skill (no sandbox needed).

        Simple string interpolation for prompt template.
        Supports {{query}} and {query} placeholders.

        Args:
            query: User's request

        Returns:
            Formatted prompt string
        """
        try:
            # Try double-brace syntax first
            if "{{query}}" in self.skill_content:
                result = self.skill_content.replace("{{query}}", query)
            # Try single-brace syntax
            elif "{query}" in self.skill_content:
                result = self.skill_content.format(query=query)
            # No placeholder - append query
            else:
                result = f"{self.skill_content}\n\nUser Query: {query}"

            return result

        except Exception as e:
            logger.error(f"Prompt formatting failed for skill {self.skill_id}: {e}")
            return f"ERROR: Failed to format prompt - {str(e)}"

    def _execute_python_skill(self, query: str) -> str:
        """
        Execute Python skill in Docker sandbox.

        Args:
            query: User's request

        Returns:
            Execution result or error message

        Raises:
            RuntimeError: If sandbox execution fails
        """
        if self.sandbox_enabled:
            # Import HazardSandbox for isolated execution
            from core.skill_sandbox import HazardSandbox

            try:
                sandbox = HazardSandbox()

                # Extract function entry point from skill content
                # Format: ```python\ndef execute(query: str) -> str:\n...
                code = self._extract_function_code()

                # Execute in sandbox with timeout and resource limits
                result = sandbox.execute_python(
                    code=code,
                    inputs={"query": query},
                    timeout_seconds=300,  # 5 minute timeout
                    memory_limit="256m",
                    cpu_limit=0.5
                )

                return result

            except RuntimeError as e:
                if "Docker daemon is not running" in str(e):
                    return f"SANDBOX_ERROR: Docker is not running. Please start Docker to execute Python skills."
                raise
            except Exception as e:
                return f"EXECUTION_ERROR: {str(e)}"
        else:
            # UNSAFE: Direct execution not allowed
            raise RuntimeError(
                f"Direct Python execution is not allowed for security reasons. "
                f"Skill '{self.skill_id}' requires sandbox execution. "
                f"Enable sandbox by setting sandbox_enabled=True."
            )

    def _extract_function_code(self) -> str:
        """
        Extract Python function code from skill content.

        Returns:
            Complete Python code with function and execution call

        Example:
            Input: "def execute(query: str) -> str:\n    return f'Hello {query}'"
            Output: "def execute(query: str) -> str:\n    return f'Hello {query}'\n\nresult = execute(query)\nprint(result)"
        """
        code = self.skill_content.strip()

        # Add execution wrapper if not present
        if "result = execute(query)" not in code:
            code += "\n\n# Execute skill function\nresult = execute(query)\nprint(result)"

        return code


def create_community_tool(parsed_skill: Dict[str, Any]) -> CommunitySkillTool:
    """
    Factory function to create CommunitySkillTool from parsed skill.

    Args:
        parsed_skill: Dictionary from SkillParser containing:
            - name: Skill name
            - description: Skill description
            - skill_type: "prompt_only" or "python_code"
            - Additional metadata

    Returns:
        CommunitySkillTool instance

    Example:
        parser = SkillParser()
        metadata, body = parser.parse_skill_file("path/to/SKILL.md")

        tool = create_community_tool({
            "name": metadata["name"],
            "description": metadata["description"],
            "skill_type": metadata["skill_type"],
            "skill_content": body,
            "skill_id": "unique_id"
        })
    """
    skill_type = parsed_skill.get("skill_type", "prompt_only")
    skill_content = parsed_skill.get("skill_content", "")
    skill_id = parsed_skill.get("skill_id", parsed_skill.get("name", "unknown"))
    sandbox_enabled = parsed_skill.get("sandbox_enabled", False)

    # Create tool instance
    tool = CommunitySkillTool(
        name=parsed_skill.get("name", "community_skill"),
        description=parsed_skill.get("description", "Execute a community skill"),
        skill_id=skill_id,
        skill_type=skill_type,
        skill_content=skill_content,
        sandbox_enabled=sandbox_enabled
    )

    logger.info(
        f"Created CommunitySkillTool: {tool.name} "
        f"(type: {skill_type}, id: {skill_id})"
    )

    return tool
