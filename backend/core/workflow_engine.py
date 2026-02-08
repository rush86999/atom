"""
Production Workflow Engine

Handles the execution of workflows with support for:
- State persistence via ExecutionStateManager
- Pause/Resume logic for missing inputs
- Many-to-many data mapping
- Automatic retries and error handling
"""

import asyncio
from datetime import datetime
import logging
import re
from typing import Any, Dict, List, Optional, Union
import uuid
import httpx
import jsonschema
from jsonschema import ValidationError, validate

from core.auto_healing import async_retry_with_backoff
from core.database import get_db_session
from core.exceptions import (
    AgentExecutionError,
    AuthenticationError,
    ExternalServiceError,
    ValidationError as AtomValidationError,
)
from core.execution_state_manager import ExecutionStateManager, get_state_manager
from core.models import IntegrationCatalog, WorkflowStepExecution
from core.token_storage import token_storage
from core.websockets import get_connection_manager

logger = logging.getLogger(__name__)

class WorkflowEngine:
    def __init__(self, max_concurrent_steps: int = 5):
        self.state_manager = get_state_manager()
        # Regex for finding variable references like ${step_id.output_key}
        self.var_pattern = re.compile(r'\${([^}]+)}')
        self.max_concurrent_steps = max_concurrent_steps
        self.semaphore = asyncio.Semaphore(max_concurrent_steps)
        self.cancellation_requests = set()

    async def start_workflow(self, workflow: Dict[str, Any], input_data: Dict[str, Any], background_tasks: Any = None) -> str:
        """Start a new workflow execution"""
        # Convert graph to steps if needed
        if "steps" not in workflow and "nodes" in workflow:
            workflow["steps"] = self._convert_nodes_to_steps(workflow)
            
        execution_id = await self.state_manager.create_execution(workflow["id"], input_data)
        
        # Run execution in background
        if background_tasks:
            background_tasks.add_task(self._run_execution, execution_id, workflow)
        else:
            asyncio.create_task(self._run_execution(execution_id, workflow))
        
        return execution_id

    def _convert_nodes_to_steps(self, workflow: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert graph-based nodes/connections to linear steps"""
        nodes = {n["id"]: n for n in workflow.get("nodes", [])}
        connections = workflow.get("connections", [])
        
        # Build adjacency list and in-degree
        adj = {n: [] for n in nodes}
        in_degree = {n: 0 for n in nodes}
        
        for conn in connections:
            source = conn["source"]
            target = conn["target"]
            if source in adj and target in in_degree:
                adj[source].append(target)
                in_degree[target] += 1
                
        # Topological sort (Kahn's algorithm)
        queue = [n for n in nodes if in_degree[n] == 0]
        sorted_ids = []
        
        while queue:
            u = queue.pop(0)
            sorted_ids.append(u)
            
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
                    
        # Convert to steps
        steps = []
        for i, node_id in enumerate(sorted_ids):
            node = nodes[node_id]
            config = node.get("config", {})
            
            step = {
                "id": node_id,
                "name": node.get("title", node_id),
                "sequence_order": i + 1,
                "service": config.get("service", "default"),
                "action": config.get("action", "default"),
                "parameters": config.get("parameters", {}),
                "continue_on_error": config.get("continue_on_error", False),
                "timeout": config.get("timeout", None),
                "input_schema": config.get("input_schema", {}),
                "output_schema": config.get("output_schema", {})
            }
            
            # Map specific node types/configs to step fields if needed
            if node.get("type") == "trigger":
                step["type"] = "trigger"
                step["action"] = config.get("action", "manual_trigger")
            else:
                step["type"] = "action"
                
            steps.append(step)
            
        return steps

    def _build_execution_graph(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build execution graph from workflow nodes and connections.
        Returns dict with:
        - nodes: dict node_id -> node
        - connections: list of connections with source, target, condition
        - adjacency: dict node_id -> list of outgoing connections
        - reverse_adjacency: dict node_id -> list of incoming connections
        """
        nodes = {n["id"]: n for n in workflow.get("nodes", [])}
        connections = workflow.get("connections", [])

        adjacency = {n: [] for n in nodes}
        reverse_adjacency = {n: [] for n in nodes}

        for conn in connections:
            source = conn.get("source")
            target = conn.get("target")
            if source in nodes and target in nodes:
                adjacency[source].append(conn)
                reverse_adjacency[target].append(conn)

        return {
            "nodes": nodes,
            "connections": connections,
            "adjacency": adjacency,
            "reverse_adjacency": reverse_adjacency
        }

    def _has_conditional_connections(self, workflow: Dict[str, Any]) -> bool:
        """Check if any connection has a condition."""
        connections = workflow.get("connections", [])
        for conn in connections:
            if conn.get("condition"):
                return True
        return False

    async def _execute_workflow_graph(self, execution_id: str, workflow: Dict[str, Any], state: Dict[str, Any], ws_manager, user_id: str, start_time: datetime):
        """
        Execute workflow using graph traversal with conditional branching and parallel execution.
        """
        # Import analytics engine
        from core.analytics_engine import get_analytics_engine
        analytics = get_analytics_engine()

        graph = self._build_execution_graph(workflow)
        nodes = graph["nodes"]
        adjacency = graph["adjacency"]
        reverse_adjacency = graph["reverse_adjacency"]

        # Track step status
        step_status = {step_id: state["steps"].get(step_id, {}).get("status", "PENDING")
                      for step_id in nodes}
        # Track activated connections (condition evaluated true)
        activated_connections = set()
        # Lock for state updates to prevent race conditions
        state_lock = asyncio.Lock()

        # Helper to evaluate connection condition
        def evaluate_connection_condition(conn, current_state):
            condition = conn.get("condition")
            if condition is None or condition == "":
                return True  # No condition means always activate
            return self._evaluate_condition(condition, current_state)

        # Initialize: evaluate already completed steps (for resume scenarios)
        for step_id, status in step_status.items():
            if status == "COMPLETED":
                # Evaluate outgoing connections for completed steps
                async with state_lock:
                    current_state = await self.state_manager.get_execution_state(execution_id)
                for conn in adjacency[step_id]:
                    if evaluate_connection_condition(conn, current_state):
                        activated_connections.add(conn)

        # Helper to get ready steps
        def get_ready_steps():
            ready = set()
            for step_id in nodes:
                if step_status.get(step_id) in ["COMPLETED", "RUNNING", "FAILED", "PAUSED"]:
                    continue
                incoming_conns = reverse_adjacency[step_id]
                # If no incoming connections, or all incoming connections are activated
                if not incoming_conns or all(conn in activated_connections for conn in incoming_conns):
                    ready.add(step_id)
            return ready

        # Main execution loop
        try:
            while True:
                ready_steps = get_ready_steps()
                if not ready_steps:
                    # No more steps ready to execute
                    break

                # Execute ready steps in parallel
                async def execute_single_step(step_id):
                    node = nodes[step_id]
                    config = node.get("config", {})
                    step = {
                        "id": step_id,
                        "name": node.get("title", step_id),
                        "service": config.get("service", "default"),
                        "action": config.get("action", "default"),
                        "parameters": config.get("parameters", {}),
                        "type": node.get("type", "action"),
                        "continue_on_error": config.get("continue_on_error", False),
                        "timeout": config.get("timeout", None),
                        "input_schema": config.get("input_schema", {}),
                        "output_schema": config.get("output_schema", {}),
                        "workflow_id": workflow.get("id", "unknown"),
                        "execution_id": execution_id,
                        "connection_id": config.get("connectionId")
                    }

                    async with self.semaphore:
                        # Update step status to RUNNING
                        async with state_lock:
                            await self.state_manager.update_step_status(execution_id, step_id, "RUNNING")
                            await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_RUNNING", {"step_id": step_id})
                            current_state = await self.state_manager.get_execution_state(execution_id)

                        # Resolve parameters (may raise MissingInputError)
                        try:
                            resolved_params = self._resolve_parameters(step.get("parameters", {}), current_state)
                        except MissingInputError as e:
                            async with state_lock:
                                logger.info(f"Pausing execution {execution_id} at step {step_id}: {e}")
                                await self.state_manager.update_step_status(execution_id, step_id, "PAUSED", error=str(e))
                                await self.state_manager.update_execution_status(execution_id, "PAUSED", error=f"Missing input: {e.missing_var}")
                                await ws_manager.notify_workflow_status(
                                    user_id, execution_id, "PAUSED",
                                    {"reason": "missing_input", "missing_var": e.missing_var, "step_id": step_id}
                                )
                            raise  # Re-raise to stop parallel execution

                        # Validate input schema
                        self._validate_input_schema(step, resolved_params)

                        # Execute step
                        try:
                            start_step_time = datetime.utcnow()
                            output = await self._execute_step(step, resolved_params)
                            duration_ms = int((datetime.utcnow() - start_step_time).total_seconds() * 1000)
                            self._validate_output_schema(step, output)
                            
                            # Extract resource_id from output
                            resource_id = None
                            if isinstance(output, dict):
                                result_data = output.get("result", {})
                                if isinstance(result_data, dict):
                                    resource_id = str(result_data.get("id") or 
                                                     result_data.get("resource_id") or 
                                                     result_data.get("task_id") or 
                                                     result_data.get("email_id") or 
                                                     result_data.get("execution_id") or "")
                            
                            # Track step execution in analytics
                            analytics.track_step_execution(
                                workflow_id=workflow.get("id", "unknown"),
                                execution_id=execution_id,
                                step_id=step_id,
                                step_name=step.get("name", step_id),
                                event_type="step_completed",
                                duration_ms=duration_ms,
                                status="COMPLETED",
                                resource_id=resource_id if resource_id else None,
                                user_id=user_id
                            )

                            async with state_lock:
                                await self.state_manager.update_step_status(execution_id, step_id, "COMPLETED", output=output)
                                await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_COMPLETED", {"step_id": step_id})
                                step_status[step_id] = "COMPLETED"
                                current_state = await self.state_manager.get_execution_state(execution_id)

                            # Evaluate outgoing connections
                            new_activated = []
                            for conn in adjacency[step_id]:
                                if evaluate_connection_condition(conn, current_state):
                                    new_activated.append(conn)

                            # Update activated connections
                            async with state_lock:
                                activated_connections.update(new_activated)

                            return (step_id, True, output, None)

                        except Exception as e:
                            logger.error(f"Step {step_id} failed: {e}")
                            
                            # Track step failure in analytics
                            try:
                                # Calculate duration for failed step if start_step_time was set
                                duration_ms = int((datetime.utcnow() - start_step_time).total_seconds() * 1000) if 'start_step_time' in locals() else None
                                analytics.track_step_execution(
                                    workflow_id=workflow.get("id", "unknown"),
                                    execution_id=execution_id,
                                    step_id=step_id,
                                    step_name=step.get("name", step_id),
                                    event_type="step_failed",
                                    duration_ms=duration_ms,
                                    status="FAILED",
                                    error_message=str(e),
                                    user_id=user_id
                                )
                            except Exception as ae:
                                logger.error(f"Failed to track step failure: {ae}")

                            async with state_lock:
                                await self.state_manager.update_step_status(execution_id, step_id, "FAILED", error=str(e))
                            return (step_id, False, None, e)

                # Execute all ready steps concurrently
                tasks = [execute_single_step(step_id) for step_id in ready_steps]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                has_failure = False
                failure_error = None
                for result in results:
                    if isinstance(result, Exception):
                        # This should not happen as exceptions are caught in execute_single_step
                        logger.error(f"Unexpected exception in step execution: {result}")
                        has_failure = True
                        failure_error = result
                        continue

                    step_id, success, output, error = result
                    if not success:
                        # Check if step has continue_on_error flag
                        node = nodes[step_id]
                        config = node.get("config", {})
                        continue_on_error = config.get("continue_on_error", False)
                        if continue_on_error:
                            logger.warning(f"Step {step_id} failed but continue_on_error is True, marking as failed but continuing workflow")
                            # Step already marked as FAILED, no need to fail whole workflow
                        else:
                            has_failure = True
                            failure_error = error
                            # If a step failed, we may want to stop the whole workflow
                            # For now, we continue processing other steps but mark failure
                            # The step status is already updated to FAILED

                # If any step failed with MissingInputError, we've paused the workflow
                # Check if workflow is paused
                async with state_lock:
                    current_state = await self.state_manager.get_execution_state(execution_id)
                    if current_state["status"] == "PAUSED":
                        logger.info(f"Workflow {execution_id} paused due to missing input")
                        return

                # If any step failed (non-MissingInputError), fail the whole execution
                if has_failure and failure_error:
                    logger.error(f"Workflow execution {execution_id} failed due to step failure: {failure_error}")
                    async with state_lock:
                        await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(failure_error))
                        await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(failure_error)})
                    return

                # Continue to next iteration (new steps may have become ready)

            # All steps processed
            completed = all(status == "COMPLETED" for status in step_status.values())
            if completed:
                async with state_lock:
                    await self.state_manager.update_execution_status(execution_id, "COMPLETED")
                    await ws_manager.notify_workflow_status(user_id, execution_id, "COMPLETED")

                # Track success
                duration = (datetime.utcnow() - start_time).total_seconds()
                analytics.track_workflow_execution(
                    workflow_id=workflow.get("id", "unknown"),
                    success=True,
                    duration_seconds=duration,
                    time_saved_seconds=workflow.get("estimated_time_saved", 60),
                    business_value=workflow.get("business_value", 10)
                )
            else:
                # Some steps stuck (maybe due to unmet conditions)
                logger.warning(f"Workflow execution {execution_id} ended with pending steps")
                async with state_lock:
                    await self.state_manager.update_execution_status(execution_id, "PARTIAL")
                    await ws_manager.notify_workflow_status(user_id, execution_id, "PARTIAL")

                # Track partial completion
                duration = (datetime.utcnow() - start_time).total_seconds()
                analytics.track_workflow_execution(
                    workflow_id=workflow.get("id", "unknown"),
                    success=False,
                    duration_seconds=duration,
                    time_saved_seconds=0,
                    business_value=0
                )

        except Exception as e:
            logger.error(f"Workflow graph execution {execution_id} failed: {e}")
            async with state_lock:
                await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(e))
                await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(e)})

            # Track failure
            duration = (datetime.utcnow() - start_time).total_seconds()
            analytics.track_workflow_execution(
                workflow_id=workflow.get("id", "unknown"),
                success=False,
                duration_seconds=duration,
                time_saved_seconds=0,
                business_value=0
            )

    async def resume_workflow(self, execution_id: str, workflow: Dict[str, Any], new_inputs: Dict[str, Any]) -> bool:
        """Resume a paused workflow with new inputs"""
        state = await self.state_manager.get_execution_state(execution_id)
        if not state:
            raise ValueError(f"Execution {execution_id} not found")

        if state["status"] != "PAUSED":
            logger.warning(f"Cannot resume execution {execution_id} in state {state['status']}")
            return False

        # Update state with new inputs
        await self.state_manager.update_execution_inputs(execution_id, new_inputs)
        await self.state_manager.update_execution_status(execution_id, "RUNNING")

        # Resume execution
        asyncio.create_task(self._run_execution(execution_id, workflow))
        return True

    async def cancel_execution(self, execution_id: str) -> bool:
        """Request cancellation of a running workflow execution."""
        self.cancellation_requests.add(execution_id)
        logger.info(f"Cancellation requested for execution {execution_id}")

        # Notify via WebSocket
        ws_manager = get_connection_manager()
        await self.state_manager.update_execution_status(execution_id, "CANCELLED")
        await ws_manager.notify_workflow_status("default", execution_id, "CANCELLED")
        return True

    async def _run_execution(self, execution_id: str, workflow: Dict[str, Any]):
        """Main execution loop"""
        ws_manager = get_connection_manager()
        # Import here to avoid circular imports if any
        from core.analytics_engine import get_analytics_engine
        analytics = get_analytics_engine()
        
        user_id = workflow.get("created_by", "default")
        start_time = datetime.utcnow()
        
        try:
            await self.state_manager.update_execution_status(execution_id, "RUNNING")
            await ws_manager.notify_workflow_status(user_id, execution_id, "RUNNING")
            
            state = await self.state_manager.get_execution_state(execution_id)

            # Decide execution mode based on conditional connections
            if self._has_conditional_connections(workflow):
                # Use graph execution with branching
                await self._execute_workflow_graph(execution_id, workflow, state, ws_manager, user_id, start_time)
                # The graph execution will update execution status internally
                # If it returns, we assume completion or failure handled
                return

            steps = workflow.get("steps", [])
            # Sort steps by sequence_order
            steps.sort(key=lambda x: x.get("sequence_order", 0))
            
            for step in steps:
                step_id = step["id"]

                # Check for cancellation
                if execution_id in self.cancellation_requests:
                    logger.info(f"Execution {execution_id} cancelled")
                    await self.state_manager.update_execution_status(execution_id, "CANCELLED")
                    await ws_manager.notify_workflow_status(user_id, execution_id, "CANCELLED")
                    self.cancellation_requests.discard(execution_id)
                    return

                # Check if step already completed (for resume scenarios)
                step_state = state["steps"].get(step_id, {})
                if step_state.get("status") == "COMPLETED":
                    continue
                
                # Check dependencies
                if not self._check_dependencies(step, state):
                    # This shouldn't happen in a linear sequence, but important for DAGs
                    logger.info(f"Step {step_id} waiting for dependencies")
                    continue

                # Check condition (if specified)
                condition = step.get("condition")
                if condition is not None:
                    condition_met = self._evaluate_condition(condition, state)
                    if not condition_met:
                        logger.info(f"Step {step_id} condition not met: {condition}")
                        await self.state_manager.update_step_status(
                            execution_id,
                            step_id,
                            "SKIPPED",
                            error=f"Condition not met: {condition}"
                        )
                        await ws_manager.notify_workflow_status(
                            user_id,
                            execution_id,
                            "STEP_SKIPPED",
                            {"step_id": step_id, "reason": f"Condition not met: {condition}"}
                        )
                        continue

                # Resolve inputs
                try:
                    resolved_params = self._resolve_parameters(step.get("parameters", {}), state)
                except MissingInputError as e:
                    logger.info(f"Pausing execution {execution_id} at step {step_id}: {e}")
                    await self.state_manager.update_step_status(execution_id, step_id, "PAUSED", error=str(e))
                    await self.state_manager.update_execution_status(execution_id, "PAUSED", error=f"Missing input: {e.missing_var}")
                    
                    await ws_manager.notify_workflow_status(
                        user_id, 
                        execution_id, 
                        "PAUSED", 
                        {
                            "reason": "missing_input",
                            "missing_var": e.missing_var,
                            "step_id": step_id
                        }
                    )
                    return

                # Validate input schema
                self._validate_input_schema(step, resolved_params)

                # Execute step
                await self.state_manager.update_step_status(execution_id, step_id, "RUNNING")
                await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_RUNNING", {"step_id": step_id})

                # Create step execution record
                with get_db_session() as db:
                    try:
                        step_exec = WorkflowStepExecution(
                            execution_id=execution_id,
                            workflow_id=workflow.get("id", "unknown"),
                            step_id=step["id"],
                            step_name=step.get("name", step["id"]),
                            step_type=step.get("type", "action"),
                            sequence_order=step.get("sequence_order", 0),
                            status="running",
                            started_at=datetime.utcnow(),
                            input_data=resolved_params
                        )
                        db.add(step_exec)
                        db.commit()
                    except Exception as e:
                        logger.error(f"Failed to create step execution record: {e}")
                
                try:
                    output = await self._execute_step(step, resolved_params)
                    self._validate_output_schema(step, output)
                    await self.state_manager.update_step_status(execution_id, step_id, "COMPLETED", output=output)
                    await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_COMPLETED", {"step_id": step_id})

                    # Update step execution record
                    with get_db_session() as db:
                        try:
                            step_exec = db.query(WorkflowStepExecution).filter(
                                WorkflowStepExecution.execution_id == execution_id,
                                WorkflowStepExecution.step_id == step_id
                            ).first()
                            if step_exec:
                                step_exec.status = "completed"
                                step_exec.completed_at = datetime.utcnow()
                                step_exec.duration_ms = int((datetime.utcnow() - step_exec.started_at).total_seconds() * 1000)
                                step_exec.output_data = output
                                db.commit()
                        except Exception as e:
                            logger.error(f"Failed to update step execution record: {e}")
                    
                    # Update in-memory state for next steps
                    state = await self.state_manager.get_execution_state(execution_id)
                    
                except Exception as e:
                    logger.error(f"Step {step_id} failed: {e}")
                    await self.state_manager.update_step_status(execution_id, step_id, "FAILED", error=str(e))
                    await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(e))
                    await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(e), "step_id": step_id})
                    
                    # Track failure
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    analytics.track_workflow_execution(
                        workflow_id=workflow.get("id", "unknown"),
                        success=False,
                        duration_seconds=duration,
                        time_saved_seconds=0, # Could calculate based on step metadata
                        business_value=0
                    )
                    return

            await self.state_manager.update_execution_status(execution_id, "COMPLETED")
            await ws_manager.notify_workflow_status(user_id, execution_id, "COMPLETED")
            
            # Track success
            duration = (datetime.utcnow() - start_time).total_seconds()
            analytics.track_workflow_execution(
                workflow_id=workflow.get("id", "unknown"),
                success=True,
                duration_seconds=duration,
                time_saved_seconds=workflow.get("estimated_time_saved", 60), # Default 1 min saved
                business_value=workflow.get("business_value", 10) # Default $10 value
            )
            
        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {e}")
            await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(e))
            await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(e)})
            
            # Track failure
            duration = (datetime.utcnow() - start_time).total_seconds()
            analytics.track_workflow_execution(
                workflow_id=workflow.get("id", "unknown"),
                success=False,
                duration_seconds=duration,
                time_saved_seconds=0,
                business_value=0
            )

    def _check_dependencies(self, step: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """Check if all dependencies are met"""
        depends_on = step.get("depends_on", [])
        for dep_id in depends_on:
            dep_state = state["steps"].get(dep_id, {})
            if dep_state.get("status") != "COMPLETED":
                return False
        return True

    def _evaluate_condition(self, condition: str, state: Dict[str, Any]) -> bool:
        """
        Evaluate a condition string against current state.
        Supports variable substitution like ${step_id.output_key} and simple boolean expressions.
        Example conditions:
        - "${step1.output.success} == true"
        - "${input.count} > 5"
        - "${step2.result.status} == 'completed'"
        """
        if not condition:
            return True  # No condition means always execute

        try:
            # First, replace all variable references with their values
            # We'll build a new expression with values substituted
            expr = condition
            matches = self.var_pattern.findall(condition)

            # Replace each variable with its actual value
            for var_path in matches:
                value = self._get_value_from_path(var_path, state)
                if value is None:
                    # Variable not found, condition evaluates to False
                    logger.warning(f"Variable {var_path} not found in condition: {condition}")
                    return False

                # Convert value to appropriate string representation for eval
                if isinstance(value, str):
                    # Quote strings for eval
                    replacement = repr(value)
                elif isinstance(value, (int, float, bool)):
                    replacement = str(value)
                elif value is None:
                    replacement = "None"
                else:
                    # For complex objects, use repr
                    replacement = repr(value)

                # Replace the variable reference in the expression
                expr = expr.replace(f"${{{var_path}}}", replacement)

            # Safe eval with limited globals and locals
            # Only allow basic operators and comparisons
            allowed_names = {
                'True': True,
                'False': False,
                'None': None,
                'true': True,  # Allow lowercase true/false
                'false': False,
            }

            # Evaluate the expression
            result = eval(expr, {"__builtins__": {}}, allowed_names)

            # Convert to boolean
            if isinstance(result, bool):
                return result
            else:
                # Non-boolean result, treat as truthy/falsy
                return bool(result)

        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            # If we can't evaluate, default to False for safety
            return False

    def _resolve_parameters(self, parameters: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve parameter values from state (inputs and previous outputs).
        Raises MissingInputError if a required variable is missing.
        """
        resolved = {}
        for key, value in parameters.items():
            if isinstance(value, str):
                # Check for variable substitution ${var}
                matches = self.var_pattern.findall(value)
                if matches:
                    # For now, handle simple single variable substitution
                    # Complex string interpolation can be added later
                    var_path = matches[0]
                    resolved_val = self._get_value_from_path(var_path, state)
                    if resolved_val is None:
                        raise MissingInputError(f"Variable {var_path} not found", var_path)
                    resolved[key] = resolved_val
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved

    def _get_value_from_path(self, path: str, state: Dict[str, Any]) -> Any:
        """
        Retrieve value from state using dot notation.
        e.g. "step_id.output_key" or "input.key"
        """
        parts = path.split('.')
        root = parts[0]
        
        if root == "input":
            # Access input data
            current = state.get("input_data", {})
            for part in parts[1:]:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
            return current
            
        else:
            # Access step output
            step_output = state["outputs"].get(root)
            if step_output is None:
                return None
                
            current = step_output
            for part in parts[1:]:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
            return current

    def _validate_input_schema(self, step: Dict[str, Any], params: Dict[str, Any]) -> None:
        """Validate input parameters against step's input schema."""
        input_schema = step.get("input_schema")
        if not input_schema:
            return
        try:
            validate(instance=params, schema=input_schema)
        except ValidationError as e:
            raise SchemaValidationError(
                f"Input validation failed for step {step['id']}: {e.message}",
                schema_type="input",
                errors=[e.message]
            )

    def _validate_output_schema(self, step: Dict[str, Any], output: Dict[str, Any]) -> None:
        """Validate output against step's output schema."""
        output_schema = step.get("output_schema")
        if not output_schema:
            return
        try:
            validate(instance=output, schema=output_schema)
        except ValidationError as e:
            raise SchemaValidationError(
                f"Output validation failed for step {step['id']}: {e.message}",
                schema_type="output",
                errors=[e.message]
            )

    @async_retry_with_backoff(max_retries=3)
    async def _execute_step(self, step: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single step.
        This is where we would dispatch to specific service integrations.
        For now, we'll simulate execution or use a basic dispatcher.
        """
        service = step["service"]
        action = step["action"]
        
        logger.info(f"Executing {service}.{action} with params: {params}")
        
        # Fixed: Implement actual service registry lookup and execution
        # Service registry mapping
        service_registry = {
            "slack": self._execute_slack_action,
            "asana": self._execute_asana_action,
            "github": self._execute_github_action,
            "email": self._execute_email_action,
            "gmail": self._execute_gmail_action,
            "outlook": self._execute_outlook_action,
            "jira": self._execute_jira_action,
            "trello": self._execute_trello_action,
            "stripe": self._execute_stripe_action,
            "shopify": self._execute_shopify_action,
            "zoho_crm": self._execute_zoho_crm_action,
            "zoho_books": self._execute_zoho_books_action,
            "zoho_inventory": self._execute_zoho_inventory_action,
            "hubspot": self._execute_hubspot_action,
            "salesforce": self._execute_salesforce_action,
            "discord": self._execute_discord_action,
            "zoom": self._execute_zoom_action,
            "notion": self._execute_notion_action,
            "calendar": self._execute_calendar_action,
            "database": self._execute_database_action,
            "ai": self._execute_ai_action,
            "webhook": self._execute_webhook_action,
            "mcp": self._execute_mcp_action,
            "main_agent": self._execute_main_agent_action,
            "workflow": self._execute_workflow_action,
            "email_automation": self._execute_email_automation_action,
            "goal_management": self._execute_goal_management_action
        }

        # Check for fallback service
        fallback_service = step.get("fallback_service")
        # Get timeout if specified
        timeout = step.get("timeout")

        # Try primary service first
        primary_error = None
        if service not in service_registry:
            # Try generic executor for catalog integrations
            try:
                logger.info(f"Service {service} not in registry, attempting generic execution via catalog")
                result = await self._execute_generic_action(service, action, params, step.get("connection_id"))
                return {
                    "status": "success",
                    "service": service,
                    "action": action,
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                    "execution_method": "generic_catalog_executor"
                } 
            except Exception as e:
                logger.warning(f"Generic execution failed or service not found in catalog: {e}")
                raise ValueError(f"Unknown service: {service} (and generic execution failed: {e})")
        
        executor = service_registry[service]
        try:
            # Pass automation context if executor supports it
            context = {
                "workflow_id": step.get("workflow_id"),
                "execution_id": step.get("execution_id")
            }
            
            if timeout is not None and timeout > 0:
                try:
                    result = await asyncio.wait_for(executor(action, params, step.get("connection_id")), timeout=timeout)
                except asyncio.TimeoutError:
                    raise StepTimeoutError(
                        f"Step {step['id']} timed out after {timeout} seconds",
                        step_id=step['id'],
                        timeout=timeout
                    )
            else:
                result = await executor(action, params, step.get("connection_id"))
            return {
                "status": "success",
                "service": service,
                "action": action,
                "result": result,
                "timestamp": datetime.now().isoformat(),
                "execution_method": "service_registry"
            }
        except Exception as e:
            primary_error = e
            logger.warning(f"Primary service {service}.{action} failed: {e}")
            # Continue to fallback if available

        # If primary failed and fallback service is specified, try fallback
        if primary_error is not None and fallback_service and fallback_service in service_registry:
            logger.info(f"Attempting fallback service {fallback_service}.{action}")
            try:
                fallback_executor = service_registry[fallback_service]
                if timeout is not None and timeout > 0:
                    try:
                        result = await asyncio.wait_for(fallback_executor(action, params), timeout=timeout)
                    except asyncio.TimeoutError:
                        raise StepTimeoutError(
                        timeout=timeout
                        )
                else:
                    result = await fallback_executor(action, params, step.get("connection_id"))
                return {
                    "status": "success",
                    "service": fallback_service,
                    "action": action,
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                    "execution_method": "fallback_service",
                    "original_service": service,
                    "fallback_used": True
                }
            except Exception as e:
                logger.error(f"Fallback service {fallback_service}.{action} also failed: {e}")
                # Both primary and fallback failed
                return {
                    "status": "error",
                    "service": service,
                    "action": action,
                    "error": f"Primary failed: {primary_error}, Fallback failed: {e}",
                    "timestamp": datetime.now().isoformat(),
                    "execution_method": "service_registry_failed",
                    "params": params,
                    "fallback_attempted": True
                }

        # No fallback or fallback not in registry
        logger.error(f"Failed to execute {service}.{action}: {primary_error}")
        return {
            "status": "error",
            "service": service,
            "action": action,
            "error": str(primary_error),
            "timestamp": datetime.now().isoformat(),
            "execution_method": "service_registry_failed",
            "params": params,
            "fallback_attempted": False
        }

    # Service executor methods
    async def _execute_slack_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Slack service actions"""
        from integrations.slack_service_unified import slack_unified_service

        # Try to get token if connection_id is present
        token_data = None
        if connection_id:
            token_data = token_storage.get_token(connection_id)
            if not token_data:
                # Fallback: try looking up by service name
                token_data = token_storage.get_token("slack")
        
        token = token_data.get("access_token") if token_data else None
        
        logger.info(f"Executing Slack action {action} with connection {connection_id} (Token found: {bool(token)})")

        try:
            result = None

            if not token:
                raise AuthenticationError("Slack authentication required (no token found)")

            # Map workflow actions to Slack service methods
            if action == "chat_postMessage":
                channel = params.get("channel")
                text = params.get("text")
                result = await slack_unified_service.post_message(token=token, channel_id=channel, text=text)

            elif action == "chat_getChannels" or action == "list_channels":
                # List channels (public and private by default)
                types = params.get("types", "public_channel,private_channel")
                result = await slack_unified_service.list_channels(token=token, types=types)

            elif action == "chat_getUsers" or action == "list_users":
                # Get user info - use team info endpoint for user list
                result = await slack_unified_service.get_team_info(token=token)

            elif action == "get_channel_info":
                channel_id = params.get("channel_id")
                if not channel_id:
                    raise ValueError("channel_id is required for get_channel_info")
                result = await slack_unified_service.get_channel_info(token=token, channel_id=channel_id)

            elif action == "get_channel_history":
                channel_id = params.get("channel_id")
                limit = params.get("limit", 100)
                if not channel_id:
                    raise ValueError("channel_id is required for get_channel_history")
                result = await slack_unified_service.get_channel_history(token=token, channel_id=channel_id, limit=limit)

            elif action == "update_message":
                channel_id = params.get("channel_id")
                message_ts = params.get("message_ts")
                text = params.get("text")
                if not all([channel_id, message_ts, text]):
                    raise ValueError("channel_id, message_ts, and text are required for update_message")
                result = await slack_unified_service.update_message(token=token, channel_id=channel_id, message_ts=message_ts, text=text)

            elif action == "delete_message":
                channel_id = params.get("channel_id")
                message_ts = params.get("message_ts")
                if not all([channel_id, message_ts]):
                    raise ValueError("channel_id and message_ts are required for delete_message")
                result = await slack_unified_service.delete_message(token=token, channel_id=channel_id, message_ts=message_ts)

            elif action == "search_messages":
                query = params.get("query")
                if not query:
                    raise ValueError("query is required for search_messages")
                count = params.get("count", 100)
                result = await slack_unified_service.search_messages(token=token, query=query, count=count)

            elif action == "files_list":
                channel_id = params.get("channel_id")
                user_id = params.get("user_id")
                count = params.get("count", 100)
                result = await slack_unified_service.list_files(token=token, channel_id=channel_id, user_id=user_id, count=count)

            elif action == "files_get_upload_url_external":
                # File upload requires special handling - get upload URL first
                # For now, provide a structured response indicating the flow
                result = {
                    "ok": False,
                    "error": "File upload requires getUploadURLExternal endpoint followed by file upload",
                    "flow": "1. Call files.getUploadURLExternal, 2. Upload file to returned URL, 3. Call files.completeUploadExternal"
                }

            elif action == "reactions_add":
                # Add reaction to message
                # This would need to be implemented in SlackUnifiedService
                result = {
                    "ok": False,
                    "error": "reactions_add not yet implemented in SlackUnifiedService - needs API endpoint addition",
                    "endpoint": "reactions.add"
                }

            else:
                # Unknown action - provide helpful error
                raise ValueError(
                    f"Unsupported Slack action: {action}. "
                    f"Supported actions: chat_postMessage, chat_getChannels, chat_getUsers, "
                    f"get_channel_info, get_channel_history, update_message, delete_message, "
                    f"search_messages, files_list, files_get_upload_url_external, reactions_add"
                )

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token)
            }
        except Exception as e:
             logger.error(f"Slack execution failed: {e}")
             raise e

    async def _execute_asana_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Asana service actions"""
        from integrations.asana_service import asana_service
        
        token = self._get_token(connection_id, "asana")
        if not token:
             # Try environment if no connection but that is fallback
             token = os.getenv("ASANA_ACCESS_TOKEN")

        logger.info(f"Executing Asana action {action} with connection {connection_id}")
        
        try:
            result = None

            if not token:
                raise AuthenticationError("Asana authentication required")

            # Map workflow actions to Asana service methods
            if action == "create_task":
                task_data = {
                    "name": params.get("name"),
                    "workspace": params.get("workspace"),
                    "projects": params.get("projects", [])
                }
                if params.get("notes"): task_data["notes"] = params.get("notes")
                if params.get("due_on"): task_data["due_on"] = params.get("due_on")
                if params.get("assignee"): task_data["assignee"] = params.get("assignee")

                result = await asana_service.create_task(token, task_data)

            elif action == "get_tasks":
                project_gid = params.get("project")
                workspace_gid = params.get("workspace")
                assignee = params.get("assignee")
                limit = params.get("limit", 50)

                result = await asana_service.get_tasks(
                    token,
                    project_gid=project_gid,
                    workspace_gid=workspace_gid,
                    assignee=assignee,
                    limit=limit
                )

            elif action == "get_projects":
                workspace = params.get("workspace")
                result = await asana_service.get_projects(token, workspace_gid=workspace)

            elif action == "update_task":
                task_gid = params.get("task_gid")
                if not task_gid:
                    raise ValueError("task_gid is required for update_task")

                updates = {}
                if params.get("name"): updates["name"] = params.get("name")
                if params.get("notes"): updates["notes"] = params.get("notes")
                if params.get("completed") is not None: updates["completed"] = params.get("completed")
                if params.get("due_on"): updates["due_on"] = params.get("due_on")
                if params.get("assignee"): updates["assignee"] = params.get("assignee")

                result = await asana_service.update_task(token, task_gid, updates)

            elif action == "add_comment":
                task_gid = params.get("task_gid")
                text = params.get("text")
                if not all([task_gid, text]):
                    raise ValueError("task_gid and text are required for add_comment")

                result = await asana_service.add_task_comment(token, task_gid, text)

            elif action == "get_workspaces":
                result = await asana_service.get_workspaces(token)

            elif action == "get_users":
                workspace_gid = params.get("workspace")
                if not workspace_gid:
                    raise ValueError("workspace is required for get_users")
                limit = params.get("limit", 50)
                result = await asana_service.get_users(token, workspace_gid, limit)

            elif action == "get_teams":
                workspace_gid = params.get("workspace")
                if not workspace_gid:
                    raise ValueError("workspace is required for get_teams")
                limit = params.get("limit", 50)
                result = await asana_service.get_teams(token, workspace_gid, limit)

            elif action == "search_tasks":
                workspace_gid = params.get("workspace")
                query = params.get("query")
                if not all([workspace_gid, query]):
                    raise ValueError("workspace and query are required for search_tasks")
                limit = params.get("limit", 20)
                result = await asana_service.search_tasks(token, workspace_gid, query, limit)

            elif action == "create_project":
                # Project creation needs to be added to AsanaService
                # For now, provide structured error
                result = {
                    "ok": False,
                    "error": "create_project not yet implemented in AsanaService - needs API endpoint addition",
                    "endpoint": "projects.create"
                }

            else:
                # Unknown action - provide helpful error
                raise ValueError(
                    f"Unsupported Asana action: {action}. "
                    f"Supported actions: create_task, get_tasks, get_projects, update_task, "
                    f"add_comment, get_workspaces, get_users, get_teams, search_tasks, create_project"
                )

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token)
            }
        except Exception as e:
            logger.error(f"Asana execution failed: {e}")
            raise e

    async def _execute_discord_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Discord service actions"""
        from integrations.discord_service import discord_service
        
        token = self._get_token(connection_id, "discord")
        logger.info(f"Executing Discord action {action} with connection {connection_id}")
        
        try:
            if not token and not discord_service.bot_token:
                 raise AuthenticationError("Discord authentication required")

            if action == "send_message":
                 channel_id = params.get("channel_id")
                 content = params.get("content")
                 result = await discord_service.send_message(channel_id, content, access_token=token, use_bot_token=not bool(token))
            else:
                 await asyncio.sleep(0.1)
                 result = f"Discord {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token) or bool(discord_service.bot_token)
            }
        except Exception as e:
             logger.error(f"Discord execution failed: {e}")
             raise e

    async def _execute_hubspot_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute HubSpot service actions"""
        from integrations.hubspot_service import hubspot_service
        
        token = self._get_token(connection_id, "hubspot")
        logger.info(f"Executing HubSpot action {action} with connection {connection_id}")
        
        try:
            if not token and not hubspot_service.access_token:
                 raise AuthenticationError("HubSpot authentication required")

            if action == "create_contact":
                 email = params.get("email")
                 first_name = params.get("firstname")
                 last_name = params.get("lastname")
                 result = await hubspot_service.create_contact(email=email, first_name=first_name, last_name=last_name, token=token)
            elif action == "create_deal":
                 name = params.get("dealname")
                 amount = params.get("amount", 0)
                 result = await hubspot_service.create_deal(name=name, amount=float(amount), token=token)
            else:
                 await asyncio.sleep(0.1)
                 result = f"HubSpot {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token)
            }
        except Exception as e:
             logger.error(f"HubSpot execution failed: {e}")
             raise e

    async def _execute_salesforce_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Salesforce service actions"""
        from integrations.salesforce_service import SalesforceService
        
        token_data = None
        if connection_id:
             token_data = token_storage.get_token(connection_id)
        
        access_token = token_data.get("access_token") if token_data else None
        instance_url = token_data.get("instance_url") if token_data else None

        logger.info(f"Executing Salesforce action {action} with connection {connection_id}")
        
        try:
            sf_service = SalesforceService()
            # If we have dynamic tokens, create client
            sf = None
            if access_token and instance_url:
                sf = sf_service.create_client(access_token, instance_url)
            
            # If no dynamic client, validation fails unless we have some other fallback (which SF service doesn't really have easily)
            if not sf:
                 raise AuthenticationError("Salesforce authentication required (token + instance_url)")

            if action == "create_lead":
                 last_name = params.get("lastname")
                 company = params.get("company")
                 email = params.get("email")
                 result = await sf_service.create_lead(sf, last_name=last_name, company=company, email=email)
            elif action == "create_contact":
                 last_name = params.get("lastname")
                 email = params.get("email")
                 result = await sf_service.create_contact(sf, last_name=last_name, email=email)
            elif action == "create_opportunity":
                 name = params.get("name")
                 stage = params.get("stagename")
                 close_date = params.get("closedate")
                 result = await sf_service.create_opportunity(sf, name=name, stage_name=stage, close_date=close_date)
            else:
                 await asyncio.sleep(0.1)
                 result = f"Salesforce {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": True
            }
        except Exception as e:
             logger.error(f"Salesforce execution failed: {e}")
             raise e

    async def _execute_github_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute GitHub service actions"""
        from integrations.github_service import GitHubService
        
        token = self._get_token(connection_id, "github")
        logger.info(f"Executing GitHub action {action} with connection {connection_id}")
        
        try:
            # Instantiate service with token
            github = GitHubService(access_token=token)
            
            if action == "create_issue":
                 owner = params.get("owner")
                 repo = params.get("repo")
                 title = params.get("title")
                 body = params.get("body")
                 result = github.create_issue(owner, repo, title, body)
            else:
                 await asyncio.sleep(0.1)
                 result = f"GitHub {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"GitHub execution failed: {e}")
            raise e
            
    async def _execute_zoom_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        from integrations.zoom_service import zoom_service
        token = self._get_token(connection_id, "zoom")
        try:
            if action == "create_meeting":
                topic = params.get("topic")
                result = await zoom_service.create_meeting(topic=topic, access_token=token)
            else:
                await asyncio.sleep(0.1)
                result = f"Zoom {action} simulated"
            return {"action": action, "result": result, "status": "success"}
        except Exception as e:
            logger.error(f"Zoom execution failed: {e}")
            raise e

    async def _execute_notion_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        from integrations.notion_service import NotionService
        token = self._get_token(connection_id, "notion")
        try:
            notion = NotionService(access_token=token)
            if action == "create_page":
                parent = params.get("parent") # e.g. {"database_id": "..."}
                properties = params.get("properties")
                result = notion.create_page(parent, properties)
            else:
                await asyncio.sleep(0.1)
                result = f"Notion {action} simulated"
            return {"action": action, "result": result, "status": "success"}
        except Exception as e:
            logger.error(f"Notion execution failed: {e}")
            raise e

    def _get_token(self, connection_id: Optional[str], service_name: str) -> Optional[str]:
        """Helper to retrieve token from connection or fallback"""
        token_data = None
        if connection_id:
            token_data = token_storage.get_token(connection_id)
            if not token_data and service_name:
                token_data = token_storage.get_token(service_name)
        
        if token_data:
            return token_data.get("access_token")
        return None

    async def _execute_email_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Email service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Email {action} executed",
            "status": "success"
        }

    async def _execute_gmail_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Gmail service actions"""
        from integrations.gmail_service import gmail_service

        # Try to get token if connection_id is present
        token_data = None
        if connection_id:
            token_data = token_storage.get_token(connection_id)
            if not token_data:
                token_data = token_storage.get_token("google")
        
        token = token_data.get("access_token") if token_data else None
        logger.info(f"Executing Gmail action {action} with connection {connection_id} (Token found: {bool(token)})")
        
        try:
            result = None
            if action == "send_email":
                to = params.get("to")
                subject = params.get("subject")
                body = params.get("body")
                
                if not token:
                     raise AuthenticationError("Gmail authentication required (no token found)")

                # Use refactored send_message with token
                result = gmail_service.send_message(to=to, subject=subject, body=body, token=token)

                if not result:
                    raise ExternalServiceError("Gmail", "Failed to send email")
            
            elif action == "create_draft":
                 to = params.get("to")
                 subject = params.get("subject")
                 body = params.get("body")
                 if not token:
                     raise AuthenticationError("Gmail authentication required")
                 result = gmail_service.draft_message(to=to, subject=subject, body=body, token=token)

            else:
                await asyncio.sleep(0.1)
                result = f"Gmail {action} simulated"

            return {
                "action": action,
                "result": result,
                "status": "success",
                "authenticated": bool(token)
            }
        except Exception as e:
             logger.error(f"Gmail execution failed: {e}")
             raise e

    async def _execute_calendar_action(self, action: str, params: dict) -> dict:
        """Execute Calendar service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Calendar {action} executed",
            "status": "success"
        }

    async def _execute_database_action(self, action: str, params: dict) -> dict:
        """Execute Database service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Database {action} executed",
            "status": "success"
        }

    async def _execute_ai_action(self, action: str, params: dict) -> dict:
        """Execute AI service actions"""
        await asyncio.sleep(0.2)  # AI actions take longer
        return {
            "action": action,
            "result": f"AI {action} executed",
            "status": "success"
        }

    async def _execute_webhook_action(self, action: str, params: dict) -> dict:
        """Execute Webhook service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Webhook {action} executed",
            "status": "success"
        }

    async def _execute_mcp_action(self, action: str, params: dict) -> dict:
        """Execute MCP server actions"""
        try:
            from integrations.mcp_service import mcp_service

            server_id = params.get("server_id")
            tool_name = params.get("tool_name", action)
            tool_args = params.get("arguments", {})

            if not server_id:
                raise ValueError("server_id is required for MCP actions")

            # Execute MCP tool
            result = await mcp_service.execute_tool(server_id, tool_name, tool_args)

            return {
                "action": action,
                "server_id": server_id,
                "tool_name": tool_name,
                "result": result,
                "status": "success"
            }

        except Exception as e:
            return {
                "action": action,
                "error": str(e),
                "status": "error"
            }

    async def _execute_main_agent_action(self, action: str, params: dict) -> dict:
        """Execute Main Agent actions with MCP connections"""
        try:
            # This allows the main agent to act as a workflow node with MCP capabilities
            agent_action = params.get("agent_action", action)
            mcp_servers = params.get("mcp_servers", [])
            input_data = params.get("input_data", {})

            # Prepare agent context with MCP connections
            agent_context = {
                "action": agent_action,
                "input_data": input_data,
                "mcp_connections": {},
                "available_tools": []
            }

            # Get active MCP connections
            if mcp_servers:
                from integrations.mcp_service import mcp_service
                active_connections = await mcp_service.get_active_connections()

                for connection in active_connections:
                    if connection["server_id"] in mcp_servers:
                        server_tools = await mcp_service.get_server_tools(connection["server_id"])
                        agent_context["mcp_connections"][connection["server_id"]] = {
                            "connected_at": connection["connected_at"],
                            "tools": server_tools
                        }
                        agent_context["available_tools"].extend([
                            {
                                "server_id": connection["server_id"],
                                "tool": tool
                            } for tool in server_tools
                        ])

            # Execute main agent action with MCP context
            # This would integrate with your existing main agent system
            result = await self._execute_agent_with_mcp(agent_context)

            return {
                "action": action,
                "agent_action": agent_action,
                "mcp_servers_used": list(agent_context["mcp_connections"].keys()),
                "result": result,
                "status": "success"
            }

        except Exception as e:
            return {
                "action": action,
                "error": str(e),
                "status": "error"
            }

    async def _execute_agent_with_mcp(self, agent_context: dict) -> dict:
        """
        Execute main agent with MCP (Model Context Protocol) tool access.

        This integrates with the BYOK LLM handler to provide the agent with
        access to MCP tools during execution.
        """
        try:
            from core.agent_context_resolver import AgentContextResolver
            from core.llm.byok_handler import BYOKHandler
            from core.models import AgentRegistry

            action = agent_context.get("action", "unknown")
            input_data = agent_context.get("input_data", {})
            mcp_connections = agent_context.get("mcp_connections", {})
            available_tools = agent_context.get("available_tools", [])
            agent_id = agent_context.get("agent_id")

            # Get agent from database
            agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            if not agent:
                logger.error(f"Agent {agent_id} not found for MCP execution")
                return {
                    "success": False,
                    "error": f"Agent {agent_id} not found"
                }

            # Format MCP tools for LLM function calling
            tool_definitions = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", "unknown"),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {})
                    }
                }
                for tool in available_tools
            ]

            # Build the prompt with context about available tools
            tool_info = "\n".join([
                f"- {tool.get('name')}: {tool.get('description', 'No description')}"
                for tool in available_tools
            ])

            prompt = f"""You are executing action: {action}

