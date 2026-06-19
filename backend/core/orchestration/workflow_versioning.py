"""
Workflow Versioning and Migration

Based on 2025-2026 research:
- Enterprise Agent Workflows (Medium.com)
- AgentOrchestra patterns

Implements:
- Workflow versioning
- Schema evolution
- Migration strategies
- Version compatibility
"""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Configuration
# ============================================================================

class VersionIncrement(Enum):
    """Types of version increments"""
    MAJOR = "major"  # Breaking changes
    MINOR = "minor"  # New features, backward compatible
    PATCH = "patch"  # Bug fixes


class MigrationStrategy(Enum):
    """Strategies for migrating between versions"""
    AUTOMATIC = "automatic"  # Fully automated migration
    MANUAL = "manual"  # Requires manual intervention
    HYBRID = "hybrid"  # Semi-automated with manual checkpoints
    ROLLBACK = "rollback"  # Rollback on failure


class CompatibilityStatus(Enum):
    """Compatibility status between versions"""
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass
class VersioningConfig:
    """Configuration for workflow versioning"""
    # Versioning
    auto_increment: bool = True
    versioning_scheme: str = "semantic"  # semantic, sequential, date-based

    # Storage
    max_versions_per_workflow: int = 10
    archive_deleted_versions: bool = True

    # Migration
    default_migration_strategy: MigrationStrategy = MigrationStrategy.HYBRID
    migration_timeout_seconds: int = 300

    # Validation
    validate_on_migration: bool = True
    rollback_on_validation_failure: bool = True


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class WorkflowVersion:
    """Version of a workflow"""
    version_id: str = ""
    workflow_id: str = ""
    version: str = "1.0.0"  # Semantic version

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    description: str = ""

    # Schema
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    step_schema: Dict[str, Any] = field(default_factory=dict)

    # Changes
    changelog: List[str] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)

    # Status
    is_latest: bool = True
    deprecated: bool = False
    deprecated_at: Optional[datetime] = None

    # Compatibility
    compatible_with: List[str] = field(default_factory=list)  # Version ranges
    incompatible_with: List[str] = field(default_factory=list)

    # Migration
    migration_required: bool = False
    migration_script: Optional[str] = None

    def is_compatible_with(self, other_version: str) -> bool:
        """Check if this version is compatible with another"""
        if other_version in self.compatible_with:
            return True
        if other_version in self.incompatible_with:
            return False

        # Check major version compatibility (semantic versioning)
        try:
            my_major = int(self.version.split(".")[0])
            other_major = int(other_version.split(".")[0])
            return my_major == other_major
        except (ValueError, IndexError):
            return True

    def get_major_minor(self) -> Tuple[int, int]:
        """Get major and minor version numbers"""
        try:
            parts = self.version.split(".")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 1, 0


@dataclass
class VersionSchema:
    """Schema definition for workflow version"""
    schema_id: str = ""
    version: str = "1.0.0"

    # Input/output definitions
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)

    # Step definitions
    step_schemas: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


@dataclass
class MigrationPlan:
    """Plan for migrating between workflow versions"""
    migration_id: str = ""
    from_version: str = ""
    to_version: str = ""

    # Strategy
    strategy: MigrationStrategy = MigrationStrategy.HYBRID

    # Steps
    steps: List[str] = field(default_factory=list)

    # Validation
    pre_validation_check: Optional[str] = None
    post_validation_check: Optional[str] = None
    rollback_plan: Optional[str] = None

    # Execution
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class VersionedWorkflow:
    """A workflow with versioning support"""
    workflow_id: str = ""
    name: str = ""
    description: str = ""

    # Versions
    current_version: str = "1.0.0"
    versions: Dict[str, WorkflowVersion] = field(default_factory=dict)

    # Schema
    schemas: Dict[str, VersionSchema] = field(default_factory=dict)

    # Migration
    migration_plans: Dict[Tuple[str, str], MigrationPlan] = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


# ============================================================================
# Workflow Versioning Manager
# ============================================================================

