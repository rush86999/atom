"""
Workflow Debugger Service

Provides step-through debugging capabilities for workflows including:
- Breakpoint management (add, remove, enable, disable)
- Step execution control (step over, step into, step out, continue, pause)
- Variable inspection and modification
- Execution trace recording
- Debug session management
- Call stack tracking for nested workflows
- Session persistence (save/restore)
- Performance profiling
- Collaborative debugging
- Real-time trace streaming
"""

import asyncio
import copy
from datetime import datetime
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.expression_parser import get_expression_evaluator
from core.models import (
    DebugVariable,
    ExecutionTrace,
    WorkflowBreakpoint,
    WorkflowDebugSession,
    WorkflowExecution,
)
from core.websocket_manager import get_debugging_websocket_manager

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
        self.expression_evaluator = get_expression_evaluator()

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
        """
        Evaluate a conditional breakpoint expression using safe expression parser.

        Uses the ExpressionParser instead of eval() for security.
        """
        try:
            return self.expression_evaluator.evaluate(condition, variables)
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{condition}': {e}")
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

    def step_into(self, session_id: str, node_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Step into a nested workflow or function.

        Pushes current frame onto call stack and enters nested context.
        """
        session = self.get_debug_session(session_id)
        if not session:
            return None

        # Push current frame onto call stack
        call_stack = session.call_stack or []
        current_frame = {
            "step_number": session.current_step,
            "node_id": session.current_node_id,
            "workflow_id": session.workflow_id,
        }
        call_stack.append(current_frame)
        session.call_stack = call_stack

        # Move into child workflow
        session.current_step += 1
        if node_id:
            session.current_node_id = node_id
        session.updated_at = datetime.now()
        self.db.commit()

        logger.info(f"Stepped into node {node_id}, call stack depth: {len(call_stack)}")

        return {
            "session_id": session_id,
            "current_step": session.current_step,
            "current_node_id": session.current_node_id,
            "call_stack_depth": len(call_stack),
            "action": "step_into",
        }

    def step_out(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Step out of current nested workflow to parent.

        Pops current frame from call stack and returns to parent context.
        """
        session = self.get_debug_session(session_id)
        if not session:
            return None

        call_stack = session.call_stack or []

        if not call_stack:
            logger.warning(f"Cannot step out: call stack is empty for session {session_id}")
            return None

        # Pop current frame and restore parent
        parent_frame = call_stack.pop()
        session.call_stack = call_stack
        session.current_step = parent_frame["step_number"] + 1
        session.current_node_id = parent_frame["node_id"]
        session.updated_at = datetime.now()
        self.db.commit()

        logger.info(f"Stepped out to node {session.current_node_id}, call stack depth: {len(call_stack)}")

        return {
            "session_id": session_id,
            "current_step": session.current_step,
            "current_node_id": session.current_node_id,
            "call_stack_depth": len(call_stack),
            "parent_frame": parent_frame,
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

    # ==================== Variable Modification ====================

    def modify_variable(
        self,
        session_id: str,
        variable_name: str,
        new_value: Any,
        scope: str = "local",
        trace_id: Optional[str] = None,
    ) -> Optional[DebugVariable]:
        """
        Modify a variable value during debugging.

        Allows developers to change variable values at runtime to test different scenarios.
        """
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return None

            # Update variable in session state
            variables = session.variables or {}
            old_value = variables.get(variable_name)

            # Create variable snapshot for audit trail
            variable = DebugVariable(
                trace_id=trace_id or "",
                debug_session_id=session_id,
                variable_name=variable_name,
                variable_path=variable_name,
                variable_type=type(new_value).__name__,
                value=new_value,
                value_preview=self._generate_value_preview(new_value),
                scope=scope,
                is_mutable=True,
                is_changed=True,
                previous_value=old_value,
            )

            self.db.add(variable)

            # Update session variable state
            variables[variable_name] = new_value
            session.variables = variables
            session.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(variable)

            logger.info(f"Modified variable {variable_name} in session {session_id}")
            return variable

        except Exception as e:
            logger.error(f"Error modifying variable: {e}")
            self.db.rollback()
            return None

    def bulk_modify_variables(
        self,
        session_id: str,
        modifications: List[Dict[str, Any]],
        scope: str = "local",
    ) -> List[DebugVariable]:
        """
        Modify multiple variables at once.

        Args:
            session_id: Debug session ID
            modifications: List of {variable_name, new_value} dictionaries
            scope: Variable scope

        Returns:
            List of modified variable snapshots
        """
        results = []
        for mod in modifications:
            variable_name = mod.get("variable_name")
            new_value = mod.get("new_value")
            if variable_name is not None:
                result = self.modify_variable(session_id, variable_name, new_value, scope)
                if result:
                    results.append(result)
        return results

    # ==================== Session Persistence ====================

    def export_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Export debug session to JSON for persistence.

        Allows saving debug sessions for later analysis or sharing.
        """
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return None

            # Get session data
            breakpoints = self.get_breakpoints(session.workflow_id, session.user_id)
            traces = self.get_execution_traces(session.execution_id or "", session_id) if session.execution_id else []

            export_data = {
                "session": {
                    "id": session.id,
                    "workflow_id": session.workflow_id,
                    "execution_id": session.execution_id,
                    "user_id": session.user_id,
                    "session_name": session.session_name,
                    "status": session.status,
                    "current_step": session.current_step,
                    "current_node_id": session.current_node_id,
                    "variables": session.variables,
                    "call_stack": session.call_stack,
                    "stop_on_entry": session.stop_on_entry,
                    "stop_on_exceptions": session.stop_on_exceptions,
                    "stop_on_error": session.stop_on_error,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                    "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                },
                "breakpoints": [
                    {
                        "id": bp.id,
                        "node_id": bp.node_id,
                        "edge_id": bp.edge_id,
                        "breakpoint_type": bp.breakpoint_type,
                        "condition": bp.condition,
                        "hit_count": bp.hit_count,
                        "hit_limit": bp.hit_limit,
                        "is_disabled": bp.is_disabled,
                        "log_message": bp.log_message,
                    }
                    for bp in breakpoints
                ],
                "traces": [
                    {
                        "id": trace.id,
                        "step_number": trace.step_number,
                        "node_id": trace.node_id,
                        "node_type": trace.node_type,
                        "status": trace.status,
                        "input_data": trace.input_data,
                        "output_data": trace.output_data,
                        "error_message": trace.error_message,
                        "duration_ms": trace.duration_ms,
                        "started_at": trace.started_at.isoformat() if trace.started_at else None,
                        "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
                    }
                    for trace in traces
                ],
                "exported_at": datetime.now().isoformat(),
            }

            logger.info(f"Exported debug session {session_id}")
            return export_data

        except Exception as e:
            logger.error(f"Error exporting session: {e}")
            return None

    def import_session(
        self,
        export_data: Dict[str, Any],
        restore_breakpoints: bool = True,
        restore_variables: bool = True,
    ) -> Optional[WorkflowDebugSession]:
        """
        Import a previously exported debug session.

        Args:
            export_data: Exported session data from export_session()
            restore_breakpoints: Whether to restore breakpoints
            restore_variables: Whether to restore variable state

        Returns:
            New debug session with imported data
        """
        try:
            session_data = export_data.get("session", {})
            breakpoints_data = export_data.get("breakpoints", [])
            traces_data = export_data.get("traces", [])

            # Create new session from imported data
            new_session = self.create_debug_session(
                workflow_id=session_data["workflow_id"],
                user_id=session_data["user_id"],
                session_name=f"{session_data['session_name']} (Imported)",
                stop_on_entry=session_data.get("stop_on_entry", False),
                stop_on_exceptions=session_data.get("stop_on_exceptions", True),
                stop_on_error=session_data.get("stop_on_error", True),
            )

            # Restore variables
            if restore_variables and session_data.get("variables"):
                new_session.variables = session_data["variables"]
                new_session.call_stack = session_data.get("call_stack", [])
                self.db.commit()

            # Restore breakpoints
            if restore_breakpoints:
                for bp_data in breakpoints_data:
                    self.add_breakpoint(
                        workflow_id=session_data["workflow_id"],
                        node_id=bp_data["node_id"],
                        user_id=session_data["user_id"],
                        debug_session_id=new_session.id,
                        edge_id=bp_data.get("edge_id"),
                        breakpoint_type=bp_data.get("breakpoint_type", "node"),
                        condition=bp_data.get("condition"),
                        hit_limit=bp_data.get("hit_limit"),
                        log_message=bp_data.get("log_message"),
                    )

            logger.info(f"Imported debug session as {new_session.id}")
            return new_session

        except Exception as e:
            logger.error(f"Error importing session: {e}")
            self.db.rollback()
            return None

    # ==================== Performance Profiling ====================

    def start_performance_profiling(self, session_id: str) -> bool:
        """
        Start performance profiling for a debug session.

        Records execution time for each step to identify bottlenecks.
        """
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return False

            # Initialize performance metrics
            session.performance_metrics = {
                "enabled": True,
                "started_at": datetime.now().isoformat(),
                "step_times": [],
                "node_times": {},
                "total_duration_ms": 0,
            }
            session.updated_at = datetime.now()
            self.db.commit()

            logger.info(f"Started performance profiling for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error starting performance profiling: {e}")
            self.db.rollback()
            return False

    def record_step_timing(
        self,
        session_id: str,
        node_id: str,
        node_type: str,
        duration_ms: int,
    ) -> bool:
        """
        Record timing data for a workflow step.

        Called by the workflow engine during execution when profiling is enabled.
        """
        try:
            session = self.get_debug_session(session_id)
            if not session or not session.performance_metrics:
                return False

            metrics = session.performance_metrics
            metrics["step_times"].append({
                "node_id": node_id,
                "node_type": node_type,
                "duration_ms": duration_ms,
                "timestamp": datetime.now().isoformat(),
            })

            # Aggregate by node
            if node_id not in metrics["node_times"]:
                metrics["node_times"][node_id] = {
                    "count": 0,
                    "total_ms": 0,
                    "avg_ms": 0,
                    "min_ms": float('inf'),
                    "max_ms": 0,
                }

            node_metrics = metrics["node_times"][node_id]
            node_metrics["count"] += 1
            node_metrics["total_ms"] += duration_ms
            node_metrics["avg_ms"] = node_metrics["total_ms"] / node_metrics["count"]
            node_metrics["min_ms"] = min(node_metrics["min_ms"], duration_ms)
            node_metrics["max_ms"] = max(node_metrics["max_ms"], duration_ms)

            # Update total duration
            metrics["total_duration_ms"] += duration_ms

            session.updated_at = datetime.now()
            self.db.commit()

            return True

        except Exception as e:
            logger.error(f"Error recording step timing: {e}")
            return False

    def get_performance_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Generate a performance report for a debug session.

        Returns aggregated timing data and bottleneck identification.
        """
        try:
            session = self.get_debug_session(session_id)
            if not session or not session.performance_metrics:
                return None

            metrics = session.performance_metrics

            # Find bottlenecks (slowest steps)
            sorted_steps = sorted(
                metrics["step_times"],
                key=lambda x: x["duration_ms"],
                reverse=True,
            )

            # Find slowest nodes by average time
            sorted_nodes = sorted(
                [
                    {"node_id": node_id, **data}
                    for node_id, data in metrics["node_times"].items()
                ],
                key=lambda x: x["avg_ms"],
                reverse=True,
            )

            report = {
                "session_id": session_id,
                "total_duration_ms": metrics["total_duration_ms"],
                "total_steps": len(metrics["step_times"]),
                "average_step_duration_ms": metrics["total_duration_ms"] / len(metrics["step_times"]) if metrics["step_times"] else 0,
                "slowest_steps": sorted_steps[:10],  # Top 10 slowest steps
                "slowest_nodes": sorted_nodes[:10],  # Top 10 slowest nodes by average
                "profiling_started_at": metrics.get("started_at"),
                "generated_at": datetime.now().isoformat(),
            }

            return report

        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return None

    # ==================== Collaborative Debugging ====================

    def add_collaborator(
        self,
        session_id: str,
        user_id: str,
        permission: str = "viewer",
    ) -> bool:
        """
        Add a collaborator to a debug session.

        Permissions:
        - viewer: Can view session state and traces
        - operator: Can control execution (step, pause, continue)
        - owner: Full control including modifying breakpoints and variables
        """
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return False

            collaborators = session.collaborators or {}

            collaborators[user_id] = {
                "permission": permission,
                "added_at": datetime.now().isoformat(),
            }

            session.collaborators = collaborators
            session.updated_at = datetime.now()
            self.db.commit()

            logger.info(f"Added collaborator {user_id} with permission {permission} to session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding collaborator: {e}")
            self.db.rollback()
            return False

    def remove_collaborator(self, session_id: str, user_id: str) -> bool:
        """Remove a collaborator from a debug session."""
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return False

            collaborators = session.collaborators or {}

            if user_id in collaborators:
                del collaborators[user_id]
                session.collaborators = collaborators
                session.updated_at = datetime.now()
                self.db.commit()

                logger.info(f"Removed collaborator {user_id} from session {session_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error removing collaborator: {e}")
            self.db.rollback()
            return False

    def check_collaborator_permission(
        self,
        session_id: str,
        user_id: str,
        required_permission: str,
    ) -> bool:
        """
        Check if a collaborator has the required permission.

        Permission hierarchy: viewer < operator < owner
        """
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return False

            # Session owner has all permissions
            if session.user_id == user_id:
                return True

            collaborators = session.collaborators or {}
            collaborator = collaborators.get(user_id)

            if not collaborator:
                return False

            permission_hierarchy = {"viewer": 1, "operator": 2, "owner": 3}
            user_level = permission_hierarchy.get(collaborator["permission"], 0)
            required_level = permission_hierarchy.get(required_permission, 0)

            return user_level >= required_level

        except Exception as e:
            logger.error(f"Error checking collaborator permission: {e}")
            return False

    def get_session_collaborators(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all collaborators for a debug session."""
        try:
            session = self.get_debug_session(session_id)
            if not session:
                return []

            collaborators = session.collaborators or {}

            return [
                {
                    "user_id": user_id,
                    "permission": data["permission"],
                    "added_at": data["added_at"],
                }
                for user_id, data in collaborators.items()
            ]

        except Exception as e:
            logger.error(f"Error getting collaborators: {e}")
            return []

    # ==================== Real-time Trace Streaming ====================

    def create_trace_stream(
        self,
        session_id: str,
        execution_id: str,
    ) -> str:
        """
        Create a unique stream ID for real-time trace updates.

        Returns a stream ID that can be used with WebSocket connections.
        """
        stream_id = f"trace_{execution_id}_{session_id}_{uuid.uuid4().hex[:8]}"

        logger.info(f"Created trace stream {stream_id} for execution {execution_id}")
        return stream_id

    def stream_trace_update(
        self,
        stream_id: str,
        trace_data: Dict[str, Any],
        websocket_manager=None,
    ) -> bool:
        """
        Stream a trace update via WebSocket.

        Args:
            stream_id: Stream identifier from create_trace_stream()
            trace_data: Trace data to stream
            websocket_manager: WebSocket manager instance (optional)

        Returns:
            True if streamed successfully, False otherwise
        """
        try:
            if websocket_manager:
                # Broadcast trace update to all subscribers
                websocket_manager.broadcast(stream_id, {
                    "type": "trace_update",
                    "data": trace_data,
                    "timestamp": datetime.now().isoformat(),
                })
                logger.debug(f"Streamed trace update for stream {stream_id}")
                return True

            # Fallback: Log the trace data
            logger.info(f"Trace stream update (no WebSocket): {stream_id}")
            return False

        except Exception as e:
            logger.error(f"Error streaming trace update: {e}")
            return False

    def close_trace_stream(self, stream_id: str, websocket_manager=None) -> bool:
        """Close a trace stream and clean up resources."""
        try:
            if websocket_manager:
                # Notify subscribers that stream is closing
                websocket_manager.broadcast(stream_id, {
                    "type": "stream_closed",
                    "stream_id": stream_id,
                    "timestamp": datetime.now().isoformat(),
                })

            logger.info(f"Closed trace stream {stream_id}")
            return True

        except Exception as e:
            logger.error(f"Error closing trace stream: {e}")
            return False

    # ==================== WebSocket Integration Helpers ====================

    def _run_async_websocket(self, coro) -> int:
        """
        Run an async WebSocket method in a fire-and-forget manner.

        Args:
            coro: Async coroutine to run

        Returns:
            Number of subscribers notified (0 if failed or no event loop)
        """
        try:
            # Try to get running event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create task in running loop
                    asyncio.create_task(coro)
                    return 0  # Can't get result from fire-and-forget
                else:
                    # Run in new loop
                    return asyncio.run(coro)
            except RuntimeError:
                # No event loop, run in new one
                return asyncio.run(coro)
        except Exception as e:
            logger.debug(f"WebSocket notification skipped: {e}")
            return 0

    def stream_trace_with_manager(
        self,
        execution_id: str,
        session_id: str,
        trace_data: Dict[str, Any],
    ) -> None:
        """
        Stream a trace update using the debugging WebSocket manager.

        Convenience method that integrates with the DebuggingWebSocketManager.
        Runs asynchronously in fire-and-forget mode.

        Args:
            execution_id: Execution identifier
            session_id: Debug session identifier
            trace_data: Trace data to stream
        """
        async def _stream():
            debug_manager = get_debugging_websocket_manager()
            await debug_manager.stream_trace(execution_id, session_id, trace_data)

        self._run_async_websocket(_stream())

    def notify_variable_changed(
        self,
        session_id: str,
        variable_name: str,
        new_value: Any,
        previous_value: Any = None,
    ) -> None:
        """
        Notify subscribers that a variable was modified.

        Args:
            session_id: Debug session identifier
            variable_name: Name of the variable
            new_value: New value
            previous_value: Previous value (optional)
        """
        async def _notify():
            debug_manager = get_debugging_websocket_manager()
            await debug_manager.notify_variable_changed(
                session_id, variable_name, new_value, previous_value
            )

        self._run_async_websocket(_notify())

    def notify_breakpoint_hit(
        self,
        session_id: str,
        breakpoint_id: str,
        node_id: str,
        hit_count: int,
    ) -> None:
        """
        Notify subscribers that a breakpoint was hit.

        Args:
            session_id: Debug session identifier
            breakpoint_id: Breakpoint identifier
            node_id: Node where breakpoint was hit
            hit_count: Current hit count
        """
        async def _notify():
            debug_manager = get_debugging_websocket_manager()
            await debug_manager.notify_breakpoint_hit(
                session_id, breakpoint_id, node_id, hit_count
            )

        self._run_async_websocket(_notify())

    def notify_session_paused(
        self,
        session_id: str,
        reason: str = "user_action",
        node_id: Optional[str] = None,
    ) -> None:
        """
        Notify subscribers that a session was paused.

        Args:
            session_id: Debug session identifier
            reason: Reason for pausing
            node_id: Current node ID (optional)
        """
        async def _notify():
            debug_manager = get_debugging_websocket_manager()
            await debug_manager.notify_session_paused(session_id, reason, node_id)

        self._run_async_websocket(_notify())

    def notify_session_resumed(self, session_id: str) -> None:
        """
        Notify subscribers that a session was resumed.

        Args:
            session_id: Debug session identifier
        """
        async def _notify():
            debug_manager = get_debugging_websocket_manager()
            await debug_manager.notify_session_resumed(session_id)

        self._run_async_websocket(_notify())

    def notify_step_completed(
        self,
        session_id: str,
        action: str,
        step_number: int,
        node_id: Optional[str] = None,
    ) -> None:
        """
        Notify subscribers that a step action completed.

        Args:
            session_id: Debug session identifier
            action: Action performed (step_over, step_into, step_out)
            step_number: New step number
            node_id: Current node ID (optional)
        """
        async def _notify():
            debug_manager = get_debugging_websocket_manager()
            await debug_manager.notify_step_completed(
                session_id, action, step_number, node_id
            )

        self._run_async_websocket(_notify())
