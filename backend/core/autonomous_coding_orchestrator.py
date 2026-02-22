"""
Autonomous Coding Orchestrator

Coordinates all 7 specialized autonomous coding agents through the complete SDLC:
- RequirementParserService: Parse natural language into structured requirements
- CodebaseResearchService: Research existing codebase and conflicts
- PlanningAgent: Create implementation plan
- CodeGeneratorOrchestrator: Generate source code
- TestGeneratorService: Generate comprehensive tests
- TestRunnerService: Run tests and fix failures
- DocumenterAgent: Generate documentation
- CommitterAgent: Create commits and PRs

Features:
- Checkpoint/rollback system with Git commits
- Pause/resume with human feedback
- Shared state and file locking for parallel workflows
- Progress tracking and audit trail
- Error recovery and retry logic

Governance: AUTONOMOUS maturity required.
"""

import asyncio
import logging
import subprocess
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from core.llm.byok_handler import BYOKHandler
from core.requirement_parser_service import RequirementParserService
from core.codebase_research_service import CodebaseResearchService
from core.autonomous_planning_agent import PlanningAgent
from core.autonomous_coder_agent import CodeGeneratorOrchestrator
from core.test_generator_service import TestGeneratorService
from core.test_runner_service import TestRunnerService
from core.episode_segmentation_service import EpisodeSegmentationService

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class WorkflowPhase(str, Enum):
    """Phases of autonomous coding workflow."""
    PARSE_REQUIREMENTS = "parse_requirements"
    RESEARCH_CODEBASE = "research_codebase"
    CREATE_PLAN = "create_plan"
    GENERATE_CODE = "generate_code"
    GENERATE_TESTS = "generate_tests"
    FIX_TESTS = "fix_tests"
    GENERATE_DOCS = "generate_docs"
    CREATE_COMMIT = "create_commit"


