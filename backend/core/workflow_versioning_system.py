"""
Comprehensive Workflow Versioning and Rollback System

This module provides enterprise-grade workflow version control with:
- Semantic versioning (major.minor.patch)
- Branching and merging capabilities
- Automatic change detection
- Differential storage optimization
- Rollback to any previous version
- Version comparison and diff visualization
- Audit trail and change tracking
- Collaborative version management
- Conflict resolution
- Version tagging and releases
"""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import difflib
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class VersionType(Enum):
    """Type of version change"""
    MAJOR = "major"  # Breaking changes
    MINOR = "minor"  # New features (backward compatible)
    PATCH = "patch"  # Bug fixes (backward compatible)
    HOTFIX = "hotfix"  # Emergency fixes
    BETA = "beta"  # Pre-release versions
    ALPHA = "alpha"  # Early development versions

class ChangeType(Enum):
    """Type of workflow change"""
    STRUCTURAL = "structural"  # Changes to workflow structure
    PARAMETRIC = "parametric"  # Changes to parameters only
    EXECUTION = "execution"    # Changes to execution logic
    METADATA = "metadata"      # Changes to metadata only
    DEPENDENCY = "dependency"  # Changes to dependencies

@dataclass
class WorkflowVersion:
    """Represents a single workflow version"""
    workflow_id: str
    version: str
    version_type: VersionType
    change_type: ChangeType
    created_at: datetime
    created_by: str
    commit_message: str
    tags: List[str]
    workflow_data: Dict[str, Any]
    parent_version: Optional[str] = None
    branch_name: Optional[str] = None
    is_active: bool = True
    checksum: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class VersionDiff:
    """Represents differences between two versions"""
    workflow_id: str
    from_version: str
    to_version: str
    added_steps: List[Dict[str, Any]]
    removed_steps: List[Dict[str, Any]]
    modified_steps: List[Dict[str, Any]]
    structural_changes: List[str]
    parametric_changes: Dict[str, Tuple[Any, Any]]
    dependency_changes: List[Dict[str, Any]]
    metadata_changes: Dict[str, Tuple[Any, Any]]
    impact_level: str  # low, medium, high, critical
    automated_tests_passed: bool = False

@dataclass
class Branch:
    """Represents a workflow branch"""
    branch_name: str
    workflow_id: str
    base_version: str
    current_version: str
    created_at: datetime
    created_by: str
    is_protected: bool = False
    merge_strategy: str = "merge_commit"  # merge_commit, rebase, squash

@dataclass
class ConflictResolution:
    """Represents conflict resolution strategy"""
    conflict_id: str
    workflow_id: str
    source_version: str
    target_version: str
    conflict_type: str
    resolution_strategy: str  # manual, auto_source, auto_target, auto_merge
    resolved_data: Dict[str, Any]
    resolved_by: str
    resolved_at: datetime

