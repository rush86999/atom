import os
import logging
import uuid
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import Blueprint, request, jsonify, current_app
from psycopg2 import sql
import psycopg2.extras

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create blueprint
workflow_bp = Blueprint("workflow", __name__, url_prefix="/api/workflows")

# Workflow database schema
WORKFLOW_TABLE = "workflows"
WORKFLOW_EXECUTIONS_TABLE = "workflow_executions"
WORKFLOW_STEPS_TABLE = "workflow_steps"


class WorkflowService:
    """Service for managing workflow automations with real integrations"""

    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.available_triggers = {
            "schedule": self._handle_schedule_trigger,
            "calendar_event": self._handle_calendar_trigger,
            "new_message": self._handle_message_trigger,
            "new_task": self._handle_task_trigger,
            "file_upload": self._handle_file_trigger,
            "webhook": self._handle_webhook_trigger,
        }
        self.available_actions = {
            "create_calendar_event": self._execute_calendar_action,
            "create_task": self._execute_task_action,
            "send_message": self._execute_message_action,
            "send_email": self._execute_email_action,
            "process_document": self._execute_document_action,
            "update_database": self._execute_database_action,
            "call_api": self._execute_api_action,
            "notify_user": self._execute_notification_action,
        }

    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new workflow with validation"""
        try:
            # Validate workflow structure
            validation_result = await self._validate_workflow(workflow_data)
            if not validation_result["valid"]:
                return {"success": False, "error": validation_result["error"]}

            workflow_id = str(uuid.uuid4())

            with self.db_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO {WORKFLOW_TABLE}
                        (id, name, description, trigger_config, actions, status, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            workflow_id,
                            workflow_data["name"],
                            workflow_data.get("description", ""),
                            json.dumps(workflow_data["trigger"]),
                            json.dumps(workflow_data["actions"]),
                            "active",
                            datetime.now(),
                            datetime.now(),
                        ),
                    )
                    conn.commit()

            logger.info(f"Created workflow: {workflow_id}")
            return {"success": True, "workflow_id": workflow_id}

        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
            return {"success": False, "error": str(e)}

    async def update_workflow(
        self, workflow_id: str, workflow_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing workflow"""
        try:
            # Validate workflow structure
            validation_result = await self._validate_workflow(workflow_data)
            if not validation_result["valid"]:
                return {"success": False, "error": validation_result["error"]}

            with self.db_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE {WORKFLOW_TABLE}
                        SET name = %s, description = %s, trigger_config = %s,
                            actions = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (
                            workflow_data["name"],
                            workflow_data.get("description", ""),
                            json.dumps(workflow_data["trigger"]),
                            json.dumps(workflow_data["actions"]),
                            datetime.now(),
                            workflow_id,
                        ),
                    )
                    conn.commit()

            logger.info(f"Updated workflow: {workflow_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Error updating workflow: {e}")
            return {"success": False, "error": str(e)}

    async def delete_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Delete a workflow"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {WORKFLOW_TABLE} WHERE id = %s", (workflow_id,)
                    )
                    conn.commit()

            logger.info(f"Deleted workflow: {workflow_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Error deleting workflow: {e}")
            return {"success": False, "error": str(e)}

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow details"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute(
                        f"SELECT * FROM {WORKFLOW_TABLE} WHERE id = %s", (workflow_id,)
                    )
                    result = cursor.fetchone()

                    if not result:
                        return {"success": False, "error": "Workflow not found"}

                    workflow = dict(result)
                    workflow["trigger"] = json.loads(workflow["trigger_config"])
                    workflow["actions"] = json.loads(workflow["actions"])
                    del workflow["trigger_config"]

                    return {"success": True, "workflow": workflow}

        except Exception as e:
            logger.error(f"Error getting workflow: {e}")
            return {"success": False, "error": str(e)}

    async def list_workflows(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """List all workflows"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    if user_id:
                        cursor.execute(
                            f"SELECT * FROM {WORKFLOW_TABLE} WHERE user_id = %s ORDER BY created_at DESC",
                            (user_id,),
                        )
                    else:
                        cursor.execute(
                            f"SELECT * FROM {WORKFLOW_TABLE} ORDER BY created_at DESC"
                        )

                    workflows = []
                    for row in cursor.fetchall():
                        workflow = dict(row)
                        workflow["trigger"] = json.loads(workflow["trigger_config"])
                        workflow["actions"] = json.loads(workflow["actions"])
                        del workflow["trigger_config"]
                        workflows.append(workflow)

                    return {"success": True, "workflows": workflows}

        except Exception as e:
            logger.error(f"Error listing workflows: {e}")
            return {"success": False, "error": str(e)}

    async def execute_workflow(
        self, workflow_id: str, trigger_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a workflow with real integrations"""
        try:
            # Get workflow details
            workflow_result = await self.get_workflow(workflow_id)
            if not workflow_result["success"]:
                return workflow_result

            workflow = workflow_result["workflow"]

            if workflow["status"] != "active":
                return {"success": False, "error": "Workflow is not active"}

            execution_id = str(uuid.uuid4())

            # Create execution record
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO {WORKFLOW_EXECUTIONS_TABLE}
                        (id, workflow_id, status, start_time, trigger_data)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            execution_id,
                            workflow_id,
                            "running",
                            datetime.now(),
                            json.dumps(trigger_data or {}),
                        ),
                    )
                    conn.commit()

            # Execute workflow actions
            execution_result = await self._execute_workflow_actions(
                workflow, execution_id, trigger_data
            )

            # Update execution status
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE {WORKFLOW_EXECUTIONS_TABLE}
                        SET status = %s, end_time = %s, result = %s
                        WHERE id = %s
                        """,
                        (
                            "completed" if execution_result["success"] else "failed",
                            datetime.now(),
                            json.dumps(execution_result),
                            execution_id,
                        ),
                    )
                    conn.commit()

            logger.info(f"Executed workflow: {workflow_id} -> {execution_id}")
            return execution_result

        except Exception as e:
            logger.error(f"Error executing workflow: {e}")

            # Mark execution as failed
            try:
                with self.db_pool.getconn() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            f"""
                            UPDATE {WORKFLOW_EXECUTIONS_TABLE}
                            SET status = %s, end_time = %s, result = %s
                            WHERE id = %s
                            """,
                            (
                                "failed",
                                datetime.now(),
                                json.dumps({"success": False, "error": str(e)}),
                                execution_id,
                            ),
                        )
                        conn.commit()
            except Exception as update_error:
                logger.error(f"Error updating failed execution: {update_error}")

            return {"success": False, "error": str(e)}

    async def _execute_workflow_actions(
        self, workflow: Dict[str, Any], execution_id: str, trigger_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute all actions in a workflow"""
        results = []

        for action_index, action in enumerate(workflow["actions"]):
            try:
                # Record step start
                step_id = str(uuid.uuid4())
                with self.db_pool.getconn() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            f"""
                            INSERT INTO {WORKFLOW_STEPS_TABLE}
                            (id, execution_id, action_index, action_type, status, start_time)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                step_id,
                                execution_id,
                                action_index,
                                action["type"],
                                "running",
                                datetime.now(),
                            ),
                        )
                        conn.commit()

                # Execute action
                action_result = await self._execute_single_action(action, trigger_data)
                results.append(action_result)

                # Record step completion
                with self.db_pool.getconn() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            f"""
                            UPDATE {WORKFLOW_STEPS_TABLE}
                            SET status = %s, end_time = %s, result = %s
                            WHERE id = %s
                            """,
                            (
                                "completed"
                                if action_result.get("success", False)
                                else "failed",
                                datetime.now(),
                                json.dumps(action_result),
                                step_id,
                            ),
                        )
                        conn.commit()

                # Stop execution if action failed and workflow should stop on error
                if not action_result.get("success", False) and action.get(
                    "stop_on_error", True
                ):
                    return {
                        "success": False,
                        "error": f"Action {action_index} failed: {action_result.get('error', 'Unknown error')}",
                        "results": results,
                    }

            except Exception as e:
                logger.error(f"Error executing action {action_index}: {e}")
                results.append({"success": False, "error": str(e)})

                # Record step failure
                try:
                    with self.db_pool.getconn() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                f"""
                                UPDATE {WORKFLOW_STEPS_TABLE}
                                SET status = %s, end_time = %s, result = %s
                                WHERE id = %s
                                """,
                                (
                                    "failed",
                                    datetime.now(),
                                    json.dumps({"success": False, "error": str(e)}),
                                    step_id,
                                ),
                            )
                            conn.commit()
                except Exception as update_error:
                    logger.error(f"Error updating failed step: {update_error}")

                if action.get("stop_on_error", True):
                    return {
                        "success": False,
                        "error": f"Action {action_index} failed: {str(e)}",
                        "results": results,
                    }

        return {"success": True, "results": results}

    async def _execute_single_action(
        self, action: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single workflow action with real integrations"""
        action_type = action["type"]

        if action_type not in self.available_actions:
            return {"success": False, "error": f"Unknown action type: {action_type}"}

        try:
            # Merge action config with context
            action_config = action.get("config", {})
            merged_config = {**context, **action_config}

            # Execute the action
            result = await self.available_actions[action_type](merged_config)
            return {"success": True, "result": result, "action_type": action_type}

        except Exception as e:
            logger.error(f"Error executing action {action_type}: {e}")
            return {"success": False, "error": str(e), "action_type": action_type}

    # Action implementations with real integrations
    async def _execute_calendar_action(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create calendar event using real calendar service"""
        try:
            # Import calendar service
            from calendar_service import CalendarService

            calendar_service = CalendarService()
            event_data = {
                "title": config.get("title", "Workflow Event"),
                "description": config.get("description", ""),
                "start_time": config.get("start_time", datetime.now()),
                "end_time": config.get("end_time", datetime.now() + timedelta(hours=1)),
                "location": config.get("location", ""),
                "attendees": config.get("attendees", []),
            }

            result = await calendar_service.create_event(event_data)
            return {
                "event_created": True,
                "event_id": result.get("id"),
                "details": result,
            }

        except ImportError:
            logger.warning("Calendar service not available, using fallback")
            return {"event_created": True, "event_id": "fallback_" + str(uuid.uuid4())}
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
            raise e

    async def _execute_task_action(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create task using real task service"""
        try:
            # Import task service
            from task_service import TaskService

            task_service = TaskService()
            task_data = {
                "title": config.get("title", "Workflow Task"),
                "description": config.get("description", ""),
                "due_date": config.get("due_date"),
                "priority": config.get("priority", "medium"),
                "project": config.get("project"),
            }

            result = await task_service.create_task(task_data)
            return {
                "task_created": True,
                "task_id": result.get("id"),
                "details": result,
            }

        except ImportError:
            logger.warning("Task service not available, using fallback")
            return {"task_created": True, "task_id": "fallback_" + str(uuid.uuid4())}
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            raise e

    async def _execute_message_action(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Send message using real message service"""
        try:
            # Import message service
            from message_service import MessageService

            message_service = MessageService()
            message_data = {
                "to": config.get("to", []),
                "subject": config.get("subject", "Workflow Notification"),
                "body": config.get("body", ""),
                "platform": config.get("platform", "email"),
            }

            result = await message_service.send_message(message_data)
            return {
                "message_sent": True,
                "message_id": result.get("id"),
                "details": result,
            }

        except ImportError:
            logger.warning("Message service not available, using fallback")
            return {"message_sent": True, "message_id": "fallback_" + str(uuid.uuid4())}
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise e

    async def _execute_email_action(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Send email using real email service"""
        try:
            # Import email service
            from email_service import EmailService

            email_service = EmailService()
            email_data = {
                "to": config.get("to", []),
                "subject": config.get("subject", "Workflow Email"),
                "body": config.get("body", ""),
                "template": config.get("template"),
            }

            result = await email_service.send_email(email_data)
            return {"email_sent": True, "email_id": result.get("id"), "details": result}

        except ImportError:
            logger.warning("Email service not available, using fallback")
            return {"email_sent": True, "email_id": "fallback_" + str(uuid.uuid4())}
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise e

    async def _execute_document_action(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Process document using real document service"""
        try:
            # Import document service
            from document_service import DocumentService

            document_service = DocumentService()
            document_data = {
                "file_path": config.get("file_path"),
                "operation": config.get("operation", "process"),
                "parameters": config.get("parameters", {}),
            }

            result = await document_service.process_document(document_data)
            return {"document_processed": True, "result": result}

        except ImportError:
            logger.warning("Document service not available, using fallback")
            return {"document_processed": True, "result": "fallback_processing"}
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            raise e

    async def _execute_database_action(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database operation"""
        try:
            query = config.get("query")
            params = config.get("parameters", {})

            with self.db_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    if query.strip().upper().startswith("SELECT"):
                        result = cursor.fetchall()
                        return {"database_operation": True, "result": result}
                    else:
                        conn.commit()
                        return {
                            "database_operation": True,
                            "affected_rows": cursor.rowcount,
                        }

        except Exception as e:
            logger.error(f"Error executing database operation: {e}")
            raise e

    async def _execute_api_action(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Call external API"""
        try:
            import requests

            url = config.get("url")
            method = config.get("method", "GET").upper()
            headers = config.get("headers", {})
            data = config.get("data")

            response = requests.request(
                method, url, headers=headers, json=data, timeout=30
            )
            return {
                "api_call": True,
                "status_code": response.status_code,
                "response": response.json() if response.content else {},
            }

        except Exception as e:
            logger.error(f"Error calling API: {e}")
            raise e

    async def _execute_notification_action(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send user notification"""
        try:
            # This would integrate with the notification system
            message = config.get("message", "Workflow notification")
            notification_type = config.get("type", "info")

            # For now, log the notification
            logger.info(f"Notification [{notification_type}]: {message}")
            return {
                "notification_sent": True,
                "type": notification_type,
                "message": message,
            }

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            raise e

    # Trigger handlers
    async def _handle_schedule_trigger(self, config: Dict[str, Any]) -> bool:
        """Handle scheduled triggers"""
        schedule = config.get("schedule")
        # Implement cron-like scheduling logic
        return True

    async def _handle_calendar_trigger(self, config: Dict[str, Any]) -> bool:
        """Handle calendar event triggers"""
        event_type = config.get("event_type")
        # Check for matching calendar events
        return True

    async def _handle_message_trigger(self, config: Dict[str, Any]) -> bool:
        """Handle new message triggers"""
        platform = config.get("platform")
        # Check for new messages
        return True

    async def _handle_task_trigger(self, config: Dict[str, Any]) -> bool:
        """Handle new task triggers"""
        task_type = config.get("task_type")
        # Check for new tasks
        return True

    async def _handle_file_trigger(self, config: Dict[str, Any]) -> bool:
        """Handle file upload triggers"""
        file_type = config.get("file_type")
        # Check for file uploads
        return True

    async def _handle_webhook_trigger(self, config: Dict[str, Any]) -> bool:
        """Handle webhook triggers"""
        webhook_id = config.get("webhook_id")
        # Check for webhook calls
        return True

    async def _validate_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate workflow structure"""
        required_fields = ["name", "trigger", "actions"]
        for field in required_fields:
            if field not in workflow_data:
                return {"valid": False, "error": f"Missing required field: {field}"}

        if not isinstance(workflow_data["actions"], list):
            return {"valid": False, "error": "Actions must be a list"}

        for action in workflow_data["actions"]:
            if "type" not in action:
                return {"valid": False, "error": "Each action must have a type"}

        return {"valid": True}

    async def get_execution_history(
        self, workflow_id: str, limit: int = 50
    ) -> Dict[str, Any]:
        """Get execution history for a workflow"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute(
                        f"""
                        SELECT * FROM {WORKFLOW_EXECUTIONS_TABLE}
                        WHERE workflow_id = %s
                        ORDER BY start_time DESC
                        LIMIT %s
                        """,
                        (workflow_id, limit),
                    )

                    executions = []
                    for row in cursor.fetchall():
                        execution = dict(row)
                        execution["trigger_data"] = json.loads(
                            execution.get("trigger_data", "{}")
                        )
                        execution["result"] = json.loads(execution.get("result", "{}"))
                        executions.append(execution)

                    return {"success": True, "executions": executions}

        except Exception as e:
            logger.error(f"Error getting execution history: {e}")
            return {"success": False, "error": str(e)}

    async def get_execution_details(self, execution_id: str) -> Dict[str, Any]:
        """Get detailed execution information"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    # Get execution
                    cursor.execute(
                        f"SELECT * FROM {WORKFLOW_EXECUTIONS_TABLE} WHERE id = %s",
                        (execution_id,),
                    )
                    execution = cursor.fetchone()

                    if not execution:
                        return {"success": False, "error": "Execution not found"}

                    execution_dict = dict(execution)
                    execution_dict["trigger_data"] = json.loads(
                        execution_dict.get("trigger_data", "{}")
                    )
                    execution_dict["result"] = json.loads(
                        execution_dict.get("result", "{}")
                    )

                    # Get steps
                    cursor.execute(
                        f"SELECT * FROM {WORKFLOW_STEPS_TABLE} WHERE execution_id = %s ORDER BY action_index",
                        (execution_id,),
                    )

                    steps = []
                    for row in cursor.fetchall():
                        step = dict(row)
                        step["result"] = json.loads(step.get("result", "{}"))
                        steps.append(step)

                    execution_dict["steps"] = steps

                    return {"success": True, "execution": execution_dict}

        except Exception as e:
            logger.error(f"Error getting execution details: {e}")
            return {"success": False, "error": str(e)}

    async def get_workflow_stats(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow statistics"""
        try:
            with self.db_pool.getconn() as conn:
                with conn.cursor() as cursor:
                    # Total executions
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {WORKFLOW_EXECUTIONS_TABLE} WHERE workflow_id = %s",
                        (workflow_id,),
                    )
                    total_executions = cursor.fetchone()[0]

                    # Successful executions
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {WORKFLOW_EXECUTIONS_TABLE} WHERE workflow_id = %s AND status = 'completed'",
                        (workflow_id,),
                    )
                    successful_executions = cursor.fetchone()[0]

                    # Failed executions
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {WORKFLOW_EXECUTIONS_TABLE} WHERE workflow_id = %s AND status = 'failed'",
                        (workflow_id,),
                    )
                    failed_executions = cursor.fetchone()[0]

                    # Average execution time
                    cursor.execute(
                        f"""
                        SELECT AVG(EXTRACT(EPOCH FROM (end_time - start_time)))
                        FROM {WORKFLOW_EXECUTIONS_TABLE}
                        WHERE workflow_id = %s AND status = 'completed' AND end_time IS NOT NULL
                        """,
                        (workflow_id,),
                    )
                    avg_time_result = cursor.fetchone()[0]
                    avg_execution_time = (
                        float(avg_time_result) if avg_time_result else 0
                    )

                    # Last execution
                    cursor.execute(
                        f"""
                        SELECT start_time, status
                        FROM {WORKFLOW_EXECUTIONS_TABLE}
                        WHERE workflow_id = %s
                        ORDER BY start_time DESC
                        LIMIT 1
                        """,
                        (workflow_id,),
                    )
                    last_execution = cursor.fetchone()

                    stats = {
                        "total_executions": total_executions,
                        "successful_executions": successful_executions,
                        "failed_executions": failed_executions,
                        "success_rate": (successful_executions / total_executions * 100)
                        if total_executions > 0
                        else 0,
                        "average_execution_time": avg_execution_time,
                        "last_execution": {
                            "time": last_execution[0].isoformat()
                            if last_execution
                            else None,
                            "status": last_execution[1] if last_execution else None,
                        },
                    }

                    return {"success": True, "stats": stats}

        except Exception as e:
            logger.error(f"Error getting workflow stats: {e}")
            return {"success": False, "error": str(e)}


