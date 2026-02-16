"""
Skill Registry Service - Manage imported community skills.

Provides import workflow, security scanning, and lifecycle management
for OpenClaw community skills with governance integration.

Reference: Phase 14 Plan 03 - Skills Registry & Security
"""

import datetime
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import SkillExecution
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

    def import_skill(
        self,
        source: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Import a community skill from various sources.

        Args:
            source: Import source - "github_url", "file_upload", or "raw_content"
            content: SKILL.md content or file content
            metadata: Optional metadata (author, tags, etc.)

        Returns:
            Dict with:
                - skill_id: str - Unique identifier for imported skill
                - scan_result: Dict - Security scan results
                - status: str - "Untrusted" or "Active"
                - metadata: Dict - Skill metadata

        Example:
            result = service.import_skill(
                source="raw_content",
                content="---\\nname: Calculator\\n---\\n...",
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

            # Detect skill type
            skill_type = self._parser._detect_skill_type(skill_metadata, skill_body)
            skill_metadata['skill_type'] = skill_type

            # Merge metadata
            skill_metadata.update(metadata)

            skill_name = skill_metadata.get("name", "Unnamed Skill")
            skill_type = skill_metadata.get("skill_type", "prompt_only")

            logger.info(f"Parsed skill '{skill_name}' (type: {skill_type})")

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
                    "skill_body": skill_body
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

    def execute_skill(
        self,
        skill_id: str,
        inputs: Dict[str, Any],
        agent_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Execute a community skill with governance checks.

        Args:
            skill_id: Skill ID from import
            inputs: Input parameters for skill execution
            agent_id: Agent ID executing the skill

        Returns:
            Dict with execution result

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

        # Governance check: Verify agent maturity
        # Community skills default to INTERN maturity requirement
        agent = self._governance.get_agent(agent_id)
        if not agent:
            logger.warning(f"Agent not found: {agent_id}, executing as system")
        else:
            agent_maturity = agent.get("maturity_level", "STUDENT")
            if agent_maturity == "STUDENT" and skill_type == "python_code":
                raise ValueError(
                    f"STUDENT agents cannot execute Python skills. "
                    f"Agent '{agent_id}' needs INTERN+ maturity for skill '{skill_name}'"
                )

        logger.info(f"Executing skill '{skill_name}' (type: {skill_type}, status: {status})")

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

        try:
            # Execute based on skill type
            if skill_type == "prompt_only":
                result = self._execute_prompt_skill(skill, inputs)
            elif skill_type == "python_code":
                result = self._execute_python_skill(skill, inputs)
            else:
                raise ValueError(f"Unknown skill type: {skill_type}")

            # Update execution record
            execution.status = "completed"
            execution.output_result = {"result": result}
            execution.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()

            return {
                "success": True,
                "result": result,
                "execution_id": execution.id
            }

        except Exception as e:
            # Update execution record with error
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()

            logger.error(f"Skill execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "execution_id": execution.id
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