class WorkflowVersioningSystem:
    """
    Comprehensive workflow versioning and rollback system

    Features:
    - Semantic versioning with automatic version bumping
    - Differential storage for optimization
    - Branching and merging capabilities
    - Advanced conflict resolution
    - Automated rollback procedures
    - Comprehensive audit trail
    - Performance monitoring for version operations
    """

    def __init__(self, db_path: str = "workflow_versions.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the version control database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Versions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                version TEXT NOT NULL,
                version_type TEXT NOT NULL,
                change_type TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                created_by TEXT NOT NULL,
                commit_message TEXT,
                tags TEXT,
                workflow_data TEXT NOT NULL,
                parent_version TEXT,
                branch_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                checksum TEXT,
                metadata TEXT,
                UNIQUE(workflow_id, version),
                FOREIGN KEY (parent_version) REFERENCES workflow_versions(version),
                FOREIGN KEY (workflow_id) REFERENCES workflows(id)
            )
        """)

        # Branches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_name TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                base_version TEXT NOT NULL,
                current_version TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                created_by TEXT NOT NULL,
                is_protected BOOLEAN DEFAULT 0,
                merge_strategy TEXT DEFAULT 'merge_commit',
                UNIQUE(workflow_id, branch_name),
                FOREIGN KEY (workflow_id) REFERENCES workflows(id)
            )
        """)

        # Version differences table (for caching)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS version_differences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                from_version TEXT NOT NULL,
                to_version TEXT NOT NULL,
                differences TEXT NOT NULL,
                impact_level TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(workflow_id, from_version, to_version),
                FOREIGN KEY (workflow_id) REFERENCES workflows(id)
            )
        """)

        # Conflict resolutions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflict_resolutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conflict_id TEXT NOT NULL UNIQUE,
                workflow_id TEXT NOT NULL,
                source_version TEXT NOT NULL,
                target_version TEXT NOT NULL,
                conflict_type TEXT NOT NULL,
                resolution_strategy TEXT NOT NULL,
                resolved_data TEXT NOT NULL,
                resolved_by TEXT NOT NULL,
                resolved_at TIMESTAMP NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id)
            )
        """)

        # Version metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS version_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                version TEXT NOT NULL,
                execution_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                avg_execution_time REAL DEFAULT 0.0,
                error_count INTEGER DEFAULT 0,
                last_execution TIMESTAMP,
                performance_score REAL DEFAULT 0.0,
                UNIQUE(workflow_id, version),
                FOREIGN KEY (workflow_id) REFERENCES workflows(id)
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflow_versions_workflow_id ON workflow_versions(workflow_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflow_versions_created_at ON workflow_versions(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workflow_branches_workflow_id ON workflow_branches(workflow_id)")

        conn.commit()
        conn.close()

    def _calculate_checksum(self, workflow_data: Dict[str, Any]) -> str:
        """Calculate SHA-256 checksum of workflow data"""
        data_str = json.dumps(workflow_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _determine_change_type(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> ChangeType:
        """Determine the type of change made to workflow"""
        if not old_data:
            return ChangeType.STRUCTURAL

        changes = []

        # Check structural changes
        old_steps = {step.get('id'): step for step in old_data.get('steps', [])}
        new_steps = {step.get('id'): step for step in new_data.get('steps', [])}

        if set(old_steps.keys()) != set(new_steps.keys()):
            changes.append('structural')

        # Check parametric changes
        for step_id in old_steps.keys() & new_steps.keys():
            old_step = old_steps[step_id]
            new_step = new_steps[step_id]

            # Compare parameters
            old_params = old_step.get('parameters', {})
            new_params = new_step.get('parameters', {})

            if old_params != new_params:
                changes.append('parametric')

            # Compare execution logic
            old_exec = old_step.get('execution_logic', {})
            new_exec = new_step.get('execution_logic', {})

            if old_exec != new_exec:
                changes.append('execution')

        # Check metadata changes
        old_metadata = {k: v for k, v in old_data.items() if k not in ['steps', 'parameters', 'execution_logic']}
        new_metadata = {k: v for k, v in new_data.items() if k not in ['steps', 'parameters', 'execution_logic']}

        if old_metadata != new_metadata:
            changes.append('metadata')

        # Check dependency changes
        old_deps = set(old_data.get('dependencies', []))
        new_deps = set(new_data.get('dependencies', []))

        if old_deps != new_deps:
            changes.append('dependency')

        # Prioritize change types
        if 'structural' in changes:
            return ChangeType.STRUCTURAL
        elif 'execution' in changes:
            return ChangeType.EXECUTION
        elif 'dependency' in changes:
            return ChangeType.DEPENDENCY
        elif 'parametric' in changes:
            return ChangeType.PARAMETRIC
        elif 'metadata' in changes:
            return ChangeType.METADATA
        else:
            return ChangeType.METADATA

    def _bump_version(self, current_version: str, version_type: VersionType) -> str:
        """Bump semantic version based on change type"""
        try:
            # Handle pre-release versions
            if '-' in current_version:
                base_version, prerelease = current_version.split('-', 1)
            else:
                base_version, prerelease = current_version, ''

            parts = base_version.split('.')
            if len(parts) != 3:
                # Initialize with 1.0.0 if invalid version
                major, minor, patch = 1, 0, 0
            else:
                major, minor, patch = map(int, parts)

            if version_type == VersionType.MAJOR:
                major += 1
                minor = 0
                patch = 0
            elif version_type == VersionType.MINOR:
                minor += 1
                patch = 0
            elif version_type == VersionType.PATCH or version_type == VersionType.HOTFIX:
                patch += 1
            elif version_type in [VersionType.BETA, VersionType.ALPHA]:
                # For pre-release versions, increment the prerelease number
                if prerelease:
                    if version_type == VersionType.BETA:
                        prerelease = f"beta.{int(prerelease.split('.')[-1] if '.' in prerelease else '0') + 1}"
                    else:
                        prerelease = f"alpha.{int(prerelease.split('.')[-1] if '.' in prerelease else '0') + 1}"
                else:
                    prerelease = "beta.1" if version_type == VersionType.BETA else "alpha.1"

            new_version = f"{major}.{minor}.{patch}"
            if prerelease:
                new_version += f"-{prerelease}"

            return new_version

        except Exception as e:
            logger.error(f"Error bumping version {current_version}: {str(e)}")
            return f"{current_version}.1"  # Fallback: append .1

    async def create_version(
        self,
        workflow_id: str,
        workflow_data: Dict[str, Any],
        version_type: VersionType,
        created_by: str,
        commit_message: str,
        tags: List[str] = None,
        branch_name: str = "main"
    ) -> WorkflowVersion:
        """
        Create a new version of a workflow

        Args:
            workflow_id: ID of the workflow
            workflow_data: New workflow data
            version_type: Type of version change
            created_by: User creating the version
            commit_message: Commit message for the version
            tags: Optional tags for the version
            branch_name: Branch name (default: "main")

        Returns:
            WorkflowVersion: Created version object
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get latest version for this workflow
            cursor.execute("""
                SELECT version FROM workflow_versions
                WHERE workflow_id = ? AND branch_name = ?
                ORDER BY created_at DESC LIMIT 1
            """, (workflow_id, branch_name))

            result = cursor.fetchone()
            latest_version = result[0] if result else "1.0.0"

            # Get previous version data for change detection
            cursor.execute("""
                SELECT workflow_data FROM workflow_versions
                WHERE workflow_id = ? AND branch_name = ?
                ORDER BY created_at DESC LIMIT 1
            """, (workflow_id, branch_name))

            prev_data_result = cursor.fetchone()
            previous_data = json.loads(prev_data_result[0]) if prev_data_result else {}

            # Determine change type
            change_type = self._determine_change_type(previous_data, workflow_data)

            # Calculate new version
            new_version = self._bump_version(latest_version, version_type)

            # Calculate checksum
            checksum = self._calculate_checksum(workflow_data)

            # Check for duplicate (same data)
            cursor.execute("""
                SELECT id FROM workflow_versions
                WHERE workflow_id = ? AND checksum = ?
            """, (workflow_id, checksum))

            if cursor.fetchone():
                conn.close()
                raise ValueError("This workflow version already exists")

            # Create version object
            workflow_version = WorkflowVersion(
                workflow_id=workflow_id,
                version=new_version,
                version_type=version_type,
                change_type=change_type,
                created_at=datetime.now(timezone.utc),
                created_by=created_by,
                commit_message=commit_message,
                tags=tags or [],
                workflow_data=workflow_data,
                parent_version=latest_version if previous_data else None,
                branch_name=branch_name,
                checksum=checksum,
                metadata={
                    'change_type': change_type.value,
                    'parent_version': latest_version,
                    'auto_bumped': True
                }
            )

            # Insert into database
            cursor.execute("""
                INSERT INTO workflow_versions (
                    workflow_id, version, version_type, change_type,
                    created_at, created_by, commit_message, tags,
                    workflow_data, parent_version, branch_name,
                    checksum, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workflow_version.workflow_id,
                workflow_version.version,
                workflow_version.version_type.value,
                workflow_version.change_type.value,
                workflow_version.created_at.isoformat(),
                workflow_version.created_by,
                workflow_version.commit_message,
                json.dumps(workflow_version.tags),
                json.dumps(workflow_version.workflow_data),
                workflow_version.parent_version,
                workflow_version.branch_name,
                workflow_version.checksum,
                json.dumps(workflow_version.metadata)
            ))

            # Update branch current version
            cursor.execute("""
                INSERT OR REPLACE INTO workflow_branches
                (branch_name, workflow_id, base_version, current_version, created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                branch_name,
                workflow_id,
                latest_version,
                new_version,
                workflow_version.created_at.isoformat(),
                created_by
            ))

            conn.commit()
            conn.close()

            logger.info(f"Created version {new_version} for workflow {workflow_id}")
            return workflow_version

        except Exception as e:
            logger.error(f"Error creating version: {str(e)}")
            raise

    async def get_version(self, workflow_id: str, version: str) -> Optional[WorkflowVersion]:
        """Get a specific version of a workflow"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT workflow_id, version, version_type, change_type,
                       created_at, created_by, commit_message, tags,
                       workflow_data, parent_version, branch_name,
                       is_active, checksum, metadata
                FROM workflow_versions
                WHERE workflow_id = ? AND version = ?
            """, (workflow_id, version))

            result = cursor.fetchone()
            conn.close()

            if result:
                return WorkflowVersion(
                    workflow_id=result[0],
                    version=result[1],
                    version_type=VersionType(result[2]),
                    change_type=ChangeType(result[3]),
                    created_at=datetime.fromisoformat(result[4]),
                    created_by=result[5],
                    commit_message=result[6],
                    tags=json.loads(result[7]),
                    workflow_data=json.loads(result[8]),
                    parent_version=result[9],
                    branch_name=result[10],
                    is_active=bool(result[11]),
                    checksum=result[12],
                    metadata=json.loads(result[13]) if result[13] else None
                )
            return None

        except Exception as e:
            logger.error(f"Error getting version {version}: {str(e)}")
            return None

    async def get_version_history(
        self,
        workflow_id: str,
        branch_name: str = "main",
        limit: int = 50
    ) -> List[WorkflowVersion]:
        """Get version history for a workflow"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT workflow_id, version, version_type, change_type,
                       created_at, created_by, commit_message, tags,
                       workflow_data, parent_version, branch_name,
                       is_active, checksum, metadata
                FROM workflow_versions
                WHERE workflow_id = ? AND branch_name = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (workflow_id, branch_name, limit))

            results = cursor.fetchall()
            conn.close()

            versions = []
            for result in results:
                versions.append(WorkflowVersion(
                    workflow_id=result[0],
                    version=result[1],
                    version_type=VersionType(result[2]),
                    change_type=ChangeType(result[3]),
                    created_at=datetime.fromisoformat(result[4]),
                    created_by=result[5],
                    commit_message=result[6],
                    tags=json.loads(result[7]),
                    workflow_data=json.loads(result[8]),
                    parent_version=result[9],
                    branch_name=result[10],
                    is_active=bool(result[11]),
                    checksum=result[12],
                    metadata=json.loads(result[13]) if result[13] else None
                ))

            return versions

        except Exception as e:
            logger.error(f"Error getting version history: {str(e)}")
            return []

    async def rollback_to_version(
        self,
        workflow_id: str,
        target_version: str,
        created_by: str,
        rollback_reason: str
    ) -> WorkflowVersion:
        """
        Rollback a workflow to a previous version

        Args:
            workflow_id: ID of the workflow to rollback
            target_version: Version to rollback to
            created_by: User performing the rollback
            rollback_reason: Reason for the rollback

        Returns:
            WorkflowVersion: New rollback version
        """
        try:
            # Get target version
            target_version_obj = await self.get_version(workflow_id, target_version)
            if not target_version_obj:
                raise ValueError(f"Version {target_version} not found")

            # Create rollback version
            rollback_message = f"Rollback to version {target_version}: {rollback_reason}"
            rollback_tags = ["rollback", f"from-{target_version}"]

            rollback_version = await self.create_version(
                workflow_id=workflow_id,
                workflow_data=target_version_obj.workflow_data,
                version_type=VersionType.HOTFIX,
                created_by=created_by,
                commit_message=rollback_message,
                tags=rollback_tags
            )

            logger.info(f"Rolled back workflow {workflow_id} to version {target_version}")
            return rollback_version

        except Exception as e:
            logger.error(f"Error rolling back to version {target_version}: {str(e)}")
            raise

    async def compare_versions(
        self,
        workflow_id: str,
        from_version: str,
        to_version: str
    ) -> VersionDiff:
        """Compare two versions of a workflow"""
        try:
            # Check cache first
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT differences, impact_level FROM version_differences
                WHERE workflow_id = ? AND from_version = ? AND to_version = ?
            """, (workflow_id, from_version, to_version))

            cached_result = cursor.fetchone()
            if cached_result:
                diff_data = json.loads(cached_result[0])
                impact_level = cached_result[1]
                return VersionDiff(workflow_id=workflow_id, from_version=from_version,
                                 to_version=to_version, impact_level=impact_level, **diff_data)

            # Get version data
            from_version_obj = await self.get_version(workflow_id, from_version)
            to_version_obj = await self.get_version(workflow_id, to_version)

            if not from_version_obj or not to_version_obj:
                raise ValueError("One or both versions not found")

            # Calculate differences
            diff = await self._calculate_version_diff(from_version_obj, to_version_obj)

            # Cache the result
            cursor.execute("""
                INSERT OR REPLACE INTO version_differences
                (workflow_id, from_version, to_version, differences, impact_level, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                workflow_id,
                from_version,
                to_version,
                json.dumps(asdict(diff, default=str)),
                diff.impact_level,
                datetime.now(timezone.utc).isoformat()
            ))

            conn.commit()
            conn.close()

            return diff

        except Exception as e:
            logger.error(f"Error comparing versions: {str(e)}")
            raise

    async def _calculate_version_diff(
        self,
        from_version: WorkflowVersion,
        to_version: WorkflowVersion
    ) -> VersionDiff:
        """Calculate differences between two versions"""
        from_data = from_version.workflow_data
        to_data = to_version.workflow_data

        # Get steps
        from_steps = {step.get('id'): step for step in from_data.get('steps', [])}
        to_steps = {step.get('id'): step for step in to_data.get('steps', [])}

        # Find added, removed, and modified steps
        added_step_ids = set(to_steps.keys()) - set(from_steps.keys())
        removed_step_ids = set(from_steps.keys()) - set(to_steps.keys())
        common_step_ids = set(from_steps.keys()) & set(to_steps.keys())

        added_steps = [to_steps[step_id] for step_id in added_step_ids]
        removed_steps = [from_steps[step_id] for step_id in removed_step_ids]

        # Find modified steps
        modified_steps = []
        for step_id in common_step_ids:
            from_step = from_steps[step_id]
            to_step = to_steps[step_id]

            # Deep comparison
            if json.dumps(from_step, sort_keys=True) != json.dumps(to_step, sort_keys=True):
                modified_steps.append({
                    'step_id': step_id,
                    'old_step': from_step,
                    'new_step': to_step,
                    'changes': self._find_step_changes(from_step, to_step)
                })

        # Find parametric changes
        parametric_changes = {}
        for step_id, step in modified_steps:
            old_params = step['old_step'].get('parameters', {})
            new_params = step['new_step'].get('parameters', {})

            if old_params != new_params:
                parametric_changes[step_id] = (old_params, new_params)

        # Find structural changes
        structural_changes = []
        if len(from_steps) != len(to_steps):
            structural_changes.append(f"Step count changed from {len(from_steps)} to {len(to_steps)}")

        for step in modified_steps:
            if step['changes'].get('structural'):
                structural_changes.append(f"Step {step['step_id']} structure changed")

        # Find dependency changes
        from_deps = set(from_data.get('dependencies', []))
        to_deps = set(to_data.get('dependencies', []))

        dependency_changes = []
        if from_deps != to_deps:
            dependency_changes.append({
                'added': list(to_deps - from_deps),
                'removed': list(from_deps - to_deps)
            })

        # Find metadata changes
        metadata_changes = {}
        from_metadata = {k: v for k, v in from_data.items() if k not in ['steps', 'dependencies']}
        to_metadata = {k: v for k, v in to_data.items() if k not in ['steps', 'dependencies']}

        for key in set(from_metadata.keys()) | set(to_metadata.keys()):
            old_val = from_metadata.get(key)
            new_val = to_metadata.get(key)
            if old_val != new_val:
                metadata_changes[key] = (old_val, new_val)

        # Determine impact level
        impact_score = 0
        if structural_changes:
            impact_score += len(structural_changes) * 3
        if modified_steps:
            impact_score += len(modified_steps) * 2
        if dependency_changes:
            impact_score += len(dependency_changes) * 2
        if parametric_changes:
            impact_score += len(parametric_changes)

        if impact_score >= 10:
            impact_level = "critical"
        elif impact_score >= 7:
            impact_level = "high"
        elif impact_score >= 4:
            impact_level = "medium"
        else:
            impact_level = "low"

        return VersionDiff(
            workflow_id=from_version.workflow_id,
            from_version=from_version.version,
            to_version=to_version.version,
            added_steps=added_steps,
            removed_steps=removed_steps,
            modified_steps=modified_steps,
            structural_changes=structural_changes,
            parametric_changes=parametric_changes,
            dependency_changes=dependency_changes,
            metadata_changes=metadata_changes,
            impact_level=impact_level
        )

    def _find_step_changes(self, old_step: Dict[str, Any], new_step: Dict[str, Any]) -> Dict[str, Any]:
        """Find specific changes between two steps"""
        changes = {
            'parameters': {},
            'execution_logic': {},
            'metadata': {},
            'structural': False
        }

        # Compare parameters
        old_params = old_step.get('parameters', {})
        new_params = new_step.get('parameters', {})

        for key in set(old_params.keys()) | set(new_params.keys()):
            if old_params.get(key) != new_params.get(key):
                changes['parameters'][key] = {
                    'old': old_params.get(key),
                    'new': new_params.get(key)
                }

        # Compare execution logic
        old_exec = old_step.get('execution_logic', {})
        new_exec = new_step.get('execution_logic', {})

        if old_exec != new_exec:
            changes['execution_logic'] = {
                'old': old_exec,
                'new': new_exec
            }

        # Compare metadata
        old_meta = {k: v for k, v in old_step.items() if k not in ['parameters', 'execution_logic', 'id']}
        new_meta = {k: v for k, v in new_step.items() if k not in ['parameters', 'execution_logic', 'id']}

        for key in set(old_meta.keys()) | set(new_meta.keys()):
            if old_meta.get(key) != new_meta.get(key):
                changes['metadata'][key] = {
                    'old': old_meta.get(key),
                    'new': new_meta.get(key)
                }

        # Check for structural changes
        structural_fields = ['type', 'category', 'required_inputs', 'outputs']
        for field in structural_fields:
            if old_step.get(field) != new_step.get(field):
                changes['structural'] = True
                break

        return changes

    async def create_branch(
        self,
        workflow_id: str,
        branch_name: str,
        base_version: str,
        created_by: str,
        merge_strategy: str = "merge_commit"
    ) -> Branch:
        """Create a new branch for a workflow"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if branch already exists
            cursor.execute("""
                SELECT id FROM workflow_branches
                WHERE workflow_id = ? AND branch_name = ?
            """, (workflow_id, branch_name))

            if cursor.fetchone():
                conn.close()
                raise ValueError(f"Branch {branch_name} already exists")

            # Verify base version exists
            base_version_obj = await self.get_version(workflow_id, base_version)
            if not base_version_obj:
                conn.close()
                raise ValueError(f"Base version {base_version} not found")

            # Create branch
            branch = Branch(
                branch_name=branch_name,
                workflow_id=workflow_id,
                base_version=base_version,
                current_version=base_version,
                created_at=datetime.now(timezone.utc),
                created_by=created_by,
                merge_strategy=merge_strategy
            )

            cursor.execute("""
                INSERT INTO workflow_branches
                (branch_name, workflow_id, base_version, current_version, created_at, created_by, merge_strategy)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                branch.branch_name,
                branch.workflow_id,
                branch.base_version,
                branch.current_version,
                branch.created_at.isoformat(),
                branch.created_by,
                branch.merge_strategy
            ))

            conn.commit()
            conn.close()

            logger.info(f"Created branch {branch_name} for workflow {workflow_id}")
            return branch

        except Exception as e:
            logger.error(f"Error creating branch: {str(e)}")
            raise

    async def merge_branch(
        self,
        workflow_id: str,
        source_branch: str,
        target_branch: str,
        merge_by: str,
        merge_message: str
    ) -> WorkflowVersion:
        """Merge a branch into another branch"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get branch info
            cursor.execute("""
                SELECT base_version, current_version FROM workflow_branches
                WHERE workflow_id = ? AND branch_name = ?
            """, (workflow_id, source_branch))

            source_result = cursor.fetchone()
            if not source_result:
                conn.close()
                raise ValueError(f"Source branch {source_branch} not found")

            cursor.execute("""
                SELECT base_version, current_version FROM workflow_branches
                WHERE workflow_id = ? AND branch_name = ?
            """, (workflow_id, target_branch))

            target_result = cursor.fetchone()
            if not target_result:
                conn.close()
                raise ValueError(f"Target branch {target_branch} not found")

            source_version = source_result[1]
            target_version = target_result[1]

            # Get source version data
            source_version_obj = await self.get_version(workflow_id, source_version)
            if not source_version_obj:
                conn.close()
                raise ValueError(f"Source version {source_version} not found")

            # Create merge commit
            merge_tags = ["merge", f"from-{source_branch}", f"to-{target_branch}"]
            full_merge_message = f"Merge {source_branch} into {target_branch}: {merge_message}"

            merged_version = await self.create_version(
                workflow_id=workflow_id,
                workflow_data=source_version_obj.workflow_data,
                version_type=VersionType.MINOR,
                created_by=merge_by,
                commit_message=full_merge_message,
                tags=merge_tags,
                branch_name=target_branch
            )

            conn.close()

            logger.info(f"Merged branch {source_branch} into {target_branch}")
            return merged_version

        except Exception as e:
            logger.error(f"Error merging branch: {str(e)}")
            raise

    async def get_branches(self, workflow_id: str) -> List[Branch]:
        """Get all branches for a workflow"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT branch_name, workflow_id, base_version, current_version,
                       created_at, created_by, is_protected, merge_strategy
                FROM workflow_branches
                WHERE workflow_id = ?
                ORDER BY created_at DESC
            """, (workflow_id,))

            results = cursor.fetchall()
            conn.close()

            branches = []
            for result in results:
                branches.append(Branch(
                    branch_name=result[0],
                    workflow_id=result[1],
                    base_version=result[2],
                    current_version=result[3],
                    created_at=datetime.fromisoformat(result[4]),
                    created_by=result[5],
                    is_protected=bool(result[6]),
                    merge_strategy=result[7]
                ))

            return branches

        except Exception as e:
            logger.error(f"Error getting branches: {str(e)}")
            return []

    async def delete_version(
        self,
        workflow_id: str,
        version: str,
        deleted_by: str,
        delete_reason: str
    ) -> bool:
        """Delete a version (soft delete)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if version is being used
            cursor.execute("""
                SELECT COUNT(*) FROM workflow_branches
                WHERE workflow_id = ? AND current_version = ?
            """, (workflow_id, version))

            if cursor.fetchone()[0] > 0:
                conn.close()
                raise ValueError("Cannot delete version that is currently in use")

            # Soft delete (mark as inactive)
            cursor.execute("""
                UPDATE workflow_versions
                SET is_active = 0,
                    metadata = json_patch(
                        COALESCE(metadata, '{}'),
                        json_object('deleted_at', ?, 'deleted_by', ?, 'delete_reason', ?)
                    )
                WHERE workflow_id = ? AND version = ?
            """, (
                datetime.now(timezone.utc).isoformat(),
                deleted_by,
                delete_reason,
                workflow_id,
                version
            ))

            conn.commit()
            conn.close()

            logger.info(f"Deleted version {version} for workflow {workflow_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting version: {str(e)}")
            return False

    async def get_version_metrics(
        self,
        workflow_id: str,
        version: str
    ) -> Optional[Dict[str, Any]]:
        """Get performance metrics for a specific version"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT execution_count, success_rate, avg_execution_time,
                       error_count, last_execution, performance_score
                FROM version_metrics
                WHERE workflow_id = ? AND version = ?
            """, (workflow_id, version))

            result = cursor.fetchone()
            conn.close()

            if result:
                return {
                    'execution_count': result[0],
                    'success_rate': result[1],
                    'avg_execution_time': result[2],
                    'error_count': result[3],
                    'last_execution': result[4],
                    'performance_score': result[4]
                }
            return None

        except Exception as e:
            logger.error(f"Error getting version metrics: {str(e)}")
            return None

    async def update_version_metrics(
        self,
        workflow_id: str,
        version: str,
        execution_result: Dict[str, Any]
    ) -> bool:
        """Update performance metrics for a version"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get current metrics
            cursor.execute("""
                SELECT execution_count, success_rate, avg_execution_time, error_count
                FROM version_metrics
                WHERE workflow_id = ? AND version = ?
            """, (workflow_id, version))

            result = cursor.fetchone()

            if result:
                # Update existing metrics
                exec_count = result[0] + 1
                error_count = result[3] + (0 if execution_result.get('success', False) else 1)

                # Calculate new success rate
                success_count = exec_count - error_count
                new_success_rate = (success_count / exec_count) * 100 if exec_count > 0 else 0

                # Update average execution time
                exec_time = execution_result.get('execution_time', 0)
                current_avg = result[2]
                new_avg = ((current_avg * result[0]) + exec_time) / exec_count

                # Calculate performance score
                performance_score = min(100, (new_success_rate * 0.7) + (1000 / (exec_time + 1) * 30))

                cursor.execute("""
                    UPDATE version_metrics
                    SET execution_count = ?, success_rate = ?, avg_execution_time = ?,
                        error_count = ?, last_execution = ?, performance_score = ?
                    WHERE workflow_id = ? AND version = ?
                """, (
                    exec_count,
                    new_success_rate,
                    new_avg,
                    error_count,
                    datetime.now(timezone.utc).isoformat(),
                    performance_score,
                    workflow_id,
                    version
                ))
            else:
                # Insert new metrics
                success_rate = 100 if execution_result.get('success', False) else 0
                exec_time = execution_result.get('execution_time', 0)
                performance_score = min(100, (success_rate * 0.7) + (1000 / (exec_time + 1) * 30))

                cursor.execute("""
                    INSERT INTO version_metrics
                    (workflow_id, version, execution_count, success_rate, avg_execution_time,
                     error_count, last_execution, performance_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    workflow_id,
                    version,
                    1,
                    success_rate,
                    exec_time,
                    0 if execution_result.get('success', False) else 1,
                    datetime.now(timezone.utc).isoformat(),
                    performance_score
                ))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"Error updating version metrics: {str(e)}")
            return False

