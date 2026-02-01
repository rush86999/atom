"""
Workflow Debugger Service

Provides step-through debugging capabilities for workflows including:
- Breakpoint management (add, remove, enable, disable)
- Step execution control (step over, step into, step out, continue, pause)
- Variable inspection and watch expressions
- Execution trace recording
- Debug session management
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.models import (
    WorkflowDebugSession,
    WorkflowBreakpoint,
    ExecutionTrace,
    DebugVariable,
    WorkflowExecution,
)

logger = logging.getLogger(__name__)


class WorkflowDebugger:
    """
    Workflow debugger with breakpoint management and step control.

    Enables developers to debug workflow execution with:
    - Breakpoints on nodes/edges
    - Conditional breakpoints
    - Step-through execution
    - Variable inspection
    - Call stack tracking
    - Execution tracing
    """

    def __init__(self, db: Session):
        self.db = db

    # ==================== Debug Session Management ====================

    def create_debug_session(
        self,
        workflow_id: str,
        user_id: str,
        execution_id: Optional[str] = None,
        session_name: Optional[str] = None,
        stop_on_entry: bool = False,
        stop_on_exceptions: bool = True,
        stop_on_error: bool = True,
    ) -> WorkflowDebugSession:
        """Create a new debug session for a workflow."""
        try:
            session = WorkflowDebugSession(
                workflow_id=workflow_id,
                execution_id=execution_id,
                user_id=user_id,
                session_name=session_name or f"Debug {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                status="active",
                current_step=0,
                breakpoints=[],
                variables={},
                call_stack=[],
                stop_on_entry=stop_on_entry,
                stop_on_exceptions=stop_on_exceptions,
                stop_on_error=stop_on_error,
                conditional_breakpoints={},
            )

            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            logger.info(f"Created debug session {session.id} for workflow {workflow_id}")
            return session

        except Exception as e:
            logger.error(f"Error creating debug session: {e}")
            self.db.rollback()
            raise

    def get_debug_session(self, session_id: str) -> Optional[WorkflowDebugSession]:
        """Get a debug session by ID."""
        return self.db.query(WorkflowDebugSession).filter(
            WorkflowDebugSession.id == session_id
        ).first()

    def get_active_debug_sessions(
        self, workflow_id: str, user_id: Optional[str] = None
    ) -> List[WorkflowDebugSession]:
        """Get all active debug sessions for a workflow."""
        query = self.db.query(WorkflowDebugSession).filter(
            and_(
                WorkflowDebugSession.workflow_id == workflow_id,
                WorkflowDebugSession.status == "active",
            )
        )

        if user_id:
            query = query.filter(WorkflowDebugSession.user_id == user_id)

        return query.order_by(WorkflowDebugSession.created_at.desc()).all()

    def pause_debug_session(self, session_id: str) -> bool:
        """Pause a debug session."""
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return False

            session.status = "paused"
            session.updated_at = datetime.now()
            self.db.commit()

            logger.info(f"Paused debug session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error pausing debug session: {e}")
            self.db.rollback()
            return False

    def resume_debug_session(self, session_id: str) -> bool:
        """Resume a paused debug session."""
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return False

            session.status = "active"
            session.updated_at = datetime.now()
            self.db.commit()

            logger.info(f"Resumed debug session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error resuming debug session: {e}")
            self.db.rollback()
            return False

    def complete_debug_session(self, session_id: str) -> bool:
        """Mark a debug session as completed."""
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return False

            session.status = "completed"
            session.completed_at = datetime.now()
            session.updated_at = datetime.now()
            self.db.commit()

            logger.info(f"Completed debug session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error completing debug session: {e}")
            self.db.rollback()
            return False

    # ==================== Breakpoint Management ====================

    def add_breakpoint(
        self,
        workflow_id: str,
        node_id: str,
        user_id: str,
        debug_session_id: Optional[str] = None,
        edge_id: Optional[str] = None,
        breakpoint_type: str = "node",
        condition: Optional[str] = None,
        hit_limit: Optional[int] = None,
        log_message: Optional[str] = None,
    ) -> WorkflowBreakpoint:
        """Add a breakpoint to a workflow node or edge."""
        try:
            breakpoint = WorkflowBreakpoint(
                workflow_id=workflow_id,
                debug_session_id=debug_session_id,
                node_id=node_id,
                edge_id=edge_id,
                breakpoint_type=breakpoint_type,
                condition=condition,
                hit_count=0,
                hit_limit=hit_limit,
                is_active=True,
                is_disabled=False,
                log_message=log_message,
                created_by=user_id,
            )

            self.db.add(breakpoint)
            self.db.commit()
            self.db.refresh(breakpoint)

            logger.info(f"Added breakpoint {breakpoint.id} on node {node_id}")
            return breakpoint

        except Exception as e:
            logger.error(f"Error adding breakpoint: {e}")
            self.db.rollback()
            raise

    def remove_breakpoint(self, breakpoint_id: str, user_id: str) -> bool:
        """Remove a breakpoint."""
        try:
            breakpoint = self.db.query(WorkflowBreakpoint).filter(
                and_(
                    WorkflowBreakpoint.id == breakpoint_id,
                    WorkflowBreakpoint.created_by == user_id,
                )
            ).first()

            if not breakpoint:
                return False

            self.db.delete(breakpoint)
            self.db.commit()

            logger.info(f"Removed breakpoint {breakpoint_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing breakpoint: {e}")
            self.db.rollback()
            return False

    def toggle_breakpoint(self, breakpoint_id: str, user_id: str) -> Optional[bool]:
        """Toggle breakpoint enabled/disabled state."""
        try:
            breakpoint = self.db.query(WorkflowBreakpoint).filter(
                and_(
                    WorkflowBreakpoint.id == breakpoint_id,
                    WorkflowBreakpoint.created_by == user_id,
                )
            ).first()

            if not breakpoint:
                return None

            breakpoint.is_disabled = not breakpoint.is_disabled
            breakpoint.updated_at = datetime.now()
            self.db.commit()

            logger.info(f"Toggled breakpoint {breakpoint_id} to disabled={breakpoint.is_disabled}")
            return not breakpoint.is_disabled

        except Exception as e:
            logger.error(f"Error toggling breakpoint: {e}")
            self.db.rollback()
            return None

    def get_breakpoints(
        self, workflow_id: str, user_id: Optional[str] = None, active_only: bool = True
    ) -> List[WorkflowBreakpoint]:
        """Get all breakpoints for a workflow."""
        query = self.db.query(WorkflowBreakpoint).filter(
            WorkflowBreakpoint.workflow_id == workflow_id
        )

        if user_id:
            query = query.filter(WorkflowBreakpoint.created_by == user_id)

        if active_only:
            query = query.filter(WorkflowBreakpoint.is_active == True)

        return query.order_by(WorkflowBreakpoint.created_at.desc()).all()

    def check_breakpoint_hit(
        self, node_id: str, variables: Dict[str, Any], session_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if execution should pause at this node.

        Returns (should_pause, log_message)
        """
        try:
            # Get breakpoints for this node
            query = self.db.query(WorkflowBreakpoint).filter(
                and_(
                    WorkflowBreakpoint.node_id == node_id,
                    WorkflowBreakpoint.is_active == True,
                    WorkflowBreakpoint.is_disabled == False,
                )
            )

            if session_id:
                query = query.filter(
                    or_(
                        WorkflowBreakpoint.debug_session_id == session_id,
                        WorkflowBreakpoint.debug_session_id.is_(None),
                    )
                )

            breakpoints = query.all()

            for bp in breakpoints:
                # Check hit limit
                if bp.hit_limit is not None and bp.hit_count >= bp.hit_limit:
                    continue

                # Check condition
                if bp.condition:
                    if not self._evaluate_condition(bp.condition, variables):
                        continue

                # Increment hit count
                bp.hit_count += 1
                self.db.commit()

                # Return log message or pause signal
                if bp.log_message:
                    return False, bp.log_message
                else:
                    return True, None

            return False, None

        except Exception as e:
            logger.error(f"Error checking breakpoint: {e}")
            return False, None

    def _evaluate_condition(self, condition: str, variables: Dict[str, Any]) -> bool:
        """Evaluate a conditional breakpoint expression."""
        try:
            # Simple variable substitution
            # For production, use a safer eval approach
            safe_vars = {k.replace("-", "_"): v for k, v in variables.items()}
            return eval(condition, {"__builtins__": {}}, safe_vars)
        except Exception:
            return False

    # ==================== Step Execution Control ====================

    def step_over(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Execute current step and pause at the next sibling."""
        session = self.get_debug_session(session_id)
        if not session:
            return None

        # Move to next step at same level
        session.current_step += 1
        session.updated_at = datetime.now()
        self.db.commit()

        return {
            "session_id": session_id,
            "current_step": session.current_step,
            "action": "step_over",
        }

    def step_into(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Step into a nested workflow or function."""
        session = self.get_debug_session(session_id)
        if not session:
            return None

        # Move into child workflow
        session.current_step += 1
        # TODO: Implement nested workflow tracking
        session.updated_at = datetime.now()
        self.db.commit()

        return {
            "session_id": session_id,
            "current_step": session.current_step,
            "action": "step_into",
        }

    def step_out(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Step out of current nested workflow to parent."""
        session = self.get_debug_session(session_id)
        if not session:
            return None

        # Move to parent level
        # TODO: Implement call stack tracking
        session.current_step += 1
        session.updated_at = datetime.now()
        self.db.commit()

        return {
            "session_id": session_id,
            "current_step": session.current_step,
            "action": "step_out",
        }

    def continue_execution(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Continue execution until next breakpoint."""
        session = self.get_debug_session(session_id)
        if not session:
            return None

        session.status = "running"
        session.updated_at = datetime.now()
        self.db.commit()

        return {
            "session_id": session_id,
            "status": "running",
            "action": "continue",
        }

    def pause_execution(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Pause execution at current position."""
        session = self.get_debug_session(session_id)
        if not session:
            return None

        session.status = "paused"
        session.updated_at = datetime.now()
        self.db.commit()

        return {
            "session_id": session_id,
            "status": "paused",
            "action": "pause",
        }

    # ==================== Execution Tracing ====================

    def create_trace(
        self,
        workflow_id: str,
        execution_id: str,
        step_number: int,
        node_id: str,
        node_type: str,
        input_data: Optional[Dict[str, Any]] = None,
        variables_before: Optional[Dict[str, Any]] = None,
        debug_session_id: Optional[str] = None,
        parent_step_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> ExecutionTrace:
        """Create a new execution trace entry."""
        try:
            trace = ExecutionTrace(
                workflow_id=workflow_id,
                execution_id=execution_id,
                debug_session_id=debug_session_id,
                step_number=step_number,
                node_id=node_id,
                node_type=node_type,
                status="started",
                input_data=input_data or {},
                variables_before=variables_before or {},
                variables_after={},
                variable_changes=[],
                parent_step_id=parent_step_id,
                thread_id=thread_id,
            )

            self.db.add(trace)
            self.db.commit()
            self.db.refresh(trace)

            return trace

        except Exception as e:
            logger.error(f"Error creating trace: {e}")
            self.db.rollback()
            raise

    def complete_trace(
        self,
        trace_id: str,
        output_data: Optional[Dict[str, Any]] = None,
        variables_after: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Mark a trace as completed."""
        try:
            trace = self.db.query(ExecutionTrace).filter(
                ExecutionTrace.id == trace_id
            ).first()

            if not trace:
                return False

            trace.output_data = output_data or {}
            trace.variables_after = variables_after or {}
            trace.status = "failed" if error_message else "completed"
            trace.error_message = error_message
            trace.completed_at = datetime.now()

            # Calculate duration
            if trace.started_at:
                duration = trace.completed_at - trace.started_at
                trace.duration_ms = int(duration.total_seconds() * 1000)

            # Track variable changes
            if trace.variables_before and variables_after:
                changes = self._calculate_variable_changes(
                    trace.variables_before, variables_after
                )
                trace.variable_changes = changes

            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Error completing trace: {e}")
            self.db.rollback()
            return False

    def get_execution_traces(
        self,
        execution_id: str,
        debug_session_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ExecutionTrace]:
        """Get execution traces for an execution."""
        query = self.db.query(ExecutionTrace).filter(
            ExecutionTrace.execution_id == execution_id
        )

        if debug_session_id:
            query = query.filter(ExecutionTrace.debug_session_id == debug_session_id)

        return query.order_by(ExecutionTrace.step_number).limit(limit).all()

    def _calculate_variable_changes(
        self, before: Dict[str, Any], after: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calculate changes between variable states."""
        changes = []

        for key, new_value in after.items():
            old_value = before.get(key)

            if key not in before:
                changes.append({
                    "variable": key,
                    "type": "added",
                    "old_value": None,
                    "new_value": new_value,
                })
            elif old_value != new_value:
                changes.append({
                    "variable": key,
                    "type": "changed",
                    "old_value": old_value,
                    "new_value": new_value,
                })

        for key in before:
            if key not in after:
                changes.append({
                    "variable": key,
                    "type": "removed",
                    "old_value": before[key],
                    "new_value": None,
                })

        return changes

    # ==================== Variable Inspection ====================

    def create_variable_snapshot(
        self,
        trace_id: str,
        variable_name: str,
        variable_path: str,
        variable_type: str,
        value: Any,
        scope: str = "local",
        is_watch: bool = False,
        debug_session_id: Optional[str] = None,
    ) -> DebugVariable:
        """Create a variable snapshot for inspection."""
        try:
            # Generate preview for complex objects
            value_preview = self._generate_value_preview(value)

            variable = DebugVariable(
                trace_id=trace_id,
                debug_session_id=debug_session_id,
                variable_name=variable_name,
                variable_path=variable_path,
                variable_type=variable_type,
                value=value,
                value_preview=value_preview,
                scope=scope,
                is_watch=is_watch,
            )

            self.db.add(variable)
            self.db.commit()
            self.db.refresh(variable)

            return variable

        except Exception as e:
            logger.error(f"Error creating variable snapshot: {e}")
            self.db.rollback()
            raise

    def get_variables_for_trace(self, trace_id: str) -> List[DebugVariable]:
        """Get all variable snapshots for a trace."""
        return self.db.query(DebugVariable).filter(
            DebugVariable.trace_id == trace_id
        ).all()

    def get_watch_variables(self, debug_session_id: str) -> List[DebugVariable]:
        """Get all watch expressions for a debug session."""
        return self.db.query(DebugVariable).filter(
            and_(
                DebugVariable.debug_session_id == debug_session_id,
                DebugVariable.is_watch == True,
            )
        ).all()

    def _generate_value_preview(self, value: Any, max_length: int = 100) -> Optional[str]:
        """Generate a string preview for complex values."""
        if value is None:
            return "null"

        value_type = type(value).__name__

        if value_type in ("str", "int", "float", "bool"):
            return str(value)

        if value_type == "dict":
            return f"dict({len(value)} keys)"

        if value_type == "list":
            return f"list({len(value)} items)"

        if value_type == "set":
            return f"set({len(value)} items)"

        return str(value)[:max_length]
