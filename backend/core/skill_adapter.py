"""
Skill Adapter for OpenClaw community skills.

Wraps parsed SKILL.md files as LangChain BaseTool subclasses
with Pydantic validation for seamless integration with Atom agents.

Extended for Python package support (Phase 35):
- Accepts packages parameter in __init__
- Uses PackageInstaller for skills with packages
- Falls back to default HazardSandbox when no packages
- Automatic Docker image building for isolated package execution

Extended for npm package support (Phase 36):
- NodeJsSkillAdapter for Node.js-based skills
- npm package installation with governance checks
- Node.js code execution with pre-installed packages
- Script analysis and vulnerability scanning

Reference: Phase 14 Plan 01 - Skill Adapter
Reference: Phase 25 Plan 02 - CLI Skill Integration
Reference: Phase 35 Plan 06 - Skill Integration
Reference: Phase 36 Plan 06 - npm Skill Integration
"""

import logging
import re
from typing import Any, Dict, List, Optional, Type

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

    Extended for Python package support (Phase 35):
    - packages: List of Python package requirements (e.g., ["numpy==1.21.0", "pandas>=1.3.0"])
    - Automatic Docker image building when packages present
    - Uses PackageInstaller for isolated package execution

    Instance attributes:
        name: Tool name (overridden per instance)
        description: Tool description from skill metadata
        args_schema: Pydantic schema for input validation
        skill_id: Unique identifier for this skill
        skill_type: "prompt_only" or "python_code"
        skill_content: Prompt template or Python code
        sandbox_enabled: Whether sandbox is enabled for Python skills
        packages: List of Python package requirements (Phase 35)
    """

    name: str = "community_skill"
    description: str = "Execute a community skill from ClawHub"
    args_schema: Type[BaseModel] = CommunitySkillInput

    skill_id: str = ""
    skill_type: str = "prompt_only"  # "prompt_only" or "python_code"
    skill_content: str = ""  # Prompt template or Python code
    sandbox_enabled: bool = False
    packages: list = []  # List of package requirements (Phase 35)

    def _run(self, query: str) -> str:
        """
        Execute the skill synchronously.

        Extended for Python package support (Phase 35):
        - If packages present and skill_type == "python_code":
          1. Install packages in dedicated Docker image
          2. Execute using custom image with pre-installed packages
        - Otherwise: Use default execution path (HazardSandbox or prompt template)

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

        # Package execution path (Phase 35)
        if self.packages and self.skill_type == "python_code":
            return self._execute_python_skill_with_packages(query)

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

    def _execute_python_skill_with_packages(self, query: str) -> str:
        """
        Execute Python skill with custom Docker image containing packages.

        Package execution workflow (Phase 35):
        1. Install packages in dedicated Docker image using PackageInstaller
        2. Execute skill code using custom image with pre-installed packages
        3. Handle installation and execution errors gracefully

        Args:
            query: User's request

        Returns:
            Execution result or error message
        """
        from core.package_installer import PackageInstaller

        # Generate skill ID for image tagging
        # Format: atom-skill:{skill_name}-v1
        skill_id_for_image = f"skill-{self.name.replace(' ', '-').lower()}"

        try:
            installer = PackageInstaller()

            # Step 1: Install packages in dedicated image
            logger.info(
                f"Installing {len(self.packages)} packages for skill '{self.name}'"
            )
            install_result = installer.install_packages(
                skill_id=skill_id_for_image,
                requirements=self.packages,
                scan_for_vulnerabilities=True  # Scan before installation
            )

            if not install_result["success"]:
                error_msg = install_result.get("error", "Unknown installation error")
                logger.error(
                    f"Package installation failed for skill '{self.name}': {error_msg}"
                )
                return f"PACKAGE_INSTALLATION_ERROR: {error_msg}"

            # Log vulnerabilities if any
            vulnerabilities = install_result.get("vulnerabilities", [])
            if vulnerabilities:
                logger.warning(
                    f"Skill '{self.name}' has {len(vulnerabilities)} vulnerabilities "
                    f"(proceeding with execution)"
                )

            # Step 2: Execute skill using custom image
            logger.info(
                f"Executing skill '{self.name}' with image {install_result['image_tag']}"
            )

            code = self._extract_function_code()

            output = installer.execute_with_packages(
                skill_id=skill_id_for_image,
                code=code,
                inputs={"query": query}
            )

            return output

        except Exception as e:
            logger.error(f"Package execution failed for skill '{self.name}': {e}")
            return f"PACKAGE_EXECUTION_ERROR: {str(e)}"

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

    Extended to support Python packages (Phase 35):
    - Extracts packages from parsed_skill metadata
    - Passes packages list to CommunitySkillTool constructor
    - Enables automatic Docker image building for package execution

    Args:
        parsed_skill: Dictionary from SkillParser containing:
            - name: Skill name
            - description: Skill description
            - skill_type: "prompt_only" or "python_code"
            - packages: List of Python package requirements (optional)
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
            "skill_id": "unique_id",
            "packages": metadata.get("packages", [])  # Phase 35
        })
    """
    skill_type = parsed_skill.get("skill_type", "prompt_only")
    skill_content = parsed_skill.get("skill_content", "")
    skill_id = parsed_skill.get("skill_id", parsed_skill.get("name", "unknown"))
    sandbox_enabled = parsed_skill.get("sandbox_enabled", False)
    packages = parsed_skill.get("packages", [])  # Phase 35: Extract packages

    # Create tool instance
    tool = CommunitySkillTool(
        name=parsed_skill.get("name", "community_skill"),
        description=parsed_skill.get("description", "Execute a community skill"),
        skill_id=skill_id,
        skill_type=skill_type,
        skill_content=skill_content,
        sandbox_enabled=sandbox_enabled,
        packages=packages  # Phase 35: Pass packages to tool
    )

    logger.info(
        f"Created CommunitySkillTool: {tool.name} "
        f"(type: {skill_type}, id: {skill_id}, packages: {len(packages)})"
    )

    return tool


class NodeJsSkillAdapter(BaseTool):
    """
    LangChain BaseTool wrapper for Node.js-based community skills with npm packages.

    Supports npm package installation and execution:
    - Governance permission checks before npm installation
    - NpmPackageInstaller for isolated package execution
    - Script analysis (postinstall/preinstall detection)
    - Vulnerability scanning before installation
    - Node.js code execution in Docker sandbox

    Instance attributes:
        name: Tool name (overridden per instance)
        description: Tool description from skill metadata
        args_schema: Pydantic schema for input validation
        skill_id: Unique identifier for this skill
        code: Node.js code to execute
        node_packages: List of npm package requirements
        package_manager: Package manager (npm, yarn, pnpm)
        agent_id: Agent ID executing this skill
    """

    name: str = "nodejs_skill"
    description: str = "Execute Node.js skill code with npm packages"
    args_schema: Type[BaseModel] = CommunitySkillInput

    skill_id: str = ""
    code: str = ""
    node_packages: list = []
    package_manager: str = "npm"
    agent_id: Optional[str] = None

    # Lazy-loaded services
    _installer: Optional[Any] = None
    _governance: Optional[Any] = None

    def __init__(
        self,
        skill_id: str,
        code: str,
        node_packages: List[str],
        package_manager: str = "npm",
        agent_id: Optional[str] = None,
        **kwargs
    ):
        """Initialize NodeJsSkillAdapter with skill metadata."""
        super().__init__(**kwargs)
        self.skill_id = skill_id
        self.code = code
        self.node_packages = node_packages
        self.package_manager = package_manager
        self.agent_id = agent_id

    @property
    def installer(self):
        """Lazy load NpmPackageInstaller."""
        if self._installer is None:
            from core.npm_package_installer import NpmPackageInstaller
            self._installer = NpmPackageInstaller()
        return self._installer

    @property
    def governance(self):
        """Lazy load PackageGovernanceService."""
        if self._governance is None:
            from core.package_governance_service import PackageGovernanceService
            self._governance = PackageGovernanceService()
        return self._governance

    def _run(self, tool_input: Dict[str, Any], run_manager=None) -> str:
        """
        Execute the Node.js skill synchronously.

        Args:
            tool_input: Input parameters with 'query' key
            run_manager: Optional run manager for LangChain

        Returns:
            Execution result or error message
        """
        try:
            # Extract query from tool_input
            query = tool_input.get("query", "")

            # Step 1: Install npm dependencies
            install_result = self.install_npm_dependencies()
            if not install_result["success"]:
                error_msg = install_result.get("error", "Unknown installation error")
                return f"NPM_INSTALLATION_ERROR: {error_msg}"

            # Step 2: Execute Node.js code with packages
            output = self.execute_nodejs_code(query)
            return output

        except Exception as e:
            logger.error(f"Node.js skill execution failed for {self.skill_id}: {e}")
            return f"NODEJS_EXECUTION_ERROR: {str(e)}"

    async def _arun(self, tool_input: Dict[str, Any], run_manager=None) -> str:
        """
        Execute the skill asynchronously.

        Args:
            tool_input: Input parameters
            run_manager: Optional run manager

        Returns:
            Execution result
        """
        # Delegate to synchronous implementation
        return self._run(tool_input, run_manager)

    def install_npm_dependencies(self) -> Dict[str, Any]:
        """
        Install npm packages with governance checks and script analysis.

        Workflow:
        1. Check governance permissions for all packages
        2. Analyze package scripts (postinstall/preinstall detection)
        3. Install packages using NpmPackageInstaller
        4. Return installation result

        Returns:
            Dict with success status and image_tag or error

        Raises:
            PermissionError: If governance check fails
            SecurityError: If malicious scripts detected
        """
        from core.npm_script_analyzer import NpmScriptAnalyzer
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # Create database session for governance checks
        engine = create_engine("sqlite:///./atom_dev.db")
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            # Step 1: Check governance permissions for all packages
            logger.info(f"Checking governance permissions for {len(self.node_packages)} npm packages")

            for pkg in self.node_packages:
                name, version = self._parse_npm_package(pkg)

                permission = self.governance.check_package_permission(
                    agent_id=self.agent_id or "system",
                    package_name=name,
                    version=version,
                    package_type="npm",
                    db=db
                )

                if not permission["allowed"]:
                    error_msg = (
                        f"npm package {name}@{version} blocked by governance: "
                        f"{permission.get('reason', 'Unknown reason')}"
                    )
                    logger.warning(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "package": name,
                        "version": version
                    }

                logger.info(f"Governance check passed for {name}@{version}")

            # Step 2: Analyze package scripts (postinstall/preinstall detection)
            script_analyzer = NpmScriptAnalyzer()
            script_warnings = script_analyzer.analyze_package_scripts(
                self.node_packages,
                self.package_manager
            )

            if script_warnings["malicious"]:
                error_msg = (
                    f"Malicious postinstall/preinstall scripts detected: "
                    f"{script_warnings['warnings']}"
                )
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "script_warnings": script_warnings
                }

            if script_warnings["warnings"]:
                logger.warning(f"Suspicious scripts detected: {script_warnings['warnings']}")

            # Step 3: Install packages using NpmPackageInstaller
            logger.info(
                f"Installing {len(self.node_packages)} npm packages for skill {self.skill_id}"
            )

            install_result = self.installer.install_packages(
                skill_id=self.skill_id,
                packages=self.node_packages,
                package_manager=self.package_manager,
                scan_for_vulnerabilities=True
            )

            if not install_result["success"]:
                error_msg = install_result.get("error", "Unknown installation error")
                logger.error(f"npm installation failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "install_result": install_result
                }

            logger.info(
                f"Successfully installed npm packages for skill {self.skill_id} "
                f"(image: {install_result['image_tag']})"
            )

            return {
                "success": True,
                "image_tag": install_result["image_tag"],
                "vulnerabilities": install_result.get("vulnerabilities", []),
                "script_warnings": script_warnings
            }

        finally:
            db.close()

    def execute_nodejs_code(self, query: str) -> str:
        """
        Execute Node.js code with pre-installed npm packages.

        Args:
            query: User query/input for the skill

        Returns:
            Execution output or error message

        Raises:
            RuntimeError: If skill image not found or execution fails
        """
        try:
            # Prepare inputs for execution
            inputs = {"query": query}

            # Execute using custom image with pre-installed packages
            logger.info(f"Executing Node.js skill {self.skill_id}")

            output = self.installer.execute_with_packages(
                skill_id=self.skill_id,
                code=self.code,
                inputs=inputs,
                timeout_seconds=300  # 5 minute timeout
            )

            logger.info(f"Node.js skill {self.skill_id} executed successfully")
            return output

        except Exception as e:
            error_msg = f"Node.js execution failed: {str(e)}"
            logger.error(f"{error_msg} for skill {self.skill_id}")
            return error_msg

    def _parse_npm_package(self, package: str) -> tuple:
        """
        Parse npm package specifier into name and version.

        Args:
            package: Package specifier (e.g., "lodash@4.17.21", "express", "@scope/name@^1.0.0")

        Returns:
            Tuple of (name, version)

        Examples:
            "lodash@4.17.21" -> ("lodash", "4.17.21")
            "express" -> ("express", "latest")
            "@scope/name@^1.0.0" -> ("@scope/name", "^1.0.0")
        """
        # Handle scoped packages (@scope/name or @scope/name@version)
        if package.startswith('@'):
            if package.count('@') >= 2:
                # @scope/name@version
                parts = package.split('@')
                # parts[0] = '', parts[1] = 'scope/name', parts[2] = 'version'
                name = f"@{parts[1]}"
                version = parts[2]
                return (name, version)
            else:
                # @scope/name without version
                return (package, "latest")

        # Handle regular packages
        if '@' in package:
            # name@version or name@range
            name, version = package.split('@', 1)
            return (name, version)
        else:
            # No version specified
            return (package, "latest")
