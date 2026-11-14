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
import json
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
        self._sandbox = None  # Lazy-initialized — requires Docker only when executing Python skills
        self._governance = AgentGovernanceService(db)
        self._segmentation_service = EpisodeSegmentationService(db)

    def _get_sandbox(self) -> HazardSandbox:
        """Lazy-initialize HazardSandbox only when needed (requires Docker)."""
        if self._sandbox is None:
            self._sandbox = HazardSandbox()
        return self._sandbox

    async def import_skill(
        self,
        source: str,
        content: str,
        metadata: Dict[str, Any] = None,
        *,
        commit: bool = True,
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
            scan_result = await self._scanner.scan_skill(skill_name, skill_body)

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
                tenant_id="system",  # Community skills belong to system tenant
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
            if commit:
                self.db.commit()
            else:
                self.db.flush()

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
            if commit:
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
            # Filter by skill_type in input_params (SQLAlchemy 2.x compatible)
            query = query.filter(
                SkillExecution.input_params["skill_type"].as_string() == skill_type
            )

        skills = query.order_by(SkillExecution.created_at.desc()).limit(limit).all()

        result = []
        for skill in skills:
            created_at = skill.created_at.isoformat() if skill.created_at else None
            result.append({
                "skill_id": skill.id,
                "skill_name": skill.input_params.get("skill_name", "Unknown"),
                "skill_type": skill.input_params.get("skill_type", "unknown"),
                "status": skill.status,
                "risk_level": skill.security_scan_result.get("risk_level", "UNKNOWN") if skill.security_scan_result else "UNKNOWN",
                "created_at": created_at,
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
            "packages": skill.input_params.get("packages", []),
            "node_packages": skill.input_params.get("node_packages", []),
            "package_manager": skill.input_params.get("package_manager"),
            "reviewed_executable": skill.input_params.get(
                "reviewed_executable"),
            "linked_skill_id": skill.skill_id,
            "status": skill.status,
            "security_scan_result": skill.security_scan_result,
            "sandbox_enabled": skill.sandbox_enabled,
            "created_at": skill.created_at.isoformat() if skill.created_at else None
        }

    @staticmethod
    def _json_object(value: Any) -> Dict[str, Any]:
        """Normalize a JSON column that may arrive as a dict or a string."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _declares_reviewed_executable(self, skill: Dict[str, Any]) -> bool:
        """Whether this registry record claims reviewed-executable provenance.

        The binding is normally on ``input_params.reviewed_executable``.  A
        record that lost that binding must not silently fall through to the
        generic community-skill path: the reviewed package frontmatter
        (code digests) and the linked ``Skill.config`` are durable markers
        that the artifact is the executable exception.  Fail closed when any
        marker is present.
        """
        metadata = self._json_object(skill.get("skill_metadata"))
        if any(metadata.get(key) for key in (
                "executable_code_sha256", "candidate_code_sha256",
                "reviewed_executable")):
            return True

        linked_skill_id = str(skill.get("linked_skill_id") or "")
        if not linked_skill_id:
            return False
        from core.models import Skill

        linked = (
            self.db.query(Skill)
            .filter(Skill.id == linked_skill_id)
            .first()
        )
        if linked is None:
            return False
        config = self._json_object(linked.config)
        return bool(config.get("reviewed_executable"))

    def _invocable_executable_entry(
        self,
        execution: SkillExecution,
        *,
        tenant_id: str,
        workspace_id: str,
        agent_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Describe one agent-invocable reviewed executable skill or None.

        Discovery metadata only, but it must not advertise a stale or revoked
        artifact: before returning an entry this runs the SAME read-only
        authorization the execution path uses (candidate promoted + current
        material digest, review revision/digest, linked ``Skill`` code/type,
        registry binding and workspace assignment).  ``_authorize_reviewed_executable``
        performs no writes, creates no ``SkillExecution`` row and never touches
        Docker.  ``execute_skill`` still re-runs it immediately before the
        sandbox, so a change between listing and dispatch cannot execute.
        """
        if execution is None:
            return None
        if str(execution.skill_source or "") != "community":
            return None
        if str(execution.status or "") != "Active":
            return None
        if not bool(execution.sandbox_enabled):
            return None

        params = self._json_object(execution.input_params)
        binding = params.get("reviewed_executable")
        if not isinstance(binding, dict) or not binding:
            return None
        if (str(binding.get("tenant_id") or "") != str(tenant_id or "")
                or str(binding.get("workspace_id") or "")
                != str(workspace_id or "")
                or str(binding.get("agent_id") or "") != str(agent_id or "")):
            return None

        from core.models import Skill

        linked_skill_id = str(execution.skill_id or "")
        linked = (
            self.db.query(Skill)
            .filter(Skill.id == linked_skill_id)
            .first()
        )
        if linked is None or str(linked.type or "") != "script":
            return None

        skill = self.get_skill(str(execution.id))
        if skill is None:
            return None
        try:
            self._authorize_reviewed_executable(
                skill,
                binding,
                tenant_id=str(tenant_id),
                workspace_id=str(workspace_id),
                agent_id=str(agent_id),
            )
        except ValueError:
            # Changed candidate/code, revoked review, missing binding or a
            # removed workspace assignment: not currently invocable.
            return None

        metadata = self._json_object(params.get("skill_metadata"))
        description = str(
            metadata.get("description")
            or linked.description
            or ""
        ).strip()
        name = str(linked.name or "").strip()
        registry_name = str(params.get("skill_name") or "").strip()
        if not name:
            return None
        return {
            "skill_id": str(execution.id),
            "name": name,
            "registry_name": registry_name,
            "description": description[:500],
            "runtime": "docker",
            "tool": "skills.execute",
            "review_revision": binding.get("review_revision"),
            "review_digest": str(binding.get("review_digest") or ""),
        }

    def list_invocable_skills(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        agent_id: str,
    ) -> List[Dict[str, Any]]:
        """List reviewed executable skills this employee may invoke now.

        Scope is the exact reviewed binding: tenant, workspace and employee.
        A skill unassigned from the workspace, demoted from ``Active``, edited
        after review, or bound to another employee is omitted.  Never raises
        for a single malformed row.
        """
        if not tenant_id or not workspace_id or not agent_id:
            return []
        rows = (
            self.db.query(SkillExecution)
            .filter(
                SkillExecution.skill_source == "community",
                SkillExecution.status == "Active",
                SkillExecution.tenant_id == str(tenant_id),
                SkillExecution.workspace_id == str(workspace_id),
                SkillExecution.sandbox_enabled.is_(True),
            )
            .order_by(SkillExecution.created_at.desc())
            .all()
        )
        entries: List[Dict[str, Any]] = []
        for row in rows:
            try:
                entry = self._invocable_executable_entry(
                    row,
                    tenant_id=str(tenant_id),
                    workspace_id=str(workspace_id),
                    agent_id=str(agent_id),
                )
            except Exception as exc:  # noqa: BLE001 - one bad row is omitted
                logger.debug("invocable skill row skipped: %s", exc)
                continue
            if entry is not None:
                entries.append(entry)
        entries.sort(key=lambda item: item["name"])
        return entries

    def resolve_invocable_skill(
        self,
        identifier: str,
        *,
        tenant_id: str,
        workspace_id: str,
        agent_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Resolve a model-supplied skill name to one authorized entry.

        Accepts the workspace ``Skill.name`` (``summarize_values_r1``), the
        registered package name (``summarize_values``) or the durable
        registry execution id.  Ambiguous identifiers are refused rather than
        guessed.
        """
        wanted = str(identifier or "").strip().casefold()
        if not wanted:
            return None
        matches = [
            entry
            for entry in self.list_invocable_skills(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                agent_id=agent_id,
            )
            if wanted in {
                str(entry.get("name") or "").casefold(),
                str(entry.get("registry_name") or "").casefold(),
                str(entry.get("skill_id") or "").casefold(),
            }
        ]
        if len(matches) != 1:
            return None
        return matches[0]

    async def execute_skill(
        self,
        skill_id: str,
        inputs: Dict[str, Any],
        agent_id: str = "system",
        *,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a community skill with governance checks.

        Extended for Python package support (Phase 35):
        - Extracts packages from skill metadata
        - Checks package permissions using PackageGovernanceService
        - Installs packages in dedicated Docker images using PackageInstaller
        - Executes skills with custom images containing pre-installed packages

        Reviewed executable skills (``input_params.reviewed_executable``) are
        additionally authorized before any execution record exists: the
        caller's tenant/workspace, the supplied employee, the current candidate
        row and the registered SKILL.md must all match the exact review
        revision and digests captured at apply time.

        Args:
            skill_id: Skill ID from import
            inputs: Input parameters for skill execution
            agent_id: Agent ID executing the skill
            tenant_id: Authenticated caller's tenant (reviewed skills only)
            workspace_id: Authenticated caller's workspace (reviewed skills only)
            user_id: Authenticated caller id, for receipts

        Returns:
            Dict with execution result (includes image_tag and packages if applicable)

        Raises:
            ValueError: If skill not found, scope/binding changed, or governance
                check fails
        """
        # Retrieve skill
        skill = self.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        skill_name = skill["skill_name"]
        skill_type = skill["skill_type"]
        status = skill["status"]

        # Reviewed executable skills are authorized against the exact review
        # binding BEFORE a SkillExecution row is created.  A refusal here is
        # therefore a hard request error, not an execution failure receipt.
        # A record that still carries reviewed-executable provenance (package
        # digests / linked Skill binding) but lost the registry binding must
        # not downgrade into the generic community-skill execution path.
        reviewed_binding = skill.get("reviewed_executable")
        reviewed_verified: Optional[Dict[str, Any]] = None
        if not reviewed_binding and self._declares_reviewed_executable(skill):
            raise ValueError(
                "reviewed_executable_not_approved: registry record is missing "
                "the reviewed executable binding")
        if reviewed_binding:
            reviewed_verified = self._authorize_reviewed_executable(
                skill, reviewed_binding,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                agent_id=agent_id,
            )
            if str(status) != "Active":
                raise ValueError(
                    "reviewed_executable_not_approved: registry record is not "
                    f"Active (status {status!r})")

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
            agent_maturity = str(agent_caps.get("maturity_level", "student")).upper()
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
                    # Fail closed: a governance check that errors must NOT let
                    # the package through unvetted (previously logged + continued,
                    # a supply-chain permission bypass).
                    logger.error(f"Package permission check failed for {package_req}: {e}")
                    raise ValueError(
                        f"Package permission check failed for {package_req}; "
                        "execution aborted (fail-closed)"
                    )

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
                        # Fail closed: an errored governance check must not let
                        # the package through unvetted.
                        raise ValueError(
                            f"npm package permission check failed for {pkg_spec}; "
                            "execution aborted (fail-closed)"
                        )

        # Create execution record
        execution_skill_id = f"{skill_name}_{skill_id[:8]}"
        if reviewed_binding:
            linked = str(skill.get("linked_skill_id") or "")
            if not linked:
                raise ValueError(
                    "reviewed_executable_artifact_changed: registry record has "
                    "no linked Skill row")
            execution_skill_id = linked
        execution = SkillExecution(
            agent_id=agent_id,
            skill_id=execution_skill_id,
            tenant_id="system",  # Community skills belong to the system tenant
            workspace_id="default",
            status="running",
            input_params=inputs,
            skill_source="community",
            sandbox_enabled=skill["sandbox_enabled"]
        )
        if reviewed_binding:
            execution.tenant_id = str(tenant_id or "")
            execution.workspace_id = str(workspace_id or "")

        self.db.add(execution)
        self.db.commit()

        start_time = datetime.datetime.now(datetime.timezone.utc)
        error = None
        result = None
        reviewed_receipt: Optional[Dict[str, Any]] = None
        sandbox_receipt: Optional[Dict[str, Any]] = None

        try:
            # Execute based on skill type and package presence
            if reviewed_binding:
                from core.reviewed_executable import (
                    ReviewedExecutableExecutionError,
                )

                try:
                    result, sandbox_receipt = (
                        self._execute_reviewed_executable_skill(
                            skill, inputs, reviewed_binding))
                except ReviewedExecutableExecutionError as exc:
                    sandbox_receipt = exc.receipt or {}
                    reviewed_receipt = self._reviewed_execution_receipt(
                        reviewed_verified or {},
                        inputs=inputs,
                        result=None,
                        sandbox_receipt=sandbox_receipt,
                        user_id=user_id,
                        registry_execution_id=skill_id,
                        error=str(exc),
                    )
                    self._apply_sandbox_receipt(
                        execution, reviewed_receipt, sandbox_receipt)
                    raise
                reviewed_receipt = self._reviewed_execution_receipt(
                    reviewed_verified or {},
                    inputs=inputs,
                    result=result,
                    sandbox_receipt=sandbox_receipt,
                    user_id=user_id,
                    registry_execution_id=skill_id,
                )
                self._apply_sandbox_receipt(
                    execution, reviewed_receipt, sandbox_receipt)
            elif skill_type == "prompt_only":
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
            if reviewed_receipt is not None:
                execution.audit_metadata = {
                    **(execution.audit_metadata or {}),
                    "reviewed_executable": reviewed_receipt,
                }
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

            response = {
                "success": True,
                "result": result,
                "execution_id": execution.id,
                "episode_id": episode_id
            }
            if reviewed_receipt is not None:
                response["reviewed_executable"] = reviewed_receipt
            return response

        except Exception as e:
            error = e
            # Update execution record with error
            execution.status = "failed"
            execution.error_message = str(e)
            if reviewed_receipt is not None:
                execution.audit_metadata = {
                    **(execution.audit_metadata or {}),
                    "reviewed_executable": {
                        **reviewed_receipt,
                        "status": "failed",
                        "error": str(e),
                    },
                }
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

            response = {
                "success": False,
                "error": str(e),
                "execution_id": execution.id,
                "episode_id": episode_id
            }
            if reviewed_receipt is not None:
                response["reviewed_executable"] = {
                    **reviewed_receipt, "status": "failed", "error": str(e)}
            return response

    def _authorize_reviewed_executable(
        self,
        skill: Dict[str, Any],
        binding: Any,
        *,
        tenant_id: Optional[str],
        workspace_id: Optional[str],
        agent_id: str,
    ) -> Dict[str, Any]:
        """Verify the exact reviewed artifact and current caller scope.

        This is authorization, not a best-effort check: any mismatch raises a
        ``ValueError`` before a SkillExecution row is written.  The candidate
        digest is recomputed from the CURRENT row so post-approval edits to
        either the candidate or the registered SKILL.md are refused.
        """
        from core.auto_dev.models import SkillCandidate
        from core.models import AgentRegistry
        from core.reviewed_executable import verify_executable_artifact
        from core.reviewed_improvement import _binding_digest

        if not tenant_id or not workspace_id:
            raise ValueError(
                "reviewed_executable_scope_required: authenticated tenant and "
                "workspace are required for a reviewed executable skill")
        if not agent_id or agent_id == "system":
            raise ValueError(
                "reviewed_executable_workspace_mismatch: a reviewed executable "
                "skill must run as the reviewed employee")
        if not isinstance(binding, dict) or not binding:
            raise ValueError(
                "reviewed_executable_not_approved: executable binding missing")

        candidate_id = str(binding.get("candidate_id") or "")
        candidate = (
            self.db.query(SkillCandidate)
            .filter(
                SkillCandidate.id == candidate_id,
                SkillCandidate.tenant_id == str(tenant_id),
            )
            .populate_existing()
            .first()
        )
        agent = (
            self.db.query(AgentRegistry)
            .filter(
                AgentRegistry.id == str(agent_id),
                AgentRegistry.tenant_id == str(tenant_id),
            )
            .populate_existing()
            .first()
        )
        if (agent is None
                or str(agent.workspace_id or "") != str(workspace_id)):
            raise ValueError(
                "reviewed_executable_workspace_mismatch: employee is not in "
                "the authenticated workspace")

        expected_digest = ""
        if candidate is not None:
            expected_digest = _binding_digest(
                candidate,
                tenant_id=str(tenant_id),
                workspace_id=str(workspace_id),
                agent_id=str(candidate.agent_id or ""),
            )

        code_blocks = self._parser.extract_python_code(
            skill.get("skill_body") or "")
        if len(code_blocks) != 1:
            raise ValueError(
                "reviewed_executable_artifact_changed: registry package must "
                "contain exactly one python block")

        from core.models import Skill

        linked_skill_id = str(skill.get("linked_skill_id") or "")
        linked_skill = (
            self.db.query(Skill)
            .filter(Skill.id == linked_skill_id)
            .first()
        )
        if (linked_skill is None
                or str(linked_skill.type or "") != "script"
                or str(linked_skill.code or "").rstrip("\n")
                != code_blocks[0].rstrip("\n")):
            raise ValueError(
                "reviewed_executable_artifact_changed: linked Skill code/type "
                "differs from the registered artifact")

        linked_binding = self._json_object(linked_skill.config).get(
            "reviewed_executable")
        if not isinstance(linked_binding, dict) or not linked_binding:
            raise ValueError(
                "reviewed_executable_not_approved: linked Skill row has no "
                "executable binding")
        from core.reviewed_executable import canonical_json

        if (canonical_json(linked_binding)
                != canonical_json(binding)):
            raise ValueError(
                "reviewed_executable_artifact_changed: linked Skill binding "
                "differs from the registry binding")

        from core.models import workspace_skills

        assigned = (
            self.db.query(workspace_skills.c.skill_id)
            .filter(
                workspace_skills.c.workspace_id == str(workspace_id),
                workspace_skills.c.skill_id == linked_skill_id,
            )
            .first()
        )
        if assigned is None:
            raise ValueError(
                "reviewed_executable_workspace_mismatch: linked Skill is not "
                "assigned to the authenticated workspace")

        return verify_executable_artifact(
            binding=binding,
            candidate=candidate,
            registered_code=code_blocks[0],
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            agent_id=str(agent_id),
            registry_execution_id=str(skill.get("skill_id") or ""),
            review_digest=expected_digest,
        )

    def _execute_reviewed_executable_skill(
        self,
        skill: Dict[str, Any],
        inputs: Dict[str, Any],
        binding: Dict[str, Any],
    ):
        """Run the reviewed code in the Docker sandbox and prove it ran.

        There is deliberately no subprocess fallback: ``HazardSandbox`` raises
        when Docker is unavailable, and the nonce echo proves the returned
        output came from the container started for this execution.
        """
        from core.reviewed_executable import ReviewedExecutableExecutionError

        if (str(skill.get("skill_type") or "") != "python_code"
                or not skill.get("sandbox_enabled")):
            raise ValueError(
                "reviewed_executable_not_approved: artifact is not a "
                "sandboxed python skill")
        code_blocks = self._parser.extract_python_code(
            skill.get("skill_body") or "")
        if len(code_blocks) != 1:
            raise ValueError(
                "reviewed_executable_artifact_changed: registry package must "
                "contain exactly one python block")
        code = code_blocks[0]
        nonce = uuid.uuid4().hex
        try:
            # Docker initialization is part of the fail-closed boundary: an
            # unreachable daemon must produce an unverified receipt, never a
            # host execution and never a missing receipt.
            sandbox = self._get_sandbox()
            receipt = sandbox.execute_python_receipt(
                code=code,
                inputs=inputs,
                timeout_seconds=30,
                memory_limit="256m",
                cpu_limit=0.5,
                nonce=nonce,
            )
        except TypeError as exc:
            raise ReviewedExecutableExecutionError(
                "reviewed_executable_sandbox_unverified: sandbox cannot "
                f"produce a container receipt ({exc})",
                receipt={
                    "backend": "docker",
                    "ok": False,
                    "error": str(exc),
                    "nonce": nonce,
                },
            ) from exc
        except Exception as exc:  # noqa: BLE001 - surfaces as a failed receipt
            raise ReviewedExecutableExecutionError(
                "reviewed_executable_sandbox_unverified: "
                f"{exc}",
                receipt={
                    "backend": "docker",
                    "ok": False,
                    "error": str(exc),
                    "nonce": nonce,
                },
            ) from exc

        if not isinstance(receipt, dict):
            raise ReviewedExecutableExecutionError(
                "reviewed_executable_sandbox_unverified: malformed receipt",
                receipt={"backend": "docker", "ok": False, "nonce": nonce},
            )
        if not receipt.get("ok"):
            raise ReviewedExecutableExecutionError(
                "reviewed_executable_sandbox_failed: "
                + str(receipt.get("error") or receipt.get("stderr")
                      or "container execution failed"),
                receipt={**receipt, "nonce": nonce},
            )

        stdout = str(receipt.get("stdout") or "")
        lines = stdout.rstrip("\n").split("\n") if stdout else []
        echo = None
        if lines and lines[-1].startswith("__atom_sandbox_nonce__="):
            echo = lines.pop().split("=", 1)[1]
        result = "\n".join(lines)
        if echo != nonce:
            raise ReviewedExecutableExecutionError(
                "reviewed_executable_sandbox_unverified: the container did "
                "not echo this execution's nonce",
                receipt={**receipt, "nonce": nonce},
            )
        receipt["nonce_echo"] = echo
        return result, receipt

    @staticmethod
    def _reviewed_execution_receipt(
        verified: Dict[str, Any],
        *,
        inputs: Dict[str, Any],
        result: Optional[str],
        sandbox_receipt: Optional[Dict[str, Any]],
        user_id: Optional[str],
        registry_execution_id: str,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        from core.reviewed_executable import (
            EXECUTABLE_RECEIPT_SCHEMA,
            canonical_json,
            sha256_text,
        )

        sandbox = sandbox_receipt or {}
        receipt: Dict[str, Any] = {
            "schema": EXECUTABLE_RECEIPT_SCHEMA,
            "status": "failed" if error else "success",
            "binding": verified,
            "registry_execution_id": str(registry_execution_id or ""),
            "executed_by": str(user_id or ""),
            "inputs_sha256": sha256_text(canonical_json(inputs or {})),
            "result_sha256": sha256_text(result or ""),
            "sandbox": {
                "backend": sandbox.get("backend") or "docker",
                "ran": bool(sandbox.get("ok")),
                "container_id": sandbox.get("container_id"),
                "docker_container_id": sandbox.get("docker_container_id"),
                "image": sandbox.get("image"),
                "exit_code": sandbox.get("exit_code"),
                "network_disabled": bool(
                    sandbox.get("network_disabled", False)),
                "read_only": bool(sandbox.get("read_only", False)),
                # ``ephemeral``/``removed``/``cleanup_error`` are the observed
                # cleanup outcome, not an assumption: a leaked container must
                # be visible in the durable receipt.
                "ephemeral": bool(sandbox.get("ephemeral", False)),
                "removed": bool(sandbox.get("removed", False)),
                "timed_out": bool(sandbox.get("timed_out", False)),
                "terminated": bool(sandbox.get("terminated", False)),
                "cleanup_error": sandbox.get("cleanup_error"),
                "nonce": sandbox.get("nonce"),
                "nonce_echo": sandbox.get("nonce_echo"),
            },
        }
        if error:
            receipt["error"] = str(error)
        return receipt

    @staticmethod
    def _apply_sandbox_receipt(
        execution: SkillExecution,
        reviewed_receipt: Dict[str, Any],
        sandbox_receipt: Optional[Dict[str, Any]],
    ) -> None:
        sandbox = sandbox_receipt or {}
        execution.container_id = sandbox.get("container_id")
        execution.stdout = str(sandbox.get("stdout") or "")[:65535]
        execution.stderr = str(sandbox.get("stderr") or "")[:65535]
        execution.exit_code = sandbox.get("exit_code")
        execution.audit_metadata = {
            **(execution.audit_metadata or {}),
            "reviewed_executable": reviewed_receipt,
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
        result = self._get_sandbox().execute_python(code, inputs)

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
        from core.npm_script_analyzer import NpmScriptAnalyzer
        from core.audit_service import audit_service
        from core.sql_validator import SecurityError

        # Step 1: Check governance permissions with audit logging
        logger.info(f"Checking npm governance permissions for {len(node_packages)} packages")

        for pkg in node_packages:
            name, version = self._parse_npm_package(pkg)

            from core.package_governance_service import PackageGovernanceService

            governance = PackageGovernanceService()
            permission = governance.check_package_permission(
                agent_id=agent_id,
                package_name=name,
                version=version,
                package_type="npm",
                db=db
            )

            # Log governance decision to audit trail
            audit_service.create_package_audit(
                db=db,
                agent_id=agent_id,
                agent_execution_id=None,
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
        script_warnings = script_analyzer.analyze_package_scripts(node_packages)

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
        from core.npm_package_installer import NpmPackageInstaller

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
                agent_execution_id=None,
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

    def promote_skill(self, skill_id: str, *, commit: bool = True) -> Dict[str, Any]:
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
        if commit:
            self.db.commit()
        else:
            self.db.flush()

        skill_name = skill.input_params.get("skill_name", "Unknown")
        logger.info(f"Promoted skill '{skill_name}' from {previous_status} to Active")

        return {
            "status": "Active",
            "previous_status": previous_status,
            "message": f"Skill promoted from {previous_status} to Active"
        }

    def delete_skill(self, skill_id: str) -> Dict[str, Any]:
        """
        Delete a community skill from the registry.

        Removes the SkillExecution record (and any related execution history)
        for the given community skill. Skills imported from the marketplace
        (skill_source='cloud') are not managed by this registry and are skipped.

        Args:
            skill_id: Skill ID to delete

        Returns:
            Dict with deletion confirmation

        Raises:
            ValueError: If skill not found

        Example:
            result = service.delete_skill("abc-123-def")
            # {"skill_id": "abc-123-def", "skill_name": "My Skill", "deleted": True}
        """
        skill = self.db.query(SkillExecution).filter(
            SkillExecution.id == skill_id,
            SkillExecution.skill_source == "community"
        ).first()

        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        skill_name = skill.input_params.get("skill_name", "Unknown")

        self.db.delete(skill)
        self.db.commit()

        logger.info(f"Deleted community skill '{skill_name}' ({skill_id})")

        return {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "deleted": True,
            "message": f"Skill '{skill_name}' deleted successfully"
        }
