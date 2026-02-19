"""
Skill Registry Service - Manage imported community skills.

Provides import workflow, security scanning, and lifecycle management
for OpenClaw community skills with governance integration.

Extended for Python package support (Phase 35):
- Extracts packages from parsed skill metadata
- Checks package permissions using PackageGovernanceService
- Installs packages in dedicated Docker images using PackageInstaller
- Executes skills with custom images containing pre-installed packages

Extended for npm package support (Phase 36):
- Extracts node_packages from parsed skill metadata
- Checks npm package permissions using PackageGovernanceService (package_type='npm')
- Installs npm packages using NpmPackageInstaller
- Executes Node.js skills with pre-installed npm packages
- Audit logging for all npm governance decisions and installations
- Skill type detection (Python vs Node.js)

Reference: Phase 14 Plan 03 - Skills Registry & Security
Reference: Phase 35 Plan 06 - Skill Integration
Reference: Phase 36 Plan 06 - npm Skill Integration
"""

import datetime
import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.episode_segmentation_service import EpisodeSegmentationService
from core.models import EpisodeSegment, SkillExecution
from core.skill_adapter import create_community_tool
from core.skill_parser import SkillParser
from core.skill_sandbox import HazardSandbox
from core.skill_security_scanner import SkillSecurityScanner

logger = logging.getLogger(__name__)


