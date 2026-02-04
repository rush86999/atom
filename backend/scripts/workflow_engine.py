import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional
from data_persistence import data_persistence

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class StepStatus(Enum):
    """Step execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """Represents a single step in a workflow"""

    id: str
    name: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    timeout: int = 300  # 5 minutes default
    retry_count: int = 3
    retry_delay: int = 5  # seconds


@dataclass
class WorkflowContext:
    """Context for workflow execution"""

    workflow_id: str
    execution_id: str
    input_data: Dict[str, Any]
    step_results: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class WorkflowEngine:
    """Advanced workflow execution engine for ATOM platform"""

    def __init__(self):
        self.actions = {}
        self.running_workflows = {}
        self._lock = asyncio.Lock()

        # Register built-in actions
        self._register_builtin_actions()

    def register_action(
        self,
        action_name: str,
        action_func: Callable[[WorkflowContext, Dict[str, Any]], Awaitable[Any]],
    ):
        """Register a new action that can be used in workflows"""
        self.actions[action_name] = action_func
        logger.info(f"Registered action: {action_name}")

    def _register_builtin_actions(self):
        """Register built-in actions"""

        async def http_request_action(
            context: WorkflowContext, params: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Make HTTP request"""
            import aiohttp

            url = params.get("url")
            method = params.get("method", "GET").upper()
            headers = params.get("headers", {})
            body = params.get("body")

            if not url:
                raise ValueError("URL is required for http_request action")

            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, headers=headers, json=body
                ) as response:
                    return {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text(),
                    }

        async def condition_action(
            context: WorkflowContext, params: Dict[str, Any]
        ) -> bool:
            """Evaluate condition"""
            condition = params.get("condition", "")
            if not condition:
                return True

            # Simple condition evaluation
            # In production, use a proper expression evaluator
            try:
                return eval(condition, {}, context.variables)
            except Exception as e:
                logger.error(f"Condition evaluation failed: {e}")
                return False

        async def set_variable_action(
            context: WorkflowContext, params: Dict[str, Any]
        ) -> Any:
            """Set workflow variable"""
            name = params.get("name")
            value = params.get("value")

            if name:
                context.variables[name] = value
                return value

            return None

        async def log_action(context: WorkflowContext, params: Dict[str, Any]) -> str:
            """Log message"""
            message = params.get("message", "")
            level = params.get("level", "info")

            log_message = f"[Workflow {context.workflow_id}] {message}"

            if level == "error":
                logger.error(log_message)
            elif level == "warning":
                logger.warning(log_message)
            elif level == "debug":
                logger.debug(log_message)
            else:
                logger.info(log_message)

            return message

        async def wait_action(context: WorkflowContext, params: Dict[str, Any]) -> None:
            """Wait for specified time"""
            seconds = params.get("seconds", 1)
            await asyncio.sleep(seconds)

        async def transform_data_action(
            context: WorkflowContext, params: Dict[str, Any]
        ) -> Any:
            """Transform data using template"""
            template = params.get("template", "")
            data = params.get("data", {})

            # Simple template replacement
            # In production, use a proper templating engine
            result = template
            for key, value in data.items():
                result = result.replace(f"{{{{{key}}}}}", str(value))

            return result

        # Register built-in actions
        self.register_action("http_request", http_request_action)
        self.register_action("condition", condition_action)
        self.register_action("set_variable", set_variable_action)
        self.register_action("log", log_action)
        self.register_action("wait", wait_action)
        self.register_action("transform_data", transform_data_action)

    async def execute_workflow(
        self, workflow_id: str, input_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a workflow"""
        execution_id = str(uuid.uuid4())

        # Load workflow template
        template = data_persistence.get_workflow_template(workflow_id)
        if not template:
            raise ValueError(f"Workflow template not found: {workflow_id}")

        # Create execution context
        context = WorkflowContext(
            workflow_id=workflow_id,
            execution_id=execution_id,
            input_data=input_data or {},
        )

        # Save initial execution record
        execution_data = {
            "id": execution_id,
            "template_id": workflow_id,
            "input_data": input_data,
            "status": WorkflowStatus.RUNNING.value,
            "started_at": datetime.now().isoformat(),
        }
        data_persistence.save_workflow_execution(execution_data)

        try:
            # Parse workflow steps
            steps_data = template["template_data"].get("steps", [])
            steps = [WorkflowStep(**step_data) for step_data in steps_data]

            # Execute workflow
            result = await self._execute_steps(context, steps)

            # Update execution record
            execution_data.update(
                {
                    "status": WorkflowStatus.COMPLETED.value,
                    "output_data": result,
                    "completed_at": datetime.now().isoformat(),
                    "execution_time_ms": int(
                        (
                            datetime.now()
                            - datetime.fromisoformat(execution_data["started_at"])
                        ).total_seconds()
                        * 1000
                    ),
                }
            )
            data_persistence.save_workflow_execution(execution_data)

            return {
                "execution_id": execution_id,
                "status": "completed",
                "result": result,
                "context": {
                    "variables": context.variables,
                    "step_results": context.step_results,
                },
            }

        except Exception as e:
            # Update execution record with error
            execution_data.update(
                {
                    "status": WorkflowStatus.FAILED.value,
                    "error_message": str(e),
                    "completed_at": datetime.now().isoformat(),
                    "execution_time_ms": int(
                        (
                            datetime.now()
                            - datetime.fromisoformat(execution_data["started_at"])
                        ).total_seconds()
                        * 1000
                    ),
                }
            )
            data_persistence.save_workflow_execution(execution_data)

            logger.error(f"Workflow execution failed: {e}")
            raise

    async def _execute_steps(
        self, context: WorkflowContext, steps: List[WorkflowStep]
    ) -> Dict[str, Any]:
        """Execute workflow steps"""
        executed_steps = set()
        step_results = {}

        while len(executed_steps) < len(steps):
            executable_steps = self._get_executable_steps(
                steps, executed_steps, step_results
            )

            if not executable_steps:
                # No executable steps found - check for circular dependencies
                remaining_steps = [s for s in steps if s.id not in executed_steps]
                if remaining_steps:
                    raise RuntimeError(
                        f"Circular dependency detected in steps: {[s.id for s in remaining_steps]}"
                    )
                break

            # Execute steps in parallel
            tasks = []
            for step in executable_steps:
                task = self._execute_step(context, step, step_results)
                tasks.append(task)

            # Wait for all parallel steps to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for step, result in zip(executable_steps, results):
                if isinstance(result, Exception):
                    logger.error(f"Step {step.id} failed: {result}")
                    # Handle step failure based on retry configuration
                    if step.retry_count > 0:
                        await self._retry_step(context, step, step_results)
                    else:
                        raise result
                else:
                    step_results[step.id] = result
                    executed_steps.add(step.id)

        return step_results

    def _get_executable_steps(
        self,
        steps: List[WorkflowStep],
        executed_steps: set,
        step_results: Dict[str, Any],
    ) -> List[WorkflowStep]:
        """Get steps that are ready to execute (dependencies satisfied)"""
        executable = []

        for step in steps:
            if step.id in executed_steps:
                continue

            # Check if all dependencies are satisfied
            dependencies_satisfied = all(
                dep_id in executed_steps and step_results.get(dep_id) is not None
                for dep_id in step.depends_on
            )

            if dependencies_satisfied:
                executable.append(step)

        return executable

    async def _execute_step(
        self, context: WorkflowContext, step: WorkflowStep, step_results: Dict[str, Any]
    ) -> Any:
        """Execute a single workflow step"""
        logger.info(f"Executing step: {step.name} ({step.id})")

        try:
            # Check if action is registered
            if step.action not in self.actions:
                raise ValueError(f"Unknown action: {step.action}")

            # Prepare step parameters with variable substitution
            parameters = self._substitute_variables(step.parameters, context.variables)

            # Execute action with timeout
            action_func = self.actions[step.action]
            result = await asyncio.wait_for(
                action_func(context, parameters), timeout=step.timeout
            )

            # Store result in context
            context.step_results[step.id] = result

            logger.info(f"Step completed: {step.name} ({step.id})")
            return result

        except asyncio.TimeoutError:
            raise TimeoutError(f"Step {step.id} timed out after {step.timeout} seconds")
        except Exception as e:
            logger.error(f"Step {step.id} failed: {e}")
            raise

    async def _retry_step(
        self, context: WorkflowContext, step: WorkflowStep, step_results: Dict[str, Any]
    ) -> None:
        """Retry a failed step"""
        for attempt in range(step.retry_count):
            logger.info(f"Retrying step {step.id}, attempt {attempt + 1}")

            try:
                await asyncio.sleep(step.retry_delay)
                result = await self._execute_step(context, step, step_results)
                step_results[step.id] = result
                return
            except Exception as e:
                logger.warning(f"Step {step.id} retry {attempt + 1} failed: {e}")
                if attempt == step.retry_count - 1:
                    raise e

    def _substitute_variables(self, data: Any, variables: Dict[str, Any]) -> Any:
        """Recursively substitute variables in data"""
        if isinstance(data, str):
            # Simple variable substitution: {{variable_name}}
            for key, value in variables.items():
                data = data.replace(f"{{{{{key}}}}}", str(value))
            return data
        elif isinstance(data, dict):
            return {
                k: self._substitute_variables(v, variables) for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._substitute_variables(item, variables) for item in data]
        else:
            return data

    def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow execution status"""
        # In a real implementation, this would query the database
        # For now, return basic status
        execution = data_persistence.get_workflow_execution(execution_id)
        if execution:
            return {
                "execution_id": execution_id,
                "status": execution["status"],
                "started_at": execution["started_at"],
                "completed_at": execution.get("completed_at"),
                "error_message": execution.get("error_message"),
            }
        return None

    async def cancel_workflow(self, execution_id: str) -> bool:
        """Cancel a running workflow"""
        async with self._lock:
            if execution_id in self.running_workflows:
                # Cancel the task
                task = self.running_workflows[execution_id]
                task.cancel()

                # Update execution record
                execution_data = {
                    "id": execution_id,
                    "status": WorkflowStatus.CANCELLED.value,
                    "completed_at": datetime.now().isoformat(),
                }
                data_persistence.save_workflow_execution(execution_data)

                return True
            return False

    def get_workflow_logs(
        self, execution_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get workflow execution logs"""
        # In a real implementation, this would query a log database
        # For now, return basic log structure
        execution = data_persistence.get_workflow_execution(execution_id)
        if not execution:
            return []

        logs = [
            {
                "timestamp": execution["started_at"],
                "level": "info",
                "message": f"Workflow execution started: {execution_id}",
            }
        ]

        if execution.get("completed_at"):
            logs.append(
                {
                    "timestamp": execution["completed_at"],
                    "level": "info" if execution["status"] == "completed" else "error",
                    "message": f"Workflow execution {execution['status']}: {execution_id}",
                }
            )

        if execution.get("error_message"):
            logs.append(
                {
                    "timestamp": execution.get("completed_at", execution["started_at"]),
                    "level": "error",
                    "message": f"Error: {execution['error_message']}",
                }
            )

        return logs[-limit:]


# Global workflow engine instance
workflow_engine = WorkflowEngine()
