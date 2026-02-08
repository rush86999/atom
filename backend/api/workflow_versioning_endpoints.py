"""
Workflow Versioning API Endpoints

RESTful API endpoints for workflow versioning and rollback functionality.
Provides comprehensive version control capabilities including:
- Version creation and management
- Rollback operations
- Version comparison and diff
- Branch management
- Version history and metrics
- Conflict resolution
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import Depends, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.workflow_versioning_system import (
    Branch,
    ChangeType,
    VersionDiff,
    VersionType,
    WorkflowVersion,
    WorkflowVersioningSystem,
    WorkflowVersionManager,
)
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.models import User

logger = logging.getLogger(__name__)

# Initialize router
router = BaseAPIRouter(prefix="/api/v1/workflows", tags=["workflow-versioning"])

# Initialize versioning systems
versioning_system = WorkflowVersioningSystem()
version_manager = WorkflowVersionManager()

# Pydantic models for API requests/responses
class VersionCreateRequest(BaseModel):
    """Request model for creating a new version"""
    version_type: str = Field(..., description="Type of version change", pattern="^(major|minor|patch|hotfix|auto)$")
    commit_message: str = Field(..., description="Commit message for the version")
    tags: Optional[List[str]] = Field(None, description="Optional tags for the version")
    branch_name: str = Field("main", description="Branch name (default: main)")

class VersionResponse(BaseModel):
    """Response model for workflow version"""
    workflow_id: str
    version: str
    version_type: str
    change_type: str
    created_at: str
    created_by: str
    commit_message: str
    tags: List[str]
    parent_version: Optional[str]
    branch_name: str
    checksum: Optional[str]
    is_active: bool

class VersionDiffResponse(BaseModel):
    """Response model for version comparison"""
    workflow_id: str
    from_version: str
    to_version: str
    impact_level: str
    added_steps_count: int
    removed_steps_count: int
    modified_steps_count: int
    structural_changes: List[str]
    dependency_changes: List[Dict[str, Any]]
    parametric_changes: Dict[str, Any]
    metadata_changes: Dict[str, Any]

class RollbackRequest(BaseModel):
    """Request model for rollback operation"""
    target_version: str = Field(..., description="Version to rollback to")
    rollback_reason: str = Field(..., description="Reason for the rollback")

class BranchCreateRequest(BaseModel):
    """Request model for creating a branch"""
    branch_name: str = Field(..., description="Name of the new branch")
    base_version: str = Field(..., description="Base version for the branch")
    merge_strategy: str = Field("merge_commit", description="Merge strategy")

class BranchResponse(BaseModel):
    """Response model for branch information"""
    branch_name: str
    workflow_id: str
    base_version: str
    current_version: str
    created_at: str
    created_by: str
    is_protected: bool
    merge_strategy: str

class MergeRequest(BaseModel):
    """Request model for branch merging"""
    source_branch: str = Field(..., description="Source branch to merge")
    target_branch: str = Field(..., description="Target branch to merge into")
    merge_message: str = Field(..., description="Message for the merge commit")

# Utility functions
# get_current_user is now imported from core.security_dependencies as get_current_active_user


async def get_workflow_data(workflow_id: str) -> Dict[str, Any]:
    """Get current workflow data from workflows.json"""
    try:
        # Load workflows from JSON file
        workflows_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "workflows.json"
        )

        if not os.path.exists(workflows_file):
            logger.warning(f"Workflows file not found: {workflows_file}")
            return {
                "steps": [],
                "parameters": {},
                "dependencies": [],
                "metadata": {}
            }

        import json
        with open(workflows_file, 'r') as f:
            workflows = json.load(f)

        # Find the workflow by ID
        workflow = next((w for w in workflows if w.get('id') == workflow_id), None)

        if not workflow:
            logger.warning(f"Workflow {workflow_id} not found in workflows.json")
            return {
                "steps": [],
                "parameters": {},
                "dependencies": [],
                "metadata": {}
            }

        # Extract workflow data
        steps = workflow.get("steps", [])
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", [])

        # Convert nodes to steps if needed
        if not steps and nodes:
            steps = []
            for i, node in enumerate(nodes):
                config = node.get("config", {})
                step = {
                    "id": node["id"],
                    "name": node.get("title", node["id"]),
                    "sequence_order": i + 1,
                    "service": config.get("service", "default"),
                    "action": config.get("action", "default"),
                    "parameters": config.get("parameters", {}),
                    "type": node.get("type", "action")
                }
                steps.append(step)

        return {
            "steps": steps,
            "parameters": workflow.get("parameters", {}),
            "dependencies": [],
            "metadata": {
                "name": workflow.get("name", ""),
                "description": workflow.get("description", ""),
                "category": workflow.get("category", ""),
                "nodes": nodes,
                "connections": connections,
                "created_at": workflow.get("created_at", ""),
                "updated_at": workflow.get("updated_at", "")
            }
        }

    except Exception as e:
        logger.error(f"Error loading workflow data for {workflow_id}: {e}")
        return {
            "steps": [],
            "parameters": {},
            "dependencies": [],
            "metadata": {}
        }

# Version Management Endpoints

@router.post("/{workflow_id}/versions", response_model=VersionResponse)
async def create_workflow_version(
    workflow_id: str = Path(..., description="ID of the workflow"),
    request: VersionCreateRequest = ...,
    user: User = Depends(get_current_user)
):
    """
    Create a new version of a workflow

    This endpoint creates a new version with automatic version bumping
    based on the change type and workflow analysis.
    """
    try:
        # Get current workflow data
        workflow_data = await get_workflow_data(workflow_id)

        # Create version using version manager
        version_result = await version_manager.create_workflow_version(
            workflow_id=workflow_id,
            workflow_data=workflow_data,
            user_id=user.id,
            change_description=request.commit_message,
            version_type=request.version_type
        )

        # Get full version details
        version = await versioning_system.get_version(workflow_id, version_result['version'])
        if not version:
            raise router.internal_error("Failed to retrieve created version", details={"workflow_id": workflow_id})

        return VersionResponse(
            workflow_id=version.workflow_id,
            version=version.version,
            version_type=version.version_type.value,
            change_type=version.change_type.value,
            created_at=version.created_at.isoformat(),
            created_by=version.created_by,
            commit_message=version.commit_message,
            tags=version.tags,
            parent_version=version.parent_version,
            branch_name=version.branch_name,
            checksum=version.checksum,
            is_active=version.is_active
        )

    except Exception as e:
        logger.error(f"Error creating version for workflow {workflow_id}: {str(e)}")
        raise router.internal_error(str(e))

@router.get("/{workflow_id}/versions", response_model=List[VersionResponse])
async def get_workflow_versions(
    workflow_id: str = Path(..., description="ID of the workflow"),
    branch_name: str = Query("main", description="Branch name"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of versions to return"),
    user: User = Depends(get_current_user)
):
    """
    Get version history for a workflow

    Returns a list of versions for the specified workflow and branch,
    ordered by creation date (newest first).
    """
    try:
        versions = await versioning_system.get_version_history(
            workflow_id=workflow_id,
            branch_name=branch_name,
            limit=limit
        )

        return [
            VersionResponse(
                workflow_id=v.workflow_id,
                version=v.version,
                version_type=v.version_type.value,
                change_type=v.change_type.value,
                created_at=v.created_at.isoformat(),
                created_by=v.created_by,
                commit_message=v.commit_message,
                tags=v.tags,
                parent_version=v.parent_version,
                branch_name=v.branch_name,
                checksum=v.checksum,
                is_active=v.is_active
            )
            for v in versions
        ]

    except Exception as e:
        logger.error(f"Error getting versions for workflow {workflow_id}: {str(e)}")
        raise router.internal_error(str(e))

@router.get("/{workflow_id}/versions/{version}", response_model=VersionResponse)
async def get_workflow_version(
    workflow_id: str = Path(..., description="ID of the workflow"),
    version: str = Path(..., description="Version number"),
    user: User = Depends(get_current_user)
):
    """Get a specific version of a workflow"""
    try:
        version_obj = await versioning_system.get_version(workflow_id, version)
        if not version_obj:
            raise router.not_found_error("Version", version)

        return VersionResponse(
            workflow_id=version_obj.workflow_id,
            version=version_obj.version,
            version_type=version_obj.version_type.value,
            change_type=version_obj.change_type.value,
            created_at=version_obj.created_at.isoformat(),
            created_by=version_obj.created_by,
            commit_message=version_obj.commit_message,
            tags=version_obj.tags,
            parent_version=version_obj.parent_version,
            branch_name=version_obj.branch_name,
            checksum=version_obj.checksum,
            is_active=version_obj.is_active
        )

    except Exception as e:
        logger.error(f"Error getting version {version} for workflow {workflow_id}: {str(e)}")
        if "not found" in str(e).lower():
            raise router.not_found_error("Version", version)
        raise router.internal_error(str(e))

@router.get("/{workflow_id}/versions/{version}/data")
async def get_workflow_version_data(
    workflow_id: str = Path(..., description="ID of the workflow"),
    version: str = Path(..., description="Version number"),
    user: User = Depends(get_current_user)
):
    """Get the workflow data for a specific version"""
    try:
        version_obj = await versioning_system.get_version(workflow_id, version)
        if not version_obj:
            raise router.not_found_error("Version", version)

        return router.success_response(
            data={
                "workflow_id": version_obj.workflow_id,
                "version": version_obj.version,
                "workflow_data": version_obj.workflow_data,
                "metadata": version_obj.metadata,
                "checksum": version_obj.checksum
            }
        )

    except Exception as e:
        logger.error(f"Error getting version data {version} for workflow {workflow_id}: {str(e)}")
        if "not found" in str(e).lower():
            raise
        raise router.internal_error(str(e))

@router.post("/{workflow_id}/rollback")
async def rollback_workflow(
    workflow_id: str = Path(..., description="ID of the workflow"),
    request: RollbackRequest = ...,
    user: User = Depends(get_current_user)
):
    """
    Rollback a workflow to a previous version

    Creates a new rollback version that restores the workflow state
    to the specified target version.
    """
    try:
        # Verify target version exists
        target_version = await versioning_system.get_version(workflow_id, request.target_version)
        if not target_version:
            raise router.not_found_error("Target version", request.target_version)

        # Perform rollback
        rollback_result = await version_manager.rollback_workflow(
            workflow_id=workflow_id,
            target_version=request.target_version,
            user_id=user.id,
            reason=request.rollback_reason
        )

        return router.success_response(
            data={
                "rollback_version": rollback_result['rollback_version'],
                "target_version": rollback_result['target_version'],
                "created_at": rollback_result['created_at']
            },
            message=f"Successfully rolled back to version {request.target_version}"
        )

    except Exception as e:
        logger.error(f"Error rolling back workflow {workflow_id}: {str(e)}")
        if "not found" in str(e).lower():
            raise
        raise router.internal_error(str(e))

@router.get("/{workflow_id}/versions/compare", response_model=VersionDiffResponse)
async def compare_workflow_versions(
    workflow_id: str = Path(..., description="ID of the workflow"),
    from_version: str = Query(..., description="Source version"),
    to_version: str = Query(..., description="Target version"),
    user: User = Depends(get_current_user)
):
    """
    Compare two versions of a workflow

    Returns detailed differences between two versions including
    structural changes, parameter changes, and impact assessment.
    """
    try:
        # Verify both versions exist
        from_version_obj = await versioning_system.get_version(workflow_id, from_version)
        to_version_obj = await versioning_system.get_version(workflow_id, to_version)

        if not from_version_obj:
            raise router.not_found_error("Source version", from_version)
        if not to_version_obj:
            raise router.not_found_error("Target version", to_version)

        # Compare versions
        changes = await version_manager.get_workflow_changes(
            workflow_id=workflow_id,
            from_version=from_version,
            to_version=to_version
        )

        return VersionDiffResponse(
            workflow_id=workflow_id,
            from_version=changes['from_version'],
            to_version=changes['to_version'],
            impact_level=changes['impact_level'],
            added_steps_count=changes['added_steps_count'],
            removed_steps_count=changes['removed_steps_count'],
            modified_steps_count=changes['modified_steps_count'],
            structural_changes=changes['structural_changes'],
            dependency_changes=changes['dependency_changes'],
            parametric_changes=changes['parametric_changes'],
            metadata_changes=changes['metadata_changes']
        )

    except Exception as e:
        logger.error(f"Error comparing versions for workflow {workflow_id}: {str(e)}")
        if "not found" in str(e).lower():
            raise
        raise router.internal_error(str(e))

@router.delete("/{workflow_id}/versions/{version}")
async def delete_workflow_version(
    workflow_id: str = Path(..., description="ID of the workflow"),
    version: str = Path(..., description="Version to delete"),
    delete_reason: str = Query(..., description="Reason for deletion"),
    user: User = Depends(get_current_user)
):
    """
    Delete a workflow version (soft delete)

    Marks a version as inactive rather than permanently deleting it.
    Versions currently in use cannot be deleted.
    """
    try:
        success = await versioning_system.delete_version(
            workflow_id=workflow_id,
            version=version,
            deleted_by=user.id,
            delete_reason=delete_reason
        )

        if not success:
            raise router.validation_error("version", "Failed to delete version")

        return router.success_response(
            data={"deleted_at": datetime.now().isoformat()},
            message=f"Version {version} marked as deleted"
        )

    except Exception as e:
        logger.error(f"Error deleting version {version} for workflow {workflow_id}: {str(e)}")
        if "validation" in str(e).lower():
            raise
        raise router.internal_error(str(e))

# Branch Management Endpoints

@router.post("/{workflow_id}/branches", response_model=BranchResponse)
async def create_workflow_branch(
    workflow_id: str = Path(..., description="ID of the workflow"),
    request: BranchCreateRequest = ...,
    user: User = Depends(get_current_user)
):
    """Create a new branch for a workflow"""
    try:
        branch = await versioning_system.create_branch(
            workflow_id=workflow_id,
            branch_name=request.branch_name,
            base_version=request.base_version,
            created_by=user.id,
            merge_strategy=request.merge_strategy
        )

        return BranchResponse(
            branch_name=branch.branch_name,
            workflow_id=branch.workflow_id,
            base_version=branch.base_version,
            current_version=branch.current_version,
            created_at=branch.created_at.isoformat(),
            created_by=branch.created_by,
            is_protected=branch.is_protected,
            merge_strategy=branch.merge_strategy
        )

    except Exception as e:
        logger.error(f"Error creating branch for workflow {workflow_id}: {str(e)}")
        raise router.internal_error(str(e))

@router.get("/{workflow_id}/branches", response_model=List[BranchResponse])
async def get_workflow_branches(
    workflow_id: str = Path(..., description="ID of the workflow"),
    user: User = Depends(get_current_user)
):
    """Get all branches for a workflow"""
    try:
        branches = await versioning_system.get_branches(workflow_id)

        return [
            BranchResponse(
                branch_name=branch.branch_name,
                workflow_id=branch.workflow_id,
                base_version=branch.base_version,
                current_version=branch.current_version,
                created_at=branch.created_at.isoformat(),
                created_by=branch.created_by,
                is_protected=branch.is_protected,
                merge_strategy=branch.merge_strategy
            )
            for branch in branches
        ]

    except Exception as e:
        logger.error(f"Error getting branches for workflow {workflow_id}: {str(e)}")
        raise router.internal_error(str(e))

@router.post("/{workflow_id}/branches/merge")
async def merge_workflow_branch(
    workflow_id: str = Path(..., description="ID of the workflow"),
    request: MergeRequest = ...,
    user: User = Depends(get_current_user)
):
    """
    Merge a branch into another branch

    Performs a branch merge operation with conflict detection
    and resolution capabilities.
    """
    try:
        merged_version = await versioning_system.merge_branch(
            workflow_id=workflow_id,
            source_branch=request.source_branch,
            target_branch=request.target_branch,
            merge_by=user.id,
            merge_message=request.merge_message
        )

        return router.success_response(
            data={
                "merged_version": merged_version.version,
                "merge_timestamp": merged_version.created_at.isoformat()
            },
            message=f"Successfully merged {request.source_branch} into {request.target_branch}"
        )

    except Exception as e:
        logger.error(f"Error merging branches for workflow {workflow_id}: {str(e)}")
        raise router.internal_error(str(e))

# Version Metrics and Analytics Endpoints

@router.get("/{workflow_id}/versions/{version}/metrics")
async def get_version_metrics(
    workflow_id: str = Path(..., description="ID of the workflow"),
    version: str = Path(..., description="Version number"),
    user: User = Depends(get_current_user)
):
    """Get performance metrics for a specific version"""
    try:
        metrics = await versioning_system.get_version_metrics(workflow_id, version)
        if not metrics:
            return router.success_response(
                data={
                    "workflow_id": workflow_id,
                    "version": version,
                    "metrics": {}
                },
                message="No metrics available for this version"
            )

        return router.success_response(
            data={
                "workflow_id": workflow_id,
                "version": version,
                "metrics": metrics
            }
        )

    except Exception as e:
        logger.error(f"Error getting metrics for version {version}: {str(e)}")
        raise router.internal_error(str(e))

@router.post("/{workflow_id}/versions/{version}/metrics")
async def update_version_metrics(
    workflow_id: str = Path(..., description="ID of the workflow"),
    version: str = Path(..., description="Version number"),
    execution_result: Dict[str, Any] = ...,
    user: User = Depends(get_current_user)
):
    """
    Update performance metrics for a version

    This endpoint is typically called automatically after workflow execution
    to track performance trends over time.
    """
    try:
        success = await versioning_system.update_version_metrics(
            workflow_id=workflow_id,
            version=version,
            execution_result=execution_result
        )

        if success:
            return router.success_response(message="Metrics updated successfully")
        else:
            return router.success_response(message="Failed to update metrics")

    except Exception as e:
        logger.error(f"Error updating metrics for version {version}: {str(e)}")
        raise router.internal_error(str(e))

# Utility Endpoints

@router.get("/{workflow_id}/versions/latest")
async def get_latest_version(
    workflow_id: str = Path(..., description="ID of the workflow"),
    branch_name: str = Query("main", description="Branch name"),
    user: User = Depends(get_current_user)
):
    """Get the latest version of a workflow"""
    try:
        versions = await versioning_system.get_version_history(
            workflow_id=workflow_id,
            branch_name=branch_name,
            limit=1
        )

        if not versions:
            raise router.not_found_error("Version", "latest")

        latest_version = versions[0]

        return VersionResponse(
            workflow_id=latest_version.workflow_id,
            version=latest_version.version,
            version_type=latest_version.version_type.value,
            change_type=latest_version.change_type.value,
            created_at=latest_version.created_at.isoformat(),
            created_by=latest_version.created_by,
            commit_message=latest_version.commit_message,
            tags=latest_version.tags,
            parent_version=latest_version.parent_version,
            branch_name=latest_version.branch_name,
            checksum=latest_version.checksum,
            is_active=latest_version.is_active
        )

    except Exception as e:
        logger.error(f"Error getting latest version for workflow {workflow_id}: {str(e)}")
        if "not found" in str(e).lower():
            raise
        raise router.internal_error(str(e))

@router.get("/{workflow_id}/versions/summary")
async def get_version_summary(
    workflow_id: str = Path(..., description="ID of the workflow"),
    branch_name: str = Query("main", description="Branch name"),
    user: User = Depends(get_current_user)
):
    """Get a summary of all versions for a workflow"""
    try:
        versions = await versioning_system.get_version_history(
            workflow_id=workflow_id,
            branch_name=branch_name,
            limit=100
        )

        # Calculate summary statistics
        total_versions = len(versions)
        version_types = {}
        change_types = {}
        creators = set()

        for version in versions:
            # Count version types
            vtype = version.version_type.value
            version_types[vtype] = version_types.get(vtype, 0) + 1

            # Count change types
            ctype = version.change_type.value
            change_types[ctype] = change_types.get(ctype, 0) + 1

            # Track unique creators
            creators.add(version.created_by)

        return router.success_response(
            data={
                "workflow_id": workflow_id,
                "branch_name": branch_name,
                "total_versions": total_versions,
                "version_types": version_types,
                "change_types": change_types,
                "unique_contributors": len(creators),
                "latest_version": versions[0].version if versions else None,
                "oldest_version": versions[-1].version if versions else None,
                "date_range": {
                    "first_created": versions[-1].created_at.isoformat() if versions else None,
                    "last_created": versions[0].created_at.isoformat() if versions else None
                }
            }
        )

    except Exception as e:
        logger.error(f"Error getting version summary for workflow {workflow_id}: {str(e)}")
        raise router.internal_error(str(e))

# Health check endpoint
@router.get("/versioning/health")
async def health_check():
    """Health check for the versioning system"""
    try:
        # Test database connection
        # This is a simple health check - in production, you might want more comprehensive checks
        return router.success_response(
            data={
                "versioning_system": "operational"
            },
            message="Versioning system is healthy"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise router.internal_error("Versioning system unavailable", status_code=503)

# Export router for inclusion in main app
__all__ = ["router"]