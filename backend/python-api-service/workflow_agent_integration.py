import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid
from nlu_bridge_service import get_nlu_bridge_service
from rrule_scheduler import get_scheduler, RRuleScheduler
from rrule_scheduler import get_scheduler, RRuleScheduler

logger = logging.getLogger(__name__)


class WorkflowAgentIntegrationService:
    """
    Integration service that connects existing workflow agents with backend workflow execution.
    This service bridges the gap between the TypeScript workflow agents and Python backend services.
    """

    def __init__(self):
        self.workflow_execution_service = None
        self.workflow_api = None
        self.initialize_services()

    def initialize_services(self):
        """Initialize backend workflow services"""
        try:
            from workflow_execution_service import workflow_execution_service
            from workflow_api import WORKFLOW_TEMPLATES, workflow_api_bp

            self.workflow_execution_service = workflow_execution_service
            self.workflow_api = workflow_api_bp
            self.workflow_templates = WORKFLOW_TEMPLATES

            logger.info("✅ Workflow services initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to initialize workflow services: {e}")
            self.workflow_execution_service = None
            self.workflow_api = None

    async def process_natural_language_workflow_request(
        self, user_input: str, user_id: str, session_id: str = None
    ) -> Dict[str, Any]:
        """
        Process natural language workflow requests from Atom Agent chat.
        This integrates with the existing workflow agents in src/nlu_agents/
        """
        try:
            # Use NLU bridge service to call TypeScript workflow agents
            nlu_bridge = await get_nlu_bridge_service()
            workflow_analysis = await nlu_bridge.analyze_workflow_request(
                user_input, user_id
            )

            if not workflow_analysis or not workflow_analysis.is_workflow_request:
                return {
                    "success": False,
                    "message": "This doesn't appear to be a workflow request. Please specify a workflow you'd like to create.",
                    "is_workflow_request": False,
                }

            # Generate workflow definition from NLU analysis
            workflow_definition = await nlu_bridge.generate_workflow_from_nlu_analysis(
                workflow_analysis
            )

            # Register the workflow
            workflow_id = workflow_definition["id"]
            self.workflow_execution_service.register_workflow(
                workflow_id, workflow_definition
            )

            # Check if this should be a scheduled workflow
            scheduled_config = await self._extract_rrule_schedule_configuration(
                user_input
            )

            response = {
                "success": True,
                "workflow_id": workflow_id,
                "workflow_name": workflow_definition["name"],
                "description": workflow_definition["description"],
                "steps_count": len(workflow_definition["steps"]),
                "is_scheduled": scheduled_config["is_scheduled"],
                "next_execution": scheduled_config["next_execution"],
                "schedule_config": scheduled_config["schedule_config"],
                "message": f"I've created a workflow '{workflow_definition['name']}' with {len(workflow_definition['steps'])} steps. Would you like me to execute it now?",
            }

            if scheduled_config["is_scheduled"]:
                response["message"] += (
                    f" This workflow is scheduled to run {scheduled_config['schedule_description']}."
                )
                if scheduled_config.get("rrule_string"):
                    response["message"] += (
                        f" Schedule: {scheduled_config['rrule_string']}"
                    )

            return response

        except Exception as e:
            logger.error(f"Error processing workflow request: {e}")
            return {
                "success": False,
                "message": f"Sorry, I encountered an error while creating your workflow: {str(e)}",
                "is_workflow_request": True,
            }

    async def _extract_rrule_schedule_configuration(
        self, user_input: str
    ) -> Dict[str, Any]:
        """Extract RRule-based schedule configuration from natural language"""
        scheduler = get_scheduler()

        try:
            # Parse natural language schedule using RRule scheduler
            schedule_config = scheduler.parse_natural_language_schedule(user_input)

            if schedule_config["is_valid"]:
                return {
                    "is_scheduled": True,
                    "schedule_type": "rrule",
                    "schedule_config": schedule_config["rrule_config"],
                    "rrule_string": schedule_config["rrule_string"],
                    "next_execution": schedule_config["next_execution"],
                    "schedule_description": f"{schedule_config['frequency']} using RRule",
                    "frequency": schedule_config["frequency"],
                }
            else:
                # Fallback to basic schedule detection
                return await self._extract_basic_schedule_configuration(user_input)

        except Exception as e:
            logger.error(f"Error extracting RRule schedule: {e}")
            # Fallback to basic schedule detection
            return await self._extract_basic_schedule_configuration(user_input)

    async def _extract_basic_schedule_configuration(
        self, user_input: str
    ) -> Dict[str, Any]:
        """Fallback basic schedule configuration extraction"""
        user_input_lower = user_input.lower()

        schedule_keywords = {
            "daily": "daily",
            "every day": "daily",
            "weekly": "weekly",
            "every week": "weekly",
            "monthly": "monthly",
            "every month": "monthly",
            "hourly": "hourly",
            "every hour": "hourly",
            "monday": "weekly",
            "tuesday": "weekly",
            "wednesday": "weekly",
            "thursday": "weekly",
            "friday": "weekly",
            "saturday": "weekly",
            "sunday": "weekly",
        }

        for keyword, schedule_type in schedule_keywords.items():
            if keyword in user_input_lower:
                next_execution = self._calculate_next_execution(schedule_type)
                return {
                    "is_scheduled": True,
                    "schedule_type": schedule_type,
                    "next_execution": next_execution,
                    "schedule_description": f"{schedule_type} starting from {next_execution}",
                }

        return {
            "is_scheduled": False,
            "schedule_type": "manual",
            "next_execution": None,
            "schedule_description": "on-demand",
        }

    def _calculate_next_execution(self, schedule_type: str) -> str:
        """Calculate next execution time based on schedule type"""
        now = datetime.now()

        if schedule_type == "daily":
            next_time = now + timedelta(days=1)
        elif schedule_type == "weekly":
            next_time = now + timedelta(weeks=1)
        elif schedule_type == "monthly":
            next_time = now + timedelta(days=30)
        elif schedule_type == "hourly":
            next_time = now + timedelta(hours=1)
        else:
            next_time = now + timedelta(days=1)

        return next_time.isoformat()

    async def execute_generated_workflow(
        self, workflow_id: str, input_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a workflow that was generated by the agent"""
        try:
            if not self.workflow_execution_service:
                return {
                    "success": False,
                    "error": "Workflow execution service not available",
                }

            workflow = self.workflow_execution_service.get_workflow(workflow_id)
            if not workflow:
                return {"success": False, "error": f"Workflow {workflow_id} not found"}

            execution_data = input_data or {}
            execution_result = await self.workflow_execution_service.execute_workflow(
                workflow_id, execution_data
            )

            return {
                "success": True,
                "execution_id": execution_result["execution_id"],
                "workflow_id": workflow_id,
                "status": execution_result["status"].value,
                "message": f"Workflow '{workflow['name']}' execution started successfully",
            }

        except Exception as e:
            logger.error(f"Error executing generated workflow: {e}")
            return {"success": False, "error": str(e)}

    async def schedule_workflow(
        self, workflow_id: str, schedule_config: Dict[str, Any], user_id: str = None
    ) -> Dict[str, Any]:
        """Schedule a workflow using RRule configuration"""
        try:
            if not self.workflow_execution_service:
                return {
                    "success": False,
                    "error": "Workflow execution service not available",
                }

            workflow = self.workflow_execution_service.get_workflow(workflow_id)
            if not workflow:
                return {"success": False, "error": f"Workflow {workflow_id} not found"}

            # Validate schedule configuration
            scheduler = get_scheduler()
            validation_result = scheduler.validate_schedule(schedule_config)

            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "error": f"Invalid schedule configuration: {validation_result.get('error', 'Unknown error')}",
                }

            # Add schedule metadata to workflow
            workflow["schedule_config"] = schedule_config
            workflow["rrule_string"] = validation_result["rrule_string"]
            workflow["cron_expression"] = scheduler.create_cron_expression(
                schedule_config
            )
            workflow["next_execution"] = validation_result["next_execution"]
            workflow["is_scheduled"] = True

            # Update workflow in execution service
            self.workflow_execution_service.register_workflow(workflow_id, workflow)

            return {
                "success": True,
                "workflow_id": workflow_id,
                "schedule_config": schedule_config,
                "rrule_string": validation_result["rrule_string"],
                "cron_expression": workflow["cron_expression"],
                "next_execution": validation_result["next_execution"],
                "message": f"Workflow '{workflow['name']}' scheduled successfully",
            }

        except Exception as e:
            logger.error(f"Error scheduling workflow: {e}")
            return {"success": False, "error": str(e)}

    async def get_schedule_suggestions(self, base_schedule: str) -> Dict[str, Any]:
        """Get schedule suggestions based on natural language input"""
        try:
            scheduler = get_scheduler()
            suggestions = scheduler.get_schedule_suggestions(base_schedule)

            return {
                "success": True,
                "base_schedule": base_schedule,
                "suggestions": suggestions,
                "total_suggestions": len(suggestions),
            }

        except Exception as e:
            logger.error(f"Error getting schedule suggestions: {e}")
            return {"success": False, "error": str(e)}

    async def schedule_workflow(
        self, workflow_id: str, schedule_config: Dict[str, Any], user_id: str = None
    ) -> Dict[str, Any]:
        """Schedule a workflow using RRule configuration"""
        try:
            if not self.workflow_execution_service:
                return {
                    "success": False,
                    "error": "Workflow execution service not available",
                }

            workflow = self.workflow_execution_service.get_workflow(workflow_id)
            if not workflow:
                return {"success": False, "error": f"Workflow {workflow_id} not found"}

            # Validate schedule configuration
            scheduler = get_scheduler()
            validation_result = scheduler.validate_schedule(schedule_config)

            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "error": f"Invalid schedule configuration: {validation_result.get('error', 'Unknown error')}",
                }

            # Add schedule metadata to workflow
            workflow["schedule_config"] = schedule_config
            workflow["rrule_string"] = validation_result["rrule_string"]
            workflow["cron_expression"] = scheduler.create_cron_expression(
                schedule_config
            )
            workflow["next_execution"] = validation_result["next_execution"]
            workflow["is_scheduled"] = True

            # Update workflow in execution service
            self.workflow_execution_service.register_workflow(workflow_id, workflow)

            return {
                "success": True,
                "workflow_id": workflow_id,
                "schedule_config": schedule_config,
                "rrule_string": validation_result["rrule_string"],
                "cron_expression": workflow["cron_expression"],
                "next_execution": validation_result["next_execution"],
                "message": f"Workflow '{workflow['name']}' scheduled successfully",
            }

        except Exception as e:
            logger.error(f"Error scheduling workflow: {e}")
            return {"success": False, "error": str(e)}

    async def get_schedule_suggestions(self, base_schedule: str) -> Dict[str, Any]:
        """Get schedule suggestions based on natural language input"""
        try:
            scheduler = get_scheduler()
            suggestions = scheduler.get_schedule_suggestions(base_schedule)

            return {
                "success": True,
                "base_schedule": base_schedule,
                "suggestions": suggestions,
                "total_suggestions": len(suggestions),
            }

        except Exception as e:
            logger.error(f"Error getting schedule suggestions: {e}")
            return {"success": False, "error": str(e)}

    async def list_ai_generated_workflows(
        self, user_id: str = None
    ) -> List[Dict[str, Any]]:
        """List workflows that were generated by AI agents"""
        try:
            if not self.workflow_execution_service:
                return []

            workflows = []
            for workflow_id in self.workflow_execution_service.list_workflows():
                workflow = self.workflow_execution_service.get_workflow(workflow_id)
                if workflow and workflow.get("is_ai_generated", False):
                    if not user_id or workflow.get("created_by") == user_id:
                        workflows.append(
                            {
                                "id": workflow_id,
                                "name": workflow.get("name", "Unnamed Workflow"),
                                "description": workflow.get("description", ""),
                                "steps_count": len(workflow.get("steps", [])),
                                "created_by": workflow.get("created_by"),
                                "created_at": workflow.get("created_at"),
                                "is_ai_generated": True,
                            }
                        )

            return workflows

        except Exception as e:
            logger.error(f"Error listing AI generated workflows: {e}")
            return []

    async def get_workflow_suggestions(
        self, user_context: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Get workflow suggestions based on user context and existing templates"""
        suggestions = []

        # Add template-based suggestions
        for template_id, template in self.workflow_templates.items():
            suggestions.append(
                {
                    "type": "template",
                    "id": template_id,
                    "name": template["name"],
                    "description": template["description"],
                    "category": template.get("category", "general"),
                    "steps_count": len(template.get("steps", [])),
                    "confidence": 0.8,
                }
            )

        # Add context-based suggestions
        if user_context:
            context_suggestions = await self._generate_context_suggestions(user_context)
            suggestions.extend(context_suggestions)

        return sorted(suggestions, key=lambda x: x.get("confidence", 0), reverse=True)[
            :5
        ]

    async def _generate_context_suggestions(
        self, user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate context-based workflow suggestions"""
        suggestions = []

        # Example context-based suggestions
        if user_context.get("has_calendar_integration"):
            suggestions.append(
                {
                    "type": "context",
                    "id": "context_meeting_followup",
                    "name": "Meeting Follow-up Automation",
                    "description": "Automatically send follow-up emails after meetings",
                    "category": "communication",
                    "confidence": 0.9,
                }
            )

        if user_context.get("has_task_management"):
            suggestions.append(
                {
                    "type": "context",
                    "id": "context_task_sync",
                    "name": "Cross-Platform Task Sync",
                    "description": "Sync tasks across all your task management platforms",
                    "category": "productivity",
                    "confidence": 0.85,
                }
            )

        if user_context.get("frequent_document_work"):
            suggestions.append(
                {
                    "type": "context",
                    "id": "context_document_processing",
                    "name": "Document Processing Pipeline",
                    "description": "Automatically process and organize uploaded documents",
                    "category": "documents",
                    "confidence": 0.8,
                }
            )

        return suggestions


# Global instance for easy access
workflow_agent_integration_service = WorkflowAgentIntegrationService()