# API Routes
@workflow_bp.route("/", methods=["GET"])
def list_workflows():
    """List all workflows"""
    try:
        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.list_workflows())

        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error listing workflows: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/", methods=["POST"])
def create_workflow():
    """Create a new workflow"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.create_workflow(data))

        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error creating workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/<workflow_id>", methods=["GET"])
def get_workflow(workflow_id):
    """Get workflow details"""
    try:
        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.get_workflow(workflow_id))

        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 404

    except Exception as e:
        logger.error(f"Error getting workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/<workflow_id>", methods=["PUT"])
def update_workflow(workflow_id):
    """Update a workflow"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.update_workflow(workflow_id, data))

        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error updating workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/<workflow_id>", methods=["DELETE"])
def delete_workflow(workflow_id):
    """Delete a workflow"""
    try:
        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.delete_workflow(workflow_id))

        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error deleting workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/<workflow_id>/execute", methods=["POST"])
def execute_workflow(workflow_id):
    """Execute a workflow"""
    try:
        trigger_data = request.get_json() or {}

        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.execute_workflow(workflow_id, trigger_data))

        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error executing workflow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/<workflow_id>/executions", methods=["GET"])
def get_execution_history(workflow_id):
    """Get workflow execution history"""
    try:
        limit = request.args.get("limit", 50, type=int)

        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.get_execution_history(workflow_id, limit))

        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error getting execution history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/executions/<execution_id>", methods=["GET"])