class WorkflowStatus(str, Enum):
    """Status of autonomous coding workflow."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== Git Operations ====================

class GitOperations:
    """Git operations for checkpoint/rollback."""

    def __init__(self, repo_path: str = "/Users/rushiparikh/projects/atom"):
        self.repo_path = Path(repo_path)

    def create_commit(self, message: str) -> str:
        """Create git commit and return SHA."""
        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )

            # Create commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )

            # Get SHA
            sha_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )

            return sha_result.stdout.strip()

        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit failed: {e.stderr}")
            raise

    def get_current_sha(self) -> str:
        """Get current HEAD SHA."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def reset_to_sha(self, sha: str) -> None:
        """Reset repository to specific SHA."""
        subprocess.run(
            ["git", "reset", "--hard", sha],
            cwd=self.repo_path,
            check=True,
            capture_output=True
        )

    def get_diff(self, sha1: str, sha2: Optional[str] = None) -> str:
        """Get diff between two SHAs."""
        if sha2 is None:
            sha2 = "HEAD"
        result = subprocess.run(
            ["git", "diff", sha1, sha2],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout


# ==================== Checkpoint Manager ====================

class CheckpointManager:
    """Manage workflow checkpoints for pause/resume/rollback."""

    def __init__(self, db: Session, git_ops: GitOperations):
        self.db = db
        self.git_ops = git_ops

    async def create_checkpoint(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        state: Dict[str, Any]
    ) -> str:
        """
        Create checkpoint for workflow.

        Creates:
        1. Git commit (for rollback)
        2. Database checkpoint record
        3. State snapshot in memory

        Returns checkpoint SHA.
        """
        from core.models import AutonomousCheckpoint

        # Create git commit
        commit_message = f"[Checkpoint] Workflow {workflow_id} - {phase.value}"
        checkpoint_sha = self.git_ops.create_commit(commit_message)

        # Save to database
        await self.save_checkpoint_to_db(
            workflow_id=workflow_id,
            phase=phase,
            checkpoint_sha=checkpoint_sha,
            state=state
        )

        logger.info(f"Created checkpoint {checkpoint_sha} for workflow {workflow_id} at phase {phase.value}")
        return checkpoint_sha

    async def save_checkpoint_to_db(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        checkpoint_sha: str,
        state: Dict[str, Any]
    ):
        """Save checkpoint to database."""
        from core.models import AutonomousCheckpoint

        checkpoint = AutonomousCheckpoint(
            workflow_id=workflow_id,
            phase=phase.value,
            checkpoint_sha=checkpoint_sha,
            state_json=state,
            created_at=datetime.utcnow()
        )

        self.db.add(checkpoint)
        self.db.commit()

    async def load_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """
        Load checkpoint state.
        Returns full state snapshot.
        """
        from core.models import AutonomousCheckpoint

        checkpoint = self.db.query(AutonomousCheckpoint).filter(
            AutonomousCheckpoint.id == checkpoint_id
        ).first()

        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")

        return checkpoint.state_json

    async def rollback_to_checkpoint(
        self,
        workflow_id: str,
        checkpoint_sha: str
    ) -> Dict[str, Any]:
        """
        Rollback workflow to checkpoint.

        1. Reset git to checkpoint SHA
        2. Restore state from checkpoint
        3. Update workflow status

        Returns rollback result.
        """
        from core.models import AutonomousCheckpoint, AutonomousWorkflow

        # Reset git
        self.git_ops.reset_to_sha(checkpoint_sha)

        # Load checkpoint
        checkpoint = self.db.query(AutonomousCheckpoint).filter(
            AutonomousWorkflow.id == workflow_id,
            AutonomousCheckpoint.checkpoint_sha == checkpoint_sha
        ).first()

        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_sha} not found for workflow {workflow_id}")

        # Update workflow status
        workflow = self.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.id == workflow_id
        ).first()

        if workflow:
            workflow.status = WorkflowStatus.PAUSED.value
            workflow.current_phase = checkpoint.phase
            self.db.commit()

        logger.info(f"Rolled back workflow {workflow_id} to checkpoint {checkpoint_sha}")

        return {
            "workflow_id": workflow_id,
            "checkpoint_sha": checkpoint_sha,
            "phase": checkpoint.phase,
            "state": checkpoint.state_json
        }

    async def rollback_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase
    ) -> Dict[str, Any]:
        """
        Rollback to specific phase.
        Finds most recent checkpoint for phase.
        """
        from core.models import AutonomousCheckpoint

        checkpoint = self.db.query(AutonomousCheckpoint).filter(
            AutonomousCheckpoint.workflow_id == workflow_id,
            AutonomousCheckpoint.phase == phase.value
        ).order_by(AutonomousCheckpoint.created_at.desc()).first()

        if not checkpoint:
            raise ValueError(f"No checkpoint found for phase {phase.value}")

        return await self.rollback_to_checkpoint(workflow_id, checkpoint.checkpoint_sha)

    def get_available_checkpoints(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        List all checkpoints for workflow.
        Returns sorted by creation time.
        """
        from core.models import AutonomousCheckpoint

        checkpoints = self.db.query(AutonomousCheckpoint).filter(
            AutonomousCheckpoint.workflow_id == workflow_id
        ).order_by(AutonomousCheckpoint.created_at.asc()).all()

        return [
            {
                "id": cp.id,
                "phase": cp.phase,
                "checkpoint_sha": cp.checkpoint_sha,
                "created_at": cp.created_at.isoformat()
            }
            for cp in checkpoints
        ]


# ==================== Shared State Store ====================

class SharedStateStore:
    """Manage shared state between agents."""

    def __init__(self):
        self.state: Dict[str, Dict[str, Any]] = {}  # {workflow_id: state}
        self.locks: Dict[str, asyncio.Lock] = {}  # {workflow_id: lock}
        self.file_locks: Dict[str, str] = {}  # {file: workflow_id}

    async def get_state(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow state."""
        if workflow_id not in self.state:
            raise ValueError(f"No state found for workflow {workflow_id}")
        return self.state[workflow_id]

    async def update_state(
        self,
        workflow_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update workflow state.
        Merges updates with existing state.
        Returns updated state.
        """
        if workflow_id not in self.state:
            raise ValueError(f"No state found for workflow {workflow_id}")

        # Get lock for workflow
        if workflow_id not in self.locks:
            self.locks[workflow_id] = asyncio.Lock()

        async with self.locks[workflow_id]:
            self.state[workflow_id].update(updates)

        return self.state[workflow_id]

    async def acquire_file_lock(
        self,
        workflow_id: str,
        file_path: str
    ) -> bool:
        """
        Acquire lock on file for modification.
        Returns True if lock acquired, False if file locked by another workflow.
        """
        if file_path in self.file_locks:
            if self.file_locks[file_path] != workflow_id:
                return False
        self.file_locks[file_path] = workflow_id
        return True

    async def release_file_lock(
        self,
        workflow_id: str,
        file_path: str
    ) -> None:
        """Release file lock."""
        if file_path in self.file_locks and self.file_locks[file_path] == workflow_id:
            del self.file_locks[file_path]

    def check_file_conflicts(
        self,
        workflow_id: str,
        files: List[str]
    ) -> List[str]:
        """
        Check for file modification conflicts.
        Returns list of conflicting files.
        """
        conflicts = []
        for file_path in files:
            if file_path in self.file_locks and self.file_locks[file_path] != workflow_id:
                conflicts.append(file_path)
        return conflicts

    async def merge_state(
        self,
        workflow_id: str,
        new_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge new state with existing state.
        Handles conflicts by keeping latest value.
        Returns merged state.
        """
        if workflow_id not in self.state:
            self.state[workflow_id] = new_state
            return new_state

        # Get lock for workflow
        if workflow_id not in self.locks:
            self.locks[workflow_id] = asyncio.Lock()

        async with self.locks[workflow_id]:
            current = self.state[workflow_id]
            merged = {**current, **new_state}
            self.state[workflow_id] = merged

        return merged

    def create_initial_state(
        self,
        workflow_id: str,
        feature_request: str,
        workspace_id: str
    ) -> Dict[str, Any]:
        """
        Create initial workflow state.
        Returns {"workflow_id", "feature_request", "workspace_id", ...}
        """
        return {
            "workflow_id": workflow_id,
            "feature_request": feature_request,
            "workspace_id": workspace_id,
            "status": WorkflowStatus.PENDING.value,
            "current_phase": None,
            "completed_phases": [],
            "requirements": {},
            "research_context": {},
            "implementation_plan": {},
            "files_created": [],
            "files_modified": [],
            "test_results": {},
            "documentation": {},
            "commit_result": {},
            "started_at": datetime.utcnow().isoformat()
        }


# ==================== Pause/Resume Manager ====================

class PauseResumeManager:
    """Manage workflow pause/resume with human feedback."""

    def __init__(self, orchestrator: 'AgentOrchestrator'):
        self.orchestrator = orchestrator
        self.paused_workflows: Set[str] = set()
        self.pause_reasons: Dict[str, str] = {}

    async def pause_workflow(
        self,
        workflow_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pause workflow for human review.

        1. Stop workflow execution
        2. Create checkpoint
        3. Update workflow status to PAUSED
        4. Generate summary for human review

        Returns pause result with checkpoint info.
        """
        from core.models import AutonomousWorkflow

        # Create checkpoint
        state = await self.orchestrator.state_store.get_state(workflow_id)
        current_phase = state.get("current_phase")

        if current_phase:
            checkpoint_sha = await self.orchestrator.checkpoint_manager.create_checkpoint(
                workflow_id=workflow_id,
                phase=WorkflowPhase(current_phase),
                state=state
            )
        else:
            checkpoint_sha = None

        # Update workflow in database
        workflow = self.orchestrator.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.id == workflow_id
        ).first()

        if workflow:
            workflow.status = WorkflowStatus.PAUSED.value
            self.orchestrator.db.commit()

        # Track pause
        self.paused_workflows.add(workflow_id)
        if reason:
            self.pause_reasons[workflow_id] = reason

        # Generate summary
        summary = self.generate_pause_summary(workflow_id)

        logger.info(f"Paused workflow {workflow_id}: {reason}")

        return {
            "workflow_id": workflow_id,
            "status": "paused",
            "checkpoint_sha": checkpoint_sha,
            "reason": reason,
            "summary": summary
        }

    async def resume_workflow(
        self,
        workflow_id: str,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resume workflow with optional human feedback.

        Args:
            workflow_id: Workflow to resume
            feedback: Human feedback/instructions to apply

        1. Load checkpoint
        2. Apply feedback if provided
        3. Continue from checkpoint phase
        4. Update workflow status to RUNNING

        Returns resume result.
        """
        from core.models import AutonomousWorkflow

        # Get state
        state = await self.orchestrator.state_store.get_state(workflow_id)

        # Apply feedback if provided
        if feedback:
            await self.apply_human_feedback(workflow_id, feedback, state)

        # Update workflow in database
        workflow = self.orchestrator.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.id == workflow_id
        ).first()

        if workflow:
            workflow.status = WorkflowStatus.RUNNING.value
            self.orchestrator.db.commit()

        # Remove from paused set
        self.paused_workflows.discard(workflow_id)
        self.pause_reasons.pop(workflow_id, None)

        logger.info(f"Resumed workflow {workflow_id} with feedback: {feedback}")

        return {
            "workflow_id": workflow_id,
            "status": "running",
            "feedback_applied": feedback is not None
        }

    def generate_pause_summary(self, workflow_id: str) -> str:
        """
        Generate human-readable pause summary.

        Shows:
        - Phases completed
        - Current state
        - Files created/modified
        - What to review
        """
        try:
            state = self.orchestrator.state_store.state.get(workflow_id, {})
            completed = state.get("completed_phases", [])
            files_created = state.get("files_created", [])
            files_modified = state.get("files_modified", [])

            summary = f"""
# Workflow {workflow_id} - Pause Summary

## Completed Phases
{chr(10).join(f'- {phase}' for phase in completed)}

## Files Created ({len(files_created)})
{chr(10).join(f'- {f}' for f in files_created[:10])}

## Files Modified ({len(files_modified)})
{chr(10).join(f'- {f}' for f in files_modified[:10])}

## Next Steps
- Review changes above
- Provide feedback to resume
- Or rollback to previous checkpoint if needed
"""
            return summary

        except Exception as e:
            logger.error(f"Failed to generate pause summary: {e}")
            return f"Error generating summary: {str(e)}"

    async def apply_human_feedback(
        self,
        workflow_id: str,
        feedback: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply human feedback to workflow state.

        Feedback types:
        - "Use X instead of Y" (change approach)
        - "Don't modify file Z" (exclusion)
        - "Add feature W" (additional requirement)
        """
        # Store feedback in state
        state["human_feedback"] = feedback
        state["feedback_timestamp"] = datetime.utcnow().isoformat()

        # Update state
        await self.orchestrator.state_store.update_state(workflow_id, {
            "human_feedback": feedback,
            "feedback_timestamp": state["feedback_timestamp"]
        })

        return {"feedback_applied": True}

    def is_workflow_paused(self, workflow_id: str) -> bool:
        """Check if workflow is paused."""
        return workflow_id in self.paused_workflows

    def get_pause_reason(self, workflow_id: str) -> Optional[str]:
        """Get pause reason for workflow."""
        return self.pause_reasons.get(workflow_id)


# ==================== Progress Tracker ====================

class ProgressTracker:
    """Track workflow progress and audit trail."""

    def __init__(self, db: Session):
        self.db = db

    async def update_progress(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        status: WorkflowStatus,
        artifacts: Dict[str, Any]
    ) -> None:
        """Update workflow progress in database.
        Updates AutonomousWorkflow record.
        """
        from core.models import AutonomousWorkflow

        workflow = self.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.id == workflow_id
        ).first()

        if workflow:
            workflow.current_phase = phase.value
            workflow.status = status.value

            # Update completed phases
            if status == WorkflowStatus.COMPLETED and phase.value not in workflow.completed_phases:
                workflow.completed_phases = workflow.completed_phases + [phase.value]

            # Update artifacts
            if "files_created" in artifacts:
                workflow.files_created = artifacts["files_created"]
            if "files_modified" in artifacts:
                workflow.files_modified = artifacts["files_modified"]
            if "test_results" in artifacts:
                workflow.test_results = artifacts["test_results"]

            self.db.commit()

    async def log_agent_action(
        self,
        workflow_id: str,
        agent_id: str,
        phase: str,
        action: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Log agent action to database.
        Creates AgentLog entry for audit trail.
        """
        from core.models import AgentLog

        log = AgentLog(
            workflow_id=workflow_id,
            agent_id=agent_id,
            phase=phase,
            action=action,
            input_json=input_data,
            output_json=output_data,
            status=status,
            error_message=error_message,
            started_at=datetime.utcnow()
        )

        self.db.add(log)
        self.db.commit()

    def calculate_progress_percent(
        self,
        completed_phases: List[str],
        total_phases: int = 8
    ) -> float:
        """
        Calculate progress percentage.
        Returns 0-100.
        """
        if not completed_phases:
            return 0.0
        return (len(completed_phases) / total_phases) * 100

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get current workflow status.
        Returns comprehensive status dict.
        """
        from core.models import AutonomousWorkflow

        workflow = self.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        return {
            "workflow_id": workflow.id,
            "status": workflow.status,
            "current_phase": workflow.current_phase,
            "completed_phases": workflow.completed_phases or [],
            "files_created": workflow.files_created or [],
            "files_modified": workflow.files_modified or [],
            "test_results": workflow.test_results,
            "progress_percent": self.calculate_progress_percent(workflow.completed_phases or []),
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            "error_message": workflow.error_message
        }

    async def get_audit_trail(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get audit trail for workflow.
        Returns all AgentLog entries in order.
        """
        from core.models import AgentLog

        logs = self.db.query(AgentLog).filter(
            AgentLog.workflow_id == workflow_id
        ).order_by(AgentLog.started_at).all()

        return [
            {
                "agent_id": log.agent_id,
                "phase": log.phase,
                "action": log.action,
                "status": log.status,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "duration_seconds": log.duration_seconds,
                "error_message": log.error_message
            }
            for log in logs
        ]

    def generate_progress_report(self, workflow_id: str) -> str:
        """
        Generate human-readable progress report.
        Shows phases, status, artifacts, next steps.
        """
        # This would be called from orchestrator with state
        # Placeholder implementation
        return f"Progress report for workflow {workflow_id}"


# ==================== Main Orchestrator ====================

class AgentOrchestrator:
    """
    Orchestrates all autonomous coding agents.

    Coordinates 7 specialized agents through complete SDLC:
    1. Parse Requirements
    2. Research Codebase
    3. Create Plan
    4. Generate Code
    5. Generate Tests
    6. Fix Tests
    7. Generate Docs
    8. Create Commit
    """

    def __init__(
        self,
        db: Session,
        byok_handler: BYOKHandler
    ):
        self.db = db
        self.byok_handler = byok_handler

        # Initialize all agents
        self.requirement_parser = RequirementParserService(db, byok_handler)
        self.codebase_researcher = CodebaseResearchService(db)
        self.planning_agent = PlanningAgent(db, byok_handler)
        self.coder_agent = CodeGeneratorOrchestrator(db, byok_handler)
        self.test_generator = TestGeneratorService(db, byok_handler)
        self.test_runner = TestRunnerService(db)
        # Note: Documenter and Committer agents will be added in future plans
        # self.documenter = DocumenterAgent(db, byok_handler)
        # self.committer = CommitterAgent(db, byok_handler)

        # Episode service for WorldModel recall
        self.episode_service = EpisodeSegmentationService(db, byok_handler)

        # Git operations
        self.git_ops = GitOperations()

        # Managers
        self.checkpoint_manager = CheckpointManager(db, self.git_ops)
        self.state_store = SharedStateStore()
        self.pause_manager = PauseResumeManager(self)
        self.progress_tracker = ProgressTracker(db)

        # Workflow state
        self.active_workflows: Dict[str, Dict[str, Any]] = {}

        # Configuration
        self.max_fix_iterations = 5
        self.checkpoint_interval = 1  # Checkpoint after each phase

    async def execute_feature(
        self,
        feature_request: str,
        workspace_id: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute complete autonomous coding workflow.

        Args:
            feature_request: Natural language feature description
            workspace_id: Workspace context
            options: {"auto_commit": bool, "checkpoints": ["after_implementation"]}

        Returns:
            {
                "workflow_id": str,
                "status": str,
                "phases_completed": [str],
                "files_created": [str],
                "files_modified": [str],
                "commit_sha": str (if committed),
                "pr_url": str (if PR created)
            }
        """
        options = options or {}
        workflow_id = str(uuid.uuid4())

        logger.info(f"Starting autonomous workflow {workflow_id}: {feature_request}")

        # Create initial state
        initial_state = self.state_store.create_initial_state(
            workflow_id=workflow_id,
            feature_request=feature_request,
            workspace_id=workspace_id
        )
        self.state_store.state[workflow_id] = initial_state

        # Create workflow record in database
        from core.models import AutonomousWorkflow, Episode
        workflow = AutonomousWorkflow(
            id=workflow_id,
            feature_request=feature_request,
            workspace_id=workspace_id,
            status=WorkflowStatus.RUNNING.value,
            started_at=datetime.utcnow()
        )
        self.db.add(workflow)
        self.db.commit()

        # Create Episode for WorldModel recall
        # Use a system agent_id for autonomous coding workflows
        episode = Episode(
            id=str(uuid.uuid4()),
            title=f"Autonomous Coding: {feature_request[:50]}{'...' if len(feature_request) > 50 else ''}",
            description=f"Feature request: {feature_request}\n"
                       f"Workflow ID: {workflow_id}\n"
                       f"Workspace: {workspace_id}",
            summary=f"Autonomous coding workflow for: {feature_request[:100]}",
            agent_id="autonomous_coding_agent",  # System agent for autonomous coding
            user_id=None,  # No user context for autonomous coding
            workspace_id=workspace_id,
            session_id=None,  # No chat session for autonomous coding
            execution_ids=[workflow_id],
            started_at=datetime.utcnow(),
            status="active",
            topics=["autonomous_coding", "code_generation"],
            entities=[f"workflow:{workflow_id}"],
            importance_score=0.7,
            maturity_at_time="AUTONOMOUS",
            human_intervention_count=0,
            human_edits=[],
            world_model_state="v1.0"
        )
        self.db.add(episode)
        self.db.commit()
        self.db.refresh(episode)

        # Store episode_id in state for segment creation
        await self.state_store.update_state(workflow_id, {
            "episode_id": str(episode.id)
        })

        # Define phases
        phases = [
            (WorkflowPhase.PARSE_REQUIREMENTS, self._run_parse_requirements),
            (WorkflowPhase.RESEARCH_CODEBASE, self._run_research_codebase),
            (WorkflowPhase.CREATE_PLAN, self._run_create_plan),
            (WorkflowPhase.GENERATE_CODE, self._run_generate_code),
            (WorkflowPhase.GENERATE_TESTS, self._run_generate_tests),
            (WorkflowPhase.FIX_TESTS, self._run_fix_tests),
            # Note: Docs and Commit will be added when those agents are implemented
            # (WorkflowPhase.GENERATE_DOCS, self._run_generate_docs),
            # (WorkflowPhase.CREATE_COMMIT, self._run_create_commit),
        ]

        completed_phases = []

        try:
            # Execute each phase
            for phase, phase_func in phases:
                # Check if paused
                while self.pause_manager.is_workflow_paused(workflow_id):
                    await asyncio.sleep(1)

                # Update state
                await self.state_store.update_state(workflow_id, {
                    "current_phase": phase.value
                })

                # Run phase
                logger.info(f"Running phase {phase.value} for workflow {workflow_id}")
                result = await self._run_phase(workflow_id, phase, {})

                # Update completed phases
                completed_phases.append(phase.value)
                await self.state_store.update_state(workflow_id, {
                    "completed_phases": completed_phases
                })

                # Create checkpoint
                await self.checkpoint_manager.create_checkpoint(
                    workflow_id=workflow_id,
                    phase=phase,
                    state=await self.state_store.get_state(workflow_id)
                )

                # Update progress
                await self.progress_tracker.update_progress(
                    workflow_id=workflow_id,
                    phase=phase,
                    status=WorkflowStatus.COMPLETED,
                    artifacts=result.get("artifacts", {})
                )

            # Mark workflow as completed
            workflow.status = WorkflowStatus.COMPLETED.value
            workflow.completed_at = datetime.utcnow()
            self.db.commit()

            # Get final state
            final_state = await self.state_store.get_state(workflow_id)

            logger.info(f"Completed autonomous workflow {workflow_id}")

            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "phases_completed": completed_phases,
                "files_created": final_state.get("files_created", []),
                "files_modified": final_state.get("files_modified", []),
                "test_results": final_state.get("test_results", {})
            }

        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")

            # Update workflow with error
            workflow.status = WorkflowStatus.FAILED.value
            workflow.error_message = str(e)
            workflow.completed_at = datetime.utcnow()
            self.db.commit()

            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e),
                "phases_completed": completed_phases
            }

    async def _run_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        phase_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run a single phase of the workflow.
        Routes to appropriate agent.
        Handles errors and retries.
        """
        state = await self.state_store.get_state(workflow_id)

        # Route to appropriate phase handler
        phase_handlers = {
            WorkflowPhase.PARSE_REQUIREMENTS: self._run_parse_requirements,
            WorkflowPhase.RESEARCH_CODEBASE: self._run_research_codebase,
            WorkflowPhase.CREATE_PLAN: self._run_create_plan,
            WorkflowPhase.GENERATE_CODE: self._run_generate_code,
            WorkflowPhase.GENERATE_TESTS: self._run_generate_tests,
            WorkflowPhase.FIX_TESTS: self._run_fix_tests,
            # WorkflowPhase.GENERATE_DOCS: self._run_generate_docs,
            # WorkflowPhase.CREATE_COMMIT: self._run_create_commit,
        }

        handler = phase_handlers.get(phase)
        if not handler:
            raise ValueError(f"No handler for phase {phase.value}")

        # Log agent action
        await self.progress_tracker.log_agent_action(
            workflow_id=workflow_id,
            agent_id=f"orchestrator-{phase.value}",
            phase=phase.value,
            action=f"Execute {phase.value}",
            input_data=phase_data,
            output_data={},
            status="running"
        )

        try:
            result = await handler(workflow_id, state)

            # Update log with success
            await self.progress_tracker.log_agent_action(
                workflow_id=workflow_id,
                agent_id=f"orchestrator-{phase.value}",
                phase=phase.value,
                action=f"Execute {phase.value}",
                input_data=phase_data,
                output_data=result,
                status="completed"
            )

            return result

        except Exception as e:
            # Log error
            await self.progress_tracker.log_agent_action(
                workflow_id=workflow_id,
                agent_id=f"orchestrator-{phase.value}",
                phase=phase.value,
                action=f"Execute {phase.value}",
                input_data=phase_data,
                output_data={},
                status="failed",
                error_message=str(e)
            )
            raise

    async def _run_parse_requirements(
        self,
        workflow_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 1: Parse requirements with RequirementParserService."""
        state = await self.state_store.get_state(workflow_id)

        parsed = await self.requirement_parser.parse_requirements(
            feature_request=state["feature_request"],
            workspace_id=state["workspace_id"]
        )

        # Update state
        await self.state_store.update_state(workflow_id, {
            "requirements": parsed
        })

        return {
            "phase": "parse_requirements",
            "artifacts": {"requirements": parsed}
        }

    async def _run_research_codebase(
        self,
        workflow_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 2: Research codebase with CodebaseResearchService."""
        state = await self.state_store.get_state(workflow_id)

        # Research based on requirements
        research = await self.codebase_researcher.research_codebase(
            query=state["feature_request"],
            workspace_id=state["workspace_id"]
        )

        # Update state
        await self.state_store.update_state(workflow_id, {
            "research_context": research
        })

        return {
            "phase": "research_codebase",
            "artifacts": {"research": research}
        }

    async def _run_create_plan(
        self,
        workflow_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 3: Create plan with PlanningAgent."""
        state = await self.state_store.get_state(workflow_id)

        plan = await self.planning_agent.create_implementation_plan(
            feature_request=state["feature_request"],
            requirements=state.get("requirements", {}),
            research_context=state.get("research_context", {}),
            workspace_id=state["workspace_id"]
        )

        # Update state
        await self.state_store.update_state(workflow_id, {
            "implementation_plan": plan
        })

        return {
            "phase": "create_plan",
            "artifacts": {"plan": plan}
        }

    async def _run_generate_code(
        self,
        workflow_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 4: Generate code with CoderAgent."""
        state = await self.state_store.get_state(workflow_id)

        code_result = await self.coder_agent.generate_feature_code(
            feature_request=state["feature_request"],
            implementation_plan=state.get("implementation_plan", {}),
            workspace_id=state["workspace_id"]
        )

        # Update state
        files_created = code_result.get("files_created", [])
        files_modified = code_result.get("files_modified", [])

        await self.state_store.update_state(workflow_id, {
            "files_created": state.get("files_created", []) + files_created,
            "files_modified": state.get("files_modified", []) + files_modified
        })

        return {
            "phase": "generate_code",
            "artifacts": {
                "files_created": files_created,
                "files_modified": files_modified
            }
        }

    async def _run_generate_tests(
        self,
        workflow_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 5: Generate tests with TestGeneratorService."""
        state = await self.state_store.get_state(workflow_id)

        tests_result = await self.test_generator.generate_tests(
            feature_description=state["feature_request"],
            implementation_plan=state.get("implementation_plan", {}),
            files_created=state.get("files_created", []),
            workspace_id=state["workspace_id"]
        )

        # Update state
        test_files = tests_result.get("test_files", [])
        await self.state_store.update_state(workflow_id, {
            "files_created": state.get("files_created", []) + test_files
        })

        return {
            "phase": "generate_tests",
            "artifacts": {"test_files": test_files}
        }

    async def _run_fix_tests(
        self,
        workflow_id: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 6: Fix test failures with TestRunnerService."""
        state = await self.state_store.get_state(workflow_id)

        # Run tests
        test_results = await self.test_runner.run_tests(
            workspace_id=state["workspace_id"]
        )

        # Fix failures if any
        if test_results.get("failed", 0) > 0:
            for i in range(self.max_fix_iterations):
                fix_result = await self.test_runner.fix_test_failures(
                    test_results=test_results,
                    workspace_id=state["workspace_id"]
                )

                # Re-run tests
                test_results = await self.test_runner.run_tests(
                    workspace_id=state["workspace_id"]
                )

                if test_results.get("failed", 0) == 0:
                    break

        # Update state
        await self.state_store.update_state(workflow_id, {
            "test_results": test_results
        })

        return {
            "phase": "fix_tests",
            "artifacts": {"test_results": test_results}
        }

    async def pause_workflow(
        self,
        workflow_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pause workflow for human review.
        Public API for pause requests.
        """
        return await self.pause_manager.pause_workflow(workflow_id, reason)

    async def resume_workflow(
        self,
        workflow_id: str,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resume workflow with optional feedback.
        Public API for resume requests.
        """
        return await self.pause_manager.resume_workflow(workflow_id, feedback)

    async def rollback_workflow(
        self,
        workflow_id: str,
        checkpoint_sha: Optional[str] = None,
        phase: Optional[WorkflowPhase] = None
    ) -> Dict[str, Any]:
        """
        Rollback workflow to checkpoint or phase.
        Public API for rollback requests.
        """
        if phase:
            return await self.checkpoint_manager.rollback_phase(workflow_id, phase)
        elif checkpoint_sha:
            return await self.checkpoint_manager.rollback_to_checkpoint(workflow_id, checkpoint_sha)
        else:
            raise ValueError("Must specify either checkpoint_sha or phase")

    async def get_workflow_status(
        self,
        workflow_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive workflow status.
        Returns state, progress, audit trail.
        """
        status = await self.progress_tracker.get_workflow_status(workflow_id)
        audit_trail = await self.progress_tracker.get_audit_trail(workflow_id)

        return {
            **status,
            "audit_trail": audit_trail
        }

    def list_active_workflows(self) -> List[str]:
        """
        List all active workflow IDs.
        Returns list of workflow IDs with status != completed.
        """
        from core.models import AutonomousWorkflow

        workflows = self.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.status.in_([
                WorkflowStatus.PENDING.value,
                WorkflowStatus.RUNNING.value,
                WorkflowStatus.PAUSED.value
            ])
        ).all()

        return [w.id for w in workflows]
