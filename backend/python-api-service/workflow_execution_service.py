import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import json

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowExecutionService:
    """
    Comprehensive workflow execution service that integrates with real services
    for the Atom Agent UI.
    """

    def __init__(self):
        self.active_executions = {}
        self.workflow_definitions = {}
        self.service_registry = {}
        self.initialize_service_registry()

    def initialize_service_registry(self):
        """Initialize the service registry with available service integrations"""
        self.service_registry = {
            "calendar": {
                "create_event": self._execute_calendar_create_event,
                "update_event": self._execute_calendar_update_event,
                "delete_event": self._execute_calendar_delete_event,
                "find_available_time": self._execute_calendar_find_available_time,
            },
            "tasks": {
                "create_task": self._execute_task_create_task,
                "update_task": self._execute_task_update_task,
                "complete_task": self._execute_task_complete_task,
                "assign_task": self._execute_task_assign_task,
            },
            "messages": {
                "send_message": self._execute_message_send_message,
                "schedule_message": self._execute_message_schedule_message,
                "reply_to_message": self._execute_message_reply_to_message,
            },
            "email": {
                "send_email": self._execute_email_send_email,
                "schedule_email": self._execute_email_schedule_email,
                "create_draft": self._execute_email_create_draft,
            },
            "documents": {
                "create_document": self._execute_document_create_document,
                "update_document": self._execute_document_update_document,
                "share_document": self._execute_document_share_document,
            },
            "notifications": {
                "send_notification": self._execute_notification_send_notification,
                "schedule_notification": self._execute_notification_schedule_notification,
            },
            "asana": {
                "create_task": self._execute_asana_create_task,
                "update_task": self._execute_asana_update_task,
                "create_project": self._execute_asana_create_project,
            },
            "trello": {
                "create_card": self._execute_trello_create_card,
                "update_card": self._execute_trello_update_card,
                "create_board": self._execute_trello_create_board,
            },
            "notion": {
                "create_page": self._execute_notion_create_page,
                "update_page": self._execute_notion_update_page,
                "create_database": self._execute_notion_create_database,
            },
            "dropbox": {
                "upload_file": self._execute_dropbox_upload_file,
                "download_file": self._execute_dropbox_download_file,
                "share_file": self._execute_dropbox_share_file,
            },
            "google_drive": {
                "upload_file": self._execute_gdrive_upload_file,
                "create_folder": self._execute_gdrive_create_folder,
                "share_file": self._execute_gdrive_share_file,
            },
        }

    async def execute_workflow(
        self, workflow_id: str, trigger_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a workflow with the given ID and trigger data
        """
        execution_id = str(uuid.uuid4())

        if workflow_id not in self.workflow_definitions:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow = self.workflow_definitions[workflow_id]

        execution = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "status": WorkflowStatus.RUNNING,
            "start_time": datetime.now(),
            "end_time": None,
            "current_step": 0,
            "total_steps": len(workflow.get("steps", [])),
            "trigger_data": trigger_data or {},
            "results": {},
            "errors": [],
        }

        self.active_executions[execution_id] = execution

        try:
            # Execute workflow steps
            for step_index, step in enumerate(workflow.get("steps", [])):
                execution["current_step"] = step_index + 1

                step_result = await self._execute_workflow_step(step, execution)
                execution["results"][step["id"]] = step_result

                # Check if step should stop execution
                if step.get("stop_on_failure") and not step_result.get(
                    "success", False
                ):
                    execution["status"] = WorkflowStatus.FAILED
                    execution["errors"].append(
                        f"Step {step['id']} failed and stop_on_failure is set"
                    )
                    break

            if execution["status"] == WorkflowStatus.RUNNING:
                execution["status"] = WorkflowStatus.COMPLETED

        except Exception as e:
            execution["status"] = WorkflowStatus.FAILED
            execution["errors"].append(str(e))
            logger.error(f"Workflow execution failed: {e}")

        finally:
            execution["end_time"] = datetime.now()

        return execution

    async def _execute_workflow_step(
        self, step: Dict[str, Any], execution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step
        """
        step_type = step.get("type")
        action = step.get("action")
        parameters = step.get("parameters", {})

        try:
            # Resolve dynamic parameters from previous steps
            resolved_parameters = self._resolve_parameters(
                parameters, execution["results"]
            )

            # Execute based on step type
            if step_type == "service_action":
                result = await self._execute_service_action(
                    step["service"], action, resolved_parameters
                )
            elif step_type == "condition":
                result = await self._execute_condition_step(step, execution)
            elif step_type == "delay":
                result = await self._execute_delay_step(step)
            elif step_type == "webhook":
                result = await self._execute_webhook_step(step, resolved_parameters)
            elif step_type == "data_transform":
                result = await self._execute_data_transform_step(
                    step, resolved_parameters
                )
            else:
                raise ValueError(f"Unknown step type: {step_type}")

            return {
                "success": True,
                "step_type": step_type,
                "action": action,
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Step execution failed: {e}")
            return {
                "success": False,
                "step_type": step_type,
                "action": action,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def _execute_service_action(
        self, service: str, action: str, parameters: Dict[str, Any]
    ) -> Any:
        """
        Execute a service action with real service integration
        """
        if service not in self.service_registry:
            raise ValueError(f"Service {service} not found in registry")

        if action not in self.service_registry[service]:
            raise ValueError(f"Action {action} not found for service {service}")

        action_function = self.service_registry[service][action]
        return await action_function(parameters)

    def _resolve_parameters(
        self, parameters: Dict[str, Any], previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve dynamic parameters that reference previous step results
        """
        resolved = {}

        for key, value in parameters.items():
            if (
                isinstance(value, str)
                and value.startswith("{{")
                and value.endswith("}}")
            ):
                # Extract reference: {{step_id.result_field}}
                reference = value[2:-2].strip()
                if "." in reference:
                    step_id, field = reference.split(".", 1)
                    if step_id in previous_results:
                        result_data = previous_results[step_id].get("result", {})
                        resolved[key] = self._get_nested_value(result_data, field)
                    else:
                        resolved[key] = None
                else:
                    resolved[key] = previous_results.get(reference, {}).get("result")
            else:
                resolved[key] = value

        return resolved

    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """
        Get nested value from object using dot notation
        """
        keys = path.split(".")
        current = obj

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                current = current[int(key)] if int(key) < len(current) else None
            else:
                return None

            if current is None:
                break

        return current

    async def _execute_condition_step(
        self, step: Dict[str, Any], execution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a conditional step
        """
        condition = step.get("condition")
        resolved_condition = self._resolve_parameters(
            {"cond": condition}, execution["results"]
        )["cond"]

        # Simple condition evaluation (in production, use a proper expression evaluator)
        try:
            condition_met = eval(resolved_condition, {"__builtins__": {}}, {})
        except:
            condition_met = False

        return {
            "condition_met": condition_met,
            "evaluated_condition": resolved_condition,
        }

    async def _execute_delay_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a delay step
        """
        delay_seconds = step.get("delay_seconds", 0)
        await asyncio.sleep(delay_seconds)

        return {
            "delayed_seconds": delay_seconds,
            "completed_at": datetime.now().isoformat(),
        }

    async def _execute_webhook_step(
        self, step: Dict[str, Any], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a webhook step
        """
        import aiohttp

        url = step.get("url")
        method = step.get("method", "POST")
        headers = step.get("headers", {})
        body = parameters.get("body", {})

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, json=body, headers=headers
            ) as response:
                return {
                    "status_code": response.status,
                    "response_text": await response.text(),
                    "headers": dict(response.headers),
                }

    async def _execute_data_transform_step(
        self, step: Dict[str, Any], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a data transformation step
        """
        transform_type = step.get("transform_type")
        input_data = parameters.get("input")

        if transform_type == "filter":
            condition = step.get("condition")
            filtered = [item for item in input_data if eval(condition, {"item": item})]
            return {"output": filtered}

        elif transform_type == "map":
            mapping = step.get("mapping")
            mapped = [eval(mapping, {"item": item}) for item in input_data]
            return {"output": mapped}

        elif transform_type == "aggregate":
            operation = step.get("operation")
            if operation == "sum":
                result = sum(input_data)
            elif operation == "average":
                result = sum(input_data) / len(input_data)
            elif operation == "count":
                result = len(input_data)
            else:
                result = None
            return {"output": result}

        else:
            return {"output": input_data}

    # Real Service Integration Methods

    async def _execute_calendar_create_event(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a calendar event using real calendar service"""
        try:
            from calendar_service import UnifiedCalendarService

            calendar_service = UnifiedCalendarService()
            event_data = {
                "title": parameters.get("title"),
                "description": parameters.get("description"),
                "start_time": parameters.get("start_time"),
                "end_time": parameters.get("end_time"),
                "location": parameters.get("location"),
                "attendees": parameters.get("attendees", []),
            }

            result = await calendar_service.create_event("user_id", event_data)
            return {"event_id": result.get("id"), "status": "created"}

        except Exception as e:
            logger.error(f"Calendar event creation failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_task_create_task(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a task using real task service"""
        try:
            from task_handler import create_task

            task_data = {
                "title": parameters.get("title"),
                "description": parameters.get("description"),
                "due_date": parameters.get("due_date"),
                "priority": parameters.get("priority", "medium"),
                "project": parameters.get("project"),
                "assignee": parameters.get("assignee"),
            }

            result = await create_task("user_id", task_data)
            return {"task_id": result.get("id"), "status": "created"}

        except Exception as e:
            logger.error(f"Task creation failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_message_send_message(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a message using real message service"""
        try:
            from message_handler import send_message

            message_data = {
                "platform": parameters.get("platform", "email"),
                "to": parameters.get("to"),
                "subject": parameters.get("subject"),
                "body": parameters.get("body"),
                "attachments": parameters.get("attachments", []),
            }

            result = await send_message("user_id", message_data)
            return {"message_id": result.get("id"), "status": "sent"}

        except Exception as e:
            logger.error(f"Message sending failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_email_send_email(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send an email using real email service"""
        try:
            # Import and use real email service
            from email_service import send_email

            email_data = {
                "to": parameters.get("to"),
                "subject": parameters.get("subject"),
                "body": parameters.get("body"),
                "cc": parameters.get("cc", []),
                "bcc": parameters.get("bcc", []),
                "attachments": parameters.get("attachments", []),
            }

            result = await send_email("user_id", email_data)
            return {"email_id": result.get("id"), "status": "sent"}

        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_asana_create_task(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an Asana task using real Asana service"""
        try:
            from asana_service_real import AsanaService

            asana_service = AsanaService()
            task_data = {
                "name": parameters.get("title"),
                "notes": parameters.get("description"),
                "due_on": parameters.get("due_date"),
                "assignee": parameters.get("assignee"),
                "projects": parameters.get("projects", []),
                "tags": parameters.get("tags", []),
            }

            result = await asana_service.create_task(task_data)
            return {"asana_task_id": result.get("gid"), "status": "created"}

        except Exception as e:
            logger.error(f"Asana task creation failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_trello_create_card(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a Trello card using real Trello service"""
        try:
            from trello_service_real import TrelloService

            trello_service = TrelloService()
            card_data = {
                "name": parameters.get("title"),
                "desc": parameters.get("description"),
                "due": parameters.get("due_date"),
                "idList": parameters.get("list_id"),
                "idMembers": parameters.get("members", []),
            }

            result = await trello_service.create_card(card_data)
            return {"trello_card_id": result.get("id"), "status": "created"}

        except Exception as e:
            logger.error(f"Trello card creation failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_notion_create_page(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a Notion page using real Notion service"""
        try:
            from notion_service_real import NotionService

            notion_service = NotionService()
            page_data = {
                "parent": {"database_id": parameters.get("database_id")},
                "properties": parameters.get("properties", {}),
                "children": parameters.get("children", []),
            }

            result = await notion_service.create_page(page_data)
            return {"notion_page_id": result.get("id"), "status": "created"}

        except Exception as e:
            logger.error(f"Notion page creation failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_dropbox_upload_file(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Upload a file to Dropbox using real Dropbox service"""
        try:
            from dropbox_service_real import DropboxService

            dropbox_service = DropboxService()
            upload_data = {
                "file_path": parameters.get("file_path"),
                "file_content": parameters.get("file_content"),
                "overwrite": parameters.get("overwrite", True),
            }

            result = await dropbox_service.upload_file(upload_data)
            return {"dropbox_file_id": result.get("id"), "status": "uploaded"}

        except Exception as e:
            logger.error(f"Dropbox file upload failed: {e}")
            return {"error": str(e), "status": "failed"}

    # Placeholder methods for other service actions (implementation would be similar)

    async def _execute_calendar_update_event(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "updated", "service": "calendar"}

    async def _execute_calendar_delete_event(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "deleted", "service": "calendar"}

    async def _execute_calendar_find_available_time(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"available_slots": [], "service": "calendar"}

    async def _execute_task_update_task(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "updated", "service": "tasks"}

    async def _execute_task_complete_task(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "completed", "service": "tasks"}

    async def _execute_task_assign_task(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "assigned", "service": "tasks"}

    async def _execute_message_schedule_message(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "scheduled", "service": "messages"}

    async def _execute_message_reply_to_message(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "replied", "service": "messages"}

    async def _execute_email_schedule_email(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "scheduled", "service": "email"}

    async def _execute_email_create_draft(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "draft_created", "service": "email"}

    async def _execute_document_create_document(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "created", "service": "documents"}

    async def _execute_document_update_document(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "updated", "service": "documents"}

    async def _execute_document_share_document(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "shared", "service": "documents"}

    async def _execute_notification_send_notification(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "sent", "service": "notifications"}

    async def _execute_notification_schedule_notification(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "scheduled", "service": "notifications"}

    async def _execute_asana_update_task(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "updated", "service": "asana"}

    async def _execute_asana_create_project(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "created", "service": "asana"}

    async def _execute_trello_update_card(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "updated", "service": "trello"}

    async def _execute_trello_create_board(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "created", "service": "trello"}

    async def _execute_notion_update_page(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "updated", "service": "notion"}

    async def _execute_notion_create_database(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "created", "service": "notion"}

    async def _execute_dropbox_download_file(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "downloaded", "service": "dropbox"}

    async def _execute_dropbox_share_file(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "shared", "service": "dropbox"}

    async def _execute_gdrive_upload_file(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "uploaded", "service": "google_drive"}

    async def _execute_gdrive_create_folder(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "created", "service": "google_drive"}

    async def _execute_gdrive_share_file(
        self, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"status": "shared", "service": "google_drive"}

    # Workflow Management Methods

    def register_workflow(self, workflow_id: str, workflow_definition: Dict[str, Any]):
        """Register a workflow definition"""
        self.workflow_definitions[workflow_id] = workflow_definition

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get a workflow definition"""
        return self.workflow_definitions.get(workflow_id)

    def list_workflows(self) -> List[str]:
        """List all registered workflow IDs"""
        return list(self.workflow_definitions.keys())

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a workflow execution"""
        return self.active_executions.get(execution_id)

    def list_active_executions(self) -> List[Dict[str, Any]]:
        """List all active workflow executions"""
        return list(self.active_executions.values())

    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a workflow execution"""
        if execution_id in self.active_executions:
            execution = self.active_executions[execution_id]
            if execution["status"] == WorkflowStatus.RUNNING:
                execution["status"] = WorkflowStatus.CANCELLED
                execution["end_time"] = datetime.now()
                return True
        return False


# Global instance for easy access
workflow_execution_service = WorkflowExecutionService()