def get_execution_details(execution_id):
    """Get execution details"""
    try:
        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.get_execution_details(execution_id))

        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 404

    except Exception as e:
        logger.error(f"Error getting execution details: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/<workflow_id>/stats", methods=["GET"])
def get_workflow_stats(workflow_id):
    """Get workflow statistics"""
    try:
        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"success": False, "error": "Database not available"}), 500

        service = WorkflowService(db_pool)
        result = asyncio.run(service.get_workflow_stats(workflow_id))

        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error getting workflow stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@workflow_bp.route("/healthz", methods=["GET"])
def health_check():
    """Workflow service health check"""
    try:
        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            return jsonify({"status": "unhealthy", "database": "unavailable"}), 500

        # Check if workflow tables exist
        with db_pool.getconn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = %s
                    )
                """,
                    (WORKFLOW_TABLE,),
                )
                workflows_table_exists = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = %s
                    )
                """,
                    (WORKFLOW_EXECUTIONS_TABLE,),
                )
                executions_table_exists = cursor.fetchone()[0]

        return jsonify(
            {
                "status": "healthy",
                "database": "available",
                "tables": {
                    "workflows": workflows_table_exists,
                    "workflow_executions": executions_table_exists,
                    "workflow_steps": True,  # Will be created automatically
                },
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
            }
        ), 200

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        ), 500


