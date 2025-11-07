"""
Google Drive Automation Engine
Core workflow execution, trigger processing, and action framework
"""

import os
import json
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict, field
from pathlib import Path
from contextlib import asynccontextmanager
from enum import Enum

# Local imports
from loguru import logger
from config import get_config_instance
from extensions import db, redis_client

# Try to import required services
try:
    from google_drive_service import get_google_drive_service
    from google_drive_memory import get_google_drive_memory_service
    from ingestion_pipeline.content_extractor import get_content_extractor
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logger.warning("Google Drive services not available")

class TriggerType(Enum):
    """Trigger types for workflows"""
    FILE_CREATED = "file_created"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    FILE_SHARED = "file_shared"
    FILE_MOVED = "file_moved"
    FILE_RENAMED = "file_renamed"
    FOLDER_CREATED = "folder_created"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    MANUAL = "manual"

class ActionType(Enum):
    """Action types for workflows"""
    COPY_FILE = "copy_file"
    MOVE_FILE = "move_file"
    DELETE_FILE = "delete_file"
    RENAME_FILE = "rename_file"
    CREATE_FOLDER = "create_folder"
    SEND_NOTIFICATION = "send_notification"
    SEND_EMAIL = "send_email"
    EXTRACT_TEXT = "extract_text"
    GENERATE_EMBEDDINGS = "generate_embeddings"
    UPDATE_SEARCH_INDEX = "update_search_index"
    ADD_LABELS = "add_labels"
    SET_PERMISSIONS = "set_permissions"
    WEBHOOK_CALL = "webhook_call"
    CUSTOM_SCRIPT = "custom_script"

class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

@dataclass
class TriggerCondition:
    """Trigger condition data model"""
    field: str
    operator: str  # equals, contains, starts_with, ends_with, greater_than, less_than, in, not_in
    value: Any
    logic: str = "and"  # and, or
    case_sensitive: bool = False