class WorkflowVersioning:
    """
    Manages workflow versioning and migration.

    Features:
    - Version creation and management
    - Schema evolution
    - Migration planning and execution
    - Compatibility checking
    """

    def __init__(self, config: Optional[VersioningConfig] = None):
        self.config = config or VersioningConfig()

        # Storage
        self._workflows: Dict[str, VersionedWorkflow] = {}
        self._version_history: List[WorkflowVersion] = []

    def create_workflow(
        self,
        workflow_id: str,
        name: str,
        description: str,
        version: str = "1.0.0",
        creator: str = "system"
    ) -> VersionedWorkflow:
        """Create a new versioned workflow"""
        workflow = VersionedWorkflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            current_version=version,
            created_at=datetime.now()
        )

        # Store workflow first
        self._workflows[workflow_id] = workflow

        # Create initial version
        self.add_version(
            workflow_id=workflow_id,
            version=version,
            input_schema={},
            output_schema={},
            step_schema={},
            created_by=creator
        )

        logger.info(f"Created versioned workflow: {workflow_id} v{version}")
        return workflow

    def add_version(
        self,
        workflow_id: str,
        version: str,
        input_schema: Dict[str, Any],
        output_schema: Dict[str, Any],
        step_schema: Dict[str, Any],
        increment_type: VersionIncrement = VersionIncrement.MINOR,
        changelog: Optional[List[str]] = None,
        breaking_changes: Optional[List[str]] = None,
        created_by: str = "system"
    ) -> WorkflowVersion:
        """Add a new version to a workflow"""
        if workflow_id not in self._workflows:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self._workflows[workflow_id]

        version_id = f"{workflow_id}_v_{version.replace('.', '_')}"

        # Create version
        wf_version = WorkflowVersion(
            version_id=version_id,
            workflow_id=workflow_id,
            version=version,
            input_schema=input_schema,
            output_schema=output_schema,
            step_schema=step_schema,
            changelog=changelog or [],
            breaking_changes=breaking_changes or [],
            created_by=created_by
        )

        # Add to workflow
        workflow.versions[version] = wf_version
        workflow.current_version = version
        workflow.updated_at = datetime.now()

        # Update other versions' latest status
        for v in workflow.versions.values():
            if v.version != version:
                v.is_latest = False
        wf_version.is_latest = True

        # Update schema
        schema = VersionSchema(
            schema_id=f"schema_{version_id}",
            version=version,
            input_schema=input_schema,
            output_schema=output_schema,
            step_schemas={"default": step_schema}
        )
        workflow.schemas[version] = schema

        self._version_history.append(wf_version)

        logger.info(f"Added version {version} to workflow {workflow_id}")
        return wf_version

    def get_version(self, workflow_id: str, version: str) -> Optional[WorkflowVersion]:
        """Get a specific version of a workflow"""
        if workflow_id not in self._workflows:
            return None
        return self._workflows[workflow_id].versions.get(version)

    def get_latest_version(self, workflow_id: str) -> Optional[WorkflowVersion]:
        """Get latest version of a workflow"""
        if workflow_id not in self._workflows:
            return None
        version = self._workflows[workflow_id].current_version
        return self._workflows[workflow_id].versions.get(version)

    def list_versions(self, workflow_id: str) -> List[WorkflowVersion]:
        """List all versions of a workflow"""
        if workflow_id not in self._workflows:
            return []

        versions = list(self._workflows[workflow_id].versions.values())
        versions.sort(key=lambda v: [int(x) for x in v.version.split(".")], reverse=True)
        return versions

    def deprecate_version(
        self,
        workflow_id: str,
        version: str,
        notice: Optional[str] = None
    ) -> bool:
        """Deprecate a workflow version"""
        wf_version = self.get_version(workflow_id, version)
        if not wf_version:
            return False

        wf_version.deprecated = True
        wf_version.deprecated_at = datetime.now()

        logger.info(f"Deprecated version {version} of workflow {workflow_id}")
        return True

    def create_migration_plan(
        self,
        workflow_id: str,
        from_version: str,
        to_version: str,
        strategy: MigrationStrategy = MigrationStrategy.HYBRID
    ) -> MigrationPlan:
        """Create a migration plan between versions"""
        migration_id = f"mig_{workflow_id}_{from_version}_to_{to_version}"

        # Get versions
        from_ver = self.get_version(workflow_id, from_version)
        to_ver = self.get_version(workflow_id, to_version)

        if not from_ver or not to_ver:
            raise ValueError(f"One or both versions not found")

        # Build migration steps based on schema differences
        steps = self._build_migration_steps(from_ver, to_ver)

        plan = MigrationPlan(
            migration_id=migration_id,
            from_version=from_version,
            to_version=to_version,
            strategy=strategy,
            steps=steps
        )

        # Store plan
        key = (from_version, to_version)
        if workflow_id not in self._workflows:
            self._workflows[workflow_id] = VersionedWorkflow(
                workflow_id=workflow_id,
                name=workflow_id,
                description="Auto-created for migration"
            )
        self._workflows[workflow_id].migration_plans[key] = plan

        logger.info(f"Created migration plan: {migration_id}")
        return plan

    def _build_migration_steps(
        self,
        from_ver: WorkflowVersion,
        to_ver: WorkflowVersion
    ) -> List[str]:
        """Build migration steps based on schema differences"""
        steps = []

        # Check for breaking changes
        if to_ver.breaking_changes:
            steps.append(f"Address breaking changes: {', '.join(to_ver.breaking_changes)}")

        # Check for schema changes
        if from_ver.input_schema != to_ver.input_schema:
            steps.append("Update input data to match new schema")

        if from_ver.output_schema != to_ver.output_schema:
            steps.append("Update output data consumers for new schema")

        if from_ver.step_schema != to_ver.step_schema:
            steps.append("Update step configurations")

        # Check for new required parameters
        from_params = set(from_ver.input_schema.get("properties", {}).keys())
        to_params = set(to_ver.input_schema.get("properties", {}).keys())

        new_params = to_params - from_params
        if new_params:
            steps.append(f"Provide new parameters: {', '.join(new_params)}")

        # Add validation step
        steps.append("Validate migrated workflow")

        return steps

    async def execute_migration(
        self,
        workflow_id: str,
        migration_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Execute a migration plan"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False

        # Find migration plan
        plan = None
        for key, plan_candidate in workflow.migration_plans.items():
            if plan_candidate.migration_id == migration_id:
                plan = plan_candidate
                break

        if not plan:
            logger.error(f"Migration plan {migration_id} not found")
            return False

        plan.status = "running"
        plan.started_at = datetime.now()

        try:
            # Execute steps
            for step in plan.steps:
                logger.info(f"Executing migration step: {step}")
                # In production, actual migration logic here
                await asyncio.sleep(0.1)

            plan.status = "completed"
            plan.completed_at = datetime.now()

            logger.info(f"Migration {migration_id} completed")
            return True

        except Exception as e:
            logger.error(f"Migration {migration_id} failed: {e}")
            plan.status = "failed"
            plan.error = str(e)

            # Rollback if configured
            if self.config.rollback_on_validation_failure:
                return await self._rollback_migration(workflow_id, migration_id)

            return False

    async def _rollback_migration(
        self,
        workflow_id: str,
        migration_id: str
    ) -> bool:
        """Rollback a failed migration"""
        # In production, execute rollback plan
        logger.info(f"Rolling back migration {migration_id}")
        return True

    def check_compatibility(
        self,
        workflow_id: str,
        from_version: str,
        to_version: str
    ) -> CompatibilityStatus:
        """Check compatibility between versions"""
        from_ver = self.get_version(workflow_id, from_version)
        to_ver = self.get_version(workflow_id, to_version)

        if not from_ver or not to_ver:
            return CompatibilityStatus.UNKNOWN

        # Check if to_version lists from_version as incompatible
        if from_version in to_ver.incompatible_with:
            return CompatibilityStatus.INCOMPATIBLE

        # Check if to_version lists from_version as compatible
        if from_version in to_ver.compatible_with:
            return CompatibilityStatus.COMPATIBLE

        # Check major versions
        try:
            from_major = int(from_version.split(".")[0])
            to_major = int(to_version.split(".")[0])

            if from_major != to_major:
                return CompatibilityStatus.INCOMPATIBLE
        except (ValueError, IndexError):
            pass

        return CompatibilityStatus.UNKNOWN

    def increment_version(
        self,
        workflow_id: str,
        increment: VersionIncrement = VersionIncrement.PATCH
    ) -> str:
        """Increment workflow version"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        current = workflow.current_version
        parts = current.split(".")

        if increment == VersionIncrement.MAJOR:
            new_version = f"{int(parts[0]) + 1}.0.0"
        elif increment == VersionIncrement.MINOR:
            new_version = f"{parts[0]}.{int(parts[1]) + 1}.0"
        else:  # PATCH
            new_version = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

        logger.info(f"Incremented version: {current} -> {new_version}")
        return new_version

    def get_statistics(self) -> Dict[str, Any]:
        """Get versioning statistics"""
        total_versions = sum(len(w.versions) for w in self._workflows.values())

        return {
            "total_workflows": len(self._workflows),
            "total_versions": total_versions,
            "migration_plans": sum(len(w.migration_plans) for w in self._workflows.values()),
            "config": {
                "auto_increment": self.config.auto_increment,
                "max_versions": self.config.max_versions_per_workflow
            }
        }


# ============================================================================
# Factory
# ============================================================================

_versioning_instance: Optional[WorkflowVersioning] = None


def get_workflow_versioning(config: Optional[VersioningConfig] = None) -> WorkflowVersioning:
    """Get or create workflow versioning instance"""
    global _versioning_instance
    if _versioning_instance is None:
        _versioning_instance = WorkflowVersioning(config)
    return _versioning_instance


# Import asyncio for async operations
import asyncio