class SkillRegistryService:
    """
    Service for managing imported community skills.

    Workflow:
    1. Import skill (from GitHub URL, file upload, or raw content)
    2. Parse SKILL.md using SkillParser
    3. Security scan using SkillSecurityScanner
    4. Store in database with status (Untrusted/Active)
    5. Execute skills with governance checks
    6. Promote skills from Untrusted to Active

    Governance integration:
    - Default community skills to INTERN maturity level
    - Check agent maturity before execution
    - Create SkillExecution audit records
    - Sandbox execution for Python skills

    Example:
        service = SkillRegistryService(db)
        result = service.import_skill(
            source="raw_content",
            content="---\nname: My Skill\n---\n...",
            metadata={"imported_by": "user123"}
        )
    """

    def __init__(self, db: Session):
        """
        Initialize skill registry service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._parser = SkillParser()
        self._scanner = SkillSecurityScanner()
        self._sandbox = HazardSandbox()
        self._governance = AgentGovernanceService(db)
        self._segmentation_service = EpisodeSegmentationService(db)

    def import_skill(
        self,
        source: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Import a community skill from various sources.

        Extended to extract Python packages from SKILL.md (Phase 35):
        - Parses packages from frontmatter using SkillParser
        - Stores packages in input_params for execution workflow

        Args:
            source: Import source - "github_url", "file_upload", or "raw_content"
            content: SKILL.md content or file content
            metadata: Optional metadata (author, tags, etc.)

        Returns:
            Dict with:
                - skill_id: str - Unique identifier for imported skill
                - scan_result: Dict - Security scan results
                - status: str - "Untrusted" or "Active"
                - metadata: Dict - Skill metadata (includes packages)

        Example:
            result = service.import_skill(
                source="raw_content",
                content="---\\nname: Calculator\\npackages:\\n  - numpy==1.21.0\\n---\\n...",
                metadata={"author": "community"}
            )
        """
        logger.info(f"Importing skill from source: {source}")

        try:
            # Step 1: Parse SKILL.md
            metadata = metadata or {}
            # For raw content, we need to create a temp file or parse directly
            # For now, assume content is already SKILL.md format
            import frontmatter
            post = frontmatter.loads(content)
            skill_metadata = post.metadata
            skill_body = post.content

            # Apply auto-fix for missing fields
            skill_metadata = self._parser._auto_fix_metadata(skill_metadata, skill_body, source)

            # Extract packages (Phase 35)
            packages = self._parser._extract_packages(skill_metadata, source)
            skill_metadata['packages'] = packages

            # Extract node_packages (Phase 36)
            node_packages = self._parser._extract_node_packages(skill_metadata, source)
            skill_metadata['node_packages'] = node_packages

            # Extract package_manager (Phase 36)
            package_manager = self._parser._extract_package_manager(skill_metadata, source)
            skill_metadata['package_manager'] = package_manager

            # Detect skill type
            skill_type = self._parser._detect_skill_type(skill_metadata, skill_body)
            skill_metadata['skill_type'] = skill_type

            # Merge metadata
            skill_metadata.update(metadata)

            skill_name = skill_metadata.get("name", "Unnamed Skill")
            skill_type = skill_metadata.get("skill_type", "prompt_only")

            logger.info(
                f"Parsed skill '{skill_name}' (type: {skill_type}, packages: {len(packages)})"
            )

            # Step 2: Security scan
            scan_result = self._scanner.scan_skill(skill_name, skill_body)

            logger.info(f"Security scan result: {scan_result['risk_level']}")

            # Step 3: Determine status based on scan result
            if scan_result["risk_level"] == "LOW":
                status = "Active"
            else:
                status = "Untrusted"
                logger.warning(f"Skill '{skill_name}' marked as Untrusted (risk: {scan_result['risk_level']})")

            # Step 4: Store in database
            skill_id = str(uuid.uuid4())

            skill_record = SkillExecution(
                id=skill_id,
                agent_id="system",  # Community skills don't belong to specific agent
                workspace_id="default",
                skill_id=f"community_{skill_name}_{skill_id[:8]}",
                status=status,
                input_params={
                    "skill_name": skill_name,
                    "skill_type": skill_type,
                    "skill_metadata": skill_metadata,
                    "skill_body": skill_body,
                    "packages": packages,  # Phase 35: Store Python packages
                    "node_packages": node_packages,  # Phase 36: Store npm packages
                    "package_manager": package_manager  # Phase 36: Store package manager
                },
                skill_source="community",
                security_scan_result=scan_result,
                sandbox_enabled=(skill_type == "python_code")
            )

            self.db.add(skill_record)
            self.db.commit()

            logger.info(f"Imported skill '{skill_name}' (id: {skill_id}, status: {status})")

            return {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "scan_result": scan_result,
                "status": status,
                "metadata": skill_metadata
            }

        except Exception as e:
            logger.error(f"Failed to import skill: {e}")
            self.db.rollback()
            raise

    def list_skills(
        self,
        status: str = None,
        skill_type: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List imported community skills with filtering.

        Args:
            status: Filter by status - "Untrusted", "Active", or None (all)
            skill_type: Filter by skill_type - "prompt_only", "python_code", or None (all)
            limit: Maximum number of skills to return

        Returns:
            List of skill metadata dicts

        Example:
            skills = service.list_skills(status="Active", limit=10)
        """
        query = self.db.query(SkillExecution).filter(
            SkillExecution.skill_source == "community"
        )

        if status:
            query = query.filter(SkillExecution.status == status)

        if skill_type:
            # Filter by skill_type in input_params
            query = query.filter(
                SkillExecution.input_params["skill_type"].astext == skill_type
            )

        skills = query.order_by(SkillExecution.created_at.desc()).limit(limit).all()

        result = []
        for skill in skills:
            result.append({
                "skill_id": skill.id,
                "skill_name": skill.input_params.get("skill_name", "Unknown"),
                "skill_type": skill.input_params.get("skill_type", "unknown"),
                "status": skill.status,
                "risk_level": skill.security_scan_result.get("risk_level", "UNKNOWN") if skill.security_scan_result else "UNKNOWN",
                "created_at": skill.created_at.isoformat(),
                "sandbox_enabled": skill.sandbox_enabled
            })

        logger.info(f"Listed {len(result)} skills (status={status}, type={skill_type})")

        return result

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific skill.

        Args:
            skill_id: Skill ID from import

        Returns:
            Dict with skill details or None if not found

        Example:
            skill = service.get_skill("abc-123-def")
        """
        skill = self.db.query(SkillExecution).filter(
            SkillExecution.id == skill_id,
            SkillExecution.skill_source == "community"
        ).first()

        if not skill:
            logger.warning(f"Skill not found: {skill_id}")
            return None

        return {
            "skill_id": skill.id,
            "skill_name": skill.input_params.get("skill_name"),
            "skill_type": skill.input_params.get("skill_type"),
            "skill_body": skill.input_params.get("skill_body"),
            "skill_metadata": skill.input_params.get("skill_metadata", {}),
            "status": skill.status,
            "security_scan_result": skill.security_scan_result,
            "sandbox_enabled": skill.sandbox_enabled,
            "created_at": skill.created_at.isoformat()
        }

    async def execute_skill(
        self,
        skill_id: str,
        inputs: Dict[str, Any],
        agent_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Execute a community skill with governance checks.

        Extended for Python package support (Phase 35):
        - Extracts packages from skill metadata
        - Checks package permissions using PackageGovernanceService
        - Installs packages in dedicated Docker images using PackageInstaller
        - Executes skills with custom images containing pre-installed packages

        Args:
            skill_id: Skill ID from import
            inputs: Input parameters for skill execution
            agent_id: Agent ID executing the skill

        Returns:
            Dict with execution result (includes image_tag and packages if applicable)

        Raises:
            ValueError: If skill not found or governance check fails
        """
        # Retrieve skill
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        skill_name = skill["skill_name"]
        skill_type = skill["skill_type"]
        status = skill["status"]

        # Extract packages from skill metadata (Phase 35)
        packages = skill["skill_metadata"].get("packages", [])

        # Extract node_packages from skill metadata (Phase 36)
        node_packages = skill["skill_metadata"].get("node_packages", [])
        package_manager = skill["skill_metadata"].get("package_manager", "npm")

        # Governance check: Verify agent maturity
        # Community skills default to INTERN maturity requirement
        agent_caps = self._governance.get_agent_capabilities(agent_id)
        if not agent_caps:
            logger.warning(f"Agent not found: {agent_id}, executing as system")
        else:
            agent_maturity = agent_caps.get("maturity_level", "STUDENT")
            if agent_maturity == "STUDENT" and skill_type == "python_code":
                raise ValueError(
                    f"STUDENT agents cannot execute Python skills. "
                    f"Agent '{agent_id}' needs INTERN+ maturity for skill '{skill_name}'"
                )

        logger.info(
            f"Executing skill '{skill_name}' (type: {skill_type}, status: {status}, "
            f"python_packages: {len(packages)}, node_packages: {len(node_packages)})"
        )

        # Package permission checks (Phase 35 - Python, Phase 36 - npm)
        if packages and skill_type == "python_code":
            from core.package_governance_service import PackageGovernanceService
            from packaging.requirements import Requirement

            governance = PackageGovernanceService()

            # Check permissions for all packages
            for package_req in packages:
                try:
                    req = Requirement(package_req)
                    version_spec = str(req.specifier) if req.specifier else "latest"

                    permission = governance.check_package_permission(
                        agent_id=agent_id,
                        package_name=req.name,
                        version=version_spec,
                        db=self.db
                    )

                    if not permission["allowed"]:
                        error_msg = (
                            f"Package permission denied: {req.name}@{version_spec}. "
                            f"Reason: {permission['reason']}"
                        )
                        logger.warning(error_msg)
                        raise ValueError(error_msg)

                except ValueError:
                    # Re-raise ValueError from permission check
                    raise
                except Exception as e:
                    logger.error(f"Error checking package permission for {package_req}: {e}")
                    # Continue on parsing errors (already validated in SkillParser)

            # npm package permission checks (Phase 36)
            if node_packages:
                from core.package_governance_service import PackageGovernanceService

                governance = PackageGovernanceService()

                # Check permissions for all npm packages
                for pkg_spec in node_packages:
                    try:
                        name, version = self._parse_npm_package(pkg_spec)

                        permission = governance.check_package_permission(
                            agent_id=agent_id,
                            package_name=name,
                            version=version,
                            package_type="npm",
                            db=self.db
                        )

                        if not permission["allowed"]:
                            error_msg = (
                                f"npm package permission denied: {name}@{version}. "
                                f"Reason: {permission['reason']}"
                            )
                            logger.warning(error_msg)
                            raise ValueError(error_msg)

                    except ValueError:
                        raise  # Re-raise ValueError from permission check
                    except Exception as e:
                        logger.error(f"Error checking npm package permission for {pkg_spec}: {e}")
                        # Continue on parsing errors

        # Create execution record
        execution = SkillExecution(
            agent_id=agent_id,
            skill_id=f"{skill_name}_{skill_id[:8]}",
            workspace_id="default",
            status="running",
            input_params=inputs,
            skill_source="community",
            sandbox_enabled=skill["sandbox_enabled"]
        )

        self.db.add(execution)
        self.db.commit()

        start_time = datetime.datetime.now(datetime.timezone.utc)
        error = None
        result = None

        try:
            # Execute based on skill type and package presence
            if skill_type == "prompt_only":
                result = self._execute_prompt_skill(skill, inputs)
            elif skill_type == "python_code":
                if node_packages:
                    # npm package execution path (Phase 36)
                    result = await self._execute_nodejs_skill_with_packages(
                        skill, inputs, node_packages, package_manager, agent_id
                    )
                elif packages:
                    # Python package execution path (Phase 35)
                    result = await self._execute_python_skill_with_packages(
                        skill, inputs, packages, agent_id
                    )
                else:
                    # Original execution without packages
                    result = self._execute_python_skill(skill, inputs)
            else:
                raise ValueError(f"Unknown skill type: {skill_type}")

            # Update execution record
            execution.status = "success"
            execution.output_result = {"result": result}
            execution.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()

            # Create episode segment for successful execution
            execution_time = (datetime.datetime.now(datetime.timezone.utc) - start_time).total_seconds()
            episode_id = await self._create_execution_episode(
                skill_name=skill_name,
                agent_id=agent_id,
                inputs=inputs,
                result=result,
                error=None,
                execution_time=execution_time
            )

            return {
                "success": True,
                "result": result,
                "execution_id": execution.id,
                "episode_id": episode_id
            }

        except Exception as e:
            error = e
            # Update execution record with error
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()

            logger.error(f"Skill execution failed: {e}")

            # Create episode segment for failed execution
            execution_time = (datetime.datetime.now(datetime.timezone.utc) - start_time).total_seconds()
            episode_id = await self._create_execution_episode(
                skill_name=skill_name,
                agent_id=agent_id,
                inputs=inputs,
                result=None,
                error=e,
                execution_time=execution_time
            )

            return {
                "success": False,
                "error": str(e),
                "execution_id": execution.id,
                "episode_id": episode_id
            }

    def _execute_prompt_skill(self, skill: Dict[str, Any], inputs: Dict[str, Any]) -> str:
        """
        Execute prompt-only skill (no sandbox needed).

        Args:
            skill: Skill metadata
            inputs: Input parameters

        Returns:
            Formatted prompt string
        """
        # Create tool instance
        tool = create_community_tool({
            "name": skill["skill_name"],
            "description": skill["skill_metadata"].get("description", ""),
            "skill_type": "prompt_only",
            "skill_content": skill["skill_body"],
            "skill_id": skill["skill_id"]
        })

        # Execute
        query = inputs.get("query", "")
        return tool._run(query)

    def _execute_python_skill(self, skill: Dict[str, Any], inputs: Dict[str, Any]) -> str:
        """
        Execute Python skill in sandbox.

        Args:
            skill: Skill metadata
            inputs: Input parameters

        Returns:
            Execution result from sandbox
        """
        if not skill["sandbox_enabled"]:
            raise ValueError(
                f"Python skill '{skill['skill_name']}' requires sandbox execution. "
                f"Sandbox is disabled for this skill."
            )

        # Extract Python code
        code_blocks = self._parser.extract_python_code(skill["skill_body"])
        if not code_blocks:
            raise ValueError(f"No Python code found in skill '{skill['skill_name']}'")

        # Use first code block
        code = code_blocks[0]

        # Execute in sandbox
        result = self._sandbox.execute_python(code, inputs)

        return result

    async def _execute_python_skill_with_packages(
        self,
        skill: Dict[str, Any],
        inputs: Dict[str, Any],
        packages: List[str],
        agent_id: str
    ) -> str:
        """
        Execute Python skill with custom Docker image containing packages.

        Package execution workflow (Phase 35):
        1. Install packages in dedicated Docker image using PackageInstaller
        2. Execute skill code using custom image with pre-installed packages
        3. Return execution output

        Args:
            skill: Skill metadata
            inputs: Input parameters
            packages: List of Python package requirements
            agent_id: Agent ID executing the skill

        Returns:
            Execution result from package-aware execution

        Raises:
            ValueError: If package installation fails
        """
        from core.package_installer import PackageInstaller

        skill_name = skill["skill_name"]
        skill_id_for_image = f"skill-{skill_name.replace(' ', '-').lower()}"

        logger.info(
            f"Executing skill '{skill_name}' with {len(packages)} packages"
        )

        try:
            installer = PackageInstaller()

            # Step 1: Install packages in dedicated image
            logger.info(
                f"Installing {len(packages)} packages for skill '{skill_name}'"
            )
            install_result = installer.install_packages(
                skill_id=skill_id_for_image,
                requirements=packages,
                scan_for_vulnerabilities=True
            )

            if not install_result["success"]:
                error_msg = install_result.get("error", "Unknown installation error")
                logger.error(
                    f"Package installation failed for skill '{skill_name}': {error_msg}"
                )
                raise ValueError(f"Package installation failed: {error_msg}")

            # Log vulnerabilities if any
            vulnerabilities = install_result.get("vulnerabilities", [])
            if vulnerabilities:
                logger.warning(
                    f"Skill '{skill_name}' has {len(vulnerabilities)} vulnerabilities "
                    f"(proceeding with execution)"
                )

            # Step 2: Extract Python code
            code_blocks = self._parser.extract_python_code(skill["skill_body"])
            if not code_blocks:
                raise ValueError(f"No Python code found in skill '{skill_name}'")

            # Use first code block
            code = code_blocks[0]

            # Step 3: Execute skill using custom image
            logger.info(
                f"Executing skill '{skill_name}' with image {install_result['image_tag']}"
            )

            output = installer.execute_with_packages(
                skill_id=skill_id_for_image,
                code=code,
                inputs=inputs
            )

            return output

        except Exception as e:
            logger.error(f"Package execution failed for skill '{skill_name}': {e}")
            raise

    async def _execute_nodejs_skill_with_packages(
        self,
        skill: Dict[str, Any],
        inputs: Dict[str, Any],
        node_packages: List[str],
        package_manager: str,
        agent_id: str
    ) -> str:
        """
        Execute Node.js skill with npm packages using NpmPackageInstaller.

        Package execution workflow (Phase 36):
        1. Install npm packages in dedicated Docker image
        2. Execute Node.js code using custom image with pre-installed packages
        3. Return execution output

        Args:
            skill: Skill metadata
            inputs: Input parameters
            node_packages: List of npm package specifiers
            package_manager: Package manager (npm, yarn, pnpm)
            agent_id: Agent ID executing the skill

        Returns:
            Execution result from npm-aware execution

        Raises:
            ValueError: If npm installation fails
        """
        from core.npm_package_installer import NpmPackageInstaller

        skill_name = skill["skill_name"]
        skill_id_for_image = f"skill-{skill['skill_id']}" if 'skill_id' in skill else f"skill-{skill_name.replace(' ', '-').lower()}"

        logger.info(
            f"Executing Node.js skill '{skill_name}' with {len(node_packages)} npm packages"
        )

        try:
            # Step 1: Install npm packages using NpmPackageInstaller
            logger.info(
                f"Installing {len(node_packages)} npm packages for skill '{skill_name}'"
            )

            # Install with governance checks and audit logging
            install_result = self._install_npm_dependencies_for_skill(
                skill_id=skill_id_for_image,
                node_packages=node_packages,
                package_manager=package_manager,
                agent_id=agent_id,
                db=self.db
            )

            if not install_result.get("success"):
                error_msg = install_result.get("error", "Unknown npm installation error")
                logger.error(
                    f"npm installation failed for skill '{skill_name}': {error_msg}"
                )
                raise ValueError(f"npm installation failed: {error_msg}")

            # Log vulnerabilities if any
            vulnerabilities = install_result.get("vulnerabilities", [])
            if vulnerabilities:
                logger.warning(
                    f"Skill '{skill_name}' has {len(vulnerabilities)} vulnerabilities "
                    f"(proceeding with execution)"
                )

            # Step 2: Extract Node.js code from skill body
            code = self._extract_nodejs_code(skill["skill_body"])
            if not code:
                raise ValueError(f"No Node.js code found in skill '{skill_name}'")

            # Step 3: Execute skill using custom image
            logger.info(
                f"Executing skill '{skill_name}' with image {install_result['image_tag']}"
            )

            installer = NpmPackageInstaller()
            output = installer.execute_with_packages(
                skill_id=skill_id_for_image,
                code=code,
                inputs=inputs
            )

            return output

        except Exception as e:
            logger.error(f"npm execution failed for skill '{skill_name}': {e}")
            raise

    def _extract_nodejs_code(self, skill_body: str) -> str:
        """
        Extract Node.js code from skill body.

        Looks for ```javascript or ```node fence blocks.
        If no code blocks found, returns entire body as code.

        Args:
            skill_body: Skill body content

        Returns:
            Node.js code string
        """
        # Check for ```javascript or ```node fence blocks
        lines = skill_body.split('\n')
        in_code_block = False
        code_lines = []

        for line in lines:
            if line.strip().startswith('```javascript') or line.strip().startswith('```node') or line.strip().startswith('``` js'):
                in_code_block = True
                continue

            if in_code_block and line.strip() == '```':
                break

            if in_code_block:
                code_lines.append(line)

        # If code block found, return it
        if code_lines:
            return '\n'.join(code_lines)

        # Otherwise, return entire body (might be pure Node.js code)
        return skill_body

    def _install_npm_dependencies_for_skill(
        self,
        skill_id: str,
        node_packages: List[str],
        package_manager: str,
        agent_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Install npm packages for skill with governance checks and audit logging.

        Workflow:
        1. Check governance permissions for all packages (package_type='npm')
        2. Log governance decisions to audit trail
        3. Scan for postinstall/preinstall scripts
        4. Install packages using NpmPackageInstaller
        5. Log installation attempts to audit trail

        Args:
            skill_id: Unique skill identifier
            node_packages: List of npm package specifiers
            package_manager: Package manager (npm, yarn, pnpm)
            agent_id: Agent ID executing the skill
            db: Database session for governance and audit logging

        Returns:
            Dict with installation result (success, image_tag, vulnerabilities)

        Raises:
            PermissionError: If governance check fails
            SecurityError: If malicious scripts detected
        """
        from core.npm_package_installer import NpmPackageInstaller
        from core.npm_script_analyzer import NpmScriptAnalyzer
        from core.audit_service import audit_service

        # Step 1: Check governance permissions with audit logging
        logger.info(f"Checking npm governance permissions for {len(node_packages)} packages")

        for pkg in node_packages:
            name, version = self._parse_npm_package(pkg)

            permission = self._governance.check_package_permission(
                agent_id, name, version, package_type="npm", db=db
            )

            # Log governance decision to audit trail
            audit_service.create_package_audit(
                db=db,
                agent_id=agent_id,
                user_id=agent_id,  # Agent as user
                action="governance_decision",
                package_name=name,
                package_version=version,
                package_type="npm",
                skill_id=skill_id,
                governance_decision="approved" if permission["allowed"] else "denied",
                governance_reason=permission.get("reason", ""),
                metadata={"package_manager": package_manager}
            )

            if not permission["allowed"]:
                error_msg = (
                    f"npm package {name}@{version} blocked by governance: "
                    f"{permission['reason']}"
                )
                logger.warning(error_msg)
                raise PermissionError(error_msg)

            logger.info(f"Governance check passed for npm package {name}@{version}")

        # Step 2: Scan for postinstall scripts
        script_analyzer = NpmScriptAnalyzer()
        script_warnings = script_analyzer.analyze_package_scripts(
            node_packages, package_manager
        )

        if script_warnings["malicious"]:
            error_msg = (
                f"Malicious postinstall/preinstall scripts detected: "
                f"{script_warnings['warnings']}"
            )
            logger.error(error_msg)
            raise SecurityError(error_msg)

        if script_warnings["warnings"]:
            logger.warning(f"Suspicious npm scripts detected: {script_warnings['warnings']}")

        # Step 3: Install packages with audit logging
        installer = NpmPackageInstaller()
        install_result = installer.install_packages(
            skill_id=skill_id,
            packages=node_packages,
            package_manager=package_manager
        )

        # Step 4: Log installation attempt to audit trail
        for pkg in node_packages:
            name, version = self._parse_npm_package(pkg)

            audit_service.create_package_audit(
                db=db,
                agent_id=agent_id,
                user_id=agent_id,
                action="install",
                package_name=name,
                package_version=version,
                package_type="npm",
                skill_id=skill_id,
                governance_decision="approved",
                metadata={
                    "install_success": install_result.get("success", False),
                    "image_tag": install_result.get("image_tag"),
                    "package_manager": package_manager
                }
            )

        if not install_result["success"]:
            error_msg = install_result.get("error", "Unknown npm installation error")
            logger.error(f"npm installation failed: {error_msg}")
            raise ValueError(error_msg)

        logger.info(
            f"Successfully installed {len(node_packages)} npm packages for skill {skill_id} "
            f"(image: {install_result['image_tag']})"
        )

        return install_result

    def _parse_npm_package(self, package: str) -> tuple:
        """
        Parse npm package specifier into name and version.

        Args:
            package: Package specifier (e.g., "lodash@4.17.21", "express", "@scope/name@^1.0.0")

        Returns:
            Tuple of (name, version)
        """
        # Handle scoped packages (@scope/name or @scope/name@version)
        if package.startswith('@'):
            if package.count('@') >= 2:
                # @scope/name@version
                parts = package.split('@')
                name = f"@{parts[1]}"
                version = parts[2]
                return (name, version)
            else:
                # @scope/name without version
                return (package, "latest")

        # Handle regular packages
        if '@' in package:
            name, version = package.split('@', 1)
            return (name, version)
        else:
            return (package, "latest")

    def detect_skill_type(self, skill_content: str) -> str:
        """
        Detect if skill is Python or Node.js based on content.

        Args:
            skill_content: Full SKILL.md content (YAML frontmatter + body)

        Returns:
            "npm" or "python"

        Detection rules (in order of priority):
        1. Has node_packages field -> 'npm'
        2. Has python_packages field -> 'python'
        3. Code file extension .js/.mjs/.cjs -> 'npm'
        4. Code file extension .py -> 'python'
        5. Shebang #!/usr/bin/env node -> 'npm'
        6. Shebang #!/usr/bin/env python -> 'python'
        7. Default: 'python' (backward compatibility)
        """
        # Check for explicit package declarations first (highest priority)
        if 'node_packages:' in skill_content:
            return 'npm'
        if 'python_packages:' in skill_content or '\npackages:' in skill_content:
            return 'python'

        # Check code file extension
        # Extract code file from skill_content if present
        import frontmatter
        try:
            post = frontmatter.loads(skill_content)
            body = post.content

            # Check for code file references in body
            # Format: "Code file: skill.js" or similar
            for line in body.split('\n'):
                line_lower = line.lower()
                if 'code file:' in line_lower or 'file:' in line_lower:
                    if line.endswith('.js') or line.endswith('.mjs') or line.endswith('.cjs'):
                        return 'npm'
                    if line.endswith('.py'):
                        return 'python'

            # Check shebang in code blocks
            if '```javascript' in body.lower() or '```node' in body.lower() or '``` js' in body.lower():
                return 'npm'
            if '```python' in body.lower():
                return 'python'

        except Exception as e:
            logger.warning(f"Failed to parse skill content for type detection: {e}")

        # Default to Python for backward compatibility
        return 'python'

    def _summarize_inputs(self, inputs: Dict[str, Any]) -> str:
        """
        Summarize input parameters for episode context.

        Args:
            inputs: Input parameters

        Returns:
            Summarized string representation
        """
        if not inputs:
            return "{}"

        # Truncate long values
        summarized = {}
        for key, value in inputs.items():
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:97] + "..."
            summarized[key] = value_str

        return str(summarized)

    async def _create_execution_episode(
        self,
        skill_name: str,
        agent_id: str,
        inputs: dict,
        result: Any,
        error: Optional[Exception],
        execution_time: float
    ) -> Optional[str]:
        """
        Create an episode segment for skill execution.

        Args:
            skill_name: Name of the executed skill
            agent_id: Agent ID that executed the skill
            inputs: Input parameters
            result: Execution result
            error: Exception if execution failed
            execution_time: Execution time in seconds

        Returns:
            Episode segment ID or None if creation failed
        """
        try:
            segment_type = "skill_success" if error is None else "skill_failure"

            # Extract skill metadata
            skill_context = {
                "skill_name": skill_name,
                "skill_source": "community",
                "execution_time": execution_time,
                "input_summary": self._summarize_inputs(inputs),
                "result_summary": str(result)[:200] if result else None,
                "error_type": type(error).__name__ if error else None,
                "error_message": str(error)[:200] if error else None
            }

            # Create episode segment directly without full episode
            segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=f"skill_{skill_name}_{agent_id[:8]}_{int(datetime.datetime.now().timestamp())}",
                segment_type=segment_type,
                sequence_order=0,
                content=f"Skill execution: {skill_name}",
                content_summary=f"Executed {skill_name} - {'Success' if error is None else 'Failed'}",
                source_type="skill_execution",
                source_id=str(uuid.uuid4()),
                metadata=skill_context
            )

            self.db.add(segment)
            self.db.commit()
            self.db.refresh(segment)

            logger.info(f"Created episode segment {segment.id} for skill execution: {skill_name}")
            return segment.id

        except Exception as e:
            logger.error(f"Failed to create episode segment for skill execution: {e}")
            self.db.rollback()
            return None

    def load_skill_dynamically(
        self,
        skill_id: str,
        skill_path: str
    ) -> Dict[str, Any]:
        """
        Load skill dynamically using SkillDynamicLoader.

        Enables runtime skill loading without restart.

        Args:
            skill_id: Unique skill identifier
            skill_path: Absolute path to skill file

        Returns:
            Dict with load result
        """
        try:
            from core.skill_dynamic_loader import get_global_loader

            loader = get_global_loader()
            module = loader.load_skill(skill_id, skill_path)

            if module is None:
                return {
                    "success": False,
                    "error": "Failed to load skill module"
                }

            return {
                "success": True,
                "skill_id": skill_id,
                "loaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Dynamic skill loading failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def reload_skill_dynamically(self, skill_id: str) -> Dict[str, Any]:
        """
        Hot-reload skill using SkillDynamicLoader.

        Args:
            skill_id: Skill identifier to reload

        Returns:
            Dict with reload result
        """
        try:
            from core.skill_dynamic_loader import get_global_loader

            loader = get_global_loader()
            module = loader.reload_skill(skill_id)

            if module is None:
                return {
                    "success": False,
                    "error": "Skill not loaded or reload failed"
                }

            return {
                "success": True,
                "skill_id": skill_id,
                "reloaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Skill hot-reload failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def promote_skill(self, skill_id: str) -> Dict[str, Any]:
        """
        Promote a skill from Untrusted to Active status.

        Args:
            skill_id: Skill ID to promote

        Returns:
            Dict with updated status

        Raises:
            ValueError: If skill not found or already Active

        Example:
            result = service.promote_skill("abc-123-def")
            # {"status": "Active", "previous_status": "Untrusted"}
        """
        skill = self.db.query(SkillExecution).filter(
            SkillExecution.id == skill_id,
            SkillExecution.skill_source == "community"
        ).first()

        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        if skill.status == "Active":
            logger.warning(f"Skill '{skill_id}' is already Active")
            return {
                "status": "Active",
                "previous_status": "Active",
                "message": "Skill is already Active"
            }

        previous_status = skill.status
        skill.status = "Active"
        self.db.commit()

        skill_name = skill.input_params.get("skill_name", "Unknown")
        logger.info(f"Promoted skill '{skill_name}' from {previous_status} to Active")

        return {
            "status": "Active",
            "previous_status": previous_status,
            "message": f"Skill promoted from {previous_status} to Active"
        }