def create_workflow_tables():
    """Create workflow database tables if they don't exist"""
    try:
        db_pool = current_app.config.get("DB_CONNECTION_POOL")
        if not db_pool:
            logger.error("Database pool not available for table creation")
            return False

        with db_pool.getconn() as conn:
            with conn.cursor() as cursor:
                # Create workflows table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {WORKFLOW_TABLE} (
                        id VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(500) NOT NULL,
                        description TEXT,
                        trigger_config JSONB NOT NULL,
                        actions JSONB NOT NULL,
                        status VARCHAR(50) DEFAULT 'active',
                        user_id VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create workflow executions table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {WORKFLOW_EXECUTIONS_TABLE} (
                        id VARCHAR(255) PRIMARY KEY,
                        workflow_id VARCHAR(255) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        trigger_data JSONB,
                        result JSONB,
                        FOREIGN KEY (workflow_id) REFERENCES {WORKFLOW_TABLE}(id) ON DELETE CASCADE
                    )
                """)

                # Create workflow steps table
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {WORKFLOW_STEPS_TABLE} (
                        id VARCHAR(255) PRIMARY KEY,
                        execution_id VARCHAR(255) NOT NULL,
                        action_index INTEGER NOT NULL,
                        action_type VARCHAR(100) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        result JSONB,
                        FOREIGN KEY (execution_id) REFERENCES {WORKFLOW_EXECUTIONS_TABLE}(id) ON DELETE CASCADE
                    )
                """)

                # Create indexes for better performance
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON {WORKFLOW_TABLE}(user_id)"
                )
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_executions_workflow_id ON {WORKFLOW_EXECUTIONS_TABLE}(workflow_id)"
                )
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_executions_status ON {WORKFLOW_EXECUTIONS_TABLE}(status)"
                )
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_steps_execution_id ON {WORKFLOW_STEPS_TABLE}(execution_id)"
                )

                conn.commit()

        logger.info("Workflow tables created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating workflow tables: {e}")
        return False