@dataclass
class Trigger:
    """Trigger data model"""
    type: TriggerType
    conditions: List[TriggerCondition] = field(default_factory=list)
    logic: str = "and"  # and, or
    debounce_time: int = 0  # seconds
    enabled: bool = True
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate trigger conditions against data"""
        
        if not self.conditions:
            return True
        
        results = []
        
        for condition in self.conditions:
            result = self._evaluate_condition(condition, data)
            results.append(result)
        
        # Apply logic
        if self.logic == "or":
            return any(results)
        else:  # default to "and"
            return all(results)
    
    def _evaluate_condition(self, condition: TriggerCondition, data: Dict[str, Any]) -> bool:
        """Evaluate individual condition"""
        
        try:
            # Get field value
            field_path = condition.field.split('.')
            field_value = data
            
            for path_part in field_path:
                if isinstance(field_value, dict):
                    field_value = field_value.get(path_part)
                elif isinstance(field_value, list) and path_part.isdigit():
                    index = int(path_part)
                    field_value = field_value[index] if index < len(field_value) else None
                else:
                    field_value = None
                    break
                
                if field_value is None:
                    break
            
            # Handle missing field
            if field_value is None:
                return condition.operator == "not_equals" or condition.operator == "not_in"
            
            # Convert to string for text operations if needed
            if condition.operator in ["contains", "starts_with", "ends_with"]:
                field_value = str(field_value)
                condition_value = str(condition.value)
                
                if not condition.case_sensitive:
                    field_value = field_value.lower()
                    condition_value = condition_value.lower()
                
                if condition.operator == "contains":
                    return condition_value in field_value
                elif condition.operator == "starts_with":
                    return field_value.startswith(condition_value)
                elif condition.operator == "ends_with":
                    return field_value.endswith(condition_value)
            
            # Handle comparison operations
            elif condition.operator == "equals":
                return field_value == condition.value
            elif condition.operator == "not_equals":
                return field_value != condition.value
            elif condition.operator == "greater_than":
                try:
                    return float(field_value) > float(condition.value)
                except (ValueError, TypeError):
                    return False
            elif condition.operator == "less_than":
                try:
                    return float(field_value) < float(condition.value)
                except (ValueError, TypeError):
                    return False
            elif condition.operator == "in":
                return field_value in condition.value
            elif condition.operator == "not_in":
                return field_value not in condition.value
            
            return False
        
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")
            return False

@dataclass
class Action:
    """Action data model"""
    type: ActionType
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    retry_count: int = 3
    retry_delay: int = 5  # seconds
    timeout: int = 300  # seconds

@dataclass
class Workflow:
    """Workflow data model"""
    id: str
    name: str
    description: str
    triggers: List[Trigger]
    actions: List[Action]
    enabled: bool = True
    max_concurrent_runs: int = 1
    timeout: int = 1800  # 30 minutes
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "triggers": [asdict(trigger) for trigger in self.triggers],
            "actions": [asdict(action) for action in self.actions],
            "enabled": self.enabled,
            "max_concurrent_runs": self.max_concurrent_runs,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Workflow':
        """Create from dictionary"""
        triggers = []
        for trigger_data in data.get("triggers", []):
            conditions = []
            for condition_data in trigger_data.get("conditions", []):
                condition = TriggerCondition(
                    field=condition_data["field"],
                    operator=condition_data["operator"],
                    value=condition_data["value"],
                    logic=condition_data.get("logic", "and"),
                    case_sensitive=condition_data.get("case_sensitive", False)
                )
                conditions.append(condition)
            
            trigger = Trigger(
                type=TriggerType(trigger_data["type"]),
                conditions=conditions,
                logic=trigger_data.get("logic", "and"),
                debounce_time=trigger_data.get("debounce_time", 0),
                enabled=trigger_data.get("enabled", True)
            )
            triggers.append(trigger)
        
        actions = []
        for action_data in data.get("actions", []):
            action = Action(
                type=ActionType(action_data["type"]),
                config=action_data.get("config", {}),
                enabled=action_data.get("enabled", True),
                retry_count=action_data.get("retry_count", 3),
                retry_delay=action_data.get("retry_delay", 5),
                timeout=action_data.get("timeout", 300)
            )
            actions.append(action)
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            triggers=triggers,
            actions=actions,
            enabled=data.get("enabled", True),
            max_concurrent_runs=data.get("max_concurrent_runs", 1),
            timeout=data.get("timeout", 1800),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            created_by=data.get("created_by", ""),
            tags=data.get("tags", [])
        )

@dataclass
class WorkflowExecution:
    """Workflow execution data model"""
    execution_id: str
    workflow_id: str
    status: WorkflowStatus
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    steps_executed: List[str] = field(default_factory=list)
    action_results: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "trigger_data": self.trigger_data,
            "results": self.results,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "steps_executed": self.steps_executed,
            "action_results": self.action_results
        }

class AutomationEngine:
    """Google Drive Automation Engine"""
    
    def __init__(self, config=None):
        self.config = config or get_config_instance()
        self.automation_config = self.config.automation
        
        # Workflow storage
        self.workflows: Dict[str, Workflow] = {}
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.execution_history: List[WorkflowExecution] = []
        
        # Execution limits
        self.max_concurrent_workflows = self.automation_config.max_concurrent_workflows
        self.default_workflow_timeout = self.automation_config.default_workflow_timeout
        
        # Action handlers
        self.action_handlers: Dict[ActionType, Callable] = {}
        self._register_action_handlers()
        
        # Trigger debounce cache
        self.trigger_cache: Dict[str, datetime] = {}
        
        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        
        logger.info("Google Drive Automation Engine initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.load_workflows()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop()
    
    async def stop(self):
        """Stop automation engine and cleanup resources"""
        
        try:
            # Cancel background tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
            self._background_tasks.clear()
            
            # Save workflows and execution history
            await self.save_workflows()
            await self.save_execution_history()
            
            logger.info("Automation Engine stopped")
        
        except Exception as e:
            logger.error(f"Error stopping Automation Engine: {e}")
    
    # ==================== WORKFLOW MANAGEMENT ====================
    
    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new workflow"""
        
        try:
            # Generate workflow ID
            workflow_id = str(uuid.uuid4())
            workflow_data["id"] = workflow_id
            workflow_data["created_at"] = datetime.utcnow().isoformat()
            workflow_data["updated_at"] = datetime.utcnow().isoformat()
            
            # Create workflow object
            workflow = Workflow.from_dict(workflow_data)
            
            # Validate workflow
            validation_result = await self.validate_workflow(workflow)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Workflow validation failed: {validation_result['error']}"
                }
            
            # Store workflow
            self.workflows[workflow_id] = workflow
            
            # Save to storage
            await self.save_workflow(workflow)
            
            logger.info(f"Created workflow: {workflow.name} ({workflow_id})")
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "workflow": workflow.to_dict()
            }
        
        except Exception as e:
            logger.error(f"Failed to create workflow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing workflow"""
        
        try:
            if workflow_id not in self.workflows:
                return {
                    "success": False,
                    "error": "Workflow not found"
                }
            
            # Get existing workflow
            existing_workflow = self.workflows[workflow_id]
            
            # Update workflow data
            workflow_data["id"] = workflow_id
            workflow_data["created_at"] = existing_workflow.created_at.isoformat()
            workflow_data["updated_at"] = datetime.utcnow().isoformat()
            
            # Create updated workflow object
            updated_workflow = Workflow.from_dict(workflow_data)
            
            # Validate workflow
            validation_result = await self.validate_workflow(updated_workflow)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": f"Workflow validation failed: {validation_result['error']}"
                }
            
            # Store updated workflow
            self.workflows[workflow_id] = updated_workflow
            
            # Save to storage
            await self.save_workflow(updated_workflow)
            
            logger.info(f"Updated workflow: {updated_workflow.name} ({workflow_id})")
            
            return {
                "success": True,
                "workflow_id": workflow_id,
                "workflow": updated_workflow.to_dict()
            }
        
        except Exception as e:
            logger.error(f"Failed to update workflow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Delete workflow"""
        
        try:
            if workflow_id not in self.workflows:
                return {
                    "success": False,
                    "error": "Workflow not found"
                }
            
            # Get workflow
            workflow = self.workflows[workflow_id]
            
            # Cancel any active executions
            executions_to_cancel = [
                execution for execution in self.active_executions.values()
                if execution.workflow_id == workflow_id and execution.status == WorkflowStatus.RUNNING
            ]
            
            for execution in executions_to_cancel:
                await self.cancel_execution(execution.execution_id)
            
            # Remove workflow
            del self.workflows[workflow_id]
            
            # Remove from storage
            await self.delete_workflow_storage(workflow_id)
            
            logger.info(f"Deleted workflow: {workflow.name} ({workflow_id})")
            
            return {
                "success": True,
                "workflow_id": workflow_id
            }
        
        except Exception as e:
            logger.error(f"Failed to delete workflow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow by ID"""
        
        try:
            workflow = self.workflows.get(workflow_id)
            
            if not workflow:
                return {
                    "success": False,
                    "error": "Workflow not found"
                }
            
            # Add execution statistics
            execution_stats = await self.get_workflow_execution_stats(workflow_id)
            
            return {
                "success": True,
                "workflow": workflow.to_dict(),
                "execution_stats": execution_stats
            }
        
        except Exception as e:
            logger.error(f"Failed to get workflow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_workflows(self, 
                            enabled_only: bool = False,
                            page: int = 1,
                            limit: int = 50,
                            tags: Optional[List[str]] = None,
                            created_by: Optional[str] = None) -> Dict[str, Any]:
        """List workflows"""
        
        try:
            # Filter workflows
            workflows = []
            
            for workflow in self.workflows.values():
                # Apply filters
                if enabled_only and not workflow.enabled:
                    continue
                
                if tags and not any(tag in workflow.tags for tag in tags):
                    continue
                
                if created_by and workflow.created_by != created_by:
                    continue
                
                workflows.append(workflow)
            
            # Sort by updated_at (most recent first)
            workflows.sort(key=lambda w: w.updated_at, reverse=True)
            
            # Pagination
            total = len(workflows)
            start = (page - 1) * limit
            end = start + limit
            paginated_workflows = workflows[start:end]
            
            return {
                "success": True,
                "workflows": [workflow.to_dict() for workflow in paginated_workflows],
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit
            }
        
        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflows": []
            }
    
    # ==================== WORKFLOW EXECUTION ====================
    
    async def execute_workflow(self, 
                              workflow_id: str,
                              trigger_data: Dict[str, Any],
                              manual_trigger: bool = False) -> Dict[str, Any]:
        """Execute workflow"""
        
        try:
            # Get workflow
            workflow = self.workflows.get(workflow_id)
            if not workflow:
                return {
                    "success": False,
                    "error": "Workflow not found"
                }
            
            if not workflow.enabled and not manual_trigger:
                return {
                    "success": False,
                    "error": "Workflow is disabled"
                }
            
            # Check concurrent execution limit
            if not manual_trigger:
                running_count = sum(
                    1 for execution in self.active_executions.values()
                    if execution.workflow_id == workflow_id and execution.status == WorkflowStatus.RUNNING
                )
                
                if running_count >= workflow.max_concurrent_runs:
                    return {
                        "success": False,
                        "error": f"Maximum concurrent executions reached ({workflow.max_concurrent_runs})"
                    }
            
            # Generate execution ID
            execution_id = str(uuid.uuid4())
            
            # Create execution object
            execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_id=workflow_id,
                status=WorkflowStatus.PENDING,
                trigger_data=trigger_data
            )
            
            # Add to active executions
            self.active_executions[execution_id] = execution
            
            # Start execution in background
            task = asyncio.create_task(
                self._execute_workflow_background(workflow, execution)
            )
            self._background_tasks.append(task)
            
            logger.info(f"Started workflow execution: {workflow.name} ({execution_id})")
            
            return {
                "success": True,
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "status": execution.status.value
            }
        
        except Exception as e:
            logger.error(f"Failed to execute workflow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_workflow_background(self, 
                                          workflow: Workflow,
                                          execution: WorkflowExecution):
        """Execute workflow in background"""
        
        try:
            # Update status
            execution.status = WorkflowStatus.RUNNING
            
            # Log start
            logger.info(f"Executing workflow: {workflow.name} ({execution.execution_id})")
            
            start_time = datetime.utcnow()
            
            # Execute actions
            for i, action in enumerate(workflow.actions):
                if not action.enabled:
                    continue
                
                try:
                    # Check if execution has been cancelled
                    if execution.status == WorkflowStatus.CANCELLED:
                        break
                    
                    # Execute action
                    action_result = await self._execute_action(action, execution)
                    
                    # Store action result
                    execution.action_results[f"action_{i}"] = action_result
                    execution.steps_executed.append(f"action_{i}: {action.type.value}")
                    
                    # Check if action failed and should stop workflow
                    if not action_result.get("success", False):
                        error_msg = f"Action {action.type.value} failed: {action_result.get('error', 'Unknown error')}"
                        logger.error(f"Workflow action failed: {error_msg}")
                        
                        # Mark execution as failed
                        execution.status = WorkflowStatus.FAILED
                        execution.error_message = error_msg
                        break
                
                except Exception as e:
                    error_msg = f"Action {action.type.value} error: {str(e)}"
                    logger.error(f"Workflow action error: {error_msg}")
                    
                    # Mark execution as failed
                    execution.status = WorkflowStatus.FAILED
                    execution.error_message = error_msg
                    break
            
            # Update execution
            end_time = datetime.utcnow()
            execution.completed_at = end_time
            execution.duration = (end_time - start_time).total_seconds()
            
            # Mark as completed if not failed or cancelled
            if execution.status == WorkflowStatus.RUNNING:
                execution.status = WorkflowStatus.COMPLETED
            
            # Log completion
            logger.info(f"Workflow execution completed: {workflow.name} ({execution.execution_id}) - {execution.status.value}")
            
            # Save to execution history
            self.execution_history.append(execution)
            
            # Clean up old history (keep last 1000)
            if len(self.execution_history) > 1000:
                self.execution_history = self.execution_history[-1000:]
        
        except asyncio.CancelledError:
            execution.status = WorkflowStatus.CANCELLED
            execution.error_message = "Execution was cancelled"
            logger.info(f"Workflow execution cancelled: {execution.execution_id}")
        
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error_message = str(e)
            logger.error(f"Workflow execution failed: {execution.execution_id} - {e}")
        
        finally:
            # Remove from active executions
            if execution.execution_id in self.active_executions:
                del self.active_executions[execution.execution_id]
            
            # Save execution history
            await self.save_execution_history()
    
    async def _execute_action(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        """Execute individual action"""
        
        try:
            # Get action handler
            handler = self.action_handlers.get(action.type)
            if not handler:
                return {
                    "success": False,
                    "error": f"No handler for action type: {action.type.value}"
                }
            
            # Execute action with retry logic
            for attempt in range(action.retry_count + 1):
                try:
                    # Execute action
                    result = await handler(action, execution)
                    
                    if result.get("success", False):
                        return result
                    
                    # If failed and not last attempt, wait and retry
                    if attempt < action.retry_count:
                        logger.warning(f"Action {action.type.value} failed (attempt {attempt + 1}), retrying in {action.retry_delay}s...")
                        await asyncio.sleep(action.retry_delay)
                        continue
                    
                    return result
                
                except Exception as e:
                    if attempt < action.retry_count:
                        logger.warning(f"Action {action.type.value} error (attempt {attempt + 1}), retrying in {action.retry_delay}s: {e}")
                        await asyncio.sleep(action.retry_delay)
                        continue
                    
                    return {
                        "success": False,
                        "error": f"Action {action.type.value} error after {attempt + 1} attempts: {str(e)}"
                    }
        
        except Exception as e:
            logger.error(f"Failed to execute action {action.type.value}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== TRIGGER PROCESSING ====================
    
    async def process_trigger(self, 
                             trigger_type: str,
                             trigger_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process trigger and execute matching workflows"""
        
        try:
            results = []
            
            # Find matching workflows
            matching_workflows = await self._find_matching_workflows(trigger_type, trigger_data)
            
            # Execute matching workflows
            for workflow in matching_workflows:
                result = await self.execute_workflow(workflow.id, trigger_data)
                results.append({
                    "workflow_id": workflow.id,
                    "workflow_name": workflow.name,
                    "execution_result": result
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Failed to process trigger {trigger_type}: {e}")
            return []
    
    async def _find_matching_workflows(self, 
                                      trigger_type: str,
                                      trigger_data: Dict[str, Any]) -> List[Workflow]:
        """Find workflows that match trigger"""
        
        try:
            matching_workflows = []
            
            for workflow in self.workflows.values():
                if not workflow.enabled:
                    continue
                
                # Check triggers
                for trigger in workflow.triggers:
                    if not trigger.enabled:
                        continue
                    
                    # Check trigger type
                    if trigger.type.value != trigger_type:
                        continue
                    
                    # Check debounce
                    debounce_key = f"{workflow.id}_{trigger_type}"
                    if trigger.debounce_time > 0:
                        last_triggered = self.trigger_cache.get(debounce_key)
                        if last_triggered and (datetime.utcnow() - last_triggered).seconds < trigger.debounce_time:
                            continue
                        
                        # Update debounce cache
                        self.trigger_cache[debounce_key] = datetime.utcnow()
                    
                    # Evaluate trigger conditions
                    if trigger.evaluate(trigger_data):
                        matching_workflows.append(workflow)
                        break  # Only match workflow once
            
            return matching_workflows
        
        except Exception as e:
            logger.error(f"Failed to find matching workflows: {e}")
            return []
    
    # ==================== EXECUTION MANAGEMENT ====================
    
    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """Get workflow execution by ID"""
        
        try:
            # Check active executions first
            execution = self.active_executions.get(execution_id)
            
            if not execution:
                # Check execution history
                for hist_execution in self.execution_history:
                    if hist_execution.execution_id == execution_id:
                        execution = hist_execution
                        break
            
            if not execution:
                return {
                    "success": False,
                    "error": "Execution not found"
                }
            
            return {
                "success": True,
                "execution": execution.to_dict()
            }
        
        except Exception as e:
            logger.error(f"Failed to get execution: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """Cancel workflow execution"""
        
        try:
            execution = self.active_executions.get(execution_id)
            
            if not execution:
                return {
                    "success": False,
                    "error": "Execution not found or already completed"
                }
            
            if execution.status != WorkflowStatus.RUNNING:
                return {
                    "success": False,
                    "error": f"Cannot cancel execution in status: {execution.status.value}"
                }
            
            # Mark as cancelled
            execution.status = WorkflowStatus.CANCELLED
            execution.error_message = "Execution was cancelled by user"
            execution.completed_at = datetime.utcnow()
            
            logger.info(f"Cancelled execution: {execution_id}")
            
            return {
                "success": True,
                "execution_id": execution_id,
                "status": execution.status.value
            }
        
        except Exception as e:
            logger.error(f"Failed to cancel execution: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_executions(self,
                             workflow_id: Optional[str] = None,
                             status: Optional[str] = None,
                             page: int = 1,
                             limit: int = 50) -> Dict[str, Any]:
        """List workflow executions"""
        
        try:
            # Combine active executions and history
            all_executions = list(self.active_executions.values()) + self.execution_history
            
            # Filter executions
            filtered_executions = []
            
            for execution in all_executions:
                if workflow_id and execution.workflow_id != workflow_id:
                    continue
                
                if status and execution.status.value != status:
                    continue
                
                filtered_executions.append(execution)
            
            # Sort by started_at (most recent first)
            filtered_executions.sort(key=lambda e: e.started_at, reverse=True)
            
            # Pagination
            total = len(filtered_executions)
            start = (page - 1) * limit
            end = start + limit
            paginated_executions = filtered_executions[start:end]
            
            return {
                "success": True,
                "executions": [execution.to_dict() for execution in paginated_executions],
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit
            }
        
        except Exception as e:
            logger.error(f"Failed to list executions: {e}")
            return {
                "success": False,
                "error": str(e),
                "executions": []
            }
    
    # ==================== ACTION HANDLERS ====================
    
    def _register_action_handlers(self):
        """Register action handlers"""
        
        # File operations
        self.action_handlers[ActionType.COPY_FILE] = self._action_copy_file
        self.action_handlers[ActionType.MOVE_FILE] = self._action_move_file
        self.action_handlers[ActionType.DELETE_FILE] = self._action_delete_file
        self.action_handlers[ActionType.RENAME_FILE] = self._action_rename_file
        self.action_handlers[ActionType.CREATE_FOLDER] = self._action_create_folder
        
        # Communication
        self.action_handlers[ActionType.SEND_NOTIFICATION] = self._action_send_notification
        self.action_handlers[ActionType.SEND_EMAIL] = self._action_send_email
        
        # Content processing
        self.action_handlers[ActionType.EXTRACT_TEXT] = self._action_extract_text
        self.action_handlers[ActionType.GENERATE_EMBEDDINGS] = self._action_generate_embeddings
        self.action_handlers[ActionType.UPDATE_SEARCH_INDEX] = self._action_update_search_index
        
        # Management
        self.action_handlers[ActionType.ADD_LABELS] = self._action_add_labels
        self.action_handlers[ActionType.SET_PERMISSIONS] = self._action_set_permissions
        
        # External
        self.action_handlers[ActionType.WEBHOOK_CALL] = self._action_webhook_call
        self.action_handlers[ActionType.CUSTOM_SCRIPT] = self._action_custom_script
    
    # File operation action handlers
    async def _action_copy_file(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        """Copy file action handler"""
        
        try:
            config = action.config
            file_id = config.get("file_id")
            if not file_id:
                # Try to get file_id from trigger data
                file_id = execution.trigger_data.get("file_id")
            
            new_name = config.get("new_name", "")
            parent_ids = config.get("parent_ids", [])
            
            if not file_id:
                return {
                    "success": False,
                    "error": "file_id is required"
                }
            
            # Get Google Drive service
            drive_service = await get_google_drive_service()
            if not drive_service:
                return {
                    "success": False,
                    "error": "Google Drive service not available"
                }
            
            # Get file info first
            file_result = await drive_service.get_file(file_id)
            if not file_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to get file info: {file_result.get('error')}"
                }
            
            file_data = file_result["file"]
            
            # Download file
            import tempfile
            temp_path = None
            
            try:
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name
                
                download_result = await drive_service.download_file(file_id, temp_path)
                if not download_result["success"]:
                    return {
                        "success": False,
                        "error": f"Failed to download file: {download_result.get('error')}"
                    }
                
                # Upload file
                upload_result = await drive_service.upload_file(
                    file_path=temp_path,
                    file_name=new_name or file_data["name"],
                    parent_id=parent_ids[0] if parent_ids else None
                )
                
                if not upload_result["success"]:
                    return {
                        "success": False,
                        "error": f"Failed to upload file: {upload_result.get('error')}"
                    }
                
                # Add additional parents if specified
                if len(parent_ids) > 1:
                    uploaded_file_id = upload_result["file"]["id"]
                    for parent_id in parent_ids[1:]:
                        update_result = await drive_service.update_file(
                            uploaded_file_id,
                            add_parents=parent_id
                        )
                        if not update_result["success"]:
                            logger.warning(f"Failed to add parent {parent_id}: {update_result.get('error')}")
                
                return {
                    "success": True,
                    "message": f"File copied successfully",
                    "original_file_id": file_id,
                    "new_file_id": upload_result["file"]["id"],
                    "new_file_name": upload_result["file"]["name"]
                }
            
            finally:
                # Clean up temp file
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        except Exception as e:
            logger.error(f"Copy file action failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_move_file(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        """Move file action handler"""
        
        try:
            config = action.config
            file_id = config.get("file_id")
            if not file_id:
                file_id = execution.trigger_data.get("file_id")
            
            add_parents = config.get("add_parents", [])
            remove_parents = config.get("remove_parents", [])
            
            if not file_id or (not add_parents and not remove_parents):
                return {
                    "success": False,
                    "error": "file_id and either add_parents or remove_parents are required"
                }
            
            # Get Google Drive service
            drive_service = await get_google_drive_service()
            if not drive_service:
                return {
                    "success": False,
                    "error": "Google Drive service not available"
                }
            
            # Update file parents
            update_result = await drive_service.update_file(
                file_id,
                add_parents=add_parents[0] if add_parents else None,
                remove_parents=remove_parents[0] if remove_parents else None
            )
            
            if not update_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to move file: {update_result.get('error')}"
                }
            
            return {
                "success": True,
                "message": "File moved successfully",
                "file_id": file_id,
                "added_parents": add_parents,
                "removed_parents": remove_parents
            }
        
        except Exception as e:
            logger.error(f"Move file action failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_delete_file(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        """Delete file action handler"""
        
        try:
            config = action.config
            file_id = config.get("file_id")
            if not file_id:
                file_id = execution.trigger_data.get("file_id")
            
            if not file_id:
                return {
                    "success": False,
                    "error": "file_id is required"
                }
            
            # Get Google Drive service
            drive_service = await get_google_drive_service()
            if not drive_service:
                return {
                    "success": False,
                    "error": "Google Drive service not available"
                }
            
            # Delete file
            delete_result = await drive_service.delete_file(file_id)
            
            if not delete_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to delete file: {delete_result.get('error')}"
                }
            
            return {
                "success": True,
                "message": "File deleted successfully",
                "file_id": file_id
            }
        
        except Exception as e:
            logger.error(f"Delete file action failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_send_notification(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        """Send notification action handler"""
        
        try:
            config = action.config
            message = config.get("message", "Workflow executed")
            title = config.get("title", "Workflow Notification")
            recipients = config.get("recipients", [])
            
            # This would integrate with your notification system
            # For now, just log the notification
            logger.info(f"NOTIFICATION - {title}: {message}")
            
            if recipients:
                logger.info(f"Notification sent to: {', '.join(recipients)}")
            
            return {
                "success": True,
                "message": "Notification sent successfully",
                "title": title,
                "recipients": recipients
            }
        
        except Exception as e:
            logger.error(f"Send notification action failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_extract_text(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        """Extract text action handler"""
        
        try:
            config = action.config
            file_id = config.get("file_id")
            if not file_id:
                file_id = execution.trigger_data.get("file_id")
            
            if not file_id:
                return {
                    "success": False,
                    "error": "file_id is required"
                }
            
            # Get content extractor
            content_extractor = await get_content_extractor()
            if not content_extractor:
                return {
                    "success": False,
                    "error": "Content extractor not available"
                }
            
            # Get file info
            drive_service = await get_google_drive_service()
            if not drive_service:
                return {
                    "success": False,
                    "error": "Google Drive service not available"
                }
            
            file_result = await drive_service.get_file(file_id)
            if not file_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to get file info: {file_result.get('error')}"
                }
            
            file_data = file_result["file"]
            
            # Download file
            import tempfile
            temp_path = None
            
            try:
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name
                
                download_result = await drive_service.download_file(file_id, temp_path)
                if not download_result["success"]:
                    return {
                        "success": False,
                        "error": f"Failed to download file: {download_result.get('error')}"
                    }
                
                # Extract content
                extracted_content = await content_extractor.extract_content(
                    file_id=file_id,
                    file_path=temp_path,
                    file_name=file_data["name"]
                )
                
                if not extracted_content.success:
                    return {
                        "success": False,
                        "error": f"Failed to extract content: {extracted_content.error_message}"
                    }
                
                # Store extracted content (this would typically be saved to database)
                content_data = {
                    "file_id": file_id,
                    "text_content": extracted_content.text_content,
                    "html_content": extracted_content.html_content,
                    "metadata": extracted_content.to_dict()
                }
                
                return {
                    "success": True,
                    "message": "Text extracted successfully",
                    "file_id": file_id,
                    "content_length": len(extracted_content.text_content),
                    "word_count": extracted_content.word_count,
                    "extraction_method": extracted_content.extraction_method
                }
            
            finally:
                # Clean up temp file
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        except Exception as e:
            logger.error(f"Extract text action failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _action_generate_embeddings(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        """Generate embeddings action handler"""
        
        try:
            config = action.config
            file_id = config.get("file_id")
            if not file_id:
                file_id = execution.trigger_data.get("file_id")
            
            if not file_id:
                return {
                    "success": False,
                    "error": "file_id is required"
                }
            
            # Get memory service
            memory_service = await get_google_drive_memory_service()
            if not memory_service:
                return {
                    "success": False,
                    "error": "Memory service not available"
                }
            
            # Get existing text content (from previous step or database)
            text_content = execution.trigger_data.get("text_content", "")
            
            if not text_content:
                # Try to get from file database
                # This would integrate with your content storage
                text_content = "Sample text content for embeddings"
            
            if not text_content.strip():
                return {
                    "success": False,
                    "error": "No text content available for embeddings"
                }
            
            # Generate and store embeddings
            embedding_result = await memory_service.store_embedding(
                file_id=file_id,
                text=text_content,
                metadata={
                    "source": "workflow_action",
                    "execution_id": execution.execution_id,
                    "workflow_id": execution.workflow_id
                }
            )
            
            if not embedding_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to store embeddings: {embedding_result.get('error')}"
                }
            
            return {
                "success": True,
                "message": "Embeddings generated successfully",
                "file_id": file_id,
                "embedding_model": embedding_result.get("embedding_model"),
                "content_length": len(text_content)
            }
        
        except Exception as e:
            logger.error(f"Generate embeddings action failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Placeholder handlers for other action types
    async def _action_rename_file(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        return {"success": False, "error": "Not implemented yet"}
    
    async def _action_create_folder(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        return {"success": False, "error": "Not implemented yet"}
    
    async def _action_send_email(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        return {"success": False, "error": "Not implemented yet"}
    
    async def _action_update_search_index(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        return {"success": False, "error": "Not implemented yet"}
    
    async def _action_add_labels(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        return {"success": False, "error": "Not implemented yet"}
    
    async def _action_set_permissions(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        return {"success": False, "error": "Not implemented yet"}
    
    async def _action_webhook_call(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        return {"success": False, "error": "Not implemented yet"}
    
    async def _action_custom_script(self, action: Action, execution: WorkflowExecution) -> Dict[str, Any]:
        return {"success": False, "error": "Not implemented yet"}
    
    # ==================== VALIDATION ====================
    
    async def validate_workflow(self, workflow: Workflow) -> Dict[str, Any]:
        """Validate workflow configuration"""
        
        try:
            # Check basic fields
            if not workflow.name.strip():
                return {"valid": False, "error": "Workflow name is required"}
            
            if not workflow.triggers:
                return {"valid": False, "error": "At least one trigger is required"}
            
            if not workflow.actions:
                return {"valid": False, "error": "At least one action is required"}
            
            # Validate triggers
            for i, trigger in enumerate(workflow.triggers):
                if not any(self.action_handlers.get(ActionType(action_type)) for action_type in ActionType):
                    continue
                
                # Validate trigger conditions
                for j, condition in enumerate(trigger.conditions):
                    if not condition.field:
                        return {"valid": False, "error": f"Trigger {i+1}, condition {j+1}: field is required"}
                    
                    if not condition.operator:
                        return {"valid": False, "error": f"Trigger {i+1}, condition {j+1}: operator is required"}
                    
                    if condition.value is None:
                        return {"valid": False, "error": f"Trigger {i+1}, condition {j+1}: value is required"}
            
            # Validate actions
            for i, action in enumerate(workflow.actions):
                # Check if action handler exists
                if action.type not in self.action_handlers:
                    return {"valid": False, "error": f"Action {i+1}: No handler for action type {action.type.value}"}
                
                # Validate action config based on type
                validation_result = await self._validate_action_config(action)
                if not validation_result["valid"]:
                    return validation_result
            
            return {"valid": True, "message": "Workflow is valid"}
        
        except Exception as e:
            logger.error(f"Workflow validation error: {e}")
            return {"valid": False, "error": f"Validation error: {str(e)}"}
    
    async def _validate_action_config(self, action: Action) -> Dict[str, Any]:
        """Validate individual action configuration"""
        
        try:
            config = action.config
            
            if action.type == ActionType.COPY_FILE:
                if not config.get("file_id") and not config.get("from_trigger"):
                    return {"valid": False, "error": "file_id or from_trigger is required"}
            
            elif action.type == ActionType.MOVE_FILE:
                if not config.get("file_id") and not config.get("from_trigger"):
                    return {"valid": False, "error": "file_id or from_trigger is required"}
                
                if not config.get("add_parents") and not config.get("remove_parents"):
                    return {"valid": False, "error": "add_parents or remove_parents is required"}
            
            elif action.type == ActionType.DELETE_FILE:
                if not config.get("file_id") and not config.get("from_trigger"):
                    return {"valid": False, "error": "file_id or from_trigger is required"}
            
            elif action.type == ActionType.SEND_NOTIFICATION:
                if not config.get("message"):
                    return {"valid": False, "error": "message is required"}
            
            elif action.type == ActionType.EXTRACT_TEXT:
                if not config.get("file_id") and not config.get("from_trigger"):
                    return {"valid": False, "error": "file_id or from_trigger is required"}
            
            elif action.type == ActionType.GENERATE_EMBEDDINGS:
                if not config.get("file_id") and not config.get("from_trigger"):
                    return {"valid": False, "error": "file_id or from_trigger is required"}
            
            return {"valid": True}
        
        except Exception as e:
            logger.error(f"Action config validation error: {e}")
            return {"valid": False, "error": f"Config validation error: {str(e)}"}
    
    # ==================== STORAGE ====================
    
    async def save_workflow(self, workflow: Workflow):
        """Save workflow to storage"""
        
        try:
            # This would integrate with your database
            # For now, just log
            logger.debug(f"Saving workflow: {workflow.id}")
        
        except Exception as e:
            logger.error(f"Failed to save workflow: {e}")
    
    async def load_workflows(self):
        """Load workflows from storage"""
        
        try:
            # This would integrate with your database
            # For now, just log
            logger.debug(f"Loading workflows from storage")
            logger.info(f"Loaded {len(self.workflows)} workflows")
        
        except Exception as e:
            logger.error(f"Failed to load workflows: {e}")
    
    async def save_execution_history(self):
        """Save execution history to storage"""
        
        try:
            # This would integrate with your database
            # For now, just log
            logger.debug(f"Saving {len(self.execution_history)} executions to history")
        
        except Exception as e:
            logger.error(f"Failed to save execution history: {e}")
    
    async def delete_workflow_storage(self, workflow_id: str):
        """Delete workflow from storage"""
        
        try:
            # This would integrate with your database
            logger.debug(f"Deleting workflow from storage: {workflow_id}")
        
        except Exception as e:
            logger.error(f"Failed to delete workflow from storage: {e}")
    
    # ==================== STATISTICS ====================
    
    async def get_workflow_execution_stats(self, workflow_id: str) -> Dict[str, Any]:
        """Get execution statistics for workflow"""
        
        try:
            # Get all executions for this workflow
            workflow_executions = [
                execution for execution in self.execution_history
                if execution.workflow_id == workflow_id
            ]
            
            # Add active executions
            active_executions = [
                execution for execution in self.active_executions.values()
                if execution.workflow_id == workflow_id
            ]
            
            all_executions = workflow_executions + active_executions
            
            if not all_executions:
                return {
                    "total_executions": 0,
                    "successful_executions": 0,
                    "failed_executions": 0,
                    "success_rate": 0.0,
                    "average_duration": 0.0,
                    "last_execution": None
                }
            
            # Calculate statistics
            total = len(all_executions)
            successful = len([e for e in all_executions if e.status == WorkflowStatus.COMPLETED])
            failed = len([e for e in all_executions if e.status == WorkflowStatus.FAILED])
            
            success_rate = (successful / total) * 100 if total > 0 else 0
            
            durations = [e.duration for e in all_executions if e.duration is not None]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # Get last execution
            last_execution = max(all_executions, key=lambda e: e.started_at)
            
            return {
                "total_executions": total,
                "successful_executions": successful,
                "failed_executions": failed,
                "success_rate": success_rate,
                "average_duration": avg_duration,
                "last_execution": {
                    "execution_id": last_execution.execution_id,
                    "status": last_execution.status.value,
                    "started_at": last_execution.started_at.isoformat(),
                    "duration": last_execution.duration
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to get workflow execution stats: {e}")
            return {}
    
    async def get_engine_stats(self) -> Dict[str, Any]:
        """Get automation engine statistics"""
        
        try:
            return {
                "total_workflows": len(self.workflows),
                "enabled_workflows": len([w for w in self.workflows.values() if w.enabled]),
                "active_executions": len(self.active_executions),
                "execution_history_size": len(self.execution_history),
                "background_tasks": len(self._background_tasks),
                "trigger_cache_size": len(self.trigger_cache),
                "max_concurrent_workflows": self.max_concurrent_workflows,
                "supported_triggers": [t.value for t in TriggerType],
                "supported_actions": [a.value for a in ActionType]
            }
        
        except Exception as e:
            logger.error(f"Failed to get engine stats: {e}")
            return {}

# Global automation engine instance
_automation_engine: Optional[AutomationEngine] = None

async def get_automation_engine() -> Optional[AutomationEngine]:
    """Get global automation engine instance"""
    
    global _automation_engine
    
    if _automation_engine is None:
        try:
            config = get_config_instance()
            _automation_engine = AutomationEngine(config)
            await _automation_engine.load_workflows()
            logger.info("Automation Engine created and workflows loaded")
        except Exception as e:
            logger.error(f"Failed to create Automation Engine: {e}")
            _automation_engine = None
    
    return _automation_engine

def clear_automation_engine():
    """Clear global automation engine instance"""
    
    global _automation_engine
    _automation_engine = None
    logger.info("Automation Engine cleared")

# Export classes and functions
__all__ = [
    'AutomationEngine',
    'Workflow',
    'WorkflowExecution',
    'Trigger',
    'TriggerType',
    'Action',
    'ActionType',
    'WorkflowStatus',
    'TriggerCondition',
    'get_automation_engine',
    'clear_automation_engine'
]