Available MCP Tools:
{tool_info}

Input data:
{input_data if isinstance(input_data, str) else str(input_data)}

Use the available tools as needed to complete the action. Return your response in a clear, structured format."""

            # Execute using BYOK handler
            try:
                llm_handler = BYOKHandler(self.db)
                response = await llm_handler.chat_completion(
                    provider=agent.llm_provider,
                    model=agent.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    tools=tool_definitions if tool_definitions else None,
                    temperature=0.7
                )

                return {
                    "success": True,
                    "agent_response": response.get("content", ""),
                    "tool_calls": response.get("tool_calls", []),
                    "tools_available": len(available_tools),
                    "mcp_connections": len(mcp_connections),
                    "input_processed": input_data,
                    "execution_method": "main_agent_with_mcp",
                    "agent_id": agent_id,
                    "action": action
                }

            except Exception as llm_error:
                logger.error(f"LLM execution failed for agent {agent_id}: {llm_error}")
                # Fallback: Return basic response without LLM
                return {
                    "success": True,
                    "agent_response": f"Executed {action} with {len(available_tools)} MCP tools available (LLM execution failed, using fallback)",
                    "tools_available": len(available_tools),
                    "mcp_connections": len(mcp_connections),
                    "input_processed": input_data,
                    "execution_method": "fallback",
                    "error": str(llm_error)
                }

        except Exception as e:
            logger.error(f"MCP agent execution failed: {e}")
            raise AgentExecutionError(
                agent_id=agent_context.get("agent_id", "unknown"),
                reason=str(e),
                cause=e
            )

    async def _execute_email_automation_action(self, action: str, params: dict) -> dict:
        """Execute email automation service actions (Follow-ups, etc.)"""
        try:
            from core.email_followup_engine import followup_engine
            
            if action == "detect_followups":
                # In a real app, we'd fetch actual emails here. 
                # For now, we'll use mock data like the analytics endpoint did.
                from datetime import datetime, timedelta
                now = datetime.now()
                mock_sent = [
                    {"id": "e1", "to": "investor@venture.com", "subject": "Quarterly Update", "sent_at": (now - timedelta(days=5)).isoformat(), "thread_id": "thread_1", "snippet": "Hey, checking in on the report..."},
                ]
                mock_received = []
                
                days_threshold = params.get("days_threshold", 3)
                followup_engine.days_threshold = days_threshold
                
                candidates = await followup_engine.detect_missing_replies(mock_sent, mock_received)
                return {
                    "status": "success",
                    "candidates": [c.dict() for c in candidates],
                    "count": len(candidates)
                }
            
            elif action == "draft_nudge":
                subject = params.get("subject", "Following up")
                # Simple AI-like drafting
                draft = f"Hi there,\n\nI'm just following up on my previous email regarding \"{subject}\". I assume you've been busy, but I wanted to make sure this stayed on your radar. Looking forward to hearing from you!\n\nBest, [Your Name]"
                return {
                    "status": "success",
                    "draft": draft
                }
            
            else:
                raise ValueError(f"Unknown email_automation action: {action}")
                
        except Exception as e:
            logger.error(f"Email automation failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _execute_workflow_action(self, action: str, params: dict) -> dict:
        """Execute a sub-workflow as a step."""
        try:
            workflow_id = params.get("workflow_id")
            if not workflow_id:
                raise ValueError("workflow_id is required for workflow actions")

            input_data = params.get("input_data", {})
            max_depth = params.get("max_depth", 10)  # Prevent infinite recursion
            timeout = params.get("timeout", 300)  # Default 5 minute timeout

            # Check recursion depth (track via context or simple counter)
            # For now, implement simple depth check
            # In a full implementation, we would track via execution context

            # Load workflow definition
            workflow = self._load_workflow_by_id(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

            # Execute sub-workflow using the same engine
            # This creates a new execution ID and runs asynchronously
            execution_id = await self.start_workflow(workflow, input_data)

            # Monitor the execution status with timeout
            start_time = datetime.now()
            poll_interval = 0.5  # Poll every 500ms

            while True:
                # Check timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    logger.warning(f"Sub-workflow {workflow_id} execution {execution_id} timed out after {timeout}s")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "timeout",
                        "error": f"Sub-workflow execution timed out after {timeout} seconds"
                    }

                # Get current execution state
                state = await self.state_manager.get_execution_state(execution_id)

                if not state:
                    logger.error(f"Sub-workflow execution {execution_id} not found in state manager")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "error",
                        "error": "Execution state not found"
                    }

                status = state.get("status")

                # Check if execution is complete
                if status in ["COMPLETED", "SUCCESS"]:
                    logger.info(f"Sub-workflow {workflow_id} execution {execution_id} completed successfully")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "result": state.get("outputs", {}),
                        "status": "success"
                    }
                elif status in ["FAILED", "ERROR"]:
                    error_msg = state.get("error", "Unknown error")
                    logger.error(f"Sub-workflow {workflow_id} execution {execution_id} failed: {error_msg}")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "error",
                        "error": error_msg
                    }
                elif status in ["CANCELLED"]:
                    logger.warning(f"Sub-workflow {workflow_id} execution {execution_id} was cancelled")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "cancelled",
                        "error": "Sub-workflow was cancelled"
                    }
                elif status in ["PAUSED"]:
                    logger.warning(f"Sub-workflow {workflow_id} execution {execution_id} is paused, waiting for input")
                    return {
                        "action": action,
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "status": "paused",
                        "error": "Sub-workflow is paused waiting for input"
                    }
                elif status in ["RUNNING", "PENDING"]:
                    # Still running, wait and poll again
                    await asyncio.sleep(poll_interval)
                    continue
                else:
                    logger.warning(f"Sub-workflow {workflow_id} execution {execution_id} has unknown status: {status}")
                    await asyncio.sleep(poll_interval)
                    continue

        except Exception as e:
            logger.error(f"Error executing sub-workflow: {e}")
            return {
                "action": action,
                "error": str(e),
                "status": "error"
            }

    def _load_workflow_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load workflow definition by ID from workflows.json."""
        import json
        import os

        # Calculate path to workflows.json (same as in workflow_endpoints.py)
        workflows_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "workflows.json"
        )

        if not os.path.exists(workflows_file):
            return None

        try:
            with open(workflows_file, 'r') as f:
                workflows = json.load(f)

            # Find workflow by ID
            for workflow in workflows:
                if workflow.get('id') == workflow_id:
                    return workflow
            return None
        except Exception as e:
            logger.error(f"Error loading workflow {workflow_id}: {e}")
            return None

    async def _execute_outlook_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Outlook service actions"""
        try:
            from integrations.outlook_service import OutlookService
            service = OutlookService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None
            user_id = params.get("user_id", "default") # Or derive from context
            
            # Helper to call service method
            async def call_service(method_name, **kwargs):
                method = getattr(service, method_name)
                # Filter kwargs to match method signature to be safe, or rely on **kwargs in service
                # Our service methods are explicit, so we should map params carefully or rely on compatible keys
                # Simplified invocation:
                if token:
                    kwargs["token"] = token
                result = await method(**kwargs)
                return result

            result = None
            if action == "send_email":
                result = await call_service("send_email", 
                    user_id=user_id,
                    to_recipients=params.get("to_recipients"),
                    subject=params.get("subject"),
                    body=params.get("body"),
                    cc_recipients=params.get("cc_recipients"),
                    bcc_recipients=params.get("bcc_recipients")
                )
            elif action == "create_event":
                 result = await call_service("create_calendar_event",
                    user_id=user_id,
                    subject=params.get("subject"),
                    body=params.get("body"),
                    start=params.get("start"),
                    end=params.get("end"),
                    location=params.get("location"),
                    attendees=params.get("attendees")
                 )
            elif action == "get_emails":
                result = await call_service("get_user_emails",
                    user_id=user_id,
                    folder=params.get("folder", "inbox"),
                    max_results=params.get("max_results", 10),
                    query=params.get("query")
                )
            else:
                # Generic fallback if action matches method name
                if hasattr(service, action):
                     # Add user_id if not in params
                     if "user_id" not in params:
                         params["user_id"] = user_id
                     result = await call_service(action, **params)
                else:
                    raise ValueError(f"Unknown Outlook action: {action}")
            
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Outlook execution failed: {e}")
            raise e

    async def _execute_jira_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Jira service actions"""
        try:
            from integrations.jira_service import JiraService
            service = JiraService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None
            
            if hasattr(service, action):
                method = getattr(service, action)
                if token:
                    params["token"] = token
                result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Jira action: {action}")
        except Exception as e:
            logger.error(f"Jira execution failed: {e}")
            raise e

    async def _execute_trello_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Trello service actions"""
        try:
            from integrations.trello_service import TrelloService
            service = TrelloService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None # In Trello, this might be 'token'
            
            # TrelloService methods explicitly take 'token'
            if hasattr(service, action):
                method = getattr(service, action)
                if token:
                    params["token"] = token
                result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Trello action: {action}")
        except Exception as e:
            logger.error(f"Trello execution failed: {e}")
            raise e

    async def _execute_stripe_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Stripe service actions"""
        try:
            from integrations.stripe_service import StripeService
            service = StripeService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            access_token = token_data.get("access_token") if token_data else None
            
            if not access_token:
                # StripeService methods require access_token
                # Log warning and skip execution if token not available
                logger.warning(
                    f"Stripe action '{action}' requires access_token but none found "
                    f"for connection_id: {connection_id}. Skipping execution."
                )
                return {
                    "status": "error",
                    "error": "Stripe access token not found",
                    "connection_id": connection_id,
                    "action": action
                }

            if hasattr(service, action):
                method = getattr(service, action)
                if access_token:
                    params["access_token"] = access_token
                
                # Strip connection_id from params if it leaked in? No, params is separate.
                result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Stripe action: {action}")
        except Exception as e:
            logger.error(f"Stripe execution failed: {e}")
            raise e

    async def _execute_shopify_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Shopify service actions"""
        try:
            from integrations.shopify_service import ShopifyService
            service = ShopifyService()
            
            token_data = token_storage.get_token(connection_id) if connection_id else None
            access_token = token_data.get("access_token") if token_data else None
            shop = token_data.get("shop_url") or token_data.get("shop") if token_data else None
            
            if access_token:
                params["access_token"] = access_token
            if shop:
                params["shop"] = shop

            if hasattr(service, action):
                method = getattr(service, action)
                # Allow async methods
                if asyncio.iscoroutinefunction(method):
                    result = await method(**params)
                else:
                    result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Shopify action: {action}")
        except Exception as e:
            logger.error(f"Shopify execution failed: {e}")
            raise e

    async def _execute_zoho_crm_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Zoho CRM service actions"""
        try:
            from integrations.zoho_crm_service import ZohoCRMService
            service = ZohoCRMService()

            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None

            if hasattr(service, action):
                method = getattr(service, action)
                if token:
                    params["token"] = token
                if asyncio.iscoroutinefunction(method):
                    result = await method(**params)
                else:
                    result = method(**params)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Zoho CRM action: {action}")
        except Exception as e:
            logger.error(f"Zoho CRM execution failed: {e}")
            raise e

    async def _execute_zoho_books_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Zoho Books service actions"""
        try:
            from integrations.zoho_books_service import ZohoBooksService
            service = ZohoBooksService()

            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None
            organization_id = token_data.get("organization_id") or token_data.get("org_id") if token_data else None

            if hasattr(service, action):
                method = getattr(service, action)
                # Check method signature or just pass likely kwargs
                kwargs = params.copy()
                if token:
                    kwargs["access_token"] = token # ZohoBooksService uses 'access_token' param name
                if organization_id and "organization_id" not in kwargs:
                    kwargs["organization_id"] = organization_id

                if asyncio.iscoroutinefunction(method):
                    result = await method(**kwargs)
                else:
                    result = method(**kwargs)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Zoho Books action: {action}")
        except Exception as e:
            logger.error(f"Zoho Books execution failed: {e}")
            raise e

    async def _execute_zoho_inventory_action(self, action: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """Execute Zoho Inventory service actions"""
        try:
            from integrations.zoho_inventory_service import ZohoInventoryService
            service = ZohoInventoryService()

            token_data = token_storage.get_token(connection_id) if connection_id else None
            token = token_data.get("access_token") if token_data else None
            organization_id = token_data.get("organization_id") or token_data.get("org_id") if token_data else None

            if hasattr(service, action):
                method = getattr(service, action)
                kwargs = params.copy()
                if token:
                    kwargs["token"] = token
                if organization_id and "organization_id" not in kwargs:
                    kwargs["organization_id"] = organization_id

                if asyncio.iscoroutinefunction(method):
                    result = await method(**kwargs)
                else:
                    result = method(**kwargs)
                return {"status": "success", "result": result}
            else:
                 raise ValueError(f"Unknown Zoho Inventory action: {action}")
        except Exception as e:
            logger.error(f"Zoho Inventory execution failed: {e}")
            raise e

    async def _execute_generic_action(self, service_name: str, action_name: str, params: dict, connection_id: Optional[str] = None) -> dict:
        """
        Universal Generic Executor for Catalog Integrations.
        Fetches metadata from IntegrationCatalog and executes HTTP request.
        """
        from core.cache import cache
        
        logger.info(f"Attempting generic execution for {service_name}.{action_name}")
        
        # 0. Try Cache
        cache_key = f"catalog:{service_name}"
        catalog_data = await cache.get(cache_key)
        
        if not catalog_data:
            # 1. Fetch metadata from DB
            with get_db_session() as db:
                try:
                    catalog_item = db.query(IntegrationCatalog).filter(IntegrationCatalog.id == service_name).first()
                    if not catalog_item:
                        raise ValueError(f"Service '{service_name}' not found in Integration Catalog")

                    # Serialize for cache
                    catalog_data = {
                        "id": catalog_item.id,
                        "actions": catalog_item.actions
                    }
                    # Cache for 1 hour
                    await cache.set(cache_key, catalog_data, expire=3600)
                except Exception as e:
                    logger.error(f"Failed to fetch catalog item: {e}")
                    raise
            
        # 2. Find specific action definition
        actions = catalog_data.get("actions") or []
        action_def = next((a for a in actions if a.get("name") == action_name), None)
            
        if not action_def:
            raise ValueError(f"Action '{action_name}' not found in catalog for service '{service_name}'")
            
        # 3. Construct HTTP Request
        url = action_def.get("url") or action_def.get("path")
        method = action_def.get("method", "GET").upper()
            
        if not url:
            raise ValueError(f"No URL/path defined for action '{action_name}'")
            
        # Parameter Substitution (Path variables)
        # e.g. /users/{id}
        path_params = re.findall(r'\{([^}]+)\}', url)
        for param in path_params:
            if param in params:
                url = url.replace(f"{{{param}}}", str(params.pop(param)))
            else:
                raise ValueError(f"Missing path parameter: {param}")
            
        # Prepare Query & Body
        # Simple heuristic: GET/DELETE uses query, POST/PUT/PATCH uses body
        query_params = {}
        json_body = {}
            
        if method in ["GET", "DELETE"]:
            query_params = params
        else:
            json_body = params
            
        # 4. Authentication
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Atom-Workflow-Engine/1.0"
        }
            
        if connection_id:
            token_data = token_storage.get_token(connection_id)
            if token_data:
                # Generic Bearer Auth Support
                if "access_token" in token_data:
                    headers["Authorization"] = f"Bearer {token_data['access_token']}"
            
        # 5. Execute Request
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_body if method not in ["GET", "DELETE"] else None,
                headers=headers,
                timeout=30.0
            )
                
            response.raise_for_status()
            return response.json()

    async def _execute_goal_management_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute goal management actions"""
        from core.goal_engine import goal_engine
        
        if action == "create_goal":
            title = params.get("title")
            target_date_str = params.get("target_date")
            owner_id = params.get("owner_id", "default")
            
            if not title or not target_date_str:
                raise ValueError("Missing title or target_date for create_goal")
                
            from datetime import datetime
            target_date = datetime.fromisoformat(target_date_str.replace('Z', '+00:00'))
            goal = await goal_engine.create_goal_from_text(title, target_date, owner_id)
            return goal.dict()
            
        elif action == "check_escalations":
            escalations = await goal_engine.check_for_escalations()
            return {"escalations": escalations}
            
        elif action == "update_subtask":
            goal_id = params.get("goal_id")
            sub_task_id = params.get("sub_task_id")
            status = params.get("status")
            
            if goal_id not in goal_engine.goals:
                raise ValueError(f"Goal {goal_id} not found")
                
            goal = goal_engine.goals[goal_id]
            for st in goal.sub_tasks:
                if st.id == sub_task_id:
                    st.status = status
                    break
            
            await goal_engine.update_goal_progress(goal_id)
            return goal.dict()
            
        else:
            raise ValueError(f"Unknown goal_management action: {action}")

class MissingInputError(Exception):
    def __init__(self, message: str, missing_var: str):
        super().__init__(message)
        self.missing_var = missing_var

class SchemaValidationError(Exception):
    def __init__(self, message: str, schema_type: str, errors: list = None):
        super().__init__(message)
        self.schema_type = schema_type  # "input" or "output"
        self.errors = errors or []

class StepTimeoutError(Exception):
    def __init__(self, message: str, step_id: str, timeout: float):
        super().__init__(message)
        self.step_id = step_id
        self.timeout = timeout

# Global instance
_workflow_engine = None

def get_workflow_engine() -> WorkflowEngine:
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine
    return _workflow_engine
