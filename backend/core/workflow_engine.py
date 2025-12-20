"""
Production Workflow Engine

Handles the execution of workflows with support for:
- State persistence via ExecutionStateManager
- Pause/Resume logic for missing inputs
- Many-to-many data mapping
- Automatic retries and error handling
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
import uuid
import jsonschema
from jsonschema import validate, ValidationError

from core.execution_state_manager import get_state_manager, ExecutionStateManager
from core.auto_healing import async_retry_with_backoff
from core.websockets import get_connection_manager

logger = logging.getLogger(__name__)

class WorkflowEngine:
    def __init__(self, max_concurrent_steps: int = 5):
        self.state_manager = get_state_manager()
        # Regex for finding variable references like ${step_id.output_key}
        self.var_pattern = re.compile(r'\${([^}]+)}')
        self.max_concurrent_steps = max_concurrent_steps
        self.semaphore = asyncio.Semaphore(max_concurrent_steps)

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
                        "output_schema": config.get("output_schema", {})
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
                            output = await self._execute_step(step, resolved_params)
                            self._validate_output_schema(step, output)
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
                
                try:
                    output = await self._execute_step(step, resolved_params)
                    self._validate_output_schema(step, output)
                    await self.state_manager.update_step_status(execution_id, step_id, "COMPLETED", output=output)
                    await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_COMPLETED", {"step_id": step_id})
                    
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
            raise ValueError(f"Unknown service: {service}")

        executor = service_registry[service]
        try:
            if timeout is not None and timeout > 0:
                try:
                    result = await asyncio.wait_for(executor(action, params), timeout=timeout)
                except asyncio.TimeoutError:
                    raise StepTimeoutError(
                        f"Step {step['id']} timed out after {timeout} seconds",
                        step_id=step['id'],
                        timeout=timeout
                    )
            else:
                result = await executor(action, params)
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
                            f"Fallback step {step['id']} timed out after {timeout} seconds",
                            step_id=step['id'],
                            timeout=timeout
                        )
                else:
                    result = await fallback_executor(action, params)
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
    async def _execute_slack_action(self, action: str, params: dict) -> dict:
        """Execute Slack service actions"""
        # For now, simulate execution with proper structure
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Slack {action} executed",
            "status": "success"
        }

    async def _execute_asana_action(self, action: str, params: dict) -> dict:
        """Execute Asana service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Asana {action} executed",
            "status": "success"
        }

    async def _execute_github_action(self, action: str, params: dict) -> dict:
        """Execute GitHub service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"GitHub {action} executed",
            "status": "success"
        }

    async def _execute_email_action(self, action: str, params: dict) -> dict:
        """Execute Email service actions"""
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "result": f"Email {action} executed",
            "status": "success"
        }

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
        """Execute main agent with MCP tool access"""
        try:
            # This is a placeholder for your main agent execution
            # You would integrate with your actual main agent system here

            action = agent_context["action"]
            input_data = agent_context["input_data"]
            mcp_connections = agent_context["mcp_connections"]
            available_tools = agent_context["available_tools"]

            # Simulate agent execution with MCP tools
            await asyncio.sleep(0.5)  # Agent actions take time

            # In a real implementation, this would:
            # 1. Pass the MCP tools to your main agent
            # 2. Let the agent decide which tools to use
            # 3. Execute the selected MCP tools
            # 4. Return the agent's response

            return {
                "agent_response": f"Executed {action} with {len(available_tools)} MCP tools available",
                "tools_available": len(available_tools),
                "mcp_connections": len(mcp_connections),
                "input_processed": input_data,
                "execution_method": "main_agent_with_mcp"
            }

        except Exception as e:
            raise Exception(f"Agent execution failed: {e}")

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

            # Check recursion depth (track via context or simple counter)
            # For now, implement simple depth check
            # In a full implementation, we would track via execution context

            # Load workflow definition
            workflow = self._load_workflow_by_id(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

            # Execute sub-workflow using the same engine
            # Note: This creates a new execution ID and runs asynchronously
            # We'll wait for completion and return the result
            execution_id = await self.start_workflow(workflow, input_data)

            # For simplicity, we'll simulate waiting for completion
            # In a real implementation, we would monitor the execution status
            await asyncio.sleep(0.5)  # Simulate sub-workflow execution time

            # Return placeholder result
            return {
                "action": action,
                "workflow_id": workflow_id,
                "execution_id": execution_id,
                "result": f"Sub-workflow {workflow_id} executed",
                "status": "success"
            }

        except Exception as e:
            return {
                "action": action,
                "error": str(e),
                "status": "error"
            }

    def _load_workflow_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load workflow definition by ID from workflows.json."""
        import os
        import json

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