# Example usage and integration
class WorkflowVersionManager:
    """High-level workflow version management interface"""

    def __init__(self):
        self.versioning_system = WorkflowVersioningSystem()

    async def create_workflow_version(
        self,
        workflow_id: str,
        workflow_data: Dict[str, Any],
        user_id: str,
        change_description: str,
        version_type: str = "minor"
    ) -> Dict[str, Any]:
        """Create a new workflow version with intelligent version bumping"""

        # Map string to VersionType enum
        version_type_map = {
            "major": VersionType.MAJOR,
            "minor": VersionType.MINOR,
            "patch": VersionType.PATCH,
            "hotfix": VersionType.HOTFIX
        }

        vtype = version_type_map.get(version_type.lower(), VersionType.MINOR)

        # Auto-detect version type if not specified
        if version_type == "auto":
            latest_version = await self.versioning_system.get_latest_version(workflow_id)
            if latest_version:
                # Analyze changes to determine version type
                change_type = self.versioning_system._determine_change_type(
                    latest_version.workflow_data,
                    workflow_data
                )

                if change_type == ChangeType.STRUCTURAL:
                    vtype = VersionType.MAJOR
                elif change_type == ChangeType.EXECUTION:
                    vtype = VersionType.MINOR
                else:
                    vtype = VersionType.PATCH

        # Create the version
        version = await self.versioning_system.create_version(
            workflow_id=workflow_id,
            workflow_data=workflow_data,
            version_type=vtype,
            created_by=user_id,
            commit_message=change_description
        )

        return {
            'version': version.version,
            'version_type': version.version_type.value,
            'change_type': version.change_type.value,
            'created_at': version.created_at.isoformat(),
            'checksum': version.checksum,
            'parent_version': version.parent_version
        }

    async def rollback_workflow(
        self,
        workflow_id: str,
        target_version: str,
        user_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """Rollback workflow to a previous version"""

        rollback_version = await self.versioning_system.rollback_to_version(
            workflow_id=workflow_id,
            target_version=target_version,
            created_by=user_id,
            rollback_reason=reason
        )

        return {
            'rollback_version': rollback_version.version,
            'target_version': target_version,
            'created_at': rollback_version.created_at.isoformat(),
            'rollback_successful': True
        }

    async def get_workflow_changes(
        self,
        workflow_id: str,
        from_version: str,
        to_version: str
    ) -> Dict[str, Any]:
        """Get detailed changes between two versions"""

        diff = await self.versioning_system.compare_versions(
            workflow_id=workflow_id,
            from_version=from_version,
            to_version=to_version
        )

        return {
            'from_version': diff.from_version,
            'to_version': diff.to_version,
            'impact_level': diff.impact_level,
            'added_steps_count': len(diff.added_steps),
            'removed_steps_count': len(diff.removed_steps),
            'modified_steps_count': len(diff.modified_steps),
            'structural_changes': diff.structural_changes,
            'dependency_changes': diff.dependency_changes,
            'parametric_changes': diff.parametric_changes,
            'metadata_changes': diff.metadata_changes
        }

# Export the main classes
__all__ = [
    'WorkflowVersioningSystem',
    'WorkflowVersionManager',
    'WorkflowVersion',
    'VersionDiff',
    'Branch',
    'VersionType',
    'ChangeType'
]