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

from core.execution_state_manager import get_state_manager, ExecutionStateManager
from core.auto_healing import with_retry
from core.websockets import get_connection_manager

logger = logging.getLogger(__name__)

class WorkflowEngine:
    def __init__(self):
        self.state_manager = get_state_manager()
        # Regex for finding variable references like ${step_id.output_key}
        self.var_pattern = re.compile(r'\${([^}]+)}')

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
                "parameters": config.get("parameters", {})
            }
            
            # Map specific node types/configs to step fields if needed
            if node.get("type") == "trigger":
                step["type"] = "trigger"
                step["action"] = config.get("action", "manual_trigger")
            else:
                step["type"] = "action"
                
            steps.append(step)
            
        return steps

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
        user_id = workflow.get("created_by", "default")
        
        try:
            await self.state_manager.update_execution_status(execution_id, "RUNNING")
            await ws_manager.notify_workflow_status(user_id, execution_id, "RUNNING")
            
            state = await self.state_manager.get_execution_state(execution_id)
            
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

                # Execute step
                await self.state_manager.update_step_status(execution_id, step_id, "RUNNING")
                await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_RUNNING", {"step_id": step_id})
                
                try:
                    output = await self._execute_step(step, resolved_params)
                    await self.state_manager.update_step_status(execution_id, step_id, "COMPLETED", output=output)
                    await ws_manager.notify_workflow_status(user_id, execution_id, "STEP_COMPLETED", {"step_id": step_id})
                    
                    # Update in-memory state for next steps
                    state = await self.state_manager.get_execution_state(execution_id)
                    
                except Exception as e:
                    logger.error(f"Step {step_id} failed: {e}")
                    await self.state_manager.update_step_status(execution_id, step_id, "FAILED", error=str(e))
                    await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(e))
                    await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(e), "step_id": step_id})
                    return

            await self.state_manager.update_execution_status(execution_id, "COMPLETED")
            await ws_manager.notify_workflow_status(user_id, execution_id, "COMPLETED")
            
        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {e}")
            await self.state_manager.update_execution_status(execution_id, "FAILED", error=str(e))
            await ws_manager.notify_workflow_status(user_id, execution_id, "FAILED", {"error": str(e)})

    def _check_dependencies(self, step: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """Check if all dependencies are met"""
        depends_on = step.get("depends_on", [])
        for dep_id in depends_on:
            dep_state = state["steps"].get(dep_id, {})
            if dep_state.get("status") != "COMPLETED":
                return False
        return True

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

    @with_retry(max_retries=3)
    async def _execute_step(self, step: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single step.
        This is where we would dispatch to specific service integrations.
        For now, we'll simulate execution or use a basic dispatcher.
        """
        service = step["service"]
        action = step["action"]
        
        logger.info(f"Executing {service}.{action} with params: {params}")
        
        # TODO: Replace with actual service registry lookup and execution
        # For prototype/verification, we'll simulate success
        
        # Simulate processing time
        await asyncio.sleep(0.5)
        
        return {
            "status": "success",
            "service": service,
            "action": action,
            "result": f"Executed {action}",
            "timestamp": datetime.now().isoformat(),
            # Echo params back for verification
            "params": params
        }

class MissingInputError(Exception):
    def __init__(self, message: str, missing_var: str):
        super().__init__(message)
        self.missing_var = missing_var

# Global instance
_workflow_engine = None

def get_workflow_engine() -> WorkflowEngine:
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine
